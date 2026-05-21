/**
 * Playwright Test Fixtures
 * 
 * Extend Playwright's test with custom fixtures for Doczly.
 */

import { test as base, expect, Page } from '@playwright/test';

// Custom fixture types
interface TestFixtures {
  authenticatedPage: Page;
  mockAPI: void;
}

// Extend base test with custom fixtures
export const test = base.extend<TestFixtures>({
  // Authenticated page fixture - logs in before each test
  authenticatedPage: async ({ page }, runFixture) => {
    // Navigate to login
    await page.goto('/login');
    
    // Fill login form
    await page.fill('[data-testid="email-input"], input[type="email"]', 'test@example.com');
    await page.fill('[data-testid="password-input"], input[type="password"]', 'password123');
    
    // Submit login
    await page.click('[data-testid="login-button"], button[type="submit"]');
    
    // Wait for navigation to complete
    await page.waitForURL(/\/(dashboard|home|\/)/, { timeout: 10000 });
    
    // Use the authenticated page
    await runFixture(page);
    
    // Cleanup: logout after test
    try {
      await page.click('[data-testid="logout-button"]');
    } catch {
      // Ignore if logout button not found
    }
  },

  // Mock API fixture - sets up API mocking
  mockAPI: async ({ page }, runFixture) => {
    // Intercept and mock API calls
    await page.route('**/api/**', async (route) => {
      const url = route.request().url();
      
      // Mock specific endpoints
      if (url.includes('/api/documents')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            documents: [
              { id: '1', filename: 'test.pdf', status: 'processed' },
            ],
            total: 1,
          }),
        });
      } else if (url.includes('/api/query')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            results: [
              { id: '1', content: 'Mock result', score: 0.95 },
            ],
            total: 1,
          }),
        });
      } else {
        await route.continue();
      }
    });
    
    await runFixture();
  },
});

// Re-export expect for convenience
export { expect };

// Page Object Model base class
export class BasePage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async goto(path: string) {
    await this.page.goto(path);
  }

  async waitForLoad() {
    await this.page.waitForLoadState('networkidle');
  }

  async getToastMessage(): Promise<string | null> {
    const toast = this.page.locator('[data-testid="toast"], [role="alert"]').first();
    if (await toast.isVisible({ timeout: 5000 })) {
      return toast.textContent();
    }
    return null;
  }
}

// Login Page Object
export class LoginPage extends BasePage {
  readonly emailInput = this.page.locator('[data-testid="email-input"], input[type="email"]');
  readonly passwordInput = this.page.locator('[data-testid="password-input"], input[type="password"]');
  readonly submitButton = this.page.locator('[data-testid="login-button"], button[type="submit"]');
  readonly errorMessage = this.page.locator('[data-testid="error-message"], .error');

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }
}

// Dashboard Page Object
export class DashboardPage extends BasePage {
  readonly documentList = this.page.locator('[data-testid="document-list"]');
  readonly uploadButton = this.page.locator('[data-testid="upload-button"]');
  readonly searchInput = this.page.locator('[data-testid="search-input"], input[type="search"]');

  async getDocumentCount(): Promise<number> {
    return this.page.locator('[data-testid="document-item"]').count();
  }

  async uploadFile(filePath: string) {
    const fileInput = this.page.locator('input[type="file"]');
    await fileInput.setInputFiles(filePath);
  }
}

// Query Page Object
export class QueryPage extends BasePage {
  readonly queryInput = this.page.locator('[data-testid="query-input"], textarea, input[type="text"]');
  readonly submitButton = this.page.locator('[data-testid="submit-query"], button[type="submit"]');
  readonly resultsList = this.page.locator('[data-testid="results-list"]');
  readonly loadingSpinner = this.page.locator('[data-testid="loading"], .loading');

  async search(query: string) {
    await this.queryInput.fill(query);
    await this.submitButton.click();
  }

  async waitForResults() {
    await this.loadingSpinner.waitFor({ state: 'hidden', timeout: 30000 });
    await this.resultsList.waitFor({ state: 'visible', timeout: 5000 });
  }

  async getResultCount(): Promise<number> {
    return this.page.locator('[data-testid="result-item"]').count();
  }
}
