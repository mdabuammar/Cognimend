-- Seed default plans for Cognimend SaaS
-- Run once after migration 004 is applied

INSERT INTO plans (name, display_name, monthly_price_usd, yearly_price_usd,
    document_limit, query_limit_monthly, storage_limit_mb, max_file_size_mb,
    team_members_limit, connector_limit,
    has_analytics, has_drift_detection, has_api_access, has_audit_logs,
    has_connectors, has_chat_history, has_export)
VALUES
    ('free',       'Free',       0,    0,    3,     50,     10,  10,  1,  0, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE),
    ('personal',   'Personal',   12,   10,   100,   2000,   500, 50,  1,  1, FALSE, FALSE, FALSE, FALSE, TRUE,  TRUE,  TRUE),
    ('team',       'Team',       49,   39,   1000,  20000,  5000,50,  5,  3, TRUE,  FALSE, FALSE, FALSE, TRUE,  TRUE,  TRUE),
    ('business',   'Business',   149,  119,  10000, 100000, 20000,100,20,  10,TRUE,  TRUE,  TRUE,  TRUE,  TRUE,  TRUE,  TRUE),
    ('enterprise', 'Enterprise', 0,    0,    -1,    -1,     -1,  100, -1, -1, TRUE,  TRUE,  TRUE,  TRUE,  TRUE,  TRUE,  TRUE)
ON CONFLICT (name) DO NOTHING;
