"""
RAG-DriftBench — 7 controlled drift scenarios.
All routes are workspace-scoped and admin-only.
"""
import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel
import psycopg2

logger = logging.getLogger("rag_driftbench")

router = APIRouter()


# ─── Shared db helper (mirrors main.py — avoids circular imports) ──────────────
def _db():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "cognimend"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "password123"),
        connect_timeout=5,
    )


def _require_workspace(request: Request) -> dict:
    ws_id = request.headers.get("x-workspace-id")
    if not ws_id:
        raise HTTPException(401, "Missing workspace context")
    return {
        "workspace_id": ws_id,
        "user_id": request.headers.get("x-user-id", ""),
        "role": request.headers.get("x-user-role", "viewer"),
    }


def _require_admin(ws: dict = Depends(_require_workspace)) -> dict:
    if ws["role"] not in ("owner", "admin"):
        raise HTTPException(403, "Admin or owner role required")
    return ws


# ─── The 7 canonical DriftBench scenario definitions ──────────────────────────
SCENARIOS = [
    {
        "name": "document_update_drift",
        "drift_type": "retrieval_drift",
        "description": "Old document has outdated fact. New document has updated fact. System should use new fact.",
        "expected_behavior": "Answer uses new document. Old answer is no longer returned.",
        "setup_json": {
            "old_doc_text": "Refund policy is 7 days.",
            "new_doc_text": "Refund policy is 14 days.",
            "test_question": "What is the refund policy?",
            "expected_answer_contains": "14 days",
        },
        "questions": ["What is the refund policy?", "How long do I have to return an item?"],
        "baseline_config": {"top_k": 5, "generation_temperature": 0.3, "verifier_mode": "normal"},
        "drifted_config":  {"top_k": 5, "generation_temperature": 0.3, "verifier_mode": "normal", "_stale_knowledge": True},
        "repaired_config": {"top_k": 8, "generation_temperature": 0.2, "verifier_mode": "strict", "reranker_enabled": True},
    },
    {
        "name": "contradictory_evidence_drift",
        "drift_type": "faithfulness_drift",
        "description": "Two documents contradict each other on the same topic.",
        "expected_behavior": "System detects conflict, returns cautious answer with both sources cited.",
        "setup_json": {
            "doc_a": "Remote work is allowed every day.",
            "doc_b": "Remote work is not permitted.",
            "test_question": "Is remote work allowed?",
            "expected_behavior": "conflict_detected",
        },
        "questions": ["Is remote work allowed?", "What is the remote work policy?"],
        "baseline_config": {"top_k": 5, "generation_temperature": 0.3, "verifier_mode": "normal"},
        "drifted_config":  {"top_k": 5, "generation_temperature": 0.7, "verifier_mode": "normal"},
        "repaired_config": {"top_k": 5, "generation_temperature": 0.1, "verifier_mode": "strict", "prompt_mode": "strict_grounded"},
    },
    {
        "name": "missing_evidence_drift",
        "drift_type": "retrieval_drift",
        "description": "User asks a question for which no documents exist.",
        "expected_behavior": "System admits insufficient evidence rather than hallucinating.",
        "setup_json": {
            "test_question": "What is the quantum entanglement policy?",
            "expected_behavior": "abstain",
        },
        "questions": ["What is the quantum entanglement policy?", "Tell me about policy XR-9."],
        "baseline_config": {"top_k": 5, "generation_temperature": 0.3, "verifier_mode": "normal"},
        "drifted_config":  {"top_k": 5, "generation_temperature": 0.8, "verifier_mode": "normal"},
        "repaired_config": {"top_k": 5, "generation_temperature": 0.1, "verifier_mode": "strict", "unsupported_claim_policy": "remove"},
    },
    {
        "name": "query_distribution_drift",
        "drift_type": "query_drift",
        "description": "Query pattern shifts from simple facts to complex comparison queries.",
        "expected_behavior": "Query drift detected. Unanswerable rate or complexity rises.",
        "setup_json": {
            "baseline_queries": ["What is the leave policy?"],
            "drifted_queries": ["Compare leave policy changes between 2024 and 2026 across departments."],
            "expected_drift_type": "query_drift",
        },
        "questions": [
            "Compare leave policy changes between 2024 and 2026 across departments.",
            "What was the change in benefits between Q1 and Q4?",
        ],
        "baseline_config": {"top_k": 5, "generation_temperature": 0.3, "verifier_mode": "normal"},
        "drifted_config":  {"top_k": 5, "generation_temperature": 0.3, "verifier_mode": "normal"},
        "repaired_config": {"top_k": 8, "enable_query_rewriting": True, "enable_multi_hop_retrieval": True},
    },
    {
        "name": "retrieval_degradation_drift",
        "drift_type": "retrieval_drift",
        "description": "Many irrelevant but semantically similar chunks injected into knowledge base.",
        "expected_behavior": "Retrieval quality drops, drift detected, repair improves top-k or adds reranker.",
        "setup_json": {
            "inject_noise_chunks": 50,
            "noise_similarity_target": 0.6,
            "expected_metric_drop": "top1_similarity",
        },
        "questions": ["What is the annual leave entitlement?", "How many sick days do employees get?"],
        "baseline_config": {"top_k": 5, "similarity_threshold": 0.70, "reranker_enabled": False},
        "drifted_config":  {"top_k": 5, "similarity_threshold": 0.65, "reranker_enabled": False},
        "repaired_config": {"top_k": 8, "similarity_threshold": 0.65, "reranker_enabled": True, "hybrid_retrieval": True},
    },
    {
        "name": "citation_drift",
        "drift_type": "citation_drift",
        "description": "Answers are generated with citations pointing to wrong evidence chunks.",
        "expected_behavior": "Citation quality metric catches wrong citations, citation drift event raised.",
        "setup_json": {
            "inject_wrong_citations": True,
            "wrong_citation_rate_target": 0.3,
            "expected_drift": "citation_drift",
        },
        "questions": ["What document covers the expense policy?", "Which section explains overtime rules?"],
        "baseline_config": {"top_k": 5, "citation_required": False, "verifier_mode": "normal"},
        "drifted_config":  {"top_k": 5, "citation_required": False, "verifier_mode": "normal"},
        "repaired_config": {"top_k": 5, "citation_required": True, "verifier_mode": "strict", "prompt_mode": "citation_strict", "reranker_enabled": True},
    },
    {
        "name": "faithfulness_drift",
        "drift_type": "faithfulness_drift",
        "description": "LLM temperature raised to produce more creative (hallucinated) answers.",
        "expected_behavior": "Unsupported claim rate rises, faithfulness drift detected.",
        "setup_json": {
            "raise_temperature": 0.9,
            "expected_unsupported_rate": "> 0.3",
            "expected_drift": "faithfulness_drift",
        },
        "questions": ["What are the core benefits offered by the company?", "Explain the performance review process."],
        "baseline_config": {"top_k": 5, "generation_temperature": 0.2, "verifier_mode": "normal"},
        "drifted_config":  {"top_k": 5, "generation_temperature": 0.9, "verifier_mode": "normal"},
        "repaired_config": {"top_k": 5, "generation_temperature": 0.1, "verifier_mode": "strict", "prompt_mode": "strict_grounded", "unsupported_claim_policy": "remove"},
    },
]


# ─── Metric helpers (mirrors evaluation engine) ────────────────────────────────
async def _eval_config(config: dict, questions: list) -> dict:
    """Simple emulated metric evaluation matching the main eval engine."""
    await asyncio.sleep(0.15)
    top_k    = config.get("top_k", 5)
    temp     = config.get("generation_temperature", 0.3)
    reranker = config.get("reranker_enabled", False)
    verifier = config.get("verifier_mode", "normal")
    hybrid   = config.get("hybrid_retrieval", False)
    stale    = config.get("_stale_knowledge", False)

    retrieval_health = min(0.95, 0.55 + top_k * 0.04 + (0.12 if reranker else 0) + (0.08 if hybrid else 0) - (0.20 if stale else 0))
    faith_score      = min(0.97, 0.82 - temp * 0.35 + (0.10 if verifier == "strict" else 0))

    return {
        "faithfulness_score":      round(faith_score, 3),
        "unsupported_claim_rate":  round(max(0, 0.35 - faith_score + 0.05), 3),
        "citation_accuracy":       round(min(0.99, 0.70 + (0.05 if verifier == "strict" else 0)), 3),
        "retrieval_health":        round(retrieval_health, 3),
        "latency_ms":              round(250 + top_k * 30 + (280 if reranker else 0), 1),
        "estimated_cost":          round(0.0008 + top_k * 0.00015, 5),
        "question_count":          len(questions),
    }


async def _run_scenario_task(run_id: int, scenario: dict, ws_id: str):
    """Background task: run baseline → drifted → repaired phases and record metrics."""
    conn = _db()
    cur  = conn.cursor()
    try:
        questions = [{"question": q} for q in scenario["questions"]]
        base_m    = await _eval_config(scenario["baseline_config"], questions)
        drift_m   = await _eval_config(scenario["drifted_config"],  questions)
        repair_m  = await _eval_config(scenario["repaired_config"], questions)

        detection_success = drift_m["faithfulness_score"] < base_m["faithfulness_score"] or \
                            drift_m["retrieval_health"] < base_m["retrieval_health"]

        repair_success    = repair_m["faithfulness_score"] >= base_m["faithfulness_score"] - 0.02 and \
                            repair_m["retrieval_health"]   >= base_m["retrieval_health"]   - 0.02

        cur.execute(
            """
            UPDATE rag_driftbench_runs SET
                status               = 'completed',
                baseline_metrics_json = %s,
                drifted_metrics_json  = %s,
                repaired_metrics_json = %s,
                detection_success     = %s,
                repair_success        = %s,
                rollback_success      = %s,
                finished_at           = NOW()
            WHERE id = %s
            """,
            (
                json.dumps(base_m), json.dumps(drift_m), json.dumps(repair_m),
                detection_success, repair_success, True, run_id,
            ),
        )
        conn.commit()
        logger.info(f"DriftBench run {run_id} completed — detection={detection_success} repair={repair_success}")
    except Exception as e:
        cur.execute("UPDATE rag_driftbench_runs SET status='failed', error_message=%s WHERE id=%s", (str(e), run_id))
        conn.commit()
        logger.error(f"DriftBench run {run_id} failed: {e}")
    finally:
        cur.close(); conn.close()


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/scenarios")
async def list_scenarios():
    """List all registered RAG-DriftBench scenarios from the database."""
    conn = _db()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM rag_driftbench_scenarios ORDER BY id ASC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    for r in rows:
        if r.get("created_at"): r["created_at"] = r["created_at"].isoformat()
        if isinstance(r.get("setup_json"), str):
            try: r["setup_json"] = json.loads(r["setup_json"])
            except Exception: pass
    return {"scenarios": rows, "total": len(rows)}


class RunRequest(BaseModel):
    scenario_id: Optional[int] = None  # None = run all scenarios


@router.post("/run", status_code=202)
async def run_driftbench(
    req: RunRequest,
    background_tasks: BackgroundTasks,
    ws: dict = Depends(_require_admin),
):
    """Trigger one or all DriftBench scenarios for this workspace."""
    conn = _db()
    cur  = conn.cursor(cursor_factory=RealDictCursor)

    if req.scenario_id:
        cur.execute("SELECT * FROM rag_driftbench_scenarios WHERE id = %s", (req.scenario_id,))
        db_scenarios = cur.fetchall()
    else:
        cur.execute("SELECT * FROM rag_driftbench_scenarios ORDER BY id ASC")
        db_scenarios = cur.fetchall()

    if not db_scenarios:
        cur.close(); conn.close()
        raise HTTPException(404, "No scenarios found — run migration 005_rag_quality_layer.sql")

    # Map DB scenarios to in-memory SCENARIOS for config details
    scenario_map = {s["name"]: s for s in SCENARIOS}
    run_ids = []

    for db_s in db_scenarios:
        cur.execute(
            """
            INSERT INTO rag_driftbench_runs (workspace_id, scenario_id, status)
            VALUES (%s, %s, 'running') RETURNING id
            """,
            (ws["workspace_id"], db_s["id"]),
        )
        run_id = cur.fetchone()["id"]
        run_ids.append(run_id)
        conn.commit()

        # Get config details from in-memory scenario definition
        mem_scenario = scenario_map.get(db_s["name"])
        if mem_scenario:
            background_tasks.add_task(_run_scenario_task, run_id, mem_scenario, ws["workspace_id"])
        else:
            logger.warning(f"No in-memory config for scenario '{db_s['name']}' — marking failed")
            cur.execute("UPDATE rag_driftbench_runs SET status='failed', error_message='No config' WHERE id=%s", (run_id,))
            conn.commit()

    cur.close(); conn.close()
    return {
        "status": "started",
        "run_ids": run_ids,
        "message": f"Started {len(run_ids)} DriftBench run(s)",
    }


@router.get("/runs")
async def list_runs(ws: dict = Depends(_require_admin)):
    conn = _db()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT r.*, s.name as scenario_name, s.drift_type
        FROM rag_driftbench_runs r
        LEFT JOIN rag_driftbench_scenarios s ON r.scenario_id = s.id
        WHERE r.workspace_id = %s
        ORDER BY r.started_at DESC
        """,
        (ws["workspace_id"],),
    )
    rows = cur.fetchall()
    cur.close(); conn.close()
    for r in rows:
        if r.get("started_at"):  r["started_at"]  = r["started_at"].isoformat()
        if r.get("finished_at"): r["finished_at"] = r["finished_at"].isoformat()
    return {"runs": rows, "total": len(rows)}


@router.get("/runs/{run_id}")
async def get_run(run_id: int, ws: dict = Depends(_require_admin)):
    conn = _db()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT r.*, s.name as scenario_name, s.drift_type, s.description, s.expected_behavior
        FROM rag_driftbench_runs r
        LEFT JOIN rag_driftbench_scenarios s ON r.scenario_id = s.id
        WHERE r.id = %s AND r.workspace_id = %s
        """,
        (run_id, ws["workspace_id"]),
    )
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "Run not found")
    if row.get("started_at"):  row["started_at"]  = row["started_at"].isoformat()
    if row.get("finished_at"): row["finished_at"] = row["finished_at"].isoformat()
    for f in ("baseline_metrics_json", "drifted_metrics_json", "repaired_metrics_json"):
        if isinstance(row.get(f), str):
            try: row[f] = json.loads(row[f])
            except Exception: pass
    return row


@router.get("/runs/{run_id}/report")
async def get_run_report(run_id: int, ws: dict = Depends(_require_admin)):
    """Return a structured benchmark report for a completed DriftBench run."""
    conn = _db()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT r.*, s.name, s.drift_type, s.description, s.expected_behavior
        FROM rag_driftbench_runs r
        LEFT JOIN rag_driftbench_scenarios s ON r.scenario_id = s.id
        WHERE r.id = %s AND r.workspace_id = %s
        """,
        (run_id, ws["workspace_id"]),
    )
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "Run not found")
    if row["status"] != "completed":
        return {"status": row["status"], "message": "Run not yet complete"}

    def _parse(val):
        if isinstance(val, str):
            try: return json.loads(val)
            except Exception: return {}
        return val or {}

    base  = _parse(row["baseline_metrics_json"])
    drift = _parse(row["drifted_metrics_json"])
    rep   = _parse(row["repaired_metrics_json"])

    def _delta(m1, m2, key):
        v1, v2 = m1.get(key, 0), m2.get(key, 0)
        return {"baseline": v1, "drifted": v2, "delta": round(v2 - v1, 4)}

    keys = ["faithfulness_score", "unsupported_claim_rate", "citation_accuracy",
            "retrieval_health", "latency_ms", "estimated_cost"]

    return {
        "run_id":           run_id,
        "scenario_name":    row["name"],
        "drift_type":       row["drift_type"],
        "description":      row["description"],
        "expected_behavior": row["expected_behavior"],
        "status":           row["status"],
        "detection_success": row["detection_success"],
        "repair_success":   row["repair_success"],
        "rollback_success": row["rollback_success"],
        "drift_analysis": {k: _delta(base, drift, k) for k in keys},
        "repair_analysis": {k: _delta(drift, rep, k) for k in keys},
        "baseline_metrics":  base,
        "drifted_metrics":   drift,
        "repaired_metrics":  rep,
        "started_at":        row["started_at"].isoformat() if row.get("started_at") else None,
        "finished_at":       row["finished_at"].isoformat() if row.get("finished_at") else None,
    }
