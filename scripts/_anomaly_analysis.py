"""
Deep dive into specific anomaly cases where TV fires but bar-close RSI is NOT a crossunder.
Focus on: what ETH/BTC price action happened during those bars.
"""

import sqlite3
import sys

import pandas as pd
import pandas_ta as ta

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from backend.core.indicators import calculate_rsi as wilder_rsi

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
ETH_CACHE = r"d:\bybit_strategy_tester_v2\data\eth_30m_cache.csv"


# Load BTC 30m from DB (tz-naive)
def load_btc():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT open_time, open_price, high_price, low_price, close_price FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='30' ORDER BY open_time"
    ).fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    df = df.set_index("ts")
    return df


# Load ETH 30m from cache (tz-naive)
def load_eth():
    df = pd.read_csv(ETH_CACHE, index_col=0, parse_dates=True)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


# Load BTC 5m from DB (for intra-bar analysis)
def load_btc_5m():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT open_time, open_price, high_price, low_price, close_price FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='5' ORDER BY open_time"
    ).fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    df = df.set_index("ts")
    return df


print("Loading data...")
btc = load_btc()
eth = load_eth()
btc5m = load_btc_5m()
print(f"BTC 30m: {len(btc)} bars")
print(f"ETH 30m: {len(eth)} bars")
print(f"BTC 5m:  {len(btc5m)} bars")
print()

# Compute BTC RSI on full series (DB-only, converged for Feb+ bars)
period = 14
rsi_arr = wilder_rsi(btc["close"].values, period=period)
rsi = pd.Series(rsi_arr, index=btc.index)

# Also compute BTC 5m RSI (for intra-bar simulation)
rsi_5m_arr = wilder_rsi(btc5m["close"].values, period=period)
rsi_5m = pd.Series(rsi_5m_arr, index=btc5m.index)


def get_rsi(ts):
    t = pd.Timestamp(ts)
    v = rsi.get(t)
    return float(v) if v is not None and pd.notna(v) else None


def get_rsi5m(ts):
    t = pd.Timestamp(ts)
    v = rsi_5m.get(t)
    return float(v) if v is not None and pd.notna(v) else None


cross_level = 52.0

# ── Anomaly cases ─────────────────────────────────────────────────────────────
# TV fires but bar-close RSI is NOT a crossunder
anomalies = [
    # (TV entry UTC,    signal_bar (=entry-30min),  direction)
    ("2025-02-12 10:00", "2025-02-12 09:30", "short"),  # RSI[T-1]=52.23, RSI[T]=52.02 - above 52!
    ("2025-02-19 16:00", "2025-02-19 15:30", "short"),  # RSI[T-1]=51.81 - already below 52!
    ("2025-03-28 18:00", "2025-03-28 17:30", "long"),  # Long anomaly
    ("2025-04-19 21:00", "2025-04-19 20:30", "short"),  # RSI[T-1]=51.97 - already below 52!
    ("2025-06-14 01:30", "2025-06-14 01:00", "short"),  # RSI[T]=52.0036 - borderline!
    ("2025-07-25 05:00", "2025-07-25 04:30", "long"),  # Long anomaly
]

print("=" * 80)
print("ANOMALY CASE ANALYSIS")
print("=" * 80)
print()

for tv_entry_str, sig_bar_str, direction in anomalies:
    sig_bar = pd.Timestamp(sig_bar_str)
    prev_bar = sig_bar - pd.Timedelta(minutes=30)
    prev2_bar = sig_bar - pd.Timedelta(minutes=60)
    next_bar = sig_bar + pd.Timedelta(minutes=30)

    level = cross_level if direction == "short" else 24.0

    r_t1 = get_rsi(sig_bar)
    r_t1_1 = get_rsi(prev_bar)
    r_t1_2 = get_rsi(prev2_bar)
    r_next = get_rsi(next_bar)

    print(f"TV entry: {tv_entry_str} UTC  (signal bar: {sig_bar_str})  dir={direction}  level={level}")

    # Show RSI context around signal bar
    btc_row = btc.loc[sig_bar] if sig_bar in btc.index else None
    eth_row = eth.loc[sig_bar] if sig_bar in eth.index else None

    print("  RSI context (30m):")

    def fmt(v):
        return f"{v:.4f}" if v is not None else "N/A"

    print(f"    T-2 ({prev2_bar}): RSI = {fmt(r_t1_2)}")
    print(f"    T-1 ({prev_bar}):  RSI = {fmt(r_t1_1)}")
    print(f"    T   ({sig_bar}):   RSI = {fmt(r_t1)} <-- signal bar CLOSE")
    print(f"    T+1 ({next_bar}):  RSI = {fmt(r_next)}")

    if btc_row is not None:
        print(
            f"  BTC 30m bar T: open={btc_row.open:.2f}, high={btc_row.high:.2f}, low={btc_row.low:.2f}, close={btc_row.close:.2f}"
        )
    if eth_row is not None:
        print(
            f"  ETH 30m bar T: open={eth_row.open:.2f}, high={eth_row.high:.2f}, low={eth_row.low:.2f}, close={eth_row.close:.2f}"
        )

    # Show BTC 5m bars during the 30m signal bar
    # Signal bar opens at sig_bar, covers 6 × 5m bars
    print("  BTC 5m bars within signal bar (intra-bar RSI):")
    for offset in range(6):
        t5 = sig_bar + pd.Timedelta(minutes=5 * offset)
        r5 = get_rsi5m(t5)
        b5 = btc5m.loc[t5] if t5 in btc5m.index else None
        if b5 is not None:
            below = " <<< BELOW LEVEL" if r5 is not None and r5 < level else ""
            print(f"    {t5}  BTC={b5.close:.2f}  RSI(5m)={fmt(r5)}{below}")
        else:
            print(f"    {t5}  NO DATA")

    # Cross check: what is RSI at the 5m bar JUST BEFORE signal bar?
    for offset in range(-2, 0):
        t5 = sig_bar + pd.Timedelta(minutes=5 * offset)
        r5 = get_rsi5m(t5)
        b5 = btc5m.loc[t5] if t5 in btc5m.index else None
        if b5 is not None:
            print(f"    {t5}  BTC={b5.close:.2f}  RSI(5m)={fmt(r5)}  [PRE-BAR]")

    print()
