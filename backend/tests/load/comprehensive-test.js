/**
 * Comprehensive K6 Load Test for Cognimend RAG System
 * 
 * Test Scenarios:
 * 1. Ramp-up Test (0-20 min): Gradual load increase
 * 2. Spike Test (20-25 min): Sudden traffic spike
 * 3. Constant Load Test (30-40 min): Baseline performance
 * 
 * Usage:
 *   k6 run comprehensive-test.js
 *   k6 run --env TARGET_URL=https://api.example.com comprehensive-test.js
 *   k6 run --out json=results.json comprehensive-test.js
 */

import http from 'k6/http';
import { check, sleep, group, fail } from 'k6';
import { Counter, Rate, Trend, Gauge } from 'k6/metrics';
import { htmlReport } from "https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js";
import { textSummary } from "https://jslib.k6.io/k6-summary/0.0.1/index.js";
import { randomItem, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// =============================================================================
// Configuration
// =============================================================================

const BASE_URL = __ENV.TARGET_URL || 'http://localhost:8002';
const UPLOAD_URL = __ENV.UPLOAD_URL || 'http://localhost:8001';
const API_KEY = __ENV.API_KEY || 'test-api-key';

// =============================================================================
// Custom Metrics
// =============================================================================

// Latency metrics
const queryLatency = new Trend('query_latency', true);
const uploadLatency = new Trend('upload_latency', true);
const metricsLatency = new Trend('metrics_latency', true);

// Rate metrics
const errorRate = new Rate('error_rate');
const successRate = new Rate('success_rate');
const querySuccessRate = new Rate('query_success_rate');
const uploadSuccessRate = new Rate('upload_success_rate');

// Counter metrics
const totalQueries = new Counter('total_queries');
const totalUploads = new Counter('total_uploads');
const totalErrors = new Counter('total_errors');
const cacheHits = new Counter('cache_hits');
const cacheMisses = new Counter('cache_misses');

// Gauge metrics
const confidenceScore = new Trend('confidence_score');
const responseSize = new Trend('response_size');
const tokensUsed = new Trend('tokens_used');

// =============================================================================
// Test Options - Multi-Scenario Configuration
// =============================================================================

export const options = {
    scenarios: {
        // Scenario 1: Ramp-up Test (0-16 minutes)
        ramp_up: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '2m', target: 50 },    // Ramp to 50 VUs
                { duration: '5m', target: 100 },   // Ramp to 100 VUs
                { duration: '2m', target: 200 },   // Ramp to 200 VUs
                { duration: '5m', target: 200 },   // Sustain 200 VUs
                { duration: '2m', target: 0 },     // Ramp down
            ],
            startTime: '0s',
            gracefulRampDown: '30s',
            tags: { scenario: 'ramp_up' },
        },

        // Scenario 2: Spike Test (starts at 20 minutes)
        spike_test: {
            executor: 'ramping-vus',
            startVUs: 100,
            stages: [
                { duration: '30s', target: 100 },  // Baseline
                { duration: '30s', target: 500 },  // Spike up
                { duration: '1m', target: 500 },   // Hold spike
                { duration: '30s', target: 100 },  // Drop back
                { duration: '2m', target: 100 },   // Recovery observation
            ],
            startTime: '20m',
            gracefulRampDown: '30s',
            tags: { scenario: 'spike' },
        },

        // Scenario 3: Constant Load (starts at 30 minutes)
        constant_load: {
            executor: 'constant-vus',
            vus: 50,
            duration: '10m',
            startTime: '30m',
            tags: { scenario: 'constant' },
        },
    },

    thresholds: {
        // HTTP metrics
        http_req_duration: [
            'p(95)<3000',   // 95% of requests under 3s
            'p(99)<5000',   // 99% of requests under 5s
        ],
        http_req_failed: ['rate<0.05'],  // Less than 5% errors

        // Custom metrics
        query_latency: [
            'p(95)<2500',   // 95% of queries under 2.5s
            'p(99)<4000',   // 99% of queries under 4s
        ],
        upload_latency: ['p(95)<10000'],  // Uploads can take longer
        error_rate: ['rate<0.02'],         // Less than 2% errors
        success_rate: ['rate>0.95'],       // More than 95% success
        confidence_score: ['avg>0.5'],     // Average confidence above 50%
    },

    // Summary settings
    summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)', 'count'],
    
    // Tags for better filtering
    tags: {
        testType: 'comprehensive',
        environment: __ENV.ENVIRONMENT || 'staging',
    },
};

// =============================================================================
// Test Data
// =============================================================================

const testQueries = [
    "What is machine learning and how does it work?",
    "Explain the concept of neural networks in simple terms",
    "How does RAG (Retrieval Augmented Generation) improve LLM responses?",
    "What are transformer models and why are they important?",
    "Describe the attention mechanism in deep learning",
    "What is natural language processing and its applications?",
    "How do word embeddings capture semantic meaning?",
    "Explain the difference between supervised and unsupervised learning",
    "What are vector databases and why are they used with LLMs?",
    "How does fine-tuning work for language models?",
];

const advancedQueries = [
    "Compare the performance of BERT vs GPT models for text classification",
    "What are the best practices for chunking documents in RAG systems?",
    "How can I optimize embedding model inference latency?",
    "Explain the trade-offs between different retrieval strategies",
    "What metrics should I use to evaluate RAG system quality?",
];

const sampleDocuments = [
    {
        name: "machine_learning_basics.txt",
        content: `
Machine Learning Fundamentals

Machine learning is a subset of artificial intelligence (AI) that enables systems 
to learn and improve from experience without being explicitly programmed. It focuses 
on developing algorithms that can access data, learn from it, and make predictions 
or decisions based on that learning.

Key Concepts:
1. Supervised Learning: Training models with labeled data
2. Unsupervised Learning: Finding patterns in unlabeled data
3. Reinforcement Learning: Learning through trial and error with rewards
4. Deep Learning: Neural networks with multiple layers

Applications include image recognition, natural language processing, recommendation 
systems, and autonomous vehicles.
        `.trim(),
    },
    {
        name: "neural_networks.txt",
        content: `
Neural Networks Explained

A neural network is a computational model inspired by the structure and function 
of the human brain. It consists of interconnected nodes (neurons) organized in layers.

Architecture:
- Input Layer: Receives raw data
- Hidden Layers: Process and transform data
- Output Layer: Produces final predictions

Types of Neural Networks:
1. Feedforward Networks (FNN)
2. Convolutional Neural Networks (CNN)
3. Recurrent Neural Networks (RNN)
4. Transformer Networks

Training involves adjusting weights through backpropagation to minimize error.
        `.trim(),
    },
    {
        name: "rag_systems.txt",
        content: `
Retrieval Augmented Generation (RAG)

RAG combines retrieval-based and generation-based approaches for improved 
language model performance. It retrieves relevant context from a knowledge 
base and uses it to generate more accurate, grounded responses.

Components:
1. Document Store: Vector database for embeddings
2. Retriever: Finds relevant documents based on query
3. Generator: LLM that produces responses using context

Benefits:
- Reduced hallucination
- Up-to-date information
- Domain-specific knowledge
- Traceable sources
        `.trim(),
    },
    {
        name: "transformers.txt",
        content: `
Transformer Architecture

Transformers revolutionized NLP with their attention mechanism, enabling 
parallel processing and capturing long-range dependencies in text.

Key Components:
1. Self-Attention: Weighs importance of different input positions
2. Multi-Head Attention: Multiple attention layers in parallel
3. Positional Encoding: Maintains sequence order information
4. Feed-Forward Networks: Process attention outputs

Popular Models:
- BERT: Bidirectional encoding for understanding
- GPT: Autoregressive generation
- T5: Text-to-text framework
- LLaMA: Open-source efficient models
        `.trim(),
    },
    {
        name: "embeddings.txt",
        content: `
Word and Sentence Embeddings

Embeddings are dense vector representations of text that capture semantic meaning.
Similar texts have similar embedding vectors, enabling semantic search.

Embedding Types:
1. Word Embeddings: Word2Vec, GloVe, FastText
2. Sentence Embeddings: BERT, Sentence-BERT
3. Document Embeddings: Doc2Vec, paragraph vectors

Applications:
- Semantic search
- Document similarity
- Clustering and classification
- Recommendation systems

Popular embedding models: OpenAI Ada, Cohere Embed, all-MiniLM-L6-v2
        `.trim(),
    },
];

// =============================================================================
// Helper Functions
// =============================================================================

function getHeaders() {
    return {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
        'X-Request-ID': `k6-${__VU}-${__ITER}-${Date.now()}`,
    };
}

function getFormHeaders() {
    return {
        'X-API-Key': API_KEY,
        'X-Request-ID': `k6-${__VU}-${__ITER}-${Date.now()}`,
    };
}

function parseConfidence(response) {
    try {
        const body = JSON.parse(response.body);
        return body.confidence || body.score || 0;
    } catch (e) {
        return 0;
    }
}

function parseCacheInfo(response) {
    try {
        const body = JSON.parse(response.body);
        return body.cached || body.cache_hit || false;
    } catch (e) {
        return false;
    }
}

function parseTokens(response) {
    try {
        const body = JSON.parse(response.body);
        return body.tokens_used || body.usage?.total_tokens || 0;
    } catch (e) {
        return 0;
    }
}

// =============================================================================
// Test Functions
// =============================================================================

function performQuery() {
    const query = randomItem([...testQueries, ...advancedQueries]);
    const topK = randomIntBetween(3, 10);

    const payload = JSON.stringify({
        query: query,
        top_k: topK,
        include_sources: true,
    });

    const startTime = Date.now();
    const response = http.post(`${BASE_URL}/query`, payload, {
        headers: getHeaders(),
        timeout: '30s',
        tags: { name: 'query' },
    });
    const duration = Date.now() - startTime;

    // Record metrics
    queryLatency.add(duration);
    totalQueries.add(1);
    responseSize.add(response.body ? response.body.length : 0);

    // Parse response data
    const confidence = parseConfidence(response);
    if (confidence > 0) {
        confidenceScore.add(confidence);
    }

    const tokens = parseTokens(response);
    if (tokens > 0) {
        tokensUsed.add(tokens);
    }

    // Track cache hits
    if (parseCacheInfo(response)) {
        cacheHits.add(1);
    } else {
        cacheMisses.add(1);
    }

    // Checks
    const checkResult = check(response, {
        'query: status is 200': (r) => r.status === 200,
        'query: has answer field': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.answer !== undefined;
            } catch (e) {
                return false;
            }
        },
        'query: latency < 3000ms': (r) => r.timings.duration < 3000,
        'query: confidence > 0': (r) => parseConfidence(r) > 0,
        'query: no error message': (r) => {
            try {
                const body = JSON.parse(r.body);
                return !body.error && !body.detail;
            } catch (e) {
                return true;
            }
        },
    });

    // Record success/error rates
    const success = response.status === 200;
    successRate.add(success);
    querySuccessRate.add(success);
    errorRate.add(!success);

    if (!success) {
        totalErrors.add(1);
        console.log(`Query failed: ${response.status} - ${response.body}`);
    }

    return response;
}

function performUpload() {
    const doc = randomItem(sampleDocuments);
    const uniqueContent = `${doc.content}\n\nGenerated at: ${new Date().toISOString()}\nVU: ${__VU}, Iter: ${__ITER}`;

    const formData = {
        file: http.file(uniqueContent, doc.name, 'text/plain'),
    };

    const startTime = Date.now();
    const response = http.post(`${UPLOAD_URL}/upload`, formData, {
        headers: getFormHeaders(),
        timeout: '60s',
        tags: { name: 'upload' },
    });
    const duration = Date.now() - startTime;

    // Record metrics
    uploadLatency.add(duration);
    totalUploads.add(1);

    // Checks
    const checkResult = check(response, {
        'upload: status is 200 or 201': (r) => r.status === 200 || r.status === 201,
        'upload: has document_id or status': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.document_id || body.status || body.id;
            } catch (e) {
                return false;
            }
        },
        'upload: latency < 10000ms': (r) => r.timings.duration < 10000,
    });

    // Record success/error rates
    const success = response.status === 200 || response.status === 201;
    successRate.add(success);
    uploadSuccessRate.add(success);
    errorRate.add(!success);

    if (!success) {
        totalErrors.add(1);
        console.log(`Upload failed: ${response.status} - ${response.body}`);
    }

    return response;
}

function checkMetrics() {
    const startTime = Date.now();
    const response = http.get(`${BASE_URL}/metrics/prometheus`, {
        headers: getHeaders(),
        timeout: '10s',
        tags: { name: 'metrics' },
    });
    const duration = Date.now() - startTime;

    metricsLatency.add(duration);

    check(response, {
        'metrics: status is 200 or 404': (r) => r.status === 200 || r.status === 404,
        'metrics: latency < 1000ms': (r) => r.timings.duration < 1000,
    });

    return response;
}

function checkHealth() {
    const response = http.get(`${BASE_URL}/health`, {
        timeout: '5s',
        tags: { name: 'health' },
    });

    check(response, {
        'health: status is 200': (r) => r.status === 200,
        'health: response is healthy': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.status === 'healthy' || body.status === 'ok';
            } catch (e) {
                return r.status === 200;
            }
        },
    });

    return response;
}

// =============================================================================
// Main Test Function
// =============================================================================

export default function () {
    // Determine action based on weighted probability
    const action = Math.random() * 100;

    if (action < 80) {
        // 80% - Query operations
        group('Query RAG System', () => {
            performQuery();
        });
    } else if (action < 90) {
        // 10% - Upload operations
        group('Upload Document', () => {
            performUpload();
        });
    } else {
        // 10% - Metrics check
        group('Check Metrics', () => {
            checkMetrics();
        });
    }

    // Random sleep between requests (1-3 seconds)
    sleep(randomIntBetween(1, 3));
}

// =============================================================================
// Setup & Teardown
// =============================================================================

export function setup() {
    console.log('='.repeat(60));
    console.log('Starting Comprehensive Load Test');
    console.log('='.repeat(60));
    console.log(`Target URL: ${BASE_URL}`);
    console.log(`Upload URL: ${UPLOAD_URL}`);
    console.log(`Environment: ${__ENV.ENVIRONMENT || 'staging'}`);
    console.log('='.repeat(60));

    // Verify services are healthy before starting
    const healthResponse = checkHealth();
    if (healthResponse.status !== 200) {
        console.error('Health check failed! Services may not be ready.');
    }

    return {
        startTime: Date.now(),
        baseUrl: BASE_URL,
    };
}

export function teardown(data) {
    const duration = (Date.now() - data.startTime) / 1000;
    
    console.log('='.repeat(60));
    console.log('Load Test Complete');
    console.log('='.repeat(60));
    console.log(`Total Duration: ${duration.toFixed(2)} seconds`);
    console.log('='.repeat(60));
}

// =============================================================================
// Summary Handler - Generates Reports
// =============================================================================

export function handleSummary(data) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    
    return {
        // Console output
        stdout: textSummary(data, { indent: ' ', enableColors: true }),
        
        // HTML report
        [`results/load-test-report-${timestamp}.html`]: htmlReport(data, {
            title: 'Cognimend RAG System - Load Test Report',
        }),
        
        // JSON summary for programmatic analysis
        [`results/load-test-summary-${timestamp}.json`]: JSON.stringify(data, null, 2),
        
        // Simplified metrics for CI/CD
        'results/metrics.json': JSON.stringify({
            timestamp: timestamp,
            thresholds: {
                passed: Object.values(data.metrics).every(m => !m.thresholds || 
                    Object.values(m.thresholds).every(t => t.ok)),
            },
            metrics: {
                http_req_duration_p95: data.metrics.http_req_duration?.values?.['p(95)'] || 0,
                http_req_duration_p99: data.metrics.http_req_duration?.values?.['p(99)'] || 0,
                http_req_failed_rate: data.metrics.http_req_failed?.values?.rate || 0,
                query_latency_p95: data.metrics.query_latency?.values?.['p(95)'] || 0,
                error_rate: data.metrics.error_rate?.values?.rate || 0,
                success_rate: data.metrics.success_rate?.values?.rate || 0,
                total_requests: data.metrics.http_reqs?.values?.count || 0,
                requests_per_second: data.metrics.http_reqs?.values?.rate || 0,
                confidence_avg: data.metrics.confidence_score?.values?.avg || 0,
            },
        }, null, 2),
    };
}
