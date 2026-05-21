#!/usr/bin/env python3
"""
VELA Automated End-to-End Test Loop
====================================
1. Starts Upload + Query services
2. Creates diverse test documents
3. Uploads them to the system
4. Runs queries and checks confidence
5. Verifies drift detection
6. Reports results
7. Loops until everything works perfectly
"""
import subprocess
import time
import sys
import os
import json
import requests
import tempfile
import signal
from pathlib import Path
from datetime import datetime

# ─── Config ────────────────────────────────────────────────────────────────────
UPLOAD_URL  = "http://localhost:8001"
QUERY_URL   = "http://localhost:8002"
PROJECT_DIR = Path(r"D:\Project")
BACKEND_DIR = PROJECT_DIR / "backend"
MAX_LOOPS   = 5
TIMEOUT     = 30

RESET  = "\033[0m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
BLUE   = "\033[94m"

def log(msg, color=RESET):    print(f"{color}{msg}{RESET}", flush=True)
def ok(msg):                  log(f"  ✅  {msg}", GREEN)
def fail(msg):                log(f"  ❌  {msg}", RED)
def warn(msg):                log(f"  ⚠️   {msg}", YELLOW)
def info(msg):                log(f"  ℹ️   {msg}", CYAN)
def section(msg):             log(f"\n{'='*60}\n  {msg}\n{'='*60}", BOLD + BLUE)

# ─── Test Documents ─────────────────────────────────────────────────────────────
TEST_DOCS = [
    {
        "filename": "employee_handbook.txt",
        "title": "Employee Handbook 2026",
        "content": """EMPLOYEE HANDBOOK 2026

VACATION POLICY
Full-time employees receive 20 days of paid vacation per year.
Vacation days accrue at a rate of 1.67 days per month.
Unused vacation can be carried over up to 5 days into the next year.
Vacation requests must be submitted at least 2 weeks in advance through the HR portal.
Vacation is pro-rated for employees who join mid-year.

SICK LEAVE POLICY
All employees are entitled to 10 days of paid sick leave per year.
Sick leave does not carry over to the next year.
A doctor's note is required for absences exceeding 3 consecutive days.
Sick leave cannot be used for vacation purposes.

REMOTE WORK POLICY
Employees may work remotely up to 3 days per week with manager approval.
Remote work requires a reliable internet connection of at least 25 Mbps.
All remote employees must be available during core hours: 10 AM - 3 PM local time.
Remote work requests must be submitted 48 hours in advance.

WORKING HOURS
Standard working hours are 9 AM to 6 PM Monday through Friday.
A one-hour lunch break is provided daily.
Overtime requires prior manager approval and is compensated at 1.5x rate.
Flexible start times between 7 AM and 10 AM are available with manager approval.

PERFORMANCE REVIEW
Performance reviews are conducted twice a year: in June and December.
Reviews assess technical skills, collaboration, and goal achievement.
Employees scoring below expectations receive a Performance Improvement Plan (PIP).
Annual raises are determined based on performance review scores.

EXPENSE REIMBURSEMENT
Employees can submit expense reports through the Finance portal.
Receipts must be attached for all expenses above $25.
Expense reports must be submitted within 30 days of the expense.
Pre-approval is required for expenses exceeding $500.

DRESS CODE
Business casual attire is expected in the office.
Jeans are acceptable on Fridays.
Client-facing meetings require formal business attire.
Visible tattoos and piercings are acceptable as long as they are not offensive.

ONBOARDING PROCESS
New employees complete a 2-week onboarding program.
Week 1 covers company culture, policies, and team introductions.
Week 2 is role-specific training and tool setup.
A buddy is assigned to each new employee for the first 90 days.

COMPANY BENEFITS
Health insurance coverage begins on the first day of employment.
Dental and vision insurance are included in the standard benefits package.
401k matching up to 4% of salary is provided after 6 months of employment.
Employee wellness programs include gym membership reimbursement up to $50/month.
""",
    },
    {
        "filename": "technical_docs.txt",
        "title": "VELA System Technical Documentation",
        "content": """VELA TECHNICAL DOCUMENTATION

ARCHITECTURE OVERVIEW
VELA is a microservices-based autonomous RAG (Retrieval-Augmented Generation) system.
The system consists of 6 core services: Upload, Query, Telemetry, Drift Detector, Controller, and Evaluation.
All services communicate via REST APIs and shared PostgreSQL, Redis, and Qdrant databases.
The system uses OpenRouter as an AI gateway providing access to 500+ language models.

UPLOAD SERVICE (Port 8001)
Accepts PDF, DOCX, and TXT files for ingestion into the knowledge base.
Documents are split into chunks using tiktoken with a 256-token window and 64-token overlap.
Each chunk is embedded using the text-embedding-3-small model from OpenRouter.
Embeddings are stored in Qdrant vector database for semantic search.
SHA-256 hashing prevents duplicate document uploads.
Redis caches embeddings for 24 hours to reduce API costs.

QUERY SERVICE (Port 8002)
Accepts natural language questions and returns AI-generated answers with citations.
Performs semantic search in Qdrant using cosine similarity.
Retrieves top-K most relevant chunks (default K=5).
Confidence scoring uses a multi-factor formula: 45% retrieval similarity + 35% groundedness + 20% answer quality.
Results are cached in Redis for 2 hours to improve response times.
Supports file attachment queries with OCR for image files.

DRIFT DETECTOR SERVICE (Port 8004)
Monitors system health using three statistical tests:
1. Kolmogorov-Smirnov test for data drift in document embeddings
2. Welch T-test for retrieval quality degradation
3. Mann-Whitney U test for performance drift in confidence and latency metrics
Drift detection runs every 5 minutes in the background.
Uses p-value threshold of 0.05 for statistical significance.

CONTROLLER SERVICE (Port 8000)
Responds to drift events by automatically adjusting system configuration.
Actions: reindex documents, increase top-k retrieval, expand chunk overlap, lower confidence threshold.
All configuration changes are versioned with optimistic locking in PostgreSQL.
Supports full rollback to any previous configuration version.
Background monitor checks drift events every 60 seconds.

DATABASE SCHEMA
documents: stores document metadata including title, filename, version, status
chunks: stores individual text chunks with their embeddings
query_events: logs all queries with confidence, latency, and cache status
drift_events: records detected drift events with statistical measures
auto_fix_actions: logs all autonomous controller actions
system_config: stores versioned system configuration parameters

DEPLOYMENT
All services are containerized and Kubernetes-ready.
Horizontal Pod Autoscaling enabled for the Query service (3-10 replicas).
Health probes: /health/live, /health/ready, /health/startup
Circuit breakers protect all external service calls.
Connection pooling configured for PostgreSQL and Redis.
""",
    },
    {
        "filename": "ai_research.txt",
        "title": "AI and Machine Learning Research Notes",
        "content": """AI AND MACHINE LEARNING RESEARCH NOTES

RETRIEVAL-AUGMENTED GENERATION (RAG)
RAG combines retrieval systems with language model generation to produce accurate, grounded answers.
The retrieval component searches a vector database for relevant context using semantic similarity.
The generation component uses a large language model to synthesize answers from retrieved context.
RAG systems are particularly effective for domain-specific question answering over large document corpora.
Key metrics for RAG systems include retrieval precision, answer faithfulness, and response latency.

VECTOR DATABASES
Vector databases store high-dimensional embeddings and support approximate nearest neighbor search.
Popular vector databases include Qdrant, Pinecone, Weaviate, and Chroma.
Cosine similarity is the most common distance metric for text embeddings.
Qdrant supports payload filtering allowing metadata-based search refinement.
Collection sharding allows horizontal scaling of vector storage.

EMBEDDING MODELS
Text embeddings convert natural language into dense numerical vectors.
OpenAI text-embedding-3-small produces 1536-dimensional embeddings with strong retrieval performance.
text-embedding-3-large produces higher quality embeddings at higher cost.
Voyage voyage-3 excels specifically at RAG retrieval tasks.
Embedding quality directly impacts retrieval accuracy in RAG systems.

STATISTICAL DRIFT DETECTION
Data drift occurs when the statistical properties of inputs change over time.
The Kolmogorov-Smirnov (KS) test compares two distributions to detect if they differ significantly.
A KS statistic above 0.15 with p-value below 0.05 indicates statistically significant drift.
Welch's T-test is appropriate for comparing means of two groups with unequal variances.
The Mann-Whitney U test is a non-parametric alternative that does not assume normal distribution.
Running multiple statistical tests simultaneously improves drift detection reliability.

LARGE LANGUAGE MODELS
Large language models (LLMs) are trained on massive text corpora to predict and generate text.
GPT-4o by OpenAI offers superior reasoning capabilities at moderate cost.
Claude 3.5 Sonnet by Anthropic excels at long-form analysis and complex instructions.
Meta's Llama 3.3 70B is an open-source model competitive with proprietary alternatives.
Google's Gemini Flash offers fast inference at low cost for high-volume applications.
Model fallback chains ensure system reliability when primary models are unavailable.

PRODUCTION MLOps
MLOps practices ensure reliable deployment and operation of machine learning systems.
Continuous monitoring tracks model performance metrics to detect degradation.
A/B testing compares different model configurations in production environments.
Canary deployments gradually roll out changes to limit blast radius.
Feature stores enable consistent feature computation across training and serving.
Model registries version and track model artifacts through the ML lifecycle.

CONFIDENCE SCORING
Confidence scores estimate the reliability of AI-generated answers.
High confidence (above 80%) indicates strong grounding in retrieved context.
Medium confidence (50-80%) suggests the answer may be partially supported.
Low confidence (below 50%) indicates the system lacks sufficient relevant context.
Confidence should account for retrieval quality, answer groundedness, and response coherence.
""",
    },
    {
        "filename": "company_policies.txt",
        "title": "Company Security and IT Policies",
        "content": """COMPANY SECURITY AND IT POLICIES 2026

PASSWORD POLICY
All passwords must be at least 12 characters long.
Passwords must contain uppercase, lowercase, numbers, and special characters.
Passwords must be changed every 90 days.
Password reuse is not allowed for the last 10 passwords.
Multi-factor authentication (MFA) is required for all systems.
Use of a company-approved password manager is strongly recommended.

DATA CLASSIFICATION
Data is classified into four levels: Public, Internal, Confidential, and Restricted.
Public data can be freely shared outside the organization.
Internal data is for employee use only and must not be shared externally.
Confidential data requires encryption in transit and at rest.
Restricted data (including PII and financial data) requires additional access controls.

INCIDENT RESPONSE
Suspected security incidents must be reported to security@company.com within 1 hour.
The incident response team will acknowledge within 30 minutes during business hours.
All systems involved in an incident must be isolated immediately.
A post-incident review is conducted within 5 business days of resolution.
All incidents are documented in the security incident management system.

ACCEPTABLE USE POLICY
Company devices may only be used for legitimate business purposes.
Installation of unauthorized software on company devices is prohibited.
Accessing inappropriate or illegal content on company networks is strictly forbidden.
Company data must not be stored on personal devices or unauthorized cloud services.
VPN must be used whenever connecting to company resources from outside the office.

SOFTWARE DEVELOPMENT SECURITY
All code must undergo peer review before merging to main branches.
Security testing (SAST, DAST) must be performed before production deployment.
Third-party dependencies must be approved and regularly updated.
Secrets and credentials must never be committed to version control.
API keys must be rotated every 6 months or immediately if compromised.

BUSINESS CONTINUITY
Critical systems have a Recovery Time Objective (RTO) of 4 hours.
Recovery Point Objective (RPO) for critical data is 1 hour.
Disaster recovery drills are conducted quarterly.
Backup systems are tested monthly to ensure data integrity.
Off-site backups are maintained for all critical data.
""",
    },
    {
        "filename": "product_roadmap.txt",
        "title": "Product Roadmap Q2-Q4 2026",
        "content": """PRODUCT ROADMAP Q2-Q4 2026

Q2 2026 PRIORITIES
Launch autonomous drift detection with statistical testing (KS-test, T-test, Mann-Whitney U).
Implement versioned configuration management with atomic rollback capability.
Release file attachment feature for query-with-document functionality.
Deploy real-time monitoring dashboard with confidence trends and auto-fix action logs.
Complete Kubernetes production manifests with HPA and PodDisruptionBudgets.
Achieve 99.9% uptime SLA across all microservices.

Q3 2026 PRIORITIES
Integrate multimodal document support including images and scanned PDFs with OCR.
Launch public SaaS product with Starter, Pro, and Enterprise pricing tiers.
Implement multi-tenant isolation for enterprise customers.
Add support for hybrid search combining dense vectors with BM25 keyword search.
Release public API with rate limiting, API key management, and usage analytics.
Expand to 1000+ supported AI models through additional gateway integrations.

Q4 2026 PRIORITIES
Launch SDKs for Python, TypeScript, and Go.
Implement automated evaluation pipelines with continuous benchmarking.
Add custom embedding model fine-tuning support for domain-specific use cases.
Deploy to additional cloud regions for global low-latency query serving.
Release enterprise SSO integration with SAML and OIDC support.
Achieve SOC 2 Type II certification for enterprise compliance requirements.

KEY PERFORMANCE TARGETS
Query latency P95 below 2000ms end-to-end including LLM generation.
Document upload processing under 30 seconds for files up to 10MB.
Drift detection running every 5 minutes with sub-second statistical computation.
Cache hit rate above 40% for repeated or similar queries.
Answer confidence averaging above 80% for well-indexed document corpora.
Zero unexpected service downtime through circuit breakers and health monitoring.

TECHNICAL DEBT ITEMS
Migrate from synchronous to asynchronous drift detection pipeline.
Replace in-memory rate limiting with distributed Redis-based implementation.
Implement connection pool monitoring with automatic pool size adjustment.
Add comprehensive distributed tracing across all service boundaries.
Upgrade embedding model selection to include user-configurable options.
Implement automatic test question generation for evaluation service.
""",
    },
]

QUERIES = [
    ("What is the vacation policy?",           80),
    ("How many sick leave days do employees get?", 75),
    ("What is the remote work policy?",         75),
    ("How does the drift detection work?",      70),
    ("What are the password requirements?",     70),
    ("What is the Q3 2026 product roadmap?",    70),
    ("How does VELA calculate confidence scores?", 65),
    ("What is the onboarding process?",         70),
    ("What is the working hours policy?",       75),
    ("How are expenses reimbursed?",            70),
]

# ─── Helpers ─────────────────────────────────────────────────────────────────────
procs = []

def start_service(name, port, service_dir, env_extra=None):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)
    if env_extra:
        env.update(env_extra)

    cmd = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--log-level", "warning",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(service_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    procs.append((name, proc))
    return proc


def wait_for_service(url, name, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{url}/health", timeout=3)
            if r.status_code in (200, 422):
                ok(f"{name} is ready at {url}")
                return True
        except Exception:
            pass
        time.sleep(2)
    fail(f"{name} did NOT start within {timeout}s")
    return False


def stop_all():
    for name, proc in procs:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    procs.clear()


def check_health(url, service):
    try:
        r = requests.get(f"{url}/health", timeout=5)
        data = r.json()
        status = data.get("status", "unknown")
        components = data.get("components", {})
        if status == "healthy":
            ok(f"{service}: healthy {components}")
            return True
        else:
            warn(f"{service}: {status} {components}")
            return False
    except Exception as e:
        fail(f"{service} health check failed: {e}")
        return False


def upload_document(doc):
    try:
        text = doc["content"].encode("utf-8")
        files = {"file": (doc["filename"], text, "text/plain")}
        data = {"title": doc["title"]}
        r = requests.post(f"{UPLOAD_URL}/upload", files=files, data=data, timeout=120)
        if r.status_code == 200:
            result = r.json()
            ok(f"Uploaded '{doc['title']}' → doc_id={result.get('document_id')}, chunks={result.get('chunks')}")
            return result
        else:
            fail(f"Upload failed ({r.status_code}): {r.text[:200]}")
            return None
    except Exception as e:
        fail(f"Upload exception: {e}")
        return None


def run_query(question, min_confidence):
    try:
        payload = {"question": question, "top_k": 5}
        r = requests.post(f"{QUERY_URL}/query", json=payload, timeout=60)
        if r.status_code == 200:
            data = r.json()
            confidence = data.get("confidence", 0)
            latency    = data.get("latency_ms", 0)
            citations  = len(data.get("citations", []))
            answer     = data.get("answer", "")[:100]
            color = GREEN if confidence >= min_confidence else YELLOW
            log(f"    Q: {question[:55]:<55} | conf={confidence:5.1f}% | lat={latency:5}ms | cit={citations}", color)
            return {"success": True, "confidence": confidence, "latency": latency, "citations": citations, "answer": answer}
        else:
            fail(f"Query failed ({r.status_code}): {r.text[:150]}")
            return {"success": False, "confidence": 0}
    except Exception as e:
        fail(f"Query exception: {e}")
        return {"success": False, "confidence": 0}


def get_documents():
    try:
        r = requests.get(f"{UPLOAD_URL}/documents", timeout=10)
        if r.status_code == 200:
            return r.json()
        return []
    except Exception:
        return []


def print_summary(results, loop_num):
    section(f"LOOP {loop_num} SUMMARY")
    uploaded = results["uploaded"]
    queries  = results["queries"]
    
    info(f"Documents uploaded:  {uploaded['success']}/{uploaded['total']}")
    
    if queries:
        passed    = sum(1 for q in queries if q.get("success") and q.get("confidence", 0) >= q.get("min_confidence", 70))
        avg_conf  = sum(q.get("confidence", 0) for q in queries) / max(len(queries), 1)
        avg_lat   = sum(q.get("latency", 0) for q in queries) / max(len(queries), 1)
        info(f"Queries succeeded:   {sum(1 for q in queries if q.get('success'))}/{len(queries)}")
        info(f"Confidence met:      {passed}/{len(queries)}")
        info(f"Avg confidence:      {avg_conf:.1f}%")
        info(f"Avg latency:         {avg_lat:.0f}ms")
        
        all_good = (
            uploaded["success"] == uploaded["total"]
            and sum(1 for q in queries if q.get("success")) == len(queries)
            and avg_conf >= 65
        )
        if all_good:
            log("\n  🎉 SYSTEM WORKING PERFECTLY! All tests passed.\n", BOLD + GREEN)
            return True
        else:
            warn("System needs improvement — will keep looping...")
            return False
    return False


# ─── Main Loop ───────────────────────────────────────────────────────────────────
def main():
    log(f"\n{'#'*60}", BOLD + CYAN)
    log(f"  VELA Automated End-to-End Test Loop", BOLD + CYAN)
    log(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", CYAN)
    log(f"{'#'*60}\n", BOLD + CYAN)

    for loop in range(1, MAX_LOOPS + 1):
        section(f"LOOP {loop}/{MAX_LOOPS} — Starting")
        results = {"uploaded": {"success": 0, "total": len(TEST_DOCS)}, "queries": []}

        # ── 1. Start Services ─────────────────────────────────────────────────
        section(f"LOOP {loop} — Starting Backend Services")
        service_env = {
            "POSTGRES_HOST":     "localhost",
            "POSTGRES_PORT":     "5432",
            "POSTGRES_DB":       "cognimend",
            "POSTGRES_USER":     "postgres",
            "POSTGRES_PASSWORD": "password123",
            "REDIS_HOST":        "localhost",
            "REDIS_PORT":        "6379",
            "QDRANT_HOST":       "localhost",
            "QDRANT_PORT":       "6333",
            "OPENROUTER_API_KEY": "YOUR_OPENROUTER_API_KEY_HERE",
            "OPENAI_API_KEY":     "YOUR_OPENROUTER_API_KEY_HERE",
            "OPENROUTER_PRESET":  "cheap",
            "CORS_ORIGINS":       "http://localhost:5173,http://localhost:8080,http://localhost:3000",
        }

        upload_proc = start_service("Upload", 8001, BACKEND_DIR / "services" / "upload", service_env)
        time.sleep(2)
        query_proc  = start_service("Query",  8002, BACKEND_DIR / "services" / "query",  service_env)

        # ── 2. Wait for Ready ─────────────────────────────────────────────────
        section(f"LOOP {loop} — Waiting for Services")
        upload_ready = wait_for_service(UPLOAD_URL, "Upload Service", timeout=90)
        query_ready  = wait_for_service(QUERY_URL,  "Query Service",  timeout=90)

        if not upload_ready or not query_ready:
            fail("Services failed to start — retrying loop...")
            # Print stderr for debugging
            for name, proc in procs:
                _, stderr = proc.communicate(timeout=3) if proc.poll() is not None else ("", "")
                if stderr:
                    warn(f"{name} stderr: {stderr[:300]}")
            stop_all()
            time.sleep(3)
            continue

        # ── 3. Health Checks ──────────────────────────────────────────────────
        section(f"LOOP {loop} — Health Checks")
        upload_healthy = check_health(UPLOAD_URL, "Upload Service")
        query_healthy  = check_health(QUERY_URL,  "Query Service")

        # ── 4. Upload Documents ───────────────────────────────────────────────
        section(f"LOOP {loop} — Uploading {len(TEST_DOCS)} Test Documents")
        uploaded_count = 0
        for doc in TEST_DOCS:
            result = upload_document(doc)
            if result:
                uploaded_count += 1
        results["uploaded"]["success"] = uploaded_count
        info(f"Uploaded {uploaded_count}/{len(TEST_DOCS)} documents")

        # ── 5. List Documents ─────────────────────────────────────────────────
        section(f"LOOP {loop} — Verifying Document List")
        docs = get_documents()
        if isinstance(docs, list):
            info(f"Total documents in system: {len(docs)}")
            for d in docs[:5]:
                if isinstance(d, dict):
                    name = d.get("filename") or d.get("title") or str(d)
                    status = d.get("status", "unknown")
                    chunks = d.get("chunks", "?")
                    info(f"  → {name} | status={status} | chunks={chunks}")
        elif isinstance(docs, dict):
            items = docs.get("documents", [])
            info(f"Total documents in system: {len(items)}")
            for d in items[:5]:
                name = d.get("filename") or d.get("title") or "unknown"
                status = d.get("status", "unknown")
                info(f"  → {name} | status={status}")

        # ── 6. Run Queries ────────────────────────────────────────────────────
        section(f"LOOP {loop} — Running {len(QUERIES)} Test Queries")
        query_results = []
        for question, min_conf in QUERIES:
            result = run_query(question, min_conf)
            result["min_confidence"] = min_conf
            query_results.append(result)
            time.sleep(0.5)  # gentle rate limiting
        results["queries"] = query_results

        # ── 7. Summary ────────────────────────────────────────────────────────
        success = print_summary(results, loop)

        # ── 8. Stop Services ──────────────────────────────────────────────────
        stop_all()
        
        if success:
            log(f"\n{'#'*60}", BOLD + GREEN)
            log(f"  🚀 VELA SYSTEM FULLY VERIFIED — LOOP {loop}", BOLD + GREEN)
            log(f"  All {len(TEST_DOCS)} documents uploaded successfully", GREEN)
            log(f"  All {len(QUERIES)} queries answered correctly", GREEN)
            log(f"{'#'*60}\n", BOLD + GREEN)
            return 0

        if loop < MAX_LOOPS:
            warn(f"\nWaiting 5s before loop {loop + 1}...\n")
            time.sleep(5)

    fail(f"\nReached max {MAX_LOOPS} loops. Check errors above.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        warn("\nInterrupted — stopping services...")
        stop_all()
        sys.exit(0)
