"""
Correct RSI alignment analysis — DB-only version (no API calls).

KEY INSIGHT: TV entry timestamp = bar_open_time[T+1] (bar AFTER signal bar T).
So signal bar T = tv_entry_time - 30 minutes.

We use BTC data from 2025-01-01 in the local DB. The divergences all occur
after 2025-02-12 (42+ days / 2000+ bars into the series), so Wilder RSI
is fully converged — no warmup API needed for analyzing divergences.

For the engine run we still need the warmup (to match the first trades),
so we re-use the already-working pattern from _run_rsi7.py but fall back
to DB-only if the API times out.
"""

import asyncio
import csv
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
import pandas_ta as ta

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.core.indicators import calculate_rsi as wilder_rsi

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
TV_FILE = r"c:\Users\roman\Downloads\z4.csv"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
WARMUP_BARS = 500
TF_MINUTES = 30
API_TIMEOUT = 30  # seconds (longer than default 10)


# ── Helpers ───────────────────────────────────────────────────────────────────


def load_strategy():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
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


def load_tv_trades():
    with open(TV_FILE, encoding="cp1251") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
    trades = []
    for i in range(1, len(rows), 2):
        if i + 1 >= len(rows):
            break
        entry_row = rows[i + 1]
        entry_type = entry_row[1].strip()
        entry_ts_str = entry_row[2].strip()
        entry_price = float(entry_row[4].replace(",", "."))
        dt_utc3 = pd.to_datetime(entry_ts_str)
        dt_utc = dt_utc3 - pd.Timedelta(hours=3)
        signal_bar_time = dt_utc - pd.Timedelta(minutes=TF_MINUTES)
        trades.append(
            {
                "trade_num": int(rows[i][0]),
                "direction": "short" if "short" in entry_type.lower() else "long",
                "entry_utc": dt_utc,
                "signal_bar_time": signal_bar_time,
                "price": entry_price,
            }
        )
    return trades


def load_btc_from_db():
    """Load BTCUSDT 30m from local DB (2025-01-01 onwards), tz-naive index."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT open_time, open_price, high_price, low_price, close_price, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='30' "
        "ORDER BY open_time ASC"
    ).fetchall()
    conn.close()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume"])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("open_time")
    df.index.name = "timestamp"
    return df


ETH_CACHE = r"d:\bybit_strategy_tester_v2\data\eth_30m_cache.csv"


def load_eth_from_cache():
    """Load ETHUSDT 30m from local CSV cache (populated by fetch_and_cache_eth)."""
    import os

    if not os.path.exists(ETH_CACHE):
        return None
    df = pd.read_csv(ETH_CACHE, index_col=0, parse_dates=True)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


# ── Main ──────────────────────────────────────────────────────────────────────


async def main():
    print("=" * 72)
    print("RSI CORRECT ALIGNMENT ANALYSIS  (DB-only, no API calls)")
    print("=" * 72)

    graph = load_strategy()
    rsi_block = next((b for b in graph["blocks"] if b.get("type") == "rsi"), None)
    rsi_params = rsi_block.get("params", {})
    period = int(rsi_params.get("period", 14))
    use_btc = bool(rsi_params.get("use_btc_source", False))
    cross_short_level = float(rsi_params.get("cross_short_level", 52.0))
    cross_long_level = float(rsi_params.get("cross_long_level", 24.0))
    print(f"RSI params: period={period}, use_btc_source={use_btc}")
    print(f"  cross_short_level={cross_short_level}, cross_long_level={cross_long_level}")

    # ── Load BTC from DB, ETH from cache or API ───────────────────────────────
    print("\nLoading BTC from DB...")
    btc_db = load_btc_from_db()
    print(f"BTC DB:  {len(btc_db)} bars [{btc_db.index[0]} .. {btc_db.index[-1]}]")

    eth_db = load_eth_from_cache()
    if eth_db is not None:
        print(f"ETH cache: {len(eth_db)} bars [{eth_db.index[0]} .. {eth_db.index[-1]}]")
    else:
        print("ETH cache not found — will fetch from API and cache for future runs")

    # ── Compute RSI from DB-only BTC (fully converged for Feb 12+ divergences) ─
    # Use same Wilder RSI formula as indicator_handlers.py
    # (ETH data not needed for RSI computation since use_btc_source=True)
    rsi_source_series = btc_db["close"]
    rsi_arr = wilder_rsi(rsi_source_series.values, period=period)
    rsi_db = pd.Series(rsi_arr, index=rsi_source_series.index)
    print(f"RSI from DB: {rsi_db.notna().sum()} valid bars")

    # ── Try to get API warmup (best effort, skip on timeout) ─────────────────
    rsi_full = rsi_db  # default: DB-only RSI
    print("\nTrying BTC warmup API (timeout=30s, best-effort)...")
    try:
        from backend.services.adapters.bybit import BybitAdapter

        adapter_api = BybitAdapter(timeout=API_TIMEOUT)
        btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * TF_MINUTES)
        raw_warmup = await asyncio.wait_for(
            adapter_api.get_historical_klines(
                symbol="BTCUSDT",
                interval="30",
                start_time=int(btc_start.timestamp() * 1000),
                end_time=int(START_DATE.timestamp() * 1000),
                market_type="linear",
            ),
            timeout=API_TIMEOUT,
        )
        if raw_warmup:
            df_w = pd.DataFrame(raw_warmup)
            col_map = {
                "startTime": "timestamp",
                "open_time": "timestamp",
                "openPrice": "open",
                "highPrice": "high",
                "lowPrice": "low",
                "closePrice": "close",
            }
            for old, new in col_map.items():
                if old in df_w.columns and new not in df_w.columns:
                    df_w = df_w.rename(columns={old: new})
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df_w.columns:
                    df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
            if "timestamp" in df_w.columns:
                if df_w["timestamp"].dtype in ["int64", "float64"]:
                    df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms", utc=True)
                else:
                    df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], utc=True)
                df_w = df_w.set_index("timestamp").sort_index()
            # Make tz-naive
            if df_w.index.tz is not None:
                df_w.index = df_w.index.tz_localize(None)
            btc_full = pd.concat([df_w, btc_db]).sort_index()
            btc_full = btc_full[~btc_full.index.duplicated(keep="last")]
            rsi_arr2 = wilder_rsi(btc_full["close"].values, period=period)
            rsi_series2 = pd.Series(rsi_arr2, index=btc_full.index)
            # Trim to ETH period
            rsi_full = rsi_series2.reindex(btc_db.index, method="ffill")
            print(f"  API warmup: {len(df_w)} bars. RSI re-computed with warmup.")
    except Exception as exc:
        print(f"  API warmup SKIPPED ({type(exc).__name__}): {exc}")
        print("  Using DB-only RSI (fully accurate for Feb 12+ divergences)")

    def get_rsi(ts):
        t = pd.Timestamp(ts)
        if t.tzinfo is not None:
            t = t.tz_localize(None)
        v = rsi_full.get(t)
        return float(v) if v is not None and pd.notna(v) else None

    # ── Run engine with best-effort API / cache ──────────────────────────────
    print("\nRunning engine...")
    import os

    svc = BacktestService()
    candles = None

    # Try to use cached ETH data first
    if eth_db is not None:
        candles = eth_db.copy()
        if candles.index.tz is None:
            candles.index = candles.index.tz_localize("UTC")
        print(f"ETH from cache: {len(candles)} bars")
    else:
        # Need to fetch from API
        print("  Fetching ETH 30m from Bybit API (timeout=30s)...")
        try:
            from backend.services.adapters.bybit import BybitAdapter as _BA

            _adapter_tmp = _BA(timeout=API_TIMEOUT)
            raw_eth = await asyncio.wait_for(
                _adapter_tmp.get_historical_klines(
                    symbol="ETHUSDT",
                    interval="30",
                    start_time=int(START_DATE.timestamp() * 1000),
                    end_time=int(END_DATE.timestamp() * 1000),
                    market_type="linear",
                ),
                timeout=API_TIMEOUT,
            )
            if not raw_eth:
                raise RuntimeError("Empty ETH response from API")
            df_eth = pd.DataFrame(raw_eth)
            col_map = {
                "startTime": "timestamp",
                "open_time": "timestamp",
                "openPrice": "open",
                "highPrice": "high",
                "lowPrice": "low",
                "closePrice": "close",
            }
            for old, new in col_map.items():
                if old in df_eth.columns and new not in df_eth.columns:
                    df_eth = df_eth.rename(columns={old: new})
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df_eth.columns:
                    df_eth[col] = pd.to_numeric(df_eth[col], errors="coerce")
            if "timestamp" in df_eth.columns:
                if df_eth["timestamp"].dtype in ["int64", "float64"]:
                    df_eth["timestamp"] = pd.to_datetime(df_eth["timestamp"], unit="ms", utc=True)
                else:
                    df_eth["timestamp"] = pd.to_datetime(df_eth["timestamp"], utc=True)
                df_eth = df_eth.set_index("timestamp").sort_index()
            candles = df_eth
            # Save to cache for future runs
            os.makedirs(os.path.dirname(ETH_CACHE), exist_ok=True)
            cache_save = df_eth.copy()
            if cache_save.index.tz is not None:
                cache_save.index = cache_save.index.tz_localize(None)
            cache_save.to_csv(ETH_CACHE)
            print(f"  ETH fetched: {len(candles)} bars. Saved to cache: {ETH_CACHE}")
        except Exception as exc:
            raise RuntimeError(f"Cannot get ETH 30m data (API timeout, no cache): {exc}") from exc

    # Build BTC series for adapter
    btc_for_adapter = None
    try:
        btc_main = await asyncio.wait_for(
            svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE),
            timeout=15,
        )
        # Try to include warmup
        btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * TF_MINUTES)
        from backend.services.adapters.bybit import BybitAdapter

        adapter_api2 = BybitAdapter(timeout=API_TIMEOUT)
        raw_w2 = await asyncio.wait_for(
            adapter_api2.get_historical_klines(
                symbol="BTCUSDT",
                interval="30",
                start_time=int(btc_start.timestamp() * 1000),
                end_time=int(START_DATE.timestamp() * 1000),
                market_type="linear",
            ),
            timeout=API_TIMEOUT,
        )
        if raw_w2:
            df_w2 = pd.DataFrame(raw_w2)
            col_map = {
                "startTime": "timestamp",
                "open_time": "timestamp",
                "openPrice": "open",
                "highPrice": "high",
                "lowPrice": "low",
                "closePrice": "close",
            }
            for old, new in col_map.items():
                if old in df_w2.columns and new not in df_w2.columns:
                    df_w2 = df_w2.rename(columns={old: new})
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df_w2.columns:
                    df_w2[col] = pd.to_numeric(df_w2[col], errors="coerce")
            if "timestamp" in df_w2.columns:
                if df_w2["timestamp"].dtype in ["int64", "float64"]:
                    df_w2["timestamp"] = pd.to_datetime(df_w2["timestamp"], unit="ms", utc=True)
                else:
                    df_w2["timestamp"] = pd.to_datetime(df_w2["timestamp"], utc=True)
                df_w2 = df_w2.set_index("timestamp").sort_index()
            if btc_main.index.tz is None:
                btc_main.index = btc_main.index.tz_localize("UTC")
            if df_w2.index.tz is None:
                df_w2.index = df_w2.index.tz_localize("UTC")
            btc_for_adapter = pd.concat([df_w2, btc_main]).sort_index()
            btc_for_adapter = btc_for_adapter[~btc_for_adapter.index.duplicated(keep="last")]
            print(f"BTC for engine: {len(btc_for_adapter)} bars (with warmup)")
        else:
            btc_for_adapter = btc_main
            print(f"BTC for engine: {len(btc_for_adapter)} bars (no warmup)")
    except Exception as exc:
        print(f"  BTC API SKIPPED: {exc}")
        btc_for_adapter = btc_db.copy()
        if btc_for_adapter.index.tz is None:
            btc_for_adapter.index = btc_for_adapter.index.tz_localize("UTC")
        print(f"BTC for engine: {len(btc_for_adapter)} bars (DB-only)")

    adapter_eng = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_for_adapter)
    signals = adapter_eng.generate_signals(candles)
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

    eng_result = FallbackEngineV4().run(
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
    engine_trades = eng_result.trades
    print(f"Engine trades: {len(engine_trades)}\n")

    # ── Load TV trades ────────────────────────────────────────────────────────
    tv_trades = load_tv_trades()
    tv_by_engine_ts = {}
    for t in tv_trades:
        eq = t["entry_utc"] - pd.Timedelta(minutes=TF_MINUTES)
        eq_naive = eq.tz_localize(None) if eq.tzinfo else eq
        tv_by_engine_ts[eq_naive] = t

    engine_ts_set = set()
    for t in engine_trades:
        ts = pd.Timestamp(t.entry_time)
        if ts.tzinfo:
            ts = ts.tz_localize(None)
        engine_ts_set.add(ts)

    extras = []
    for t in engine_trades:
        ts = pd.Timestamp(t.entry_time)
        if ts.tzinfo:
            ts = ts.tz_localize(None)
        if ts not in tv_by_engine_ts:
            extras.append(t)

    missing_tv = []
    for eng_ts, tv_t in tv_by_engine_ts.items():
        if eng_ts not in engine_ts_set:
            missing_tv.append((eng_ts, tv_t))

    print(f"engine={len(engine_trades)}, TV={len(tv_trades)}, extras={len(extras)}, missing_tv={len(missing_tv)}\n")

    # ── Extras RSI analysis ───────────────────────────────────────────────────
    print("=" * 72)
    print("EXTRAS (engine fires, TV skips) — RSI at signal bar T:")
    print(f"  {'#':>3}  {'Entry (engine)':16}  {'Dir':5}  {'RSI[T-1]':>9}  {'RSI[T]':>8}  {'dist[T-1]':>10}")
    print("-" * 72)
    extra_dists = []
    extra_dirs = []
    for i, t in enumerate(sorted(extras, key=lambda x: x.entry_time)):
        ts = pd.Timestamp(t.entry_time)
        if ts.tzinfo:
            ts = ts.tz_localize(None)
        prev = ts - pd.Timedelta(minutes=TF_MINUTES)
        r_t = get_rsi(ts)
        r_t1 = get_rsi(prev)
        dire = getattr(t, "direction", "short")
        level = cross_short_level if dire == "short" else cross_long_level
        dist = (r_t1 - level) if r_t1 is not None else float("nan")
        if r_t is None or r_t1 is None:
            print(f"  {i + 1:>3}  {str(ts)[:16]:16}  {dire:5}  RSI NOT FOUND")
            continue
        print(f"  {i + 1:>3}  {str(ts)[:16]:16}  {dire:5}  {r_t1:>9.4f}  {r_t:>8.4f}  {dist:>+10.4f}")
        extra_dists.append(dist)
        extra_dirs.append(dire)
    print()
    if extra_dists:
        print(
            f"  Avg dist (extras): {np.nanmean(extra_dists):>+8.4f}  "
            f"min={np.nanmin(extra_dists):+.4f}  max={np.nanmax(extra_dists):+.4f}"
        )
    print()

    # ── Missing TV RSI analysis (CORRECT signal bar = tv_entry - 30min) ──────
    print("=" * 72)
    print("MISSING TV (TV fires, engine skips) — RSI at signal bar T = tv_entry - 30min:")
    hdr = (
        f"  {'#':>3}  {'TV Entry (UTC)':16}  {'Signal Bar':16}  {'Dir':5}  "
        f"{'RSI[T-1]':>9}  {'RSI[T]':>8}  {'dist':>8}  {'cross?':>7}"
    )
    print(hdr)
    print("-" * 72)
    tv_miss_dists = []
    tv_miss_dirs = []
    tv_miss_anomaly = []
    for i, (eng_ts, tv_t) in enumerate(sorted(missing_tv, key=lambda x: x[0])):
        sig = tv_t["signal_bar_time"]
        sig_n = sig.tz_localize(None) if sig.tzinfo else sig
        prev_n = sig_n - pd.Timedelta(minutes=TF_MINUTES)
        r_t = get_rsi(sig_n)
        r_t1 = get_rsi(prev_n)
        dire = tv_t["direction"]
        level = cross_short_level if dire == "short" else cross_long_level
        if r_t is None or r_t1 is None:
            print(f"  {i + 1:>3}  RSI not found at sig_bar={sig_n}")
            continue
        dist = r_t1 - level
        cross_ok = r_t1 >= level and r_t < level
        e_str = str(tv_t["entry_utc"])[:16]
        s_str = str(sig_n)[:16]
        ok_str = "YES" if cross_ok else "NO"
        print(f"  {i + 1:>3}  {e_str:16}  {s_str:16}  {dire:5}  {r_t1:>9.4f}  {r_t:>8.4f}  {dist:>+8.4f}  {ok_str:>7}")
        tv_miss_dists.append(dist)
        tv_miss_dirs.append(dire)
        if not cross_ok:
            tv_miss_anomaly.append((i + 1, tv_t["entry_utc"], dire, r_t1, r_t, dist))
    print()
    if tv_miss_dists:
        print(
            f"  Avg dist (TV missing): {np.nanmean(tv_miss_dists):>+8.4f}  "
            f"min={np.nanmin(tv_miss_dists):+.4f}  max={np.nanmax(tv_miss_dists):+.4f}"
        )
    if tv_miss_anomaly:
        print("\n  ANOMALIES (TV fires but NOT a crossunder at signal bar T):")
        for num, ts, dire, r1, r, d in tv_miss_anomaly:
            print(f"    #{num}: {str(ts)[:16]}  dir={dire}  RSI[T-1]={r1:.4f}  RSI[T]={r:.4f}  dist={d:+.4f}")
    print()

    # ── Histograms ────────────────────────────────────────────────────────────
    def histogram(dists, label, lo=-2.0, hi=12.0, step=0.5):
        print(f"  {label}  (n={len(dists)}, mean={np.mean(dists):+.3f}):")
        bucket_lo = lo
        while bucket_lo < hi:
            bucket_hi = bucket_lo + step
            count = sum(1 for d in dists if bucket_lo <= d < bucket_hi)
            if count > 0:
                bar = "#" * min(count, 50)
                print(f"    [{bucket_lo:+.1f},{bucket_hi:+.1f}): {count:>3}  {bar}")
            bucket_lo = bucket_hi
        print()

    all_tv_short_dists = []
    for t in tv_trades:
        if t["direction"] != "short":
            continue
        sig_n = t["signal_bar_time"]
        sig_n = sig_n.tz_localize(None) if sig_n.tzinfo else sig_n
        prev_n = sig_n - pd.Timedelta(minutes=TF_MINUTES)
        r_t = get_rsi(sig_n)
        r_t1 = get_rsi(prev_n)
        if r_t is None or r_t1 is None:
            continue
        all_tv_short_dists.append(r_t1 - cross_short_level)

    print("=" * 72)
    print("HISTOGRAMS:")
    print()
    extra_short_dists = [d for d, dire in zip(extra_dists, extra_dirs, strict=False) if dire == "short"]
    tv_miss_short_dists = [d for d, dire in zip(tv_miss_dists, tv_miss_dirs, strict=False) if dire == "short"]
    histogram(extra_short_dists, "EXTRAS (engine short):")
    histogram(all_tv_short_dists, "ALL TV SHORT TRADES:")
    histogram(tv_miss_short_dists, "TV MISSING SHORT:")

    # ── Threshold search ──────────────────────────────────────────────────────
    print("=" * 72)
    print("THRESHOLD SEARCH:")
    print()
    if not extra_dists or not tv_miss_dists:
        print("  Not enough data for threshold search")
        return

    min_extra = np.nanmin(extra_dists)
    max_missing = np.nanmax(tv_miss_dists)
    print(f"  Extras:   min dist = {min_extra:+.4f}  (smallest extra RSI[T-1] - level)")
    print(f"  TV miss:  max dist = {max_missing:+.4f}  (largest missing-TV RSI[T-1] - level)")

    if max_missing < min_extra:
        threshold = (min_extra + max_missing) / 2.0
        print("\n  CLEAN SEPARATION!")
        print("  Optimal threshold T such that rsi_prev <= level + T:")
        print(f"    T = {threshold:+.4f}")
        print(f"    Filter: rsi_prev <= {cross_short_level + threshold:.4f}")
        print(f"    Code:   cross_short = cross_short & (rsi_prev <= cross_short_level + {threshold:.4f})")
    else:
        print(f"\n  OVERLAP detected (max_missing={max_missing:+.4f} >= min_extra={min_extra:+.4f})")
        print(f"  Overlap size = {max_missing - min_extra:.4f}")
        # List cases in overlap
        overlap_extra = [
            (d, t)
            for d, t in zip(extra_dists, sorted(extras, key=lambda x: x.entry_time), strict=False)
            if d <= max_missing + 0.001
        ]
        overlap_tv_miss = [
            (d, tv_t)
            for d, (_, tv_t) in zip(tv_miss_dists, sorted(missing_tv, key=lambda x: x[0]), strict=False)
            if d >= min_extra - 0.001
        ]
        if overlap_extra:
            print(f"\n  Extras with dist <= {max_missing:+.4f}:")
            for d, t in overlap_extra:
                ts = (
                    pd.Timestamp(t.entry_time).tz_localize(None)
                    if pd.Timestamp(t.entry_time).tzinfo
                    else pd.Timestamp(t.entry_time)
                )
                print(f"    {str(ts)[:16]}  dist={d:+.4f}")
        if overlap_tv_miss:
            print(f"\n  TV missing with dist >= {min_extra:+.4f}:")
            for d, tv_t in overlap_tv_miss:
                print(f"    {str(tv_t['entry_utc'])[:16]}  dist={d:+.4f}")


asyncio.run(main())
