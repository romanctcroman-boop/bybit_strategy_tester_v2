"""Tests for GPU optimizer (AUDIT_PROJECT_EXTENDED)."""


def test_gpu_optimizer_module_imports():
    """Module imports without error."""
    from backend.backtesting import gpu_optimizer

    assert hasattr(gpu_optimizer, "is_gpu_available")


def test_is_gpu_available_returns_bool():
    """is_gpu_available returns bool (True if CUDA, False otherwise)."""
    from backend.backtesting.gpu_optimizer import is_gpu_available

    result = is_gpu_available()
    assert isinstance(result, bool)


def test_gpu_optimizer_grid_class_exists():
    """GPUGridOptimizer class exists and has optimize method."""
    from backend.backtesting.gpu_optimizer import GPUGridOptimizer

    assert hasattr(GPUGridOptimizer, "optimize")
