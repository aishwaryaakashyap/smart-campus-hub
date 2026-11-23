-- Phase 16.2 recovery:
-- Add missing SLA and current-handler fields to an existing grievances table.
-- grievance_escalations already exists; do not recreate it.

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

-- Preserve existing assignments.
-- Do not create artificial SLA deadlines for old grievances.
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
