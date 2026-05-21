# Cognimend Security Architecture

## Multi-Tenant Isolation
Cognimend uses a strict multi-tenant architecture. The fundamental boundary is the `workspace_id`.
- The Gateway intercepts all incoming requests, validates the JWT, and extracts the user's identities.
- The Gateway queries the central authentication database to verify the user belongs to the requested workspace.
- The Gateway strips any client-provided `X-Workspace-ID` and `X-User-ID` headers to prevent spoofing, and injects trusted headers.

## Central Permission Engine
Beyond basic workspace isolation, Cognimend implements granular Access Control via the `PermissionEngine`:
1. **Platform Roles**: Super Admin, Support Admin, etc.
2. **Workspace Roles**: Owner, Admin, Billing Admin, etc.
3. **Department Roles**: Department Admin, Member.
4. **Document Permissions**: Custom access matrices defining exactly who can view/query a document.

## RAG Query Safety
The RAG pipeline operates with CIA-grade security principles:
1. The `PermissionEngine` computes a list of allowed `document_ids` for a user before any vector search occurs.
2. The Qdrant vector database is queried with a strict filter: `workspace_id` AND `document_id IN (allowed_list)`.
3. If a user tries to ask a question about a restricted document, the system responds safely without revealing the document's existence.
4. Cache keys incorporate a `permission_hash` to ensure two users in the same workspace but with different permissions cannot cross-contaminate the query cache.

## Admin Audit Logs
Every sensitive action (inviting users, changing permissions, deleting documents, suspending users) is written to an immutable `admin_action_logs` table. This provides a cryptographically verifiable trail of actions for compliance.

## Emergency Access
Platform Super Admins cannot read customer documents by default. To investigate issues involving customer content, they must file an `Emergency Access Request` providing a reason. This request activates temporary access and logs every action taken under the emergency scope.
