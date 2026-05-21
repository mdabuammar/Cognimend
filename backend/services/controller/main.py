"""
Controller Service
Features:
- Config versioning
- Repair candidate generation based on drift types
- Verify-before-apply evaluation flow
- Config apply and rollback
- Role-based multi-tenancy isolation
- RabbitMQ event publishing
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import asyncio
import json
import logging
from contextlib import asynccontextmanager
import sys
import uuid
import psycopg2

from services.shared.actions import action_registry

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

db_manager = None


def _test_workspace_fallback() -> bool:
    return os.getenv("API_KEY_REQUIRED", "false").lower() != "true"

def get_db():
    if db_manager is not None:
        return db_manager.get_connection()

    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "cognimend"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        connect_timeout=5
    )

def return_db(conn):
    if db_manager is not None:
        db_manager.return_connection(conn)
    else:
        conn.close()

# Message Publisher Mock/Fallback
async def publish_event(event_type: str, payload: dict):
    logger.info(f"🐰 Publishing {event_type}: {payload}")
    # In a real setup, connect to RabbitMQ using pika/aio_pika here
    pass

# Auth Dependency
def require_workspace(request: Request) -> dict:
    ws_id = request.headers.get("x-workspace-id")
    u_id = request.headers.get("x-user-id")
    role = request.headers.get("x-user-role", "viewer")

    if not ws_id and _test_workspace_fallback():
        ws_id = "test-workspace"
        u_id = u_id or "test-user"
        role = role or "admin"
    
    if not ws_id:
        raise HTTPException(401, "Missing workspace context")
    
    return {"workspace_id": ws_id, "user_id": u_id, "role": role}

def require_admin(ws: dict = Depends(require_workspace)) -> dict:
    if ws["role"] not in ("owner", "admin"):
        raise HTTPException(403, "Admin privileges required to modify configuration")
    return ws

# Default Config
DEFAULT_CONFIG = {
    "top_k": 5,
    "similarity_threshold": 0.70,
    "hybrid_retrieval": False,
    "reranker_enabled": False,
    "prompt_mode": "normal",
    "verifier_mode": "normal",
    "unsupported_claim_policy": "caveat",
    "generation_temperature": 0.3,
    "max_latency_increase_percent": 50,
    "max_cost_increase_percent": 100,
    "auto_repair_mode": "manual" # manual | auto_apply_verified
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Controller Service starting...")
    # Initialize background task for drift processing
    asyncio.create_task(monitor_drift_events())
    yield
    logger.info("🛑 Controller Service shutting down...")

app = FastAPI(title="Controller Service", version="2.0.0", lifespan=lifespan)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:8080,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== CONFIGURATION CORE =====

def _get_stable_config(cur, workspace_id: str):
    cur.execute("""
        SELECT id, version_number, config_json, status 
        FROM config_versions 
        WHERE workspace_id = %s AND status IN ('stable', 'active')
        ORDER BY version_number DESC LIMIT 1
    """, (workspace_id,))
    return cur.fetchone()

def _ensure_default_config(cur, workspace_id: str):
    stable = _get_stable_config(cur, workspace_id)
    if not stable:
        cur.execute("""
            INSERT INTO config_versions (workspace_id, version_number, config_json, status, created_reason)
            VALUES (%s, 1, %s, 'active', 'Initial workspace setup')
            RETURNING id, version_number, config_json
        """, (workspace_id, json.dumps(DEFAULT_CONFIG)))
        stable = cur.fetchone()
        asyncio.create_task(publish_event("config.version_created", {
            "workspace_id": workspace_id, "config_version_id": stable['id']
        }))
    return stable

# ===== CANDIDATE GENERATION RULES =====

def generate_repair_candidate_for_drift(drift_type: str, current_config: dict, include_metadata: bool = False):
    candidate = dict(current_config)
    actions = []
    metadata = {
        "repair_reason": f"Quality drift detected: {drift_type}",
        "evidence_signal": drift_type,
        "recommended_action_type": "configuration_change",
        "user_friendly_message": "No action needed",
    }

    if drift_type == "faithfulness_drift":
        candidate["prompt_mode"] = "strict_grounded"
        candidate["verifier_mode"] = "strict"
        candidate["unsupported_claim_policy"] = "remove"
        candidate["generation_temperature"] = 0.1
        candidate["top_k"] = max(8, current_config.get("top_k", 5))
        actions.append("Enforce strict verification and grounded prompts")
        actions.append("Lower temperature to 0.1")
        actions.append("Increase top_k to provide more context")
        metadata.update({
            "repair_reason": "Unsupported answer claims increased.",
            "evidence_signal": "unsupported_claim_rate_high",
            "recommended_action_type": "stricter_verification",
            "user_friendly_message": "Answers will be checked more strictly against your documents.",
        })
        
    elif drift_type == "citation_drift":
        candidate["citation_required"] = True
        candidate["prompt_mode"] = "citation_strict"
        candidate["reranker_enabled"] = True
        candidate["verifier_mode"] = "verified"
        candidate["citation_truth_required"] = True
        candidate["source_count_minimum"] = 2
        actions.append("Require stronger citation verification")
        actions.append("Enable reranker for better citation targets when available")
        actions.append("Keep answer claims tied to cited chunks")
        metadata.update({
            "repair_reason": "Citation Truth Score is low.",
            "evidence_signal": "citation_truth_score_low",
            "recommended_action_type": "citation_verification",
            "user_friendly_message": "The assistant will require stronger source support before presenting citations.",
        })

    elif drift_type == "conflict_drift" or drift_type == "conflict_events":
        candidate["prompt_mode"] = "conflict_aware"
        candidate["verifier_mode"] = "strict"
        candidate["conflict_aware_answers"] = True
        candidate["freshness_priority_enabled"] = True
        actions.append("Require answers to mention document conflicts")
        actions.append("Prefer newer sources only when freshness metadata supports it")
        metadata.update({
            "repair_reason": "Conflicting information was found in retrieved sources.",
            "evidence_signal": "conflict_detected",
            "recommended_action_type": "conflict_aware_answering",
            "user_friendly_message": "Conflicting information found. The assistant will surface conflicts instead of hiding them.",
        })

    elif drift_type == "evidence_gap_drift" or drift_type == "evidence_gap_events":
        candidate["manual_review_required"] = True
        candidate["user_action_needed"] = True
        actions.append("Mark missing evidence as user action needed")
        actions.append("Do not apply parameter-only repair while documents are missing")
        metadata.update({
            "repair_reason": "Required evidence is missing from the workspace.",
            "evidence_signal": "evidence_gap_detected",
            "recommended_action_type": "user_action_needed",
            "user_friendly_message": "More evidence is needed. Upload a relevant document or reprocess failed files.",
        })

    elif drift_type == "freshness_drift" or drift_type == "freshness_warning":
        candidate["freshness_priority_enabled"] = True
        candidate["prompt_mode"] = "freshness_aware"
        actions.append("Keep freshness warning visible")
        actions.append("Prefer latest relevant source only when metadata supports it")
        metadata.update({
            "repair_reason": "Freshness warning exists for retrieved sources.",
            "evidence_signal": "freshness_warning",
            "recommended_action_type": "freshness_aware_source_priority",
            "user_friendly_message": "The assistant will keep freshness warnings visible and avoid claiming latest when dates are unknown.",
        })

    elif drift_type == "retrieval_drift" or drift_type == "data_drift":
        candidate["top_k"] = min(10, current_config.get("top_k", 5) + 3)
        candidate["similarity_threshold"] = round(max(0.60, current_config.get("similarity_threshold", 0.70) - 0.05), 2)
        candidate["hybrid_retrieval"] = True
        candidate["reranker_enabled"] = True
        actions.append("Enable hybrid retrieval and reranker")
        actions.append("Lower similarity threshold slightly to expand recall")

    elif drift_type == "query_drift" or drift_type == "query_pattern_drift":
        candidate["enable_query_rewriting"] = True
        candidate["enable_multi_hop_retrieval"] = True
        candidate["top_k"] = max(8, current_config.get("top_k", 5))
        candidate["prompt_mode"] = "reasoning_grounded"
        actions.append("Enable query rewriting and multi-hop retrieval for complex queries")

    elif drift_type == "performance_drift":
        if current_config.get("top_k", 5) > 5:
            candidate["top_k"] = 5
            actions.append("Reduce top_k to improve latency")
        if current_config.get("reranker_enabled"):
            candidate["reranker_enabled"] = False
            actions.append("Disable reranker to reduce latency")
            
    else:
        # Generic fallback
        candidate["top_k"] = current_config.get("top_k", 5) + 1
        actions.append("Increment top_k marginally")

    if include_metadata:
        return candidate, actions, metadata
    return candidate, actions

# ===== DRIFT MONITORING LOOP =====

async def monitor_drift_events():
    logger.info("📊 Starting background drift-to-candidate monitoring loop")
    while True:
        try:
            await asyncio.sleep(60)
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Find open drift events that need candidates
            cur.execute("""
                SELECT id, workspace_id, drift_type 
                FROM drift_events 
                WHERE status = 'open' OR status = 'investigating'
            """)
            events = cur.fetchall()
            
            for event in events:
                ws_id = event["workspace_id"]
                drift_id = event["id"]
                drift_type = event["drift_type"]
                
                # Check if candidate already exists
                cur.execute("SELECT id FROM repair_candidates WHERE drift_event_id = %s", (drift_id,))
                if cur.fetchone():
                    # Update status
                    cur.execute("UPDATE drift_events SET status = 'repair_candidate_generated' WHERE id = %s", (drift_id,))
                    continue

                stable = _ensure_default_config(cur, ws_id)
                current_cfg = stable["config_json"]
                
                new_cfg, actions, repair_metadata = generate_repair_candidate_for_drift(
                    drift_type, current_cfg, include_metadata=True
                )
                
                # Create candidate config version
                next_version = stable["version_number"] + 1
                cur.execute("""
                    INSERT INTO config_versions (workspace_id, version_number, config_json, status, created_reason, drift_event_id)
                    VALUES (%s, %s, %s, 'candidate', %s, %s)
                    RETURNING id
                """, (ws_id, next_version, json.dumps(new_cfg), f"Auto candidate for {drift_type}", drift_id))
                cand_version_id = cur.fetchone()["id"]
                
                # Create repair candidate
                cur.execute("""
                    INSERT INTO repair_candidates (
                        workspace_id, drift_event_id, candidate_config_version_id,
                        candidate_config_json, repair_actions_json, status,
                        repair_reason, evidence_signal, recommended_action_type, user_friendly_message
                    )
                    VALUES (%s, %s, %s, %s, %s, 'generated', %s, %s, %s, %s)
                    RETURNING id
                """, (
                    ws_id, drift_id, cand_version_id, json.dumps(new_cfg), json.dumps(actions),
                    repair_metadata["repair_reason"], repair_metadata["evidence_signal"],
                    repair_metadata["recommended_action_type"], repair_metadata["user_friendly_message"],
                ))
                cand_id = cur.fetchone()["id"]
                
                cur.execute("UPDATE drift_events SET status = 'repair_candidate_generated' WHERE id = %s", (drift_id,))
                conn.commit()
                
                asyncio.create_task(publish_event("repair.candidate_generated", {
                    "workspace_id": ws_id, "drift_event_id": drift_id, "candidate_id": cand_id
                }))
                
            cur.close()
            return_db(conn)
        except Exception as e:
            logger.error(f"Error in drift monitoring: {e}")
            await asyncio.sleep(60)

# ===== ROUTES =====

@app.get("/repair-candidates")
async def list_repair_candidates(ws: dict = Depends(require_workspace)):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT rc.*, de.drift_type, de.severity, de.metric_name, de.baseline_value
        FROM repair_candidates rc
        LEFT JOIN drift_events de ON rc.drift_event_id = de.id
        WHERE rc.workspace_id = %s
        ORDER BY rc.created_at DESC
    """, (ws["workspace_id"],))
    candidates = cur.fetchall()
    cur.close()
    return_db(conn)
    return {"candidates": [dict(c, created_at=c['created_at'].isoformat() if c['created_at'] else None) for c in candidates]}


@app.get("/repair-candidates/{candidate_id}")
async def get_repair_candidate(candidate_id: int, ws: dict = Depends(require_workspace)):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM repair_candidates WHERE id = %s AND workspace_id = %s", (candidate_id, ws["workspace_id"]))
    cand = cur.fetchone()
    
    if not cand:
        cur.close()
        return_db(conn)
        raise HTTPException(404, "Candidate not found")
        
    # Get evaluations if any
    cur.execute("SELECT * FROM repair_evaluation_results WHERE repair_candidate_id = %s ORDER BY created_at DESC", (candidate_id,))
    evals = cur.fetchall()
    
    cur.close()
    return_db(conn)
    cand['created_at'] = cand['created_at'].isoformat() if cand['created_at'] else None
    return {"candidate": cand, "evaluations": [dict(e, created_at=e['created_at'].isoformat() if e['created_at'] else None) for e in evals]}


@app.post("/repair-candidates/{candidate_id}/test")
async def test_repair_candidate(candidate_id: int, background_tasks: BackgroundTasks, ws: dict = Depends(require_admin)):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM repair_candidates WHERE id = %s AND workspace_id = %s", (candidate_id, ws["workspace_id"]))
    cand = cur.fetchone()
    if not cand:
        cur.close()
        return_db(conn)
        raise HTTPException(404, "Candidate not found")
        
    if cand["status"] in ("applied", "rejected"):
        cur.close()
        return_db(conn)
        raise HTTPException(400, f"Cannot test candidate in status {cand['status']}")

    cur.execute("UPDATE repair_candidates SET status = 'testing', tested_at = NOW() WHERE id = %s", (candidate_id,))
    conn.commit()
    
    # Call evaluation service
    async def real_evaluation():
        try:
            eval_conn = get_db()
            eval_cur = eval_conn.cursor(cursor_factory=RealDictCursor)
            stable = _ensure_default_config(eval_cur, ws["workspace_id"])
            baseline_ver = stable["id"]
            eval_cur.close()
            return_db(eval_conn)
            
            import httpx
            EVAL_URL = os.getenv("EVALUATION_SERVICE_URL", "http://evaluation:8006")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{EVAL_URL}/repair-candidate/{candidate_id}/run",
                    json={
                        "baseline_config_version_id": baseline_ver,
                        "candidate_config_version_id": cand["candidate_config_version_id"],
                        "candidate_id": candidate_id
                    },
                    headers={"x-workspace-id": ws["workspace_id"], "x-user-role": ws["role"]}
                )
                
            if resp.status_code == 200:
                data = resp.json()
                rec = data.get("recommendation", "manual_review")
                new_status = "approved" if rec == "apply" else "rejected" if rec == "reject" else "testing"
                
                # Update statuses
                upd_conn = get_db()
                upd_cur = upd_conn.cursor()
                upd_cur.execute("UPDATE config_versions SET evaluation_result_id = %s, status = 'testing' WHERE id = %s", (data.get("evaluation_result_id"), cand["candidate_config_version_id"]))
                upd_cur.execute("UPDATE repair_candidates SET status = %s WHERE id = %s", (new_status, candidate_id))
                upd_cur.execute("UPDATE drift_events SET status = 'repair_testing' WHERE id = %s", (cand["drift_event_id"],))
                upd_conn.commit()
                upd_cur.close()
                return_db(upd_conn)
                
                await publish_event("repair.candidate_evaluated", {
                    "workspace_id": ws["workspace_id"], "candidate_id": candidate_id, "recommendation": rec
                })
        except Exception as e:
            logger.error(f"Real evaluation failed: {e}")

    background_tasks.add_task(real_evaluation)
    cur.close()
    return_db(conn)
    return {"status": "testing_started", "message": "Candidate sent to real evaluation service"}


@app.post("/repair-candidates/{candidate_id}/apply")
async def apply_repair_candidate(candidate_id: int, ws: dict = Depends(require_admin)):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM repair_candidates WHERE id = %s AND workspace_id = %s", (candidate_id, ws["workspace_id"]))
    cand = cur.fetchone()
    if not cand:
        raise HTTPException(404, "Candidate not found")
        
    if cand["status"] != "approved":
        raise HTTPException(400, "Candidate must be approved before applying")

    # Verify evaluation result exists
    cur.execute("SELECT evaluation_result_id FROM config_versions WHERE id = %s", (cand["candidate_config_version_id"],))
    ver_res = cur.fetchone()
    if not ver_res or not ver_res["evaluation_result_id"]:
        raise HTTPException(400, "Candidate must have a completed evaluation before applying")

    # Mark old active as stable
    cur.execute("UPDATE config_versions SET status = 'stable' WHERE workspace_id = %s AND status = 'active'", (ws["workspace_id"],))
    
    # Mark candidate as active
    cur.execute("UPDATE config_versions SET status = 'active', applied_at = NOW() WHERE id = %s", (cand["candidate_config_version_id"],))
    
    # Update candidate and drift event
    cur.execute("UPDATE repair_candidates SET status = 'applied', applied_at = NOW() WHERE id = %s", (candidate_id,))
    if cand["drift_event_id"]:
        cur.execute("UPDATE drift_events SET status = 'repaired', updated_at = NOW() WHERE id = %s", (cand["drift_event_id"],))

    conn.commit()
    cur.close()
    return_db(conn)
    
    asyncio.create_task(publish_event("repair.candidate_applied", {
        "workspace_id": ws["workspace_id"], "candidate_id": candidate_id, "user_id": ws["user_id"]
    }))
    return {"status": "applied", "message": "Repair candidate successfully applied to active config"}


@app.post("/repair-candidates/{candidate_id}/reject")
async def reject_repair_candidate(candidate_id: int, reason: dict, ws: dict = Depends(require_admin)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE repair_candidates SET status = 'rejected', rejected_reason = %s WHERE id = %s AND workspace_id = %s RETURNING drift_event_id", 
               (reason.get("reason", "Manual rejection"), candidate_id, ws["workspace_id"]))
    res = cur.fetchone()
    if not res:
        raise HTTPException(404, "Candidate not found")
        
    if res[0]:
        cur.execute("UPDATE drift_events SET status = 'investigating' WHERE id = %s", (res[0],))
        
    conn.commit()
    cur.close()
    return_db(conn)
    return {"status": "rejected"}


@app.post("/config/rollback")
async def rollback_config(ws: dict = Depends(require_admin)):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Find current active
    cur.execute("SELECT id, drift_event_id FROM config_versions WHERE workspace_id = %s AND status = 'active'", (ws["workspace_id"],))
    active = cur.fetchone()
    
    # Find last stable
    cur.execute("SELECT id FROM config_versions WHERE workspace_id = %s AND status = 'stable' ORDER BY version_number DESC LIMIT 1", (ws["workspace_id"],))
    stable = cur.fetchone()
    
    if not active or not stable:
        cur.close()
        return_db(conn)
        raise HTTPException(400, "Cannot rollback: missing active or previous stable config")
        
    # Mark active as rolled_back
    cur.execute("UPDATE config_versions SET status = 'rolled_back', rolled_back_at = NOW() WHERE id = %s", (active["id"],))
    
    # Mark stable as active
    cur.execute("UPDATE config_versions SET status = 'active' WHERE id = %s", (stable["id"],))
    
    # Re-open drift event if one caused the bad config
    if active["drift_event_id"]:
        cur.execute("UPDATE drift_events SET status = 'open', updated_at = NOW() WHERE id = %s", (active["drift_event_id"],))
        
    conn.commit()
    cur.close()
    return_db(conn)
    
    asyncio.create_task(publish_event("repair.rollback_completed", {
        "workspace_id": ws["workspace_id"], "user_id": ws["user_id"], "rolled_back_version": active["id"], "restored_version": stable["id"]
    }))
    
    return {"status": "rolled_back", "message": "Successfully rolled back to previous stable configuration"}


@app.get("/config/history")
async def get_config_history(ws: dict = Depends(require_workspace)):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT * FROM config_versions 
        WHERE workspace_id = %s 
        ORDER BY version_number DESC 
        LIMIT 50
    """, (ws["workspace_id"],))
    history = cur.fetchall()
    cur.close()
    return_db(conn)
    
    return {"versions": [dict(h, 
        created_at=h['created_at'].isoformat() if h['created_at'] else None,
        applied_at=h['applied_at'].isoformat() if h['applied_at'] else None,
        rolled_back_at=h['rolled_back_at'].isoformat() if h['rolled_back_at'] else None
    ) for h in history]}

@app.get("/health")
async def health_check():
    try:
        conn = get_db()
        conn.close()
        return {
            "status": "healthy",
            "service": "controller",
            "db": "connected",
            "components": {"database": "connected", "repair_candidates": "available"},
        }
    except:
        return {
            "status": "degraded",
            "service": "controller",
            "db": "disconnected",
            "components": {"database": "disconnected", "repair_candidates": "unknown"},
        }


@app.get("/actions")
async def list_actions():
    return {"actions": action_registry.list_actions()}


@app.post("/trigger-action")
async def trigger_action(action_type: str):
    action = action_registry.get(action_type)
    if not action:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action_type}")
    return {"status": "queued", "action": action_type}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
