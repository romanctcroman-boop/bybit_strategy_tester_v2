from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig, StrategyType


def _cfg(**kw):
    base = {
        "symbol": "BTCUSDT",
        "interval": "15",
        "start_date": datetime(2025, 6, 1, tzinfo=UTC),
        "end_date": datetime(2025, 6, 2, tzinfo=UTC),
        "strategy_type": StrategyType.SMA_CROSSOVER,
        "strategy_params": {"fast_period": 2, "slow_period": 5},
        "initial_capital": 10000.0,
        "taker_fee": 0.0007,
        "maker_fee": 0.0002,
        "leverage": 1.0,
        "position_size": 1.0,
        "slippage": 0.0,
        "direction": "long",
    }
    base.update(kw)
    cfg = BacktestConfig(**base)
    if "taker_fee" in kw:
        cfg = BacktestConfig(**{**base, "commission_value": kw["taker_fee"]})
    return cfg


prices = [100, 100, 105, 110, 115, 120, 120, 120, 120, 120]
arr = np.asarray(prices, dtype=np.float64)
idx = pd.date_range("2025-06-01", periods=len(arr), freq="15min", tz="UTC")
ohlcv = pd.DataFrame({"open": arr, "high": arr * 1.005, "low": arr * 0.995, "close": arr, "volume": 1000.0}, index=idx)

n = len(ohlcv)
le = pd.Series(np.zeros(n, dtype=bool), index=ohlcv.index)
le.iloc[1] = True
lx = pd.Series(np.zeros(n, dtype=bool), index=ohlcv.index)

signals = SimpleNamespace(
    entries=le,
    exits=lx,
    long_entries=le,
    long_exits=lx,
    short_entries=pd.Series(np.zeros(n, dtype=bool), index=ohlcv.index),
    short_exits=pd.Series(np.zeros(n, dtype=bool), index=ohlcv.index),
    entry_sizes=None,
    short_entry_sizes=None,
    extra_data=None,
)

cfg = _cfg(taker_fee=0.0007, leverage=1.0)
eng = BacktestEngine()
r = eng._run_fallback(config=cfg, ohlcv=ohlcv, signals=signals)
print(f"Num trades: {len(r.trades)}")
for t in r.trades:
    is_open = getattr(t, "is_open", False)
    ec = getattr(t, "exit_comment", "?")
    exact = t.size * t.entry_price * 0.0007 + t.size * t.exit_price * 0.0007
    print(
        f"  is_open={is_open}, fees={t.fees:.4f}, exact={exact:.4f}, exit_comment={ec}, entry={t.entry_price}, exit={t.exit_price}, size={t.size:.4f}"
    )
