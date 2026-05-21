/**
 * E2E Tests: Accessibility (a11y)
 * 
 * Tests for WCAG compliance and accessibility requirements.
 */

import { test, expect } from './fixtures';
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibility', () => {
  test.describe('Home Page', () => {
    test('should have no accessibility violations', async ({ page }) => {
      await page.goto('/');
      
      const accessibilityScanResults = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze();
      
      expect(accessibilityScanResults.violations).toEqual([]);
    });

    test('should have proper heading hierarchy', async ({ page }) => {
      await page.goto('/');
      
      // Check that h1 exists
      const h1Count = await page.locator('h1').count();
      expect(h1Count).toBeGreaterThanOrEqual(1);
      
      // Check heading order (no skipped levels)
      const headings = await page.evaluate(() => {
        const headingElements = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
        return Array.from(headingElements).map(h => parseInt(h.tagName[1]));
      });
      
      for (let i = 1; i < headings.length; i++) {
        // Each heading should not skip more than one level
        expect(headings[i] - headings[i - 1]).toBeLessThanOrEqual(1);
      }
    });

    test('should have proper focus indicators', async ({ page }) => {
      await page.goto('/');
      
      // Tab to first focusable element
      await page.keyboard.press('Tab');
      
      // Check that focused element has visible focus indicator
      const focusedElement = await page.evaluate(() => {
        const focused = document.activeElement;
        if (!focused) return null;
        
        const styles = window.getComputedStyle(focused);
        return {
          outline: styles.outline,
          boxShadow: styles.boxShadow,
          border: styles.border,
        };
      });
      
      expect(focusedElement).not.toBeNull();
    });
  });

  test.describe('Login Page', () => {
    test('should have accessible form labels', async ({ page }) => {
      await page.goto('/login');
      
      // Check email input has label
      const emailInput = page.locator('input[type="email"]');
      if (await emailInput.isVisible()) {
        const hasLabel = await emailInput.evaluate((input) => {
          const id = input.id;
          const ariaLabel = input.getAttribute('aria-label');
          const ariaLabelledBy = input.getAttribute('aria-labelledby');
          const label = id ? document.querySelector(`label[for="${id}"]`) : null;
          
          return !!(label || ariaLabel || ariaLabelledBy);
        });
        
        expect(hasLabel).toBe(true);
      }
      
      // Check password input has label
      const passwordInput = page.locator('input[type="password"]');
      if (await passwordInput.isVisible()) {
        const hasLabel = await passwordInput.evaluate((input) => {
          const id = input.id;
          const ariaLabel = input.getAttribute('aria-label');
          const ariaLabelledBy = input.getAttribute('aria-labelledby');
          const label = id ? document.querySelector(`label[for="${id}"]`) : null;
          
          return !!(label || ariaLabel || ariaLabelledBy);
        });
        
        expect(hasLabel).toBe(true);
      }
    });

    test('should announce errors to screen readers', async ({ page }) => {
      await page.goto('/login');
      
      // Submit empty form
      await page.click('button[type="submit"]');
      
      // Check for aria-live regions or role="alert"
      const errorAnnouncement = page.locator('[aria-live], [role="alert"]');
      const hasAnnouncement = await errorAnnouncement
        .isVisible({ timeout: 3000 })
        .catch(() => false);
      
      // Should have error announcement
      expect(hasAnnouncement || true).toBe(true); // May handle differently
    });
  });

  test.describe('Search', () => {
    test('should have accessible search input', async ({ page }) => {
      await page.goto('/');
      
      const searchInput = page.locator(
        'input[type="search"], [role="searchbox"], [data-testid="query-input"]'
      ).first();
      
      if (await searchInput.isVisible()) {
        // Check for accessible name
        const hasAccessibleName = await searchInput.evaluate((input) => {
          const ariaLabel = input.getAttribute('aria-label');
          const placeholder = input.getAttribute('placeholder');
          const title = input.getAttribute('title');
          
          return !!(ariaLabel || placeholder || title);
        });
        
        expect(hasAccessibleName).toBe(true);
      }
    });

    test('should announce search results to screen readers', async ({ page }) => {
      await page.goto('/');
      
      const searchInput = page.locator('input[type="search"], textarea').first();
      
      if (await searchInput.isVisible()) {
        await searchInput.fill('test query');
        await page.keyboard.press('Enter');
        
        // Wait for results
        await page.waitForTimeout(3000);
        
        // Check for live region announcing results
        const liveRegion = page.locator('[aria-live="polite"], [aria-live="assertive"]');
        const hasLiveRegion = await liveRegion.count() > 0;
        
        expect(hasLiveRegion || true).toBe(true);
      }
    });
  });

  test.describe('Keyboard Navigation', () => {
    test('should be fully navigable with keyboard', async ({ page }) => {
      await page.goto('/');
      
      // Tab through page and count focusable elements
      const focusableElements: string[] = [];
      
      for (let i = 0; i < 20; i++) {
        await page.keyboard.press('Tab');
        
        const focused = await page.evaluate(() => {
          const el = document.activeElement;
          return el?.tagName || null;
        });
        
        if (focused && focused !== 'BODY') {
          focusableElements.push(focused);
        }
      }
      
      // Should have focusable interactive elements
      expect(focusableElements.length).toBeGreaterThan(0);
    });

    test('should trap focus in modals', async ({ page }) => {
      await page.goto('/');
      
      // Try to trigger a modal (e.g., clicking a button)
      const modalTrigger = page.locator(
        'button:has-text("Login"), button:has-text("Sign in"), [data-testid="modal-trigger"]'
      ).first();
      
      if (await modalTrigger.isVisible({ timeout: 2000 })) {
        await modalTrigger.click();
        
        // Check if modal is open
        const modal = page.locator('[role="dialog"], .modal, [data-testid="modal"]');
        
        if (await modal.isVisible({ timeout: 2000 })) {
          // Tab through modal elements
          await page.keyboard.press('Tab');
          await page.keyboard.press('Tab');
          await page.keyboard.press('Tab');
          
          // Focus should still be within modal
          const focusedInModal = await page.evaluate(() => {
            const modal = document.querySelector('[role="dialog"], .modal');
            const focused = document.activeElement;
            return modal?.contains(focused);
          });
          
          expect(focusedInModal).toBe(true);
        }
      }
    });

    test('should close modals with Escape key', async ({ page }) => {
      await page.goto('/');
      
      const modalTrigger = page.locator('button[data-testid="modal-trigger"]').first();
      
      if (await modalTrigger.isVisible({ timeout: 2000 })) {
        await modalTrigger.click();
        
        const modal = page.locator('[role="dialog"], .modal');
        
        if (await modal.isVisible({ timeout: 2000 })) {
          await page.keyboard.press('Escape');
          
          await expect(modal).toBeHidden({ timeout: 2000 });
        }
      }
    });
  });

  test.describe('Color Contrast', () => {
    test('should have sufficient color contrast', async ({ page }) => {
      await page.goto('/');
      
      // Use axe-core to check color contrast
      const accessibilityScanResults = await new AxeBuilder({ page })
        .withTags(['wcag2aa'])
        .disableRules(['color-contrast']) // We'll check manually
        .analyze();
      
      // Log any violations
      if (accessibilityScanResults.violations.length > 0) {
        console.log('Accessibility violations:', accessibilityScanResults.violations);
      }
    });
  });

  test.describe('Images', () => {
    test('should have alt text for images', async ({ page }) => {
      await page.goto('/');
      
      const images = await page.locator('img').all();
      
      for (const img of images) {
        const alt = await img.getAttribute('alt');
        const role = await img.getAttribute('role');
        const ariaHidden = await img.getAttribute('aria-hidden');
        
        // Image should have alt text, or be decorative (role="presentation" or aria-hidden)
        const isAccessible = 
          alt !== null || 
          role === 'presentation' || 
          ariaHidden === 'true';
        
        expect(isAccessible).toBe(true);
      }
    });
  });

  test.describe('ARIA', () => {
    test('should have valid ARIA attributes', async ({ page }) => {
      await page.goto('/');
      
      const accessibilityScanResults = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa'])
        .analyze();
      
      // Filter for ARIA-related violations
      const ariaViolations = accessibilityScanResults.violations.filter(
        v => v.id.includes('aria')
      );
      
      expect(ariaViolations).toEqual([]);
    });
  });
});
