"""
Centralized constants for Bybit Strategy Tester v2.

Single source of truth for commission rates, capital defaults, and trading parameters.
All modules MUST import from here — never hardcode these values.

Invariant: COMMISSION_TV = 0.0007 (TradingView parity) — NEVER change without explicit approval.
"""

# =============================================================================
# COMMISSION RATES
# =============================================================================

# TradingView parity commission — used for all backtests by default.
# Do NOT change without explicit approval (breaks TradingView parity).
COMMISSION_TV: float = 0.0007  # 0.07%

# Bybit linear perpetuals (taker = market orders)
COMMISSION_LINEAR_TAKER: float = 0.00055  # 0.055%
COMMISSION_LINEAR_MAKER: float = 0.0002  # 0.02%

# Bybit spot market
COMMISSION_SPOT_TAKER: float = 0.001  # 0.1%
COMMISSION_SPOT_MAKER: float = 0.001  # 0.1%

# Default maker/taker alias (linear perpetuals)
TAKER_FEE_DEFAULT: float = COMMISSION_LINEAR_TAKER
MAKER_FEE_DEFAULT: float = COMMISSION_LINEAR_MAKER


# =============================================================================
# CAPITAL AND BACKTEST DEFAULTS
# =============================================================================

INITIAL_CAPITAL: float = 10_000.0
MAX_BACKTEST_DAYS: int = 730  # 2 years — enforced by BacktestConfig.validate_dates()
DEFAULT_SLIPPAGE: float = 0.0005  # 0.05%
DEFAULT_RISK_FREE_RATE: float = 0.02  # 2% annual


# =============================================================================
# LEVERAGE DEFAULTS
# =============================================================================

# Intentionally different: optimizer/UI needs higher leverage for meaningful results,
# live trading uses 1x for safety (ADR-006).
LEVERAGE_DEFAULT_BACKTEST: float = 1.0
LEVERAGE_DEFAULT_OPTIMIZATION: int = 10
LEVERAGE_MAX: float = 125.0  # Bybit maximum


# =============================================================================
# TIMEFRAMES
# =============================================================================

VALID_TIMEFRAMES: list[str] = ["1", "5", "15", "30", "60", "240", "D", "W", "M"]

# Legacy timeframe remapping (applied on load)
TIMEFRAME_LEGACY_MAP: dict[str, str] = {
    "3": "5",
    "120": "60",
    "360": "240",
    "720": "D",
}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "COMMISSION_LINEAR_MAKER",
    "COMMISSION_LINEAR_TAKER",
    "COMMISSION_SPOT_MAKER",
    "COMMISSION_SPOT_TAKER",
    "COMMISSION_TV",
    "DEFAULT_RISK_FREE_RATE",
    "DEFAULT_SLIPPAGE",
    "INITIAL_CAPITAL",
    "LEVERAGE_DEFAULT_BACKTEST",
    "LEVERAGE_DEFAULT_OPTIMIZATION",
    "LEVERAGE_MAX",
    "MAKER_FEE_DEFAULT",
    "MAX_BACKTEST_DAYS",
    "TAKER_FEE_DEFAULT",
    "TIMEFRAME_LEGACY_MAP",
    "VALID_TIMEFRAMES",
]
