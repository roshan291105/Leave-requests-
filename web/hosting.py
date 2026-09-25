"""Cloud entry point. Local development still uses python app.py.

Initialize: python web/hosting.py
Serve: gunicorn --chdir web hosting:app --bind 0.0.0.0:$PORT
"""
import os
import re

# Read hosting settings before app.py loads a developer's optional .env file.
_settings = dict(os.environ)
_database_url = _settings.get("DATABASE_URL", "").strip()
_secret = _settings.get("LEAVE_SECRET", "")
if not _database_url.startswith(("postgresql://", "postgres://")):
    raise RuntimeError("Set DATABASE_URL to a dedicated PostgreSQL database URL.")
if len(_secret) < 32 or _secret == "change-me-in-production":
    raise RuntimeError("Set LEAVE_SECRET to a random value of at least 32 characters.")

from flask import abort, jsonify, request
from werkzeug.security import generate_password_hash
from app import app, db, init_db, DEFAULT_WORK_SCHEDULE

app.config.update(
    DATABASE=_database_url,
    SECRET_KEY=_secret,
    DEBUG=False,
    TESTING=False,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


@app.before_request
def hide_local_database_tools():
    # These routes belong to the separate, local pgAdmin connectivity exercise.
    if request.endpoint in {"test_pg", "postgres_leave_requests"}:
        abort(404)


@app.get("/healthz")
def hosting_health():
    try:
        db().execute("SELECT 1").fetchone()
    except Exception as exc:
        app.logger.error("Database health check failed (%s)", type(exc).__name__)
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok")


def initialize_hosted_database():
    """Create missing schema and the first administrator without demo accounts.

    Repeat starts preserve existing users, passwords, leave data and schedules.
    Use a fresh, dedicated database, never the shared company TestDb.
    """
    with app.app_context():
        init_db(seed_demo=False)
        connection = db()
        try:
            connection.begin_write()
            admin = connection.execute(
                "SELECT id FROM users WHERE role='ADMIN' AND active=1 LIMIT 1"
            ).fetchone()
            if not admin:
                username = _settings.get("DAYORA_ADMIN_USERNAME", "admin").strip()
                password = _settings.get("DAYORA_ADMIN_PASSWORD", "")
                full_name = _settings.get("DAYORA_ADMIN_NAME", "Roshan").strip()
                email = _settings.get("DAYORA_ADMIN_EMAIL", "").strip()
                if not re.fullmatch(r"[a-zA-Z0-9._-]{3,30}", username):
                    raise ValueError("DAYORA_ADMIN_USERNAME must be 3-30 letters, numbers, dots, underscores or hyphens.")
                if not 12 <= len(password) <= 128 or not password.strip():
                    raise ValueError("Set DAYORA_ADMIN_PASSWORD to a unique password of 12-128 characters.")
                if not 2 <= len(full_name) <= 100:
                    raise ValueError("DAYORA_ADMIN_NAME must contain 2-100 characters.")
                if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                    raise ValueError("Set DAYORA_ADMIN_EMAIL to your email address.")
                if connection.execute(
                    "SELECT 1 FROM users WHERE LOWER(username)=LOWER(?)", (username,)
                ).fetchone():
                    raise ValueError("The initial admin username already exists. Choose a different username.")
                connection.execute(
                    "INSERT INTO users(username,password,full_name,email,department,role) "
                    "VALUES(?,?,?,?,?,'ADMIN')",
                    (username, generate_password_hash(password), full_name, email, "People Operations"),
                )
            connection.executemany(
                "INSERT INTO work_schedule(weekday,day_name,start_time,end_time,is_working_day) "
                "VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING",
                DEFAULT_WORK_SCHEDULE,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


if __name__ == "__main__":
    initialize_hosted_database()
    print("Dayora database initialization complete.")
