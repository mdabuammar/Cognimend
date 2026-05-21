/**
 * MSW Browser Setup
 * 
 * This file sets up the MSW service worker for browser environments.
 * Used in development and Playwright E2E tests.
 */

import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

// Create the MSW worker with default handlers
export const worker = setupWorker(...handlers);

// Export for use in development
export { handlers };
