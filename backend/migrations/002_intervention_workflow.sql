ALTER TABLE priority_scores
    MODIFY COLUMN score FLOAT NULL,
    ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'pending',
    ADD COLUMN scoring_method VARCHAR(50) NOT NULL DEFAULT 'legacy-rules',
    ADD COLUMN chosen_action TEXT NULL,
    ADD COLUMN follow_up_at DATETIME NULL,
    ADD COLUMN completed_at DATETIME NULL,
    ADD COLUMN updated_at DATETIME NULL;

UPDATE priority_scores
SET updated_at = COALESCE(computed_at, CURRENT_TIMESTAMP)
WHERE updated_at IS NULL;

UPDATE priority_scores AS priority
JOIN scans AS scan ON scan.id = priority.scan_id
SET priority.status = 'completed'
WHERE scan.status = 'resolved';