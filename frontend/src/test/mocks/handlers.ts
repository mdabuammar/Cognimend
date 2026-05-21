/**
 * MSW (Mock Service Worker) Handlers
 * 
 * Define mock API responses for integration testing.
 * These handlers intercept HTTP requests and return mock responses.
 */

import { http, HttpResponse, delay } from 'msw';

// Base URL for API
const API_BASE = 'http://localhost:8000';

// Mock data
export const mockDocuments = [
  {
    id: 'doc-1',
    filename: 'company-handbook.pdf',
    title: 'Employee Handbook 2025',
    size: 2048576,
    uploadedAt: '2025-01-15T10:30:00Z',
    status: 'processed',
  },
  {
    id: 'doc-2',
    filename: 'security-policy.pdf',
    title: 'Security Policies and Procedures',
    size: 1024000,
    uploadedAt: '2025-01-14T09:15:00Z',
    status: 'processed',
  },
  {
    id: 'doc-3',
    filename: 'onboarding-guide.pdf',
    title: 'New Employee Onboarding Guide',
    size: 512000,
    uploadedAt: '2025-01-13T14:45:00Z',
    status: 'processing',
  },
];

export const mockQueryResults = [
  {
    id: 'result-1',
    documentId: 'doc-1',
    content: 'Our company offers 15 days of paid vacation per year for full-time employees.',
    score: 0.95,
    metadata: {
      filename: 'company-handbook.pdf',
      page: 12,
      section: 'Benefits',
    },
  },
  {
    id: 'result-2',
    documentId: 'doc-2',
    content: 'All employees must complete security training within 30 days of hire.',
    score: 0.87,
    metadata: {
      filename: 'security-policy.pdf',
      page: 3,
      section: 'Training Requirements',
    },
  },
];

export const mockUser = {
  id: 'user-1',
  email: 'test@example.com',
  name: 'Test User',
  role: 'user',
  createdAt: '2025-01-01T00:00:00Z',
};

// API Handlers
export const handlers = [
  // =========================================================================
  // Health Check
  // =========================================================================
  http.get(`${API_BASE}/health`, async () => {
    await delay(50);
    return HttpResponse.json({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      services: {
        database: 'connected',
        vectorStore: 'connected',
        llm: 'connected',
      },
    });
  }),

  // =========================================================================
  // Authentication
  // =========================================================================
  http.post(`${API_BASE}/auth/login`, async ({ request }) => {
    await delay(100);
    const body = await request.json() as { email: string; password: string };
    
    if (body.email === 'test@example.com' && body.password === 'password123') {
      return HttpResponse.json({
        user: mockUser,
        token: 'mock-jwt-token-12345',
        expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
      });
    }
    
    return HttpResponse.json(
      { error: 'Invalid credentials' },
      { status: 401 }
    );
  }),

  http.post(`${API_BASE}/auth/logout`, async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  http.get(`${API_BASE}/auth/me`, async ({ request }) => {
    const authHeader = request.headers.get('Authorization');
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }
    
    await delay(50);
    return HttpResponse.json({ user: mockUser });
  }),

  // =========================================================================
  // Documents / Upload
  // =========================================================================
  http.get(`${API_BASE}/api/documents`, async () => {
    await delay(100);
    return HttpResponse.json({
      documents: mockDocuments,
      total: mockDocuments.length,
    });
  }),

  http.get(`${API_BASE}/api/documents/:id`, async ({ params }) => {
    await delay(50);
    const document = mockDocuments.find(d => d.id === params.id);
    
    if (!document) {
      return HttpResponse.json(
        { error: 'Document not found' },
        { status: 404 }
      );
    }
    
    return HttpResponse.json({ document });
  }),

  http.post(`${API_BASE}/api/upload`, async ({ request }) => {
    await delay(100); // Simulate upload time
    
    // Check content-type header
    const contentType = request.headers.get('content-type') || '';
    
    // Must be multipart/form-data
    if (!contentType.includes('multipart/form-data')) {
      return HttpResponse.json(
        { error: 'No file provided' },
        { status: 400 }
      );
    }
    
    // Try to parse FormData - works in jsdom/happy-dom environments
    try {
      const formData = await request.formData();
      const file = formData.get('file');
      
      // No file provided - check if null/undefined OR if it's a string (empty FormData)
      if (!file || typeof file === 'string') {
        return HttpResponse.json(
          { error: 'No file provided' },
          { status: 400 }
        );
      }
      
      // At this point file is a Blob or File
      const fileName = 'name' in file ? (file as File).name : 'uploaded-file';
      const fileType = file.type || '';
      const fileSize = file.size || 0;
      
      // Check for invalid file types
      if (fileName.endsWith('.exe') || 
          fileType.includes('x-msdownload') ||
          fileType.includes('executable')) {
        return HttpResponse.json(
          { error: 'Invalid file type' },
          { status: 400 }
        );
      }
      
      // Valid file upload
      return HttpResponse.json({
        id: `doc-${Date.now()}`,
        filename: fileName,
        size: fileSize,
        status: 'processing',
        uploadedAt: new Date().toISOString(),
      }, { status: 201 });
    } catch {
      // Fallback: try to parse body as text and check for file content
      const bodyText = await request.clone().text().catch(() => '');
      
      // Empty body means no file - check for very short content only
      // Note: Even empty FormData has some multipart headers
      if (!bodyText || bodyText.trim() === '') {
        return HttpResponse.json(
          { error: 'No file provided' },
          { status: 400 }
        );
      }
      
      // Check for invalid file types in the raw body
      if (bodyText.includes('.exe') || bodyText.includes('x-msdownload')) {
        return HttpResponse.json(
          { error: 'Invalid file type' },
          { status: 400 }
        );
      }
      
      // Has content and not invalid - assume valid upload
      return HttpResponse.json({
        id: `doc-${Date.now()}`,
        filename: 'uploaded-file.pdf',
        size: bodyText.length,
        status: 'processing',
        uploadedAt: new Date().toISOString(),
      }, { status: 201 });
    }
  }),

  http.delete(`${API_BASE}/api/documents/:id`, async ({ params }) => {
    await delay(100);
    const documentIndex = mockDocuments.findIndex(d => d.id === params.id);
    
    if (documentIndex === -1) {
      return HttpResponse.json(
        { error: 'Document not found' },
        { status: 404 }
      );
    }
    
    return HttpResponse.json({ success: true });
  }),

  // =========================================================================
  // Query / Search
  // =========================================================================
  http.post(`${API_BASE}/api/query`, async ({ request }) => {
    await delay(200);
    const body = await request.json() as { query: string; limit?: number };
    
    if (!body.query || body.query.trim().length === 0) {
      return HttpResponse.json(
        { error: 'Query is required' },
        { status: 400 }
      );
    }

    // Simulate no results for specific query
    if (body.query.toLowerCase().includes('nonexistent')) {
      return HttpResponse.json({
        results: [],
        total: 0,
        query: body.query,
        processingTimeMs: 45,
      });
    }

    return HttpResponse.json({
      results: mockQueryResults.slice(0, body.limit || 10),
      total: mockQueryResults.length,
      query: body.query,
      processingTimeMs: 156,
    });
  }),

  // =========================================================================
  // Feedback
  // =========================================================================
  http.post(`${API_BASE}/api/feedback`, async ({ request }) => {
    await delay(100);
    const body = await request.json() as { resultId: string; rating: number; comment?: string };
    
    if (!body.resultId || typeof body.rating !== 'number') {
      return HttpResponse.json(
        { error: 'Invalid feedback data' },
        { status: 400 }
      );
    }
    
    return HttpResponse.json({
      id: `feedback-${Date.now()}`,
      resultId: body.resultId,
      rating: body.rating,
      createdAt: new Date().toISOString(),
    }, { status: 201 });
  }),

  // =========================================================================
  // Error Scenarios (for testing)
  // =========================================================================
  http.get(`${API_BASE}/api/error/500`, async () => {
    await delay(50);
    return HttpResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }),

  http.get(`${API_BASE}/api/error/429`, async () => {
    await delay(50);
    return HttpResponse.json(
      { error: 'Rate limit exceeded', retryAfter: 60 },
      { status: 429, headers: { 'Retry-After': '60' } }
    );
  }),

  http.get(`${API_BASE}/api/error/timeout`, async () => {
    // Simulate a very long delay (timeout)
    await delay(60000);
    return HttpResponse.json({ data: 'never returned' });
  }),

  http.get(`${API_BASE}/api/error/network`, async () => {
    // Return network error
    return HttpResponse.error();
  }),
];

// Additional handlers for specific test scenarios
export const errorHandlers = {
  serverError: http.get(`${API_BASE}/api/*`, () => {
    return HttpResponse.json({ error: 'Server error' }, { status: 500 });
  }),
  
  networkError: http.get(`${API_BASE}/api/*`, () => {
    return HttpResponse.error();
  }),
  
  slowResponse: http.get(`${API_BASE}/api/*`, async () => {
    await delay(5000);
    return HttpResponse.json({ data: 'slow' });
  }),
  
  rateLimited: http.all(`${API_BASE}/api/*`, () => {
    return HttpResponse.json(
      { error: 'Too many requests' },
      { status: 429, headers: { 'Retry-After': '30' } }
    );
  }),
};
