"""
backend.backtesting.gpu — GPU-accelerated optimization package.

Public API (backward-compatible with gpu_optimizer.py):
    GPU_AVAILABLE       — bool, set after first is_gpu_available() call
    GPU_NAME            — str, human-readable GPU name
    GPUOptimizationResult
    GPUGridOptimizer
    run_gpu_optimization
"""

from backend.backtesting.gpu.device import GPU_AVAILABLE, GPU_NAME, is_gpu_available
from backend.backtesting.gpu.optimizer import GPUGridOptimizer, run_gpu_optimization
from backend.backtesting.gpu.result import GPUOptimizationResult

__all__ = [
    "GPU_AVAILABLE",
    "GPU_NAME",
    "GPUGridOptimizer",
    "GPUOptimizationResult",
    "is_gpu_available",
    "run_gpu_optimization",
]
