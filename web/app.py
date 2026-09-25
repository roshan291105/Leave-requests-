from __future__ import annotations

import psycopg
import os
import hmac
import json
import re
import secrets

from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps
from pathlib import Path
from urllib.parse import quote
from flask import Flask, abort, flash, g, jsonify, make_response, redirect, render_template, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv
from database import connect_database, INTEGRITY_ERRORS
from demo_employees import seed_demo_employees
from reminders import admin_reminder_data, init_reminder_schema

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)
pg_url = (
    f"postgresql://"
    f"{quote(os.getenv('PGUSER', ''), safe='')}:"
    f"{quote(os.getenv('PGPASSWORD', ''), safe='')}@"
    f"{os.getenv('PGHOST')}:{os.getenv('PGPORT')}/"
    f"{quote(os.getenv('PGDATABASE', ''), safe='')}"
)
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("LEAVE_SECRET", "change-me-in-production"),
    DATABASE=BASE_DIR / "leave.db"
)
def pg_connection():
    return psycopg.connect(
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT"),
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        connect_timeout=5
    )


@app.route("/test-pg")
def test_pg():
    try:
        conn = pg_connection()

        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            result = cur.fetchone()

        conn.close()

        return f"PostgreSQL Connected: Database={result[0]}, User={result[1]}"

    except Exception as e:
        return f"PostgreSQL ERROR: {type(e).__name__}: {str(e)}", 500
DEFAULT_WORK_SCHEDULE = (
    (0, "Monday", "09:00", "18:00", 1), (1, "Tuesday", "09:00", "18:00", 1),
    (2, "Wednesday", "09:00", "18:00", 1), (3, "Thursday", "09:00", "18:00", 1),
    (4, "Friday", "09:00", "18:00", 1), (5, "Saturday", "09:00", "13:00", 1),
    (6, "Sunday", None, None, 0),
)
TASK_STATUSES = {"TODO": "To do", "IN_PROGRESS": "In progress", "COMPLETED": "Completed"}
EMPLOYMENT_TYPES = ("Permanent", "Contract", "Intern", "Part-time", "Probation")
# Editable demo starting amounts in INR, not market salary recommendations.
DEFAULT_DEPARTMENT_SALARIES = {
    "Engineering": 35000, "Product Design": 30000, "Finance": 28000,
    "People Operations": 25000, "Marketing": 25000, "Sales": 22000, "Customer Success": 20000,
}
MESSAGE_TOPICS = ("General question", "Task clarification", "Leave & schedule", "Share an idea")
TASK_TITLE_SUGGESTIONS = (
    "Prepare the Weekly Project Status Report",
    "Review and Update Employee Attendance Records",
    "Complete Application Testing and Document Findings",
    "Resolve Outstanding Customer Support Requests",
    "Reconcile Monthly Expenses and Submit a Summary",
    "Update Project Documentation and User Guides",
    "Prepare the Monthly Sales Performance Report",
    "Develop the Upcoming Social Media Content Calendar",
    "Review Inventory Levels and Report Shortages",
    "Complete Required Training and Submit a Progress Update",
)


def db():
    if "db" not in g:
        g.db = connect_database(app.config["DATABASE"])
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    connection = g.pop("db", None)
    if connection:
        connection.close()


def init_db(seed_demo=True):
    schema = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, full_name TEXT NOT NULL, email TEXT NOT NULL,
            department TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'EMPLOYEE',
            employee_code TEXT, employment_type TEXT NOT NULL DEFAULT 'Permanent',
            annual_balance INTEGER NOT NULL DEFAULT 18, sick_balance INTEGER NOT NULL DEFAULT 10,
            casual_balance INTEGER NOT NULL DEFAULT 8, active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id INTEGER NOT NULL,
            leave_type TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
            days INTEGER NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
            admin_comment TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            decided_at TEXT, FOREIGN KEY(employee_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES users(id),
            assigned_by INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL, instructions TEXT NOT NULL, due_date TEXT,
            status TEXT NOT NULL DEFAULT 'TODO' CHECK(status IN ('TODO','IN_PROGRESS','COMPLETED')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_employee ON tasks(employee_id);
        CREATE TABLE IF NOT EXISTS personal_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 160),
            completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_checklist_employee ON personal_checklist(employee_id);
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES users(id),
            subject TEXT NOT NULL, topic TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_conversations_employee ON conversations(employee_id);
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            sender_id INTEGER NOT NULL REFERENCES users(id),
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_conversation_messages_thread ON conversation_messages(conversation_id, id);
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            check_in TEXT NOT NULL,
            check_out TEXT,
            status TEXT NOT NULL DEFAULT 'PRESENT',
            UNIQUE(employee_id, attendance_date),
            FOREIGN KEY(employee_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS work_schedule (
            weekday INTEGER PRIMARY KEY,
            day_name TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            is_working_day INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS salary_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES users(id),
            salary_month TEXT NOT NULL,
            basic_pay INTEGER NOT NULL CHECK(basic_pay BETWEEN 0 AND 9999999999),
            allowances INTEGER NOT NULL DEFAULT 0 CHECK(allowances BETWEEN 0 AND 9999999999),
            deductions INTEGER NOT NULL DEFAULT 0 CHECK(deductions BETWEEN 0 AND 9999999999),
            status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','PAID')),
            paid_on TEXT,
            notes TEXT NOT NULL DEFAULT '',
            updated_by INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(employee_id, salary_month),
            CHECK(deductions <= basic_pay + allowances),
            CHECK((status='PENDING' AND paid_on IS NULL) OR (status='PAID' AND paid_on IS NOT NULL))
        );
        CREATE TABLE IF NOT EXISTS department_salary_defaults (
            department TEXT PRIMARY KEY,
            basic_pay INTEGER NOT NULL CHECK(basic_pay BETWEEN 1 AND 9999999999),
            updated_by INTEGER REFERENCES users(id),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """
    if db().backend == "postgresql":
        schema = (BASE_DIR.parent / "database" / "postgresql_schema.sql").read_text(encoding="utf-8")
    db().executescript(schema)
    user_columns = db().columns("users")
    task_columns = db().columns("tasks")
    if "duration_minutes" not in task_columns:
        db().execute("ALTER TABLE tasks ADD COLUMN duration_minutes INTEGER NOT NULL DEFAULT 60 CHECK(duration_minutes BETWEEN 15 AND 60000)")
    init_reminder_schema(db())
    if "employee_code" not in user_columns:
        db().execute("ALTER TABLE users ADD COLUMN employee_code TEXT")
    if "employment_type" not in user_columns:
        db().execute("ALTER TABLE users ADD COLUMN employment_type TEXT NOT NULL DEFAULT 'Permanent'")
    if not seed_demo:
        db().commit()
        return
    db().execute("INSERT INTO users(username,password,full_name,email,department,role) VALUES(?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                 ("admin", generate_password_hash("admin123"), "Roshan", "admin@dayora.test", "People Operations", "ADMIN"))
    db().execute("UPDATE users SET full_name='Roshan' WHERE username='admin' AND full_name='Maya Anderson'")
    seed_demo_employees(db())
    db().executemany("INSERT INTO department_salary_defaults(department,basic_pay) VALUES(?,?) ON CONFLICT DO NOTHING", [
        (row["department"], DEFAULT_DEPARTMENT_SALARIES.get(row["department"], 20000) * 100)
        for row in db().execute("SELECT DISTINCT department FROM users WHERE role='EMPLOYEE'").fetchall()
    ])
    db().executemany("INSERT INTO work_schedule(weekday,day_name,start_time,end_time,is_working_day) VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING", DEFAULT_WORK_SCHEDULE)
    db().commit()


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            current_user = db().execute("SELECT full_name,role,active FROM users WHERE id=?", (session["user_id"],)).fetchone()
            if not current_user or not current_user["active"]:
                session.clear()
                return redirect(url_for("login"))
            session.update(name=current_user["full_name"], role=current_user["role"])
            if role and session.get("role") != role:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator



# This page reads the existing PostgreSQL table independently of the app's
# SQLite database. It never initializes, migrates, seeds or writes PostgreSQL.
POSTGRES_LEAVE_REQUESTS_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PostgreSQL Leave Requests | Dayora</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #f4f6fa; color: #182337;
           font: 15px/1.5 system-ui, sans-serif; }
    main { max-width: 1440px; margin: 36px auto; padding: 0 24px; }
    header { display: flex; flex-wrap: wrap; align-items: center;
             justify-content: space-between; gap: 20px; margin-bottom: 24px; }
    h1 { margin: 8px 0; font-size: clamp(24px, 3vw, 32px); }
    p { margin: 8px 0; }
    .muted { color: #566278; }
    .badge { color: #285247; background: #e1f1e9; border-radius: 20px;
             padding: 5px 12px; font-size: 13px; }
    a { color: #314dcc; }
    nav { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; }
    .button { display: inline-block; border: 1px solid #ccd3df; background: white;
              border-radius: 8px; padding: 9px 14px; text-decoration: none; }
    .panel { border: 1px solid #e0e5ed; background: white; border-radius: 12px;
             overflow: hidden; }
    .scroll { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; }
    caption { text-align: left; padding: 16px; font-weight: 600; }
    th, td { padding: 13px 16px; text-align: left; vertical-align: top;
             border-top: 1px solid #e7eaf0; }
    th { background: #f8f9fc; font-size: 13px; white-space: nowrap; }
    td { font-size: 14px; }
    .reason { min-width: 220px; max-width: 400px; overflow-wrap: anywhere;
              white-space: pre-wrap; }
    .empty { padding: 36px 24px; }
    .error { padding: 24px; border-left: 4px solid #bc3434; }
    footer { display: flex; justify-content: space-between; gap: 16px;
             flex-wrap: wrap; margin-top: 20px; align-items: center; }
    a:focus-visible { outline: 3px solid #8094ff; outline-offset: 3px; }
  </style>
</head>
<body><main>
  <header>
    <div><span class="badge">Read only</span>
      <h1>PostgreSQL Leave Requests</h1>
      <p class="muted">Leave requests from the connected PostgreSQL database.</p>
    </div>
    <nav aria-label="Page actions">
      <a href="{{ url_for('dashboard') }}">Back to dashboard</a>
      <a class="button" href="{{ url_for('postgres_leave_requests', page=page) }}">Refresh</a>
    </nav>
  </header>
  <section class="panel" aria-label="Leave requests">
  {% if error %}
    <div class="error" role="alert"><strong>Unable to load leave requests</strong>
      <p>{{ error }}</p></div>
  {% elif rows %}
    <div class="scroll" tabindex="0" aria-label="Scrollable leave requests table">
    <table><caption>Page {{ page }} · {{ rows|length }} requests</caption>
      <thead><tr><th scope="col">Leave ID</th><th scope="col">Employee</th>
        <th scope="col">Employee ID</th><th scope="col">Company ID</th>
        <th scope="col">Leave type</th><th scope="col">Start date</th>
        <th scope="col">End date</th><th scope="col">Reason</th>
        <th scope="col">Status</th></tr></thead>
      <tbody>{% for row in rows %}<tr>
        <td>{{ row.leave_id }}</td>
        <td>{{ row.employee_name if row.employee_name is not none else '—' }}</td>
        <td>{{ row.employee_id if row.employee_id is not none else '—' }}</td>
        <td>{{ row.company_id if row.company_id is not none else '—' }}</td>
        <td>{{ row.leave_type if row.leave_type is not none else '—' }}</td>
        <td>{{ row.start_date if row.start_date is not none else '—' }}</td>
        <td>{{ row.end_date if row.end_date is not none else '—' }}</td>
        <td class="reason">{{ row.reason if row.reason is not none else '—' }}</td>
        <td>{{ row.status if row.status is not none else '—' }}</td>
      </tr>{% endfor %}</tbody>
    </table></div>
  {% else %}
    <div class="empty"><strong>{{ 'No leave requests found' if page == 1 else 'No requests on this page' }}</strong>
      <p class="muted">{{ 'The database returned no records for this account.' if page == 1 else 'Go back to an earlier page to view requests.' }}</p>
    </div>
  {% endif %}
  </section>
  <footer><span class="muted">View only · No records are changed here.</span>
    <nav aria-label="Pagination">
      {% if page > 1 %}<a class="button" href="{{ url_for('postgres_leave_requests', page=page-1) }}">Previous</a>{% endif %}
      {% if has_next %}<a class="button" href="{{ url_for('postgres_leave_requests', page=page+1) }}">Next</a>{% endif %}
    </nav>
  </footer>
</main></body></html>"""


@app.get("/admin/postgres-leave-requests")
@login_required("ADMIN")
def postgres_leave_requests():
    # The existing app has global admins, not company-scoped admins. Do not
    # expose these records to employees or equate SQLite IDs with PostgreSQL IDs.
    raw_page = request.args.get("page", "1")
    if not re.fullmatch(r"[0-9]{1,5}", raw_page):
        abort(400)
    page = int(raw_page)
    if not 1 <= page <= 10000:
        abort(400)
    page_size = 50
    rows, error, has_next = [], None, False
    response_status = 200
    try:
        with pg_connection() as connection:
            # psycopg issues BEGIN READ ONLY before the SELECT. The restriction
            # applies only to this connection; other app connections are intact.
            connection.read_only = True
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT leave_id, employee_name, employee_id, company_id,
                           leave_type, start_date, end_date, reason, status
                    FROM public.leave_requests
                    ORDER BY leave_id DESC
                    LIMIT %s OFFSET %s
                """, (page_size + 1, (page - 1) * page_size))
                columns = [column.name for column in cursor.description]
                records = cursor.fetchall()
                has_next = len(records) > page_size and page < 10000
                rows = [dict(zip(columns, record)) for record in records[:page_size]]
    except psycopg.Error as exc:
        # Avoid returning connection strings, SQL details or credentials.
        app.logger.error("PostgreSQL leave requests unavailable (%s)", type(exc).__name__)
        error = ("Check the PostgreSQL connection settings, access to the leave requests "
                 "table, and its column names, then refresh this page.")
        response_status = 503
    response = make_response(render_template_string(
        POSTGRES_LEAVE_REQUESTS_HTML, rows=rows, error=error,
        page=page, has_next=has_next,
    ), response_status)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.context_processor
def globals_for_templates():
    unread = 0
    if session.get("user_id"):
        unread = db().execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (session["user_id"],)).fetchone()[0]
    hour = datetime.now().hour
    time_greeting = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 17 else "Good evening" if 17 <= hour < 21 else "Good night"
    context = {"current_year": date.today().year, "unread_count": unread, "time_greeting": time_greeting}
    if session.get('role') == 'ADMIN' and session.get('user_id'):
        context['admin_reminders'] = admin_reminder_data(db(), session['user_id'])
        context['reminder_csrf_token'] = session.setdefault('reminder_csrf_token', secrets.token_urlsafe(32))
    return context


@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        user = db().execute("SELECT * FROM users WHERE username=? AND active=1", (request.form["username"].strip(),)).fetchone()
        if user and check_password_hash(user["password"], request.form["password"]):
            session.clear(); session.update(user_id=user["id"], name=user["full_name"], role=user["role"])
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("You have signed out successfully.", "success")
    return redirect(url_for("login"))


@app.get("/dashboard")
@login_required()
def dashboard():
    if session["role"] == "ADMIN":
        stats = db().execute("SELECT COUNT(*) total, SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) pending, SUM(CASE WHEN status='APPROVED' THEN 1 ELSE 0 END) approved, SUM(CASE WHEN status='REJECTED' THEN 1 ELSE 0 END) rejected FROM leave_requests").fetchone()
        requests = db().execute("SELECT l.*,u.full_name,u.department,u.employee_code,u.employment_type FROM leave_requests l JOIN users u ON u.id=l.employee_id ORDER BY l.created_at DESC LIMIT 8").fetchall()
        departments = db().execute("SELECT u.department,COUNT(*) total FROM leave_requests l JOIN users u ON u.id=l.employee_id WHERE l.status='APPROVED' GROUP BY u.department ORDER BY total DESC").fetchall()
        return render_template("admin_dashboard.html", stats=stats, requests=requests, departments=departments)
    user = db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    stats = db().execute("SELECT COUNT(*) total,SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) pending,SUM(CASE WHEN status='APPROVED' THEN 1 ELSE 0 END) approved,SUM(CASE WHEN status='REJECTED' THEN 1 ELSE 0 END) rejected FROM leave_requests WHERE employee_id=?", (user["id"],)).fetchone()
    requests = db().execute("SELECT * FROM leave_requests WHERE employee_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
    upcoming = db().execute("SELECT * FROM leave_requests WHERE employee_id=? AND status='APPROVED' AND end_date>=? ORDER BY start_date LIMIT 3", (user["id"], date.today().isoformat())).fetchall()
    today_attendance = db().execute("SELECT * FROM attendance WHERE employee_id=? AND attendance_date=?", (user["id"], date.today().isoformat())).fetchone()
    on_leave_today = db().execute("SELECT leave_type FROM leave_requests WHERE employee_id=? AND status='APPROVED' AND start_date<=? AND end_date>=?", (user["id"], date.today().isoformat(), date.today().isoformat())).fetchone()
    return render_template("employee_dashboard.html", user=user, stats=stats, requests=requests, upcoming=upcoming,
                           today_attendance=today_attendance, on_leave_today=on_leave_today)


@app.get('/my-day')
@login_required('EMPLOYEE')
def my_day():
    employee_id = session['user_id']
    today = date.today()
    task_summary = db().execute("""SELECT COUNT(*) total,
        COALESCE(SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END),0) completed,
        COALESCE(SUM(CASE WHEN status<>'COMPLETED' AND due_date=? THEN 1 ELSE 0 END),0) due_today,
        COALESCE(SUM(CASE WHEN status<>'COMPLETED' AND due_date<? THEN 1 ELSE 0 END),0) overdue,
        COALESCE(SUM(CASE WHEN status<>'COMPLETED' THEN duration_minutes ELSE 0 END),0) open_minutes
        FROM tasks WHERE employee_id=?""", (today.isoformat(), today.isoformat(), employee_id)).fetchone()
    priorities = db().execute("""SELECT * FROM tasks WHERE employee_id=? AND status<>'COMPLETED'
        ORDER BY (due_date IS NULL),due_date,(status='IN_PROGRESS') DESC,id LIMIT 3""", (employee_id,)).fetchall()
    checklist = db().execute('SELECT * FROM personal_checklist WHERE employee_id=? ORDER BY completed,id DESC', (employee_id,)).fetchall()
    schedule = db().execute('SELECT * FROM work_schedule WHERE weekday=?', (today.weekday(),)).fetchone()
    leave = db().execute("""SELECT leave_type,start_date,end_date FROM leave_requests WHERE employee_id=?
        AND status='APPROVED' AND end_date>=? ORDER BY start_date LIMIT 1""", (employee_id, today.isoformat())).fetchone()
    token = session.setdefault('my_day_csrf_token', secrets.token_urlsafe(32))
    return render_template('my_day.html', task_summary=task_summary, priorities=priorities,
                           checklist=checklist, schedule=schedule, next_leave=leave,
                           today=today.isoformat(), day_token=token)


@app.post('/my-day/checklist')
@login_required('EMPLOYEE')
def update_personal_checklist():
    expected = session.get('my_day_csrf_token', '')
    if not expected or not secrets.compare_digest(expected.encode(), request.form.get('csrf_token', '').encode()):
        abort(403)
    employee_id = session['user_id']
    action = request.form.get('action')
    with db():
        db().begin_write()
        if action == 'add':
            title = request.form.get('title', '').strip()
            if not 1 <= len(title) <= 160:
                flash('Enter a reminder between 1 and 160 characters.', 'error')
            elif db().execute('SELECT COUNT(*) FROM personal_checklist WHERE employee_id=?', (employee_id,)).fetchone()[0] >= 50:
                flash('Your checklist is full. Remove an old item before adding another.', 'error')
            else:
                db().execute('INSERT INTO personal_checklist(employee_id,title) VALUES(?,?)', (employee_id, title))
                flash('Added to your personal checklist.', 'success')
        elif action in ('complete', 'reopen', 'delete'):
            try:
                item_id = int(request.form.get('item_id', ''))
                if not 0 < item_id < 2**63:
                    raise ValueError
            except ValueError:
                abort(400)
            if action == 'delete':
                result = db().execute('DELETE FROM personal_checklist WHERE id=? AND employee_id=?', (item_id, employee_id))
            else:
                result = db().execute('UPDATE personal_checklist SET completed=? WHERE id=? AND employee_id=?',
                                      (int(action == 'complete'), item_id, employee_id))
            if not result.rowcount:
                abort(404)
            flash('Checklist updated.', 'success')
        else:
            abort(400)
    return redirect(url_for('my_day') + '#personal-checklist')


def get_conversation(conversation_id):
    conversation = db().execute("""SELECT c.*, u.full_name, u.department FROM conversations c
        JOIN users u ON u.id=c.employee_id WHERE c.id=?""", (conversation_id,)).fetchone()
    if not conversation or (session["role"] != "ADMIN" and conversation["employee_id"] != session["user_id"]):
        abort(404)
    return conversation


def render_messages(conversation=None, error=None, form=None):
    query = """SELECT c.*, u.full_name, m.body AS preview, m.created_at AS updated_at,
        s.role AS last_sender_role FROM conversations c JOIN users u ON u.id=c.employee_id
        JOIN conversation_messages m ON m.id=(SELECT MAX(id) FROM conversation_messages WHERE conversation_id=c.id)
        JOIN users s ON s.id=m.sender_id"""
    params = ()
    if session["role"] != "ADMIN":
        query += " WHERE c.employee_id=?"
        params = (session["user_id"],)
    threads = db().execute(query + " ORDER BY m.id DESC", params).fetchall()
    history = []
    if conversation:
        history = db().execute("""SELECT m.*, u.full_name, u.role FROM conversation_messages m
            JOIN users u ON u.id=m.sender_id WHERE m.conversation_id=? ORDER BY m.id""", (conversation["id"],)).fetchall()
    token = session.setdefault("message_csrf_token", secrets.token_urlsafe(32))
    return render_template("messages.html", conversations=threads, conversation=conversation,
                           history=history, message_csrf_token=token, topics=MESSAGE_TOPICS,
                           error=error, form=form or {})


def validate_message_csrf():
    expected = session.get("message_csrf_token")
    if not expected or not secrets.compare_digest(expected.encode(), request.form.get("csrf_token", "").encode()):
        abort(403)


def save_conversation_message(conversation_id, employee_id, subject, body):
    # Called inside the same transaction as conversation creation, when applicable.
    db().execute("INSERT INTO conversation_messages(conversation_id,sender_id,body) VALUES(?,?,?)",
                 (conversation_id, session["user_id"], body))
    if session["role"] == "ADMIN":
        recipients = [employee_id]
    else:
        recipients = [row["id"] for row in db().execute("SELECT id FROM users WHERE role='ADMIN' AND active=1")]
    notice = f"{session['name']} sent a message: {subject}. Open Messages to read and reply."
    db().executemany("INSERT INTO notifications(user_id,message) VALUES(?,?)", [(user_id, notice) for user_id in recipients])


@app.route("/messages", methods=["GET", "POST"])
@login_required()
def messages():
    if request.method == "POST":
        validate_message_csrf()
        if session["role"] != "EMPLOYEE":
            abort(403)
        subject = request.form.get("subject", "").strip()
        topic = request.form.get("topic", "")
        body = request.form.get("body", "").strip()
        error = None
        if not subject or len(subject) > 120:
            error = "Enter a subject between 1 and 120 characters."
        elif topic not in MESSAGE_TOPICS:
            error = "Choose a conversation topic."
        elif not body or len(body) > 2000:
            error = "Enter a message between 1 and 2,000 characters."
        if error:
            return render_messages(error=error, form=request.form), 400
        with db():
            conversation_id = db().execute("INSERT INTO conversations(employee_id,subject,topic) VALUES(?,?,?)",
                                           (session["user_id"], subject, topic)).lastrowid
            save_conversation_message(conversation_id, session["user_id"], subject, body)
        flash("Message sent to the admin team.", "success")
        return redirect(url_for("message_thread", conversation_id=conversation_id))
    return render_messages()


@app.route("/messages/<int:conversation_id>", methods=["GET", "POST"])
@login_required()
def message_thread(conversation_id):
    conversation = get_conversation(conversation_id)
    if request.method == "POST":
        validate_message_csrf()
        body = request.form.get("body", "").strip()
        if not body or len(body) > 2000:
            return render_messages(conversation, "Enter a reply between 1 and 2,000 characters.", request.form), 400
        with db():
            save_conversation_message(conversation_id, conversation["employee_id"], conversation["subject"], body)
        flash("Reply sent.", "success")
        return redirect(url_for("message_thread", conversation_id=conversation_id, _anchor="latest-message"))
    return render_messages(conversation)


def validate_reminder_csrf():
    expected = session.get('reminder_csrf_token')
    if not expected or not secrets.compare_digest(expected.encode(), request.form.get('csrf_token','').encode()):
        abort(403)


@app.get('/admin/reminders')
@login_required('ADMIN')
def admin_reminders():
    return render_template('reminders.html')


@app.post('/admin/reminders/review')
@login_required('ADMIN')
def review_admin_reminder():
    validate_reminder_csrf()
    kind = request.form.get('kind','')
    reviewed = request.form.get('reviewed','')
    if kind not in ('attendance','tasks','salary') or reviewed not in ('0','1'):
        abort(400)
    period = date.today().strftime('%Y-%m') if kind == 'salary' else date.today().isoformat()
    if request.form.get('period') != period:
        flash('This reminder belongs to an earlier period. Please review the current reminder.', 'error')
        return redirect(url_for('admin_reminders'))
    with db():
        if reviewed == '1':
            db().execute('INSERT INTO admin_reminder_reviews(admin_id,kind,period) VALUES(?,?,?) ON CONFLICT DO NOTHING', (session['user_id'],kind,period))
        else:
            db().execute('DELETE FROM admin_reminder_reviews WHERE admin_id=? AND kind=? AND period=?', (session['user_id'],kind,period))
    flash('Reminder marked as reviewed.' if reviewed == '1' else 'Reminder reopened.', 'success')
    return redirect(url_for('admin_reminders'))


@app.post('/admin/reminders/settings')
@login_required('ADMIN')
def save_reminder_settings():
    validate_reminder_csrf()
    try:
        salary_day = int(request.form.get('salary_day',''))
        if not 1 <= salary_day <= 31:
            raise ValueError()
    except ValueError:
        return render_template('reminders.html', error='Choose a salary reminder day from 1 to 31.'), 400
    with db():
        db().execute('INSERT INTO admin_reminder_settings(admin_id,salary_day) VALUES(?,?) ON CONFLICT(admin_id) DO UPDATE SET salary_day=excluded.salary_day', (session['user_id'],salary_day))
    flash('Monthly salary reminder day saved.', 'success')
    return redirect(url_for('admin_reminders'))


def task_workloads():
    return db().execute("""SELECT u.id,u.full_name,u.employee_code,
        COALESCE(SUM(t.duration_minutes),0) AS workload_minutes
        FROM users u LEFT JOIN tasks t ON t.employee_id=u.id AND t.status<>'COMPLETED'
        WHERE u.role='EMPLOYEE' AND u.active=1 GROUP BY u.id ORDER BY u.full_name""").fetchall()


def render_tasks(form=None, error=None):
    employees = []
    query = """SELECT t.*, e.full_name AS employee_name, e.employee_code,
        a.full_name AS admin_name FROM tasks t
        JOIN users e ON e.id=t.employee_id JOIN users a ON a.id=t.assigned_by"""
    params = ()
    if session["role"] == "ADMIN":
        employees = task_workloads()
    else:
        query += " WHERE t.employee_id=?"
        params = (session["user_id"],)
    query += " ORDER BY (t.status='COMPLETED'), (t.due_date IS NULL), t.due_date, t.id DESC"
    rows = db().execute(query, params).fetchall()
    token = session.setdefault("task_csrf_token", secrets.token_urlsafe(32))
    return render_template("tasks.html", tasks=rows, employees=employees, statuses=TASK_STATUSES,
                           title_suggestions=TASK_TITLE_SUGGESTIONS,
                           pending_count=sum(row['status'] == 'TODO' for row in rows),
                           task_csrf_token=token, form=form or {}, error=error, today=date.today().isoformat())


def validate_task_csrf():
    expected = session.get("task_csrf_token")
    if not expected or not secrets.compare_digest(expected.encode(), request.form.get("csrf_token", "").encode()):
        abort(403)


@app.get("/tasks")
@login_required()
def tasks():
    return render_tasks()


@app.post("/admin/tasks/assign")
@login_required("ADMIN")
def assign_task():
    validate_task_csrf()
    title_template = request.form.get("title_template", "")
    title = title_template or request.form.get("title", "").strip()
    instructions = request.form.get("instructions", "").strip()
    due_date = request.form.get("due_date", "").strip() or None
    automatic = request.form.get("employee_id") == "AUTO"
    try:
        if not automatic:
            employee_id = int(request.form.get("employee_id", ""))
            employee = db().execute("SELECT id,full_name FROM users WHERE id=? AND role='EMPLOYEE' AND active=1", (employee_id,)).fetchone()
            if not employee:
                raise ValueError("Select an active employee.")
        duration_text = request.form.get("duration_hours", "1").strip()
        if not re.fullmatch(r"\d{1,4}(?:\.\d{1,2})?", duration_text):
            raise ValueError("Enter an estimated duration from 0.25 to 1,000 hours in 0.25-hour steps.")
        duration = Decimal(duration_text)
        if not Decimal('0.25') <= duration <= 1000 or duration % Decimal('0.25'):
            raise ValueError("Enter an estimated duration from 0.25 to 1,000 hours in 0.25-hour steps.")
        duration_minutes = int(duration * 60)
        if title_template and title_template not in TASK_TITLE_SUGGESTIONS:
            raise ValueError("Choose a suggested task title or enter a custom title.")
        if not title or len(title) > 120:
            raise ValueError("Enter a task title between 1 and 120 characters.")
        if not instructions or len(instructions) > 2000:
            raise ValueError("Enter task instructions between 1 and 2,000 characters.")
        if due_date:
            try:
                due_day = date.fromisoformat(due_date)
            except ValueError:
                raise ValueError("Enter a valid due date in YYYY-MM-DD format.")
            if due_day < date.today():
                raise ValueError("The due date cannot be in the past.")
            due_date = due_day.isoformat()
    except (ValueError, OverflowError) as exc:
        error = str(exc) if not isinstance(exc, OverflowError) else "Select an active employee."
        if not automatic and not request.form.get("employee_id", "").isdigit():
            error = "Select an active employee."
        return render_tasks(request.form, error), 400
    with db():
        # Keep employee selection and task creation in the same transaction.
        db().begin_write()
        if automatic:
            employees = task_workloads()
            if not employees:
                return render_tasks(request.form, "No active employees are available for assignment."), 400
            employee = secrets.choice(employees)
            employee_id = employee['id']
        db().execute("INSERT INTO tasks(employee_id,assigned_by,title,instructions,due_date,duration_minutes) VALUES(?,?,?,?,?,?)",
                     (employee_id, session["user_id"], title, instructions, due_date, duration_minutes))
        message = f"{session['name']} assigned you a task: {title}."
        if due_date:
            message += f" Due {due_date}."
        db().execute("INSERT INTO notifications(user_id,message) VALUES(?,?)",
                     (employee_id, message + " Open My tasks to view the instructions."))
    flash(f"Task assigned to {employee['full_name']}.", "success")
    return redirect(url_for("tasks"))


@app.post("/admin/tasks/shuffle")
@login_required("ADMIN")
def shuffle_tasks():
    validate_task_csrf()
    changed = 0
    with db():
        db().begin_write()
        employees = task_workloads()
        if not employees:
            return render_tasks(error="No active employees are available for assignment."), 400
        names = {row['id']: row['full_name'] for row in employees}
        # Each random round gives every active employee one turn, longest tasks first.
        rotation = []
        pending = db().execute("SELECT * FROM tasks WHERE status='TODO' ORDER BY duration_minutes DESC, (due_date IS NULL), due_date, id").fetchall()
        for task in pending:
            if not rotation:
                rotation = list(names)
                secrets.SystemRandom().shuffle(rotation)
            employee_id = rotation.pop()
            if employee_id == task['employee_id']:
                continue
            db().execute("UPDATE tasks SET employee_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                         (employee_id, task['id']))
            db().executemany("INSERT INTO notifications(user_id,message) VALUES(?,?)", [
                (employee_id, f"{session['name']} assigned you task '{task['title']}' during the team shuffle. Open My tasks for details."),
                (task['employee_id'], f"Task '{task['title']}' was reassigned to {names[employee_id]} during the team shuffle."),
            ])
            changed += 1
    flash(f"Shuffled {len(pending)} pending tasks in random employee rounds, longest tasks first; {changed} reassigned. In-progress and completed tasks were kept with their owners.", "success")
    return redirect(url_for("tasks"))


@app.post("/tasks/<int:task_id>/status")
@login_required("EMPLOYEE")
def update_task_status(task_id):
    validate_task_csrf()
    status = request.form.get("status", "")
    if status not in TASK_STATUSES:
        return render_tasks(error="Select a valid task status."), 400
    with db():
        task = db().execute("SELECT * FROM tasks WHERE id=? AND employee_id=?", (task_id, session["user_id"])).fetchone()
        if not task:
            abort(404)
        changed = db().execute("UPDATE tasks SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND employee_id=? AND status<>?",
                               (status, task_id, session["user_id"], status)).rowcount
        if changed:
            db().execute("INSERT INTO notifications(user_id,message) VALUES(?,?)",
                         (task["assigned_by"], f"{session['name']} updated task '{task['title']}' to {TASK_STATUSES[status].lower()}."))
    flash("Task status updated." if changed else "Task status is unchanged.", "success")
    return redirect(url_for("tasks"))


@app.get("/admin/attendance")
@login_required("ADMIN")
def attendance():
    selected_date = request.args.get("date", date.today().isoformat())
    try: selected_day = date.fromisoformat(selected_date)
    except ValueError: selected_day = date.today(); selected_date = selected_day.isoformat()
    selected_date = selected_day.isoformat()
    department = request.args.get("department", "ALL")
    departments = [row["department"] for row in db().execute("SELECT DISTINCT department FROM users WHERE role='EMPLOYEE' ORDER BY department").fetchall()]
    if department not in departments: department = "ALL"
    query = """SELECT u.employee_code,u.full_name,u.department,u.employment_type,u.active,
        a.check_in,a.check_out,a.status,
        EXISTS(SELECT 1 FROM leave_requests l WHERE l.employee_id=u.id AND l.status='APPROVED' AND l.start_date<=? AND l.end_date>=?) on_leave
        FROM users u LEFT JOIN attendance a ON a.employee_id=u.id AND a.attendance_date=?
        WHERE u.role='EMPLOYEE' AND (u.active=1 OR a.id IS NOT NULL)"""
    params = [selected_date, selected_date, selected_date]
    if department != "ALL": query += " AND u.department=?"; params.append(department)
    query += " ORDER BY u.full_name"
    records = []
    for row in db().execute(query, params).fetchall():
        item = dict(row)
        item["display_status"] = "ON LEAVE" if item["on_leave"] else (item["status"] or "ABSENT")
        item["duration"] = "—"
        if item["check_in"] and item["check_out"]:
            start_time = datetime.strptime(item["check_in"], "%H:%M:%S")
            end_time = datetime.strptime(item["check_out"], "%H:%M:%S")
            minutes = max(0, int((end_time - start_time).total_seconds() // 60))
            item["duration"] = f"{minutes // 60}h {minutes % 60}m"
        records.append(item)
    summary = {key: sum(1 for row in records if row["display_status"] == key) for key in ("PRESENT", "LATE", "ABSENT", "ON LEAVE")}
    schedule = db().execute("SELECT * FROM work_schedule WHERE weekday=?", (selected_day.weekday(),)).fetchone()
    unmarked_count = sum(1 for row in records if row["active"] and not row["status"] and not row["on_leave"])
    bulk_check_in = schedule["start_time"] if schedule and schedule["start_time"] else "09:00"
    attendance_csrf_token = session.setdefault("attendance_csrf_token", secrets.token_urlsafe(32))
    worked_minutes = 0
    completed_shifts = 0
    for row in records:
        if row["check_in"] and row["check_out"]:
            start_time = datetime.strptime(row["check_in"], "%H:%M:%S")
            end_time = datetime.strptime(row["check_out"], "%H:%M:%S")
            worked_minutes += max(0, int((end_time - start_time).total_seconds() // 60)); completed_shifts += 1
    time_summary = {
        "total": f"{worked_minutes // 60}h {worked_minutes % 60}m",
        "average": f"{worked_minutes // completed_shifts // 60}h {worked_minutes // completed_shifts % 60}m" if completed_shifts else "0h 0m",
        "completed": completed_shifts,
    }
    employee_condition = " AND u.department=?" if department != "ALL" else ""
    employee_params = [department] if department != "ALL" else []
    total_employees = db().execute("SELECT COUNT(*) FROM users u WHERE u.role='EMPLOYEE' AND u.active=1" + employee_condition, employee_params).fetchone()[0]
    analysis = []
    for offset in range(6, -1, -1):
        analysis_day = selected_day - timedelta(days=offset)
        day_text = analysis_day.isoformat()
        day_schedule = db().execute("SELECT * FROM work_schedule WHERE weekday=?", (analysis_day.weekday(),)).fetchone()
        former_employees = db().execute("""SELECT COUNT(*) FROM users u WHERE u.role='EMPLOYEE' AND u.active=0
            AND (EXISTS(SELECT 1 FROM attendance a WHERE a.employee_id=u.id AND a.attendance_date=?)
                OR EXISTS(SELECT 1 FROM leave_requests l WHERE l.employee_id=u.id AND l.status='APPROVED'
                          AND l.start_date<=? AND l.end_date>=?))""" + employee_condition,
            [day_text, day_text, day_text] + employee_params).fetchone()[0]
        day_total = total_employees + former_employees
        status_rows = db().execute("""SELECT a.status,COUNT(*) total FROM attendance a JOIN users u ON u.id=a.employee_id
            WHERE a.attendance_date=?""" + employee_condition + " GROUP BY a.status", [day_text] + employee_params).fetchall()
        counts = {row["status"]: row["total"] for row in status_rows}
        leave_count = db().execute("""SELECT COUNT(DISTINCT l.employee_id) FROM leave_requests l JOIN users u ON u.id=l.employee_id
            WHERE l.status='APPROVED' AND l.start_date<=? AND l.end_date>=?""" + employee_condition,
            [day_text, day_text] + employee_params).fetchone()[0]
        marked = sum(counts.values())
        absent = max(0, day_total - marked - leave_count) if day_schedule["is_working_day"] else 0
        analysis.append({"date": day_text, "label": analysis_day.strftime("%a"), "working": day_schedule["is_working_day"],
                         "present": counts.get("PRESENT", 0), "late": counts.get("LATE", 0),
                         "absent": absent, "leave": leave_count, "total": day_total})
    return render_template("attendance.html", records=records, summary=summary, departments=departments,
                           selected_department=department, selected_date=selected_date, schedule=schedule,
                           time_summary=time_summary, analysis=analysis, unmarked_count=unmarked_count,
                           bulk_check_in=bulk_check_in, can_mark_date=selected_day <= date.today(),
                           attendance_csrf_token=attendance_csrf_token)


@app.post("/admin/attendance/mark-all-present")
@login_required("ADMIN")
def mark_all_present():
    expected = session.get("attendance_csrf_token")
    if not expected or not secrets.compare_digest(expected.encode(), request.form.get("csrf_token", "").encode()):
        abort(403)
    department = request.form.get("department", "ALL")
    if department != "ALL" and not db().execute("SELECT 1 FROM users WHERE role='EMPLOYEE' AND department=?", (department,)).fetchone():
        flash("Select a valid department before marking attendance.", "error")
        return redirect(url_for("attendance"))
    try:
        attendance_day = date.fromisoformat(request.form.get("attendance_date", ""))
    except ValueError:
        flash("Select a valid attendance date.", "error")
        return redirect(url_for("attendance", department=department))
    selected_date = attendance_day.isoformat()
    if attendance_day > date.today():
        flash("Attendance cannot be marked for a future date.", "error")
        return redirect(url_for("attendance", date=selected_date, department=department))
    schedule = db().execute("SELECT start_time FROM work_schedule WHERE weekday=?", (attendance_day.weekday(),)).fetchone()
    check_in = schedule["start_time"] if schedule and schedule["start_time"] else "09:00"
    check_in = datetime.strptime(check_in, "%H:%M").strftime("%H:%M:%S")
    query = """INSERT INTO attendance(employee_id,attendance_date,check_in,check_out,status)
        SELECT u.id,?,?,NULL,'PRESENT' FROM users u
        WHERE u.role='EMPLOYEE' AND u.active=1
        AND NOT EXISTS (SELECT 1 FROM attendance a WHERE a.employee_id=u.id AND a.attendance_date=?)
        AND NOT EXISTS (SELECT 1 FROM leave_requests l WHERE l.employee_id=u.id
            AND l.status='APPROVED' AND l.start_date<=? AND l.end_date>=?)"""
    params = [selected_date, check_in, selected_date, selected_date, selected_date]
    if department != "ALL":
        query += " AND u.department=?"
        params.append(department)
    query += " ON CONFLICT(employee_id,attendance_date) DO NOTHING"
    with db():
        marked = db().execute(query, params).rowcount
    if marked:
        flash(f"Marked {marked} employee{'s' if marked != 1 else ''} as present for {selected_date}.", "success")
    else:
        flash("No unmarked employees are available for this date and department.", "success")
    return redirect(url_for("attendance", date=selected_date, department=department))


@app.post("/admin/attendance/<employee_code>/mark")
@login_required("ADMIN")
def mark_attendance(employee_code):
    selected_date = request.form.get("attendance_date", date.today().isoformat())
    try:
        attendance_day = date.fromisoformat(selected_date)
        if attendance_day > date.today(): raise ValueError("Attendance cannot be marked for a future date.")
    except ValueError as exc:
        flash(str(exc) if str(exc) else "Select a valid attendance date.", "error")
        return redirect(url_for("attendance"))
    employee = db().execute("SELECT * FROM users WHERE employee_code=? AND role='EMPLOYEE' AND active=1", (employee_code,)).fetchone()
    if not employee:
        flash("Employee not found.", "error"); return redirect(url_for("attendance", date=selected_date))
    approved_leave = db().execute("SELECT leave_type FROM leave_requests WHERE employee_id=? AND status='APPROVED' AND start_date<=? AND end_date>=?", (employee["id"], selected_date, selected_date)).fetchone()
    if approved_leave:
        flash(f"{employee['full_name']} is already on approved {approved_leave['leave_type'].lower()} leave.", "error")
        return redirect(url_for("attendance", date=selected_date))
    status = "CLEAR" if request.form.get("action") == "clear" else request.form.get("status", "PRESENT").upper()
    if status == "CLEAR":
        db().execute("DELETE FROM attendance WHERE employee_id=? AND attendance_date=?", (employee["id"], selected_date))
        db().commit(); flash(f"Cleared attendance for {employee['full_name']}.", "success")
        return redirect(url_for("attendance", date=selected_date))
    if status not in ("PRESENT", "ABSENT"):
        flash("Select a valid attendance status.", "error"); return redirect(url_for("attendance", date=selected_date))
    check_in = request.form.get("check_in", "").strip()
    check_out = request.form.get("check_out", "").strip()
    if status == "ABSENT":
        check_in = ""; check_out = None
    else:
        schedule = db().execute("SELECT * FROM work_schedule WHERE weekday=?", (attendance_day.weekday(),)).fetchone()
        check_in = check_in or (schedule["start_time"] if schedule and schedule["start_time"] else "09:00")
        try:
            check_in_time = datetime.strptime(check_in, "%H:%M")
            check_in = check_in_time.strftime("%H:%M:%S")
            if check_out:
                check_out_time = datetime.strptime(check_out, "%H:%M")
                if check_out_time <= check_in_time: raise ValueError("Check-out time must be after check-in time.")
                check_out = check_out_time.strftime("%H:%M:%S")
            else: check_out = None
            if schedule and schedule["is_working_day"] and schedule["start_time"]:
                scheduled_start = datetime.strptime(schedule["start_time"], "%H:%M")
                status = "LATE" if check_in_time > scheduled_start else "PRESENT"
        except ValueError as exc:
            flash(str(exc) if "after" in str(exc) else "Enter valid attendance times.", "error")
            return redirect(url_for("attendance", date=selected_date))
    db().execute("""INSERT INTO attendance(employee_id,attendance_date,check_in,check_out,status) VALUES(?,?,?,?,?)
        ON CONFLICT(employee_id,attendance_date) DO UPDATE SET check_in=excluded.check_in,check_out=excluded.check_out,status=excluded.status""",
        (employee["id"], selected_date, check_in, check_out, status))
    db().commit(); flash(f"Marked {employee['full_name']} as {status.lower()}.", "success")
    return redirect(url_for("attendance", date=selected_date))


@app.get("/admin/center")
@login_required("ADMIN")
def admin_center():
    today = date.today().isoformat()
    stats = {
        "active_employees": db().execute("SELECT COUNT(*) FROM users WHERE role='EMPLOYEE' AND active=1").fetchone()[0],
        "inactive_employees": db().execute("SELECT COUNT(*) FROM users WHERE role='EMPLOYEE' AND active=0").fetchone()[0],
        "pending_requests": db().execute("SELECT COUNT(*) FROM leave_requests WHERE status='PENDING'").fetchone()[0],
        "attendance_marked": db().execute("SELECT COUNT(*) FROM attendance WHERE attendance_date=?", (today,)).fetchone()[0],
        "on_leave": db().execute("SELECT COUNT(DISTINCT employee_id) FROM leave_requests WHERE status='APPROVED' AND start_date<=? AND end_date>=?", (today, today)).fetchone()[0],
    }
    schedules = db().execute("SELECT * FROM work_schedule ORDER BY weekday").fetchall()
    schedule_defaults = {
        weekday: {"start_time": start, "end_time": end, "is_working_day": working}
        for weekday, _name, start, end, working in DEFAULT_WORK_SCHEDULE
    }
    return render_template("admin_center.html", stats=stats, schedules=schedules, schedule_defaults=schedule_defaults)


@app.get("/schedule")
@login_required("EMPLOYEE")
def employee_schedule():
    schedules = db().execute("SELECT * FROM work_schedule ORDER BY weekday").fetchall()
    today_weekday = date.today().weekday()
    return render_template("employee_schedule.html", schedules=schedules, today_weekday=today_weekday)


@app.post("/admin/center/schedule")
@login_required("ADMIN")
def update_work_schedule():
    previous = {row["weekday"]: dict(row) for row in db().execute("SELECT * FROM work_schedule").fetchall()}
    updates = []
    try:
        for weekday in range(7):
            working = 1 if request.form.get(f"working_{weekday}") == "1" else 0
            start_time = request.form.get(f"start_{weekday}", "").strip() or None
            end_time = request.form.get(f"end_{weekday}", "").strip() or None
            if working:
                if not start_time or not end_time: raise ValueError("Working days require start and end times.")
                start_value = datetime.strptime(start_time, "%H:%M")
                end_value = datetime.strptime(end_time, "%H:%M")
                if end_value <= start_value: raise ValueError("A workday must end after it starts.")
            else:
                start_time = None; end_time = None
            updates.append((start_time, end_time, working, weekday))
    except ValueError as exc:
        flash(str(exc) if str(exc) else "Enter valid schedule times.", "error")
        return redirect(url_for("admin_center"))
    db().executemany("UPDATE work_schedule SET start_time=?,end_time=?,is_working_day=? WHERE weekday=?", updates)
    changed_days = []
    for start_time, end_time, working, weekday in updates:
        old = previous.get(weekday)
        if not old or old["start_time"] != start_time or old["end_time"] != end_time or old["is_working_day"] != working:
            day_name = old["day_name"] if old else ("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")[weekday]
            changed_days.append(f"{day_name}: {start_time}–{end_time}" if working else f"{day_name}: day off")
    if changed_days:
        message = "Work schedule updated by Roshan — " + "; ".join(changed_days) + "."
        employees = db().execute("SELECT id FROM users WHERE role='EMPLOYEE' AND active=1").fetchall()
        db().executemany("INSERT INTO notifications(user_id,message) VALUES(?,?)", [(employee["id"], message) for employee in employees])
    db().commit()
    flash("Work schedule updated and employees notified." if changed_days else "No schedule changes were detected.", "success")
    return redirect(url_for("admin_center"))


@app.post("/leave/apply")
@login_required("EMPLOYEE")
def apply_leave():
    try:
        start = date.fromisoformat(request.form["start_date"]); end = date.fromisoformat(request.form["end_date"])
        if start < date.today(): raise ValueError("Start date cannot be in the past.")
        if end < start: raise ValueError("End date must be on or after the start date.")
        days = (end - start).days + 1
        leave_type = request.form["leave_type"]
        if leave_type not in ("Annual", "Sick", "Casual", "Unpaid"): raise ValueError("Select a valid leave type.")
        column = {"Annual": "annual_balance", "Sick": "sick_balance", "Casual": "casual_balance"}.get(leave_type)
        user = db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
        if column and days > user[column]: raise ValueError(f"Only {user[column]} {leave_type.lower()} leave days remain.")
        overlap = db().execute("SELECT 1 FROM leave_requests WHERE employee_id=? AND status IN ('PENDING','APPROVED') AND start_date<=? AND end_date>=?", (user["id"], end.isoformat(), start.isoformat())).fetchone()
        if overlap: raise ValueError("These dates overlap with an existing leave request.")
        reason = request.form["reason"].strip()
        if len(reason) < 5: raise ValueError("Please provide a short reason (at least 5 characters).")
        cursor = db().execute("INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,days,reason) VALUES(?,?,?,?,?,?)", (user["id"],leave_type,start.isoformat(),end.isoformat(),days,reason))
        admins = db().execute("SELECT id FROM users WHERE role='ADMIN' AND active=1").fetchall()
        db().executemany("INSERT INTO notifications(user_id,message) VALUES(?,?)", [
            (admin["id"], f"{user['full_name']} ({user['employee_code']}, {user['employment_type']}) requested {days} day{'s' if days != 1 else ''} of {leave_type.lower()} leave (request #{cursor.lastrowid}).")
            for admin in admins
        ])
        db().commit(); flash("Your leave request was submitted.", "success")
    except ValueError as exc: flash(str(exc), "error")
    return redirect(url_for("dashboard"))


@app.post("/leave/<int:leave_id>/cancel")
@login_required("EMPLOYEE")
def cancel_leave(leave_id):
    leave = db().execute("SELECT l.leave_type,l.days,u.employee_code,u.employment_type FROM leave_requests l JOIN users u ON u.id=l.employee_id WHERE l.id=? AND l.employee_id=? AND l.status='PENDING'", (leave_id, session["user_id"])).fetchone()
    changed = db().execute("DELETE FROM leave_requests WHERE id=? AND employee_id=? AND status='PENDING'", (leave_id, session["user_id"])).rowcount
    if changed and leave:
        admins = db().execute("SELECT id FROM users WHERE role='ADMIN' AND active=1").fetchall()
        db().executemany("INSERT INTO notifications(user_id,message) VALUES(?,?)", [
            (admin["id"], f"{session['name']} ({leave['employee_code']}, {leave['employment_type']}) cancelled a {leave['days']}-day {leave['leave_type'].lower()} leave request.")
            for admin in admins
        ])
    db().commit(); flash("Pending request cancelled." if changed else "This request can no longer be cancelled.", "success" if changed else "error")
    return redirect(url_for("dashboard"))


@app.get("/admin/requests")
@login_required("ADMIN")
def admin_requests():
    status = request.args.get("status", "ALL").upper()
    if status not in ("ALL", "PENDING", "APPROVED", "REJECTED"):
        status = "ALL"
    employee_type = request.args.get("employee_type", "ALL")
    employee_types = [row["employment_type"] for row in db().execute(
        "SELECT DISTINCT employment_type FROM users WHERE role='EMPLOYEE' ORDER BY employment_type").fetchall()]
    if employee_type not in employee_types:
        employee_type = "ALL"
    query = "SELECT l.*,u.full_name,u.department,u.employee_code,u.employment_type FROM leave_requests l JOIN users u ON u.id=l.employee_id"
    params = []
    conditions = []
    if status != "ALL": conditions.append("l.status=?"); params.append(status)
    if employee_type != "ALL": conditions.append("u.employment_type=?"); params.append(employee_type)
    if conditions: query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY CASE l.status WHEN 'PENDING' THEN 0 ELSE 1 END,l.created_at DESC"
    return render_template("requests.html", requests=db().execute(query, params).fetchall(), selected_status=status,
                           employee_types=employee_types, selected_employee_type=employee_type)


@app.get("/admin/employees")
@login_required("ADMIN")
def employees():
    status = request.args.get("status", "ACTIVE").upper()
    if status not in ("ACTIVE", "INACTIVE", "ALL"):
        status = "ACTIVE"
    department = request.args.get("department", "ALL")
    departments = [row["department"] for row in db().execute(
        "SELECT DISTINCT department FROM users WHERE role='EMPLOYEE' ORDER BY department").fetchall()]
    query = """SELECT u.*,
        COUNT(l.id) request_count,
        COALESCE(SUM(CASE WHEN l.status='APPROVED' THEN 1 ELSE 0 END),0) approved_count
        FROM users u LEFT JOIN leave_requests l ON l.employee_id=u.id
        WHERE u.role='EMPLOYEE'"""
    params = []
    if status != "ALL":
        query += " AND u.active=?"; params.append(1 if status == "ACTIVE" else 0)
    if department in departments:
        query += " AND u.department=?"; params.append(department)
    else:
        department = "ALL"
    query += " GROUP BY u.id ORDER BY u.full_name"
    people = [dict(person) for person in db().execute(query, params).fetchall()]
    for person in people:
        person["name_password"] = person["full_name"] if check_password_hash(person["password"], person["full_name"]) else None
    total_employees = db().execute("SELECT COUNT(*) FROM users WHERE role='EMPLOYEE' AND active=1").fetchone()[0]
    return render_template("employees.html", employees=people, departments=departments,
                           selected_department=department, selected_status=status, total_employees=total_employees)


def validate_employee_csrf():
    expected = session.get("employee_csrf_token")
    if not expected or not secrets.compare_digest(expected.encode(), request.form.get("csrf_token", "").encode()):
        abort(403)


@app.route("/admin/employees/new", methods=["GET", "POST"])
@login_required("ADMIN")
def register_employee():
    error = None
    if request.method == "POST":
        validate_employee_csrf()
        name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        department = request.form.get("department", "").strip()
        employment_type = request.form.get("employment_type", "")
        password = request.form.get("password", "")
        try:
            if not 2 <= len(name) <= 100:
                raise ValueError("Full name must be 2–100 characters.")
            if not re.fullmatch(r"[a-zA-Z0-9._-]{3,30}", username):
                raise ValueError("Login ID must be 3–30 characters using letters, numbers, dots, underscores, or hyphens.")
            if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                raise ValueError("Enter a valid email address.")
            if not 1 <= len(department) <= 80 or employment_type not in EMPLOYMENT_TYPES:
                raise ValueError("Enter a department and choose a valid employment type.")
            if not 8 <= len(password) <= 128 or not password.strip():
                raise ValueError("Set an initial password between 8 and 128 characters.")
            balances = []
            for field in ("annual_balance", "sick_balance", "casual_balance"):
                value = request.form.get(field, "")
                if not re.fullmatch(r"[0-9]{1,3}", value) or not 0 <= int(value) <= 365:
                    raise ValueError("Leave balances must be whole numbers between 0 and 365.")
                balances.append(int(value))
            password_hash = generate_password_hash(password)
            # Serialize allocation so simultaneous registrations receive distinct codes.
            db().begin_write()
            if db().execute("SELECT 1 FROM users WHERE LOWER(username)=LOWER(?)", (username,)).fetchone():
                raise ValueError("That login ID is already in use, including by inactive accounts.")
            if db().execute("SELECT 1 FROM users WHERE LOWER(email)=LOWER(?)", (email,)).fetchone():
                raise ValueError("That email address is already registered.")
            numbers = [int(match[1]) for row in db().execute("SELECT employee_code FROM users")
                       if (match := re.fullmatch(r"DYO([0-9]+)", row["employee_code"] or ""))]
            employee_code = f"DYO{max(numbers, default=0) + 1:03d}"
            db().execute("""INSERT INTO users(username,password,full_name,email,department,role,employee_code,
                employment_type,annual_balance,sick_balance,casual_balance,active)
                VALUES(?,?,?,?,?,'EMPLOYEE',?,?,?,?,?,1)""",
                (username, password_hash, name, email, department, employee_code, employment_type, *balances))
            db().commit()
            flash(f"Registered {name} ({employee_code}). They can now sign in with the login ID and password you set.", "success")
            return redirect(url_for("employee_detail", employee_code=employee_code))
        except ValueError as exc:
            db().rollback()
            error = str(exc)
        except INTEGRITY_ERRORS:
            db().rollback()
            error = "An account already uses those details. Check the login ID and try again."
    token = session.setdefault("employee_csrf_token", secrets.token_urlsafe(32))
    departments = [row["department"] for row in db().execute(
        "SELECT DISTINCT department FROM users WHERE role='EMPLOYEE' ORDER BY department")]
    return render_template("employee_register.html", departments=departments, employment_types=EMPLOYMENT_TYPES,
                           form=request.form, error=error, employee_csrf_token=token), 400 if error else 200


@app.post("/admin/employees/<employee_code>/remove")
@login_required("ADMIN")
def remove_employee(employee_code):
    validate_employee_csrf()
    employee = db().execute("SELECT id,full_name FROM users WHERE employee_code=? AND role='EMPLOYEE'", (employee_code,)).fetchone()
    if not employee:
        abort(404)
    changed = db().execute("UPDATE users SET active=0 WHERE id=? AND role='EMPLOYEE' AND active=1", (employee["id"],)).rowcount
    db().commit()
    flash(f"Removed {employee['full_name']}. Sign-in access is disabled; their records remain in Removed / inactive."
          if changed else "This employee is already inactive.", "success")
    return redirect(url_for("employees"))


@app.get("/admin/employees/<employee_code>")
@login_required("ADMIN")
def employee_detail(employee_code):
    employee = db().execute("SELECT * FROM users WHERE employee_code=? AND role='EMPLOYEE'", (employee_code,)).fetchone()
    if not employee:
        flash("Employee not found.", "error"); return redirect(url_for("employees"))
    leaves = db().execute("SELECT * FROM leave_requests WHERE employee_id=? ORDER BY created_at DESC", (employee["id"],)).fetchall()
    attendance_rows = db().execute("SELECT * FROM attendance WHERE employee_id=? ORDER BY attendance_date DESC LIMIT 30", (employee["id"],)).fetchall()
    leave_stats = {status: sum(1 for leave in leaves if leave["status"] == status) for status in ("PENDING", "APPROVED", "REJECTED")}
    attendance_stats = {status: sum(1 for row in attendance_rows if row["status"] == status) for status in ("PRESENT", "LATE", "ABSENT")}
    attendance_history = []
    for row in attendance_rows:
        item = dict(row); item["duration"] = "—"
        if item["check_in"] and item["check_out"]:
            start_time = datetime.strptime(item["check_in"][:5], "%H:%M"); end_time = datetime.strptime(item["check_out"][:5], "%H:%M")
            minutes = max(0, int((end_time - start_time).total_seconds() // 60)); item["duration"] = f"{minutes // 60}h {minutes % 60}m"
        attendance_history.append(item)
    departments = [row["department"] for row in db().execute("SELECT DISTINCT department FROM users WHERE role='EMPLOYEE' ORDER BY department").fetchall()]
    return render_template("employee_detail.html", employee=employee, leaves=leaves, leave_stats=leave_stats,
                           attendance_history=attendance_history, attendance_stats=attendance_stats,
                           departments=departments, employment_types=EMPLOYMENT_TYPES,
                           employee_csrf_token=session.setdefault("employee_csrf_token", secrets.token_urlsafe(32)))


@app.post("/admin/employees/<employee_code>/update")
@login_required("ADMIN")
def update_employee(employee_code):
    employee = db().execute("SELECT * FROM users WHERE employee_code=? AND role='EMPLOYEE'", (employee_code,)).fetchone()
    if not employee:
        flash("Employee not found.", "error"); return redirect(url_for("employees"))
    name = request.form.get("full_name", "").strip(); email = request.form.get("email", "").strip()
    username = request.form.get("username", "").strip()
    department = request.form.get("department", "").strip(); employment_type = request.form.get("employment_type", "")
    if len(name) < 2 or "@" not in email or not department or employment_type not in ("Permanent","Contract","Intern","Part-time","Probation"):
        flash("Enter valid employee details.", "error"); return redirect(url_for("employee_detail", employee_code=employee_code))
    if not re.fullmatch(r"[a-zA-Z0-9._-]{3,30}", username):
        flash("Login ID must be 3–30 characters using letters, numbers, dots, underscores, or hyphens.", "error")
        return redirect(url_for("employee_detail", employee_code=employee_code))
    if db().execute("SELECT 1 FROM users WHERE username=? AND id<>?", (username, employee["id"])).fetchone():
        flash("That login ID is already in use.", "error"); return redirect(url_for("employee_detail", employee_code=employee_code))
    try:
        annual = max(0, int(request.form.get("annual_balance", 0))); sick = max(0, int(request.form.get("sick_balance", 0))); casual = max(0, int(request.form.get("casual_balance", 0)))
    except ValueError:
        flash("Leave balances must be whole numbers.", "error"); return redirect(url_for("employee_detail", employee_code=employee_code))
    active = 1 if request.form.get("active") == "1" else 0
    db().execute("""UPDATE users SET username=?,full_name=?,email=?,department=?,employment_type=?,annual_balance=?,sick_balance=?,casual_balance=?,active=? WHERE id=?""",
                 (username,name,email,department,employment_type,annual,sick,casual,active,employee["id"]))
    if username != employee["username"]:
        db().execute("INSERT INTO notifications(user_id,message) VALUES(?,?)",
                     (employee["id"], f"Roshan changed your login ID from {employee['username']} to {username}. Use the new ID the next time you sign in."))
    db().commit(); flash(f"Updated {name}'s profile.", "success")
    return redirect(url_for("employee_detail", employee_code=employee_code))


@app.post("/admin/employees/<employee_code>/reset-password")
@login_required("ADMIN")
def reset_employee_password(employee_code):
    employee = db().execute("SELECT id,full_name FROM users WHERE employee_code=? AND role='EMPLOYEE'", (employee_code,)).fetchone()
    if not employee:
        flash("Employee not found.", "error")
        return redirect(url_for("employees"))
    db().execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(employee["full_name"]), employee["id"]))
    db().commit()
    flash(f"Password reset to {employee['full_name']} (case-sensitive).", "success")
    return redirect(url_for("employee_detail", employee_code=employee_code))


@app.post("/admin/leave/<int:leave_id>/decide")
@login_required("ADMIN")
def decide_leave(leave_id):
    status = request.form["status"]
    if status not in ("APPROVED", "REJECTED"): return ("Invalid status", 400)
    # Serialize decisions before checking request status and leave balance.
    db().begin_write()
    leave = db().execute("SELECT * FROM leave_requests WHERE id=? AND status='PENDING'", (leave_id,)).fetchone()
    if not leave: flash("That request has already been processed.", "error")
    else:
        if status == "APPROVED":
            column = {"Annual":"annual_balance","Sick":"sick_balance","Casual":"casual_balance"}.get(leave["leave_type"])
            if column:
                employee = db().execute(f"SELECT {column} balance FROM users WHERE id=?", (leave["employee_id"],)).fetchone()
                if employee["balance"] < leave["days"]:
                    flash("This employee no longer has enough leave balance.", "error")
                    return redirect(request.referrer or url_for("admin_requests"))
                db().execute(f"UPDATE users SET {column}={column}-? WHERE id=?", (leave["days"],leave["employee_id"]))
        db().execute("UPDATE leave_requests SET status=?,admin_comment=?,decided_at=? WHERE id=?", (status,request.form.get("comment","").strip(),datetime.now().isoformat(timespec="seconds"),leave_id))
        db().execute("INSERT INTO notifications(user_id,message) VALUES(?,?)", (leave["employee_id"],f"Your {leave['leave_type'].lower()} leave request was {status.lower()}."))
        db().commit(); flash(f"Request {status.lower()}.", "success")
    return redirect(request.referrer or url_for("admin_requests"))


@app.get("/notifications")
@login_required()
def notifications():
    items = db().execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
    return render_template("notifications.html", notifications=items)


@app.post("/notifications/<int:notification_id>/read")
@login_required()
def read_notification(notification_id):
    db().execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notification_id, session["user_id"]))
    db().commit()
    return redirect(url_for("notifications"))


@app.post("/notifications/read-all")
@login_required()
def read_all_notifications():
    db().execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (session["user_id"],))
    db().commit(); flash("All notifications marked as read.", "success")
    return redirect(url_for("notifications"))


@app.post("/notifications/clear-read")
@login_required()
def clear_read_notifications():
    removed = db().execute("DELETE FROM notifications WHERE user_id=? AND is_read=1", (session["user_id"],)).rowcount
    db().commit(); flash(f"Cleared {removed} read notification{'s' if removed != 1 else ''}.", "success")
    return redirect(url_for("notifications"))


@app.template_filter("salary_money")
def salary_money(paise):
    whole, fraction = divmod(paise, 100)
    digits = str(whole)
    groups = [digits[-3:]]
    digits = digits[:-3]
    while digits:
        groups.append(digits[-2:])
        digits = digits[:-2]
    return "₹" + ",".join(reversed(groups)) + f".{fraction:02d}"


@app.template_filter("salary_month_label")
def salary_month_label(month):
    return date.fromisoformat(month + "-01").strftime("%B %Y")


def salary_month(value):
    if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value):
        raise ValueError("Choose a valid salary month.")
    try:
        date.fromisoformat(value + "-01")
    except ValueError:
        raise ValueError("Choose a valid salary month.") from None
    return value


def salary_amount(value, label):
    if not re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,2})?", value):
        raise ValueError(f"{label} must be between 0 and 99,999,999.99, with at most two decimal places.")
    # Store whole paise to keep saved amounts and totals exact.
    return int(Decimal(value) * 100)


def render_salary_page(template, status=200, **context):
    response = make_response(render_template(template, **context), status)
    response.headers["Cache-Control"] = "private, no-store"
    return response


def validate_salary_csrf():
    expected = session.get("salary_csrf_token")
    if not expected or not secrets.compare_digest(expected.encode(), request.form.get("csrf_token", "").encode()):
        abort(403)


def salary_departments():
    return [row["department"] for row in db().execute(
        "SELECT DISTINCT department FROM users WHERE role='EMPLOYEE' ORDER BY department")]


def salary_payroll_rows(month, department="ALL"):
    query = """SELECT u.id employee_id,u.full_name,u.employee_code,u.department,
        s.id salary_id,s.status,s.basic_pay saved_basic_pay,s.allowances,s.deductions,d.basic_pay department_basic_pay
        FROM users u LEFT JOIN salary_records s ON s.employee_id=u.id AND s.salary_month=?
        LEFT JOIN department_salary_defaults d ON d.department=u.department
        WHERE u.role='EMPLOYEE' AND u.active=1"""
    params = [month]
    if department != "ALL":
        query += " AND u.department=?"; params.append(department)
    rows = []
    for result in db().execute(query + " ORDER BY u.department,u.full_name", params):
        row = dict(result)
        row["basic_pay"] = row["saved_basic_pay"] if row["salary_id"] else row["department_basic_pay"]
        row["allowances"] = row["allowances"] or 0
        row["deductions"] = row["deductions"] or 0
        row["net_pay"] = None if row["basic_pay"] is None else row["basic_pay"] + row["allowances"] - row["deductions"]
        row["payable"] = row["net_pay"] is not None and row["status"] != "PAID"
        # Bind selection to the displayed employee, month and amounts so a stale page cannot pay a changed rate.
        payload = json.dumps([row["employee_id"], month, row["department"], row["salary_id"], row["status"],
                              row["basic_pay"], row["allowances"], row["deductions"]], separators=(",", ":"))
        secret = app.secret_key.encode() if isinstance(app.secret_key, str) else app.secret_key
        row["preview_token"] = hmac.digest(secret, payload.encode(), "sha256").hex()
        rows.append(row)
    return rows


def salary_admin_page(month, department="ALL", error=None, status=200):
    departments = salary_departments()
    if department not in departments:
        department = "ALL"
    query = """SELECT s.*,u.full_name,u.employee_code,u.department,u.active,
        s.basic_pay+s.allowances-s.deductions AS net_pay FROM salary_records s
        JOIN users u ON u.id=s.employee_id WHERE s.salary_month=?"""
    params = [month]
    if department != "ALL":
        query += " AND u.department=?"; params.append(department)
    records = db().execute(query + " ORDER BY u.full_name", params).fetchall()
    totals = {"net": sum(row["net_pay"] for row in records),
              "paid": sum(row["net_pay"] for row in records if row["status"] == "PAID"),
              "pending": sum(row["net_pay"] for row in records if row["status"] == "PENDING")}
    payroll = salary_payroll_rows(month, department)
    token = session.setdefault("salary_csrf_token", secrets.token_urlsafe(32))
    return render_salary_page("salaries.html", status=status, records=records, month=month, totals=totals,
                              departments=departments, selected_department=department, payroll=payroll,
                              payable_count=sum(row["payable"] for row in payroll), salary_csrf_token=token,
                              today=date.today().isoformat(), error=error)


@app.get("/salary")
@login_required()
def salaries():
    try:
        month = salary_month(request.args.get("month", date.today().strftime("%Y-%m")))
    except ValueError as exc:
        month = date.today().strftime("%Y-%m")
        flash(str(exc), "error")
    query = """SELECT s.*,u.full_name,u.employee_code,u.department,u.active,
        s.basic_pay+s.allowances-s.deductions AS net_pay
        FROM salary_records s JOIN users u ON u.id=s.employee_id"""
    if session["role"] == "ADMIN":
        return salary_admin_page(month, request.args.get("department", "ALL"))
    # Employee identity always comes from the authenticated session.
    history = db().execute(query + " WHERE s.employee_id=? ORDER BY s.salary_month DESC", (session["user_id"],)).fetchall()
    current = next((row for row in history if row["salary_month"] == month), None)
    return render_salary_page("salaries.html", history=history, current=current, month=month)


def salary_editor(record=None):
    error = None
    if request.method == "POST":
        validate_salary_csrf()
        form = request.form.to_dict()
        try:
            if record is None:
                employee_id = request.form.get("employee_id", "")
                if not re.fullmatch(r"[0-9]{1,18}", employee_id):
                    raise ValueError("Choose an employee.")
                employee_id = int(employee_id)
                employee = db().execute("SELECT id FROM users WHERE id=? AND role='EMPLOYEE'", (employee_id,)).fetchone()
                if not employee:
                    raise ValueError("Choose an employee.")
                month = salary_month(request.form.get("salary_month", ""))
            else:
                employee_id, month = record["employee_id"], record["salary_month"]
            basic = salary_amount(request.form.get("basic_pay", "").strip(), "Basic pay")
            allowances = salary_amount(request.form.get("allowances", "").strip(), "Allowances")
            deductions = salary_amount(request.form.get("deductions", "").strip(), "Deductions")
            if deductions > basic + allowances:
                raise ValueError("Deductions cannot exceed basic pay plus allowances.")
            status = request.form.get("status", "")
            if status not in ("PENDING", "PAID"):
                raise ValueError("Choose a valid payment status.")
            paid_on = None
            if status == "PAID":
                try:
                    paid_date = date.fromisoformat(request.form.get("paid_on", ""))
                except ValueError:
                    raise ValueError("Enter the payment date for a paid salary.") from None
                if paid_date > date.today():
                    raise ValueError("The payment date cannot be in the future.")
                paid_on = paid_date.isoformat()
            notes = request.form.get("notes", "").strip()
            if len(notes) > 1000:
                raise ValueError("Notes must be 1,000 characters or fewer.")
            values = (basic, allowances, deductions, status, paid_on, notes, session["user_id"])
            if record is None:
                db().execute("""INSERT INTO salary_records(basic_pay,allowances,deductions,status,paid_on,notes,updated_by,employee_id,salary_month)
                    VALUES(?,?,?,?,?,?,?,?,?)""", (*values, employee_id, month))
            else:
                db().execute("""UPDATE salary_records SET basic_pay=?,allowances=?,deductions=?,status=?,paid_on=?,notes=?,updated_by=?,
                    updated_at=CURRENT_TIMESTAMP WHERE id=?""", (*values, record["id"]))
            db().commit()
            flash("Salary record saved. The employee can view it in My salary.", "success")
            return redirect(url_for("salaries", month=month))
        except ValueError as exc:
            error = str(exc)
        except INTEGRITY_ERRORS:
            db().rollback()
            error = "A salary record already exists for this employee and month. Open Salary and edit the existing record."
    elif record is not None:
        form = dict(record)
        for field in ("basic_pay", "allowances", "deductions"):
            form[field] = f"{record[field] // 100}.{record[field] % 100:02d}"
    else:
        form = {"employee_id": request.args.get("employee_id", ""), "salary_month": request.args.get("month", date.today().strftime("%Y-%m")),
                "basic_pay": "", "allowances": "0.00", "deductions": "0.00", "status": "PENDING"}
    token = session.setdefault("salary_csrf_token", secrets.token_urlsafe(32))
    employees = db().execute("SELECT id,full_name,employee_code,active FROM users WHERE role='EMPLOYEE' ORDER BY active DESC,full_name").fetchall()
    return render_salary_page("salary_form.html", status=400 if error else 200, form=form, record=record,
                              employees=employees, error=error, salary_csrf_token=token, today=date.today().isoformat())


@app.route("/admin/salary/departments", methods=["GET", "POST"])
@login_required("ADMIN")
def department_salaries():
    rows = [dict(row) for row in db().execute("""SELECT u.department,SUM(CASE WHEN u.active=1 THEN 1 ELSE 0 END) employee_count,d.basic_pay
        FROM users u LEFT JOIN department_salary_defaults d ON d.department=u.department
        WHERE u.role='EMPLOYEE' GROUP BY u.department,d.basic_pay ORDER BY u.department""")]
    error = None
    if request.method == "POST":
        validate_salary_csrf()
        departments = request.form.getlist("department")
        amounts = request.form.getlist("basic_pay")
        try:
            if len(departments) != len(amounts) or len(set(departments)) != len(departments) or set(departments) != {row["department"] for row in rows}:
                raise ValueError("The department list has changed. Reload this page before saving rates.")
            updates = []
            for department, amount in zip(departments, amounts):
                basic = salary_amount(amount.strip(), department + " salary")
                if not basic:
                    raise ValueError("Department salaries must be greater than zero.")
                updates.append((department, basic, session["user_id"]))
            db().executemany("""INSERT INTO department_salary_defaults(department,basic_pay,updated_by) VALUES(?,?,?)
                ON CONFLICT(department) DO UPDATE SET basic_pay=excluded.basic_pay,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP""", updates)
            db().commit()
            flash("Department salary defaults saved. Existing monthly salary records keep their saved amounts.", "success")
            return redirect(url_for("salaries"))
        except ValueError as exc:
            error = str(exc)
        submitted = dict(zip(departments, amounts))
    else:
        submitted = {}
    for row in rows:
        basic = row["basic_pay"] or DEFAULT_DEPARTMENT_SALARIES.get(row["department"], 20000) * 100
        row["input_amount"] = submitted.get(row["department"], f"{basic // 100}.{basic % 100:02d}")
    return render_salary_page("department_salaries.html", status=400 if error else 200, departments=rows,
                              error=error, salary_csrf_token=session.setdefault("salary_csrf_token", secrets.token_urlsafe(32)))


@app.post("/admin/salary/pay-selected")
@login_required("ADMIN")
def pay_selected_salaries():
    validate_salary_csrf()
    month = date.today().strftime("%Y-%m")
    department = request.form.get("department", "ALL")
    try:
        month = salary_month(request.form.get("salary_month", ""))
        if department != "ALL" and department not in salary_departments():
            raise ValueError("Choose a valid department.")
        selected = request.form.getlist("employee_id")
        if not selected or any(not re.fullmatch(r"[0-9]{1,18}", value) for value in selected):
            raise ValueError("Select at least one employee to pay.")
        employee_ids = {int(value) for value in selected}
        try:
            paid_date = date.fromisoformat(request.form.get("paid_on", ""))
        except ValueError:
            raise ValueError("Enter a valid payment date.") from None
        if paid_date > date.today():
            raise ValueError("The payment date cannot be in the future.")
        # Validate the complete selection and save it in one transaction, including concurrent retries.
        db().begin_write()
        roster = {row["employee_id"]: row for row in salary_payroll_rows(month, department)}
        if employee_ids - roster.keys():
            raise ValueError("The selection includes an inactive employee or someone outside this department. Review the list and select again.")
        plans = []
        already_paid = 0
        for employee_id in sorted(employee_ids):
            row = roster[employee_id]
            if row["status"] == "PAID":
                already_paid += 1
                continue
            if not row["payable"]:
                raise ValueError(f"Set a department salary for {row['department']} before paying {row['full_name']}.")
            if not secrets.compare_digest(row["preview_token"].encode(), request.form.get(f"preview_{employee_id}", "").encode()):
                raise ValueError("Salary details have changed or the selection is outdated. Review the amounts below and select again.")
            plans.append(row)
        for row in plans:
            if row["salary_id"]:
                db().execute("UPDATE salary_records SET status='PAID',paid_on=?,updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='PENDING'",
                             (paid_date.isoformat(), session["user_id"], row["salary_id"]))
            else:
                db().execute("""INSERT INTO salary_records(employee_id,salary_month,basic_pay,allowances,deductions,status,paid_on,notes,updated_by)
                    VALUES(?,?,?,0,0,'PAID',?,?,?)""", (row["employee_id"], month, row["basic_pay"], paid_date.isoformat(),
                    f"Department salary: {row['department']}.", session["user_id"]))
        db().commit()
        message = (f"Marked {len(plans)} salary record{'s' if len(plans) != 1 else ''} as paid for {salary_month_label(month)}. "
                   f"Total: {salary_money(sum(row['net_pay'] for row in plans))}.") if plans else "All selected employees are already paid for this month. No records changed."
        if already_paid and plans:
            message += f" Skipped {already_paid} already paid."
        flash(message, "success")
        return redirect(url_for("salaries", month=month, department=department))
    except ValueError as exc:
        db().rollback()
        return salary_admin_page(month, department, error=str(exc), status=400)


@app.route("/admin/salary/new", methods=["GET", "POST"])
@login_required("ADMIN")
def new_salary():
    return salary_editor()


@app.route("/admin/salary/<int:salary_id>/edit", methods=["GET", "POST"])
@login_required("ADMIN")
def edit_salary(salary_id):
    record = db().execute("""SELECT s.*,u.full_name,u.employee_code FROM salary_records s
        JOIN users u ON u.id=s.employee_id WHERE s.id=? AND u.role='EMPLOYEE'""", (salary_id,)).fetchone()
    if not record:
        abort(404)
    return salary_editor(record)


@app.get("/api/calendar")
@login_required()
def calendar_api():
    rows=db().execute("SELECT l.start_date,l.end_date,l.leave_type,u.full_name FROM leave_requests l JOIN users u ON u.id=l.employee_id WHERE l.status='APPROVED'").fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/notifications/unread")
@login_required()
def unread_notifications_api():
    count = db().execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (session["user_id"],)).fetchone()[0]
    return jsonify({"count": count})


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host=os.getenv("LEAVE_HOST", "127.0.0.1"), port=int(os.getenv("LEAVE_PORT", "5000")), debug=os.getenv("LEAVE_DEBUG", "0") == "1")
