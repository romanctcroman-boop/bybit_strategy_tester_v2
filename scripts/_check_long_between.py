"""Check ALL signals (LE+SE) between prev exit and the 1st SE signal for each root.
Maybe a LONG entry fires between prev exit and 1st SE, blocking the short."""

import asyncio
import json
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


async def main():
    svc = BacktestService()
    conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        ("dd2969a2-bbba-410e-b190-be1e8cc50b21",),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br)
    conns = json.loads(cr)
    gp = json.loads(gr)
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

    candles = await svc._fetch_historical_data(
        "ETHUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc_warmup = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2020-01-01", tz="UTC"),
        pd.Timestamp("2025-01-01", tz="UTC"),
    )
    btc_main = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)

    le = np.asarray(signals.entries.values, dtype=bool)
    lx = np.asarray(signals.exits.values, dtype=bool)
    se = np.asarray(signals.short_entries.values, dtype=bool)
    sx = np.asarray(signals.short_exits.values, dtype=bool)

    # Root divergences:
    # #9:  prev exit = trade #8 exit = 2025-01-27 18:30
    #      engine signal = 2025-01-28 17:30
    #      TV signal = 2025-01-28 14:00 (entry 14:30)
    # #12: prev exit = trade #11 exit = 2025-02-05 18:30
    #      engine 1st SE = 2025-02-06 14:00 (entry 14:30)
    #      TV SE = 2025-02-07 05:00 (entry 05:30)

    roots = [
        (12, "2025-02-05 18:30", "2025-02-06 14:00", "2025-02-07 05:00"),
        (85, "2025-08-15 15:30", "2025-08-16 01:00", "2025-08-16 13:30"),
        (89, "2025-08-25 19:00", "2025-08-27 02:30", "2025-08-27 12:00"),
        (91, "2025-09-01 20:30", "2025-09-02 11:00", "2025-09-02 18:00"),
    ]

    for root_idx, prev_exit_str, engine_sig, tv_sig in roots:
        prev_exit = pd.Timestamp(prev_exit_str)
        engine_sig_ts = pd.Timestamp(engine_sig)
        tv_sig_ts = pd.Timestamp(tv_sig)

        # Find indices
        prev_exit_idx = None
        engine_sig_idx = None
        tv_sig_idx = None
        for idx_c, ts in enumerate(candles.index):
            if ts == prev_exit:
                prev_exit_idx = idx_c
            if ts == engine_sig_ts:
                engine_sig_idx = idx_c
            if ts == tv_sig_ts:
                tv_sig_idx = idx_c

        print(f"\n{'=' * 70}")
        print(f"ROOT #{root_idx}: prev exit {prev_exit} → engine signal {engine_sig_ts} → TV signal {tv_sig_ts}")
        print(f"{'=' * 70}")

        print(f"\nALL signals between prev exit and engine's 1st SE signal:")
        for k in range(prev_exit_idx, engine_sig_idx + 1):
            ts = candles.index[k]
            if le[k] or se[k] or lx[k] or sx[k]:
                signals_str = []
                if le[k]:
                    signals_str.append("LE=1")
                if se[k]:
                    signals_str.append("SE=1")
                if lx[k]:
                    signals_str.append("LX=1")
                if sx[k]:
                    signals_str.append("SX=1")
                marker = " ← PREV EXIT" if k == prev_exit_idx else ""
                marker2 = " ← ENGINE SIG" if k == engine_sig_idx else ""
                print(f"  {ts}: {', '.join(signals_str)}{marker}{marker2}")

        # Check if there's a LE signal between prev exit and engine's 1st SE
        le_count = 0
        for k in range(prev_exit_idx, engine_sig_idx + 1):
            if le[k]:
                le_count += 1
                print(f"  *** LE at {candles.index[k]}")

        if le_count > 0:
            print(f"\n  >>> {le_count} LONG ENTRY signals before engine's 1st SE!")
            print(f"  >>> If this LE fires → long position open → SE is blocked by pyramiding=1!")

            # Now check: would this LE trade still be open when the 1st SE fires?
            # LE at bar k → long entry at bar k+1
            # SE at engine_sig_idx → short entry at engine_sig_idx+1
            # If long position is still open at engine_sig_idx+1, then SE is blocked
            for k in range(prev_exit_idx, engine_sig_idx + 1):
                if le[k]:
                    entry_bar = k + 1  # entry_on_next_bar_open
                    entry_price = candles["open"].values[entry_bar]
                    tp_level = entry_price * (1 + 0.023)  # long TP
                    sl_level = entry_price * (1 - 0.132)  # long SL
                    print(f"\n  Long entry at bar {candles.index[entry_bar]}, price={entry_price:.2f}")
                    print(f"  TP level={tp_level:.2f}, SL level={sl_level:.2f}")

                    # Check if TP hits before engine's SE signal bar
                    for j in range(entry_bar, engine_sig_idx + 2):
                        high = candles["high"].values[j]
                        low = candles["low"].values[j]
                        if high >= tp_level:
                            print(f"  TP HIT at bar {candles.index[j]} (high={high:.2f} >= {tp_level:.2f})")
                            if j < engine_sig_idx:
                                print(f"  TP BEFORE engine SE → position clear → SE can fire")
                            elif j == engine_sig_idx:
                                print(f"  TP ON SAME BAR as engine SE!")
                                print(
                                    f"  TV: entry at bar {candles.index[engine_sig_idx + 1]} OPEN, "
                                    f"position still open → BLOCKED"
                                )
                            else:
                                print(f"  TP AFTER engine SE → position still open → SE BLOCKED")
                            break
                        if low <= sl_level:
                            print(f"  SL HIT at bar {candles.index[j]} (low={low:.2f} <= {sl_level:.2f})")
                            break
                    else:
                        print(f"  Neither TP nor SL hit before engine SE bar")
        else:
            print(f"\n  No LE signals between prev exit and engine SE. Mystery remains.")


asyncio.run(main())
