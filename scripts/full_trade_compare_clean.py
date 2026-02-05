"""Full per-trade comparison between fallback and vectorbt engines (clean copy).

Produces:
- logs/full_trades_fallback.json
- logs/full_trades_vectorbt.json
- logs/full_trade_matches.json

This is a clean, standalone script to avoid editing the corrupted original.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dateutil import parser

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.fast_optimizer import load_candles_fast
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategies import get_strategy

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data.sqlite3"


def dump(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, default=str, indent=2, ensure_ascii=False)


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


def trade_to_dict(t: Any) -> dict[str, Any]:
    try:
        return t.model_dump() if hasattr(t, "model_dump") else t.dict()
    except Exception:
        try:
            return t.dict()
        except Exception:
            return t.__dict__ if hasattr(t, "__dict__") else dict(t)


def _parse_dt(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        import pandas as _pd

        if isinstance(v, _pd.Timestamp):
            return v.to_pydatetime()
    except Exception:
        pass
    try:
        return parser.parse(v)
    except Exception:
        return None


def pairwise_match(
    fb_trades: list[dict[str, Any]],
    vb_trades: list[dict[str, Any]],
    max_time_diff_seconds: int = 86400,
) -> dict[str, Any]:
    for t in fb_trades:
        t["entry_dt"] = _parse_dt(t.get("entry_time"))
        t["exit_dt"] = _parse_dt(t.get("exit_time"))
    for t in vb_trades:
        t["entry_dt"] = _parse_dt(t.get("entry_time"))
        t["exit_dt"] = _parse_dt(t.get("exit_time"))

    used_vb = set()
    matches: list[dict[str, Any]] = []

    def num(x: Any) -> float | None:
        try:
            return float(x)
        except Exception:
            return None

    def pct_diff(a: float | None, b: float | None) -> float | None:
        if a is None or b is None:
            return None
        if b == 0:
            return None
        return (a - b) / (abs(b) if abs(b) > 0 else 1) * 100

    for i, ft in enumerate(fb_trades):
        best_j = None
        best_dt = None
        for j, vt in enumerate(vb_trades):
            if j in used_vb:
                continue
            if ft.get("side") != vt.get("side"):
                continue
            if not ft.get("entry_dt") or not vt.get("entry_dt"):
                continue
            dt = abs((ft["entry_dt"] - vt["entry_dt"]).total_seconds())
            if best_dt is None or dt < best_dt:
                best_dt = dt
                best_j = j

        if (
            best_j is not None
            and best_dt is not None
            and best_dt <= max_time_diff_seconds
        ):
            used_vb.add(best_j)
            vt = vb_trades[best_j]

            entry_time_diff = best_dt
            exit_time_diff = None
            try:
                if ft.get("exit_dt") and vt.get("exit_dt"):
                    exit_time_diff = abs(
                        (ft["exit_dt"] - vt["exit_dt"]).total_seconds()
                    )
            except Exception:
                exit_time_diff = None

            entry_price_a = num(ft.get("entry_price"))
            entry_price_b = num(vt.get("entry_price"))
            exit_price_a = num(ft.get("exit_price"))
            exit_price_b = num(vt.get("exit_price"))
            size_a = num(ft.get("size"))
            size_b = num(vt.get("size"))
            pnl_a = num(ft.get("pnl"))
            pnl_b = num(vt.get("pnl"))
            fees_a = num(ft.get("fees"))
            fees_b = num(vt.get("fees"))
            mfe_a = num(ft.get("mfe"))
            mfe_b = num(vt.get("mfe"))
            mae_a = num(ft.get("mae"))
            mae_b = num(vt.get("mae"))

            match = {
                "fallback_idx": i,
                "vectorbt_idx": best_j,
                "entry_time_diff_s": entry_time_diff,
                "exit_time_diff_s": exit_time_diff,
                "entry_price": {
                    "fallback": entry_price_a,
                    "vectorbt": entry_price_b,
                    "diff": None
                    if entry_price_a is None or entry_price_b is None
                    else entry_price_a - entry_price_b,
                    "pct_diff": pct_diff(entry_price_a, entry_price_b),
                },
                "exit_price": {
                    "fallback": exit_price_a,
                    "vectorbt": exit_price_b,
                    "diff": None
                    if exit_price_a is None or exit_price_b is None
                    else exit_price_a - exit_price_b,
                    "pct_diff": pct_diff(exit_price_a, exit_price_b),
                },
                "size": {
                    "fallback": size_a,
                    "vectorbt": size_b,
                    "diff": None
                    if size_a is None or size_b is None
                    else size_a - size_b,
                },
                "pnl": {
                    "fallback": pnl_a,
                    "vectorbt": pnl_b,
                    "diff": None if pnl_a is None or pnl_b is None else pnl_a - pnl_b,
                    "pct_diff": pct_diff(pnl_a, pnl_b),
                },
                "fees": {
                    "fallback": fees_a,
                    "vectorbt": fees_b,
                    "diff": None
                    if fees_a is None or fees_b is None
                    else fees_a - fees_b,
                },
                "mfe": {
                    "fallback": mfe_a,
                    "vectorbt": mfe_b,
                    "diff": None if mfe_a is None or mfe_b is None else mfe_a - mfe_b,
                },
                "mae": {
                    "fallback": mae_a,
                    "vectorbt": mae_b,
                    "diff": None if mae_a is None or mae_b is None else mae_a - mae_b,
                },
                "fallback": ft,
                "vectorbt": vt,
            }
            matches.append(match)
        else:
            matches.append(
                {
                    "fallback_idx": i,
                    "vectorbt_idx": None,
                    "fallback": ft,
                    "vectorbt": None,
                }
            )

    unmatched_vb = [
        {"vectorbt_idx": j, "vectorbt": vt}
        for j, vt in enumerate(vb_trades)
        if j not in used_vb
    ]

    return {"matches": matches, "unmatched_vectorbt": unmatched_vb}


def main() -> int:
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
        direction="both",
        initial_capital=10000.0,
        leverage=10.0,
        position_size=1.0,
    )

    strategy = get_strategy(config.strategy_type, config.strategy_params)
    signals = strategy.generate_signals(ohlcv)

    engine = BacktestEngine()

    print("Running fallback engine (this may take a moment)...")
    res_fallback = engine._run_fallback(config, ohlcv, signals)
    print("Running vectorbt engine (this may take a moment)...")
    res_vectorbt = engine._run_vectorbt(config, ohlcv, signals)

    # Serialize full trades
    fb_trades = [trade_to_dict(t) for t in res_fallback.trades]
    vb_trades = [trade_to_dict(t) for t in res_vectorbt.trades]

    cfg_obj = (
        config.model_dump()
        if hasattr(config, "model_dump")
        else (config.dict() if hasattr(config, "dict") else {})
    )
    dump(
        {"config": cfg_obj, "trades": fb_trades},
        ROOT / "logs" / "full_trades_fallback.json",
    )
    dump(
        {"config": cfg_obj, "trades": vb_trades},
        ROOT / "logs" / "full_trades_vectorbt.json",
    )

    print(f"Wrote full trades: fallback={len(fb_trades)} vectorbt={len(vb_trades)}")

    # Run matcher
    match_result = pairwise_match(fb_trades, vb_trades, max_time_diff_seconds=86400)
    dump(match_result, ROOT / "logs" / "full_trade_matches.json")
    print("Wrote match result to logs/full_trade_matches.json")

    # Print quick summary
    matched = sum(
        1 for m in match_result.get("matches", []) if m.get("vectorbt_idx") is not None
    )
    unmatched_vb = len(match_result.get("unmatched_vectorbt", []))
    print(f"Matched pairs: {matched}, Unmatched vectorbt trades: {unmatched_vb}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
