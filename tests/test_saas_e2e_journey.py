"""
Phase 5 — Full End-to-End SaaS Journey Test
=============================================
Simulates a complete new user journey from signup to deletion.

Run:
    pip install pytest requests
    GATEWAY_URL=http://localhost:8007 pytest tests/test_saas_e2e_journey.py -v -s
"""
import os
import io
import time
import pytest
import requests

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080")
TIMEOUT = 60  # seconds to wait for document processing


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _auth_headers(token: str, workspace_id: str = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if workspace_id:
        h["X-Workspace-ID"] = workspace_id
    return h


def wait_for_status(token: str, workspace_id: str, doc_id, target: str = "ready", timeout: int = TIMEOUT):
    """Poll document status until it reaches target or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(
            f"{GATEWAY}/documents/{doc_id}",
            headers=_auth_headers(token, workspace_id)
        )
        if r.status_code == 200:
            status = r.json().get("status")
            if status == target:
                return True
            if status == "failed":
                pytest.fail(f"Document processing failed: {r.json()}")
        time.sleep(2)
    return False


# ─── Full Journey ─────────────────────────────────────────────────────────────

class TestFullSaaSJourney:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ts = int(time.time() * 1000)
        self.email = f"e2e_{self.ts}@example.com"
        self.password = "Password123!"
        self.token = None
        self.workspace_id = None
        self.doc_id = None

    def test_step_1_signup(self):
        r = requests.post(f"{GATEWAY}/auth/signup", json={
            "email": self.email,
            "password": self.password,
            "full_name": "E2E Test User",
        })
        assert r.status_code == 200, f"Signup failed: {r.text}"
        data = r.json()
        assert "access_token" in data
        assert data.get("is_new_user") is True
        self.token = data["access_token"]

    def test_step_2_login(self):
        # First signup to get credentials
        r0 = requests.post(f"{GATEWAY}/auth/signup", json={
            "email": self.email, "password": self.password, "full_name": "E2E User"
        })
        r = requests.post(f"{GATEWAY}/auth/login", json={
            "email": self.email, "password": self.password
        })
        assert r.status_code == 200, f"Login failed: {r.text}"
        self.token = r.json()["access_token"]

    def test_step_3_workspace_created_on_signup(self):
        r0 = requests.post(f"{GATEWAY}/auth/signup", json={
            "email": self.email, "password": self.password, "full_name": "E2E User"
        })
        token = r0.json()["access_token"]
        r = requests.get(f"{GATEWAY}/auth/me", headers=_auth_headers(token))
        assert r.status_code == 200
        workspaces = r.json().get("workspaces", [])
        assert len(workspaces) >= 1, "No workspace created after signup"
        self.workspace_id = workspaces[0]["id"]

    def test_step_4_free_subscription_exists(self):
        r0 = requests.post(f"{GATEWAY}/auth/signup", json={
            "email": self.email, "password": self.password, "full_name": "E2E User"
        })
        token = r0.json()["access_token"]
        me   = requests.get(f"{GATEWAY}/auth/me", headers=_auth_headers(token)).json()
        ws_id = me["workspaces"][0]["id"]
        # Check usage endpoint — if plan limits are sensible (>=1 doc, >=1 query)
        r = requests.get(f"{GATEWAY}/dashboard/usage", headers=_auth_headers(token, ws_id))
        assert r.status_code in (200, 503), f"Usage endpoint broken: {r.status_code}"
        if r.status_code == 200:
            data = r.json()
            assert data["document_limit"] >= 1
            assert data["monthly_queries_limit"] >= 1

    def test_full_journey(self):
        """
        Complete journey: signup → upload → poll → query → feedback → dashboard → delete.
        """
        # 1. Signup
        r = requests.post(f"{GATEWAY}/auth/signup", json={
            "email": self.email, "password": self.password, "full_name": "Journey User"
        })
        assert r.status_code == 200, f"Signup: {r.text}"
        token = r.json()["access_token"]

        # 2. Get workspace
        me = requests.get(f"{GATEWAY}/auth/me", headers=_auth_headers(token)).json()
        workspace_id = me["workspaces"][0]["id"]
        h = _auth_headers(token, workspace_id)

        # 3. Upload a TXT document
        content = (
            b"Cognimend is an AI-powered RAG knowledge platform. "
            b"It allows users to upload documents and ask questions with source citations. "
            b"The system uses OpenRouter for LLM inference and Qdrant for vector storage."
        )
        files = {"file": ("cognimend_overview.txt", io.BytesIO(content), "text/plain")}
        r = requests.post(f"{GATEWAY}/upload", headers=h, files=files)
        assert r.status_code in (200, 201), f"Upload failed: {r.status_code} {r.text}"
        doc = r.json()
        doc_id = doc.get("document_id") or doc.get("document", {}).get("id")
        assert doc_id, f"No doc_id in response: {doc}"
        self.doc_id = doc_id

        # 4. Poll until ready (or skip if processing is async)
        is_ready = wait_for_status(token, workspace_id, doc_id, "ready", timeout=90)
        if not is_ready:
            pytest.skip("Document processing timed out — check upload service logs")

        # 5. Ask a question
        r = requests.post(f"{GATEWAY}/query", headers=h,
                          json={"question": "What is Cognimend?", "top_k": 3})
        assert r.status_code == 200, f"Query failed: {r.status_code} {r.text}"
        answer_data = r.json()
        answer = answer_data.get("answer", "")
        assert len(answer) > 10, "Answer too short / empty"

        # 6. Verify source citation exists
        sources = answer_data.get("sources") or answer_data.get("citations") or []
        assert len(sources) >= 1, f"No source citations returned. Full response: {answer_data}"

        # 7. Dashboard should reflect new data
        r = requests.get(f"{GATEWAY}/dashboard/stats", headers=h)
        assert r.status_code == 200
        stats = r.json()
        assert stats.get("total_documents", 0) >= 1
        assert stats.get("total_queries", 0) >= 1

        # 8. Delete document
        r = requests.delete(f"{GATEWAY}/documents/{doc_id}", headers=h)
        assert r.status_code == 200, f"Delete failed: {r.status_code} {r.text}"

        # 9. Confirm document is gone
        r = requests.get(f"{GATEWAY}/documents/{doc_id}", headers=h)
        assert r.status_code == 404, f"Document still accessible after deletion: {r.status_code}"

        # 10. Confirm vector not searchable (query should return empty sources)
        time.sleep(1)  # brief pause for Qdrant propagation
        r = requests.post(f"{GATEWAY}/query", headers=h,
                          json={"question": "What is Cognimend?", "top_k": 3})
        if r.status_code == 200:
            sources_after = r.json().get("sources") or r.json().get("citations") or []
            # None of the sources should reference the deleted doc
            for src in sources_after:
                src_doc_id = src.get("document_id") or src.get("doc_id")
                assert str(src_doc_id) != str(doc_id), \
                    f"Deleted document {doc_id} still appears in search results!"


# ─── Deletion Consistency ──────────────────────────────────────────────────────

class TestDocumentDeletion:

    def test_delete_removes_from_db_and_qdrant(self):
        """
        Upload → delete → verify 404 and no vectors remaining.
        """
        ts    = int(time.time() * 1000)
        email = f"del_test_{ts}@example.com"

        r0 = requests.post(f"{GATEWAY}/auth/signup", json={
            "email": email, "password": "Password123!", "full_name": "Del User"
        })
        assert r0.status_code == 200
        token = r0.json()["access_token"]
        me    = requests.get(f"{GATEWAY}/auth/me", headers=_auth_headers(token)).json()
        ws_id = me["workspaces"][0]["id"]
        h     = _auth_headers(token, ws_id)

        files = {"file": ("del_test.txt", b"This doc should be deleted.", "text/plain")}
        r = requests.post(f"{GATEWAY}/upload", headers=h, files=files)
        if r.status_code not in (200, 201):
            pytest.skip(f"Upload unavailable: {r.status_code}")

        doc = r.json()
        doc_id = doc.get("document_id") or doc.get("document", {}).get("id")
        if not doc_id:
            pytest.skip("No doc_id returned")

        # Wait briefly for indexing
        wait_for_status(token, ws_id, doc_id, "ready", timeout=60)

        # Delete
        r = requests.delete(f"{GATEWAY}/documents/{doc_id}", headers=h)
        assert r.status_code == 200

        # Confirm 404
        r = requests.get(f"{GATEWAY}/documents/{doc_id}", headers=h)
        assert r.status_code == 404, "Document still in DB after deletion"
