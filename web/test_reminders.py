import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import app, db, init_db
from reminders import admin_reminder_data


class AdminReminderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True,DATABASE=Path(self.temp_dir.name)/'reminders.db')
        with app.app_context():
            init_db()
            self.users = {u['username']:u['id'] for u in db().execute('SELECT id,username FROM users')}
        self.client = app.test_client()
        self.login('admin')

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, name):
        self.client.post('/logout')
        self.client.post('/',data={'username':name,'password':'admin123' if name=='admin' else name})
        page = self.client.get('/dashboard')
        with self.client.session_transaction() as session:
            self.token = session.get('reminder_csrf_token','')
        return page

    def review(self, kind='tasks', reviewed='1', period=None, **overrides):
        values = dict(kind=kind,reviewed=reviewed,period=period or (date.today().strftime('%Y-%m') if kind=='salary' else date.today().isoformat()),csrf_token=self.token)
        values.update(overrides)
        return self.client.post('/admin/reminders/review',data=values,follow_redirects=True)

    def test_home_navigation_readonly_counts_and_manual_links(self):
        response=self.client.get('/admin/reminders')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'Record attendance',response.data)
        self.assertIn(b'Assign employee tasks',response.data)
        self.assertIn(b'Process employee salaries',response.data)
        self.assertIn(f'/salary?month={date.today():%Y-%m}'.encode(),response.data)
        self.assertIn(b'YOUR ADMIN CHECKLIST',self.client.get('/dashboard').data)
        with app.app_context():
            data=admin_reminder_data(db(),self.users['admin'])
            self.assertEqual([c['remaining'] for c in data['cards']],[20,20,20])
            for table in ('tasks','attendance','salary_records','notifications'):
                self.assertEqual(db().execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)
        self.assertEqual(self.client.get('/admin/automation').status_code,404)

    def test_counts_reflect_actual_work_and_exclude_inactive_and_leave(self):
        day=date.today().isoformat()
        with app.app_context():
            with db():
                db().execute("UPDATE work_schedule SET is_working_day=1")
                db().execute("UPDATE users SET active=0 WHERE username='Arul'")
                db().execute("INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,days,reason,status) VALUES(?,'Casual',?,?,1,'Day off','APPROVED')",(self.users['Nila'],day,day))
                db().execute("INSERT INTO attendance(employee_id,attendance_date,check_in,status) VALUES(?,?,'','ABSENT')",(self.users['Kavin'],day))
                db().execute("INSERT INTO tasks(employee_id,assigned_by,title,instructions,created_at) VALUES(?,?,'Daily report','Prepare report',?)",(self.users['Kavin'],self.users['admin'],day+' 06:00:00'))
                db().execute("INSERT INTO salary_records(employee_id,salary_month,basic_pay,status,paid_on,updated_by) VALUES(?,?,10000,'PAID',?,?)",(self.users['Kavin'],day[:7],day,self.users['admin']))
            data=admin_reminder_data(db(),self.users['admin'])
            self.assertEqual([c['remaining'] for c in data['cards']],[17,17,18])
            with db():
                db().execute('UPDATE work_schedule SET is_working_day=0')
            self.assertEqual(admin_reminder_data(db(),self.users['admin'])['cards'][0]['state_label'],'Day off')

    def test_personal_reviews_daily_and_monthly_reset_and_reopen(self):
        self.assertIn(b'Reminder marked as reviewed',self.review().data)
        self.review(kind='salary')
        with app.app_context():
            today=date.today()
            data=admin_reminder_data(db(),self.users['admin'],today)
            self.assertTrue(data['cards'][1]['reviewed'])
            self.assertTrue(data['cards'][2]['reviewed'])
            tomorrow=admin_reminder_data(db(),self.users['admin'],today+timedelta(days=1))
            self.assertFalse(tomorrow['cards'][1]['reviewed'])
            next_month=(today.replace(day=28)+timedelta(days=4)).replace(day=1)
            self.assertFalse(admin_reminder_data(db(),self.users['admin'],next_month)['cards'][2]['reviewed'])
            with db():
                second_admin=db().execute("INSERT INTO users(username,password,full_name,email,department,role) VALUES('admin2','unused','Second','second@example.test','People Operations','ADMIN')").lastrowid
            self.assertFalse(admin_reminder_data(db(),second_admin)['cards'][1]['reviewed'])
            init_db()
            self.assertTrue(admin_reminder_data(db(),self.users['admin'])['cards'][1]['reviewed'])
        self.review(reviewed='0')
        with app.app_context():
            self.assertFalse(admin_reminder_data(db(),self.users['admin'])['cards'][1]['reviewed'])
            self.assertEqual(db().execute('SELECT COUNT(*) FROM tasks').fetchone()[0],0)
            self.assertEqual(db().execute('SELECT COUNT(*) FROM salary_records').fetchone()[0],0)

    def test_salary_day_settings_short_months_and_completion(self):
        response=self.client.post('/admin/reminders/settings',data={'salary_day':'31','csrf_token':self.token},follow_redirects=True)
        self.assertIn(b'Monthly salary reminder day saved',response.data)
        with app.app_context():
            data=admin_reminder_data(db(),self.users['admin'],date(2027,2,27))
            self.assertEqual(data['salary_due'],date(2027,2,28))
            self.assertEqual(data['cards'][2]['state'],'upcoming')
            self.assertEqual(admin_reminder_data(db(),self.users['admin'],date(2027,2,28))['cards'][2]['state'],'due')
            self.assertEqual(admin_reminder_data(db(),self.users['admin'],date(2028,2,1))['salary_due'],date(2028,2,29))
            with db():
                db().execute("INSERT INTO salary_records(employee_id,salary_month,basic_pay,status,paid_on,updated_by) SELECT id,'2027-02',100,'PAID','2027-02-01',? FROM users WHERE role='EMPLOYEE'",(self.users['admin'],))
            self.assertEqual(admin_reminder_data(db(),self.users['admin'],date(2027,2,28))['cards'][2]['state_label'],'All marked paid')

    def test_validation_csrf_roles_and_stale_page(self):
        for day in ('0','32','bad'):
            self.assertEqual(self.client.post('/admin/reminders/settings',data={'salary_day':day,'csrf_token':self.token}).status_code,400)
        self.assertEqual(self.client.post('/admin/reminders/settings',data={'salary_day':'5'}).status_code,403)
        self.assertEqual(self.review(kind='bad').status_code,400)
        self.assertEqual(self.review(reviewed='bad').status_code,400)
        for token in ('','bad','\u2713'):
            self.assertEqual(self.review(csrf_token=token).status_code,403)
        self.assertIn(b'earlier period',self.review(period='2000-01-01').data)
        with app.app_context():
            self.assertEqual(db().execute('SELECT COUNT(*) FROM admin_reminder_reviews').fetchone()[0],0)
        home=self.login('Kavin')
        self.assertNotIn(b'YOUR ADMIN CHECKLIST',home.data)
        self.assertNotIn(b'/admin/reminders',home.data)
        self.assertEqual(self.client.get('/admin/reminders').status_code,302)
        for path in ('/admin/reminders/settings','/admin/reminders/review'):
            self.assertEqual(self.client.post(path).status_code,302)
        self.client.post('/logout')
        self.assertEqual(self.client.get('/admin/reminders').status_code,302)


if __name__=='__main__':
    unittest.main()
