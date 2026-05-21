# Role-Based Access Control (RBAC) Matrix

Cognimend uses a sophisticated, multi-tiered RBAC system divided into Platform Roles, Workspace Roles, and Department Roles.

## 1. Platform Roles
Assigned globally. Manage the entire SaaS platform.
- **Super Admin**: Full platform control. Can suspend users/workspaces, alter plans, and view billing. Cannot read customer documents without filing an Emergency Access Request.
- **Support Admin**: Can view users and system health to assist customers.
- **Security Admin**: Can view audit logs and suspend users/workspaces.
- **Billing Admin**: Platform-wide revenue and cost overview.
- **Platform Auditor**: Read-only access to platform audit logs.

## 2. Workspace Roles
Assigned per workspace. Manage an organization's specific instance.
- **Owner**: Absolute control over the workspace, billing, and all documents.
- **Admin**: Can manage users, departments, and documents. Cannot alter the subscription plan.
- **Billing Admin**: Manages workspace billing, usage, and invoices. Cannot read documents by default.
- **IT Admin**: Manages API keys and integrations.
- **Auditor**: Read-only access to workspace audit logs.
- **Member**: Standard user. Can view and query documents they have access to.
- **Viewer**: Read-only user. Cannot upload or run queries.

## 3. Department Roles
Assigned per department. Manage groups within a workspace.
- **Department Admin**: Can manage users and documents assigned specifically to their department.
- **Department Member**: Standard participant in the department.
- **Department Viewer**: Can view department activities but cannot run actions.

## Role Inheritance Rule
Higher-level management roles (e.g., Workspace Admin) automatically inherit access permissions for lower-level groupings (e.g., Departments). A Workspace Admin can manage all departments without explicitly needing a Department Admin role.
