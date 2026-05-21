-- =============================================================================
-- Row Level Security (RLS) Policies for DriftGuard
-- =============================================================================
-- Apply these policies in Supabase SQL Editor or via migrations
-- IMPORTANT: Enable RLS on all tables before applying policies
-- =============================================================================

-- =============================================================================
-- Enable RLS on All Tables
-- =============================================================================

ALTER TABLE IF EXISTS documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS drift_events ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- Documents Table Policies
-- =============================================================================
-- Users can only access their own documents

-- SELECT: Users can view their own documents
CREATE POLICY "documents_select_own" ON documents
    FOR SELECT
    USING (auth.uid() = user_id);

-- INSERT: Users can create documents for themselves
CREATE POLICY "documents_insert_own" ON documents
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- UPDATE: Users can update their own documents
CREATE POLICY "documents_update_own" ON documents
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- DELETE: Users can delete their own documents
CREATE POLICY "documents_delete_own" ON documents
    FOR DELETE
    USING (auth.uid() = user_id);

-- =============================================================================
-- Chunks Table Policies
-- =============================================================================
-- Chunks inherit access from parent document

-- SELECT: Users can view chunks of their documents
CREATE POLICY "chunks_select_via_document" ON chunks
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM documents
            WHERE documents.id = chunks.document_id
            AND documents.user_id = auth.uid()
        )
    );

-- INSERT: Only system can insert chunks (via service role)
-- No user-facing insert policy

-- DELETE: Chunks deleted via cascade when document is deleted
-- No explicit delete policy needed

-- =============================================================================
-- Queries Table Policies
-- =============================================================================
-- Users can only see their own queries

-- SELECT: Users can view their own queries
CREATE POLICY "queries_select_own" ON queries
    FOR SELECT
    USING (auth.uid() = user_id);

-- INSERT: Users can create queries for themselves
CREATE POLICY "queries_insert_own" ON queries
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- UPDATE: No updates allowed on queries (immutable audit log)
-- DELETE: No deletes allowed on queries (audit trail)

-- =============================================================================
-- Feedback Table Policies
-- =============================================================================

-- SELECT: Users can view their own feedback
CREATE POLICY "feedback_select_own" ON feedback
    FOR SELECT
    USING (auth.uid() = user_id);

-- INSERT: Users can submit feedback
CREATE POLICY "feedback_insert_own" ON feedback
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- UPDATE: Users can update their own feedback
CREATE POLICY "feedback_update_own" ON feedback
    FOR UPDATE
    USING (auth.uid() = user_id);

-- DELETE: Users can delete their own feedback
CREATE POLICY "feedback_delete_own" ON feedback
    FOR DELETE
    USING (auth.uid() = user_id);

-- =============================================================================
-- Drift Events Table Policies
-- =============================================================================
-- Only admins can view drift events

-- SELECT: Only admins can view drift events
CREATE POLICY "drift_events_select_admin" ON drift_events
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM users
            WHERE users.id = auth.uid()
            AND users.role = 'admin'
        )
    );

-- INSERT: Only system can insert drift events (via service role)
-- No user-facing insert policy

-- =============================================================================
-- Admin Override Policies
-- =============================================================================
-- Admins can access all data (be careful with this!)

-- Uncomment if you want admin access to all documents:
-- CREATE POLICY "admin_access_all_documents" ON documents
--     FOR ALL
--     USING (
--         EXISTS (
--             SELECT 1 FROM users
--             WHERE users.id = auth.uid()
--             AND users.role = 'admin'
--         )
--     );

-- =============================================================================
-- Service Role Bypass
-- =============================================================================
-- The service_role key bypasses RLS - use ONLY in backend services!
-- NEVER expose service_role key to frontend or client code!

-- =============================================================================
-- Helper Function: Get Current User ID
-- =============================================================================

CREATE OR REPLACE FUNCTION current_user_id()
RETURNS UUID
LANGUAGE SQL
STABLE
AS $$
    SELECT auth.uid()
$$;

-- =============================================================================
-- Verification Queries
-- =============================================================================
-- Run these to verify RLS is properly configured:

-- Check if RLS is enabled:
-- SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';

-- List all policies:
-- SELECT tablename, policyname, permissive, roles, cmd, qual 
-- FROM pg_policies 
-- WHERE schemaname = 'public';
