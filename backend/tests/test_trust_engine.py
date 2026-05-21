import os
import sys
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.controller.repair_rules import generate_repair_candidate_for_drift
from services.query.trust_engine import (
    TrustChunk,
    apply_freshness,
    detect_conflict_heuristic,
    deterministic_citation_verifications,
    evidence_gap_from_signals,
)


def chunk(doc_id, text, title="Policy", score=0.8, uploaded_at=None):
    return TrustChunk(
        document_id=doc_id,
        document_title=title,
        chunk_id=f"chunk-{doc_id}",
        text=text,
        similarity=score,
        uploaded_at=uploaded_at,
    )


def test_supported_citation_returns_high_score():
    score, label, verifications, _ = deterministic_citation_verifications(
        "The refund period is 14 days.",
        [chunk(1, "Customers may request a refund within 14 days of purchase.")],
    )
    assert score >= 0.6
    assert label in {"strong", "partial"}
    assert verifications[0]["support_status"] in {"supports", "partial"}


def test_irrelevant_citation_returns_low_score():
    score, label, verifications, _ = deterministic_citation_verifications(
        "The refund period is 14 days.",
        [chunk(1, "The office has a cafeteria on the second floor.", score=0.1)],
    )
    assert score < 0.45
    assert label == "weak"
    assert verifications[0]["support_status"] in {"weak", "irrelevant"}


def test_contradicted_citation_returns_low_score():
    score, _, verifications, _ = deterministic_citation_verifications(
        "The refund period is 14 days.",
        [chunk(1, "Customers may request a refund within 7 days of purchase.")],
    )
    assert score < 0.5
    assert verifications[0]["support_status"] == "contradicted"


def test_conflicting_snippets_trigger_conflict():
    pairs = detect_conflict_heuristic([
        chunk(1, "Refunds are allowed within 7 days.", "Old refund policy"),
        chunk(2, "Refunds are allowed within 14 days.", "New refund policy"),
    ])
    assert pairs


def test_agreeing_snippets_do_not_trigger_conflict():
    pairs = detect_conflict_heuristic([
        chunk(1, "Refunds are allowed within 14 days.", "Refund policy A"),
        chunk(2, "Customers may request refunds during the 14 day period.", "Refund policy B"),
    ])
    assert pairs == []


def test_uncertain_conflict_does_not_overdetect():
    pairs = detect_conflict_heuristic([
        chunk(1, "The office opens at 9 AM.", "Office handbook"),
        chunk(2, "The support email is help@example.com.", "Support handbook"),
    ])
    assert pairs == []


def test_no_retrieved_chunks_triggers_evidence_gap():
    detected, summary, missing, actions = evidence_gap_from_signals(
        "What is the refund period?", 0, [], None, None, False
    )
    assert detected is True
    assert summary
    assert missing
    assert actions


def test_supported_query_returns_no_evidence_gap():
    detected, *_ = evidence_gap_from_signals(
        "What is the refund period?", 2, [0.8, 0.7], 0.9, 0.0, False
    )
    assert detected is False


def test_latest_source_marked_only_when_metadata_exists():
    older = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    newer = datetime.now(timezone.utc).isoformat()
    old_chunk = chunk(1, "Policy text")
    old_chunk.document_created_at = older
    new_chunk = chunk(2, "Policy text")
    new_chunk.document_created_at = newer
    labels, warning, latest = apply_freshness([
        old_chunk,
        new_chunk,
    ], conflict_detected=False)
    assert labels["chunk-2"]["is_latest_relevant_source"] is True
    assert latest == "2"
    assert warning is None


def test_upload_time_fallback_does_not_mark_latest_source():
    older = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    newer = datetime.now(timezone.utc).isoformat()
    labels, warning, latest = apply_freshness([
        chunk(1, "Policy text", uploaded_at=older),
        chunk(2, "Policy text", uploaded_at=newer),
    ], conflict_detected=False)
    assert labels["chunk-2"]["is_latest_relevant_source"] is False
    assert latest is None
    assert "upload time" in warning


def test_missing_metadata_returns_unknown_freshness():
    labels, warning, latest = apply_freshness([chunk(1, "Policy text")], conflict_detected=False)
    assert labels["chunk-1"]["source_freshness_label"] == "unknown"
    assert latest is None
    assert "unknown" in warning


def test_old_new_conflict_creates_freshness_warning():
    older = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    newer = datetime.now(timezone.utc).isoformat()
    old_chunk = chunk(1, "Refunds are 7 days")
    old_chunk.document_created_at = older
    new_chunk = chunk(2, "Refunds are 14 days")
    new_chunk.document_created_at = newer
    _, warning, _ = apply_freshness([
        old_chunk,
        new_chunk,
    ], conflict_detected=True)
    assert warning


def test_evidence_gap_creates_user_action_needed_repair():
    _, actions, metadata = generate_repair_candidate_for_drift("evidence_gap_drift", {"top_k": 5}, include_metadata=True)
    assert metadata["recommended_action_type"] == "user_action_needed"
    assert "More evidence is needed" in metadata["user_friendly_message"]
    assert any("Do not apply parameter-only repair" in action for action in actions)


def test_low_citation_truth_creates_citation_focused_repair():
    config, _, metadata = generate_repair_candidate_for_drift("citation_drift", {"top_k": 5}, include_metadata=True)
    assert config["citation_truth_required"] is True
    assert metadata["evidence_signal"] == "citation_truth_score_low"


def test_failed_repair_remains_rejected_signal():
    _, _, metadata = generate_repair_candidate_for_drift("evidence_gap_drift", {"top_k": 5}, include_metadata=True)
    assert metadata["recommended_action_type"] in {"user_action_needed", "manual_review"}
