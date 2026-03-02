"""
Engine Calibration Script — Strategy-A2
=========================================
Runs Strategy-A2 (RSI + Static SL/TP) through ALL available engines
and compares results against the TradingView gold standard (155 trades).

TV Gold Standard:
  - Total trades  : 155
  - Net profit    : 1023.57 USDT
  - Win rate      : 90.32%
  - Profit factor : 1.511
  - Sharpe        : 0.35

Engines tested:
  1. FallbackEngineV4  (reference/gold standard)
  2. NumbaEngineV2     (JIT, should be 100% parity)
  3. FallbackEngineV3  (deprecated, pyramiding era)
  4. FallbackEngineV2  (deprecated, legacy)
  5. BacktestEngine    (engine.py, via _run_fallback path)
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from loguru import logger

logger.remove()  # Suppress engine logs — only our output matters

# ── TV Gold Standard ──────────────────────────────────────────────────────────
TV = {
    "total_trades": 155,
    "net_profit": 1023.57,
    "win_rate": 90.32,
    "profit_factor": 1.511,
    "sharpe": 0.35,
    "sortino": 0.587,
    "long_trades": 31,
    "short_trades": 124,
    "commission": 216.45,
}

# ── Load Strategy-A2 params from DB ──────────────────────────────────────────
import sqlite3

conn = sqlite3.connect("data.sqlite3")

# Load the known-good backtest trades (numba_v2 result = TV parity)
cur = conn.execute("SELECT trades, parameters FROM backtests WHERE id LIKE '68758d14%'")
row = cur.fetchone()
reference_trades = json.loads(row[0])
bt_params = json.loads(row[1])
conn.close()

print(f"Reference trades loaded: {len(reference_trades)}")
print(f"Params: {bt_params}")
print()

# ── Load OHLCV data with warmup prefix (2024-12-01 → 2026-03-01) ─────────────
# We load from 2024-12-01 so RSI(14) is fully warmed up before 2025-01-01.
# Backtest still starts at 2025-01-01 — engines receive full data but entry_on_next_bar_open
# means the first trade entry can only happen on/after 2025-01-01 13:30 UTC (TV gold standard).
WARMUP_START_DATE = "2024-12-01"
BACKTEST_START_DATE = "2025-01-01"
BACKTEST_END_DATE = "2026-03-01"

print("Loading ETHUSDT 30m OHLCV data (with warmup from 2024-12-01)...")
kline_conn = sqlite3.connect("data.sqlite3")

cur = kline_conn.execute(
    "SELECT open_time, open_price, high_price, low_price, close_price, volume "
    "FROM bybit_kline_audit "
    "WHERE symbol='ETHUSDT' AND interval='30' AND market_type='linear' "
    "AND open_time_dt >= ? AND open_time_dt < ? "
    "ORDER BY open_time ASC",
    (WARMUP_START_DATE, BACKTEST_END_DATE),
)
rows = cur.fetchall()
print(f"  Loaded {len(rows)} candles (incl. warmup)")

ohlcv_full = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume"])
ohlcv_full["open_time"] = pd.to_datetime(ohlcv_full["open_time"], unit="ms", utc=True)
ohlcv_full = ohlcv_full.set_index("open_time").astype(float)
print(f"  Full range: {ohlcv_full.index[0]} -> {ohlcv_full.index[-1]}")

# The slice actually used for backtesting (2025-01-01+) — needed for BacktestEngine / config
ohlcv = ohlcv_full.loc[BACKTEST_START_DATE:]
print(f"  Backtest range: {ohlcv.index[0]} -> {ohlcv.index[-1]} ({len(ohlcv)} candles)")
print()

# ── Load BTC data (needed by RSI block with use_btc_source=True) ──────────────
print("Loading BTCUSDT 30m OHLCV data (with warmup from 2024-12-01)...")
cur = kline_conn.execute(
    "SELECT open_time, open_price, high_price, low_price, close_price, volume "
    "FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear' "
    "AND open_time_dt >= ? AND open_time_dt < ? "
    "ORDER BY open_time ASC",
    (WARMUP_START_DATE, BACKTEST_END_DATE),
)
btc_rows = cur.fetchall()
kline_conn.close()

btc_ohlcv = None
btc_ohlcv_full = None
if btc_rows:
    btc_ohlcv_full = pd.DataFrame(btc_rows, columns=["open_time", "open", "high", "low", "close", "volume"])
    btc_ohlcv_full["open_time"] = pd.to_datetime(btc_ohlcv_full["open_time"], unit="ms", utc=True)
    btc_ohlcv_full = btc_ohlcv_full.set_index("open_time").astype(float)
    btc_ohlcv = btc_ohlcv_full  # pass full (with warmup) to adapter
    print(f"  BTC loaded: {len(btc_ohlcv_full)} candles")
else:
    print("  BTC data NOT found!")
print()

# ── Build strategy adapter from DB strategy data ─────────────────────────────
print("Building strategy adapter from DB...")
db_conn2 = sqlite3.connect("data.sqlite3")
cur = db_conn2.execute(
    "SELECT builder_blocks, builder_connections, builder_graph FROM strategies WHERE id LIKE '149454c2%'"
)
s_row = db_conn2.fetchone() if hasattr(db_conn2, "fetchone") else None
s_row = cur.fetchone()
db_conn2.close()

builder_blocks = json.loads(s_row[0]) if s_row[0] else []
builder_connections = json.loads(s_row[1]) if s_row[1] else []
builder_graph_raw = json.loads(s_row[2]) if s_row[2] else {}

print(f"  Blocks: {[b.get('type', '?') for b in builder_blocks]}")
print(f"  Connections: {len(builder_connections)}")

strategy_graph = {
    "name": "Strategy-A2 (calibration)",
    "description": "",
    "blocks": builder_blocks,
    "connections": builder_connections,
    "market_type": "linear",
    "direction": "both",
    "interval": "30",
}
if builder_graph_raw.get("main_strategy"):
    strategy_graph["main_strategy"] = builder_graph_raw["main_strategy"]

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc_ohlcv)
print("  Adapter created OK")
print()

# ── Build BacktestConfig ──────────────────────────────────────────────────────
from backend.backtesting.models import BacktestConfig

config = BacktestConfig(
    symbol="ETHUSDT",
    interval="30",
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
    initial_capital=10000.0,
    position_size=0.1,
    leverage=10.0,
    stop_loss=0.132,
    take_profit=0.023,
    commission_value=0.0007,
    direction="both",
    pyramiding=1,
    sl_type="average_price",
    slippage=0.0,
    breakeven_enabled=False,
    close_only_in_profit=False,
    strategy_type="builder",
    strategy_params={"strategy_type": "builder"},
)

# ── Generate signals once on FULL data (incl. warmup) ────────────────────────
# Pass ohlcv_full (with 2024-12-01 prefix) so RSI(14) is warmed up.
# Then slice signals back to 2025-01-01 for the actual backtest window.
print("Generating signals on full data (with warmup)...")
signals_full = adapter.generate_signals(ohlcv_full)

# Slice signals to backtest window [2025-01-01, ...)
backtest_start_ts = pd.Timestamp(BACKTEST_START_DATE, tz="UTC")
warmup_bars = ohlcv_full.index.searchsorted(backtest_start_ts)
print(f"  Warmup bars: {warmup_bars} (discarded from signal arrays)")


def _slice_signal(sig, start_idx: int, total_len: int):
    if sig is None:
        return np.zeros(total_len, dtype=bool)
    arr = np.asarray(sig, dtype=bool)
    return arr[start_idx:]


n_bt = len(ohlcv)  # backtest window length
le = _slice_signal(signals_full.entries, warmup_bars, n_bt)
se = _slice_signal(signals_full.short_entries, warmup_bars, n_bt)
lx = _slice_signal(signals_full.exits, warmup_bars, n_bt)
sx = _slice_signal(signals_full.short_exits, warmup_bars, n_bt)

print(f"  Long entries (post-warmup) : {int(le.sum())}")
print(f"  Short entries (post-warmup): {int(se.sum())}")
assert len(le) == len(ohlcv), f"Signal length mismatch: {len(le)} != {len(ohlcv)}"
print()

# ── BacktestInput builder ─────────────────────────────────────────────────────
from backend.backtesting.interfaces import BacktestInput, TradeDirection


def make_input() -> BacktestInput:
    """Convert signals + ohlcv into BacktestInput for V2/V3/V4/Numba engines.

    CRITICAL: TV uses fixed notional = initial_capital * position_size (NOT compounding equity).
    BacktestEngine._run_fallback uses: position_value = initial_capital * position_size (fixed).
    FallbackEngineV4 uses: order_capital = cash * position_size (grows with equity!).
    To match TV, we pass use_fixed_amount=True with fixed_amount = initial_capital * position_size.
    """
    # TV fixed notional: initial_capital * position_size = 10000 * 0.1 = 1000 USDT notional.
    # BacktestEngine (engine.py) computes: position_value = initial_capital * position_size (NO leverage)
    # FallbackEngineV4 with use_fixed_amount=True computes: order_size = (fixed_amount * leverage) / price
    # Therefore: fixed_amount = notional / leverage = 1000 / 10 = 100 USDT (margin per trade)
    fixed_margin = (10000.0 * 0.1) / 10  # = 100 USDT (margin; * leverage = 1000 notional)

    return BacktestInput(
        candles=ohlcv,
        long_entries=le,  # already np.bool arrays sliced to backtest window
        short_entries=se,
        long_exits=lx,
        short_exits=sx,
        initial_capital=10000.0,
        position_size=0.1,
        use_fixed_amount=True,
        fixed_amount=fixed_margin,
        leverage=10,
        stop_loss=0.132,
        take_profit=0.023,
        taker_fee=0.0007,
        slippage=0.0,
        direction=TradeDirection.BOTH,
        pyramiding=1,
        entry_on_next_bar_open=True,  # TV parity: enter at open of NEXT bar after signal
        breakeven_enabled=False,
    )


# ── Run engines & collect results ─────────────────────────────────────────────
results: dict[str, dict] = {}


def run_engine(name: str, fn):
    print(f"Running {name}...", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        output = fn()
        elapsed = time.perf_counter() - t0
        # Extract metrics
        if hasattr(output, "metrics") and output.metrics:
            m = output.metrics
            # BacktestOutput (V3/V4/Numba) has BacktestMetrics
            trades_list = output.trades or []
            net_p = getattr(m, "net_profit", None)
            total_t = getattr(m, "total_trades", len(trades_list))
            wr = getattr(m, "win_rate", None)
            pf = getattr(m, "profit_factor", None)
            sh = getattr(m, "sharpe_ratio", None)
            so = getattr(m, "sortino_ratio", None)
            lt = getattr(m, "long_trades", None)
            st_ = getattr(m, "short_trades", None)
            comm = getattr(m, "commission_paid", None) or getattr(m, "total_commission", None)
            if not comm and trades_list:
                comm = sum(getattr(t, "fees", 0) or 0 for t in trades_list) or None
        elif hasattr(output, "performance") and output.performance:  # BacktestResult
            pm = output.performance
            trades_list = output.trades or []
            net_p = getattr(pm, "net_profit", None)
            total_t = getattr(pm, "total_trades", len(trades_list))
            wr = getattr(pm, "win_rate", None)
            pf = getattr(pm, "profit_factor", None)
            sh = getattr(pm, "sharpe_ratio", None)
            so = getattr(pm, "sortino_ratio", None)
            lt = getattr(pm, "long_trades", None)
            st_ = getattr(pm, "short_trades", None)
            comm = getattr(pm, "total_commission", None) or getattr(pm, "commission_paid", None)
        else:
            print(f"ERROR: no metrics in output. Keys: {dir(output)}")
            return

        # First trade entry time (UTC+3 for display)
        from datetime import timedelta

        first_entry = None
        if trades_list:
            t0_trade = trades_list[0]
            if hasattr(t0_trade, "entry_time"):
                et = t0_trade.entry_time
                if isinstance(et, str):
                    et = datetime.fromisoformat(et)
                if et.tzinfo is None:
                    et = et.replace(tzinfo=timezone.utc)
                first_entry = (et + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
            elif isinstance(t0_trade, dict):
                et_str = t0_trade.get("entry_time", "")
                et = datetime.fromisoformat(et_str)
                if et.tzinfo is None:
                    et = et.replace(tzinfo=timezone.utc)
                first_entry = (et + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")

        # Normalize win_rate: engines return fraction (0.903) but TV shows percent (90.32)
        if wr is not None and float(wr) <= 1.0:
            wr = round(float(wr) * 100.0, 4)

        results[name] = {
            "total_trades": total_t,
            "net_profit": net_p,
            "win_rate": wr,
            "profit_factor": pf,
            "sharpe": sh,
            "sortino": so,
            "long_trades": lt,
            "short_trades": st_,
            "commission": comm,
            "first_entry": first_entry,
            "elapsed_ms": elapsed * 1000,
        }
        print(f"OK ({elapsed * 1000:.0f}ms) — trades={total_t}, net={net_p:.2f}")
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"FAILED ({elapsed * 1000:.0f}ms): {e!r}")
        results[name] = {"error": str(e)}


# 1. FallbackEngineV4
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4

run_engine("FallbackEngineV4", lambda: FallbackEngineV4().run(make_input()))

# 2. NumbaEngineV2
try:
    from backend.backtesting.engines.numba_engine_v2 import NUMBA_AVAILABLE, NumbaEngineV2

    if NUMBA_AVAILABLE:
        run_engine("NumbaEngineV2", lambda: NumbaEngineV2().run(make_input()))
    else:
        print("NumbaEngineV2: Numba not available (JIT disabled), using fallback path")
        run_engine("NumbaEngineV2(nojit)", lambda: NumbaEngineV2().run(make_input()))
except Exception as e:
    print(f"NumbaEngineV2: import failed — {e}")

# 3. FallbackEngineV3 (deprecated)
try:
    from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3

    run_engine("FallbackEngineV3", lambda: FallbackEngineV3().run(make_input()))
except Exception as e:
    print(f"FallbackEngineV3: {e}")

# 4. FallbackEngineV2 (deprecated)
try:
    from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2

    run_engine("FallbackEngineV2", lambda: FallbackEngineV2().run(make_input()))
except Exception as e:
    print(f"FallbackEngineV2: {e}")

# 5. BacktestEngine (engine.py — via standard run() path)
# BacktestEngine calls strategy.generate_signals(ohlcv) internally.
# We must pass it ohlcv (backtest window only) BUT the adapter needs the full data
# (with warmup) to produce warmed-up signals.
# Solution: pre-generate signals on ohlcv_full, then patch adapter.generate_signals
# to return the already-sliced signals for the backtest window.
from backend.backtesting.engine import BacktestEngine


class _WarmupAdapter:
    """Wraps the real adapter but returns pre-computed warmed-up signals."""

    def __init__(self, inner_adapter, pre_le, pre_se, pre_lx, pre_sx, ref_ohlcv):
        self._inner = inner_adapter
        self._le = pre_le
        self._se = pre_se
        self._lx = pre_lx
        self._sx = pre_sx
        self._ref_ohlcv = ref_ohlcv  # expected ohlcv (backtest window)

    def generate_signals(self, df):
        """Return pre-computed sliced signals; validate that df matches backtest window."""
        import pandas as pd

        from backend.backtesting.strategies import SignalResult

        n = len(df)
        assert n == len(self._le), (
            f"_WarmupAdapter: ohlcv length mismatch {n} != {len(self._le)}. "
            "BacktestEngine may have sliced ohlcv differently than expected."
        )

        # SignalResult expects Series aligned to df index
        def _to_series(arr, name):
            return pd.Series(arr, index=df.index, name=name)

        return SignalResult(
            entries=_to_series(self._le, "entries"),
            exits=_to_series(self._lx, "exits"),
            short_entries=_to_series(self._se, "short_entries"),
            short_exits=_to_series(self._sx, "short_exits"),
        )

    def __getattr__(self, name):
        return getattr(self._inner, name)


warmup_adapter = _WarmupAdapter(adapter, le, se, lx, sx, ohlcv)
run_engine("BacktestEngine(engine.py)", lambda: BacktestEngine().run(config, ohlcv, custom_strategy=warmup_adapter))

# ── Print comparison table ────────────────────────────────────────────────────
print()
print("=" * 100)
print("ENGINE CALIBRATION RESULTS vs TradingView Gold Standard")
print("=" * 100)


def match(our, tv_val, tol_pct=1.0):
    if our is None or tv_val is None:
        return "?"
    try:
        diff = abs(float(our) - float(tv_val))
        pct = diff / max(abs(float(tv_val)), 1e-9) * 100
        return "OK" if pct <= tol_pct else f"!{pct:.1f}%"
    except Exception:
        return "?"


metrics_to_check = [
    ("total_trades", "total_trades", 0.0),
    ("net_profit", "net_profit", 0.1),
    ("win_rate", "win_rate", 0.1),
    ("profit_factor", "profit_factor", 1.0),
    ("sharpe", "sharpe", 5.0),
    ("sortino", "sortino", 5.0),
    ("long_trades", "long_trades", 0.0),
    ("short_trades", "short_trades", 0.0),
    ("commission", "commission", 1.0),
]

# Header
engine_names = list(results.keys())
col_w = 22
print(f"{'Metric':<20} {'TV':>12} ", end="")
for n in engine_names:
    print(f"{n[:col_w]:>{col_w}} ", end="")
print()
print("-" * (20 + 14 + len(engine_names) * (col_w + 1)))

for metric_key, tv_key, tol in metrics_to_check:
    tv_val = TV.get(tv_key)
    print(f"{metric_key:<20} {tv_val!s:>12} ", end="")
    for n in engine_names:
        r = results.get(n, {})
        if "error" in r:
            print(f"{'ERROR':>{col_w}} ", end="")
        else:
            val = r.get(metric_key)
            flag = match(val, tv_val, tol)
            cell = f"{val!s:.8}" if val is not None else "N/A"
            cell = f"{cell}[{flag}]"
            print(f"{cell:>{col_w}} ", end="")
    print()

# First entry row
print(f"{'first_entry(UTC+3)':<20} {'2025-01-01 16:30':>12} ", end="")
for n in engine_names:
    r = results.get(n, {})
    val = r.get("first_entry", "N/A") if "error" not in r else "ERROR"
    flag = "OK" if val == "2025-01-01 16:30" else "!!"
    cell = f"{val!s}[{flag}]"
    print(f"{cell:>{col_w}} ", end="")
print()

# Speed row
print(f"{'speed_ms':<20} {'':>12} ", end="")
for n in engine_names:
    r = results.get(n, {})
    val = f"{r.get('elapsed_ms', 0):.0f}ms" if "error" not in r else "ERROR"
    print(f"{val:>{col_w}} ", end="")
print()

print("=" * 100)
print("Tolerance: trades/long/short=exact, net_profit/commission=1%, PF/sharpe/sortino=5%")
print("OK = within tolerance, !X% = X% deviation, ? = missing data")

# ── Summary: which engines pass calibration? ─────────────────────────────────
print()
print("CALIBRATION SUMMARY:")
critical = ["total_trades", "net_profit", "profit_factor", "long_trades", "short_trades"]
for n in engine_names:
    r = results.get(n, {})
    if "error" in r:
        print(f"  {n}: ❌ EXCEPTION — {r['error'][:80]}")
        continue
    failures = []
    for mkey, tvkey, tol in metrics_to_check:
        if mkey not in critical:
            continue
        tv_val = TV.get(tvkey)
        val = r.get(mkey)
        flag = match(val, tv_val, tol)
        if flag != "OK":
            failures.append(f"{mkey}={val} (TV={tv_val}, {flag})")
    if failures:
        print(f"  {n}: ❌ FAILS — {', '.join(failures)}")
    else:
        print(f"  {n}: ✅ PASSES critical metrics")
print("OK = within tolerance, !X% = X% deviation, ? = missing data")
