/**
 * K6 Load Testing Script
 * 
 * Run with: k6 run load-tests/load-test.js
 * 
 * Prerequisites:
 * 1. Install K6: https://k6.io/docs/getting-started/installation/
 * 2. Start the backend services
 * 3. Run this script against your API
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const searchLatency = new Trend('search_latency');
const uploadLatency = new Trend('upload_latency');
const authLatency = new Trend('auth_latency');
const successfulRequests = new Counter('successful_requests');
const failedRequests = new Counter('failed_requests');

// Test configuration
export const options = {
  // Test scenarios
  scenarios: {
    // Smoke test - verify system works under minimal load
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '30s',
      startTime: '0s',
      tags: { test_type: 'smoke' },
    },
    
    // Load test - normal expected traffic
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },   // Ramp up
        { duration: '5m', target: 50 },   // Stay at 50 users
        { duration: '2m', target: 0 },    // Ramp down
      ],
      startTime: '30s',
      tags: { test_type: 'load' },
    },
    
    // Stress test - find breaking point
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 100 },  // Ramp up
        { duration: '5m', target: 100 },  // Stay at 100 users
        { duration: '2m', target: 200 },  // Push to 200
        { duration: '5m', target: 200 },  // Stay at 200
        { duration: '2m', target: 0 },    // Ramp down
      ],
      startTime: '10m',
      tags: { test_type: 'stress' },
    },
    
    // Spike test - sudden traffic spike
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 10 },   // Normal load
        { duration: '10s', target: 500 },  // Spike!
        { duration: '1m', target: 500 },   // Stay at spike
        { duration: '10s', target: 10 },   // Back to normal
        { duration: '1m', target: 10 },    // Stay at normal
        { duration: '10s', target: 0 },    // Ramp down
      ],
      startTime: '25m',
      tags: { test_type: 'spike' },
    },
  },
  
  // Thresholds - test fails if these are not met
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests under 2s
    http_req_failed: ['rate<0.05'],    // Less than 5% errors
    errors: ['rate<0.1'],              // Less than 10% error rate
    search_latency: ['p(95)<3000'],    // Search under 3s
    upload_latency: ['p(95)<10000'],   // Upload under 10s
  },
};

// Configuration
const BASE_URL = __ENV.API_BASE_URL || 'http://localhost:8000';
const TEST_USER_EMAIL = __ENV.TEST_USER_EMAIL || 'test@example.com';
const TEST_USER_PASSWORD = __ENV.TEST_USER_PASSWORD || 'password123';

// Sample queries for search testing
const sampleQueries = [
  'What is the vacation policy?',
  'How do I submit an expense report?',
  'What are the security guidelines?',
  'Employee onboarding process',
  'Remote work policy',
  'Performance review process',
  'Health insurance benefits',
  'Parental leave policy',
  'Code of conduct',
  'IT support procedures',
];

// Helper function to get random query
function getRandomQuery() {
  return sampleQueries[Math.floor(Math.random() * sampleQueries.length)];
}

// Helper function to handle responses
function handleResponse(res, operation) {
  const success = res.status >= 200 && res.status < 300;
  
  if (success) {
    successfulRequests.add(1);
  } else {
    failedRequests.add(1);
    errorRate.add(1);
    console.log(`${operation} failed: ${res.status} - ${res.body}`);
  }
  
  return success;
}

// Main test function
export default function () {
  let authToken = null;
  
  // Authentication
  group('Authentication', () => {
    const loginStart = Date.now();
    
    const loginRes = http.post(`${BASE_URL}/auth/login`, JSON.stringify({
      email: TEST_USER_EMAIL,
      password: TEST_USER_PASSWORD,
    }), {
      headers: { 'Content-Type': 'application/json' },
    });
    
    authLatency.add(Date.now() - loginStart);
    
    const loginSuccess = check(loginRes, {
      'login status is 200': (r) => r.status === 200,
      'login has token': (r) => {
        try {
          const body = JSON.parse(r.body);
          authToken = body.token;
          return !!body.token;
        } catch {
          return false;
        }
      },
    });
    
    handleResponse(loginRes, 'login');
    
    sleep(1);
  });
  
  // Get auth headers
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': authToken ? `Bearer ${authToken}` : '',
  };
  
  // Search queries
  group('Search', () => {
    const query = getRandomQuery();
    const searchStart = Date.now();
    
    const searchRes = http.post(`${BASE_URL}/api/query`, JSON.stringify({
      query: query,
      limit: 5,
    }), { headers });
    
    searchLatency.add(Date.now() - searchStart);
    
    check(searchRes, {
      'search status is 200': (r) => r.status === 200,
      'search has results': (r) => {
        try {
          const body = JSON.parse(r.body);
          return Array.isArray(body.results);
        } catch {
          return false;
        }
      },
    });
    
    handleResponse(searchRes, 'search');
    
    sleep(2);
  });
  
  // Get documents
  group('Documents', () => {
    const docsRes = http.get(`${BASE_URL}/api/documents`, { headers });
    
    check(docsRes, {
      'documents status is 200': (r) => r.status === 200,
      'documents is array': (r) => {
        try {
          const body = JSON.parse(r.body);
          return Array.isArray(body.documents);
        } catch {
          return false;
        }
      },
    });
    
    handleResponse(docsRes, 'documents');
    
    sleep(1);
  });
  
  // Submit feedback
  group('Feedback', () => {
    const feedbackRes = http.post(`${BASE_URL}/api/feedback`, JSON.stringify({
      resultId: 'result-' + Math.floor(Math.random() * 1000),
      rating: Math.floor(Math.random() * 5) + 1,
      comment: 'Load test feedback',
    }), { headers });
    
    check(feedbackRes, {
      'feedback status is 201': (r) => r.status === 201,
    });
    
    handleResponse(feedbackRes, 'feedback');
    
    sleep(1);
  });
  
  // Health check
  group('Health', () => {
    const healthRes = http.get(`${BASE_URL}/health`);
    
    check(healthRes, {
      'health status is 200': (r) => r.status === 200,
      'health is healthy': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.status === 'healthy';
        } catch {
          return false;
        }
      },
    });
    
    handleResponse(healthRes, 'health');
  });
  
  // Logout
  if (authToken) {
    group('Logout', () => {
      const logoutRes = http.post(`${BASE_URL}/auth/logout`, null, { headers });
      
      check(logoutRes, {
        'logout status is 200': (r) => r.status === 200,
      });
      
      handleResponse(logoutRes, 'logout');
    });
  }
  
  // Random sleep between iterations
  sleep(Math.random() * 3 + 1);
}

// Setup function - runs once before the test
export function setup() {
  console.log(`Starting load test against ${BASE_URL}`);
  
  // Verify the service is available
  const healthRes = http.get(`${BASE_URL}/health`);
  
  if (healthRes.status !== 200) {
    console.error('Service is not healthy, aborting test');
    return { abort: true };
  }
  
  console.log('Service is healthy, starting test...');
  return { startTime: Date.now() };
}

// Teardown function - runs once after the test
export function teardown(data) {
  if (data && data.startTime) {
    const duration = (Date.now() - data.startTime) / 1000;
    console.log(`Test completed in ${duration} seconds`);
  }
}

// Handle summary results
export function handleSummary(data) {
  return {
    'load-test-results.json': JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

// Text summary helper
function textSummary(data, options) {
  const metrics = data.metrics;
  const lines = [];
  
  lines.push('\n========== LOAD TEST SUMMARY ==========\n');
  
  if (metrics.http_req_duration) {
    lines.push(`HTTP Request Duration:`);
    lines.push(`  - avg: ${metrics.http_req_duration.values.avg.toFixed(2)}ms`);
    lines.push(`  - p95: ${metrics.http_req_duration.values['p(95)'].toFixed(2)}ms`);
    lines.push(`  - p99: ${metrics.http_req_duration.values['p(99)'].toFixed(2)}ms`);
  }
  
  if (metrics.http_reqs) {
    lines.push(`\nTotal Requests: ${metrics.http_reqs.values.count}`);
    lines.push(`Requests/sec: ${metrics.http_reqs.values.rate.toFixed(2)}`);
  }
  
  if (metrics.errors) {
    lines.push(`\nError Rate: ${(metrics.errors.values.rate * 100).toFixed(2)}%`);
  }
  
  if (metrics.search_latency) {
    lines.push(`\nSearch Latency (p95): ${metrics.search_latency.values['p(95)'].toFixed(2)}ms`);
  }
  
  lines.push('\n========================================\n');
  
  return lines.join('\n');
}
