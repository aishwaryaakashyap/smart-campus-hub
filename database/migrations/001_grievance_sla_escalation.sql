-- Phase 16.2: Grievance SLA and Escalation Foundation
-- Apply first to smart_campus_hub_phase16_test.
-- Existing advisor assignment and grievance history are preserved.

ALTER TABLE grievances
    ADD COLUMN current_handler_id INT NULL,
    ADD COLUMN current_handler_role VARCHAR(30) NULL,
    ADD COLUMN sla_due_at DATETIME NULL,
    ADD COLUMN escalation_level TINYINT UNSIGNED NOT NULL DEFAULT 0,
    ADD COLUMN last_escalated_at DATETIME NULL,
    ADD COLUMN resolution_confirmed_at DATETIME NULL,
    ADD COLUMN reopen_count INT UNSIGNED NOT NULL DEFAULT 0,
    ADD INDEX idx_grievances_current_handler (current_handler_id),
    ADD INDEX idx_grievances_sla_due (sla_due_at),
    ADD CONSTRAINT fk_grievances_current_handler
        FOREIGN KEY (current_handler_id)
        REFERENCES users(id)
        ON DELETE SET NULL;

-- Preserve the existing advisor assignment as the current handler.
-- Do not create artificial historical SLA deadlines.
UPDATE grievances AS g
LEFT JOIN users AS u ON u.id = g.assigned_to
SET
    g.current_handler_id = CASE
        WHEN g.status IN ('Resolved', 'Rejected') THEN NULL
        ELSE g.assigned_to
    END,
    g.current_handler_role = CASE
        WHEN g.status IN ('Resolved', 'Rejected') THEN NULL
        ELSE u.role
    END
WHERE g.assigned_to IS NOT NULL;

CREATE TABLE grievance_escalations (
    id INT NOT NULL AUTO_INCREMENT,
    grievance_id INT NOT NULL,
    from_user_id INT NULL,
    to_user_id INT NOT NULL,
    from_role VARCHAR(30) NULL,
    to_role VARCHAR(30) NOT NULL,
    escalation_level TINYINT UNSIGNED NOT NULL,
    reason VARCHAR(500) NOT NULL,
    sla_due_at DATETIME NULL,
    escalated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    triggered_by_user_id INT NULL,

    PRIMARY KEY (id),

    INDEX idx_grievance_escalations_grievance_time
        (grievance_id, escalated_at),

    INDEX idx_grievance_escalations_to_user
        (to_user_id),

    CONSTRAINT fk_escalations_grievance
        FOREIGN KEY (grievance_id)
        REFERENCES grievances(id),

    CONSTRAINT fk_escalations_from_user
        FOREIGN KEY (from_user_id)
        REFERENCES users(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_escalations_to_user
        FOREIGN KEY (to_user_id)
        REFERENCES users(id),

    CONSTRAINT fk_escalations_triggered_by
        FOREIGN KEY (triggered_by_user_id)
        REFERENCES users(id)
        ON DELETE SET NULL

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
