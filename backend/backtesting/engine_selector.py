"""
Engine Selector Module
======================

ARCHITECTURE (2026-01-30): Два основных движка — простая логика
---------------------------------------------------------------

::

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    TWO ENGINE ARCHITECTURE                           │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │   ┌─────────────────────────────────────────────────────────────┐   │
    │   │  FallbackEngineV4 — ЭТАЛОН (Single Backtest)                │   │
    │   │  - Все фичи: pyramiding, multi-TP, ATR, trailing, DCA       │   │
    │   │  - Скорость: 1x (Python)                                    │   │
    │   │  - Роль: ОДИНОЧНЫЙ БЭКТЕСТ (точность важнее скорости)       │   │
    │   └─────────────────────────────────────────────────────────────┘   │
    │                              ▲                                      │
    │                              │ паритет 100%                         │
    │                              ▼                                      │
    │   ┌─────────────────────────────────────────────────────────────┐   │
    │   │  NumbaEngineV2 — БЫСТРЫЙ (Optimization)                     │   │
    │   │  - 100% паритет с FallbackEngineV4 (все V4 фичи)            │   │
    │   │  - Скорость: ~20-40x (JIT compiled)                         │   │
    │   │  - Роль: ОПТИМИЗАЦИЯ (скорость важна для grid search)       │   │
    │   └─────────────────────────────────────────────────────────────┘   │
    │                                                                     │
    │   DEPRECATED: V2/V3/GPU — только для обратной совместимости         │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

Engine Selection Logic (2026-01-30)
-----------------------------------
- "single" / "fallback" / "auto" → FallbackEngineV4 (одиночный бэктест)
- "optimization" / "numba"       → NumbaEngineV2 (оптимизация, 20-40x)
- "gpu"                          → GPUEngineV2 (deprecated)

Feature Matrix (100% Parity!)
-----------------------------
::

    ┌─────────────────────┬────────────┬────────┐
    │ Feature             │ Fallback   │ Numba  │
    │                     │ (V4)       │ (V4)   │
    ├─────────────────────┼────────────┼────────┤
    │ Basic SL/TP         │     ✓      │   ✓    │
    │ Bar Magnifier       │     ✓      │   ✓    │
    │ Pyramiding          │     ✓      │   ✓    │
    │ Multi-level TP      │     ✓      │   ✓    │
    │ ATR-based SL/TP     │     ✓      │   ✓    │
    │ Trailing Stop       │     ✓      │   ✓    │
    │ DCA (Safety Orders) │     ✓      │   ✓    │
    │ Breakeven Stop      │     ✓      │   ✓    │  <- NEW!
    │ Time-based Exit     │     ✓      │   ✓    │  <- NEW!
    │ Re-entry Rules      │     ✓      │   ✓    │  <- NEW!
    │ Market Filters      │     ✓      │   ✓    │  <- NEW!
    │ Funding Rate        │     ✓      │   ✓    │  <- NEW!
    │ Adv. Slippage       │     ✓      │   ✓    │  <- FIXED!
    │ FIFO/LIFO close     │     ✓      │   ✓    │  <- FIXED!
    │ JIT Acceleration    │     -      │   ✓    │
    └─────────────────────┴────────────┴────────┘

Numba V4 = 100% паритет с Fallback по функционалу!
"""

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from backend.backtesting.interfaces import BaseBacktestEngine


def get_engine(
    engine_type: str = "auto",
    require_bar_magnifier: bool = False,
    pyramiding: int = 1,
    strategy_type: str | None = None,
    max_entries: int | None = None,
    dca_enabled: bool = False,
) -> "BaseBacktestEngine":
    """
    Get the appropriate backtest engine based on configuration.

    Args:
        engine_type: Engine preference:
            - "auto" / "single" / "fallback" / "fallback_v4" / "v4":
                  FallbackEngineV4 — эталон, одиночный бэктест
            - "optimization" / "numba":
                  NumbaEngineV2 — JIT-compiled, ~20-40x быстрее, 100% паритет с V4
            - "dca" / "grid" / "dca_grid":
                  DCAEngine — специализированный движок для DCA/Grid стратегий
            - "fallback_v3" / "fallback_v2" / "gpu":
                  ⚠️ DEPRECATED — только для обратной совместимости
        require_bar_magnifier: Зарезервировано (все актуальные движки поддерживают Bar Magnifier)
        pyramiding: Максимум одновременных позиций (передаётся в движок)
        strategy_type: Тип стратегии ('dca', 'grid', 'martingale') — для валидации
        max_entries: Максимум входов для DCA/Grid — для валидации pyramiding
        dca_enabled: Если True, принудительно использует DCAEngine

    Returns:
        Инстанс движка, готового к запуску

    Note:
        FallbackEngineV4 и NumbaEngineV2 дают 100% идентичные результаты.
        Выбор влияет только на скорость, не на точность.
    """
    engine_type = engine_type.lower()

    # Import engines
    # V4 = основной эталон (FallbackEngine)
    # V2/V3 = deprecated, для обратной совместимости
    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4

    # ==========================================================================
    # DCA ENABLED AUTO-SELECTION
    # ==========================================================================
    # When dca_enabled=True, automatically use DCAEngine regardless of engine_type
    if dca_enabled:
        from backend.backtesting.engines.dca_engine import DCAEngine

        logger.info("🎯 DCA enabled - using DCAEngine for DCA/Grid/Martingale strategy")
        return DCAEngine()

    # DCA/Grid/Martingale validation: these strategies require pyramiding > 1
    accumulation_strategies = {"dca", "grid", "martingale", "dca_long", "dca_short"}
    if strategy_type and strategy_type.lower() in accumulation_strategies:
        if pyramiding <= 1:
            logger.warning(
                f"Strategy '{strategy_type}' requires pyramiding > 1 for accumulation. "
                f"Current pyramiding={pyramiding}. DCA/Grid accumulation will NOT work!"
            )
        elif max_entries and pyramiding < max_entries:
            logger.warning(
                f"Strategy '{strategy_type}' has max_entries={max_entries} but pyramiding={pyramiding}. "
                f"Some entries will be skipped. Consider setting pyramiding >= {max_entries}."
            )
        else:
            logger.info(f"Strategy '{strategy_type}' with pyramiding={pyramiding} - accumulation enabled")

    # ==========================================================================
    # SIMPLIFIED ENGINE SELECTION (2026-01-30)
    # ==========================================================================
    # Two engines only:
    # 1. FallbackEngineV4 - for SINGLE backtest (accuracy)
    # 2. NumbaEngineV2    - for OPTIMIZATION (speed, 100% parity with V4)
    # ==========================================================================

    # Import Numba engine (if available)
    numba_available = False
    NumbaEngineV2 = None  # type: ignore[misc]

    try:
        from backend.backtesting.engines.numba_engine_v2 import (
            NUMBA_AVAILABLE,
            NumbaEngineV2,
        )

        numba_available = NUMBA_AVAILABLE
    except ImportError:
        pass

    # === OPTIMIZATION MODE: Use Numba (fast, 100% parity) ===
    if engine_type in ("optimization", "numba"):
        if numba_available and NumbaEngineV2 is not None:
            logger.info(
                "🚀 Using NumbaEngineV2 for OPTIMIZATION (JIT-compiled, ~20-40x faster, 100% parity with FallbackV4)"
            )
            return NumbaEngineV2()
        else:
            logger.warning("NumbaEngineV2 not available, falling back to FallbackEngineV4")
            return FallbackEngineV4()

    # === SINGLE BACKTEST MODE: Use FallbackEngineV4 (reference, accurate) ===
    if engine_type in ("single", "fallback", "fallback_v4", "v4", "auto"):
        logger.info("🎯 Using FallbackEngineV4 for SINGLE BACKTEST (reference implementation)")
        return FallbackEngineV4()

    # === DEPRECATED ENGINES (backward compatibility) ===
    if engine_type == "fallback_v3":
        from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3

        logger.warning("⚠️ FallbackEngineV3 is DEPRECATED. Use 'single' or 'fallback' instead.")
        return FallbackEngineV3()

    if engine_type == "fallback_v2":
        from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2

        logger.warning("⚠️ FallbackEngineV2 is DEPRECATED. Use 'single' or 'fallback' instead.")
        return FallbackEngineV2()

    # === DCA/GRID ENGINE (specialized for DCA strategies) ===
    if engine_type in ("dca", "grid", "dca_grid"):
        from backend.backtesting.engines.dca_engine import DCAEngine

        logger.info("🎯 Using DCAEngine for DCA/Grid trading strategy")
        return DCAEngine()

    if engine_type == "gpu":
        try:
            from backend.backtesting.engines.gpu_engine_v2 import (
                GPU_AVAILABLE,
                GPUEngineV2,
            )

            if GPU_AVAILABLE:
                logger.warning("⚠️ GPUEngineV2 is DEPRECATED. Use 'optimization' (Numba) instead.")
                return GPUEngineV2()
        except ImportError:
            pass
        logger.warning("GPUEngineV2 not available, falling back to FallbackEngineV4")
        return FallbackEngineV4()

    # Unknown engine type - default to FallbackEngineV4
    logger.warning(f"Unknown engine_type '{engine_type}', using FallbackEngineV4")
    return FallbackEngineV4()


def get_available_engines() -> dict:
    """

    Get information about available engines.

    Returns:
        Dict with engine availability and capabilities
    """
    engines = {
        "fallback": {
            "available": True,
            "name": "FallbackEngineV4",
            "description": "Эталонный движок: Multi-TP, ATR SL/TP, Trailing, DCA, Pyramiding",
            "supports_bar_magnifier": True,
            "supports_pyramiding": True,
            "supports_multi_tp": True,
            "supports_atr_sltp": True,
            "acceleration": "None (CPU)",
        },
        "fallback_v4": {
            "available": True,
            "name": "FallbackEngineV4",
            "description": "Эталонный движок: Multi-TP, ATR SL/TP, Trailing, DCA, Pyramiding",
            "supports_bar_magnifier": True,
            "supports_pyramiding": True,
            "supports_multi_tp": True,
            "supports_atr_sltp": True,
            "acceleration": "None (CPU)",
        },
        "dca": {
            "available": True,
            "name": "DCAEngine",
            "description": "Specialized DCA/Grid trading with Martingale, Log steps, Multi-TP",
            "supports_bar_magnifier": False,
            "supports_pyramiding": True,
            "supports_multi_tp": True,
            "supports_dca_grid": True,
            "supports_martingale": True,
            "acceleration": "None (CPU)",
        },
    }

    # Check Numba
    try:
        from backend.backtesting.engines.numba_engine_v2 import (
            NumbaEngineV2,  # noqa: F401
        )

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
        from backend.backtesting.engines.gpu_engine_v2 import GPUEngineV2  # noqa: F401

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
