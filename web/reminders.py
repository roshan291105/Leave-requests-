"""Read-only daily and monthly admin checklists with personal review markers."""
import calendar
from datetime import date


def init_reminder_schema(connection):
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS admin_reminder_settings (
            admin_id INTEGER PRIMARY KEY REFERENCES users(id),
            salary_day INTEGER NOT NULL DEFAULT 1 CHECK(salary_day BETWEEN 1 AND 31)
        );
        CREATE TABLE IF NOT EXISTS admin_reminder_reviews (
            admin_id INTEGER NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL CHECK(kind IN ('attendance','tasks','salary')),
            period TEXT NOT NULL, reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(admin_id,kind,period)
        );
    """)


def admin_reminder_data(connection, admin_id, today=None):
    today = today or date.today()
    day, month = today.isoformat(), today.strftime('%Y-%m')
    # One SQL round trip for the counters/settings instead of six.
    summary = connection.execute(f"""
        WITH active_users AS (
            SELECT id FROM users WHERE role='EMPLOYEE' AND active=1
        ), eligible AS (
            SELECT u.id FROM active_users u
            WHERE NOT EXISTS(SELECT 1 FROM leave_requests l WHERE l.employee_id=u.id
                AND l.status='APPROVED' AND l.start_date<=? AND l.end_date>=?)
        )
        SELECT
            COALESCE((SELECT salary_day FROM admin_reminder_settings WHERE admin_id=?),1) AS salary_day,
            (SELECT COUNT(*) FROM active_users) AS active,
            (SELECT COUNT(*) FROM eligible u WHERE NOT EXISTS(
                SELECT 1 FROM attendance a WHERE a.employee_id=u.id AND a.attendance_date=?)) AS attendance,
            (SELECT COUNT(*) FROM eligible u WHERE NOT EXISTS(
                SELECT 1 FROM tasks t WHERE t.employee_id=u.id AND {connection.local_date('t.created_at')}=?)) AS tasks,
            (SELECT COUNT(*) FROM active_users u WHERE NOT EXISTS(
                SELECT 1 FROM salary_records s WHERE s.employee_id=u.id AND s.salary_month=? AND s.status='PAID')) AS salary,
            COALESCE((SELECT is_working_day FROM work_schedule WHERE weekday=?),0) AS working
        """, (day, day, admin_id, day, day, month, today.weekday())).fetchone()
    salary_day = summary['salary_day']
    salary_due = today.replace(day=min(salary_day, calendar.monthrange(today.year,today.month)[1]))
    reviews = {(r['kind'],r['period']) for r in connection.execute(
        'SELECT kind,period FROM admin_reminder_reviews WHERE admin_id=? AND period IN (?,?)',
        (admin_id,day,month))}
    active, attendance, tasks, salary = (summary[key] for key in ('active','attendance','tasks','salary'))
    working = bool(summary['working'])
    cards = [
        dict(kind='attendance', title='Record attendance', icon='clock', frequency='Daily', period=day,
             period_label=today.strftime('%d %b %Y'), remaining=attendance, endpoint='attendance',
             action='Open attendance', params={'date':day}, detail=f'{attendance} active employees still need an attendance record today.',
             complete=attendance == 0 or not working, complete_label='All recorded' if working else 'Day off', due=True),
        dict(kind='tasks', title='Assign employee tasks', icon='tasks', frequency='Daily', period=day,
             period_label=today.strftime('%d %b %Y'), remaining=tasks, endpoint='tasks',
             action='Open team tasks', params={}, detail=f'{tasks} active employees have no new task assigned today. Review existing work before assigning more.',
             complete=tasks == 0, complete_label='Tasks assigned', due=True),
        dict(kind='salary', title='Process employee salaries', icon='wallet', frequency='Monthly', period=month,
             period_label=today.strftime('%B %Y'), remaining=salary, endpoint='salaries',
             action='Open salary records', params={'month':month}, detail=f'{salary} of {active} active employees have salary records missing or not marked paid for this month.',
             complete=salary == 0, complete_label='All marked paid', due=today >= salary_due),
    ]
    for card in cards:
        card['reviewed'] = (card['kind'],card['period']) in reviews
        card['state'] = 'complete' if card['complete'] else 'reviewed' if card['reviewed'] else 'due' if card['due'] else 'upcoming'
        card['state_label'] = card['complete_label'] if card['complete'] else 'Reviewed' if card['reviewed'] else 'Due now' if card['due'] else 'Upcoming'
        card['needs_attention'] = card['state'] == 'due'
    return dict(cards=cards, due_count=sum(c['needs_attention'] for c in cards), salary_day=salary_day,
                salary_due=salary_due, today=today)
