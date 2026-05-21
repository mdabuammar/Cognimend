-- Migration 010: query_events live proof stability columns

BEGIN;

ALTER TABLE query_events
    ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS model_used VARCHAR(100),
    ADD COLUMN IF NOT EXISTS citations_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS workspace_id UUID,
    ADD COLUMN IF NOT EXISTS user_id UUID,
    ADD COLUMN IF NOT EXISTS faithfulness_score FLOAT,
    ADD COLUMN IF NOT EXISTS unsupported_claim_rate FLOAT,
    ADD COLUMN IF NOT EXISTS verification_status VARCHAR(50),
    ADD COLUMN IF NOT EXISTS retrieval_top1_sim FLOAT,
    ADD COLUMN IF NOT EXISTS retrieval_avg_sim FLOAT,
    ADD COLUMN IF NOT EXISTS citation_truth_score FLOAT,
    ADD COLUMN IF NOT EXISTS conflict_detected BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS evidence_gap_detected BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS freshness_warning BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS evidence_gap_summary TEXT,
    ADD COLUMN IF NOT EXISTS suggested_actions JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS conflict_details JSONB DEFAULT '[]'::jsonb;

ALTER TABLE query_events
    ALTER COLUMN retrieved_doc_ids TYPE TEXT[] USING retrieved_doc_ids::TEXT[];

ALTER TABLE claim_verifications
    ALTER COLUMN evidence_document_id TYPE TEXT USING evidence_document_id::TEXT;

ALTER TABLE citation_verifications
    ALTER COLUMN document_id TYPE TEXT USING document_id::TEXT;

ALTER TABLE conflict_events
    ALTER COLUMN document_id_a TYPE TEXT USING document_id_a::TEXT,
    ALTER COLUMN document_id_b TYPE TEXT USING document_id_b::TEXT;

ALTER TABLE freshness_warnings
    ALTER COLUMN outdated_document_id TYPE TEXT USING outdated_document_id::TEXT,
    ALTER COLUMN newer_document_id TYPE TEXT USING newer_document_id::TEXT;

COMMIT;
