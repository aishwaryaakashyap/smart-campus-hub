-- ============================================================
-- Smart Campus Hub
-- Phase 20: Academic Structure and Account Status
--
-- IMPORTANT:
-- 1. Back up the database before applying this migration.
-- 2. Apply this migration only once.
-- 3. Do not execute migrations 001, 002 or 003 again.
-- 4. Existing users and student records must be preserved.
-- ============================================================


-- ============================================================
-- 1. EXTEND USERS TABLE
-- ============================================================

ALTER TABLE users
    ADD COLUMN account_status VARCHAR(20)
        NOT NULL DEFAULT 'active',

    ADD COLUMN email_verified_at DATETIME NULL,

    ADD COLUMN reviewed_by_user_id INT NULL,

    ADD COLUMN reviewed_at DATETIME NULL,

    ADD COLUMN rejection_reason VARCHAR(500) NULL,

    ADD INDEX idx_users_account_status (account_status),

    ADD INDEX idx_users_reviewed_by_user (reviewed_by_user_id),

    ADD CONSTRAINT fk_users_reviewed_by_user
        FOREIGN KEY (reviewed_by_user_id)
        REFERENCES users(id)
        ON DELETE SET NULL;


-- ============================================================
-- 2. CREATE ACADEMIC CLASSES TABLE
-- ============================================================

CREATE TABLE academic_classes (
    id INT NOT NULL AUTO_INCREMENT,

    course VARCHAR(50) NOT NULL,

    branch VARCHAR(50) NOT NULL,

    section VARCHAR(20) NOT NULL,

    admission_year INT NOT NULL,

    advisor_user_id INT NULL,

    is_active TINYINT(1) NOT NULL DEFAULT 1,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uq_academic_class_identity
        (course, branch, section, admission_year),

    INDEX idx_academic_classes_advisor
        (advisor_user_id),

    INDEX idx_academic_classes_active
        (is_active),

    CONSTRAINT fk_academic_classes_advisor
        FOREIGN KEY (advisor_user_id)
        REFERENCES users(id)
        ON DELETE SET NULL

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
-- 3. EXTEND STUDENTS TABLE
-- ============================================================

ALTER TABLE students
    ADD COLUMN academic_class_id INT NULL,

    ADD INDEX idx_students_academic_class
        (academic_class_id),

    ADD CONSTRAINT fk_students_academic_class
        FOREIGN KEY (academic_class_id)
        REFERENCES academic_classes(id)
        ON DELETE SET NULL;


-- ============================================================
-- MIGRATION COMPLETE
--
-- Existing users receive account_status = 'active'.
-- Existing student profiles remain without a class until assigned.
-- Existing grievance records remain untouched.
-- ============================================================
