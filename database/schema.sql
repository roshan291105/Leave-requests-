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
('admin', 'admin123', 'System Administrator', 'ADMIN'),
('employee', 'employee123', 'Demo Employee', 'EMPLOYEE');
