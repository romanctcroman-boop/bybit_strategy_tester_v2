"""Debug trade-by-trade comparison."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import logging
import sqlite3

import pandas as pd

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig

logging.getLogger("backend").setLevel(logging.WARNING)

# Load data
db_path = ROOT / "data.sqlite3"
conn = sqlite3.connect(str(db_path))
df = pd.read_sql(
    """SELECT open_time, open_price as open, high_price as high,
       low_price as low, close_price as close, volume
    FROM bybit_kline_audit WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time DESC LIMIT 500""", conn)
conn.close()
df = df.sort_values("open_time")
df["datetime"] = pd.to_datetime(df["open_time"], unit="ms")
df = df.set_index("datetime")

# Config
config_dict = {
    "symbol": "BTCUSDT", "interval": "60",
    "strategy_type": "rsi",
    "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
    "initial_capital": 10000.0, "leverage": 10.0, "position_size": 1.0,
    "direction": "long",  # Testing LONG
    "stop_loss": 0.02, "take_profit": 0.04,
    "use_bar_magnifier": False,
    "start_date": df.index[0], "end_date": df.index[-1],
}
config = BacktestConfig(**config_dict)

engine = BacktestEngine()

from backend.backtesting.strategies import get_strategy

strategy = get_strategy(config.strategy_type)
strategy.params = config.strategy_params
strategy.direction = config.direction
signals = strategy.generate_signals(df)

# Run both
result_vbt = engine._run_vectorbt(config, df, signals)
result_fb = engine._run_fallback(config, df, signals)

print("=" * 80)
print("TRADE-BY-TRADE COMPARISON (LONG)")
print("=" * 80)

for i, (t_vbt, t_fb) in enumerate(zip(result_vbt.trades, result_fb.trades)):
    print(f"\nTrade {i+1}:")
    print(f"  VBT: entry={t_vbt.entry_price:.2f}, exit={t_vbt.exit_price:.2f}, size={t_vbt.size:.6f}, pnl={t_vbt.pnl:.2f}, fees={t_vbt.fees:.4f}")
    print(f"  FB:  entry={t_fb.entry_price:.2f}, exit={t_fb.exit_price:.2f}, size={t_fb.size:.6f}, pnl={t_fb.pnl:.2f}, fees={t_fb.fees:.4f}")

    if abs(t_vbt.entry_price - t_fb.entry_price) > 0.01:
        print(f"  ❌ Entry price diff: {t_vbt.entry_price - t_fb.entry_price:.6f}")
    if abs(t_vbt.exit_price - t_fb.exit_price) > 0.01:
        print(f"  ❌ Exit price diff: {t_vbt.exit_price - t_fb.exit_price:.6f}")
    if abs(t_vbt.size - t_fb.size) > 0.0001:
        print(f"  ❌ Size diff: {t_vbt.size - t_fb.size:.6f}")
    if abs(t_vbt.pnl - t_fb.pnl) > 0.1:
        print(f"  ❌ PnL diff: {t_vbt.pnl - t_fb.pnl:.4f}")

# Equity curve comparison
print("\n" + "=" * 80)
print("EQUITY CURVE COMPARISON")
print("=" * 80)
vbt_eq = result_vbt.equity_curve.equity
fb_eq = result_fb.equity_curve.equity
print(f"Length: VBT={len(vbt_eq)}, FB={len(fb_eq)}")
print(f"First 5 VBT: {[f'{v:.2f}' for v in vbt_eq[:5]]}")
print(f"First 5 FB:  {[f'{v:.2f}' for v in fb_eq[:5]]}")
print(f"Last 5 VBT: {[f'{v:.2f}' for v in vbt_eq[-5:]]}")
print(f"Last 5 FB:  {[f'{v:.2f}' for v in fb_eq[-5:]]}")

# Debug: show first trade bar indices
if result_vbt.trades:
    t = result_vbt.trades[0]
    print(f"\nFirst VBT trade: entry_bar={t.entry_bar_index}, exit_bar={t.exit_bar_index}")
if result_fb.trades:
    t = result_fb.trades[0]
    print(f"First FB trade: entry_bar={t.entry_bar_index}, exit_bar={t.exit_bar_index}")

# Metrics comparison
print("\n" + "=" * 80)
print("KEY METRICS COMPARISON")
print("=" * 80)
vbt_m = result_vbt.metrics
fb_m = result_fb.metrics
print(f"Net Profit: VBT={vbt_m.net_profit:.2f}, FB={fb_m.net_profit:.2f}")
print(f"Max DD:     VBT={vbt_m.max_drawdown:.4f}, FB={fb_m.max_drawdown:.4f}")
print(f"Sharpe:     VBT={vbt_m.sharpe_ratio:.4f}, FB={fb_m.sharpe_ratio:.4f}")
print(f"Sortino:    VBT={vbt_m.sortino_ratio:.4f}, FB={fb_m.sortino_ratio:.4f}")

