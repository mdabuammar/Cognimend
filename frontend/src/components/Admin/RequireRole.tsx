import React from 'react';

// Types for RBAC
export type PlatformRole = 'super_admin' | 'support_admin' | 'security_admin' | 'billing_admin' | 'platform_auditor';
export type WorkspaceRole = 'owner' | 'admin' | 'billing_admin' | 'it_admin' | 'department_admin' | 'member' | 'viewer';

interface RequireRoleProps {
  userRole?: string | null;
  allowedRoles: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * A declarative component to hide UI elements if the user lacks the required role.
 * IMPORTANT: This is for UX only. The backend ALWAYS enforces actual permissions.
 */
export const RequireRole: React.FC<RequireRoleProps> = ({ userRole, allowedRoles, children, fallback = null }) => {
  if (!userRole) return <>{fallback}</>;
  if (allowedRoles.includes(userRole)) {
    return <>{children}</>;
  }
  return <>{fallback}</>;
};

// Common Presets
export const SuperAdminOnly: React.FC<{ userRole: string; children: React.ReactNode }> = ({ userRole, children }) => (
  <RequireRole userRole={userRole} allowedRoles={['super_admin']} children={children} />
);

export const WorkspaceAdminOnly: React.FC<{ userRole: string; children: React.ReactNode }> = ({ userRole, children }) => (
  <RequireRole userRole={userRole} allowedRoles={['owner', 'admin']} children={children} />
);

export const BillingAdminOnly: React.FC<{ userRole: string; children: React.ReactNode }> = ({ userRole, children }) => (
  <RequireRole userRole={userRole} allowedRoles={['owner', 'admin', 'billing_admin']} children={children} />
);

export const DepartmentAdminOnly: React.FC<{ userRole: string; children: React.ReactNode }> = ({ userRole, children }) => (
  <RequireRole userRole={userRole} allowedRoles={['owner', 'admin', 'department_admin']} children={children} />
);

export const ITAdminOnly: React.FC<{ userRole: string; children: React.ReactNode }> = ({ userRole, children }) => (
  <RequireRole userRole={userRole} allowedRoles={['owner', 'admin', 'it_admin']} children={children} />
);
