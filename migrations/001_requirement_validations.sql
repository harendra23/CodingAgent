CREATE TABLE IF NOT EXISTS requirement_validations (
    id UUID PRIMARY KEY,
    jira_issue_key VARCHAR(128) NOT NULL,
    confluence_page_id VARCHAR(64) NOT NULL,
    assessment JSON NOT NULL,
    jira_content TEXT NOT NULL,
    confluence_content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_requirement_validations_created_at
    ON requirement_validations (created_at);