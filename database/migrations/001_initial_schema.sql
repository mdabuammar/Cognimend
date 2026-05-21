-- =============================================================================
-- Migration 001: Initial Schema
-- =============================================================================
-- Created: 2024-01-15
-- Description: Creates the initial database schema for DriftGuard
-- =============================================================================

BEGIN;

-- =============================================================================
-- Extensions
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- Users Table
-- =============================================================================
-- Note: If using Supabase Auth, this table is managed by Supabase
-- Only create if using custom auth

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255), -- NEVER store plain text!
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

-- =============================================================================
-- Documents Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    version VARCHAR(50) DEFAULT 'v1.0',
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'ready', 'error')),
    content_hash VARCHAR(64) NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    chunk_count INTEGER DEFAULT 0,
    error_message TEXT,
    description TEXT,
    content_preview TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint: same file (by hash) can't be uploaded twice by same user
    CONSTRAINT unique_user_document_hash UNIQUE (user_id, content_hash)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);

-- =============================================================================
-- Chunks Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    token_count INTEGER,
    vector_id VARCHAR(255), -- Reference to vector in Qdrant
    metadata JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processed', 'error')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint: no duplicate chunks per document
    CONSTRAINT unique_document_chunk UNIQUE (document_id, chunk_index)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_vector ON chunks(vector_id) WHERE vector_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS query_events (
    id SERIAL PRIMARY KEY,
    workspace_id UUID,
    question TEXT NOT NULL,
    answer TEXT,
    retrieved_doc_ids INTEGER[],
    similarities FLOAT[],
    confidence FLOAT,
    latency_ms INTEGER,
    cost_usd FLOAT DEFAULT 0.0,
    tokens_used INTEGER DEFAULT 0,
    model_used VARCHAR(50) DEFAULT 'gpt-4o',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_events_created_at ON query_events(created_at DESC);

-- =============================================================================
-- Queries Table (Audit Log)
-- =============================================================================

CREATE TABLE IF NOT EXISTS queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id UUID,
    question TEXT NOT NULL,
    -- Don't store full answer to save space, just key metrics
    answer_preview VARCHAR(500),
    confidence DECIMAL(5,2),
    documents_searched INTEGER,
    chunks_retrieved INTEGER,
    latency_ms INTEGER,
    cache_hit BOOLEAN DEFAULT FALSE,
    model_used VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_queries_user ON queries(user_id);
CREATE INDEX IF NOT EXISTS idx_queries_created ON queries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_queries_confidence ON queries(confidence);

-- =============================================================================
-- Feedback Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_id UUID NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feedback_type VARCHAR(20) NOT NULL CHECK (feedback_type IN ('positive', 'negative')),
    feedback_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- One feedback per query per user
    CONSTRAINT unique_query_user_feedback UNIQUE (query_id, user_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_feedback_query ON feedback(query_id);
CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(feedback_type);

-- =============================================================================
-- Drift Events Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS drift_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drift_type VARCHAR(50) NOT NULL CHECK (drift_type IN ('data', 'retrieval', 'performance', 'concept')),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    score DECIMAL(5,4) NOT NULL,
    threshold DECIMAL(5,4) NOT NULL,
    description TEXT,
    affected_documents UUID[],
    auto_fix_applied BOOLEAN DEFAULT FALSE,
    auto_fix_action VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_drift_type ON drift_events(drift_type);
CREATE INDEX IF NOT EXISTS idx_drift_severity ON drift_events(severity);
CREATE INDEX IF NOT EXISTS idx_drift_created ON drift_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_drift_unresolved ON drift_events(resolved_at) WHERE resolved_at IS NULL;

-- =============================================================================
-- Updated At Trigger
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to documents
DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Row Level Security
-- =============================================================================

-- Enable RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE drift_events ENABLE ROW LEVEL SECURITY;

-- Apply policies (see rls_policies.sql for full policy definitions)

COMMIT;

-- =============================================================================
-- Rollback Script (Save separately!)
-- =============================================================================
-- BEGIN;
-- DROP TABLE IF EXISTS drift_events CASCADE;
-- DROP TABLE IF EXISTS feedback CASCADE;
-- DROP TABLE IF EXISTS queries CASCADE;
-- DROP TABLE IF EXISTS chunks CASCADE;
-- DROP TABLE IF EXISTS documents CASCADE;
-- DROP FUNCTION IF EXISTS update_updated_at_column();
-- COMMIT;
