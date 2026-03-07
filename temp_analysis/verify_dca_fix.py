"""
Verify that Strategy_DCA_RSI_02 now correctly uses DCAEngine.

Checks:
1. has_dca_blocks() returns True for strategy
2. extract_dca_config() returns dca_enabled=True
3. DCAEngine is selected (dca_enabled=True in router logic)
4. DCAEngine produces DCA grid fills (>1 order per trade)
5. RSI cross+range conflict fix works

Run with:
    py -3.14 temp_analysis/verify_dca_fix.py
"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import json
import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd

print("=" * 60)
print("DCA Fix Verification")
print("=" * 60)

# 1. Load strategy from DB (using builder_blocks/builder_connections as the router does)
conn = sqlite3.connect("data.sqlite3")
cur = conn.cursor()
cur.execute(
    "SELECT id, name, builder_blocks, builder_connections, builder_graph "
    "FROM strategies WHERE name = 'Strategy_DCA_RSI_02' AND is_deleted=0"
)
row = cur.fetchone()
conn.close()

if not row:
    print("ERROR: Strategy_DCA_RSI_02 not found in DB!")
    sys.exit(1)

strat_id, strat_name = row[0], row[1]
builder_blocks = json.loads(row[2]) if row[2] else []
builder_connections = json.loads(row[3]) if row[3] else []
builder_graph = json.loads(row[4]) if row[4] else {}

print(f"\nStrategy: {strat_name} (id={strat_id})")
print(f"builder_blocks: {len(builder_blocks)} blocks")
print(f"builder_connections: {len(builder_connections)} connections")
print("\nBlock types in builder_blocks:")
for b in builder_blocks:
    print(f"  type={b.get('type','?')!r:20} category={b.get('category','')!r}")

# 2. Build strategy_graph as the router does
strategy_graph = {
    "name": strat_name,
    "blocks": builder_blocks,
    "connections": builder_connections,
    "interval": "15",
}
if builder_graph.get("main_strategy"):
    strategy_graph["main_strategy"] = builder_graph["main_strategy"]

# 3. Test has_dca_blocks and extract_dca_config
from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter

adapter = StrategyBuilderAdapter(strategy_graph)

has_dca = adapter.has_dca_blocks()
dca_cfg = adapter.extract_dca_config()

print(f"\n--- DCA Detection (after fix) ---")
print(f"has_dca_blocks(): {has_dca}")
print(f"dca_enabled: {dca_cfg.get('dca_enabled')}")
print(f"dca_order_count: {dca_cfg.get('dca_order_count')}")
print(f"dca_grid_size_percent: {dca_cfg.get('dca_grid_size_percent')}")
print(f"dca_direction: {dca_cfg.get('dca_direction')}")
print(f"dca_martingale_coef: {dca_cfg.get('dca_martingale_coef')}")
print(f"custom_orders: {dca_cfg.get('custom_orders') is not None}")

# Router logic check (simulated)
dca_enabled_final = (
    False  # request.dca_enabled (not set by user in this test)
    or has_dca
    or dca_cfg.get("dca_enabled", False)
)
print(f"\nEngine selection: dca_enabled={dca_enabled_final}")
if dca_enabled_final:
    print("  → DCAEngine would be used ✓")
else:
    print("  → FallbackEngineV4 would be used ✗ (BUG!)")

# 4. Generate signals on synthetic data
np.random.seed(42)
n = 600
dates = pd.date_range("2025-01-01", periods=n, freq="15min", tz=timezone.utc)
# Price falls then rises to trigger RSI
prices = np.concatenate([
    np.linspace(50000, 42000, n // 3) + np.random.randn(n // 3) * 100,
    np.linspace(42000, 55000, n // 3) + np.random.randn(n // 3) * 100,
    np.linspace(55000, 48000, n // 3) + np.random.randn(n // 3) * 100,
])
ohlcv = pd.DataFrame({
    "open": prices,
    "high": prices * 1.005,
    "low": prices * 0.995,
    "close": prices,
    "volume": np.full(n, 100.0),
}, index=dates)

signal_result = adapter.generate_signals(ohlcv)
long_count = int(signal_result.entries.sum())
short_count = int(signal_result.short_entries.sum()) if signal_result.short_entries is not None else 0
print(f"\n--- Signal Generation ---")
print(f"Long signals: {long_count}")
print(f"Short signals: {short_count}")

# 5. Run DCAEngine
from backend.backtesting.engines.dca_engine import DCAEngine


class FakeConfig:
    symbol = "BTCUSDT"
    interval = "15"
    start_date = dates[0]
    end_date = dates[-1]
    strategy_type = type("ST", (), {"value": "builder"})()
    strategy_params = {}
    initial_capital = 10000.0
    position_size = 1.0
    leverage = 1
    direction = "long"
    stop_loss = None
    take_profit = None
    taker_fee = 0.0007
    maker_fee = 0.0007
    slippage = 0.0
    pyramiding = 1
    market_type = "linear"
    dca_enabled = dca_cfg.get("dca_enabled", True)
    dca_direction = dca_cfg.get("dca_direction", "both")
    dca_order_count = dca_cfg.get("dca_order_count", 5)
    dca_grid_size_percent = dca_cfg.get("dca_grid_size_percent", 6.0)
    dca_martingale_coef = dca_cfg.get("dca_martingale_coef", 1.0)
    dca_martingale_mode = dca_cfg.get("dca_martingale_mode", "multiply_each")
    dca_log_step_enabled = dca_cfg.get("dca_log_step_enabled", False)
    dca_log_step_coef = dca_cfg.get("dca_log_step_coef", 1.2)
    dca_drawdown_threshold = dca_cfg.get("dca_drawdown_threshold", 30.0)
    dca_safety_close_enabled = dca_cfg.get("dca_safety_close_enabled", True)
    dca_custom_orders = dca_cfg.get("custom_orders", None)
    dca_grid_trailing_percent = dca_cfg.get("grid_trailing_percent", 0.0)
    dca_multi_tp_enabled = dca_cfg.get("dca_multi_tp_enabled", False)
    dca_tp1_percent = dca_cfg.get("dca_tp1_percent", 0.5)
    dca_tp1_close_percent = dca_cfg.get("dca_tp1_close_percent", 25.0)
    dca_tp2_percent = dca_cfg.get("dca_tp2_percent", 1.0)
    dca_tp2_close_percent = dca_cfg.get("dca_tp2_close_percent", 25.0)
    dca_tp3_percent = dca_cfg.get("dca_tp3_percent", 2.0)
    dca_tp3_close_percent = dca_cfg.get("dca_tp3_close_percent", 25.0)
    dca_tp4_percent = dca_cfg.get("dca_tp4_percent", 3.0)
    dca_tp4_close_percent = dca_cfg.get("dca_tp4_close_percent", 25.0)
    partial_grid_orders = dca_cfg.get("partial_grid_orders", 1)
    grid_pullback_percent = dca_cfg.get("grid_pullback_percent", 0.0)


class PrecomputedAdapter:
    def __init__(self, signals):
        self._signals = signals

    def generate_signals(self, data):
        return self._signals


config = FakeConfig()
engine = DCAEngine()
result = engine.run_from_config(config, ohlcv, custom_strategy=PrecomputedAdapter(signal_result))

print(f"\n--- DCAEngine Results ---")
print(f"Status: {result.status}")
n_trades = len(result.trades) if result.trades else 0
print(f"Total trades (positions): {n_trades}")
print(f"Total signals fired: {engine.total_signals}")
print(f"Total orders filled: {engine.total_orders_filled}")

if n_trades > 0:
    avg_orders = engine.total_orders_filled / n_trades
    print(f"Avg orders per trade: {avg_orders:.2f}")
    if avg_orders <= 1.05:
        print("  ⚠ WARNING: only 1 order/trade — DCA grid NOT filling!")
    else:
        print(f"  ✓ DCA grid filling properly: {avg_orders:.1f} orders/trade")

    print(f"\nSample trades (first 5):")
    print(f"  {'#':>3} {'Entry':>10} {'Exit':>10} {'PnL%':>7}  Reason")
    print("  " + "-" * 45)
    for i, t in enumerate(result.trades[:5], 1):
        ep = getattr(t, "entry_price", 0)
        xp = getattr(t, "exit_price", 0)
        pnl = getattr(t, "pnl_percent", getattr(t, "pnl_pct", 0))
        reason = getattr(t, "exit_reason", "?")
        print(f"  {i:>3} {ep:>10.1f} {xp:>10.1f} {pnl:>7.2f}%  {reason}")
else:
    if long_count == 0 and short_count == 0:
        print("  ⚠ WARNING: 0 RSI signals generated — check RSI config!")
    else:
        print(f"  ⚠ WARNING: 0 trades despite {long_count} signals!")

print("\n" + "=" * 60)
# Final verdict
checks = [
    ("has_dca_blocks() returns True", has_dca),
    ("extract_dca_config() dca_enabled=True", dca_cfg.get("dca_enabled", False)),
    ("Router selects DCAEngine", dca_enabled_final),
    ("RSI generates signals", long_count > 0 or short_count > 0),
    ("DCAEngine produces trades", n_trades > 0),
    ("DCA grid fills (>1 order/trade)", n_trades > 0 and engine.total_orders_filled / n_trades > 1.05),
]
all_ok = all(ok for _, ok in checks)
for desc, ok in checks:
    icon = "✓" if ok else "✗"
    print(f"  {icon} {desc}")
print("=" * 60)
print("RESULT:", "ALL CHECKS PASSED ✓" if all_ok else "SOME CHECKS FAILED ✗")
print()
