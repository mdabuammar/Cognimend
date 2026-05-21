"""
Production OpenRouter Client
Access 500+ models with one API key
Fully compatible with your existing code
"""

import os
import time
from typing import List, Dict, Optional
from openai import AsyncOpenAI, OpenAI
import tiktoken
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """
    OpenRouter client with intelligent model routing
    Compatible with your existing OpenAI code
    """

    # ========== RECOMMENDED MODELS FOR RAG ==========

    # Best models by use case
    MODELS = {
        # Embeddings (cheapest to most expensive)
        "embedding": {
            "cheap": "text-embedding-3-small",  # OpenAI: $0.02/1M
            "quality": "text-embedding-3-large",  # OpenAI: $0.13/1M
            "best": "voyage/voyage-3",  # Voyage: $0.12/1M - Best for RAG
        },
        # Generation (RAG answers)
        "generation": {
            "ultra_cheap": "meta-llama/llama-3.3-70b-instruct",  # Free! (or $0.35/1M)
            "cheap": "google/gemini-2.0-flash-lite-preview-02-05:free",  # Free!
            "balanced": "anthropic/claude-3.5-haiku",  # $0.25/1M input
            "quality": "openai/gpt-4o",  # $2.50/1M input
            "best": "anthropic/claude-3.5-sonnet",  # $3/1M - Best reasoning
            "latest": "openai/chatgpt-4o-latest",  # Latest GPT-4o
        },
        # Long context (for large documents)
        "long_context": {
            "gemini_flash": "google/gemini-2.0-flash-lite-preview-02-05:free",  # 1M tokens context!
            "gemini_pro": "google/gemini-1.5-pro",  # 2M tokens context
            "claude": "anthropic/claude-3.5-sonnet",  # 200K context
        },
        # Fast inference
        "fast": {
            "deepseek": "deepseek/deepseek-r1",  # Very fast, free
            "groq_llama": "meta-llama/llama-3.3-70b-instruct",  # Groq routing = fast
            "gemini": "google/gemini-2.0-flash-lite-preview-02-05:free",  # Fast + free
        },
    }

    def __init__(
        self,
        api_key: str,
        embedding_model: str = "openai/text-embedding-3-small",
        generation_model: str = "meta-llama/llama-3.3-70b-instruct",
        enable_fallback: bool = True,
    ):
        """
        Initialize OpenRouter client

        Args:
            api_key: Your OpenRouter API key
            embedding_model: Model for embeddings
            generation_model: Model for answer generation
            enable_fallback: Enable automatic fallback to cheaper models
        """

        # OpenRouter base URL (OpenAI-compatible)
        self.base_url = "https://openrouter.ai/api/v1"

        # Initialize OpenAI-compatible client
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/yourusername/cognimend",  # Optional
                "X-Title": "Cognimend RAG System",  # Optional - shows in OpenRouter dashboard
            },
        )

        self.sync_client = OpenAI(
            base_url=self.base_url,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/yourusername/cognimend",
                "X-Title": "Cognimend RAG System",
            },
        )

        # Model configuration
        self.embedding_model = embedding_model
        self.generation_model = generation_model
        self.enable_fallback = enable_fallback

        # Fallback models (if primary fails)
        self.fallback_models = [
            "meta-llama/llama-3.3-70b-instruct",  # Free
            "google/gemma-3-4b-it:free",  # Free
        ]

        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Could not initialize tiktoken: {e}")
            self.encoding = None

        # Metrics
        self.total_calls = 0
        self.total_cost = 0.0
        self.model_usage = {}

    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if not self.encoding:
            return len(text) // 4  # Rough estimate
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}")
            return len(text) // 4

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_embedding(
        self, text: str, model: Optional[str] = None
    ) -> List[float]:
        """
        Get embedding from OpenRouter

        Compatible with OpenAI API
        """
        model = model or self.embedding_model

        try:
            response = await self.client.embeddings.create(
                input=text,
                model=model
            )

            self.total_calls += 1
            self.model_usage[model] = self.model_usage.get(model, 0) + 1

            logger.info(f"✅ Embedding generated: {model}")

            return response.data[0].embedding

        except Exception as e:
            logger.error(f"❌ Embedding error: {e}")
            raise

    async def get_embeddings_batch(
        self, texts: List[str], model: Optional[str] = None
    ) -> List[List[float]]:
        """Batch embeddings"""
        model = model or self.embedding_model

        # OpenRouter supports same batching as OpenAI
        response = await self.client.embeddings.create(
            input=texts,
            model=model
        )

        self.total_calls += 1
        self.model_usage[model] = self.model_usage.get(model, 0) + 1

        return [item.embedding for item in response.data]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
    )
    async def generate_answer(
        self,
        question: str,
        context: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 800,
        system_prompt: Optional[str] = None,
    ) -> Dict:
        """
        Generate answer with automatic fallback

        OpenRouter automatically routes to best provider
        """
        model = model or self.generation_model

        if system_prompt is None:
            system_prompt = """You are a highly accurate AI assistant. Answer ONLY using the provided context. 
If the context doesn't contain the answer, say "I don't have sufficient information."
Always cite sources. Be precise and detailed."""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:",
            },
        ]

        # Track models attempted
        models_to_try = [model]
        if self.enable_fallback:
            models_to_try.extend([m for m in self.fallback_models if m != model])

        last_error = None

        for current_model in models_to_try:
            try:
                start_time = time.time()

                response = await self.client.chat.completions.create(
                    model=current_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                latency_ms = int((time.time() - start_time) * 1000)

                answer = response.choices[0].message.content

                # Track usage
                self.total_calls += 1
                self.model_usage[current_model] = (
                    self.model_usage.get(current_model, 0) + 1
                )

                logger.info(
                    f"✅ Answer generated: {current_model} ({latency_ms}ms)"
                )

                return {
                    "answer": answer,
                    "model": current_model,
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                    "latency_ms": latency_ms,
                    "cost_usd": 0.0,  # OpenRouter provides this in response metadata
                    "finish_reason": response.choices[0].finish_reason,
                    "fallback_used": current_model != model,
                }

            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ {current_model} failed: {e}")

                if current_model != models_to_try[-1]:
                    logger.info(f"🔄 Falling back to next model...")
                    continue
                else:
                    raise last_error

        raise last_error

    def get_metrics(self) -> Dict:
        """Get client metrics"""
        return {
            "total_api_calls": self.total_calls,
            "model_usage": self.model_usage,
            "embedding_model": self.embedding_model,
            "generation_model": self.generation_model,
            "fallback_enabled": self.enable_fallback,
        }


# ========== INITIALIZE CLIENT ==========


def create_openrouter_client(
    preset: str = "balanced",
) -> OpenRouterClient:
    """
    Create OpenRouter client with preset configuration

    Presets:
    - free: Best free models (Gemini Flash, Llama 3.3)
    - cheap: Cheapest paid models (Claude Haiku, ~$0.25/1M)
    - balanced: Good quality + cost (Claude Haiku / GPT-4o-mini)
    - quality: High quality (GPT-4o, Claude 3.5 Sonnet)
    - best: Best available (Claude 3.5 Sonnet, GPT-4o)
    """

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment")

    presets = {
        "free": {
            "embedding": "openai/text-embedding-3-small",
            "generation": "meta-llama/llama-3.3-70b-instruct",
        },
        "cheap": {
            "embedding": "openai/text-embedding-3-small",
            "generation": "meta-llama/llama-3.3-70b-instruct",
        },
        "balanced": {
            "embedding": "openai/text-embedding-3-small",
            "generation": "meta-llama/llama-3.3-70b-instruct",
        },
        "quality": {
            "embedding": "openai/text-embedding-3-large",
            "generation": "openai/gpt-4o",
        },
        "best": {
            "embedding": "openai/text-embedding-3-large",
            "generation": "anthropic/claude-3-5-sonnet-20241022",
        },
    }

    config = presets.get(preset, presets["balanced"])

    return OpenRouterClient(
        api_key=api_key,
        embedding_model=config["embedding"],
        generation_model=config["generation"],
        enable_fallback=True,
    )
