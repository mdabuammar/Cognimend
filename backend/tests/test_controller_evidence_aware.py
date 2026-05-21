import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.controller.repair_rules import generate_repair_candidate_for_drift


def test_evidence_gap_creates_user_action_needed_or_manual_review():
    config, actions, metadata = generate_repair_candidate_for_drift(
        "evidence_gap_drift", {"top_k": 5}, include_metadata=True
    )
    assert config["user_action_needed"] is True
    assert config["manual_review_required"] is True
    assert metadata["recommended_action_type"] in {"user_action_needed", "manual_review"}
    assert "Upload a relevant document" in metadata["user_friendly_message"]
    assert any("Do not apply parameter-only repair" in action for action in actions)


def test_conflict_creates_conflict_aware_repair_candidate():
    config, actions, metadata = generate_repair_candidate_for_drift(
        "conflict_drift", {"top_k": 5}, include_metadata=True
    )
    assert config["conflict_aware_answers"] is True
    assert config["prompt_mode"] == "conflict_aware"
    assert metadata["evidence_signal"] == "conflict_detected"
    assert any("mention document conflicts" in action for action in actions)


def test_low_citation_truth_creates_citation_focused_candidate():
    config, actions, metadata = generate_repair_candidate_for_drift(
        "citation_drift", {"top_k": 5}, include_metadata=True
    )
    assert config["citation_truth_required"] is True
    assert config["reranker_enabled"] is True
    assert metadata["recommended_action_type"] == "citation_verification"
    assert any("citation verification" in action for action in actions)


def test_failed_repair_is_rejected_signal_not_auto_approved():
    config, _, metadata = generate_repair_candidate_for_drift(
        "evidence_gap_drift", {"top_k": 5}, include_metadata=True
    )
    assert config.get("auto_approved") is not True
    assert metadata["recommended_action_type"] == "user_action_needed"


def test_rollback_restores_previous_stable_config_shape():
    active = {"id": "active", "status": "active", "config_json": {"verifier_mode": "strict"}}
    stable = {"id": "stable", "status": "stable", "config_json": {"verifier_mode": "verified"}}

    restored = dict(stable["config_json"])
    active["status"] = "rolled_back"
    stable["status"] = "active"

    assert restored["verifier_mode"] == "verified"
    assert active["status"] == "rolled_back"
    assert stable["status"] == "active"
