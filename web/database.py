"""Database connections with a common, parameterized interface for the web app."""
from datetime import date, datetime
from decimal import Decimal
import os
import atexit
from threading import Lock
import re
import sqlite3

try:
    import psycopg
except ImportError:
    psycopg = None

try:
    from psycopg_pool import ConnectionPool
except ImportError:
    ConnectionPool = None


_pools = {}
_pool_lock = Lock()


def close_database_pools():
    """Close this process's pools on shutdown (never a parent worker's pool)."""
    with _pool_lock:
        pools = [pool for key, pool in _pools.items() if key[0] == os.getpid()]
        _pools.clear()
    for pool in pools:
        pool.close()


atexit.register(close_database_pools)


def _configure_postgres(connection, schema, timezone):
    # Run once per physical connection, not once per HTTP request.
    if schema:
        with connection.execute(
            "SELECT 1 FROM pg_namespace WHERE nspname=%s", (schema,)
        ) as cursor:
            if not cursor.fetchone():
                raise RuntimeError("Create LEAVE_DB_SCHEMA in PostgreSQL first")
        with connection.execute(
            "SELECT set_config('search_path',%s,false), "
            "set_config('TimeZone','UTC',false), set_config('dayora.timezone',%s,false)",
            (schema, timezone),
        ):
            pass
    else:
        with connection.execute(
            "SELECT set_config('TimeZone','UTC',false), set_config('dayora.timezone',%s,false)",
            (timezone,),
        ):
            pass


def _postgres_pool(dsn, schema, timezone):
    if ConnectionPool is None:
        raise RuntimeError("Install updated web/requirements.txt for PostgreSQL pooling.")
    # Lazy, per-process creation works with Flask reload and Gunicorn workers.
    key = (os.getpid(), dsn, schema, timezone)
    with _pool_lock:
        pool = _pools.get(key)
        if pool is None:
            pool = ConnectionPool(
                conninfo=dsn,
                kwargs=dict(autocommit=True, connect_timeout=5, application_name="dayora"),
                min_size=1, max_size=4, timeout=10, max_idle=60,
                max_lifetime=1800, open=False,
                configure=lambda connection: _configure_postgres(connection, schema, timezone),
                check=ConnectionPool.check_connection,
                name="dayora",
            )
            pool.open()
            _pools[key] = pool
    return pool


INTEGRITY_ERRORS = (sqlite3.IntegrityError,) + ((psycopg.IntegrityError,) if psycopg else ())
IDENTITY_TABLES = frozenset(("users", "leave_requests", "notifications", "tasks", "personal_checklist",
                           "conversations", "conversation_messages", "attendance", "salary_records"))


class SQLiteConnection(sqlite3.Connection):
    backend = "sqlite"

    def columns(self, table):
        if not re.fullmatch(r"[a-z_]+", table):
            raise ValueError("Invalid table name")
        return {row["name"] for row in self.execute(f'PRAGMA table_info("{table}")')}

    def begin_write(self):
        self.execute("BEGIN IMMEDIATE")

    def local_date(self, column):
        return f"date({column},'localtime')"


def postgres_parameters(statement):
    """Translate positional placeholders without changing quoted SQL literals."""
    parts = re.split(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|--[^\n]*|/\*[\s\S]*?\*/)", statement)
    return "".join(part.replace("%", "%%").replace("?", "%s") if index % 2 == 0
                   else part.replace("%", "%%") for index, part in enumerate(parts))


class Row:
    """Support the named and positional access used by sqlite3.Row callers."""
    def __init__(self, columns, values):
        self._columns = columns
        self._values = tuple(self._value(value) for value in values)

    @staticmethod
    def _value(value):
        if isinstance(value, datetime):
            return value.isoformat(sep=" ")
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal) and value == value.to_integral_value():
            return int(value)
        return value

    def keys(self):
        return self._columns

    def __getitem__(self, key):
        return self._values[self._columns.index(key)] if isinstance(key, str) else self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class Cursor:
    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def fetchone(self):
        values = self.cursor.fetchone()
        return None if values is None else Row([column.name for column in self.cursor.description], values)

    def fetchall(self):
        columns = [column.name for column in self.cursor.description]
        return [Row(columns, values) for values in self.cursor.fetchall()]

    def __iter__(self):
        while (row := self.fetchone()) is not None:
            yield row


class PostgresConnection:
    backend = "postgresql"

    def __init__(self, dsn):
        if psycopg is None:
            raise RuntimeError("PostgreSQL needs psycopg. Install web/requirements.txt first.")
        self._write_locked = False
        self._pool = None
        self._closed = False
        schema = os.getenv("LEAVE_DB_SCHEMA", "").strip()
        timezone = os.getenv("LEAVE_TIMEZONE", "Asia/Kolkata")
        if schema and not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
            raise ValueError("Invalid LEAVE_DB_SCHEMA")
        if os.getenv("LEAVE_DB_POOL", "1") != "0":
            self._pool = _postgres_pool(dsn, schema, timezone)
            self.raw = self._pool.getconn()
        else:
            self.raw = psycopg.connect(dsn, autocommit=True, connect_timeout=5, application_name="dayora")
            try:
                _configure_postgres(self.raw, schema, timezone)
            except Exception:
                self.raw.close()
                raise

    @property
    def in_transaction(self):
        return self.raw.info.transaction_status != psycopg.pq.TransactionStatus.IDLE

    def execute(self, statement, parameters=()):
        sql = statement.strip().rstrip(";")
        executable = re.sub(r"\A(?:\s|--[^\n]*(?:\n|$)|/\*[\s\S]*?\*/)*", "", sql)
        operation = executable.split(None, 1)[0].upper() if executable else ""
        if operation in ("INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP", "TRUNCATE"):
            self.begin_write()
        match = re.match(r"INSERT\s+INTO\s+([a-z_]+)\b", sql, re.I)
        generated_id = bool(match and match[1].lower() in IDENTITY_TABLES and not re.search(r"\bRETURNING\b", sql, re.I))
        if generated_id:
            sql += " RETURNING id"
        cursor = self.raw.execute(postgres_parameters(sql), tuple(parameters))
        lastrowid = None
        if generated_id:
            row = cursor.fetchone()
            lastrowid = row[0] if row else None
        return Cursor(cursor, lastrowid)

    def executemany(self, statement, parameters):
        count = 0
        for values in parameters:
            cursor = self.execute(statement, values)
            count += cursor.rowcount
            cursor.cursor.close()
        return count

    def executescript(self, script):
        # Application schema files contain plain DDL, without procedural blocks.
        self.commit()
        try:
            self.begin_write()
            for statement in script.split(";"):
                if statement.strip():
                    self.execute(statement).cursor.close()
            self.commit()
        except Exception:
            self.rollback()
            raise

    def columns(self, table):
        return {row[0] for row in self.raw.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s", (table,))}

    def begin_write(self):
        if not self.in_transaction:
            self.raw.execute("BEGIN").close()
        # Preserve the serialized read-modify-write operations previously guarded by SQLite's write lock.
        if not self._write_locked:
            self.raw.execute("SELECT pg_advisory_xact_lock(748231905)").close()
            self._write_locked = True

    def local_date(self, column):
        return f"CAST(CAST({column} AS timestamptz) AT TIME ZONE current_setting('dayora.timezone') AS date)"

    def commit(self):
        self.raw.commit()
        self._write_locked = False

    def rollback(self):
        self.raw.rollback()
        self._write_locked = False

    def close(self):
        if self._closed:
            return
        self._closed = True
        connection = self.raw
        try:
            # An early return or exception must not commit an unfinished write.
            if not connection.closed and self.in_transaction:
                connection.rollback()
        except Exception:
            connection.close()
        finally:
            self._write_locked = False
            self.raw = None
            if self._pool is not None:
                self._pool.putconn(connection)
            else:
                connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.rollback() if exc_type else self.commit()


def connect_database(target):
    if str(target).startswith(("postgresql://", "postgres://")):
        return PostgresConnection(str(target))
    connection = sqlite3.connect(target, factory=SQLiteConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
