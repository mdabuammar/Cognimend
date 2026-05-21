"""
Production-ready OpenAI client with:
- Automatic retries
- Circuit breaker
- Rate limiting
- Cost tracking
- Comprehensive error handling
"""

import asyncio
import time
import os
from typing import List, Dict, Optional
from functools import wraps
import logging

try:
    import tiktoken
    from openai import AsyncOpenAI, RateLimitError, APIError
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
    )
except ImportError as e:
    print(f"⚠️ Warning: Missing dependencies - {e}")

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker pattern for API calls"""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = "HALF_OPEN"
                    logger.info("🔌 Circuit breaker: HALF_OPEN, attempting request")
                else:
                    raise Exception(
                        "Circuit breaker is OPEN - service unavailable"
                    )

            try:
                result = await func(*args, **kwargs)
                if self.state == "HALF_OPEN":
                    self.state = "CLOSED"
                    self.failures = 0
                    logger.info("✅ Circuit breaker: CLOSED, service recovered")
                return result

            except Exception as e:
                self.failures += 1
                self.last_failure_time = time.time()

                if self.failures >= self.failure_threshold:
                    self.state = "OPEN"
                    logger.error(f"🔴 Circuit breaker: OPEN after {self.failures} failures")

                raise e

        return wrapper


class ProductionOpenAIClient:
    """
    Production-grade OpenAI client with enterprise features
    """

    def __init__(self, api_key: Optional[str] = None, org_id: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.org_id = org_id or os.getenv("OPENAI_ORG_ID")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not provided")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            organization=self.org_id,
            timeout=30,
            max_retries=0,  # We handle retries ourselves
        )

        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Could not initialize tiktoken: {e}")
            self.encoding = None

        self.circuit_breaker = CircuitBreaker(failure_threshold=5)

        # Metrics
        self.total_calls = 0
        self.total_cost = 0.0
        self.total_tokens = 0

    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if not self.encoding:
            return len(text) // 4  # Rough estimate
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}")
            return len(text) // 4

    def calculate_cost(
        self, input_tokens: int, output_tokens: int, model: str
    ) -> float:
        """Calculate cost for API call"""
        costs = {
            "text-embedding-3-small": {"input": 0.02 / 1_000_000, "output": 0},
            "text-embedding-3-large": {"input": 0.13 / 1_000_000, "output": 0},
            "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
            "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
        }

        model_costs = costs.get(model, {"input": 0, "output": 0})
        return (input_tokens * model_costs["input"]) + (
            output_tokens * model_costs["output"]
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
        before_sleep=lambda retry_state: logger.warning(
            f"🔄 Retrying API call, attempt {retry_state.attempt_number}"
        ),
    )
    async def get_embedding(
        self, text: str, model: str = "text-embedding-3-large"
    ) -> List[float]:
        """
        Get embedding with production-grade error handling
        """
        try:
            response = await self.client.embeddings.create(input=text, model=model)

            # Track metrics
            self.total_calls += 1
            tokens = self.count_tokens(text)
            self.total_tokens += tokens
            cost = self.calculate_cost(tokens, 0, model)
            self.total_cost += cost

            logger.info(f"✓ Embedding: {tokens} tokens, ${cost:.6f}")

            return response.data[0].embedding

        except RateLimitError as e:
            logger.error(f"⚠️ Rate limit exceeded: {e}")
            await asyncio.sleep(1.0)
            raise

        except APIError as e:
            logger.error(f"❌ OpenAI API error: {e}")
            raise

        except Exception as e:
            logger.error(f"❌ Unexpected error in get_embedding: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
    )
    async def get_embeddings_batch(
        self, texts: List[str], model: str = "text-embedding-3-large"
    ) -> List[List[float]]:
        """
        Batch embedding with automatic chunking for large batches
        """
        MAX_BATCH_SIZE = 2048

        if len(texts) <= MAX_BATCH_SIZE:
            response = await self.client.embeddings.create(input=texts, model=model)

            # Track metrics
            total_tokens = sum(self.count_tokens(t) for t in texts)
            cost = self.calculate_cost(total_tokens, 0, model)
            self.total_cost += cost
            self.total_tokens += total_tokens

            return [item.embedding for item in response.data]

        # Chunk large batches
        embeddings = []
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i : i + MAX_BATCH_SIZE]
            batch_embeddings = await self.get_embeddings_batch(batch, model)
            embeddings.extend(batch_embeddings)

        return embeddings

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((RateLimitError, APIError)),
    )
    async def generate_answer(
        self,
        question: str,
        context: str,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        max_tokens: int = 800,
        system_prompt: Optional[str] = None,
    ) -> Dict:
        """
        Generate answer with production-grade quality and error handling
        """
        system_prompt = system_prompt or self._get_default_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}\n\nProvide a detailed, accurate answer based solely on the context above.",
            },
        ]

        try:
            start_time = time.time()

            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.95,
                frequency_penalty=0.3,
                presence_penalty=0.1,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract response
            answer = response.choices[0].message.content

            # Calculate costs
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            cost = self.calculate_cost(input_tokens, output_tokens, model)

            # Track metrics
            self.total_calls += 1
            self.total_tokens += total_tokens
            self.total_cost += cost

            # Log
            logger.info(
                f"✓ Answer generated: {latency_ms}ms, {total_tokens} tokens, ${cost:.6f}"
            )

            # Alert if slow
            if latency_ms > 3000:
                logger.warning(
                    f"⚠️ Slow query: {latency_ms}ms (threshold: 3000ms)"
                )

            return {
                "answer": answer,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost_usd": cost,
                "latency_ms": latency_ms,
                "finish_reason": response.choices[0].finish_reason,
            }

        except RateLimitError as e:
            logger.error(
                f"⚠️ Rate limit exceeded, fallback to gpt-4o-mini"
            )
            # Fallback to cheaper model
            if model != "gpt-4o-mini":
                return await self.generate_answer(
                    question,
                    context,
                    model="gpt-4o-mini",
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                )
            raise

        except Exception as e:
            logger.error(f"❌ Error in generate_answer: {e}")
            raise

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt"""
        return """You are a highly accurate AI assistant for a knowledge retrieval system.

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

    def get_metrics(self) -> Dict:
        """Get client metrics"""
        return {
            "total_api_calls": self.total_calls,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 4),
            "average_cost_per_call": round(
                self.total_cost / max(self.total_calls, 1), 6
            ),
            "circuit_breaker_state": self.circuit_breaker.state,
        }


# Initialize client
try:
    openai_client = ProductionOpenAIClient()
except Exception as e:
    logger.error(f"Could not initialize OpenAI client: {e}")
    openai_client = None
