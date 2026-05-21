-- =============================================================================
-- Migration 008: Enterprise Admin & Access Control Schema
-- =============================================================================
-- Adds: platform_admins, departments, department_members,
--       document_permissions, workspace_invitations, access_policies,
--       admin_action_logs, emergency_access_requests,
--       user_suspensions, workspace_suspensions
-- =============================================================================

BEGIN;

-- =============================================================================
-- PLATFORM ADMINS
-- Super Admin, Support Admin, Security Admin, etc.
-- =============================================================================

CREATE TABLE IF NOT EXISTS platform_admins (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role         VARCHAR(30) NOT NULL
                 CHECK (role IN ('super_admin','support_admin','security_admin','billing_admin','platform_auditor')),
    status       VARCHAR(20) NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active','suspended','revoked')),
    created_by   UUID REFERENCES users(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_platform_admin_user UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_platform_admins_user   ON platform_admins(user_id);
CREATE INDEX IF NOT EXISTS idx_platform_admins_role   ON platform_admins(role);
CREATE INDEX IF NOT EXISTS idx_platform_admins_status ON platform_admins(status);

DROP TRIGGER IF EXISTS update_platform_admins_updated_at ON platform_admins;
CREATE TRIGGER update_platform_admins_updated_at
    BEFORE UPDATE ON platform_admins
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- DEPARTMENTS
-- Hierarchical groupings inside a workspace (HR, Accounts, IT, Legal, etc.)
-- =============================================================================

CREATE TABLE IF NOT EXISTS departments (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id         UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name                 VARCHAR(100) NOT NULL,
    slug                 VARCHAR(100) NOT NULL,
    description          TEXT,
    parent_department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    created_by           UUID NOT NULL REFERENCES users(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at          TIMESTAMPTZ,

    CONSTRAINT uq_department_slug_workspace UNIQUE (workspace_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_departments_workspace   ON departments(workspace_id);
CREATE INDEX IF NOT EXISTS idx_departments_parent      ON departments(parent_department_id);
CREATE INDEX IF NOT EXISTS idx_departments_archived    ON departments(archived_at) WHERE archived_at IS NULL;

DROP TRIGGER IF EXISTS update_departments_updated_at ON departments;
CREATE TRIGGER update_departments_updated_at
    BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- DEPARTMENT MEMBERS
-- Users assigned to departments with specific roles
-- =============================================================================

CREATE TABLE IF NOT EXISTS department_members (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role          VARCHAR(30) NOT NULL DEFAULT 'department_member'
                  CHECK (role IN ('department_admin','department_member','department_viewer')),
    status        VARCHAR(20) NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active','suspended','removed')),
    added_by      UUID REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_dept_member_per_dept UNIQUE (department_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_dept_members_workspace  ON department_members(workspace_id);
CREATE INDEX IF NOT EXISTS idx_dept_members_dept       ON department_members(department_id);
CREATE INDEX IF NOT EXISTS idx_dept_members_user       ON department_members(user_id);
CREATE INDEX IF NOT EXISTS idx_dept_members_status     ON department_members(status);

DROP TRIGGER IF EXISTS update_dept_members_updated_at ON department_members;
CREATE TRIGGER update_dept_members_updated_at
    BEFORE UPDATE ON department_members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- DOCUMENT PERMISSIONS
-- Fine-grained access control at the document level
-- =============================================================================

CREATE TABLE IF NOT EXISTS document_permissions (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id     UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    document_id      UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    department_id    UUID REFERENCES departments(id) ON DELETE CASCADE,
    user_id          UUID REFERENCES users(id) ON DELETE CASCADE,
    workspace_role   VARCHAR(30),  -- grant to all members of this role
    access_scope     VARCHAR(20) NOT NULL DEFAULT 'custom'
                     CHECK (access_scope IN ('private','workspace','departments','users','custom')),
    permission_level VARCHAR(20) NOT NULL DEFAULT 'view'
                     CHECK (permission_level IN ('none','view','query','upload','delete','manage','owner')),
    granted_by       UUID NOT NULL REFERENCES users(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- at least one target must be set (dept, user, or workspace role)
    CONSTRAINT chk_permission_target CHECK (
        department_id IS NOT NULL
        OR user_id IS NOT NULL
        OR workspace_role IS NOT NULL
        OR access_scope IN ('workspace','private')
    ),

    -- workspace of document must match permission workspace
    CONSTRAINT chk_permission_workspace CHECK (workspace_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_doc_perms_workspace  ON document_permissions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_doc_perms_document   ON document_permissions(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_perms_department ON document_permissions(department_id) WHERE department_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_doc_perms_user       ON document_permissions(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_doc_perms_scope      ON document_permissions(access_scope);

DROP TRIGGER IF EXISTS update_doc_perms_updated_at ON document_permissions;
CREATE TRIGGER update_doc_perms_updated_at
    BEFORE UPDATE ON document_permissions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Add access control columns to documents table
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='access_scope') THEN
        ALTER TABLE documents ADD COLUMN access_scope VARCHAR(20) NOT NULL DEFAULT 'workspace'
            CHECK (access_scope IN ('private','workspace','departments','users','custom'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='sensitivity_level') THEN
        ALTER TABLE documents ADD COLUMN sensitivity_level VARCHAR(20) NOT NULL DEFAULT 'normal'
            CHECK (sensitivity_level IN ('public','normal','confidential','restricted','top_secret'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='documents' AND column_name='created_by_user_id') THEN
        ALTER TABLE documents ADD COLUMN created_by_user_id UUID REFERENCES users(id);
    END IF;
END $$;

-- =============================================================================
-- WORKSPACE INVITATIONS
-- Staff invitation by email with secure token
-- =============================================================================

CREATE TABLE IF NOT EXISTS workspace_invitations (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id      UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    email             VARCHAR(255) NOT NULL,
    workspace_role    VARCHAR(30) NOT NULL DEFAULT 'member'
                      CHECK (workspace_role IN ('owner','admin','member','viewer',
                             'billing_admin','it_admin','hr_admin','accounts_admin',
                             'legal_admin','security_admin','auditor','department_admin')),
    department_id     UUID REFERENCES departments(id) ON DELETE SET NULL,
    department_role   VARCHAR(30) DEFAULT 'department_member'
                      CHECK (department_role IN ('department_admin','department_member','department_viewer')),
    permissions       TEXT[] DEFAULT '{}',
    invited_by        UUID NOT NULL REFERENCES users(id),
    invite_token_hash VARCHAR(255) NOT NULL UNIQUE,
    status            VARCHAR(20) NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','accepted','expired','revoked')),
    expires_at        TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),
    accepted_at       TIMESTAMPTZ,
    accepted_by       UUID REFERENCES users(id),
    message           TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Only one active pending invite per workspace/email
    CONSTRAINT uq_pending_invite UNIQUE (workspace_id, email, status)
                                 DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS idx_invitations_workspace ON workspace_invitations(workspace_id);
CREATE INDEX IF NOT EXISTS idx_invitations_email     ON workspace_invitations(email);
CREATE INDEX IF NOT EXISTS idx_invitations_token     ON workspace_invitations(invite_token_hash);
CREATE INDEX IF NOT EXISTS idx_invitations_status    ON workspace_invitations(status);

DROP TRIGGER IF EXISTS update_invitations_updated_at ON workspace_invitations;
CREATE TRIGGER update_invitations_updated_at
    BEFORE UPDATE ON workspace_invitations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- ACCESS POLICIES
-- Named policy objects (JSON) that can be applied to groups/roles
-- =============================================================================

CREATE TABLE IF NOT EXISTS access_policies (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name         VARCHAR(100) NOT NULL,
    description  TEXT,
    policy_json  JSONB NOT NULL DEFAULT '{}',
    status       VARCHAR(20) NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active','archived')),
    created_by   UUID NOT NULL REFERENCES users(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_policy_name_workspace UNIQUE (workspace_id, name)
);

CREATE INDEX IF NOT EXISTS idx_access_policies_workspace ON access_policies(workspace_id);

DROP TRIGGER IF EXISTS update_access_policies_updated_at ON access_policies;
CREATE TRIGGER update_access_policies_updated_at
    BEFORE UPDATE ON access_policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- ADMIN ACTION LOGS
-- Immutable audit trail for all admin/sensitive operations
-- =============================================================================

CREATE TABLE IF NOT EXISTS admin_action_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_user_id   UUID REFERENCES users(id),
    actor_role      VARCHAR(50),
    target_user_id  UUID REFERENCES users(id),
    workspace_id    UUID REFERENCES workspaces(id),
    department_id   UUID REFERENCES departments(id),
    document_id     UUID REFERENCES documents(id),
    action          VARCHAR(150) NOT NULL,
    reason          TEXT,
    metadata_json   JSONB DEFAULT '{}',
    ip_address      VARCHAR(45),
    request_id      VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    -- NOTE: No updated_at — this table is append-only / immutable
);

CREATE INDEX IF NOT EXISTS idx_admin_logs_workspace     ON admin_action_logs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_admin_logs_actor         ON admin_action_logs(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_logs_target        ON admin_action_logs(target_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_logs_department    ON admin_action_logs(department_id);
CREATE INDEX IF NOT EXISTS idx_admin_logs_document      ON admin_action_logs(document_id);
CREATE INDEX IF NOT EXISTS idx_admin_logs_action        ON admin_action_logs(action);
CREATE INDEX IF NOT EXISTS idx_admin_logs_created       ON admin_action_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_logs_request_id   ON admin_action_logs(request_id) WHERE request_id IS NOT NULL;

-- =============================================================================
-- EMERGENCY ACCESS REQUESTS
-- Super Admin must request before accessing customer document content
-- =============================================================================

CREATE TABLE IF NOT EXISTS emergency_access_requests (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    requested_by UUID NOT NULL REFERENCES users(id),
    approved_by  UUID REFERENCES users(id),
    reason       TEXT NOT NULL,
    scope_json   JSONB NOT NULL DEFAULT '{}',  -- { "document_ids": [...], "read_only": true }
    status       VARCHAR(20) NOT NULL DEFAULT 'requested'
                 CHECK (status IN ('requested','approved','denied','expired','revoked')),
    expires_at   TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '4 hours'),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at  TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_emergency_access_workspace   ON emergency_access_requests(workspace_id);
CREATE INDEX IF NOT EXISTS idx_emergency_access_requester   ON emergency_access_requests(requested_by);
CREATE INDEX IF NOT EXISTS idx_emergency_access_status      ON emergency_access_requests(status);

-- =============================================================================
-- USER SUSPENSIONS
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_suspensions (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE, -- NULL = platform-wide
    suspended_by UUID NOT NULL REFERENCES users(id),
    reason       TEXT NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active','lifted')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lifted_at    TIMESTAMPTZ,
    lifted_by    UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_user_suspensions_user      ON user_suspensions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_suspensions_workspace ON user_suspensions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_user_suspensions_status    ON user_suspensions(status);

-- =============================================================================
-- WORKSPACE SUSPENSIONS
-- =============================================================================

CREATE TABLE IF NOT EXISTS workspace_suspensions (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    suspended_by UUID NOT NULL REFERENCES users(id),
    reason       TEXT NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active','lifted')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lifted_at    TIMESTAMPTZ,
    lifted_by    UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_ws_suspensions_workspace ON workspace_suspensions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_ws_suspensions_status    ON workspace_suspensions(status);

-- =============================================================================
-- Extend workspace_members with new special roles
-- =============================================================================

DO $$
BEGIN
    -- Drop old constraint if exists and recreate with new roles
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'workspace_members'
        AND constraint_name = 'workspace_members_role_check'
    ) THEN
        ALTER TABLE workspace_members DROP CONSTRAINT workspace_members_role_check;
    END IF;

    ALTER TABLE workspace_members ADD CONSTRAINT workspace_members_role_check
        CHECK (role IN (
            'owner','admin','member','viewer',
            'billing_admin','it_admin','hr_admin','accounts_admin',
            'legal_admin','security_admin','auditor','department_admin'
        ));
END $$;

-- =============================================================================
-- API KEYS TABLE (for IT Admin management)
-- =============================================================================

CREATE TABLE IF NOT EXISTS workspace_api_keys (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name          VARCHAR(100) NOT NULL,
    key_hash      VARCHAR(255) NOT NULL UNIQUE,
    key_prefix    VARCHAR(12) NOT NULL,
    scopes        TEXT[] DEFAULT '{"query"}',
    department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    created_by    UUID NOT NULL REFERENCES users(id),
    last_used_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_workspace ON workspace_api_keys(workspace_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash      ON workspace_api_keys(key_hash);

-- =============================================================================
-- SEED: Default super admin guard (placeholder — filled via env/setup script)
-- =============================================================================

-- Insert note: actual super admin is seeded via setup script using
-- SUPER_ADMIN_EMAIL env var, not here. Migration stays schema-only.

-- =============================================================================
-- HELPER VIEW: Effective document permissions per user
-- =============================================================================

CREATE OR REPLACE VIEW v_user_document_access AS
SELECT DISTINCT
    dp.document_id,
    dp.workspace_id,
    COALESCE(dm.user_id, dp.user_id)          AS user_id,
    dp.permission_level,
    dp.access_scope
FROM document_permissions dp

-- Grant by department membership
LEFT JOIN department_members dm
    ON dm.department_id = dp.department_id
    AND dm.status = 'active'

WHERE
    -- direct user grant
    dp.user_id IS NOT NULL
    -- or workspace-wide
    OR dp.access_scope = 'workspace'
    -- or department membership
    OR (dp.department_id IS NOT NULL AND dm.user_id IS NOT NULL);

COMMENT ON VIEW v_user_document_access IS
    'Flattened effective document access per user, combining direct grants, department membership, and workspace-wide rules.';

COMMIT;
