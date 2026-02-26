"""
Root #144 deep dive: Why does the engine fire a short signal at 2026-02-07 16:00
when RSI at that bar = 53.30 (no crossunder)?

Hypothesis: The signal was generated at bar 15:30 (RSI 52.97→51.53 = CROSS↓52),
and the engine fires entry at 16:00 due to entry_on_next_bar_open=True.
But at bar 15:30, trade #143 is STILL OPEN (TP exits at bar 16:00).
With pyramiding=1, how can a new entry fire?

Also check: Does the engine evaluate signals BEFORE or AFTER TP/SL exits on the same bar?
If AFTER: TP fills at bar 16:00 → position closes → signal at bar 16:00 can fire → entry at 16:30
  But then signal bar is 16:00, and crossunder at 16:00 is (rsi_prev=51.53, rsi=53.30) → NO CROSS
If BEFORE: Signal at bar 15:30 fires (cross=True) but blocked by pyramiding (position open)

Let's trace the actual signal array around these bars.
"""

import asyncio
import json
import sqlite3
import sys
import warnings

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
from backend.core.indicators.momentum import calculate_rsi

STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")


async def main():
    svc = BacktestService()

    # Load strategy
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    ms = gp.get("main_strategy", {})
    graph = {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if ms:
        graph["main_strategy"] = ms

    # Fetch data
    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    # BTC RSI
    btc_rsi_arr = calculate_rsi(btc["close"].values, period=14)
    btc_rsi = pd.Series(btc_rsi_arr, index=btc.index)

    # Generate signals
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
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

    # ════════════════════════════════════════════════════════════════════════
    # 1. Check the signal arrays around Root #144
    # ════════════════════════════════════════════════════════════════════════
    print("=" * 100)
    print("ROOT #144: Signal array around 2026-02-07 15:00 - 2026-02-08 04:00")
    print("=" * 100)

    ts_start = pd.Timestamp("2026-02-07 14:00")
    ts_end = pd.Timestamp("2026-02-08 05:00")

    for i, ts in enumerate(candles.index):
        ts_naive = ts.tz_localize(None) if ts.tzinfo else ts
        if ts_naive >= ts_start and ts_naive <= ts_end:
            btc_rsi_val = btc_rsi.get(ts.tz_localize(None) if ts.tzinfo else ts, np.nan)
            if np.isnan(btc_rsi_val):
                btc_rsi_val = btc_rsi.get(ts, np.nan)
            print(
                f"  {str(ts)[:19]}  SE={se[i]:d}  LE={le[i]:d}  SX={sx[i]:d}  LX={lx[i]:d}  BTC_RSI={btc_rsi_val:.4f}"
            )

    # ════════════════════════════════════════════════════════════════════════
    # 2. Check Root #9
    # ════════════════════════════════════════════════════════════════════════
    print()
    print("=" * 100)
    print("ROOT #9: Signal array around 2025-01-28 13:00 - 2025-01-28 19:00")
    print("=" * 100)

    ts_start9 = pd.Timestamp("2025-01-28 13:00")
    ts_end9 = pd.Timestamp("2025-01-28 19:00")

    for i, ts in enumerate(candles.index):
        ts_naive = ts.tz_localize(None) if ts.tzinfo else ts
        if ts_naive >= ts_start9 and ts_naive <= ts_end9:
            btc_rsi_val = btc_rsi.get(ts.tz_localize(None) if ts.tzinfo else ts, np.nan)
            if np.isnan(btc_rsi_val):
                btc_rsi_val = btc_rsi.get(ts, np.nan)
            print(
                f"  {str(ts)[:19]}  SE={se[i]:d}  LE={le[i]:d}  SX={sx[i]:d}  LX={lx[i]:d}  BTC_RSI={btc_rsi_val:.4f}"
            )

    # ════════════════════════════════════════════════════════════════════════
    # 3. Check ALL root signal bars and their signal flags
    # ════════════════════════════════════════════════════════════════════════
    print()
    print("=" * 100)
    print("ALL ROOTS: Signal flag at engine and TV signal bars")
    print("=" * 100)

    roots_eng = {
        9: "2025-01-28 17:30",
        12: "2025-02-06 14:00",
        85: "2025-08-16 01:00",
        89: "2025-08-27 02:30",
        91: "2025-09-02 11:00",
        144: "2026-02-07 16:00",
    }
    roots_tv = {
        9: "2025-01-28 14:00",
        12: "2025-02-07 05:00",
        85: "2025-08-16 13:30",
        89: "2025-08-27 12:00",
        91: "2025-09-02 18:00",
        144: "2026-02-08 03:00",
    }

    for root_id in [9, 12, 85, 89, 91, 144]:
        eng_ts_str = roots_eng[root_id]
        tv_ts_str = roots_tv[root_id]

        # Find indices
        eng_i = None
        tv_i = None
        for i, ts in enumerate(candles.index):
            ts_str = str(ts)[:16]
            if ts_str.endswith(eng_ts_str[:16]) or eng_ts_str[:16] in ts_str:
                eng_i = i
            if ts_str.endswith(tv_ts_str[:16]) or tv_ts_str[:16] in ts_str:
                tv_i = i

        print(f"\n  Root #{root_id}:")
        if eng_i is not None:
            print(f"    Engine signal bar {roots_eng[root_id]}: SE={se[eng_i]}, LE={le[eng_i]}")
        else:
            print(f"    Engine signal bar {roots_eng[root_id]}: NOT FOUND in candles")
        if tv_i is not None:
            print(f"    TV signal bar     {roots_tv[root_id]}: SE={se[tv_i]}, LE={le[tv_i]}")
        else:
            print(f"    TV signal bar     {roots_tv[root_id]}: NOT FOUND in candles")

    # ════════════════════════════════════════════════════════════════════════
    # 4. Verify Root #144 engine trade details
    # ════════════════════════════════════════════════════════════════════════
    result = FallbackEngineV4().run(
        BacktestInput(
            candles=candles,
            long_entries=le,
            long_exits=lx,
            short_entries=se,
            short_exits=sx,
            initial_capital=1_000_000.0,
            position_size=0.001,
            use_fixed_amount=False,
            leverage=1,
            stop_loss=0.132,
            take_profit=0.023,
            taker_fee=0.0007,
            slippage=0.0,
            direction=TradeDirection.BOTH,
            pyramiding=1,
            interval="30",
            entry_on_next_bar_open=True,
        )
    )
    trades = result.trades

    print()
    print("=" * 100)
    print("ROOT #144: Trades #142-#145 details")
    print("=" * 100)
    for i in range(141, min(146, len(trades))):
        t = trades[i]
        print(
            f"  Trade #{i + 1}: {t.direction:5s}  entry={str(t.entry_time)[:19]} @ {t.entry_price:.2f}  "
            f"exit={str(t.exit_time)[:19]} @ {t.exit_price:.2f}  reason={t.exit_reason}  pnl={t.pnl:.2f}"
        )

    print()
    print("=" * 100)
    print("ROOT #89/#91: Check engine trades around those areas")
    print("=" * 100)

    # Root #89 = trade #89
    for root_id in [89, 91]:
        idx = root_id - 1
        if idx < len(trades):
            t = trades[idx]
            tp = trades[idx - 1] if idx > 0 else None
            print(f"\n  --- Root #{root_id} ---")
            if tp:
                print(
                    f"  Prev trade #{root_id - 1}: {tp.direction:5s}  "
                    f"exit={str(tp.exit_time)[:19]} reason={tp.exit_reason}"
                )
            print(
                f"  This trade #{root_id}: {t.direction:5s}  "
                f"entry={str(t.entry_time)[:19]} exit={str(t.exit_time)[:19]}  reason={t.exit_reason}"
            )

    # ════════════════════════════════════════════════════════════════════════
    # 5. Key insight check: For roots where prev trade exits at bar T,
    #    AND there's a crossunder at bar T, AND the engine fires a signal
    #    right after — does the engine use the crossunder from bar T?
    # ════════════════════════════════════════════════════════════════════════
    print()
    print("=" * 100)
    print("CHECK: Does the crossunder fire at the SAME bar as TP exit?")
    print("(If yes, engine is in position when cross fires → should be blocked by pyramiding)")
    print("=" * 100)

    # Root #89: prev exit at 2025-08-25 19:00, cross↓52 at same bar
    # Root #91: prev exit at 2025-09-01 20:30, cross↓52 at same bar
    # Root #144: prev exit at 2026-02-07 16:00, BUT cross at 15:30 (bar BEFORE exit)

    for root_id, exit_bar_str, cross_bar_str in [
        (89, "2025-08-25 19:00", "2025-08-25 19:00"),
        (91, "2025-09-01 20:30", "2025-09-01 20:30"),
        (144, "2026-02-07 16:00", "2026-02-07 15:30"),
    ]:
        ci = None
        for i, ts in enumerate(candles.index):
            ts_str = str(ts)[:16]
            if cross_bar_str[:16] in ts_str:
                ci = i
                break
        if ci is not None:
            print(f"\n  Root #{root_id}: Cross bar {cross_bar_str}  SE={se[ci]}")
            # Also check the NEXT bar (entry_on_next_bar_open)
            if ci + 1 < len(candles):
                print(f"    Next bar {str(candles.index[ci + 1])[:19]}  SE={se[ci + 1]}")
        else:
            print(f"\n  Root #{root_id}: Cross bar {cross_bar_str} NOT FOUND")

    print("\nDone.")


asyncio.run(main())
