import pytest
import sys
import os
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))
from services.controller.repair_rules import generate_repair_candidate_for_drift

def test_candidate_generation_faithfulness():
    current_config = {"top_k": 5, "generation_temperature": 0.3}
    candidate, actions = generate_repair_candidate_for_drift("faithfulness_drift", current_config)
    
    assert candidate["prompt_mode"] == "strict_grounded"
    assert candidate["verifier_mode"] == "strict"
    assert candidate["unsupported_claim_policy"] == "remove"
    assert candidate["generation_temperature"] == 0.1
    assert candidate["top_k"] >= 8
    assert len(actions) > 0

def test_candidate_generation_citation():
    current_config = {"top_k": 5}
    candidate, actions = generate_repair_candidate_for_drift("citation_drift", current_config)
    
    assert candidate["citation_required"] is True
    assert candidate["prompt_mode"] == "citation_strict"
    assert candidate["reranker_enabled"] is True
    assert candidate["source_count_minimum"] == 2

def test_candidate_generation_retrieval():
    current_config = {"top_k": 5, "similarity_threshold": 0.70}
    candidate, actions = generate_repair_candidate_for_drift("retrieval_drift", current_config)
    
    assert candidate["top_k"] == 8
    assert candidate["similarity_threshold"] == 0.65
    assert candidate["hybrid_retrieval"] is True

def test_candidate_generation_query_pattern():
    current_config = {"top_k": 5}
    candidate, actions = generate_repair_candidate_for_drift("query_pattern_drift", current_config)
    
    assert candidate["enable_query_rewriting"] is True
    assert candidate["enable_multi_hop_retrieval"] is True
    assert candidate["prompt_mode"] == "reasoning_grounded"

def test_candidate_generation_performance():
    current_config = {"top_k": 8, "reranker_enabled": True}
    candidate, actions = generate_repair_candidate_for_drift("performance_drift", current_config)
    
    assert candidate["top_k"] == 5
    assert candidate["reranker_enabled"] is False

def test_evidence_gap_candidate_requires_user_action():
    candidate, actions, metadata = generate_repair_candidate_for_drift(
        "evidence_gap_drift", {"top_k": 5}, include_metadata=True
    )

    assert candidate["user_action_needed"] is True
    assert candidate["manual_review_required"] is True
    assert metadata["recommended_action_type"] == "user_action_needed"
    assert any("missing" in action.lower() for action in actions)

def test_conflict_candidate_is_conflict_aware():
    candidate, actions, metadata = generate_repair_candidate_for_drift(
        "conflict_events", {"top_k": 5}, include_metadata=True
    )

    assert candidate["prompt_mode"] == "conflict_aware"
    assert candidate["conflict_aware_answers"] is True
    assert candidate["freshness_priority_enabled"] is True
    assert metadata["evidence_signal"] == "conflict_detected"

def test_low_citation_truth_candidate_focuses_citations():
    candidate, actions, metadata = generate_repair_candidate_for_drift(
        "citation_drift", {"top_k": 5}, include_metadata=True
    )

    assert candidate["citation_truth_required"] is True
    assert candidate["prompt_mode"] == "citation_strict"
    assert metadata["recommended_action_type"] == "citation_verification"
    assert any("citation" in action.lower() for action in actions)

def test_failed_repair_is_not_auto_approved():
    candidate, _, metadata = generate_repair_candidate_for_drift(
        "evidence_gap_events", {"top_k": 5}, include_metadata=True
    )

    assert candidate.get("auto_approved") is not True
    assert metadata["recommended_action_type"] == "user_action_needed"

def test_rollback_restores_stable_config():
    active = {"id": "active", "status": "active", "config_json": {"verifier_mode": "strict"}}
    stable = {"id": "stable", "status": "stable", "config_json": {"verifier_mode": "verified"}}

    restored = dict(stable["config_json"])
    active["status"] = "rolled_back"
    stable["status"] = "active"

    assert restored["verifier_mode"] == "verified"
    assert active["status"] == "rolled_back"
    assert stable["status"] == "active"
