"""Direct side-by-side: Engine trades vs TV trades, corrected parsing."""

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

TV_CSV = r"c:\Users\roman\Downloads\as4.csv"


def parse_tv_trades(csv_path):
    """Parse TV trades from as4.csv (semicolon-separated, Moscow UTC+3)."""
    tv_raw = pd.read_csv(csv_path, sep=";")
    trades = []
    for i in range(0, len(tv_raw), 2):
        exit_row = tv_raw.iloc[i]
        entry_row = tv_raw.iloc[i + 1]
        entry_type = str(entry_row["Тип"]).strip()
        direction = "short" if "short" in entry_type.lower() else "long"
        entry_msk = pd.Timestamp(str(entry_row["Дата и время"]).strip())
        exit_msk = pd.Timestamp(str(exit_row["Дата и время"]).strip())
        entry_utc = entry_msk - pd.Timedelta(hours=3)
        exit_utc = exit_msk - pd.Timedelta(hours=3)
        pnl = float(str(exit_row["Чистая прибыль / убыток USDT"]).replace(",", ".").strip())
        trades.append(
            {
                "direction": direction,
                "entry_time": entry_utc,
                "exit_time": exit_utc,
                "pnl": pnl,
            }
        )
    return trades


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
    engine_trades = result.trades
    tv_trades = parse_tv_trades(TV_CSV)

    print(f"Engine: {len(engine_trades)} trades, TV: {len(tv_trades)} trades")
    print()

    # Side-by-side comparison for specific ranges
    for start, end in [(1, 15), (80, 95), (135, 151)]:
        print(f"\n{'=' * 110}")
        print(f"Trades {start}-{end}")
        print(f"{'=' * 110}")
        print(f"{'#':>3s}  {'ENGINE':^45s}  {'TV':^45s}  Match")
        print(f"{'':>3s}  {'dir':5s} {'entry':19s} {'exit':19s}  |  {'dir':5s} {'entry':19s} {'exit':19s}")
        print("-" * 110)

        n = max(len(engine_trades), len(tv_trades))
        for idx in range(start - 1, min(end, n)):
            e_dir = e_entry = e_exit = ""
            t_dir = t_entry = t_exit = ""
            match = ""

            if idx < len(engine_trades):
                t = engine_trades[idx]
                e_dir = t.direction
                e_entry = str(t.entry_time)[:19].replace("T", " ")
                e_exit = str(t.exit_time)[:19].replace("T", " ")

            if idx < len(tv_trades):
                tv = tv_trades[idx]
                t_dir = tv["direction"]
                t_entry = str(tv["entry_time"])[:19]
                t_exit = str(tv["exit_time"])[:19]

            if e_entry and t_entry:
                if e_entry == t_entry and e_exit == t_exit and e_dir == t_dir:
                    match = "✅"
                elif e_entry == t_entry and e_dir == t_dir:
                    match = "⏱️"  # Same entry, different exit
                elif e_dir == t_dir:
                    match = "❌"  # Same dir, different times
                else:
                    match = "🔴"  # Different direction

            print(
                f"{idx + 1:3d}  {e_dir:5s} {e_entry:19s} {e_exit:19s}  |  {t_dir:5s} {t_entry:19s} {t_exit:19s}  {match}"
            )


asyncio.run(main())
