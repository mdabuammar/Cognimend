-- Cognimend Enterprise RBAC Schema Update

-- 1. Staff Accounts
CREATE TABLE IF NOT EXISTS staff_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    staff_role VARCHAR(50) NOT NULL, -- support_agent, support_manager, operations_staff, billing_staff, security_staff, compliance_staff, customer_success, staff_admin
    status VARCHAR(20) DEFAULT 'active',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- 2. Support Tickets
CREATE TABLE IF NOT EXISTS support_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    assigned_staff_id UUID REFERENCES users(id) ON DELETE SET NULL,
    category VARCHAR(50),
    priority VARCHAR(20) DEFAULT 'medium', -- low, medium, high, urgent
    status VARCHAR(20) DEFAULT 'open', -- open, in_progress, pending_customer, resolved, closed
    title VARCHAR(255) NOT NULL,
    description TEXT,
    internal_notes_json JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- 3. Staff Activity Logs
CREATE TABLE IF NOT EXISTS staff_activity_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    staff_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(255) NOT NULL,
    target_workspace_id UUID,
    target_user_id UUID,
    metadata_json JSONB DEFAULT '{}'::jsonb,
    request_id VARCHAR(100),
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Audit Log Enhancements (Ensure table exists)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID,
    user_id UUID,
    action VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(100),
    metadata_json JSONB DEFAULT '{}'::jsonb,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Optional local role seeding
INSERT INTO platform_admins (user_id, role, status)
SELECT id, 'super_admin', 'active' FROM users WHERE email = current_setting('app.local_admin_email', true)
ON CONFLICT (user_id) DO UPDATE SET role = 'super_admin', status = 'active';

-- Add a test staff user if they exist
-- INSERT INTO staff_accounts (user_id, staff_role)
-- SELECT id, 'support_agent' FROM users WHERE email = current_setting('app.local_reviewer_email', true)
-- ON CONFLICT (user_id) DO UPDATE SET staff_role = 'support_agent';
