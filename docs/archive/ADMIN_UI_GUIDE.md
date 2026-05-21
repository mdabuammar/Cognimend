# Admin UI Guide

The Cognimend frontend incorporates a strict RBAC (Role-Based Access Control) UX layer to complement the secure backend APIs.

## UI Principles
1. **Frontend Hiding is UX Only**: The frontend explicitly hides unauthorized buttons and panels (e.g., hiding the `API Keys` sidebar link for normal members). However, the ultimate security is enforced by the backend `PermissionEngine` and API Gateway.
2. **Premium Design**: The UI leverages Tailwind CSS with careful attention to whitespace, typography, and clear security warnings.
3. **No Name Leaks**: Document tables and matrix views never render document IDs or Titles that the user is not explicitly authorized to see.

## Super Admin Panel
- **Access**: Located at `/super-admin`. Only users with `X-Platform-Role` (super_admin, etc.) can view this.
- **Emergency Access**: If a Super Admin needs to read customer text, they must click the "Request Emergency Access" button located in the header. The UI blocks direct document fetches unless this session is active.

## Workspace Admin Panel
- **Access**: Located at `/workspaces/:id/admin`.
- **Components Used**:
  - `RequireRole` - A declarative React component that checks the current user's role against an allowed array.
  - `WorkspaceAdminOnly` - Preset for Owner/Admin.
  - `DepartmentAdminOnly` - Preset for Department Admins.
- **Invitation Flow**: The `InviteStaffModal` uses the `workspaceAdminAPI` to generate a secure token and link. If the SMTP server is down, the UI gracefully displays the cryptographic link for manual distribution.

## Document Permission UI
The `DocumentPermissionEditor` component provides a simple radio-button interface for assigning CIA-grade isolation:
- Private
- Workspace-wide
- Specific Departments
It clearly displays a "Security Guarantee" warning to assure the user that access isolation is absolute.

## Testing Frontend Permissions
To test the UI isolation locally:
1. Log in as a workspace `owner`. Verify the Admin Sidebar is visible.
2. Log in as a workspace `member`. Verify the `/admin` routes redirect to a 403 Forbidden or simply hide the navigation links.
3. Log in as an `it_admin`. Verify you can see the API Keys tab but the Documents tab is blocked.
