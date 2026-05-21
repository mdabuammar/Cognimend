-- =============================================================================
-- Migration 009: True Trust Engine Persistence
-- =============================================================================
-- Adds support for storing citation truth, conflict detection,
-- evidence gap detection, and freshness warnings.
-- =============================================================================

BEGIN;

-- Extend query_events with new trust engine columns
ALTER TABLE query_events
    ADD COLUMN IF NOT EXISTS citation_truth_score FLOAT,
    ADD COLUMN IF NOT EXISTS citation_quality_label VARCHAR(20),
    ADD COLUMN IF NOT EXISTS conflict_detected BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS conflict_summary TEXT,
    ADD COLUMN IF NOT EXISTS conflict_sources JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS evidence_gap_detected BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS freshness_warning BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS freshness_warning_text TEXT,
    ADD COLUMN IF NOT EXISTS latest_source_id TEXT,
    ADD COLUMN IF NOT EXISTS evidence_gap_summary TEXT,
    ADD COLUMN IF NOT EXISTS missing_information JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS suggested_actions JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS conflict_details JSONB DEFAULT '[]'::jsonb;

-- 1. citation_verifications table
CREATE TABLE IF NOT EXISTS citation_verifications (
    id SERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL,
    query_id INTEGER REFERENCES query_events(id) ON DELETE CASCADE,
    document_id INTEGER,
    chunk_id TEXT,
    claim_id TEXT,
    title VARCHAR(255),
    snippet TEXT,
    similarity FLOAT,
    support_status VARCHAR(20),
    support_score FLOAT,
    explanation TEXT,
    truth_score FLOAT,
    is_supported BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE citation_verifications
    ADD COLUMN IF NOT EXISTS chunk_id TEXT,
    ADD COLUMN IF NOT EXISTS claim_id TEXT,
    ADD COLUMN IF NOT EXISTS support_status VARCHAR(20),
    ADD COLUMN IF NOT EXISTS support_score FLOAT,
    ADD COLUMN IF NOT EXISTS explanation TEXT;
CREATE INDEX IF NOT EXISTS idx_citation_verif_workspace ON citation_verifications(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_citation_verif_query ON citation_verifications(query_id);
CREATE INDEX IF NOT EXISTS idx_citation_verif_created_at ON citation_verifications(created_at DESC);

-- 2. conflict_events table
CREATE TABLE IF NOT EXISTS conflict_events (
    id SERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL,
    query_id INTEGER REFERENCES query_events(id) ON DELETE CASCADE,
    document_id_a INTEGER,
    document_id_b INTEGER,
    document_title_a VARCHAR(255),
    document_title_b VARCHAR(255),
    topic TEXT,
    conflict_summary TEXT,
    conflict_sources_json JSONB DEFAULT '[]'::jsonb,
    severity VARCHAR(20) DEFAULT 'medium',
    conflict_explanation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE conflict_events
    ADD COLUMN IF NOT EXISTS conflict_summary TEXT,
    ADD COLUMN IF NOT EXISTS conflict_sources_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS severity VARCHAR(20) DEFAULT 'medium';
CREATE INDEX IF NOT EXISTS idx_conflict_events_workspace ON conflict_events(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conflict_events_query ON conflict_events(query_id);
CREATE INDEX IF NOT EXISTS idx_conflict_events_created_at ON conflict_events(created_at DESC);

-- 3. evidence_gaps table
CREATE TABLE IF NOT EXISTS evidence_gaps (
    id SERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL,
    query_id INTEGER REFERENCES query_events(id) ON DELETE CASCADE,
    question TEXT,
    gap_summary TEXT,
    evidence_gap_summary TEXT,
    missing_information_json JSONB DEFAULT '[]'::jsonb,
    suggested_actions JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE evidence_gaps
    ADD COLUMN IF NOT EXISTS evidence_gap_summary TEXT,
    ADD COLUMN IF NOT EXISTS missing_information_json JSONB DEFAULT '[]'::jsonb;
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_workspace ON evidence_gaps(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_query ON evidence_gaps(query_id);
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_created_at ON evidence_gaps(created_at DESC);

-- 4. freshness_warnings table
CREATE TABLE IF NOT EXISTS freshness_warnings (
    id SERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL,
    query_id INTEGER REFERENCES query_events(id) ON DELETE CASCADE,
    outdated_document_id INTEGER,
    newer_document_id INTEGER,
    outdated_doc_title VARCHAR(255),
    newer_doc_title VARCHAR(255),
    explanation TEXT,
    latest_source_id TEXT,
    warning_text TEXT,
    source_metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE freshness_warnings
    ADD COLUMN IF NOT EXISTS latest_source_id TEXT,
    ADD COLUMN IF NOT EXISTS warning_text TEXT,
    ADD COLUMN IF NOT EXISTS source_metadata_json JSONB DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS idx_freshness_warnings_workspace ON freshness_warnings(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_freshness_warnings_query ON freshness_warnings(query_id);
CREATE INDEX IF NOT EXISTS idx_freshness_warnings_created_at ON freshness_warnings(created_at DESC);

ALTER TABLE repair_candidates
    ADD COLUMN IF NOT EXISTS repair_reason TEXT,
    ADD COLUMN IF NOT EXISTS evidence_signal VARCHAR(50),
    ADD COLUMN IF NOT EXISTS recommended_action_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS user_friendly_message TEXT;

COMMIT;
