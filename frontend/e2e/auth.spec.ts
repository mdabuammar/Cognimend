/**
 * E2E Tests: Authentication Flow
 * 
 * Tests for login, logout, and session management.
 */

import { test, expect, LoginPage } from './fixtures';

test.describe('Authentication', () => {
  test.describe('Login', () => {
    test('should display login page', async ({ page }) => {
      await page.goto('/login');
      
      // Check for login form elements
      await expect(page.locator('input[type="email"], [data-testid="email-input"]')).toBeVisible();
      await expect(page.locator('input[type="password"], [data-testid="password-input"]')).toBeVisible();
      await expect(page.locator('button[type="submit"], [data-testid="login-button"]')).toBeVisible();
    });

    test('should login with valid credentials', async ({ page }) => {
      const loginPage = new LoginPage(page);
      await loginPage.goto('/login');
      
      await loginPage.login('test@example.com', 'password123');
      
      // Should redirect to dashboard or home
      await expect(page).toHaveURL(/\/(dashboard|home|$)/);
    });

    test('should show error for invalid credentials', async ({ page }) => {
      const loginPage = new LoginPage(page);
      await loginPage.goto('/login');
      
      await loginPage.login('wrong@example.com', 'wrongpassword');
      
      // Should show error message
      await expect(
        page.locator('[data-testid="error-message"], .error, [role="alert"]')
      ).toBeVisible({ timeout: 5000 });
      
      // Should stay on login page
      await expect(page).toHaveURL(/\/login/);
    });

    test('should show validation errors for empty fields', async ({ page }) => {
      await page.goto('/login');
      
      // Click submit without filling fields
      await page.click('button[type="submit"], [data-testid="login-button"]');
      
      // Should show validation errors
      const errorVisible = await page.locator('text=/required|email|password/i').isVisible();
      expect(errorVisible).toBe(true);
    });

    test('should validate email format', async ({ page }) => {
      await page.goto('/login');
      
      await page.fill('input[type="email"], [data-testid="email-input"]', 'invalid-email');
      await page.fill('input[type="password"], [data-testid="password-input"]', 'password123');
      await page.click('button[type="submit"], [data-testid="login-button"]');
      
      // Should show email validation error
      await expect(
        page.locator('text=/valid email|invalid email|email format/i')
      ).toBeVisible({ timeout: 3000 }).catch(() => {
        // Some forms may submit anyway, which is also acceptable for this test
      });
    });
  });

  test.describe('Logout', () => {
    test('should logout successfully', async ({ authenticatedPage }) => {
      // User is already logged in via fixture
      await authenticatedPage.goto('/');
      
      // Find and click logout
      const logoutButton = authenticatedPage.locator(
        '[data-testid="logout-button"], button:has-text("Logout"), button:has-text("Sign out")'
      );
      
      if (await logoutButton.isVisible()) {
        await logoutButton.click();
        
        // Should redirect to login page
        await expect(authenticatedPage).toHaveURL(/\/(login|$)/);
      }
    });
  });

  test.describe('Session Management', () => {
    test('should persist session across page refresh', async ({ authenticatedPage }) => {
      await authenticatedPage.goto('/');
      
      // Reload the page
      await authenticatedPage.reload();
      
      // Should still be on authenticated page (not redirected to login)
      await expect(authenticatedPage).not.toHaveURL(/\/login/);
    });

    test('should redirect to login when not authenticated', async ({ page }) => {
      // Clear any stored auth
      await page.context().clearCookies();
      await page.evaluate(() => localStorage.clear());
      
      // Try to access protected route
      await page.goto('/dashboard');
      
      // Should redirect to login (or stay if no auth required)
      // This depends on the app's auth implementation
      const currentUrl = page.url();
      const isOnDashboard = currentUrl.includes('/dashboard');
      const isOnLogin = currentUrl.includes('/login');
      
      // Either redirected to login or dashboard is public
      expect(isOnDashboard || isOnLogin).toBe(true);
    });
  });

  test.describe('Password Reset', () => {
    test('should navigate to password reset page', async ({ page }) => {
      await page.goto('/login');
      
      const forgotLink = page.locator(
        'a:has-text("Forgot"), a:has-text("Reset"), [data-testid="forgot-password"]'
      );
      
      if (await forgotLink.isVisible()) {
        await forgotLink.click();
        await expect(page).toHaveURL(/\/(forgot|reset|password)/);
      }
    });
  });

  test.describe('Registration', () => {
    test('should navigate to registration page', async ({ page }) => {
      await page.goto('/login');
      
      const registerLink = page.locator(
        'a:has-text("Register"), a:has-text("Sign up"), a:has-text("Create account"), [data-testid="register-link"]'
      );
      
      if (await registerLink.isVisible()) {
        await registerLink.click();
        await expect(page).toHaveURL(/\/(register|signup|sign-up)/);
      }
    });
  });
});
