"""
Compare ALL MetricsCalculator metrics between strategy 9a4d45bc and 5c03fd86.
Both are Strategy_RSI_L/S_6 with identical params — all metrics must match.
"""

import asyncio
import json
import math
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import sqlite3

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.metrics_calculator import MetricsCalculator, TimeFrequency

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGIES = {
    "9a4d45bc": "9a4d45bc-0f41-484e-bfee-40a15011c729",
    "5c03fd86": "5c03fd86-a821-4a62-a783-4d617bf25bc7",
}
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
INITIAL_CAPITAL = 10_000.0


def load_graph(strategy_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        (strategy_id,),
    ).fetchone()
    conn.close()
    name, blocks_raw, conns_raw, graph_raw = row
    blocks = json.loads(blocks_raw) if isinstance(blocks_raw, str) else (blocks_raw or [])
    conns = json.loads(conns_raw) if isinstance(conns_raw, str) else (conns_raw or [])
    graph_parsed = json.loads(graph_raw) if isinstance(graph_raw, str) else (graph_raw or {})
    graph: dict = {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if graph_parsed and graph_parsed.get("main_strategy"):
        graph["main_strategy"] = graph_parsed["main_strategy"]
    return graph


async def fetch_candles() -> pd.DataFrame:
    svc = BacktestService()
    return await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=START_DATE,
        end_date=END_DATE,
    )


def run_strategy(strategy_id: str, candles: pd.DataFrame) -> tuple:
    """Returns (trades_list, equity_curve, result)"""
    graph = load_graph(strategy_id)
    adapter = StrategyBuilderAdapter(graph)
    signals = adapter.generate_signals(candles)

    le = np.asarray(signals.entries.values, dtype=bool)
    se = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(le), dtype=bool)
    )
    lx = np.asarray(signals.exits.values, dtype=bool) if signals.exits is not None else np.zeros(len(le), dtype=bool)
    sx = (
        np.asarray(signals.short_exits.values, dtype=bool)
        if signals.short_exits is not None
        else np.zeros(len(le), dtype=bool)
    )

    bt_input = BacktestInput(
        candles=candles,
        long_entries=le,
        long_exits=lx,
        short_entries=se,
        short_exits=sx,
        initial_capital=INITIAL_CAPITAL,
        position_size=0.10,
        use_fixed_amount=True,
        fixed_amount=100.0,
        leverage=10,
        stop_loss=0.091,
        take_profit=0.015,
        taker_fee=0.0007,
        slippage=0.0,
        direction=TradeDirection.BOTH,
        pyramiding=1,
        interval="30",
    )

    result = FallbackEngineV4().run(bt_input)
    return result.trades, result.equity_curve, result


def trades_to_dicts(trades) -> list[dict]:
    out = []
    for t in trades:
        out.append(
            {
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct if hasattr(t, "pnl_pct") else 0.0,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "direction": t.direction,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "exit_reason": str(t.exit_reason),
                "commission": getattr(t, "commission", 0.0),
                "size": getattr(t, "size", 0.0),
                "bars_held": getattr(t, "bars_held", 0),
            }
        )
    return out


def is_close(a, b, rel_tol=1e-6, abs_tol=1e-9) -> bool:
    """True if a and b are numerically close."""
    if a == b:
        return True
    if math.isnan(a) and math.isnan(b):
        return True
    if math.isinf(a) and math.isinf(b) and (a > 0) == (b > 0):
        return True
    try:
        return math.isclose(float(a), float(b), rel_tol=rel_tol, abs_tol=abs_tol)
    except (TypeError, ValueError):
        return str(a) == str(b)


def main():
    print("Fetching candles (2025-01-01 to 2026-02-24) ...")
    candles = asyncio.run(fetch_candles())
    print(f"  {len(candles)} bars  {candles.index[0]} .. {candles.index[-1]}\n")

    print("Running strategy 9a4d45bc ...")
    trades_a, equity_a, _ = run_strategy(STRATEGIES["9a4d45bc"], candles)
    print("Running strategy 5c03fd86 ...")
    trades_b, equity_b, _ = run_strategy(STRATEGIES["5c03fd86"], candles)

    print(f"\n9a4d45bc: {len(trades_a)} trades, equity_curve len={len(equity_a)}")
    print(f"5c03fd86: {len(trades_b)} trades, equity_curve len={len(equity_b)}\n")

    # Convert to dicts for MetricsCalculator
    td_a = trades_to_dicts(trades_a)
    td_b = trades_to_dicts(trades_b)

    eq_a = np.asarray(equity_a)
    eq_b = np.asarray(equity_b)

    # Years covered
    days = (END_DATE - START_DATE).days
    years = days / 365.25

    # Calculate all metrics
    print("Calculating metrics for 9a4d45bc ...")
    metrics_a = MetricsCalculator.calculate_all(
        td_a, eq_a, INITIAL_CAPITAL, years=years, frequency=TimeFrequency.HOURLY
    )
    print("Calculating metrics for 5c03fd86 ...")
    metrics_b = MetricsCalculator.calculate_all(
        td_b, eq_b, INITIAL_CAPITAL, years=years, frequency=TimeFrequency.HOURLY
    )

    # Compare every key
    all_keys = sorted(set(metrics_a.keys()) | set(metrics_b.keys()))
    print(f"\nTotal metrics: {len(all_keys)}\n")

    HDR = f"{'Metric':<45} {'9a4d45bc':>18} {'5c03fd86':>18} {'match':>8}"
    print(HDR)
    print("=" * len(HDR))

    matched = 0
    mismatched = 0
    missing = 0
    mismatch_list = []

    for key in all_keys:
        in_a = key in metrics_a
        in_b = key in metrics_b

        if not in_a or not in_b:
            tag = "[ONLY_A]" if not in_b else "[ONLY_B]"
            val = metrics_a.get(key, metrics_b.get(key))
            print(f"  {key:<45} {val!s:>18} {'---':>18} {tag:>8}")
            missing += 1
            mismatch_list.append((key, "MISSING"))
            continue

        va = metrics_a[key]
        vb = metrics_b[key]

        try:
            close = is_close(float(va), float(vb), rel_tol=1e-5, abs_tol=1e-7)
        except (TypeError, ValueError):
            close = str(va) == str(vb)

        if close:
            matched += 1
            status = "[OK]"
        else:
            mismatched += 1
            status = "[DIFF]"
            mismatch_list.append((key, va, vb))

        # Format floats nicely
        def fmt(v):
            try:
                f = float(v)
                if abs(f) >= 1000:
                    return f"{f:.2f}"
                elif abs(f) >= 1:
                    return f"{f:.4f}"
                elif abs(f) >= 0.0001:
                    return f"{f:.6f}"
                else:
                    return f"{f:.8f}"
            except (TypeError, ValueError):
                return str(v)

        print(f"  {key:<45} {fmt(va):>18} {fmt(vb):>18} {status:>8}")

    print("=" * len(HDR))
    print(f"\n[OK] MATCHED:    {matched} / {len(all_keys)}")
    print(f"[X]  MISMATCHED: {mismatched} / {len(all_keys)}")
    print(f"[?]  MISSING:    {missing} / {len(all_keys)}")

    if mismatch_list:
        print("\nDifferences:")
        for item in mismatch_list:
            if len(item) == 2:
                print(f"  {item[0]}: {item[1]}")
            else:
                print(f"  {item[0]}: 9a4d45bc={item[1]}  5c03fd86={item[2]}")

    if mismatched == 0 and missing == 0:
        print(f"\n[PASS] PERFECT: all {matched} metrics are identical")
        sys.exit(0)
    else:
        print(f"\n[FAIL] {mismatched + missing} metrics differ")
        sys.exit(1)


if __name__ == "__main__":
    main()
