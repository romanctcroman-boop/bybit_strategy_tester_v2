"""
GPU-Accelerated Grid Optimizer - compatibility shim.

The implementation has been split into backend.backtesting.gpu package:
  - device.py     - GPU init, CuPy lazy loading
  - kernels.py    - Numba JIT functions (RSI, backtest)
  - pool.py       - WarmProcessPool, shared memory workers
  - parallel.py   - per-period parallel worker, GPU RSI/backtest helpers
  - result.py     - GPUOptimizationResult dataclass
  - optimizer.py  - GPUGridOptimizer class + run_gpu_optimization()

All public names are re-exported here for backward compatibility.
Existing code:
    from backend.backtesting.gpu_optimizer import GPUGridOptimizer, GPU_AVAILABLE
continues to work without changes.

Performance targets (unchanged):
- 100K combinations: ~5-10 seconds
- 1M combinations: ~30-60 seconds
- 10M combinations: ~5-10 minutes
"""

# Re-export entire public API from the new package
from backend.backtesting.gpu import (  # noqa: F401
    GPU_AVAILABLE,
    GPU_NAME,
    GPUGridOptimizer,
    GPUOptimizationResult,
    is_gpu_available,
    run_gpu_optimization,
)
from backend.backtesting.gpu.kernels import (  # noqa: F401
    JOBLIB_AVAILABLE,
    MAX_COMBINATIONS,
    N_WORKERS,
    NUMBA_AVAILABLE,
)
from backend.backtesting.gpu.pool import WarmProcessPool, _cleanup_shared_memory  # noqa: F401
