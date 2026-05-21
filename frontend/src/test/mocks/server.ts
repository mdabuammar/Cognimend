/**
 * MSW Server Setup for Node.js (Vitest)
 * 
 * This file sets up the MSW server for use in integration tests.
 */

import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// Create the MSW server with default handlers
export const server = setupServer(...handlers);

// Export for use in tests
export { handlers };
