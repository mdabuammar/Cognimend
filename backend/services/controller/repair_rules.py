from __future__ import annotations

from typing import Dict, Tuple, List, Any


DEFAULT_CONFIG = {
    "top_k": 5,
    "similarity_threshold": 0.70,
    "hybrid_retrieval": False,
    "reranker_enabled": False,
    "prompt_mode": "normal",
    "verifier_mode": "normal",
    "unsupported_claim_policy": "caveat",
    "generation_temperature": 0.3,
    "max_latency_increase_percent": 50,
    "max_cost_increase_percent": 100,
    "auto_repair_mode": "manual",
}


def generate_repair_candidate_for_drift(
    drift_type: str,
    current_config: Dict[str, Any],
    include_metadata: bool = False,
) -> Tuple[Dict[str, Any], List[str]] | Tuple[Dict[str, Any], List[str], Dict[str, Any]]:
    candidate = dict(current_config)
    actions: List[str] = []
    metadata = {
        "repair_reason": f"Quality drift detected: {drift_type}",
        "evidence_signal": drift_type,
        "recommended_action_type": "configuration_change",
        "user_friendly_message": "No action needed",
    }

    if drift_type == "faithfulness_drift":
        candidate["prompt_mode"] = "strict_grounded"
        candidate["verifier_mode"] = "strict"
        candidate["unsupported_claim_policy"] = "remove"
        candidate["generation_temperature"] = 0.1
        candidate["top_k"] = max(8, current_config.get("top_k", 5))
        actions.extend([
            "Enforce strict verification and grounded prompts",
            "Lower temperature to 0.1",
            "Increase top_k to provide more context",
        ])
        metadata.update({
            "repair_reason": "Unsupported answer claims increased.",
            "evidence_signal": "unsupported_claim_rate_high",
            "recommended_action_type": "stricter_verification",
            "user_friendly_message": "Answers will be checked more strictly against your documents.",
        })

    elif drift_type == "citation_drift":
        candidate["citation_required"] = True
        candidate["prompt_mode"] = "citation_strict"
        candidate["reranker_enabled"] = True
        candidate["verifier_mode"] = "verified"
        candidate["citation_truth_required"] = True
        candidate["source_count_minimum"] = 2
        actions.extend([
            "Require stronger citation verification",
            "Enable reranker for better citation targets when available",
            "Keep answer claims tied to cited chunks",
        ])
        metadata.update({
            "repair_reason": "Citation Truth Score is low.",
            "evidence_signal": "citation_truth_score_low",
            "recommended_action_type": "citation_verification",
            "user_friendly_message": "The assistant will require stronger source support before presenting citations.",
        })

    elif drift_type in ("conflict_drift", "conflict_events"):
        candidate["prompt_mode"] = "conflict_aware"
        candidate["verifier_mode"] = "strict"
        candidate["conflict_aware_answers"] = True
        candidate["freshness_priority_enabled"] = True
        actions.extend([
            "Require answers to mention document conflicts",
            "Prefer newer sources only when freshness metadata supports it",
        ])
        metadata.update({
            "repair_reason": "Conflicting information was found in retrieved sources.",
            "evidence_signal": "conflict_detected",
            "recommended_action_type": "conflict_aware_answering",
            "user_friendly_message": "Conflicting information found. The assistant will surface conflicts instead of hiding them.",
        })

    elif drift_type in ("evidence_gap_drift", "evidence_gap_events"):
        candidate["manual_review_required"] = True
        candidate["user_action_needed"] = True
        actions.extend([
            "Mark missing evidence as user action needed",
            "Do not apply parameter-only repair while documents are missing",
        ])
        metadata.update({
            "repair_reason": "Required evidence is missing from the workspace.",
            "evidence_signal": "evidence_gap_detected",
            "recommended_action_type": "user_action_needed",
            "user_friendly_message": "More evidence is needed. Upload a relevant document or reprocess failed files.",
        })

    elif drift_type in ("freshness_drift", "freshness_warning"):
        candidate["freshness_priority_enabled"] = True
        candidate["prompt_mode"] = "freshness_aware"
        actions.extend([
            "Keep freshness warning visible",
            "Prefer latest relevant source only when metadata supports it",
        ])
        metadata.update({
            "repair_reason": "Freshness warning exists for retrieved sources.",
            "evidence_signal": "freshness_warning",
            "recommended_action_type": "freshness_aware_source_priority",
            "user_friendly_message": "The assistant will keep freshness warnings visible and avoid claiming latest when dates are unknown.",
        })

    elif drift_type in ("retrieval_drift", "data_drift"):
        candidate["top_k"] = min(10, current_config.get("top_k", 5) + 3)
        candidate["similarity_threshold"] = round(max(0.60, current_config.get("similarity_threshold", 0.70) - 0.05), 2)
        candidate["hybrid_retrieval"] = True
        candidate["reranker_enabled"] = True
        actions.extend([
            "Enable hybrid retrieval and reranker",
            "Lower similarity threshold slightly to expand recall",
        ])

    elif drift_type in ("query_drift", "query_pattern_drift"):
        candidate["enable_query_rewriting"] = True
        candidate["enable_multi_hop_retrieval"] = True
        candidate["top_k"] = max(8, current_config.get("top_k", 5))
        candidate["prompt_mode"] = "reasoning_grounded"
        actions.append("Enable query rewriting and multi-hop retrieval for complex queries")

    elif drift_type == "performance_drift":
        if current_config.get("top_k", 5) > 5:
            candidate["top_k"] = 5
            actions.append("Reduce top_k to improve latency")
        if current_config.get("reranker_enabled"):
            candidate["reranker_enabled"] = False
            actions.append("Disable reranker to reduce latency")

    else:
        candidate["top_k"] = current_config.get("top_k", 5) + 1
        actions.append("Increment top_k marginally")

    if include_metadata:
        return candidate, actions, metadata
    return candidate, actions
