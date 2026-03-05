import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from backend.core.indicators import calculate_rsi as wilder_rsi

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
ETH_CACHE = r"d:\bybit_strategy_tester_v2\data\eth_30m_cache.csv"


def load_btc():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT open_time,open_price,high_price,low_price,close_price FROM bybit_kline_audit WHERE symbol='BTCUSDT' AND interval='30' ORDER BY open_time"
    ).fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df.set_index("ts")


def load_eth():
    df = pd.read_csv(ETH_CACHE, index_col=0, parse_dates=True)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def rsi_alt(closes, alt_last, period):
    n = len(closes)
    result = np.full(n, np.nan)
    if n < period + 1:
        return result
    deltas = np.diff(closes)
    ag = float(np.mean(np.maximum(deltas[:period], 0)))
    al = float(np.mean(np.maximum(-deltas[:period], 0)))
    ag_arr = np.zeros(n)
    al_arr = np.zeros(n)
    ag_arr[period - 1] = ag
    al_arr[period - 1] = al
    for t in range(period, n):
        d = deltas[t - 1]
        ag = (ag * (period - 1) + max(d, 0)) / period
        al = (al * (period - 1) + max(-d, 0)) / period
        ag_arr[t] = ag
        al_arr[t] = al
    for t in range(period, n):
        da = alt_last[t] - closes[t - 1]
        a = (ag_arr[t - 1] * (period - 1) + max(da, 0)) / period
        b = (al_arr[t - 1] * (period - 1) + max(-da, 0)) / period
        result[t] = 100.0 if b == 0 else 100.0 - 100.0 / (1.0 + a / b)
    return result


print("Loading...")
btc = load_btc()
eth = load_eth()
print(f"BTC:{len(btc)} ETH:{len(eth)}")
P = 14
closes = btc["close"].values
lows = btc["low"].values
highs = btc["high"].values
rsi_c = pd.Series(wilder_rsi(closes, P), index=btc.index)
rsi_l = pd.Series(rsi_alt(closes, lows, P), index=btc.index)
rsi_h = pd.Series(rsi_alt(closes, highs, P), index=btc.index)
CS = 52.0
CL = 24.0
rsi_p = rsi_c.shift(1)
bc_s = (rsi_p >= CS) & (rsi_c < CS)
bc_l = (rsi_p <= CL) & (rsi_c > CL)
ib_s = (rsi_p >= CS) & (rsi_l < CS) & ~bc_s
ib_l = (rsi_p <= CL) & (rsi_h > CL) & ~bc_l
cm_s = bc_s | ib_s
cm_l = bc_l | ib_l
eth_ts = set(eth.index)
mask = pd.Series(btc.index.isin(eth_ts), index=btc.index)
print(f"\nSHORT: bc={bc_s[mask].sum()} ib={ib_s[mask].sum()} combined={cm_s[mask].sum()}")
print(f"LONG:  bc={bc_l[mask].sum()} ib={ib_l[mask].sum()} combined={cm_l[mask].sum()}")
print("\nSpot checks (anomaly bars):")
for bar_str, direction in [
    ("2025-02-12 09:30", "short"),
    ("2025-02-19 15:30", "short"),
    ("2025-03-28 17:30", "long"),
    ("2025-04-19 20:30", "short"),
    ("2025-06-14 01:00", "short"),
    ("2025-07-25 04:30", "long"),
]:
    t = pd.Timestamp(bar_str)
    tp = t - pd.Timedelta(minutes=30)
    level = CS if direction == "short" else CL
    rp = float(rsi_c.get(tp, float("nan")))
    rc = float(rsi_c.get(t, float("nan")))
    rl = float(rsi_l.get(t, float("nan")))
    rh = float(rsi_h.get(t, float("nan")))
    if direction == "short":
        std = rp >= level and rc < level
        ib = rp >= level and rl < level
        print(f"  {bar_str} S: prev={rp:.4f} close={rc:.4f} low={rl:.4f}  std={std} ib={ib}")
    else:
        std = rp <= level and rc > level
        ib = rp <= level and rh > level
        print(f"  {bar_str} L: prev={rp:.4f} close={rc:.4f} high={rh:.4f} std={std} ib={ib}")
print("\nNew intra-bar SHORT:")
for d in ib_s[ib_s & mask].index:
    print(
        f"  {d}  prev={float(rsi_p.get(d, float('nan'))):.4f}  close={float(rsi_c.get(d, float('nan'))):.4f}  low={float(rsi_l.get(d, float('nan'))):.4f}"
    )
print("\nNew intra-bar LONG:")
for d in ib_l[ib_l & mask].index:
    print(
        f"  {d}  prev={float(rsi_p.get(d, float('nan'))):.4f}  close={float(rsi_c.get(d, float('nan'))):.4f}  high={float(rsi_h.get(d, float('nan'))):.4f}"
    )
try:
    tv = pd.read_csv(r"c:\Users\roman\Downloads\z4.csv", sep=";")
    ent = tv[tv["Тип"].str.startswith("Entry")].copy()
    ent["ts_utc"] = pd.to_datetime(ent["Дата и время"]) - pd.Timedelta(hours=3)
    ent["sb"] = ent["ts_utc"] - pd.Timedelta(minutes=30)
    tv_s = set(ent[ent["Сигнал"].str.endswith("SE")]["sb"])
    tv_l = set(ent[ent["Сигнал"].str.endswith("LE")]["sb"])
    eng_s = set(cm_s[cm_s & mask].index)
    eng_l = set(cm_l[cm_l & mask].index)
    xs = sorted(eng_s - tv_s)
    ms = sorted(tv_s - eng_s)
    xl = sorted(eng_l - tv_l)
    ml = sorted(tv_l - eng_l)
    print(f"\nTV: {len(tv_s)}S+{len(tv_l)}L={len(tv_s) + len(tv_l)} | Engine: {len(eng_s)}S+{len(eng_l)}L")
    print(f"SHORT extras={len(xs)} missing={len(ms)} | LONG extras={len(xl)} missing={len(ml)}")
    ib_s_set = set(ib_s[ib_s].index)
    ib_l_set = set(ib_l[ib_l].index)

    def tag(d):
        return "[IB]" if d in ib_s_set or d in ib_l_set else "[BC]"

    print("\nExtra SHORT:")
    [
        print(
            f"  {tag(d)} {d}  prev={float(rsi_p.get(d, float('nan'))):.4f}  close={float(rsi_c.get(d, float('nan'))):.4f}  low={float(rsi_l.get(d, float('nan'))):.4f}"
        )
        for d in xs
    ]
    print("\nMissing SHORT:")
    [
        print(
            f"  {d}  prev={float(rsi_p.get(d, float('nan'))):.4f}  close={float(rsi_c.get(d, float('nan'))):.4f}  low={float(rsi_l.get(d, float('nan'))):.4f}"
        )
        for d in ms
    ]
    print("\nExtra LONG:")
    [
        print(
            f"  {tag(d)} {d}  prev={float(rsi_p.get(d, float('nan'))):.4f}  close={float(rsi_c.get(d, float('nan'))):.4f}  high={float(rsi_h.get(d, float('nan'))):.4f}"
        )
        for d in xl
    ]
    print("\nMissing LONG:")
    [
        print(
            f"  {d}  prev={float(rsi_p.get(d, float('nan'))):.4f}  close={float(rsi_c.get(d, float('nan'))):.4f}  high={float(rsi_h.get(d, float('nan'))):.4f}"
        )
        for d in ml
    ]
except FileNotFoundError:
    print("TV CSV not found")
