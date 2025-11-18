/**
 * Dashboard E2E Tests
 *
 * Tests home page/dashboard functionality
 */

import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('should load dashboard page', async ({ page }) => {
    await page.goto('/');

    // Check page loads
    await expect(page).toHaveTitle(/Bybit/i);

    // Check navigation exists
    await expect(page.getByRole('link', { name: /home/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /ai studio/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /backtests/i })).toBeVisible();
  });

  test('should navigate to AI Studio', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /ai studio/i }).click();

    // Wait for navigation
    await page.waitForURL('**/#/ai-studio');

    // Verify we're on AI Studio page
    await expect(page).toHaveURL(/ai-studio/);
  });

  test('should navigate to Backtests page', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /backtests/i }).click();

    await page.waitForURL('**/#/backtests');
    await expect(page).toHaveURL(/backtests/);
  });

  test.skip('should show API health indicator', async ({ page }) => {
    // API health indicator не реализован на HomePage (Dashboard)
    // TODO: Добавить API health indicator на HomePage
    // Или перенести тест на другую страницу где он есть
  });
});
