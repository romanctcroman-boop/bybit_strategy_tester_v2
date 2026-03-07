"""
Compare backtest results with memory ON vs OFF for Strategy_MACD_07.
Shows which trades would be taken in each scenario.
"""

import os
import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
os.chdir(r"d:\bybit_strategy_tester_v2")

import requests

BASE = "http://localhost:8000/api/v1/strategy-builder/strategies/963da4df-8e09-4c8e-a361-3143914b3581/backtest"


def run_backtest(label, extra_override=None):
    payload = {
        "symbol": "ETHUSDT",
        "interval": "30",
        "start_date": "2025-04-01T00:00:00Z",
        "end_date": "2025-04-30T00:00:00Z",
        "initial_capital": 10000.0,
        "position_size": 0.10,
        "leverage": 10,
        "direction": "both",
        "commission": 0.0007,
        "slippage": 0.0,
        "stop_loss": 0.132,
        "take_profit": 0.066,
        "pyramiding": 1,
    }
    if extra_override:
        payload.update(extra_override)
    resp = requests.post(BASE, json=payload, timeout=120)
    if resp.status_code != 200:
        print(f"{label}: ERROR {resp.status_code} {resp.text[:200]}")
        return []
    result = resp.json()
    trades = result.get("trades", [])
    metrics = result.get("metrics", result.get("results", {}))
    net_pnl = metrics.get("net_profit", metrics.get("net_pnl", "N/A"))
    win_rate = metrics.get("win_rate", "N/A")
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"  Trades: {len(trades)}  Net PnL: {net_pnl}  Win Rate: {win_rate}")
    print(f"{'=' * 60}")
    for i, t in enumerate(trades):
        entry = t.get("entry_time", "")[:16]
        exit_ = t.get("exit_time", "")[:16]
        side = t.get("side", t.get("direction", "?"))[:4]
        ep = t.get("entry_price", 0)
        xp = t.get("exit_price", 0)
        reason = t.get("exit_comment", t.get("exit_reason", "?"))
        pnl = t.get("pnl", 0)
        print(f"  [{i + 1:2d}] {side} | {entry} @ {ep:8.2f} → {exit_} @ {xp:8.2f} | {reason:10s} | PnL: {pnl:+.2f}")
    return trades


# Current config: disable_signal_memory=true (no memory)
t1 = run_backtest("OUR CURRENT (disable_memory=True, matches DB)")

# Now check with TV params but we can't override block params via this endpoint
# Instead show the signal bars with memory
import sqlite3

import pandas as pd

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
warmup_start_ms = int(pd.Timestamp("2025-02-14", tz="UTC").timestamp() * 1000)
end_ms = int(pd.Timestamp("2025-04-30", tz="UTC").timestamp() * 1000) + 86400000

con = sqlite3.connect(DB_PATH)
df_full = pd.read_sql(
    "SELECT open_time, open_price AS open, high_price AS high, low_price AS low, "
    "close_price AS close, volume FROM bybit_kline_audit "
    "WHERE symbol='ETHUSDT' AND interval='30' AND open_time >= ? AND open_time <= ? "
    "ORDER BY open_time",
    con,
    params=(warmup_start_ms, end_ms),
)
con.close()
df_full["timestamp"] = pd.to_datetime(df_full["open_time"], unit="ms", utc=True)
df_full = df_full.set_index("timestamp").sort_index()
df_full = df_full.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
close = df_full["close"]

FAST, SLOW, SIG = 14, 15, 9
fast_ema = close.ewm(span=FAST, adjust=False).mean()
slow_ema = close.ewm(span=SLOW, adjust=False).mean()
macd_line = fast_ema - slow_ema
signal_line = macd_line.ewm(span=SIG, adjust=False).mean()

macd_prev = macd_line.shift(1)
sig_prev = signal_line.shift(1)
cross_dn_sig = (macd_prev >= sig_prev) & (macd_line < signal_line)
cross_up_sig = (macd_prev <= sig_prev) & (macd_line > signal_line)
zero_cross_dn = (macd_prev >= 0) & (macd_line < 0)
zero_cross_up = (macd_prev <= 0) & (macd_line > 0)

# After opposite swap: long=crossDN, short=crossUP
long_raw = cross_dn_sig & zero_cross_dn
short_raw = cross_up_sig & zero_cross_up

# Trim to April 2025
cutoff = pd.Timestamp("2025-04-01", tz="UTC")
mask = df_full.index >= cutoff

print("\n" + "=" * 60)
print("  SIGNAL BARS IN APRIL 2025 (MACD fast=14 slow=15 sig=9)")
print("  With opposite swap: long=crossDN, short=crossUP")
print("=" * 60)
print("\n  LONG signals (raw, no memory):")
for t in df_full.index[mask][long_raw[mask].values]:
    bar = df_full.loc[t]
    # entry fills on next bar
    idx = list(df_full.index).index(t)
    if idx + 1 < len(df_full):
        next_bar = df_full.index[idx + 1]
        entry_open = df_full.loc[next_bar, "open"]
    else:
        next_bar = None
        entry_open = None
    entry_str = f"{entry_open:.2f}" if entry_open is not None else "N/A"
    print(
        f"    Signal: {t.strftime('%Y-%m-%d %H:%M')}  close={bar['close']:.2f}  "
        f"→ Entry bar: {next_bar.strftime('%Y-%m-%d %H:%M') if next_bar else 'N/A'}  "
        f"open={entry_str}"
    )

print("\n  SHORT signals (raw, no memory):")
for t in df_full.index[mask][short_raw[mask].values]:
    bar = df_full.loc[t]
    idx = list(df_full.index).index(t)
    if idx + 1 < len(df_full):
        next_bar = df_full.index[idx + 1]
        entry_open = df_full.loc[next_bar, "open"]
    else:
        next_bar = None
        entry_open = None
    entry_str = f"{entry_open:.2f}" if entry_open is not None else "N/A"
    print(
        f"    Signal: {t.strftime('%Y-%m-%d %H:%M')}  close={bar['close']:.2f}  "
        f"→ Entry bar: {next_bar.strftime('%Y-%m-%d %H:%M') if next_bar else 'N/A'}  "
        f"open={entry_str}"
    )

print("\n  NOTE: With pyramiding=1 and trades blocking re-entries,")
print("  signal memory mainly adds entries when no position is open during memory window.")
print("  TV: disable_memory=UNCHECKED (memory ON, 5 bars)")
print("  Our DB: disable_signal_memory=true (memory OFF, signals only on fresh bar)")
