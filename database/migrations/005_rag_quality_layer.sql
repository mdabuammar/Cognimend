-- =============================================================================
-- Migration 005: Self-Healing RAG Quality Layer
-- =============================================================================
-- Adds: claim_verifications, answer_verification_summaries,
--       retrieval_metrics, citation_metrics, query_analysis,
--       drift_events (extended), config_versions, repair_candidates,
--       repair_evaluation_results, evaluation_questions,
--       rag_driftbench_scenarios, rag_driftbench_runs
-- =============================================================================

BEGIN;

-- =============================================================================
-- Extend query_events with faithfulness columns
-- =============================================================================

ALTER TABLE query_events
    ADD COLUMN IF NOT EXISTS faithfulness_score      FLOAT,
    ADD COLUMN IF NOT EXISTS unsupported_claim_rate  FLOAT,
    ADD COLUMN IF NOT EXISTS verification_status     VARCHAR(30),
    ADD COLUMN IF NOT EXISTS retrieval_top1_sim      FLOAT,
    ADD COLUMN IF NOT EXISTS retrieval_avg_sim       FLOAT,
    ADD COLUMN IF NOT EXISTS query_id_ext            UUID DEFAULT uuid_generate_v4();

CREATE INDEX IF NOT EXISTS idx_query_events_workspace_created
    ON query_events(workspace_id, created_at DESC);

-- =============================================================================
-- Claim Verifications
-- =============================================================================

CREATE TABLE IF NOT EXISTS claim_verifications (
    id                      SERIAL PRIMARY KEY,
    workspace_id            UUID NOT NULL,
    query_id                INTEGER REFERENCES query_events(id) ON DELETE CASCADE,
    claim_text              TEXT NOT NULL,
    status                  VARCHAR(20) NOT NULL DEFAULT 'uncertain',
                                 -- supported | unsupported | contradicted | uncertain
    confidence              FLOAT NOT NULL DEFAULT 0.0,
    evidence_chunk_id       TEXT,
    evidence_document_id    INTEGER,
    explanation             TEXT,
    verifier_model          VARCHAR(100),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_claim_verif_workspace
    ON claim_verifications(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claim_verif_query
    ON claim_verifications(query_id);

-- =============================================================================
-- Answer Verification Summaries
-- =============================================================================

CREATE TABLE IF NOT EXISTS answer_verification_summaries (
    id                          SERIAL PRIMARY KEY,
    workspace_id                UUID NOT NULL,
    query_id                    INTEGER REFERENCES query_events(id) ON DELETE CASCADE,
    total_claims                INTEGER NOT NULL DEFAULT 0,
    supported_claims            INTEGER NOT NULL DEFAULT 0,
    unsupported_claims          INTEGER NOT NULL DEFAULT 0,
    contradicted_claims         INTEGER NOT NULL DEFAULT 0,
    uncertain_claims            INTEGER NOT NULL DEFAULT 0,
    unsupported_claim_rate      FLOAT NOT NULL DEFAULT 0.0,
    contradicted_claim_rate     FLOAT NOT NULL DEFAULT 0.0,
    claim_support_rate          FLOAT NOT NULL DEFAULT 0.0,
    answer_faithfulness_score   FLOAT NOT NULL DEFAULT 0.0,
    verifier_status             VARCHAR(30) NOT NULL DEFAULT 'ok',
                                     -- ok | failed | skipped | timeout
    verifier_latency_ms         INTEGER,
    verifier_model              VARCHAR(100),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_avs_workspace
    ON answer_verification_summaries(workspace_id, created_at DESC);

-- =============================================================================
-- Retrieval Metrics (per query)
-- =============================================================================

CREATE TABLE IF NOT EXISTS retrieval_metrics (
    id                          SERIAL PRIMARY KEY,
    workspace_id                UUID NOT NULL,
    query_id                    INTEGER REFERENCES query_events(id) ON DELETE CASCADE,
    top1_similarity             FLOAT,
    top5_avg_similarity         FLOAT,
    top_k                       INTEGER,
    chunks_retrieved            INTEGER,
    zero_retrieval              BOOLEAN DEFAULT FALSE,
    low_similarity              BOOLEAN DEFAULT FALSE,
    retrieval_latency_ms        INTEGER,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_metrics_workspace
    ON retrieval_metrics(workspace_id, created_at DESC);

-- =============================================================================
-- Citation Metrics (per query)
-- =============================================================================

CREATE TABLE IF NOT EXISTS citation_metrics (
    id                          SERIAL PRIMARY KEY,
    workspace_id                UUID NOT NULL,
    query_id                    INTEGER REFERENCES query_events(id) ON DELETE CASCADE,
    total_citations             INTEGER DEFAULT 0,
    supported_citations         INTEGER DEFAULT 0,
    unsupported_citations       INTEGER DEFAULT 0,
    citation_support_score      FLOAT DEFAULT 0.0,
    wrong_citation_rate         FLOAT DEFAULT 0.0,
    missing_citation_rate       FLOAT DEFAULT 0.0,
    citation_coverage           FLOAT DEFAULT 0.0,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_citation_metrics_workspace
    ON citation_metrics(workspace_id, created_at DESC);

-- =============================================================================
-- Query Analysis (intent classification)
-- =============================================================================

CREATE TABLE IF NOT EXISTS query_analysis (
    id                  SERIAL PRIMARY KEY,
    workspace_id        UUID NOT NULL,
    query_id            INTEGER REFERENCES query_events(id) ON DELETE CASCADE,
    intent              VARCHAR(50) DEFAULT 'other',
                             -- simple_fact | summary | comparison | multi_hop |
                             --   temporal | policy_lookup | unsupported | other
    complexity_score    FLOAT DEFAULT 0.5,
    is_multi_hop        BOOLEAN DEFAULT FALSE,
    is_temporal         BOOLEAN DEFAULT FALSE,
    is_comparison       BOOLEAN DEFAULT FALSE,
    is_unanswerable     BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_analysis_workspace
    ON query_analysis(workspace_id, created_at DESC);

-- =============================================================================
-- Extend drift_events with full schema
-- =============================================================================

ALTER TABLE drift_events
    ADD COLUMN IF NOT EXISTS workspace_id       UUID,
    ADD COLUMN IF NOT EXISTS metric_name        VARCHAR(100),
    ADD COLUMN IF NOT EXISTS baseline_value     FLOAT,
    ADD COLUMN IF NOT EXISTS p_value            FLOAT,
    ADD COLUMN IF NOT EXISTS window_start       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS window_end         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS recommended_action TEXT,
    ADD COLUMN IF NOT EXISTS status             VARCHAR(30) DEFAULT 'open',
                                -- open | investigating | repair_candidate_generated |
                                --   repair_testing | repaired | rolled_back | ignored
    ADD COLUMN IF NOT EXISTS updated_at         TIMESTAMPTZ DEFAULT NOW();

-- drift_type extended: data_drift | retrieval_drift | citation_drift |
--                      query_drift | faithfulness_drift | performance_drift

CREATE INDEX IF NOT EXISTS idx_drift_events_workspace
    ON drift_events(workspace_id, created_at DESC);

-- =============================================================================
-- Config Versions (per-workspace config versioning)
-- =============================================================================

CREATE TABLE IF NOT EXISTS config_versions (
    id                      SERIAL PRIMARY KEY,
    workspace_id            UUID NOT NULL,
    version_number          INTEGER NOT NULL,
    config_json             JSONB NOT NULL,
    status                  VARCHAR(20) NOT NULL DEFAULT 'candidate',
                                 -- stable | candidate | testing | active | rejected | rolled_back
    created_by              VARCHAR(100) DEFAULT 'system',
    created_reason          TEXT,
    drift_event_id          UUID REFERENCES drift_events(id),
    evaluation_result_id    INTEGER,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_at              TIMESTAMPTZ,
    rolled_back_at          TIMESTAMPTZ,

    UNIQUE(workspace_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_config_versions_workspace
    ON config_versions(workspace_id, version_number DESC);

-- =============================================================================
-- Repair Candidates
-- =============================================================================

CREATE TABLE IF NOT EXISTS repair_candidates (
    id                          SERIAL PRIMARY KEY,
    workspace_id                UUID NOT NULL,
    drift_event_id              UUID REFERENCES drift_events(id),
    candidate_config_json       JSONB NOT NULL,
    repair_actions_json         JSONB NOT NULL DEFAULT '[]',
    expected_improvement        FLOAT,
    expected_cost_impact        FLOAT DEFAULT 0.0,
    expected_latency_impact     FLOAT DEFAULT 0.0,
    status                      VARCHAR(20) NOT NULL DEFAULT 'generated',
                                     -- generated | testing | approved | applied | rejected | failed
    rejected_reason             TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tested_at                   TIMESTAMPTZ,
    applied_at                  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_repair_candidates_workspace
    ON repair_candidates(workspace_id, created_at DESC);

-- =============================================================================
-- Repair Evaluation Results
-- =============================================================================

CREATE TABLE IF NOT EXISTS repair_evaluation_results (
    id                          SERIAL PRIMARY KEY,
    workspace_id                UUID NOT NULL,
    repair_candidate_id         INTEGER REFERENCES repair_candidates(id) ON DELETE CASCADE,
    baseline_config_version     INTEGER,
    candidate_config_version    INTEGER,
    baseline_metrics_json       JSONB,
    candidate_metrics_json      JSONB,
    improvement_json            JSONB,
    quality_improved            BOOLEAN,
    latency_acceptable          BOOLEAN,
    cost_acceptable             BOOLEAN,
    recommendation              VARCHAR(20) DEFAULT 'manual_review',
                                     -- apply | reject | manual_review
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_repair_eval_workspace
    ON repair_evaluation_results(workspace_id, created_at DESC);

-- FK back-reference
ALTER TABLE config_versions
    ADD CONSTRAINT fk_config_eval_result
    FOREIGN KEY (evaluation_result_id)
    REFERENCES repair_evaluation_results(id)
    ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;

-- =============================================================================
-- Evaluation Questions (workspace-scoped benchmark questions)
-- =============================================================================

CREATE TABLE IF NOT EXISTS evaluation_questions (
    id                          SERIAL PRIMARY KEY,
    workspace_id                UUID,        -- NULL = system-wide default
    question                    TEXT NOT NULL,
    expected_answer             TEXT,
    expected_source_document_id INTEGER,
    expected_source_chunk_id    TEXT,
    category                    VARCHAR(50) DEFAULT 'general',
    difficulty                  VARCHAR(20) DEFAULT 'medium',
    created_by                  VARCHAR(100) DEFAULT 'system',
    enabled                     BOOLEAN DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_questions_workspace
    ON evaluation_questions(workspace_id);

-- =============================================================================
-- RAG-DriftBench Scenarios
-- =============================================================================

CREATE TABLE IF NOT EXISTS rag_driftbench_scenarios (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) UNIQUE NOT NULL,
    drift_type      VARCHAR(50) NOT NULL,
    description     TEXT,
    setup_json      JSONB,
    expected_behavior TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the 7 canonical scenarios
INSERT INTO rag_driftbench_scenarios (name, drift_type, description, expected_behavior, setup_json)
VALUES
    ('document_update_drift', 'retrieval_drift',
     'Old document has outdated fact. New document has updated fact. System should use new fact.',
     'Answer uses new document. Old answer is no longer returned.',
     '{"old_doc_text": "Refund policy is 7 days.", "new_doc_text": "Refund policy is 14 days.", "test_question": "What is the refund policy?", "expected_answer_contains": "14 days"}'::jsonb),

    ('contradictory_evidence_drift', 'faithfulness_drift',
     'Two documents contradict each other on the same topic.',
     'System detects conflict, returns cautious answer with both sources cited.',
     '{"doc_a": "Remote work is allowed every day.", "doc_b": "Remote work is not permitted.", "test_question": "Is remote work allowed?", "expected_behavior": "conflict_detected"}'::jsonb),

    ('missing_evidence_drift', 'retrieval_drift',
     'User asks a question for which no documents exist.',
     'System admits insufficient evidence rather than hallucinating.',
     '{"test_question": "What is the quantum entanglement policy?", "expected_behavior": "abstain"}'::jsonb),

    ('query_distribution_drift', 'query_drift',
     'Query pattern shifts from simple facts to complex comparison queries.',
     'Query drift detected. Unanswerable rate or complexity rises.',
     '{"baseline_queries": ["What is the leave policy?"], "drifted_queries": ["Compare leave policy changes between 2024 and 2026 across departments."], "expected_drift_type": "query_drift"}'::jsonb),

    ('retrieval_degradation_drift', 'retrieval_drift',
     'Many irrelevant but semantically similar chunks injected into knowledge base.',
     'Retrieval quality drops, drift detected, repair improves top-k or adds reranker.',
     '{"inject_noise_chunks": 50, "noise_similarity_target": 0.6, "expected_metric_drop": "top1_similarity"}'::jsonb),

    ('citation_drift', 'citation_drift',
     'Answers are generated with citations pointing to wrong evidence chunks.',
     'Citation quality metric catches wrong citations, citation drift event raised.',
     '{"inject_wrong_citations": true, "wrong_citation_rate_target": 0.3, "expected_drift": "citation_drift"}'::jsonb),

    ('faithfulness_drift', 'faithfulness_drift',
     'LLM temperature raised to produce more creative (hallucinated) answers.',
     'Unsupported claim rate rises, faithfulness drift detected.',
     '{"raise_temperature": 0.9, "expected_unsupported_rate": "> 0.3", "expected_drift": "faithfulness_drift"}'::jsonb)

ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- RAG-DriftBench Runs
-- =============================================================================

CREATE TABLE IF NOT EXISTS rag_driftbench_runs (
    id                      SERIAL PRIMARY KEY,
    workspace_id            UUID NOT NULL,
    scenario_id             INTEGER REFERENCES rag_driftbench_scenarios(id),
    status                  VARCHAR(20) DEFAULT 'pending',
                                 -- pending | running | completed | failed
    baseline_metrics_json   JSONB,
    drifted_metrics_json    JSONB,
    repaired_metrics_json   JSONB,
    detection_success       BOOLEAN,
    repair_success          BOOLEAN,
    rollback_success        BOOLEAN,
    error_message           TEXT,
    started_at              TIMESTAMPTZ DEFAULT NOW(),
    finished_at             TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_driftbench_runs_workspace
    ON rag_driftbench_runs(workspace_id, started_at DESC);

COMMIT;
