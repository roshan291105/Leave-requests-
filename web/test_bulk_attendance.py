import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import app, db, init_db


class BulkAttendanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True, DATABASE=Path(self.directory.name) / "attendance.db")
        with app.app_context():
            init_db()
            self.users = {row["username"]: row["id"] for row in db().execute("SELECT id,username FROM users")}
        self.client = app.test_client()
        self.day = date.today() - timedelta(days=date.today().weekday())
        self.login("admin", "admin123")
        self.client.get("/admin/attendance", query_string={"date": self.day.isoformat()})
        with self.client.session_transaction() as session:
            self.token = session["attendance_csrf_token"]

    def tearDown(self):
        self.directory.cleanup()

    def login(self, username, password):
        self.client.post("/logout")
        self.client.post("/", data={"username": username, "password": password})

    def mark_all(self, **overrides):
        data = {"attendance_date": self.day.isoformat(), "department": "ALL", "csrf_token": self.token}
        data.update(overrides)
        return self.client.post("/admin/attendance/mark-all-present", data=data, follow_redirects=True)

    def test_marks_only_unrecorded_active_employees_and_preserves_records_on_repeat(self):
        with app.app_context():
            db().execute("UPDATE work_schedule SET start_time='08:30' WHERE weekday=0")
            for name, status, check_in, check_out in (
                ("Kavin", "PRESENT", "08:15:00", "17:00:00"),
                ("Arul", "LATE", "10:00:00", None),
                ("Nila", "ABSENT", "", None),
            ):
                db().execute("INSERT INTO attendance(employee_id,attendance_date,check_in,check_out,status) VALUES(?,?,?,?,?)",
                             (self.users[name], self.day.isoformat(), check_in, check_out, status))
            db().execute("UPDATE users SET active=0 WHERE username='Kayal'")
            for name, status in (("Thamizh", "APPROVED"), ("Ezhil", "PENDING")):
                db().execute("""INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,days,reason,status)
                    VALUES(?,'Annual',?,?,1,'Leave request',?)""", (self.users[name], self.day.isoformat(), self.day.isoformat(), status))
            db().commit()
            original = {row["employee_id"]: tuple(row) for row in db().execute("SELECT * FROM attendance")}
        response = self.mark_all()
        self.assertIn(b"Marked 15 employees as present", response.data)
        with app.app_context():
            records = db().execute("SELECT * FROM attendance ORDER BY id").fetchall()
            self.assertEqual(len(records), 18)
            ids = {row["employee_id"] for row in records}
            self.assertTrue(ids.isdisjoint({self.users["Thamizh"], self.users["Kayal"], self.users["admin"]}))
            self.assertIn(self.users["Ezhil"], ids)
            for row in records:
                if row["employee_id"] in original:
                    self.assertEqual(tuple(row), original[row["employee_id"]])
                else:
                    self.assertEqual(row["status"], "PRESENT")
                    self.assertEqual(row["check_in"], "08:30:00")
                    self.assertIsNone(row["check_out"])
            snapshot = [tuple(row) for row in records]
        response = self.mark_all()
        self.assertIn(b"No unmarked employees are available", response.data)
        with app.app_context():
            self.assertEqual(snapshot, [tuple(row) for row in db().execute("SELECT * FROM attendance ORDER BY id")])

    def test_department_and_date_scope_are_preserved(self):
        other_date = (self.day - timedelta(days=1)).isoformat()
        with app.app_context():
            expected = {row["id"] for row in db().execute("SELECT id FROM users WHERE role='EMPLOYEE' AND department='Engineering'")}
            db().execute("INSERT INTO attendance(employee_id,attendance_date,check_in,status) VALUES(?,?,?,'ABSENT')",
                         (self.users["Kavin"], other_date, ""))
            db().commit()
        response = self.mark_all(department="Engineering")
        self.assertIn("department=Engineering", response.request.url)
        self.assertIn(f"date={self.day.isoformat()}", response.request.url)
        with app.app_context():
            actual = {row["employee_id"] for row in db().execute("SELECT employee_id FROM attendance WHERE attendance_date=?", (self.day.isoformat(),))}
            self.assertEqual(actual, expected)
            self.assertEqual(db().execute("SELECT status FROM attendance WHERE attendance_date=?", (other_date,)).fetchone()[0], "ABSENT")

    def test_permissions_csrf_and_invalid_input_cannot_mark_attendance(self):
        self.client.post("/logout")
        self.assertEqual(self.client.post("/admin/attendance/mark-all-present").status_code, 302)
        self.login("Kavin", "Kavin")
        self.assertEqual(self.client.post("/admin/attendance/mark-all-present").status_code, 302)
        self.login("admin", "admin123")
        self.client.get("/admin/attendance")
        with self.client.session_transaction() as session:
            self.token = session["attendance_csrf_token"]
        self.assertEqual(self.client.get("/admin/attendance/mark-all-present").status_code, 405)
        for token in ("", "invalid", "invalid-✓"):
            self.assertEqual(self.mark_all(csrf_token=token).status_code, 403)
        for invalid_date in ("", "invalid", "2026-02-30"):
            self.assertIn(b"Select a valid attendance date", self.mark_all(attendance_date=invalid_date).data)
        future_date = (date.today() + timedelta(days=1)).isoformat()
        self.assertIn(b"cannot be marked for a future date", self.mark_all(attendance_date=future_date).data)
        self.assertIn(b"Select a valid department", self.mark_all(department="Missing department").data)
        with app.app_context():
            self.assertEqual(db().execute("SELECT COUNT(*) FROM attendance").fetchone()[0], 0)

    def test_default_time_and_disabled_empty_or_future_dates(self):
        with app.app_context():
            db().execute("UPDATE work_schedule SET start_time=NULL,end_time=NULL,is_working_day=0 WHERE weekday=0")
            db().commit()
        self.assertIn(b"Marked 20 employees as present", self.mark_all().data)
        with app.app_context():
            self.assertEqual({row[0] for row in db().execute("SELECT check_in FROM attendance")}, {"09:00:00"})
        page = self.client.get("/admin/attendance", query_string={"date": self.day.isoformat()})
        self.assertIn(b'disabled>Mark all present</button>', page.data)
        future = self.client.get("/admin/attendance", query_string={"date": (date.today() + timedelta(days=1)).isoformat()})
        self.assertIn(b'disabled>Mark all present</button>', future.data)
        self.assertIn(b"Choose today or an earlier date", future.data)


if __name__ == "__main__":
    unittest.main()
