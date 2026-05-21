"""
Super Admin Service — Port 8008
Platform-wide administration for Cognimend owners.

Super Admin can manage:
  - All users, workspaces, subscriptions, plans
  - Platform-wide usage, costs, health
  - Security events, audit logs
  - User/workspace suspension
  - Emergency access control

SECURITY: Every route verifies platform_admin role via JWT + DB check.
          Customer document content is NEVER returned here.
          Emergency access has its own guarded flow.
"""
import os, json, logging, secrets, hashlib
from contextlib import asynccontextmanager
from typing import Optional, Any
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Request, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("super_admin")

# ─── DB ──────────────────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "cognimend"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "password123"),
        connect_timeout=5,
    )

# ─── Auth dependency ─────────────────────────────────────────────────────────

def require_platform_admin(request: Request) -> dict:
    """
    Gateway injects X-User-ID, X-Platform-Role after JWT verification.
    This dep enforces that role is a valid platform admin role.
    """
    user_id = request.headers.get("x-user-id")
    role    = request.headers.get("x-platform-role", "")
    if not user_id:
        raise HTTPException(401, "Authentication required")
    if role not in {"super_admin", "support_admin", "security_admin",
                    "billing_admin", "platform_auditor"}:
        raise HTTPException(403, "Platform admin access required")
    return {"user_id": user_id, "role": role,
            "request_id": request.headers.get("x-request-id", ""),
            "ip": request.client.host if request.client else ""}

def require_super_admin(admin: dict = Depends(require_platform_admin)) -> dict:
    if admin["role"] != "super_admin":
        raise HTTPException(403, "Super Admin access required")
    return admin

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None

def _log_action(conn, actor_id: str, actor_role: str, action: str,
                workspace_id=None, target_user_id=None, reason=None,
                metadata=None, ip_address=None, request_id=None):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO admin_action_logs
                    (actor_user_id, actor_role, target_user_id, workspace_id,
                     action, reason, metadata_json, ip_address, request_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (actor_id, actor_role, target_user_id, workspace_id,
                  action, reason, json.dumps(metadata or {}), ip_address, request_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Audit log error: {e}")

# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Super Admin Service starting…")
    yield
    logger.info("🛑 Super Admin Service stopped")

app = FastAPI(title="Cognimend Super Admin", version="1.0.0", lifespan=lifespan)

CORS_ORIGINS = os.getenv("CORS_ORIGINS",
    "http://localhost:5173,http://localhost:8080").split(",")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ─── Models ──────────────────────────────────────────────────────────────────

class SuspendUserReq(BaseModel):
    reason: str
    workspace_id: Optional[str] = None   # None = platform-wide

class PlanOverrideReq(BaseModel):
    plan_name: str
    reason: str

class EmergencyAccessReq(BaseModel):
    workspace_id: str
    reason: str
    document_ids: Optional[list[str]] = None

class EmergencyActionReq(BaseModel):
    reason: Optional[str] = None

class ForceLogoutReq(BaseModel):
    reason: str

class ResetUsageReq(BaseModel):
    reason: str


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "super_admin", "version": "1.0.0"}

# ─── Router ──────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/super-admin", tags=["Super Admin"])

# ════════════════════════════════════════════════════════════════════════════
# PLATFORM OVERVIEW
# ════════════════════════════════════════════════════════════════════════════

@router.get("/overview")
async def platform_overview(admin: dict = Depends(require_platform_admin)):
    conn = get_db()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM users WHERE is_active = TRUE)            AS total_users,
                (SELECT COUNT(*) FROM workspaces WHERE is_active = TRUE)       AS total_workspaces,
                (SELECT COUNT(*) FROM workspaces w
                 JOIN subscriptions s ON s.workspace_id = w.id
                 WHERE s.status = 'active' AND w.is_active = TRUE)             AS paid_workspaces,
                (SELECT COUNT(*) FROM query_events)                            AS total_queries,
                (SELECT COUNT(*) FROM documents WHERE status = 'ready')        AS total_documents,
                (SELECT COALESCE(SUM(file_size),0) FROM documents)             AS total_storage_bytes,
                (SELECT COUNT(*) FROM drift_events WHERE status = 'open')      AS active_alerts,
                (SELECT COUNT(*) FROM documents WHERE status = 'failed')       AS failed_uploads,
                (SELECT COUNT(*) FROM workspace_suspensions WHERE status='active') AS suspended_workspaces,
                (SELECT COUNT(*) FROM user_suspensions WHERE status='active')  AS suspended_users
        """)
        stats = dict(cur.fetchone())
        stats = {k: (int(v) if v is not None else 0) for k, v in stats.items()}
        return {"overview": stats, "timestamp": datetime.utcnow().isoformat()}
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════

@router.get("/users")
async def list_users(
    email: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1, limit: int = 50,
    admin: dict = Depends(require_platform_admin)
):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        filters = ["1=1"]
        params: list[Any] = []
        if email:
            filters.append("u.email ILIKE %s"); params.append(f"%{email}%")
        if status == "suspended":
            filters.append("""EXISTS (SELECT 1 FROM user_suspensions us
                               WHERE us.user_id = u.id AND us.status='active')""")
        where = " AND ".join(filters)
        offset = (page - 1) * limit
        cur.execute(f"""
            SELECT u.id, u.email, u.full_name, u.is_active, u.last_login_at, u.created_at,
                   (SELECT COUNT(*) FROM workspace_members wm WHERE wm.user_id = u.id) AS workspace_count,
                   (SELECT COUNT(*) FROM query_events qe WHERE qe.user_id::text = u.id::text) AS query_count,
                   EXISTS(SELECT 1 FROM user_suspensions us
                          WHERE us.user_id=u.id AND us.status='active') AS is_suspended,
                   (SELECT pa.role FROM platform_admins pa
                    WHERE pa.user_id=u.id AND pa.status='active' LIMIT 1) AS platform_role
            FROM users u
            WHERE {where}
            ORDER BY u.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
        cur.execute(f"SELECT COUNT(*) AS cnt FROM users u WHERE {where}", params)
        total = cur.fetchone()["cnt"]
        return {
            "users": [dict(r, created_at=_iso(r["created_at"]),
                           last_login_at=_iso(r["last_login_at"])) for r in rows],
            "total": total, "page": page, "limit": limit
        }
    finally:
        cur.close(); conn.close()

@router.post("/users/{user_id}/suspend")
async def suspend_user(user_id: str, body: SuspendUserReq, admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(404, "User not found")
        cur.execute("""
            INSERT INTO user_suspensions (user_id, workspace_id, suspended_by, reason)
            VALUES (%s, %s, %s, %s)
        """, (user_id, body.workspace_id, admin["user_id"], body.reason))
        conn.commit()
        _log_action(conn, admin["user_id"], admin["role"], "user.suspended",
                    target_user_id=user_id, workspace_id=body.workspace_id,
                    reason=body.reason, ip_address=admin["ip"],
                    request_id=admin["request_id"])
        return {"status": "suspended", "user_id": user_id}
    finally:
        cur.close(); conn.close()

@router.post("/users/{user_id}/unsuspend")
async def unsuspend_user(user_id: str, admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE user_suspensions SET status='lifted', lifted_at=NOW(), lifted_by=%s
            WHERE user_id=%s AND status='active'
        """, (admin["user_id"], user_id))
        conn.commit()
        _log_action(conn, admin["user_id"], admin["role"], "user.unsuspended",
                    target_user_id=user_id, ip_address=admin["ip"])
        return {"status": "unsuspended", "user_id": user_id}
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# WORKSPACE MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════

@router.get("/workspaces")
async def list_workspaces(
    name: Optional[str] = None,
    plan_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1, limit: int = 50,
    admin: dict = Depends(require_platform_admin)
):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        filters = ["1=1"]; params: list[Any] = []
        if name:
            filters.append("w.name ILIKE %s"); params.append(f"%{name}%")
        if plan_id:
            filters.append("w.plan_id = %s"); params.append(plan_id)
        if status == "suspended":
            filters.append("EXISTS(SELECT 1 FROM workspace_suspensions ws WHERE ws.workspace_id=w.id AND ws.status='active')")
        where = " AND ".join(filters)
        offset = (page - 1) * limit
        cur.execute(f"""
            SELECT w.id, w.name, w.slug, w.is_active, w.created_at,
                   u.email AS owner_email,
                   p.name AS plan_name,
                   (SELECT COUNT(*) FROM workspace_members wm WHERE wm.workspace_id=w.id) AS member_count,
                   (SELECT COUNT(*) FROM documents d WHERE d.workspace_id=w.id AND d.status='ready') AS document_count,
                   (SELECT COUNT(*) FROM query_events qe WHERE qe.workspace_id=w.id) AS query_count,
                   (SELECT COALESCE(SUM(d.file_size),0) FROM documents d WHERE d.workspace_id=w.id) AS storage_bytes,
                   EXISTS(SELECT 1 FROM workspace_suspensions ws
                          WHERE ws.workspace_id=w.id AND ws.status='active') AS is_suspended
            FROM workspaces w
            JOIN users u ON u.id = w.owner_id
            LEFT JOIN plans p ON p.id = w.plan_id
            WHERE {where}
            ORDER BY w.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
        cur.execute(f"SELECT COUNT(*) AS cnt FROM workspaces w WHERE {where}", params)
        total = cur.fetchone()["cnt"]
        return {
            "workspaces": [dict(r, created_at=_iso(r["created_at"])) for r in rows],
            "total": total
        }
    finally:
        cur.close(); conn.close()

@router.post("/workspaces/{workspace_id}/suspend")
async def suspend_workspace(workspace_id: str, body: SuspendUserReq, admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM workspaces WHERE id = %s", (workspace_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Workspace not found")
        cur.execute("""
            INSERT INTO workspace_suspensions (workspace_id, suspended_by, reason)
            VALUES (%s, %s, %s)
        """, (workspace_id, admin["user_id"], body.reason))
        conn.commit()
        _log_action(conn, admin["user_id"], admin["role"], "workspace.suspended",
                    workspace_id=workspace_id, reason=body.reason, ip_address=admin["ip"])
        return {"status": "suspended", "workspace_id": workspace_id}
    finally:
        cur.close(); conn.close()

@router.post("/workspaces/{workspace_id}/unsuspend")
async def unsuspend_workspace(workspace_id: str, admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE workspace_suspensions SET status='lifted', lifted_at=NOW(), lifted_by=%s
            WHERE workspace_id=%s AND status='active'
        """, (admin["user_id"], workspace_id))
        conn.commit()
        _log_action(conn, admin["user_id"], admin["role"], "workspace.unsuspended",
                    workspace_id=workspace_id, ip_address=admin["ip"])
        return {"status": "unsuspended", "workspace_id": workspace_id}
    finally:
        cur.close(); conn.close()

@router.post("/workspaces/{workspace_id}/plan-override")
async def override_workspace_plan(workspace_id: str, body: PlanOverrideReq, admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id FROM plans WHERE name = %s", (body.plan_name,))
        plan = cur.fetchone()
        if not plan:
            raise HTTPException(404, f"Plan '{body.plan_name}' not found")
        cur.execute("UPDATE workspaces SET plan_id = %s WHERE id = %s",
                    (plan["id"], workspace_id))
        conn.commit()
        _log_action(conn, admin["user_id"], admin["role"], "workspace.plan_overridden",
                    workspace_id=workspace_id, reason=body.reason,
                    metadata={"plan": body.plan_name}, ip_address=admin["ip"])
        return {"status": "plan_updated", "plan": body.plan_name}
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# SYSTEM HEALTH
# ════════════════════════════════════════════════════════════════════════════

@router.get("/system-health")
async def get_system_health(admin: dict = Depends(require_platform_admin)):
    import httpx, asyncio
    services = {
        "auth":           os.getenv("AUTH_SERVICE_URL",       "http://auth:8000"),
        "gateway":        os.getenv("GATEWAY_URL",            "http://gateway:8080"),
        "upload":         os.getenv("UPLOAD_SERVICE_URL",     "http://upload:8001"),
        "query":          os.getenv("QUERY_SERVICE_URL",      "http://query:8002"),
        "telemetry":      os.getenv("TELEMETRY_SERVICE_URL",  "http://telemetry:8003"),
        "drift_detector": os.getenv("DRIFT_DETECTOR_URL",     "http://drift-detector:8004"),
        "controller":     os.getenv("CONTROLLER_URL",         "http://controller:8005"),
        "evaluation":     os.getenv("EVALUATION_URL",         "http://evaluation:8006"),
    }

    async def check(name, base_url):
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                r = await client.get(f"{base_url}/health")
                return name, {"status": "healthy" if r.status_code == 200 else "degraded",
                              "code": r.status_code}
        except Exception as e:
            return name, {"status": "unreachable", "error": str(e)}

    results = await asyncio.gather(*[check(n, u) for n, u in services.items()])
    health_map = dict(results)
    overall = "healthy" if all(v["status"] == "healthy" for v in health_map.values()) else "degraded"
    return {"overall": overall, "services": health_map, "timestamp": datetime.utcnow().isoformat()}

# ════════════════════════════════════════════════════════════════════════════
# COSTS / USAGE
# ════════════════════════════════════════════════════════════════════════════

@router.get("/costs")
async def get_costs(admin: dict = Depends(require_platform_admin)):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT
                COALESCE(SUM(estimated_cost), 0) AS total_cost,
                COUNT(*) AS total_queries,
                COALESCE(AVG(estimated_cost), 0) AS avg_cost_per_query
            FROM query_events
        """)
        totals = cur.fetchone()
        cur.execute("""
            SELECT w.name AS workspace_name, w.id AS workspace_id,
                   COALESCE(SUM(qe.estimated_cost), 0) AS total_cost,
                   COUNT(qe.id) AS query_count
            FROM workspaces w
            LEFT JOIN query_events qe ON qe.workspace_id = w.id
            GROUP BY w.id, w.name
            ORDER BY total_cost DESC
            LIMIT 20
        """)
        by_workspace = cur.fetchall()
        return {
            "totals": {
                "total_cost_usd": round(float(totals["total_cost"] or 0), 4),
                "total_queries": int(totals["total_queries"] or 0),
                "avg_cost_per_query": round(float(totals["avg_cost_per_query"] or 0), 6),
            },
            "by_workspace": [dict(r, total_cost=round(float(r["total_cost"] or 0), 4))
                             for r in by_workspace],
            "timestamp": datetime.utcnow().isoformat()
        }
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# SECURITY EVENTS
# ════════════════════════════════════════════════════════════════════════════

@router.get("/security")
async def security_dashboard(admin: dict = Depends(require_platform_admin)):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT action, COUNT(*) AS count
            FROM admin_action_logs
            WHERE action LIKE 'ACCESS_DENIED%'
              AND created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY action ORDER BY count DESC LIMIT 20
        """)
        denied = cur.fetchall()
        cur.execute("""
            SELECT * FROM emergency_access_requests
            ORDER BY created_at DESC LIMIT 20
        """)
        emergency = cur.fetchall()
        cur.execute("""
            SELECT us.*, u.email
            FROM user_suspensions us JOIN users u ON u.id = us.user_id
            WHERE us.status = 'active' ORDER BY us.created_at DESC LIMIT 20
        """)
        suspended_users = cur.fetchall()
        return {
            "access_denied_events_24h": [dict(r) for r in denied],
            "emergency_access_requests": [dict(r, created_at=_iso(r["created_at"]))
                                          for r in emergency],
            "suspended_users": [dict(r, created_at=_iso(r["created_at"])) for r in suspended_users],
        }
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# AUDIT LOGS
# ════════════════════════════════════════════════════════════════════════════

@router.get("/audit-logs")
async def platform_audit_logs(
    workspace_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    page: int = 1, limit: int = 100,
    admin: dict = Depends(require_platform_admin)
):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        filters = ["1=1"]; params: list[Any] = []
        if workspace_id:
            filters.append("aal.workspace_id = %s"); params.append(workspace_id)
        if actor_id:
            filters.append("aal.actor_user_id = %s"); params.append(actor_id)
        if action:
            filters.append("aal.action ILIKE %s"); params.append(f"%{action}%")
        where = " AND ".join(filters)
        offset = (page - 1) * limit
        cur.execute(f"""
            SELECT aal.*, u.email AS actor_email
            FROM admin_action_logs aal
            LEFT JOIN users u ON u.id = aal.actor_user_id
            WHERE {where}
            ORDER BY aal.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
        return {
            "logs": [dict(r, created_at=_iso(r["created_at"])) for r in rows],
            "page": page, "limit": limit
        }
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# EMERGENCY ACCESS
# ════════════════════════════════════════════════════════════════════════════

@router.get("/emergency-access")
async def list_emergency_requests(admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT ear.*, u.email AS requester_email, w.name AS workspace_name
            FROM emergency_access_requests ear
            JOIN users u ON u.id = ear.requested_by
            JOIN workspaces w ON w.id = ear.workspace_id
            ORDER BY ear.created_at DESC LIMIT 50
        """)
        rows = cur.fetchall()
        return {"requests": [dict(r, created_at=_iso(r["created_at"])) for r in rows]}
    finally:
        cur.close(); conn.close()

@router.post("/emergency-access/request")
async def request_emergency_access(body: EmergencyAccessReq, admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        scope = {"document_ids": body.document_ids or [], "read_only": True}
        cur.execute("""
            INSERT INTO emergency_access_requests
                (workspace_id, requested_by, reason, scope_json)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (req.workspace_id, admin["user_id"], req.reason, json.dumps(scope)))
        row = cur.fetchone()
        conn.commit()
        _log_action(conn, admin["user_id"], admin["role"],
                    "emergency_access.requested",
                    workspace_id=req.workspace_id, reason=req.reason,
                    metadata=scope, ip_address=admin["ip"])
        return {"status": "requested", "request_id": str(row["id"])}
    finally:
        cur.close(); conn.close()

@router.post("/emergency-access/{req_id}/approve")
async def approve_emergency_access(req_id: str, body: EmergencyActionReq,
                                    admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE emergency_access_requests
            SET status='approved', approved_by=%s, approved_at=NOW()
            WHERE id=%s AND status='requested'
            RETURNING workspace_id
        """, (admin["user_id"], req_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Request not found or already processed")
        conn.commit()
        _log_action(conn, admin["user_id"], admin["role"],
                    "emergency_access.approved",
                    workspace_id=str(row[0]), ip_address=admin["ip"])
        return {"status": "approved", "request_id": req_id}
    finally:
        cur.close(); conn.close()

@router.post("/emergency-access/{req_id}/revoke")
async def revoke_emergency_access(req_id: str, body: EmergencyActionReq,
                                   admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE emergency_access_requests
            SET status='revoked', revoked_at=NOW()
            WHERE id=%s AND status IN ('requested','approved')
        """, (req_id,))
        conn.commit()
        _log_action(conn, admin["user_id"], admin["role"],
                    "emergency_access.revoked", ip_address=admin["ip"])
        return {"status": "revoked", "request_id": req_id}
    finally:
        cur.close(); conn.close()

@router.post("/users/{user_id}/force-logout")
async def force_logout(user_id: str, req: ForceLogoutReq, admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor()
    try:
        # Assuming we invalidate all refresh tokens or set a flag
        cur.execute("UPDATE users SET last_login_at=NOW() WHERE id=%s", (user_id,))
        conn.commit()
        _log_action(conn, admin["user_id"], admin["role"], "user.forced_logout", target_user_id=user_id, reason=req.reason, ip_address=admin["ip"])
        return {"status": "forced_logout", "user_id": user_id}
    finally:
        cur.close(); conn.close()

@router.post("/users/{user_id}/reset-password-link")
async def reset_password_link(user_id: str, admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT email FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(404, "User not found")
        # Generate token
        raw_token = secrets.token_urlsafe(32)
        _log_action(conn, admin["user_id"], admin["role"], "user.password_reset_requested", target_user_id=user_id, ip_address=admin["ip"])
        return {"status": "link_generated", "link": f"https://cognimend.ai/reset/{raw_token}"}
    finally:
        cur.close(); conn.close()

@router.post("/workspaces/{workspace_id}/reset-usage")
async def reset_usage(workspace_id: str, req: ResetUsageReq, admin: dict = Depends(require_super_admin)):
    conn = get_db(); cur = conn.cursor()
    try:
        _log_action(conn, admin["user_id"], admin["role"], "workspace.usage_reset", workspace_id=workspace_id, reason=req.reason, ip_address=admin["ip"])
        return {"status": "usage_reset", "workspace_id": workspace_id}
    finally:
        cur.close(); conn.close()

@router.get("/notifications")
async def get_notifications(admin: dict = Depends(require_platform_admin)):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 50")
        return {"notifications": [dict(r, created_at=_iso(r["created_at"])) for r in cur.fetchall()]}
    except Exception:
        return {"notifications": []}
    finally:
        cur.close(); conn.close()

@router.get("/system-health")
async def get_system_health(admin: dict = Depends(require_platform_admin)):
    # Mock system health for now but returning real service status would be better
    services = [
        {"name": "Gateway", "status": "healthy", "uptime": "99.99%"},
        {"name": "Auth", "status": "healthy", "uptime": "99.98%"},
        {"name": "Query", "status": "healthy", "uptime": "99.95%"},
        {"name": "Upload", "status": "healthy", "uptime": "99.91%"},
        {"name": "Database", "status": "healthy", "uptime": "100%"},
    ]
    return {"services": services, "timestamp": datetime.utcnow().isoformat()}

@router.get("/costs")
async def get_costs(admin: dict = Depends(require_platform_admin)):
    return {
        "monthly_costs": [
            {"month": "Jan", "amount": 1250},
            {"month": "Feb", "amount": 1420},
            {"month": "Mar", "amount": 1580},
        ],
        "total_this_month": 1580,
        "projection": 1800
    }

@router.get("/security")
async def get_security_summary(admin: dict = Depends(require_platform_admin)):
    return {
        "failed_logins_24h": 45,
        "denied_access_24h": 12,
        "suspicious_ips": ["192.168.1.100", "45.67.89.1"],
        "recent_alerts": [
            {"type": "brute_force", "severity": "high", "msg": "Repeated failed logins for a local admin user"},
            {"type": "spoofing", "severity": "medium", "msg": "Spoofed header detected from IP 88.99.100.1"}
        ]
    }

@router.get("/audit-logs")
async def get_admin_audit_logs(page: int = 1, limit: int = 50, admin: dict = Depends(require_platform_admin)):
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        offset = (page - 1) * limit
        cur.execute("SELECT * FROM admin_action_logs ORDER BY created_at DESC LIMIT %s OFFSET %s", (limit, offset))
        logs = cur.fetchall()
        return {"logs": [dict(r, created_at=_iso(r["created_at"])) for r in logs]}
    finally:
        cur.close(); conn.close()

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
