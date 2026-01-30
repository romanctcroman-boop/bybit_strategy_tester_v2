"""
Engines Package - Unified Backtest Engines

ARCHITECTURE (2026-01-28): Консолидация до 2 движков
----------------------------------------------------

::

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    SIMPLIFIED ENGINE ARCHITECTURE                    │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │   FallbackEngine (V4) — ОСНОВНОЙ ЭТАЛОН                             │
    │   - Все фичи: pyramiding, multi-TP, ATR, trailing, DCA              │
    │   - Скорость: 1x (Python)                                           │
    │   - Роль: старт, отладка, уточнение, верификация                    │
    │                                                                     │
    │   NumbaEngine (V2→V4) — БЫСТРЫЙ                                     │
    │   - Все фичи V4: pyramiding, multi-TP, ATR, trailing                │
    │   - Скорость: ~20-40x                                               │
    │   - Роль: оптимизация (точность + скорость)                         │
    │                                                                     │
    │   V2/V3/GPU — DEPRECATED (для обратной совместимости)               │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

Usage:
    from backend.backtesting.engines import FallbackEngine, NumbaEngine

    # Основной эталон (все фичи)
    engine = FallbackEngine()

    # Быстрый (для оптимизации)
    engine = NumbaEngine()  # or get_engine("numba")

    # DEPRECATED (работают, но выдают warning):
    engine = FallbackEngineV2()  # -> use FallbackEngine
    engine = FallbackEngineV3()  # -> use FallbackEngine
"""

# === MAIN ENGINE (V4 as FallbackEngine) ===
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import (
    BacktestInput,
    BacktestMetrics,
    BacktestOutput,
    BaseBacktestEngine,
    EngineComparator,
    ExitReason,
    TradeDirection,
    TradeRecord,
)

# FallbackEngine = V4 (основной эталон)
FallbackEngine = FallbackEngineV4

# === NUMBA ENGINE ===
try:
    from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

    NumbaEngine = NumbaEngineV2
    NUMBA_AVAILABLE = True
except ImportError:
    NumbaEngine = None  # type: ignore[misc,assignment]
    NumbaEngineV2 = None  # type: ignore[misc,assignment]
    NUMBA_AVAILABLE = False

# === DEPRECATED (for backward compatibility) ===
# These still work but emit DeprecationWarning
# === DCA ENGINE (Grid/DCA Trading) ===
from backend.backtesting.engines.dca_engine import DCAEngine, DCAGridCalculator, DCAGridConfig
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3

__all__ = [
    # Interfaces
    "BaseBacktestEngine",
    "BacktestInput",
    "BacktestOutput",
    "BacktestMetrics",
    "TradeRecord",
    "TradeDirection",
    "ExitReason",
    "EngineComparator",
    # Main Engines
    "FallbackEngine",  # = V4 (основной)
    "NumbaEngine",  # = NumbaEngineV2 (быстрый)
    "DCAEngine",  # = DCA/Grid Trading engine
    # Explicit versions (for parity tests)
    "FallbackEngineV4",
    "NumbaEngineV2",
    # DCA Components
    "DCAGridConfig",
    "DCAGridCalculator",
    # Deprecated (backward compatibility)
    "FallbackEngineV2",  # deprecated
    "FallbackEngineV3",  # deprecated
    # Availability flags
    "NUMBA_AVAILABLE",
]
