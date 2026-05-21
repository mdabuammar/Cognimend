"""
Cognimend Auth Service — Port 8000
Handles: signup, login, logout, refresh, Google OAuth, JWT
"""
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from contextlib import asynccontextmanager
import os, hashlib, secrets, logging, asyncio
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
import psycopg2
import psycopg2.pool
import psycopg2.extras
import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("auth")

# ─── Config ───────────────────────────────────────────────────────────────────
JWT_SECRET        = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "change-refresh-secret-too")
JWT_ALGO          = "HS256"
ACCESS_TOKEN_TTL  = int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "60"))
REFRESH_TOKEN_TTL = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))
FRONTEND_URL      = os.getenv("FRONTEND_URL", "http://localhost:8080")

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
PG_DB   = os.getenv("POSTGRES_DB", "cognimend")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "password123")

# ─── DB Pool ──────────────────────────────────────────────────────────────────
db_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

def get_conn():
    return db_pool.getconn()

def release_conn(conn):
    db_pool.putconn(conn)

def db_execute(sql: str, params=None, fetch: str = "none"):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if fetch == "one":
                result = cur.fetchone()
            elif fetch == "all":
                result = cur.fetchall()
            else:
                result = None
            conn.commit()
            return result
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)

# ─── JWT Helpers ──────────────────────────────────────────────────────────────
def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_TTL),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_TTL),
    }
    return jwt.encode(payload, JWT_REFRESH_SECRET, algorithm=JWT_ALGO)

def verify_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

def verify_refresh_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_REFRESH_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid refresh token")

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

# ─── Auth Dependency ──────────────────────────────────────────────────────────
def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    return verify_access_token(auth[7:])

# ─── Workspace bootstrap ──────────────────────────────────────────────────────
def bootstrap_new_user(user_id: str, name: str):
    """Create default workspace + free subscription for a new user."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get free plan
            cur.execute("SELECT id FROM plans WHERE name = 'free' LIMIT 1")
            plan = cur.fetchone()
            plan_id = plan["id"] if plan else None

            # Create workspace
            workspace_name = f"{name}'s Workspace" if name else "My Workspace"
            cur.execute(
                """INSERT INTO workspaces (name, slug, owner_id, plan_id)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (workspace_name, f"ws-{user_id[:8]}", user_id, plan_id)
            )
            ws = cur.fetchone()
            workspace_id = ws["id"]

            # Add owner as member
            cur.execute(
                """INSERT INTO workspace_members (workspace_id, user_id, role)
                   VALUES (%s, %s, 'owner') ON CONFLICT DO NOTHING""",
                (workspace_id, user_id)
            )

            # Create subscription if plan exists
            if plan_id:
                cur.execute(
                    """INSERT INTO subscriptions (workspace_id, plan_id, status)
                       VALUES (%s, %s, 'active') ON CONFLICT DO NOTHING""",
                    (workspace_id, plan_id)
                )

            conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning(f"bootstrap_new_user failed: {e}")
    finally:
        release_conn(conn)

# ─── Pydantic models ──────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    logger.info("Auth Service starting…")
    db_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=2, maxconn=20,
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS
    )
    logger.info("✅ DB pool ready")
    yield
    if db_pool:
        db_pool.closeall()
    logger.info("Auth Service stopped")

app = FastAPI(title="Cognimend Auth Service", version="1.0.0", lifespan=lifespan)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:8080,http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:5176").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "auth"}

# ─── Signup ───────────────────────────────────────────────────────────────────
@app.post("/auth/signup")
async def signup(body: SignupRequest):
    # Check duplicate
    existing = db_execute("SELECT id FROM users WHERE email = %s", (body.email,), fetch="one")
    if existing:
        raise HTTPException(400, "This email is already registered. Please log in or use another email.")

    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user = db_execute(
        """INSERT INTO users (email, password_hash, full_name)
           VALUES (%s, %s, %s) RETURNING id, email, full_name""",
        (body.email, pw_hash, body.full_name),
        fetch="one"
    )
    db_execute(
        "INSERT INTO auth_accounts (user_id, provider) VALUES (%s, 'local')",
        (user["id"],)
    )

    bootstrap_new_user(str(user["id"]), user["full_name"])
    _audit(None, str(user["id"]), "user.signup", "user", str(user["id"]), {"method": "manual"})

    access  = create_access_token(str(user["id"]), user["email"])
    refresh = create_refresh_token(str(user["id"]))
    _store_refresh(str(user["id"]), refresh)

    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": {"id": str(user["id"]), "email": user["email"], "full_name": user["full_name"]},
        "is_new_user": True,
    }

# ─── Login ────────────────────────────────────────────────────────────────────
@app.post("/auth/login")
async def login(body: LoginRequest):
    user = db_execute(
        "SELECT id, email, full_name, password_hash, is_active FROM users WHERE email = %s",
        (body.email,), fetch="one"
    )
    if not user:
        raise HTTPException(401, "Invalid email or password.")
    if not user["is_active"]:
        raise HTTPException(403, "Your account has been suspended.")
    if not user["password_hash"]:
        raise HTTPException(400, "This account uses Google sign-in. Please use 'Continue with Google'.")
    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Invalid email or password.")

    db_execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user["id"],))
    _audit(None, str(user["id"]), "user.login", "user", str(user["id"]), {"method": "manual"})

    access  = create_access_token(str(user["id"]), user["email"])
    refresh = create_refresh_token(str(user["id"]))
    _store_refresh(str(user["id"]), refresh)

    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": {"id": str(user["id"]), "email": user["email"], "full_name": user["full_name"]},
        "is_new_user": False,
    }

# ─── Me ───────────────────────────────────────────────────────────────────────
@app.get("/auth/me")
async def me(current: dict = Depends(get_current_user)):
    user = db_execute(
        "SELECT id, email, full_name, created_at FROM users WHERE id = %s",
        (current["sub"],), fetch="one"
    )
    if not user:
        raise HTTPException(404, "User not found")

    # Get linked providers
    accounts = db_execute(
        "SELECT provider FROM auth_accounts WHERE user_id = %s",
        (current["sub"],), fetch="all"
    )
    providers = [a["provider"] for a in (accounts or [])]

    # Get workspace details and subscription plan
    workspace_info = db_execute(
        """SELECT w.id as workspace_id, w.name as workspace_name, w.slug as workspace_slug, p.name as plan_name
           FROM workspaces w
           JOIN workspace_members wm ON wm.workspace_id = w.id
           LEFT JOIN plans p ON w.plan_id = p.id
           WHERE wm.user_id = %s AND w.is_active = TRUE
           LIMIT 1""",
        (current["sub"],), fetch="one"
    )
    
    workspace_id = str(workspace_info['workspace_id']) if workspace_info else None
    plan_name = workspace_info['plan_name'] if workspace_info and workspace_info['plan_name'] else "free"
    workspace_name = workspace_info['workspace_name'] if workspace_info else "My Workspace"
    workspace_slug = workspace_info['workspace_slug'] if workspace_info else "default"

    # Get platform role
    platform_admin = db_execute(
        "SELECT role FROM platform_admins WHERE user_id = %s AND status = 'active'",
        (current["sub"],), fetch="one"
    )
    platform_role = platform_admin["role"] if platform_admin else None
    role = "admin" if platform_role in ("super_admin", "admin") else "user"

    # Compute allowed portals for backward compatibility
    portals = ["customer"]
    if role == "admin":
        portals.append("super_admin")

    return {
        "id": str(user["id"]),
        "email": user["email"],
        "full_name": user["full_name"],
        "role": role,
        "plan": plan_name,
        "workspace_id": workspace_id,
        "avatar_url": None,
        "email_verified": True,
        "providers": providers,
        "platform_role": platform_role,
        "staff_role": None,
        "allowed_portals": portals,
        "workspaces": [
            {
                "id": workspace_id,
                "name": workspace_name,
                "slug": workspace_slug,
                "role": "owner" if role == "admin" else "member",
                "departments": []
            }
        ] if workspace_id else []
    }

# ─── Refresh ──────────────────────────────────────────────────────────────────
@app.post("/auth/refresh")
async def refresh_token(body: RefreshRequest):
    payload = verify_refresh_token(body.refresh_token)
    token_hash = hash_token(body.refresh_token)

    stored = db_execute(
        "SELECT id FROM refresh_tokens WHERE token_hash = %s AND revoked_at IS NULL AND expires_at > NOW()",
        (token_hash,), fetch="one"
    )
    if not stored:
        raise HTTPException(401, "Refresh token is invalid or expired.")

    # Rotate: revoke old, issue new
    db_execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE token_hash = %s", (token_hash,))

    user = db_execute("SELECT id, email FROM users WHERE id = %s", (payload["sub"],), fetch="one")
    if not user:
        raise HTTPException(401, "User not found")

    access  = create_access_token(str(user["id"]), user["email"])
    new_ref = create_refresh_token(str(user["id"]))
    _store_refresh(str(user["id"]), new_ref)

    return {"access_token": access, "refresh_token": new_ref, "token_type": "bearer"}

# ─── Logout ───────────────────────────────────────────────────────────────────
@app.post("/auth/logout")
async def logout(body: RefreshRequest):
    token_hash = hash_token(body.refresh_token)
    db_execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE token_hash = %s", (token_hash,))
    return {"message": "Logged out successfully"}

# ─── Forgot Password ──────────────────────────────────────────────────────────
@app.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    user = db_execute("SELECT id FROM users WHERE email = %s", (body.email,), fetch="one")
    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If that email exists, a reset link has been sent."}

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    db_execute(
        "INSERT INTO password_reset_tokens (user_id, token_hash) VALUES (%s, %s)",
        (user["id"], token_hash)
    )
    reset_link = f"{FRONTEND_URL}/reset-password?token={raw_token}"
    logger.info(f"Password reset link (send via email): {reset_link}")
    # TODO: Send email via SendGrid/SES
    return {"message": "If that email exists, a reset link has been sent.", "debug_link": reset_link}

# ─── Reset Password ───────────────────────────────────────────────────────────
@app.post("/auth/reset-password")
async def reset_password(body: ResetPasswordRequest):
    token_hash = hash_token(body.token)
    record = db_execute(
        """SELECT id, user_id FROM password_reset_tokens
           WHERE token_hash = %s AND used_at IS NULL AND expires_at > NOW()""",
        (token_hash,), fetch="one"
    )
    if not record:
        raise HTTPException(400, "Reset link is invalid or has expired.")

    pw_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    db_execute("UPDATE users SET password_hash = %s WHERE id = %s", (pw_hash, record["user_id"]))
    db_execute("UPDATE password_reset_tokens SET used_at = NOW() WHERE id = %s", (record["id"],))
    # Revoke all refresh tokens for this user
    db_execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = %s", (record["user_id"],))
    return {"message": "Password updated. Please log in with your new password."}

# ─── Google OAuth ─────────────────────────────────────────────────────────────
@app.get("/auth/google/start")
async def google_start():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google OAuth is not configured on this server.")
    state = secrets.token_urlsafe(32)
    # TODO: store state in Redis with short TTL for CSRF protection
    params = (
        f"client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid+email+profile"
        f"&state={state}"
        f"&access_type=offline"
        f"&prompt=select_account"
    )
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")

@app.get("/auth/google/callback")
async def google_callback(code: str, state: str):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google OAuth not configured")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        )
    if token_resp.status_code != 200:
        raise HTTPException(400, "We could not sign you in with Google. Please try again.")

    tokens = token_resp.json()
    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(400, "Invalid Google response.")

    # Decode Google ID token (no verification for simplicity; use google-auth lib in prod)
    import base64, json as _json
    parts = id_token.split(".")
    padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
    google_payload = _json.loads(base64.urlsafe_b64decode(padded))

    google_sub   = google_payload.get("sub")
    google_email = google_payload.get("email")
    google_name  = google_payload.get("name", "")
    google_pic   = google_payload.get("picture")
    email_verified = google_payload.get("email_verified", False)

    if not email_verified:
        raise HTTPException(400, "Google account email is not verified.")

    # Check if Google account already linked
    account = db_execute(
        "SELECT user_id FROM auth_accounts WHERE provider = 'google' AND provider_user_id = %s",
        (google_sub,), fetch="one"
    )

    is_new = False
    if account:
        user_id = str(account["user_id"])
    else:
        # Check if manual user with same email exists
        existing_user = db_execute(
            "SELECT id FROM users WHERE email = %s", (google_email,), fetch="one"
        )
        if existing_user:
            user_id = str(existing_user["id"])
            # Link Google to existing account
            db_execute(
                """INSERT INTO auth_accounts (user_id, provider, provider_user_id, provider_email, provider_avatar_url)
                   VALUES (%s, 'google', %s, %s, %s) ON CONFLICT DO NOTHING""",
                (user_id, google_sub, google_email, google_pic)
            )
        else:
            # Create new user
            new_user = db_execute(
                """INSERT INTO users (email, full_name, avatar_url, email_verified)
                   VALUES (%s, %s, %s, TRUE) RETURNING id""",
                (google_email, google_name, google_pic), fetch="one"
            )
            user_id = str(new_user["id"])
            db_execute(
                """INSERT INTO auth_accounts (user_id, provider, provider_user_id, provider_email, provider_avatar_url)
                   VALUES (%s, 'google', %s, %s, %s)""",
                (user_id, google_sub, google_email, google_pic)
            )
            bootstrap_new_user(user_id, google_name)
            is_new = True

    db_execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (user_id,))
    _audit(None, user_id, "user.google_login", "user", user_id, {})

    access  = create_access_token(user_id, google_email)
    refresh = create_refresh_token(user_id)
    _store_refresh(user_id, refresh)

    # Redirect to frontend with tokens in query params (use secure method in prod)
    redirect = f"{FRONTEND_URL}/auth/callback?access_token={access}&refresh_token={refresh}&is_new={is_new}"
    return RedirectResponse(redirect)

# ─── Link / Unlink Google ─────────────────────────────────────────────────────
@app.post("/auth/google/unlink")
async def unlink_google(current: dict = Depends(get_current_user)):
    has_password = db_execute(
        "SELECT password_hash FROM users WHERE id = %s", (current["sub"],), fetch="one"
    )
    if not has_password or not has_password["password_hash"]:
        raise HTTPException(400, "Set a password before unlinking Google.")
    db_execute(
        "DELETE FROM auth_accounts WHERE user_id = %s AND provider = 'google'",
        (current["sub"],)
    )
    return {"message": "Google account unlinked."}

# ─── Helpers ──────────────────────────────────────────────────────────────────
def _store_refresh(user_id: str, token: str):
    token_hash = hash_token(token)
    expires = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_TTL)
    db_execute(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
        (user_id, token_hash, expires)
    )

def _audit(workspace_id, user_id, action, entity_type, entity_id, meta):
    try:
        db_execute(
            """INSERT INTO audit_logs (workspace_id, user_id, action, entity_type, entity_id, metadata_json)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (workspace_id, user_id, action, entity_type, entity_id, psycopg2.extras.Json(meta))
        )
    except Exception as e:
        logger.warning(f"Audit log failed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
