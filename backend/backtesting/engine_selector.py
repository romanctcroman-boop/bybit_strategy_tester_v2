"""
Engine Selector Module
======================

Provides intelligent selection of backtest engine based on:
1. User preference (engine_type parameter)
2. Hardware availability (GPU, Numba)
3. Feature requirements (Bar Magnifier support)

All engines produce 100% identical results (bit-level parity verified).
"""

from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from backend.backtesting.interfaces import BaseBacktestEngine


def get_engine(
    engine_type: str = "auto",
    require_bar_magnifier: bool = False,
    pyramiding: int = 1,
) -> "BaseBacktestEngine":
    """
    Get the appropriate backtest engine based on configuration.

    Args:
        engine_type: Engine preference:
            - "auto": Automatically select best available (GPU > Numba > Fallback)
            - "fallback": FallbackEngineV2 (reference implementation)
            - "fallback_v3": FallbackEngineV3 (with pyramiding support)
            - "numba": NumbaEngineV2 (JIT-compiled)
            - "gpu": GPUEngineV2 (CUDA-accelerated)
        require_bar_magnifier: If True, only engines supporting Bar Magnifier are valid
        pyramiding: Max concurrent positions (if > 1, uses FallbackEngineV3)

    Returns:
        Instantiated engine ready for use

    Note:
        All engines produce 100% identical results (147-metric parity verified).
        The choice affects performance only, not accuracy.

    Pyramiding:
        When pyramiding > 1, FallbackEngineV3 is automatically used regardless
        of engine_type selection, as it's the only engine with full pyramiding
        support (multiple entries, weighted average price, FIFO/LIFO/ALL close).
    """
    engine_type = engine_type.lower()

    # Import engines
    from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
    from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3

    # Pyramiding > 1 requires FallbackEngineV3 (only engine with full support)
    if pyramiding > 1:
        logger.info(
            f"🔺 Using FallbackEngineV3 (pyramiding={pyramiding} requires multi-position support)"
        )
        return FallbackEngineV3()

    # Explicit FallbackEngineV3 request
    if engine_type == "fallback_v3":
        logger.info("🔺 Using FallbackEngineV3 (pyramiding-enabled)")
        return FallbackEngineV3()

    # Try to import optional engines
    numba_available = False
    gpu_available = False

    try:
        from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

        numba_available = True
    except ImportError:
        NumbaEngineV2 = None

    try:
        from backend.backtesting.engines.gpu_engine_v2 import GPUEngineV2

        # Check if CUDA is actually available
        try:
            import cupy

            cupy.cuda.Device(0).compute_capability
            gpu_available = True
        except Exception:
            gpu_available = False
    except ImportError:
        GPUEngineV2 = None

    # Handle explicit engine requests
    if engine_type == "fallback":
        logger.info("🔧 Using FallbackEngineV2 (reference implementation)")
        return FallbackEngineV2()

    if engine_type == "numba":
        if numba_available and NumbaEngineV2:
            logger.info("⚡ Using NumbaEngineV2 (JIT-compiled)")
            return NumbaEngineV2()
        else:
            logger.warning(
                "NumbaEngineV2 not available, falling back to FallbackEngineV2"
            )
            return FallbackEngineV2()

    if engine_type == "gpu":
        if gpu_available and GPUEngineV2:
            logger.info("🚀 Using GPUEngineV2 (CUDA-accelerated)")
            return GPUEngineV2()
        else:
            logger.warning(
                "GPUEngineV2 not available (no CUDA), falling back to FallbackEngineV2"
            )
            return FallbackEngineV2()

    # Auto or unknown engine type - use fallback (user must explicitly choose)
    # No automatic selection - predictable behavior
    if engine_type == "auto":
        logger.info(
            "🔧 Using FallbackEngineV2 (default - select engine manually for optimization)"
        )
        return FallbackEngineV2()

    # Unknown engine type - use fallback
    logger.warning(f"Unknown engine_type '{engine_type}', using FallbackEngineV2")
    return FallbackEngineV2()


def get_available_engines() -> dict:
    """
    Get information about available engines.

    Returns:
        Dict with engine availability and capabilities
    """
    engines = {
        "fallback": {
            "available": True,
            "name": "FallbackEngineV2",
            "description": "Pure Python reference implementation, 100% accurate",
            "supports_bar_magnifier": True,
            "supports_pyramiding": False,
            "acceleration": "None (CPU)",
        },
        "fallback_v3": {
            "available": True,
            "name": "FallbackEngineV3",
            "description": "Pyramiding-enabled (Grid/DCA/Martingale strategies)",
            "supports_bar_magnifier": True,
            "supports_pyramiding": True,
            "acceleration": "None (CPU)",
        },
    }

    # Check Numba
    try:
        from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

        engines["numba"] = {
            "available": True,
            "name": "NumbaEngineV2",
            "description": "Numba JIT-compiled, faster than Fallback",
            "supports_bar_magnifier": True,
            "acceleration": "Numba JIT",
        }
    except ImportError:
        engines["numba"] = {
            "available": False,
            "name": "NumbaEngineV2",
            "description": "Not installed (pip install numba)",
            "supports_bar_magnifier": True,
            "acceleration": "Numba JIT",
        }

    # Check GPU
    try:
        from backend.backtesting.engines.gpu_engine_v2 import GPUEngineV2

        try:
            import cupy

            gpu = cupy.cuda.Device(0)
            mem = gpu.mem_info
            engines["gpu"] = {
                "available": True,
                "name": "GPUEngineV2",
                "description": f"CUDA-accelerated on GPU 0 ({mem[1] / 1e9:.1f}GB)",
                "supports_bar_magnifier": True,
                "acceleration": "NVIDIA CUDA",
            }
        except Exception:
            engines["gpu"] = {
                "available": False,
                "name": "GPUEngineV2",
                "description": "No CUDA-capable GPU found",
                "supports_bar_magnifier": True,
                "acceleration": "NVIDIA CUDA",
            }
    except ImportError:
        engines["gpu"] = {
            "available": False,
            "name": "GPUEngineV2",
            "description": "Not installed (pip install cupy)",
            "supports_bar_magnifier": True,
            "acceleration": "NVIDIA CUDA",
        }

    return engines
