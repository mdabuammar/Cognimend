# Self-Healing RAG Controller & Configuration Versioning

## Overview
Cognimend's Self-Healing Controller is the decision engine for the RAG platform. When the Drift Detector identifies quality degradation (faithfulness drops, citation errors, retrieval shifts), the Controller generates a repair candidate, sends it to the **Evaluation Service** for real measurement, and rolls it out only when metrics actually improve.

## Phase 3 Update: Real Evaluation (no more mocks)
The candidate testing endpoint `POST /controller/repair-candidates/{id}/test` previously used a mock async sleep to simulate evaluation. It now calls the Evaluation Service at `EVALUATION_SERVICE_URL` with the baseline and candidate config version IDs. The Evaluation Service runs real metric pipelines (retrieval + generation + verifier emulation over workspace questions) and returns a `recommendation: apply | reject | manual_review`. The controller maps that to candidate status.

## Config Versioning
All configurations are strictly versioned per workspace in `config_versions`.
- **Immutable Active State:** Active configs are never overwritten — a new candidate version is always created.
- **Statuses:** `stable` → `candidate` → `testing` → `active` or `rejected` or `rolled_back`.

## Repair Evaluation (Verify-Before-Apply)
1. **Candidate Generation**: Drift type determines config heuristics (faithfulness → strict mode + low temperature).
2. **Testing**: Controller calls `POST /evaluation/repair-candidate/{id}/run`. Evaluation runs baseline + candidate on workspace evaluation questions concurrently.
3. **Approval**: If faithfulness improves ≥5% OR retrieval_health improves ≥10% — and latency/cost stay acceptable — candidate is `approved`.
4. **Application**: Approved candidate requires `evaluation_result_id` to exist before apply is allowed.

## Rollback
`POST /controller/config/rollback` instantly reverts the workspace to the last `stable` config, marks the failing config as `rolled_back`, and re-opens the original drift event.

## RabbitMQ Events
- `repair.candidate_generated`
- `repair.candidate_evaluated`
- `repair.candidate_applied`
- `repair.candidate_rejected`
- `repair.rollback_completed`

