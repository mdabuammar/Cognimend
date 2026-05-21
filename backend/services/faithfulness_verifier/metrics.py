"""
RAG Quality Metrics — per-query metric computation and storage.
Logs retrieval metrics, citation metrics, and query intent classification.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rag_metrics")


# ─── Query intent classifier (rule-based, no LLM cost) ───────────────────────

_COMPARISON_PATTERNS = re.compile(
    r"\b(compare|comparison|difference|vs\.?|versus|contrast|"
    r"better|worse|more than|less than|which is|rank)\b",
    re.IGNORECASE,
)
_TEMPORAL_PATTERNS = re.compile(
    r"\b(when|since|before|after|during|timeline|history|"
    r"recently|latest|newest|oldest|year|month|date|changed)\b",
    re.IGNORECASE,
)
_MULTI_HOP_PATTERNS = re.compile(
    r"\b(and then|which also|related to|additionally|furthermore|"
    r"as well as|both|combine|how does .+ affect)\b",
    re.IGNORECASE,
)
_UNANSWERABLE_PATTERNS = re.compile(
    r"\b(quantum|philosophy|opinion|your (view|opinion|thoughts?)|"
    r"what do you (think|feel|believe)|i wonder|hypothetical)\b",
    re.IGNORECASE,
)
_POLICY_PATTERNS = re.compile(
    r"\b(policy|guideline|rule|regulation|procedure|process|"
    r"allowed|permitted|forbidden|required|mandatory|must)\b",
    re.IGNORECASE,
)
_SUMMARY_PATTERNS = re.compile(
    r"\b(summarize|summary|overview|brief|main points?|key (points?|ideas?)|tldr)\b",
    re.IGNORECASE,
)


def classify_query_intent(question: str) -> Dict[str, Any]:
    """
    Classify the intent and complexity of a query using rule-based patterns.

    Returns a dict with: intent, complexity_score, is_multi_hop, is_temporal,
    is_comparison, is_unanswerable.
    """
    q = question.strip()
    words = len(q.split())

    is_comparison = bool(_COMPARISON_PATTERNS.search(q))
    is_temporal = bool(_TEMPORAL_PATTERNS.search(q))
    is_multi_hop = bool(_MULTI_HOP_PATTERNS.search(q)) or (is_comparison and words > 20)
    is_unanswerable = bool(_UNANSWERABLE_PATTERNS.search(q))
    is_policy = bool(_POLICY_PATTERNS.search(q))
    is_summary = bool(_SUMMARY_PATTERNS.search(q))

    # Determine primary intent
    if is_unanswerable:
        intent = "unsupported_or_unanswerable"
    elif is_comparison:
        intent = "comparison"
    elif is_multi_hop:
        intent = "multi_hop"
    elif is_temporal:
        intent = "temporal"
    elif is_summary:
        intent = "summary"
    elif is_policy:
        intent = "policy_lookup"
    elif words <= 12:
        intent = "simple_fact"
    else:
        intent = "other"

    # Complexity score 0–1
    complexity = 0.2
    if words > 10:  complexity += 0.1
    if words > 20:  complexity += 0.1
    if is_multi_hop: complexity += 0.25
    if is_comparison: complexity += 0.2
    if is_temporal:  complexity += 0.1
    complexity = round(min(complexity, 1.0), 2)

    return {
        "intent": intent,
        "complexity_score": complexity,
        "is_multi_hop": is_multi_hop,
        "is_temporal": is_temporal,
        "is_comparison": is_comparison,
        "is_unanswerable": is_unanswerable,
    }


# ─── Retrieval metrics computation ───────────────────────────────────────────

def compute_retrieval_metrics(
    similarities: List[float],
    top_k: int,
    retrieval_latency_ms: int,
    low_sim_threshold: float = 0.35,
) -> Dict[str, Any]:
    """
    Compute retrieval quality metrics from a list of similarity scores.
    """
    if not similarities:
        return {
            "top1_similarity": 0.0,
            "top5_avg_similarity": 0.0,
            "top_k": top_k,
            "chunks_retrieved": 0,
            "zero_retrieval": True,
            "low_similarity": True,
            "retrieval_latency_ms": retrieval_latency_ms,
        }

    top1 = similarities[0]
    top5_avg = sum(similarities[:5]) / min(len(similarities), 5)
    zero_retrieval = len(similarities) == 0
    low_similarity = top1 < low_sim_threshold

    return {
        "top1_similarity": round(top1, 4),
        "top5_avg_similarity": round(top5_avg, 4),
        "top_k": top_k,
        "chunks_retrieved": len(similarities),
        "zero_retrieval": zero_retrieval,
        "low_similarity": low_similarity,
        "retrieval_latency_ms": retrieval_latency_ms,
    }


# ─── Citation metrics computation ────────────────────────────────────────────

def compute_citation_metrics(
    citations: List[Dict[str, Any]],
    verification_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Compute citation quality metrics.
    Uses claim verification results if available for accuracy.
    """
    total_citations = len(citations)

    if total_citations == 0:
        return {
            "total_citations": 0,
            "supported_citations": 0,
            "unsupported_citations": 0,
            "citation_support_score": 0.0,
            "wrong_citation_rate": 0.0,
            "missing_citation_rate": 1.0,
            "citation_coverage": 0.0,
        }

    # If we have claim verification, use it to assess citation quality
    if verification_results:
        supported_ev = {
            r.get("evidence_document_id")
            for r in verification_results
            if r.get("status") == "supported" and r.get("evidence_document_id")
        }
        contradicted_ev = {
            r.get("evidence_document_id")
            for r in verification_results
            if r.get("status") == "contradicted" and r.get("evidence_document_id")
        }

        cited_doc_ids = {c.get("document_id") for c in citations}
        supported_citations = len(cited_doc_ids & supported_ev)
        wrong_citations = len(cited_doc_ids & contradicted_ev)
        total_claims = len(verification_results)
        missing_rate = (
            sum(1 for r in verification_results
                if r.get("status") == "unsupported" and not r.get("evidence_chunk_id"))
            / total_claims
            if total_claims else 0.0
        )

        citation_support_score = supported_citations / total_citations if total_citations else 0.0
        wrong_citation_rate = wrong_citations / total_citations if total_citations else 0.0
        coverage = min(supported_citations / max(total_claims, 1), 1.0)
    else:
        # Fallback: use similarity scores as proxy
        sim_scores = [c.get("similarity", 0) for c in citations]
        avg_sim = sum(sim_scores) / len(sim_scores) if sim_scores else 0
        citation_support_score = round(avg_sim / 100.0, 3) if avg_sim > 1 else round(avg_sim, 3)
        wrong_citation_rate = 0.0
        missing_rate = 0.0
        coverage = citation_support_score
        supported_citations = total_citations
        wrong_citations = 0

    return {
        "total_citations": total_citations,
        "supported_citations": supported_citations,
        "unsupported_citations": total_citations - supported_citations,
        "citation_support_score": round(citation_support_score, 3),
        "wrong_citation_rate": round(wrong_citation_rate, 3),
        "missing_citation_rate": round(missing_rate, 3),
        "citation_coverage": round(coverage, 3),
    }


# ─── DB persistence helpers ──────────────────────────────────────────────────

async def store_retrieval_metrics(
    conn, workspace_id: str, query_id: int, metrics: Dict[str, Any]
) -> None:
    """Insert retrieval metrics row."""
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO retrieval_metrics
            (workspace_id, query_id, top1_similarity, top5_avg_similarity,
             top_k, chunks_retrieved, zero_retrieval, low_similarity, retrieval_latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                workspace_id,
                query_id,
                metrics["top1_similarity"],
                metrics["top5_avg_similarity"],
                metrics["top_k"],
                metrics["chunks_retrieved"],
                metrics["zero_retrieval"],
                metrics["low_similarity"],
                metrics["retrieval_latency_ms"],
            ),
        )
        conn.commit()
        cur.close()
    except Exception as exc:
        logger.error("store_retrieval_metrics: %s", exc)


async def store_citation_metrics(
    conn, workspace_id: str, query_id: int, metrics: Dict[str, Any]
) -> None:
    """Insert citation metrics row."""
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO citation_metrics
            (workspace_id, query_id, total_citations, supported_citations,
             unsupported_citations, citation_support_score, wrong_citation_rate,
             missing_citation_rate, citation_coverage)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                workspace_id,
                query_id,
                metrics["total_citations"],
                metrics["supported_citations"],
                metrics["unsupported_citations"],
                metrics["citation_support_score"],
                metrics["wrong_citation_rate"],
                metrics["missing_citation_rate"],
                metrics["citation_coverage"],
            ),
        )
        conn.commit()
        cur.close()
    except Exception as exc:
        logger.error("store_citation_metrics: %s", exc)


async def store_query_analysis(
    conn, workspace_id: str, query_id: int, analysis: Dict[str, Any]
) -> None:
    """Insert query analysis row."""
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO query_analysis
            (workspace_id, query_id, intent, complexity_score,
             is_multi_hop, is_temporal, is_comparison, is_unanswerable)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                workspace_id,
                query_id,
                analysis["intent"],
                analysis["complexity_score"],
                analysis["is_multi_hop"],
                analysis["is_temporal"],
                analysis["is_comparison"],
                analysis["is_unanswerable"],
            ),
        )
        conn.commit()
        cur.close()
    except Exception as exc:
        logger.error("store_query_analysis: %s", exc)


async def store_verification_summary(
    conn,
    workspace_id: str,
    query_id: int,
    summary_dict: Dict[str, Any],
) -> None:
    """Insert claim verification rows and answer_verification_summary row."""
    try:
        cur = conn.cursor()

        # Insert per-claim rows
        for claim in summary_dict.get("claims", []):
            cur.execute(
                """
                INSERT INTO claim_verifications
                (workspace_id, query_id, claim_text, status, confidence,
                 evidence_chunk_id, evidence_document_id, explanation, verifier_model)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    workspace_id,
                    query_id,
                    claim["claim"],
                    claim["status"],
                    claim["confidence"],
                    claim.get("evidence_chunk_id"),
                    claim.get("evidence_document_id"),
                    claim.get("explanation"),
                    claim.get("verifier_model"),
                ),
            )

        # Insert summary row
        cur.execute(
            """
            INSERT INTO answer_verification_summaries
            (workspace_id, query_id, total_claims, supported_claims,
             unsupported_claims, contradicted_claims, uncertain_claims,
             unsupported_claim_rate, contradicted_claim_rate, claim_support_rate,
             answer_faithfulness_score, verifier_status, verifier_latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                workspace_id,
                query_id,
                summary_dict["total_claims"],
                summary_dict["supported_claims"],
                summary_dict["unsupported_claims"],
                summary_dict["contradicted_claims"],
                summary_dict["uncertain_claims"],
                summary_dict["unsupported_claim_rate"],
                summary_dict["contradicted_claim_rate"],
                summary_dict["claim_support_rate"],
                summary_dict["answer_faithfulness_score"],
                summary_dict["verifier_status"],
                summary_dict["verifier_latency_ms"],
            ),
        )

        # Update query_events with faithfulness metrics
        cur.execute(
            """
            UPDATE query_events
            SET faithfulness_score     = %s,
                unsupported_claim_rate = %s,
                verification_status    = %s
            WHERE id = %s
            """,
            (
                summary_dict["answer_faithfulness_score"],
                summary_dict["unsupported_claim_rate"],
                summary_dict["verifier_status"],
                query_id,
            ),
        )

        conn.commit()
        cur.close()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error("store_verification_summary: %s", exc)
