CREATE DATABASE IF NOT EXISTS leave_management;
USE leave_management;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('EMPLOYEE', 'ADMIN') NOT NULL DEFAULT 'EMPLOYEE',
    employee_code VARCHAR(20) UNIQUE,
    employment_type ENUM('Permanent','Contract','Intern','Part-time','Probation') NOT NULL DEFAULT 'Permanent'
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    employee_id BIGINT NOT NULL,
    leave_type VARCHAR(30) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason VARCHAR(500) NOT NULL,
    status ENUM('PENDING', 'APPROVED', 'REJECTED') NOT NULL DEFAULT 'PENDING',
    admin_comment VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMP NULL,
    CONSTRAINT fk_leave_employee FOREIGN KEY (employee_id) REFERENCES users(id),
    CONSTRAINT chk_leave_dates CHECK (end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS tasks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    employee_id BIGINT NOT NULL,
    assigned_by BIGINT NOT NULL,
    title VARCHAR(120) NOT NULL,
    instructions VARCHAR(2000) NOT NULL,
    due_date DATE NULL,
    status ENUM('TODO', 'IN_PROGRESS', 'COMPLETED') NOT NULL DEFAULT 'TODO',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES users(id),
    FOREIGN KEY (assigned_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS attendance (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    employee_id BIGINT NOT NULL,
    attendance_date DATE NOT NULL,
    check_in TIME NULL,
    check_out TIME NULL,
    status ENUM('PRESENT', 'LATE', 'ABSENT') NOT NULL DEFAULT 'PRESENT',
    CONSTRAINT fk_attendance_employee FOREIGN KEY (employee_id) REFERENCES users(id),
    CONSTRAINT uq_employee_attendance UNIQUE (employee_id, attendance_date)
);

CREATE TABLE IF NOT EXISTS work_schedule (
    weekday TINYINT PRIMARY KEY,
    day_name VARCHAR(12) NOT NULL,
    start_time TIME NULL,
    end_time TIME NULL,
    is_working_day BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT IGNORE INTO work_schedule (weekday, day_name, start_time, end_time, is_working_day) VALUES
(0, 'Monday', '09:00:00', '18:00:00', TRUE),
(1, 'Tuesday', '09:00:00', '18:00:00', TRUE),
(2, 'Wednesday', '09:00:00', '18:00:00', TRUE),
(3, 'Thursday', '09:00:00', '18:00:00', TRUE),
(4, 'Friday', '09:00:00', '18:00:00', TRUE),
(5, 'Saturday', '09:00:00', '13:00:00', TRUE),
(6, 'Sunday', NULL, NULL, FALSE);

INSERT IGNORE INTO users (username, password, full_name, role) VALUES
('admin', 'admin123', 'System Administrator', 'ADMIN');

CREATE TABLE IF NOT EXISTS app_migrations (
    name VARCHAR(100) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TEMPORARY TABLE tamil_employee_names (
    employee_code VARCHAR(20) PRIMARY KEY,
    legacy_username VARCHAR(50) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    employment_type VARCHAR(20) NOT NULL
);
INSERT INTO tamil_employee_names VALUES
('DYO001', 'employee', 'Kavin', 'Permanent'),
('DYO002', 'jordan', 'Arul', 'Permanent'),
('DYO003', 'priya', 'Nila', 'Permanent'),
('DYO004', 'arjun', 'Thamizh', 'Contract'),
('DYO005', 'ananya', 'Kayal', 'Permanent'),
('DYO006', 'rohan', 'Ezhil', 'Permanent'),
('DYO007', 'meera', 'Malar', 'Permanent'),
('DYO008', 'vikram', 'Iniyan', 'Contract'),
('DYO009', 'kavya', 'Yazhini', 'Intern'),
('DYO010', 'aditya', 'Cheran', 'Part-time'),
('DYO011', 'isha', 'Thenmozhi', 'Intern'),
('DYO012', 'rahul', 'Kathir', 'Permanent'),
('DYO013', 'sneha', 'Thamarai', 'Permanent'),
('DYO014', 'naveen', 'Kumaran', 'Probation'),
('DYO015', 'divya', 'Vennila', 'Intern'),
('DYO016', 'karan', 'Senthil', 'Contract'),
('DYO017', 'aisha', 'Oviya', 'Probation'),
('DYO018', 'siddharth', 'Sezhiyan', 'Permanent'),
('DYO019', 'neha', 'Poongodi', 'Part-time'),
('DYO020', 'varun', 'Velan', 'Permanent');

-- Apply once so later administrator edits survive restarts and schema reruns.
START TRANSACTION;
UPDATE users u JOIN tamil_employee_names n
    ON u.employee_code=n.employee_code
       OR (u.employee_code IS NULL AND u.username IN (n.legacy_username,n.full_name))
SET u.username=n.full_name, u.password=n.full_name, u.full_name=n.full_name,
    u.employee_code=n.employee_code
WHERE u.role='EMPLOYEE'
    AND NOT EXISTS (SELECT 1 FROM app_migrations WHERE name='tamil_employee_names_v1');

INSERT INTO users(username,password,full_name,role,employee_code,employment_type)
SELECT n.full_name,n.full_name,n.full_name,'EMPLOYEE',n.employee_code,n.employment_type
FROM tamil_employee_names n
WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.employee_code=n.employee_code)
    AND NOT EXISTS (SELECT 1 FROM app_migrations WHERE name='tamil_employee_names_v1');
INSERT IGNORE INTO app_migrations(name) VALUES('tamil_employee_names_v1');
COMMIT;
DROP TEMPORARY TABLE tamil_employee_names;
