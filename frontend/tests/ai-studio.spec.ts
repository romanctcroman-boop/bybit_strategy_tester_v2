/**
 * AI Studio E2E Tests
 *
 * Tests AI Studio page with Perplexity integration
 */

import { test, expect } from '@playwright/test';

test.describe('AI Studio', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/#/ai-studio');
  });

  test('should load AI Studio page', async ({ page }) => {
    await expect(page).toHaveURL(/ai-studio/);

    // Page should have AI Studio content
    await expect(page.locator('text=/ai|perplexity|studio/i').first()).toBeVisible({
      timeout: 10000,
    });
  });

  test('should have input for AI queries', async ({ page }) => {
    // Input field - AI Studio uses MUI TextField with multiline (textarea)
    const input = page.getByPlaceholder(/ask ai anything|trading strategies|backtests/i);

    await expect(input).toBeVisible({ timeout: 5000 });
  });

  test('should have submit/send button', async ({ page }) => {
    // AI Studio uses Button with Send icon
    // Wait for page to fully load first
    await page.waitForLoadState('networkidle');

    // Look for the Send button (it's a contained button in the input area)
    const sendButton = page.locator('button[type="button"]').last();

    // Should exist
    await expect(sendButton).toBeVisible({ timeout: 5000 });
  });

  test('should display AI response area', async ({ page }) => {
    // AI Studio shows welcome message on load
    // Look for the welcome message content
    const welcomeMessage = page.locator('text=/welcome to ai studio|strategy code generation/i');

    await expect(welcomeMessage).toBeVisible({ timeout: 5000 });
  });

  // Note: Actual AI query testing would require mocking or real API key
  test.skip('should send query and receive AI response', async ({ page }) => {
    // This test requires either:
    // 1. Mocking the Perplexity API
    // 2. Using a test API key
    // Skip for now, implement when API mocking is set up
  });
});
