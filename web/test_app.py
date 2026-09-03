import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import app, db, init_db
from werkzeug.security import check_password_hash


class LeaveWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True, DATABASE=Path(self.temp_dir.name) / "test.db")
        with app.app_context():
            init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username, password):
        return self.client.post("/", data={"username": username, "password": password}, follow_redirects=True)

    def logout(self):
        return self.client.post("/logout", follow_redirects=True)

    def future_dates(self, offset=2):
        start = date.today() + timedelta(days=offset)
        return start.isoformat(), (start + timedelta(days=2)).isoformat()

    def test_employee_can_login_apply_and_cancel(self):
        response = self.login("employee", "employee123")
        self.assertIn(b'data-time-greeting', response.data)
        self.assertIn(b'data-name="Alex"', response.data)
        start, end = self.future_dates()
        response = self.client.post("/leave/apply", data={
            "leave_type": "Annual", "start_date": start, "end_date": end,
            "reason": "Family holiday"
        }, follow_redirects=True)
        self.assertIn(b"submitted", response.data)
        with app.app_context():
            leave = db().execute("SELECT * FROM leave_requests").fetchone()
            self.assertEqual(leave["status"], "PENDING")
            leave_id = leave["id"]
        response = self.client.post(f"/leave/{leave_id}/cancel", follow_redirects=True)
        self.assertIn(b"cancelled", response.data)

    def test_admin_approval_updates_balance_and_notification(self):
        self.login("employee", "employee123")
        start, end = self.future_dates(8)
        self.client.post("/leave/apply", data={"leave_type":"Annual","start_date":start,"end_date":end,"reason":"Family travel"})
        self.logout(); self.login("admin", "admin123")
        with app.app_context():
            leave_id = db().execute("SELECT id FROM leave_requests").fetchone()["id"]
        response = self.client.post(f"/admin/leave/{leave_id}/decide", data={"status":"APPROVED","comment":"Enjoy your break"}, follow_redirects=True)
        self.assertIn(b"approved", response.data)
        with app.app_context():
            employee = db().execute("SELECT annual_balance FROM users WHERE username='employee'").fetchone()
            notice = db().execute("SELECT n.message FROM notifications n JOIN users u ON u.id=n.user_id WHERE u.username='employee'").fetchone()
            self.assertEqual(employee["annual_balance"], 15)
            self.assertIn("approved", notice["message"])

    def test_validation_permissions_and_filters(self):
        self.assertEqual(self.client.get("/dashboard").status_code, 302)
        self.login("employee", "employee123")
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        response = self.client.post("/leave/apply", data={"leave_type":"Invalid","start_date":yesterday,"end_date":yesterday,"reason":"Invalid request"}, follow_redirects=True)
        self.assertIn(b"cannot be in the past", response.data)
        self.logout(); self.login("admin", "admin123")
        self.assertEqual(self.client.get("/admin/requests?status=UNKNOWN").status_code, 200)

    def test_signout_clears_session_and_protects_pages(self):
        self.login("employee", "employee123")
        response = self.client.post("/logout", follow_redirects=True)
        self.assertIn(b"signed out successfully", response.data)
        self.assertEqual(self.client.get("/dashboard").status_code, 302)
        self.assertEqual(self.client.get("/logout").status_code, 405)

    def test_admin_has_visible_approve_and_reject_actions(self):
        self.login("employee", "employee123")
        start, end = self.future_dates(14)
        self.client.post("/leave/apply", data={"leave_type":"Sick","start_date":start,"end_date":end,"reason":"Medical recovery"})
        self.logout(); self.login("admin", "admin123")
        dashboard = self.client.get("/dashboard")
        self.assertIn(b"Approve", dashboard.data)
        self.assertIn(b"Reject", dashboard.data)
        self.assertIn(b'data-time-greeting', dashboard.data)
        self.assertIn(b'data-name="Roshan"', dashboard.data)
        self.assertIn(b"DYO001", dashboard.data)
        self.assertIn(b"Permanent", dashboard.data)
        with app.app_context():
            leave_id = db().execute("SELECT id FROM leave_requests").fetchone()["id"]
        self.client.post(f"/admin/leave/{leave_id}/decide", data={"status":"REJECTED"})
        with app.app_context():
            leave = db().execute("SELECT status FROM leave_requests WHERE id=?", (leave_id,)).fetchone()
            self.assertEqual(leave["status"], "REJECTED")

    def test_employee_directory_contains_twenty_members(self):
        self.login("admin", "admin123")
        response = self.client.get("/admin/employees")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"20 people, one team", response.data)
        with app.app_context():
            people = db().execute("SELECT username,password FROM users WHERE role='EMPLOYEE'").fetchall()
            self.assertEqual(len(people), 20)
            self.assertTrue(all(check_password_hash(person["password"], "employee123") for person in people))
            types = {row[0] for row in db().execute("SELECT DISTINCT employment_type FROM users WHERE role='EMPLOYEE'").fetchall()}
            self.assertEqual(types, {"Permanent", "Contract", "Intern", "Part-time", "Probation"})

    def test_admin_can_view_and_manage_complete_employee_profile(self):
        self.login("admin", "admin123")
        profile = self.client.get("/admin/employees/DYO003")
        self.assertEqual(profile.status_code, 200)
        self.assertIn(b"data-back-button", profile.data)
        self.assertIn(b'data-fallback="/dashboard"', profile.data)
        self.assertIn(b"Priya Sharma", profile.data)
        self.assertIn(b"LEAVE HISTORY", profile.data)
        self.assertIn(b"ATTENDANCE HISTORY", profile.data)
        response = self.client.post("/admin/employees/DYO003/update", data={
            "username":"priya.new", "full_name":"Priya Sharma", "email":"priya.sharma@dayora.test",
            "department":"Engineering", "employment_type":"Permanent",
            "annual_balance":"20", "sick_balance":"9", "casual_balance":"7", "active":"1"
        }, follow_redirects=True)
        self.assertIn(b"Updated Priya Sharma", response.data)
        self.client.post("/admin/employees/DYO003/reset-password")
        with app.app_context():
            person = db().execute("SELECT * FROM users WHERE employee_code='DYO003'").fetchone()
            self.assertEqual(person["annual_balance"], 20)
            self.assertEqual(person["email"], "priya.sharma@dayora.test")
            self.assertEqual(person["username"], "priya.new")
            self.assertTrue(check_password_hash(person["password"], "employee123"))
            notice = db().execute("SELECT message FROM notifications WHERE user_id=?", (person["id"],)).fetchone()
            self.assertIn("login ID from priya to priya.new", notice["message"])
        self.logout()
        old_login = self.login("priya", "employee123")
        self.assertIn(b"Invalid username or password", old_login.data)
        self.login("priya.new", "employee123")
        self.assertEqual(self.client.get("/admin/employees/DYO003").status_code, 302)

    def test_admin_center_is_protected_and_updates_schedule(self):
        self.login("employee", "employee123")
        self.assertEqual(self.client.get("/admin/center").status_code, 302)
        self.logout(); self.login("admin", "admin123")
        center = self.client.get("/admin/center")
        self.assertEqual(center.status_code, 200)
        self.assertIn(b"ADMINISTRATOR ACCESS ONLY", center.data)
        schedule_data = {}
        for weekday in range(7):
            if weekday < 6:
                schedule_data[f"working_{weekday}"] = "1"
                schedule_data[f"start_{weekday}"] = "08:30" if weekday == 0 else "09:00"
                schedule_data[f"end_{weekday}"] = "17:30" if weekday == 0 else ("13:00" if weekday == 5 else "18:00")
        response = self.client.post("/admin/center/schedule", data=schedule_data, follow_redirects=True)
        self.assertIn(b"employees notified", response.data)
        with app.app_context():
            monday = db().execute("SELECT * FROM work_schedule WHERE weekday=0").fetchone()
            sunday = db().execute("SELECT * FROM work_schedule WHERE weekday=6").fetchone()
            self.assertEqual(monday["start_time"], "08:30")
            self.assertEqual(sunday["is_working_day"], 0)
            employee_notices = db().execute("SELECT COUNT(*) FROM notifications n JOIN users u ON u.id=n.user_id WHERE u.role='EMPLOYEE'").fetchone()[0]
            self.assertEqual(employee_notices, 20)
        self.logout(); self.login("employee", "employee123")
        schedule = self.client.get("/schedule")
        self.assertEqual(schedule.status_code, 200)
        self.assertIn(b"08:30", schedule.data)
        notices = self.client.get("/notifications")
        self.assertIn(b"Work schedule updated by Roshan", notices.data)

    def test_notifications_are_delivered_and_can_be_managed(self):
        self.login("employee", "employee123")
        start, end = self.future_dates(20)
        self.client.post("/leave/apply", data={"leave_type":"Casual","start_date":start,"end_date":end,"reason":"Personal appointment"})
        self.logout(); self.login("admin", "admin123")
        api = self.client.get("/api/notifications/unread")
        self.assertEqual(api.get_json()["count"], 1)
        page = self.client.get("/notifications")
        self.assertIn(b"Alex Morgan (DYO001, Permanent) requested", page.data)
        self.client.post("/notifications/read-all")
        self.assertEqual(self.client.get("/api/notifications/unread").get_json()["count"], 0)
        self.client.post("/notifications/clear-read")
        with app.app_context():
            admin = db().execute("SELECT id FROM users WHERE username='admin'").fetchone()
            total = db().execute("SELECT COUNT(*) FROM notifications WHERE user_id=?", (admin["id"],)).fetchone()[0]
            self.assertEqual(total, 0)

    def test_admin_marks_and_corrects_employee_attendance(self):
        attendance_day = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        self.login("employee", "employee123")
        denied = self.client.post("/admin/attendance/DYO001/mark", data={"attendance_date":attendance_day,"status":"PRESENT"})
        self.assertEqual(denied.status_code, 302)
        self.logout(); self.login("admin", "admin123")
        response = self.client.post("/admin/attendance/DYO001/mark", data={
            "attendance_date": attendance_day, "status": "PRESENT",
            "check_in": "09:00", "check_out": "17:30"
        }, follow_redirects=True)
        self.assertIn(b"Marked Alex Morgan as present", response.data)
        with app.app_context():
            record = db().execute("SELECT * FROM attendance").fetchone()
            self.assertEqual(record["status"], "PRESENT")
            self.assertEqual(record["check_out"], "17:30:00")
        register = self.client.get(f"/admin/attendance?date={attendance_day}")
        self.assertEqual(register.status_code, 200)
        self.assertIn(b"Alex Morgan", register.data)
        self.assertIn(b"19", register.data)
        self.assertIn(b"Seven-day attendance pattern", register.data)
        self.client.post("/admin/attendance/DYO001/mark", data={
            "attendance_date":attendance_day, "status":"PRESENT",
            "check_in":"10:30", "check_out":"18:00"
        })
        with app.app_context():
            record = db().execute("SELECT * FROM attendance").fetchone()
            schedule = db().execute("SELECT * FROM work_schedule WHERE weekday=0").fetchone()
            self.assertEqual(record["status"], "LATE")
            self.assertEqual(schedule["start_time"], "09:00")
        self.client.post("/admin/attendance/DYO001/mark", data={
            "attendance_date":attendance_day, "status":"ABSENT"
        })
        with app.app_context():
            record = db().execute("SELECT * FROM attendance").fetchone()
            self.assertEqual(record["status"], "ABSENT")
        self.client.post("/admin/attendance/DYO001/mark", data={
            "attendance_date":attendance_day, "action":"clear"
        })
        with app.app_context():
            self.assertEqual(db().execute("SELECT COUNT(*) FROM attendance").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
