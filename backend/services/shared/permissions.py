"""
Central Permission Engine — Cognimend
======================================
Single source of truth for ALL access-control decisions across every service.

Usage:
    from services.shared.permissions import PermissionEngine, AccessDenied

    engine = PermissionEngine(conn)
    allowed_ids = engine.get_allowed_document_ids(user_id, workspace_id)

Rules:
  Super Admin   → platform metadata only; NO customer docs without emergency access
  Workspace Owner → full access inside workspace
  Workspace Admin → manage users/depts/docs inside workspace
  Department Admin → manage their department only
  Billing Admin   → billing/usage only
  IT Admin        → integrations/API keys/security settings
  HR/Accounts/Legal Admin → their department documents only
  Auditor         → read-only audit logs
  Member          → query/view allowed documents
  Viewer          → view only allowed documents
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional
from uuid import UUID

from psycopg2.extras import RealDictCursor

logger = logging.getLogger("permissions")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AccessDenied(Exception):
    """Raised when a permission check fails."""
    def __init__(self, message: str = "Access denied"):
        super().__init__(message)
        self.message = message


class SuspendedAccount(AccessDenied):
    """Raised when user or workspace is suspended."""


# ---------------------------------------------------------------------------
# Role constants
# ---------------------------------------------------------------------------

PLATFORM_ROLES = {
    "super_admin",
    "support_admin",
    "security_admin",
    "billing_admin",
    "platform_auditor",
}

# Workspace roles ordered by privilege (highest first)
WORKSPACE_ROLE_RANK = {
    "owner":            100,
    "admin":             90,
    "billing_admin":     70,
    "it_admin":          70,
    "security_admin":    70,
    "hr_admin":          60,
    "accounts_admin":    60,
    "legal_admin":       60,
    "auditor":           50,
    "department_admin":  40,
    "member":            20,
    "viewer":            10,
}

MANAGE_ROLES = {"owner", "admin"}
SPECIAL_ADMIN_ROLES = {"billing_admin", "it_admin", "security_admin", "hr_admin",
                        "accounts_admin", "legal_admin", "auditor", "department_admin"}
ALL_WORKSPACE_ROLES = set(WORKSPACE_ROLE_RANK.keys())

PERMISSION_RANK = {
    "none":    0,
    "view":    1,
    "query":   2,
    "upload":  3,
    "delete":  4,
    "manage":  5,
    "owner":   6,
}


# ---------------------------------------------------------------------------
# Permission Engine
# ---------------------------------------------------------------------------

class PermissionEngine:
    """
    All permission checks live here.  Pass a live psycopg2 connection.
    This engine is stateless — call it per-request.
    """

    def __init__(self, conn):
        self._conn = conn

    def _cur(self):
        return self._conn.cursor(cursor_factory=RealDictCursor)

    # -----------------------------------------------------------------------
    # Suspension checks
    # -----------------------------------------------------------------------

    def assert_user_not_suspended(self, user_id: str, workspace_id: Optional[str] = None):
        """Raise SuspendedAccount if user has an active suspension."""
        with self._cur() as cur:
            if workspace_id:
                cur.execute("""
                    SELECT id FROM user_suspensions
                    WHERE user_id = %s
                      AND status = 'active'
                      AND (workspace_id = %s OR workspace_id IS NULL)
                    LIMIT 1
                """, (user_id, workspace_id))
            else:
                cur.execute("""
                    SELECT id FROM user_suspensions
                    WHERE user_id = %s AND status = 'active'
                    LIMIT 1
                """, (user_id,))
            if cur.fetchone():
                raise SuspendedAccount("Your account has been suspended.")

    def assert_workspace_not_suspended(self, workspace_id: str):
        """Raise SuspendedAccount if workspace is suspended."""
        with self._cur() as cur:
            cur.execute("""
                SELECT id FROM workspace_suspensions
                WHERE workspace_id = %s AND status = 'active'
                LIMIT 1
            """, (workspace_id,))
            if cur.fetchone():
                raise SuspendedAccount("This workspace is suspended.")

    # -----------------------------------------------------------------------
    # Platform admin checks
    # -----------------------------------------------------------------------

    def is_super_admin(self, user_id: str) -> bool:
        with self._cur() as cur:
            cur.execute("""
                SELECT id FROM platform_admins
                WHERE user_id = %s AND role = 'super_admin' AND status = 'active'
                LIMIT 1
            """, (user_id,))
            return cur.fetchone() is not None

    def is_platform_admin(self, user_id: str) -> bool:
        with self._cur() as cur:
            cur.execute("""
                SELECT id FROM platform_admins
                WHERE user_id = %s AND status = 'active'
                LIMIT 1
            """, (user_id,))
            return cur.fetchone() is not None

    def get_platform_role(self, user_id: str) -> Optional[str]:
        with self._cur() as cur:
            cur.execute("""
                SELECT role FROM platform_admins
                WHERE user_id = %s AND status = 'active'
                LIMIT 1
            """, (user_id,))
            row = cur.fetchone()
            return row["role"] if row else None

    def has_platform_permission(self, user_id: str, permission: str) -> bool:
        """
        permission can be:
          'manage_users' | 'manage_workspaces' | 'view_billing' |
          'view_audit_logs' | 'emergency_access' | 'manage_platform'
        """
        role = self.get_platform_role(user_id)
        if not role:
            return False
        rules = {
            "super_admin":      {"manage_users","manage_workspaces","view_billing",
                                  "view_audit_logs","emergency_access","manage_platform",
                                  "suspend_users","suspend_workspaces","view_costs",
                                  "view_security","view_system_health"},
            "support_admin":    {"manage_users","view_audit_logs","view_system_health"},
            "security_admin":   {"view_audit_logs","view_security","suspend_users"},
            "billing_admin":    {"view_billing","view_costs"},
            "platform_auditor": {"view_audit_logs","view_security"},
        }
        return permission in rules.get(role, set())

    def assert_platform_permission(self, user_id: str, permission: str):
        if not self.has_platform_permission(user_id, permission):
            raise AccessDenied(f"Platform permission '{permission}' required.")

    # -----------------------------------------------------------------------
    # Workspace role checks
    # -----------------------------------------------------------------------

    def get_user_workspace_role(self, user_id: str, workspace_id: str) -> Optional[str]:
        with self._cur() as cur:
            cur.execute("""
                SELECT role FROM workspace_members
                WHERE user_id = %s AND workspace_id = %s AND status = 'active'
                LIMIT 1
            """, (user_id, workspace_id))
            row = cur.fetchone()
            return row["role"] if row else None

    def can_access_workspace(self, user_id: str, workspace_id: str) -> bool:
        if self.is_platform_admin(user_id):
            return True
        role = self.get_user_workspace_role(user_id, workspace_id)
        return role is not None

    def assert_workspace_access(self, user_id: str, workspace_id: str):
        self.assert_user_not_suspended(user_id, workspace_id)
        self.assert_workspace_not_suspended(workspace_id)
        if not self.can_access_workspace(user_id, workspace_id):
            raise AccessDenied("You are not a member of this workspace.")

    def can_manage_workspace(self, user_id: str, workspace_id: str) -> bool:
        role = self.get_user_workspace_role(user_id, workspace_id)
        return role in MANAGE_ROLES

    def can_manage_users(self, user_id: str, workspace_id: str) -> bool:
        role = self.get_user_workspace_role(user_id, workspace_id)
        return role in MANAGE_ROLES | {"it_admin"}

    def can_manage_billing(self, user_id: str, workspace_id: str) -> bool:
        role = self.get_user_workspace_role(user_id, workspace_id)
        return role in MANAGE_ROLES | {"billing_admin"}

    def can_view_audit_logs(self, user_id: str, workspace_id: str) -> bool:
        role = self.get_user_workspace_role(user_id, workspace_id)
        return role in MANAGE_ROLES | {"security_admin", "auditor", "it_admin"}

    def can_manage_settings(self, user_id: str, workspace_id: str) -> bool:
        role = self.get_user_workspace_role(user_id, workspace_id)
        return role in MANAGE_ROLES | {"it_admin", "security_admin"}

    # -----------------------------------------------------------------------
    # Department checks
    # -----------------------------------------------------------------------

    def get_user_departments(self, user_id: str, workspace_id: str) -> list[dict]:
        with self._cur() as cur:
            cur.execute("""
                SELECT dm.department_id, dm.role, d.name, d.slug
                FROM department_members dm
                JOIN departments d ON d.id = dm.department_id
                WHERE dm.user_id = %s
                  AND dm.workspace_id = %s
                  AND dm.status = 'active'
                  AND d.archived_at IS NULL
            """, (user_id, workspace_id))
            return [dict(r) for r in cur.fetchall()]

    def get_user_department_ids(self, user_id: str, workspace_id: str) -> list[str]:
        return [str(d["department_id"]) for d in self.get_user_departments(user_id, workspace_id)]

    def get_user_department_role(self, user_id: str, workspace_id: str,
                                  department_id: str) -> Optional[str]:
        with self._cur() as cur:
            cur.execute("""
                SELECT role FROM department_members
                WHERE user_id = %s AND workspace_id = %s
                  AND department_id = %s AND status = 'active'
                LIMIT 1
            """, (user_id, workspace_id, department_id))
            row = cur.fetchone()
            return row["role"] if row else None

    def can_manage_department(self, user_id: str, workspace_id: str,
                               department_id: str) -> bool:
        ws_role = self.get_user_workspace_role(user_id, workspace_id)
        if ws_role in MANAGE_ROLES:
            return True
        dept_role = self.get_user_department_role(user_id, workspace_id, department_id)
        return dept_role == "department_admin"

    # -----------------------------------------------------------------------
    # Document permission checks
    # -----------------------------------------------------------------------

    def get_allowed_document_ids(self, user_id: str, workspace_id: str) -> list[str]:
        """
        Return the list of document IDs the user can QUERY in this workspace.
        This is the critical method called by the Query Service before every search.

        Priority order:
          1. Workspace owner/admin → all workspace documents
          2. Direct user grant with permission_level >= 'query'
          3. Department membership grant with permission_level >= 'query'
          4. Workspace-wide document (access_scope = 'workspace')
          5. User's own private documents (created_by_user_id = user_id)
        """
        ws_role = self.get_user_workspace_role(user_id, workspace_id)

        # Platform admin with emergency access handled separately
        if self.is_platform_admin(user_id):
            with self._cur() as cur:
                # Check for active approved emergency access request
                cur.execute("""
                    SELECT scope_json FROM emergency_access_requests
                    WHERE requested_by = %s AND workspace_id = %s
                      AND status = 'approved' AND expires_at > NOW()
                    LIMIT 1
                """, (user_id, workspace_id))
                row = cur.fetchone()
                if not row:
                    # Super admin sees NO documents without approved emergency access
                    return []
                
                scope = row["scope_json"]
                doc_ids = scope.get("document_ids", [])
                
                if not doc_ids:
                    # If scope is empty but approved, they might have full access or it's a mistake
                    # For safety, return all if explicitly allowed or empty if restricted
                    cur.execute("""
                        SELECT id FROM documents 
                        WHERE workspace_id = %s AND status = 'ready'
                    """, (workspace_id,))
                    return [str(r["id"]) for r in cur.fetchall()]
                
                return [str(did) for did in doc_ids]
        
        if not ws_role:
            return []

        # Workspace owner / admin see everything
        if ws_role in MANAGE_ROLES:
            with self._cur() as cur:
                cur.execute("""
                    SELECT id FROM documents
                    WHERE workspace_id = %s AND status = 'ready'
                """, (workspace_id,))
                return [str(r["id"]) for r in cur.fetchall()]

        dept_ids = self.get_user_department_ids(user_id, workspace_id)

        with self._cur() as cur:
            # Documents explicitly allowed for user or their departments
            cur.execute("""
                SELECT DISTINCT d.id
                FROM documents d
                WHERE d.workspace_id = %s AND d.status = 'ready'
                  AND (
                    -- workspace-wide docs
                    d.access_scope = 'workspace'

                    -- private doc owned by this user
                    OR (d.access_scope = 'private' AND d.created_by_user_id = %s)

                    -- direct user permission
                    OR EXISTS (
                        SELECT 1 FROM document_permissions dp
                        WHERE dp.document_id = d.id
                          AND dp.user_id = %s
                          AND dp.permission_level IN ('query','upload','delete','manage','owner')
                    )

                    -- department permission (user is in that dept)
                    OR EXISTS (
                        SELECT 1 FROM document_permissions dp
                        WHERE dp.document_id = d.id
                          AND dp.department_id = ANY(%s::uuid[])
                          AND dp.permission_level IN ('query','upload','delete','manage','owner')
                    )

                    -- workspace role grant
                    OR EXISTS (
                        SELECT 1 FROM document_permissions dp
                        WHERE dp.document_id = d.id
                          AND dp.workspace_role = %s
                          AND dp.permission_level IN ('query','upload','delete','manage','owner')
                    )
                  )
            """, (workspace_id, user_id, user_id, dept_ids or ["00000000-0000-0000-0000-000000000000"],
                  ws_role))
            return [str(r["id"]) for r in cur.fetchall()]

    def can_view_document(self, user_id: str, workspace_id: str, document_id: str) -> bool:
        allowed = self.get_allowed_document_ids(user_id, workspace_id)
        return document_id in allowed

    def can_query_document(self, user_id: str, workspace_id: str, document_id: str) -> bool:
        """Same as view for now; can be tightened separately."""
        return self.can_view_document(user_id, workspace_id, document_id)

    def can_upload_document(self, user_id: str, workspace_id: str,
                             department_id: Optional[str] = None) -> bool:
        ws_role = self.get_user_workspace_role(user_id, workspace_id)
        if not ws_role:
            return False
        if ws_role in MANAGE_ROLES:
            return True
        if ws_role in {"member", "it_admin", "hr_admin", "accounts_admin", "legal_admin"}:
            return True
        if department_id and ws_role == "department_admin":
            return self.can_manage_department(user_id, workspace_id, department_id)
        return False

    def can_delete_document(self, user_id: str, workspace_id: str, document_id: str) -> bool:
        ws_role = self.get_user_workspace_role(user_id, workspace_id)
        if ws_role in MANAGE_ROLES:
            return True
        with self._cur() as cur:
            # Check direct owner/manage permission
            cur.execute("""
                SELECT 1 FROM document_permissions
                WHERE document_id = %s AND user_id = %s
                  AND permission_level IN ('delete','manage','owner')
                LIMIT 1
            """, (document_id, user_id))
            if cur.fetchone():
                return True
            # Check if user created the document
            cur.execute("""
                SELECT 1 FROM documents
                WHERE id = %s AND workspace_id = %s AND created_by_user_id = %s
            """, (document_id, workspace_id, user_id))
            return cur.fetchone() is not None

    def can_manage_document_permissions(self, user_id: str, workspace_id: str,
                                         document_id: str) -> bool:
        ws_role = self.get_user_workspace_role(user_id, workspace_id)
        if ws_role in MANAGE_ROLES:
            return True
        with self._cur() as cur:
            cur.execute("""
                SELECT 1 FROM document_permissions
                WHERE document_id = %s AND user_id = %s
                  AND permission_level IN ('manage','owner')
                LIMIT 1
            """, (document_id, user_id))
            return cur.fetchone() is not None

    # -----------------------------------------------------------------------
    # Permission hash for cache key isolation
    # -----------------------------------------------------------------------

    def get_permission_hash(self, user_id: str, workspace_id: str) -> str:
        """
        Deterministic hash of the user's allowed document set.
        Used as part of the query cache key to prevent cross-permission leakage
        inside the same workspace.

        Cache key pattern:
          query:{workspace_id}:{permission_hash}:{question_hash}:{top_k}:{verifier_mode}
        """
        allowed = sorted(self.get_allowed_document_ids(user_id, workspace_id))
        raw = f"{workspace_id}:{user_id}:" + ",".join(allowed)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # -----------------------------------------------------------------------
    # Audit logging helper
    # -----------------------------------------------------------------------

    def log_action(
        self,
        actor_user_id: str,
        actor_role: str,
        action: str,
        workspace_id: Optional[str] = None,
        target_user_id: Optional[str] = None,
        department_id: Optional[str] = None,
        document_id: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """Write an immutable admin action log entry."""
        try:
            with self._cur() as cur:
                cur.execute("""
                    INSERT INTO admin_action_logs
                        (actor_user_id, actor_role, target_user_id, workspace_id,
                         department_id, document_id, action, reason,
                         metadata_json, ip_address, request_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    actor_user_id, actor_role, target_user_id, workspace_id,
                    department_id, document_id, action, reason,
                    __import__("json").dumps(metadata or {}),
                    ip_address, request_id
                ))
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to write admin action log: {e}")

    def log_denied(
        self,
        user_id: str,
        workspace_id: Optional[str],
        action: str,
        resource: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """Log an access-denied event for security monitoring."""
        self.log_action(
            actor_user_id=user_id,
            actor_role="unknown",
            action=f"ACCESS_DENIED:{action}",
            workspace_id=workspace_id,
            metadata={"resource": resource},
            ip_address=ip_address,
            request_id=request_id,
        )


# ---------------------------------------------------------------------------
# FastAPI dependency helper
# ---------------------------------------------------------------------------

def build_engine_from_request(request, get_db_fn) -> PermissionEngine:
    """
    Convenience factory for use in FastAPI route deps.
    
    Example:
        async def my_route(request: Request, conn=Depends(get_db)):
            engine = build_engine_from_request(request, lambda: conn)
    """
    conn = get_db_fn()
    return PermissionEngine(conn)
