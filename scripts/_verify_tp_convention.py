"""
Verify same-bar TP behavior across all perfect-match trades.
Check: does TV use exact TP level or close price?
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

    # Load TV
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

    # For each trade, check if it's a "fast TP" (duration <= 2 bars) and compare exit price
    print(
        f"{'#':>3}  {'dir':5}  {'bars':>4}  {'entry_px':>10}  {'tp_target':>10}  {'eng_exit':>10}  {'tv_exit':>10}  {'close_prev':>10}  {'match_tp':>8}  {'match_cl':>8}  {'pnl_d':>8}"
    )
    print("-" * 130)

    n = min(len(trades), len(tv_entries), len(tv_exits))
    fast_tp_count = 0
    tv_uses_tp = 0
    tv_uses_close = 0

    for idx in range(n):
        t = trades[idx]
        tv_x = tv_exits.iloc[idx]
        tv_e = tv_entries.iloc[idx]

        if t.duration_bars is None or t.duration_bars > 3:
            continue
        if str(t.exit_reason) != "ExitReason.TAKE_PROFIT":
            continue

        fast_tp_count += 1
        ep = t.entry_price
        if t.direction == "long":
            tp_level = ep * 1.023
        else:
            tp_level = ep * (1 - 0.023)

        # Find exit bar in candles to get close
        exit_ts = pd.Timestamp(str(t.exit_time)[:19])
        # The exit bar is actually the bar BEFORE (pending exit convention)
        # Find the bar index
        if exit_ts in candles.index:
            close_at_exit = candles.loc[exit_ts, "close"]
        else:
            close_at_exit = float("nan")

        eng_xp = t.exit_price
        tv_xp = tv_x["exit_px"]
        pnl_d = (t.pnl or 0) - tv_x["pnl_tv"]

        tp_match = abs(tv_xp - tp_level) < 0.1
        cl_match = abs(tv_xp - close_at_exit) < 0.1

        if tp_match:
            tv_uses_tp += 1
        if cl_match:
            tv_uses_close += 1

        # Check entry time match
        e_et = str(t.entry_time)[:19].replace("T", " ")
        tv_et = str(tv_e["ts_utc"])[:19]
        et_ok = e_et == tv_et

        if not et_ok:
            continue  # skip cascade-affected trades

        print(
            f"{idx + 1:3d}  {t.direction:5}  {t.duration_bars:4d}  {ep:10.2f}  {tp_level:10.2f}  {eng_xp:10.2f}  {tv_xp:10.2f}  {close_at_exit:10.2f}  {'TP' if tp_match else '':>8}  {'CLOSE' if cl_match else '':>8}  {pnl_d:+8.4f}"
        )

    print()
    print("Fast TP trades with matching entry: shown above")
    print(f"TV uses exact TP level: {tv_uses_tp}")
    print(f"TV uses close price:    {tv_uses_close}")


asyncio.run(main())
