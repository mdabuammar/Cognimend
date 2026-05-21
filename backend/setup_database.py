"""
Database schema setup for production RAG system
Run this to initialize all necessary tables and indexes
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment
load_dotenv(".env.production")

def setup_database():
    """Initialize production database schema"""
    
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "cognimend_prod"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
    
    cur = conn.cursor()
    
    print("🔧 Setting up production database schema...")
    
    # ========== QUERY EVENTS TABLE ==========
    print("  Creating query_events table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS query_events (
            id SERIAL PRIMARY KEY,
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
        )
    """)
    
    # Create indexes for performance
    print("  Creating indexes...")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_query_events_created_at ON query_events(created_at DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_query_events_confidence ON query_events(confidence DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_query_events_latency ON query_events(latency_ms)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_query_events_cost ON query_events(cost_usd DESC)"
    )
    
    # ========== DAILY METRICS TABLE ==========
    print("  Creating daily_metrics table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            id SERIAL PRIMARY KEY,
            metric_date DATE NOT NULL UNIQUE,
            total_queries INTEGER DEFAULT 0,
            avg_confidence FLOAT DEFAULT 0.0,
            avg_latency_ms FLOAT DEFAULT 0.0,
            total_cost_usd FLOAT DEFAULT 0.0,
            total_tokens BIGINT DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            error_rate FLOAT DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(metric_date DESC)"
    )
    
    # ========== ERROR LOGS TABLE ==========
    print("  Creating error_logs table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS error_logs (
            id SERIAL PRIMARY KEY,
            error_type VARCHAR(100) NOT NULL,
            error_message TEXT,
            question TEXT,
            stack_trace TEXT,
            service VARCHAR(50),
            severity VARCHAR(20) DEFAULT 'ERROR',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_error_logs_created_at ON error_logs(created_at DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_error_logs_type ON error_logs(error_type)"
    )
    
    # ========== COST TRACKING TABLE ==========
    print("  Creating cost_tracking table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cost_tracking (
            id SERIAL PRIMARY KEY,
            model VARCHAR(50) NOT NULL,
            input_tokens BIGINT DEFAULT 0,
            output_tokens BIGINT DEFAULT 0,
            cost_usd FLOAT DEFAULT 0.0,
            operation_type VARCHAR(50),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cost_tracking_created_at ON cost_tracking(created_at DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cost_tracking_model ON cost_tracking(model)"
    )
    
    # ========== LATENCY TRACKING TABLE ==========
    print("  Creating latency_tracking table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS latency_tracking (
            id SERIAL PRIMARY KEY,
            service VARCHAR(50) NOT NULL,
            endpoint VARCHAR(100),
            latency_ms INTEGER,
            status_code INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_latency_tracking_created_at ON latency_tracking(created_at DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_latency_tracking_service ON latency_tracking(service)"
    )
    
    # ========== USER FEEDBACK TABLE ==========
    print("  Creating user_feedback table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_feedback (
            id SERIAL PRIMARY KEY,
            query_event_id INTEGER REFERENCES query_events(id),
            rating INTEGER CHECK (rating >= 1 AND rating <= 5),
            feedback TEXT,
            helpful BOOLEAN,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_feedback_created_at ON user_feedback(created_at DESC)"
    )
    
    # ========== DOCUMENT QUALITY TABLE ==========
    print("  Creating document_quality table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_quality (
            id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL,
            title VARCHAR(255),
            relevance_score FLOAT,
            retrieval_count INTEGER DEFAULT 0,
            useful_count INTEGER DEFAULT 0,
            quality_score FLOAT GENERATED ALWAYS AS (
                CASE 
                    WHEN retrieval_count = 0 THEN 0.0
                    ELSE (useful_count::FLOAT / retrieval_count) * 100
                END
            ) STORED,
            last_updated TIMESTAMP DEFAULT NOW()
        )
    """)
    
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_quality_doc_id ON document_quality(document_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_quality_score ON document_quality(quality_score DESC)"
    )
    
    # ========== ALERTS TABLE ==========
    print("  Creating alerts table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            alert_type VARCHAR(100) NOT NULL,
            severity VARCHAR(20) DEFAULT 'WARNING',
            message TEXT,
            metric_value FLOAT,
            threshold FLOAT,
            acknowledged BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            acknowledged_at TIMESTAMP
        )
    """)
    
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged)"
    )
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("✅ Database schema setup complete!")
    print("\nCreated tables:")
    print("  - query_events (main query tracking)")
    print("  - daily_metrics (aggregated daily stats)")
    print("  - error_logs (error tracking)")
    print("  - cost_tracking (API cost tracking)")
    print("  - latency_tracking (performance monitoring)")
    print("  - user_feedback (user ratings and feedback)")
    print("  - document_quality (document performance metrics)")
    print("  - alerts (system alerts)")


if __name__ == "__main__":
    try:
        setup_database()
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        exit(1)
