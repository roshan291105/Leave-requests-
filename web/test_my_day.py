import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import app, db, init_db


class MyDayTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True, DATABASE=Path(self.directory.name) / 'day.db')
        with app.app_context():
            init_db()
            self.users = {r['username']: r['id'] for r in db().execute('SELECT id,username FROM users')}
        self.client = app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def login(self, name):
        self.client.post('/logout')
        self.client.post('/', data={'username': name, 'password': 'admin123' if name == 'admin' else name})
        page = self.client.get('/my-day')
        with self.client.session_transaction() as session:
            self.token = session.get('my_day_csrf_token', '')
        return page

    def post(self, **data):
        return self.client.post('/my-day/checklist', data={'csrf_token': self.token, **data}, follow_redirects=True)

    def test_checklist_persistence_escaping_and_idempotent_completion(self):
        page = self.login('Kavin')
        self.assertIn(b'No open tasks', page.data)
        self.assertIn(b'focus-duration', page.data)
        self.assertIn(b'/my-day', self.client.get('/dashboard').data)
        result = self.post(action='add', title='<script>private reminder</script>')
        self.assertIn(b'&lt;script&gt;private reminder&lt;/script&gt;', result.data)
        self.assertNotIn(b'<script>private reminder', result.data)
        with app.app_context():
            item_id = db().execute('SELECT id FROM personal_checklist').fetchone()[0]
        for _ in range(2):
            self.assertEqual(self.post(action='complete', item_id=item_id).status_code, 200)
        with app.app_context():
            init_db()
            self.assertEqual(db().execute('SELECT completed FROM personal_checklist').fetchone()[0], 1)
        self.assertIn(b'1/1 done', self.login('Kavin').data)
        self.assertIn(b'0/1 done', self.post(action='reopen', item_id=item_id).data)
        self.post(action='delete', item_id=item_id)
        with app.app_context():
            self.assertEqual(db().execute('SELECT COUNT(*) FROM personal_checklist').fetchone()[0], 0)
            self.assertEqual(db().execute('SELECT COUNT(*) FROM notifications').fetchone()[0], 0)

    def test_access_isolation_csrf_and_validation(self):
        self.assertEqual(self.client.get('/my-day').status_code, 302)
        self.assertEqual(self.client.post('/my-day/checklist').status_code, 302)
        self.login('Kavin')
        self.assertEqual(self.client.post('/my-day/checklist', data={'action': 'add', 'title': 'No token'}).status_code, 403)
        self.assertEqual(self.post(action='add', title='x', csrf_token='bad').status_code, 403)
        self.post(action='add', title='   ')
        self.post(action='add', title='x' * 161)
        self.post(action='add', title='Kavin private reminder')
        with app.app_context():
            self.assertEqual(db().execute('SELECT COUNT(*) FROM personal_checklist').fetchone()[0], 1)
            item_id = db().execute('SELECT id FROM personal_checklist').fetchone()[0]
        self.assertNotIn(b'Kavin private reminder', self.login('Arul').data)
        for action in ('complete', 'reopen', 'delete'):
            self.assertEqual(self.post(action=action, item_id=item_id).status_code, 404)
        self.assertEqual(self.post(action='other').status_code, 400)
        for item in ('bad', '9' * 100, '-1'):
            self.assertEqual(self.post(action='delete', item_id=item).status_code, 400)
        self.assertEqual(self.login('admin').status_code, 302)
        self.assertEqual(self.client.post('/my-day/checklist').status_code, 302)
        self.assertNotIn(b'Open My day', self.client.get('/dashboard').data)
        with app.app_context():
            self.assertEqual(db().execute('SELECT completed FROM personal_checklist').fetchone()[0], 0)

    def test_priority_order_summary_leave_and_task_privacy(self):
        today = date.today()
        with app.app_context():
            tasks = [('No deadline', None, 'TODO', 30), ('Today task', today.isoformat(), 'IN_PROGRESS', 90),
                     ('Overdue task', (today - timedelta(days=1)).isoformat(), 'TODO', 120),
                     ('Finished task', today.isoformat(), 'COMPLETED', 60)]
            db().executemany('INSERT INTO tasks(employee_id,assigned_by,title,instructions,due_date,status,duration_minutes) VALUES(?,?,?,?,?,?,?)',
                             [(self.users['Kavin'], self.users['admin'], title, 'Instructions', due, status, minutes) for title, due, status, minutes in tasks])
            db().execute('INSERT INTO tasks(employee_id,assigned_by,title,instructions) VALUES(?,?,?,?)',
                         (self.users['Arul'], self.users['admin'], 'Arul private task', 'Instructions'))
            db().execute("INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,days,reason,status) VALUES(?,'Annual',?,?,1,'Rest','APPROVED')",
                         (self.users['Kavin'], today.isoformat(), today.isoformat()))
            db().commit()
        page = self.login('Kavin').data.decode()
        self.assertLess(page.index('Overdue task'), page.index('Today task'))
        self.assertLess(page.index('Today task'), page.index('No deadline'))
        self.assertNotIn('Finished task', page)
        self.assertNotIn('Arul private task', page)
        self.assertIn('4 <small>h</small>', page)
        self.assertIn('On annual leave', page)
        self.assertIn('href="/tasks#task-', page)

    def test_checklist_limit_is_per_employee(self):
        self.login('Kavin')
        with app.app_context():
            db().executemany('INSERT INTO personal_checklist(employee_id,title) VALUES(?,?)',
                             [(self.users['Kavin'], f'Reminder {i}') for i in range(50)])
            db().commit()
        self.assertIn(b'checklist is full', self.post(action='add', title='One more').data)
        self.login('Arul')
        self.assertIn(b'Added to your personal checklist', self.post(action='add', title='My first').data)
        with app.app_context():
            self.assertEqual(db().execute('SELECT COUNT(*) FROM personal_checklist').fetchone()[0], 51)


if __name__ == '__main__':
    unittest.main()
