import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import asyncio
from datetime import datetime, timezone

import pandas as pd

from backend.backtesting.engines.dca_engine import DCAEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter
from backend.database import SessionLocal
from backend.database.models.strategy import Strategy

STRATEGY_ID = "f46c7cc3-1098-483a-a177-67b7867dd72e"

db = SessionLocal()
s = db.query(Strategy).filter(Strategy.id == STRATEGY_ID).first()
db.close()

_blocks = s.builder_blocks
_connections = s.builder_connections
if not _blocks and s.builder_graph:
    _blocks = s.builder_graph.get("blocks", [])
    _connections = s.builder_graph.get("connections", [])

strategy_graph = {
    "name": s.name,
    "blocks": _blocks or [],
    "connections": _connections or [],
    "market_type": "linear",
    "direction": "both",
    "interval": "30",
}

adapter = StrategyBuilderAdapter(strategy_graph)
print(f"has_dca_blocks: {adapter.has_dca_blocks()}")
cfg = adapter.extract_dca_config()
print(f"DCA config: {cfg}")

# Get OHLCV
svc = BacktestService()
ohlcv = asyncio.run(
    svc._fetch_historical_data(
        symbol="ETHUSDT",
        interval="30",
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
        market_type="linear",
    )
)
print(f"OHLCV bars: {len(ohlcv)}, price range: {ohlcv['close'].min():.2f} - {ohlcv['close'].max():.2f}")

# Build BacktestConfig
from backend.backtesting.models import BacktestConfig, StrategyType

bc = BacktestConfig(
    symbol="ETHUSDT",
    interval="30",
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
    strategy_type=StrategyType.CUSTOM,
    initial_capital=10000.0,
    position_size=0.1,
    leverage=1,
    direction="both",
    taker_fee=0.0007,
    maker_fee=0.0007,
    dca_enabled=True,
    dca_order_count=cfg.get("dca_order_count", 5),
    dca_grid_size_percent=cfg.get("dca_grid_size_percent", 2.0),
    dca_martingale_coef=cfg.get("dca_martingale_coef", 1.0),
    dca_martingale_mode=cfg.get("dca_martingale_mode", "size"),
    dca_direction=cfg.get("dca_direction", "both"),
    dca_log_step_enabled=cfg.get("dca_log_step_enabled", False),
    dca_log_step_coef=cfg.get("dca_log_step_coef", 1.0),
    dca_drawdown_threshold=cfg.get("dca_drawdown_threshold", 0.0),
    dca_safety_close_enabled=cfg.get("dca_safety_close_enabled", False),
    dca_multi_tp_enabled=cfg.get("dca_multi_tp_enabled", False),
    stop_loss=cfg.get("stop_loss", None),
    take_profit=cfg.get("take_profit", None),
)

# Run DCA
engine = DCAEngine()
result = engine.run_from_config(bc, ohlcv, custom_strategy=adapter)

print(f"\n=== RESULTS ===")
print(f"Trades: {len(result.trades)}")
if result.trades:
    t0 = result.trades[0]
    print(
        f"Trade 0: entry={getattr(t0, 'entry_price', 0):.2f}, pnl={getattr(t0, 'pnl', 0):.4f}, pnl_pct={getattr(t0, 'pnl_pct', 0):.6f}"
    )

print(f"\n=== DCA ORDER NUMBERS PER TRADE ===")
for i, t in enumerate(result.trades):
    print(f"  Trade {i + 1}: dca_orders_filled={t.dca_orders_filled}, exit={t.exit_comment}, pnl={t.pnl:.2f}")

m = result.metrics
print(f"\nMetrics:")
print(f"  win_rate: {m.win_rate}")
print(f"  total_trades: {m.total_trades}")
print(f"  winning_trades: {m.winning_trades}")
print(f"  net_profit: {m.net_profit}")
print(f"  final_equity: {result.final_equity}")
