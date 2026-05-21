"""
Cognimend API Gateway — Port 8007
Phase 5 hardened: rate limiting, spoofed-header stripping, role injection,
internal service trust token, audit logging, request ID propagation.
"""
import os
import time
import logging
import uuid
import secrets
from collections import defaultdict
from typing import Optional

import httpx
import jwt
from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from database import (
    init_db_pool,
    get_user_workspace_role,
    get_user_default_workspace,
    get_user_platform_role,
    get_user_staff_role,
    log_audit_event,
)
from billing import check_workspace_plan_limits

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("gateway")

# ─── Config ───────────────────────────────────────────────────────────────────
JWT_SECRET           = os.getenv("JWT_SECRET", "change-me-in-production")
INTERNAL_TOKEN       = os.getenv("INTERNAL_SERVICE_TOKEN", "internal-dev-token")
AUTH_SERVICE_URL     = os.getenv("AUTH_SERVICE_URL",     "http://localhost:8000")
UPLOAD_SERVICE_URL   = os.getenv("UPLOAD_SERVICE_URL",   "http://localhost:8001")
QUERY_SERVICE_URL    = os.getenv("QUERY_SERVICE_URL",    "http://localhost:8002")
TELEMETRY_SERVICE_URL= os.getenv("TELEMETRY_SERVICE_URL","http://localhost:8003")
DRIFT_DETECTOR_URL   = os.getenv("DRIFT_DETECTOR_URL",   "http://localhost:8004")
CONTROLLER_URL       = os.getenv("CONTROLLER_URL",       "http://localhost:8005")
EVALUATION_URL       = os.getenv("EVALUATION_URL",       "http://localhost:8006")
SUPER_ADMIN_URL      = os.getenv("SUPER_ADMIN_URL",      "http://localhost:8008")
WORKSPACE_ADMIN_URL  = os.getenv("WORKSPACE_ADMIN_URL",  "http://localhost:8009")
STAFF_SERVICE_URL    = os.getenv("STAFF_SERVICE_URL",    "http://localhost:8010")

MAX_UPLOAD_BYTES     = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))  # 50 MB

# ─── In-memory Rate Limiter ────────────────────────────────────────────────────
_rate_store: dict[str, list[float]] = defaultdict(list)

RATE_LIMITS = {
    "/auth/signup":          (5,  60),
    "/auth/login":           (10, 60),
    "/auth/google/start":    (5,  60),
    "/auth/forgot-password": (3,  60),
    "/upload":               (20, 60),
    "/query":                (30, 60),
    "/query/with-file":      (10, 60),
}


def _check_rate_limit(client_ip: str, path: str):
    """Sliding-window rate limiter. Raises 429 if over limit."""
    # find best matching route prefix
    limit, window = None, None
    for route, (lim, win) in RATE_LIMITS.items():
        if path.startswith(route):
            limit, window = lim, win
            break
    if limit is None:
        return  # no limit for this route

    key = f"{client_ip}:{path}"
    now = time.time()
    cutoff = now - window
    _rate_store[key] = [t for t in _rate_store[key] if t > cutoff]
    if len(_rate_store[key]) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {window} seconds.",
        )
    _rate_store[key].append(now)


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Cognimend API Gateway",
    version="2.0.0",
    docs_url=None,          # disable swagger in prod-like mode
    redoc_url=None,
)

# CORS — only allow configured frontend origin(s)
cors_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:8080,http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:5176"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


# ─── Error handler — never expose tracebacks ─────────────────────────────────
@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "?")
    logger.exception(f"[{request_id}] Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


# ─── Startup / Shutdown ───────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    init_db_pool()
    app.state.client = httpx.AsyncClient(timeout=60.0, limits=httpx.Limits(max_connections=100))
    logger.info("✅ Gateway started — INTERNAL_SERVICE_TOKEN configured: %s",
                bool(INTERNAL_TOKEN))


@app.on_event("shutdown")
async def shutdown_event():
    await app.state.client.aclose()
    logger.info("Gateway shut down cleanly")


# ─── JWT Auth ────────────────────────────────────────────────────────────────
async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid authentication token")
    token = auth[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return {"user_id": payload.get("sub"), "email": payload.get("email")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


# ─── Workspace Access Check ───────────────────────────────────────────────────
async def require_workspace_access(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    # Client-supplied header — validate against DB (not blindly trusted)
    workspace_id = request.headers.get("X-Workspace-ID")
    if workspace_id:
        role = get_user_workspace_role(user["user_id"], workspace_id)
        if not role:
            raise HTTPException(403, "Access to workspace denied")
    else:
        default_ws = get_user_default_workspace(user["user_id"])
        if not default_ws:
            raise HTTPException(403, "User has no workspaces")
        workspace_id = str(default_ws["workspace_id"])
        role = default_ws["role"]

    request.state.workspace_id = str(workspace_id)
    request.state.user_id      = str(user["user_id"])
    request.state.user_role    = role
    return {"workspace_id": workspace_id, "role": role, "user_id": user["user_id"]}


# ─── Role enforcement helpers ─────────────────────────────────────────────────
def _require_role(ws: dict, *allowed_roles: str):
    if ws["role"] not in allowed_roles:
        raise HTTPException(403, f"Role '{ws['role']}' is not permitted for this action")


# ─── Proxy core ───────────────────────────────────────────────────────────────
async def proxy_request(
    request: Request,
    target_url: str,
    background_tasks: Optional[BackgroundTasks] = None,
    enforce_workspace: bool = True,
) -> Response:
    client: httpx.AsyncClient = request.app.state.client

    # Rate limit (using client IP)
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip, request.url.path)

    # Build outbound headers — STRIP any client-supplied internal/tenant headers
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in (
            "host",
            "x-workspace-id", "x-user-id", "x-user-role", "x-platform-role", "x-staff-role",
            "x-internal-token", "x-api-key", "x-request-id",
        )
    }

    # Inject gateway-controlled headers
    request_id = str(uuid.uuid4())
    headers["X-Request-ID"]    = request_id
    headers["X-API-Key"]       = INTERNAL_TOKEN   # internal trust token
    request.state.request_id   = request_id

    if enforce_workspace:
        headers["X-Workspace-ID"] = request.state.workspace_id
        headers["X-User-ID"]      = request.state.user_id
        headers["X-User-Role"]    = request.state.user_role

    body = await request.body()
    logger.info("[%s] → %s %s (ws=%s)",
                request_id, request.method, target_url,
                getattr(request.state, "workspace_id", "-"))

    try:
        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            params=request.query_params,
        )
    except httpx.RequestError as exc:
        logger.error("[%s] Proxy error → %s: %s", request_id, target_url, exc)
        raise HTTPException(502, "Bad Gateway")

    # Audit log for successful mutating actions
    if (
        enforce_workspace
        and background_tasks
        and request.method in ("POST", "PUT", "DELETE", "PATCH")
        and response.status_code < 400
    ):
        background_tasks.add_task(
            log_audit_event,
            request.state.workspace_id,
            request.state.user_id,
            f"{request.method} {request.url.path}",
            "API_CALL",
            target_url,
            client_ip,
        )

    logger.info("[%s] ← %d from %s", request_id, response.status_code, target_url)

    # Forward response (strip unsafe response headers)
    safe_headers = {
        k: v for k, v in response.headers.items()
        if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")
    }
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=safe_headers,
    )


# ─── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway", "version": "2.0.0"}


# ─── 1. Auth Routes (no workspace auth) ──────────────────────────────────────
@app.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_auth(request: Request, path: str):
    target = f"{AUTH_SERVICE_URL}/auth/{path}"
    return await proxy_request(request, target, enforce_workspace=False)


# ─── 2. Upload / Document Routes ─────────────────────────────────────────────
@app.api_route("/documents", methods=["GET"])
@app.api_route("/documents/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
@app.api_route("/upload", methods=["POST"])
async def proxy_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    path: str = "",
    ws: dict = Depends(require_workspace_access),
):
    actual_path = (
        f"/documents/{path}" if request.url.path.startswith("/documents") else "/upload"
    )

    # Viewers cannot upload or delete
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        _require_role(ws, "owner", "admin", "member")

    # Billing limit check before hitting upstream
    if request.method == "POST" and actual_path == "/upload":
        check_workspace_plan_limits(ws["workspace_id"], "upload_document")

    # Body size check for uploads
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large. Maximum allowed: {MAX_UPLOAD_BYTES // (1024*1024)} MB")

    target = f"{UPLOAD_SERVICE_URL}{actual_path}"
    return await proxy_request(request, target, background_tasks)


# ─── 3. Query Routes ─────────────────────────────────────────────────────────
@app.api_route("/query", methods=["POST"])
@app.api_route("/query/with-file", methods=["POST"])
@app.api_route("/history", methods=["GET", "DELETE"])
@app.api_route("/history/{path:path}", methods=["GET", "DELETE"])
async def proxy_query(
    request: Request,
    background_tasks: BackgroundTasks,
    path: str = "",
    ws: dict = Depends(require_workspace_access),
):
    # Billing limit check before hitting upstream
    if request.method == "POST" and request.url.path in ("/query", "/query/with-file"):
        check_workspace_plan_limits(ws["workspace_id"], "query")

    target = f"{QUERY_SERVICE_URL}{request.url.path}"
    return await proxy_request(request, target, background_tasks)


# ─── 4. Telemetry / Dashboard Routes ─────────────────────────────────────────
@app.api_route("/dashboard/{path:path}", methods=["GET"])
@app.api_route("/metrics", methods=["GET"])
@app.api_route("/telemetry/{path:path}", methods=["GET"])
@app.api_route("/notifications", methods=["GET"])
@app.api_route("/notifications/{path:path}", methods=["GET", "PUT", "POST", "DELETE"])
async def proxy_telemetry(
    request: Request,
    background_tasks: BackgroundTasks,
    path: str = "",
    ws: dict = Depends(require_workspace_access),
):
    upstream_path = request.url.path
    if upstream_path.startswith("/telemetry/"):
        upstream_path = upstream_path[len("/telemetry"):]
    target = f"{TELEMETRY_SERVICE_URL}{upstream_path}"
    return await proxy_request(request, target, background_tasks)


# ─── 5. Drift Detector Routes ─────────────────────────────────────────────────
@app.api_route("/run-detection", methods=["POST"])
@app.api_route("/run-detection/{path:path}", methods=["POST"])
@app.api_route("/detect", methods=["POST"])
@app.api_route("/drift/status", methods=["GET"])
@app.api_route("/drift/history", methods=["GET"])
@app.api_route("/drift/detectors", methods=["GET"])
async def proxy_drift(
    request: Request,
    background_tasks: BackgroundTasks,
    path: str = "",
    ws: dict = Depends(require_workspace_access),
):
    # Map frontend-friendly /drift/* paths to drift detector service paths
    upstream_path = request.url.path
    if upstream_path.startswith("/drift/"):
        upstream_path = upstream_path[len("/drift"):]  # /drift/status -> /status
    target = f"{DRIFT_DETECTOR_URL}{upstream_path}"
    return await proxy_request(request, target, background_tasks)

# ─── 6. Controller Routes ─────────────────────────────────────────────────────
@app.api_route("/controller/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_controller(
    request: Request,
    background_tasks: BackgroundTasks,
    path: str = "",
    ws: dict = Depends(require_workspace_access),
):
    upstream_path = request.url.path[len("/controller"):]
    target = f"{CONTROLLER_URL}{upstream_path}"
    return await proxy_request(request, target, background_tasks)

# ─── 7. Evaluation Routes ─────────────────────────────────────────────────────
@app.api_route("/evaluation/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_evaluation(
    request: Request,
    background_tasks: BackgroundTasks,
    path: str = "",
    ws: dict = Depends(require_workspace_access),
):
    upstream_path = request.url.path[len("/evaluation"):]
    target = f"{EVALUATION_URL}{upstream_path}"
    return await proxy_request(request, target, background_tasks)

# ─── 8. Billing Routes ────────────────────────────────────────────────────────
@app.post("/billing/checkout")
async def create_checkout(
    request: Request,
    ws: dict = Depends(require_workspace_access)
):
    """Create a Stripe checkout session for the workspace."""
    body = await request.json()
    plan_name = body.get("plan")
    
    if not plan_name:
        raise HTTPException(400, "Missing plan name")
        
    from billing import create_stripe_checkout
    url = await create_stripe_checkout(ws["workspace_id"], plan_name)
    if not url:
        raise HTTPException(501, "Billing is not configured on this server")
        
    return {"url": url}
# ─── 6. Stripe Webhook (no JWT required — Stripe calls this directly) ─────────
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Stripe billing webhook placeholder. Validates Stripe signature before processing."""
    stripe_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not stripe_secret:
        logger.warning("STRIPE_WEBHOOK_SECRET not configured — webhook ignored")
        return {"status": "stripe_not_configured"}

    # Signature verification placeholder
    stripe_sig = request.headers.get("stripe-signature", "")
    payload    = await request.body()

    try:
        import stripe  # type: ignore
        event = stripe.Webhook.construct_event(payload, stripe_sig, stripe_secret)
        logger.info("Stripe event received: %s", event["type"])
        # Dispatch to billing handler (see billing.py)
        from billing import handle_stripe_event
        await handle_stripe_event(event)
        return {"status": "ok"}
    except Exception as exc:
        logger.error("Stripe webhook error: %s", exc)
        raise HTTPException(400, "Webhook error")


# ─── 9. Staff Operations Routes ──────────────────────────────────────────────
@app.api_route("/staff/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_staff(request: Request, path: str = ""):
    raise HTTPException(404, "Not Found")


# ─── 10. Super Admin Routes ───────────────────────────────────────────────────
@app.api_route("/super-admin/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_super_admin(request: Request, path: str = ""):
    raise HTTPException(404, "Not Found")


# ─── 10. Workspace Admin Routes ──────────────────────────────────────────────
@app.api_route("/workspaces/{workspace_id}/admin/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_workspace_admin(request: Request, workspace_id: str, path: str = ""):
    raise HTTPException(404, "Not Found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
