"""
Compare all 104 trades between strategy 9a4d45bc and strategy 5c03fd86.
Both strategies are Strategy_RSI_L\S_6 with identical params — they must
produce identical trade lists (entry_time, exit_time, entry_price,
exit_price, pnl, direction, exit_reason).
"""

import asyncio
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
import sqlite3

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"

STRATEGIES = {
    "9a4d45bc": "9a4d45bc-0f41-484e-bfee-40a15011c729",
    "5c03fd86": "5c03fd86-a821-4a62-a783-4d617bf25bc7",
}

END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")


def load_graph(strategy_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        (strategy_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise ValueError(f"Strategy not found: {strategy_id}")
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


def run_strategy(strategy_id: str, candles: pd.DataFrame) -> list:
    graph = load_graph(strategy_id)
    adapter = StrategyBuilderAdapter(graph)
    signals = adapter.generate_signals(candles)

    le = np.asarray(signals.entries.values, dtype=bool)
    se = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(le), dtype=bool)
    )
    lx = (
        np.asarray(signals.exits.values, dtype=bool)
        if signals.exits is not None
        else np.zeros(len(le), dtype=bool)
    )
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
        initial_capital=10_000.0,
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
    return result.trades


def fmt_time(t) -> str:
    return str(t)[:19] if t else "-"


def main():
    import warnings
    warnings.filterwarnings("ignore")

    print("Fetching candles (2025-01-01 to 2026-02-24) ...")
    candles = asyncio.run(fetch_candles())
    print(f"  {len(candles)} bars  {candles.index[0]} .. {candles.index[-1]}\n")

    trades_a = run_strategy(STRATEGIES["9a4d45bc"], candles)
    trades_b = run_strategy(STRATEGIES["5c03fd86"], candles)

    print(f"Strategy 9a4d45bc: {len(trades_a)} trades")
    print(f"Strategy 5c03fd86: {len(trades_b)} trades")
    print()

    max_n = max(len(trades_a), len(trades_b))
    min_n = min(len(trades_a), len(trades_b))

    HDR = (
        f"{'#':<4} {'side':<6} "
        f"{'entry_time_A':<20} {'entry_time_B':<20} "
        f"{'ep_A':>9} {'ep_B':>9}  "
        f"{'exit_time_A':<20} {'exit_time_B':<20}  "
        f"{'xp_A':>10} {'xp_B':>10}  "
        f"{'pnl_A':>8} {'pnl_B':>8}  "
        f"{'reason_A':<18} {'reason_B':<18} status"
    )
    print(HDR)
    print("=" * len(HDR))

    matched = 0
    diverged = 0
    diverged_list = []

    for i in range(max_n):
        a = trades_a[i] if i < len(trades_a) else None
        b = trades_b[i] if i < len(trades_b) else None

        if a is None or b is None:
            tag = "[MISSING_A]" if a is None else "[MISSING_B]"
            t = a or b
            print(
                f"{i+1:<4} {t.direction:<6} "
                f"{'---':<20} {fmt_time(t.entry_time):<20} "
                f"{'---':>9} {t.entry_price:>9.1f}  "
                f"{'---':<20} {fmt_time(t.exit_time):<20}  "
                f"{'---':>10} {t.exit_price:>10.4f}  "
                f"{'---':>8} {t.pnl:>8.2f}  "
                f"{'---':<18} {t.exit_reason:<18} {tag}"
            )
            diverged += 1
            diverged_list.append(i + 1)
            continue

        # Compare key fields
        same_dir = a.direction == b.direction
        same_entry_t = fmt_time(a.entry_time) == fmt_time(b.entry_time)
        same_exit_t = fmt_time(a.exit_time) == fmt_time(b.exit_time)
        same_ep = abs(a.entry_price - b.entry_price) < 0.1
        same_xp = abs(a.exit_price - b.exit_price) < 0.2
        same_pnl = abs(a.pnl - b.pnl) < 0.02
        same_reason = a.exit_reason == b.exit_reason

        ok = all([same_dir, same_entry_t, same_exit_t, same_ep, same_xp, same_pnl, same_reason])

        if ok:
            matched += 1
            status = "[OK]"
        else:
            diverged += 1
            diverged_list.append(i + 1)
            diffs = []
            if not same_dir: diffs.append("dir")
            if not same_entry_t: diffs.append("entry_t")
            if not same_exit_t: diffs.append("exit_t")
            if not same_ep: diffs.append("ep")
            if not same_xp: diffs.append("xp")
            if not same_pnl: diffs.append("pnl")
            if not same_reason: diffs.append("reason")
            status = f"[DIFF:{','.join(diffs)}]"

        print(
            f"{i+1:<4} {a.direction:<6} "
            f"{fmt_time(a.entry_time):<20} {fmt_time(b.entry_time):<20} "
            f"{a.entry_price:>9.1f} {b.entry_price:>9.1f}  "
            f"{fmt_time(a.exit_time):<20} {fmt_time(b.exit_time):<20}  "
            f"{a.exit_price:>10.4f} {b.exit_price:>10.4f}  "
            f"{a.pnl:>8.2f} {b.pnl:>8.2f}  "
            f"{a.exit_reason:<18} {b.exit_reason:<18} {status}"
        )

    print("=" * len(HDR))
    print(f"[OK] MATCHED:  {matched} / {min_n}  -- perfect")
    print(f"[X]  DIVERGED: {diverged} / {max_n}  -- has differences")
    if diverged_list:
        print(f"     Diverged trade numbers: {diverged_list}")
    print()

    # PnL totals
    pnl_a = sum(t.pnl for t in trades_a)
    pnl_b = sum(t.pnl for t in trades_b)
    print(f"Net profit  9a4d45bc={pnl_a:.2f}   5c03fd86={pnl_b:.2f}   gap={pnl_a - pnl_b:.2f}")

    if matched == 104 and diverged == 0:
        print("\n[PASS] PERFECT: both strategies produce identical 104 trades")
        sys.exit(0)
    else:
        print("\n[FAIL] MISMATCH: trades differ -- see rows above")
        sys.exit(1)


if __name__ == "__main__":
    main()
