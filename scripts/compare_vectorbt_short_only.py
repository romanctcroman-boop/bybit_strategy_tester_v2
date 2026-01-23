#!/usr/bin/env python3
"""Compare fallback vs vectorbt engines (short-only signals).

Writes report to logs/compare_vectorbt_short_only.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.fast_optimizer import load_candles_fast
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategies import get_strategy

LOGS = Path(ROOT) / "logs"
LOGS.mkdir(exist_ok=True)


def to_dataframe(data: np.ndarray) -> pd.DataFrame:
    df = pd.DataFrame(
        data, columns=["open_time", "open", "high", "low", "close", "volume"]
    )
    try:
        df["open_time"] = pd.to_datetime(df["open_time"].astype("int64"), unit="ms")
    except Exception:
        df["open_time"] = pd.to_datetime(df["open_time"])
    df = df.set_index("open_time")
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def run_comparison():
    symbol = "BTCUSDT"
    interval = "15"
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 1, 11)

    db_path = Path(ROOT) / "data.sqlite3"
    data = load_candles_fast(str(db_path), symbol, interval, start_date, end_date)
    if data is None:
        print("No candle data found; aborting")
        return 1

    ohlcv = to_dataframe(data)

    cfg = BacktestConfig(
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        strategy_type="rsi",
        strategy_params={"period": 21, "oversold": 30, "overbought": 70},
        initial_capital=10000.0,
        leverage=10.0,
        position_size=1.0,
        direction="short",
    )

    strategy = get_strategy(cfg.strategy_type, cfg.strategy_params)
    signals = strategy.generate_signals(ohlcv)

    engine = BacktestEngine()
    fb_res = engine._run_fallback(cfg, ohlcv, signals)
    try:
        vb_res = engine._run_vectorbt(cfg, ohlcv, signals)
    except Exception as e:
        vb_res = {"error": str(e)}

    def metrics_to_dict(m):
        try:
            return m.model_dump()
        except Exception:
            try:
                return m.dict()
            except Exception:
                return m

    fb_metrics = metrics_to_dict(getattr(fb_res, "metrics", None))
    vb_metrics = None
    if isinstance(vb_res, dict) and "metrics" in vb_res:
        vb_metrics = metrics_to_dict(vb_res["metrics"])

    report = {
        "config": cfg.__dict__,
        "fallback": {
            "trades_len": len(getattr(fb_res, "trades", [])),
            "equity_final": getattr(fb_res, "final_equity", None),
            "metrics": fb_metrics,
        },
        "vectorbt": {
            "status": "ok"
            if isinstance(vb_res, dict) and "error" not in vb_res
            else "error",
            "error": vb_res.get("error") if isinstance(vb_res, dict) else None,
            "trades_len": len(vb_res.get("trades", []))
            if isinstance(vb_res, dict) and "trades" in vb_res
            else None,
            "equity_final": vb_res.get("final_equity")
            if isinstance(vb_res, dict)
            else None,
            "metrics": vb_metrics,
        },
    }

    out_path = LOGS / "compare_vectorbt_short_only.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str, ensure_ascii=False)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    run_comparison()
