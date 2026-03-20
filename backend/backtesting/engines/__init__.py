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

# === DCA ENGINE (Grid/DCA Trading) ===
from backend.backtesting.engines.dca_engine import DCAEngine, DCAGridCalculator, DCAGridConfig

# === DEPRECATED (not imported — import directly to use) ===
# FallbackEngineV2 and FallbackEngineV3 are no longer exported from this package.
# They still exist at:
#   backend/backtesting/engines/fallback_engine_v2.py  (parity tests)
#   backend/backtesting/engines/fallback_engine_v3.py  (parity tests)
# Import them directly if needed:
#   from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2


def _deprecated_engine_shim(name: str):
    """Backward-compat shim: returns class but warns."""
    import warnings

    if name == "FallbackEngineV2":
        warnings.warn(
            "FallbackEngineV2 is deprecated. Use FallbackEngine (V4). "
            "Importing from engines package is deprecated; import directly from "
            "backend.backtesting.engines.fallback_engine_v2 for parity tests.",
            DeprecationWarning,
            stacklevel=3,
        )
        from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2

        return FallbackEngineV2
    if name == "FallbackEngineV3":
        warnings.warn(
            "FallbackEngineV3 is deprecated. Use FallbackEngine (V4). "
            "Importing from engines package is deprecated; import directly from "
            "backend.backtesting.engines.fallback_engine_v3 for parity tests.",
            DeprecationWarning,
            stacklevel=3,
        )
        from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3

        return FallbackEngineV3
    return None


def __getattr__(name: str):
    """Lazy + deprecated access for removed engines."""
    cls = _deprecated_engine_shim(name)
    if cls is not None:
        return cls
    raise AttributeError(f"module 'backend.backtesting.engines' has no attribute '{name}'")


# Event-driven engine (skeleton, ROADMAP_REMAINING_TASKS)
try:
    from backend.backtesting.engines.event_driven_engine import (
        BarEvent,
        EventDrivenEngine,
        EventQueue,
        FillEvent,
        OrderEvent,
    )
except ImportError:
    EventDrivenEngine = None  # type: ignore[misc,assignment]
    EventQueue = None  # type: ignore[misc,assignment]
    BarEvent = None  # type: ignore[misc,assignment]
    OrderEvent = None  # type: ignore[misc,assignment]
    FillEvent = None  # type: ignore[misc,assignment]

__all__ = [
    # Availability flags
    "NUMBA_AVAILABLE",
    "BacktestInput",
    "BacktestMetrics",
    "BacktestOutput",
    "BarEvent",
    # Interfaces
    "BaseBacktestEngine",
    "DCAEngine",  # = DCA/Grid Trading engine
    "DCAGridCalculator",
    # DCA Components
    "DCAGridConfig",
    "EngineComparator",
    # Event-driven (skeleton, ROADMAP)
    "EventDrivenEngine",
    "EventQueue",
    "ExitReason",
    # Main Engines
    "FallbackEngine",  # = V4 (основной)
    # Explicit versions (for parity tests)
    "FallbackEngineV4",
    # NOTE: FallbackEngineV2 and FallbackEngineV3 removed from __all__
    # Import directly: from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
    "FillEvent",
    "NumbaEngine",  # = NumbaEngineV2 (быстрый)
    "NumbaEngineV2",
    "OrderEvent",
    "TradeDirection",
    "TradeRecord",
]
