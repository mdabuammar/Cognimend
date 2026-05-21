import os

paths = [
    'frontend/src/pages/WorkspaceAdmin/WorkspaceAdminDepartmentsPage.tsx',
    'frontend/src/pages/WorkspaceAdmin/WorkspaceAdminDocumentsPage.tsx',
    'frontend/src/pages/WorkspaceAdmin/WorkspaceAdminAccessControlPage.tsx',
    'frontend/src/pages/WorkspaceAdmin/WorkspaceAdminAuditLogsPage.tsx',
    'frontend/src/pages/WorkspaceAdmin/WorkspaceAdminUsagePage.tsx',
    'frontend/src/pages/WorkspaceAdmin/WorkspaceAdminSecurityPage.tsx',
    'frontend/src/pages/WorkspaceAdmin/WorkspaceAdminApiKeysPage.tsx',
    'frontend/src/pages/WorkspaceAdmin/WorkspaceAdminBillingPage.tsx',
    'frontend/src/pages/WorkspaceAdmin/WorkspaceAdminSettingsPage.tsx',
    'frontend/src/pages/Staff/StaffTicketsPage.tsx',
    'frontend/src/pages/Staff/StaffReportsPage.tsx',
    'frontend/src/pages/SuperAdmin/SuperAdminUsersPage.tsx',
    'frontend/src/pages/SuperAdmin/SuperAdminWorkspacesPage.tsx',
    'frontend/src/pages/SuperAdmin/SuperAdminStaffPage.tsx',
    'frontend/src/pages/SuperAdmin/SuperAdminPlansPage.tsx',
    'frontend/src/pages/SuperAdmin/SuperAdminCostsPage.tsx',
    'frontend/src/pages/SuperAdmin/SuperAdminHealthPage.tsx',
    'frontend/src/pages/SuperAdmin/SuperAdminEmergencyPage.tsx'
]

content = """import React from "react";

export default function Placeholder() {
  return (
    <div className="p-8 text-white">
      <h1 className="text-2xl font-bold">Coming Soon</h1>
      <p className="text-slate-400 mt-2">This administrative feature is currently under development.</p>
    </div>
  );
}
"""

for p in paths:
    full_path = os.path.join(os.getcwd(), p)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w') as f:
        f.write(content)
    print(f"Created {p}")
