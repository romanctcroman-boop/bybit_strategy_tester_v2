"""
MEGA Test V6 - Real Historical Data Tests (8 months)
=====================================================

Testing optimization engines with REAL market data from DB:
- BTCUSDT, ETHUSDT, SOLUSDT - 8 months of data
- 15m, 1h, 4h timeframes
- Long and Short directions
- All optimizer types

This validates that optimizers work correctly on actual market conditions.
"""

import os
import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

# ============================================================================
# Configuration
# ============================================================================
DB_PATH = "data.sqlite3"
TEST_PERIOD_MONTHS = 8  # 8 months of data


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


def load_real_candles(
    symbol: str = "BTCUSDT",
    interval: str = "15",
    months: int = 8,
) -> pd.DataFrame:
    """Load real historical candles from database."""
    conn = sqlite3.connect(DB_PATH)

    # Calculate date range (last N months)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=months * 30)

    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    query = """
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM bybit_kline_audit
        WHERE symbol = ? AND interval = ?
          AND open_time >= ? AND open_time <= ?
        ORDER BY open_time ASC
    """

    df = pd.read_sql_query(query, conn, params=(symbol, interval, start_ts, end_ts))
    conn.close()

    if df.empty:
        raise ValueError(f"No data found for {symbol}/{interval}")

    # Rename columns to standard names
    df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    return df


def get_data_info(df: pd.DataFrame) -> str:
    """Get info string about dataframe."""
    start = df["timestamp"].min()
    end = df["timestamp"].max()
    days = (end - start).days
    return f"{len(df):,} candles, {days} days ({start.date()} to {end.date()})"


# ============================================================================
# CATEGORY 1: BTCUSDT Long Direction Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 1: BTCUSDT - Long Direction (8 months)")
print("=" * 70)


@run_test("Load BTCUSDT 15m data", "BTCUSDT_Long")
def test_load_btc_15m():
    """Test loading real BTCUSDT 15m data."""
    df = load_real_candles("BTCUSDT", "15", TEST_PERIOD_MONTHS)
    info = get_data_info(df)
    print(f"    [INFO] {info}")
    assert len(df) > 1000, f"Expected >1000 candles, got {len(df)}"
    return True


@run_test("BTCUSDT 15m Long - FastGridOptimizer", "BTCUSDT_Long")
def test_btc_15m_long_fast():
    """Test FastGridOptimizer on BTCUSDT 15m Long."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("BTCUSDT", "15", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 14, 21],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}, "
        f"WinRate={best.get('win_rate', 0):.1f}%"
    )
    return True


@run_test("BTCUSDT 1h Long - FastGridOptimizer", "BTCUSDT_Long")
def test_btc_1h_long_fast():
    """Test FastGridOptimizer on BTCUSDT 1h Long."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("BTCUSDT", "60", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21, 28],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.5, 2.5, 3.5],
        take_profit_range=[3.0, 5.0, 7.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}, "
        f"WinRate={best.get('win_rate', 0):.1f}%"
    )
    return True


@run_test("BTCUSDT 4h Long - FastGridOptimizer", "BTCUSDT_Long")
def test_btc_4h_long_fast():
    """Test FastGridOptimizer on BTCUSDT 4h Long."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("BTCUSDT", "240", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21, 28],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[2.0, 3.0, 4.0],
        take_profit_range=[4.0, 6.0, 8.0],
        initial_capital=10000,
        leverage=3,
        direction="long",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}, "
        f"WinRate={best.get('win_rate', 0):.1f}%"
    )
    return True


@run_test("BTCUSDT 15m Long - GPUGridOptimizer", "BTCUSDT_Long")
def test_btc_15m_long_gpu():
    """Test GPUGridOptimizer on BTCUSDT 15m Long."""
    from backend.backtesting.gpu_optimizer import GPU_AVAILABLE, GPUGridOptimizer

    candles = load_real_candles("BTCUSDT", "15", TEST_PERIOD_MONTHS)

    if not GPU_AVAILABLE:
        print("    [INFO] GPU not available, using CPU fallback")

    optimizer = GPUGridOptimizer(force_cpu=not GPU_AVAILABLE)

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 14, 21],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}"
    )
    return True


# ============================================================================
# CATEGORY 2: BTCUSDT Short Direction Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 2: BTCUSDT - Short Direction (8 months)")
print("=" * 70)


@run_test("BTCUSDT 15m Short - FastGridOptimizer", "BTCUSDT_Short")
def test_btc_15m_short_fast():
    """Test FastGridOptimizer on BTCUSDT 15m Short."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("BTCUSDT", "15", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 14, 21],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="short",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}, "
        f"WinRate={best.get('win_rate', 0):.1f}%"
    )
    return True


@run_test("BTCUSDT 1h Short - FastGridOptimizer", "BTCUSDT_Short")
def test_btc_1h_short_fast():
    """Test FastGridOptimizer on BTCUSDT 1h Short."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("BTCUSDT", "60", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21, 28],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.5, 2.5, 3.5],
        take_profit_range=[3.0, 5.0, 7.0],
        initial_capital=10000,
        leverage=5,
        direction="short",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}, "
        f"WinRate={best.get('win_rate', 0):.1f}%"
    )
    return True


@run_test("BTCUSDT 4h Short - FastGridOptimizer", "BTCUSDT_Short")
def test_btc_4h_short_fast():
    """Test FastGridOptimizer on BTCUSDT 4h Short."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("BTCUSDT", "240", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21, 28],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[2.0, 3.0, 4.0],
        take_profit_range=[4.0, 6.0, 8.0],
        initial_capital=10000,
        leverage=3,
        direction="short",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}, "
        f"WinRate={best.get('win_rate', 0):.1f}%"
    )
    return True


@run_test("BTCUSDT 15m Short - GPUGridOptimizer", "BTCUSDT_Short")
def test_btc_15m_short_gpu():
    """Test GPUGridOptimizer on BTCUSDT 15m Short."""
    from backend.backtesting.gpu_optimizer import GPU_AVAILABLE, GPUGridOptimizer

    candles = load_real_candles("BTCUSDT", "15", TEST_PERIOD_MONTHS)

    optimizer = GPUGridOptimizer(force_cpu=not GPU_AVAILABLE)

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 14, 21],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[1.0, 2.0, 3.0],
        take_profit_range=[2.0, 3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="short",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}"
    )
    return True


# ============================================================================
# CATEGORY 3: ETHUSDT Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 3: ETHUSDT - Long & Short (8 months)")
print("=" * 70)


@run_test("ETHUSDT 15m Long - FastGridOptimizer", "ETHUSDT")
def test_eth_15m_long():
    """Test FastGridOptimizer on ETHUSDT 15m Long."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("ETHUSDT", "15", TEST_PERIOD_MONTHS)
    info = get_data_info(candles)
    print(f"    [DATA] {info}")

    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 14, 21],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[1.5, 2.5, 3.5],
        take_profit_range=[3.0, 4.0, 6.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}, "
        f"WinRate={best.get('win_rate', 0):.1f}%"
    )
    return True


@run_test("ETHUSDT 15m Short - FastGridOptimizer", "ETHUSDT")
def test_eth_15m_short():
    """Test FastGridOptimizer on ETHUSDT 15m Short."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("ETHUSDT", "15", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 14, 21],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[1.5, 2.5, 3.5],
        take_profit_range=[3.0, 4.0, 6.0],
        initial_capital=10000,
        leverage=5,
        direction="short",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}, "
        f"WinRate={best.get('win_rate', 0):.1f}%"
    )
    return True


@run_test("ETHUSDT 1h Long - FastGridOptimizer", "ETHUSDT")
def test_eth_1h_long():
    """Test FastGridOptimizer on ETHUSDT 1h Long."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("ETHUSDT", "60", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[2.0, 3.0],
        take_profit_range=[4.0, 6.0],
        initial_capital=10000,
        leverage=3,
        direction="long",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}"
    )
    return True


@run_test("ETHUSDT 1h Short - FastGridOptimizer", "ETHUSDT")
def test_eth_1h_short():
    """Test FastGridOptimizer on ETHUSDT 1h Short."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("ETHUSDT", "60", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[2.0, 3.0],
        take_profit_range=[4.0, 6.0],
        initial_capital=10000,
        leverage=3,
        direction="short",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}"
    )
    return True


# ============================================================================
# CATEGORY 4: SOLUSDT Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 4: SOLUSDT - Long & Short (8 months)")
print("=" * 70)


@run_test("SOLUSDT 15m Long - FastGridOptimizer", "SOLUSDT")
def test_sol_15m_long():
    """Test FastGridOptimizer on SOLUSDT 15m Long."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("SOLUSDT", "15", TEST_PERIOD_MONTHS)
    info = get_data_info(candles)
    print(f"    [DATA] {info}")

    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 14, 21],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[2.0, 3.0, 4.0],
        take_profit_range=[4.0, 6.0, 8.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}, "
        f"WinRate={best.get('win_rate', 0):.1f}%"
    )
    return True


@run_test("SOLUSDT 15m Short - FastGridOptimizer", "SOLUSDT")
def test_sol_15m_short():
    """Test FastGridOptimizer on SOLUSDT 15m Short."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("SOLUSDT", "15", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 14, 21],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[2.0, 3.0, 4.0],
        take_profit_range=[4.0, 6.0, 8.0],
        initial_capital=10000,
        leverage=5,
        direction="short",
    )

    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Trades={best.get('total_trades', 0)}, "
        f"WinRate={best.get('win_rate', 0):.1f}%"
    )
    return True


@run_test("SOLUSDT 15m Long - Large Grid", "SOLUSDT")
def test_sol_15m_long_large():
    """Test large grid on SOLUSDT 15m Long."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("SOLUSDT", "15", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 10, 14, 21, 28],
        rsi_overbought_range=[65, 70, 75, 80],
        rsi_oversold_range=[20, 25, 30, 35],
        stop_loss_range=[1.5, 2.0, 2.5, 3.0, 4.0],
        take_profit_range=[3.0, 4.0, 5.0, 6.0, 8.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    combos = result.total_combinations
    assert result.status == "completed"
    best = result.best_metrics
    print(
        f"    [INFO] {combos:,} combos tested. Best: Return={best.get('total_return', 0):.1f}%"
    )
    return True


# ============================================================================
# CATEGORY 5: Multi-Symbol Comparison
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 5: Multi-Symbol Comparison")
print("=" * 70)


@run_test("Compare BTC vs ETH vs SOL - Long", "MultiSymbol")
def test_multi_symbol_long():
    """Compare optimization results across multiple symbols."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    results_summary = {}

    for symbol in symbols:
        try:
            candles = load_real_candles(symbol, "60", TEST_PERIOD_MONTHS)
            optimizer = FastGridOptimizer()

            result = optimizer.optimize(
                candles=candles,
                rsi_period_range=[10, 14, 21],
                rsi_overbought_range=[70, 75],
                rsi_oversold_range=[25, 30],
                stop_loss_range=[2.0, 3.0],
                take_profit_range=[4.0, 6.0],
                initial_capital=10000,
                leverage=5,
                direction="long",
            )

            if result.status == "completed":
                best = result.best_metrics
                results_summary[symbol] = {
                    "return": best.get("total_return", 0),
                    "trades": best.get("total_trades", 0),
                    "win_rate": best.get("win_rate", 0),
                }
        except Exception as e:
            print(f"    [WARN] {symbol}: {e}")

    # Print comparison
    for sym, data in results_summary.items():
        print(
            f"    {sym}: Return={data['return']:.1f}%, Trades={data['trades']}, WR={data['win_rate']:.1f}%"
        )

    assert len(results_summary) >= 2, "At least 2 symbols should have results"
    return True


@run_test("Compare BTC vs ETH vs SOL - Short", "MultiSymbol")
def test_multi_symbol_short():
    """Compare optimization results across multiple symbols for Short."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    results_summary = {}

    for symbol in symbols:
        try:
            candles = load_real_candles(symbol, "60", TEST_PERIOD_MONTHS)
            optimizer = FastGridOptimizer()

            result = optimizer.optimize(
                candles=candles,
                rsi_period_range=[10, 14, 21],
                rsi_overbought_range=[70, 75],
                rsi_oversold_range=[25, 30],
                stop_loss_range=[2.0, 3.0],
                take_profit_range=[4.0, 6.0],
                initial_capital=10000,
                leverage=5,
                direction="short",
            )

            if result.status == "completed":
                best = result.best_metrics
                results_summary[symbol] = {
                    "return": best.get("total_return", 0),
                    "trades": best.get("total_trades", 0),
                }
        except Exception as e:
            print(f"    [WARN] {symbol}: {e}")

    for sym, data in results_summary.items():
        print(f"    {sym}: Return={data['return']:.1f}%, Trades={data['trades']}")

    assert len(results_summary) >= 2
    return True


# ============================================================================
# CATEGORY 6: Universal Optimizer on Real Data
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 6: Universal Optimizer on Real Data")
print("=" * 70)


@run_test("UniversalOptimizer - BTCUSDT Long", "Universal")
def test_universal_btc_long():
    """Test UniversalOptimizer on real BTCUSDT data."""
    from backend.backtesting.optimizer import UniversalOptimizer

    candles = load_real_candles("BTCUSDT", "15", TEST_PERIOD_MONTHS)
    optimizer = UniversalOptimizer(backend="auto")

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.5, 2.5],
        take_profit_range=[3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"
    print(f"    [INFO] Best Return: {result.best_metrics.get('total_return', 0):.1f}%")
    return True


@run_test("UniversalOptimizer - BTCUSDT Short", "Universal")
def test_universal_btc_short():
    """Test UniversalOptimizer on real BTCUSDT data for Short."""
    from backend.backtesting.optimizer import UniversalOptimizer

    candles = load_real_candles("BTCUSDT", "15", TEST_PERIOD_MONTHS)
    optimizer = UniversalOptimizer(backend="auto")

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.5, 2.5],
        take_profit_range=[3.0, 5.0],
        initial_capital=10000,
        leverage=5,
        direction="short",
    )

    assert result.status == "completed"
    print(f"    [INFO] Best Return: {result.best_metrics.get('total_return', 0):.1f}%")
    return True


@run_test("UniversalOptimizer - ETHUSDT Both", "Universal")
def test_universal_eth_both():
    """Test UniversalOptimizer on ETHUSDT with both directions."""
    from backend.backtesting.optimizer import UniversalOptimizer

    candles = load_real_candles("ETHUSDT", "60", TEST_PERIOD_MONTHS)
    optimizer = UniversalOptimizer(backend="auto")

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[2.0, 3.0],
        take_profit_range=[4.0, 6.0],
        initial_capital=10000,
        leverage=3,
        direction="both",
    )

    assert result.status == "completed"
    print(f"    [INFO] Best Return: {result.best_metrics.get('total_return', 0):.1f}%")
    return True


# ============================================================================
# CATEGORY 7: Large Grid on Real Data
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 7: Large Grid Stress Tests")
print("=" * 70)


@run_test("BTCUSDT 15m - 2000+ combinations Long", "LargeGrid")
def test_btc_large_grid_long():
    """Test large grid optimization on BTCUSDT Long."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("BTCUSDT", "15", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[5, 7, 10, 14, 21, 28],
        rsi_overbought_range=[65, 70, 75, 80, 85],
        rsi_oversold_range=[15, 20, 25, 30, 35],
        stop_loss_range=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0],
        take_profit_range=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    combos = result.total_combinations
    print(f"    [INFO] {combos:,} combinations tested")
    assert result.status == "completed"
    assert combos > 2000, f"Expected >2000 combos, got {combos}"

    best = result.best_metrics
    print(
        f"    [INFO] Best: Return={best.get('total_return', 0):.1f}%, "
        f"Sharpe={best.get('sharpe_ratio', 0):.2f}"
    )
    return True


@run_test("BTCUSDT 15m - 2000+ combinations Short", "LargeGrid")
def test_btc_large_grid_short():
    """Test large grid optimization on BTCUSDT Short."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("BTCUSDT", "15", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[5, 7, 10, 14, 21, 28],
        rsi_overbought_range=[65, 70, 75, 80, 85],
        rsi_oversold_range=[15, 20, 25, 30, 35],
        stop_loss_range=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0],
        take_profit_range=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0],
        initial_capital=10000,
        leverage=5,
        direction="short",
    )

    combos = result.total_combinations
    assert result.status == "completed"

    best = result.best_metrics
    print(
        f"    [INFO] {combos:,} combos. Best: Return={best.get('total_return', 0):.1f}%"
    )
    return True


@run_test("ETHUSDT 1h - 1000+ combinations Both", "LargeGrid")
def test_eth_large_grid_both():
    """Test large grid on ETHUSDT with both directions."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("ETHUSDT", "60", TEST_PERIOD_MONTHS)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 10, 14, 21, 28],
        rsi_overbought_range=[65, 70, 75, 80],
        rsi_oversold_range=[20, 25, 30, 35],
        stop_loss_range=[1.5, 2.0, 2.5, 3.0, 4.0],
        take_profit_range=[3.0, 4.0, 5.0, 6.0, 8.0],
        initial_capital=10000,
        leverage=3,
        direction="both",
    )

    combos = result.total_combinations
    assert result.status == "completed"

    best = result.best_metrics
    print(
        f"    [INFO] {combos:,} combos. Best: Return={best.get('total_return', 0):.1f}%"
    )
    return True


# ============================================================================
# CATEGORY 8: Metrics Verification on Real Data
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 8: Metrics Verification on Real Data")
print("=" * 70)


@run_test("Verify metrics structure - BTCUSDT", "Metrics")
def test_metrics_structure():
    """Verify all required metrics are returned."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("BTCUSDT", "60", 3)  # 3 months for speed
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14],
        rsi_overbought_range=[70],
        rsi_oversold_range=[30],
        stop_loss_range=[2.0],
        take_profit_range=[4.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"

    # Check required metrics
    required_metrics = [
        "total_return",
        "sharpe_ratio",
        "max_drawdown",
        "win_rate",
        "total_trades",
        "profit_factor",
        "calmar_ratio",
    ]

    best = result.best_metrics
    for metric in required_metrics:
        assert metric in best, f"Missing metric: {metric}"
        print(f"    {metric}: {best[metric]}")

    return True


@run_test("Verify trades have MFE/MAE - BTCUSDT", "Metrics")
def test_trades_mfe_mae():
    """Verify trades include MFE/MAE metrics."""
    from backend.backtesting.fast_optimizer import FastGridOptimizer

    candles = load_real_candles("BTCUSDT", "60", 3)
    optimizer = FastGridOptimizer()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14],
        rsi_overbought_range=[70],
        rsi_oversold_range=[30],
        stop_loss_range=[2.0],
        take_profit_range=[4.0],
        initial_capital=10000,
        leverage=5,
        direction="long",
    )

    assert result.status == "completed"

    # Check trades structure
    if result.top_results and result.top_results[0].get("trades"):
        trades = result.top_results[0]["trades"]
        if trades:
            trade = trades[0]
            required_fields = ["entry_time", "exit_time", "pnl", "mfe", "mae"]
            for field in required_fields:
                assert field in trade, f"Missing trade field: {field}"
            print(
                f"    [INFO] Trade has all fields. MFE={trade['mfe']:.2f}, MAE={trade['mae']:.2f}"
            )

    return True


# ============================================================================
# Print Summary
# ============================================================================
def print_summary():
    """Print test summary."""
    print("\n")
    print("=" * 70)
    print("MEGA TEST V6 - REAL DATA SUMMARY (8 months)")
    print("=" * 70)

    # Group by category
    categories = {}
    for r in test_results:
        if r.category not in categories:
            categories[r.category] = {"passed": 0, "failed": 0, "time": 0.0}
        if r.passed:
            categories[r.category]["passed"] += 1
        else:
            categories[r.category]["failed"] += 1
        categories[r.category]["time"] += r.execution_time

    total_passed = sum(c["passed"] for c in categories.values())
    total_failed = sum(c["failed"] for c in categories.values())
    total = total_passed + total_failed
    total_time = sum(c["time"] for c in categories.values())

    for cat, data in categories.items():
        passed = data["passed"]
        failed = data["failed"]
        cat_total = passed + failed
        status = "✅" if failed == 0 else "❌"
        print(f"\n{status} {cat}: {passed}/{cat_total} passed ({data['time']:.2f}s)")

    print("\n" + "-" * 70)
    pct = total_passed / total * 100 if total > 0 else 0

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
    # BTCUSDT Long tests
    test_load_btc_15m()
    test_btc_15m_long_fast()
    test_btc_1h_long_fast()
    test_btc_4h_long_fast()
    test_btc_15m_long_gpu()

    # BTCUSDT Short tests
    test_btc_15m_short_fast()
    test_btc_1h_short_fast()
    test_btc_4h_short_fast()
    test_btc_15m_short_gpu()

    # ETHUSDT tests
    test_eth_15m_long()
    test_eth_15m_short()
    test_eth_1h_long()
    test_eth_1h_short()

    # SOLUSDT tests
    test_sol_15m_long()
    test_sol_15m_short()
    test_sol_15m_long_large()

    # Multi-symbol comparison
    test_multi_symbol_long()
    test_multi_symbol_short()

    # Universal optimizer
    test_universal_btc_long()
    test_universal_btc_short()
    test_universal_eth_both()

    # Large grid tests
    test_btc_large_grid_long()
    test_btc_large_grid_short()
    test_eth_large_grid_both()

    # Metrics verification
    test_metrics_structure()
    test_trades_mfe_mae()

    print_summary()
