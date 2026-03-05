#!/usr/bin/env python3
"""
Diagnose why entry/exit bar timestamps differ between our backtest and TradingView.

The screenshots show:
- TV image 1: signal at ~02:00 (UTC+3 = 23:00 UTC Mar 3), entry at next bar open
- Our image 2: buy 1967.37 at ~20:00 (UTC+3 = 17:00 UTC Mar 3)

Load TV CSV and our API to compare exact timestamps for first 5 trades.
"""

import csv
import sys
from datetime import UTC, datetime

import requests

OUT = open(r"d:\bybit_strategy_tester_v2\temp_analysis\cmp_result.txt", "w", encoding="utf-8")  # noqa: SIM115


def p(*args, **kwargs):
    line = " ".join(str(a) for a in args)
    print(line)
    OUT.write(line + "\n")
    OUT.flush()


STRATEGY_ID = "3fc04505-a70d-4ede-98ee-275369d1008f"
TV_CSV = r"c:\Users\roman\Downloads\a4.csv"
BASE_URL = "http://localhost:8000"

# Load TV trades
by_num: dict[int, dict] = {}
with open(TV_CSV, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        keys = list(row.keys())
        num_key = keys[0]
        num_str = row.get(num_key, "").strip()
        if not num_str:
            continue
        try:
            num = int(num_str)
        except ValueError:
            continue
        trade_type = row.get("Тип", "")
        dt_str = row.get("Дата и время", "")
        price_str = (row.get("Цена USDT", "0") or "0").replace(",", ".").replace(" ", "").replace("\u202f", "")
        signal = row.get("Сигнал", "")
        try:
            price = float(price_str)
        except ValueError:
            price = 0.0
        try:
            dt: datetime | None = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
        except Exception:
            dt = None
        if num not in by_num:
            by_num[num] = {}
        if "Вход" in trade_type:
            by_num[num]["entry_time"] = dt
            by_num[num]["entry_price"] = price
            by_num[num]["signal"] = signal
            by_num[num]["direction"] = "long" if "длинн" in trade_type.lower() else "short"
        elif "Выход" in trade_type:
            by_num[num]["exit_time"] = dt
            by_num[num]["exit_price"] = price
            by_num[num]["exit_signal"] = signal

tv_trades = [by_num[n] for n in sorted(by_num.keys()) if "entry_time" in by_num[n]]
p(f"TV trades: {len(tv_trades)}")
p("\nFirst 5 TV trades (UTC):")
for t in tv_trades[:5]:
    p(
        f"  {t['direction']:5s} | entry={t['entry_time']} @ {t['entry_price']:.2f} "
        f"| exit={t.get('exit_time')} @ {t.get('exit_price', 0):.2f} "
        f"| sig={t.get('signal', '')}"
    )

# Run our backtest
p("\nRunning our backtest...")
resp = requests.post(
    f"{BASE_URL}/api/v1/strategy-builder/strategies/{STRATEGY_ID}/backtest",
    json={
        "symbol": "ETHUSDT",
        "interval": "30",
        "start_date": "2025-01-01T00:00:00+00:00",
        "end_date": "2026-03-04T21:30:00+00:00",
        "initial_capital": 10000,
        "commission": 0.0007,
        "slippage": 0.0,
        "position_size": 0.1,
        "position_size_type": "percent",
        "leverage": 10,
        "pyramiding": 1,
        "direction": "both",
        "market_type": "linear",
        "take_profit": 0.066,
        "stop_loss": 0.132,
        "sl_type": "average_price",
    },
    timeout=120,
)
if resp.status_code != 200:
    p(f"ERROR {resp.status_code}: {resp.text[:500]}")
    sys.exit(1)
data = resp.json()
our_trades = data.get("trades", data.get("closed_trades", []))
p(f"Our trades: {len(our_trades)}")
p("\nFirst 5 our trades (UTC):")
for t in our_trades[:5]:
    et = t.get("entry_time", "")
    xt = t.get("exit_time", "")
    ep = t.get("entry_price", 0)
    xp = t.get("exit_price", 0)
    dr = t.get("direction", t.get("side", "?"))
    p(f"  {dr:5s} | entry={et} @ {ep:.2f} | exit={xt} @ {xp:.2f}")

# Compare bar-by-bar
p("\n\nSide-by-side comparison (first 5 trades):")
p(f"{'#':3s} | {'TV entry (UTC)':22s} {'TV price':8s} | {'Our entry (UTC)':22s} {'Our price':8s} | {'Match?':6s}")
p("-" * 95)
for i in range(min(5, len(tv_trades), len(our_trades))):
    tv = tv_trades[i]
    our = our_trades[i]
    et_str = str(tv["entry_time"])[:19] if tv["entry_time"] else "None"
    our_et_str = str(our.get("entry_time", ""))[:19]
    ep = tv["entry_price"]
    oep = our.get("entry_price", 0)
    match = "OK" if et_str == our_et_str else "DIFF"
    p(f"{i + 1:3d} | {et_str:22s} {ep:8.2f} | {our_et_str:22s} {oep:8.2f} | {match}")

    # If timestamps differ, show offset
    if et_str != our_et_str and tv["entry_time"]:
        try:
            our_dt = datetime.fromisoformat(our.get("entry_time", "").replace("Z", "+00:00"))
            diff = our_dt.replace(tzinfo=None) - tv["entry_time"].replace(tzinfo=None)
            p(f"     Offset: {diff}")
        except Exception:
            pass

OUT.flush()
OUT.close()
p("Done - output written to cmp_result.txt")
