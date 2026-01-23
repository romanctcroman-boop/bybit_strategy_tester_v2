"""Compare BacktestEngine vectorbt vs fallback outputs for identical signals

Runs a single small RSI backtest using both internal _run_vectorbt and
_run_fallback and reports differences in metrics, trades and equity.
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
    # data columns: open_time, open_price, high_price, low_price, close_price, volume
    df = pd.DataFrame(
        data, columns=["open_time", "open", "high", "low", "close", "volume"]
    )
    # open_time likely in ms
    try:
        df["open_time"] = pd.to_datetime(df["open_time"].astype("int64"), unit="ms")
    except Exception:
        df["open_time"] = pd.to_datetime(df["open_time"])
    df = df.set_index("open_time")
    # Ensure numeric types
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def dump(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, default=str, indent=2, ensure_ascii=False)


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

    config = BacktestConfig(
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        strategy_type="rsi",
        strategy_params={"period": 21, "oversold": 30, "overbought": 70},
        # Run long-only for vectorbt parity checks (vectorbt + percent sizing
        # does not support signal-based position reversal). Use fallback for
        # bidirectional comparisons later if needed.
        direction="long",
        initial_capital=10000.0,
        leverage=10.0,
        position_size=1.0,
    )

    strategy = get_strategy(config.strategy_type, config.strategy_params)
    signals = strategy.generate_signals(ohlcv)

    engine = BacktestEngine()

    print("Running fallback engine...")
    res_fallback = engine._run_fallback(config, ohlcv, signals)
    print("Running vectorbt engine...")
    res_vectorbt = engine._run_vectorbt(config, ohlcv, signals)

    # Summarize
    def metrics_to_dict(m):
        # Pydantic model -> dict
        try:
            return m.model_dump()
        except Exception:
            try:
                return m.dict()
            except Exception:
                return {}

    mf = metrics_to_dict(res_fallback.metrics)
    mv = metrics_to_dict(res_vectorbt.metrics)

    diff = {
        "metrics_diff": {},
        "trades": {
            "fallback_len": len(res_fallback.trades),
            "vectorbt_len": len(res_vectorbt.trades),
        },
        "equity": {
            "fallback_final": res_fallback.final_equity,
            "vectorbt_final": res_vectorbt.final_equity,
            "equity_len_fallback": len(res_fallback.equity_curve.equity)
            if res_fallback.equity_curve
            else 0,
            "equity_len_vectorbt": len(res_vectorbt.equity_curve.equity)
            if res_vectorbt.equity_curve
            else 0,
        },
    }

    # Compare selected keys
    keys = set(list(mf.keys()) + list(mv.keys()))
    for k in sorted(keys):
        a = mf.get(k)
        b = mv.get(k)
        try:
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                diff_val = float(a) - float(b)
                diff["metrics_diff"][k] = {
                    "fallback": a,
                    "vectorbt": b,
                    "diff": diff_val,
                }
            else:
                if a != b:
                    diff["metrics_diff"][k] = {"fallback": a, "vectorbt": b}
        except Exception:
            diff["metrics_diff"][k] = {"fallback": a, "vectorbt": b}

    # sample trades
    sample = {
        "fallback_trades_sample": [
            t.__dict__ if hasattr(t, "__dict__") else t for t in res_fallback.trades[:5]
        ],
        "vectorbt_trades_sample": [
            t.__dict__ if hasattr(t, "__dict__") else t for t in res_vectorbt.trades[:5]
        ],
    }

    out = {
        "config": config.model_dump()
        if hasattr(config, "model_dump")
        else config.dict(),
        "summary": diff,
        "sample_trades": sample,
    }

    out_path = ROOT / "logs" / "compare_vectorbt_vs_fallback.json"
    dump(out, out_path)
    print(f"Wrote comparison to: {out_path}")
    print("Metric differences (top 10):")
    # print some diffs
    i = 0
    for k, v in diff["metrics_diff"].items():
        print(k, v)
        i += 1
        if i >= 10:
            break


if __name__ == "__main__":
    raise SystemExit(main())
