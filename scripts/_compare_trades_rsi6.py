"""
Trade-by-trade comparison: RSI_6 engine trades vs TV q4.csv (47 known trades).

For each of our 103 engine trades:
  1. Find matching TV trade by (side, entry_price rounded to 0.1)
  2. Compare exit_time, exit_price, pnl, exit_reason
  3. Show DIFF column for every mismatch

Also shows:
  - TV trades not found in our engine (missing engine trades)
  - Our engine trades not found in TV (extra engine trades vs TV subset)
  - Running PnL comparison
"""

import json
import sqlite3
import sys
from datetime import UTC, datetime
from typing import NamedTuple

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5c03fd86-a821-4a62-a783-4d617bf25bc7"


class TvTrade(NamedTuple):
    num: int
    side: str
    entry_utc3: str
    entry_price: float
    exit_reason: str
    exit_utc3: str
    exit_price: float
    pnl: float


# All 47 TV trades from q4.csv (UTC+3)
TV_TRADES: list[TvTrade] = [
    TvTrade(1, "short", "2025-01-01 19:30", 94126.2, "SL Hit", "2025-01-07 03:30", 102691.7, -92.46),
    TvTrade(2, "short", "2025-01-07 04:00", 101996.9, "TP Hit", "2025-01-07 14:30", 100466.9, 13.61),
    TvTrade(3, "long", "2025-01-08 00:00", 96494.5, "TP Hit", "2025-01-15 16:30", 97942.0, 13.59),
    TvTrade(4, "short", "2025-01-15 20:00", 98970.0, "TP Hit", "2025-01-16 17:30", 97485.4, 13.61),
    TvTrade(5, "short", "2025-01-17 06:00", 101068.3, "TP Hit", "2025-01-20 03:30", 99552.2, 13.61),
    TvTrade(6, "short", "2025-01-20 15:30", 106664.3, "TP Hit", "2025-01-20 18:30", 105064.3, 13.61),
    TvTrade(7, "short", "2025-01-21 17:00", 104455.7, "TP Hit", "2025-01-21 18:00", 102888.8, 13.61),
    TvTrade(8, "short", "2025-01-22 00:00", 106100.0, "TP Hit", "2025-01-22 16:30", 104508.5, 13.61),
    TvTrade(9, "short", "2025-01-23 18:30", 104189.8, "TP Hit", "2025-01-23 23:30", 102626.9, 13.61),
    TvTrade(10, "short", "2025-01-24 22:00", 106304.3, "TP Hit", "2025-01-24 23:30", 104709.7, 13.61),
    TvTrade(11, "short", "2025-01-26 08:00", 105142.8, "TP Hit", "2025-01-27 02:00", 103565.6, 13.61),
    TvTrade(12, "long", "2025-01-27 03:30", 102800.0, "TP Hit", "2025-01-29 23:00", 104342.0, 13.59),
    TvTrade(13, "short", "2025-01-30 01:00", 103679.0, "TP Hit", "2025-01-31 22:00", 102123.8, 13.61),
    TvTrade(14, "short", "2025-02-04 05:30", 101020.9, "TP Hit", "2025-02-04 08:00", 99505.5, 13.61),
    TvTrade(15, "short", "2025-02-06 10:30", 98144.7, "TP Hit", "2025-02-06 19:30", 96672.5, 13.61),
    TvTrade(16, "short", "2025-02-07 18:30", 98466.4, "TP Hit", "2025-02-07 22:30", 96989.4, 13.61),
    TvTrade(17, "short", "2025-02-09 05:30", 96680.0, "TP Hit", "2025-02-10 00:30", 95229.8, 13.61),
    TvTrade(18, "short", "2025-02-10 15:00", 97629.9, "TP Hit", "2025-02-11 20:00", 96165.4, 13.61),
    TvTrade(19, "long", "2025-02-11 23:30", 95233.2, "TP Hit", "2025-02-12 19:30", 96661.7, 13.59),
    TvTrade(20, "short", "2025-02-12 21:00", 97321.3, "TP Hit", "2025-02-13 09:30", 95861.4, 13.61),
    TvTrade(21, "short", "2025-02-14 04:00", 96723.2, "TP Hit", "2025-02-17 19:30", 95272.3, 13.61),
    TvTrade(22, "short", "2025-02-19 16:00", 96157.2, "TP Hit", "2025-02-24 17:30", 94714.8, 13.61),
    TvTrade(23, "long", "2025-02-25 14:00", 88176.2, "TP Hit", "2025-02-25 15:00", 89498.9, 13.59),
    TvTrade(24, "short", "2025-02-27 14:30", 86599.6, "TP Hit", "2025-02-27 17:30", 85300.6, 13.61),
    TvTrade(25, "short", "2025-02-28 21:00", 83566.2, "SL Hit", "2025-03-02 19:30", 91170.8, -92.46),
    TvTrade(26, "short", "2025-03-03 04:30", 93061.1, "TP Hit", "2025-03-03 09:30", 91665.1, 13.61),
    TvTrade(27, "short", "2025-03-03 17:30", 93163.9, "TP Hit", "2025-03-03 18:00", 89270.3, 40.42),
    TvTrade(28, "short", "2025-03-05 00:00", 86841.8, "TP Hit", "2025-03-07 03:30", 85539.1, 13.61),
    TvTrade(29, "short", "2025-03-07 18:30", 89183.3, "TP Hit", "2025-03-07 19:00", 87845.5, 13.61),
    TvTrade(30, "long", "2025-03-09 18:00", 83558.3, "TP Hit", "2025-03-14 18:00", 84811.7, 13.59),
    TvTrade(31, "short", "2025-03-14 21:00", 84332.4, "TP Hit", "2025-03-16 14:00", 83067.4, 13.61),
    TvTrade(32, "long", "2025-03-16 15:30", 82818.4, "TP Hit", "2025-03-16 19:00", 84060.7, 13.59),
    TvTrade(33, "short", "2025-03-17 23:30", 84083.2, "TP Hit", "2025-03-18 07:30", 82821.9, 13.61),
    TvTrade(34, "short", "2025-03-19 04:30", 82812.5, "TP Hit", "2025-03-31 01:00", 81570.3, 13.61),
    TvTrade(35, "short", "2025-03-31 20:00", 83246.7, "TP Hit", "2025-04-03 15:30", 81997.9, 13.61),
    TvTrade(36, "short", "2025-04-06 05:00", 83390.0, "TP Hit", "2025-04-06 19:30", 82139.1, 13.61),
    TvTrade(37, "long", "2025-04-06 22:30", 79474.0, "TP Hit", "2025-04-07 17:00", 80666.2, 13.59),
    TvTrade(38, "short", "2025-04-08 02:30", 79821.1, "TP Hit", "2025-04-08 17:30", 78623.7, 13.61),
    TvTrade(39, "short", "2025-04-10 05:00", 82220.2, "TP Hit", "2025-04-10 16:30", 80986.8, 13.61),
    TvTrade(40, "short", "2025-04-11 16:00", 82093.8, "SL Hit", "2025-04-22 16:00", 89564.4, -92.46),
    TvTrade(41, "short", "2025-04-23 05:00", 92612.0, "SL Hit", "2025-05-08 18:30", 101039.7, -92.46),
    TvTrade(42, "short", "2025-05-09 05:30", 102685.6, "TP Hit", "2025-05-12 21:30", 101145.3, 13.61),
    TvTrade(43, "short", "2025-05-13 15:30", 103496.3, "TP Hit", "2025-05-15 10:00", 101943.8, 13.61),
    TvTrade(44, "short", "2025-05-15 21:30", 103450.6, "TP Hit", "2025-06-05 22:00", 101898.8, 13.61),
    TvTrade(45, "long", "2025-06-06 00:30", 100946.9, "TP Hit", "2025-06-06 06:30", 102461.2, 13.59),
    TvTrade(46, "short", "2025-06-06 16:00", 103704.8, "TP Hit", "2025-06-21 23:00", 102149.2, 13.61),
    TvTrade(47, "short", "2025-06-23 12:00", 101826.8, "TP Hit", "2025-06-23 19:00", 100299.3, 13.61),
]


def utc3_to_utc(s: str) -> pd.Timestamp:
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
    return pd.Timestamp(dt) - pd.Timedelta(hours=3)


def load_ohlcv() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 2, 25, tzinfo=UTC).timestamp() * 1000)
    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


def load_strategy_graph() -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cursor.fetchone()
    col_names = [d[0] for d in cursor.description]
    conn.close()
    strat = dict(zip(col_names, row, strict=True))
    builder_blocks = (
        json.loads(strat["builder_blocks"]) if isinstance(strat["builder_blocks"], str) else strat["builder_blocks"]
    )
    builder_connections = (
        json.loads(strat["builder_connections"])
        if isinstance(strat["builder_connections"], str)
        else strat["builder_connections"]
    )
    builder_graph_raw = (
        json.loads(strat["builder_graph"]) if isinstance(strat["builder_graph"], str) else strat["builder_graph"]
    )
    graph = {
        "name": strat["name"],
        "description": strat.get("description") or "",
        "blocks": builder_blocks,
        "connections": builder_connections,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if builder_graph_raw and isinstance(builder_graph_raw, dict) and builder_graph_raw.get("main_strategy"):
        graph["main_strategy"] = builder_graph_raw["main_strategy"]
    return graph


def load_bt_params() -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT parameters, builder_blocks, timeframe FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cur.fetchone()
    conn.close()
    params = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
    blocks = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
    timeframe = row[2]
    sltp_block: dict = next((b for b in blocks if b.get("type") == "static_sltp"), {})
    sltp_params = sltp_block.get("params", {})
    return {
        "slippage": float(params.get("_slippage", 0.0)),
        "taker_fee": float(params.get("_commission", 0.0007)),
        "leverage": int(params.get("_leverage", 10)),
        "pyramiding": int(params.get("_pyramiding", 1)),
        "take_profit": float(sltp_params.get("take_profit_percent", 1.5)) / 100.0,
        "stop_loss": float(sltp_params.get("stop_loss_percent", 9.1)) / 100.0,
        "interval": str(timeframe or "30"),
    }


def normalize_ts(t) -> pd.Timestamp:
    """Normalize timestamp to UTC-aware."""
    if t is None:
        return None
    ts = pd.Timestamp(t)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts


def main() -> None:
    p = load_bt_params()
    print("=" * 80)
    print("RSI_6 — Trade-by-trade comparison: Engine vs TV (q4.csv, 47 trades)")
    print(
        f"Params: SL={p['stop_loss'] * 100:.1f}% TP={p['take_profit'] * 100:.1f}% "
        f"fee={p['taker_fee']} slippage={p['slippage']} lev={p['leverage']}x"
    )
    print("=" * 80)

    # ── 1. Run backtest ───────────────────────────────────────────────────────
    import asyncio

    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import BacktestInput, TradeDirection
    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    async def _fetch():
        svc = BacktestService()
        return await svc._fetch_historical_data(
            symbol="BTCUSDT",
            interval="30",
            start_date=pd.Timestamp("2025-01-01", tz="UTC"),
            end_date=pd.Timestamp("2026-02-24", tz="UTC"),
        )

    candles = asyncio.run(_fetch())
    if candles is None or len(candles) == 0:
        candles = load_ohlcv()

    print(f"Candles: {len(candles)} bars  {candles.index[0]} → {candles.index[-1]}")

    adapter = StrategyBuilderAdapter(load_strategy_graph())
    signals = adapter.generate_signals(candles)

    long_entries = np.asarray(signals.entries.values, dtype=bool)
    short_entries = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(long_entries), dtype=bool)
    )
    long_exits = (
        np.asarray(signals.exits.values, dtype=bool)
        if signals.exits is not None
        else np.zeros(len(long_entries), dtype=bool)
    )
    short_exits = (
        np.asarray(signals.short_exits.values, dtype=bool)
        if signals.short_exits is not None
        else np.zeros(len(long_entries), dtype=bool)
    )

    bt_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=1_000_000.0,
        position_size=0.10,
        use_fixed_amount=True,
        fixed_amount=100.0,
        leverage=p["leverage"],
        stop_loss=p["stop_loss"],
        take_profit=p["take_profit"],
        taker_fee=p["taker_fee"],
        slippage=p["slippage"],
        direction=TradeDirection.BOTH,
        pyramiding=p["pyramiding"],
        interval=p["interval"],
    )

    result = FallbackEngineV4().run(bt_input)
    our_trades = result.trades
    print(f"Engine trades: {len(our_trades)}  (TV total=104)\n")

    # ── 2. Build TV lookup: entry_price → TV trade ───────────────────────────
    # Key: (side, round(entry_price, 1))
    tv_lookup: dict[tuple[str, float], TvTrade] = {}
    for tv in TV_TRADES:
        key = (tv.side, round(tv.entry_price, 1))
        tv_lookup[key] = tv

    # ── 3. Trade-by-trade diff table ─────────────────────────────────────────
    print(
        f"{'#':<4} {'TV#':<5} {'side':<6} {'entry_time(UTC)':<22} {'entry_p':<10}"
        f"{'our_exit_time':<22} {'tv_exit_time':<22} "
        f"{'our_ep':<10} {'tv_ep':<10} {'our_pnl':<9} {'tv_pnl':<9} {'STATUS'}"
    )
    print("-" * 145)

    total_pnl_diff = 0.0
    diffs = []
    matched_tv = set()

    for i, t in enumerate(our_trades):
        our_num = i + 1
        key = (t.direction, round(t.entry_price, 1))
        tv: TvTrade | None = tv_lookup.get(key)

        our_entry = normalize_ts(t.entry_time)
        our_exit = normalize_ts(t.exit_time)
        our_ep = t.exit_price
        our_pnl = t.pnl
        our_reason = str(t.exit_reason)

        if tv is None:
            # Not in our 47 TV trades — engine trade beyond TV subset
            print(
                f"{our_num:<4} {'?':<5} {t.direction:<6} {str(our_entry)[:19]:<22} {t.entry_price:<10.1f}"
                f"{'':22} {'N/A in TV-47':<22} "
                f"{our_ep:<10.1f} {'—':<10} {our_pnl:<9.2f} {'—':<9} [NOT IN TV-47]"
            )
            continue

        matched_tv.add(tv.num)
        tv_exit = utc3_to_utc(tv.exit_utc3)
        tv_ep = tv.exit_price
        tv_pnl = tv.pnl
        tv_reason = tv.exit_reason

        pnl_diff = our_pnl - tv_pnl
        ep_diff = our_ep - tv_ep

        # Time diff in minutes
        exit_time_diff_min = None
        if our_exit is not None:
            exit_time_diff_min = int((our_exit - tv_exit).total_seconds() / 60)

        issues = []
        if abs(pnl_diff) > 0.05:
            issues.append(f"PNL:{pnl_diff:+.2f}")
        if abs(ep_diff) > 0.5:
            issues.append(f"EXIT_P:{ep_diff:+.1f}")
        if exit_time_diff_min is not None and abs(exit_time_diff_min) >= 30:
            issues.append(f"EXIT_T:{exit_time_diff_min:+d}m")
        if (
            tv_reason.replace(" ", "")
            != our_reason.replace("ExitReason.", "")
            .replace("_", " ")
            .replace(" ", "")
            .upper()[: len(tv_reason.replace(" ", ""))]
        ):
            pass  # reason comparison is tricky, skip for now

        status = "✓ OK" if not issues else "DIFF: " + "  ".join(issues)
        if issues:
            total_pnl_diff += pnl_diff
            diffs.append((our_num, tv.num, t.direction, t.entry_price, our_pnl, tv_pnl, pnl_diff, issues))

        tv_exit_str = str(tv_exit)[:19] if tv_exit else "—"
        our_exit_str = str(our_exit)[:19] if our_exit else "—"

        print(
            f"{our_num:<4} {tv.num:<5} {t.direction:<6} {str(our_entry)[:19]:<22} {t.entry_price:<10.1f}"
            f"{our_exit_str:<22} {tv_exit_str:<22} "
            f"{our_ep:<10.1f} {tv_ep:<10.1f} {our_pnl:<9.2f} {tv_pnl:<9.2f} {status}"
        )

    # ── 4. TV trades not found in engine ─────────────────────────────────────
    unmatched_tv = [tv for tv in TV_TRADES if tv.num not in matched_tv]
    print()
    if unmatched_tv:
        print("=== TV trades NOT matched by engine (entry_price not found) ===")
        for tv in unmatched_tv:
            print(
                f"  TV#{tv.num} {tv.side:5s} entry={tv.entry_price:.1f} ({tv.entry_utc3} UTC+3)  exit={tv.exit_price:.1f}  pnl={tv.pnl:.2f}"
            )
    else:
        print("=== All 47 TV trades matched in engine ✓ ===")

    # ── 5. Summary of diffs ───────────────────────────────────────────────────
    print()
    print("=" * 80)
    print(f"DIFF SUMMARY ({len(diffs)} trades with differences):")
    print(f"{'our#':<5} {'TV#':<5} {'side':<6} {'entry_p':<11} {'our_pnl':<10} {'tv_pnl':<10} {'diff':<10} issues")
    print("-" * 80)
    for d in diffs:
        our_num, tv_num, side, ep, our_pnl, tv_pnl, diff, issues = d
        print(
            f"  {our_num:<5} {tv_num:<5} {side:<6} {ep:<11.1f} {our_pnl:<10.2f} {tv_pnl:<10.2f} {diff:<+10.2f} {', '.join(issues)}"
        )

    print()
    print(f"Total PnL difference (matched trades): {total_pnl_diff:+.2f} USDT")
    print(
        f"Engine net_profit = {result.metrics.net_profit:.2f}  TV net_profit = 381.47  gap = {result.metrics.net_profit - 381.47:+.2f}"
    )

    # ── 6. Detailed analysis of each DIFF trade ───────────────────────────────
    if diffs:
        print()
        print("=" * 80)
        print("DETAILED ANALYSIS OF DIFF TRADES:")
        print()
        for d in diffs:
            our_num, tv_num, side, ep, our_pnl, tv_pnl, pnl_diff, issues = d
            t = our_trades[our_num - 1]
            tv = tv_lookup[(side, round(ep, 1))]

            our_exit = normalize_ts(t.exit_time)
            tv_exit = utc3_to_utc(tv.exit_utc3)

            print(f"  Trade #{our_num} (TV#{tv_num}) — {side.upper()} — entry @ {ep:.1f}")
            print(
                f"    Entry time:  our={str(normalize_ts(t.entry_time))[:19]}  tv={str(utc3_to_utc(tv.entry_utc3))[:19]}"
            )
            print(f"    Exit time:   our={str(our_exit)[:19]}  tv={str(tv_exit)[:19]}")
            print(
                f"    Exit price:  our={t.exit_price:.4f}  tv={tv.exit_price:.4f}  diff={t.exit_price - tv.exit_price:+.4f}"
            )
            print(f"    Exit reason: our={t.exit_reason}  tv={tv.exit_reason}")
            print(f"    PnL:         our={our_pnl:.4f}  tv={tv_pnl:.4f}  diff={pnl_diff:+.4f}")

            # Show OHLCV at TV exit bar
            tv_exit_bar = utc3_to_utc(tv.exit_utc3)
            if tv_exit_bar in candles.index:
                bar = candles.loc[tv_exit_bar]
                print(
                    f"    TV exit bar OHLCV: O={bar['open']:.1f} H={bar['high']:.1f} L={bar['low']:.1f} C={bar['close']:.1f}"
                )
                # TP price calculation
                if side == "short":
                    tp_price = ep * (1 - p["take_profit"])
                    sl_price = ep * (1 + p["stop_loss"])
                else:
                    tp_price = ep * (1 + p["take_profit"])
                    sl_price = ep * (1 - p["stop_loss"])
                print(f"    TP level={tp_price:.4f}  SL level={sl_price:.4f}")
                if side == "short":
                    tp_touched = bar["low"] <= tp_price
                    sl_touched = bar["high"] >= sl_price
                else:
                    tp_touched = bar["high"] >= tp_price
                    sl_touched = bar["low"] <= sl_price
                print(f"    At TV exit bar: TP_touched={tp_touched}  SL_touched={sl_touched}")
            print()


if __name__ == "__main__":
    main()
