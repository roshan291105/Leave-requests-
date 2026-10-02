"""Create PostgreSQL storage, copy SQLite data, and activate only after verification."""
import argparse
from contextlib import closing
from datetime import datetime
from getpass import getpass
import json
import os
import re
from pathlib import Path
import sqlite3
from urllib.parse import quote

from dotenv import load_dotenv, set_key
import psycopg
from psycopg import sql

from database import IDENTITY_TABLES

BASE_DIR = Path(__file__).resolve().parent
TABLES = ("users", "leave_requests", "notifications", "tasks", "personal_checklist",
          "conversations", "conversation_messages", "attendance", "work_schedule",
          "salary_records", "department_salary_defaults", "admin_reminder_settings",
          "admin_reminder_reviews", "app_migrations")


def configured_url():
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    host = os.getenv("PGHOST", "127.0.0.1")

    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    user = quote(os.getenv("PGUSER", "postgres"), safe="")

    password = os.getenv("PGPASSWORD", "")
    password = quote(password, safe="")

    port = int(os.getenv("PGPORT", "5432"))

    database = quote(
        os.getenv("PGDATABASE", "dayora"),
        safe=""
    )

    return (
        f"postgresql://{user}:{password}"
        f"@{host}:{port}/{database}"
    )


def ensure_database(dsn):
    parameters = psycopg.conninfo.conninfo_to_dict(dsn)
    name = parameters["dbname"]
    if name in ("postgres", "template0", "template1"):
        raise ValueError("Choose a dedicated application database, for example PGDATABASE=dayora.")
    parameters["dbname"] = "postgres"
    with psycopg.connect(**parameters, autocommit=True, connect_timeout=5) as connection:
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def configure_schema(connection):
    schema_name = os.getenv("LEAVE_DB_SCHEMA", "").strip()
    if schema_name:
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema_name):
            raise ValueError("Invalid LEAVE_DB_SCHEMA")
        if not connection.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (schema_name,)).fetchone():
            raise ValueError("Create LEAVE_DB_SCHEMA in PostgreSQL first")
        connection.execute("SELECT set_config('search_path',%s,true)", (schema_name,))


def migrate(source_path, dsn, backup_dir):
    """Copy a consistent backup, preserving IDs, password hashes, and all saved values.

    The website must be stopped during the final migration to prevent later SQLite writes.
    A nonempty destination is always refused; no existing data is overwritten.
    """
    source_path, backup_dir = Path(source_path).resolve(), Path(backup_dir)
    if not source_path.is_file():
        raise ValueError(f"SQLite source does not exist: {source_path}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"leave-before-postgres-{datetime.now():%Y%m%d-%H%M%S-%f}.db"
    with closing(sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(backup)) as snapshot:
            source.backup(snapshot)

    with closing(sqlite3.connect(backup)) as source, psycopg.connect(dsn, connect_timeout=5) as target:
        target.execute("SET TIME ZONE 'UTC'")
        configure_schema(target)
        target.execute("SELECT pg_advisory_xact_lock(748231905)")
        source_tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        unknown = source_tables - set(TABLES)
        if unknown:
            raise ValueError("Unrecognized SQLite tables; migration stopped: " + ", ".join(sorted(unknown)))
        if "users" not in source_tables:
            raise ValueError("Source is not a Dayora database (users table missing).")
        existing = {row[0] for row in target.execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()")}
        if existing - set(TABLES):
            raise ValueError("Destination contains unrelated tables; choose an empty database.")
        for table in existing:
            if target.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier(table))).fetchone():
                raise ValueError(f"Destination table {table} already contains data; nothing was overwritten.")
        schema = (BASE_DIR.parent / "database" / "postgresql_schema.sql").read_text(encoding="utf-8")
        target.execute(schema)
        counts = {}
        for table in TABLES:
            if table not in source_tables:
                counts[table] = 0
                continue
            rows = source.execute(f'SELECT * FROM "{table}"')
            columns = [column[0] for column in rows.description]
            values = rows.fetchall()
            identifiers = sql.SQL(",").join(map(sql.Identifier, columns))
            placeholders = sql.SQL(",").join(sql.Placeholder() for _ in columns)
            if values:
                with target.cursor() as cursor:
                    cursor.executemany(sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        sql.Identifier(table), identifiers, placeholders), values)
            # Full-value comparison also checks balances, money, IDs, and password hashes.
            copied = target.execute(sql.SQL("SELECT {} FROM {}").format(identifiers, sql.Identifier(table))).fetchall()
            if sorted(values, key=repr) != sorted(copied, key=repr):
                raise ValueError(f"Verification failed for {table}; PostgreSQL changes rolled back.")
            counts[table] = len(copied)
        for table in IDENTITY_TABLES:
            maximum = target.execute(sql.SQL("SELECT MAX(id) FROM {}").format(sql.Identifier(table))).fetchone()[0]
            target.execute("SELECT setval(pg_get_serial_sequence(%s,'id'),%s,%s)",
                           (table, max(maximum or 1, 1), maximum is not None))
    return backup, counts


def activate(dsn, env_path=BASE_DIR / ".env"):
    set_key(str(env_path), "DATABASE_URL", dsn)
    params = psycopg.conninfo.conninfo_to_dict(dsn)
    server = {"Servers": {"1": {"Name": "Dayora", "Group": "Servers",
              "Host": params.get("host", "127.0.0.1"), "Port": int(params.get("port", 5432)),
              "MaintenanceDB": params["dbname"], "Username": params.get("user", "postgres"),
              "SSLMode": params.get("sslmode", "prefer")}}}
    (BASE_DIR / "pgadmin-server.json").write_text(json.dumps(server, indent=2) + "\n", encoding="utf-8")


def check(dsn):
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        configure_schema(connection)
        name, version = connection.execute("SELECT current_database(), current_setting('server_version')").fetchone()
        print(f"Connected to PostgreSQL {version}, database: {name}")
        for table in TABLES:
            count = connection.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))).fetchone()[0]
            print(f"  {table}: {count}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the configured PostgreSQL connection and table counts")
    parser.add_argument("--source", type=Path, default=BASE_DIR / "leave.db")
    args = parser.parse_args()
    load_dotenv(BASE_DIR / ".env", override=True)
    dsn = configured_url()
    try:
        if args.check:
            check(dsn)
            return 0
        if not os.getenv("PGPASSWORD") and not psycopg.conninfo.conninfo_to_dict(dsn).get("password"):
            password = getpass("Local PostgreSQL password (hidden): ")
            if not password:
                raise ValueError("Enter the PostgreSQL password in web/.env before running setup.")
            os.environ["PGPASSWORD"] = password
            set_key(str(BASE_DIR / ".env"), "PGPASSWORD", password)
        print("Keep the website stopped until setup completes.")
        ensure_database(dsn)
        backup, counts = migrate(args.source.resolve(), dsn, BASE_DIR / "backups")
        activate(dsn)
        print(f"Migrated and verified {sum(counts.values())} rows in {len(counts)} tables.")
        print(f"SQLite backup: {backup}")
        print("PostgreSQL is configured. Start the website with web/run.ps1.")
        return 0
    except (ValueError, psycopg.Error, sqlite3.Error, OSError) as error:
        # Connection errors can include user/host information but never echo a password-bearing URL.
        message = str(error)
        for secret in (os.getenv("PGPASSWORD"), dsn):
            if secret:
                message = message.replace(secret, "[redacted]")
        print(f"Setup did not complete: {message}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
