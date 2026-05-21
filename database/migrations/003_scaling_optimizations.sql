-- Database scaling optimizations for 100K+ queries/day
-- Run this migration to optimize PostgreSQL for production scale

-- ============================================================
-- 1. Partitioning for queries table (time-based)
-- ============================================================

-- Create partitioned queries table
CREATE TABLE IF NOT EXISTS queries_partitioned (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    query_text TEXT NOT NULL,
    query_hash VARCHAR(64) NOT NULL,  -- For deduplication/caching
    response_text TEXT,
    confidence DECIMAL(5,2),
    response_time_ms INTEGER,
    tokens_used INTEGER,
    model_used VARCHAR(100),
    cache_hit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions for next 12 months
DO $$
DECLARE
    start_date DATE := DATE_TRUNC('month', CURRENT_DATE);
    partition_date DATE;
    partition_name TEXT;
    next_date DATE;
BEGIN
    FOR i IN 0..11 LOOP
        partition_date := start_date + (i || ' months')::INTERVAL;
        next_date := partition_date + INTERVAL '1 month';
        partition_name := 'queries_y' || TO_CHAR(partition_date, 'YYYY') || 'm' || TO_CHAR(partition_date, 'MM');
        
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF queries_partitioned 
             FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            partition_date,
            next_date
        );
    END LOOP;
END $$;

-- Create default partition for data outside defined ranges
CREATE TABLE IF NOT EXISTS queries_default PARTITION OF queries_partitioned DEFAULT;

-- Indexes on partitioned table
CREATE INDEX IF NOT EXISTS idx_queries_user_id ON queries_partitioned (user_id);
CREATE INDEX IF NOT EXISTS idx_queries_created_at ON queries_partitioned (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_queries_hash ON queries_partitioned (query_hash);


-- ============================================================
-- 2. Materialized views for analytics (avoid expensive aggregations)
-- ============================================================

-- Daily query statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_query_stats AS
SELECT 
    DATE_TRUNC('day', created_at) as day,
    user_id,
    COUNT(*) as query_count,
    COUNT(*) FILTER (WHERE cache_hit = TRUE) as cache_hits,
    AVG(confidence) as avg_confidence,
    AVG(response_time_ms) as avg_response_time_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95_response_time,
    SUM(tokens_used) as total_tokens,
    COUNT(DISTINCT query_hash) as unique_queries
FROM queries_partitioned
WHERE created_at > NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', created_at), user_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_query_stats_day_user 
ON daily_query_stats (day, user_id);

-- Hourly system stats (for real-time dashboards)
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_system_stats AS
SELECT 
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as query_count,
    COUNT(DISTINCT user_id) as unique_users,
    AVG(response_time_ms) as avg_response_time_ms,
    SUM(tokens_used) as total_tokens,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*), 0) as cache_hit_rate
FROM queries_partitioned
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', created_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_hourly_system_stats_hour 
ON hourly_system_stats (hour);


-- ============================================================
-- 3. Document search optimization with GIN indexes
-- ============================================================

-- Add search vector column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'documents' AND column_name = 'search_vector'
    ) THEN
        ALTER TABLE documents ADD COLUMN search_vector tsvector;
    END IF;
END $$;

-- Create GIN index for full-text search
CREATE INDEX IF NOT EXISTS idx_documents_search 
ON documents USING gin(search_vector);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_documents_user_status 
ON documents (user_id, status) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_documents_created_at 
ON documents (created_at DESC);

-- Trigger to auto-update search vector
CREATE OR REPLACE FUNCTION documents_search_vector_update() 
RETURNS trigger AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.name, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.content_preview, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS documents_search_vector_trigger ON documents;
CREATE TRIGGER documents_search_vector_trigger
    BEFORE INSERT OR UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION documents_search_vector_update();


-- ============================================================
-- 4. Chunks table optimization
-- ============================================================

-- Index for efficient chunk retrieval
CREATE INDEX IF NOT EXISTS idx_chunks_document_id 
ON chunks (document_id);

CREATE INDEX IF NOT EXISTS idx_chunks_document_position 
ON chunks (document_id, chunk_index);


-- ============================================================
-- 5. User activity tracking (for rate limiting)
-- ============================================================

CREATE TABLE IF NOT EXISTS user_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    count INTEGER DEFAULT 1,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE (user_id, action, window_start)
);

CREATE INDEX IF NOT EXISTS idx_user_activity_lookup 
ON user_activity (user_id, action, window_start, window_end);

-- Auto-cleanup old activity records
CREATE OR REPLACE FUNCTION cleanup_old_activity() 
RETURNS void AS $$
BEGIN
    DELETE FROM user_activity WHERE window_end < NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- 6. Cache metadata table
-- ============================================================

CREATE TABLE IF NOT EXISTS cache_metadata (
    cache_key VARCHAR(255) PRIMARY KEY,
    cache_type VARCHAR(50) NOT NULL,
    hit_count INTEGER DEFAULT 0,
    last_hit_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    size_bytes INTEGER
);

CREATE INDEX IF NOT EXISTS idx_cache_metadata_expires 
ON cache_metadata (expires_at);

CREATE INDEX IF NOT EXISTS idx_cache_metadata_type 
ON cache_metadata (cache_type);


-- ============================================================
-- 7. Table statistics for query planner
-- ============================================================

-- Increase statistics target for frequently queried columns
DO $$
BEGIN
    -- Documents table
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents' AND column_name = 'user_id') THEN
        ALTER TABLE documents ALTER COLUMN user_id SET STATISTICS 1000;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents' AND column_name = 'status') THEN
        ALTER TABLE documents ALTER COLUMN status SET STATISTICS 1000;
    END IF;
    
    -- Queries table
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'queries_partitioned') THEN
        ALTER TABLE queries_partitioned ALTER COLUMN user_id SET STATISTICS 1000;
        ALTER TABLE queries_partitioned ALTER COLUMN created_at SET STATISTICS 1000;
    END IF;
END $$;


-- ============================================================
-- 8. Refresh functions for materialized views
-- ============================================================

CREATE OR REPLACE FUNCTION refresh_daily_stats() 
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW daily_query_stats;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION refresh_hourly_stats() 
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW hourly_system_stats;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- 9. Vacuum and analyze
-- ============================================================

-- Run analyze on main tables (should be scheduled via cron in production)
ANALYZE documents;
ANALYZE chunks;

-- ============================================================
-- PostgreSQL Configuration Recommendations
-- Add these to postgresql.conf for production:
-- ============================================================
/*
# Memory Settings (adjust based on available RAM)
shared_buffers = 4GB                    # 25% of RAM
effective_cache_size = 12GB             # 75% of RAM
work_mem = 256MB                        # For complex queries
maintenance_work_mem = 1GB              # For VACUUM, CREATE INDEX

# Write Performance
wal_buffers = 64MB
checkpoint_completion_target = 0.9
max_wal_size = 4GB
min_wal_size = 1GB

# Query Planner
random_page_cost = 1.1                  # For SSD storage
effective_io_concurrency = 200          # For SSD storage
default_statistics_target = 100

# Parallelism
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_parallel_maintenance_workers = 4

# Connections
max_connections = 200
superuser_reserved_connections = 3

# Logging (for monitoring)
log_min_duration_statement = 1000       # Log queries > 1 second
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on
log_temp_files = 0

# Autovacuum (more aggressive for high-write tables)
autovacuum_vacuum_scale_factor = 0.1
autovacuum_analyze_scale_factor = 0.05
autovacuum_vacuum_cost_limit = 1000
*/
