"""Compare engine trade entries vs TV as4.csv"""

import asyncio
import json
import sqlite3
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"


async def run():
    svc = BacktestService()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?", (STRATEGY_ID,)
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
        symbol="ETHUSDT",
        interval="30",
        start_date=pd.Timestamp("2025-01-01", tz="UTC"),
        end_date=pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc_w = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=pd.Timestamp("2020-01-01", tz="UTC"),
        end_date=pd.Timestamp("2025-01-01", tz="UTC"),
    )
    btc_m = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=pd.Timestamp("2025-01-01", tz="UTC"),
        end_date=pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc = pd.concat([btc_w, btc_m]).sort_index()
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

    # Load TV entries from as4.csv
    tv = pd.read_csv(r"c:\Users\roman\Downloads\as4.csv", sep=";")
    entry_mask = tv["Тип"].str.contains("Entry|Вход", case=False, na=False)
    tv_ent = tv[entry_mask].copy().reset_index(drop=True)
    tv_ent["ts_utc"] = pd.to_datetime(tv_ent["Дата и время"]) - pd.Timedelta(hours=3)

    def get_side(r):
        s = str(r.get("Сигнал", ""))
        t = str(r.get("Тип", ""))
        if "RsiSE" in s or "short" in t.lower():
            return "short"
        if "RsiLE" in s or "long" in t.lower() or "длинн" in t.lower():
            return "long"
        return "?"

    tv_ent["side"] = tv_ent.apply(get_side, axis=1)

    print(f"Engine:{len(trades)} TV:{len(tv_ent)}")
    print(f"  {'#':3}  {'dir':5}  {'eng_time':16}  {'tv_time':16}  t_ok  d_ok  ep_diff")
    n = min(len(trades), len(tv_ent))
    diffs = []
    for i in range(n):
        t = trades[i]
        tv_r = tv_ent.iloc[i]
        et = str(t.entry_time)[:16].replace("T", " ")
        tv_t = str(tv_r.ts_utc)[:16]
        t_ok = et == tv_t
        d_ok = t.direction == tv_r["side"]
        ep = t.entry_price
        tv_ep = float(str(tv_r["Цена USDT"]).replace(",", "."))
        ep_diff = ep - tv_ep
        if not t_ok or not d_ok:
            diffs.append(i + 1)
            print(
                f"  {i + 1:3}  {t.direction:5}  {et:16}  {tv_t:16}  {str(t_ok):5}  {str(d_ok):5}  {ep_diff:+.2f}  <---"
            )
    print(f"Divergences at trades: {diffs}")
    if not diffs:
        print("All entry times and directions MATCH!")


asyncio.run(run())
