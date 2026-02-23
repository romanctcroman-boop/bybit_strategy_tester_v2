"""Run engine comparisons under several config variations and report results.

This runs the same RSI signals through fallback and vectorbt engines with:
- baseline (default fees/slippage)
- zero fees & zero slippage

Outputs a JSON report with diffs for each variation.
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.fast_optimizer import load_candles_fast
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategies import get_strategy

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data.sqlite3"


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


def run_compare(config: BacktestConfig, ohlcv: pd.DataFrame):
    strategy = get_strategy(config.strategy_type, config.strategy_params)
    signals = strategy.generate_signals(ohlcv)

    engine = BacktestEngine()
    res_fb = engine._run_fallback(config, ohlcv, signals)
    res_vb = engine._run_vectorbt(config, ohlcv, signals)
    return res_fb, res_vb


def metrics_to_dict(m):
    try:
        return m.model_dump()
    except Exception:
        try:
            return m.dict()
        except Exception:
            return {}


def summarize(res_fb, res_vb):
    mf = metrics_to_dict(res_fb.metrics)
    mv = metrics_to_dict(res_vb.metrics)
    keys = set(list(mf.keys()) + list(mv.keys()))
    metrics_diff = {}
    for k in sorted(keys):
        a = mf.get(k)
        b = mv.get(k)
        try:
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                metrics_diff[k] = {
                    "fallback": a,
                    "vectorbt": b,
                    "diff": float(a) - float(b),
                }
            else:
                if a != b:
                    metrics_diff[k] = {"fallback": a, "vectorbt": b}
        except Exception:
            metrics_diff[k] = {"fallback": a, "vectorbt": b}

    return {
        "trades": {
            "fallback_len": len(res_fb.trades),
            "vectorbt_len": len(res_vb.trades),
        },
        "equity": {
            "fallback_final": res_fb.final_equity,
            "vectorbt_final": res_vb.final_equity,
        },
        "metrics_diff": metrics_diff,
    }


def main():
    symbol = "BTCUSDT"
    interval = "15"
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 1, 11)

    data = load_candles_fast(str(DB_PATH), symbol, interval, start_date, end_date)
    if data is None:
        print("No candle data found; aborting")
        return 1

    ohlcv = to_dataframe(data)

    base_cfg = {
        "symbol": symbol,
        "interval": interval,
        "start_date": start_date,
        "end_date": end_date,
        "strategy_type": "rsi",
        "strategy_params": {"period": 21, "oversold": 30, "overbought": 70},
        # Use long-only signals for vectorbt parity checks
        "direction": "long",
        "initial_capital": 10000.0,
        "leverage": 10.0,
        "position_size": 1.0,
    }

    variations = {
        "baseline": {**base_cfg},
        "zero_fees_slippage": {**base_cfg, "taker_fee": 0.0, "slippage": 0.0},
    }

    report = {}
    for name, cfg_kwargs in variations.items():
        cfg = BacktestConfig(**cfg_kwargs)
        print(f"Running variation: {name}")
        fb, vb = run_compare(cfg, ohlcv)
        report[name] = summarize(fb, vb)

    out_path = ROOT / "logs" / "compare_vectorbt_variations.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str, ensure_ascii=False)

    print(f"Wrote variations report to: {out_path}")


if __name__ == "__main__":
    raise SystemExit(main())
