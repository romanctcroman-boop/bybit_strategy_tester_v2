# 🧪 Phase 1 Security Testing Guide

Comprehensive test suite for Phase 1 Security Integration covering:
- JWT Authentication
- Rate Limiting
- Sandbox Execution
- Frontend Integration
- E2E Browser Tests

---

## 📋 Test Coverage

### Backend Tests (`tests/test_phase1_security.py`)
- ✅ **JWT Authentication** (13 tests)
  - Login/logout flow
  - Token creation and validation
  - Protected endpoints
  - Token refresh
  - Scope-based authorization
  
- ✅ **Rate Limiting** (5 tests)
  - TokenBucket algorithm
  - Token consumption
  - Rate limit enforcement
  - Retry-After headers
  
- ✅ **Sandbox Executor** (6 tests)
  - Safe code execution
  - Forbidden imports blocking
  - Network access blocking
  - Timeout enforcement
  - Memory limits
  - Escape attempt detection
  
- ✅ **Integration Tests** (4 tests)
  - Full authentication flow
  - Rate limiting with auth
  - CORS headers
  
- ✅ **Performance Tests** (2 tests)
  - JWT validation speed
  - Sandbox execution overhead

**Total: 30 backend tests**

### Frontend Tests (`frontend/tests/auth.test.ts`)
- ✅ **Token Storage** (4 tests)
- ✅ **Token Expiry** (4 tests)
- ✅ **Login** (3 tests)
- ✅ **Token Refresh** (3 tests)
- ✅ **Get Current User** (3 tests)
- ✅ **Logout** (2 tests)
- ✅ **Auth Header** (2 tests)
- ✅ **Login Status** (3 tests)

**Total: 24 frontend unit tests**

### E2E Tests (`frontend/tests/e2e/auth.spec.ts`)
- ✅ **Authentication Flow** (11 tests)
  - Login page display
  - Login with credentials
  - Error handling
  - Logout
  - Session persistence
  - Route protection
  
- ✅ **API Integration** (2 tests)
  - JWT token in requests
  - 401 error handling
  
- ✅ **Rate Limiting** (1 test)
  - Rate limit error handling
  
- ✅ **Security** (2 tests)
  - Token storage security
  - Token cleanup

**Total: 16 E2E tests**

---

## 🚀 Running Tests

### Prerequisites

**Backend:**
```bash
# Install dependencies
cd d:\bybit_strategy_tester_v2
pip install pytest pytest-asyncio httpx

# Make sure backend is running
py -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
```

**Frontend:**
```bash
# Install dependencies
cd d:\bybit_strategy_tester_v2\frontend
npm install

# Make sure frontend is running
npm run dev
```

---

### Backend Tests

#### Run All Tests:
```bash
cd d:\bybit_strategy_tester_v2
pytest tests/test_phase1_security.py -v
```

#### Run Specific Test Class:
```bash
# JWT Authentication tests only
pytest tests/test_phase1_security.py::TestJWTAuthentication -v

# Rate Limiting tests only
pytest tests/test_phase1_security.py::TestRateLimiting -v

# Sandbox tests only
pytest tests/test_phase1_security.py::TestSandboxExecutor -v
```

#### Run with Coverage:
```bash
pytest tests/test_phase1_security.py --cov=backend.auth --cov=backend.middleware --cov=backend.security --cov-report=html
```

#### Run Specific Test:
```bash
pytest tests/test_phase1_security.py::TestJWTAuthentication::test_login_success_admin -v
```

---

### Frontend Unit Tests

#### Run All Tests:
```bash
cd d:\bybit_strategy_tester_v2\frontend
npm test
```

#### Run in Watch Mode:
```bash
npm test -- --watch
```

#### Run with Coverage:
```bash
npm test -- --coverage
```

---

### E2E Tests (Playwright)

#### Run All E2E Tests:
```bash
cd d:\bybit_strategy_tester_v2\frontend
npx playwright test tests/e2e/auth.spec.ts
```

#### Run in Headed Mode (see browser):
```bash
npx playwright test tests/e2e/auth.spec.ts --headed
```

#### Run in Debug Mode:
```bash
npx playwright test tests/e2e/auth.spec.ts --debug
```

#### Run Specific Test:
```bash
npx playwright test tests/e2e/auth.spec.ts -g "should login with admin credentials"
```

#### View Test Report:
```bash
npx playwright show-report
```

---

## 📊 Expected Results

### Backend Tests
```
✅ TestJWTAuthentication::test_login_success_admin PASSED
✅ TestJWTAuthentication::test_login_success_user PASSED
✅ TestJWTAuthentication::test_login_failure_wrong_password PASSED
✅ TestJWTAuthentication::test_protected_endpoint_with_valid_token PASSED
✅ TestJWTAuthentication::test_token_refresh PASSED
✅ TestJWTAuthentication::test_admin_scopes PASSED
✅ TestRateLimiting::test_token_bucket_creation PASSED
✅ TestRateLimiting::test_rate_limit_triggered_over_limit PASSED
✅ TestSandboxExecutor::test_safe_code_execution PASSED
✅ TestSandboxExecutor::test_forbidden_import_blocked PASSED
✅ TestSandboxExecutor::test_timeout_enforcement PASSED
✅ TestSecurityIntegration::test_full_authentication_flow PASSED

========================== 30 passed in 45.2s ==========================
```

### Frontend Tests
```
✅ Auth Service › Token Storage › should save tokens to localStorage
✅ Auth Service › Login › should login successfully with valid credentials
✅ Auth Service › Token Refresh › should refresh access token successfully
✅ Auth Service › Logout › should logout and clear tokens

Test Suites: 1 passed, 1 total
Tests:       24 passed, 24 total
Time:        2.5s
```

### E2E Tests
```
✅ Authentication E2E Tests › should show login page when not authenticated
✅ Authentication E2E Tests › should login with admin credentials
✅ Authentication E2E Tests › should logout successfully
✅ Authentication E2E Tests › should persist session across page reload
✅ Authentication E2E Tests › should protect routes when not authenticated
✅ API Integration Tests › should include JWT token in API requests
✅ Security Tests › should not expose sensitive data in localStorage

 16 passed (1.2m)
```

---

## 🐛 Troubleshooting

### Backend Tests Failing

**Issue:** Tests fail with connection errors
```
ConnectionError: Connection refused
```
**Solution:** Make sure backend is running on port 8000
```bash
py -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
```

**Issue:** Docker tests fail
```
Error: Docker daemon not running
```
**Solution:** Start Docker Desktop or Docker service

**Issue:** Rate limiting tests fail
```
AssertionError: Rate limit not triggered
```
**Solution:** Whitelist was enabled. Already fixed - localhost removed from whitelist.

---

### Frontend Tests Failing

**Issue:** Module not found errors
```
Cannot find module 'vitest'
```
**Solution:** Install test dependencies
```bash
npm install --save-dev vitest @vitest/ui
```

**Issue:** Test timeout
```
Timeout exceeded
```
**Solution:** Increase timeout in vitest.config.ts
```typescript
export default defineConfig({
  test: {
    testTimeout: 10000,
  }
})
```

---

### E2E Tests Failing

**Issue:** Browser not found
```
Error: Browser not found
```
**Solution:** Install Playwright browsers
```bash
npx playwright install
```

**Issue:** Page not loading
```
TimeoutError: page.goto: Timeout 30000ms exceeded
```
**Solution:** Make sure frontend dev server is running on port 5173
```bash
npm run dev
```

**Issue:** Login test fails
```
Error: Login button not found
```
**Solution:** Check that frontend is properly built with login page

---

## 📈 Test Metrics

### Coverage Goals
- **Backend:** > 80% coverage
- **Frontend:** > 70% coverage
- **E2E:** Cover all critical user flows

### Performance Benchmarks
- JWT validation: < 20ms per token
- Rate limiting: < 5ms per request
- Sandbox execution: < 5 seconds for simple code
- E2E full flow: < 30 seconds

---

## 🔍 Manual Testing Checklist

Use this checklist for manual verification:

### Authentication Flow
- [ ] Login page displays correctly
- [ ] Login with admin works
- [ ] Login with user works
- [ ] Invalid credentials show error
- [ ] User info shows in navbar after login
- [ ] Logout clears session
- [ ] Session persists after page reload

### Protected Routes
- [ ] Accessing protected route without login redirects to /login
- [ ] After login, protected routes are accessible
- [ ] All navigation links work while authenticated

### Token Management
- [ ] Tokens saved to localStorage
- [ ] Tokens included in API requests (check Network tab)
- [ ] Token refresh works on 401 errors
- [ ] Tokens cleared on logout

### Rate Limiting
- [ ] Making 25+ rapid requests to /health triggers 429
- [ ] Retry-After header present in 429 response
- [ ] Rate limit applies to all endpoints

### Security
- [ ] No sensitive data in console logs
- [ ] JWT tokens are properly formatted
- [ ] Protected endpoints require authentication
- [ ] Scope checking works for admin endpoints

---

## 📝 Adding New Tests

### Backend Test Template:
```python
class TestNewFeature:
    """Test description"""
    
    def test_feature_works(self):
        """Test that feature works correctly"""
        response = client.post("/api/v1/endpoint", json={...})
        
        assert response.status_code == 200
        assert "expected_field" in response.json()
```

### Frontend Test Template:
```typescript
describe('New Feature', () => {
  it('should work correctly', () => {
    // Arrange
    const input = {...};
    
    // Act
    const result = someFunction(input);
    
    // Assert
    expect(result).toBe(expected);
  });
});
```

### E2E Test Template:
```typescript
test('should do something in browser', async ({ page }) => {
  await page.goto(BASE_URL);
  
  await page.getByLabel('Input').fill('value');
  await page.getByRole('button', { name: 'Submit' }).click();
  
  await expect(page.getByText('Success')).toBeVisible();
});
```

---

## 🎯 Next Steps

1. **Run all tests** to verify current implementation
2. **Fix any failing tests** (should all pass)
3. **Add coverage reporting** to CI/CD pipeline
4. **Create integration tests** for Phase 2 components
5. **Add performance tests** for high-load scenarios

---

## 📚 Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)
- [Playwright Documentation](https://playwright.dev/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [React Testing Library](https://testing-library.com/react)

---

**Test Suite Version:** 1.0  
**Last Updated:** 2025-01-04  
**Total Tests:** 70 (30 backend + 24 frontend + 16 E2E)
