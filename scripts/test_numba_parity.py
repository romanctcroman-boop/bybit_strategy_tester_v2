"""
Numba vs Fallback Parity Test Suite

Tests parity between FallbackEngineV4 and NumbaEngineV2 for all features:
- V2: Basic SL/TP
- V3: Pyramiding
- V4: ATR SL/TP, Multi-TP, Trailing

Run: py -3.14 scripts/test_numba_parity.py
"""

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.engines.numba_engine_v2 import NUMBA_AVAILABLE, NumbaEngineV2
from backend.backtesting.interfaces import (
    BacktestInput,
    BacktestOutput,
    TradeDirection,
)


@dataclass
class ParityResult:
    """Result of a parity test."""
    test_name: str
    fallback_trades: int
    numba_trades: int
    trade_count_match: bool
    pnl_diff_pct: float
    equity_diff_pct: float
    passed: bool
    details: dict


def generate_synthetic_data(n_bars: int = 500, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(seed)

    # Generate price series with random walk
    returns = np.random.randn(n_bars) * 0.02  # 2% daily volatility
    prices = 50000 * np.exp(np.cumsum(returns))

    # Generate OHLC from close prices
    high_mult = 1 + np.abs(np.random.randn(n_bars) * 0.005)
    low_mult = 1 - np.abs(np.random.randn(n_bars) * 0.005)

    close = prices
    high = close * high_mult
    low = close * low_mult
    open_ = np.roll(close, 1)
    open_[0] = close[0]

    # Ensure OHLC consistency
    high = np.maximum(high, np.maximum(open_, close))
    low = np.minimum(low, np.minimum(open_, close))

    volume = np.random.uniform(100, 1000, n_bars)

    # Create DataFrame with datetime index
    dates = pd.date_range(start="2025-01-01", periods=n_bars, freq="1h")

    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=dates)

    return df


def generate_rsi_signals(
    close: np.ndarray,
    period: int = 14,
    overbought: int = 70,
    oversold: int = 30,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate RSI-based entry/exit signals."""
    n = len(close)

    # Calculate RSI
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    avg_gain = np.zeros(n)
    avg_loss = np.zeros(n)

    # Initial SMA
    avg_gain[period] = np.mean(gain[1:period+1])
    avg_loss[period] = np.mean(loss[1:period+1])

    # Wilder's smoothing
    for i in range(period + 1, n):
        avg_gain[i] = (avg_gain[i-1] * (period - 1) + gain[i]) / period
        avg_loss[i] = (avg_loss[i-1] * (period - 1) + loss[i]) / period

    rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100)
    rsi = 100 - (100 / (1 + rs))

    # Generate signals
    long_entries = (rsi < oversold) & (np.roll(rsi, 1) >= oversold)
    long_exits = (rsi > overbought) & (np.roll(rsi, 1) <= overbought)
    short_entries = (rsi > overbought) & (np.roll(rsi, 1) <= overbought)
    short_exits = (rsi < oversold) & (np.roll(rsi, 1) >= oversold)

    # Clean up first period bars
    long_entries[:period+1] = False
    long_exits[:period+1] = False
    short_entries[:period+1] = False
    short_exits[:period+1] = False

    return long_entries, long_exits, short_entries, short_exits


def create_backtest_input(
    candles: pd.DataFrame,
    long_entries: np.ndarray,
    long_exits: np.ndarray,
    short_entries: np.ndarray,
    short_exits: np.ndarray,
    **kwargs,
) -> BacktestInput:
    """Create BacktestInput with given parameters."""
    defaults = {
        "candles": candles,
        "long_entries": long_entries,
        "long_exits": long_exits,
        "short_entries": short_entries,
        "short_exits": short_exits,
        "initial_capital": 10000.0,
        "leverage": 1.0,
        "position_size": 1.0,
        "stop_loss": 0.02,
        "take_profit": 0.04,
        "taker_fee": 0.0007,  # 0.07% for TradingView parity
        "slippage": 0.0,
        "direction": TradeDirection.BOTH,
        "use_fixed_amount": True,
        "fixed_amount": 10000.0,
    }
    defaults.update(kwargs)
    return BacktestInput(**defaults)


def compare_results(
    fb_result: BacktestOutput,
    numba_result: BacktestOutput,
    tolerance_pct: float = 1.0,
) -> dict:
    """Compare two backtest results."""
    fb_trades = len(fb_result.trades)
    numba_trades = len(numba_result.trades)

    # Compare total PnL
    fb_pnl = sum(t.pnl for t in fb_result.trades if t.pnl)
    numba_pnl = sum(t.pnl for t in numba_result.trades if t.pnl)

    if abs(fb_pnl) > 0.01:
        pnl_diff_pct = abs(fb_pnl - numba_pnl) / abs(fb_pnl) * 100
    else:
        pnl_diff_pct = 0.0 if abs(numba_pnl) < 0.01 else 100.0

    # Compare final equity
    fb_equity = fb_result.equity_curve[-1] if len(fb_result.equity_curve) > 0 else 10000
    numba_equity = numba_result.equity_curve[-1] if len(numba_result.equity_curve) > 0 else 10000

    if abs(fb_equity) > 0.01:
        equity_diff_pct = abs(fb_equity - numba_equity) / abs(fb_equity) * 100
    else:
        equity_diff_pct = 0.0

    return {
        "fb_trades": fb_trades,
        "numba_trades": numba_trades,
        "trade_count_match": fb_trades == numba_trades,
        "fb_pnl": fb_pnl,
        "numba_pnl": numba_pnl,
        "pnl_diff_pct": pnl_diff_pct,
        "fb_equity": fb_equity,
        "numba_equity": numba_equity,
        "equity_diff_pct": equity_diff_pct,
        "passed": (
            fb_trades == numba_trades
            and pnl_diff_pct < tolerance_pct
            and equity_diff_pct < tolerance_pct
        ),
    }


def run_parity_test(
    test_name: str,
    candles: pd.DataFrame,
    signals: tuple,
    extra_params: dict,
    tolerance_pct: float = 1.0,
) -> ParityResult:
    """Run a single parity test."""
    long_entries, long_exits, short_entries, short_exits = signals

    # Create input
    input_data = create_backtest_input(
        candles,
        long_entries,
        long_exits,
        short_entries,
        short_exits,
        **extra_params,
    )

    # Run Fallback
    fb_engine = FallbackEngineV4()
    fb_result = fb_engine.run(input_data)

    # Run Numba
    numba_engine = NumbaEngineV2()
    numba_result = numba_engine.run(input_data)

    # Compare
    comparison = compare_results(fb_result, numba_result, tolerance_pct)

    return ParityResult(
        test_name=test_name,
        fallback_trades=comparison["fb_trades"],
        numba_trades=comparison["numba_trades"],
        trade_count_match=comparison["trade_count_match"],
        pnl_diff_pct=comparison["pnl_diff_pct"],
        equity_diff_pct=comparison["equity_diff_pct"],
        passed=comparison["passed"],
        details=comparison,
    )


def test_v2_basic() -> list[ParityResult]:
    """Test V2: Basic SL/TP (no pyramiding, no ATR)."""
    print("\n" + "=" * 60)
    print("V2 PARITY TESTS: Basic SL/TP")
    print("=" * 60)

    results = []
    candles = generate_synthetic_data(500)
    signals = generate_rsi_signals(candles["close"].values)

    # Test 1: Long only
    result = run_parity_test(
        "V2 Long Only",
        candles,
        signals,
        {"direction": TradeDirection.LONG, "stop_loss": 0.02, "take_profit": 0.04},
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    # Test 2: Short only
    result = run_parity_test(
        "V2 Short Only",
        candles,
        signals,
        {"direction": TradeDirection.SHORT, "stop_loss": 0.02, "take_profit": 0.04},
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    # Test 3: Both directions
    result = run_parity_test(
        "V2 Both Directions",
        candles,
        signals,
        {"direction": TradeDirection.BOTH, "stop_loss": 0.02, "take_profit": 0.04},
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    # Test 4: No SL/TP (signal-only exit)
    result = run_parity_test(
        "V2 No SL/TP",
        candles,
        signals,
        {"direction": TradeDirection.BOTH, "stop_loss": 0.0, "take_profit": 0.0},
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    return results


def test_v3_pyramiding() -> list[ParityResult]:
    """Test V3: Pyramiding support."""
    print("\n" + "=" * 60)
    print("V3 PARITY TESTS: Pyramiding")
    print("=" * 60)

    results = []
    candles = generate_synthetic_data(500)
    signals = generate_rsi_signals(candles["close"].values)

    # Test 1: Pyramiding = 2
    result = run_parity_test(
        "V3 Pyramiding=2",
        candles,
        signals,
        {"direction": TradeDirection.LONG, "pyramiding": 2, "stop_loss": 0.03, "take_profit": 0.06},
        tolerance_pct=5.0,  # Higher tolerance for pyramiding
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    # Test 2: Pyramiding = 3
    result = run_parity_test(
        "V3 Pyramiding=3",
        candles,
        signals,
        {"direction": TradeDirection.BOTH, "pyramiding": 3, "stop_loss": 0.02, "take_profit": 0.04},
        tolerance_pct=5.0,
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    return results


def test_v4_atr() -> list[ParityResult]:
    """Test V4: ATR-based SL/TP."""
    print("\n" + "=" * 60)
    print("V4 PARITY TESTS: ATR SL/TP")
    print("=" * 60)

    from backend.backtesting.interfaces import SlMode, TpMode

    results = []
    candles = generate_synthetic_data(500)
    signals = generate_rsi_signals(candles["close"].values)

    # Test 1: ATR SL only
    result = run_parity_test(
        "V4 ATR SL",
        candles,
        signals,
        {
            "direction": TradeDirection.LONG,
            "sl_mode": SlMode.ATR,
            "atr_sl_multiplier": 1.5,
            "take_profit": 0.04,
        },
        tolerance_pct=5.0,
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    # Test 2: ATR TP only
    result = run_parity_test(
        "V4 ATR TP",
        candles,
        signals,
        {
            "direction": TradeDirection.LONG,
            "stop_loss": 0.02,
            "tp_mode": TpMode.ATR,
            "atr_tp_multiplier": 2.0,
        },
        tolerance_pct=5.0,
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    # Test 3: ATR SL + TP
    result = run_parity_test(
        "V4 ATR SL+TP",
        candles,
        signals,
        {
            "direction": TradeDirection.BOTH,
            "sl_mode": SlMode.ATR,
            "tp_mode": TpMode.ATR,
            "atr_sl_multiplier": 1.5,
            "atr_tp_multiplier": 2.5,
        },
        tolerance_pct=5.0,
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    return results


def test_v4_multi_tp() -> list[ParityResult]:
    """Test V4: Multi-level TP."""
    print("\n" + "=" * 60)
    print("V4 PARITY TESTS: Multi-level TP")
    print("=" * 60)

    from backend.backtesting.interfaces import SlMode, TpMode

    results = []
    candles = generate_synthetic_data(500)
    signals = generate_rsi_signals(candles["close"].values)

    # Test 1: Multi-TP with fixed %
    result = run_parity_test(
        "V4 Multi-TP Fixed",
        candles,
        signals,
        {
            "direction": TradeDirection.LONG,
            "tp_mode": TpMode.MULTI,
            "multi_tp_enabled": True,
            "tp_portions": (0.25, 0.25, 0.25, 0.25),  # 25% at each level
            "tp_levels": (0.01, 0.02, 0.03, 0.04),    # 1%, 2%, 3%, 4% profit
            "stop_loss": 0.02,
        },
        tolerance_pct=10.0,  # Higher tolerance for multi-TP
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    # Test 2: Multi-TP with ATR
    result = run_parity_test(
        "V4 Multi-TP ATR",
        candles,
        signals,
        {
            "direction": TradeDirection.BOTH,
            "tp_mode": TpMode.MULTI,
            "multi_tp_enabled": True,
            "tp_portions": (0.50, 0.50, 0.0, 0.0),  # 50% at first two levels
            "tp_levels": (0.01, 0.02, 0.03, 0.04),  # Will use first two
            "sl_mode": SlMode.ATR,
            "atr_sl_multiplier": 1.5,
        },
        tolerance_pct=10.0,
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    return results


def test_v4_trailing() -> list[ParityResult]:
    """Test V4: Trailing stop."""
    print("\n" + "=" * 60)
    print("V4 PARITY TESTS: Trailing Stop")
    print("=" * 60)

    from backend.backtesting.interfaces import TpMode

    results = []
    candles = generate_synthetic_data(500)
    signals = generate_rsi_signals(candles["close"].values)

    # Test 1: Trailing only
    result = run_parity_test(
        "V4 Trailing",
        candles,
        signals,
        {
            "direction": TradeDirection.LONG,
            "trailing_stop_enabled": True,
            "trailing_stop_activation": 0.01,  # Activate after 1% profit
            "trailing_stop_distance": 0.005,   # Trail 0.5% from best
            "stop_loss": 0.03,
            "take_profit": 0.0,  # No fixed TP
        },
        tolerance_pct=10.0,
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    # Test 2: Trailing + Multi-TP (activate after TP1)
    result = run_parity_test(
        "V4 Trailing + Multi-TP",
        candles,
        signals,
        {
            "direction": TradeDirection.BOTH,
            "trailing_stop_enabled": True,
            "tp_mode": TpMode.MULTI,
            "multi_tp_enabled": True,
            "trailing_stop_activation": 0.0,  # Activate immediately after TP1
            "trailing_stop_distance": 0.005,
            "tp_portions": (0.50, 0.0, 0.0, 0.50),  # 50% at TP1, 50% at TP4
            "tp_levels": (0.02, 0.04, 0.06, 0.10),  # 2%, 4%, 6%, 10%
            "stop_loss": 0.02,
        },
        tolerance_pct=15.0,
    )
    results.append(result)
    print(f"  {result.test_name}: {'PASS' if result.passed else 'FAIL'} "
          f"(FB:{result.fallback_trades} NUM:{result.numba_trades} PnL diff:{result.pnl_diff_pct:.2f}%)")

    return results


def main():
    """Run all parity tests."""
    print("\n" + "=" * 70)
    print("NUMBA vs FALLBACK PARITY TEST SUITE")
    print("=" * 70)

    if not NUMBA_AVAILABLE:
        print("\n[WARN] Numba not installed - tests will use Python fallback")
        print("       Install numba for actual JIT performance: pip install numba")

    all_results = []

    # V2 tests
    all_results.extend(test_v2_basic())

    # V3 tests
    all_results.extend(test_v3_pyramiding())

    # V4 tests
    all_results.extend(test_v4_atr())
    all_results.extend(test_v4_multi_tp())
    all_results.extend(test_v4_trailing())

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)

    print(f"\n{'Test Name':<30} {'FB':>6} {'NUM':>6} {'PnL%':>8} {'Result':>8}")
    print("-" * 70)

    for r in all_results:
        status = "[PASS]" if r.passed else "[FAIL]"
        print(f"{r.test_name:<30} {r.fallback_trades:>6} {r.numba_trades:>6} "
              f"{r.pnl_diff_pct:>7.2f}% {status:>8}")

    print("-" * 70)
    print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n[OK] All parity tests PASSED!")
    else:
        print(f"\n[WARN] {total - passed} tests failed - check implementation")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
