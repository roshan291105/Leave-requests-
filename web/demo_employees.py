from werkzeug.security import generate_password_hash


# Position determines the stable DYO employee code used by existing records.
DEMO_EMPLOYEES = (
    ("employee", "Kavin", "Product Design", "Permanent"),
    ("jordan", "Arul", "Engineering", "Permanent"),
    ("priya", "Nila", "Engineering", "Permanent"),
    ("arjun", "Thamizh", "Product Design", "Contract"),
    ("ananya", "Kayal", "Marketing", "Permanent"),
    ("rohan", "Ezhil", "Finance", "Permanent"),
    ("meera", "Malar", "People Operations", "Permanent"),
    ("vikram", "Iniyan", "Sales", "Contract"),
    ("kavya", "Yazhini", "Engineering", "Intern"),
    ("aditya", "Cheran", "Customer Success", "Part-time"),
    ("isha", "Thenmozhi", "Marketing", "Intern"),
    ("rahul", "Kathir", "Finance", "Permanent"),
    ("sneha", "Thamarai", "Product Design", "Permanent"),
    ("naveen", "Kumaran", "Engineering", "Probation"),
    ("divya", "Vennila", "Customer Success", "Intern"),
    ("karan", "Senthil", "Sales", "Contract"),
    ("aisha", "Oviya", "People Operations", "Probation"),
    ("siddharth", "Sezhiyan", "Engineering", "Permanent"),
    ("neha", "Poongodi", "Marketing", "Part-time"),
    ("varun", "Velan", "Sales", "Permanent"),
)
ADDITIONAL_NAMES = ("Mugilan", "Thendral", "Kabilan", "Kuyil", "Pari", "Kanmani", "Vetri", "Pugazh", "Ilango", "Amuthan")
MIGRATION_NAME = "tamil_employee_names_v1"


def seed_demo_employees(connection):
    """Rename existing accounts once, retaining their IDs and related records."""
    with connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS app_migrations (
            name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        if connection.execute("SELECT 1 FROM app_migrations WHERE name=?", (MIGRATION_NAME,)).fetchone():
            return
        existing = connection.execute("SELECT * FROM users WHERE role='EMPLOYEE' ORDER BY id").fetchall()
        used_ids = set()
        used_codes = set()
        assignments = []
        for number, (legacy_username, name, department, employment_type) in enumerate(DEMO_EMPLOYEES, start=1):
            code = f"DYO{number:03d}"
            person = next((row for row in existing if row["id"] not in used_ids and row["employee_code"] == code), None)
            if person is None:
                person = next((row for row in existing if row["id"] not in used_ids
                               and not row["employee_code"] and row["username"] in (legacy_username, name)), None)
            if person is not None:
                used_ids.add(person["id"])
            used_codes.add(code)
            assignments.append((person, name, code, department, employment_type))

        # Earlier startup seeding could duplicate an employee after a login ID edit.
        # Retain those accounts, assigning distinct names and codes instead of merging records.
        extra_people = [row for row in existing if row["id"] not in used_ids]
        if len(extra_people) > len(ADDITIONAL_NAMES):
            raise ValueError("More Tamil names are needed for the additional employee accounts.")
        next_code = len(DEMO_EMPLOYEES) + 1
        for person, name in zip(extra_people, ADDITIONAL_NAMES):
            code = person["employee_code"]
            if not code or code in used_codes:
                while f"DYO{next_code:03d}" in used_codes:
                    next_code += 1
                code = f"DYO{next_code:03d}"
            used_codes.add(code)
            assignments.append((person, name, code, person["department"], person["employment_type"]))

        for _person, name, _code, _department, _type in assignments:
            if connection.execute("SELECT 1 FROM users WHERE username=? AND role<>'EMPLOYEE'", (name,)).fetchone():
                raise ValueError(f"The login ID {name} is already used by a non-employee account.")
        # Temporary unique logins allow existing employees to exchange names safely.
        for person in existing:
            connection.execute("UPDATE users SET username=? WHERE id=?", (f"__tamil_migration_{person['id']}__", person["id"]))
        for person, name, code, department, employment_type in assignments:
            password = generate_password_hash(name)
            email = f"{name.lower()}@dayora.test"
            if person is None:
                connection.execute("""INSERT INTO users(username,password,full_name,email,department,role,employee_code,employment_type)
                    VALUES(?,?,?,?,?,'EMPLOYEE',?,?)""", (name, password, name, email, department, code, employment_type))
            else:
                if not person["email"].endswith(("@dayora.test", "@luma.test")):
                    email = person["email"]
                connection.execute("UPDATE users SET username=?,password=?,full_name=?,email=?,employee_code=? WHERE id=?",
                                   (name, password, name, email, code, person["id"]))
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_employee_code ON users(employee_code) WHERE role='EMPLOYEE' AND employee_code IS NOT NULL")
        connection.execute("INSERT INTO app_migrations(name) VALUES(?)", (MIGRATION_NAME,))
