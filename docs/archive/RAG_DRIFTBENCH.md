# RAG-DriftBench

A controlled benchmark suite for verifying that Cognimend's drift detection, evaluation, and repair pipeline work correctly end-to-end.

## The 7 Canonical Scenarios

| # | Scenario | Drift Type | What Is Tested |
|---|----------|-----------|----------------|
| 1 | `document_update_drift` | retrieval_drift | System answers with new document after update |
| 2 | `contradictory_evidence_drift` | faithfulness_drift | System handles conflicting documents cautiously |
| 3 | `missing_evidence_drift` | retrieval_drift | System abstains rather than hallucinating |
| 4 | `query_distribution_drift` | query_drift | Complex queries trigger query drift detection |
| 5 | `retrieval_degradation_drift` | retrieval_drift | Reranker improves retrieval after noise injection |
| 6 | `citation_drift` | citation_drift | Wrong citations caught by citation quality metric |
| 7 | `faithfulness_drift` | faithfulness_drift | High temperature increases unsupported claim rate |

## How It Works

Each scenario runs 3 phases:

1. **Baseline** — eval the pre-drift configuration
2. **Drifted** — eval the config that simulates drift (high temperature, stale KB, noise chunks, etc.)
3. **Repaired** — eval the auto-generated repair config

The engine records `detection_success` (did drifted score drop vs baseline?) and `repair_success` (did repaired score recover to within ~5% of baseline?).

## Running Scenarios

### Via API
```bash
# Run all 7 scenarios for your workspace
curl -X POST http://localhost:8007/evaluation/driftbench/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-workspace-id: $WORKSPACE_ID" \
  -d '{}'

# Run a single scenario (id from /driftbench/scenarios)
curl -X POST http://localhost:8007/evaluation/driftbench/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-workspace-id: $WORKSPACE_ID" \
  -d '{"scenario_id": 1}'
```

### List Results
```bash
curl http://localhost:8007/evaluation/driftbench/runs \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-workspace-id: $WORKSPACE_ID"
```

### Get a Report
```bash
curl http://localhost:8007/evaluation/driftbench/runs/1/report \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-workspace-id: $WORKSPACE_ID"
```

## Interpreting a Report

```json
{
  "scenario_name": "faithfulness_drift",
  "drift_type": "faithfulness_drift",
  "detection_success": true,
  "repair_success": true,
  "drift_analysis": {
    "faithfulness_score": { "baseline": 0.82, "drifted": 0.54, "delta": -0.28 },
    "unsupported_claim_rate": { "baseline": 0.08, "drifted": 0.31, "delta": 0.23 }
  },
  "repair_analysis": {
    "faithfulness_score": { "baseline": 0.54, "drifted": 0.87, "delta": 0.33 }
  }
}
```

| Field | Meaning |
|-------|---------|
| `detection_success: true` | Drift was measurably introduced (drifted < baseline) |
| `repair_success: true` | Repaired config recovered to ≥ baseline − 2% |
| `drift_analysis` | Baseline → Drifted deltas (how bad the drift is) |
| `repair_analysis` | Drifted → Repaired deltas (how well repair worked) |

## Tables
- **`rag_driftbench_scenarios`** — seeded in migration `005`, immutable
- **`rag_driftbench_runs`** — one row per workspace run, workspace-scoped

## Adding Custom Scenarios
1. Insert a row into `rag_driftbench_scenarios` with your `setup_json`.
2. Add its configuration triple to `SCENARIOS` list in `rag_driftbench.py`.
3. Runs will automatically pick it up.
