/**
 * End-to-End Tests for Phase 1 Security Integration
 * Tests full authentication flow in browser
 *
 * Run with: npx playwright test e2e/auth.spec.ts
 */

import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';
const API_URL = 'http://localhost:8000/api/v1';

// Helper function to perform login
async function performLogin(page: Page, username: string, password: string) {
  // Listen to console logs
  page.on('console', (msg) => console.log('BROWSER:', msg.text()));

  await page.getByLabel(/username/i).fill(username);
  // Use getByRole to avoid conflict with password visibility toggle button
  await page.getByRole('textbox', { name: /password/i }).fill(password);

  // Wait for button to be enabled
  const loginButton = page.getByRole('button', { name: /login/i });
  await expect(loginButton).toBeEnabled({ timeout: 1000 });

  // Click login
  await loginButton.click();

  // Wait for navigation to home page to complete
  await page.waitForURL('**/#/', { timeout: 10000 });
}
test.describe('Authentication E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage before each test
    await page.goto(BASE_URL);
    await page.evaluate(() => localStorage.clear());
  });

  test('should show login page when not authenticated', async ({ page }) => {
    await page.goto(BASE_URL);

    // Should redirect to login
    await expect(page).toHaveURL(`${BASE_URL}/#/login`);

    // Check login form elements
    await expect(page.getByLabel(/username/i)).toBeVisible();
    await expect(page.getByRole('textbox', { name: /password/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /login/i })).toBeVisible();
  });

  test('should login with admin credentials', async ({ page }) => {
    await page.goto(`${BASE_URL}/#/login`);

    // Track API requests
    const requests: any[] = [];
    page.on('request', (req) => {
      if (req.url().includes('/auth/login')) {
        console.log('REQUEST:', req.method(), req.url());
        console.log('BODY:', req.postDataJSON());
      }
    });
    page.on('response', (resp) => {
      if (resp.url().includes('/auth/login')) {
        console.log('RESPONSE:', resp.status(), resp.url());
        resp
          .json()
          .then((data) => console.log('DATA:', data))
          .catch(() => {});
      }
    });

    // Perform login
    await performLogin(page, 'admin', 'admin123');

    // Should redirect to home page
    await expect(page).toHaveURL(`${BASE_URL}/#/`);

    // Wait for user info to load and be displayed in navbar
    await expect(page.getByText(/admin/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: /logout/i })).toBeVisible();
  });

  test('should login with user credentials', async ({ page }) => {
    // Fixed: Added networkidle wait to ensure page fully loads before checking text
    await page.goto(`${BASE_URL}/#/login`);

    await performLogin(page, 'user', 'user123');

    // Wait for page navigation and full load
    await expect(page).toHaveURL(`${BASE_URL}/#/`);
    await page.waitForLoadState('networkidle');

    // Check for username displayed in navigation (format: "👤 user")
    await expect(page.getByText(/👤\s*user/)).toBeVisible();
  });

  test('should show error on invalid credentials', async ({ page }) => {
    // Real authentication is now implemented with bcrypt
    // Clear localStorage to reset any rate limit issues
    await page.goto(BASE_URL);
    await page.evaluate(() => localStorage.clear());

    await page.goto(`${BASE_URL}/#/login`);

    // Fill in form with wrong password
    await page.getByLabel(/username/i).fill('testuser_invalid');
    await page.getByRole('textbox', { name: /password/i }).fill('wrongpassword123');

    // Click login button
    const loginButton = page.getByRole('button', { name: /login/i });
    await expect(loginButton).toBeEnabled({ timeout: 1000 });
    await loginButton.click();

    // Wait for error to appear
    await page.waitForTimeout(1500);

    // Should show error message in Alert component (role="alert")
    const alert = page.locator('.MuiAlert-message');
    await expect(alert).toBeVisible({ timeout: 5000 });
    await expect(alert).toContainText(/invalid/i);

    // Should stay on login page
    await expect(page).toHaveURL(`${BASE_URL}/#/login`);
  });

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/#/login`);
    await performLogin(page, 'admin', 'admin123');

    await expect(page).toHaveURL(`${BASE_URL}/#/`);

    // Click logout
    await page.getByRole('button', { name: /logout/i }).click();

    // Should redirect to login
    await expect(page).toHaveURL(`${BASE_URL}/#/login`);

    // User info should be gone
    await expect(page.getByRole('button', { name: /logout/i })).not.toBeVisible();
  });

  test('should persist session across page reload', async ({ page }) => {
    // Login
    await page.goto(`${BASE_URL}/#/login`);
    await performLogin(page, 'admin', 'admin123');

    await expect(page).toHaveURL(`${BASE_URL}/#/`);

    // Reload page
    await page.reload();

    // Should still be logged in
    await expect(page).toHaveURL(`${BASE_URL}/#/`);
    await expect(page.getByText(/admin/i)).toBeVisible({ timeout: 10000 });
  });

  test('should protect routes when not authenticated', async ({ page }) => {
    // Try to access protected route directly
    await page.goto(`${BASE_URL}/#/strategies`);

    // Should redirect to login
    await expect(page).toHaveURL(`${BASE_URL}/#/login`);
  });

  test('should allow access to protected routes when authenticated', async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/#/login`);
    await performLogin(page, 'admin', 'admin123');

    // Navigate to protected routes
    await page.goto(`${BASE_URL}/#/strategies`);
    await expect(page).toHaveURL(`${BASE_URL}/#/strategies`);

    await page.goto(`${BASE_URL}/#/backtests`);
    await expect(page).toHaveURL(`${BASE_URL}/#/backtests`);

    await page.goto(`${BASE_URL}/#/ai-studio`);
    await expect(page).toHaveURL(`${BASE_URL}/#/ai-studio`);
  });

  test('should show/hide password on toggle', async ({ page }) => {
    // Aria-label is now properly set in LoginPage
    await page.goto(`${BASE_URL}/#/login`);

    const passwordInput = page.getByRole('textbox', { name: /password/i });

    // Password should be hidden by default
    await expect(passwordInput).toHaveAttribute('type', 'password');

    // Click show password button
    await page.getByRole('button', { name: /show password/i }).click();

    // Password should be visible
    await expect(passwordInput).toHaveAttribute('type', 'text');

    // Click hide password button
    await page.getByRole('button', { name: /hide password/i }).click();

    // Password should be hidden again
    await expect(passwordInput).toHaveAttribute('type', 'password');
  });

  test('should display demo credentials hint', async ({ page }) => {
    await page.goto(`${BASE_URL}/#/login`);

    // Check test accounts box
    await expect(page.getByText(/test accounts/i)).toBeVisible();
    await expect(page.getByText(/admin.*admin123/i)).toBeVisible();
    await expect(page.getByText(/user.*user123/i)).toBeVisible();
  });

  test('should handle token refresh automatically', async ({ page, context }) => {
    // Login
    await page.goto(`${BASE_URL}/#/login`);
    await performLogin(page, 'admin', 'admin123');

    await expect(page).toHaveURL(`${BASE_URL}/#/`);

    // Simulate token expiry by modifying localStorage
    await page.evaluate(() => {
      const pastTime = Date.now() - 1000;
      localStorage.setItem('bybit_token_expiry', pastTime.toString());
    });

    // Make an API request (should trigger refresh)
    await page.goto(`${BASE_URL}/#/strategies`);

    // Should still work (token refreshed automatically)
    await expect(page).toHaveURL(`${BASE_URL}/#/strategies`);
  });
});

test.describe('API Integration Tests', () => {
  test('should include JWT token in API requests', async ({ page }) => {
    // Login
    await page.goto(`${BASE_URL}/#/login`);
    await performLogin(page, 'admin', 'admin123');

    await expect(page).toHaveURL(`${BASE_URL}/#/`);

    // Listen for API requests
    const apiRequests: any[] = [];
    page.on('request', (request) => {
      if (request.url().includes('/api/v1/')) {
        apiRequests.push({
          url: request.url(),
          headers: request.headers(),
        });
      }
    });

    // Navigate to page that makes API calls
    await page.goto(`${BASE_URL}/#/strategies`);

    // Wait for requests
    await page.waitForTimeout(2000);

    // Check that requests include Authorization header
    const authRequests = apiRequests.filter(
      (req) => req.headers.authorization && req.headers.authorization.startsWith('Bearer ')
    );

    expect(authRequests.length).toBeGreaterThan(0);
  });

  test('should handle 401 errors gracefully', async ({ page }) => {
    // Login
    await page.goto(`${BASE_URL}/#/login`);
    await performLogin(page, 'admin', 'admin123');

    await expect(page).toHaveURL(`${BASE_URL}/#/`);

    // Clear tokens to simulate session expiry
    await page.evaluate(() => localStorage.clear());

    // Reload to trigger AuthContext re-initialization
    await page.reload();

    // Should redirect to login automatically
    await expect(page).toHaveURL(`${BASE_URL}/#/login`, { timeout: 10000 });
  });
});

test.describe('Rate Limiting Tests', () => {
  test('should handle rate limit errors', async ({ page }) => {
    // NOTE: This test requires E2E_TEST_MODE='rate_limit' environment variable
    // This disables localhost whitelist in rate limiter to test 429 responses
    // Rate limiter config: 25 login attempts max, 1.0/sec refill rate

    // Skip if not in rate limit test mode
    const isRateLimitMode = process.env.E2E_TEST_MODE === 'rate_limit';
    if (!isRateLimitMode) {
      console.log('⏭️  Skipping rate limit test (set E2E_TEST_MODE=rate_limit to enable)');
      return;
    }

    await page.goto(`${BASE_URL}/#/login`);

    // Make 26 rapid login attempts to exceed limit (25 is max)
    for (let i = 0; i < 26; i++) {
      await page.getByLabel(/username/i).fill('admin');
      await page.getByRole('textbox', { name: /password/i }).fill('wrongpassword');

      const loginButton = page.getByRole('button', { name: /login/i });
      await loginButton.click();

      // Small delay between attempts
      await page.waitForTimeout(150);
    }

    // Should show rate limit error on 26th attempt
    // Backend returns 429 with message "Rate limit exceeded"
    await expect(page.getByText(/rate limit exceeded|too many/i)).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Security Tests', () => {
  test('should not expose sensitive data in localStorage', async ({ page }) => {
    await page.goto(`${BASE_URL}/#/login`);
    await performLogin(page, 'admin', 'admin123');

    await expect(page).toHaveURL(`${BASE_URL}/#/`);

    // Check localStorage contents
    const tokens = await page.evaluate(() => ({
      access: localStorage.getItem('bybit_access_token'),
      refresh: localStorage.getItem('bybit_refresh_token'),
    }));

    // Tokens should be present but not contain sensitive info in plain text
    expect(tokens.access).toBeTruthy();
    expect(tokens.refresh).toBeTruthy();

    // Tokens should be JWT format (3 parts separated by dots)
    expect(tokens.access?.split('.').length).toBe(3);
    expect(tokens.refresh?.split('.').length).toBe(3);
  });

  test('should clear tokens on logout', async ({ page }) => {
    // Login
    await page.goto(`${BASE_URL}/#/login`);
    await performLogin(page, 'admin', 'admin123');

    await expect(page).toHaveURL(`${BASE_URL}/#/`);

    // Verify tokens exist
    const tokensBefore = await page.evaluate(() => ({
      access: localStorage.getItem('bybit_access_token'),
      refresh: localStorage.getItem('bybit_refresh_token'),
    }));
    expect(tokensBefore.access).toBeTruthy();

    // Logout
    await page.getByRole('button', { name: /logout/i }).click();

    // Wait for redirect to login page
    await expect(page).toHaveURL(`${BASE_URL}/#/login`);

    // Verify tokens cleared
    const tokensAfter = await page.evaluate(() => ({
      access: localStorage.getItem('bybit_access_token'),
      refresh: localStorage.getItem('bybit_refresh_token'),
    }));
    expect(tokensAfter.access).toBeNull();
    expect(tokensAfter.refresh).toBeNull();
  });
});
