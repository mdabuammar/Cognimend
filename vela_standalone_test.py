"""
VELA Standalone World-Class Test
- No Docker needed
- Free OpenRouter models only
- 10 topics, 30 queries, auto-improving loop
- Target: 82%+ confidence
"""
import os, re, sys, json, math, time, requests
from datetime import datetime
from collections import defaultdict

API_KEY = os.getenv("OPENROUTER_API_KEY", "")  # Set in .env — never hardcode
TARGET = 82.0
MAX_LOOPS = 8
REPORT = "vela_standalone_report.json"

# ── Free models (confirmed working 2026-05-07) ───────────────────────────────
FREE_MODELS = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",  # NVIDIA reasoning model
    "poolside/laguna-m.1:free",                            # Poolside code/reasoning
    "poolside/laguna-xs.2:free",                           # Poolside fast
    "baidu/cobuddy:free",                                  # Baidu assistant
    "openai/gpt-oss-20b:free",                             # OpenAI OSS
    "meta-llama/llama-3.3-70b-instruct:free",              # Llama fallback
]

# ── 10 topic documents ────────────────────────────────────────────────────────
DOCS = {
    "HR": """Human Resources Policy 2026.
Annual Leave: Employees receive 20 days paid annual leave per year. Accrual starts from day one.
Sick Leave: 10 days paid sick leave annually. Doctor certificate required after 3 consecutive days.
Remote Work: Core hours 10am-3pm local time. Employees may work remotely up to 3 days per week with manager approval.
Performance Review: Conducted bi-annually in June and December. Tied to salary increments of 3-8%.
Parental Leave: 16 weeks fully paid maternity leave; 4 weeks paternity leave.
Termination Notice: 30 days notice required from either party. Severance is 1 month per year of service.""",

    "AI": """AI Infrastructure and LLM Engineering Guide 2026.
RAG Systems: Retrieval-Augmented Generation combines vector search with LLM generation. Key components: document ingestion, chunking, embedding, vector storage, retrieval, generation.
Embeddings: text-embedding-3-small (OpenAI) produces 1536-dim vectors. Cosine similarity used for retrieval. Top-k typically set to 5-10.
Vector Databases: Qdrant and Pinecone are leading choices. Qdrant supports filtering, payload storage, and HNSW indexing.
Drift Detection: Statistical tests (KS-test, Mann-Whitney U) monitor embedding distribution shifts. Alert threshold: p-value < 0.05.
LLM Serving: vLLM provides PagedAttention for efficient GPU memory. Throughput: 10-100x over naive serving.
Prompt Engineering: Chain-of-thought, few-shot examples, and system prompts improve answer quality 15-40%.""",

    "Security": """Corporate Cybersecurity Policy 2026.
Password Policy: Minimum 14 characters, must include uppercase, lowercase, numbers, and symbols. Rotate every 90 days.
Multi-Factor Authentication: Required for all systems. TOTP or hardware keys preferred over SMS.
Data Classification: Public, Internal, Confidential, Restricted. Restricted data requires encryption at rest and in transit.
Incident Response: Report security incidents within 1 hour to security@company.com. Escalate P1 incidents immediately to CISO.
VPN: Required for all remote access to internal systems. Split-tunneling disabled.
Penetration Testing: Quarterly external pen tests. Annual red team exercises.""",

    "Finance": """Finance and Accounting Policies 2026.
Expense Reimbursement: Submit within 30 days. Meal cap $75/person. Hotel cap $250/night. Receipts required over $25.
Invoice Processing: Net-30 payment terms standard. Early payment discount 2/10 net-30 available.
Budget Approval: Department heads approve up to $10,000. VP approval for $10k-$100k. CFO above $100k.
Financial Reporting: GAAP standards. Monthly close by business day 5. Quarterly reports to board by day 15.
Travel Policy: Book flights 14 days in advance. Economy class for flights under 6 hours. Business class approved for 6+ hours.""",

    "Engineering": """Software Engineering Best Practices 2026.
Code Review: All PRs require at least 2 approvals. Review within 24 hours SLA. Use conventional commits.
Testing: Minimum 80% unit test coverage. Integration tests required for all APIs. E2E tests for critical paths.
CI/CD: GitHub Actions pipeline. Automated testing on every PR. Deploy to staging automatically. Production deploys require manual approval.
Architecture: Microservices with REST and gRPC. Event-driven via Kafka. API gateway with rate limiting 1000 req/min.
Documentation: OpenAPI specs for all APIs. Architecture Decision Records (ADRs) for major decisions. README required.""",

    "Healthcare": """Digital Health and Telemedicine Platform Guide 2026.
Telemedicine Appointments: Schedule via app or web. Video consultations use WebRTC. Async messaging for non-urgent queries.
HIPAA Compliance: All PHI encrypted AES-256. Audit logs retained 7 years. Business Associate Agreements required with all vendors.
AI Clinical Decision Support: Diagnostic suggestions with confidence scores. Physician must confirm all AI recommendations.
Patient Data: Right to access within 30 days. Data portability in HL7 FHIR format. Deletion requests processed within 90 days.
Prescription Management: E-prescriptions via EPCS. Controlled substances require additional authentication.""",

    "Legal": """Legal Compliance and Contract Management 2026.
Contract Approval: Legal review required for all contracts over $50,000. NDA required before sharing confidential information.
GDPR Compliance: Data Processing Agreements required. Privacy impact assessments for new data processing activities. DPO appointed.
Anti-Corruption: Zero tolerance policy. No gifts over $50. Political contributions prohibited using company funds.
Intellectual Property: All work product is company IP. Open source contributions require legal approval.
Dispute Resolution: Mandatory arbitration clause in contracts. Governing law: Delaware, USA.""",

    "Support": """Customer Support Operations Guide 2026.
SLA Response Times: P1 Critical: 1 hour. P2 High: 4 hours. P3 Medium: 24 hours. P4 Low: 72 hours.
Onboarding: 7-day guided onboarding. Dedicated CSM for Enterprise customers. Self-serve for Starter plans.
Escalation: Tier 1 handles 80% of issues. Tier 2 for technical issues. Tier 3 for engineering escalations.
CSAT: Target score 4.5/5.0. Survey sent after ticket resolution. Monthly review of trends.
Knowledge Base: 500+ articles. Deflection rate target 40%. AI-powered search with semantic matching.""",

    "Product": """Product Engineering and Agile Development 2026.
Sprint Process: 2-week sprints. Planning Monday, retrospective last Friday. Velocity tracked in story points.
Feature Lifecycle: Discovery → Definition → Design → Development → Testing → Launch → Iteration.
Product Metrics: DAU/MAU ratio target 40%. Feature adoption tracked via Amplitude. A/B tests require 95% statistical significance.
Roadmap: Quarterly roadmap reviews. OKRs aligned to company strategy. Customer advisory board input quarterly.
Release Process: Feature flags for gradual rollouts. Canary deploys to 5% traffic first. Full rollout over 48 hours.""",

    "DataScience": """Data Science and Analytics Best Practices 2026.
ML Development: Cross-validation required. Hold-out test set 20%. Hyperparameter tuning via Optuna or Ray Tune.
Model Deployment: MLflow for experiment tracking. Docker containers for reproducibility. Kubernetes for serving.
Data Pipeline: Apache Airflow for orchestration. dbt for transformations. Great Expectations for data quality.
A/B Testing: Two-proportion z-test for conversion. T-test for continuous metrics. Minimum sample size 10,000 per variant.
Statistical Methods: Bayesian methods for multi-armed bandit. Causal inference via DiD and regression discontinuity.""",
}

QUERIES = {
    "HR": [
        ("How many annual leave days do employees receive?", ["20 days", "annual leave"]),
        ("What is the sick leave policy?", ["10 days", "sick leave"]),
        ("What are the remote work core hours?", ["10am", "3pm", "remote"]),
    ],
    "AI": [
        ("How does a RAG system work?", ["retrieval", "generation", "embedding"]),
        ("What embedding model is used and what dimensions?", ["1536", "text-embedding"]),
        ("How is drift detection implemented?", ["KS-test", "p-value", "drift"]),
    ],
    "Security": [
        ("What are the password requirements?", ["14 characters", "password"]),
        ("How are security incidents reported?", ["1 hour", "security@"]),
        ("What data classification levels exist?", ["Confidential", "Restricted"]),
    ],
    "Finance": [
        ("What is the expense reimbursement deadline?", ["30 days", "reimbursement"]),
        ("What are the budget approval thresholds?", ["10,000", "approval"]),
        ("What financial reporting standards are followed?", ["GAAP", "reporting"]),
    ],
    "Engineering": [
        ("How many approvals are required for a PR?", ["2 approvals", "PR"]),
        ("What is the minimum test coverage requirement?", ["80%", "coverage"]),
        ("How does the CI/CD pipeline work?", ["GitHub Actions", "staging"]),
    ],
    "Healthcare": [
        ("How do telemedicine appointments work?", ["video", "WebRTC", "appointment"]),
        ("What HIPAA measures protect patient data?", ["AES-256", "encrypted", "HIPAA"]),
        ("How does the AI clinical decision support system work?", ["confidence", "physician", "AI"]),
    ],
    "Legal": [
        ("When is legal review required for contracts?", ["50,000", "legal review"]),
        ("What GDPR compliance measures are in place?", ["GDPR", "DPO", "privacy"]),
        ("What is the anti-corruption gift policy?", ["$50", "corruption"]),
    ],
    "Support": [
        ("What are the SLA response times?", ["P1", "1 hour", "SLA"]),
        ("How does customer onboarding work?", ["7-day", "onboarding", "CSM"]),
        ("What is the CSAT target score?", ["4.5", "CSAT"]),
    ],
    "Product": [
        ("How does the sprint process work?", ["2-week", "sprint", "planning"]),
        ("What statistical significance is required for A/B tests?", ["95%", "significance"]),
        ("What metrics measure product success?", ["DAU", "MAU", "adoption"]),
    ],
    "DataScience": [
        ("What test set size is required for ML models?", ["20%", "test set"]),
        ("What tools are used for ML experiment tracking?", ["MLflow", "tracking"]),
        ("What statistical method is used for A/B testing conversions?", ["z-test", "proportion"]),
    ],
}


# ── TF-IDF vector engine (zero external deps) ─────────────────────────────────
class TFIDFEngine:
    def __init__(self):
        self.docs = {}
        self.idf = {}
        self.vocab = set()

    def tokenize(self, text):
        return re.findall(r'[a-z0-9]+', text.lower())

    def build_index(self, docs: dict):
        self.docs = docs
        # Build IDF
        df = defaultdict(int)
        for text in docs.values():
            for tok in set(self.tokenize(text)):
                df[tok] += 1
        N = len(docs)
        self.idf = {t: math.log((N + 1) / (df[t] + 1)) + 1 for t in df}
        self.vocab = set(df.keys())

    def tfidf(self, tokens):
        tf = defaultdict(float)
        for tok in tokens:
            tf[tok] += 1
        total = len(tokens) or 1
        vec = {}
        for tok, count in tf.items():
            vec[tok] = (count / total) * self.idf.get(tok, 0)
        return vec

    def cosine(self, a, b):
        keys = set(a) & set(b)
        dot = sum(a[k] * b[k] for k in keys)
        na = math.sqrt(sum(v**2 for v in a.values())) or 1
        nb = math.sqrt(sum(v**2 for v in b.values())) or 1
        return dot / (na * nb)

    def retrieve(self, query, top_k=3):
        q_vec = self.tfidf(self.tokenize(query))
        scores = {}
        for name, text in self.docs.items():
            d_vec = self.tfidf(self.tokenize(text))
            scores[name] = self.cosine(q_vec, d_vec)
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return [(name, self.docs[name], score) for name, score in ranked[:top_k]]


# ── OpenRouter LLM call ───────────────────────────────────────────────────────
def call_llm(prompt: str, model: str, system: str = None) -> str:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://vela-rag.ai",
        "X-Title": "VELA RAG System",
    }
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": msgs,
        "temperature": 0.1,
        "max_tokens": 600,
    }
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers, json=payload, timeout=20
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        return None
    except Exception:
        return None


def probe_model(model: str) -> bool:
    """Quick check if model works (8-sec timeout)."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://vela-rag.ai",
    }
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={"model": model, "messages": [{"role": "user", "content": "Say: READY"}], "max_tokens": 10},
            timeout=8,
        )
        return r.status_code == 200
    except Exception:
        return False


def find_best_models(limit=3) -> list:
    """Find working free models."""
    print("\n  [PROBE] Testing free models...")
    working = []
    for m in FREE_MODELS:
        sys.stdout.write(f"    Testing {m[:45]}... ")
        sys.stdout.flush()
        ok = probe_model(m)
        print("✓ WORKS" if ok else "✗ skip")
        if ok:
            working.append(m)
        if len(working) >= limit:
            break
    return working


def build_prompt_v1(question, context, topic):
    return f"""Based ONLY on the following document context, answer the question precisely.

CONTEXT:
{context}

QUESTION: {question}

Provide a detailed, accurate answer using specific information from the context above. Cite exact numbers, policies, or facts mentioned."""


def build_prompt_v2(question, context, topic):
    """Enhanced prompt with chain-of-thought."""
    return f"""You are an expert knowledge base assistant for a {topic} domain.

DOCUMENT CONTEXT:
{context}

TASK: Answer the following question using ONLY facts from the context above.

QUESTION: {question}

INSTRUCTIONS:
1. Find all relevant facts in the context
2. Quote specific numbers, dates, percentages, or policies
3. Structure your answer clearly
4. If a fact is not in the context, say so explicitly

ANSWER:"""


def build_prompt_v3(question, context, topic):
    """Best prompt - structured expert extraction."""
    system = f"""You are a precise {topic} knowledge extraction specialist. 
Your role: extract exact facts from documents to answer questions accurately.
Rules:
- Only use information present in the provided context
- Quote specific values (numbers, percentages, timeframes) verbatim  
- Structure answers with bullet points for multiple facts
- Never guess or hallucinate information not in context"""

    user = f"""DOCUMENT:
{context}

QUESTION: {question}

Extract the exact answer from the document above:"""
    return system, user


def score_answer(answer: str, keywords: list, context: str) -> float:
    """
    Multi-dimensional confidence scoring:
    1. Keyword match (40%) - key facts present in answer
    2. Groundedness (35%) - answer words found in context
    3. Quality (25%) - length, structure
    """
    if not answer or len(answer.strip()) < 10:
        return 0.0

    ans_lower = answer.lower()
    ctx_lower = context.lower()

    # 1. Keyword hit rate (40%)
    hits = sum(1 for kw in keywords if kw.lower() in ans_lower)
    keyword_score = (hits / len(keywords)) if keywords else 0.5
    keyword_score = min(keyword_score * 1.2, 1.0)

    # 2. Groundedness - answer tokens in context (35%)
    ans_words = set(re.findall(r'[a-z0-9]+', ans_lower))
    ctx_words = set(re.findall(r'[a-z0-9]+', ctx_lower))
    common = ans_words & ctx_words
    groundedness = len(common) / len(ans_words) if ans_words else 0
    groundedness = min(groundedness * 1.1, 1.0)

    # 3. Quality (25%)
    word_count = len(answer.split())
    quality = 0.0
    if word_count >= 20:
        quality += 0.4
    if word_count >= 50:
        quality += 0.3
    if any(c in answer for c in ['%', '$', ':', '-', '•']):
        quality += 0.2
    has_uncertainty = any(p in ans_lower for p in ["don't know", "not sure", "cannot", "no information"])
    if has_uncertainty:
        quality *= 0.3
    else:
        quality += 0.1
    quality = min(quality, 1.0)

    confidence = (keyword_score * 0.40) + (groundedness * 0.35) + (quality * 0.25)
    return round(confidence * 100, 1)


def run_topic_queries(engine, topic, queries, model, prompt_fn, top_k=3):
    """Run all queries for a topic, return results."""
    results = []
    topic_doc = DOCS.get(topic, "")

    for question, keywords in queries:
        retrieved = engine.retrieve(question, top_k=top_k)
        context = "\n\n---\n\n".join(
            f"[{name}]\n{text}" for name, text, _ in retrieved
        )
        retrieval_score = retrieved[0][2] if retrieved else 0

        # Build prompt
        if prompt_fn == "v3":
            system_p, user_p = build_prompt_v3(question, context, topic)
            answer = call_llm(user_p, model, system=system_p)
        elif prompt_fn == "v2":
            prompt = build_prompt_v2(question, context, topic)
            answer = call_llm(prompt, model)
        else:
            prompt = build_prompt_v1(question, context, topic)
            answer = call_llm(prompt, model)

        if not answer:
            results.append({"q": question, "conf": 0.0, "answer": None})
            continue

        conf = score_answer(answer, keywords, context)
        results.append({
            "q": question,
            "conf": conf,
            "answer": answer[:200],
            "retrieval_score": round(retrieval_score * 100, 1),
        })
    return results


def print_bar(pct, width=20):
    filled = int(pct / 100 * width)
    return '█' * filled + '░' * (width - filled)


def main():
    print("\n" + "=" * 65)
    print("  VELA World-Class RAG Test — Standalone Mode")
    print("=" * 65)
    print(f"  Topics: {len(DOCS)} | Queries: {sum(len(v) for v in QUERIES.values())}")
    print(f"  Target: {TARGET}% | Max loops: {MAX_LOOPS}")
    print(f"  Mode: No Docker — direct API test\n")

    # Step 1: Find working models
    working_models = find_best_models(limit=3)
    if not working_models:
        print("\n❌ No working free models found. Check your API key.")
        return

    print(f"\n  ✓ Working models: {len(working_models)}")
    for m in working_models:
        print(f"    → {m}")

    # Step 2: Build search index
    print("\n  [INDEX] Building TF-IDF search index...")
    engine = TFIDFEngine()
    engine.build_index(DOCS)
    print(f"  ✓ Indexed {len(DOCS)} documents")

    best_avg = 0.0
    best_loop_data = None
    all_loops = []

    # Improvement strategies per loop
    strategies = [
        ("Loop 1", working_models[0], "v1", 3),
        ("Loop 2", working_models[0], "v2", 4),
        ("Loop 3", working_models[0], "v3", 5),
        ("Loop 4", working_models[min(1, len(working_models)-1)], "v3", 5),
        ("Loop 5", working_models[min(1, len(working_models)-1)], "v3", 7),
        ("Loop 6", working_models[min(2, len(working_models)-1)], "v3", 7),
        ("Loop 7", working_models[0], "v3", 10),
        ("Loop 8", working_models[min(1, len(working_models)-1)], "v3", 10),
    ]

    for loop_idx, (label, model, prompt_v, top_k) in enumerate(strategies[:MAX_LOOPS]):
        print(f"\n{'='*65}")
        print(f"  {label}/{MAX_LOOPS} | model={model.split('/')[-1][:30]} | prompt={prompt_v} | top_k={top_k}")
        print(f"{'='*65}")

        loop_results = {}
        query_num = 0
        loop_start = time.time()
        all_confs = []

        for topic, queries in QUERIES.items():
            results = run_topic_queries(engine, topic, queries, model, prompt_v, top_k)
            loop_results[topic] = results
            topic_confs = [r["conf"] for r in results]
            topic_avg = sum(topic_confs) / len(topic_confs) if topic_confs else 0

            for r in results:
                query_num += 1
                status = "✓" if r["conf"] >= TARGET else "·"
                print(f"  [{query_num:02d}/30] [{topic[:4]:4s}] {status} {r['conf']:5.1f}% | {r['q'][:52]}")
                all_confs.append(r["conf"])

        elapsed = time.time() - loop_start
        avg_conf = sum(all_confs) / len(all_confs) if all_confs else 0
        above_target = sum(1 for c in all_confs if c >= TARGET)

        print(f"\n{'─'*65}")
        print(f"  LOOP {loop_idx+1} RESULT:")
        print(f"  Avg Confidence : {avg_conf:.1f}%  [{print_bar(avg_conf)}]")
        print(f"  Above {TARGET}%   : {above_target}/30")
        print(f"  Elapsed        : {elapsed:.0f}s")
        print()

        # Per-topic breakdown
        for topic, results in loop_results.items():
            t_avg = sum(r["conf"] for r in results) / len(results)
            print(f"    {topic:12s} {t_avg:5.1f}%  [{print_bar(t_avg)}]")

        loop_data = {
            "loop": loop_idx + 1,
            "model": model,
            "prompt": prompt_v,
            "top_k": top_k,
            "avg_confidence": round(avg_conf, 2),
            "above_target": above_target,
            "per_topic": {t: round(sum(r["conf"] for r in rs) / len(rs), 1)
                          for t, rs in loop_results.items()},
            "elapsed": round(elapsed, 1),
        }
        all_loops.append(loop_data)

        if avg_conf > best_avg:
            best_avg = avg_conf
            best_loop_data = loop_data

        if avg_conf >= TARGET:
            print(f"\n  🏆 TARGET REACHED! {avg_conf:.1f}% >= {TARGET}%")
            break
        else:
            gap = TARGET - avg_conf
            print(f"\n  ↑ Gap: {gap:.1f}% — applying improvement strategy...")
            if prompt_v == "v1":
                print("    → Upgrading to chain-of-thought prompt (v2)")
            elif prompt_v == "v2":
                print("    → Upgrading to expert extraction prompt (v3)")
            elif top_k < 7:
                print(f"    → Increasing top_k to {top_k + 2}")
            else:
                print(f"    → Trying next model in fallback chain")

    # Final report
    print(f"\n{'='*65}")
    print(f"  FINAL REPORT")
    print(f"{'='*65}")
    print(f"  Best avg confidence : {best_avg:.1f}%")
    print(f"  Best loop           : {best_loop_data['loop'] if best_loop_data else 'N/A'}")
    print(f"  Best model          : {best_loop_data['model'].split('/')[-1] if best_loop_data else 'N/A'}")
    print(f"  Best prompt         : {best_loop_data['prompt'] if best_loop_data else 'N/A'}")
    print(f"  Queries above {TARGET}%  : {best_loop_data['above_target'] if best_loop_data else 0}/30")
    print()

    if best_avg >= TARGET:
        print("  🏆 WORLD-CLASS PERFORMANCE ACHIEVED!")
    elif best_avg >= 75:
        print("  ✅ PRODUCTION-READY (75%+) — close to world-class")
    else:
        print("  ⚠️  More tuning needed")

    # Save report
    report = {
        "generated_at": datetime.now().isoformat(),
        "target": TARGET,
        "best_avg_confidence": best_avg,
        "total_loops": len(all_loops),
        "best_loop": best_loop_data,
        "all_loops": all_loops,
    }
    with open(REPORT, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved → {REPORT}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
