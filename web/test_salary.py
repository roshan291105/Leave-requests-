import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import app, db, init_db


class SalaryTests(unittest.TestCase):
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
        database = Path(self.directory.name) / "salary.db"
        shutil.copyfile(self.seed_database, database)
        app.config.update(TESTING=True, DATABASE=database)
        self.client = app.test_client()
        self.client.post("/", data={"username": "admin", "password": "admin123"})
        self.client.get("/admin/salary/new")
        with self.client.session_transaction() as session:
            self.token = session["salary_csrf_token"]
        with app.app_context():
            self.users = {row["username"]: row["id"] for row in db().execute("SELECT id,username FROM users")}

    def tearDown(self):
        self.directory.cleanup()

    def details(self, **changes):
        form = {"employee_id": str(self.users["Kavin"]), "salary_month": "2026-09", "basic_pay": "50000.10",
                "allowances": "1000.20", "deductions": "500.05", "status": "PENDING", "paid_on": "",
                "notes": "September salary", "csrf_token": self.token}
        form.update(changes)
        return form

    def create(self, **changes):
        return self.client.post("/admin/salary/new", data=self.details(**changes))

    def first_record(self):
        with app.app_context():
            return dict(db().execute("SELECT * FROM salary_records ORDER BY id").fetchone())

    def test_admin_creates_and_edits_exact_amounts_and_payment_details(self):
        response = self.create(net_pay="1", updated_by=str(self.users["Kavin"]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/salary?month=2026-09")
        record = self.first_record()
        self.assertEqual((record["basic_pay"], record["allowances"], record["deductions"]), (5000010, 100020, 50005))
        self.assertEqual(record["updated_by"], self.users["admin"])
        self.assertIsNone(record["paid_on"])
        page = self.client.get(response.location)
        self.assertIn("₹50,500.25", page.get_data(as_text=True))
        self.assertIn(b"Edit salary", page.data)
        self.assertEqual(page.headers["Cache-Control"], "private, no-store")
        response = self.client.post(f"/admin/salary/{record['id']}/edit", data=self.details(
            employee_id=str(self.users["Arul"]), salary_month="2026-08", basic_pay="123456.78", allowances="120.05", deductions="500.25",
            status="PAID", paid_on=date.today().isoformat(), notes="<script>secret()</script>"), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("₹1,23,076.58", response.get_data(as_text=True))
        updated = self.first_record()
        self.assertEqual(updated["employee_id"], self.users["Kavin"])
        self.assertEqual(updated["salary_month"], "2026-09")
        self.assertEqual(updated["status"], "PAID")
        self.assertEqual(updated["paid_on"], date.today().isoformat())
        employee = app.test_client()
        employee.post("/", data={"username": "Kavin", "password": "Kavin"})
        page = employee.get("/salary?month=2026-09")
        self.assertIn(b"&lt;script&gt;secret()&lt;/script&gt;", page.data)
        self.assertNotIn(b"<script>secret()</script>", page.data)
        self.client.post(f"/admin/salary/{record['id']}/edit", data=self.details(status="PENDING", paid_on=date.today().isoformat()))
        self.assertIsNone(self.first_record()["paid_on"])

    def test_employees_see_only_their_salary_and_history(self):
        self.create(notes="Kavin private September")
        self.create(salary_month="2026-08", notes="Kavin August")
        self.create(employee_id=str(self.users["Arul"]), basic_pay="98765.43", allowances="0", deductions="0", notes="Arul confidential salary")
        for username, own_note, other_note in (("Kavin", "Kavin private September", "Arul confidential salary"), ("Arul", "Arul confidential salary", "Kavin private September")):
            client = app.test_client()
            client.post("/", data={"username": username, "password": username})
            page = client.get(f"/salary?month=2026-09&employee_id={self.users['Arul']}&salary_id=3")
            self.assertEqual(page.status_code, 200)
            self.assertIn(own_note.encode(), page.data)
            self.assertNotIn(other_note.encode(), page.data)
            self.assertNotIn(b"Add salary", page.data)
            self.assertNotIn(b"Edit salary", page.data)
            self.assertNotIn(b'name="employee_id"', page.data)
            self.assertEqual(page.headers["Cache-Control"], "private, no-store")
            if username == "Kavin":
                self.assertNotIn("₹98,765.43", page.get_data(as_text=True))
                self.assertIn(b"August 2026", page.data)
            else:
                self.assertNotIn(b"August 2026", page.data)

    def test_permissions_csrf_and_unknown_records(self):
        self.create()
        record_id = self.first_record()["id"]
        for username in (None, "Kavin"):
            client = app.test_client()
            if username:
                client.post("/", data={"username": username, "password": username})
                with client.session_transaction() as session:
                    session["role"] = "ADMIN"
            else:
                self.assertEqual(client.get("/salary").status_code, 302)
            for route in ("/admin/salary/new", f"/admin/salary/{record_id}/edit"):
                self.assertEqual(client.get(route).status_code, 302)
                self.assertEqual(client.post(route, data=self.details(basic_pay="1")).status_code, 302)
            self.assertEqual(client.post("/salary", data=self.details()).status_code, 405)
        for token in ("", "wrong", "wrong-✓"):
            self.assertEqual(self.create(csrf_token=token).status_code, 403)
            self.assertEqual(self.client.post(f"/admin/salary/{record_id}/edit", data=self.details(csrf_token=token)).status_code, 403)
        self.assertEqual(self.client.get("/admin/salary/99999/edit").status_code, 404)
        self.assertEqual(self.client.post("/admin/salary/99999/edit", data=self.details()).status_code, 404)
        self.assertEqual(self.first_record()["basic_pay"], 5000010)

    def test_validation_and_duplicate_month_do_not_change_saved_salary(self):
        self.create()
        original = self.first_record()
        duplicate = self.create(basic_pay="70000")
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn(b"already exists", duplicate.data)
        bad_inputs = ({"basic_pay": "-1"}, {"allowances": "1.001"}, {"deductions": "900000"},
                      {"basic_pay": "NaN"}, {"basic_pay": "Infinity"}, {"basic_pay": "1e5"},
                      {"basic_pay": "100000000"}, {"basic_pay": ""}, {"status": "INVALID"},
                      {"status": "PAID", "paid_on": ""}, {"status": "PAID", "paid_on": "2026-02-30"},
                      {"status": "PAID", "paid_on": (date.today() + timedelta(days=1)).isoformat()}, {"notes": "a" * 1001})
        for changes in bad_inputs:
            with self.subTest(changes=changes):
                response = self.client.post(f"/admin/salary/{original['id']}/edit", data=self.details(**changes))
                self.assertEqual(response.status_code, 400)
                self.assertIn(b'role="alert"', response.data)
                self.assertEqual(self.first_record(), original)
        for changes in ({"salary_month": "2026-13"}, {"salary_month": "0000-01"}, {"salary_month": "2026-9"},
                        {"employee_id": "999999999999999999999"}, {"employee_id": "missing"},
                        {"employee_id": str(self.users["admin"])}, {"employee_id": "999999"}):
            self.assertEqual(self.create(**changes).status_code, 400)
        with app.app_context():
            self.assertEqual(db().execute("SELECT COUNT(*) FROM salary_records").fetchone()[0], 1)

    def test_empty_month_zero_pay_and_month_filters(self):
        page = self.client.get("/salary?month=2026-09")
        self.assertIn(b"No salary records yet", page.data)
        self.create(basic_pay="0", allowances="0", deductions="0")
        client = app.test_client()
        client.post("/", data={"username": "Kavin", "password": "Kavin"})
        self.assertIn("₹0.00", client.get("/salary?month=2026-09").get_data(as_text=True))
        page = client.get("/salary?month=2026-08")
        self.assertIn(b"No salary details for August 2026", page.data)
        self.assertIn(b"September 2026", page.data)
        self.assertIn(b"Choose a valid salary month", client.get("/salary?month=invalid").data)
        self.assertIn(b"No salary records yet", self.client.get("/salary?month=2026-08").data)

    def test_salary_survives_removal_restart_and_employee_cannot_reenter(self):
        self.create()
        original = self.first_record()
        client = app.test_client()
        client.post("/", data={"username": "Kavin", "password": "Kavin"})
        self.client.get("/admin/employees/DYO001")
        with self.client.session_transaction() as session:
            employee_token = session["employee_csrf_token"]
        self.client.post("/admin/employees/DYO001/remove", data={"csrf_token": employee_token})
        self.assertEqual(client.get("/salary").status_code, 302)
        self.assertIn(b"Inactive", self.client.get("/salary?month=2026-09").data)
        self.assertEqual(self.client.get(f"/admin/salary/{original['id']}/edit").status_code, 200)
        self.assertEqual(self.create(salary_month="2026-10").status_code, 302)
        with app.app_context():
            before = [tuple(row) for row in db().execute("SELECT * FROM salary_records ORDER BY id")]
            init_db()
            self.assertEqual(before, [tuple(row) for row in db().execute("SELECT * FROM salary_records ORDER BY id")])


if __name__ == "__main__":
    unittest.main()
