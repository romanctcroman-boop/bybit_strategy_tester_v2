"""
Optimizer Exceptions

Custom exceptions for GPU and Fast optimizers.
Provides clear error messages and proper error handling.
"""

from typing import Any


class OptimizerError(Exception):
    """Base exception for all optimizer errors."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        self.message = message
        self.details = details or {}
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self) -> str:
        result = self.message
        if self.details:
            result += f" | Details: {self.details}"
        if self.original_error:
            result += f" | Original: {type(self.original_error).__name__}: {self.original_error}"
        return result


class GPUNotAvailableError(OptimizerError):
    """Raised when GPU is required but not available."""

    def __init__(
        self,
        message: str = "GPU not available. Install CuPy with CUDA support.",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)


class CUDAError(OptimizerError):
    """Raised when a CUDA operation fails."""

    def __init__(
        self,
        message: str,
        cuda_error: str | None = None,
        device_id: int | None = None,
    ):
        details = {}
        if cuda_error:
            details["cuda_error"] = cuda_error
        if device_id is not None:
            details["device_id"] = device_id
        super().__init__(message, details)


class GPUMemoryError(OptimizerError):
    """Raised when GPU runs out of memory."""

    def __init__(
        self,
        message: str = "GPU out of memory",
        required_mb: float | None = None,
        available_mb: float | None = None,
    ):
        details = {}
        if required_mb is not None:
            details["required_mb"] = required_mb
        if available_mb is not None:
            details["available_mb"] = available_mb
        super().__init__(message, details)


class ParameterGridError(OptimizerError):
    """Raised when parameter grid is invalid."""

    def __init__(
        self,
        message: str,
        param_name: str | None = None,
        param_value: Any | None = None,
        valid_range: tuple | None = None,
    ):
        details = {}
        if param_name:
            details["param_name"] = param_name
        if param_value is not None:
            details["param_value"] = param_value
        if valid_range:
            details["valid_range"] = valid_range
        super().__init__(message, details)


class GridSizeExceededError(OptimizerError):
    """Raised when parameter grid is too large."""

    def __init__(
        self,
        actual_size: int,
        max_size: int,
        message: str | None = None,
    ):
        if message is None:
            message = f"Grid size {actual_size:,} exceeds maximum {max_size:,}"
        details = {
            "actual_size": actual_size,
            "max_size": max_size,
        }
        super().__init__(message, details)


class DataValidationError(OptimizerError):
    """Raised when input data is invalid."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        expected: str | None = None,
        actual: str | None = None,
    ):
        details = {}
        if field:
            details["field"] = field
        if expected:
            details["expected"] = expected
        if actual:
            details["actual"] = actual
        super().__init__(message, details)


class InsufficientDataError(DataValidationError):
    """Raised when there's not enough data for optimization."""

    def __init__(
        self,
        required_bars: int,
        actual_bars: int,
        message: str | None = None,
    ):
        if message is None:
            message = f"Insufficient data: need {required_bars} bars, got {actual_bars}"
        super().__init__(
            message,
            field="bars",
            expected=str(required_bars),
            actual=str(actual_bars),
        )


class OptimizationTimeoutError(OptimizerError):
    """Raised when optimization exceeds time limit."""

    def __init__(
        self,
        timeout_seconds: float,
        elapsed_seconds: float,
        combinations_completed: int | None = None,
        total_combinations: int | None = None,
    ):
        message = f"Optimization timed out after {elapsed_seconds:.1f}s (limit: {timeout_seconds}s)"
        details = {
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": elapsed_seconds,
        }
        if combinations_completed is not None:
            details["combinations_completed"] = combinations_completed
        if total_combinations is not None:
            details["total_combinations"] = total_combinations
            if combinations_completed:
                details["progress_pct"] = round(
                    100 * combinations_completed / total_combinations, 1
                )
        super().__init__(message, details)


class NumbaCompilationError(OptimizerError):
    """Raised when Numba JIT compilation fails."""

    def __init__(
        self,
        function_name: str,
        error: Exception,
    ):
        message = f"Numba compilation failed for '{function_name}'"
        super().__init__(message, {"function": function_name}, error)


class WorkerError(OptimizerError):
    """Raised when a parallel worker fails."""

    def __init__(
        self,
        worker_id: int,
        error: Exception,
        task_info: dict[str, Any] | None = None,
    ):
        message = f"Worker {worker_id} failed"
        details = {"worker_id": worker_id}
        if task_info:
            details["task_info"] = task_info
        super().__init__(message, details, error)


class SharedMemoryError(OptimizerError):
    """Raised when shared memory operations fail."""

    def __init__(
        self,
        operation: str,
        error: Exception,
        memory_name: str | None = None,
    ):
        message = f"Shared memory {operation} failed"
        details = {"operation": operation}
        if memory_name:
            details["memory_name"] = memory_name
        super().__init__(message, details, error)


# Helper functions for error handling


def handle_gpu_error(func):
    """Decorator to handle GPU errors gracefully."""
    from functools import wraps

    from loguru import logger

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except GPUMemoryError:
            raise
        except GPUNotAvailableError:
            raise
        except Exception as e:
            error_str = str(e).lower()
            if "out of memory" in error_str or "cuda" in error_str:
                logger.error(f"GPU error in {func.__name__}: {e}")
                raise CUDAError(
                    f"CUDA error in {func.__name__}",
                    cuda_error=str(e),
                ) from e
            raise

    return wrapper


def validate_parameter_grid(
    param_ranges: dict[str, Any],
    max_combinations: int = 50_000_000,
) -> int:
    """
    Validate parameter grid and return total combinations.

    Args:
        param_ranges: Dictionary of parameter names to value ranges
        max_combinations: Maximum allowed combinations

    Returns:
        Total number of combinations

    Raises:
        ParameterGridError: If any parameter is invalid
        GridSizeExceededError: If grid is too large
    """
    if not param_ranges:
        raise ParameterGridError("Empty parameter grid")

    total = 1
    for name, values in param_ranges.items():
        if not isinstance(values, (list, tuple, range)):
            raise ParameterGridError(
                f"Parameter '{name}' must be a list, tuple, or range",
                param_name=name,
                param_value=type(values).__name__,
            )

        if len(values) == 0:
            raise ParameterGridError(
                f"Parameter '{name}' has no values",
                param_name=name,
            )

        total *= len(values)

        if total > max_combinations:
            raise GridSizeExceededError(total, max_combinations)

    return total


def validate_price_data(
    data: dict[str, Any],
    min_bars: int = 100,
) -> None:
    """
    Validate price data for optimization.

    Args:
        data: Dictionary with OHLCV data
        min_bars: Minimum required bars

    Raises:
        DataValidationError: If data is invalid
        InsufficientDataError: If not enough data
    """
    required_fields = ["open", "high", "low", "close"]

    for field in required_fields:
        if field not in data:
            raise DataValidationError(
                f"Missing required field: {field}",
                field=field,
            )

        if data[field] is None:
            raise DataValidationError(
                f"Field '{field}' is None",
                field=field,
            )

    # Check length
    close_len = len(data["close"])
    if close_len < min_bars:
        raise InsufficientDataError(min_bars, close_len)

    # Check all arrays have same length
    for field in required_fields:
        if len(data[field]) != close_len:
            raise DataValidationError(
                f"Field '{field}' has different length",
                field=field,
                expected=str(close_len),
                actual=str(len(data[field])),
            )
