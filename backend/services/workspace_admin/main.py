"""
Workspace Admin Service — Port 8009
Handles: invitations, departments, document permissions, workspace admin overview.
"""
import os, json, secrets, hashlib, smtplib, logging
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime
from email.mime.text import MIMEText

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workspace_admin")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
INVITE_EXPIRE_DAYS = int(os.getenv("INVITE_EXPIRE_DAYS", "7"))

def get_db():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST","localhost"),
        port=int(os.getenv("POSTGRES_PORT","5432")),
        database=os.getenv("POSTGRES_DB","cognimend"),
        user=os.getenv("POSTGRES_USER","postgres"),
        password=os.getenv("POSTGRES_PASSWORD","password123"),
        connect_timeout=5,
    )

def _iso(dt): return dt.isoformat() if dt else None

# ── Auth deps ────────────────────────────────────────────────────────────────

def require_workspace_member(request: Request) -> dict:
    ws  = request.headers.get("x-workspace-id")
    uid = request.headers.get("x-user-id")
    role= request.headers.get("x-user-role","viewer")
    if not ws or not uid:
        raise HTTPException(401, "Authentication required")
    return {"workspace_id": ws, "user_id": uid, "role": role,
            "ip": request.client.host if request.client else "",
            "request_id": request.headers.get("x-request-id","")}

def require_admin(ctx: dict = Depends(require_workspace_member)) -> dict:
    if ctx["role"] not in ("owner","admin"):
        raise HTTPException(403, "Workspace admin required")
    return ctx

def require_dept_admin(ctx: dict = Depends(require_workspace_member)) -> dict:
    if ctx["role"] not in ("owner","admin","department_admin"):
        raise HTTPException(403, "Department admin required")
    return ctx

# ── Audit helper ─────────────────────────────────────────────────────────────

def _log(conn, actor_id, actor_role, action, workspace_id=None,
         target_user_id=None, department_id=None, document_id=None,
         reason=None, metadata=None, ip=None, request_id=None):
    try:
        with conn.cursor() as c:
            c.execute("""INSERT INTO admin_action_logs
                (actor_user_id,actor_role,target_user_id,workspace_id,
                 department_id,document_id,action,reason,metadata_json,ip_address,request_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
               (actor_id,actor_role,target_user_id,workspace_id,
                department_id,document_id,action,reason,
                json.dumps(metadata or {}),ip,request_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Audit log error: {e}")

# ── Email helper ──────────────────────────────────────────────────────────────

def _send_invite_email(to_email: str, invite_link: str, workspace_name: str):
    provider = os.getenv("EMAIL_PROVIDER","")
    if not provider:
        return False
    try:
        msg = MIMEText(
            f"You have been invited to join {workspace_name} on Cognimend.\n\n"
            f"Accept your invitation here:\n{invite_link}\n\n"
            f"This link expires in {INVITE_EXPIRE_DAYS} days.",
            "plain"
        )
        msg["Subject"] = f"Invitation to join {workspace_name} on Cognimend"
        msg["From"]    = os.getenv("EMAIL_FROM","noreply@cognimend.ai")
        msg["To"]      = to_email
        with smtplib.SMTP(os.getenv("SMTP_HOST","localhost"),
                          int(os.getenv("SMTP_PORT","587"))) as s:
            if os.getenv("SMTP_USER"):
                s.starttls()
                s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD",""))
            s.send_message(msg)
        return True
    except Exception as e:
        logger.warning(f"Email send failed: {e}")
        return False

# ── Models ────────────────────────────────────────────────────────────────────

class InviteRequest(BaseModel):
    email: str
    workspace_role: str = "member"
    department_id: Optional[str] = None
    department_role: str = "department_member"
    permissions: list[str] = []
    message: Optional[str] = None

class DepartmentCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    parent_department_id: Optional[str] = None

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class AddDeptMember(BaseModel):
    user_id: str
    role: str = "department_member"

class DocPermissionSet(BaseModel):
    document_id: str
    access_scope: str = "workspace"
    department_ids: list[str] = []
    user_ids: list[str] = []
    workspace_role: Optional[str] = None
    permission_level: str = "query"

class RoleUpdate(BaseModel):
    role: str

class AssignDepartmentReq(BaseModel):
    department_id: str
    role: str = "department_member"

class SuspendUserReq(BaseModel):
    reason: str

class ApiKeyCreate(BaseModel):
    name: str
    scopes: list[str] = []
    department_ids: list[str] = []
    document_ids: list[str] = []
    expires_in_days: Optional[int] = None


# ── App ───────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    logger.info("🚀 Workspace Admin Service starting…")
    yield
    logger.info("🛑 Workspace Admin Service stopped")

app = FastAPI(title="Workspace Admin Service", version="1.0.0", lifespan=lifespan)
CORS_ORIGINS = os.getenv("CORS_ORIGINS","http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    return {"status":"healthy","service":"workspace_admin"}

# ════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ════════════════════════════════════════════════════════════════════════════

@app.get("/workspaces/{workspace_id}/admin/overview")
async def workspace_overview(workspace_id: str, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM workspace_members WHERE workspace_id=%s AND status='active') AS total_members,
                (SELECT COUNT(*) FROM departments WHERE workspace_id=%s AND archived_at IS NULL) AS dept_count,
                (SELECT COUNT(*) FROM documents WHERE workspace_id=%s AND status='ready') AS doc_count,
                (SELECT COUNT(*) FROM query_events WHERE workspace_id=%s
                 AND created_at >= date_trunc('month',NOW())) AS queries_this_month,
                (SELECT COALESCE(SUM(file_size),0) FROM documents WHERE workspace_id=%s) AS storage_bytes
        """, (workspace_id,)*5)
        stats = dict(cur.fetchone())
        return {"overview": stats, "timestamp": datetime.utcnow().isoformat()}
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# INVITATIONS  (Phase 4)
# ════════════════════════════════════════════════════════════════════════════

@app.post("/workspaces/{workspace_id}/admin/invitations", status_code=201)
async def create_invitation(workspace_id: str, req: InviteRequest,
                             ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403, "Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Workspace name for email
        cur.execute("SELECT name FROM workspaces WHERE id=%s", (workspace_id,))
        ws = cur.fetchone()
        if not ws:
            raise HTTPException(404,"Workspace not found")

        # Revoke any prior pending invite for same email/workspace
        cur.execute("""UPDATE workspace_invitations SET status='revoked'
                       WHERE workspace_id=%s AND email=%s AND status='pending'""",
                    (workspace_id, req.email.lower()))

        # Generate secure token
        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        cur.execute("""
            INSERT INTO workspace_invitations
                (workspace_id,email,workspace_role,department_id,department_role,
                 permissions,invited_by,invite_token_hash,message,
                 expires_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW() + INTERVAL '%s days')
            RETURNING id
        """ , (workspace_id, req.email.lower(), req.workspace_role,
               req.department_id, req.department_role,
               req.permissions, ctx["user_id"], token_hash,
               req.message, INVITE_EXPIRE_DAYS))
        invite_id = cur.fetchone()["id"]
        conn.commit()

        invite_link = f"{FRONTEND_URL}/invite/{raw_token}"
        email_sent  = _send_invite_email(req.email, invite_link, ws["name"])

        _log(conn, ctx["user_id"], ctx["role"], "invitation.created",
             workspace_id=workspace_id, target_user_id=None,
             metadata={"email": req.email, "role": req.workspace_role,
                       "email_sent": email_sent},
             ip=ctx["ip"], request_id=ctx["request_id"])

        return {
            "id": str(invite_id),
            "email": req.email,
            "status": "pending",
            "email_sent": email_sent,
            "invite_link": None if email_sent else invite_link,
        }
    finally:
        cur.close(); conn.close()

@app.get("/workspaces/{workspace_id}/admin/invitations")
async def list_invitations(workspace_id: str, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT wi.id,wi.email,wi.workspace_role,wi.department_id,
                   wi.status,wi.expires_at,wi.accepted_at,wi.created_at,
                   u.email AS invited_by_email
            FROM workspace_invitations wi
            LEFT JOIN users u ON u.id = wi.invited_by
            WHERE wi.workspace_id=%s
            ORDER BY wi.created_at DESC
        """, (workspace_id,))
        rows = cur.fetchall()
        return {"invitations": [dict(r, created_at=_iso(r["created_at"]),
                                     expires_at=_iso(r["expires_at"]),
                                     accepted_at=_iso(r["accepted_at"])) for r in rows]}
    finally:
        cur.close(); conn.close()

@app.post("/workspaces/{workspace_id}/admin/invitations/{invite_id}/revoke")
async def revoke_invitation(workspace_id: str, invite_id: str,
                             ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("""UPDATE workspace_invitations SET status='revoked',updated_at=NOW()
                       WHERE id=%s AND workspace_id=%s AND status='pending'
                       RETURNING id""", (invite_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404,"Invitation not found or already processed")
        conn.commit()
        _log(conn,ctx["user_id"],ctx["role"],"invitation.revoked",
             workspace_id=workspace_id,metadata={"invite_id":invite_id},ip=ctx["ip"])
        return {"status":"revoked"}
    finally:
        cur.close(); conn.close()

# ── Accept invite (public) ───────────────────────────────────────────────────

@app.get("/invite/{token}")
async def get_invite_info(token: str):
    """Return invite metadata (used by frontend to show join screen)."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT wi.id,wi.email,wi.workspace_role,wi.status,wi.expires_at,
                   w.name AS workspace_name
            FROM workspace_invitations wi
            JOIN workspaces w ON w.id=wi.workspace_id
            WHERE wi.invite_token_hash=%s
        """, (token_hash,))
        inv = cur.fetchone()
        if not inv:
            raise HTTPException(404,"Invitation not found")
        if inv["status"] != "pending":
            raise HTTPException(410,f"Invitation is {inv['status']}")
        if inv["expires_at"] < datetime.utcnow().replace(tzinfo=inv["expires_at"].tzinfo):
            raise HTTPException(410,"Invitation has expired")
        return {
            "email": inv["email"],
            "workspace_name": inv["workspace_name"],
            "workspace_role": inv["workspace_role"],
            "expires_at": _iso(inv["expires_at"]),
        }
    finally:
        cur.close(); conn.close()

@app.post("/invite/{token}/accept")
async def accept_invite(token: str, request: Request):
    """
    Accept invite. Gateway must provide X-User-ID after login/signup.
    If user does not yet exist, frontend redirects to signup first.
    """
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(401,"Must be logged in to accept invitation")

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT * FROM workspace_invitations
            WHERE invite_token_hash=%s AND status='pending'
        """, (token_hash,))
        inv = cur.fetchone()
        if not inv:
            raise HTTPException(404,"Invitation not found or already used")
        now_utc = datetime.utcnow().replace(tzinfo=inv["expires_at"].tzinfo)
        if inv["expires_at"] < now_utc:
            cur.execute("UPDATE workspace_invitations SET status='expired' WHERE id=%s", (inv["id"],))
            conn.commit()
            raise HTTPException(410,"Invitation has expired")

        # Add to workspace_members (upsert)
        cur.execute("""
            INSERT INTO workspace_members(workspace_id,user_id,role,status,invited_by)
            VALUES(%s,%s,%s,'active',%s)
            ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=EXCLUDED.role,status='active'
        """, (inv["workspace_id"],user_id,inv["workspace_role"],inv["invited_by"]))

        # Add to department if specified
        if inv["department_id"]:
            cur.execute("""
                INSERT INTO department_members(workspace_id,department_id,user_id,role,added_by)
                VALUES(%s,%s,%s,%s,%s)
                ON CONFLICT(department_id,user_id) DO UPDATE SET role=EXCLUDED.role,status='active'
            """, (inv["workspace_id"],inv["department_id"],user_id,
                  inv["department_role"],inv["invited_by"]))

        # Mark invite accepted
        cur.execute("""UPDATE workspace_invitations
                       SET status='accepted',accepted_at=NOW(),accepted_by=%s
                       WHERE id=%s""", (user_id, inv["id"]))
        conn.commit()
        _log(conn, user_id,"member","invitation.accepted",
             workspace_id=str(inv["workspace_id"]),
             metadata={"role":inv["workspace_role"]})
        return {"status":"accepted","workspace_id":str(inv["workspace_id"])}
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# DEPARTMENTS  (Phase 5)
# ════════════════════════════════════════════════════════════════════════════

@app.get("/workspaces/{workspace_id}/admin/departments")
async def list_departments(workspace_id: str, ctx: dict = Depends(require_workspace_member)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT d.*,
                   (SELECT COUNT(*) FROM department_members dm
                    WHERE dm.department_id=d.id AND dm.status='active') AS member_count,
                   (SELECT COUNT(*) FROM document_permissions dp
                    WHERE dp.department_id=d.id) AS doc_count
            FROM departments d
            WHERE d.workspace_id=%s AND d.archived_at IS NULL
            ORDER BY d.name
        """, (workspace_id,))
        rows = cur.fetchall()
        return {"departments": [dict(r, created_at=_iso(r["created_at"])) for r in rows]}
    finally:
        cur.close(); conn.close()

@app.post("/workspaces/{workspace_id}/admin/departments", status_code=201)
async def create_department(workspace_id: str, req: DepartmentCreate,
                             ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO departments(workspace_id,name,slug,description,
                                    parent_department_id,created_by)
            VALUES(%s,%s,%s,%s,%s,%s) RETURNING *
        """, (workspace_id,req.name,req.slug.lower().replace(" ","-"),
              req.description,req.parent_department_id,ctx["user_id"]))
        dept = cur.fetchone()
        conn.commit()
        _log(conn,ctx["user_id"],ctx["role"],"department.created",
             workspace_id=workspace_id,department_id=str(dept["id"]),
             metadata={"name":req.name},ip=ctx["ip"])
        return {"department": dict(dept, created_at=_iso(dept["created_at"]))}
    except Exception as e:
        if "uq_department_slug_workspace" in str(e):
            raise HTTPException(409,"Department slug already exists in this workspace")
        raise HTTPException(500,str(e))
    finally:
        cur.close(); conn.close()

@app.patch("/workspaces/{workspace_id}/admin/departments/{dept_id}")
async def update_department(workspace_id: str, dept_id: str, req: DepartmentUpdate,
                             ctx: dict = Depends(require_dept_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        sets, params = [], []
        if req.name:
            sets.append("name=%s"); params.append(req.name)
        if req.description is not None:
            sets.append("description=%s"); params.append(req.description)
        if not sets:
            raise HTTPException(400,"Nothing to update")
        sets.append("updated_at=NOW()")
        params += [dept_id, workspace_id]
        cur.execute(f"UPDATE departments SET {','.join(sets)} "
                    "WHERE id=%s AND workspace_id=%s RETURNING *", params)
        dept = cur.fetchone()
        if not dept:
            raise HTTPException(404,"Department not found")
        conn.commit()
        return {"department": dict(dept, created_at=_iso(dept["created_at"]))}
    finally:
        cur.close(); conn.close()

@app.delete("/workspaces/{workspace_id}/admin/departments/{dept_id}")
async def archive_department(workspace_id: str, dept_id: str,
                              ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("""UPDATE departments SET archived_at=NOW()
                       WHERE id=%s AND workspace_id=%s AND archived_at IS NULL
                       RETURNING id""", (dept_id, workspace_id))
        if not cur.fetchone():
            raise HTTPException(404,"Department not found")
        conn.commit()
        _log(conn,ctx["user_id"],ctx["role"],"department.archived",
             workspace_id=workspace_id,department_id=dept_id,ip=ctx["ip"])
        return {"status":"archived"}
    finally:
        cur.close(); conn.close()

@app.post("/workspaces/{workspace_id}/admin/departments/{dept_id}/members")
async def add_dept_member(workspace_id: str, dept_id: str, req: AddDeptMember,
                           ctx: dict = Depends(require_dept_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor()
    try:
        # Verify user is workspace member
        cur.execute("""SELECT id FROM workspace_members
                       WHERE workspace_id=%s AND user_id=%s AND status='active'""",
                    (workspace_id, req.user_id))
        if not cur.fetchone():
            raise HTTPException(400,"User is not a member of this workspace")
        cur.execute("""
            INSERT INTO department_members(workspace_id,department_id,user_id,role,added_by)
            VALUES(%s,%s,%s,%s,%s)
            ON CONFLICT(department_id,user_id) DO UPDATE SET role=EXCLUDED.role,status='active'
        """, (workspace_id,dept_id,req.user_id,req.role,ctx["user_id"]))
        conn.commit()
        _log(conn,ctx["user_id"],ctx["role"],"department.member_added",
             workspace_id=workspace_id,department_id=dept_id,
             target_user_id=req.user_id,metadata={"role":req.role},ip=ctx["ip"])
        return {"status":"added","user_id":req.user_id,"role":req.role}
    finally:
        cur.close(); conn.close()

@app.delete("/workspaces/{workspace_id}/admin/departments/{dept_id}/members/{user_id}")
async def remove_dept_member(workspace_id: str, dept_id: str, user_id: str,
                              ctx: dict = Depends(require_dept_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("""UPDATE department_members SET status='removed',updated_at=NOW()
                       WHERE department_id=%s AND user_id=%s AND workspace_id=%s""",
                    (dept_id,user_id,workspace_id))
        conn.commit()
        return {"status":"removed"}
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# DOCUMENT PERMISSIONS  (Phase 6)
# ════════════════════════════════════════════════════════════════════════════

@app.post("/workspaces/{workspace_id}/admin/documents/permissions")
async def set_document_permissions(workspace_id: str, req: DocPermissionSet,
                                    ctx: dict = Depends(require_admin)):
    """Set access permissions on a document."""
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Verify doc belongs to workspace
        cur.execute("SELECT id,access_scope FROM documents WHERE id=%s AND workspace_id=%s",
                    (req.document_id, workspace_id))
        doc = cur.fetchone()
        if not doc:
            raise HTTPException(404,"Document not found in this workspace")

        # Update document access_scope
        cur.execute("UPDATE documents SET access_scope=%s WHERE id=%s",
                    (req.access_scope, req.document_id))

        # Delete existing non-owner permissions
        cur.execute("""DELETE FROM document_permissions
                       WHERE document_id=%s AND permission_level != 'owner'""",
                    (req.document_id,))

        if req.access_scope == "workspace":
            cur.execute("""INSERT INTO document_permissions
                (workspace_id,document_id,access_scope,permission_level,granted_by)
                VALUES(%s,%s,'workspace',%s,%s)""",
               (workspace_id,req.document_id,req.permission_level,ctx["user_id"]))

        elif req.access_scope == "departments":
            for dept_id in req.department_ids:
                cur.execute("""INSERT INTO document_permissions
                    (workspace_id,document_id,department_id,access_scope,permission_level,granted_by)
                    VALUES(%s,%s,%s,'departments',%s,%s)""",
                   (workspace_id,req.document_id,dept_id,req.permission_level,ctx["user_id"]))

        elif req.access_scope == "users":
            for uid in req.user_ids:
                cur.execute("""INSERT INTO document_permissions
                    (workspace_id,document_id,user_id,access_scope,permission_level,granted_by)
                    VALUES(%s,%s,%s,'users',%s,%s)""",
                   (workspace_id,req.document_id,uid,req.permission_level,ctx["user_id"]))

        elif req.access_scope == "private":
            # owner only — keep owner record created at upload time
            pass

        conn.commit()
        _log(conn,ctx["user_id"],ctx["role"],"document.permissions_updated",
             workspace_id=workspace_id,document_id=req.document_id,
             metadata={"scope":req.access_scope,"level":req.permission_level},ip=ctx["ip"])
        return {"status":"updated","document_id":req.document_id,"scope":req.access_scope}
    finally:
        cur.close(); conn.close()

@app.get("/workspaces/{workspace_id}/admin/documents")
async def list_workspace_documents(workspace_id: str, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT d.id,d.name,d.status,d.access_scope,d.sensitivity_level,
                   d.file_size,d.created_at,u.email AS uploaded_by_email,
                   (SELECT COUNT(*) FROM document_permissions dp WHERE dp.document_id=d.id) AS permission_count
            FROM documents d
            LEFT JOIN users u ON u.id=d.created_by_user_id
            WHERE d.workspace_id=%s
            ORDER BY d.created_at DESC
        """, (workspace_id,))
        rows = cur.fetchall()
        return {"documents": [dict(r,created_at=_iso(r["created_at"])) for r in rows]}
    finally:
        cur.close(); conn.close()

@app.get("/workspaces/{workspace_id}/admin/audit-logs")
async def workspace_audit_logs(workspace_id: str, page: int = 1, limit: int = 50,
                                ctx: dict = Depends(require_dept_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        offset = (page-1)*limit
        cur.execute("""
            SELECT aal.*,u.email AS actor_email
            FROM admin_action_logs aal
            LEFT JOIN users u ON u.id=aal.actor_user_id
            WHERE aal.workspace_id=%s
            ORDER BY aal.created_at DESC LIMIT %s OFFSET %s
        """, (workspace_id,limit,offset))
        rows = cur.fetchall()
        return {"logs":[dict(r,created_at=_iso(r["created_at"])) for r in rows],
                "page":page,"limit":limit}
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# USERS (Phase 2)
# ════════════════════════════════════════════════════════════════════════════

@app.get("/workspaces/{workspace_id}/admin/users")
async def list_workspace_users(workspace_id: str, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT u.id, u.email, u.full_name, wm.role AS workspace_role,
                   wm.status, wm.created_at AS joined_at,
                   (SELECT COUNT(*) FROM department_members dm WHERE dm.workspace_id=%s AND dm.user_id=u.id AND dm.status='active') AS dept_count,
                   (SELECT COUNT(*) FROM query_events qe WHERE qe.workspace_id=%s AND qe.user_id::text=u.id::text) AS query_count
            FROM workspace_members wm
            JOIN users u ON u.id = wm.user_id
            WHERE wm.workspace_id=%s AND wm.status != 'removed'
            ORDER BY u.email
        """, (workspace_id, workspace_id, workspace_id))
        rows = cur.fetchall()
        return {"users": [dict(r, joined_at=_iso(r["joined_at"])) for r in rows]}
    finally:
        cur.close(); conn.close()

@app.patch("/workspaces/{workspace_id}/admin/users/{user_id}/role")
async def update_user_role(workspace_id: str, user_id: str, req: RoleUpdate, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("UPDATE workspace_members SET role=%s WHERE workspace_id=%s AND user_id=%s RETURNING id",
                    (req.role, workspace_id, user_id))
        if not cur.fetchone():
            raise HTTPException(404,"User not found in workspace")
        conn.commit()
        _log(conn, ctx["user_id"], ctx["role"], "user.role_changed", workspace_id, user_id, metadata={"new_role":req.role}, ip=ctx["ip"])
        return {"status":"updated"}
    finally:
        cur.close(); conn.close()

@app.post("/workspaces/{workspace_id}/admin/users/{user_id}/assign-department")
async def assign_department(workspace_id: str, user_id: str, req: AssignDepartmentReq, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO department_members(workspace_id,department_id,user_id,role,added_by)
            VALUES(%s,%s,%s,%s,%s)
            ON CONFLICT(department_id,user_id) DO UPDATE SET role=EXCLUDED.role,status='active'
        """, (workspace_id,req.department_id,user_id,req.role,ctx["user_id"]))
        conn.commit()
        _log(conn, ctx["user_id"], ctx["role"], "user.department_assigned", workspace_id, user_id, req.department_id, metadata={"role":req.role}, ip=ctx["ip"])
        return {"status":"assigned"}
    finally:
        cur.close(); conn.close()

@app.delete("/workspaces/{workspace_id}/admin/users/{user_id}/departments/{department_id}")
async def remove_user_department(workspace_id: str, user_id: str, department_id: str, ctx: dict = Depends(require_dept_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("UPDATE department_members SET status='removed', updated_at=NOW() WHERE workspace_id=%s AND department_id=%s AND user_id=%s",
                    (workspace_id, department_id, user_id))
        conn.commit()
        _log(conn, ctx["user_id"], ctx["role"], "user.department_removed", workspace_id, user_id, department_id, ip=ctx["ip"])
        return {"status":"removed"}
    finally:
        cur.close(); conn.close()

@app.post("/workspaces/{workspace_id}/admin/users/{user_id}/suspend")
async def suspend_workspace_user(workspace_id: str, user_id: str, req: SuspendUserReq, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("UPDATE workspace_members SET status='suspended' WHERE workspace_id=%s AND user_id=%s", (workspace_id, user_id))
        conn.commit()
        _log(conn, ctx["user_id"], ctx["role"], "user.suspended", workspace_id, user_id, reason=req.reason, ip=ctx["ip"])
        return {"status":"suspended"}
    finally:
        cur.close(); conn.close()

@app.post("/workspaces/{workspace_id}/admin/users/{user_id}/unsuspend")
async def unsuspend_workspace_user(workspace_id: str, user_id: str, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("UPDATE workspace_members SET status='active' WHERE workspace_id=%s AND user_id=%s", (workspace_id, user_id))
        conn.commit()
        _log(conn, ctx["user_id"], ctx["role"], "user.unsuspended", workspace_id, user_id, ip=ctx["ip"])
        return {"status":"unsuspended"}
    finally:
        cur.close(); conn.close()

@app.delete("/workspaces/{workspace_id}/admin/users/{user_id}")
async def remove_workspace_user(workspace_id: str, user_id: str, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("UPDATE workspace_members SET status='removed' WHERE workspace_id=%s AND user_id=%s", (workspace_id, user_id))
        conn.commit()
        _log(conn, ctx["user_id"], ctx["role"], "user.removed", workspace_id, user_id, ip=ctx["ip"])
        return {"status":"removed"}
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# API KEYS (Phase 5)
# ════════════════════════════════════════════════════════════════════════════

@app.get("/workspaces/{workspace_id}/admin/api-keys")
async def list_api_keys(workspace_id: str, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, name, created_at, expires_at, last_used_at, scopes_json, revoked_at FROM api_keys WHERE workspace_id=%s ORDER BY created_at DESC", (workspace_id,))
        rows = cur.fetchall()
        return {"api_keys": [dict(r, created_at=_iso(r["created_at"]), expires_at=_iso(r["expires_at"]), last_used_at=_iso(r["last_used_at"]), revoked_at=_iso(r["revoked_at"])) for r in rows]}
    except Exception as e:
        logger.warning(f"Could not fetch API keys (table may not exist yet): {e}")
        return {"api_keys":[]}
    finally:
        cur.close(); conn.close()

@app.post("/workspaces/{workspace_id}/admin/api-keys")
async def create_api_key(workspace_id: str, req: ApiKeyCreate, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        raw_key = "cm_" + secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                workspace_id UUID NOT NULL,
                name VARCHAR(255) NOT NULL,
                key_hash VARCHAR(255) NOT NULL,
                created_by UUID NOT NULL,
                scopes_json JSONB,
                department_ids JSONB,
                document_ids JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                expires_at TIMESTAMP WITH TIME ZONE,
                last_used_at TIMESTAMP WITH TIME ZONE,
                revoked_at TIMESTAMP WITH TIME ZONE
            )
        """)
        cur.execute("""
            INSERT INTO api_keys(workspace_id, name, key_hash, created_by, scopes_json, department_ids, document_ids, expires_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s, NOW() + INTERVAL '%s days') RETURNING id
        """, (workspace_id, req.name, key_hash, ctx["user_id"], json.dumps(req.scopes), json.dumps(req.department_ids), json.dumps(req.document_ids), req.expires_in_days or 365))
        key_id = cur.fetchone()["id"]
        conn.commit()
        _log(conn, ctx["user_id"], ctx["role"], "api_key.created", workspace_id, metadata={"name":req.name}, ip=ctx["ip"])
        return {"id": str(key_id), "name": req.name, "api_key": raw_key}
    finally:
        cur.close(); conn.close()

@app.delete("/workspaces/{workspace_id}/admin/api-keys/{key_id}")
async def revoke_api_key(workspace_id: str, key_id: str, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("UPDATE api_keys SET revoked_at=NOW() WHERE id=%s AND workspace_id=%s", (key_id, workspace_id))
        conn.commit()
        _log(conn, ctx["user_id"], ctx["role"], "api_key.revoked", workspace_id, metadata={"key_id":key_id}, ip=ctx["ip"])
        return {"status":"revoked"}
    except Exception:
        raise HTTPException(500, "Error revoking key")
    finally:
        cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# BILLING & USAGE
# ════════════════════════════════════════════════════════════════════════════

@app.get("/workspaces/{workspace_id}/admin/usage")
async def get_workspace_usage(workspace_id: str, ctx: dict = Depends(require_workspace_member)):
    if ctx["workspace_id"] != workspace_id or ctx["role"] not in ("owner","admin","billing_admin"):
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT COALESCE(SUM(estimated_cost),0) AS total_cost,
                   COUNT(*) AS query_count
            FROM query_events
            WHERE workspace_id=%s AND created_at >= date_trunc('month',NOW())
        """, (workspace_id,))
        return {"usage": dict(cur.fetchone()), "timestamp": datetime.utcnow().isoformat()}
    finally:
        cur.close(); conn.close()

@app.get("/workspaces/{workspace_id}/admin/billing")
async def get_workspace_billing(workspace_id: str, ctx: dict = Depends(require_workspace_member)):
    if ctx["workspace_id"] != workspace_id or ctx["role"] not in ("owner","admin","billing_admin"):
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT p.name AS plan_name, s.status FROM workspaces w LEFT JOIN subscriptions s ON s.workspace_id=w.id LEFT JOIN plans p ON p.id=w.plan_id WHERE w.id=%s", (workspace_id,))
        return {"billing": dict(cur.fetchone() or {})}
    finally:
        cur.close(); conn.close()

@app.post("/workspaces/{workspace_id}/admin/billing/checkout")
async def start_checkout(workspace_id: str, ctx: dict = Depends(require_workspace_member)):
    if ctx["workspace_id"] != workspace_id or ctx["role"] not in ("owner","admin","billing_admin"):
        raise HTTPException(403,"Access denied")
    conn = get_db()
    _log(conn, ctx["user_id"], ctx["role"], "billing.checkout_started", workspace_id, ip=ctx["ip"])
    conn.close()
    return {"checkout_url": f"https://billing.cognimend.ai/checkout/{workspace_id}"}

@app.get("/workspaces/{workspace_id}/admin/security")
async def get_workspace_security(workspace_id: str, ctx: dict = Depends(require_admin)):
    if ctx["workspace_id"] != workspace_id:
        raise HTTPException(403,"Access denied")
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM admin_action_logs WHERE workspace_id=%s AND action LIKE 'ACCESS_DENIED%' ORDER BY created_at DESC LIMIT 20", (workspace_id,))
        return {"security_events": [dict(r, created_at=_iso(r["created_at"])) for r in cur.fetchall()]}
    finally:
        cur.close(); conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8009)

