"""
Drift Detector Service
Features:
- Connection pooling (Priority 4)
- Statistical drift detection using KS-test (Priority 7)
- Distributed tracing (Priority 5)
- Three types of drift detection:
  1. Data Drift - embedding distribution shifts
  2. Retrieval Drift - similarity score degradation
  3. Performance Drift - confidence/latency degradation
"""
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import asyncio
import logging
from contextlib import asynccontextmanager
import sys
import numpy as np
from scipy import stats

# Add parent path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _test_workspace_default() -> str:
    return "test-workspace" if os.getenv("API_KEY_REQUIRED", "false").lower() != "true" else ""


def _get_workspace_id(request: Request) -> str:
    workspace_id = request.headers.get("X-Workspace-ID") or _test_workspace_default()
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Missing workspace ID")
    return workspace_id

# ===== IMPORT SHARED MODULES =====
SHARED_MODULES_AVAILABLE = False
db_pool = None
cache = None
init_tracing = None
DatabaseManager = None

try:
    from services.shared.database import db_pool
    from services.shared.cache import cache
    from services.shared.tracing import init_tracing
    from services.shared.utils import DatabaseManager, HealthCheckBuilder
    from services.shared.exceptions import (
        ServiceException, DatabaseError, ValidationError
    )
    SHARED_MODULES_AVAILABLE = True
    logger.info("✅ Shared modules loaded")
except ImportError as e:
    logger.warning(f"⚠️ Shared modules not available: {e}")
    SHARED_MODULES_AVAILABLE = False

# ===== THRESHOLDS =====
# Statistical significance level (p-value threshold)
SIGNIFICANCE_LEVEL = 0.05

# Effect size thresholds for KS-test
DATA_DRIFT_THRESHOLD = 0.15  # KS statistic threshold
RETRIEVAL_DRIFT_THRESHOLD = 0.10  # 10% drop in similarity
PERFORMANCE_DRIFT_THRESHOLD = 0.05  # 5% drop in confidence

# ===== APP LIFECYCLE =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager"""
    logger.info("🚀 Drift Detector Service starting...")
    
    if SHARED_MODULES_AVAILABLE:
        init_tracing("drift-detector-service")
    
    logger.info("✅ Drift Detector Service ready")
    
    # Start background drift monitoring
    asyncio.create_task(continuous_drift_monitoring())
    
    yield
    
    logger.info("🛑 Drift Detector Service shutting down...")
    if SHARED_MODULES_AVAILABLE:
        db_pool.close_all()

app = FastAPI(
    title="Drift Detector Service",
    version="2.0.0",
    description="Drift detection with statistical testing",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Drift Detector Service",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "endpoints": ["/detect", "/status", "/health"]
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


# ===== DATABASE MANAGER =====
db_manager = None
if SHARED_MODULES_AVAILABLE and DatabaseManager:
    db_manager = DatabaseManager(db_pool)
else:
    class FallbackDBManager:
        """Fallback database manager when shared modules unavailable."""
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
        def return_connection(self, conn) -> None:
            conn.close()
    db_manager = FallbackDBManager()


# ===== DATABASE FUNCTIONS (USING SHARED MANAGER) =====
def get_db():
    """Get database connection from manager."""
    return db_manager.get_connection()


def return_db(conn) -> None:
    """Return connection to manager."""
    db_manager.return_connection(conn)


def log_drift_event(
    drift_type: str,
    severity: str,
    metric_value: float,
    threshold: float,
    description: str,
    p_value: Optional[float] = None,
    workspace_id: Optional[str] = None
) -> None:
    """Log drift event to database and create notification."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Include p-value in description if available
        if p_value is not None:
            description = f"{description} (p-value: {p_value:.4f})"
        
        # Original drift_events insert (global / non-workspace scoped fallback)
        cur.execute(
            """
            INSERT INTO drift_events (drift_type, severity, metric_value, threshold, description)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (drift_type, severity, metric_value, threshold, description)
        )
        drift_event_id = cur.fetchone()[0]
        
        # If workspace_id exists, trigger notification
        if workspace_id:
            import json
            title = f"RAG Drift Detected: {drift_type.replace('_', ' ').title()}"
            metadata = json.dumps({"drift_event_id": drift_event_id, "metric_value": metric_value})
            cur.execute(
                """
                INSERT INTO notifications (workspace_id, type, severity, title, message, status, metadata_json)
                VALUES (%s, %s, %s, %s, %s, 'unread', %s)
                """,
                (workspace_id, "drift", severity, title, description, metadata)
            )

        conn.commit()
        cur.close()
        return_db(conn)
        
        ws_log = f"[WS: {workspace_id}] " if workspace_id else ""
        logger.warning(f"🚨 {ws_log}{drift_type.upper()}: {severity.upper()} - {description}")
        
    except Exception as e:
        logger.error(f"❌ Failed to log drift event: {e}")


# ===== STATISTICAL DRIFT DETECTION (Priority 7) =====

async def get_document_chunk_counts_by_period() -> Tuple[List[int], List[int], int, int]:
    """
    Get chunk counts per document for recent and older documents.
    Uses a single optimized CTE query to avoid N+1 problem.
    
    Returns:
        Tuple of (recent_chunks, older_chunks, recent_doc_count, older_doc_count)
    """
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Single optimized CTE query combining all data
        cur.execute("""
            WITH document_periods AS (
                SELECT 
                    d.id,
                    CASE 
                        WHEN d.created_at >= NOW() - INTERVAL '7 days' THEN 'recent'
                        WHEN d.created_at >= NOW() - INTERVAL '30 days' THEN 'older'
                    END as period
                FROM documents d
                WHERE d.status = 'ready' 
                AND d.created_at >= NOW() - INTERVAL '30 days'
            ),
            chunk_counts AS (
                SELECT 
                    dp.period,
                    COUNT(c.id) as chunk_count
                FROM document_periods dp
                INNER JOIN chunks c ON c.document_id = dp.id
                WHERE dp.period IS NOT NULL
                GROUP BY dp.id, dp.period
            )
            SELECT period, chunk_count
            FROM chunk_counts
            ORDER BY period
        """)
        
        results = cur.fetchall()
        cur.close()
        
        recent_chunks = [r['chunk_count'] for r in results if r['period'] == 'recent']
        older_chunks = [r['chunk_count'] for r in results if r['period'] == 'older']
        
        return recent_chunks, older_chunks, len(recent_chunks), len(older_chunks)
        
    finally:
        return_db(conn)


async def detect_data_drift() -> Dict[str, Any]:
    """
    Detect if document embeddings have shifted significantly.
    Uses Kolmogorov-Smirnov test for statistical significance.
    
    Returns:
        Dict with drift detection results
    """
    try:
        recent_chunks, older_chunks, recent_count, older_count = await get_document_chunk_counts_by_period()
        
        if recent_count < 5 or older_count < 5:
            logger.info("📊 Data drift: Insufficient documents for analysis")
            return {
                "status": "insufficient_data", 
                "message": "Need at least 5 documents in each period"
            }
        
        if not recent_chunks or not older_chunks:
            return {"status": "no_chunks", "message": "No chunk data available"}
        
        # ===== KOLMOGOROV-SMIRNOV TEST =====
        # Tests if two samples come from the same distribution
        ks_statistic, p_value = stats.ks_2samp(recent_chunks, older_chunks)
        
        logger.info(f"📊 Data drift KS-test: statistic={ks_statistic:.4f}, p-value={p_value:.4f}")
        
        result = {
            "status": "no_drift",
            "ks_statistic": round(ks_statistic, 4),
            "p_value": round(p_value, 4),
            "threshold": DATA_DRIFT_THRESHOLD,
            "significance_level": SIGNIFICANCE_LEVEL,
            "recent_docs": recent_count,
            "older_docs": older_count
        }
        
        # Check for statistically significant drift
        if ks_statistic > DATA_DRIFT_THRESHOLD and p_value < SIGNIFICANCE_LEVEL:
            severity = "high" if ks_statistic > 0.25 else "medium"
            
            log_drift_event(
                drift_type="data_drift",
                severity=severity,
                metric_value=ks_statistic,
                threshold=DATA_DRIFT_THRESHOLD,
                description=f"Document distribution shift detected. KS statistic: {ks_statistic:.3f}",
                p_value=p_value
            )
            
            result["status"] = "detected"
            result["severity"] = severity
            result["action"] = "Consider re-indexing recent documents"
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in data drift detection: {e}")
        return {"status": "error", "message": str(e)}


async def detect_retrieval_drift() -> Dict[str, Any]:
    """
    Detect if retrieval quality has degraded.
    Uses statistical comparison of similarity scores.
    
    Returns:
        Dict with retrieval drift detection results
    """
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get recent query similarities (last 100)
        cur.execute("""
            SELECT similarities[1] as top_sim
            FROM query_events
            WHERE similarities IS NOT NULL AND array_length(similarities, 1) > 0
            ORDER BY created_at DESC
            LIMIT 100
        """)
        recent_sims = [r['top_sim'] for r in cur.fetchall() if r['top_sim'] is not None]
        
        # Get previous query similarities (101-200)
        cur.execute("""
            SELECT similarities[1] as top_sim
            FROM query_events
            WHERE similarities IS NOT NULL AND array_length(similarities, 1) > 0
            ORDER BY created_at DESC
            LIMIT 100 OFFSET 100
        """)
        previous_sims = [r['top_sim'] for r in cur.fetchall() if r['top_sim'] is not None]
        
        cur.close()
        return_db(conn)
        
        if len(recent_sims) < 20 or len(previous_sims) < 20:
            logger.info("📊 Retrieval drift: Insufficient query data")
            return {"status": "insufficient_data", "message": "Need at least 20 queries in each period"}
        
        # Convert to numpy arrays
        recent_arr = np.array(recent_sims)
        previous_arr = np.array(previous_sims)
        
        # Calculate means
        recent_mean = float(np.mean(recent_arr))
        previous_mean = float(np.mean(previous_arr))
        
        # Calculate relative drop
        drop_percent = (previous_mean - recent_mean) / previous_mean if previous_mean > 0 else 0
        
        # ===== WELCH'S T-TEST =====
        # Tests if means are significantly different (handles unequal variances)
        t_statistic, p_value = stats.ttest_ind(previous_arr, recent_arr, equal_var=False)
        
        logger.info(f"📊 Retrieval drift: drop={drop_percent:.2%}, t={t_statistic:.4f}, p={p_value:.4f}")
        
        result = {
            "status": "no_drift",
            "recent_mean": round(recent_mean, 4),
            "previous_mean": round(previous_mean, 4),
            "drop_percent": round(drop_percent * 100, 2),
            "t_statistic": round(t_statistic, 4),
            "p_value": round(p_value, 4),
            "threshold": RETRIEVAL_DRIFT_THRESHOLD * 100
        }
        
        # Check for significant degradation
        if drop_percent > RETRIEVAL_DRIFT_THRESHOLD and p_value < SIGNIFICANCE_LEVEL:
            severity = "high" if drop_percent > 0.20 else "medium"
            
            log_drift_event(
                drift_type="retrieval_drift",
                severity=severity,
                metric_value=drop_percent,
                threshold=RETRIEVAL_DRIFT_THRESHOLD,
                description=f"Retrieval similarity dropped by {drop_percent:.1%}. Consider increasing top-k.",
                p_value=p_value
            )
            
            result["status"] = "detected"
            result["severity"] = severity
            result["action"] = "Consider increasing top-k or reindexing documents"
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in retrieval drift detection: {e}")
        return {"status": "error", "message": str(e)}


async def detect_performance_drift() -> Dict[str, Any]:
    """
    Detect if answer quality (confidence) has degraded.
    Uses statistical comparison of confidence scores.
    
    Returns:
        Dict with performance drift detection results
    """
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get recent confidence scores (last 100)
        cur.execute("""
            SELECT confidence
            FROM query_events
            WHERE confidence IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 100
        """)
        recent_conf = [r['confidence'] for r in cur.fetchall()]
        
        # Get previous confidence scores (101-200)
        cur.execute("""
            SELECT confidence
            FROM query_events
            WHERE confidence IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 100 OFFSET 100
        """)
        previous_conf = [r['confidence'] for r in cur.fetchall()]
        
        # Also check latency
        cur.execute("""
            SELECT AVG(latency_ms) as avg_latency
            FROM (
                SELECT latency_ms FROM query_events
                ORDER BY created_at DESC LIMIT 100
            ) recent
        """)
        recent_latency = cur.fetchone()['avg_latency'] or 0
        
        cur.execute("""
            SELECT AVG(latency_ms) as avg_latency
            FROM (
                SELECT latency_ms FROM query_events
                ORDER BY created_at DESC LIMIT 100 OFFSET 100
            ) previous
        """)
        previous_latency = cur.fetchone()['avg_latency'] or 0
        
        cur.close()
        return_db(conn)
        
        if len(recent_conf) < 20 or len(previous_conf) < 20:
            logger.info("📊 Performance drift: Insufficient data")
            return {"status": "insufficient_data", "message": "Need at least 20 queries in each period"}
        
        # Convert to numpy arrays
        recent_arr = np.array(recent_conf)
        previous_arr = np.array(previous_conf)
        
        # Calculate means
        recent_mean = float(np.mean(recent_arr))
        previous_mean = float(np.mean(previous_arr))
        
        # Calculate relative drop
        drop_percent = (previous_mean - recent_mean) / previous_mean if previous_mean > 0 else 0
        
        # ===== MANN-WHITNEY U TEST =====
        # Non-parametric test for comparing distributions
        u_statistic, p_value = stats.mannwhitneyu(previous_arr, recent_arr, alternative='greater')
        
        # Latency increase
        latency_increase = (recent_latency - previous_latency) / previous_latency if previous_latency > 0 else 0
        
        logger.info(f"📊 Performance drift: conf_drop={drop_percent:.2%}, latency_increase={latency_increase:.2%}")
        
        result = {
            "status": "no_drift",
            "confidence": {
                "recent_mean": round(recent_mean, 1),
                "previous_mean": round(previous_mean, 1),
                "drop_percent": round(drop_percent * 100, 2)
            },
            "latency": {
                "recent_avg_ms": int(recent_latency),
                "previous_avg_ms": int(previous_latency),
                "increase_percent": round(latency_increase * 100, 2)
            },
            "u_statistic": round(u_statistic, 4),
            "p_value": round(p_value, 4),
            "threshold": PERFORMANCE_DRIFT_THRESHOLD * 100
        }
        
        # Check for significant degradation
        if drop_percent > PERFORMANCE_DRIFT_THRESHOLD and p_value < SIGNIFICANCE_LEVEL:
            severity = "high" if drop_percent > 0.10 else "medium"
            
            log_drift_event(
                drift_type="performance_drift",
                severity=severity,
                metric_value=drop_percent,
                threshold=PERFORMANCE_DRIFT_THRESHOLD,
                description=f"Answer confidence dropped by {drop_percent:.1%}. Model may need tuning.",
                p_value=p_value
            )
            
            result["status"] = "detected"
            result["severity"] = severity
            result["action"] = "Consider prompt tuning or model upgrade"
        
        # Also check latency increase
        if latency_increase > 0.50:  # 50% increase
            log_drift_event(
                drift_type="performance_drift",
                severity="medium",
                metric_value=latency_increase,
                threshold=0.50,
                description=f"Latency increased by {latency_increase:.1%}. Check system resources."
            )
            
            if result["status"] == "no_drift":
                result["status"] = "detected"
                result["severity"] = "medium"
                result["action"] = "Check system resources and connection pools"
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in performance drift detection: {e}")
        return {"status": "error", "message": str(e)}


# ===== EXTENSIBLE DRIFT DETECTOR REGISTRY =====
from abc import ABC, abstractmethod
from typing import Callable, Awaitable


class DriftDetector(ABC):
    """Base class for drift detectors. Extend this to add custom drift detection."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this detector."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this detector monitors."""
        pass
    
    @abstractmethod
    async def detect(self) -> Dict[str, Any]:
        """
        Run drift detection.
        
        Returns:
            Dict with at least 'status' key ('no_drift', 'detected', 'error')
        """
        pass


class DriftDetectorRegistry:
    """Registry for drift detectors. Supports adding custom detectors."""
    
    def __init__(self) -> None:
        self._detectors: Dict[str, Callable[[], Awaitable[Dict[str, Any]]]] = {}
        self._metadata: Dict[str, Dict[str, str]] = {}
    
    def register(
        self,
        name: str,
        detector_fn: Callable[[], Awaitable[Dict[str, Any]]],
        description: str = ""
    ) -> None:
        """
        Register a drift detector.
        
        Args:
            name: Unique detector name
            detector_fn: Async function that returns drift detection results
            description: Description of what this detector monitors
        """
        self._detectors[name] = detector_fn
        self._metadata[name] = {"description": description}
        logger.info(f"📊 Registered drift detector: {name}")
    
    def register_class(self, detector: DriftDetector) -> None:
        """Register a DriftDetector class instance."""
        self.register(detector.name, detector.detect, detector.description)
    
    def unregister(self, name: str) -> bool:
        """Unregister a detector by name."""
        if name in self._detectors:
            del self._detectors[name]
            del self._metadata[name]
            logger.info(f"📊 Unregistered drift detector: {name}")
            return True
        return False
    
    def list_detectors(self) -> List[Dict[str, str]]:
        """List all registered detectors with metadata."""
        return [
            {"name": name, **self._metadata[name]}
            for name in self._detectors
        ]
    
    async def run_all(self) -> Dict[str, Dict[str, Any]]:
        """Run all registered detectors."""
        results = {}
        for name, detector_fn in self._detectors.items():
            try:
                results[name] = await detector_fn()
            except Exception as e:
                logger.error(f"❌ Detector {name} failed: {e}")
                results[name] = {"status": "error", "message": str(e)}
        return results
    
    async def run_one(self, name: str) -> Dict[str, Any]:
        """Run a specific detector by name."""
        if name not in self._detectors:
            raise ValueError(f"Unknown detector: {name}")
        return await self._detectors[name]()



# ===== PHASE 2 QUALITY DRIFT DETECTORS =====

async def detect_faithfulness_drift(workspace_id: Optional[str] = None) -> Dict[str, Any]:
    """Detect when answers become less grounded (faithfulness drift)."""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        ws_filter = "AND workspace_id = %s" if workspace_id else ""
        params_recent = (workspace_id,) if workspace_id else ()

        cur.execute(f"""
            SELECT AVG(answer_faithfulness_score) AS avg_faith,
                   AVG(unsupported_claim_rate)    AS avg_unsupported,
                   AVG(contradicted_claim_rate)   AS avg_contradicted,
                   COUNT(*)                        AS total
            FROM answer_verification_summaries
            WHERE created_at >= NOW() - INTERVAL '1 day'
              AND verifier_status = 'ok'
              {ws_filter}
        """, params_recent)
        recent = dict(cur.fetchone() or {})

        cur.execute(f"""
            SELECT AVG(answer_faithfulness_score) AS avg_faith,
                   AVG(unsupported_claim_rate)    AS avg_unsupported
            FROM answer_verification_summaries
            WHERE created_at >= NOW() - INTERVAL '8 days'
              AND created_at < NOW() - INTERVAL '1 day'
              AND verifier_status = 'ok'
              {ws_filter}
        """, params_recent)
        baseline = dict(cur.fetchone() or {})

        cur.close()
        return_db(conn)

        if (recent.get("total") or 0) < 5:
            return {"status": "insufficient_data", "message": "Need at least 5 verified answers"}

        recent_faith  = float(recent.get("avg_faith") or 0)
        baseline_faith = float(baseline.get("avg_faith") or 0)
        recent_unsup  = float(recent.get("avg_unsupported") or 0)
        baseline_unsup = float(baseline.get("avg_unsupported") or 0)

        result = {
            "status": "no_drift",
            "recent_faithfulness": round(recent_faith, 3),
            "baseline_faithfulness": round(baseline_faith, 3),
            "recent_unsupported_rate": round(recent_unsup, 3),
            "baseline_unsupported_rate": round(baseline_unsup, 3),
        }

        faith_drop = (baseline_faith - recent_faith) / baseline_faith if baseline_faith > 0 else 0
        unsup_increase = recent_unsup - baseline_unsup

        if faith_drop > 0.15 or unsup_increase > 0.15:
            severity = "high" if faith_drop > 0.25 or unsup_increase > 0.25 else "medium"
            log_drift_event(
                drift_type="faithfulness_drift",
                severity=severity,
                metric_value=round(recent_faith, 3),
                threshold=0.15,
                description=(
                    f"Faithfulness dropped {faith_drop:.1%} from baseline. "
                    f"Unsupported claim rate is {recent_unsup:.1%}. "
                    "Consider switching to strict verifier mode or adjusting LLM temperature."
                ),
                workspace_id=workspace_id
            )
            result["status"] = "detected"
            result["severity"] = severity
            result["recommended_action"] = "Switch to strict verifier mode; lower LLM temperature"

        return result
    except Exception as exc:
        logger.error("faithfulness drift error: %s", exc)
        return {"status": "error", "message": str(exc)}


async def detect_citation_drift(workspace_id: Optional[str] = None) -> Dict[str, Any]:
    """Detect when citations become less accurate."""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        ws_filter = "AND workspace_id = %s" if workspace_id else ""
        params = (workspace_id,) if workspace_id else ()

        cur.execute(f"""
            SELECT AVG(citation_support_score) AS avg_support,
                   AVG(wrong_citation_rate)    AS avg_wrong,
                   COUNT(*)                     AS total
            FROM citation_metrics
            WHERE created_at >= NOW() - INTERVAL '1 day'
              {ws_filter}
        """, params)
        recent = dict(cur.fetchone() or {})

        cur.execute(f"""
            SELECT AVG(citation_support_score) AS avg_support,
                   AVG(wrong_citation_rate)    AS avg_wrong
            FROM citation_metrics
            WHERE created_at >= NOW() - INTERVAL '8 days'
              AND created_at < NOW() - INTERVAL '1 day'
              {ws_filter}
        """, params)
        baseline = dict(cur.fetchone() or {})

        cur.close()
        return_db(conn)

        if (recent.get("total") or 0) < 5:
            return {"status": "insufficient_data", "message": "Need at least 5 queries with citation metrics"}

        recent_wrong = float(recent.get("avg_wrong") or 0)
        baseline_wrong = float(baseline.get("avg_wrong") or 0)
        wrong_increase = recent_wrong - baseline_wrong

        result = {
            "status": "no_drift",
            "recent_wrong_citation_rate": round(recent_wrong, 3),
            "baseline_wrong_citation_rate": round(baseline_wrong, 3),
        }

        if recent_wrong > 0.1 or wrong_increase > 0.08:
            severity = "high" if recent_wrong > 0.2 else "medium"
            log_drift_event(
                drift_type="citation_drift",
                severity=severity,
                metric_value=round(recent_wrong, 3),
                threshold=0.1,
                description=(
                    f"Wrong citation rate is {recent_wrong:.1%} (baseline {baseline_wrong:.1%}). "
                    "Citations may be pointing to irrelevant evidence. "
                    "Consider enabling reranker or citation_required mode."
                ),
                workspace_id=workspace_id
            )
            result["status"] = "detected"
            result["severity"] = severity
            result["recommended_action"] = "Enable reranker; set prompt_mode=citation_strict"

        return result
    except Exception as exc:
        logger.error("citation drift error: %s", exc)
        return {"status": "error", "message": str(exc)}


async def detect_query_pattern_drift(workspace_id: Optional[str] = None) -> Dict[str, Any]:
    """Detect when query intent distribution shifts significantly."""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        ws_filter = "AND workspace_id = %s" if workspace_id else ""
        params = (workspace_id,) if workspace_id else ()

        cur.execute(f"""
            SELECT intent, COUNT(*) AS cnt
            FROM query_analysis
            WHERE created_at >= NOW() - INTERVAL '1 day'
              {ws_filter}
            GROUP BY intent
        """, params)
        recent_dist = {r["intent"]: int(r["cnt"]) for r in cur.fetchall()}

        cur.execute(f"""
            SELECT intent, COUNT(*) AS cnt
            FROM query_analysis
            WHERE created_at >= NOW() - INTERVAL '8 days'
              AND created_at < NOW() - INTERVAL '1 day'
              {ws_filter}
            GROUP BY intent
        """, params)
        baseline_dist = {r["intent"]: int(r["cnt"]) for r in cur.fetchall()}

        cur.close()
        return_db(conn)

        recent_total  = sum(recent_dist.values())
        baseline_total = sum(baseline_dist.values())

        if recent_total < 5:
            return {"status": "insufficient_data", "message": "Need at least 5 recent queries"}

        # Compute recent unanswerable rate
        recent_unans = recent_dist.get("unsupported_or_unanswerable", 0) / recent_total
        recent_complex = (
            recent_dist.get("comparison", 0) + recent_dist.get("multi_hop", 0)
        ) / recent_total

        result = {
            "status": "no_drift",
            "recent_intent_distribution": {k: v / recent_total for k, v in recent_dist.items()},
            "recent_unanswerable_rate": round(recent_unans, 3),
            "recent_complex_rate": round(recent_complex, 3),
        }

        drifted = False
        descriptions = []

        if recent_unans > 0.20:
            drifted = True
            descriptions.append(f"Unanswerable query rate is {recent_unans:.1%}.")

        if recent_complex > 0.30:
            drifted = True
            descriptions.append(f"Complex query rate (comparison+multi_hop) is {recent_complex:.1%}.")

        # Check for baseline shifts
        if baseline_total > 0:
            for intent, count in recent_dist.items():
                recent_pct   = count / recent_total
                baseline_pct = baseline_dist.get(intent, 0) / baseline_total
                if recent_pct - baseline_pct > 0.25:
                    drifted = True
                    descriptions.append(
                        f"Intent '{intent}' increased from {baseline_pct:.0%} to {recent_pct:.0%}."
                    )

        if drifted:
            log_drift_event(
                drift_type="query_drift",
                severity="medium",
                metric_value=recent_unans,
                threshold=0.20,
                description=" ".join(descriptions) + " Consider enabling query rewriting or multi-hop retrieval.",
                workspace_id=workspace_id
            )
            result["status"] = "detected"
            result["severity"] = "medium"
            result["description"] = " ".join(descriptions)
            result["recommended_action"] = "Enable query rewriting; increase top_k; enable hybrid retrieval"

        return result
    except Exception as exc:
        logger.error("query drift error: %s", exc)
        return {"status": "error", "message": str(exc)}


# Initialize global registry with built-in detectors
drift_registry = DriftDetectorRegistry()
drift_registry.register("data_drift", detect_data_drift, "Monitors document embedding distribution shifts")
drift_registry.register("retrieval_drift", detect_retrieval_drift, "Monitors retrieval similarity degradation")
drift_registry.register("performance_drift", detect_performance_drift, "Monitors answer confidence and latency")
# Phase 2: quality-layer drift detectors
drift_registry.register("faithfulness_drift", detect_faithfulness_drift, "Monitors claim-level faithfulness degradation")
drift_registry.register("citation_drift", detect_citation_drift, "Monitors citation accuracy degradation")
drift_registry.register("query_drift", detect_query_pattern_drift, "Monitors query intent distribution shifts")



# ===== CONTINUOUS MONITORING =====

async def continuous_drift_monitoring() -> None:
    """Background task for continuous drift monitoring."""
    logger.info("📊 Starting continuous drift monitoring...")
    
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            
            logger.info("📊 Running scheduled drift detection...")
            
            # Run all registered drift detectors
            await drift_registry.run_all()
            
            logger.info("✅ Scheduled drift detection complete")
            
        except asyncio.CancelledError:
            logger.info("🛑 Drift monitoring stopped")
            break
        except Exception as e:
            logger.error(f"❌ Error in drift monitoring: {e}")
            await asyncio.sleep(60)  # Wait a minute on error


# ===== API ENDPOINTS =====

@app.post("/run-detection")
async def run_detection(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Trigger drift detection manually."""
    logger.info("📊 Manual drift detection triggered")
    
    # Run all registered detectors
    results = await drift_registry.run_all()
    
    # Invalidate cache
    if SHARED_MODULES_AVAILABLE:
        await cache.delete("telemetry:drift:status")
    
    results["timestamp"] = datetime.now().isoformat()
    return results


@app.get("/detectors")
async def list_detectors() -> Dict[str, Any]:
    """List all registered drift detectors."""
    return {
        "detectors": drift_registry.list_detectors(),
        "count": len(drift_registry.list_detectors())
    }


@app.post("/run-detection/{detector_name}")
async def run_single_detector(detector_name: str) -> Dict[str, Any]:
    """Run a specific drift detector by name."""
    try:
        result = await drift_registry.run_one(detector_name)
        result["detector"] = detector_name
        result["timestamp"] = datetime.now().isoformat()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/status")
async def get_drift_status(request: Request) -> Dict[str, Any]:
    """Get current drift detection status."""
    workspace_id = _get_workspace_id(request)
        
    cache_key = f"drift:status:{workspace_id}"
    
    if SHARED_MODULES_AVAILABLE:
        cached = await cache.get(cache_key)
        if cached:
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
        
        events = cur.fetchall()
        cur.close()
        return_db(conn)
        
        result = {
            "data_drift": {"status": "no_drift", "last_check": None},
            "retrieval_drift": {"status": "no_drift", "last_check": None},
            "performance_drift": {"status": "no_drift", "last_check": None},
            "timestamp": datetime.now().isoformat()
        }
        
        for event in events:
            result[event['drift_type']] = {
                "status": "detected" if event['severity'] in ['high', 'medium'] else "monitoring",
                "severity": event['severity'],
                "metric_value": event['metric_value'],
                "threshold": event['threshold'],
                "description": event['description'],
                "last_check": event['created_at'].isoformat() if event['created_at'] else None
            }
        
        if SHARED_MODULES_AVAILABLE:
            await cache.set(cache_key, result, ttl_seconds=60)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error getting drift status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
async def get_drift_history(request: Request, limit: int = 50) -> Dict[str, Any]:
    """Get drift event history."""
    workspace_id = _get_workspace_id(request)
        
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                id,
                drift_type,
                severity,
                metric_value,
                threshold,
                description,
                created_at
            FROM drift_events
            WHERE workspace_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (workspace_id, limit))
        
        events = cur.fetchall()
        cur.close()
        return_db(conn)
        
        for e in events:
            e['created_at'] = e['created_at'].isoformat() if e['created_at'] else None
        
        return {"events": events}
        
    except Exception as e:
        logger.error(f"❌ Error getting drift history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    components = {
        "service": "healthy",
        "database": "unknown",
        "redis": "unknown" if SHARED_MODULES_AVAILABLE else "disabled"
    }
    
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return_db(conn)
        components["database"] = "healthy"
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        components["database"] = "unhealthy"
    
    if SHARED_MODULES_AVAILABLE:
        components["redis"] = "healthy" if cache.is_available() else "unhealthy"
    
    overall = "healthy" if all(
        v in ["healthy", "disabled"] for v in components.values()
    ) else "degraded"
    
    return {
        "status": overall,
        "service": "drift-detector",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "components": components,
        "statistical_tests": ["KS-test", "Welch's t-test", "Mann-Whitney U"],
        "registered_detectors": len(drift_registry.list_detectors())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
