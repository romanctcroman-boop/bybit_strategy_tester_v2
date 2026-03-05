"""
For each of the 4 unsolved roots (#12, #85, #89, #91):
- Show engine entry bar vs TV entry bar
- Show BTC RSI at both bars and all bars in between
- Check if TV's bar has a stronger/cleaner cross
- Look for patterns explaining why TV skips engine's bar
"""

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

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4 as FallbackEngine
from backend.backtesting.interfaces import BacktestInput, TradeDirection
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

    engine = FallbackEngine()
    inp = BacktestInput(
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
    result = engine.run(inp)
    engine_trades = result.trades

    # Parse TV trades
    tv_raw = pd.read_csv(r"c:\Users\roman\Downloads\as4.csv", sep=";")
    tv_trades = []
    for i in range(0, len(tv_raw), 2):
        exit_row = tv_raw.iloc[i]
        entry_row = tv_raw.iloc[i + 1]
        trade_num = int(str(exit_row["№ Сделки"]).strip())
        entry_type = str(entry_row["Тип"]).strip()
        direction = "short" if "short" in entry_type.lower() else "long"
        entry_time = pd.Timestamp(str(entry_row["Дата и время"]).strip()) - pd.Timedelta(hours=3)
        exit_time = pd.Timestamp(str(exit_row["Дата и время"]).strip()) - pd.Timedelta(hours=3)
        entry_price = float(str(entry_row["Цена USDT"]).replace(",", ".").strip())
        exit_signal = str(exit_row["Сигнал"]).strip()
        tv_trades.append(
            {
                "num": trade_num,
                "direction": direction,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": entry_price,
                "exit_signal": exit_signal,
            }
        )

    # Compute BTC RSI using the exact same calculate_rsi as the adapter
    from backend.core.indicators import calculate_rsi

    btc_close = btc["close"]
    btc_rsi_arr = calculate_rsi(btc_close.values, period=14)
    btc_rsi_full = pd.Series(btc_rsi_arr, index=btc_close.index)
    btc_rsi = btc_rsi_full.reindex(candles.index, method="ffill")

    timestamps = candles.index

    # Roots to analyze (1-based trade numbers)
    # These are roots where engine enters EARLIER than TV
    roots = [12, 85, 89, 91]

    for root_num in roots:
        et = engine_trades[root_num - 1]
        tt = tv_trades[root_num - 1]

        e_entry_time = pd.Timestamp(et.entry_time)
        t_entry_time = tt["entry_time"]

        # Previous trade (should match)
        et_prev = engine_trades[root_num - 2]
        tt_prev = tv_trades[root_num - 2]
        e_prev_exit = pd.Timestamp(et_prev.exit_time)
        t_prev_exit = tt_prev["exit_time"]

        print(f"\n{'=' * 100}")
        print(f"ROOT #{root_num}: Engine={et.direction}, TV={tt['direction']}")
        print(f"  Prev trade exit: Engine={e_prev_exit}, TV={t_prev_exit}")
        print(f"  This trade entry: Engine={e_entry_time}, TV={t_entry_time}")

        # Determine the signal bar (one before entry because entry_on_next_bar_open=True)
        # Engine: signal on bar BEFORE e_entry_time
        e_entry_idx = timestamps.get_loc(e_entry_time)
        e_signal_idx = e_entry_idx - 1
        e_signal_time = timestamps[e_signal_idx]

        # TV: signal on bar BEFORE t_entry_time
        t_entry_idx = timestamps.get_loc(t_entry_time)
        t_signal_idx = t_entry_idx - 1
        t_signal_time = timestamps[t_signal_idx]

        print(f"  Engine signal bar: {e_signal_time} (idx={e_signal_idx})")
        print(f"  TV signal bar: {t_signal_time} (idx={t_signal_idx})")
        print(f"  Gap: {t_signal_idx - e_signal_idx} bars")

        # Show RSI at engine signal bar
        e_rsi = btc_rsi.iloc[e_signal_idx]
        e_rsi_prev = btc_rsi.iloc[e_signal_idx - 1]
        e_se = se[e_signal_idx]

        print(f"\n  ENGINE SIGNAL BAR ({e_signal_time}):")
        print(f"    RSI[prev]={e_rsi_prev:.6f}, RSI[bar]={e_rsi:.6f}")
        print(f"    Cross: {e_rsi_prev:.6f} >= 52 and {e_rsi:.6f} < 52 → {e_rsi_prev >= 52 and e_rsi < 52}")
        print(f"    Range: 50 <= {e_rsi:.6f} <= 70 → {50 <= e_rsi <= 70}")
        print(f"    SE signal: {e_se}")

        # Show RSI at TV signal bar
        t_rsi = btc_rsi.iloc[t_signal_idx]
        t_rsi_prev = btc_rsi.iloc[t_signal_idx - 1]
        t_se = se[t_signal_idx]

        print(f"\n  TV SIGNAL BAR ({t_signal_time}):")
        print(f"    RSI[prev]={t_rsi_prev:.6f}, RSI[bar]={t_rsi:.6f}")
        print(f"    Cross: {t_rsi_prev:.6f} >= 52 and {t_rsi:.6f} < 52 → {t_rsi_prev >= 52 and t_rsi < 52}")
        print(f"    Range: 50 <= {t_rsi:.6f} <= 70 → {50 <= t_rsi <= 70}")
        print(f"    SE signal: {t_se}")

        # Show ALL SE signals between prev exit and TV entry
        prev_exit_idx = timestamps.get_loc(e_prev_exit)

        print(
            f"\n  ALL SE=True BARS from prev_exit ({e_prev_exit}, idx={prev_exit_idx}) to TV_entry ({t_entry_time}, idx={t_entry_idx}):"
        )
        se_count = 0
        for j in range(prev_exit_idx, t_entry_idx + 1):
            if se[j]:
                rsi_j = btc_rsi.iloc[j]
                rsi_j_prev = btc_rsi.iloc[j - 1] if j > 0 else float("nan")
                cross = rsi_j_prev >= 52 and rsi_j < 52
                rng = 50 <= rsi_j <= 70
                marker = " ← ENGINE" if j == e_signal_idx else (" ← TV" if j == t_signal_idx else "")
                print(
                    f"    [{j:5d}] {timestamps[j]}  RSI_prev={rsi_j_prev:.4f}  RSI={rsi_j:.4f}  margin_below_52={52 - rsi_j:.4f}  cross={cross}  range={rng}{marker}"
                )
                se_count += 1
        print(f"  Total SE=True bars in range: {se_count}")

        # Also show RSI values at ALL bars between engine signal and TV signal
        # to look for patterns
        print("\n  RSI VALUES between engine_signal and TV_signal:")
        for j in range(e_signal_idx - 2, t_signal_idx + 3):
            if j < 0 or j >= len(timestamps):
                continue
            rsi_j = btc_rsi.iloc[j]
            rsi_j_prev = btc_rsi.iloc[j - 1] if j > 0 else float("nan")
            se_j = se[j]
            le_j = le[j]
            sx_j = sx[j]
            lx_j = lx[j]

            markers = []
            if j == e_signal_idx:
                markers.append("ENGINE_SIG")
            if j == t_signal_idx:
                markers.append("TV_SIG")
            if se_j:
                markers.append("SE=1")
            if le_j:
                markers.append("LE=1")
            if sx_j:
                markers.append("SX=1")
            if lx_j:
                markers.append("LX=1")

            above_52 = "▲" if rsi_j >= 52 else "▼"
            marker_str = " | ".join(markers) if markers else ""
            print(f"    [{j:5d}] {timestamps[j]}  RSI={rsi_j:.4f} {above_52}  prev={rsi_j_prev:.4f}  {marker_str}")

        # KEY QUESTION: Is there any SE between engine and TV where TV actually enters?
        # What's special about TV's chosen bar?
        print("\n  ANALYSIS:")
        se_between = []
        for j in range(e_signal_idx, t_signal_idx + 1):
            if se[j]:
                se_between.append((j, timestamps[j], btc_rsi.iloc[j], 52 - btc_rsi.iloc[j]))

        if len(se_between) > 1:
            print("    Multiple SE signals between engine and TV signal bars:")
            for idx, ts, rsi, margin in se_between:
                marker = " ← ENGINE" if idx == e_signal_idx else (" ← TV" if idx == t_signal_idx else "")
                print(f"      [{idx}] {ts} RSI={rsi:.4f} margin_below_52={margin:.4f}{marker}")
        elif len(se_between) == 1:
            print("    Only 1 SE signal (engine's). TV bar has NO SE=True in our signals!")
            # This would mean TV's signal is different from ours
            print(f"    TV fires at bar {t_signal_time} where our SE={se[t_signal_idx]}")
            print("    This means TV's BTC RSI at this bar is DIFFERENT from ours!")


asyncio.run(main())
