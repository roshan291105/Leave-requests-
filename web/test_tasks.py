import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from app import app, db, init_db


class TaskWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True, DATABASE=Path(self.temp_dir.name) / "tasks.db")
        with app.app_context():
            init_db()
            self.users = {row["username"]: row["id"] for row in db().execute("SELECT id,username FROM users")}
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username):
        self.client.post("/logout")
        self.client.post("/", data={"username": username, "password": "admin123" if username == "admin" else username})
        response = self.client.get("/tasks")
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session:
            self.token = session["task_csrf_token"]
        return response

    def assign(self, **overrides):
        data = {"employee_id": str(self.users["Kavin"]), "title": "Prepare the weekly report",
                "instructions": "Collect project updates.\nShare the report with the team.",
                "due_date": (date.today() + timedelta(days=3)).isoformat(), "csrf_token": self.token}
        data.update(overrides)
        return self.client.post("/admin/tasks/assign", data=data, follow_redirects=True)

    def update(self, task_id, status):
        return self.client.post(f"/tasks/{task_id}/status", data={"status": status, "csrf_token": self.token}, follow_redirects=True)

    def test_assignment_delivery_and_progress_round_trip(self):
        self.assertIn(b"No tasks yet", self.login("admin").data)
        response = self.assign()
        self.assertIn(b"Task assigned to Kavin", response.data)
        with app.app_context():
            task = db().execute("SELECT * FROM tasks").fetchone()
            task_id = task["id"]
            self.assertEqual(task["assigned_by"], self.users["admin"])
            self.assertEqual(task["status"], "TODO")
            notice = db().execute("SELECT * FROM notifications").fetchone()
            self.assertEqual(notice["user_id"], self.users["Kavin"])
            self.assertIn("Prepare the weekly report", notice["message"])
        employee_page = self.login("Kavin")
        self.assertIn(b"Share the report with the team", employee_page.data)
        self.assertNotIn(b"Choose an employee", employee_page.data)
        self.assertIn(b"Prepare the weekly report", self.client.get("/notifications").data)
        for status in ("IN_PROGRESS", "COMPLETED"):
            self.assertEqual(self.update(task_id, status).status_code, 200)
        self.update(task_id, "COMPLETED")
        with app.app_context():
            self.assertEqual(db().execute("SELECT status FROM tasks").fetchone()[0], "COMPLETED")
            self.assertEqual(db().execute("SELECT COUNT(*) FROM notifications WHERE user_id=?", (self.users["admin"],)).fetchone()[0], 2)
            # Schema initialization must preserve saved work on restart.
            init_db()
            self.assertEqual(db().execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()[0], "COMPLETED")
        self.assertIn(b"Completed", self.login("admin").data)

    def test_roles_ownership_missing_tasks_and_csrf(self):
        self.assertEqual(self.client.get("/tasks").status_code, 302)
        self.assertEqual(self.client.post("/admin/tasks/assign").status_code, 302)
        self.login("admin")
        self.assertEqual(self.assign(csrf_token="invalid").status_code, 403)
        self.assertEqual(self.assign(csrf_token="invalid-✓").status_code, 403)
        self.assign()
        with app.app_context():
            task_id = db().execute("SELECT id FROM tasks").fetchone()[0]
        self.update(task_id, "COMPLETED")  # Admins cannot impersonate the employee.
        page = self.login("Arul")
        self.assertNotIn(b"Prepare the weekly report", page.data)
        self.assertNotIn(b"Prepare the weekly report", self.client.get("/notifications").data)
        self.assertEqual(self.update(task_id, "COMPLETED").status_code, 404)
        self.assign(title="Unauthorized assignment")
        self.login("Kavin")
        self.assertEqual(self.update(task_id, "INVALID").status_code, 400)
        self.assertEqual(self.update(99999, "COMPLETED").status_code, 404)
        self.assertEqual(self.client.post(f"/tasks/{task_id}/status", data={"status": "COMPLETED"}).status_code, 403)
        with app.app_context():
            rows = db().execute("SELECT * FROM tasks").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "TODO")
            self.assertEqual(db().execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 1)

    def test_validation_rejects_bad_assignments_without_notifications(self):
        self.login("admin")
        with app.app_context():
            db().execute("UPDATE users SET active=0 WHERE username='Arul'")
            db().commit()
        cases = [
            {"employee_id": ""}, {"employee_id": "invalid"}, {"employee_id": "9" * 40},
            {"employee_id": str(self.users["admin"])}, {"employee_id": str(self.users["Arul"])},
            {"employee_id": "999999"}, {"title": "   "}, {"title": "x" * 121},
            {"instructions": "   "}, {"instructions": "x" * 2001},
            {"due_date": "2026-02-30"}, {"due_date": "bad-date"},
            {"due_date": (date.today() - timedelta(days=1)).isoformat()},
        ]
        for values in cases:
            with self.subTest(values=values):
                response = self.assign(**values)
                self.assertEqual(response.status_code, 400)
                self.assertIn(b'role="alert"', response.data)
        with app.app_context():
            self.assertEqual(db().execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 0)
            self.assertEqual(db().execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 0)

    def test_optional_due_date_and_escaped_instructions(self):
        self.login("admin")
        self.assertEqual(self.assign(due_date="", instructions="<script>alert('test')</script>\nKeep this literal.").status_code, 200)
        response = self.login("Kavin")
        self.assertIn(b"No due date", response.data)
        self.assertIn(b"&lt;script&gt;", response.data)
        self.assertNotIn(b"<script>alert", response.data)
        with app.app_context():
            self.assertIsNone(db().execute("SELECT due_date FROM tasks").fetchone()[0])

    def test_random_assignment_duration_and_employee_visibility(self):
        self.login("admin")
        with app.app_context():
            db().execute("UPDATE users SET active=0 WHERE username='Arul'")
            db().commit()

        def choose_kavin(employees):
            self.assertNotIn(self.users['Arul'], [row['id'] for row in employees])
            self.assertNotIn(self.users['admin'], [row['id'] for row in employees])
            return next(row for row in employees if row['id'] == self.users['Kavin'])

        with patch('app.secrets.choice', side_effect=choose_kavin) as random_choice:
            response = self.assign(employee_id='AUTO', duration_hours='2.75')
            self.assertEqual(response.status_code, 200)
            random_choice.assert_called_once()
        with app.app_context():
            task = db().execute('SELECT * FROM tasks').fetchone()
            self.assertEqual(task['employee_id'], self.users['Kavin'])
            self.assertEqual(task['duration_minutes'], 165)
        page = self.login('Kavin')
        self.assertIn(b'Estimated duration: 2.75 hours', page.data)
        self.assertNotIn(b'Shuffle pending tasks', page.data)
        self.assertNotIn(b'name="duration_hours"', page.data)

    def test_shuffle_random_rounds_duration_order_and_protected_work(self):
        self.login('admin')
        with app.app_context():
            db().execute("UPDATE users SET active=0 WHERE role='EMPLOYEE' AND username NOT IN ('Kavin','Arul')")
            for duration in (15, 60, 120, 30, 90):
                db().execute("INSERT INTO tasks(employee_id,assigned_by,title,instructions,duration_minutes,due_date) VALUES(?,?,?,?,?,?)",
                             (self.users['Nila'], self.users['admin'], f'Task {duration}', 'Instructions', duration, '2030-01-01'))
            for status in ('IN_PROGRESS', 'COMPLETED'):
                db().execute("INSERT INTO tasks(employee_id,assigned_by,title,instructions,status,duration_minutes) VALUES(?,?,?,?,?,?)",
                             (self.users['Kavin'], self.users['admin'], status, 'Instructions', status, 300))
            db().commit()
            protected = [tuple(row) for row in db().execute("SELECT * FROM tasks WHERE status<>'TODO'")]
        rounds = []

        def shuffle_in_fixed_order(rotation):
            rounds.append(list(rotation))
            rotation[:] = [self.users['Arul'], self.users['Kavin']]

        with patch('app.secrets.SystemRandom') as randomizer:
            randomizer.return_value.shuffle.side_effect = shuffle_in_fixed_order
            response = self.client.post('/admin/tasks/shuffle', data={'csrf_token': self.token}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'5 reassigned', response.data)
        self.assertEqual(len(rounds), 3)
        with app.app_context():
            pending = db().execute("SELECT * FROM tasks WHERE status='TODO' ORDER BY duration_minutes DESC").fetchall()
            self.assertEqual([row['employee_id'] for row in pending], [self.users[name] for name in ('Kavin','Arul','Kavin','Arul','Kavin')])
            self.assertTrue(all(row['due_date'] == '2030-01-01' and row['assigned_by'] == self.users['admin'] for row in pending))
            self.assertEqual(protected, [tuple(row) for row in db().execute("SELECT * FROM tasks WHERE status<>'TODO'")])
            self.assertEqual(db().execute('SELECT COUNT(*) FROM notifications').fetchone()[0], 10)

    def test_automation_permissions_validation_and_no_employees(self):
        self.assertEqual(self.client.post('/admin/tasks/shuffle').status_code, 302)
        self.login('Kavin')
        self.assertEqual(self.client.post('/admin/tasks/shuffle', data={'csrf_token': self.token}).status_code, 302)
        self.assign(employee_id='AUTO')
        self.login('admin')
        self.assertEqual(self.client.get('/admin/tasks/shuffle').status_code, 405)
        self.assertEqual(self.client.post('/admin/tasks/shuffle').status_code, 403)
        self.assertEqual(self.assign(employee_id='AUTO', csrf_token='bad').status_code, 403)
        for duration in ('', '0', '-1', 'NaN', 'Infinity', '1.1', '1001', '1e2'):
            self.assertEqual(self.assign(employee_id='AUTO', duration_hours=duration).status_code, 400)
        with app.app_context():
            self.assertEqual(db().execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 0)
            self.assertEqual(db().execute('SELECT COUNT(*) FROM notifications').fetchone()[0], 0)
            db().execute("UPDATE users SET active=0 WHERE role='EMPLOYEE'")
            db().commit()
        self.assertEqual(self.assign(employee_id='AUTO').status_code, 400)
        self.assertEqual(self.client.post('/admin/tasks/shuffle', data={'csrf_token': self.token}).status_code, 400)

    def test_duration_migration_preserves_existing_tasks(self):
        self.login('admin')
        self.assign(title='Existing work')
        with app.app_context():
            db().execute('ALTER TABLE tasks DROP COLUMN duration_minutes')
            db().commit()
            init_db()
            task = dict(db().execute('SELECT * FROM tasks').fetchone())
            self.assertEqual(task['title'], 'Existing work')
            self.assertEqual(task['duration_minutes'], 60)
            init_db()
            self.assertEqual(task, dict(db().execute('SELECT * FROM tasks').fetchone()))

    def test_empty_and_unchanged_shuffle_do_not_notify(self):
        self.login('admin')
        response = self.client.post('/admin/tasks/shuffle', data={'csrf_token': self.token}, follow_redirects=True)
        self.assertIn(b'0 reassigned', response.data)
        self.assign(duration_hours='0.25')
        with app.app_context():
            db().execute("UPDATE users SET active=0 WHERE role='EMPLOYEE' AND username<>'Kavin'")
            db().commit()
        response = self.client.post('/admin/tasks/shuffle', data={'csrf_token': self.token}, follow_redirects=True)
        self.assertIn(b'0 reassigned', response.data)
        with app.app_context():
            self.assertEqual(db().execute('SELECT COUNT(*) FROM notifications').fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
