"""
Test Strategy_RSI_L/S_9 against TradingView CSV (x4.csv).
TV: 146 trades (31L + 115S), ETHUSDT 30m, BTC RSI source = BINANCE:BTCUSDT
Key vs _7: use_long_range=True (28<=RSI<=50), use_short_range=True (50<=RSI<=70)
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
import requests

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"  # Strategy_RSI_L/S_9
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
TV_CSV = r"c:\Users\roman\Downloads\x4.csv"
TV_TOTAL = 146  # x2.csv: Всего сделок 146 (31L + 115S) — excludes open position
TV_TOTAL_WITH_OPEN = 147  # total entry rows in CSV (includes 1 open trade)


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

    # Print RSI block params
    for blk in blocks:
        if blk.get("type") == "rsi":
            print("RSI block params:", json.dumps(blk["params"], indent=2))

    # ── Fetch candles ─────────────────────────────────────────────────────────
    svc = BacktestService()
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    print(f"\nETH 30m: {len(candles)} bars  [{candles.index[0]} .. {candles.index[-1]}]")

    # ── Fetch BTC from BINANCE (matches TV source: BINANCE:BTCUSDT) ─────────
    # TV script uses: request.security("BINANCE:BTCUSDT", ...)
    # Binance data gives different RSI values than Bybit (~35-45 USD price diff)
    # This is the ROOT CAUSE of the divergence — must use Binance for parity.
    btc_start = pd.Timestamp("2020-01-01", tz="UTC")
    print("Fetching Binance BTC 30m with 2020 warmup (TV source)...")

    def get_binance_klines(symbol: str, interval: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        all_rows = []
        st = int(start.timestamp() * 1000)
        et = int(end.timestamp() * 1000)
        while st < et:
            kline_params: dict[str, str | int] = {
                "symbol": symbol,
                "interval": interval,
                "startTime": st,
                "endTime": et,
                "limit": 1000,
            }
            resp = requests.get(
                "https://api.binance.com/api/v3/klines",
                params=kline_params,
                timeout=30,
            )
            data = resp.json()
            if not data:
                break
            all_rows.extend(data)
            st = data[-1][0] + 1
            if len(data) < 1000:
                break
        df = pd.DataFrame(
            all_rows,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "qav",
                "num_trades",
                "tbbav",
                "tbqav",
                "ignore",
            ],
        )
        df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df = df.set_index("timestamp")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df

    try:
        bn_warmup = get_binance_klines("BTCUSDT", "30m", btc_start, START_DATE)
        bn_main = get_binance_klines("BTCUSDT", "30m", START_DATE, END_DATE)
        btc_candles = pd.concat([bn_warmup, bn_main]).sort_index()
        btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
        print(f"BTC 30m (Binance): {len(btc_candles)} bars (warmup from {btc_start.date()} to {START_DATE.date()})")
    except Exception as e:
        print(f"Binance fetch failed, falling back to Bybit: {e}")
        btc_main_bybit = await svc._fetch_historical_data(
            symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
        )
        btc_candles = btc_main_bybit

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

    # ── Load TV CSV (x4.csv — entry rows only) ───────────────────────────────
    tv = pd.read_csv(TV_CSV, sep=";")
    print(f"\nTV CSV columns: {list(tv.columns)}")

    # Detect entry rows: "Entry short" or "Вход в длинную позицию"
    entry_mask = tv["Тип"].str.contains("Entry|Вход", case=False, na=False)
    tv_ent = tv[entry_mask].copy()
    print(f"TV entry rows: {len(tv_ent)}")

    # Timestamp: x4.csv uses "YYYY-MM-DD HH:MM" format already (no timezone)
    # TV dates in Moscow time (UTC+3) → convert to UTC
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

    print(f"\nEntry time matches: {ok_time}/{total}  Entry price matches (±1): {ok_ep}/{total}")
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


asyncio.run(main())
