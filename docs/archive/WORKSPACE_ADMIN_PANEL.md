# Workspace Admin Panel

The Workspace Admin Panel allows organization owners and designated administrators to manage their Cognimend instance.

## Features
- **User Management**: View all workspace members. Change roles, assign members to departments, or suspend them.
- **Department Management**: Create logical groupings (e.g., HR, IT) to compartmentalize sensitive RAG documents.
- **Document Management**: View uploaded documents and their explicit access scopes. Modify who can query a document.
- **API Keys**: Manage programmatic access via scoped API keys.
- **Billing & Usage**: View workspace-level token usage and manage the billing subscription.
- **Security**: View workspace-scoped audit logs and permission denied events.

## Role Restrictions
- **Owner / Admin**: Full access to the panel.
- **Department Admin**: Can only manage users and documents within their specific department.
- **IT Admin**: Can only manage API Keys and integrations.
- **Billing Admin**: Can only manage checkout, usage limits, and invoices. Cannot view/manage documents.

## API Endpoints (Port 8009)
Requires `X-User-Role` headers (`owner`, `admin`, `department_admin`, etc.).
- `GET /workspaces/{id}/admin/overview`
- `GET /workspaces/{id}/admin/users`, `PATCH /users/{id}/role`
- `GET /workspaces/{id}/admin/departments`
- `GET /workspaces/{id}/admin/documents`
- `GET /workspaces/{id}/admin/api-keys`
- `GET /workspaces/{id}/admin/billing`, `GET /usage`
- `GET /workspaces/{id}/admin/audit-logs`
