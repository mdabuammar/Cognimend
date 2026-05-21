"""
Telemetry Service
Features:
- Connection pooling (Priority 4)
- Redis caching for dashboard data (Priority 2)
- Distributed tracing (Priority 5)
- Real-time metrics aggregation
- Optimized queries (combined N+1 queries)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

# GMT+6 timezone (Bangladesh, etc.)
GMT_PLUS_6 = timezone(timedelta(hours=6))
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging
from contextlib import asynccontextmanager
import sys

# Add parent path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== IMPORT SHARED MODULES =====
SHARED_MODULES_AVAILABLE = False
db_pool = None
cache = None
init_tracing = None
DatabaseManager = None
HealthCheckBuilder = None
datetime_to_iso = None
format_query_results = None

try:
    from services.shared.database import db_pool
    from services.shared.cache import cache
    from services.shared.tracing import init_tracing
    from services.shared.utils import (
        DatabaseManager,
        HealthCheckBuilder,
        datetime_to_iso,
        format_query_results,
        get_db_fallback
    )
    SHARED_MODULES_AVAILABLE = True
    logger.info("✅ Shared modules loaded")
except ImportError as e:
    logger.warning(f"⚠️ Shared modules not available: {e}")


# ===== DATABASE MANAGER =====
db_manager: Optional[Any] = None
if SHARED_MODULES_AVAILABLE and DatabaseManager:
    db_manager = DatabaseManager(db_pool)
else:
    # Create a simple fallback manager
    class FallbackDBManager:
        def get_connection(self):
            import psycopg2
            return psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                database=os.getenv("POSTGRES_DB", "cognimend"),
                user=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", ""),
                connect_timeout=5
            )
        def return_connection(self, conn):
            conn.close()
    db_manager = FallbackDBManager()

# ===== APP LIFECYCLE =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager"""
    logger.info("🚀 Telemetry Service starting...")
    
    if SHARED_MODULES_AVAILABLE:
        init_tracing("telemetry-service")
    
    await init_database()
    
    logger.info("✅ Telemetry Service ready")
    
    # Start background alerting loop
    import asyncio
    asyncio.create_task(continuous_alert_monitoring())
    
    yield
    
    logger.info("🛑 Telemetry Service shutting down...")
    if SHARED_MODULES_AVAILABLE:
        db_pool.close_all()

app = FastAPI(
    title="Telemetry Service",
    version="2.0.0",
    description="Metrics and monitoring service",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Telemetry Service",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "endpoints": [
            "/dashboard/stats",
            "/dashboard/trends",
            "/dashboard/drift-status",
            "/dashboard/auto-fix-actions",
            "/health"
        ]
    }


# SECURITY: Use explicit allowed origins from environment
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
)


# ===== DATABASE FUNCTIONS (USING SHARED MANAGER) =====
def get_db():
    """Get database connection from manager."""
    return db_manager.get_connection()


def return_db(conn) -> None:
    """Return connection to manager."""
    db_manager.return_connection(conn)


async def init_database() -> None:
    """Create drift tables."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Drift events table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS drift_events (
                id SERIAL PRIMARY KEY,
                drift_type VARCHAR(50) NOT NULL,
                severity VARCHAR(20),
                metric_value FLOAT,
                threshold FLOAT,
                description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create index for faster queries
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_drift_events_type_created
            ON drift_events(drift_type, created_at DESC)
        """)
        
        # Auto-fix actions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS auto_fix_actions (
                id SERIAL PRIMARY KEY,
                action_type VARCHAR(100) NOT NULL,
                status VARCHAR(20) DEFAULT 'success',
                documents_affected INTEGER DEFAULT 0,
                improvement VARCHAR(50),
                description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create index for auto_fix_actions
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_auto_fix_actions_created
            ON auto_fix_actions(created_at DESC)
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS query_events (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT,
                retrieved_doc_ids INTEGER[],
                similarities FLOAT[],
                confidence FLOAT,
                latency_ms INTEGER,
                cache_hit BOOLEAN DEFAULT FALSE,
                model_used VARCHAR(100),
                citations_json JSONB DEFAULT '[]',
                workspace_id UUID,
                user_id UUID,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            ALTER TABLE query_events
                ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS model_used VARCHAR(100),
                ADD COLUMN IF NOT EXISTS citations_json JSONB DEFAULT '[]'::jsonb,
                ADD COLUMN IF NOT EXISTS workspace_id UUID,
                ADD COLUMN IF NOT EXISTS user_id UUID,
                ADD COLUMN IF NOT EXISTS faithfulness_score FLOAT,
                ADD COLUMN IF NOT EXISTS unsupported_claim_rate FLOAT,
                ADD COLUMN IF NOT EXISTS verification_status VARCHAR(50),
                ADD COLUMN IF NOT EXISTS retrieval_top1_sim FLOAT,
                ADD COLUMN IF NOT EXISTS retrieval_avg_sim FLOAT,
                ADD COLUMN IF NOT EXISTS citation_truth_score FLOAT,
                ADD COLUMN IF NOT EXISTS conflict_detected BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS evidence_gap_detected BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS freshness_warning BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS evidence_gap_summary TEXT,
                ADD COLUMN IF NOT EXISTS suggested_actions JSONB DEFAULT '[]'::jsonb,
                ADD COLUMN IF NOT EXISTS conflict_details JSONB DEFAULT '[]'::jsonb
        """)
        
        conn.commit()
        cur.close()
        return_db(conn)
        logger.info("✅ Drift events and auto-fix tables initialized")
    except Exception as e:
        logger.warning(f"⚠️ Telemetry init warning: {e}")


# ===== HELPER FUNCTIONS =====
def _convert_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ISO format string."""
    if SHARED_MODULES_AVAILABLE and datetime_to_iso:
        return datetime_to_iso(dt)
    return dt.isoformat() if dt else None


from fastapi import Request

@app.get("/dashboard/stats")
async def get_dashboard_stats(request: Request) -> Dict[str, Any]:
    """
    Get main dashboard statistics.
    Cached for 5 minutes for performance.
    Uses single optimized query instead of N+1 queries.
    """
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")
        
    cache_key = f"telemetry:dashboard:stats:{workspace_id}"
    
    # Check cache first
    if SHARED_MODULES_AVAILABLE and cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info("⚡ Cache HIT: dashboard stats")
            cached['cached'] = True
            return cached
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # ===== OPTIMIZED: Single query instead of 5 separate queries =====
        cur.execute("""
            WITH query_stats AS (
                SELECT 
                    COUNT(*) as total_queries,
                    AVG(confidence) as avg_confidence,
                    AVG(latency_ms) as avg_latency,
                    COUNT(CASE WHEN cache_hit THEN 1 END)::float / 
                        NULLIF(COUNT(*), 0) * 100 as cache_hit_rate
                FROM query_events
                WHERE workspace_id = %s
            ),
            doc_stats AS (
                SELECT COUNT(*) as total_docs
                FROM documents 
                WHERE status = 'ready' AND workspace_id = %s
            ),
            confidence_change AS (
                SELECT 
                    COALESCE(
                        (SELECT AVG(confidence) FROM (
                            SELECT confidence FROM query_events 
                            WHERE workspace_id = %s
                            ORDER BY created_at DESC LIMIT 100
                        ) recent) -
                        (SELECT AVG(confidence) FROM (
                            SELECT confidence FROM query_events 
                            WHERE workspace_id = %s
                            ORDER BY created_at DESC LIMIT 100 OFFSET 100
                        ) previous),
                        0
                    ) as conf_change
            )
            SELECT 
                qs.total_queries,
                qs.avg_confidence,
                qs.avg_latency,
                qs.cache_hit_rate,
                ds.total_docs,
                cc.conf_change
            FROM query_stats qs, doc_stats ds, confidence_change cc
        """, (workspace_id, workspace_id, workspace_id, workspace_id))
        
        stats = cur.fetchone()
        cur.close()
        return_db(conn)
        
        result = {
            "total_queries": stats['total_queries'] or 0,
            "avg_confidence": round(stats['avg_confidence'] or 0, 1),
            "avg_latency_ms": int(stats['avg_latency'] or 0),
            "total_documents": stats['total_docs'] or 0,
            "confidence_change": round(stats['conf_change'] or 0, 1),
            "cache_hit_rate": round(stats['cache_hit_rate'] or 0, 1),
            "timestamp": datetime.now().isoformat(),
            "cached": False
        }
        
        # Cache with workspace-specific key
        if SHARED_MODULES_AVAILABLE and cache:
            await cache.set(f"dashboard:{workspace_id}:overview", result, ttl_seconds=300)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in get_dashboard_stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard stats")


@app.get("/dashboard/drift-status")
async def get_drift_status(request: Request):
    """
    Get current drift detection status
    Cached for 1 minute
    """
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")
        
    cache_key = f"telemetry:drift:status:{workspace_id}"
    
    # Check cache first
    if SHARED_MODULES_AVAILABLE:
        cached = await cache.get(cache_key)
        if cached:
            logger.info("⚡ Cache HIT: drift status")
            return cached
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get latest drift event for each type
        cur.execute("""
            SELECT DISTINCT ON (drift_type)
                drift_type,
                severity,
                metric_value,
                threshold,
                description,
                created_at
            FROM drift_events
            WHERE workspace_id = %s
            ORDER BY drift_type, created_at DESC
        """, (workspace_id,))
        
        drift_events = cur.fetchall()
        
        cur.close()
        return_db(conn)
        
        # Format response
        drift_status = {
            "data_drift": {
                "status": "no_drift",
                "last_detected": None,
                "action": "No action needed",
                "severity": "low"
            },
            "retrieval_drift": {
                "status": "no_drift",
                "last_detected": None,
                "action": "Monitoring",
                "severity": "low"
            },
            "performance_drift": {
                "status": "no_drift",
                "last_detected": None,
                "action": "Stable",
                "severity": "low"
            }
        }
        
        # Update with actual drift events
        for event in drift_events:
            drift_type = event['drift_type']
            if drift_type in drift_status:
                drift_status[drift_type] = {
                    "status": "detected" if event['severity'] in ['high', 'medium'] else "monitoring",
                    "last_detected": event['created_at'].isoformat() if event['created_at'] else None,
                    "action": event['description'] or "Investigating",
                    "severity": event['severity'] or "low",
                    "metric_value": event['metric_value'],
                    "threshold": event['threshold']
                }
        
        result = {
            "drift_status": drift_status,
            "timestamp": datetime.now().isoformat()
        }
        
        # Cache for 1 minute
        if SHARED_MODULES_AVAILABLE:
            await cache.set(cache_key, result, ttl_seconds=60)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in get_drift_status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard/auto-fix-actions")
async def get_auto_fix_actions(request: Request):
    """
    Get recent auto-fix actions.
    Returns the last 10 auto-fix actions with their status.
    """
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")
        
    cache_key = f"telemetry:auto_fix_actions:{workspace_id}"
    
    if SHARED_MODULES_AVAILABLE:
        cached = await cache.get(cache_key)
        if cached:
            logger.info("⚡ Cache HIT: auto-fix actions")
            return cached
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get recent auto-fix actions
        cur.execute("""
            SELECT 
                id,
                action_type,
                status,
                documents_affected,
                improvement,
                description,
                created_at
            FROM remediation_actions ra
            LEFT JOIN drift_events de ON ra.drift_event_id = de.id
            WHERE ra.workspace_id = %s
            ORDER BY ra.created_at DESC
            LIMIT 10
        """, (workspace_id,))
        
        actions = cur.fetchall()
        cur.close()
        return_db(conn)
        
        # Format response
        result = {
            "actions": [
                {
                    "id": str(action['id']),
                    "timestamp": action['created_at'].isoformat() if action['created_at'] else None,
                    "actionType": action['action_type'],
                    "status": action['status'] or "success",
                    "documentsAffected": action['documents_affected'] or 0,
                    "improvement": action['improvement'],
                    "description": action['description']
                }
                for action in actions
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        # Cache for 30 seconds
        if SHARED_MODULES_AVAILABLE:
            await cache.set(cache_key, result, ttl_seconds=30)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in get_auto_fix_actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard/trends")
async def get_trends(request: Request):
    """
    Get performance trends over time
    Cached for 10 minutes
    """
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")
        
    cache_key = f"telemetry:trends:{workspace_id}"
    
    if SHARED_MODULES_AVAILABLE:
        cached = await cache.get(cache_key)
        if cached:
            logger.info("⚡ Cache HIT: trends")
            return cached
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Hourly aggregates for last 24 hours (converted to GMT+6)
        cur.execute("""
            SELECT 
                date_trunc('hour', created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Dhaka') as hour,
                COUNT(*) as query_count,
                AVG(confidence) as avg_confidence,
                AVG(latency_ms) as avg_latency,
                COUNT(CASE WHEN cache_hit THEN 1 END)::float / 
                    NULLIF(COUNT(*), 0) * 100 as cache_hit_rate
            FROM query_events
            WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY date_trunc('hour', created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Dhaka')
            ORDER BY hour
        """, (workspace_id,))
        
        hourly_data = cur.fetchall()
        
        # Daily aggregates for last 7 days (converted to GMT+6)
        cur.execute("""
            SELECT 
                date_trunc('day', created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Dhaka') as day,
                COUNT(*) as query_count,
                AVG(confidence) as avg_confidence,
                AVG(latency_ms) as avg_latency
            FROM query_events
            WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '7 days'
            GROUP BY date_trunc('day', created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Dhaka')
            ORDER BY day
        """, (workspace_id,))
        
        daily_data = cur.fetchall()
        
        cur.close()
        return_db(conn)
        
        # Convert datetime to string
        for row in hourly_data:
            row['hour'] = row['hour'].isoformat() if row['hour'] else None
            row['avg_confidence'] = round(row['avg_confidence'] or 0, 1)
            row['avg_latency'] = int(row['avg_latency'] or 0)
            row['cache_hit_rate'] = round(row['cache_hit_rate'] or 0, 1)
        
        for row in daily_data:
            row['day'] = row['day'].isoformat() if row['day'] else None
            row['avg_confidence'] = round(row['avg_confidence'] or 0, 1)
            row['avg_latency'] = int(row['avg_latency'] or 0)
        
        result = {
            "hourly": hourly_data,
            "daily": daily_data,
            "timestamp": datetime.now(GMT_PLUS_6).isoformat()
        }
        
        # Cache for 30 seconds for near real-time updates
        if SHARED_MODULES_AVAILABLE:
            await cache.set(cache_key, result, ttl_seconds=30)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in get_trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard/recent-queries")
async def get_recent_queries(request: Request, limit: int = 10) -> Dict[str, Any]:
    """Get recent query events."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                id,
                question,
                LEFT(answer, 200) as answer_preview,
                confidence,
                latency_ms,
                cache_hit,
                model_used,
                created_at
            FROM query_events
            WHERE workspace_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (workspace_id, limit))
        
        queries = cur.fetchall()
        
        cur.close()
        return_db(conn)
        
        # Convert datetime to string
        for q in queries:
            q['created_at'] = q['created_at'].isoformat() if q['created_at'] else None
        
        return {"queries": queries}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in get_recent_queries: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent queries")


@app.get("/dashboard/usage")
async def get_dashboard_usage(request: Request) -> Dict[str, Any]:
    """Usage stats: docs counts, monthly queries used/remaining."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")

    cache_key = f"dashboard:{workspace_id}:usage"
    if SHARED_MODULES_AVAILABLE and cache:
        cached = await cache.get(cache_key)
        if cached:
            return cached

    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'ready')   AS ready_docs,
                COUNT(*) FILTER (WHERE status = 'failed')  AS failed_docs,
                COUNT(*) FILTER (WHERE status = 'processing') AS processing_docs,
                COUNT(*)                                    AS total_docs,
                COALESCE(SUM(file_size), 0)                AS total_storage_bytes
            FROM documents
            WHERE workspace_id = %s
        """, (workspace_id,))
        doc_stats = cur.fetchone()

        cur.execute("""
            SELECT COUNT(*) AS monthly_queries
            FROM queries
            WHERE workspace_id = %s
              AND date_trunc('month', created_at) = date_trunc('month', NOW())
        """, (workspace_id,))
        q_stats = cur.fetchone()

        cur.execute("""
            SELECT p.query_limit_monthly, p.document_limit, p.storage_limit_mb
            FROM workspaces w
            LEFT JOIN plans p ON w.plan_id = p.id
            WHERE w.id = %s
        """, (workspace_id,))
        plan = cur.fetchone()

        cur.close()
        return_db(conn)

        query_limit = (plan["query_limit_monthly"] if plan else None) or 50
        doc_limit   = (plan["document_limit"]      if plan else None) or 3
        monthly_used = q_stats["monthly_queries"] or 0

        result = {
            "ready_documents":     doc_stats["ready_docs"] or 0,
            "failed_documents":    doc_stats["failed_docs"] or 0,
            "processing_documents":doc_stats["processing_docs"] or 0,
            "total_documents":     doc_stats["total_docs"] or 0,
            "document_limit":      doc_limit,
            "storage_bytes":       int(doc_stats["total_storage_bytes"] or 0),
            "monthly_queries_used":monthly_used,
            "monthly_queries_limit":query_limit,
            "monthly_queries_remaining": max(0, query_limit - monthly_used),
            "timestamp": datetime.now().isoformat(),
        }

        if SHARED_MODULES_AVAILABLE and cache:
            await cache.set(cache_key, result, ttl_seconds=120)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in get_dashboard_usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch usage stats")


@app.get("/dashboard/quality")
async def get_dashboard_quality(request: Request) -> Dict[str, Any]:
    """Quality metrics: confidence, latency, feedback rate, RAG health score."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")

    cache_key = f"dashboard:{workspace_id}:quality"
    if SHARED_MODULES_AVAILABLE and cache:
        cached = await cache.get(cache_key)
        if cached:
            return cached

    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT
                AVG(confidence)                         AS avg_confidence,
                AVG(latency_ms)                         AS avg_latency_ms,
                COUNT(*) FILTER (WHERE confidence > 0.8) AS high_conf_count,
                COUNT(*)                                 AS total_queries
            FROM query_events
            WHERE workspace_id = %s
        """, (workspace_id,))
        q = cur.fetchone()

        # Feedback rate from query_feedback table if it exists
        feedback_rate = 0.0
        try:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE rating = 'positive') AS positive,
                    COUNT(*) AS total
                FROM query_feedback
                WHERE workspace_id = %s
            """, (workspace_id,))
            fb = cur.fetchone()
            if fb and fb["total"] and fb["total"] > 0:
                feedback_rate = round(fb["positive"] / fb["total"] * 100, 1)
        except Exception:
            pass  # table may not exist yet

        cur.close()
        return_db(conn)

        avg_conf    = round(q["avg_confidence"]  or 0, 1)
        avg_latency = int(q["avg_latency_ms"]    or 0)
        total       = q["total_queries"]          or 0
        high_conf   = q["high_conf_count"]        or 0

        # RAG health score: weighted composite
        conf_score    = avg_conf * 40                        # 0-40
        latency_score = max(0, 30 - avg_latency / 100)      # 0-30 (penalise >3s)
        fb_score      = feedback_rate * 0.3                  # 0-30
        rag_health    = round(min(100, conf_score + latency_score + fb_score), 1)

        result = {
            "avg_confidence":   avg_conf,
            "avg_latency_ms":   avg_latency,
            "total_queries":    total,
            "high_conf_queries": high_conf,
            "feedback_rate":    feedback_rate,
            "rag_health_score": rag_health,
            "timestamp": datetime.now().isoformat(),
        }

        if SHARED_MODULES_AVAILABLE and cache:
            await cache.set(cache_key, result, ttl_seconds=120)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in get_dashboard_quality: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch quality metrics")


@app.post("/log-drift-event")
async def log_drift_event(
    drift_type: str,
    severity: str,
    metric_value: float,
    threshold: float,
    description: str
) -> Dict[str, Any]:
    """Log a drift event from drift detector."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute(
            """
            INSERT INTO drift_events (drift_type, severity, metric_value, threshold, description)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (drift_type, severity, metric_value, threshold, description)
        )
        
        event_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return_db(conn)
        
        # Invalidate drift status cache
        if SHARED_MODULES_AVAILABLE:
            await cache.delete("telemetry:drift:status")
        
        logger.warning(f"🚨 Drift event logged: {drift_type} - {severity}")
        
        return {"success": True, "event_id": event_id}
        
    except Exception as e:
        logger.error(f"❌ Error logging drift event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/cache")
async def clear_cache() -> Dict[str, Any]:
    """Clear telemetry cache."""
    if SHARED_MODULES_AVAILABLE and cache:
        count = await cache.clear_pattern("telemetry:*")
        return {"success": True, "cleared": count}
    return {"success": False, "message": "Cache not available"}


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check using shared HealthCheckBuilder."""
    if SHARED_MODULES_AVAILABLE and HealthCheckBuilder:
        builder = HealthCheckBuilder("telemetry", "2.0.0")
        builder.add_database_check(db_manager)
        builder.add_redis_check(cache)
        return await builder.build()
    
    # Fallback health check
    components = {
        "service": "healthy",
        "database": "unknown",
        "redis": "disabled"
    }
    
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return_db(conn)
        components["database"] = "healthy"
    except Exception:
        components["database"] = "unhealthy"
    
    overall = "healthy" if all(
        v in ["healthy", "disabled"] for v in components.values()
    ) else "degraded"
    
    return {
        "status": overall,
        "service": "telemetry",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "components": components
    }



# ═══════════════════════════════════════════════════════════════════════════════
# RAG QUALITY DASHBOARD ENDPOINTS (Phase 2)
# All queries are workspace-scoped; cache keys include workspace_id.
# ═══════════════════════════════════════════════════════════════════════════════

from fastapi import Request as _Request


async def _cached_query(
    workspace_id: str,
    cache_key_suffix: str,
    sql: str,
    params: tuple,
    ttl: int = 120,
) -> Dict[str, Any]:
    """Run a workspace-scoped DB query with Redis caching."""
    full_key = f"rag_quality:{workspace_id}:{cache_key_suffix}"

    if SHARED_MODULES_AVAILABLE and cache:
        try:
            hit = await cache.get(full_key)
            if hit:
                return hit
        except Exception:
            pass

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return_db(conn)

    result = {k: (v if not hasattr(v, "isoformat") else v.isoformat()) for row in rows for k, v in row.items()} if rows else {}

    if SHARED_MODULES_AVAILABLE and cache:
        try:
            await cache.set(full_key, result, ttl_seconds=ttl)
        except Exception:
            pass
    return result


@app.get("/dashboard/faithfulness")
async def get_faithfulness_dashboard(request: _Request) -> Dict[str, Any]:
    """Workspace-scoped faithfulness metrics aggregated over the last 7 days."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")

    cache_key = f"faithfulness:{workspace_id}:summary"
    if SHARED_MODULES_AVAILABLE and cache:
        try:
            hit = await cache.get(cache_key)
            if hit:
                return hit
        except Exception:
            pass

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            SELECT
                COUNT(*)                                                  AS total_verified,
                AVG(answer_faithfulness_score)                            AS avg_faithfulness_score,
                AVG(unsupported_claim_rate)                               AS avg_unsupported_claim_rate,
                AVG(contradicted_claim_rate)                              AS avg_contradicted_claim_rate,
                AVG(claim_support_rate)                                   AS avg_claim_support_rate,
                SUM(CASE WHEN verifier_status = 'failed' THEN 1 ELSE 0 END) AS verifier_failures,
                SUM(supported_claims)                                     AS total_supported_claims,
                SUM(unsupported_claims)                                   AS total_unsupported_claims,
                SUM(contradicted_claims)                                  AS total_contradicted_claims,
                SUM(total_claims)                                         AS grand_total_claims,
                AVG(verifier_latency_ms)                                  AS avg_verifier_latency_ms
            FROM answer_verification_summaries
            WHERE workspace_id = %s
              AND created_at >= NOW() - INTERVAL '7 days'
            """,
            (workspace_id,)
        )
        row = dict(cur.fetchone() or {})
        cur.close()
        return_db(conn)

        total = row.get("total_verified") or 0
        failures = row.get("verifier_failures") or 0

        result = {
            "workspace_id": workspace_id,
            "period_days": 7,
            "total_verified_answers": int(total),
            "avg_faithfulness_score": round(float(row.get("avg_faithfulness_score") or 0), 3),
            "avg_unsupported_claim_rate": round(float(row.get("avg_unsupported_claim_rate") or 0), 3),
            "avg_contradicted_claim_rate": round(float(row.get("avg_contradicted_claim_rate") or 0), 3),
            "avg_claim_support_rate": round(float(row.get("avg_claim_support_rate") or 0), 3),
            "verifier_failure_rate": round(failures / total, 3) if total else 0.0,
            "total_supported_claims": int(row.get("total_supported_claims") or 0),
            "total_unsupported_claims": int(row.get("total_unsupported_claims") or 0),
            "total_contradicted_claims": int(row.get("total_contradicted_claims") or 0),
            "grand_total_claims": int(row.get("grand_total_claims") or 0),
            "avg_verifier_latency_ms": int(row.get("avg_verifier_latency_ms") or 0),
            # Human-readable label
            "faithfulness_label": (
                "Excellent" if (row.get("avg_faithfulness_score") or 0) >= 0.85
                else "Good" if (row.get("avg_faithfulness_score") or 0) >= 0.7
                else "Needs Attention"
            ),
        }

        if SHARED_MODULES_AVAILABLE and cache:
            try:
                await cache.set(cache_key, result, ttl_seconds=120)
            except Exception:
                pass
        return result

    except Exception as exc:
        logger.error("faithfulness dashboard error: %s", exc)
        raise HTTPException(status_code=503, detail="Faithfulness metrics unavailable")


@app.get("/dashboard/retrieval-quality")
async def get_retrieval_quality_dashboard(request: _Request) -> Dict[str, Any]:
    """Workspace-scoped retrieval quality metrics."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")

    cache_key = f"retrieval:{workspace_id}:summary"
    if SHARED_MODULES_AVAILABLE and cache:
        try:
            hit = await cache.get(cache_key)
            if hit:
                return hit
        except Exception:
            pass

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT
                COUNT(*)                                                        AS total_queries,
                AVG(top1_similarity)                                            AS avg_top1_similarity,
                AVG(top5_avg_similarity)                                        AS avg_top5_similarity,
                AVG(chunks_retrieved)                                           AS avg_chunks_retrieved,
                AVG(retrieval_latency_ms)                                       AS avg_retrieval_latency_ms,
                SUM(CASE WHEN zero_retrieval THEN 1 ELSE 0 END)                 AS zero_retrieval_count,
                SUM(CASE WHEN low_similarity THEN 1 ELSE 0 END)                 AS low_similarity_count
            FROM retrieval_metrics
            WHERE workspace_id = %s
              AND created_at >= NOW() - INTERVAL '7 days'
            """,
            (workspace_id,)
        )
        row = dict(cur.fetchone() or {})
        cur.close()
        return_db(conn)

        total = row.get("total_queries") or 0
        result = {
            "workspace_id": workspace_id,
            "period_days": 7,
            "total_queries": int(total),
            "avg_top1_similarity": round(float(row.get("avg_top1_similarity") or 0), 4),
            "avg_top5_similarity": round(float(row.get("avg_top5_similarity") or 0), 4),
            "avg_chunks_retrieved": round(float(row.get("avg_chunks_retrieved") or 0), 1),
            "avg_retrieval_latency_ms": int(row.get("avg_retrieval_latency_ms") or 0),
            "zero_retrieval_rate": round((row.get("zero_retrieval_count") or 0) / total, 3) if total else 0.0,
            "low_similarity_rate": round((row.get("low_similarity_count") or 0) / total, 3) if total else 0.0,
            "retrieval_health_score": round(
                min(float(row.get("avg_top1_similarity") or 0) * 100, 100), 1
            ),
        }

        if SHARED_MODULES_AVAILABLE and cache:
            try:
                await cache.set(cache_key, result, ttl_seconds=120)
            except Exception:
                pass
        return result

    except Exception as exc:
        logger.error("retrieval quality error: %s", exc)
        raise HTTPException(status_code=503, detail="Retrieval quality metrics unavailable")


@app.get("/dashboard/citation-quality")
async def get_citation_quality_dashboard(request: _Request) -> Dict[str, Any]:
    """Workspace-scoped citation quality metrics."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")

    cache_key = f"citation:{workspace_id}:summary"
    if SHARED_MODULES_AVAILABLE and cache:
        try:
            hit = await cache.get(cache_key)
            if hit:
                return hit
        except Exception:
            pass

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT
                COUNT(*)                            AS total_queries,
                AVG(citation_support_score)         AS avg_citation_support_score,
                AVG(wrong_citation_rate)            AS avg_wrong_citation_rate,
                AVG(missing_citation_rate)          AS avg_missing_citation_rate,
                AVG(citation_coverage)              AS avg_citation_coverage,
                AVG(total_citations)                AS avg_citations_per_query
            FROM citation_metrics
            WHERE workspace_id = %s
              AND created_at >= NOW() - INTERVAL '7 days'
            """,
            (workspace_id,)
        )
        row = dict(cur.fetchone() or {})
        cur.close()
        return_db(conn)

        result = {
            "workspace_id": workspace_id,
            "period_days": 7,
            "total_queries": int(row.get("total_queries") or 0),
            "avg_citation_support_score": round(float(row.get("avg_citation_support_score") or 0), 3),
            "avg_wrong_citation_rate": round(float(row.get("avg_wrong_citation_rate") or 0), 3),
            "avg_missing_citation_rate": round(float(row.get("avg_missing_citation_rate") or 0), 3),
            "avg_citation_coverage": round(float(row.get("avg_citation_coverage") or 0), 3),
            "avg_citations_per_query": round(float(row.get("avg_citations_per_query") or 0), 1),
            "citation_accuracy_score": round(
                (1.0 - float(row.get("avg_wrong_citation_rate") or 0)) * 100, 1
            ),
        }

        if SHARED_MODULES_AVAILABLE and cache:
            try:
                await cache.set(cache_key, result, ttl_seconds=120)
            except Exception:
                pass
        return result

    except Exception as exc:
        logger.error("citation quality error: %s", exc)
        raise HTTPException(status_code=503, detail="Citation quality metrics unavailable")


@app.get("/dashboard/query-drift")
async def get_query_drift_dashboard(request: _Request) -> Dict[str, Any]:
    """Workspace-scoped query intent distribution and drift signals."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")

    cache_key = f"query_drift:{workspace_id}:summary"
    if SHARED_MODULES_AVAILABLE and cache:
        try:
            hit = await cache.get(cache_key)
            if hit:
                return hit
        except Exception:
            pass

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Intent distribution
        cur.execute(
            """
            SELECT
                intent,
                COUNT(*) AS count,
                AVG(complexity_score) AS avg_complexity
            FROM query_analysis
            WHERE workspace_id = %s
              AND created_at >= NOW() - INTERVAL '7 days'
            GROUP BY intent
            ORDER BY count DESC
            """,
            (workspace_id,)
        )
        intent_rows = cur.fetchall()

        # Aggregate booleans
        cur.execute(
            """
            SELECT
                COUNT(*)                                               AS total,
                SUM(CASE WHEN is_multi_hop THEN 1 ELSE 0 END)         AS multi_hop_count,
                SUM(CASE WHEN is_temporal THEN 1 ELSE 0 END)          AS temporal_count,
                SUM(CASE WHEN is_comparison THEN 1 ELSE 0 END)        AS comparison_count,
                SUM(CASE WHEN is_unanswerable THEN 1 ELSE 0 END)      AS unanswerable_count,
                AVG(complexity_score)                                  AS avg_complexity
            FROM query_analysis
            WHERE workspace_id = %s
              AND created_at >= NOW() - INTERVAL '7 days'
            """,
            (workspace_id,)
        )
        agg = dict(cur.fetchone() or {})
        cur.close()
        return_db(conn)

        total = agg.get("total") or 0

        # Build intent distribution
        intent_dist = {}
        for row in intent_rows:
            intent_dist[row["intent"]] = {
                "count": int(row["count"]),
                "percentage": round(int(row["count"]) / total * 100, 1) if total else 0,
            }

        # Drift signal: high unanswerable or comparison rate
        unanswerable_rate = (agg.get("unanswerable_count") or 0) / total if total else 0
        comparison_rate = (agg.get("comparison_count") or 0) / total if total else 0
        drift_signal = (
            "high" if unanswerable_rate > 0.25 or comparison_rate > 0.35
            else "medium" if unanswerable_rate > 0.1 or comparison_rate > 0.2
            else "low"
        )

        result = {
            "workspace_id": workspace_id,
            "period_days": 7,
            "total_queries": int(total),
            "intent_distribution": intent_dist,
            "multi_hop_rate": round((agg.get("multi_hop_count") or 0) / total, 3) if total else 0.0,
            "temporal_rate": round((agg.get("temporal_count") or 0) / total, 3) if total else 0.0,
            "comparison_rate": round((agg.get("comparison_count") or 0) / total, 3) if total else 0.0,
            "unanswerable_rate": round(unanswerable_rate, 3),
            "avg_complexity_score": round(float(agg.get("avg_complexity") or 0), 3),
            "drift_signal": drift_signal,
            "drift_signal_label": {
                "low": "Stable — query patterns consistent",
                "medium": "Moderate shift in query types detected",
                "high": "Significant query pattern change detected",
            }.get(drift_signal, "Unknown"),
        }

        if SHARED_MODULES_AVAILABLE and cache:
            try:
                await cache.set(cache_key, result, ttl_seconds=120)
            except Exception:
                pass
        return result

    except Exception as exc:
        logger.error("query drift error: %s", exc)
        raise HTTPException(status_code=503, detail="Query drift metrics unavailable")


@app.get("/dashboard/rag-quality")
async def get_rag_quality_dashboard(request: _Request) -> Dict[str, Any]:
    """Master RAG quality summary aggregating all quality dimensions."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")

    cache_key = f"rag_quality:{workspace_id}:summary"
    if SHARED_MODULES_AVAILABLE and cache:
        try:
            hit = await cache.get(cache_key)
            if hit:
                return hit
        except Exception:
            pass

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Single combined query
        cur.execute(
            """
            SELECT
                (SELECT AVG(answer_faithfulness_score)
                 FROM answer_verification_summaries
                 WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '7 days')  AS faithfulness_score,

                (SELECT AVG(top1_similarity)
                 FROM retrieval_metrics
                 WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '7 days')  AS retrieval_top1,

                (SELECT AVG(citation_support_score)
                 FROM citation_metrics
                 WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '7 days')  AS citation_support,

                (SELECT AVG(wrong_citation_rate)
                 FROM citation_metrics
                 WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '7 days')  AS wrong_citation_rate,

                (SELECT AVG(unsupported_claim_rate)
                 FROM answer_verification_summaries
                 WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '7 days')  AS unsupported_claim_rate,

                (SELECT COUNT(*)
                 FROM query_analysis
                 WHERE workspace_id = %s
                   AND is_unanswerable = TRUE
                   AND created_at >= NOW() - INTERVAL '7 days')  AS unanswerable_count,

                (SELECT COUNT(*)
                 FROM query_analysis
                 WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '7 days')  AS total_classified,

                (SELECT COUNT(*)
                 FROM retrieval_metrics
                 WHERE workspace_id = %s
                   AND zero_retrieval = TRUE
                   AND created_at >= NOW() - INTERVAL '7 days')  AS zero_retrieval_count,

                (SELECT COUNT(*)
                 FROM retrieval_metrics
                 WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '7 days')  AS total_retrieval
                ,
                (SELECT COUNT(*)
                 FROM conflict_events
                 WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '7 days') AS conflict_events,

                (SELECT COUNT(*)
                 FROM evidence_gaps
                 WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '7 days') AS evidence_gap_events,

                (SELECT COUNT(*)
                 FROM freshness_warnings
                 WHERE workspace_id = %s AND created_at >= NOW() - INTERVAL '7 days') AS freshness_warnings
            """,
            tuple([workspace_id] * 12)
        )
        row = dict(cur.fetchone() or {})
        cur.execute(
            """
            SELECT
                question,
                citation_truth_score,
                conflict_detected,
                evidence_gap_detected,
                freshness_warning,
                evidence_gap_summary,
                created_at
            FROM query_events
            WHERE workspace_id = %s
              AND created_at >= NOW() - INTERVAL '7 days'
              AND (
                conflict_detected = TRUE
                OR evidence_gap_detected = TRUE
                OR freshness_warning = TRUE
                OR citation_truth_score IS NOT NULL
              )
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (workspace_id,),
        )
        quality_rows = cur.fetchall()
        cur.close()
        return_db(conn)

        faithfulness = float(row.get("faithfulness_score") or 0)
        retrieval = float(row.get("retrieval_top1") or 0)
        citation = float(row.get("citation_support") or 0)
        wrong_cit = float(row.get("wrong_citation_rate") or 0)
        unsupported = float(row.get("unsupported_claim_rate") or 0)
        total_classified = int(row.get("total_classified") or 0)
        unanswerable_count = int(row.get("unanswerable_count") or 0)
        zero_ret_count = int(row.get("zero_retrieval_count") or 0)
        total_ret = int(row.get("total_retrieval") or 0)
        conflict_events = int(row.get("conflict_events") or 0)
        evidence_gap_events = int(row.get("evidence_gap_events") or 0)
        freshness_warnings = int(row.get("freshness_warnings") or 0)
        recent_quality_events = []
        for item in quality_rows:
            event_type = "info"
            title = "Citation Quality Checked"
            description = "Citation support was checked against retrieved sources."
            if item.get("conflict_detected"):
                event_type = "warning"
                title = "Document Conflict Found"
                description = "Retrieved sources contained conflicting information and the answer surfaced it."
            elif item.get("evidence_gap_detected"):
                event_type = "error"
                title = "Evidence Gap Found"
                description = item.get("evidence_gap_summary") or "The documents did not contain enough support for the question."
            elif item.get("freshness_warning"):
                event_type = "warning"
                title = "Freshness Warning Raised"
                description = "Source date checks found that retrieved evidence needed a freshness warning."
            elif item.get("citation_truth_score") is not None:
                score = float(item.get("citation_truth_score") or 0)
                title = "Citation Quality Checked"
                description = "Citations strongly matched the answer." if score >= 0.72 else "Citations need source review for this answer."

            recent_quality_events.append({
                "title": title,
                "description": description,
                "created_at": item["created_at"].isoformat() if item.get("created_at") else None,
                "type": event_type,
            })

        unanswerable_rate = unanswerable_count / total_classified if total_classified else 0.0
        zero_ret_rate = zero_ret_count / total_ret if total_ret else 0.0

        result = {
            "workspace_id": workspace_id,
            "period_days": 7,
            # Scores (0–100 for display)
            "retrieval_health": round(retrieval * 100, 1),
            "citation_accuracy": round((1.0 - wrong_cit) * 100, 1),
            "faithfulness_score": round(faithfulness * 100, 1),
            "unsupported_claim_rate": round(unsupported * 100, 1),
            "zero_retrieval_rate": round(zero_ret_rate * 100, 1),
            "wrong_citation_rate": round(wrong_cit * 100, 1),
            "unanswerable_question_rate": round(unanswerable_rate * 100, 1),
            "conflict_events": conflict_events,
            "evidence_gap_events": evidence_gap_events,
            "freshness_warnings": freshness_warnings,
            "recent_quality_events": recent_quality_events,
            # Labels
            "retrieval_health_label": "How often Cognimend finds strong evidence",
            "citation_accuracy_label": "How often sources truly support the answer",
            "faithfulness_score_label": "How much of the answer is verified by your documents",
            # Overall RAG health score (weighted blend)
            "overall_rag_health": round(
                (retrieval * 0.35 + citation * 0.25 + faithfulness * 0.4) * 100, 1
            ),
        }

        if SHARED_MODULES_AVAILABLE and cache:
            try:
                await cache.set(cache_key, result, ttl_seconds=300)
            except Exception:
                pass
        return result

    except Exception as exc:
        logger.error("rag quality dashboard error: %s", exc)
        raise HTTPException(status_code=503, detail="RAG quality metrics unavailable")



import json

async def continuous_alert_monitoring() -> None:
    """Background task for continuous system alert monitoring."""
    import asyncio
    logger.info("🚨 Starting continuous alert monitoring...")
    
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # 1. High Query Latency (> 3000ms average in last 15 mins)
            cur.execute("""
                SELECT workspace_id, AVG(latency_ms) as avg_latency
                FROM query_events
                WHERE created_at >= NOW() - INTERVAL '15 minutes'
                GROUP BY workspace_id
                HAVING AVG(latency_ms) > 3000
            """)
            for row in cur.fetchall():
                create_notification(
                    cur, row['workspace_id'], "system", "warning",
                    "High Query Latency",
                    f"Average query latency in the last 15 minutes is {int(row['avg_latency'])}ms. Check system load or model configuration."
                )

            # 2. Repeated Verifier Failures (>= 3 failures in last 1 hour)
            cur.execute("""
                SELECT workspace_id, COUNT(*) as failures
                FROM answer_verification_summaries
                WHERE verifier_status = 'failed' AND created_at >= NOW() - INTERVAL '1 hour'
                GROUP BY workspace_id
                HAVING COUNT(*) >= 3
            """)
            for row in cur.fetchall():
                create_notification(
                    cur, row['workspace_id'], "system", "high",
                    "Verifier Failures Detected",
                    f"The faithfulness verifier failed {row['failures']} times in the last hour. Check OpenRouter availability or API keys."
                )

            # 3. Repeatedly Rejected Repair Candidates (>= 2 rejections in last 24 hours)
            cur.execute("""
                SELECT workspace_id, COUNT(*) as rejections
                FROM repair_candidates
                WHERE status = 'rejected' AND created_at >= NOW() - INTERVAL '24 hours'
                GROUP BY workspace_id
                HAVING COUNT(*) >= 2
            """)
            for row in cur.fetchall():
                create_notification(
                    cur, row['workspace_id'], "repair", "warning",
                    "Repair Candidates Rejected",
                    f"{row['rejections']} repair candidates were rejected in the last 24 hours. The autonomous healing process is struggling to find a safe improvement."
                )

            # 4. Failed Document Processing
            cur.execute("""
                SELECT workspace_id, COUNT(*) as failed
                FROM documents
                WHERE status = 'failed' AND created_at >= NOW() - INTERVAL '1 hour'
                GROUP BY workspace_id
                HAVING COUNT(*) > 0
            """)
            for row in cur.fetchall():
                create_notification(
                    cur, row['workspace_id'], "system", "warning",
                    "Document Processing Failed",
                    f"{row['failed']} document(s) failed to process in the last hour."
                )

            # 5. Usage limit approaching (>90%)
            cur.execute("""
                SELECT w.id, 
                       (SELECT COUNT(*) FROM queries q WHERE q.workspace_id = w.id AND date_trunc('month', q.created_at) = date_trunc('month', NOW())) as queries_used,
                       p.query_limit_monthly
                FROM workspaces w
                JOIN plans p ON w.plan_id = p.id
            """)
            for row in cur.fetchall():
                limit = row.get('query_limit_monthly', 0)
                used = row.get('queries_used', 0)
                if limit > 0 and (used / limit) >= 0.9:
                    create_notification(
                        cur, row['id'], "billing", "warning",
                        "Usage Limit Approaching",
                        f"Your workspace has used {used} out of {limit} monthly queries. Consider upgrading your plan to avoid service interruption."
                    )
            
            conn.commit()
            cur.close()
            return_db(conn)
            
        except asyncio.CancelledError:
            logger.info("🛑 Alert monitoring stopped")
            break
        except Exception as e:
            logger.error(f"❌ Error in alert monitoring: {e}")
            await asyncio.sleep(60)

def create_notification(cur, workspace_id, notif_type, severity, title, message):
    """Helper to safely insert a notification without spamming."""
    # Check if a similar unread notification exists to prevent spam
    cur.execute("""
        SELECT 1 FROM notifications 
        WHERE workspace_id = %s AND title = %s AND status = 'unread' AND created_at >= NOW() - INTERVAL '6 hours'
    """, (workspace_id, title))
    if cur.fetchone():
        return # Skip

    cur.execute(
        """
        INSERT INTO notifications (workspace_id, type, severity, title, message, status, metadata_json)
        VALUES (%s, %s, %s, %s, %s, 'unread', '{}')
        """,
        (workspace_id, notif_type, severity, title, message)
    )

# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS (Phase 4)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/notifications")
async def get_notifications(request: _Request, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """Get workspace notifications."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(
            """
            SELECT id, type, severity, title, message, status, metadata_json, created_at, read_at
            FROM notifications
            WHERE workspace_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (workspace_id, limit, offset)
        )
        notifications = cur.fetchall()
        
        cur.close()
        return_db(conn)

        for n in notifications:
            n["created_at"] = n["created_at"].isoformat() if n.get("created_at") else None
            n["read_at"] = n["read_at"].isoformat() if n.get("read_at") else None
            
        return {"notifications": notifications}
    except Exception as exc:
        logger.error("get notifications error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch notifications")


@app.get("/notifications/unread-count")
async def get_unread_notification_count(request: _Request) -> Dict[str, Any]:
    """Get unread notifications count."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")

    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT COUNT(*) FROM notifications WHERE workspace_id = %s AND status = 'unread'",
            (workspace_id,)
        )
        count = cur.fetchone()[0]
        
        cur.close()
        return_db(conn)

        return {"unread_count": count}
    except Exception as exc:
        logger.error("get unread notifications count error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch unread count")


@app.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, request: _Request) -> Dict[str, Any]:
    """Mark a notification as read."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")

    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute(
            """
            UPDATE notifications
            SET status = 'read', read_at = NOW()
            WHERE id = %s AND workspace_id = %s
            RETURNING id
            """,
            (notification_id, workspace_id)
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        return_db(conn)
        
        if not row:
            raise HTTPException(status_code=404, detail="Notification not found")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("mark notification read error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to mark notification as read")


@app.put("/notifications/read-all")
async def mark_all_notifications_read(request: _Request) -> Dict[str, Any]:
    """Mark all notifications as read for a workspace."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")

    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute(
            """
            UPDATE notifications
            SET status = 'read', read_at = NOW()
            WHERE workspace_id = %s AND status = 'unread'
            """,
            (workspace_id,)
        )
        conn.commit()
        cur.close()
        return_db(conn)

        return {"success": True}
    except Exception as exc:
        logger.error("mark all notifications read error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to mark all notifications as read")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
