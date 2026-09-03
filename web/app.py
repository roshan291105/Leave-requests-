from __future__ import annotations

import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
app.config.update(SECRET_KEY=os.getenv("LEAVE_SECRET", "change-me-in-production"), DATABASE=BASE_DIR / "leave.db")


def db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    connection = g.pop("db", None)
    if connection:
        connection.close()


def init_db():
    db().executescript("""
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
    """)
    user_columns = {column["name"] for column in db().execute("PRAGMA table_info(users)").fetchall()}
    if "employee_code" not in user_columns:
        db().execute("ALTER TABLE users ADD COLUMN employee_code TEXT")
    if "employment_type" not in user_columns:
        db().execute("ALTER TABLE users ADD COLUMN employment_type TEXT NOT NULL DEFAULT 'Permanent'")
    db().execute("INSERT OR IGNORE INTO users(username,password,full_name,email,department,role) VALUES(?,?,?,?,?,?)",
                 ("admin", generate_password_hash("admin123"), "Roshan", "admin@dayora.test", "People Operations", "ADMIN"))
    db().execute("UPDATE users SET full_name='Roshan' WHERE username='admin' AND full_name='Maya Anderson'")
    demo_employees = [
        ("employee", "Alex Morgan", "alex@dayora.test", "Product Design"),
        ("jordan", "Jordan Lee", "jordan@dayora.test", "Engineering"),
        ("priya", "Priya Sharma", "priya@dayora.test", "Engineering"),
        ("arjun", "Arjun Mehta", "arjun@dayora.test", "Product Design"),
        ("ananya", "Ananya Iyer", "ananya@dayora.test", "Marketing"),
        ("rohan", "Rohan Kapoor", "rohan@dayora.test", "Finance"),
        ("meera", "Meera Nair", "meera@dayora.test", "People Operations"),
        ("vikram", "Vikram Singh", "vikram@dayora.test", "Sales"),
        ("kavya", "Kavya Reddy", "kavya@dayora.test", "Engineering"),
        ("aditya", "Aditya Rao", "aditya@dayora.test", "Customer Success"),
        ("isha", "Isha Verma", "isha@dayora.test", "Marketing"),
        ("rahul", "Rahul Desai", "rahul@dayora.test", "Finance"),
        ("sneha", "Sneha Patel", "sneha@dayora.test", "Product Design"),
        ("naveen", "Naveen Kumar", "naveen@dayora.test", "Engineering"),
        ("divya", "Divya Menon", "divya@dayora.test", "Customer Success"),
        ("karan", "Karan Malhotra", "karan@dayora.test", "Sales"),
        ("aisha", "Aisha Khan", "aisha@dayora.test", "People Operations"),
        ("siddharth", "Siddharth Bose", "siddharth@dayora.test", "Engineering"),
        ("neha", "Neha Joshi", "neha@dayora.test", "Marketing"),
        ("varun", "Varun Gupta", "varun@dayora.test", "Sales"),
    ]
    employee_password = generate_password_hash("employee123")
    db().executemany("INSERT OR IGNORE INTO users(username,password,full_name,email,department,role) VALUES(?,?,?,?,?,'EMPLOYEE')",
                     [(username, employee_password, name, email, department) for username, name, email, department in demo_employees])
    employee_types = {
        "arjun": "Contract", "vikram": "Contract", "karan": "Contract",
        "kavya": "Intern", "isha": "Intern", "divya": "Intern",
        "aditya": "Part-time", "neha": "Part-time",
        "naveen": "Probation", "aisha": "Probation",
    }
    for number, (username, _name, _email, _department) in enumerate(demo_employees, start=1):
        db().execute("UPDATE users SET employee_code=?,employment_type=? WHERE username=?",
                     (f"DYO{number:03d}", employee_types.get(username, "Permanent"), username))
    db().executemany("INSERT OR IGNORE INTO work_schedule(weekday,day_name,start_time,end_time,is_working_day) VALUES(?,?,?,?,?)", [
        (0, "Monday", "09:00", "18:00", 1), (1, "Tuesday", "09:00", "18:00", 1),
        (2, "Wednesday", "09:00", "18:00", 1), (3, "Thursday", "09:00", "18:00", 1),
        (4, "Friday", "09:00", "18:00", 1), (5, "Saturday", "09:00", "13:00", 1),
        (6, "Sunday", None, None, 0),
    ])
    db().commit()


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def globals_for_templates():
    unread = 0
    if session.get("user_id"):
        unread = db().execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (session["user_id"],)).fetchone()[0]
    hour = datetime.now().hour
    time_greeting = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 17 else "Good evening" if 17 <= hour < 21 else "Good night"
    return {"current_year": date.today().year, "unread_count": unread, "time_greeting": time_greeting}


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
        stats = db().execute("SELECT COUNT(*) total, SUM(status='PENDING') pending, SUM(status='APPROVED') approved, SUM(status='REJECTED') rejected FROM leave_requests").fetchone()
        requests = db().execute("SELECT l.*,u.full_name,u.department,u.employee_code,u.employment_type FROM leave_requests l JOIN users u ON u.id=l.employee_id ORDER BY l.created_at DESC LIMIT 8").fetchall()
        departments = db().execute("SELECT u.department,COUNT(*) total FROM leave_requests l JOIN users u ON u.id=l.employee_id WHERE l.status='APPROVED' GROUP BY u.department ORDER BY total DESC").fetchall()
        return render_template("admin_dashboard.html", stats=stats, requests=requests, departments=departments)
    user = db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    stats = db().execute("SELECT COUNT(*) total,SUM(status='PENDING') pending,SUM(status='APPROVED') approved,SUM(status='REJECTED') rejected FROM leave_requests WHERE employee_id=?", (user["id"],)).fetchone()
    requests = db().execute("SELECT * FROM leave_requests WHERE employee_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
    upcoming = db().execute("SELECT * FROM leave_requests WHERE employee_id=? AND status='APPROVED' AND end_date>=? ORDER BY start_date LIMIT 3", (user["id"], date.today().isoformat())).fetchall()
    today_attendance = db().execute("SELECT * FROM attendance WHERE employee_id=? AND attendance_date=?", (user["id"], date.today().isoformat())).fetchone()
    on_leave_today = db().execute("SELECT leave_type FROM leave_requests WHERE employee_id=? AND status='APPROVED' AND start_date<=? AND end_date>=?", (user["id"], date.today().isoformat(), date.today().isoformat())).fetchone()
    return render_template("employee_dashboard.html", user=user, stats=stats, requests=requests, upcoming=upcoming,
                           today_attendance=today_attendance, on_leave_today=on_leave_today)


@app.get("/admin/attendance")
@login_required("ADMIN")
def attendance():
    selected_date = request.args.get("date", date.today().isoformat())
    try: selected_day = date.fromisoformat(selected_date)
    except ValueError: selected_day = date.today(); selected_date = selected_day.isoformat()
    department = request.args.get("department", "ALL")
    departments = [row["department"] for row in db().execute("SELECT DISTINCT department FROM users WHERE role='EMPLOYEE' ORDER BY department").fetchall()]
    if department not in departments: department = "ALL"
    query = """SELECT u.employee_code,u.full_name,u.department,u.employment_type,
        a.check_in,a.check_out,a.status,
        EXISTS(SELECT 1 FROM leave_requests l WHERE l.employee_id=u.id AND l.status='APPROVED' AND l.start_date<=? AND l.end_date>=?) on_leave
        FROM users u LEFT JOIN attendance a ON a.employee_id=u.id AND a.attendance_date=?
        WHERE u.role='EMPLOYEE'"""
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
    total_employees = db().execute("SELECT COUNT(*) FROM users u WHERE u.role='EMPLOYEE'" + employee_condition, employee_params).fetchone()[0]
    analysis = []
    for offset in range(6, -1, -1):
        analysis_day = selected_day - timedelta(days=offset)
        day_text = analysis_day.isoformat()
        day_schedule = db().execute("SELECT * FROM work_schedule WHERE weekday=?", (analysis_day.weekday(),)).fetchone()
        status_rows = db().execute("""SELECT a.status,COUNT(*) total FROM attendance a JOIN users u ON u.id=a.employee_id
            WHERE a.attendance_date=?""" + employee_condition + " GROUP BY a.status", [day_text] + employee_params).fetchall()
        counts = {row["status"]: row["total"] for row in status_rows}
        leave_count = db().execute("""SELECT COUNT(DISTINCT l.employee_id) FROM leave_requests l JOIN users u ON u.id=l.employee_id
            WHERE l.status='APPROVED' AND l.start_date<=? AND l.end_date>=?""" + employee_condition,
            [day_text, day_text] + employee_params).fetchone()[0]
        marked = sum(counts.values())
        absent = max(0, total_employees - marked - leave_count) if day_schedule["is_working_day"] else 0
        analysis.append({"date": day_text, "label": analysis_day.strftime("%a"), "working": day_schedule["is_working_day"],
                         "present": counts.get("PRESENT", 0), "late": counts.get("LATE", 0),
                         "absent": absent, "leave": leave_count, "total": total_employees})
    return render_template("attendance.html", records=records, summary=summary, departments=departments,
                           selected_department=department, selected_date=selected_date, schedule=schedule,
                           time_summary=time_summary, analysis=analysis)


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
    return render_template("admin_center.html", stats=stats, schedules=schedules)


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
    department = request.args.get("department", "ALL")
    departments = [row["department"] for row in db().execute(
        "SELECT DISTINCT department FROM users WHERE role='EMPLOYEE' ORDER BY department").fetchall()]
    query = """SELECT u.*,
        COUNT(l.id) request_count,
        COALESCE(SUM(l.status='APPROVED'),0) approved_count
        FROM users u LEFT JOIN leave_requests l ON l.employee_id=u.id
        WHERE u.role='EMPLOYEE'"""
    params = []
    if department in departments:
        query += " AND u.department=?"; params.append(department)
    else:
        department = "ALL"
    query += " GROUP BY u.id ORDER BY u.full_name"
    people = db().execute(query, params).fetchall()
    return render_template("employees.html", employees=people, departments=departments,
                           selected_department=department, temporary_password="employee123")


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
            start_time = datetime.strptime(item["check_in"], "%H:%M:%S"); end_time = datetime.strptime(item["check_out"], "%H:%M:%S")
            minutes = max(0, int((end_time - start_time).total_seconds() // 60)); item["duration"] = f"{minutes // 60}h {minutes % 60}m"
        attendance_history.append(item)
    departments = [row["department"] for row in db().execute("SELECT DISTINCT department FROM users WHERE role='EMPLOYEE' ORDER BY department").fetchall()]
    return render_template("employee_detail.html", employee=employee, leaves=leaves, leave_stats=leave_stats,
                           attendance_history=attendance_history, attendance_stats=attendance_stats,
                           departments=departments, employment_types=("Permanent","Contract","Intern","Part-time","Probation"))


@app.post("/admin/employees/<employee_code>/update")
@login_required("ADMIN")
def update_employee(employee_code):
    employee = db().execute("SELECT * FROM users WHERE employee_code=? AND role='EMPLOYEE'", (employee_code,)).fetchone()
    if not employee:
        flash("Employee not found.", "error"); return redirect(url_for("employees"))
    name = request.form.get("full_name", "").strip(); email = request.form.get("email", "").strip()
    username = request.form.get("username", "").strip().lower()
    department = request.form.get("department", "").strip(); employment_type = request.form.get("employment_type", "")
    if len(name) < 2 or "@" not in email or not department or employment_type not in ("Permanent","Contract","Intern","Part-time","Probation"):
        flash("Enter valid employee details.", "error"); return redirect(url_for("employee_detail", employee_code=employee_code))
    if not re.fullmatch(r"[a-z0-9._-]{3,30}", username):
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
    changed = db().execute("UPDATE users SET password=? WHERE employee_code=? AND role='EMPLOYEE'",
                           (generate_password_hash("employee123"), employee_code)).rowcount
    db().commit()
    flash("Password reset to employee123." if changed else "Employee not found.", "success" if changed else "error")
    return redirect(url_for("employee_detail", employee_code=employee_code) if changed else url_for("employees"))


@app.post("/admin/leave/<int:leave_id>/decide")
@login_required("ADMIN")
def decide_leave(leave_id):
    status = request.form["status"]
    if status not in ("APPROVED", "REJECTED"): return ("Invalid status", 400)
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
    app.run(debug=True, port=5000)
