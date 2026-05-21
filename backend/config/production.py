"""
Production-grade configuration for the Cognimend RAG system
Optimized for: Quality > Speed > Cost
"""

import os
from typing import Optional
from pydantic import BaseSettings, validator


class ProductionConfig(BaseSettings):
    """Production configuration with validation"""

    # ========== API KEYS ==========
    OPENAI_API_KEY: str
    OPENAI_ORG_ID: Optional[str] = None

    # ========== MODELS (BEST QUALITY) ==========
    EMBEDDING_MODEL: str = "text-embedding-3-large"  # Best embeddings
    GENERATION_MODEL: str = "gpt-4o"  # Best reasoning
    FALLBACK_MODEL: str = "gpt-4o-mini"  # Fallback if quota exceeded

    # ========== RAG PARAMETERS (OPTIMIZED FOR QUALITY) ==========
    CHUNK_SIZE: int = 512  # Optimal balance
    CHUNK_OVERLAP: int = 128  # Higher overlap = better context

    # Retrieval settings
    DEFAULT_TOP_K: int = 5  # More context = better answers
    MAX_TOP_K: int = 10
    MIN_SIMILARITY: float = 0.7  # Only high-quality matches

    # Generation settings
    GPT_TEMPERATURE: float = 0.1  # Low = more consistent, factual
    GPT_MAX_TOKENS: int = 800  # Detailed answers
    GPT_TOP_P: float = 0.95
    GPT_FREQUENCY_PENALTY: float = 0.3
    GPT_PRESENCE_PENALTY: float = 0.1

    # ========== PERFORMANCE ==========
    # Connection pooling
    MAX_CONCURRENT_REQUESTS: int = 100
    TIMEOUT_SECONDS: int = 30

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_PER_HOUR: int = 1000

    # Caching
    ENABLE_CACHE: bool = True
    CACHE_TTL_SECONDS: int = 3600  # 1 hour
    CACHE_MAX_SIZE: int = 1000

    # ========== RETRY & RESILIENCE ==========
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: float = 1.0
    EXPONENTIAL_BACKOFF: bool = True
    CIRCUIT_BREAKER_THRESHOLD: int = 5  # Fail after 5 consecutive errors

    # ========== MONITORING ==========
    ENABLE_TELEMETRY: bool = True
    LOG_LEVEL: str = "INFO"
    ENABLE_COST_TRACKING: bool = True
    ENABLE_LATENCY_TRACKING: bool = True

    # Alerting thresholds
    ALERT_LATENCY_MS: int = 3000  # Alert if query > 3s
    ALERT_ERROR_RATE: float = 0.05  # Alert if error rate > 5%
    ALERT_DAILY_COST: float = 50.0  # Alert if daily cost > $50

    # ========== SYSTEM PROMPT (PRODUCTION) ==========
    SYSTEM_PROMPT: str = """You are a highly accurate AI assistant for a knowledge retrieval system.

CRITICAL RULES:
1. Answer ONLY using the provided context - never use external knowledge
2. If the context doesn't contain the answer, respond: "I don't have sufficient information to answer this question accurately."
3. Always cite the specific document(s) you're referencing
4. Be precise and factual - avoid speculation or assumptions
5. If multiple documents conflict, acknowledge the discrepancy
6. Provide detailed, comprehensive answers when the context supports it
7. Use professional, clear language

QUALITY STANDARDS:
- Accuracy is paramount
- Cite sources explicitly
- Be thorough but concise
- Acknowledge uncertainty when appropriate"""

    class Config:
        env_file = ".env"
        case_sensitive = True

    @validator("OPENAI_API_KEY")
    def validate_api_key(cls, v):
        if not v or not v.startswith("sk-"):
            raise ValueError("Invalid OpenAI API key")
        return v


# Initialize config
try:
    config = ProductionConfig()
except Exception as e:
    print(f"⚠️ Warning: Could not load production config - {e}")
    print("Using environment variables or defaults")
    config = None
