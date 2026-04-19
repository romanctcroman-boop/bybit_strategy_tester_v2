"""
Engine vs TradingView metrics comparison.
TV reference values are extracted from tv_trades_104.csv (104 real TV trades).
Engine runs strategy 9a4d45bc with canonical params (commission=0.0007, slippage=0).

Compares every metric derivable from the CSV:
  total/winning/losing trades, win_rate, net/gross profit/loss,
  profit_factor, avg_win/loss, largest_win/loss, max_consec,
  avg_bars, long/short breakdown.
"""

import asyncio
import csv
import json
import math
import sqlite3
import sys
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.metrics_calculator import MetricsCalculator, TimeFrequency

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "9a4d45bc-0f41-484e-bfee-40a15011c729"
TV_CSV = r"d:\bybit_strategy_tester_v2\scripts\tv_trades_104.csv"
INITIAL_CAPITAL = 10_000.0
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
UTC3 = timedelta(hours=3)


# ── TV reference: extract from CSV ──────────────────────────────────────────


def build_tv_metrics() -> dict:
    rows = list(csv.DictReader(open(TV_CSV, encoding="utf-8-sig")))
    entries = [r for r in rows if "Entry" in r["Тип"]]
    exits = [r for r in rows if "Exit" in r["Тип"]]

    PNL = [float(r["Чистая прибыль / убыток USDT"]) for r in exits]
    PNL_P = [float(r["Чистая прибыль / убыток %"]) for r in exits]
    SIDE = ["long" if "long" in r["Тип"].lower() else "short" for r in entries]

    wins = [p for p in PNL if p > 0]
    losses = [p for p in PNL if p < 0]
    wins_p = [p for p in PNL_P if p > 0]
    loss_p = [p for p in PNL_P if p < 0]

    max_cw = max_cl = cur_w = cur_l = 0
    for p in PNL:
        if p > 0:
            cur_w += 1
            cur_l = 0
        else:
            cur_l += 1
            cur_w = 0
        max_cw = max(max_cw, cur_w)
        max_cl = max(max_cl, cur_l)

    def parse_bars(entry_row, exit_row) -> int:
        en = datetime.strptime(entry_row["Дата и время"].strip(), "%Y-%m-%d %H:%M") - UTC3
        ex = datetime.strptime(exit_row["Дата и время"].strip(), "%Y-%m-%d %H:%M") - UTC3
        return int((ex - en).total_seconds() / 1800)

    bars = [parse_bars(entries[i], exits[i]) for i in range(len(PNL))]
    win_bars = [bars[i] for i, p in enumerate(PNL) if p > 0]
    loss_bars = [bars[i] for i, p in enumerate(PNL) if p < 0]

    long_pnl = [PNL[i] for i, s in enumerate(SIDE) if s == "long"]
    short_pnl = [PNL[i] for i, s in enumerate(SIDE) if s == "short"]
    lw = [p for p in long_pnl if p > 0]
    ll = [p for p in long_pnl if p < 0]
    sw = [p for p in short_pnl if p > 0]
    sl = [p for p in short_pnl if p < 0]

    gp = sum(wins)
    gl = sum(losses)

    return {
        "total_trades": len(PNL),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": len(wins) / len(PNL) * 100,  # %
        "net_profit": sum(PNL),
        "gross_profit": gp,
        "gross_loss": gl,
        "profit_factor": abs(gp / gl) if gl else float("inf"),
        "avg_win_usd": gp / len(wins) if wins else 0,
        "avg_loss_usd": gl / len(losses) if losses else 0,
        "avg_win_pct": sum(wins_p) / len(wins_p) if wins_p else 0,
        "avg_loss_pct": sum(loss_p) / len(loss_p) if loss_p else 0,
        "largest_win_usd": max(PNL),
        "largest_loss_usd": min(PNL),
        "largest_win_pct": max(PNL_P),
        "largest_loss_pct": min(PNL_P),
        "max_consecutive_wins": max_cw,
        "max_consecutive_losses": max_cl,
        "avg_bars_in_trade": sum(bars) / len(bars) if bars else 0,
        "avg_bars_in_win": sum(win_bars) / len(win_bars) if win_bars else 0,
        "avg_bars_in_loss": sum(loss_bars) / len(loss_bars) if loss_bars else 0,
        "long_trades": len(long_pnl),
        "long_winning_trades": len(lw),
        "long_losing_trades": len(ll),
        "long_net_profit": sum(long_pnl),
        "long_gross_profit": sum(lw),
        "long_gross_loss": sum(ll),
        "long_win_rate": len(lw) / len(long_pnl) * 100 if long_pnl else 0,
        "short_trades": len(short_pnl),
        "short_winning_trades": len(sw),
        "short_losing_trades": len(sl),
        "short_net_profit": sum(short_pnl),
        "short_gross_profit": sum(sw),
        "short_gross_loss": sum(sl),
        "short_win_rate": len(sw) / len(short_pnl) * 100 if short_pnl else 0,
    }


# ── Engine run ──────────────────────────────────────────────────────────────


def load_graph() -> dict:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    graph = {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if gp and gp.get("main_strategy"):
        graph["main_strategy"] = gp["main_strategy"]
    return graph


async def fetch_candles() -> pd.DataFrame:
    svc = BacktestService()
    return await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=START_DATE,
        end_date=END_DATE,
    )


def run_engine(candles: pd.DataFrame):
    graph = load_graph()
    signals = StrategyBuilderAdapter(graph).generate_signals(candles)
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
    result = FallbackEngineV4().run(
        BacktestInput(
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
    )
    return result


def build_engine_metrics(result) -> dict:
    """Extract the same set of metrics from the engine result."""
    trades = result.trades
    PNL = [t.pnl for t in trades]
    SIDE = [t.direction for t in trades]

    wins = [p for p in PNL if p > 0]
    losses = [p for p in PNL if p < 0]
    gp = sum(wins)
    gl = sum(losses)

    # Bars held per trade
    def bars_held(t) -> int:
        if hasattr(t, "bars_held") and t.bars_held:
            return int(t.bars_held)
        if t.entry_time is not None and t.exit_time is not None:
            delta = t.exit_time - t.entry_time
            # Handle both timedelta and numpy.timedelta64
            try:
                secs = delta.total_seconds()
            except AttributeError:
                secs = float(delta) / 1e9  # numpy.timedelta64 in nanoseconds
            return max(0, int(secs / 1800))
        return 0

    bars = [bars_held(t) for t in trades]
    win_bars = [bars[i] for i, p in enumerate(PNL) if p > 0]
    loss_bars = [bars[i] for i, p in enumerate(PNL) if p < 0]

    long_pnl = [PNL[i] for i, s in enumerate(SIDE) if s == "long"]
    short_pnl = [PNL[i] for i, s in enumerate(SIDE) if s == "short"]
    lw = [p for p in long_pnl if p > 0]
    ll = [p for p in long_pnl if p < 0]
    sw = [p for p in short_pnl if p > 0]
    sl = [p for p in short_pnl if p < 0]

    # pnl_pct per trade: TV uses net_pnl / position_value
    # Better: use MetricsCalculator for these
    td = [
        {
            "pnl": t.pnl,
            "pnl_pct": getattr(t, "pnl_pct", t.pnl / INITIAL_CAPITAL * 100),
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "direction": t.direction,
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "exit_reason": str(t.exit_reason),
            "commission": getattr(t, "commission", 0.0),
            "size": getattr(t, "size", 0.0),
            "bars_held": bars_held(t),
        }
        for t in trades
    ]

    mc = MetricsCalculator.calculate_trade_metrics(td)

    return {
        "total_trades": len(PNL),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": len(wins) / len(PNL) * 100,
        "net_profit": sum(PNL),
        "gross_profit": gp,
        "gross_loss": gl,
        "profit_factor": abs(gp / gl) if gl else float("inf"),
        "avg_win_usd": gp / len(wins) if wins else 0,
        "avg_loss_usd": gl / len(losses) if losses else 0,
        "avg_win_pct": mc.avg_win_pct * 100,
        "avg_loss_pct": mc.avg_loss_pct * 100,
        "largest_win_usd": max(PNL),
        "largest_loss_usd": min(PNL),
        "largest_win_pct": mc.largest_win_pct * 100,
        "largest_loss_pct": mc.largest_loss_pct * 100,
        "max_consecutive_wins": mc.max_consec_wins,
        "max_consecutive_losses": mc.max_consec_losses,
        "avg_bars_in_trade": sum(bars) / len(bars) if bars else 0,
        "avg_bars_in_win": sum(win_bars) / len(win_bars) if win_bars else 0,
        "avg_bars_in_loss": sum(loss_bars) / len(loss_bars) if loss_bars else 0,
        "long_trades": len(long_pnl),
        "long_winning_trades": len(lw),
        "long_losing_trades": len(ll),
        "long_net_profit": sum(long_pnl),
        "long_gross_profit": sum(lw),
        "long_gross_loss": sum(ll),
        "long_win_rate": len(lw) / len(long_pnl) * 100 if long_pnl else 0,
        "short_trades": len(short_pnl),
        "short_winning_trades": len(sw),
        "short_losing_trades": len(sl),
        "short_net_profit": sum(short_pnl),
        "short_gross_profit": sum(sw),
        "short_gross_loss": sum(sl),
        "short_win_rate": len(sw) / len(short_pnl) * 100 if short_pnl else 0,
    }


# ── Comparison ──────────────────────────────────────────────────────────────

# Tolerances: (absolute, relative)
TOLERANCES = {
    "net_profit": (0.02, 1e-3),
    "gross_profit": (0.05, 1e-3),
    "gross_loss": (0.05, 1e-3),
    "avg_win_usd": (0.01, 1e-3),
    "avg_loss_usd": (0.01, 1e-3),
    "avg_win_pct": (0.01, 5e-3),  # TV rounds to 2dp
    "avg_loss_pct": (0.01, 5e-3),
    "largest_win_usd": (0.01, 1e-3),
    "largest_loss_usd": (0.01, 1e-3),
    "largest_win_pct": (0.01, 5e-3),
    "largest_loss_pct": (0.01, 5e-3),
    "profit_factor": (0.001, 1e-3),
    "long_net_profit": (0.02, 2e-3),
    "long_gross_profit": (0.05, 2e-3),
    "long_gross_loss": (0.05, 2e-3),
    "short_net_profit": (0.02, 2e-3),
    "short_gross_profit": (0.05, 2e-3),
    "short_gross_loss": (0.05, 2e-3),
    "avg_bars_in_trade": (1.0, 0.01),  # bar counts can differ by 1
    "avg_bars_in_win": (1.0, 0.01),
    "avg_bars_in_loss": (1.0, 0.02),
}


def is_match(key, tv_val, eng_val) -> bool:
    abs_tol, rel_tol = TOLERANCES.get(key, (0, 1e-5))
    if isinstance(tv_val, int) and isinstance(eng_val, int):
        return tv_val == eng_val
    try:
        return math.isclose(float(tv_val), float(eng_val), rel_tol=rel_tol, abs_tol=abs_tol)
    except (TypeError, ValueError):
        return str(tv_val) == str(eng_val)


def main():
    print("Fetching candles ...")
    candles = asyncio.run(fetch_candles())
    print(f"  {len(candles)} bars\n")

    print("Running engine ...")
    result = run_engine(candles)
    print(f"  {len(result.trades)} trades\n")

    tv = build_tv_metrics()
    eng = build_engine_metrics(result)

    keys = list(tv.keys())

    HDR = f"{'Metric':<30} {'TV (reference)':>16} {'Engine':>16} {'diff':>10} status"
    print(HDR)
    print("=" * len(HDR))

    matched = mismatched = 0
    mismatch_list = []

    for k in keys:
        tv_v = tv[k]
        eng_v = eng.get(k, None)

        if eng_v is None:
            print(f"  {k:<30} {tv_v!s:>16} {'---':>16} {'---':>10} [MISSING]")
            mismatched += 1
            mismatch_list.append(k)
            continue

        ok = is_match(k, tv_v, eng_v)

        def fmt(v):
            if isinstance(v, int):
                return str(v)
            try:
                f = float(v)
                return f"{f:.4f}" if abs(f) < 10000 else f"{f:.2f}"
            except (TypeError, ValueError):
                return str(v)

        try:
            diff = float(eng_v) - float(tv_v)
            diff_s = f"{diff:+.4f}" if abs(diff) < 10000 else f"{diff:+.2f}"
        except (TypeError, ValueError):
            diff_s = "---"

        status = "[OK]" if ok else "[DIFF]"
        if ok:
            matched += 1
        else:
            mismatched += 1
            mismatch_list.append(k)

        print(f"  {k:<30} {fmt(tv_v):>16} {fmt(eng_v):>16} {diff_s:>10} {status}")

    print("=" * len(HDR))
    print(f"\n[OK] MATCHED:    {matched} / {len(keys)}")
    print(f"[X]  MISMATCHED: {mismatched} / {len(keys)}")

    if mismatch_list:
        print("\nMismatched metrics:")
        for k in mismatch_list:
            print(f"  {k}: TV={tv.get(k, '?')}  Engine={eng.get(k, '?')}")

    if mismatched == 0:
        print(f"\n[PASS] All {matched} metrics match TV reference")
        sys.exit(0)
    else:
        print(f"\n[FAIL] {mismatched} metrics differ from TV")
        sys.exit(1)


if __name__ == "__main__":
    main()
