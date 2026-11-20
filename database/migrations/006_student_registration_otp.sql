-- ============================================================
-- Smart Campus Hub
-- Phase 22: Student Registration OTP
--
-- IMPORTANT:
-- 1. Back up the database before applying.
-- 2. Apply this migration only once.
-- 3. Do not rerun migrations 001, 002, 004 or 005.
-- 4. Existing users and student records are preserved.
-- ============================================================

CREATE TABLE student_registration_otps (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    otp_hash CHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    used_at DATETIME NULL,

    PRIMARY KEY (id),

    INDEX idx_student_otp_user_created
        (user_id, created_at),

    INDEX idx_student_otp_expires
        (expires_at),

    CONSTRAINT fk_student_otp_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- MIGRATION COMPLETE
-- ============================================================
