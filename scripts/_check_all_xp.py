"""
Comprehensive same-bar TP test: check ALL trades where duration_bars <= 2
to determine TV convention.
"""

import asyncio
import json
import os
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

STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"


async def main():
    svc = BacktestService()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?", (STRATEGY_ID,)
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

    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT",
        interval="30",
        start_date=pd.Timestamp("2025-01-01", tz="UTC"),
        end_date=pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc = pd.concat(
        [
            await svc._fetch_historical_data(
                symbol="BTCUSDT",
                interval="30",
                start_date=pd.Timestamp("2020-01-01", tz="UTC"),
                end_date=pd.Timestamp("2025-01-01", tz="UTC"),
            ),
            await svc._fetch_historical_data(
                symbol="BTCUSDT",
                interval="30",
                start_date=pd.Timestamp("2025-01-01", tz="UTC"),
                end_date=pd.Timestamp("2026-02-24", tz="UTC"),
            ),
        ]
    ).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

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

    # TV reference
    tv_df = pd.read_csv(r"c:\Users\roman\Downloads\as4.csv", sep=";")
    tv_entries = (
        tv_df[tv_df["Тип"].str.contains("Entry|Вход", case=False, na=False)]
        .sort_values("№ Сделки")
        .reset_index(drop=True)
    )
    tv_exits = (
        tv_df[tv_df["Тип"].str.contains("Exit|Выход", case=False, na=False)]
        .sort_values("№ Сделки")
        .reset_index(drop=True)
    )
    tv_entries["ts_utc"] = pd.to_datetime(tv_entries["Дата и время"]) - pd.Timedelta(hours=3)
    tv_exits["ts_utc"] = pd.to_datetime(tv_exits["Дата и время"]) - pd.Timedelta(hours=3)

    def parse_float(val):
        if pd.isna(val):
            return 0.0
        return float(str(val).replace(",", ".").replace("\xa0", "").strip())

    tv_entries["entry_px"] = tv_entries["Цена USDT"].apply(parse_float)
    tv_exits["exit_px"] = tv_exits["Цена USDT"].apply(parse_float)
    tv_exits["pnl_tv"] = tv_exits["Чистая прибыль / убыток USDT"].apply(parse_float)

    n = min(len(trades), len(tv_entries), len(tv_exits))

    # Check ALL trades where same entry time, same direction, but different exit price
    # to determine: does TV use TP level or close?
    print("ALL MATCHING TRADES where engine exit_px != TV exit_px:")
    print(
        f"{'#':>3}  {'dir':5}  {'bars':>4}  {'entry_px':>10}  {'tp_level':>10}  {'eng_xpx':>10}  {'tv_xpx':>10}  {'delta':>8}  TV=TP?  TV=CL?"
    )
    print("-" * 110)

    for idx in range(n):
        t = trades[idx]
        tv_e = tv_entries.iloc[idx]
        tv_x = tv_exits.iloc[idx]

        # Only look at trades where entry time and direction match
        e_et = str(t.entry_time)[:19].replace("T", " ")
        tv_et = str(tv_e["ts_utc"])[:19]
        if e_et != tv_et:
            continue

        eng_xp = t.exit_price
        tv_xp = tv_x["exit_px"]
        if abs(eng_xp - tv_xp) < 0.02:
            continue  # prices match

        ep = t.entry_price
        if t.direction == "long":
            tp_level = ep * 1.023
        else:
            tp_level = ep * (1 - 0.023)

        # Get close of exit bar
        exit_ts = pd.Timestamp(str(t.exit_time)[:19])
        prev_ts = exit_ts - pd.Timedelta(minutes=30)
        close_exit = candles.loc[exit_ts, "close"] if exit_ts in candles.index else float("nan")
        close_prev = candles.loc[prev_ts, "close"] if prev_ts in candles.index else float("nan")

        tp_match = abs(tv_xp - tp_level) < 0.1
        cl_match = abs(eng_xp - close_exit) < 0.1 or abs(eng_xp - close_prev) < 0.1

        print(
            f"{idx + 1:3d}  {t.direction:5}  {t.duration_bars:4d}  {ep:10.2f}  {tp_level:10.2f}  {eng_xp:10.2f}  {tv_xp:10.2f}  {eng_xp - tv_xp:+8.2f}  {'YES' if tp_match else 'no':>6}  {'YES' if cl_match else 'no':>6}"
        )


asyncio.run(main())
