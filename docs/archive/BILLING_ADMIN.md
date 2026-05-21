# Billing Admin Role

The `billing_admin` is a specialized role designed for finance teams or accounting staff. 

## Philosophy
Billing Admins need to see invoices, credit card statuses, usage metrics, and subscription plans. They absolutely **do not** need to see sensitive uploaded documents (e.g., source code, legal contracts, HR records) or manage API keys.

## Platform Billing Admin
A user with `billing_admin` in the `platform_admins` table:
- Can view `GET /costs`, `GET /usage`, and `GET /billing` on the Super Admin API.
- Cannot view `GET /security`, `GET /users`, or read customer documents.
- Cannot suspend users or workspaces.

## Workspace Billing Admin
A user with `billing_admin` in the `workspace_members` table:
- Can view `GET /workspaces/{id}/admin/usage` and `GET /workspaces/{id}/admin/billing`.
- Can trigger `POST /workspaces/{id}/admin/billing/checkout` to update payment methods.
- Cannot access `GET /workspaces/{id}/admin/documents` or `GET /workspaces/{id}/admin/api-keys`.
- Cannot query documents via the RAG API unless explicitly granted permission to specific documents.
