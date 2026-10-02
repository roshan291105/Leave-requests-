"""Run existing website workflows against disposable PostgreSQL databases.

Set DAYORA_TEST_POSTGRES_URL to a test server connection whose role has CREATEDB.
Only randomly named databases created by this suite are removed.
"""
from datetime import date, timedelta
from contextlib import closing
import importlib
import os
import sqlite3
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

import psycopg
from psycopg import sql

from app import app, db, init_db
from database import Row, postgres_parameters, close_database_pools
from postgres_setup import migrate

TEST_SERVER = os.getenv("DAYORA_TEST_POSTGRES_URL")
TEMPLATE = "dayora_test_" + uuid4().hex


def test_url(name):
    parameters = psycopg.conninfo.conninfo_to_dict(TEST_SERVER)
    parameters["dbname"] = name
    # The app distinguishes PostgreSQL URLs from SQLite paths.
    from urllib.parse import quote
    host = parameters.get('host', '127.0.0.1')
    user = quote(parameters.get('user', 'postgres'), safe='')
    password = ':' + quote(parameters['password'], safe='') if parameters.get('password') else ''
    return f"postgresql://{user}{password}@{host}:{parameters.get('port', '5432')}/{name}"


def server_sql(statement):
    with psycopg.connect(TEST_SERVER, autocommit=True) as connection:
        connection.execute(statement)


def setUpModule():
    if not TEST_SERVER:
        return
    server_sql(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEMPLATE)))
    app.config.update(TESTING=True, DATABASE=test_url(TEMPLATE))
    with app.app_context():
        init_db()
    close_database_pools()


def tearDownModule():
    if TEST_SERVER:
        close_database_pools()
        server_sql(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(TEMPLATE)))


class DatabaseAdapterTests(unittest.TestCase):
    def test_bound_parameters_preserve_literals_comments_and_percent(self):
        self.assertEqual(postgres_parameters("SELECT '?' AS x, ? AS y, '90%' AS z -- ?\n"),
                         "SELECT '?' AS x, %s AS y, '90%%' AS z -- ?\n")

    def test_row_supports_templates_dict_and_positional_access(self):
        row = Row(['id', 'name'], [3, 'Test'])
        self.assertEqual(dict(row), {'id': 3, 'name': 'Test'})
        self.assertEqual(tuple(row), (3, 'Test'))
        self.assertEqual(row[0], row['id'])


class PostgresFixture:
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.database_name = "dayora_test_" + uuid4().hex
        server_sql(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
            sql.Identifier(self.database_name), sql.Identifier(TEMPLATE)))
        self.addCleanup(lambda: server_sql(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(self.database_name))))
        self.addCleanup(close_database_pools)
        app.config.update(TESTING=True, DATABASE=test_url(self.database_name))
        self.client = app.test_client()
        with app.app_context():
            self.users = {row['username']: row['id'] for row in db().execute('SELECT id,username FROM users')}
        if self.initial_page:
            self.client.post('/', data={'username': 'admin', 'password': 'admin123'})
            self.day = date.today() - timedelta(days=date.today().weekday())
            self.client.get(self.initial_page, query_string={'date': self.day.isoformat(), 'month': '2026-09'})
            with self.client.session_transaction() as session:
                self.token = session[self.token_name]

    def tearDown(self):
        pass


# Exercise the same assertions on both backends without changing SQLite fixtures.
if TEST_SERVER:
    for module_name, class_name, page, token_name in (
        ('test_app', 'LeaveWorkflowTests', '', ''),
        ('test_tasks', 'TaskWorkflowTests', '', ''),
        ('test_messages', 'MessageWorkflowTests', '', ''),
        ('test_my_day', 'MyDayTests', '', ''),
        ('test_employee_names', 'EmployeeNameTests', '', ''),
        ('test_employee_management', 'EmployeeManagementTests', '/admin/employees/new', 'employee_csrf_token'),
        ('test_salary', 'SalaryTests', '/admin/salary/new', 'salary_csrf_token'),
        ('test_department_salary', 'DepartmentSalaryTests', '/salary', 'salary_csrf_token'),
        ('test_bulk_attendance', 'BulkAttendanceTests', '/admin/attendance', 'attendance_csrf_token'),
        ('test_reminders', 'AdminReminderTests', '/dashboard', 'reminder_csrf_token'),
    ):
        original = getattr(importlib.import_module(module_name), class_name)
        globals()['Postgres' + class_name] = type('Postgres' + class_name, (PostgresFixture, original),
            {'__module__': __name__, 'initial_page': page, 'token_name': token_name})
    del original


@unittest.skipUnless(TEST_SERVER, 'Set DAYORA_TEST_POSTGRES_URL to run PostgreSQL migration checks')
class PostgresMigrationTests(PostgresFixture, unittest.TestCase):
    initial_page = ''

    def test_invalid_source_rolls_back_every_target_table(self):
        destination = test_url(self.database_name)
        with psycopg.connect(destination) as connection:
            connection.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'invalid.db'
            with closing(sqlite3.connect(source)) as connection:
                connection.executescript("""
                    CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,password TEXT,
                        full_name TEXT,email TEXT,department TEXT,role TEXT);
                    INSERT INTO users VALUES(1,'example','hash','Example','example@test.local','Test','ADMIN');
                    CREATE TABLE notifications(id INTEGER PRIMARY KEY,user_id INTEGER,message TEXT);
                    INSERT INTO notifications VALUES(1,999,'Missing user');
                """)
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                migrate(source, destination, Path(directory) / 'backups')
            with psycopg.connect(destination) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0], 0)

    def test_migration_verifies_all_values_and_refuses_nonempty_target(self):
        destination = test_url(self.database_name)
        # This database belongs exclusively to this test, and was created above.
        with psycopg.connect(destination) as connection:
            connection.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.db'
            app.config['DATABASE'] = source
            with app.app_context():
                init_db()
                with db():
                    admin, employee = self.users['admin'], self.users['Kavin']
                    db().execute("INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,days,reason) VALUES(?,'Annual','2026-12-01','2026-12-01',1,'Keep leave')", (employee,))
                    db().execute("INSERT INTO notifications(user_id,message) VALUES(?,'Keep notice')", (employee,))
                    db().execute("INSERT INTO tasks(employee_id,assigned_by,title,instructions) VALUES(?,?,'Keep task','Instructions')", (employee,admin))
                    db().execute("INSERT INTO personal_checklist(employee_id,title) VALUES(?,'Private checklist')", (employee,))
                    thread = db().execute("INSERT INTO conversations(employee_id,subject,topic) VALUES(?,'Keep conversation','General question')", (employee,)).lastrowid
                    db().execute("INSERT INTO conversation_messages(conversation_id,sender_id,body) VALUES(?,?,'Keep reply')", (thread,employee))
                    db().execute("INSERT INTO attendance(employee_id,attendance_date,check_in) VALUES(?,'2026-09-01','09:00:00')", (employee,))
                    db().execute("INSERT INTO salary_records(employee_id,salary_month,basic_pay,updated_by) VALUES(?,'2026-09',9999999999,?)", (employee,admin))
                    db().execute("INSERT INTO admin_reminder_settings(admin_id,salary_day) VALUES(?,28)", (admin,))
                    db().execute("INSERT INTO admin_reminder_reviews(admin_id,kind,period) VALUES(?,'tasks','2026-09-01')", (admin,))
            before = source.read_bytes()
            backup, counts = migrate(source, destination, Path(directory) / 'backups')
            self.assertTrue(backup.is_file())
            self.assertEqual(len(counts), 14)
            self.assertTrue(all(counts.values()))
            self.assertEqual(source.read_bytes(), before)
            app.config['DATABASE'] = destination
            with app.app_context():
                old_users = [tuple(row) for row in db().execute('SELECT * FROM users ORDER BY id')]
                init_db()
                self.assertEqual(old_users, [tuple(row) for row in db().execute('SELECT * FROM users ORDER BY id')])
                with db():
                    self.assertGreater(db().execute("INSERT INTO notifications(user_id,message) VALUES(?,'New notice')", (employee,)).lastrowid, 1)
                with self.assertRaises(psycopg.IntegrityError):
                    with db():
                        db().execute("INSERT INTO salary_records(employee_id,salary_month,basic_pay,updated_by) VALUES(?,'2026-09',1,?)", (employee,admin))
                self.assertEqual(db().execute('SELECT COUNT(*) FROM salary_records').fetchone()[0], 1)
            with self.assertRaisesRegex(ValueError, 'already contains data'):
                migrate(source, destination, Path(directory) / 'backups')


if __name__ == '__main__':
    unittest.main()
