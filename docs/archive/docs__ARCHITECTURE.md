# 🏗️ Cognimend Architecture Documentation

> Deep dive into the system design, patterns, and technical decisions

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Service Architecture](#service-architecture)
3. [Data Architecture](#data-architecture)
4. [Autonomous Operations](#autonomous-operations)
5. [RAG Pipeline](#rag-pipeline)
6. [Scalability Design](#scalability-design)
7. [Security Architecture](#security-architecture)
8. [Observability](#observability)
9. [Deployment Architecture](#deployment-architecture)
10. [Technology Decisions](#technology-decisions)

---

## System Overview

### High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web App<br/>React + TypeScript]
        API_CLIENT[API Clients<br/>cURL/SDK]
    end

    subgraph "Edge Layer"
        INGRESS[NGINX Ingress<br/>TLS/Rate Limiting]
    end

    subgraph "Application Layer"
        UPLOAD[Upload Service<br/>:8001]
        QUERY[Query Service<br/>:8002]
        TELEMETRY[Telemetry Service<br/>:8003]
        DRIFT[Drift Detector<br/>:8004]
        CONTROLLER[Controller<br/>:8005]
        EVAL[Evaluation<br/>:8006]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL<br/>Metadata)]
        QDRANT[(Qdrant<br/>Vectors)]
        REDIS[(Redis<br/>Cache)]
        RABBIT[RabbitMQ<br/>Events]
    end

    subgraph "External Services"
        OPENROUTER[OpenRouter<br/>LLM Gateway]
    end

    subgraph "Observability"
        PROM[Prometheus]
        GRAFANA[Grafana]
        JAEGER[Jaeger]
    end

    WEB --> INGRESS
    API_CLIENT --> INGRESS
    INGRESS --> UPLOAD
    INGRESS --> QUERY
    INGRESS --> TELEMETRY

    UPLOAD --> PG
    UPLOAD --> QDRANT
    UPLOAD --> REDIS
    UPLOAD --> RABBIT
    UPLOAD --> OPENROUTER

    QUERY --> PG
    QUERY --> QDRANT
    QUERY --> REDIS
    QUERY --> OPENROUTER

    TELEMETRY --> PG
    TELEMETRY --> REDIS

    DRIFT --> PG
    DRIFT --> QDRANT
    DRIFT --> RABBIT

    CONTROLLER --> PG
    CONTROLLER --> RABBIT
    CONTROLLER --> OPENROUTER

    EVAL --> PG
    EVAL --> QUERY

    DRIFT -.->|Events| CONTROLLER
    CONTROLLER -.->|Actions| UPLOAD
    CONTROLLER -.->|Actions| QUERY

    UPLOAD --> PROM
    QUERY --> PROM
    PROM --> GRAFANA
    UPLOAD --> JAEGER
    QUERY --> JAEGER
```

### Component Interactions

```mermaid
sequenceDiagram
    participant User
    participant Upload
    participant Query
    participant Qdrant
    participant OpenRouter
    participant Telemetry
    participant Drift
    participant Controller

    Note over User,Controller: Document Upload Flow
    User->>Upload: POST /upload (file)
    Upload->>Upload: Parse & Chunk
    Upload->>OpenRouter: Generate Embeddings
    Upload->>Qdrant: Store Vectors
    Upload->>Telemetry: Log Upload Event
    Upload-->>User: document_id

    Note over User,Controller: Query Flow
    User->>Query: POST /query
    Query->>OpenRouter: Generate Query Embedding
    Query->>Qdrant: Similarity Search
    Query->>OpenRouter: Generate Answer (RAG)
    Query->>Telemetry: Log Query + Confidence
    Query-->>User: Answer + Sources

    Note over User,Controller: Autonomous Operations
    Drift->>Drift: Analyze Metrics (cron)
    Drift->>Controller: Drift Detected Event
    Controller->>Controller: Determine Action
    Controller->>Upload: Trigger Reindex
    Controller->>Telemetry: Log Action
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW OVERVIEW                              │
└─────────────────────────────────────────────────────────────────────────────┘

1. DOCUMENT INGESTION
   ┌──────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐
   │  Upload  │───►│   Parse   │───►│  Chunk    │───►│ Embed     │
   │  (PDF)   │    │ (PyPDF2)  │    │ (tiktoken)│    │(OpenRouter)│
   └──────────┘    └───────────┘    └───────────┘    └─────┬─────┘
                                                           │
   ┌──────────────────────────────────────────────────────┘
   │
   ▼
   ┌───────────┐    ┌───────────┐
   │  Qdrant   │    │PostgreSQL │
   │ (vectors) │    │(metadata) │
   └───────────┘    └───────────┘

2. QUERY PROCESSING
   ┌──────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐
   │  Query   │───►│   Embed   │───►│  Search   │───►│  Generate │
   │  (text)  │    │(OpenRouter)│   │ (Qdrant)  │    │  (LLM)    │
   └──────────┘    └───────────┘    └───────────┘    └─────┬─────┘
                                                           │
   ┌──────────────────────────────────────────────────────┘
   │
   ▼
   ┌───────────┐    ┌───────────┐    ┌───────────┐
   │  Answer   │───►│ Telemetry │───►│   Cache   │
   │ +Sources  │    │  Logging  │    │  (Redis)  │
   └───────────┘    └───────────┘    └───────────┘

3. AUTONOMOUS MONITORING
   ┌──────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐
   │Telemetry │───►│   Drift   │───►│Controller │───►│  Action   │
   │  Data    │    │ Detection │    │  Decide   │    │  Execute  │
   └──────────┘    └───────────┘    └───────────┘    └───────────┘
```

---

## Service Architecture

### Microservices Overview

| Service | Port | Responsibility | Dependencies |
|---------|------|----------------|--------------|
| **Upload** | 8001 | Document ingestion, parsing, chunking, embedding | PostgreSQL, Qdrant, Redis, OpenRouter |
| **Query** | 8002 | RAG queries, answer generation, caching | PostgreSQL, Qdrant, Redis, OpenRouter |
| **Telemetry** | 8003 | Metrics aggregation, dashboard data | PostgreSQL, Redis |
| **Drift Detector** | 8004 | Statistical drift analysis | PostgreSQL, Qdrant |
| **Controller** | 8005 | Configuration management, auto-healing | PostgreSQL, All Services |
| **Evaluation** | 8006 | Benchmarking, quality testing | PostgreSQL, Query Service |

### Service Details

#### Upload Service (8001)

```mermaid
graph LR
    subgraph "Upload Service"
        A[API Endpoint] --> B[File Validator]
        B --> C[Document Parser]
        C --> D[Text Chunker]
        D --> E[Batch Embedder]
        E --> F[Vector Storage]
        F --> G[Metadata Storage]
    end
    
    B -->|Reject| X[Error Response]
    C -->|PDF| C1[PyPDF2]
    C -->|DOCX| C2[python-docx]
    C -->|TXT| C3[Direct Read]
    
    E -->|OpenRouter| OR[Embedding API]
    F -->|Qdrant| QD[(Vectors)]
    G -->|PostgreSQL| PG[(Metadata)]
```

**Key Features:**
- Idempotency via file hashing (SHA-256)
- Batch embedding for efficiency (batch size: 100)
- Automatic retry with exponential backoff
- Circuit breaker for external services

#### Query Service (8002)

```mermaid
graph LR
    subgraph "Query Service"
        A[Query API] --> B[Cache Check]
        B -->|Hit| Z[Return Cached]
        B -->|Miss| C[Query Embedder]
        C --> D[Vector Search]
        D --> E[Context Builder]
        E --> F[LLM Generator]
        F --> G[Citation Extractor]
        G --> H[Cache Store]
        H --> I[Response]
    end
    
    C -->|OpenRouter| OR1[Embedding]
    D -->|Qdrant| QD[Top-K Search]
    F -->|OpenRouter| OR2[Chat Completion]
```

**Key Features:**
- Redis caching with 1-hour TTL
- Streaming responses via SSE
- Confidence scoring
- Source citation with page numbers

#### Drift Detector (8004)

```mermaid
graph TB
    subgraph "Drift Detection"
        A[Scheduler] --> B[Data Collector]
        B --> C{Drift Type}
        
        C -->|Data| D[KS-Test<br/>Embedding Distribution]
        C -->|Retrieval| E[Similarity<br/>Score Analysis]
        C -->|Performance| F[Confidence<br/>& Latency Trends]
        
        D --> G[Drift Score]
        E --> G
        F --> G
        
        G --> H{Score > Threshold?}
        H -->|Yes| I[Publish Event]
        H -->|No| J[Log OK]
    end
    
    I --> K[RabbitMQ]
    K --> L[Controller]
```

**Drift Types:**

| Type | Method | Threshold | Metric |
|------|--------|-----------|--------|
| Data Drift | Kolmogorov-Smirnov Test | 0.15 | Embedding distribution shift |
| Retrieval Drift | Mean Comparison | 0.10 | Similarity score degradation |
| Performance Drift | Trend Analysis | 0.05 | Confidence/latency change |

### Communication Patterns

```mermaid
graph LR
    subgraph "Synchronous (HTTP)"
        Q[Query] -->|REST| U[Upload]
        E[Eval] -->|REST| Q
    end
    
    subgraph "Asynchronous (RabbitMQ)"
        D[Drift] -->|Event| R[RabbitMQ]
        R -->|Subscribe| C[Controller]
        C -->|Command| R
        R -->|Execute| U
    end
```

### API Contracts

All services follow OpenAPI 3.0 specification with:
- Consistent error response format
- Request/response validation via Pydantic
- Versioned endpoints (`/v1/`, `/v2/`)

---

## Data Architecture

### Database Schema (PostgreSQL)

```mermaid
erDiagram
    DOCUMENTS {
        uuid id PK
        string filename
        string file_hash UK
        int version
        string status
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }
    
    CHUNKS {
        uuid id PK
        uuid document_id FK
        int chunk_index
        text content
        int token_count
        timestamp created_at
    }
    
    QUERY_LOGS {
        uuid id PK
        text query
        text answer
        float confidence
        int response_time_ms
        boolean cached
        jsonb sources
        timestamp created_at
    }
    
    DRIFT_EVENTS {
        uuid id PK
        string drift_type
        float score
        float p_value
        string status
        timestamp detected_at
        uuid remediation_id FK
    }
    
    REMEDIATIONS {
        uuid id PK
        string action_type
        string trigger
        string status
        jsonb parameters
        jsonb result
        timestamp started_at
        timestamp completed_at
    }
    
    CONFIG_VERSIONS {
        int version PK
        jsonb config
        string changed_by
        timestamp created_at
    }
    
    EVALUATIONS {
        uuid id PK
        int total_questions
        int passed
        float avg_confidence
        float avg_latency_ms
        jsonb details
        timestamp created_at
    }
    
    DOCUMENTS ||--o{ CHUNKS : contains
    DRIFT_EVENTS ||--o| REMEDIATIONS : triggers
```

### Vector Storage (Qdrant)

**Collection: `documents`**

```json
{
  "collection_name": "documents",
  "vectors_config": {
    "size": 1536,
    "distance": "Cosine"
  },
  "optimizers_config": {
    "default_segment_number": 4,
    "indexing_threshold": 20000
  },
  "replication_factor": 1,
  "write_consistency_factor": 1
}
```

**Point Structure:**
```json
{
  "id": "chunk_uuid",
  "vector": [0.123, -0.456, ...],
  "payload": {
    "document_id": "doc_uuid",
    "document_name": "handbook.pdf",
    "chunk_index": 5,
    "content": "Text content...",
    "page": 12,
    "version": 2,
    "created_at": "2024-01-31T12:00:00Z"
  }
}
```

### Cache Strategy (Redis)

```
┌─────────────────────────────────────────────────────────────────┐
│                        REDIS CACHE LAYERS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: Query Results (TTL: 1 hour)                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Key: query:{hash}                                        │    │
│  │ Value: {answer, sources, confidence, metadata}           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Layer 2: Embeddings (TTL: 24 hours)                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Key: embed:{text_hash}                                   │    │
│  │ Value: [0.123, -0.456, ...]                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Layer 3: Dashboard Stats (TTL: 5 minutes)                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Key: stats:dashboard                                     │    │
│  │ Value: {queries, documents, confidence, ...}            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Layer 4: Rate Limiting (TTL: 1 minute)                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Key: ratelimit:{api_key}:{minute}                       │    │
│  │ Value: request_count                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Consistency Model

| Operation | Consistency | Rationale |
|-----------|-------------|-----------|
| Document Upload | Strong | Critical for search accuracy |
| Query Response | Eventual | Caching acceptable |
| Telemetry Logs | Eventual | Non-critical, high volume |
| Config Updates | Strong | Requires immediate effect |
| Drift Events | At-least-once | RabbitMQ acknowledgment |

---

## Autonomous Operations

### Drift Detection Algorithms

```mermaid
graph TB
    subgraph "Data Drift Detection"
        A1[Collect Recent Embeddings] --> A2[Compute Distribution]
        A3[Load Baseline Distribution] --> A4[KS-Test]
        A2 --> A4
        A4 --> A5{p-value < 0.05?}
        A5 -->|Yes| A6[Drift Detected]
        A5 -->|No| A7[No Drift]
    end
```

**Kolmogorov-Smirnov Test Implementation:**

```python
from scipy import stats
import numpy as np

def detect_data_drift(recent_embeddings, baseline_embeddings):
    """
    Detect drift using KS-test on embedding distributions.
    
    Returns: (is_drift, ks_statistic, p_value)
    """
    # Reduce dimensionality for comparison
    recent_norms = np.linalg.norm(recent_embeddings, axis=1)
    baseline_norms = np.linalg.norm(baseline_embeddings, axis=1)
    
    # Perform KS-test
    ks_stat, p_value = stats.ks_2samp(recent_norms, baseline_norms)
    
    is_drift = ks_stat > 0.15 and p_value < 0.05
    return is_drift, ks_stat, p_value
```

### Auto-Healing Workflows

```mermaid
stateDiagram-v2
    [*] --> Monitoring
    Monitoring --> DriftDetected: Score > Threshold
    DriftDetected --> AnalyzeCause
    AnalyzeCause --> SelectAction
    
    SelectAction --> Reindex: Data Drift
    SelectAction --> ClearCache: Performance Drift
    SelectAction --> AdjustConfig: Retrieval Drift
    
    Reindex --> Verify
    ClearCache --> Verify
    AdjustConfig --> Verify
    
    Verify --> Success: Drift Resolved
    Verify --> Escalate: Drift Persists
    
    Success --> Monitoring
    Escalate --> AlertHuman
    AlertHuman --> [*]
```

**Auto-Healing Actions:**

| Trigger | Action | Parameters |
|---------|--------|------------|
| Data Drift | Reindex Documents | `affected_doc_ids`, `batch_size` |
| Retrieval Drift | Clear Cache + Reindex | `ttl_override` |
| Performance Drift | Adjust Config | `cache_ttl`, `top_k` |
| Repeated Failures | Escalate to Human | `alert_channel` |

### Telemetry Collection

```mermaid
graph LR
    subgraph "Metrics Sources"
        Q[Query Service] -->|Prometheus| M[Metrics]
        U[Upload Service] -->|Prometheus| M
        D[Drift Detector] -->|Events| E[Events]
    end
    
    subgraph "Aggregation"
        M --> T[Telemetry Service]
        E --> T
        T --> DB[(PostgreSQL)]
        T --> C[(Redis Cache)]
    end
    
    subgraph "Consumers"
        DB --> DASH[Dashboard API]
        DB --> DRIFT[Drift Detector]
        C --> DASH
    end
```

### Evaluation Framework

```mermaid
graph TB
    subgraph "Evaluation Run"
        A[Load Test Questions] --> B[Execute Queries]
        B --> C[Measure Results]
        C --> D[Compare to Baseline]
        D --> E{Pass Rate > 80%?}
        E -->|Yes| F[Report Success]
        E -->|No| G[Trigger Investigation]
    end
    
    subgraph "Test Question Format"
        Q[Question] --> Q1[Expected Keywords]
        Q --> Q2[Min Confidence]
        Q --> Q3[Max Latency]
    end
```

---

## RAG Pipeline

### Document Processing Flow

```mermaid
graph LR
    subgraph "1. Ingestion"
        A[File Upload] --> B{File Type}
        B -->|PDF| C1[PyPDF2]
        B -->|DOCX| C2[python-docx]
        B -->|TXT| C3[UTF-8 Read]
    end
    
    subgraph "2. Chunking"
        C1 --> D[Text Extraction]
        C2 --> D
        C3 --> D
        D --> E[Token Counter<br/>tiktoken]
        E --> F[Overlap Chunker]
    end
    
    subgraph "3. Embedding"
        F --> G[Batch Embedder]
        G --> H[OpenRouter API]
        H --> I[1536-dim Vectors]
    end
    
    subgraph "4. Storage"
        I --> J[Qdrant Upsert]
        D --> K[PostgreSQL Metadata]
    end
```

### Chunking Strategy

```python
class ChunkingConfig:
    CHUNK_SIZE = 512       # tokens
    CHUNK_OVERLAP = 50     # tokens
    MIN_CHUNK_SIZE = 100   # tokens
    SEPARATOR = "\n\n"     # paragraph boundary
```

**Algorithm:**
1. Split text on paragraph boundaries
2. Merge small paragraphs until `CHUNK_SIZE` reached
3. Add `CHUNK_OVERLAP` tokens from previous chunk
4. Discard chunks smaller than `MIN_CHUNK_SIZE`

### Embedding Generation

```mermaid
sequenceDiagram
    participant Service
    participant Batch as Batch Queue
    participant OpenRouter
    participant Qdrant
    
    Service->>Batch: Add chunks
    Batch->>Batch: Wait for batch (100 or 5s)
    Batch->>OpenRouter: POST /embeddings
    OpenRouter-->>Batch: vectors[]
    Batch->>Qdrant: Upsert points
    Qdrant-->>Service: Confirmation
```

**Embedding Model:** `text-embedding-3-small` (1536 dimensions)

### Vector Search

```python
def search_similar(query_embedding: List[float], top_k: int = 5):
    """
    Search for similar documents using cosine similarity.
    """
    return qdrant_client.search(
        collection_name="documents",
        query_vector=query_embedding,
        limit=top_k,
        score_threshold=0.5,  # Minimum similarity
        with_payload=True
    )
```

### Answer Generation

```mermaid
graph TB
    subgraph "RAG Prompt Construction"
        A[User Query] --> B[System Prompt]
        C[Retrieved Chunks] --> D[Context Section]
        B --> E[Final Prompt]
        D --> E
        A --> E
    end
    
    subgraph "LLM Generation"
        E --> F[OpenRouter API]
        F --> G[Raw Response]
        G --> H[Citation Extraction]
        H --> I[Confidence Scoring]
    end
```

**Prompt Template:**
```
You are a helpful assistant that answers questions based on the provided context.

CONTEXT:
{chunks with source attribution}

RULES:
1. Only use information from the context
2. Cite sources using [Source: document_name, page X]
3. If unsure, say "I cannot find this information"
4. Be concise but complete

QUESTION: {user_query}

ANSWER:
```

### Citation Extraction

```python
def extract_citations(answer: str, sources: List[dict]) -> List[Citation]:
    """
    Extract and validate citations from LLM response.
    """
    citation_pattern = r'\[Source: ([^,]+), page (\d+)\]'
    matches = re.findall(citation_pattern, answer)
    
    citations = []
    for doc_name, page in matches:
        source = find_source(sources, doc_name, int(page))
        if source:
            citations.append(Citation(
                document_id=source['document_id'],
                document_name=doc_name,
                page=int(page),
                snippet=source['content'][:200],
                similarity=source['score']
            ))
    return citations
```

---

## Scalability Design

### Horizontal Scaling Strategy

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[NGINX Ingress]
    end
    
    subgraph "Stateless Services (Scale Out)"
        LB --> Q1[Query-1]
        LB --> Q2[Query-2]
        LB --> Q3[Query-3]
        LB --> U1[Upload-1]
        LB --> U2[Upload-2]
    end
    
    subgraph "Stateful Services (Scale Up)"
        Q1 --> PG[(PostgreSQL<br/>Primary)]
        Q2 --> PG
        Q3 --> PG
        PG -.->|Replication| PGR[(PostgreSQL<br/>Replica)]
    end
```

### Auto-Scaling Configuration

```yaml
# Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: query-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: query-service
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### Caching Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                     CACHING ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  L1: Application Cache (in-memory)                              │
│  ├── Query embeddings (LRU, 1000 items)                        │
│  └── Config cache (5 min TTL)                                   │
│                                                                  │
│  L2: Redis Cache (distributed)                                  │
│  ├── Query results (1 hour TTL)                                 │
│  ├── Embeddings (24 hour TTL)                                   │
│  └── Dashboard stats (5 min TTL)                                │
│                                                                  │
│  L3: Database Query Cache (PostgreSQL)                          │
│  └── Prepared statements                                        │
│                                                                  │
│  L4: Vector Index Cache (Qdrant)                                │
│  └── HNSW index in memory                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Rate Limiting

```python
class RateLimiter:
    """Token bucket rate limiter using Redis."""
    
    def __init__(self, redis_client, key_prefix="ratelimit"):
        self.redis = redis_client
        self.prefix = key_prefix
    
    async def check_rate_limit(
        self, 
        api_key: str, 
        limit: int = 60, 
        window: int = 60
    ) -> tuple[bool, int]:
        """
        Check if request is within rate limit.
        Returns: (allowed, remaining)
        """
        key = f"{self.prefix}:{api_key}:{int(time.time()) // window}"
        
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, window)
        
        allowed = current <= limit
        remaining = max(0, limit - current)
        
        return allowed, remaining
```

---

## Security Architecture

### Authentication & Authorization

```mermaid
graph LR
    subgraph "Authentication Flow"
        A[Request] --> B{Has API Key?}
        B -->|No| C[401 Unauthorized]
        B -->|Yes| D[Validate Key]
        D --> E{Valid?}
        E -->|No| C
        E -->|Yes| F[Check Permissions]
        F --> G{Authorized?}
        G -->|No| H[403 Forbidden]
        G -->|Yes| I[Process Request]
    end
```

### API Key Management

```python
class APIKeyManager:
    """Secure API key validation and management."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.key_prefix = "apikey"
    
    def hash_key(self, api_key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    async def validate_key(self, api_key: str) -> Optional[APIKeyInfo]:
        """Validate API key and return permissions."""
        key_hash = self.hash_key(api_key)
        data = await self.redis.hgetall(f"{self.key_prefix}:{key_hash}")
        
        if not data:
            return None
        
        return APIKeyInfo(
            key_id=data['id'],
            permissions=json.loads(data['permissions']),
            rate_limit=int(data['rate_limit']),
            expires_at=datetime.fromisoformat(data['expires_at'])
        )
```

### Network Policies

```yaml
# Zero-trust network policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: query-service-policy
spec:
  podSelector:
    matchLabels:
      app: query-service
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: ingress-nginx
      ports:
        - port: 8002
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - port: 5432
    - to:
        - podSelector:
            matchLabels:
              app: qdrant
      ports:
        - port: 6333
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - port: 6379
```

### Data Encryption

| Layer | Encryption | Method |
|-------|------------|--------|
| Transit | TLS 1.3 | Ingress termination |
| At Rest (PostgreSQL) | AES-256 | Transparent Data Encryption |
| At Rest (Qdrant) | AES-256 | Volume encryption |
| Secrets | Base64 + K8s | Kubernetes Secrets |

### Secrets Management

```mermaid
graph LR
    subgraph "Development"
        A[.env file] --> B[Docker Compose]
    end
    
    subgraph "Production"
        C[AWS Secrets Manager] --> D[External Secrets Operator]
        D --> E[Kubernetes Secret]
        E --> F[Pod Volume Mount]
    end
```

---

## Observability

### Metrics Collection

```mermaid
graph LR
    subgraph "Application Metrics"
        A[FastAPI] --> B[prometheus-client]
        B --> C[/metrics endpoint]
    end
    
    subgraph "Collection"
        C --> D[Prometheus]
        D --> E[AlertManager]
        D --> F[Grafana]
    end
    
    subgraph "Custom Metrics"
        G[query_latency_seconds]
        H[cache_hit_rate]
        I[confidence_score]
        J[drift_score]
    end
```

**Key Metrics:**

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | method, path, status | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | method, path | Request latency |
| `rag_query_confidence` | Gauge | - | Last query confidence |
| `rag_cache_hits_total` | Counter | - | Cache hit count |
| `rag_drift_score` | Gauge | type | Drift detection score |
| `rag_documents_total` | Gauge | status | Document count |

### Logging Strategy

```python
# Structured logging with correlation
import logging
import json
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar('request_id', default='')

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id.get(),
            "service": "query-service"
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)
```

**Log Levels:**

| Level | Use Case | Example |
|-------|----------|---------|
| ERROR | Failures requiring attention | Database connection failed |
| WARNING | Degraded performance | Cache miss, retry |
| INFO | Normal operations | Query completed |
| DEBUG | Development details | Embedding vector size |

### Distributed Tracing

```mermaid
sequenceDiagram
    participant Client
    participant Query as Query Service
    participant OpenRouter
    participant Qdrant
    
    Note over Client,Qdrant: Trace ID: abc-123
    
    Client->>Query: POST /query (trace: abc-123)
    
    Query->>Query: Span: validate_request
    Query->>OpenRouter: Span: generate_embedding
    OpenRouter-->>Query: embedding
    Query->>Qdrant: Span: vector_search
    Qdrant-->>Query: results
    Query->>OpenRouter: Span: generate_answer
    OpenRouter-->>Query: answer
    Query-->>Client: response
```

**OpenTelemetry Integration:**

```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

# Initialize tracing
def init_tracing(service_name: str):
    tracer_provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: service_name})
    )
    tracer_provider.add_span_processor(
        BatchSpanProcessor(JaegerExporter(
            agent_host_name=os.getenv("JAEGER_HOST", "localhost"),
            agent_port=6831
        ))
    )
    trace.set_tracer_provider(tracer_provider)
    
    # Auto-instrument FastAPI
    FastAPIInstrumentor.instrument()
```

### Alerting System

```yaml
# PrometheusRule
groups:
  - name: cognimend-critical
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) 
          / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"
```

---

## Deployment Architecture

### Kubernetes Resources

```mermaid
graph TB
    subgraph "Namespace: cognimend"
        subgraph "Workloads"
            D1[Deployment: upload]
            D2[Deployment: query]
            D3[Deployment: telemetry]
            D4[Deployment: drift-detector]
            D5[Deployment: controller]
            D6[Deployment: evaluation]
            SS1[StatefulSet: postgres]
            SS2[StatefulSet: qdrant]
            SS3[StatefulSet: redis]
        end
        
        subgraph "Networking"
            S1[Service: upload-service]
            S2[Service: query-service]
            I[Ingress: cognimend-ingress]
            NP[NetworkPolicies]
        end
        
        subgraph "Config"
            CM[ConfigMap: cognimend-config]
            SEC[Secret: cognimend-secrets]
        end
        
        subgraph "Storage"
            PV1[PV: postgres-data]
            PV2[PV: qdrant-data]
            PVC1[PVC: postgres-pvc]
            PVC2[PVC: qdrant-pvc]
        end
        
        subgraph "Scaling"
            HPA1[HPA: query-hpa]
            HPA2[HPA: upload-hpa]
            PDB1[PDB: query-pdb]
        end
    end
```

### Rolling Updates

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # Create 1 new pod before killing old
      maxUnavailable: 0  # Never have less than desired replicas
```

### Canary Deployments

```mermaid
graph LR
    subgraph "Traffic Split"
        I[Ingress] --> |90%| S1[Stable v1.0]
        I --> |10%| S2[Canary v1.1]
    end
    
    subgraph "Promotion"
        M[Monitor Metrics] --> D{Success?}
        D -->|Yes| P[Promote Canary]
        D -->|No| R[Rollback]
    end
```

---

## Technology Decisions

### Why FastAPI?

| Criteria | FastAPI | Flask | Django |
|----------|---------|-------|--------|
| Async Support | ✅ Native | ❌ Requires ASGI | ❌ Limited |
| Performance | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Type Safety | ✅ Pydantic | ❌ Manual | ❌ Manual |
| Auto Docs | ✅ OpenAPI | ❌ Manual | ❌ Manual |
| Learning Curve | Easy | Easy | Medium |

**Decision:** FastAPI provides the best combination of performance, developer experience, and production-readiness for microservices.

### Why Qdrant vs Other Vector DBs?

| Feature | Qdrant | Pinecone | Milvus | Weaviate |
|---------|--------|----------|--------|----------|
| Self-hosted | ✅ | ❌ | ✅ | ✅ |
| Cloud Option | ✅ | ✅ | ✅ | ✅ |
| Filtering | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Performance | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Rust Backend | ✅ | ❌ | ❌ | ❌ |
| Memory Efficiency | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

**Decision:** Qdrant offers excellent performance, rich filtering, and self-hosting capability with a small memory footprint.

### Why OpenRouter?

| Benefit | Description |
|---------|-------------|
| Multi-model Access | Access GPT-4, Claude, Llama, Mixtral through one API |
| Cost Optimization | Switch models based on cost/performance needs |
| Fallback Support | Automatic failover between providers |
| Single Integration | One SDK instead of multiple |

**Trade-offs:**
- Additional latency (~50ms)
- Dependency on third-party service
- Limited to supported models

### Trade-offs Made

| Decision | Trade-off | Rationale |
|----------|-----------|-----------|
| Microservices | Complexity vs Flexibility | Enables independent scaling and deployment |
| Redis Cache | Memory cost vs Latency | 80%+ cache hit rate justifies cost |
| Statistical Drift | Computation vs Accuracy | KS-test provides good balance |
| Async Everything | Complexity vs Throughput | Necessary for 250+ req/s target |
| Event-driven Healing | Eventual consistency | Autonomous operation more important than immediate |

---

## Appendix

### Glossary

| Term | Definition |
|------|------------|
| RAG | Retrieval Augmented Generation |
| KS-Test | Kolmogorov-Smirnov statistical test |
| HNSW | Hierarchical Navigable Small World (vector index) |
| HPA | Horizontal Pod Autoscaler |
| PDB | Pod Disruption Budget |

### References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [OpenRouter API](https://openrouter.ai/docs)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/cluster-administration/)
- [OpenTelemetry](https://opentelemetry.io/docs/)

---

**Last Updated:** January 2024  
**Version:** 2.0.0
