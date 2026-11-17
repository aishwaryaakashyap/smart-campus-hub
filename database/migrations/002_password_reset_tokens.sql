-- Phase 18.2: Secure password reset tokens
-- Apply this migration to the intended Smart Campus Hub database.
-- Do not run against the production database until deployment approval.

CREATE TABLE password_reset_tokens (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    token_hash CHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,

    PRIMARY KEY (id),

    UNIQUE KEY uq_password_reset_token_hash (token_hash),
    INDEX idx_password_reset_user_created (user_id, created_at),
    INDEX idx_password_reset_expires (expires_at),

    CONSTRAINT fk_password_reset_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
