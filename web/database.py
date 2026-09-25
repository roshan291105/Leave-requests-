"""Database connections with a common, parameterized interface for the web app."""
from datetime import date, datetime
from decimal import Decimal
import os
import re
import sqlite3

try:
    import psycopg
except ImportError:
    psycopg = None

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
        self.raw = psycopg.connect(dsn, autocommit=True, connect_timeout=5, application_name="dayora")
        self._write_locked = False
        self.raw.execute("SELECT set_config('TimeZone','UTC',false), set_config('dayora.timezone',%s,false)",
                         (os.getenv("LEAVE_TIMEZONE", "Asia/Kolkata"),)).close()

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
        self.raw.close()

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
