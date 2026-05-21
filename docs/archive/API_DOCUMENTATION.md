# API Documentation

## Query API Trust Engine Fields

`POST /query` accepts `verifier_mode` as `fast`, `verified`, or `strict`. Default is `verified`.

The response includes backend-computed trust fields:

- `citation_truth_score`: number or null
- `citation_quality_label`: `strong`, `partial`, `weak`, or null
- `citation_verifications`: citation support checks with `support_status`, `support_score`, related claims, and explanation
- `conflict_detected`: boolean
- `conflict_summary`: string or null
- `conflict_sources`: source snippets involved in a verified conflict
- `evidence_gap_detected`: boolean
- `evidence_gap_summary`: string or null
- `missing_information`: safe list of missing facts or source context
- `suggested_actions`: safe user actions such as uploading a relevant document or reprocessing files
- `freshness_warning`: string or null
- `latest_source_id`: string or null
- `trust_mode`: active trust mode

Each citation/source can include:

- `uploaded_at`
- `document_created_at`
- `document_updated_at`
- `source_freshness_label`: `latest`, `recent`, `older`, or `unknown`
- `is_latest_relevant_source`

Raw judge prompts, thresholds, p-values, internal config JSON, `top_k`, and candidate IDs are not exposed in the UI.

## Trust Engine Repair Behavior

Repair candidates can include:

- `repair_reason`
- `evidence_signal`
- `recommended_action_type`
- `user_friendly_message`

Evidence gaps are marked as user action needed or manual review. Low citation truth produces citation-focused repairs. Conflicts produce conflict-aware answer behavior. Freshness warnings preserve visible source-date caveats.

# API Documentation updates for Admin Control Layer

This document outlines the new API routes added for the high-security administrative control layer.

## Super Admin API (Port 8008)
Requires `X-Platform-Role: super_admin`.

- `GET /overview` - Platform-wide statistics
- `GET /users` - List all users across the platform
- `POST /users/{id}/suspend` - Suspend a user globally
- `POST /users/{id}/unsuspend` - Lift user suspension
- `GET /workspaces` - List all workspaces
- `POST /workspaces/{id}/suspend` - Suspend a workspace
- `POST /workspaces/{id}/unsuspend` - Lift workspace suspension
- `POST /workspaces/{id}/override-plan` - Change a workspace plan
- `GET /system-health` - Global microservice status
- `GET /costs` - Platform-wide API costs
- `GET /security` - Security events and denied access logs
- `GET /emergency-access` - List emergency access requests and active sessions
- `POST /emergency-access/request` - Request temporary access to customer content
  - Payload: `{ "workspace_id": "uuid", "reason": "string", "document_ids": ["uuid"] }`
- `POST /emergency-access/{id}/approve` - Approve a request (Super/Security Admin only)
  - Payload: `{ "reason": "string" }`
- `POST /emergency-access/{id}/revoke` - Immediately terminate a session
  - Payload: `{ "reason": "string" }`
- `GET /audit-logs` - Query platform-wide audit trail with filters (actor, workspace, action)
- `GET /audit-logs/export` - Export filtered logs as CSV/PDF (Super Admin/Auditor only)

## Workspace Admin API (Port 8009)
Requires Workspace Owner, Admin, or specific Department Admin roles.

- `GET /workspaces/{id}/admin/overview` - Workspace statistics
- `POST /workspaces/{id}/admin/invitations` - Create staff invite
- `GET /workspaces/{id}/admin/invitations` - List invites
- `POST /workspaces/{id}/admin/invitations/{invite_id}/revoke` - Cancel invite
- `GET /invite/{token}` - Public link to resolve invite data
- `POST /invite/{token}/accept` - Consume invite (must be logged in)
- `GET /workspaces/{id}/admin/departments` - List departments
- `POST /workspaces/{id}/admin/departments` - Create department
- `PATCH /workspaces/{id}/admin/departments/{id}` - Edit department
- `DELETE /workspaces/{id}/admin/departments/{id}` - Archive department
- `POST /workspaces/{id}/admin/departments/{id}/members` - Add user to department
- `DELETE /workspaces/{id}/admin/departments/{id}/members/{user_id}` - Remove user
- `GET /workspaces/{id}/admin/documents` - List workspace documents and permissions
- `POST /workspaces/{id}/admin/documents/permissions` - Apply access scope to document
- `GET /workspaces/{id}/admin/audit-logs` - Workspace-scoped audit trail
