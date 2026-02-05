"""
Tests for Optimizer Exceptions and Error Handling

Tests custom exceptions and validation functions.
"""

import numpy as np
import pytest

from backend.backtesting.optimizer_exceptions import (
    CUDAError,
    DataValidationError,
    GPUMemoryError,
    GPUNotAvailableError,
    GridSizeExceededError,
    InsufficientDataError,
    NumbaCompilationError,
    OptimizationTimeoutError,
    OptimizerError,
    ParameterGridError,
    SharedMemoryError,
    WorkerError,
    validate_parameter_grid,
    validate_price_data,
)


class TestOptimizerExceptions:
    """Test custom exception classes."""

    def test_base_exception(self):
        """Test base OptimizerError."""
        error = OptimizerError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {}
        assert error.original_error is None

    def test_exception_with_details(self):
        """Test exception with details."""
        error = OptimizerError(
            "Test error",
            details={"key": "value", "count": 42},
        )
        assert "key" in str(error)
        assert "value" in str(error)
        assert error.details["count"] == 42

    def test_exception_with_original_error(self):
        """Test exception wrapping another exception."""
        original = ValueError("Original error")
        error = OptimizerError(
            "Wrapped error",
            original_error=original,
        )
        assert "ValueError" in str(error)
        assert "Original error" in str(error)
        assert error.original_error is original

    def test_gpu_not_available_error(self):
        """Test GPUNotAvailableError."""
        error = GPUNotAvailableError()
        assert "GPU not available" in str(error)

        custom_error = GPUNotAvailableError(
            "Custom GPU error",
            details={"reason": "CUDA not found"},
        )
        assert "Custom GPU error" in str(custom_error)

    def test_cuda_error(self):
        """Test CUDAError."""
        error = CUDAError(
            "CUDA operation failed",
            cuda_error="cudaErrorNoDevice",
            device_id=0,
        )
        assert "CUDA operation failed" in str(error)
        assert error.details["cuda_error"] == "cudaErrorNoDevice"
        assert error.details["device_id"] == 0

    def test_gpu_memory_error(self):
        """Test GPUMemoryError."""
        error = GPUMemoryError(
            required_mb=1024.0,
            available_mb=512.0,
        )
        assert "GPU out of memory" in str(error)
        assert error.details["required_mb"] == 1024.0
        assert error.details["available_mb"] == 512.0

    def test_parameter_grid_error(self):
        """Test ParameterGridError."""
        error = ParameterGridError(
            "Invalid parameter",
            param_name="rsi_period",
            param_value=-5,
            valid_range=(1, 100),
        )
        assert "Invalid parameter" in str(error)
        assert error.details["param_name"] == "rsi_period"
        assert error.details["valid_range"] == (1, 100)

    def test_grid_size_exceeded_error(self):
        """Test GridSizeExceededError."""
        error = GridSizeExceededError(
            actual_size=100_000_000,
            max_size=50_000_000,
        )
        assert "100,000,000" in str(error)
        assert "50,000,000" in str(error)
        assert error.details["actual_size"] == 100_000_000

    def test_insufficient_data_error(self):
        """Test InsufficientDataError."""
        error = InsufficientDataError(
            required_bars=1000,
            actual_bars=50,
        )
        assert "Insufficient data" in str(error)
        assert "1000" in str(error)
        assert "50" in str(error)

    def test_optimization_timeout_error(self):
        """Test OptimizationTimeoutError."""
        error = OptimizationTimeoutError(
            timeout_seconds=300.0,
            elapsed_seconds=305.5,
            combinations_completed=50000,
            total_combinations=100000,
        )
        assert "timed out" in str(error)
        assert error.details["progress_pct"] == 50.0

    def test_numba_compilation_error(self):
        """Test NumbaCompilationError."""
        original = SyntaxError("Invalid syntax")
        error = NumbaCompilationError(
            function_name="calculate_rsi",
            error=original,
        )
        assert "Numba compilation failed" in str(error)
        assert "calculate_rsi" in str(error)
        assert error.original_error is original

    def test_worker_error(self):
        """Test WorkerError."""
        original = RuntimeError("Worker crashed")
        error = WorkerError(
            worker_id=3,
            error=original,
            task_info={"batch": 5, "params": {"period": 14}},
        )
        assert "Worker 3" in str(error)
        assert error.details["worker_id"] == 3
        assert error.details["task_info"]["batch"] == 5

    def test_shared_memory_error(self):
        """Test SharedMemoryError."""
        original = PermissionError("Access denied")
        error = SharedMemoryError(
            operation="create",
            error=original,
            memory_name="price_data_shm",
        )
        assert "Shared memory create failed" in str(error)
        assert error.details["memory_name"] == "price_data_shm"


class TestValidateParameterGrid:
    """Test validate_parameter_grid function."""

    def test_valid_grid(self):
        """Test valid parameter grid."""
        param_ranges = {
            "period": [10, 14, 21],
            "overbought": [70, 75, 80],
            "oversold": [20, 25, 30],
        }
        total = validate_parameter_grid(param_ranges)
        assert total == 27  # 3 * 3 * 3

    def test_empty_grid(self):
        """Test empty parameter grid raises error."""
        with pytest.raises(ParameterGridError) as exc_info:
            validate_parameter_grid({})
        assert "Empty parameter grid" in str(exc_info.value)

    def test_invalid_parameter_type(self):
        """Test invalid parameter type raises error."""
        param_ranges = {
            "period": 14,  # Should be a list
        }
        with pytest.raises(ParameterGridError) as exc_info:
            validate_parameter_grid(param_ranges)
        assert "must be a list" in str(exc_info.value)

    def test_empty_parameter_values(self):
        """Test empty parameter values raises error."""
        param_ranges = {
            "period": [],
        }
        with pytest.raises(ParameterGridError) as exc_info:
            validate_parameter_grid(param_ranges)
        assert "has no values" in str(exc_info.value)

    def test_grid_too_large(self):
        """Test grid exceeding max size raises error."""
        param_ranges = {
            "p1": list(range(100)),
            "p2": list(range(100)),
            "p3": list(range(100)),
            "p4": list(range(100)),
        }
        # 100^4 = 100,000,000 > 50,000,000 default max
        with pytest.raises(GridSizeExceededError) as exc_info:
            validate_parameter_grid(param_ranges)
        assert exc_info.value.details["max_size"] == 50_000_000

    def test_custom_max_combinations(self):
        """Test custom max combinations limit."""
        param_ranges = {
            "p1": list(range(10)),
            "p2": list(range(10)),
        }
        # 10 * 10 = 100, but max is 50
        with pytest.raises(GridSizeExceededError):
            validate_parameter_grid(param_ranges, max_combinations=50)

        # Should pass with higher limit
        total = validate_parameter_grid(param_ranges, max_combinations=1000)
        assert total == 100

    def test_range_parameter(self):
        """Test range as parameter values."""
        param_ranges = {
            "period": range(10, 20),  # Python range
        }
        total = validate_parameter_grid(param_ranges)
        assert total == 10


class TestValidatePriceData:
    """Test validate_price_data function."""

    def test_valid_data(self):
        """Test valid price data passes validation."""
        data = {
            "open": np.random.randn(1000),
            "high": np.random.randn(1000),
            "low": np.random.randn(1000),
            "close": np.random.randn(1000),
            "volume": np.random.randn(1000),
        }
        # Should not raise
        validate_price_data(data)

    def test_missing_field(self):
        """Test missing required field raises error."""
        data = {
            "open": np.random.randn(1000),
            "high": np.random.randn(1000),
            "low": np.random.randn(1000),
            # Missing 'close'
        }
        with pytest.raises(DataValidationError) as exc_info:
            validate_price_data(data)
        assert "close" in str(exc_info.value)

    def test_none_field(self):
        """Test None field raises error."""
        data = {
            "open": np.random.randn(1000),
            "high": np.random.randn(1000),
            "low": np.random.randn(1000),
            "close": None,
        }
        with pytest.raises(DataValidationError) as exc_info:
            validate_price_data(data)
        assert "is None" in str(exc_info.value)

    def test_insufficient_data(self):
        """Test insufficient data raises error."""
        data = {
            "open": np.random.randn(50),
            "high": np.random.randn(50),
            "low": np.random.randn(50),
            "close": np.random.randn(50),
        }
        with pytest.raises(InsufficientDataError) as exc_info:
            validate_price_data(data, min_bars=100)
        assert exc_info.value.details["expected"] == "100"
        assert exc_info.value.details["actual"] == "50"

    def test_mismatched_lengths(self):
        """Test mismatched array lengths raises error."""
        data = {
            "open": np.random.randn(1000),
            "high": np.random.randn(1000),
            "low": np.random.randn(999),  # Different length
            "close": np.random.randn(1000),
        }
        with pytest.raises(DataValidationError) as exc_info:
            validate_price_data(data)
        assert "different length" in str(exc_info.value)

    def test_custom_min_bars(self):
        """Test custom min_bars parameter."""
        data = {
            "open": np.random.randn(50),
            "high": np.random.randn(50),
            "low": np.random.randn(50),
            "close": np.random.randn(50),
        }
        # Should pass with lower min_bars
        validate_price_data(data, min_bars=50)

        # Should fail with higher min_bars
        with pytest.raises(InsufficientDataError):
            validate_price_data(data, min_bars=100)


class TestExceptionInheritance:
    """Test exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_base(self):
        """Test all custom exceptions inherit from OptimizerError."""
        exceptions = [
            GPUNotAvailableError(),
            CUDAError("test"),
            GPUMemoryError(),
            ParameterGridError("test"),
            GridSizeExceededError(100, 50),
            DataValidationError("test"),
            InsufficientDataError(100, 50),
            OptimizationTimeoutError(60, 65),
            NumbaCompilationError("func", ValueError()),
            WorkerError(0, ValueError()),
            SharedMemoryError("create", ValueError()),
        ]

        for exc in exceptions:
            assert isinstance(exc, OptimizerError)
            assert isinstance(exc, Exception)

    def test_data_validation_inheritance(self):
        """Test InsufficientDataError inherits from DataValidationError."""
        error = InsufficientDataError(100, 50)
        assert isinstance(error, DataValidationError)
        assert isinstance(error, OptimizerError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
