import tempfile
import unittest
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from app import app, db, init_db
from demo_employees import DEMO_EMPLOYEES, MIGRATION_NAME, seed_demo_employees


class EmployeeNameTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True, DATABASE=Path(self.directory.name) / "names.db")
        with app.app_context():
            init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def test_every_employee_can_log_in_with_their_name_and_reset_uses_name(self):
        for _legacy, name, _department, _type in DEMO_EMPLOYEES:
            self.client.post("/logout")
            response = self.client.post("/", data={"username": name, "password": name}, follow_redirects=True)
            self.assertIn(f'data-name="{name}"'.encode(), response.data)
        self.client.post("/logout")
        for username, password in (("employee", "employee123"), ("kavin", "Kavin"), ("Kavin", "kavin")):
            response = self.client.post("/", data={"username": username, "password": password}, follow_redirects=True)
            self.assertIn(b"Invalid username or password", response.data)
        self.client.post("/", data={"username": "Kavin", "password": "Kavin"})
        with self.client.session_transaction() as session:
            session["name"] = "Alex Morgan"
        self.assertIn(b'data-name="Kavin"', self.client.get("/dashboard").data)
        self.client.post("/logout")
        self.client.post("/", data={"username": "admin", "password": "admin123"})
        with app.app_context():
            db().execute("UPDATE users SET password=? WHERE username='Kavin'", (generate_password_hash("different-password"),))
            db().commit()
        directory = self.client.get("/admin/employees")
        self.assertNotIn(b'data-password="Kavin"', directory.data)
        self.assertIn(b'data-password="Nila"', directory.data)
        reset = self.client.post("/admin/employees/DYO001/reset-password", follow_redirects=True)
        self.assertIn(b"Password reset to Kavin", reset.data)
        with app.app_context():
            stored = db().execute("SELECT password FROM users WHERE username='Kavin'").fetchone()[0]
            self.assertNotEqual(stored, "Kavin")
            self.assertTrue(check_password_hash(stored, "Kavin"))

    def test_upgrade_preserves_ids_records_balances_and_duplicate_accounts(self):
        with app.app_context():
            connection = db()
            connection.execute("DELETE FROM app_migrations WHERE name=?", (MIGRATION_NAME,))
            connection.execute("DROP INDEX idx_employee_code")
            old_password = generate_password_hash("employee123")
            for number, (legacy, _name, _department, _type) in enumerate(DEMO_EMPLOYEES, 1):
                connection.execute("UPDATE users SET username=?,full_name=?,password=? WHERE employee_code=?",
                                   (legacy, legacy.title() + " Legacy", old_password, f"DYO{number:03d}"))
            connection.execute("UPDATE users SET username='edited-login',email='personal@example.test',annual_balance=25,active=0 WHERE employee_code='DYO003'")
            duplicate_id = connection.execute("""INSERT INTO users(username,password,full_name,email,department,role,employee_code)
                VALUES('extra-login',?,'Duplicate Employee','extra@dayora.test','Engineering','EMPLOYEE','DYO017')""", (old_password,)).lastrowid
            admin_id = connection.execute("SELECT id FROM users WHERE role='ADMIN'").fetchone()[0]
            employee_id = connection.execute("SELECT id FROM users WHERE employee_code='DYO001'").fetchone()[0]
            connection.execute("""INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,days,reason)
                VALUES(?,'Annual','2026-10-01','2026-10-01',1,'Existing leave')""", (employee_id,))
            connection.execute("INSERT INTO tasks(employee_id,assigned_by,title,instructions) VALUES(?,?,?,?)",
                               (duplicate_id, admin_id, "Existing task", "Keep these instructions"))
            connection.execute("INSERT INTO attendance(employee_id,attendance_date,check_in) VALUES(?,'2026-09-01','09:00')", (duplicate_id,))
            connection.execute("INSERT INTO notifications(user_id,message) VALUES(?,'Existing notification')", (duplicate_id,))
            connection.commit()
            records = {table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
                       for table in ("tasks", "leave_requests", "attendance", "notifications")}
            before = {row["id"]: dict(row) for row in connection.execute("SELECT * FROM users")}
            seed_demo_employees(connection)
            after = {row["id"]: dict(row) for row in connection.execute("SELECT * FROM users")}
            self.assertEqual(before.keys(), after.keys())
            self.assertEqual(before[admin_id], after[admin_id])
            for user_id, person in before.items():
                for field in ("annual_balance", "sick_balance", "casual_balance", "active", "employment_type", "department"):
                    self.assertEqual(person[field], after[user_id][field])
            for table, expected in records.items():
                self.assertEqual(expected, [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")])
            self.assertEqual(after[duplicate_id]["full_name"], "Mugilan")
            self.assertEqual(after[duplicate_id]["employee_code"], "DYO021")
            self.assertEqual(after[employee_id]["username"], "Kavin")
            self.assertEqual(connection.execute("SELECT email FROM users WHERE employee_code='DYO003'").fetchone()[0], "personal@example.test")
            for person in after.values():
                if person["role"] == "EMPLOYEE":
                    self.assertEqual(person["username"], person["full_name"])
                    self.assertTrue(check_password_hash(person["password"], person["full_name"]))
            seed_demo_employees(connection)
            self.assertEqual(after, {row["id"]: dict(row) for row in connection.execute("SELECT * FROM users")})

    def test_restart_preserves_later_profile_and_password_edits(self):
        with app.app_context():
            password = generate_password_hash("updated-password")
            db().execute("UPDATE users SET username='Kavin.new',password=?,annual_balance=27 WHERE employee_code='DYO001'", (password,))
            db().commit()
            before = [tuple(row) for row in db().execute("SELECT * FROM users ORDER BY id")]
            init_db()
            self.assertEqual(before, [tuple(row) for row in db().execute("SELECT * FROM users ORDER BY id")])

    def test_migration_conflict_does_not_change_existing_accounts(self):
        with app.app_context():
            db().execute("DELETE FROM app_migrations WHERE name=?", (MIGRATION_NAME,))
            db().execute("UPDATE users SET username='employee' WHERE employee_code='DYO001'")
            db().execute("""INSERT INTO users(username,password,full_name,email,department,role)
                VALUES('Kavin',?,'Another Administrator','another@example.test','People Operations','ADMIN')""",
                         (generate_password_hash("separate-password"),))
            db().commit()
            before = [tuple(row) for row in db().execute("SELECT * FROM users ORDER BY id")]
            with self.assertRaisesRegex(ValueError, "non-employee account"):
                seed_demo_employees(db())
            self.assertEqual(before, [tuple(row) for row in db().execute("SELECT * FROM users ORDER BY id")])
            self.assertIsNone(db().execute("SELECT 1 FROM app_migrations WHERE name=?", (MIGRATION_NAME,)).fetchone())


if __name__ == "__main__":
    unittest.main()
