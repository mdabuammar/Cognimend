-- =============================================================================
-- Migration 004: Full SaaS Schema for Cognimend
-- =============================================================================
-- Adds: users, auth_accounts, workspaces, workspace_members, plans,
--       subscriptions, usage_records, audit_logs, api_keys,
--       connected_sources, oauth_tokens, synced_items, sync_jobs,
--       document_versions, conversations, query_feedback
-- =============================================================================

BEGIN;

-- =============================================================================
-- Extensions
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- updated_at trigger function (idempotent)
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Users
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   TEXT,                          -- NULL for Google-only accounts
    full_name       VARCHAR(255) NOT NULL DEFAULT '',
    avatar_url      TEXT,
    email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Auth Accounts (multiple auth providers per user)
-- =============================================================================

CREATE TABLE IF NOT EXISTS auth_accounts (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider             VARCHAR(50) NOT NULL,         -- 'local', 'google'
    provider_user_id     VARCHAR(255),                 -- Google sub
    provider_email       VARCHAR(255),
    provider_avatar_url  TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_auth_accounts_provider UNIQUE (provider, provider_user_id)
);

CREATE INDEX IF NOT EXISTS idx_auth_accounts_user ON auth_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_accounts_provider ON auth_accounts(provider, provider_user_id);

DROP TRIGGER IF EXISTS update_auth_accounts_updated_at ON auth_accounts;
CREATE TRIGGER update_auth_accounts_updated_at
    BEFORE UPDATE ON auth_accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Plans
-- =============================================================================

CREATE TABLE IF NOT EXISTS plans (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                 VARCHAR(50) UNIQUE NOT NULL,  -- free, personal, team, business, enterprise
    display_name         VARCHAR(100) NOT NULL,
    monthly_price_usd    NUMERIC(8,2) NOT NULL DEFAULT 0,
    yearly_price_usd     NUMERIC(8,2) NOT NULL DEFAULT 0,
    document_limit       INTEGER NOT NULL DEFAULT 3,
    query_limit_monthly  INTEGER NOT NULL DEFAULT 50,
    storage_limit_mb     INTEGER NOT NULL DEFAULT 10,
    max_file_size_mb     INTEGER NOT NULL DEFAULT 10,
    team_members_limit   INTEGER NOT NULL DEFAULT 1,
    connector_limit      INTEGER NOT NULL DEFAULT 0,
    has_analytics        BOOLEAN NOT NULL DEFAULT FALSE,
    has_drift_detection  BOOLEAN NOT NULL DEFAULT FALSE,
    has_api_access       BOOLEAN NOT NULL DEFAULT FALSE,
    has_audit_logs       BOOLEAN NOT NULL DEFAULT FALSE,
    has_connectors       BOOLEAN NOT NULL DEFAULT FALSE,
    has_chat_history     BOOLEAN NOT NULL DEFAULT FALSE,
    has_export           BOOLEAN NOT NULL DEFAULT FALSE,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Workspaces
-- =============================================================================

CREATE TABLE IF NOT EXISTS workspaces (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(255) UNIQUE,
    owner_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id     UUID REFERENCES plans(id),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workspaces_owner ON workspaces(owner_id);

DROP TRIGGER IF EXISTS update_workspaces_updated_at ON workspaces;
CREATE TRIGGER update_workspaces_updated_at
    BEFORE UPDATE ON workspaces
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Workspace Members
-- =============================================================================

CREATE TABLE IF NOT EXISTS workspace_members (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role          VARCHAR(20) NOT NULL DEFAULT 'member'
                  CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    status        VARCHAR(20) NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'pending', 'suspended')),
    invited_by    UUID REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_workspace_member UNIQUE (workspace_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_members_workspace ON workspace_members(workspace_id);
CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id);

DROP TRIGGER IF EXISTS update_workspace_members_updated_at ON workspace_members;
CREATE TRIGGER update_workspace_members_updated_at
    BEFORE UPDATE ON workspace_members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Subscriptions
-- =============================================================================

CREATE TABLE IF NOT EXISTS subscriptions (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id          UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    plan_id               UUID NOT NULL REFERENCES plans(id),
    status                VARCHAR(20) NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'cancelled', 'past_due', 'trialing')),
    billing_cycle         VARCHAR(10) NOT NULL DEFAULT 'monthly'
                          CHECK (billing_cycle IN ('monthly', 'yearly')),
    current_period_start  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_period_end    TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days'),
    stripe_subscription_id VARCHAR(255),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_workspace ON subscriptions(workspace_id);

DROP TRIGGER IF EXISTS update_subscriptions_updated_at ON subscriptions;
CREATE TRIGGER update_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Alter existing documents table to add workspace_id and SaaS fields
-- =============================================================================

DO $$
BEGIN
    -- Add workspace_id if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='workspace_id') THEN
        ALTER TABLE documents ADD COLUMN workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE;
    END IF;

    -- Add uploaded_by if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='uploaded_by') THEN
        ALTER TABLE documents ADD COLUMN uploaded_by UUID REFERENCES users(id);
    END IF;

    -- Add file_type if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='file_type') THEN
        ALTER TABLE documents ADD COLUMN file_type VARCHAR(20);
    END IF;

    -- Add file_size if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='file_size') THEN
        ALTER TABLE documents ADD COLUMN file_size BIGINT;
    END IF;

    -- Add storage_path if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='storage_path') THEN
        ALTER TABLE documents ADD COLUMN storage_path TEXT;
    END IF;

    -- Add source_type if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='source_type') THEN
        ALTER TABLE documents ADD COLUMN source_type VARCHAR(30) DEFAULT 'upload';
    END IF;

    -- Add connected_source_id if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='connected_source_id') THEN
        ALTER TABLE documents ADD COLUMN connected_source_id UUID;
    END IF;

    -- Add source_url if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='source_url') THEN
        ALTER TABLE documents ADD COLUMN source_url TEXT;
    END IF;

    -- Add page_count if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='page_count') THEN
        ALTER TABLE documents ADD COLUMN page_count INTEGER;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace_id);
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_documents_workspace_status ON documents(workspace_id, status);

-- =============================================================================
-- Alter existing queries table to add workspace/user/conversation fields
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='queries' AND column_name='workspace_id') THEN
        ALTER TABLE queries ADD COLUMN workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='queries' AND column_name='conversation_id') THEN
        ALTER TABLE queries ADD COLUMN conversation_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='queries' AND column_name='answer') THEN
        ALTER TABLE queries ADD COLUMN answer TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='queries' AND column_name='confidence_score') THEN
        ALTER TABLE queries ADD COLUMN confidence_score NUMERIC(5,4);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='queries' AND column_name='model_used') THEN
        ALTER TABLE queries ADD COLUMN model_used VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='queries' AND column_name='tokens_used') THEN
        ALTER TABLE queries ADD COLUMN tokens_used INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='queries' AND column_name='estimated_cost') THEN
        ALTER TABLE queries ADD COLUMN estimated_cost NUMERIC(10,6);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='queries' AND column_name='sources_json') THEN
        ALTER TABLE queries ADD COLUMN sources_json JSONB DEFAULT '[]';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_queries_workspace ON queries(workspace_id);

-- =============================================================================
-- Conversations
-- =============================================================================

CREATE TABLE IF NOT EXISTS conversations (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title         VARCHAR(500),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_workspace ON conversations(workspace_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);

DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations;
CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Query Feedback (replaces old feedback table pattern)
-- =============================================================================

CREATE TABLE IF NOT EXISTS query_feedback (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_id    UUID NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating      VARCHAR(10) NOT NULL CHECK (rating IN ('helpful', 'not_helpful')),
    reason      VARCHAR(50),      -- wrong_answer, missing_source, hallucinated, etc.
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_query_feedback UNIQUE (query_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_query_feedback_query ON query_feedback(query_id);

-- =============================================================================
-- Usage Records
-- =============================================================================

CREATE TABLE IF NOT EXISTS usage_records (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id),
    event_type      VARCHAR(50) NOT NULL,  -- document_uploaded, query_made, storage_used
    quantity        INTEGER NOT NULL DEFAULT 1,
    tokens_used     INTEGER,
    estimated_cost  NUMERIC(10,6),
    period_start    TIMESTAMPTZ NOT NULL DEFAULT date_trunc('month', NOW()),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_records_workspace ON usage_records(workspace_id);
CREATE INDEX IF NOT EXISTS idx_usage_records_period ON usage_records(workspace_id, period_start);

-- =============================================================================
-- Audit Logs
-- =============================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id  UUID REFERENCES workspaces(id),
    user_id       UUID REFERENCES users(id),
    action        VARCHAR(100) NOT NULL,       -- user.signup, document.upload, etc.
    entity_type   VARCHAR(50),
    entity_id     VARCHAR(255),
    metadata_json JSONB DEFAULT '{}',
    ip_address    VARCHAR(45),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_workspace ON audit_logs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC);

-- =============================================================================
-- API Keys (for Business/Enterprise developer API access)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name          VARCHAR(100) NOT NULL,
    key_hash      VARCHAR(255) NOT NULL UNIQUE,   -- SHA-256 hash of the key
    key_prefix    VARCHAR(10) NOT NULL,            -- First 8 chars, shown in UI
    last_used_at  TIMESTAMPTZ,
    created_by    UUID NOT NULL REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_workspace ON api_keys(workspace_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);

-- =============================================================================
-- Connected Sources (Connector System)
-- =============================================================================

CREATE TABLE IF NOT EXISTS connected_sources (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id          UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    provider              VARCHAR(50) NOT NULL,   -- google_drive, onedrive, notion, etc.
    provider_account_email VARCHAR(255),
    display_name          VARCHAR(255),
    status                VARCHAR(20) NOT NULL DEFAULT 'connected'
                          CHECK (status IN ('connected', 'disconnected', 'error', 'syncing')),
    scopes                TEXT[],
    last_synced_at        TIMESTAMPTZ,
    created_by            UUID NOT NULL REFERENCES users(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_connected_sources_workspace ON connected_sources(workspace_id);

DROP TRIGGER IF EXISTS update_connected_sources_updated_at ON connected_sources;
CREATE TRIGGER update_connected_sources_updated_at
    BEFORE UPDATE ON connected_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- OAuth Tokens (encrypted, for connector services)
-- =============================================================================

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connected_source_id       UUID NOT NULL REFERENCES connected_sources(id) ON DELETE CASCADE,
    access_token_encrypted    TEXT NOT NULL,
    refresh_token_encrypted   TEXT,
    expires_at                TIMESTAMPTZ,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oauth_tokens_source ON oauth_tokens(connected_source_id);

DROP TRIGGER IF EXISTS update_oauth_tokens_updated_at ON oauth_tokens;
CREATE TRIGGER update_oauth_tokens_updated_at
    BEFORE UPDATE ON oauth_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Synced Items (files imported from connectors)
-- =============================================================================

CREATE TABLE IF NOT EXISTS synced_items (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id          UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    connected_source_id   UUID NOT NULL REFERENCES connected_sources(id) ON DELETE CASCADE,
    provider_item_id      VARCHAR(500) NOT NULL,
    provider_parent_id    VARCHAR(500),
    item_type             VARCHAR(20) NOT NULL DEFAULT 'file',
    title                 VARCHAR(500),
    mime_type             VARCHAR(100),
    source_url            TEXT,
    last_modified_at      TIMESTAMPTZ,
    content_hash          VARCHAR(64),
    sync_status           VARCHAR(20) NOT NULL DEFAULT 'pending'
                          CHECK (sync_status IN ('pending', 'synced', 'failed', 'deleted')),
    document_id           UUID REFERENCES documents(id),
    last_synced_at        TIMESTAMPTZ,
    error_message         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_synced_item UNIQUE (connected_source_id, provider_item_id)
);

CREATE INDEX IF NOT EXISTS idx_synced_items_workspace ON synced_items(workspace_id);
CREATE INDEX IF NOT EXISTS idx_synced_items_source ON synced_items(connected_source_id);

DROP TRIGGER IF EXISTS update_synced_items_updated_at ON synced_items;
CREATE TRIGGER update_synced_items_updated_at
    BEFORE UPDATE ON synced_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Sync Jobs
-- =============================================================================

CREATE TABLE IF NOT EXISTS sync_jobs (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id         UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    connected_source_id  UUID NOT NULL REFERENCES connected_sources(id) ON DELETE CASCADE,
    job_type             VARCHAR(20) NOT NULL DEFAULT 'full',
    status               VARCHAR(20) NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    started_at           TIMESTAMPTZ,
    finished_at          TIMESTAMPTZ,
    total_items          INTEGER DEFAULT 0,
    synced_items_count   INTEGER DEFAULT 0,
    failed_items         INTEGER DEFAULT 0,
    error_message        TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sync_jobs_workspace ON sync_jobs(workspace_id);

-- =============================================================================
-- Document Versions
-- =============================================================================

CREATE TABLE IF NOT EXISTS document_versions (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id        UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number     INTEGER NOT NULL DEFAULT 1,
    content_hash       VARCHAR(64) NOT NULL,
    source_modified_at TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_doc_versions_document ON document_versions(document_id);

-- =============================================================================
-- Alter drift_events to add workspace_id
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='drift_events' AND column_name='workspace_id') THEN
        ALTER TABLE drift_events ADD COLUMN workspace_id UUID REFERENCES workspaces(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='drift_events' AND column_name='metric_value') THEN
        ALTER TABLE drift_events ADD COLUMN metric_value NUMERIC(10,4);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='drift_events' AND column_name='p_value') THEN
        ALTER TABLE drift_events ADD COLUMN p_value NUMERIC(10,6);
    END IF;
END $$;

-- =============================================================================
-- Remediation Actions
-- =============================================================================

CREATE TABLE IF NOT EXISTS remediation_actions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    UUID REFERENCES workspaces(id),
    drift_event_id  UUID REFERENCES drift_events(id),
    action_type     VARCHAR(100) NOT NULL,
    old_config      JSONB,
    new_config      JSONB,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'applied', 'failed', 'rolled_back')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS update_remediation_actions_updated_at ON remediation_actions;
CREATE TRIGGER update_remediation_actions_updated_at
    BEFORE UPDATE ON remediation_actions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Password Reset Tokens
-- =============================================================================

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '1 hour'),
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reset_tokens_hash ON password_reset_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_user ON password_reset_tokens(user_id);

-- =============================================================================
-- Refresh Tokens (for JWT rotation)
-- =============================================================================

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days'),
    revoked_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);

COMMIT;
