-- ============================================================
-- Smart Campus Hub
-- Phase 25: Administrative Activity Logs
--
-- Back up the database before applying.
-- Apply this migration only once.
-- ============================================================

CREATE TABLE activity_logs (
    id INT NOT NULL AUTO_INCREMENT,
    actor_user_id INT NULL,
    target_user_id INT NULL,
    action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INT NULL,
    description TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    INDEX idx_activity_logs_actor (actor_user_id),
    INDEX idx_activity_logs_target (target_user_id),
    INDEX idx_activity_logs_action (action),
    INDEX idx_activity_logs_created (created_at),

    CONSTRAINT fk_activity_logs_actor
        FOREIGN KEY (actor_user_id)
        REFERENCES users(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_activity_logs_target
        FOREIGN KEY (target_user_id)
        REFERENCES users(id)
        ON DELETE SET NULL

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
