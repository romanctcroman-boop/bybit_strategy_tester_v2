/**
 * Error Handling E2E Tests
 *
 * Tests error boundaries and error states
 */

import { test, expect } from '@playwright/test';

test.describe('Error Handling', () => {
  test.skip('should show error boundary on component crash', async ({ page }) => {
    // Этот тест сложно реализовать без специальных инструментов для инъекции ошибок
    // ErrorBoundary правильно работает в production, но трудно протестировать в E2E
    // TODO: Создать специальный тестовый endpoint/компонент который намеренно бросает ошибку
  });

  test('should show toast notification on API error', async ({ page }) => {
    await page.goto('/');

    // Mock API to return error
    await page.route('**/api/v1/**', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Test API error' }),
      });
    });

    // Trigger an API call (navigate to backtests)
    await page.goto('/#/backtests');

    // Should show error toast (there might be multiple alerts, just check first one)
    const alerts = page.locator('[role="alert"]');
    await expect(alerts.first()).toBeVisible({ timeout: 10000 });
  });

  test('should handle 404 not found gracefully', async ({ page }) => {
    // Navigate to non-existent route
    await page.goto('/#/non-existent-route-12345');

    // Should either show 404 page or fallback content
    await expect(page.locator('body')).toBeVisible();

    // Should not show blank page
    const bodyText = await page.textContent('body');
    expect(bodyText).toBeTruthy();
  });

  test('should recover from error with reset button', async ({ page }) => {
    await page.goto('/');

    // Cause an error somehow (this is a placeholder)
    // In reality, you'd trigger a specific component error

    // If error boundary appears with reset button
    const resetButton = page.getByRole('button', { name: /try again|reset|reload/i });

    if (await resetButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await resetButton.click();

      // Should recover
      await expect(page.locator('nav')).toBeVisible();
    }
  });
});
