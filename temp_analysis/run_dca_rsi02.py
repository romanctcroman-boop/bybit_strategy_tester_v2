"""Run Strategy_DCA_RSI_02 backtest and verify DCA grid behavior."""

import json
import sqlite3
import sys
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, "d:/bybit_strategy_tester_v2")
warnings.filterwarnings("ignore")

from backend.backtesting.engines.dca_engine import DCAEngine  # noqa: E402
from backend.backtesting.models import BacktestConfig, StrategyType  # noqa: E402
from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter  # noqa: E402

# ── 1. Load strategy from DB ──────────────────────────────────────────────────
conn = sqlite3.connect("data.sqlite3")
cur = conn.cursor()
cur.execute(
    "SELECT id, name, builder_graph, symbol, timeframe FROM strategies WHERE name LIKE '%DCA_RSI%' AND is_deleted=0"
)
rows = cur.fetchall()
conn.close()

if not rows:
    print("ERROR: No DCA_RSI strategies found!")
    sys.exit(1)

for r in rows:
    print(f"Found: {r[1]} | ID: {r[0]}")

target = next((r for r in rows if "02" in r[1]), rows[0])
strategy_id, strategy_name = target[0], target[1]
config = json.loads(target[2]) if target[2] else {}
db_symbol = target[3] or "BTCUSDT"
db_tf = target[4] or "15"
print(f"\nUsing: {strategy_name} | Symbol: {db_symbol} TF:{db_tf}")

# ── 2. Extract DCA config ─────────────────────────────────────────────────────
adapter = StrategyBuilderAdapter(config)
dca_cfg = adapter.extract_dca_config()
print("\nDCA Config:")
for k, v in dca_cfg.items():
    if v not in (None, False, 0, 0.0, [], {}):
        print(f"  {k}: {v}")

# ── 3. Load OHLCV ─────────────────────────────────────────────────────────────
try:
    kline_conn = sqlite3.connect("d:/bybit_strategy_tester_v2/bybit_klines_15m.db")
    tables_df = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", kline_conn)
    tables = tables_df["name"].tolist()
    tbl = next((t for t in tables if db_symbol in t), None)
    if not tbl:
        # Try case-insensitive
        tbl = next((t for t in tables if db_symbol.lower() in t.lower()), None)
    if not tbl and tables:
        tbl = tables[0]
        print(f"No {db_symbol} table; using {tbl}")
    if tbl:
        df = pd.read_sql(f"SELECT * FROM [{tbl}] ORDER BY open_time DESC LIMIT 5000", kline_conn)
        df = df.iloc[::-1].reset_index(drop=True)
        kline_conn.close()
        print(f"Loaded {len(df)} bars from {tbl}")
        rename = {
            "open_time": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        df.rename(columns=rename, inplace=True)
    else:
        raise ValueError("No tables in klines DB")
except Exception as e:
    print(f"Klines load failed ({e}), using volatile synthetic data")
    # Volatile mean-reverting price for grid testing (not a simple trend)
    np.random.seed(42)  # same seed as first successful run
    n = 3000
    price = 50000.0
    prices = [price]
    for _ in range(n - 1):
        price *= 1 + np.random.normal(0, 0.008)
        prices.append(price)
    prices = np.array(prices)
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="30min"),
            "open": prices * (1 + np.random.normal(0, 0.001, n)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.004, n))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.004, n))),
            "close": prices,
            "volume": np.random.uniform(100, 1000, n),
        }
    )

for col in ["open", "high", "low", "close", "volume"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
df.dropna(subset=["close"], inplace=True)

# Set DatetimeIndex required by DCAEngine
if "timestamp" in df.columns:
    df.index = pd.to_datetime(df["timestamp"], unit="ms", errors="coerce")
    if df.index.isna().all():
        df.index = pd.to_datetime(df["timestamp"], errors="coerce")
if df.index.isna().all() or not isinstance(df.index, pd.DatetimeIndex):
    df.index = pd.date_range("2025-01-01", periods=len(df), freq="15min")
df.index.name = None

print(f"\nOHLCV: {len(df)} bars | close {df['close'].min():.2f} – {df['close'].max():.2f}")

# ── 4. Build BacktestConfig ───────────────────────────────────────────────────
bc = BacktestConfig(
    symbol=db_symbol,
    interval=db_tf,
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    strategy_type=StrategyType.BUILDER,
    initial_capital=1000.0,
    leverage=1.0,
    taker_fee=0.0007,
    maker_fee=0.0007,
    dca_enabled=dca_cfg.get("dca_enabled", True),
    dca_direction=dca_cfg.get("dca_direction", "both"),
    dca_order_count=dca_cfg.get("dca_order_count", 5),
    dca_grid_size_percent=dca_cfg.get("dca_grid_size_percent", 10.0),
    dca_martingale_coef=dca_cfg.get("dca_martingale_coef", 1.0),
    dca_martingale_mode=dca_cfg.get("dca_martingale_mode", "multiply_each"),
    dca_log_step_enabled=dca_cfg.get("dca_log_step_enabled", False),
    dca_log_step_coef=dca_cfg.get("dca_log_step_coef", 1.1),
    dca_safety_close_enabled=dca_cfg.get("dca_safety_close_enabled", True),
    dca_drawdown_threshold=dca_cfg.get("dca_drawdown_threshold", 30.0),
    dca_multi_tp_enabled=dca_cfg.get("dca_multi_tp_enabled", False),
    dca_tp1_percent=dca_cfg.get("dca_tp1_percent", 0.5),
    dca_tp1_close_percent=dca_cfg.get("dca_tp1_close_percent", 25.0),
    dca_tp2_percent=dca_cfg.get("dca_tp2_percent", 1.0),
    dca_tp2_close_percent=dca_cfg.get("dca_tp2_close_percent", 25.0),
    dca_tp3_percent=dca_cfg.get("dca_tp3_percent", 2.0),
    dca_tp3_close_percent=dca_cfg.get("dca_tp3_close_percent", 25.0),
    dca_tp4_percent=dca_cfg.get("dca_tp4_percent", 3.0),
    dca_tp4_close_percent=dca_cfg.get("dca_tp4_close_percent", 25.0),
    dca_custom_orders=dca_cfg.get("custom_orders"),
    dca_grid_trailing_percent=dca_cfg.get("grid_trailing_percent", 0.0),
    partial_grid_orders=dca_cfg.get("partial_grid_orders", 1),
    grid_pullback_percent=dca_cfg.get("grid_pullback_percent", 0.0),
    strategy_params=config,
)
print(f"\nGrid: size={bc.dca_grid_size_percent}%, orders={bc.dca_order_count}, martingale={bc.dca_martingale_coef}")

# ── 5. Run engine ─────────────────────────────────────────────────────────────
engine = DCAEngine()
result = engine.run_from_config(bc, df, custom_strategy=adapter)

# ── 6. Results ────────────────────────────────────────────────────────────────
SEP = "=" * 60
print(f"\n{SEP}")
print(f"RESULTS: {strategy_name}")
print(SEP)

trades = result.trades or []
metrics = result.metrics or {}

total_trades = len(trades)
win_rate = metrics.get("win_rate", 0.0) if isinstance(metrics, dict) else getattr(metrics, "win_rate", 0.0)
net_profit = result.final_pnl or 0.0
net_pnl_pct = result.final_pnl_pct or 0.0
max_dd = (
    metrics.get("max_drawdown_percent", 0.0)
    if isinstance(metrics, dict)
    else getattr(metrics, "max_drawdown_percent", 0.0)
)

print(f"Total trades:         {total_trades}")
print(f"Win rate:             {win_rate:.1f}%")
print(f"Net profit:           {net_profit:.4f} USDT")
print(f"Net profit %:         {net_pnl_pct:.2f}%")
print(f"Max drawdown:         {max_dd:.2f}%")
print(f"Total signals fired:  {getattr(engine, 'total_signals', '?')}")
print(f"Total orders filled:  {getattr(engine, 'total_orders_filled', '?')}")
if trades:
    avg_orders = engine.total_orders_filled / len(trades)
    print(f"Avg DCA orders/trade: {avg_orders:.2f}")

    print("\nTrade sample (first 8):")
    print(f"  {'#':>3} {'Entry':>10} {'Exit':>10} {'PnL%':>7} {'Bars':>6}  Reason")
    print("  " + "-" * 56)
    for i, t in enumerate(trades[:8], 1):
        entry = getattr(t, "entry_price", 0)
        exit_p = getattr(t, "exit_price", 0)
        pnl_pct = getattr(t, "pnl_percent", getattr(t, "pnl_pct", 0))
        bars = getattr(t, "bars_held", 0)
        reason = getattr(t, "exit_reason", "?")
        print(f"  {i:>3} {entry:>10.2f} {exit_p:>10.2f} {pnl_pct:>7.2f}% {bars:>6}  {reason}")

    # Grid health check
    print()
    if avg_orders <= 1.05:
        print("*** WARNING: avg 1 order/trade — grid NOT filling! ***")
    else:
        print(f"OK: Grid filling {avg_orders:.1f} orders/trade on average")

    bar_durations = [getattr(t, "bars_held", 0) for t in trades]
    avg_bars = sum(bar_durations) / len(bar_durations)
    print(f"Avg trade duration:   {avg_bars:.1f} bars")
    if avg_bars < 3:
        print("*** WARNING: very short trades (closed too fast) ***")
else:
    print("No trades recorded")

print("\nDone.")
