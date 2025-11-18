/**
 * Backtests List E2E Tests
 *
 * Tests backtest list page functionality
 */

import { test, expect } from '@playwright/test';

test.describe('Backtests List', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/#/backtests');
  });

  test('should load backtests page', async ({ page }) => {
    // Page should load
    await expect(page).toHaveURL(/backtests/);

    // Should show page content (either backtests or empty state)
    await expect(page.locator('text=/backtest|no data|loading/i').first()).toBeVisible({
      timeout: 10000,
    });
  });

  test.skip('should show loading skeleton while fetching data', async ({ page }) => {
    // This test is too flaky - loading is very fast with local backend
    // Skeleton appears for <100ms, making it nearly impossible to catch
    // TODO: Mock API with delay to properly test skeleton loading
  });

  test('should handle empty state gracefully', async ({ page }) => {
    // BacktestsPage always shows table structure
    // Check for "Всего:" heading (total count)
    const totalCount = page.getByRole('heading', { name: /всего/i });

    // Should show table structure
    await expect(totalCount).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to backtest details when clicking item', async ({ page }) => {
    // Wait for any backtest items to load
    const firstBacktest = page.locator('[data-testid="backtest-item"]').first();

    // If backtests exist, test navigation
    const exists = await firstBacktest.isVisible({ timeout: 5000 }).catch(() => false);

    if (exists) {
      await firstBacktest.click();

      // Should navigate to detail page
      await expect(page).toHaveURL(/backtests\/\d+/);
    } else {
      // Skip if no backtests
      test.skip();
    }
  });
});
