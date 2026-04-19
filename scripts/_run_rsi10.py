"""
Test Strategy_RSI_L/S_10 against TradingView CSV (qq4.csv).
TV: 150 trades (29L + 121S), ETHUSDT.P 30m, BTC RSI source = BYBIT:BTCUSDT (auto from chart)
Key vs _9: TV script fixed — BTC ticker now uses exchange from chart (Bybit), not hardcoded BINANCE.
Strategy ID: dd2969a2-bbba-410e-b190-be1e8cc50b21 (same as _9, just renamed in UI)
Params identical to _9: rsi14, cross_long=24, cross_short=52, range L:[28,50], range S:[50,70],
                        tp=2.3%, sl=13.2%, use_btc_source=true
"""

import asyncio
import json
import sqlite3
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"  # Strategy_RSI_L/S_10 (same ID as _9)
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
TV_CSV = r"c:\Users\roman\Downloads\qq4.csv"
TV_TOTAL = 150  # qq2.csv: Всего сделок 150 (29L + 121S) — excludes open position
TV_TOTAL_WITH_OPEN = 151  # includes 1 open trade


async def main():
    # ── Load strategy graph ──────────────────────────────────────────────────
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

    # Print RSI block params for verification
    for blk in blocks:
        if blk.get("type") == "rsi":
            print("RSI block params:", json.dumps(blk["params"], indent=2, ensure_ascii=False))

    # ── Fetch ETH candles (main chart instrument) ─────────────────────────────
    svc = BacktestService()
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    print(f"\nETH 30m (Bybit): {len(candles)} bars  [{candles.index[0]} .. {candles.index[-1]}]")

    # ── Fetch BTC from BYBIT (matches fixed TV source: BYBIT:BTCUSDT) ────────
    # TV script now uses: exchange from chart (Bybit), so BYBIT:BTCUSDT.P
    # Using warmup from 2020 for RSI convergence (14-period RSI needs ~200+ bars)
    btc_start = pd.Timestamp("2020-01-01", tz="UTC")
    print("Fetching Bybit BTC 30m with 2020 warmup (TV source = Bybit)...")

    # Bybit only has data from ~2020, fetch in chunks
    btc_warmup = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=btc_start, end_date=START_DATE
    )
    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    btc_candles = pd.concat([btc_warmup, btc_main]).sort_index()
    btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
    print(f"BTC 30m (Bybit): {len(btc_candles)} bars (warmup from {btc_start.date()} to {START_DATE.date()})")

    # ── Generate signals ──────────────────────────────────────────────────────
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles, btcusdt_5m_ohlcv=None)
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
    print(f"Signals: {le.sum()} long_entries  {se.sum()} short_entries")

    # ── Run engine ────────────────────────────────────────────────────────────
    def run_engine(next_bar_open: bool, label: str):
        r = FallbackEngineV4().run(
            BacktestInput(
                candles=candles,
                long_entries=le,
                long_exits=lx,
                short_entries=se,
                short_exits=sx,
                initial_capital=1_000_000.0,
                position_size=0.10,
                use_fixed_amount=True,
                fixed_amount=100.0,
                leverage=10,
                stop_loss=0.132,
                take_profit=0.023,
                taker_fee=0.0007,
                slippage=0.0,
                direction=TradeDirection.BOTH,
                pyramiding=1,
                interval="30",
                entry_on_next_bar_open=next_bar_open,
            )
        )
        trd = r.trades
        longs = [t for t in trd if t.direction == "long"]
        shorts = [t for t in trd if t.direction == "short"]
        print(f"{label}: {len(trd)} trades ({len(longs)}L + {len(shorts)}S)")
        return trd

    base_trades = run_engine(False, "BASELINE (entry_on_next_bar_open=False)")
    next_trades = run_engine(True, "NEXT_BAR  (entry_on_next_bar_open=True )")

    # ── Load TV CSV (qq4.csv — entry rows only) ───────────────────────────────
    tv = pd.read_csv(TV_CSV, sep=";")

    # Detect entry rows: "Entry short" / "Вход в длинную позицию"
    entry_mask = tv["Тип"].str.contains("Entry|Вход", case=False, na=False)
    tv_ent = tv[entry_mask].copy()
    print(f"\nTV entry rows: {len(tv_ent)}")

    # Timestamp: qq4.csv uses "YYYY-MM-DD HH:MM" — Moscow time (UTC+3) → UTC
    tv_ent["ts_utc"] = pd.to_datetime(tv_ent["Дата и время"]) - pd.Timedelta(hours=3)

    # Side
    def get_side(row):
        sig = str(row.get("Сигнал", ""))
        t = str(row.get("Тип", ""))
        if "RsiSE" in sig or "short" in t.lower():
            return "short"
        if "RsiLE" in sig or "long" in t.lower() or "длинн" in t.lower():
            return "long"
        return "unknown"

    tv_ent["side"] = tv_ent.apply(get_side, axis=1)

    # Parse entry price
    price_col_raw = "Цена USDT"
    if price_col_raw in tv_ent.columns:
        tv_ent["ep"] = (
            tv_ent[price_col_raw]
            .astype(str)
            .str.replace(",", ".")
            .apply(lambda x: float(x.strip()) if x.strip() not in ("nan", "", "None") else 0.0)
        )
    else:
        tv_ent["ep"] = 0.0

    tv_ent = tv_ent.reset_index(drop=True)
    longs_tv = tv_ent[tv_ent["side"] == "long"]
    shorts_tv = tv_ent[tv_ent["side"] == "short"]
    print(f"TV entries: {len(tv_ent)} total ({len(longs_tv)}L + {len(shorts_tv)}S)")

    # ── Full comparison ───────────────────────────────────────────────────────
    print()
    print("=" * 95)
    print("COMPARISON: NEXT_BAR engine vs TV")
    print("=" * 95)
    print(f"  {'#':3s}  {'Side':5s}  {'Eng time':16s}  {'TV time':16s}  time_ok  {'Eng ep':10s}  {'TV ep':10s}  ep_ok")
    ok_time = ok_ep = total = 0
    tv_rows = list(tv_ent.itertuples())
    compare_n = min(len(next_trades), len(tv_rows))
    for i in range(compare_n):
        t = next_trades[i]
        tv_row = tv_rows[i]
        tv_time = str(tv_row.ts_utc)[:16].replace("T", " ")
        eng_time = str(t.entry_time)[:16].replace("T", " ")
        tm = eng_time == tv_time
        tv_ep = tv_row.ep
        ep = abs(t.entry_price - tv_ep) < 1.0 if tv_ep > 0 else None
        ok_time += int(tm)
        ok_ep += int(ep) if ep is not None else 0
        total += 1
        ep_str = "OK" if ep else ("DIFF" if ep is not None else "N/A")
        print(
            f"  {i + 1:3d}  {t.direction:5s}  {eng_time:16s}  {tv_time:16s}  {'OK' if tm else 'DIFF':7s}  "
            f"{t.entry_price:10.2f}  {tv_ep:10.2f}  {ep_str}"
        )

    # Leftovers: engine trades without TV match
    if len(next_trades) > compare_n:
        print("\n  Engine-only (no TV match):")
        for i in range(compare_n, len(next_trades)):
            t = next_trades[i]
            eng_time = str(t.entry_time)[:16].replace("T", " ")
            print(
                f"  {i + 1:3d}  {t.direction:5s}  {eng_time:16s}  {'N/A':16s}  {'---':7s}  {t.entry_price:10.2f}  {'N/A':>10s}  ---"
            )

    # Leftovers: TV trades without engine match
    if len(tv_rows) > compare_n:
        print("\n  TV-only (no engine match):")
        for i in range(compare_n, len(tv_rows)):
            tv_row = tv_rows[i]
            tv_time = str(tv_row.ts_utc)[:16].replace("T", " ")
            print(
                f"  {i + 1:3d}  {tv_row.side:5s}  {'N/A':16s}  {tv_time:16s}  {'---':7s}  {'N/A':>10s}  {tv_row.ep:10.2f}  ---"
            )

    print(f"\nEntry time matches: {ok_time}/{total}  Entry price matches (+-1): {ok_ep}/{total}")
    diff = TV_TOTAL - len(next_trades)
    print()
    print("=" * 95)
    print(f"RESULT: baseline={len(base_trades)}  next_bar={len(next_trades)}  TV={TV_TOTAL}  diff={diff:+d}")
    if diff == 0:
        print("PARITY ACHIEVED! Trade count matches TV exactly.")
    elif abs(diff) <= 3:
        print(f"Close -- only {abs(diff)} trade(s) off.")
    else:
        print(f"Still {abs(diff)} trade(s) off.")
    print("=" * 95)


asyncio.run(main())
