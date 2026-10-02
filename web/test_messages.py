import tempfile
import unittest
from pathlib import Path

from app import app, db, init_db


class MessageWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True, DATABASE=Path(self.temp_dir.name) / "messages.db")
        with app.app_context():
            init_db()
            self.users = {row["username"]: row["id"] for row in db().execute("SELECT id,username FROM users")}
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username):
        self.client.post("/logout")
        self.client.post("/", data={"username": username, "password": "admin123" if username == "admin" else username})
        response = self.client.get("/messages")
        with self.client.session_transaction() as session:
            self.token = session["message_csrf_token"]
        return response

    def send(self, **overrides):
        data = {"csrf_token": self.token, "subject": "Help with the weekly report",
                "topic": "Task clarification", "body": "Which metrics should I include?"}
        data.update(overrides)
        return self.client.post("/messages", data=data, follow_redirects=True)

    def reply(self, thread_id, body="Please include this week's attendance summary.", **overrides):
        data = {"csrf_token": self.token, "body": body}
        data.update(overrides)
        return self.client.post(f"/messages/{thread_id}", data=data, follow_redirects=True)

    def test_employee_admin_conversation_and_notifications_persist(self):
        self.assertIn(b"No conversations yet", self.login("Kavin").data)
        response = self.send(employee_id=self.users["Arul"], sender_id=self.users["admin"])
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Message sent to the admin team", response.data)
        with app.app_context():
            thread = db().execute("SELECT * FROM conversations").fetchone()
            thread_id = thread["id"]
            self.assertEqual(thread["employee_id"], self.users["Kavin"])
            self.assertEqual(db().execute("SELECT sender_id FROM conversation_messages").fetchone()[0], self.users["Kavin"])
            self.assertEqual(db().execute("SELECT user_id FROM notifications").fetchone()[0], self.users["admin"])
        self.assertIn(b"Awaiting admin", self.login("admin").data)
        self.assertIn(b"Which metrics should I include?", self.client.get(f"/messages/{thread_id}").data)
        self.assertEqual(self.reply(thread_id).status_code, 200)
        self.assertIn(b"Admin replied", self.client.get("/messages").data)
        self.login("Kavin")
        self.assertIn(b"attendance summary", self.client.get(f"/messages/{thread_id}").data)
        self.assertIn(b"Help with the weekly report", self.client.get("/notifications").data)
        self.reply(thread_id, "Thank you! I will send it today.")
        with app.app_context():
            init_db()
            self.assertEqual(db().execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 1)
            self.assertEqual(db().execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0], 3)
            self.assertEqual(db().execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 3)

    def test_other_employees_cannot_read_or_reply_and_roles_are_enforced(self):
        for method, path in (("get", "/messages"), ("post", "/messages"), ("get", "/messages/1"), ("post", "/messages/1")):
            self.assertEqual(getattr(self.client, method)(path).status_code, 302)
        self.login("Kavin")
        self.send()
        self.login("Arul")
        self.assertNotIn(b"Help with the weekly report", self.client.get("/messages").data)
        self.assertEqual(self.client.get("/messages/1").status_code, 404)
        self.assertEqual(self.reply(1).status_code, 404)
        self.assertNotIn(b"Help with the weekly report", self.client.get("/notifications").data)
        self.assertEqual(self.client.get("/messages/9999").status_code, 404)
        self.login("admin")
        self.assertEqual(self.send().status_code, 403)
        self.login("Kavin")
        with app.app_context():
            db().execute("UPDATE users SET active=0 WHERE id=?", (self.users["Kavin"],))
            db().commit()
        self.assertEqual(self.client.post("/messages/1", data={"body": "Blocked", "csrf_token": self.token}).status_code, 302)
        with app.app_context():
            self.assertEqual(db().execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0], 1)

    def test_invalid_content_and_csrf_do_not_write_partial_data(self):
        self.login("Kavin")
        for data in ({"subject": " "}, {"subject": "x" * 121}, {"topic": "invalid"}, {"body": " "}, {"body": "x" * 2001}):
            with self.subTest(data=data):
                response = self.send(**data)
                self.assertEqual(response.status_code, 400)
                self.assertIn(b'role="alert"', response.data)
        for token in ("", "invalid", "invalid-\u2713"):
            self.assertEqual(self.send(csrf_token=token).status_code, 403)
        with app.app_context():
            self.assertEqual(db().execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 0)
            self.assertEqual(db().execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0], 0)
            self.assertEqual(db().execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 0)
        self.send()
        for body in (" ", "x" * 2001):
            self.assertEqual(self.reply(1, body).status_code, 400)
        self.assertEqual(self.reply(1, csrf_token="invalid").status_code, 403)
        self.assertEqual(self.client.post("/messages/1", data={"body": "Missing CSRF"}).status_code, 403)
        with app.app_context():
            self.assertEqual(db().execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0], 1)
            self.assertEqual(db().execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 1)

    def test_message_text_is_escaped_and_invalid_reply_keeps_draft(self):
        self.login("Kavin")
        response = self.send(subject="<script>subject</script>", body="<script>alert('test')</script>\nSecond line")
        self.assertIn(b"&lt;script&gt;", response.data)
        self.assertNotIn(b"<script>alert", response.data)
        self.login("admin")
        response = self.client.get("/messages/1")
        self.assertIn(b"&lt;script&gt;", response.data)
        self.assertNotIn(b"<script>subject", response.data)
        response = self.reply(1, "Preserve this draft " + "x" * 2000)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Preserve this draft", response.data)


if __name__ == "__main__":
    unittest.main()
