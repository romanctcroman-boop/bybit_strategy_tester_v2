"""Investigate all divergence clusters from _match_trades.py output."""

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


async def main():
    svc = BacktestService()
    conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
        ("dd2969a2-bbba-410e-b190-be1e8cc50b21",),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    graph = {
        "name": name,
        "blocks": json.loads(br),
        "connections": json.loads(cr),
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    ms = json.loads(gr).get("main_strategy", {})
    if ms:
        graph["main_strategy"] = ms

    candles = await svc._fetch_historical_data(
        "ETHUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = await svc._fetch_historical_data(
        "BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2026-02-24", tz="UTC")
    )
    btc = btc[~btc.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    lx = np.asarray(signals.exits.values, dtype=bool)
    se = np.asarray(signals.short_entries.values, dtype=bool)
    sx = np.asarray(signals.short_exits.values, dtype=bool)
    times = candles.index

    # ============ CLUSTER 1: First trade divergence ============
    print("=" * 80)
    print("CLUSTER 1: First trade divergence")
    print("TV#1: short entry 2025-01-01 13:30 UTC, Engine#1: short entry 2025-01-02 22:30 UTC")
    print("TV has extra trades: #2 (short 01-08 23:30), #3 (short 01-09 17:30),")
    print("  #4 (short 01-10 21:00), #5 (long 01-13 13:30)")
    print("Engine has extra trade: #2 (long 01-07 22:30)")
    print("=" * 80)

    # Check first few bars
    print("\nFirst 10 bars of data:")
    for i in range(min(10, len(candles))):
        ts = times[i]
        print(
            f"  [{i:3d}] {ts}  O={candles.iloc[i]['open']:.2f}  H={candles.iloc[i]['high']:.2f}"
            f"  L={candles.iloc[i]['low']:.2f}  C={candles.iloc[i]['close']:.2f}"
            f"  LE={le[i]}  SE={se[i]}"
        )

    # Find the first SE=True signal
    first_se = np.argmax(se)
    print(f"\nFirst SE=True at index {first_se}: {times[first_se]}")
    if first_se > 0:
        print(f"  Previous bar [{first_se - 1}]: {times[first_se - 1]}")

    # TV entry is 2025-01-01 13:30 UTC
    # With entry_on_next_bar_open=True, the SE signal would be on 2025-01-01 13:00 bar
    # That means SE fires on 13:00 bar, entry on 13:30 bar (next bar open)
    tv_signal_bar = pd.Timestamp("2025-01-01 13:00:00")
    eng_signal_bar = pd.Timestamp("2025-01-02 22:00:00")

    # Find bars near TV signal
    print(f"\nBars around TV signal time (2025-01-01 13:00 UTC):")
    for i in range(len(candles)):
        ts = times[i]
        if pd.Timestamp("2025-01-01 10:00") <= ts <= pd.Timestamp("2025-01-01 16:00"):
            # Get BTC RSI at this bar
            print(f"  [{i:3d}] {ts}  SE={se[i]}  LE={le[i]}  LX={lx[i]}  SX={sx[i]}")

    # Find bars around engine signal
    print(f"\nBars around Engine signal time (2025-01-02 22:00 UTC):")
    for i in range(len(candles)):
        ts = times[i]
        if pd.Timestamp("2025-01-02 18:00") <= ts <= pd.Timestamp("2025-01-03 02:00"):
            print(f"  [{i:3d}] {ts}  SE={se[i]}  LE={le[i]}  LX={lx[i]}  SX={sx[i]}")

    # Check if RSI is even computed for early bars (warmup issue?)
    print(f"\nTotal ETH candles: {len(candles)}")
    print(f"Total BTC candles: {len(btc)}")
    print(f"ETH first bar: {times[0]}")
    print(f"ETH last bar: {times[-1]}")
    print(f"BTC first bar: {btc.index[0]}")
    print(f"BTC last bar: {btc.index[-1]}")

    # Check RSI values from the signals DataFrame
    if hasattr(signals, "indicators") and signals.indicators is not None:
        print("\nSignals indicators available")
    print(f"\nSignals DataFrame columns: {list(signals.entries.index[:5])}")

    # Check SE signals in first 100 bars
    se_indices = np.where(se[:100])[0]
    le_indices = np.where(le[:100])[0]
    print(f"\nFirst 100 bars SE signals at indices: {se_indices}")
    print(f"First 100 bars LE signals at indices: {le_indices}")

    for idx in se_indices[:10]:
        print(f"  SE[{idx}] = True at {times[idx]} → entry at {times[idx + 1] if idx + 1 < len(times) else 'N/A'}")

    for idx in le_indices[:10]:
        print(f"  LE[{idx}] = True at {times[idx]} → entry at {times[idx + 1] if idx + 1 < len(times) else 'N/A'}")

    # ============ CLUSTER 2: E#6/TV#9 ============
    print("\n" + "=" * 80)
    print("CLUSTER 2: E#6/TV#9 — Engine 18:00, TV 14:30 (Root #9, intra-bar)")
    print("Engine also has extra trade E#9 (short 2025-02-06 14:30)")
    print("=" * 80)

    # Engine enters at 18:00, TV at 14:30 — 3.5h gap
    # entry_on_next_bar_open: TV signal at 14:00, engine signal at 17:30
    # Both need SE=True at those bars
    for target in ["2025-01-28 14:00", "2025-01-28 17:30"]:
        ts_target = pd.Timestamp(target)
        for i in range(len(candles)):
            if times[i] == ts_target:
                print(f"  Bar {ts_target}: SE={se[i]}, LE={le[i]}")
                break

    # Check all SE signals between 2025-01-28 and 2025-01-29
    print("\n  All signals 2025-01-28:")
    for i in range(len(candles)):
        ts = times[i]
        if pd.Timestamp("2025-01-28 00:00") <= ts <= pd.Timestamp("2025-01-29 00:00"):
            if se[i] or le[i]:
                print(f"    [{i:4d}] {ts}  SE={se[i]}  LE={le[i]}")

    # ============ CLUSTER 3: May 9-18 area ============
    print("\n" + "=" * 80)
    print("CLUSTER 3: May 9-18 area")
    print("E#54/TV#56 shifted (15:30 vs 19:30), E#55+E#56 engine-only, E#57/TV#57 shifted")
    print("TV#58+#59+#60 TV-only")
    print("=" * 80)

    print("\n  All SE/LE signals May 9-19:")
    for i in range(len(candles)):
        ts = times[i]
        if pd.Timestamp("2025-05-09 00:00") <= ts <= pd.Timestamp("2025-05-19 00:00"):
            if se[i] or le[i]:
                print(f"    [{i:4d}] {ts}  SE={se[i]}  LE={le[i]}")

    # ============ CLUSTER 4: Aug-Sep area ============
    print("\n" + "=" * 80)
    print("CLUSTER 4: Aug 16 - Sep 2 area")
    print("E#82/TV#85 shifted (01:30 vs 14:00), E#86/TV#89 shifted (03:00 vs 12:30)")
    print("E#88/TV#91 shifted (11:30 vs 18:30), E#89 engine-only")
    print("=" * 80)

    # Check signals around Aug 16
    print("\n  SE signals around Aug 16:")
    for i in range(len(candles)):
        ts = times[i]
        if pd.Timestamp("2025-08-15 20:00") <= ts <= pd.Timestamp("2025-08-16 18:00"):
            if se[i]:
                print(f"    [{i:4d}] {ts}  SE={se[i]}")

    # Check signals around Sep 2
    print("\n  SE signals around Sep 2:")
    for i in range(len(candles)):
        ts = times[i]
        if pd.Timestamp("2025-09-02 00:00") <= ts <= pd.Timestamp("2025-09-03 00:00"):
            if se[i]:
                print(f"    [{i:4d}] {ts}  SE={se[i]}")

    # ============ EXIT MISMATCHES ============
    print("\n" + "=" * 80)
    print("EXIT TIME MISMATCHES (same entry, different exit)")
    print("=" * 80)

    # E#45/TV#47: short entry=2025-04-13 19:30:00
    # exit: E=2025-04-13 21:00:00 vs TV=2025-04-13 19:30:00
    print("\n  E#45/TV#47: exit: E=21:00 vs TV=19:30 (TV exits SAME bar as entry!)")
    # This means TV fires TP on entry bar itself

    # E#103/TV#105: long entry=2025-10-17 11:00:00
    # exit: E=2025-10-17 12:00:00 vs TV=2025-10-17 11:00:00
    print("  E#103/TV#105: exit: E=12:00 vs TV=11:00 (TV exits SAME bar as entry!)")

    # E#148/TV#151: long entry=2026-02-23 21:00:00
    # exit: E=2026-02-24 00:00:00 vs TV=2026-02-24 18:32:00
    print("  E#148/TV#151: exit: E=00:00 (END_OF_DATA) vs TV=18:32 (still open in TV)")

    # ============ NEAR MATCHES: E#20, E#117 ============
    print("\n" + "=" * 80)
    print("NEAR MATCHES: E#20/TV#22 and E#117/TV#119")
    print("=" * 80)

    # E#20/TV#22: short E_entry=2025-02-22 11:00 TV_entry=2025-02-22 15:00 diff=4h
    print("\n  E#20/TV#22: Engine enters 4h EARLIER (11:00 vs 15:00)")
    print("  SE signals 2025-02-22:")
    for i in range(len(candles)):
        ts = times[i]
        if pd.Timestamp("2025-02-22 08:00") <= ts <= pd.Timestamp("2025-02-22 18:00"):
            if se[i]:
                print(f"    [{i:4d}] {ts}  SE={se[i]}")

    # E#117/TV#119: short E_entry=2025-11-25 00:30 TV_entry=2025-11-25 05:30 diff=5h
    print("\n  E#117/TV#119: Engine enters 5h EARLIER (00:30 vs 05:30)")
    print("  SE signals 2025-11-25:")
    for i in range(len(candles)):
        ts = times[i]
        if pd.Timestamp("2025-11-24 20:00") <= ts <= pd.Timestamp("2025-11-25 10:00"):
            if se[i]:
                print(f"    [{i:4d}] {ts}  SE={se[i]}")

    # ============ SUMMARY ============
    print("\n" + "=" * 80)
    print("DIVERGENCE SUMMARY")
    print("=" * 80)
    print(f"""
Total divergent cases:
  1. TV#1 enters 33h EARLIER - first bar issue or intra-bar?
     → TV has 3 extra shorts + 1 extra long in first 2 weeks
     → Engine has 1 extra long
  2. E#6/TV#9: Engine 3.5h LATER (17:30 signal vs 14:00 intra-bar)
     → Known Root #9: bar-close RSI=52.055, no cross
  3. E#9 engine-only: short 2025-02-06 14:30 (TV skips this)
  4. E#20/TV#22: Engine 4h EARLIER (same pattern as roots #12,#85,#89,#91)
  5. E#54/TV#56: Engine 4h EARLIER
  6. E#55, E#56 engine-only (extra trades)
  7. E#57/TV#57: Engine 15.5h EARLIER
  8. TV#58,#59,#60 TV-only (3 extra TV trades)
  9. E#82/TV#85: Engine 12.5h EARLIER
  10. E#86/TV#89: Engine 9.5h EARLIER
  11. E#88/TV#91: Engine 7h EARLIER
  12. E#89 engine-only
  13. E#117/TV#119: Engine 5h EARLIER
  14. E#45/TV#47: Exit mismatch (same-bar TP entry?)
  15. E#103/TV#105: Exit mismatch (same-bar TP entry?)
  16. TV#136: TV-only trade
  17. E#148/TV#151: Exit mismatch (END_OF_DATA vs still open)

Pattern: Engine fires at 1st valid crossunder, TV fires LATER at a DIFFERENT crossunder.
This is consistent across ALL shifted entries.
""")


asyncio.run(main())
