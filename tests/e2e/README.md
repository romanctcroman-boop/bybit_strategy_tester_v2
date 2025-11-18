# E2E Integration Testing Guide

Complete guide for end-to-end integration testing of the Bybit Strategy Tester system.

## Overview

E2E tests validate complete workflows across multiple components:
- REST API endpoints
- Database operations
- Redis caching
- External API integrations (Bybit)
- Background task processing

## Test Structure

```
tests/e2e/
├── __init__.py                  # Module documentation
├── conftest.py                  # Fixtures and configuration
├── test_full_workflow.py        # Happy path workflows
├── test_error_handling.py       # Error scenarios and edge cases
└── README.md                    # This file
```

## Setup

### Prerequisites

1. **PostgreSQL Database** (test database)
   ```bash
   # Create test database
   createdb bybit_test
   
   # Or use Docker
   docker-compose -f docker-compose.test.yml up -d postgres
   ```

2. **Redis Instance** (separate test DB)
   ```bash
   # Redis uses DB 1 for tests (DB 0 for dev)
   docker-compose -f docker-compose.test.yml up -d redis
   ```

3. **Environment Variables**
   ```bash
   # Set test database URL
   export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/bybit_test"
   
   # Redis URL (optional, defaults to localhost:6379)
   export REDIS_URL="redis://localhost:6379"
   ```

### Installation

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Verify environment
pytest tests/e2e/conftest.py --collect-only
```

## Running Tests

### All E2E Tests
```bash
pytest tests/e2e/ -v
```

### Specific Test File
```bash
pytest tests/e2e/test_full_workflow.py -v
pytest tests/e2e/test_error_handling.py -v
```

### Specific Test Class
```bash
pytest tests/e2e/test_full_workflow.py::TestStrategyToBacktest -v
```

### Specific Test Function
```bash
pytest tests/e2e/test_full_workflow.py::TestStrategyToBacktest::test_create_strategy_and_run_backtest -v
```

### Exclude Slow Tests
```bash
# Run only fast tests
pytest tests/e2e/ -v -m "not slow"

# Run only slow tests
pytest tests/e2e/ -v -m slow
```

### With Coverage
```bash
pytest tests/e2e/ -v --cov=backend --cov-report=html
```

### Parallel Execution
```bash
# Install pytest-xdist
pip install pytest-xdist

# Run with 4 workers
pytest tests/e2e/ -v -n 4
```

## Test Categories

### 1. Full Workflow Tests (`test_full_workflow.py`)

Complete user journey tests covering happy paths.

**Test Classes:**

- **TestStrategyToBacktest**: Strategy creation → Backtest → Results
  ```python
  test_create_strategy_and_run_backtest()  # Basic workflow
  test_backtest_to_csv_export()           # Backtest → CSV
  ```

- **TestOptimizationWorkflow**: Strategy → Optimization → Best params
  ```python
  test_optimization_workflow()  # Grid search optimization
  ```

- **TestTemplateToStrategy**: Template → Strategy → Backtest
  ```python
  test_create_from_template()  # Template-based creation
  ```

- **TestFullLifecycle**: Complete system lifecycle
  ```python
  test_full_lifecycle()  # Create → Backtest → Optimize → Export → Delete
  ```

- **TestPerformanceE2E**: Performance benchmarks
  ```python
  test_large_backtest_performance()  # 1 year of 15m candles
  ```

**Example Output:**
```
✅ Backtest completed successfully!
   Initial Capital: $10,000.00
   Final Capital: $12,345.67
   Total Return: 23.46%
   Sharpe Ratio: 1.85
```

### 2. Error Handling Tests (`test_error_handling.py`)

Validation, boundary conditions, and error scenarios.

**Test Classes:**

- **TestStrategyValidation**: Invalid strategy inputs
  - Syntax errors in code
  - Missing required fields
  - Invalid parameter types
  - Duplicate strategy names

- **TestBacktestValidation**: Invalid backtest inputs
  - Nonexistent strategy ID
  - Invalid date ranges (end before start)
  - Invalid trading symbols
  - Zero or negative capital

- **TestOptimizationValidation**: Invalid optimization inputs
  - Empty parameter ranges
  - Invalid metrics

- **TestResourceNotFound**: 404 scenarios
  - Nonexistent strategies
  - Nonexistent backtests
  - Invalid exports

- **TestBoundaryConditions**: Edge cases
  - Minimum date ranges (1 day)
  - Very long code (1000+ lines)

- **TestConcurrency**: Race conditions
  - Concurrent backtest creation

- **TestExternalAPIDependencies**: API failures
  - Data fetch failures (invalid dates)

**Expected Errors:**
```
✅ Caught syntax error: SyntaxError at line 2
✅ Caught invalid date range error: end_date must be after start_date
✅ 404: Strategy not found
```

## Test Fixtures

### Database Fixtures

- **`test_engine`** (session-scoped): Database engine for all tests
- **`test_db`** (function-scoped): Fresh database session per test (with rollback)
- **`clean_database`** (function-scoped): Clean slate (deletes all records)

### Strategy Fixtures

- **`test_strategy`** (module-scoped): Pre-created Bollinger Bands strategy
- **`sample_strategy_code`**: Reusable strategy code template
- **`sample_strategy_params`**: Standard parameter definitions

### Redis Fixtures

- **`test_redis`** (session-scoped): Redis client using DB 1

### Client Fixture

- **`client`**: FastAPI TestClient for API calls

## Writing New E2E Tests

### Basic Structure

```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture(scope="module")
def client():
    """Create test client"""
    from backend.api.app import app
    return TestClient(app)

class TestYourFeature:
    """Test description"""
    
    def test_your_scenario(self, client, clean_database):
        """
        Test specific scenario
        
        Steps:
        1. Setup test data
        2. Execute operation
        3. Verify results
        4. Cleanup
        """
        # 1. Setup
        data = {"key": "value"}
        
        # 2. Execute
        response = client.post("/api/v1/endpoint", json=data)
        
        # 3. Verify
        assert response.status_code == 201
        result = response.json()
        assert result["key"] == "value"
        
        # 4. Cleanup (if needed)
        client.delete(f"/api/v1/endpoint/{result['id']}")
```

### Best Practices

1. **Use Descriptive Names**
   ```python
   # ✅ Good
   def test_backtest_with_invalid_date_range()
   
   # ❌ Bad
   def test_backtest1()
   ```

2. **Document Test Steps**
   ```python
   def test_feature(self, client):
       """
       Steps:
       1. Create resource A
       2. Update resource A
       3. Verify changes
       """
   ```

3. **Clean Up Resources**
   ```python
   # Always cleanup created resources
   strategy_id = response.json()["id"]
   yield strategy_id
   client.delete(f"/api/v1/strategies/{strategy_id}")
   ```

4. **Use Fixtures for Common Setup**
   ```python
   @pytest.fixture
   def created_strategy(client):
       """Fixture for tests needing a strategy"""
       # Create
       response = client.post(...)
       strategy_id = response.json()["id"]
       
       yield strategy_id
       
       # Cleanup
       client.delete(f"/api/v1/strategies/{strategy_id}")
   ```

5. **Test Both Success and Failure**
   ```python
   def test_success_case(self, client):
       response = client.post("/api/v1/endpoint", json=valid_data)
       assert response.status_code == 201
   
   def test_failure_case(self, client):
       response = client.post("/api/v1/endpoint", json=invalid_data)
       assert response.status_code == 422
   ```

## Test Data

### Test Symbols
- **BTCUSDT**: Bitcoin (primary test asset)
- **ETHUSDT**: Ethereum (secondary)
- **BNBUSDT**: Binance Coin (tertiary)

### Test Timeframes
- **15m**: Fast backtests (< 5 seconds)
- **1h**: Standard backtests (< 10 seconds)
- **4h**: Medium backtests (< 15 seconds)
- **1d**: Slow backtests (< 30 seconds)

### Test Date Ranges
- **7 days**: Quick validation
- **30 days**: Standard testing
- **90 days**: Comprehensive testing
- **365 days**: Performance benchmarks (marked as `@pytest.mark.slow`)

## Troubleshooting

### Test Environment Not Ready

**Error:**
```
❌ Test environment check failed:
   - PostgreSQL not available
```

**Fix:**
```bash
# Start test services
docker-compose -f docker-compose.test.yml up -d

# Verify
docker ps
```

### Database Connection Failed

**Error:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Fix:**
```bash
# Check PostgreSQL is running
psql -h localhost -U postgres -c "SELECT 1"

# Check TEST_DATABASE_URL
echo $TEST_DATABASE_URL
export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/bybit_test"
```

### Redis Connection Failed

**Error:**
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Fix:**
```bash
# Check Redis is running
redis-cli ping

# Check REDIS_URL
echo $REDIS_URL
export REDIS_URL="redis://localhost:6379"
```

### Tests Hanging

**Symptoms:** Tests start but never complete

**Possible Causes:**
1. Backtest not completing (check background tasks)
2. Database deadlock (use `clean_database` fixture)
3. Redis key conflicts (flush test DB: `redis-cli -n 1 FLUSHDB`)

**Fix:**
```bash
# Stop hanging tests
pytest --timeout=60 tests/e2e/

# Debug specific test
pytest tests/e2e/test_full_workflow.py::test_name -v -s
```

### Port Conflicts

**Error:**
```
Address already in use: 8000
```

**Fix:**
```bash
# Find process using port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process or use different port
export API_PORT=8001
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: bybit_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run E2E tests
        env:
          TEST_DATABASE_URL: postgresql://postgres:postgres@localhost:5432/bybit_test
          REDIS_URL: redis://localhost:6379
        run: |
          pytest tests/e2e/ -v --cov=backend --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          flags: e2e-tests
```

## Performance Benchmarks

Expected test execution times:

| Test Suite | Tests | Time | Notes |
|------------|-------|------|-------|
| test_full_workflow.py (fast) | 4 | ~30s | Excludes slow tests |
| test_full_workflow.py (all) | 5 | ~90s | Includes performance tests |
| test_error_handling.py | 20+ | ~15s | Fast validation tests |
| **Total E2E Suite** | **25+** | **~45s** | Without slow tests |
| **Total E2E Suite (full)** | **25+** | **~2m** | With slow tests |

## Maintenance

### Updating Test Data

When adding new endpoints or features:

1. Add test fixtures to `conftest.py`
2. Create test cases in appropriate file
3. Update this README with new test categories
4. Run full test suite to verify

### Database Schema Changes

After Alembic migrations:

```bash
# Recreate test database
dropdb bybit_test
createdb bybit_test

# Run migrations
alembic upgrade head

# Verify tests
pytest tests/e2e/ -v
```

### Periodic Maintenance

**Weekly:**
- Review test execution times (flag slow tests)
- Check for flaky tests (intermittent failures)
- Update test data (if using real market data)

**Monthly:**
- Review coverage gaps (add new E2E tests)
- Benchmark performance (ensure tests stay fast)
- Update dependencies (pytest, pytest-asyncio, etc.)

## Resources

- **FastAPI Testing Docs**: https://fastapi.tiangolo.com/tutorial/testing/
- **pytest Documentation**: https://docs.pytest.org/
- **pytest-asyncio**: https://pytest-asyncio.readthedocs.io/
- **TestClient Reference**: https://www.starlette.io/testclient/

## Support

For issues with E2E tests:

1. Check test environment (run `pytest tests/e2e/conftest.py --collect-only`)
2. Review logs (use `pytest -v -s` for verbose output)
3. Verify services are running (`docker ps`)
4. Check database connectivity (`psql -h localhost -U postgres`)
5. Consult troubleshooting section above

---

**Last Updated**: 2024-01-09  
**Coverage Target**: 70%+ for critical user workflows  
**Test Count**: 25+ E2E tests across 2 files
