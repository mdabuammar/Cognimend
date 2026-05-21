# IT Admin & API Keys

Workspace administrators (specifically `owner`, `admin`, or `it_admin`) can generate API keys to programmatically interact with Cognimend's RAG endpoints.

## Features
- **Key Generation**: API keys are securely generated (`cm_` prefix) using CSPRNG.
- **Hash Storage**: Only the SHA-256 hash of the API key is stored in the database. If the database is compromised, the plaintext keys remain safe.
- **Scoped Access**: API keys can be restricted to specific endpoints (`scopes`), specific `department_ids`, or specific `document_ids`.
- **Expiration**: Keys can be configured to expire after a certain number of days.
- **Revocation**: Keys can be immediately revoked.

## Security Rule
An API Key is bound to the `user_id` of the creator and inherently inherits their maximum permission boundaries. However, the API key can be further constrained by explicit scopes. The central `PermissionEngine` evaluates the intersection of the user's rights and the API key's scopes.
