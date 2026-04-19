"""Check previous trade details for all 6 UNKNOWN cases.
What was the previous trade? When and how did it exit?
Is the exit on the same bar as the 1st SE?
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

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4 as FallbackEngine
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.indicators.momentum import calculate_rsi


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

    START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
    END_DATE = pd.Timestamp("2026-02-24", tz="UTC")

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)

    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    lx = np.asarray(signals.exits.values, dtype=bool)
    se = np.asarray(signals.short_entries.values, dtype=bool)
    sx = np.asarray(signals.short_exits.values, dtype=bool)

    # Run engine
    bi = BacktestInput(
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
    engine = FallbackEngine()
    result = engine.run(bi)
    trades = result.trades

    # UNKNOWN engine entry times (UTC)
    unknown_entries = [
        pd.Timestamp("2025-02-22 11:00:00"),
        pd.Timestamp("2025-05-09 15:30:00"),
        pd.Timestamp("2025-08-16 01:30:00"),
        pd.Timestamp("2025-08-27 03:00:00"),
        pd.Timestamp("2025-09-02 11:30:00"),
        pd.Timestamp("2025-11-25 00:30:00"),
    ]

    print("=" * 120)
    print("PREVIOUS TRADE DETAILS for 6 UNKNOWN cases")
    print("=" * 120)

    for ue in unknown_entries:
        # Find this trade and the previous one
        target_trade = None
        prev_trade = None
        for i, t in enumerate(trades):
            if abs((t.entry_time - ue).total_seconds()) < 60:
                target_trade = t
                if i > 0:
                    prev_trade = trades[i - 1]
                print(f"\n{'=' * 120}")
                print(f"Engine trade #{i + 1}: {t.direction} entry={t.entry_time} exit={t.exit_time}")
                print(f"  Entry price: {t.entry_price:.4f}")
                print(f"  Exit price:  {t.exit_price:.4f}")
                print(f"  Exit reason: {t.exit_reason}")
                print(f"  PnL: {t.pnl:.4f}")

                if prev_trade:
                    print(
                        f"\n  PREVIOUS trade #{i}: {prev_trade.direction} "
                        f"entry={prev_trade.entry_time} exit={prev_trade.exit_time}"
                    )
                    print(f"    Entry price: {prev_trade.entry_price:.4f}")
                    print(f"    Exit price:  {prev_trade.exit_price:.4f}")
                    print(f"    Exit reason: {prev_trade.exit_reason}")

                    # Check timing: how many bars between prev exit and current entry?
                    prev_exit_ts = prev_trade.exit_time
                    curr_entry_ts = t.entry_time
                    bars_between = 0
                    for idx, ts in enumerate(candles.index):
                        if ts > prev_exit_ts and ts <= curr_entry_ts:
                            bars_between += 1
                    print(f"    Bars between prev exit and current entry: {bars_between}")

                    # CRITICAL: Check if prev exit and 1st SE are on the same bar or adjacent
                    prev_exit_bar_idx = None
                    for idx, ts in enumerate(candles.index):
                        if ts == prev_exit_ts:
                            prev_exit_bar_idx = idx
                            break
                    if prev_exit_bar_idx is None:
                        # Try tz-naive comparison
                        for idx, ts in enumerate(candles.index):
                            if ts.tz_localize(None) == prev_exit_ts or str(ts)[:19] == str(prev_exit_ts)[:19]:
                                prev_exit_bar_idx = idx
                                break

                    if prev_exit_bar_idx is not None:
                        print(f"    Prev exit bar index: {prev_exit_bar_idx}")
                        # Find first SE after prev exit
                        first_se_after = None
                        for idx in range(prev_exit_bar_idx + 1, len(se)):
                            if se[idx]:
                                first_se_after = idx
                                break
                        if first_se_after is not None:
                            print(f"    1st SE after prev exit: bar {first_se_after} = {candles.index[first_se_after]}")
                            gap = first_se_after - prev_exit_bar_idx
                            print(f"    Gap (bars): {gap}")
                    else:
                        print(f"    Could not find prev exit bar in index (exit_time={prev_exit_ts})")
                break

    # Also check TV trades for comparison
    print("\n\n" + "=" * 120)
    print("TV TRADE DETAILS for corresponding trades")
    print("=" * 120)

    df = pd.read_csv(r"c:\Users\roman\Downloads\as4.csv", sep=";")
    tv_trades_of_interest = [22, 56, 85, 89, 91, 119]
    for tn in tv_trades_of_interest:
        rows = df[df["№ Сделки"].astype(str).str.strip() == str(tn)]
        if rows.empty:
            print(f"\nTV#{tn}: NOT FOUND")
            continue
        entry_row = rows[rows["Тип"].str.contains("Entry", case=False)]
        exit_row = rows[rows["Тип"].str.contains("Exit", case=False)]
        if not entry_row.empty:
            e = entry_row.iloc[0]
            print(
                f"\nTV#{tn}: {e['Тип']}  time={e['Дата и время']} (Moscow)  signal={e['Сигнал']}  price={e['Цена USDT']}"
            )
        if not exit_row.empty:
            x = exit_row.iloc[0]
            print(f"       {x['Тип']}  time={x['Дата и время']} (Moscow)  signal={x['Сигнал']}  price={x['Цена USDT']}")

        # Also show previous TV trade
        prev_tn = tn - 1
        prev_rows = df[df["№ Сделки"].astype(str).str.strip() == str(prev_tn)]
        if not prev_rows.empty:
            prev_exit_row = prev_rows[prev_rows["Тип"].str.contains("Exit", case=False)]
            if not prev_exit_row.empty:
                px = prev_exit_row.iloc[0]
                print(
                    f"  PREV TV#{prev_tn}: {px['Тип']}  time={px['Дата и время']} (Moscow)  signal={px['Сигнал']}  price={px['Цена USDT']}"
                )


asyncio.run(main())
