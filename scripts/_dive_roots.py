"""
Deep dive on root divergences 139 and 142 — same entry time but PnL mismatch.
These are NOT signal timing issues but execution/exit differences.
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
from backend.backtesting.interfaces import BacktestInput, ExitReason, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")


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
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    btc = pd.concat(
        [
            await svc._fetch_historical_data(
                symbol="BTCUSDT", interval="30", start_date=pd.Timestamp("2020-01-01", tz="UTC"), end_date=START_DATE
            ),
            await svc._fetch_historical_data(symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE),
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

    # Load TV trades
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

    tv_exits["pnl_tv"] = tv_exits["Чистая прибыль / убыток USDT"].apply(parse_float)
    tv_entries["entry_px"] = tv_entries["Цена USDT"].apply(parse_float)
    tv_exits["exit_px"] = tv_exits["Цена USDT"].apply(parse_float)

    def tv_side(row):
        s, t = str(row.get("Сигнал", "")), str(row.get("Тип", ""))
        if "short" in t.lower() or "коротк" in t.lower() or "RsiSE" in s:
            return "short"
        if "long" in t.lower() or "длинн" in t.lower() or "RsiLE" in s:
            return "long"
        return "?"

    tv_entries["side"] = tv_entries.apply(tv_side, axis=1)

    def tv_exit_reason(row):
        s = str(row.get("Сигнал", ""))
        if "TP" in s or "Достигнут" in s:
            return "TP"
        if "SL" in s or "Стоп" in s:
            return "SL"
        return s[:20]

    tv_exits["xr_tv"] = tv_exits.apply(tv_exit_reason, axis=1)

    # Focus on all 8 root divergences
    for idx in [9, 12, 85, 89, 91, 139, 142, 144]:
        i = idx - 1
        t = trades[i]
        tv_e = tv_entries.iloc[i]
        tv_x = tv_exits.iloc[i]
        print(f"\n{'=' * 80}")
        print(f"TRADE #{idx}")
        print(f"{'=' * 80}")
        print(f"  Engine: {t.direction:5s}  entry={str(t.entry_time)[:19]}  exit={str(t.exit_time)[:19]}")
        print(f"          entry_px={t.entry_price:.2f}  exit_px={t.exit_price:.2f}  pnl={t.pnl:.4f}  fees={t.fees:.4f}")
        print(f"          exit_reason={t.exit_reason}  bars={t.duration_bars}")
        print(f"  TV:     {tv_e['side']:5s}  entry={str(tv_e['ts_utc'])[:19]}  exit={str(tv_x['ts_utc'])[:19]}")
        print(
            f"          entry_px={tv_e['entry_px']:.2f}  exit_px={tv_x['exit_px']:.2f}  pnl={tv_x['pnl_tv']:.4f}  xr={tv_x['xr_tv']}"
        )

        # Compute expected TP/SL for engine trade
        ep = t.entry_price
        if t.direction == "long":
            tp_price = ep * (1 + 0.023)
            sl_price = ep * (1 - 0.132)
        else:
            tp_price = ep * (1 - 0.023)
            sl_price = ep * (1 + 0.132)
        print(f"  Expected TP={tp_price:.2f}  SL={sl_price:.2f}")

        # Compute expected TP/SL for TV trade
        tv_ep_val = tv_e["entry_px"]
        side = tv_e["side"]
        if side == "long":
            tv_tp = tv_ep_val * (1 + 0.023)
            tv_sl = tv_ep_val * (1 - 0.132)
        else:
            tv_tp = tv_ep_val * (1 - 0.023)
            tv_sl = tv_ep_val * (1 + 0.132)
        print(f"  TV Expected TP={tv_tp:.2f}  SL={tv_sl:.2f}")

        # Show bars around entry/exit
        et_str = str(t.entry_time)[:19]
        xt_str = str(t.exit_time)[:19]
        try:
            et_ts = pd.Timestamp(et_str, tz="UTC")
            xt_ts = pd.Timestamp(xt_str, tz="UTC")
            # Entry bar and exit bar OHLCV
            if et_ts in candles.index:
                bar = candles.loc[et_ts]
                print(
                    f"  Entry bar OHLCV: O={bar['open']:.2f} H={bar['high']:.2f} L={bar['low']:.2f} C={bar['close']:.2f}"
                )
            if xt_ts in candles.index:
                bar = candles.loc[xt_ts]
                print(
                    f"  Exit  bar OHLCV: O={bar['open']:.2f} H={bar['high']:.2f} L={bar['low']:.2f} C={bar['close']:.2f}"
                )
        except:
            pass


asyncio.run(main())
