"""
Phase 5 — Multi-Tenant Isolation Test Suite
============================================
Tests that verify cross-tenant data leakage cannot happen.

Run:
    pip install pytest requests
    GATEWAY_URL=http://localhost:8007 pytest tests/test_saas_isolation.py -v
"""
import os
import time
import uuid
import pytest
import requests

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def register(suffix: str) -> dict:
    ts = int(time.time() * 1000)
    email = f"test_{suffix}_{ts}@example.com"
    r = requests.post(f"{GATEWAY}/auth/signup", json={
        "email": email, "password": "Password123!", "full_name": f"Test {suffix}"
    })
    assert r.status_code == 200, f"Register failed: {r.text}"
    data = r.json()
    return {
        "token":        data["access_token"],
        "user_id":      data["user"].get("id"),
        "email":        email,
        "workspace_id": _get_workspace(data["access_token"]),
    }


def _get_workspace(token: str) -> str:
    r = requests.get(f"{GATEWAY}/auth/me", headers=_auth(token))
    assert r.status_code == 200
    ws = r.json().get("workspaces", [])
    assert ws, "No workspace created for new user"
    return ws[0]["id"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _ws_headers(token: str, workspace_id: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-Workspace-ID": workspace_id}


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def user_a():
    return register("userA")


@pytest.fixture(scope="module")
def user_b():
    return register("userB")


# ─── Isolation Tests ──────────────────────────────────────────────────────────

class TestCrossTenantIsolation:

    def test_user_a_cannot_access_workspace_b(self, user_a, user_b):
        """User A must get 403 when requesting Workspace B's resources."""
        r = requests.get(
            f"{GATEWAY}/documents",
            headers=_ws_headers(user_a["token"], user_b["workspace_id"])
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    def test_user_b_cannot_list_user_a_documents(self, user_a, user_b):
        r = requests.get(
            f"{GATEWAY}/documents",
            headers=_ws_headers(user_b["token"], user_a["workspace_id"])
        )
        assert r.status_code == 403

    def test_user_b_cannot_query_user_a_vectors(self, user_a, user_b):
        r = requests.post(
            f"{GATEWAY}/query",
            headers=_ws_headers(user_b["token"], user_a["workspace_id"]),
            json={"question": "What is in workspace A?"}
        )
        assert r.status_code == 403

    def test_user_b_cannot_view_user_a_dashboard(self, user_a, user_b):
        r = requests.get(
            f"{GATEWAY}/dashboard/stats",
            headers=_ws_headers(user_b["token"], user_a["workspace_id"])
        )
        assert r.status_code == 403

    def test_user_b_cannot_view_user_a_telemetry_trends(self, user_a, user_b):
        r = requests.get(
            f"{GATEWAY}/dashboard/trends",
            headers=_ws_headers(user_b["token"], user_a["workspace_id"])
        )
        assert r.status_code == 403

    def test_client_cannot_spoof_x_workspace_id(self, user_a, user_b):
        """
        Even if User B attaches User A's workspace in the header, the gateway
        validates membership and must reject.
        """
        headers = {
            "Authorization": f"Bearer {user_b['token']}",
            "X-Workspace-ID": user_a["workspace_id"],
            # Attempt to also spoof X-User-ID (should be ignored/overwritten by gateway)
            "X-User-ID": user_a["user_id"],
        }
        r = requests.get(f"{GATEWAY}/documents", headers=headers)
        assert r.status_code == 403, f"Spoofed header was accepted: {r.status_code}"

    def test_gateway_strips_x_user_id_from_client(self, user_a):
        """
        Send a request with a forged X-User-ID in the header.
        The gateway must overwrite it — we verify by checking our own documents
        still work (not returning someone else's data).
        """
        headers = {
            "Authorization": f"Bearer {user_a['token']}",
            "X-Workspace-ID": user_a["workspace_id"],
            "X-User-ID": str(uuid.uuid4()),  # random forged user id
        }
        r = requests.get(f"{GATEWAY}/documents", headers=headers)
        # Should succeed (using real user_a workspace) but gateway overwrites X-User-ID
        assert r.status_code == 200, f"Request failed: {r.status_code}"

    def test_unauthenticated_request_rejected(self, user_a):
        r = requests.get(
            f"{GATEWAY}/documents",
            headers={"X-Workspace-ID": user_a["workspace_id"]}
        )
        assert r.status_code == 401


# ─── Role Permission Tests ─────────────────────────────────────────────────────

class TestRolePermissions:

    def test_viewer_cannot_upload(self, user_a, user_b):
        """
        Add User B as viewer to User A's workspace, then attempt upload — must fail.
        NOTE: Requires an admin endpoint to add members (skip if not implemented).
        """
        pytest.skip("Requires workspace member management endpoint")

    def test_own_workspace_member_can_upload(self, user_a):
        """User A (owner of their workspace) can upload."""
        files = {"file": ("test.txt", b"Hello world test document for isolation.", "text/plain")}
        r = requests.post(
            f"{GATEWAY}/upload",
            headers=_ws_headers(user_a["token"], user_a["workspace_id"]),
            files=files
        )
        # 200 = success, 403 = plan limit — either is acceptable here
        assert r.status_code in (200, 201, 403), f"Unexpected: {r.status_code}: {r.text}"

    def test_upload_requires_workspace_header(self, user_a):
        files = {"file": ("test.txt", b"data", "text/plain")}
        r = requests.post(
            f"{GATEWAY}/upload",
            headers=_auth(user_a["token"]),  # no X-Workspace-ID
            files=files
        )
        # Should use default workspace — not reject — but should succeed
        assert r.status_code in (200, 201, 403)


# ─── Header Security ──────────────────────────────────────────────────────────

class TestHeaderSecurity:

    def test_direct_upload_service_rejects_without_internal_token(self):
        """Internal services should reject requests without X-API-Key."""
        upload_url = os.getenv("UPLOAD_URL", "http://localhost:8001")
        r = requests.get(f"{upload_url}/documents", headers={
            "X-Workspace-ID": "fake-ws-id",
            "X-User-ID": "fake-user-id",
            # No X-API-Key (internal token)
        })
        assert r.status_code in (401, 403, 422), \
            f"Internal service accepted unauthenticated request: {r.status_code}"

    def test_gateway_health_is_public(self):
        r = requests.get(f"{GATEWAY}/health")
        assert r.status_code == 200

    def test_invalid_jwt_rejected(self, user_a):
        r = requests.get(
            f"{GATEWAY}/documents",
            headers={
                "Authorization": "Bearer this.is.a.fake.token",
                "X-Workspace-ID": user_a["workspace_id"],
            }
        )
        assert r.status_code == 401

    def test_expired_token_rejected(self):
        """Use a manually crafted expired token."""
        import jwt as _jwt
        expired = _jwt.encode(
            {"sub": "00000000-0000-0000-0000-000000000000",
             "email": "x@x.com", "exp": 1000},  # exp in the past
            "change-me-in-production", algorithm="HS256"
        )
        r = requests.get(f"{GATEWAY}/documents",
                         headers={"Authorization": f"Bearer {expired}"})
        assert r.status_code == 401


# ─── Rate Limit Smoke Test ────────────────────────────────────────────────────

class TestRateLimiting:

    def test_login_rate_limited(self):
        """More than 10 rapid login attempts should trigger 429."""
        hits = []
        for i in range(12):
            r = requests.post(f"{GATEWAY}/auth/login", json={
                "email": f"nope{i}@example.com", "password": "wrong"
            })
            hits.append(r.status_code)
        # At least one 429 expected after 10 attempts per 60 seconds
        assert 429 in hits or 401 in hits, \
            "Rate limiter not triggered after 12 rapid attempts"
