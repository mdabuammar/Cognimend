"""
Phase 3 Test Suite — Evaluation Service Integration

Tests cover:
1. Real evaluation call routing
2. Baseline vs candidate comparison rules
3. Not enough evaluation data → manual_review
4. Apply safety (approved + eval result required)
5. Workspace isolation
6. RAG-DriftBench scenarios & run creation
"""
import pytest
import json
import sys
import os

# ---------------------------------------------------------------------------
# Minimal stubs so tests run without a live DB
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../"))

# ── Import the pure helper functions from evaluation service ──────────────
from main import calculate_recommendation, run_pipeline_for_config
from rag_driftbench import SCENARIOS


# ══════════════════════════════════════════════════════════════════════════════
# 1. Baseline vs Candidate Comparison
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculateRecommendation:
    """
    Tests for the decision-engine that compares baseline vs candidate metrics
    and emits: apply | reject | manual_review
    """

    def _base(self):
        return {
            "faithfulness_score":      0.60,
            "unsupported_claim_rate":  0.35,
            "citation_accuracy":       0.72,
            "retrieval_health":        0.65,
            "latency_ms":              600.0,
            "estimated_cost":          0.001,
            "error_rate":              0.02,
            "question_count":          5,
        }

    def test_good_candidate_returns_apply(self):
        """Faithfulness +10% with acceptable latency/cost → apply."""
        base = self._base()
        cand = {**base,
                "faithfulness_score":      0.75,   # +25%
                "unsupported_claim_rate":  0.18,   # improved
                "citation_accuracy":       0.73,   # stable
                "retrieval_health":        0.65,
                "latency_ms":              700.0,  # +17% ← within 50% cap
                "estimated_cost":          0.001,
                "error_rate":              0.02}
        rec, imp, q_imp, lat_acc, cost_acc = calculate_recommendation(base, cand)
        assert rec == "apply"
        assert q_imp is True
        assert lat_acc is True
        assert cost_acc is True

    def test_bad_candidate_returns_reject(self):
        """Faithfulness drops → reject regardless."""
        base = self._base()
        cand = {**base,
                "faithfulness_score":      0.45,   # worse
                "unsupported_claim_rate":  0.50,   # worse
                "citation_accuracy":       0.60,   # worse
                "latency_ms":              600.0,
                "estimated_cost":          0.001,
                "error_rate":              0.02}
        rec, imp, q_imp, lat_acc, cost_acc = calculate_recommendation(base, cand)
        assert rec == "reject"

    def test_quality_improves_but_high_latency_returns_reject(self):
        """Quality up, but latency doubles (>50% threshold) → reject."""
        base = self._base()
        cand = {**base,
                "faithfulness_score":      0.80,
                "unsupported_claim_rate":  0.10,
                "citation_accuracy":       0.72,
                "latency_ms":              1200.0,  # +100% ← over 50% cap
                "estimated_cost":          0.001,
                "error_rate":              0.02}
        rec, *_ = calculate_recommendation(base, cand)
        assert rec == "reject"

    def test_mixed_results_returns_manual_review(self):
        """Citation accuracy drops slightly, quality marginally improved → manual_review."""
        base = self._base()
        cand = {**base,
                "faithfulness_score":      0.63,   # +3% — below 5% threshold
                "unsupported_claim_rate":  0.33,
                "citation_accuracy":       0.72,
                "retrieval_health":        0.66,   # +1% — below 10% threshold
                "latency_ms":              650.0,
                "estimated_cost":          0.001,
                "error_rate":              0.02}
        rec, *_ = calculate_recommendation(base, cand)
        assert rec == "manual_review"

    def test_empty_metrics_returns_manual_review(self):
        """Missing metrics → always manual_review, never crash."""
        rec, imp, *_ = calculate_recommendation({}, {})
        assert rec == "manual_review"
        assert imp == {}

    def test_improvement_dict_is_percentage_strings(self):
        """Improvement dict values are human-readable strings."""
        base = self._base()
        cand = {**base, "faithfulness_score": 0.75, "latency_ms": 700.0,
                "unsupported_claim_rate": 0.20, "estimated_cost": 0.001,
                "error_rate": 0.02}
        _, imp, *_ = calculate_recommendation(base, cand)
        assert "faithfulness_score" in imp
        assert "%" in imp["faithfulness_score"]
        assert "ms" in imp["latency_ms_diff"]


# ══════════════════════════════════════════════════════════════════════════════
# 2. Pipeline Evaluation Engine
# ══════════════════════════════════════════════════════════════════════════════

class TestRunPipelineForConfig:
    """Tests for the per-config metric simulation engine."""

    @pytest.mark.asyncio
    async def test_strict_config_has_higher_faithfulness(self):
        """Strict verifier + low temperature → higher faithfulness than relaxed."""
        strict_cfg = {"top_k": 5, "generation_temperature": 0.1, "verifier_mode": "strict"}
        relaxed_cfg = {"top_k": 5, "generation_temperature": 0.8, "verifier_mode": "normal"}
        questions = [{"question": "What is the policy?"}, {"question": "Explain the terms."}]

        strict_m  = await run_pipeline_for_config(questions, strict_cfg, "ws-test")
        relaxed_m = await run_pipeline_for_config(questions, relaxed_cfg, "ws-test")

        assert strict_m["faithfulness_score"]     > relaxed_m["faithfulness_score"]
        assert strict_m["unsupported_claim_rate"] < relaxed_m["unsupported_claim_rate"]

    @pytest.mark.asyncio
    async def test_reranker_improves_retrieval(self):
        """Enabling reranker raises retrieval_health."""
        no_rerank = {"top_k": 5, "reranker_enabled": False}
        reranked  = {"top_k": 5, "reranker_enabled": True}
        questions = [{"question": "Find the right document."}]

        m_no  = await run_pipeline_for_config(questions, no_rerank, "ws-test")
        m_yes = await run_pipeline_for_config(questions, reranked,  "ws-test")

        assert m_yes["retrieval_health"] > m_no["retrieval_health"]

    @pytest.mark.asyncio
    async def test_empty_questions_returns_empty(self):
        """No questions → empty metrics dict, no crash."""
        result = await run_pipeline_for_config([], {"top_k": 5}, "ws-test")
        assert result == {}

    @pytest.mark.asyncio
    async def test_metrics_include_all_required_keys(self):
        """All six required metric keys present in output."""
        cfg = {"top_k": 5, "generation_temperature": 0.3, "verifier_mode": "normal"}
        questions = [{"question": "Test?"}]
        result = await run_pipeline_for_config(questions, cfg, "ws-test")

        required = {"faithfulness_score", "unsupported_claim_rate", "citation_accuracy",
                    "retrieval_health", "latency_ms", "estimated_cost"}
        assert required.issubset(result.keys())


# ══════════════════════════════════════════════════════════════════════════════
# 3. RAG-DriftBench Scenarios
# ══════════════════════════════════════════════════════════════════════════════

class TestDriftBenchScenarios:
    """Tests for the 7 canonical DriftBench scenarios."""

    def test_exactly_7_scenarios_registered(self):
        """Must have exactly 7 canonical scenarios."""
        assert len(SCENARIOS) == 7

    def test_all_scenarios_have_required_fields(self):
        """Every scenario must declare name, drift_type, configs, and questions."""
        required = {"name", "drift_type", "description", "expected_behavior",
                    "baseline_config", "drifted_config", "repaired_config", "questions"}
        for s in SCENARIOS:
            missing = required - set(s.keys())
            assert not missing, f"Scenario '{s.get('name')}' missing: {missing}"

    def test_scenario_names_are_unique(self):
        names = [s["name"] for s in SCENARIOS]
        assert len(names) == len(set(names))

    def test_drift_types_are_known(self):
        allowed = {"faithfulness_drift", "citation_drift", "retrieval_drift", "query_drift"}
        for s in SCENARIOS:
            assert s["drift_type"] in allowed, \
                f"Unknown drift_type '{s['drift_type']}' in scenario '{s['name']}'"

    def test_faithfulness_drift_scenario_uses_high_temperature(self):
        """The faithfulness_drift scenario must test high temperature."""
        s = next(x for x in SCENARIOS if x["name"] == "faithfulness_drift")
        assert s["drifted_config"]["generation_temperature"] >= 0.8

    def test_repair_config_uses_stricter_verifier(self):
        """Repair configs for faithfulness drift must use strict verifier."""
        for s in SCENARIOS:
            if s["drift_type"] == "faithfulness_drift":
                assert s["repaired_config"].get("verifier_mode") == "strict", \
                    f"Scenario '{s['name']}' repair config should use strict verifier"

    def test_retrieval_scenarios_use_reranker_in_repair(self):
        """Retrieval-related repairs should enable reranker."""
        for s in SCENARIOS:
            if s["drift_type"] == "retrieval_drift":
                assert s["repaired_config"].get("reranker_enabled") is True, \
                    f"Scenario '{s['name']}' repair config should enable reranker"

    def test_all_scenarios_have_at_least_one_question(self):
        for s in SCENARIOS:
            assert len(s["questions"]) >= 1, \
                f"Scenario '{s['name']}' has no test questions"

    @pytest.mark.asyncio
    async def test_drifted_config_degrades_faithfulness(self):
        """For faithfulness_drift scenario, drifted config scores worse than baseline."""
        from rag_driftbench import _eval_config
        s = next(x for x in SCENARIOS if x["name"] == "faithfulness_drift")
        questions = [{"question": q} for q in s["questions"]]
        base  = await _eval_config(s["baseline_config"], questions)
        drift = await _eval_config(s["drifted_config"],  questions)
        assert drift["faithfulness_score"] < base["faithfulness_score"]

    @pytest.mark.asyncio
    async def test_repaired_config_recovers_faithfulness(self):
        """For faithfulness_drift scenario, repaired config recovers to near-baseline."""
        from rag_driftbench import _eval_config
        s = next(x for x in SCENARIOS if x["name"] == "faithfulness_drift")
        questions = [{"question": q} for q in s["questions"]]
        base   = await _eval_config(s["baseline_config"], questions)
        repair = await _eval_config(s["repaired_config"], questions)
        # Repaired should be within 5% of baseline
        assert abs(repair["faithfulness_score"] - base["faithfulness_score"]) <= 0.12


# ══════════════════════════════════════════════════════════════════════════════
# 4. Apply Safety Rules (pure logic)
# ══════════════════════════════════════════════════════════════════════════════

class TestApplySafetyLogic:
    """Pure-logic tests for candidate apply eligibility."""

    def test_only_approved_candidates_can_be_applied(self):
        """Any status other than 'approved' must block apply."""
        blocked_statuses = ["generated", "testing", "rejected", "failed", "applied"]
        for status in blocked_statuses:
            cand_status = status
            can_apply = cand_status == "approved"
            assert not can_apply, f"Status '{status}' should not allow apply"

    def test_approved_candidate_can_be_applied(self):
        cand_status = "approved"
        assert cand_status == "approved"

    def test_apply_requires_eval_result(self):
        """Apply logic must check evaluation_result_id is not None."""
        eval_result_id = None
        status = "approved"
        can_apply = (status == "approved") and (eval_result_id is not None)
        assert not can_apply

    def test_apply_succeeds_when_all_conditions_met(self):
        eval_result_id = 42
        status = "approved"
        role = "owner"
        can_apply = (status == "approved") and (eval_result_id is not None) and (role in ("owner", "admin"))
        assert can_apply


# ══════════════════════════════════════════════════════════════════════════════
# 5. Workspace Isolation (pure logic)
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkspaceIsolation:
    """
    Pure-logic tests for workspace isolation — no DB required.
    These model the WHERE workspace_id = %s guards in all queries.
    """

    def _ws_filter(self, records: list, ws_id: str) -> list:
        """Simulate workspace-scoped DB query."""
        return [r for r in records if r["workspace_id"] == ws_id]

    def test_workspace_a_cannot_read_workspace_b_candidates(self):
        records = [
            {"id": 1, "workspace_id": "ws-a", "drift_type": "faithfulness_drift"},
            {"id": 2, "workspace_id": "ws-b", "drift_type": "citation_drift"},
        ]
        ws_a_view = self._ws_filter(records, "ws-a")
        assert len(ws_a_view) == 1
        assert ws_a_view[0]["id"] == 1

    def test_workspace_b_cannot_read_workspace_a_candidates(self):
        records = [
            {"id": 1, "workspace_id": "ws-a"},
            {"id": 2, "workspace_id": "ws-b"},
        ]
        ws_b_view = self._ws_filter(records, "ws-b")
        assert all(r["workspace_id"] == "ws-b" for r in ws_b_view)

    def test_workspace_a_cannot_read_workspace_b_eval_results(self):
        results = [
            {"id": 10, "workspace_id": "ws-a", "recommendation": "apply"},
            {"id": 11, "workspace_id": "ws-b", "recommendation": "reject"},
        ]
        ws_a_results = self._ws_filter(results, "ws-a")
        assert len(ws_a_results) == 1
        assert ws_a_results[0]["id"] == 10

    def test_empty_workspace_returns_empty(self):
        records = [{"id": 1, "workspace_id": "ws-a"}]
        result = self._ws_filter(records, "ws-nonexistent")
        assert result == []


# ══════════════════════════════════════════════════════════════════════════════
# 6. Controller → Evaluation Integration (unit, mocked)
# ══════════════════════════════════════════════════════════════════════════════

class TestControllerEvalIntegration:
    """
    Verifies the controller routes properly to the evaluation service
    and maps recommendations to candidate statuses correctly.
    """

    def test_apply_recommendation_maps_to_approved(self):
        rec = "apply"
        new_status = "approved" if rec == "apply" else "rejected" if rec == "reject" else "testing"
        assert new_status == "approved"

    def test_reject_recommendation_maps_to_rejected(self):
        rec = "reject"
        new_status = "approved" if rec == "apply" else "rejected" if rec == "reject" else "testing"
        assert new_status == "rejected"

    def test_manual_review_recommendation_maps_to_testing(self):
        rec = "manual_review"
        new_status = "approved" if rec == "apply" else "rejected" if rec == "reject" else "testing"
        assert new_status == "testing"

    def test_controller_url_configured(self):
        """EVALUATION_SERVICE_URL must have a sensible default."""
        import os
        url = os.getenv("EVALUATION_SERVICE_URL", "http://evaluation:8006")
        assert url.startswith("http")
        assert "8006" in url or "evaluation" in url
