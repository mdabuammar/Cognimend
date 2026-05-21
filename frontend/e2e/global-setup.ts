/**
 * Global Setup for Playwright E2E Tests
 * 
 * Runs once before all tests to set up the test environment.
 */

import { chromium, FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('🚀 Global setup starting...');
  
  // Store base URL for tests
  const baseURL = config.projects[0].use.baseURL || 'http://localhost:5173';
  
  // Wait for the application to be ready
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    // Wait for the app to be accessible
    let retries = 30;
    while (retries > 0) {
      try {
        await page.goto(baseURL, { timeout: 5000 });
        console.log('✅ Application is ready');
        break;
      } catch {
        retries--;
        if (retries === 0) {
          throw new Error('Application failed to start');
        }
        console.log(`⏳ Waiting for application... (${retries} retries left)`);
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    }
    
    // You can perform authentication here and store state
    // For example, login and save auth state for reuse
    /*
    await page.goto(`${baseURL}/login`);
    await page.fill('[data-testid="email"]', 'test@example.com');
    await page.fill('[data-testid="password"]', 'password123');
    await page.click('[data-testid="login-button"]');
    await page.waitForURL(`${baseURL}/dashboard`);
    
    // Save authentication state
    await page.context().storageState({ path: './e2e/.auth/user.json' });
    */
    
  } finally {
    await browser.close();
  }
  
  console.log('✅ Global setup complete');
}

export default globalSetup;
