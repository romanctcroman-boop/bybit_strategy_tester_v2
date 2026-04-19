"""
Test RSI computation using BTCUSDT SPOT data instead of BTCUSDT linear perpetual.
TV may use BYBIT:BTCUSDT spot as the BTC source for RSI.
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
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
WARMUP_BARS = 500


def load_graph():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br)
    conns = json.loads(cr)
    gp = json.loads(gr)
    ms = gp.get("main_strategy", {})
    return {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
        **({"main_strategy": ms} if ms else {}),
    }


def process_raw_klines(raw) -> pd.DataFrame:
    """Convert raw klines (list of dicts) to DataFrame with DatetimeIndex."""
    df = pd.DataFrame(raw)
    col_map = {
        "startTime": "timestamp",
        "open_time": "timestamp",
        "openPrice": "open",
        "highPrice": "high",
        "lowPrice": "low",
        "closePrice": "close",
    }
    for old, new in col_map.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "timestamp" in df.columns:
        if df["timestamp"].dtype in ["int64", "float64"]:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
    return df


async def fetch_btc_spot_full() -> pd.DataFrame:
    """Fetch BTCUSDT spot 30m from warmup start to end date."""
    svc = BacktestService()
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)

    # Fetch in chunks: Bybit API can return up to 1000 bars per call
    # 2025-01-01 to 2026-02-24 = ~600+ days = ~29,000 bars
    CHUNK_BARS = 1000  # 1000 bars × 30min = 500 hours per chunk

    print(f"Fetching BTCUSDT SPOT 30m from {btc_start} to {END_DATE}...")

    all_chunks: list[pd.DataFrame] = []
    current_ts = int(btc_start.timestamp() * 1000)
    end_ts = int(END_DATE.timestamp() * 1000)

    while current_ts < end_ts:
        chunk_end = min(current_ts + CHUNK_BARS * 30 * 60 * 1000, end_ts)
        raw = await svc.adapter.get_historical_klines(
            symbol="BTCUSDT",
            interval="30",
            start_time=current_ts,
            end_time=chunk_end,
            market_type="spot",
        )
        if raw:
            df_chunk = process_raw_klines(raw)
            if df_chunk.index.tz is None:
                df_chunk.index = df_chunk.index.tz_localize("UTC")
            all_chunks.append(df_chunk)
            # next chunk starts at last fetched bar + 30min
            last_ts = int(df_chunk.index[-1].timestamp() * 1000) + 30 * 60 * 1000
            if last_ts <= current_ts:
                break  # no progress
            current_ts = last_ts
        else:
            current_ts = chunk_end

    if not all_chunks:
        raise RuntimeError("No spot data fetched!")

    spot_full = pd.concat(all_chunks).sort_index()
    spot_full = spot_full[~spot_full.index.duplicated(keep="last")]
    print(f"  Spot: {len(spot_full)} bars  [{spot_full.index[0]} — {spot_full.index[-1]}]")
    return spot_full


async def run_with_btc(btc_candles: pd.DataFrame, label: str) -> list:
    """Run engine with given BTC candles for RSI source, return trades."""
    graph = load_graph()
    svc = BacktestService()
    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles)
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
            initial_capital=10_000.0,
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
        )
    )
    print(f"[{label}] Trades: {len(result.trades)}  (TV=147)")
    return result.trades


async def main():
    svc = BacktestService()

    # --- Perp BTC (current approach) ---
    print("=== Fetching BTCUSDT PERP (current approach) ===")
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    warmup_start_ts = int(btc_start.timestamp() * 1000)
    warmup_end_ts = int(START_DATE.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        "BTCUSDT", "30", warmup_start_ts, warmup_end_ts, market_type="linear"
    )
    if raw_warmup:
        df_w = process_raw_klines(raw_warmup)
        if btc_main.index.tz is None:
            btc_main.index = btc_main.index.tz_localize("UTC")
        if df_w.index.tz is None:
            df_w.index = df_w.index.tz_localize("UTC")
        btc_perp = pd.concat([df_w, btc_main]).sort_index()
        btc_perp = btc_perp[~btc_perp.index.duplicated(keep="last")]
    else:
        btc_perp = btc_main
    print(f"  Perp: {len(btc_perp)} bars")

    # --- Spot BTC (test) ---
    print("\n=== Fetching BTCUSDT SPOT ===")
    btc_spot = await fetch_btc_spot_full()

    # --- Run engines ---
    print("\n=== Running engines ===")
    trades_perp = await run_with_btc(btc_perp, "PERP")
    trades_spot = await run_with_btc(btc_spot, "SPOT")

    # --- Compare: find trades in perp but not spot (by entry time ± 30 min) ---
    PRICE_TOL = 0.02
    TOLERANCE = pd.Timedelta(minutes=90)

    perp_matched: set[int] = set()
    spot_matched: set[int] = set()
    for i, pt in enumerate(trades_perp):
        for j, st in enumerate(trades_spot):
            if j in spot_matched:
                continue
            pt_naive = pt.entry_time.replace(tzinfo=None) if hasattr(pt.entry_time, "tz") else pt.entry_time
            st_naive = st.entry_time.replace(tzinfo=None) if hasattr(st.entry_time, "tz") else st.entry_time
            if st.direction == pt.direction and abs(st_naive - pt_naive) <= TOLERANCE:
                perp_matched.add(i)
                spot_matched.add(j)
                break

    perp_extra = [t for i, t in enumerate(trades_perp) if i not in perp_matched]
    spot_extra = [t for j, t in enumerate(trades_spot) if j not in spot_matched]

    print(f"\nPerp extra (not in spot): {len(perp_extra)}")
    for t in perp_extra[:10]:
        print(f"  {t.direction:5s} {t.entry_time}  ep={t.entry_price:.2f}")

    print(f"\nSpot extra (not in perp): {len(spot_extra)}")
    for t in spot_extra[:10]:
        print(f"  {t.direction:5s} {t.entry_time}  ep={t.entry_price:.2f}")

    # Show detailed comparison around Feb 12
    print("\n=== PERP trades Feb 10-15 ===")
    for t in trades_perp:
        et = t.entry_time.replace(tzinfo=None) if hasattr(t.entry_time, "tz") else t.entry_time
        if pd.Timestamp("2025-02-10") <= et <= pd.Timestamp("2025-02-16"):
            xt = t.exit_time.replace(tzinfo=None) if hasattr(t.exit_time, "tz") else t.exit_time
            print(f"  {t.direction:5s} {et} -> {xt}  ep={t.entry_price:.2f}")

    print("\n=== SPOT trades Feb 10-15 ===")
    for t in trades_spot:
        et = t.entry_time.replace(tzinfo=None) if hasattr(t.entry_time, "tz") else t.entry_time
        if pd.Timestamp("2025-02-10") <= et <= pd.Timestamp("2025-02-16"):
            xt = t.exit_time.replace(tzinfo=None) if hasattr(t.exit_time, "tz") else t.exit_time
            print(f"  {t.direction:5s} {et} -> {xt}  ep={t.entry_price:.2f}")


asyncio.run(main())
