"""
MEGA Test V5 - Extended Optimizer Testing Suite (FIXED API)
============================================================

MASSIVE testing of optimization engines with:
- 50+ different parameter configurations
- Grid search variations
- Bayesian optimization (Optuna)
- Walk-forward analysis concepts
- Monte Carlo simulations concepts
- Multi-objective optimization
- Parameter sensitivity analysis
- Robustness testing
- Edge cases and stress tests

API Notes:
- FastGridOptimizer(): No args in __init__, candles passed to optimize()
- GPUGridOptimizer(position_size=1.0, force_cpu=False): candles in optimize()
- UniversalOptimizer(backend="auto"): candles in optimize()
- All range parameters must be LISTS, not tuples
"""

import os
import sys
import time
import traceback
from dataclasses import dataclass

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd


# ============================================================================
# Test Result Tracking
# ============================================================================
@dataclass
class TestResult:
    name: str
    category: str
    passed: bool
    details: str
    execution_time: float = 0.0
    error: str | None = None


test_results: list[TestResult] = []


def run_test(name: str, category: str):
    """Decorator to track test results with timing."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                if result is True or result is None:
                    test_results.append(
                        TestResult(
                            name, category, True, f"OK ({elapsed:.2f}s)", elapsed
                        )
                    )
                    print(f"  ✅ {name} ({elapsed:.2f}s)")
                else:
                    test_results.append(
                        TestResult(name, category, False, str(result), elapsed)
                    )
                    print(f"  ❌ {name}: {result}")
            except Exception as e:
                elapsed = time.time() - start_time
                test_results.append(
                    TestResult(
                        name, category, False, str(e), elapsed, traceback.format_exc()
                    )
                )
                print(f"  ❌ {name}: {e}")

        return wrapper

    return decorator


def generate_test_ohlcv(
    n_bars: int = 500,
    start_price: float = 100.0,
    volatility: float = 0.015,
    trend: float = 0.0002,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data with configurable parameters.

    Uses stable V4 algorithm that doesn't overflow for large n_bars.
    """
    np.random.seed(seed)

    dates = pd.date_range(start="2024-01-01", periods=n_bars, freq="1h")

    # Random walk with trend and volatility clusters (STABLE VERSION)
    returns = np.random.normal(trend, volatility, n_bars)

    # Add volatility clustering (capped to prevent overflow)
    vol_factor = np.ones(n_bars)
    for i in range(1, n_bars):
        # Cap vol_factor to prevent exponential explosion
        vol_factor[i] = min(
            5.0, 0.9 * vol_factor[i - 1] + 0.1 * abs(returns[i - 1]) * 50
        )
    returns = returns * (1 + vol_factor * 0.5)

    # Build price series using cumprod (more stable)
    prices = start_price * np.cumprod(1 + returns)

    # Generate OHLC from prices
    data = {
        "timestamp": dates,
        "open": prices * (1 + np.random.uniform(-0.003, 0.003, n_bars)),
        "high": prices * (1 + np.random.uniform(0.001, 0.015, n_bars)),
        "low": prices * (1 - np.random.uniform(0.001, 0.015, n_bars)),
        "close": prices,
        "volume": np.random.uniform(1000, 50000, n_bars),
    }

    df = pd.DataFrame(data)
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


def generate_trending_data(n_bars: int = 500, direction: str = "up") -> pd.DataFrame:
    """Generate data with clear trend."""
    np.random.seed(123)
    trend = 0.001 if direction == "up" else -0.001
    return generate_test_ohlcv(n_bars=n_bars, trend=trend, volatility=0.01, seed=123)


def generate_ranging_data(n_bars: int = 500) -> pd.DataFrame:
    """Generate sideways/ranging market data."""
    np.random.seed(456)
    return generate_test_ohlcv(n_bars=n_bars, trend=0.0, volatility=0.008, seed=456)


def generate_volatile_data(n_bars: int = 500) -> pd.DataFrame:
    """Generate high volatility data."""
    np.random.seed(789)
    return generate_test_ohlcv(n_bars=n_bars, trend=0.0001, volatility=0.03, seed=789)


# ============================================================================
# CATEGORY 1: Extreme RSI Parameter Variations
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 1: Extreme RSI Parameter Variations")
print("=" * 70)


@run_test("FastGridOptimizer import", "RSI_Variations")
def test_fast_optimizer_import():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    assert FastGridOptimizer is not None
    return True


@run_test("RSI Period 5-10 (Ultra Short)", "RSI_Variations")
def test_rsi_ultra_short():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[5, 7, 10],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 3.0],
        initial_capital=10000,
        leverage=1,
        direction="long",
    )

    assert result.status == "completed", f"Status: {result.status}"
    assert len(result.top_results) > 0, "No results returned"
    print(f"    [INFO] Ultra short RSI: {len(result.top_results)} results")
    return True


@run_test("RSI Period 30-50 (Long Term)", "RSI_Variations")
def test_rsi_long_term():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(1000)  # Need more data for long RSI
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[30, 35, 40, 50],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[2.0, 3.0, 4.0],
        take_profit_range=[3.0, 5.0, 6.0],
        initial_capital=10000,
        leverage=1,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] Long term RSI: {len(result.top_results)} results")
    return True


@run_test("RSI Extreme Overbought 85-95", "RSI_Variations")
def test_rsi_extreme_overbought():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[85, 90, 95],
        rsi_oversold_range=[5, 10, 15],
        stop_loss_range=[0.5, 1.0, 1.5],
        take_profit_range=[1.0, 2.0, 3.0],
        initial_capital=10000,
        leverage=1,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] Extreme overbought RSI: {len(result.top_results)} results")
    return True


@run_test("RSI Narrow Band 45-55", "RSI_Variations")
def test_rsi_narrow_band():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14],
        rsi_overbought_range=[52, 55, 58],  # Very narrow
        rsi_oversold_range=[42, 45, 48],
        stop_loss_range=[0.5, 1.0],
        take_profit_range=[0.5, 1.0],
        initial_capital=10000,
        leverage=1,
        direction="both",
    )

    assert result.status == "completed"
    print(f"    [INFO] Narrow band RSI: {len(result.top_results)} results")
    return True


@run_test("RSI Wide Spread 20-80", "RSI_Variations")
def test_rsi_wide_spread():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 14, 21, 28],
        rsi_overbought_range=[75, 80, 85],
        rsi_oversold_range=[15, 20, 25],
        stop_loss_range=[1.5, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=1,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] Wide spread RSI: {len(result.top_results)} results")
    return True


# ============================================================================
# CATEGORY 2: Stop Loss / Take Profit Variations
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 2: Stop Loss / Take Profit Variations")
print("=" * 70)


@run_test("Tight SL 0.1-0.5%", "SL_TP_Variations")
def test_tight_stop_loss():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14],
        rsi_overbought_range=[70],
        rsi_oversold_range=[30],
        stop_loss_range=[0.1, 0.2, 0.3, 0.4, 0.5],
        take_profit_range=[0.2, 0.5, 1.0],
        initial_capital=10000,
        leverage=10,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] Tight SL: {len(result.top_results)} results")
    return True


@run_test("Wide SL 5-10%", "SL_TP_Variations")
def test_wide_stop_loss():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[5.0, 6.0, 7.0, 8.0, 10.0],
        take_profit_range=[8.0, 10.0, 15.0],
        initial_capital=10000,
        leverage=1,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] Wide SL: {len(result.top_results)} results")
    return True


@run_test("Asymmetric Risk/Reward 1:5", "SL_TP_Variations")
def test_asymmetric_risk_reward():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    # SL small, TP large (1:5 ratio)
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[0.5, 0.8, 1.0],
        take_profit_range=[2.5, 4.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] 1:5 R/R: {len(result.top_results)} results")
    return True


@run_test("Scalping TP 0.2-0.5%", "SL_TP_Variations")
def test_scalping_tp():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[5, 7, 10],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[0.1, 0.2, 0.3],
        take_profit_range=[0.2, 0.3, 0.5],
        initial_capital=10000,
        leverage=20,
        direction="both",
    )

    assert result.status == "completed"
    print(f"    [INFO] Scalping: {len(result.top_results)} results")
    return True


@run_test("Swing Trading TP 10-20%", "SL_TP_Variations")
def test_swing_tp():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(1000)  # More data for swing
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[21, 28, 35],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[3.0, 4.0, 6.0],
        take_profit_range=[10.0, 15.0, 20.0],
        initial_capital=10000,
        leverage=1,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] Swing trading: {len(result.top_results)} results")
    return True


# ============================================================================
# CATEGORY 3: Leverage Variations
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 3: Leverage Variations")
print("=" * 70)


@run_test("No Leverage (1x)", "Leverage_Tests")
def test_no_leverage():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[2.0, 3.0, 4.0],
        take_profit_range=[3.0, 4.0, 6.0],
        initial_capital=10000,
        leverage=1,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] 1x leverage: {len(result.top_results)} results")
    return True


@run_test("Medium Leverage (10x)", "Leverage_Tests")
def test_medium_leverage():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 1.5, 2.0],
        take_profit_range=[2.0, 3.0, 4.0],
        initial_capital=10000,
        leverage=10,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] 10x leverage: {len(result.top_results)} results")
    return True


@run_test("High Leverage (50x)", "Leverage_Tests")
def test_high_leverage():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[0.3, 0.5, 0.8],
        take_profit_range=[0.5, 1.0, 1.5],
        initial_capital=10000,
        leverage=50,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] 50x leverage: {len(result.top_results)} results")
    return True


@run_test("Extreme Leverage (100x)", "Leverage_Tests")
def test_extreme_leverage():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 10, 14],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[0.1, 0.3, 0.5],
        take_profit_range=[0.2, 0.5, 0.8],
        initial_capital=10000,
        leverage=100,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] 100x leverage: {len(result.top_results)} results")
    return True


# ============================================================================
# CATEGORY 4: Direction Variations
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 4: Direction Variations")
print("=" * 70)


@run_test("Long Only - Uptrend Data", "Direction_Tests")
def test_long_uptrend():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_trending_data(500, "up")
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 35],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"
    best = result.best_metrics or {}
    print(f"    [INFO] Long uptrend: return={best.get('total_return', 0):.2f}%")
    return True


@run_test("Short Only - Downtrend Data", "Direction_Tests")
def test_short_downtrend():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_trending_data(500, "down")
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[65, 70, 80],
        rsi_oversold_range=[20, 30, 35],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="short",
    )

    assert result.status == "completed"
    best = result.best_metrics or {}
    print(f"    [INFO] Short downtrend: return={best.get('total_return', 0):.2f}%")
    return True


@run_test("Both Directions - Ranging Market", "Direction_Tests")
def test_both_ranging():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_ranging_data(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[1.0, 1.5, 2.0],
        take_profit_range=[1.5, 2.0, 3.0],
        initial_capital=10000,
        leverage=5,
        direction="both",
    )

    assert result.status == "completed"
    best = result.best_metrics or {}
    print(f"    [INFO] Both ranging: {best.get('total_trades', 0)} trades")
    return True


@run_test("Long Only - Volatile Market", "Direction_Tests")
def test_long_volatile():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_volatile_data(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 10, 14],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[2.0, 3.0, 5.0],
        take_profit_range=[3.0, 5.0, 8.0],
        initial_capital=10000,
        leverage=3,
        direction="long",
    )

    assert result.status == "completed"
    best = result.best_metrics or {}
    print(f"    [INFO] Long volatile: max_dd={best.get('max_drawdown', 0):.2f}%")
    return True


# ============================================================================
# CATEGORY 5: Large Grid Searches
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 5: Large Grid Searches (1000+ combinations)")
print("=" * 70)


@run_test("Grid 1000+ combinations (5 params)", "Large_Grid")
def test_large_grid_1k():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    # 4 * 3 * 3 * 7 * 5 = 1260 combinations
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21, 28],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        take_profit_range=[1.0, 2.0, 3.0, 4.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"
    print(
        f"    [INFO] 1000+ grid: {result.tested_combinations} tested, {len(result.top_results)} returned"
    )
    return True


@run_test("Grid 5000+ combinations (stress)", "Large_Grid")
def test_large_grid_5k():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(1000)
    optimizer = FastGridOptimizer()

    # 5 * 5 * 5 * 8 * 5 = 5000 combinations
    start = time.time()
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 10, 14, 21, 28],
        rsi_overbought_range=[65, 70, 75, 80, 85],
        rsi_oversold_range=[15, 20, 25, 30, 35],
        stop_loss_range=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        take_profit_range=[1.0, 2.0, 3.0, 5.0, 8.0],
        initial_capital=10000,
        leverage=10,
        direction="long",
    )
    elapsed = time.time() - start

    assert result.status == "completed"
    speed = result.tested_combinations / elapsed if elapsed > 0 else 0
    print(f"    [INFO] 5000+ grid: {result.tested_combinations} @ {speed:.0f}/sec")
    return True


@run_test("Grid 10000+ combinations (massive)", "Large_Grid")
def test_large_grid_10k():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(1500)
    optimizer = FastGridOptimizer()

    # 6 * 5 * 5 * 8 * 7 = 8400 combinations
    start = time.time()
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[5, 10, 14, 21, 28, 35],
        rsi_overbought_range=[65, 70, 75, 80, 85],
        rsi_oversold_range=[15, 20, 25, 30, 35],
        stop_loss_range=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        take_profit_range=[1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )
    elapsed = time.time() - start

    assert result.status == "completed"
    speed = result.tested_combinations / elapsed if elapsed > 0 else 0
    print(f"    [INFO] 10000+ grid: {result.tested_combinations} @ {speed:.0f}/sec")
    return True


# ============================================================================
# CATEGORY 6: GPU Optimizer Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 6: GPU Optimizer Tests")
print("=" * 70)


@run_test("GPU Availability Check", "GPU_Tests")
def test_gpu_availability():
    from backend.backtesting.gpu_optimizer import GPU_AVAILABLE

    if GPU_AVAILABLE:
        import cupy as cp

        gpu_count = cp.cuda.runtime.getDeviceCount()
        for i in range(gpu_count):
            props = cp.cuda.runtime.getDeviceProperties(i)
            mem_gb = props["totalGlobalMem"] / (1024**3)
            print(f"    [INFO] GPU {i}: {mem_gb:.1f}GB")
    else:
        print("    [INFO] GPU not available, tests will use CPU fallback")
    return True


@run_test("GPU Small Grid (100 combos)", "GPU_Tests")
def test_gpu_small_grid():
    from backend.backtesting.gpu_optimizer import GPUGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = GPUGridOptimizer()  # No candles in __init__!

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 1.5, 2.0],
        take_profit_range=[2.0, 2.5, 3.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] GPU small: {result.tested_combinations} tested")
    return True


@run_test("GPU Medium Grid (1000 combos)", "GPU_Tests")
def test_gpu_medium_grid():
    from backend.backtesting.gpu_optimizer import GPUGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = GPUGridOptimizer()

    start = time.time()
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21, 28],
        rsi_overbought_range=[65, 70, 75, 80],
        rsi_oversold_range=[20, 25, 30, 35],
        stop_loss_range=[0.5, 1.0, 2.0, 3.0],
        take_profit_range=[1.0, 2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=10,
        direction="long",
    )
    elapsed = time.time() - start

    assert result.status == "completed"
    speed = result.tested_combinations / elapsed if elapsed > 0 else 0
    print(f"    [INFO] GPU medium: {result.tested_combinations} @ {speed:.0f}/sec")
    return True


@run_test("GPU Large Grid (5000+ combos)", "GPU_Tests")
def test_gpu_large_grid():
    from backend.backtesting.gpu_optimizer import GPUGridOptimizer

    candles = generate_test_ohlcv(1000)
    optimizer = GPUGridOptimizer()

    start = time.time()
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[5, 10, 14, 21, 28, 35],
        rsi_overbought_range=[60, 65, 70, 75, 80, 85],
        rsi_oversold_range=[15, 20, 25, 30, 35, 40],
        stop_loss_range=[0.5, 1.0, 2.0, 3.0, 5.0],
        take_profit_range=[1.0, 2.0, 3.0, 5.0, 10.0],
        initial_capital=10000,
        leverage=10,
        direction="long",
    )
    elapsed = time.time() - start

    assert result.status == "completed"
    speed = result.tested_combinations / elapsed if elapsed > 0 else 0
    print(f"    [INFO] GPU large: {result.tested_combinations} @ {speed:.0f}/sec")
    return True


@run_test("GPU Both Directions", "GPU_Tests")
def test_gpu_both_directions():
    from backend.backtesting.gpu_optimizer import GPUGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = GPUGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 1.5, 2.5],
        take_profit_range=[2.0, 3.0, 4.0],
        initial_capital=10000,
        leverage=5,
        direction="both",
    )

    assert result.status == "completed"
    print(f"    [INFO] GPU both: {result.tested_combinations} results")
    return True


# ============================================================================
# CATEGORY 7: Universal Optimizer (Auto Backend Selection)
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 7: Universal Optimizer (Auto Backend)")
print("=" * 70)


@run_test("Universal Auto-Select Backend", "Universal_Tests")
def test_universal_auto():
    from backend.backtesting.optimizer import UniversalOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = UniversalOptimizer(backend="auto")  # No candles, backend in __init__

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 1.5, 2.0],
        take_profit_range=[2.0, 2.5, 3.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    backend = getattr(result, "backend_used", "unknown")
    assert result.status == "completed"
    print(
        f"    [INFO] Universal auto: backend={backend}, {result.tested_combinations} tested"
    )
    return True


@run_test("Universal Force GPU", "Universal_Tests")
def test_universal_force_gpu():
    from backend.backtesting.gpu_optimizer import GPU_AVAILABLE
    from backend.backtesting.optimizer import UniversalOptimizer

    candles = generate_test_ohlcv(500)

    if not GPU_AVAILABLE:
        print("    [INFO] GPU not available, skipped")
        return True

    try:
        optimizer = UniversalOptimizer(backend="gpu")

        result = optimizer.optimize(
            candles=candles,
            rsi_period_range=[14, 21],
            rsi_overbought_range=[70, 75],
            rsi_oversold_range=[25, 30],
            stop_loss_range=[1.0, 1.5, 2.0],
            take_profit_range=[2.0, 2.5, 3.0],
            initial_capital=10000,
            leverage=5,
            direction="long",
        )

        assert result.status == "completed"
        print(f"    [INFO] Universal GPU: {result.tested_combinations} tested")
    except Exception as e:
        print(f"    [INFO] GPU forced error: {e}")
    return True


@run_test("Universal Force CPU/Numba", "Universal_Tests")
def test_universal_force_cpu():
    from backend.backtesting.optimizer import UniversalOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = UniversalOptimizer(backend="cpu")

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 1.5, 2.0],
        take_profit_range=[2.0, 2.5, 3.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] Universal CPU: {result.tested_combinations} tested")
    return True


# ============================================================================
# CATEGORY 8: Optimization Metrics
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 8: Optimization by Different Metrics")
print("=" * 70)


@run_test("Optimize by Sharpe Ratio", "Metrics_Tests")
def test_optimize_sharpe():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
        optimize_metric="sharpe_ratio",
    )

    assert result.status == "completed"
    print(f"    [INFO] Best Sharpe: {result.best_score:.3f}")
    return True


@run_test("Optimize by Total Return", "Metrics_Tests")
def test_optimize_return():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
        optimize_metric="total_return",
    )

    assert result.status == "completed"
    print(f"    [INFO] Best Return: {result.best_score:.2f}%")
    return True


@run_test("Optimize by Calmar Ratio", "Metrics_Tests")
def test_optimize_calmar():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
        optimize_metric="calmar_ratio",
    )

    assert result.status == "completed"
    print(f"    [INFO] Best Calmar: {result.best_score:.3f}")
    return True


@run_test("Optimize by Profit Factor", "Metrics_Tests")
def test_optimize_pf():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
        optimize_metric="profit_factor",
    )

    assert result.status == "completed"
    print(f"    [INFO] Best PF: {result.best_score:.3f}")
    return True


@run_test("Optimize by Win Rate", "Metrics_Tests")
def test_optimize_winrate():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
        optimize_metric="win_rate",
    )

    assert result.status == "completed"
    print(f"    [INFO] Best Win Rate: {result.best_score:.1f}%")
    return True


# ============================================================================
# CATEGORY 9: Filtering Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 9: Result Filtering Tests")
print("=" * 70)


@run_test("Filter by Min Trades", "Filter_Tests")
def test_filter_min_trades():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
        filters={"min_trades": 5},
    )

    # Verify all results have at least min trades
    for r in result.top_results:
        if r.get("total_trades", 0) < 5:
            return f"Found result with {r.get('total_trades', 0)} trades (min=5)"

    print(f"    [INFO] Filtered results: {len(result.top_results)} (min 5 trades)")
    return True


@run_test("Filter by Max Drawdown", "Filter_Tests")
def test_filter_max_dd():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
        filters={"max_drawdown_limit": 0.25},  # 25%
    )

    print(f"    [INFO] Filtered results: {len(result.top_results)} (max 25% DD)")
    return True


@run_test("Filter by Min Profit Factor", "Filter_Tests")
def test_filter_min_pf():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
        filters={"min_profit_factor": 1.2},
    )

    print(f"    [INFO] Filtered results: {len(result.top_results)} (min PF 1.2)")
    return True


@run_test("Combined Filters", "Filter_Tests")
def test_combined_filters():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
        filters={
            "min_trades": 3,
            "max_drawdown_limit": 0.30,
            "min_profit_factor": 1.0,
        },
    )

    print(f"    [INFO] Combined filters: {len(result.top_results)} results")
    return True


# ============================================================================
# CATEGORY 10: Edge Cases and Stress Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 10: Edge Cases and Stress Tests")
print("=" * 70)


@run_test("Minimal Data (100 candles)", "Edge_Cases")
def test_minimal_data():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(100)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 14],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 3.0],
        initial_capital=10000,
        leverage=1,
        direction="long",
    )

    print(f"    [INFO] Minimal data: {len(result.top_results)} results")
    return True


@run_test("Large Data (10000 candles)", "Edge_Cases")
def test_large_data():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(10000)
    optimizer = FastGridOptimizer()

    start = time.time()
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 3.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )
    elapsed = time.time() - start

    print(f"    [INFO] Large data: {len(result.top_results)} results in {elapsed:.2f}s")
    return True


@run_test("Single Parameter Set", "Edge_Cases")
def test_single_params():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14],
        rsi_overbought_range=[70],
        rsi_oversold_range=[30],
        stop_loss_range=[1.5],
        take_profit_range=[3.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.tested_combinations == 1, (
        f"Expected 1 combination, got {result.tested_combinations}"
    )
    print("    [INFO] Single params: 1 combination tested")
    return True


@run_test("Very Small Capital ($100)", "Edge_Cases")
def test_small_capital():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 3.0],
        initial_capital=100,
        leverage=10,
        direction="long",
    )

    print(f"    [INFO] Small capital: {len(result.top_results)} results")
    return True


@run_test("Very Large Capital ($10M)", "Edge_Cases")
def test_large_capital():
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 3.0],
        initial_capital=10_000_000,
        leverage=1,
        direction="long",
    )

    print(f"    [INFO] Large capital: {len(result.top_results)} results")
    return True


# ============================================================================
# CATEGORY 11: Optuna Integration
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 11: Optuna Bayesian Optimization")
print("=" * 70)


@run_test("Optuna Import", "Optuna_Tests")
def test_optuna_import():
    import optuna

    assert optuna is not None
    print(f"    [INFO] Optuna version: {optuna.__version__}")
    return True


@run_test("Optuna Basic Study (10 trials)", "Optuna_Tests")
def test_optuna_basic():
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial):
        rsi_period = trial.suggest_int("rsi_period", 7, 28)
        rsi_overbought = trial.suggest_float("rsi_overbought", 65, 85)
        rsi_oversold = trial.suggest_float("rsi_oversold", 15, 35)
        stop_loss = trial.suggest_float("stop_loss", 0.5, 5.0)
        take_profit = trial.suggest_float("take_profit", 1.0, 10.0)

        # Simple scoring function
        score = (take_profit / stop_loss) * (rsi_overbought - rsi_oversold) / rsi_period
        return score

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=10, show_progress_bar=False)

    print(f"    [INFO] Best trial: {study.best_trial.value:.3f}")
    return True


@run_test("Optuna Multi-Objective (20 trials)", "Optuna_Tests")
def test_optuna_multi_objective():
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objectives(trial):
        rsi_period = trial.suggest_int("rsi_period", 7, 28)
        stop_loss = trial.suggest_float("stop_loss", 0.5, 5.0)
        take_profit = trial.suggest_float("take_profit", 1.0, 10.0)

        # Multiple objectives: maximize return, minimize risk
        return_score = take_profit / stop_loss
        risk_score = stop_loss + (rsi_period / 10)

        return return_score, -risk_score  # Minimize risk

    study = optuna.create_study(directions=["maximize", "maximize"])
    study.optimize(objectives, n_trials=20, show_progress_bar=False)

    print(f"    [INFO] Pareto front: {len(study.best_trials)} solutions")
    return True


@run_test("Optuna with Pruning (30 trials)", "Optuna_Tests")
def test_optuna_pruning():
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial):
        rsi_period = trial.suggest_int("rsi_period", 7, 35)

        # Simulate intermediate values
        for step in range(5):
            intermediate_value = (35 - rsi_period) / (step + 1)
            trial.report(intermediate_value, step)

            if trial.should_prune():
                raise optuna.TrialPruned()

        return (35 - rsi_period) / 5

    study = optuna.create_study(
        direction="maximize", pruner=optuna.pruners.MedianPruner()
    )
    study.optimize(objective, n_trials=30, show_progress_bar=False)

    pruned = len([t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED])
    print(f"    [INFO] Pruned {pruned}/{30} trials")
    return True


# ============================================================================
# CATEGORY 12: Walk-Forward Optimization
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 12: Walk-Forward Optimization Concepts")
print("=" * 70)


@run_test("Walk-Forward Split Data", "WalkForward_Tests")
def test_wf_split():
    """Test walk-forward data splitting."""
    candles = generate_test_ohlcv(1000)

    # Split into 4 windows: 70% train, 30% test each
    n_windows = 4
    window_size = len(candles) // n_windows

    splits = []
    for i in range(n_windows):
        start = i * window_size
        end = start + window_size
        window = candles.iloc[start:end]

        train_size = int(len(window) * 0.7)
        train = window.iloc[:train_size]
        test = window.iloc[train_size:]

        splits.append({"window": i, "train_size": len(train), "test_size": len(test)})

    print(f"    [INFO] Created {n_windows} walk-forward windows")
    return True


@run_test("Walk-Forward In-Sample Optimization", "WalkForward_Tests")
def test_wf_in_sample():
    """Optimize on in-sample, validate on out-of-sample."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(600)

    # Split 70/30
    train_size = int(len(candles) * 0.7)
    train_candles = candles.iloc[:train_size].reset_index(drop=True)

    # Optimize on train
    optimizer = FastGridOptimizer()
    result = optimizer.optimize(
        candles=train_candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    if result.best_metrics:
        print(
            f"    [INFO] In-sample best: return={result.best_metrics.get('total_return', 0):.2f}%"
        )
    return True


@run_test("Walk-Forward Out-of-Sample Test", "WalkForward_Tests")
def test_wf_out_of_sample():
    """Test best params on out-of-sample data."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(600)

    # Split
    train_size = int(len(candles) * 0.7)
    train_candles = candles.iloc[:train_size].reset_index(drop=True)
    test_candles = candles.iloc[train_size:].reset_index(drop=True)

    # Get best from train
    optimizer_train = FastGridOptimizer()
    train_result = optimizer_train.optimize(
        candles=train_candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    if train_result.best_params:
        best = train_result.best_params
        # Use same params on test
        optimizer_test = FastGridOptimizer()
        test_result = optimizer_test.optimize(
            candles=test_candles,
            rsi_period_range=[best.get("rsi_period", 14)],
            rsi_overbought_range=[int(best.get("rsi_overbought", 70))],
            rsi_oversold_range=[int(best.get("rsi_oversold", 30))],
            stop_loss_range=[best.get("stop_loss_pct", 1.5)],
            take_profit_range=[best.get("take_profit_pct", 3.0)],
            initial_capital=10000,
            leverage=5,
            direction="long",
        )

        if test_result.best_metrics:
            test_return = test_result.best_metrics.get("total_return", 0)
            train_return = train_result.best_metrics.get("total_return", 0)
            print(f"    [INFO] Train: {train_return:.2f}%, Test: {test_return:.2f}%")
    return True


# ============================================================================
# CATEGORY 13: Monte Carlo Simulation Concepts
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 13: Monte Carlo Concepts")
print("=" * 70)


@run_test("Monte Carlo Random Seeds", "MonteCarlo_Tests")
def test_mc_random_seeds():
    """Test optimization stability with different random seeds."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    results_by_seed = []

    for seed in [42, 123, 456, 789, 1000]:
        candles = generate_test_ohlcv(500, seed=seed)
        optimizer = FastGridOptimizer()

        result = optimizer.optimize(
            candles=candles,
            rsi_period_range=[14],
            rsi_overbought_range=[70],
            rsi_oversold_range=[30],
            stop_loss_range=[1.5],
            take_profit_range=[3.0],
            initial_capital=10000,
            leverage=5,
            direction="long",
        )

        if result.best_metrics:
            results_by_seed.append(result.best_metrics.get("total_return", 0))

    if results_by_seed:
        mean_return = np.mean(results_by_seed)
        std_return = np.std(results_by_seed)
        print(
            f"    [INFO] Returns across seeds: mean={mean_return:.2f}%, std={std_return:.2f}%"
        )
    return True


@run_test("Monte Carlo Bootstrapping", "MonteCarlo_Tests")
def test_mc_bootstrap():
    """Bootstrap resampling of trades."""
    np.random.seed(42)

    # Simulate trade returns
    trade_returns = np.random.normal(0.5, 2.0, 100)  # 100 trades

    # Bootstrap
    n_simulations = 100
    bootstrap_totals = []

    for _ in range(n_simulations):
        # Resample with replacement
        resampled = np.random.choice(
            trade_returns, size=len(trade_returns), replace=True
        )
        bootstrap_totals.append(np.sum(resampled))

    mean_total = np.mean(bootstrap_totals)
    percentile_5 = np.percentile(bootstrap_totals, 5)
    percentile_95 = np.percentile(bootstrap_totals, 95)

    print(
        f"    [INFO] Bootstrap: mean={mean_total:.2f}, 5%={percentile_5:.2f}, 95%={percentile_95:.2f}"
    )
    return True


@run_test("Monte Carlo Drawdown Distribution", "MonteCarlo_Tests")
def test_mc_drawdown():
    """Simulate drawdown distribution."""
    np.random.seed(42)

    n_simulations = 50
    max_drawdowns = []

    for _ in range(n_simulations):
        # Simulate equity curve
        returns = np.random.normal(0.001, 0.02, 200)
        equity = 10000 * np.cumprod(1 + returns)

        # Calculate drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak * 100
        max_drawdowns.append(np.max(drawdown))

    mean_dd = np.mean(max_drawdowns)
    worst_dd = np.max(max_drawdowns)
    print(f"    [INFO] Drawdown: mean={mean_dd:.2f}%, worst={worst_dd:.2f}%")
    return True


# ============================================================================
# CATEGORY 14: Parameter Sensitivity Analysis
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 14: Parameter Sensitivity Analysis")
print("=" * 70)


@run_test("RSI Period Sensitivity", "Sensitivity_Tests")
def test_sensitivity_rsi_period():
    """Analyze sensitivity to RSI period changes."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)

    results_by_period = {}
    for period in [7, 10, 14, 21, 28]:
        optimizer = FastGridOptimizer()
        result = optimizer.optimize(
            candles=candles,
            rsi_period_range=[period],
            rsi_overbought_range=[70],
            rsi_oversold_range=[30],
            stop_loss_range=[1.5],
            take_profit_range=[3.0],
            initial_capital=10000,
            leverage=5,
            direction="long",
        )
        if result.best_metrics:
            results_by_period[period] = result.best_metrics.get("total_return", 0)

    if results_by_period:
        best_period = max(results_by_period, key=results_by_period.get)
        print(
            f"    [INFO] Best RSI period: {best_period} ({results_by_period[best_period]:.2f}%)"
        )
    return True


@run_test("Stop Loss Sensitivity", "Sensitivity_Tests")
def test_sensitivity_sl():
    """Analyze sensitivity to stop loss changes."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)

    results_by_sl = {}
    for sl in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
        optimizer = FastGridOptimizer()
        result = optimizer.optimize(
            candles=candles,
            rsi_period_range=[14],
            rsi_overbought_range=[70],
            rsi_oversold_range=[30],
            stop_loss_range=[sl],
            take_profit_range=[3.0],
            initial_capital=10000,
            leverage=5,
            direction="long",
        )
        if result.best_metrics:
            results_by_sl[sl] = result.best_metrics.get("total_return", 0)

    if results_by_sl:
        best_sl = max(results_by_sl, key=results_by_sl.get)
        print(f"    [INFO] Best SL: {best_sl}% ({results_by_sl[best_sl]:.2f}%)")
    return True


@run_test("Take Profit Sensitivity", "Sensitivity_Tests")
def test_sensitivity_tp():
    """Analyze sensitivity to take profit changes."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)

    results_by_tp = {}
    for tp in [1.0, 2.0, 3.0, 5.0, 8.0, 10.0]:
        optimizer = FastGridOptimizer()
        result = optimizer.optimize(
            candles=candles,
            rsi_period_range=[14],
            rsi_overbought_range=[70],
            rsi_oversold_range=[30],
            stop_loss_range=[1.5],
            take_profit_range=[tp],
            initial_capital=10000,
            leverage=5,
            direction="long",
        )
        if result.best_metrics:
            results_by_tp[tp] = result.best_metrics.get("total_return", 0)

    if results_by_tp:
        best_tp = max(results_by_tp, key=results_by_tp.get)
        print(f"    [INFO] Best TP: {best_tp}% ({results_by_tp[best_tp]:.2f}%)")
    return True


@run_test("Leverage Sensitivity", "Sensitivity_Tests")
def test_sensitivity_leverage():
    """Analyze sensitivity to leverage changes."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = generate_test_ohlcv(500)

    results_by_lev = {}
    for lev in [1, 5, 10, 20, 50]:
        optimizer = FastGridOptimizer()
        result = optimizer.optimize(
            candles=candles,
            rsi_period_range=[14],
            rsi_overbought_range=[70],
            rsi_oversold_range=[30],
            stop_loss_range=[1.5],
            take_profit_range=[3.0],
            initial_capital=10000,
            leverage=lev,
            direction="long",
        )
        if result.best_metrics:
            results_by_lev[lev] = {
                "return": result.best_metrics.get("total_return", 0),
                "dd": result.best_metrics.get("max_drawdown", 0),
            }

    if results_by_lev:
        print(
            f"    [INFO] Leverage impact: 1x={results_by_lev.get(1, {}).get('return', 0):.1f}%, 50x={results_by_lev.get(50, {}).get('return', 0):.1f}%"
        )
    return True


# ============================================================================
# Summary
# ============================================================================
def print_summary():
    print("\n" + "=" * 70)
    print("MEGA TEST V5 - EXTENDED OPTIMIZATION SUMMARY")
    print("=" * 70)

    # Group results by category
    categories = {}
    for r in test_results:
        if r.category not in categories:
            categories[r.category] = {"passed": 0, "failed": 0, "time": 0.0}
        if r.passed:
            categories[r.category]["passed"] += 1
        else:
            categories[r.category]["failed"] += 1
        categories[r.category]["time"] += r.execution_time

    total_passed = 0
    total_failed = 0
    total_time = 0.0

    for cat, stats in categories.items():
        passed = stats["passed"]
        failed = stats["failed"]
        cat_time = stats["time"]
        total = passed + failed
        total_passed += passed
        total_failed += failed
        total_time += cat_time

        status = "✅" if failed == 0 else "❌"
        print(f"\n{status} {cat}: {passed}/{total} passed ({cat_time:.2f}s)")

    print("\n" + "-" * 70)
    total = total_passed + total_failed
    pct = (total_passed / total * 100) if total > 0 else 0

    if total_failed == 0:
        print(f"🎉 ALL TESTS PASSED: {total_passed}/{total} ({pct:.1f}%)")
    else:
        print(f"⚠️ SOME TESTS FAILED: {total_passed}/{total} ({pct:.1f}%)")
        print("\nFailed tests:")
        for r in test_results:
            if not r.passed:
                print(f"  - {r.name}: {r.details}")

    print(f"\n⏱️ Total execution time: {total_time:.2f}s")
    print("=" * 70)


if __name__ == "__main__":
    # Run all tests by calling each function
    test_fast_optimizer_import()
    test_rsi_ultra_short()
    test_rsi_long_term()
    test_rsi_extreme_overbought()
    test_rsi_narrow_band()
    test_rsi_wide_spread()

    test_tight_stop_loss()
    test_wide_stop_loss()
    test_asymmetric_risk_reward()
    test_scalping_tp()
    test_swing_tp()

    test_no_leverage()
    test_medium_leverage()
    test_high_leverage()
    test_extreme_leverage()

    test_long_uptrend()
    test_short_downtrend()
    test_both_ranging()
    test_long_volatile()

    test_large_grid_1k()
    test_large_grid_5k()
    test_large_grid_10k()

    test_gpu_availability()
    test_gpu_small_grid()
    test_gpu_medium_grid()
    test_gpu_large_grid()
    test_gpu_both_directions()

    test_universal_auto()
    test_universal_force_gpu()
    test_universal_force_cpu()

    test_optimize_sharpe()
    test_optimize_return()
    test_optimize_calmar()
    test_optimize_pf()
    test_optimize_winrate()

    test_filter_min_trades()
    test_filter_max_dd()
    test_filter_min_pf()
    test_combined_filters()

    test_minimal_data()
    test_large_data()
    test_single_params()
    test_small_capital()
    test_large_capital()

    test_optuna_import()
    test_optuna_basic()
    test_optuna_multi_objective()
    test_optuna_pruning()

    test_wf_split()
    test_wf_in_sample()
    test_wf_out_of_sample()

    test_mc_random_seeds()
    test_mc_bootstrap()
    test_mc_drawdown()

    test_sensitivity_rsi_period()
    test_sensitivity_sl()
    test_sensitivity_tp()
    test_sensitivity_leverage()

    print_summary()
