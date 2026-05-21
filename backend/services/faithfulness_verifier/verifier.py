"""
Faithfulness Verifier — Core Engine
=====================================
Extracts claims from LLM answers, matches each claim to retrieved evidence,
verifies support status, and rewrites the answer to remove unsupported claims.

Works as a Python module imported by the Query service — NOT a separate HTTP
service — to keep latency bounded and avoid an extra network hop.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("faithfulness_verifier")

# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    """Represents a retrieved document chunk."""
    chunk_id: str
    document_id: int
    title: str
    text: str
    similarity: float = 0.0


@dataclass
class ClaimVerificationResult:
    claim: str
    status: str                      # supported | unsupported | contradicted | uncertain
    confidence: float = 0.0
    evidence_chunk_id: Optional[str] = None
    evidence_document_id: Optional[int] = None
    explanation: str = ""
    verifier_model: str = ""


@dataclass
class VerificationSummary:
    answer_id: str
    workspace_id: str
    query_id: Optional[int]
    claims: List[ClaimVerificationResult] = field(default_factory=list)
    unsupported_claim_rate: float = 0.0
    contradicted_claim_rate: float = 0.0
    claim_support_rate: float = 0.0
    answer_faithfulness_score: float = 0.0
    verifier_status: str = "ok"       # ok | failed | skipped | timeout
    verifier_latency_ms: int = 0


# ─── Config ───────────────────────────────────────────────────────────────────

MAX_CLAIMS_PER_ANSWER = 8
VERIFIER_TIMEOUT_SECONDS = 12
LOW_SIMILARITY_THRESHOLD = 0.35
HIGH_UNSUPPORTED_THRESHOLD = 0.5    # 50%+ unsupported → weak answer warning
ALL_UNSUPPORTED_THRESHOLD = 0.85    # 85%+ unsupported → full abstain


# ─── Claim extraction ─────────────────────────────────────────────────────────

# Patterns that mark non-factual filler sentences
_FILLER_PATTERNS = re.compile(
    r"^("
    r"based on (the|your|our|provided).*|"
    r"(in|according to) (the|your|our) (context|document|information|sources?).*|"
    r"(i hope|i trust|feel free|let me know|please note|note that).*|"
    r"(here is|here are|below is|below are|the following).*|"
    r"(this (is|was)|these (are|were)) (a|an|the)?.*|"
    r"(certainly|absolutely|of course|sure).*|"
    r"(thank you|thanks).*|"
    r"(in summary|in conclusion|to summarise|to summarize).*"
    r")",
    re.IGNORECASE,
)

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')


def extract_claims(answer: str) -> List[str]:
    """
    Split an answer into atomic factual claims.

    Ignores greetings, filler text, and formatting sentences.
    Returns at most MAX_CLAIMS_PER_ANSWER claims.
    """
    # Remove markdown formatting
    clean = re.sub(r"\*\*|__|\*|_|`+|#{1,6}\s", "", answer)
    # Remove citation markers like [1], [Doc], etc.
    clean = re.sub(r"\[[^\]]{0,30}\]", "", clean)
    # Normalize whitespace
    clean = " ".join(clean.split())

    raw_sentences = _SENTENCE_SPLIT.split(clean)

    claims = []
    for s in raw_sentences:
        s = s.strip()
        if len(s) < 15:
            continue
        if _FILLER_PATTERNS.match(s):
            continue
        # Split compound sentences joined by "and" if they are long
        if " and " in s and len(s) > 120:
            parts = [p.strip() for p in s.split(" and ", 1)]
            claims.extend([p for p in parts if len(p) > 14])
        else:
            claims.append(s)

    return claims[:MAX_CLAIMS_PER_ANSWER]


# ─── Hybrid evidence matching ─────────────────────────────────────────────────

def _lexical_overlap(claim: str, chunk_text: str) -> float:
    """Simple word overlap ratio between claim and chunk."""
    claim_words = set(re.findall(r"\b\w{3,}\b", claim.lower()))
    chunk_words = set(re.findall(r"\b\w{3,}\b", chunk_text.lower()))
    if not claim_words:
        return 0.0
    return len(claim_words & chunk_words) / len(claim_words)


def match_claim_to_evidence(claim: str, chunks: List[Chunk]) -> List[Chunk]:
    """
    Return up to 3 chunks most relevant to the given claim.
    Uses lexical overlap + retrieval similarity as a combined score.
    """
    if not chunks:
        return []

    scored = []
    for chunk in chunks:
        lex = _lexical_overlap(claim, chunk.text)
        # Blend lexical score with Qdrant similarity
        combined = lex * 0.6 + (chunk.similarity / 100.0 if chunk.similarity > 1 else chunk.similarity) * 0.4
        scored.append((combined, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:3] if scored[0][0] > 0.05]


# ─── LLM-based claim verifier ─────────────────────────────────────────────────

_VERIFY_PROMPT = """\
You are a faithfulness verifier. Your only job is to check whether the claim is directly \
supported by the provided evidence. Do NOT use any outside knowledge.

CLAIM: {claim}

EVIDENCE:
{evidence_text}

Respond with ONLY valid JSON in this exact format:
{{
  "status": "supported" | "unsupported" | "contradicted" | "uncertain",
  "confidence": <float 0.0–1.0>,
  "explanation": "<one sentence>"
}}

Rules:
- supported: evidence clearly and directly supports the claim.
- unsupported: evidence does not mention or cannot confirm the claim.
- contradicted: evidence says the opposite.
- uncertain: evidence is partially relevant but insufficient to decide.
"""


async def _call_verifier_llm(
    claim: str,
    evidence_chunks: List[Chunk],
    openrouter_client,
    model_override: Optional[str] = None,
) -> Tuple[str, float, str]:
    """
    Call the LLM verifier. Returns (status, confidence, explanation).
    Falls back to 'uncertain' on any error.
    """
    evidence_text = "\n\n".join(
        f"[Chunk {i+1} | Doc: {c.document_id}]:\n{c.text[:600]}"
        for i, c in enumerate(evidence_chunks)
    )
    prompt = _VERIFY_PROMPT.format(claim=claim, evidence_text=evidence_text)

    for attempt in range(2):
        try:
            result = await asyncio.wait_for(
                openrouter_client.generate_answer(
                    question=prompt,
                    context="",
                    system_prompt=(
                        "You are a strict faithfulness verifier. Output ONLY valid JSON. "
                        "Never add commentary outside the JSON object."
                    ),
                ),
                timeout=VERIFIER_TIMEOUT_SECONDS,
            )
            raw = result.get("answer", "").strip()

            # Extract JSON block if wrapped in markdown
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not json_match:
                logger.warning("Verifier: no JSON found in response (attempt %d)", attempt + 1)
                continue

            parsed = json.loads(json_match.group())
            status = parsed.get("status", "uncertain")
            if status not in ("supported", "unsupported", "contradicted", "uncertain"):
                status = "uncertain"
            confidence = float(parsed.get("confidence", 0.5))
            explanation = str(parsed.get("explanation", ""))
            return status, min(max(confidence, 0.0), 1.0), explanation

        except asyncio.TimeoutError:
            logger.warning("Verifier LLM timeout (attempt %d)", attempt + 1)
            break
        except json.JSONDecodeError:
            logger.warning("Verifier: JSON decode error (attempt %d)", attempt + 1)
        except Exception as exc:
            logger.error("Verifier LLM error: %s", exc)
            break

    return "uncertain", 0.5, "Verification could not complete."


# ─── Main verification pipeline ───────────────────────────────────────────────

async def verify_answer(
    answer: str,
    chunks: List[Chunk],
    workspace_id: str,
    query_id: Optional[int],
    openrouter_client,
    verifier_model: str = "default",
    answer_id: str = "",
    mode: str = "normal",       # normal | strict | off
) -> Tuple[str, VerificationSummary]:
    """
    Full verification pipeline.

    Returns:
        (verified_answer, VerificationSummary)
    """
    t_start = time.time()

    if mode == "off" or not openrouter_client:
        summary = VerificationSummary(
            answer_id=answer_id,
            workspace_id=workspace_id,
            query_id=query_id,
            verifier_status="skipped",
            answer_faithfulness_score=1.0,
            claim_support_rate=1.0,
        )
        return answer, summary

    # 1. Extract claims
    claims = extract_claims(answer)

    if not claims:
        summary = VerificationSummary(
            answer_id=answer_id,
            workspace_id=workspace_id,
            query_id=query_id,
            verifier_status="ok",
            answer_faithfulness_score=1.0,
            claim_support_rate=1.0,
        )
        return answer, summary

    # 2. Verify each claim
    results: List[ClaimVerificationResult] = []

    try:
        async def verify_one_claim(claim: str) -> ClaimVerificationResult:
            best_chunks = match_claim_to_evidence(claim, chunks)

            if not best_chunks:
                return ClaimVerificationResult(
                    claim=claim,
                    status="unsupported",
                    confidence=0.0,
                    explanation="No retrieved chunks match this claim.",
                    verifier_model=verifier_model,
                )

            status, confidence, explanation = await _call_verifier_llm(
                claim, best_chunks, openrouter_client
            )
            if status == "uncertain" and "could not complete" in explanation.lower():
                top = best_chunks[0]
                lexical = _lexical_overlap(claim, top.text)
                sim = top.similarity / 100.0 if top.similarity > 1 else top.similarity
                deterministic_confidence = min(1.0, lexical * 0.7 + sim * 0.3)
                if deterministic_confidence >= 0.45:
                    status = "supported"
                    confidence = round(deterministic_confidence, 3)
                    explanation = "Deterministic source matching supports this claim while verifier LLM is unavailable."
                else:
                    confidence = round(max(confidence, deterministic_confidence), 3)

            # Map best chunk to evidence ids
            top_chunk = best_chunks[0] if best_chunks else None

            return ClaimVerificationResult(
                claim=claim,
                status=status,
                confidence=confidence,
                evidence_chunk_id=top_chunk.chunk_id if top_chunk and status in ("supported", "contradicted") else None,
                evidence_document_id=top_chunk.document_id if top_chunk and status in ("supported", "contradicted") else None,
                explanation=explanation,
                verifier_model=verifier_model,
            )

        results = await asyncio.gather(*(verify_one_claim(claim) for claim in claims))

    except Exception as exc:
        logger.error("Verification pipeline error: %s", exc)
        verifier_status = "failed"
        latency_ms = int((time.time() - t_start) * 1000)
        summary = VerificationSummary(
            answer_id=answer_id,
            workspace_id=workspace_id,
            query_id=query_id,
            claims=[],
            verifier_status="failed",
            verifier_latency_ms=latency_ms,
            answer_faithfulness_score=0.0,
            claim_support_rate=0.0,
        )
        # Return original answer with warning — do NOT crash query
        warning = "\n\n⚠️ *Answer generated, but claim verification could not complete.*"
        return answer + warning, summary

    # 3. Compute metrics
    total = len(results)
    supported = sum(1 for r in results if r.status == "supported")
    unsupported = sum(1 for r in results if r.status == "unsupported")
    contradicted = sum(1 for r in results if r.status == "contradicted")
    uncertain = sum(1 for r in results if r.status == "uncertain")

    claim_support_rate = supported / total if total else 1.0
    unsupported_rate = (unsupported + contradicted) / total if total else 0.0
    contradicted_rate = contradicted / total if total else 0.0

    # Faithfulness score: weighted blend
    faithfulness = (
        claim_support_rate * 0.7 +
        (1.0 - contradicted_rate) * 0.2 +
        (1.0 - unsupported_rate) * 0.1
    )
    faithfulness = round(min(max(faithfulness, 0.0), 1.0), 3)

    # 4. Rewrite the answer
    verified_answer = _rewrite_answer(answer, results, unsupported_rate, mode)

    # 5. Build summary
    latency_ms = int((time.time() - t_start) * 1000)
    summary = VerificationSummary(
        answer_id=answer_id,
        workspace_id=workspace_id,
        query_id=query_id,
        claims=results,
        unsupported_claim_rate=round(unsupported_rate, 3),
        contradicted_claim_rate=round(contradicted_rate, 3),
        claim_support_rate=round(claim_support_rate, 3),
        answer_faithfulness_score=faithfulness,
        verifier_status="ok",
        verifier_latency_ms=latency_ms,
    )

    logger.info(
        "Verification complete: %d claims, faithfulness=%.2f, unsupported_rate=%.2f, latency=%dms",
        total, faithfulness, unsupported_rate, latency_ms
    )
    return verified_answer, summary


# ─── Answer rewriter ─────────────────────────────────────────────────────────

def _rewrite_answer(
    original_answer: str,
    results: List[ClaimVerificationResult],
    unsupported_rate: float,
    mode: str,
) -> str:
    """Produce a safe, verified answer based on verification results."""

    has_contradictions = any(r.status == "contradicted" for r in results)
    all_unsupported = unsupported_rate >= ALL_UNSUPPORTED_THRESHOLD

    # Full abstain
    if all_unsupported and len(results) >= 2:
        return (
            "I could not find enough evidence in your documents to answer this reliably. "
            "Please review the source documents directly or rephrase your question."
        )

    # High unsupported rate — add caveat
    if unsupported_rate >= HIGH_UNSUPPORTED_THRESHOLD:
        caveat = (
            "\n\n⚠️ **Verification note:** I found limited evidence in your documents for parts "
            "of this answer. Please verify with the cited sources."
        )
        base = _filter_claims_from_answer(original_answer, results, mode)
        return base + caveat

    # Contradictions detected
    if has_contradictions:
        caveat = (
            "\n\n⚠️ **Conflicting information:** Your documents contain conflicting information "
            "on this topic. Please review the cited sources carefully."
        )
        base = _filter_claims_from_answer(original_answer, results, mode)
        return base + caveat

    # Normal case — remove unsupported claims in strict mode
    if mode == "strict":
        return _filter_claims_from_answer(original_answer, results, mode)

    # Normal mode — keep answer, add verification note for supported answers
    if unsupported_rate == 0.0:
        return original_answer

    # Some unsupported — add light caveat
    return original_answer + (
        "\n\n*Note: Some parts of this answer could not be verified against your documents.*"
    )


def _filter_claims_from_answer(
    answer: str,
    results: List[ClaimVerificationResult],
    mode: str,
) -> str:
    """
    In strict mode, attempt to remove unsupported claim sentences from the answer.
    In normal mode, preserve the original answer (verification note added separately).
    """
    if mode != "strict":
        return answer

    unsupported_claims = {
        r.claim for r in results
        if r.status in ("unsupported", "contradicted")
    }
    if not unsupported_claims:
        return answer

    sentences = _SENTENCE_SPLIT.split(answer)
    filtered = []
    for s in sentences:
        s_stripped = s.strip()
        # Remove sentence if it closely matches an unsupported claim
        if any(_lexical_overlap(s_stripped, uc) > 0.65 for uc in unsupported_claims):
            replacement = "I could not find evidence for this in the provided documents."
            filtered.append(replacement)
        else:
            filtered.append(s_stripped)

    return " ".join(filtered)


# ─── Serializer (for DB storage) ─────────────────────────────────────────────

def summary_to_dict(summary: VerificationSummary) -> Dict[str, Any]:
    """Convert VerificationSummary to a JSON-serializable dict."""
    return {
        "answer_id": summary.answer_id,
        "workspace_id": summary.workspace_id,
        "query_id": summary.query_id,
        "claims": [
            {
                "claim": r.claim,
                "status": r.status,
                "confidence": r.confidence,
                "evidence_chunk_id": r.evidence_chunk_id,
                "evidence_document_id": r.evidence_document_id,
                "explanation": r.explanation,
                "verifier_model": r.verifier_model,
            }
            for r in summary.claims
        ],
        "total_claims": len(summary.claims),
        "supported_claims": sum(1 for r in summary.claims if r.status == "supported"),
        "unsupported_claims": sum(1 for r in summary.claims if r.status == "unsupported"),
        "contradicted_claims": sum(1 for r in summary.claims if r.status == "contradicted"),
        "uncertain_claims": sum(1 for r in summary.claims if r.status == "uncertain"),
        "unsupported_claim_rate": summary.unsupported_claim_rate,
        "contradicted_claim_rate": summary.contradicted_claim_rate,
        "claim_support_rate": summary.claim_support_rate,
        "answer_faithfulness_score": summary.answer_faithfulness_score,
        "verifier_status": summary.verifier_status,
        "verifier_latency_ms": summary.verifier_latency_ms,
    }
