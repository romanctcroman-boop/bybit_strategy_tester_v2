---
name: Test Generation
description: "Write comprehensive tests following project testing patterns with proper fixtures and coverage."
---

# Test Generation Skill for Qwen

## Overview

Create comprehensive tests that follow project conventions, achieve high coverage, and catch regressions.

## Test Structure

### Test File Location

| Code Location | Test Location |
|---------------|---------------|
| `backend/backtesting/engine.py` | `tests/backend/backtesting/test_engine.py` |
| `backend/api/routers/backtests.py` | `tests/backend/api/routers/test_backtests.py` |
| `backend/services/data_service.py` | `tests/backend/services/test_data_service.py` |
| `backend/core/metrics_calculator.py` | `tests/backend/core/test_metrics_calculator.py` |

### Test File Template

```python
"""
[Test Subject] Tests

Tests for [module/component description].

Usage:
    pytest tests/path/to/test_file.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC
import pandas as pd
import numpy as np

from backend.module import FunctionUnderTest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_data() -> pd.DataFrame:
    """Create sample OHLCV DataFrame for testing."""
    dates = pd.date_range('2025-01-01', periods=100, freq='15min')
    return pd.DataFrame({
        'timestamp': dates,
        'open': np.random.uniform(100, 110, 100),
        'high': np.random.uniform(110, 120, 100),
        'low': np.random.uniform(90, 100, 100),
        'close': np.random.uniform(100, 110, 100),
        'volume': np.random.uniform(1000, 5000, 100),
    }).set_index('timestamp')


@pytest.fixture
def mock_config() -> dict:
    """Create mock configuration."""
    return {
        'param1': 'value1',
        'param2': 42,
        'enabled': True,
    }


@pytest.fixture
def instance_under_test(mock_config) -> FunctionUnderTest:
    """Create instance of class under test."""
    return FunctionUnderTest(mock_config)


# =============================================================================
# Unit Tests
# =============================================================================


class TestFunctionUnderTest:
    """Tests for [FunctionUnderTest]."""
    
    def test_success_case(self, sample_data):
        """Test successful execution with valid input."""
        # Arrange
        expected = expected_result
        
        # Act
        result = FunctionUnderTest.process(sample_data)
        
        # Assert
        assert result is not None
        assert isinstance(result, ExpectedType)
        assert result == expected
    
    def test_empty_input(self):
        """Test handling of empty input."""
        # Arrange
        empty_data = pd.DataFrame()
        
        # Act & Assert
        with pytest.raises(ValueError, match="Input cannot be empty"):
            FunctionUnderTest.process(empty_data)
    
    def test_missing_required_param(self, mock_config):
        """Test error when required parameter is missing."""
        # Arrange
        del mock_config['required_param']
        
        # Act & Assert
        with pytest.raises(KeyError):
            FunctionUnderTest(**mock_config)
    
    def test_boundary_condition(self, sample_data):
        """Test behavior at boundary values."""
        # Arrange
        boundary_data = sample_data.copy()
        boundary_data['close'] = 0.0  # Edge case
        
        # Act
        result = FunctionUnderTest.process(boundary_data)
        
        # Assert
        assert result is not None
        assert result.handled_gracefully is True
    
    @patch('backend.module.external_api_call')
    def test_with_mocked_dependency(self, mock_api, sample_data):
        """Test with external dependency mocked."""
        # Arrange
        mock_api.return_value = {'status': 'success', 'data': [...]}
        
        # Act
        result = FunctionUnderTest.fetch_and_process(sample_data)
        
        # Assert
        assert result.status == 'success'
        mock_api.assert_called_once()


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.integration
class TestIntegration:
    """Integration tests for [component]."""
    
    def test_full_workflow(self, sample_data, mock_config):
        """Test complete workflow from start to finish."""
        # Arrange
        component = FunctionUnderTest(mock_config)
        
        # Act
        result = component.run_full_workflow(sample_data)
        
        # Assert
        assert result.completed is True
        assert len(result.steps) == expected_steps
    
    def test_database_interaction(self, db_session):
        """Test database operations."""
        # Arrange
        test_entity = Entity(name='test', value=42)
        db_session.add(test_entity)
        db_session.commit()
        
        # Act
        result = db_session.query(Entity).filter_by(name='test').first()
        
        # Assert
        assert result is not None
        assert result.value == 42


# =============================================================================
# Property-Based Tests (if applicable)
# =============================================================================


@pytest.mark.slow
class TestProperties:
    """Property-based tests for invariants."""
    
    def test_output_length_matches_input(self, sample_data):
        """Output should have same length as input."""
        # Act
        result = FunctionUnderTest.transform(sample_data)
        
        # Assert
        assert len(result) == len(sample_data)
    
    def test_preserves_index(self, sample_data):
        """Transformation should preserve DataFrame index."""
        # Act
        result = FunctionUnderTest.transform(sample_data)
        
        # Assert
        pd.testing.assert_index_equal(result.index, sample_data.index)
    
    def test_idempotent(self, sample_data):
        """Applying twice should give same result as once."""
        # Act
        result1 = FunctionUnderTest.transform(sample_data)
        result2 = FunctionUnderTest.transform(result1)
        
        # Assert
        pd.testing.assert_frame_equal(result1, result2)
```

## Test Patterns

### AAA Pattern (Arrange-Act-Assert)

```python
def test_example():
    # Arrange - set up test data
    input_data = create_test_data()
    expected = expected_result
    
    # Act - call function under test
    result = function_under_test(input_data)
    
    # Assert - verify outcome
    assert result == expected
```

### Test Naming Convention

```python
def test_[method]_[scenario]_[expected_result]():
    """Clear description of what's being tested."""
    ...

# Examples:
def test_calculate_fee_premium_user_returns_discount():
def test_validate_input_empty_string_raises_value_error():
def test_process_data_with_nulls_handles_gracefully():
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input_value,expected", [
    (0, 0),
    (1, 1),
    (5, 120),
    (10, 3628800),
])
def test_factorial_parametrized(input_value, expected):
    """Test factorial function with multiple inputs."""
    result = factorial(input_value)
    assert result == expected
```

### Async Tests

```python
import pytest
import asyncio


@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    # Arrange
    expected = "result"
    
    # Act
    result = await async_function()
    
    # Assert
    assert result == expected
```

## Fixtures

### Common Fixtures (from conftest.py)

```python
# sample_ohlcv - standard OHLCV DataFrame
def test_with_ohlcv(sample_ohlcv):
    assert len(sample_ohlcv) > 0
    assert all(col in sample_ohlcv.columns for col in ['open', 'high', 'low', 'close'])

# mock_adapter - mocked Bybit adapter
def test_with_mock_adapter(mock_adapter):
    mock_adapter.get_klines.return_value = sample_data
    # Use in test

# db_session - in-memory SQLite session
def test_database(db_session):
    # Use for database tests
```

### Custom Fixtures

```python
@pytest.fixture
def complex_test_data():
    """Create complex test data with specific characteristics."""
    return {
        'normal_case': {...},
        'edge_case': {...},
        'error_case': {...},
    }


@pytest.fixture
def mock_external_service():
    """Mock external service with realistic responses."""
    with patch('backend.services.external_api') as mock:
        mock.return_value.fetch.return_value = {'status': 'ok'}
        yield mock
```

## Coverage Goals

### Minimum Coverage

| Component | Minimum Coverage |
|-----------|-----------------|
| Core logic | 90% |
| API routers | 85% |
| Services | 85% |
| Strategies | 95% |
| Utilities | 80% |

### Run Coverage

```powershell
# Full coverage report
pytest tests/ --cov=backend --cov-report=html

# Coverage for specific module
pytest tests/backend/module/ --cov=backend/module --cov-report=term-missing

# Check minimum coverage
pytest tests/ --cov=backend --cov-fail-under=80
```

## Test Checklist

Before committing tests:

- [ ] Test names are descriptive
- [ ] AAA pattern followed
- [ ] Edge cases covered
- [ ] Error conditions tested
- [ ] Mocks used for external dependencies
- [ ] Fixtures reusable
- [ ] No hardcoded paths/secrets
- [ ] Tests run independently
- [ ] Coverage meets goals

## Running Tests

```powershell
# All tests
pytest tests/ -v

# Specific test file
pytest tests/backend/module/test_file.py -v

# Specific test function
pytest tests/backend/module/test_file.py::test_specific_function -v

# Fast tests only (skip slow)
pytest tests/ -v -m "not slow"

# With coverage
pytest tests/ --cov=backend --cov-report=html

# Rerun failed tests
pytest tests/ --lf

# Stop on first failure
pytest tests/ -x
```

## Post-Test Actions

After writing tests:

1. **Run tests:**
   ```powershell
   pytest tests/path/to/test_file.py -v
   ```

2. **Check coverage:**
   ```powershell
   pytest tests/ --cov=backend/module --cov-report=term-missing
   ```

3. **Verify no lint errors:**
   ```powershell
   ruff check tests/ --fix
   ```

4. **Update test documentation:**
   - Add to `tests/README.md` if new test category
   - Update fixture documentation in `conftest.py`

5. **Commit:**
   ```bash
   git commit -m "test: add tests for [feature]"
   ```
