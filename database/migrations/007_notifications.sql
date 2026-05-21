-- =============================================================================
-- Migration 007: Notifications & Alerting
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS notification_preferences (
    id SERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL,
    user_id UUID, -- NULL means workspace-wide preference
    email_enabled BOOLEAN DEFAULT FALSE,
    in_app_enabled BOOLEAN DEFAULT TRUE,
    webhook_enabled BOOLEAN DEFAULT FALSE,
    alert_types_json JSONB DEFAULT '["drift", "system_health", "billing"]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notif_prefs_ws_user ON notification_preferences(workspace_id, user_id);

CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL,
    user_id UUID, -- NULL means broadcast to all admins in workspace
    type VARCHAR(50) NOT NULL, -- drift, repair, system, billing
    severity VARCHAR(20) NOT NULL, -- info, warning, critical
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'unread', -- unread, read, dismissed
    metadata_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    read_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_notifications_ws_user_status ON notifications(workspace_id, user_id, status);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at);

COMMIT;
