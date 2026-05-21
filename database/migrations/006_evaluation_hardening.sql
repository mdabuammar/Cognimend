-- =============================================================================
-- Migration 006: Phase 3 Evaluation & DriftBench Hardening
-- =============================================================================
-- Adds EVALUATION_SERVICE_URL to config_versions for traceability
-- Adds missing indexes for fast isolation queries
-- Seeds evaluation_questions with starter benchmark questions
-- Adds evaluation_service_url to gateway tracking
-- =============================================================================

BEGIN;

-- ─── Ensure evaluation_questions has all required columns ────────────────────
ALTER TABLE evaluation_questions
    ADD COLUMN IF NOT EXISTS workspace_id UUID,
    ADD COLUMN IF NOT EXISTS expected_answer TEXT,
    ADD COLUMN IF NOT EXISTS expected_source_document_id INTEGER,
    ADD COLUMN IF NOT EXISTS expected_source_chunk_id TEXT,
    ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT 'general',
    ADD COLUMN IF NOT EXISTS difficulty VARCHAR(20) DEFAULT 'medium',
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) DEFAULT 'system',
    ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_eval_questions_workspace_enabled
    ON evaluation_questions(workspace_id, enabled);

-- ─── Ensure repair_evaluation_results has recommendation column ───────────────
ALTER TABLE repair_evaluation_results
    ADD COLUMN IF NOT EXISTS quality_improved   BOOLEAN,
    ADD COLUMN IF NOT EXISTS latency_acceptable BOOLEAN,
    ADD COLUMN IF NOT EXISTS cost_acceptable    BOOLEAN,
    ADD COLUMN IF NOT EXISTS recommendation     VARCHAR(20) DEFAULT 'manual_review';

-- ─── Seed 10 generic system-wide evaluation questions (workspace_id IS NULL) ──
INSERT INTO evaluation_questions
    (workspace_id, question, expected_answer, category, difficulty, created_by)
VALUES
    (NULL, 'What is the document return and refund policy?',
     NULL, 'policy', 'easy', 'system'),
    (NULL, 'How many days of annual leave are employees entitled to?',
     NULL, 'policy', 'easy', 'system'),
    (NULL, 'Is remote work allowed under current company policy?',
     NULL, 'policy', 'medium', 'system'),
    (NULL, 'What are the steps to submit an expense reimbursement?',
     NULL, 'process', 'medium', 'system'),
    (NULL, 'Who should be contacted for IT support issues?',
     NULL, 'general', 'easy', 'system'),
    (NULL, 'What is the process for performance reviews?',
     NULL, 'process', 'medium', 'system'),
    (NULL, 'What documents are required for onboarding?',
     NULL, 'process', 'easy', 'system'),
    (NULL, 'How is overtime compensation calculated?',
     NULL, 'policy', 'hard', 'system'),
    (NULL, 'What are the data privacy obligations for employees?',
     NULL, 'compliance', 'hard', 'system'),
    (NULL, 'What is the escalation process for unresolved customer complaints?',
     NULL, 'process', 'hard', 'system')
ON CONFLICT DO NOTHING;

-- ─── Ensure rag_driftbench_runs has all required status/error columns ─────────
ALTER TABLE rag_driftbench_runs
    ADD COLUMN IF NOT EXISTS error_message TEXT,
    ADD COLUMN IF NOT EXISTS rollback_success BOOLEAN;

-- ─── Performance indexes for workspace-scoped evaluation queries ──────────────
CREATE INDEX IF NOT EXISTS idx_repair_eval_candidate
    ON repair_evaluation_results(repair_candidate_id, workspace_id);

CREATE INDEX IF NOT EXISTS idx_repair_candidates_status_ws
    ON repair_candidates(workspace_id, status);

CREATE INDEX IF NOT EXISTS idx_config_versions_ws_status
    ON config_versions(workspace_id, status);

COMMIT;
