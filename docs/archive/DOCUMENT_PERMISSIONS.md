# Document Permissions in Cognimend

## Overview
Every document uploaded to Cognimend has a strict access scope and a defined permission level, enforced by the central `PermissionEngine`.

## Access Scopes
When uploading or managing a document, an admin/uploader must choose one of the following access scopes:

| Scope | Description |
|---|---|
| **Private** | Visible and queryable only by the user who uploaded it. |
| **Workspace** | Visible and queryable by all members of the workspace. |
| **Departments**| Visible and queryable only by members of the assigned departments. |
| **Users** | Visible and queryable only by specific, individually named users. |
| **Custom** | For highly granular access matrices (e.g., specific roles + specific users). |

## Permission Levels
Access is further divided into specific privileges:
- **View**: Can see the document exists but cannot use it in RAG queries.
- **Query**: Can retrieve answers from the document using the RAG query pipeline.
- **Upload**: Granted at the department/workspace level to allow adding new documents.
- **Delete**: Can permanently remove the document.
- **Manage**: Can change the permission scope and assigned users/departments.
- **Owner**: Full absolute control.

## Query Pipeline Integration
To guarantee security, the RAG Query Service does **not** rely solely on the backend database.
1. The `PermissionEngine` computes a list of allowed `document_ids` for the user.
2. The `qdrant_client.search` call is injected with a `MatchAny(any=allowed_document_ids)` filter.
3. This ensures that the vector similarity search is restricted to the user's explicit permission boundaries.
4. Cache keys incorporate a `permission_hash` to ensure two users querying the same question do not see cached answers drawn from documents they aren't authorized to access.
