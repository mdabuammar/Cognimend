/**
 * K6 Load Testing Suite for DriftGuard
 * 
 * Run with: k6 run --vus 50 --duration 5m load-test.js
 * 
 * Test Scenarios:
 * - Smoke Test: Verify basic functionality
 * - Load Test: Normal load conditions
 * - Stress Test: Beyond normal capacity
 * - Spike Test: Sudden traffic bursts
 * - Soak Test: Extended duration testing
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { randomString, randomItem } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// =============================================================================
// CUSTOM METRICS
// =============================================================================
const errorRate = new Rate('errors');
const queryLatency = new Trend('query_latency', true);
const searchLatency = new Trend('search_latency', true);
const uploadLatency = new Trend('upload_latency', true);
const queriesPerSecond = new Counter('queries_per_second');
const successfulQueries = new Counter('successful_queries');

// =============================================================================
// CONFIGURATION
// =============================================================================
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8005';
const API_KEY = __ENV.API_KEY || 'test-api-key';

const HEADERS = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY,
};

// Test data
const TEST_QUESTIONS = [
  "What is the company's vacation policy?",
  "How do I submit an expense report?",
  "What are the security guidelines?",
  "How do I request time off?",
  "What is the dress code?",
  "How do performance reviews work?",
  "What benefits are available?",
  "How do I report a bug?",
  "What is the onboarding process?",
  "How do I access the VPN?",
];

// =============================================================================
// SCENARIOS
// =============================================================================
export const options = {
  scenarios: {
    // Smoke test - minimal load to verify system works
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '1m',
      tags: { scenario: 'smoke' },
      exec: 'smokeTest',
    },
    
    // Load test - normal expected load
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },   // Ramp up
        { duration: '5m', target: 50 },   // Stay at 50
        { duration: '2m', target: 100 },  // Ramp up more
        { duration: '5m', target: 100 },  // Stay at 100
        { duration: '2m', target: 0 },    // Ramp down
      ],
      tags: { scenario: 'load' },
      exec: 'loadTest',
      startTime: '1m', // Start after smoke test
    },
    
    // Stress test - beyond normal capacity
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 100 },
        { duration: '5m', target: 200 },
        { duration: '5m', target: 300 },
        { duration: '5m', target: 400 },
        { duration: '2m', target: 0 },
      ],
      tags: { scenario: 'stress' },
      exec: 'stressTest',
      startTime: '17m', // Start after load test
    },
    
    // Spike test - sudden traffic burst
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '30s', target: 500 }, // Spike!
        { duration: '1m', target: 500 },
        { duration: '30s', target: 10 },
        { duration: '1m', target: 10 },
        { duration: '30s', target: 0 },
      ],
      tags: { scenario: 'spike' },
      exec: 'spikeTest',
      startTime: '36m',
    },
  },
  
  // Thresholds - SLO validation
  thresholds: {
    // Error rate should be less than 1%
    errors: ['rate<0.01'],
    
    // Query P95 latency should be under 500ms
    query_latency: ['p(95)<500', 'p(99)<1000'],
    
    // Search P95 latency should be under 200ms
    search_latency: ['p(95)<200', 'p(99)<500'],
    
    // Upload P95 latency should be under 5s
    upload_latency: ['p(95)<5000'],
    
    // HTTP request duration
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    
    // HTTP failures
    http_req_failed: ['rate<0.01'],
  },
};

// =============================================================================
// TEST FUNCTIONS
// =============================================================================

export function smokeTest() {
  group('Smoke Test - Health Check', () => {
    const healthRes = http.get(`${BASE_URL}/health`);
    check(healthRes, {
      'health check returns 200': (r) => r.status === 200,
      'health check returns healthy': (r) => {
        const body = JSON.parse(r.body);
        return body.status === 'healthy' || body.status === 'ok';
      },
    });
  });

  group('Smoke Test - Basic Query', () => {
    const query = randomItem(TEST_QUESTIONS);
    const payload = JSON.stringify({ question: query, top_k: 3 });
    
    const res = http.post(`${BASE_URL}/query`, payload, { headers: HEADERS });
    
    const success = check(res, {
      'query returns 200': (r) => r.status === 200,
      'query has answer': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.answer && body.answer.length > 0;
        } catch {
          return false;
        }
      },
    });
    
    errorRate.add(!success);
    queryLatency.add(res.timings.duration);
  });

  sleep(1);
}

export function loadTest() {
  group('Load Test - Mixed Operations', () => {
    // 70% queries, 20% search, 10% document listing
    const operation = Math.random();
    
    if (operation < 0.7) {
      performQuery();
    } else if (operation < 0.9) {
      performSearch();
    } else {
      listDocuments();
    }
  });

  // Random think time between 1-3 seconds
  sleep(1 + Math.random() * 2);
}

export function stressTest() {
  group('Stress Test - High Load Query', () => {
    performQuery();
  });
  
  // Minimal sleep for stress test
  sleep(0.5);
}

export function spikeTest() {
  group('Spike Test - Burst Traffic', () => {
    // Mix of all operations during spike
    const operation = Math.random();
    
    if (operation < 0.5) {
      performQuery();
    } else if (operation < 0.8) {
      performSearch();
    } else {
      performStreamingQuery();
    }
  });
  
  sleep(0.2);
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function performQuery() {
  const query = randomItem(TEST_QUESTIONS);
  const payload = JSON.stringify({
    question: query,
    top_k: 5,
    include_sources: true,
  });
  
  const startTime = Date.now();
  const res = http.post(`${BASE_URL}/query`, payload, { headers: HEADERS });
  const duration = Date.now() - startTime;
  
  const success = check(res, {
    'query status is 200': (r) => r.status === 200,
    'query has answer': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.answer !== undefined;
      } catch {
        return false;
      }
    },
    'query latency under 500ms': (r) => r.timings.duration < 500,
  });
  
  errorRate.add(!success);
  queryLatency.add(res.timings.duration);
  queriesPerSecond.add(1);
  
  if (success) {
    successfulQueries.add(1);
  }
  
  return res;
}

function performSearch() {
  const query = randomItem(TEST_QUESTIONS).split(' ').slice(0, 3).join(' ');
  const payload = JSON.stringify({
    query: query,
    top_k: 10,
  });
  
  const res = http.post(`${BASE_URL}/search`, payload, { headers: HEADERS });
  
  const success = check(res, {
    'search status is 200': (r) => r.status === 200,
    'search has results': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.results !== undefined;
      } catch {
        return false;
      }
    },
    'search latency under 200ms': (r) => r.timings.duration < 200,
  });
  
  errorRate.add(!success);
  searchLatency.add(res.timings.duration);
  
  return res;
}

function performStreamingQuery() {
  const query = randomItem(TEST_QUESTIONS);
  const payload = JSON.stringify({
    question: query,
    top_k: 3,
  });
  
  const res = http.post(`${BASE_URL}/query/stream`, payload, {
    headers: HEADERS,
    responseType: 'text',
  });
  
  const success = check(res, {
    'stream status is 200': (r) => r.status === 200,
    'stream has content': (r) => r.body && r.body.length > 0,
  });
  
  errorRate.add(!success);
  
  return res;
}

function listDocuments() {
  const res = http.get(`${BASE_URL}/documents?page=1&limit=20`, { headers: HEADERS });
  
  const success = check(res, {
    'documents list returns 200': (r) => r.status === 200,
    'documents list has data': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.documents !== undefined;
      } catch {
        return false;
      }
    },
  });
  
  errorRate.add(!success);
  
  return res;
}

// =============================================================================
// SETUP AND TEARDOWN
// =============================================================================

export function setup() {
  console.log('Starting load test against:', BASE_URL);
  
  // Verify connectivity
  const healthRes = http.get(`${BASE_URL}/health`);
  if (healthRes.status !== 200) {
    throw new Error(`Health check failed with status ${healthRes.status}`);
  }
  
  console.log('Health check passed, starting tests...');
  
  return {
    startTime: Date.now(),
  };
}

export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log(`Load test completed in ${duration}s`);
}

// =============================================================================
// DEFAULT EXPORT (for simple runs)
// =============================================================================

export default function() {
  loadTest();
}
