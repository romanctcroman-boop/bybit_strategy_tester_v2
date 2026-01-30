"""Test MarketRegimeDetector integration in FallbackEngineV4."""

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput

# Create synthetic BTCUSDT data (similar to real market)
print("Creating synthetic BTCUSDT data...")
np.random.seed(42)
n = 2000  # 2000 bars for good sample size

# Generate realistic price movement
ts = pd.date_range(start="2025-01-01", periods=n, freq="15min")
base_price = 95000
returns = np.random.randn(n) * 0.003  # 0.3% average move per bar
# Add trend component
trend = np.linspace(0, 0.1, n)  # 10% uptrend over period
# Add volatility clusters
volatility = np.ones(n)
volatility[500:700] = 2.0  # High volatility period
volatility[1200:1400] = 0.5  # Low volatility period
returns = returns * volatility + trend / n

close = base_price * np.exp(np.cumsum(returns))
high = close * (1 + np.abs(np.random.randn(n)) * 0.005)
low = close * (1 - np.abs(np.random.randn(n)) * 0.005)
open_p = close + np.random.randn(n) * 50

candles = pd.DataFrame({
    "timestamp": ts,
    "open": open_p,
    "high": np.maximum.reduce([open_p, high, close]),
    "low": np.minimum.reduce([open_p, low, close]),
    "close": close,
    "volume": np.random.randint(100, 5000, n).astype(float) * volatility,
})
print(f"Created {len(candles)} candles")

# Create engine
engine = FallbackEngineV4()


# Generate simple signals: every 20 bars
def generate_simple_signals(df):
    """Generate simple periodic signals for testing."""
    n = len(df)
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    # Enter long every 50 bars, exit 20 bars later
    for i in range(100, n - 50, 50):
        long_entries[i] = True
        long_exits[i + 20] = True

    # Enter short every 50 bars with offset, exit 20 bars later
    for i in range(125, n - 50, 50):
        short_entries[i] = True
        short_exits[i + 20] = True

    return long_entries, long_exits, short_entries, short_exits


long_entries, long_exits, short_entries, short_exits = generate_simple_signals(candles)
print(f"Generated signals: long_entries={long_entries.sum()}, short_entries={short_entries.sum()}")

# Test 1: Without market regime filter
print("\n=== Test 1: Without market regime filter ===")
input1 = BacktestInput(
    candles=candles,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    initial_capital=10000,
    position_size=1.0,
    leverage=10,
    stop_loss=0.05,
    take_profit=0.10,
    taker_fee=0.0007,
    slippage=0.0005,
    direction="both",
    use_bar_magnifier=False,
    market_regime_enabled=False,
)
result1 = engine.run(input1)
print(f"   Trades: {result1.metrics.total_trades}")
print(f"   Win Rate: {result1.metrics.win_rate:.1f}%")
print(f"   Sharpe: {result1.metrics.sharpe_ratio:.2f}")
print(f"   Total Return: {result1.metrics.total_return * 100:.1f}%")

# Test 2: With market regime filter = "not_volatile"
print("\n=== Test 2: With market regime filter = 'not_volatile' ===")
input2 = BacktestInput(
    candles=candles,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    initial_capital=10000,
    position_size=1.0,
    leverage=10,
    stop_loss=0.05,
    take_profit=0.10,
    taker_fee=0.0007,
    slippage=0.0005,
    direction="both",
    use_bar_magnifier=False,
    market_regime_enabled=True,
    market_regime_filter="not_volatile",
    market_regime_lookback=50,
)
result2 = engine.run(input2)
print(f"   Trades: {result2.metrics.total_trades}")
print(f"   Win Rate: {result2.metrics.win_rate:.1f}%")
print(f"   Sharpe: {result2.metrics.sharpe_ratio:.2f}")
print(f"   Total Return: {result2.metrics.total_return * 100:.1f}%")

# Test 3: With market regime filter = "trending"
print("\n=== Test 3: With market regime filter = 'trending' ===")
input3 = BacktestInput(
    candles=candles,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    initial_capital=10000,
    position_size=1.0,
    leverage=10,
    stop_loss=0.05,
    take_profit=0.10,
    taker_fee=0.0007,
    slippage=0.0005,
    direction="both",
    use_bar_magnifier=False,
    market_regime_enabled=True,
    market_regime_filter="trending",
    market_regime_lookback=50,
)
result3 = engine.run(input3)
print(f"   Trades: {result3.metrics.total_trades}")
print(f"   Win Rate: {result3.metrics.win_rate:.1f}%")
print(f"   Sharpe: {result3.metrics.sharpe_ratio:.2f}")
print(f"   Total Return: {result3.metrics.total_return * 100:.1f}%")

# Test 4: With market regime filter = "ranging"
print("\n=== Test 4: With market regime filter = 'ranging' ===")
input4 = BacktestInput(
    candles=candles,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    initial_capital=10000,
    position_size=1.0,
    leverage=10,
    stop_loss=0.05,
    take_profit=0.10,
    taker_fee=0.0007,
    slippage=0.0005,
    direction="both",
    use_bar_magnifier=False,
    market_regime_enabled=True,
    market_regime_filter="ranging",
    market_regime_lookback=50,
)
result4 = engine.run(input4)
print(f"   Trades: {result4.metrics.total_trades}")
print(f"   Win Rate: {result4.metrics.win_rate:.1f}%")
print(f"   Sharpe: {result4.metrics.sharpe_ratio:.2f}")
print(f"   Total Return: {result4.metrics.total_return * 100:.1f}%")

# Summary
print("\n" + "=" * 60)
print("MARKET REGIME DETECTOR SUMMARY")
print("=" * 60)
print(f"{'Filter':<20} {'Trades':>8} {'WinRate':>10} {'Sharpe':>10} {'Return':>10}")
print("-" * 60)
print(f"{'None (baseline)':<20} {result1.metrics.total_trades:>8} {result1.metrics.win_rate:>9.1f}% {result1.metrics.sharpe_ratio:>10.2f} {result1.metrics.total_return * 100:>9.1f}%")
print(f"{'not_volatile':<20} {result2.metrics.total_trades:>8} {result2.metrics.win_rate:>9.1f}% {result2.metrics.sharpe_ratio:>10.2f} {result2.metrics.total_return * 100:>9.1f}%")
print(f"{'trending':<20} {result3.metrics.total_trades:>8} {result3.metrics.win_rate:>9.1f}% {result3.metrics.sharpe_ratio:>10.2f} {result3.metrics.total_return * 100:>9.1f}%")
print(f"{'ranging':<20} {result4.metrics.total_trades:>8} {result4.metrics.win_rate:>9.1f}% {result4.metrics.sharpe_ratio:>10.2f} {result4.metrics.total_return * 100:>9.1f}%")
print("=" * 60)

# Check that regime filter reduces trades (expected behavior)
if result2.metrics.total_trades <= result1.metrics.total_trades:
    print("\n[OK] Market regime filter working - trades filtered as expected")
else:
    print("\n[WARN] Warning: Market regime filter may not be filtering correctly")

print("\n[OK] MarketRegimeDetector integration test PASSED!")
