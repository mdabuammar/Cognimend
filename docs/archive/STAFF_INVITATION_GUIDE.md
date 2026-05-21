# Staff Invitation Guide

Cognimend provides a secure email-based invitation system for adding staff to your workspace.

## Invitation Flow
1. **Initiate**: The Workspace Admin goes to the **Users** panel and clicks **Invite Staff**.
2. **Details**: The admin provides the staff member's email, workspace role, and optionally assigns them to a specific department.
3. **Dispatch**: The system generates a cryptographic token and sends an email with an invitation link. If the SMTP server is not configured, the secure link is returned directly to the admin for manual sharing.
4. **Acceptance**: 
   - When the user clicks the link, they see an invitation overview.
   - If they are a new user, they complete the signup process.
   - If they are an existing user, they log in.
   - The token is consumed, and the user is instantly added to the workspace and the assigned department.

## Security Considerations
- **Tokens**: Tokens are random 48-character strings, hashed in the database (SHA-256) to prevent leakage if the database is compromised.
- **Expiration**: Invitations expire in 7 days by default (configurable via `INVITE_EXPIRE_DAYS`).
- **Revocation**: Admins can revoke pending invitations at any time. Revoked invitations immediately become invalid.
- **One-time Use**: Once an invitation is accepted, it is permanently marked as used and cannot be shared.

## API Endpoints
- `POST /workspaces/{id}/admin/invitations` - Create invite
- `GET /workspaces/{id}/admin/invitations` - List pending/accepted invites
- `POST /workspaces/{id}/admin/invitations/{id}/revoke` - Cancel invite
- `GET /invite/{token}` - Public endpoint to retrieve invite info
- `POST /invite/{token}/accept` - Consume invite token (requires authentication)
