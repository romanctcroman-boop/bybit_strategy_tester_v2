"""
Диагностика расхождений Strategy_MACD_06 vs TradingView.
Воспроизводим сигналы и ищем источник лишней сделки #42 (Short 2026-02-16).

Запуск:  $env:PYTHONPATH="d:\bybit_strategy_tester_v2"; python temp_analysis\diag_macd06.py
"""

import json
import sqlite3
from datetime import UTC, datetime

import pandas as pd

# ── 1. Load klines from bybit_kline_audit ────────────────────────────────────
conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check columns in bybit_kline_audit
cur.execute("PRAGMA table_info(bybit_kline_audit)")
cols = [r["name"] for r in cur.fetchall()]
print("bybit_kline_audit columns:", cols)

# Count ETH 30m bars
cur.execute(
    "SELECT COUNT(*) as n, MIN(open_time) as t0, MAX(open_time) as t1 "
    "FROM bybit_kline_audit WHERE symbol='ETHUSDT' AND interval='30'"
)
row = cur.fetchone()
print(f"ETH/30m bars: {row['n']}, from {row['t0']} to {row['t1']}")

# Load all ETH 30m bars ordered by open_time
cur.execute(
    "SELECT open_time, open_price, high_price, low_price, close_price, volume "
    "FROM bybit_kline_audit WHERE symbol='ETHUSDT' AND interval='30' "
    "ORDER BY open_time ASC"
)
rows = cur.fetchall()
conn.close()

print(f"\nLoaded {len(rows)} bars")

# Build DataFrame
df = pd.DataFrame(
    [
        {
            "open_time": r["open_time"],
            "open": float(r["open_price"]),
            "high": float(r["high_price"]),
            "low": float(r["low_price"]),
            "close": float(r["close_price"]),
            "volume": float(r["volume"]) if r["volume"] else 0.0,
        }
        for r in rows
    ]
)
df.index = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df.drop(columns=["open_time"], inplace=True)
print(f"Date range: {df.index[0]} — {df.index[-1]}")

# ── 2. Generate MACD signals using StrategyBuilderAdapter ─────────────────────
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter  # noqa: E402

MACD_PARAMS_MEMORY_ON = {  # TV: disable_memory=Выкл (memory ON, 5 bars)
    "fast_period": 14,
    "slow_period": 15,
    "signal_period": 9,
    "source": "close",
    "timeframe": 30,
    "use_btc_source": False,
    "use_macd_cross_zero": True,
    "opposite_macd_cross_zero": True,
    "macd_cross_zero_level": 0,
    "use_macd_cross_signal": True,
    "signal_only_if_macd_positive": False,
    "opposite_macd_cross_signal": True,
    "disable_signal_memory": False,  # ← TV: memory ON
    "signal_memory_bars": 5,
}

MACD_PARAMS_MEMORY_OFF = {  # Our DB: disable_signal_memory=True
    **MACD_PARAMS_MEMORY_ON,
    "disable_signal_memory": True,  # ← Our current setting
}


def make_graph(params: dict) -> dict:
    return {
        "blocks": [
            {
                "id": "main_strategy",
                "type": "strategy",
                "category": "main",
                "name": "Strategy",
                "isMain": True,
                "params": {},
                "optimizationParams": {},
            },
            {
                "id": "macd_block",
                "type": "macd",
                "category": "indicator",
                "name": "MACD",
                "isMain": False,
                "params": params,
                "optimizationParams": {},
            },
            {
                "id": "sltp_block",
                "type": "static_sltp",
                "category": "exit",
                "name": "Static SL/TP",
                "isMain": False,
                "params": {
                    "take_profit_percent": 6.6,
                    "stop_loss_percent": 13.2,
                    "sl_type": "average_price",
                    "close_only_in_profit": False,
                    "activate_breakeven": False,
                },
                "optimizationParams": {},
            },
        ],
        "connections": [
            {
                "id": "c1",
                "source": {"blockId": "macd_block", "portId": "long"},
                "target": {"blockId": "main_strategy", "portId": "entry_long"},
                "type": "condition",
            },
            {
                "id": "c2",
                "source": {"blockId": "macd_block", "portId": "short"},
                "target": {"blockId": "main_strategy", "portId": "entry_short"},
                "type": "condition",
            },
            {
                "id": "c3",
                "source": {"blockId": "sltp_block", "portId": "config"},
                "target": {"blockId": "main_strategy", "portId": "sl_tp"},
                "type": "config",
            },
        ],
    }


print("\n── Generating signals (memory ON = TV behaviour) ──")
adapter_tv = StrategyBuilderAdapter(make_graph(MACD_PARAMS_MEMORY_ON))
result_tv = adapter_tv.generate_signals(df)

print("\n── Generating signals (memory OFF = our DB setting) ──")
adapter_our = StrategyBuilderAdapter(make_graph(MACD_PARAMS_MEMORY_OFF))
result_our = adapter_our.generate_signals(df)

# ── 3. Find signals around trade #41 exit (2026-02-13 UTC) and trade #42 entry ─
WINDOW_START = pd.Timestamp("2026-02-10", tz="UTC")
WINDOW_END = pd.Timestamp("2026-02-25", tz="UTC")

print(f"\n── Signal window {WINDOW_START.date()} – {WINDOW_END.date()} ──")
mask = (df.index >= WINDOW_START) & (df.index <= WINDOW_END)

entries_tv = result_tv.entries[mask]
exits_tv = result_tv.exits[mask]
short_entries_tv = (
    result_tv.short_entries[mask] if hasattr(result_tv, "short_entries") else pd.Series(False, index=df[mask].index)
)
short_exits_tv = (
    result_tv.short_exits[mask] if hasattr(result_tv, "short_exits") else pd.Series(False, index=df[mask].index)
)

entries_our = result_our.entries[mask]
exits_our = result_our.exits[mask]
short_entries_our = (
    result_our.short_entries[mask] if hasattr(result_our, "short_entries") else pd.Series(False, index=df[mask].index)
)
short_exits_our = (
    result_our.short_exits[mask] if hasattr(result_our, "short_exits") else pd.Series(False, index=df[mask].index)
)

print("\nTV (memory ON) signals in window:")
for ts in df[mask].index:
    lv = entries_tv.get(ts, False)
    sv = short_entries_tv.get(ts, False)
    if lv or sv:
        print(f"  {ts.strftime('%Y-%m-%d %H:%M')} UTC  long={lv}  short={sv}  close={df.loc[ts, 'close']:.2f}")

print("\nOUR (memory OFF) signals in window:")
for ts in df[mask].index:
    lv = entries_our.get(ts, False)
    sv = short_entries_our.get(ts, False)
    if lv or sv:
        print(f"  {ts.strftime('%Y-%m-%d %H:%M')} UTC  long={lv}  short={sv}  close={df.loc[ts, 'close']:.2f}")

# ── 4. Summary: total signal counts ──────────────────────────────────────────
print("\n── Total signal counts across full backtest period ──")
bt_mask = (df.index >= pd.Timestamp("2025-01-01", tz="UTC")) & (df.index <= pd.Timestamp("2026-03-05", tz="UTC"))


def count_signals(result, mask):  # noqa: ANN001
    long_n = int(result.entries[mask].sum()) if hasattr(result, "entries") else 0
    short_n = int(result.short_entries[mask].sum()) if hasattr(result, "short_entries") else 0
    return long_n, short_n


ln_tv, sn_tv = count_signals(result_tv, bt_mask)
ln_our, sn_our = count_signals(result_our, bt_mask)

print(f"  TV  (memory ON  5 bars): long={ln_tv}, short={sn_tv}, total={ln_tv + sn_tv}")
print(f"  OUR (memory OFF):        long={ln_our}, short={sn_our}, total={ln_our + sn_our}")
print(f"  Difference:              long={ln_tv - ln_our}, short={sn_tv - sn_our}")

# ── 5. Check the raw MACD values around 2026-02-16 ───────────────────────────
print("\n── Raw MACD values around trade #42 entry (2026-02-16 18:30 UTC) ──")
WIN2_START = pd.Timestamp("2026-02-13", tz="UTC")
WIN2_END = pd.Timestamp("2026-02-20", tz="UTC")
close = df["close"]
fast_ema = close.ewm(span=14, adjust=False).mean()
slow_ema = close.ewm(span=15, adjust=False).mean()
macd_line = fast_ema - slow_ema
signal_line = macd_line.ewm(span=9, adjust=False).mean()
macd_prev = macd_line.shift(1)
signal_prev = signal_line.shift(1)

# opposite_macd_cross_signal=True → short when MACD crosses ABOVE signal
cross_long_raw = (macd_prev >= signal_prev) & (macd_line < signal_line)  # after opposite swap
cross_short_raw = (macd_prev <= signal_prev) & (macd_line > signal_line)  # after opposite swap

win2_mask = (df.index >= WIN2_START) & (df.index <= WIN2_END)
sub = df[win2_mask].copy()
sub["macd"] = macd_line[win2_mask]
sub["signal"] = signal_line[win2_mask]
sub["cross_long"] = cross_long_raw[win2_mask]
sub["cross_short"] = cross_short_raw[win2_mask]

print(sub[["close", "macd", "signal", "cross_long", "cross_short"]].to_string())
