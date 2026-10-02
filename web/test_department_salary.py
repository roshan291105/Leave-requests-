import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from werkzeug.datastructures import MultiDict

from app import app, db, init_db, salary_payroll_rows


class DepartmentSalaryTests(unittest.TestCase):
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
        database = Path(self.directory.name) / "departments.db"
        shutil.copyfile(self.seed_database, database)
        app.config.update(TESTING=True, DATABASE=database)
        self.client = app.test_client()
        self.client.post("/", data={"username": "admin", "password": "admin123"})
        self.client.get("/salary?month=2026-09")
        with self.client.session_transaction() as session:
            self.token = session["salary_csrf_token"]
        with app.app_context():
            self.users = {row["username"]: row["id"] for row in db().execute("SELECT id,username FROM users")}

    def tearDown(self):
        self.directory.cleanup()

    def selection(self, names=None, department="ALL", month="2026-09"):
        with app.app_context():
            rows = salary_payroll_rows(month, department)
        chosen = [row for row in rows if row["payable"] and (names is None or row["employee_id"] in {self.users[name] for name in names})]
        data = MultiDict({"csrf_token": self.token, "salary_month": month, "department": department, "paid_on": date.today().isoformat()})
        for row in chosen:
            data.add("employee_id", str(row["employee_id"]))
            data[f"preview_{row['employee_id']}"] = row["preview_token"]
        return data

    def records(self):
        with app.app_context():
            return [dict(row) for row in db().execute("SELECT * FROM salary_records ORDER BY id")]

    def rate_form(self, **changes):
        with app.app_context():
            rates = db().execute("SELECT department,basic_pay FROM department_salary_defaults ORDER BY department").fetchall()
        form = MultiDict({"csrf_token": self.token})
        for row in rates:
            form.add("department", row["department"])
            form.add("basic_pay", changes.get(row["department"], f"{row['basic_pay'] // 100}.{row['basic_pay'] % 100:02d}"))
        return form

    def test_department_defaults_edit_persist_and_do_not_reprice_saved_salary(self):
        page = self.client.get("/admin/salary/departments")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'value="35000.00"', page.data)
        self.assertIn(b'value="20000.00"', page.data)
        self.client.post("/admin/salary/pay-selected", data=self.selection(["Kavin"]))
        before = self.records()
        response = self.client.post("/admin/salary/departments", data=self.rate_form(**{"Product Design": "27500.25"}))
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            init_db()
            self.assertEqual(db().execute("SELECT basic_pay FROM department_salary_defaults WHERE department='Product Design'").fetchone()[0], 2750025)
        self.assertEqual(self.records(), before)
        self.client.post("/admin/salary/pay-selected", data=self.selection(["Thamizh"]))
        self.assertEqual(self.records()[-1]["basic_pay"], 2750025)

    def test_select_all_pays_department_rates_and_retries_do_not_pay_twice(self):
        form = self.selection()
        self.assertEqual(len(form.getlist("employee_id")), 20)
        response = self.client.post("/admin/salary/pay-selected", data=form, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Marked 20 salary records as paid", response.data)
        records = self.records()
        self.assertEqual(len(records), 20)
        self.assertEqual(sum(row["basic_pay"] for row in records), 55200000)
        self.assertTrue(all(row["status"] == "PAID" and row["paid_on"] == date.today().isoformat() for row in records))
        self.assertTrue(all(row["allowances"] == row["deductions"] == 0 for row in records))
        self.assertTrue(all(row["updated_by"] == self.users["admin"] for row in records))
        response = self.client.post("/admin/salary/pay-selected", data=form, follow_redirects=True)
        self.assertIn(b"already paid", response.data)
        self.assertEqual(self.records(), records)
        employee = app.test_client()
        employee.post("/", data={"username": "Kavin", "password": "Kavin"})
        own = employee.get("/salary?month=2026-09")
        self.assertIn("₹30,000.00", own.get_data(as_text=True))
        self.assertIn(b"Paid", own.data)
        self.assertNotIn(b"Select employees", own.data)
        self.assertNotIn("₹35,000.00", own.get_data(as_text=True))

    def test_subset_department_and_month_preserve_custom_pending_and_paid_records(self):
        with app.app_context():
            db().execute("""INSERT INTO salary_records(employee_id,salary_month,basic_pay,allowances,deductions,status,notes,updated_by)
                VALUES(?,'2026-09',1234567,10001,202,'PENDING','Individual adjustment',?)""", (self.users["Arul"], self.users["admin"]))
            db().commit()
        form = self.selection(["Arul", "Nila"], department="Engineering")
        form.add("employee_id", str(self.users["Arul"]))
        response = self.client.post("/admin/salary/pay-selected", data=form)
        self.assertIn("department=Engineering", response.location)
        records = self.records()
        self.assertEqual({row["employee_id"] for row in records}, {self.users["Arul"], self.users["Nila"]})
        arul = next(row for row in records if row["employee_id"] == self.users["Arul"])
        self.assertEqual((arul["basic_pay"], arul["allowances"], arul["deductions"], arul["notes"]), (1234567, 10001, 202, "Individual adjustment"))
        self.client.post("/admin/salary/pay-selected", data=self.selection(["Kavin"], month="2026-08"))
        self.assertEqual(self.records()[:2], records)
        self.assertEqual(self.records()[-1]["salary_month"], "2026-08")
        page = self.client.get("/salary?month=2026-09&department=Engineering")
        self.assertIn(b"Arul", page.data)
        self.assertNotIn(b"Kavin", page.data)

    def test_invalid_selection_and_stale_preview_are_atomic(self):
        original = self.selection(["Kavin", "Arul"])
        invalid = []
        for field, value in (("salary_month", "2026-13"), ("department", "missing"), ("paid_on", "2026-02-30"),
                             ("paid_on", (date.today() + timedelta(days=1)).isoformat()), ("employee_id", "invalid"),
                             ("employee_id", str(self.users["admin"])), (f"preview_{self.users['Kavin']}", "tampered")):
            form = original.copy(); form[field] = value; invalid.append(form)
        form = original.copy(); form.poplist("employee_id"); invalid.append(form)
        form = original.copy(); form["department"] = "Engineering"; invalid.append(form)
        for form in invalid:
            with self.subTest(form=list(form.items())):
                self.assertEqual(self.client.post("/admin/salary/pay-selected", data=form).status_code, 400)
                self.assertEqual(self.records(), [])
        with app.app_context():
            db().execute("UPDATE department_salary_defaults SET basic_pay=3600000 WHERE department='Engineering'")
            db().commit()
        self.assertIn(b"Salary details have changed", self.client.post("/admin/salary/pay-selected", data=original).data)
        self.assertEqual(self.records(), [])
        self.assertEqual(self.client.post("/admin/salary/pay-selected", data=self.selection(["Kavin", "Arul"])).status_code, 302)

    def test_inactive_missing_rate_and_new_department_require_review(self):
        form = self.selection(["Kavin", "Arul"])
        with app.app_context():
            db().execute("UPDATE users SET active=0 WHERE username='Kavin'")
            db().commit()
        self.assertIn(b"inactive employee", self.client.post("/admin/salary/pay-selected", data=form).data)
        self.assertEqual(self.records(), [])
        with app.app_context():
            db().execute("UPDATE users SET department='New Department' WHERE username='Arul'")
            db().commit()
        page = self.client.get("/salary?month=2026-09")
        self.assertIn(b"Set rate", page.data)
        form = MultiDict({"csrf_token": self.token, "salary_month": "2026-09", "department": "ALL", "paid_on": date.today().isoformat(), "employee_id": str(self.users["Arul"])})
        self.assertIn(b"Set a department salary", self.client.post("/admin/salary/pay-selected", data=form).data)
        self.assertEqual(self.records(), [])

    def test_permissions_csrf_and_bad_rate_forms(self):
        selection = self.selection(["Kavin"])
        for username in (None, "Kavin"):
            client = app.test_client()
            if username:
                client.post("/", data={"username": username, "password": username})
                with client.session_transaction() as session:
                    session["role"] = "ADMIN"
            self.assertEqual(client.get("/admin/salary/departments").status_code, 302)
            self.assertEqual(client.post("/admin/salary/departments", data=self.rate_form()).status_code, 302)
            self.assertEqual(client.post("/admin/salary/pay-selected", data=selection).status_code, 302)
        self.assertEqual(self.client.get("/admin/salary/pay-selected").status_code, 405)
        for token in ("", "wrong", "wrong-✓"):
            form = selection.copy(); form["csrf_token"] = token
            self.assertEqual(self.client.post("/admin/salary/pay-selected", data=form).status_code, 403)
            form = self.rate_form(); form["csrf_token"] = token
            self.assertEqual(self.client.post("/admin/salary/departments", data=form).status_code, 403)
        for amount in ("0", "-1", "1.001", "NaN", "100000000"):
            self.assertEqual(self.client.post("/admin/salary/departments", data=self.rate_form(Engineering=amount)).status_code, 400)
        form = self.rate_form(); form.add("department", "Forged"); form.add("basic_pay", "25000")
        self.assertEqual(self.client.post("/admin/salary/departments", data=form).status_code, 400)
        with app.app_context():
            self.assertEqual(db().execute("SELECT basic_pay FROM department_salary_defaults WHERE department='Engineering'").fetchone()[0], 3500000)
        self.assertEqual(self.records(), [])

    def test_concurrent_payment_retries_keep_one_record_per_employee(self):
        form = self.selection(["Kavin", "Arul"])
        def pay(_):
            client = app.test_client()
            with client.session_transaction() as session:
                session.update(user_id=self.users["admin"], role="ADMIN", salary_csrf_token=self.token)
            return client.post("/admin/salary/pay-selected", data=form)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(pay, range(2)))
        self.assertTrue(all(response.status_code == 302 for response in responses))
        self.assertEqual(len(self.records()), 2)


if __name__ == "__main__":
    unittest.main()
