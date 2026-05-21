# Security Notes

Cognimend handles user-uploaded documents and generated answers, so secrets and tenant isolation matter.

## Data Isolation

- Requests carry workspace and user context.
- Document retrieval is filtered by workspace and allowed document scope.
- Qdrant vector search uses workspace/document filters.
- Query cache keys include workspace, permission context, question, top-k, and verifier mode.

## Secrets

- API keys and database passwords belong in environment variables or a secret manager.
- Do not commit `.env` files with real values.
- Do not commit OpenRouter keys, database passwords, access tokens, local test credentials, or private account details.

## Uploads

Uploaded files are parsed and chunked before vector indexing. Treat uploaded document content as private user data.

## Trust and Verification

The Trust Engine reduces unsupported answer risk, but it does not replace human review for sensitive decisions. Strict Evidence Mode should be used when unsupported claims are unacceptable.
