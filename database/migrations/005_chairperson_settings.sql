-- ============================================================
-- Smart Campus Hub
-- Phase 21: Primary Chairperson Settings
--
-- IMPORTANT:
-- 1. A fresh database backup must exist before applying.
-- 2. Apply this migration only once.
-- 3. Do not rerun migrations 001 through 004.
-- 4. Existing users and grievance records must be preserved.
-- ============================================================

CREATE TABLE chairperson_settings (
    singleton_id TINYINT UNSIGNED NOT NULL DEFAULT 1,

    primary_chairperson_user_id INT NULL,

    updated_by_user_id INT NULL,

    updated_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (singleton_id),

    UNIQUE KEY uq_chairperson_settings_primary_user
        (primary_chairperson_user_id),

    INDEX idx_chairperson_settings_updated_by
        (updated_by_user_id),

    CONSTRAINT ck_chairperson_settings_singleton
        CHECK (singleton_id = 1),

    CONSTRAINT fk_chairperson_settings_primary_user
        FOREIGN KEY (primary_chairperson_user_id)
        REFERENCES users(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_chairperson_settings_updated_by
        FOREIGN KEY (updated_by_user_id)
        REFERENCES users(id)
        ON DELETE SET NULL

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Create exactly one institution-wide settings record.
-- No Chairperson is selected initially.

INSERT INTO chairperson_settings (
    singleton_id,
    primary_chairperson_user_id,
    updated_by_user_id
)
VALUES (1, NULL, NULL);


-- ============================================================
-- MIGRATION COMPLETE
-- ============================================================
