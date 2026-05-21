# Cognimend Trust Engine

Cognimend is a simple AI document assistant: login, upload documents, ask questions, receive source-based answers, and review RAG health. The Trust Engine is the backend layer that keeps those answers honest.

## Trust Modes

- `fast`: normal RAG answer, basic citations, deterministic checks only unless a high-risk signal appears.
- `verified`: default mode. Runs claim verification and citation truth checks when evidence looks weak or uncertain.
- `strict`: runs claim verification, citation truth, conflict detection, and evidence gap detection; refuses answers when evidence is missing.

## Query Trust Signals

`POST /query` now returns backend-computed trust fields:

- `citation_truth_score`: 0.0-1.0 score for whether cited chunks support the answer.
- `citation_quality_label`: `strong`, `partial`, or `weak`.
- `citation_verifications`: per-citation support status, related claims, score, and safe explanation.
- `conflict_detected`, `conflict_summary`, `conflict_sources`: document disagreements found across retrieved chunks.
- `evidence_gap_detected`, `evidence_gap_summary`, `missing_information`, `suggested_actions`: missing-evidence analysis.
- `freshness_warning`, `latest_source_id`: source freshness warning and latest relevant source marker.
- Source objects include upload/document dates, freshness label, and `is_latest_relevant_source`.

## Layered Execution

Every query runs lightweight checks first:

- source similarity and retrieval strength
- citation chunk availability
- no-result and low-result detection
- document date metadata
- heuristic conflict checks

LLM judges run only when needed: strict mode, weak retrieval, low-confidence answers, heuristic conflict risk, uncertain citation support, or missing evidence. Judge results are cached with trust-specific keys for citation, conflict, and evidence-gap checks.

## Repair Behavior

Self-healing repair candidates include evidence-aware metadata:

- `repair_reason`
- `evidence_signal`
- `recommended_action_type`
- `user_friendly_message`

Low citation truth creates citation-focused repairs. Conflicts create conflict-aware answer behavior. Evidence gaps are marked as user action needed rather than blindly changing retrieval parameters. Freshness warnings keep date ambiguity visible.
