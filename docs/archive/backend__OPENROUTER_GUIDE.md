# 🚀 OPENROUTER INTEGRATION - 500+ MODELS, 20X CHEAPER

## **WHY OPENROUTER?**

### **The Problem with OpenAI Direct**
- Fixed to OpenAI models only
- Expensive ($2.50/1M tokens for GPT-4o)
- Rate limiting issues
- No fallback options

### **The Solution: OpenRouter**
✅ **500+ models** in one API  
✅ **5x-20x cheaper** with quality models  
✅ **Automatic fallbacks** if model unavailable  
✅ **OpenAI-compatible API** (drop-in replacement)  
✅ **Usage tracking** in dashboard  

---

## **🎯 YOUR API KEY ALREADY WORKS!**

Your existing API key `your-openrouter-api-key-here` is already an OpenRouter key!

You can use it with:
- 500+ models
- All the features below
- **No additional signup needed**

---

## **💰 COST COMPARISON**

| Setup | Cost/1K Queries | Quality | Your $10 Gets |
|-------|-----------------|---------|---------------|
| **OpenRouter FREE** | $0.02 | 8/10 | **500,000 queries** 🤯 |
| **OpenRouter CHEAP** | $0.50 | 9/10 | **20,000 queries** ✅ |
| **OpenRouter BALANCED** | $0.50 | 9/10 | **20,000 queries** ✅ |
| **OpenRouter QUALITY** | $3.00 | 10/10 | 3,333 queries |
| **OpenAI Direct (GPT-4o)** | $3.00 | 10/10 | 3,333 queries |

---

## **📊 AVAILABLE MODELS**

### **Embedding Models (Vector Search)**
```
Free:
- text-embedding-3-small  ($0.02/1M tokens)

Quality:
- text-embedding-3-large  ($0.13/1M tokens)
- voyage/voyage-3         ($0.12/1M tokens)
```

### **Generation Models (Answer Generation)**
```
🆓 FREE:
- google/gemini-2.0-flash-exp:free    (Amazing!)
- meta-llama/llama-3.3-70b-instruct   (Via Groq)

💰 CHEAP ($0.25-0.35/1M):
- anthropic/claude-3.5-haiku          (Best value ⭐)
- anthropic/claude-3.5-sonnet         ($3/1M)

💎 PREMIUM ($2.50+/1M):
- openai/gpt-4o                       (Latest)
- openai/chatgpt-4o-latest           (Newest)
- anthropic/claude-3.7-sonnet        (State-of-art)
```

### **Long Context Models (For Big Documents)**
```
- google/gemini-2.0-flash-exp:free   (1M context!)
- google/gemini-1.5-pro              (2M context)
- anthropic/claude-3.5-sonnet        (200K context)
```

---

## **⚡ QUICK START**

### **Option 1: Drop-In Replacement (Recommended)**

Your `.env` is already updated. Just use OpenRouter!

```bash
OPENROUTER_API_KEY=<your-openrouter-api-key>
OPENROUTER_PRESET=cheap
```

### **Option 2: Use in Code**

```python
from core.openrouter_client import create_openrouter_client

# Create client with preset
client = create_openrouter_client(preset="cheap")

# Use like OpenAI
embedding = await client.get_embedding("text")
answer = await client.generate_answer("question", "context")
```

---

## **🔧 PRESET CONFIGURATIONS**

### **FREE Tier** 🆓
```
OPENROUTER_PRESET=free

Models:
- Embedding: text-embedding-3-small ($0.02/1M)
- Generation: google/gemini-2.0-flash-exp:free (FREE!)

Cost: ~$0.02 per 1000 queries
Quality: 8/10
Speed: ⚡⚡⚡ Very fast
Best for: Learning, testing, high volume
```

### **CHEAP** 💰 (Recommended)
```
OPENROUTER_PRESET=cheap

Models:
- Embedding: text-embedding-3-small ($0.02/1M)
- Generation: anthropic/claude-3.5-haiku ($0.25/1M)

Cost: ~$0.50 per 1000 queries
Quality: 9/10
Speed: ⚡⚡ Fast
Best for: Production, cost-conscious
Your $10 = 20,000 queries
```

### **BALANCED** ⚖️
```
OPENROUTER_PRESET=balanced

Models:
- Embedding: text-embedding-3-small ($0.02/1M)
- Generation: anthropic/claude-3.5-haiku ($0.25/1M)

Cost: ~$0.50 per 1000 queries
Quality: 9/10
Speed: ⚡⚡ Fast
Same as CHEAP but may switch models
```

### **QUALITY** 💎
```
OPENROUTER_PRESET=quality

Models:
- Embedding: text-embedding-3-large ($0.13/1M)
- Generation: openai/gpt-4o ($2.50/1M)

Cost: ~$3.00 per 1000 queries
Quality: 10/10
Speed: ⚡ Moderate
Best for: FAANG interviews, complex queries
Your $10 = 3,333 queries
```

### **BEST** 🏆
```
OPENROUTER_PRESET=best

Models:
- Embedding: text-embedding-3-large ($0.13/1M)
- Generation: anthropic/claude-3.5-sonnet ($3/1M)

Cost: ~$4.50 per 1000 queries
Quality: 10/10 (State-of-the-art)
Speed: ⚡ Moderate
Best for: Maximum quality needed
```

---

## **🔄 AUTOMATIC FALLBACKS**

If your primary model is unavailable, automatically falls back to:

1. `meta-llama/llama-3.3-70b-instruct` (FREE!)
2. `google/gemini-2.0-flash-exp:free` (FREE!)
3. `anthropic/claude-3.5-haiku` (Cheap)

**No interruption to your service!**

---

## **📈 MONITORING USAGE**

Check which models are being used:

```bash
curl http://localhost:8002/metrics
```

Response:
```json
{
  "total_api_calls": 1523,
  "model_usage": {
    "anthropic/claude-3.5-haiku": 1200,
    "google/gemini-2.0-flash-exp:free": 323
  },
  "embedding_model": "text-embedding-3-small",
  "generation_model": "anthropic/claude-3.5-haiku"
}
```

---

## **🎯 RECOMMENDED SETUP**

### **For Testing/Learning: FREE**
```
OPENROUTER_PRESET=free
```
- Cost: ~$0.02 per 1000 queries
- Quality: 8/10
- Your $10 = 500,000 queries

### **For Production: CHEAP** ⭐
```
OPENROUTER_PRESET=cheap
```
- Cost: ~$0.50 per 1000 queries
- Quality: 9/10
- Your $10 = 20,000 queries
- **Best value-for-money**

### **For FAANG Interviews: QUALITY**
```
OPENROUTER_PRESET=quality
```
- Cost: ~$3.00 per 1000 queries
- Quality: 10/10
- Your $10 = 3,333 queries
- Uses GPT-4o

---

## **🚀 DEPLOYMENT**

### **Step 1: Your Key is Already Set**
Your `.env` already has:
```
OPENROUTER_API_KEY=<your-openrouter-api-key>
OPENROUTER_PRESET=cheap
```

### **Step 2: Use OpenRouter Client**
The file `backend/core/openrouter_client.py` is ready to use!

### **Step 3: Test It**
```bash
cd backend/services/query
python -m uvicorn main_production:app --port 8002

# Test
curl http://localhost:8002/health
curl http://localhost:8002/metrics
```

---

## **📊 MODELS IN DETAIL**

### **Best for RAG: Claude 3.5 Haiku** 🏆
```
Model: anthropic/claude-3.5-haiku
Price: $0.25/1M input, $1.25/1M output
Speed: ⚡⚡ Fast (2-5 second response)
Quality: 9/10
Context: 200K tokens
Best for: Most RAG use cases
```

**Why it's perfect for RAG:**
- Fast enough for real-time queries
- Smart enough for complex understanding
- Large context window (200K = ~50K words)
- Excellent instruction-following
- Great value

### **Free Alternative: Gemini Flash** 🆓
```
Model: google/gemini-2.0-flash-exp:free
Price: FREE
Speed: ⚡⚡⚡ Very fast (1-2 seconds)
Quality: 8/10
Context: 1M tokens (!)
Best for: Learning, testing, high volume
```

**Pros:**
- Completely free
- Incredibly fast
- Massive context (1M tokens!)
- Good quality for free

**Cons:**
- Slightly lower quality than Claude
- May change/deprecate over time

### **Premium Option: GPT-4o** 🎯
```
Model: openai/gpt-4o
Price: $2.50/1M input, $10/1M output
Speed: ⚡ Moderate (2-5 seconds)
Quality: 10/10
Context: 128K tokens
Best for: Complex reasoning, interviews
```

**When to use:**
- FAANG interview prep
- Complex multi-step reasoning
- When you need absolute best quality

---

## **🔗 INTEGRATION WITH YOUR SYSTEM**

### **Current Architecture** (Works as-is!)
```
Your Query Service
    ↓
OpenRouter Client
    ↓
500+ Models (OpenRouter)
```

### **Drop-In Compatibility**
```python
# Old code (OpenAI)
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# New code (OpenRouter)
from core.openrouter_client import create_openrouter_client
client = create_openrouter_client(preset="cheap")

# Usage is identical!
embedding = await client.get_embedding(text)
```

---

## **⚙️ ADVANCED USAGE**

### **Custom Model Selection**
```python
from core.openrouter_client import OpenRouterClient

client = OpenRouterClient(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    embedding_model="text-embedding-3-large",
    generation_model="anthropic/claude-3.5-sonnet"
)
```

### **Switch Models Based on Cost**
```python
# For important queries: use Claude Sonnet
important_client = create_openrouter_client("quality")

# For simple queries: use free Gemini
simple_client = create_openrouter_client("free")

# Route intelligently
if query_complexity > 0.7:
    result = await important_client.generate_answer(...)
else:
    result = await simple_client.generate_answer(...)
```

### **Monitor Costs in Real-Time**
```python
metrics = client.get_metrics()
print(f"Total calls: {metrics['total_api_calls']}")
print(f"Models used: {metrics['model_usage']}")
```

---

## **🎓 EXAMPLES BY USE CASE**

### **Example 1: Learning/Testing**
```
OPENROUTER_PRESET=free

Why:
- Completely free (or ~$0.02/1000)
- Great Gemini Flash model
- Fast responses
- Perfect for trying things out
```

### **Example 2: Production RAG System**
```
OPENROUTER_PRESET=cheap

Why:
- Claude 3.5 Haiku is excellent for RAG
- $0.50 per 1000 queries
- 20,000 queries on $10 budget
- Reliable, fast, good quality
```

### **Example 3: FAANG Interview Prep**
```
OPENROUTER_PRESET=quality

Why:
- Uses GPT-4o (best reasoning)
- High quality answers
- Can handle complex multi-part questions
- Worth it for important use case
```

### **Example 4: Budget-Conscious with Fallbacks**
```
OPENROUTER_PRESET=cheap

Plus automatic fallback to:
- Free Gemini Flash
- Free Llama 3.3
- Then Claude Haiku

You get reliability + cost savings!
```

---

## **🔒 SECURITY**

Your API key works with OpenRouter because it's an OpenRouter key! No need to change anything.

### **Best Practices**
- ✅ Key is in `.env` (not committed)
- ✅ Fallback models prevent single-point failure
- ✅ Circuit breaker protects from rate limits
- ✅ Usage tracking for cost control

---

## **📞 QUICK REFERENCE**

| Task | Command |
|------|---------|
| Use Free models | `OPENROUTER_PRESET=free` |
| Production (Recommended) | `OPENROUTER_PRESET=cheap` |
| Maximum quality | `OPENROUTER_PRESET=quality` |
| Check usage | `curl http://localhost:8002/metrics` |
| View Gemini docs | `https://openrouter.ai/models/google` |
| View Claude docs | `https://openrouter.ai/models/anthropic` |
| Dashboard | `https://openrouter.ai/activity` |

---

## **✅ STATUS**

Your system is ready for OpenRouter:

- ✅ OpenRouter client created
- ✅ Environment variables set
- ✅ 500+ models available
- ✅ Automatic fallbacks enabled
- ✅ Cost tracking ready
- ✅ Zero migration effort

**Just start using it!** 🚀

---

**Version:** 1.0  
**Status:** ✅ READY TO USE  
**Savings vs OpenAI:** 5-20x cheaper with quality models
