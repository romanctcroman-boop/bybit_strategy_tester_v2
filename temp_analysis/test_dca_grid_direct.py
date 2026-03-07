"""Direct test of DCA grid filling logic - no RSI needed."""

import sys
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, "d:/bybit_strategy_tester_v2")
warnings.filterwarnings("ignore")

from backend.backtesting.engines.dca_engine import DCAEngine  # noqa: E402
from backend.backtesting.models import BacktestConfig, StrategyType  # noqa: E402

# ── Build OHLCV that will definitely trigger DCA grid fills ───────────────────
# Entry at bar 10 (price 3000)
# Then price drops through 3000 * (1 - 6%/4) = ~2955  → fills order 2
# Then price drops through 3000 * (1 - 12%/4) = ~2910 → fills order 3
# etc.
n = 200
prices = np.ones(n) * 3000.0
# Drop 25% from bar 20 to bar 80 (will fill all 5 grid orders at 6% grid)
for i in range(20, 80):
    prices[i] = 3000.0 * (1.0 - (i - 20) / 60 * 0.25)
# Recover
for i in range(80, n):
    prices[i] = 2250.0 + (i - 80) / (n - 80) * 1000.0

high = prices * 1.005
low = prices * 0.995

df = pd.DataFrame(
    {
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="30min"),
        "open": prices,
        "high": high,
        "low": low,
        "close": prices,
        "volume": np.ones(n) * 5000.0,
    }
)
df.index = df["timestamp"]

print(f"OHLCV: {len(df)} bars, price range {low.min():.0f} – {high.max():.0f}")
print(f"Expected DCA fills: orders at ~2820, ~2640, ~2460, ~2280 (below 3000 entry, 6% grid, 5 orders)")

# ── BacktestConfig with DCA (NO TP = position stays open until end) ───────────
bc = BacktestConfig(
    symbol="ETHUSDT",
    interval="30",
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    strategy_type=StrategyType.DCA,
    initial_capital=10000.0,
    leverage=1.0,
    taker_fee=0.0007,
    maker_fee=0.0007,
    dca_enabled=True,
    dca_direction="long",
    dca_order_count=5,
    dca_grid_size_percent=6.0,
    dca_martingale_coef=1.0,
    dca_martingale_mode="multiply_each",
    dca_log_step_enabled=False,
    dca_log_step_coef=1.0,
    dca_safety_close_enabled=False,  # No safety close
    dca_drawdown_threshold=90.0,  # Max allowed, won't trigger on 25% drop with dca_safety_close_enabled=False
    dca_multi_tp_enabled=False,
    # No TP configured → position should stay open
)

# ── Manually inject a signal at bar 10 ───────────────────────────────────────
engine = DCAEngine()
engine._configure_from_config(bc)

# Manually open position
entry_price = float(prices[10])
print(f"\nManually opening long at bar 10, price={entry_price:.2f}")
engine.position.is_open = False
engine.trades = []
engine.equity_curve = [10000.0]
engine._realized_equity = 10000.0
engine.total_signals = 0
engine.total_orders_filled = 0

engine._open_dca_position(10, entry_price, "long")

print(f"Orders placed ({len(engine.position.orders)} total):")
for i, o in enumerate(engine.position.orders):
    status = "FILLED" if o.filled else ("active" if o.active_in_grid else "inactive")
    print(f"  Order {i + 1}: price={o.price:.2f} size=${o.size_usd:.2f}  [{status}]")

print(f"\nSimulating bars 11-{n - 1}...")
equity = 10000.0
fills_per_bar = {}
for bar_idx in range(11, n):
    h = float(high[bar_idx])
    lo = float(low[bar_idx])
    cl = float(prices[bar_idx])

    orders_before = sum(1 for o in engine.position.orders if o.filled)
    equity = engine._process_open_position(bar_idx, h, lo, cl, equity)
    orders_after = sum(1 for o in engine.position.orders if o.filled)

    if orders_after > orders_before:
        fills_per_bar[bar_idx] = orders_after - orders_before
        print(
            f"  Bar {bar_idx:3d} price={cl:7.2f}: +{orders_after - orders_before} fill(s) => total {orders_after} filled"
        )

total_filled = sum(1 for o in engine.position.orders if o.filled)
print(f"\nTotal DCA orders filled: {total_filled} / {len(engine.position.orders)}")

# Summary
SEP = "=" * 55
print(f"\n{SEP}")
if total_filled > 1:
    print(f"GRID WORKING: {total_filled} orders filled")
    print(f"  Average entry price: {engine.position.average_entry_price:.2f}")
    print(f"  Total position size: {engine.position.total_size_coins:.4f} coins")
    print(f"  Total cost: ${engine.position.total_cost_usd:.2f}")
else:
    print("GRID NOT WORKING: only 1 order filled")
    print("  Check _should_fill_order and order.active_in_grid flags")
