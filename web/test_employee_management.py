import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from werkzeug.security import check_password_hash

from app import app, db, init_db


class EmployeeManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_directory = tempfile.TemporaryDirectory()
        cls.seed_database = Path(cls.seed_directory.name) / "seed.db"
        app.config.update(TESTING=True, DATABASE=cls.seed_database)
        with app.app_context():
            init_db()

    @classmethod
    def tearDownClass(cls):
        cls.seed_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        database = Path(self.directory.name) / "employees.db"
        shutil.copyfile(self.seed_database, database)
        app.config.update(TESTING=True, DATABASE=database)
        self.client = app.test_client()
        self.client.post("/", data={"username": "admin", "password": "admin123"})
        self.client.get("/admin/employees/new")
        with self.client.session_transaction() as session:
            self.token = session["employee_csrf_token"]
        with app.app_context():
            self.users = {row["username"]: row["id"] for row in db().execute("SELECT id,username FROM users")}

    def tearDown(self):
        self.directory.cleanup()

    def details(self, **overrides):
        data = {"full_name": "New Employee", "username": "new.employee", "email": "new@example.test",
                "department": "Research", "employment_type": "Contract", "password": "Welcome-2026!",
                "annual_balance": "21", "sick_balance": "9", "casual_balance": "7", "csrf_token": self.token}
        data.update(overrides)
        return data

    def test_register_login_unique_codes_and_restart(self):
        response = self.client.post("/admin/employees/new", data=self.details(role="ADMIN", employee_code="DYO001"), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Registered New Employee (DYO021)", response.data)
        self.assertNotIn(b"Welcome-2026!", response.data)
        with app.app_context():
            person = dict(db().execute("SELECT * FROM users WHERE username='new.employee'").fetchone())
            self.assertEqual(person["role"], "EMPLOYEE")
            self.assertEqual(person["active"], 1)
            self.assertEqual((person["annual_balance"], person["sick_balance"], person["casual_balance"]), (21, 9, 7))
            self.assertEqual(person["department"], "Research")
            self.assertTrue(check_password_hash(person["password"], "Welcome-2026!"))
            self.assertNotEqual(person["password"], "Welcome-2026!")
        employee_client = app.test_client()
        employee_client.post("/", data={"username": "new.employee", "password": "Welcome-2026!"})
        self.assertEqual(employee_client.get("/schedule").status_code, 200)
        self.assertEqual(employee_client.get("/admin/employees/new").status_code, 302)
        self.client.post("/admin/employees/DYO021/remove", data={"csrf_token": self.token})
        response = self.client.post("/admin/employees/new", data=self.details(username="second.employee", email="second@example.test"))
        self.assertTrue(response.location.endswith("DYO022"))
        with app.app_context():
            before = [tuple(row) for row in db().execute("SELECT * FROM users ORDER BY id")]
            init_db()
            self.assertEqual(before, [tuple(row) for row in db().execute("SELECT * FROM users ORDER BY id")])

    def test_invalid_or_duplicate_registration_keeps_details_without_creating_accounts(self):
        invalid = ({"full_name": " "}, {"username": "bad login"}, {"username": "KAVIN"},
                   {"username": "ADMIN"}, {"email": "KAVIN@DAYORA.TEST"}, {"email": "bad@email"},
                   {"department": " "}, {"employment_type": "Manager"}, {"password": "short"},
                   {"password": "        "}, {"annual_balance": "-1"}, {"sick_balance": "1.5"},
                   {"casual_balance": "366"}, {"annual_balance": "999999999999999999999"})
        for changes in invalid:
            with self.subTest(changes=changes):
                response = self.client.post("/admin/employees/new", data=self.details(**changes))
                self.assertEqual(response.status_code, 400)
                self.assertIn(b'role="alert"', response.data)
                self.assertNotIn(b"Welcome-2026!", response.data)
                if "department" not in changes:
                    self.assertIn(b'value="Research"', response.data)
        with app.app_context():
            self.assertEqual(db().execute("SELECT COUNT(*) FROM users").fetchone()[0], 21)
        self.assertEqual(self.client.post("/admin/employees/new", data=self.details()).status_code, 302)

    def test_admin_permissions_csrf_and_removal_target(self):
        for username in (None, "Kavin"):
            client = app.test_client()
            if username:
                client.post("/", data={"username": username, "password": username})
                with client.session_transaction() as session:
                    session["role"] = "ADMIN"
            self.assertEqual(client.get("/admin/employees/new").status_code, 302)
            self.assertEqual(client.post("/admin/employees/new", data=self.details()).status_code, 302)
            self.assertEqual(client.post("/admin/employees/DYO001/remove", data={"csrf_token": self.token}).status_code, 302)
        self.assertEqual(self.client.get("/admin/employees/DYO001/remove").status_code, 405)
        for token in ("", "invalid", "invalid-✓"):
            self.assertEqual(self.client.post("/admin/employees/new", data=self.details(csrf_token=token)).status_code, 403)
            self.assertEqual(self.client.post("/admin/employees/DYO001/remove", data={"csrf_token": token}).status_code, 403)
        with app.app_context():
            db().execute("UPDATE users SET employee_code='ADMIN001' WHERE role='ADMIN'")
            db().commit()
        for code in ("missing", "ADMIN001"):
            self.assertEqual(self.client.post(f"/admin/employees/{code}/remove", data={"csrf_token": self.token}).status_code, 404)
        with app.app_context():
            self.assertEqual(db().execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0], 21)

    def test_removal_revokes_sessions_preserves_history_and_can_be_restored(self):
        employee_client = app.test_client()
        employee_client.post("/", data={"username": "Kavin", "password": "Kavin"})
        with app.app_context():
            employee_id, admin_id = self.users["Kavin"], self.users["admin"]
            db().execute("INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,days,reason) VALUES(?,'Annual','2026-01-02','2026-01-02',1,'Existing leave')", (employee_id,))
            db().execute("INSERT INTO attendance(employee_id,attendance_date,check_in,check_out) VALUES(?,'2026-01-01','09:00','18:00')", (employee_id,))
            db().execute("INSERT INTO tasks(employee_id,assigned_by,title,instructions) VALUES(?,?,'Existing task','Keep instructions')", (employee_id, admin_id))
            db().execute("INSERT INTO notifications(user_id,message) VALUES(?,'Existing notice')", (employee_id,))
            thread_id = db().execute("INSERT INTO conversations(employee_id,subject,topic) VALUES(?,'Existing thread','General question')", (employee_id,)).lastrowid
            db().execute("INSERT INTO conversation_messages(conversation_id,sender_id,body) VALUES(?,?,'Existing message')", (thread_id, employee_id))
            db().commit()
            tables = ("leave_requests", "attendance", "tasks", "notifications", "conversations", "conversation_messages")
            history = {table: [tuple(row) for row in db().execute(f"SELECT * FROM {table}")] for table in tables}
        profile = self.client.get("/admin/employees/DYO001")
        self.assertIn(b"9h 0m", profile.data)
        self.assertIn(b"Remove employee", profile.data)
        response = self.client.post("/admin/employees/DYO001/remove", data={"csrf_token": self.token}, follow_redirects=True)
        self.assertIn(b"Removed Kavin", response.data)
        self.assertNotIn(b'href="/admin/employees/DYO001"', response.data)
        self.assertIn(b'href="/admin/employees/DYO001"', self.client.get("/admin/employees?status=INACTIVE&department=Product%20Design").data)
        self.assertIn(b'href="/admin/employees/DYO001"', self.client.get("/admin/employees?status=ALL").data)
        self.assertEqual(employee_client.get("/dashboard").status_code, 302)
        with employee_client.session_transaction() as session:
            self.assertNotIn("user_id", session)
        self.assertIn(b"Invalid username or password", employee_client.post("/", data={"username": "Kavin", "password": "Kavin"}, follow_redirects=True).data)
        self.assertNotIn(b"DYO001", self.client.get(f"/admin/attendance?date={date.today().isoformat()}").data)
        self.assertIn(b"already inactive", self.client.post("/admin/employees/DYO001/remove", data={"csrf_token": self.token}, follow_redirects=True).data)
        self.assertIn(b"Employee access is disabled", self.client.get("/admin/employees/DYO001").data)
        with app.app_context():
            for table, expected in history.items():
                self.assertEqual(expected, [tuple(row) for row in db().execute(f"SELECT * FROM {table}")])
        self.client.post("/admin/employees/DYO001/update", data={"username": "Kavin", "full_name": "Kavin", "email": "kavin@dayora.test",
            "department": "Product Design", "employment_type": "Permanent", "annual_balance": "18", "sick_balance": "10", "casual_balance": "8", "active": "1"})
        employee_client.post("/", data={"username": "Kavin", "password": "Kavin"})
        self.assertEqual(employee_client.get("/dashboard").status_code, 200)

    def test_concurrent_registrations_get_distinct_employee_ids(self):
        def register(number):
            client = app.test_client()
            with client.session_transaction() as session:
                session.update(user_id=self.users["admin"], role="ADMIN", employee_csrf_token=f"registration-{number}")
            return client.post("/admin/employees/new", data=self.details(username=f"employee.{number}", email=f"employee{number}@example.test", csrf_token=f"registration-{number}"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(register, (1, 2)))
        self.assertTrue(all(response.status_code == 302 for response in responses))
        self.assertEqual({response.location for response in responses}, {"/admin/employees/DYO021", "/admin/employees/DYO022"})


if __name__ == "__main__":
    unittest.main()
