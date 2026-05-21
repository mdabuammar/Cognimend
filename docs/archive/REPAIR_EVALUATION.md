# Repair Evaluation Service

## Overview
The Evaluation Service (`port 8006`) provides a real baseline-vs-candidate evaluation pipeline for the Self-Healing Controller. All routes are workspace-scoped and require `owner` or `admin` role.

## Evaluation Questions

### Sources (priority order)
1. **Admin-created** — stored in `evaluation_questions` with a `workspace_id`
2. **System defaults** — seeded in migration `006` with `workspace_id IS NULL` (shared across all workspaces)
3. **Recent real queries** — fallback if fewer than 2 questions exist

### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/evaluation/questions` | List all questions for this workspace |
| `POST` | `/evaluation/questions` | Add a new benchmark question (admin) |
| `DELETE` | `/evaluation/questions/{id}` | Remove a question (admin) |

### Question Schema
```json
{
  "question": "What is the refund policy?",
  "expected_answer": "14 days",
  "category": "policy",
  "difficulty": "easy"
}
```

## Repair Candidate Testing

### `POST /evaluation/repair-candidate/{candidate_id}/run`

**Request body:**
```json
{
  "baseline_config_version_id": 1,
  "candidate_config_version_id": 2,
  "candidate_id": 7,
  "evaluation_question_ids": [1, 2, 3]
}
```

**Response:**
```json
{
  "evaluation_result_id": 42,
  "recommendation": "apply",
  "baseline_metrics": {
    "faithfulness_score": 0.61,
    "unsupported_claim_rate": 0.34,
    "citation_accuracy": 0.72,
    "retrieval_health": 0.66,
    "latency_ms": 620,
    "estimated_cost": 0.00085
  },
  "candidate_metrics": { "..." },
  "improvement": {
    "faithfulness_score": "+23.0%",
    "latency_ms_diff": "+90ms"
  },
  "quality_improved": true,
  "latency_acceptable": true,
  "cost_acceptable": true
}
```

### `GET /evaluation/repair-candidate/{candidate_id}/result`
Returns the latest stored evaluation result for a candidate (workspace-scoped).

## Decision Rules

### `apply` when:
- `faithfulness_score` improves by ≥ 5%, **OR**
- `unsupported_claim_rate` decreases by ≥ 20%, **OR**
- `retrieval_health` improves by ≥ 10%

**AND all of:**
- `citation_accuracy` does not drop by > 5%
- Latency increase ≤ 50%
- Cost increase ≤ 100%
- `error_rate` does not increase significantly

### `reject` when:
- `faithfulness_score` decreases
- `unsupported_claim_rate` increases
- `citation_accuracy` drops > 10%
- Latency increase > 50%
- Cost increase > 100%
- `error_rate` > 15%

### `manual_review` when:
- Mixed results that don't clearly meet apply or reject conditions
- Fewer than 2 evaluation questions exist

## Not Enough Data
If no evaluation questions exist and fewer than 2 recent queries are available, the service returns:
```json
{
  "recommendation": "manual_review",
  "message": "Not enough evaluation data to safely test this repair. Add evaluation questions first."
}
```
The candidate status stays `testing` — it will **not** be approved until real data is available.
