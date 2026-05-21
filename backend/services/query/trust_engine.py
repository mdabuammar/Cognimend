from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SUPPORT_STATUSES = ("supports", "partial", "weak", "irrelevant", "contradicted")
FRESHNESS_LABELS = ("latest", "recent", "older", "unknown")

_STOPWORDS = {
    "about", "after", "again", "against", "also", "because", "before", "being",
    "between", "could", "document", "documents", "from", "have", "into", "more",
    "only", "other", "should", "source", "that", "their", "there", "these",
    "this", "those", "with", "would", "your", "answer", "based", "context",
}


@dataclass
class TrustChunk:
    document_id: int
    document_title: str
    chunk_id: str
    text: str
    similarity: float = 0.0
    page_number: Optional[int] = None
    uploaded_at: Optional[str] = None
    document_created_at: Optional[str] = None
    document_updated_at: Optional[str] = None


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, default=str) if not isinstance(value, str) else value
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def normalize_score(score: Optional[float]) -> float:
    if score is None:
        return 0.0
    try:
        val = float(score)
    except (TypeError, ValueError):
        return 0.0
    if val > 1:
        val = val / 100.0
    return max(0.0, min(val, 1.0))


def extract_claims_light(answer: str) -> List[str]:
    clean = re.sub(r"\[[^\]]{0,40}\]", "", answer or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])|\n+", clean)
    claims = []
    for part in parts:
        item = part.strip(" -•\t")
        if len(item) >= 12 and not re.match(r"^(based on|according to|here)", item, re.I):
            claims.append(item)
    return claims[:8]


def keyword_set(text: str) -> set[str]:
    words = {w.lower() for w in re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b", text or "")}
    return {w for w in words if w not in _STOPWORDS}


def fact_tokens(text: str) -> set[str]:
    return set(re.findall(r"\b\d+(?:\.\d+)?%?\b|\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b", text or ""))


def lexical_overlap(a: str, b: str) -> float:
    a_words = keyword_set(a)
    if not a_words:
        return 0.0
    b_words = keyword_set(b)
    return len(a_words & b_words) / len(a_words)


def _has_numeric_contradiction(claim: str, evidence: str) -> bool:
    claim_nums = fact_tokens(claim)
    evidence_nums = fact_tokens(evidence)
    if not claim_nums or not evidence_nums:
        return False
    overlap = lexical_overlap(re.sub(r"\d+", "", claim), re.sub(r"\d+", "", evidence))
    return overlap >= 0.25 and claim_nums.isdisjoint(evidence_nums)


def deterministic_citation_verifications(
    answer: str,
    chunks: Sequence[TrustChunk],
    claim_verifications: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[float, str, List[Dict[str, Any]], List[Tuple[str, TrustChunk]]]:
    claims = [c.get("claim", "") for c in claim_verifications or [] if c.get("claim")] or extract_claims_light(answer)
    if not chunks:
        return 0.0, "weak", [], []
    if not claims:
        claims = [answer]

    verifications: List[Dict[str, Any]] = []
    uncertain: List[Tuple[str, TrustChunk]] = []

    for idx, chunk in enumerate(chunks):
        related: List[str] = []
        best_score = 0.0
        status = "irrelevant"
        explanation = "This source does not clearly support the answer."

        for claim in claims:
            lex = lexical_overlap(claim, chunk.text)
            sim = normalize_score(chunk.similarity)
            number_overlap = 1.0 if fact_tokens(claim) and not fact_tokens(claim).isdisjoint(fact_tokens(chunk.text)) else 0.0
            score = min(1.0, lex * 0.65 + sim * 0.25 + number_overlap * 0.10)

            if _has_numeric_contradiction(claim, chunk.text):
                score = max(score, 0.12)
                if score >= best_score:
                    best_score = score
                    status = "contradicted"
                    related = [claim]
                    explanation = "This source appears to state a different value for the same fact."
                continue

            if score > best_score:
                best_score = score
                related = [claim] if lex >= 0.15 else []

        if status != "contradicted":
            if best_score >= 0.72:
                status = "supports"
                explanation = "The cited source directly supports the related answer claim."
            elif best_score >= 0.48:
                status = "partial"
                explanation = "The cited source supports part of the answer, but not every detail."
                if related:
                    uncertain.append((related[0], chunk))
            elif best_score >= 0.25:
                status = "weak"
                explanation = "The cited source is related but weakly supports the answer."
                if related:
                    uncertain.append((related[0], chunk))
            else:
                status = "irrelevant"

        verifications.append({
            "citation_id": f"citation-{idx + 1}",
            "document_id": str(chunk.document_id),
            "chunk_id": chunk.chunk_id,
            "page_number": chunk.page_number,
            "related_claims": related,
            "support_status": status,
            "support_score": round(best_score, 3),
            "explanation": explanation,
        })

    if not verifications:
        return 0.0, "weak", [], uncertain
    avg = sum(v["support_score"] for v in verifications) / len(verifications)
    contradicted_penalty = 0.2 if any(v["support_status"] == "contradicted" for v in verifications) else 0.0
    score = round(max(0.0, min(avg - contradicted_penalty, 1.0)), 3)
    label = "strong" if score >= 0.72 else "partial" if score >= 0.45 else "weak"
    return score, label, verifications, uncertain[:4]


def detect_conflict_heuristic(chunks: Sequence[TrustChunk]) -> List[Tuple[TrustChunk, TrustChunk, str]]:
    pairs: List[Tuple[TrustChunk, TrustChunk, str]] = []
    policy_terms = {"refund", "return", "leave", "vacation", "remote", "work", "price", "cost", "fee", "deadline", "warranty", "retention", "notice"}
    opposing_terms = [("allowed", "prohibited"), ("permitted", "forbidden"), ("eligible", "ineligible"), ("required", "optional"), ("yes", "no")]

    for i, a in enumerate(chunks):
        for b in chunks[i + 1:]:
            if a.document_id == b.document_id:
                continue
            words_a = keyword_set(a.text)
            words_b = keyword_set(b.text)
            topic_terms = sorted((words_a & words_b) & policy_terms)
            shared = words_a & words_b
            if not topic_terms and len(shared) < 5:
                continue
            topic = topic_terms[0] if topic_terms else "policy"
            nums_a = fact_tokens(a.text)
            nums_b = fact_tokens(b.text)
            if nums_a and nums_b and nums_a.isdisjoint(nums_b):
                pairs.append((a, b, topic))
                continue
            lower_a = a.text.lower()
            lower_b = b.text.lower()
            for left, right in opposing_terms:
                if ((left in lower_a and right in lower_b) or (right in lower_a and left in lower_b)) and len(shared) >= 3:
                    pairs.append((a, b, topic))
                    break
    return pairs[:4]


def build_conflict_source(chunk: TrustChunk, claim: str = "") -> Dict[str, Any]:
    return {
        "document_id": str(chunk.document_id),
        "document_title": chunk.document_title,
        "page_number": chunk.page_number,
        "claim": claim or _short_claim(chunk.text),
        "uploaded_at": chunk.uploaded_at,
        "snippet": _snippet(chunk.text),
    }


def _short_claim(text: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", (text or "").strip())[0]
    return sentence[:160]


def _snippet(text: str, limit: int = 220) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    return compact[:limit] + ("..." if len(compact) > limit else "")


def evidence_gap_from_signals(
    question: str,
    retrieved_count: int,
    similarities: Sequence[float],
    citation_truth_score: Optional[float],
    unsupported_claim_rate: Optional[float],
    strict_refusal: bool,
) -> Tuple[bool, str, List[str], List[str]]:
    reasons = []
    top_similarity = max([normalize_score(s) for s in similarities], default=0.0)
    if retrieved_count == 0:
        reasons.append("No relevant source chunks were retrieved.")
    if retrieved_count > 0 and top_similarity < 0.35:
        reasons.append("The best retrieved source has a weak match to the question.")
    if citation_truth_score is not None and citation_truth_score < 0.45:
        reasons.append("The cited sources do not strongly support the answer.")
    if unsupported_claim_rate is not None and unsupported_claim_rate >= 0.5:
        reasons.append("Most answer claims could not be verified from the retrieved context.")
    if strict_refusal:
        reasons.append("Strict Evidence Mode refused the answer because source support was missing.")

    detected = bool(reasons)
    if not detected:
        return False, "", [], []

    missing = [
        "A source passage that directly answers the question.",
        "Clear facts, dates, values, or policy language relevant to the request.",
    ]
    if "who" in question.lower() or "which" in question.lower():
        missing.append("A document naming the specific person, entity, or item requested.")

    actions = [
        "Upload a more relevant document.",
        "Reprocess failed documents.",
        "Ask a more specific question.",
    ]
    return True, " ".join(reasons), missing[:3], actions


def parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def apply_freshness(chunks: Sequence[TrustChunk], conflict_detected: bool) -> Tuple[Dict[str, Dict[str, Any]], Optional[str], Optional[str]]:
    dated: List[Tuple[datetime, TrustChunk]] = []
    upload_dated: List[Tuple[datetime, TrustChunk]] = []
    enriched: Dict[str, Dict[str, Any]] = {}
    for chunk in chunks:
        metadata_date = parse_datetime(chunk.document_updated_at) or parse_datetime(chunk.document_created_at)
        upload_date = parse_datetime(chunk.uploaded_at)
        key = chunk.chunk_id
        if metadata_date:
            dated.append((metadata_date, chunk))
        elif upload_date:
            upload_dated.append((upload_date, chunk))
        enriched[key] = {
            "source_freshness_label": "unknown",
            "is_latest_relevant_source": False,
            "uploaded_at": chunk.uploaded_at,
            "document_created_at": chunk.document_created_at,
            "document_updated_at": chunk.document_updated_at,
        }

    using_upload_fallback = False
    if not dated:
        dated = upload_dated
        using_upload_fallback = True
        if not dated:
            return enriched, "Source date is unknown, so freshness could not be verified.", None

    newest_date = max(d[0] for d in dated)
    latest_source_id = None
    for dt, chunk in dated:
        age_days = max((newest_date - dt).days, 0)
        if dt == newest_date and not using_upload_fallback:
            label = "latest"
            latest_source_id = str(chunk.document_id)
            latest = True
        elif age_days <= 90:
            label = "recent"
            latest = False
        else:
            label = "older"
            latest = False
        enriched[chunk.chunk_id].update({
            "source_freshness_label": label,
            "is_latest_relevant_source": latest,
        })

    has_older = any(v["source_freshness_label"] == "older" for v in enriched.values())
    warning = None
    if using_upload_fallback:
        warning = "Document dates are unavailable; freshness is based only on upload time."
    if conflict_detected and has_older:
        warning = "Older and newer retrieved sources may disagree. Review the latest source before relying on this answer."
    return enriched, warning, latest_source_id
