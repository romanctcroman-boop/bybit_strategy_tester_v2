"""
Диагностика: проверяем что _data_ended_early работает корректно
и что сервер загрузил новый код.
"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import requests

# ────────────────────────────────────────────────────────────
# 1. Проверяем что файл engine.py содержит наш патч
# ────────────────────────────────────────────────────────────
with open("d:/bybit_strategy_tester_v2/backend/backtesting/engine.py", encoding="utf-8") as f:
    engine_src = f.read()

has_patch = "_data_ended_early" in engine_src
has_open_pos = "open_position" in engine_src
has_timedelta = "from datetime import datetime, timedelta" in engine_src

print("=== engine.py patch check ===")
print(f"  _data_ended_early: {'YES' if has_patch else 'NO ← MISSING!'}")
print(f"  open_position:     {'YES' if has_open_pos else 'NO ← MISSING!'}")
print(f"  timedelta import:  {'YES' if has_timedelta else 'NO ← MISSING!'}")

# ────────────────────────────────────────────────────────────
# 2. Проверяем router.py содержит is_open
# ────────────────────────────────────────────────────────────
with open("d:/bybit_strategy_tester_v2/backend/api/routers/strategy_builder/router.py", encoding="utf-8") as f:
    router_src = f.read()

has_is_open = '"is_open": bool(getattr' in router_src or '"is_open": bool(t.get' in router_src
has_direction = '"direction": str(getattr' in router_src or '"direction": str(t.get' in router_src
has_open_trades = '"open_trades": int(getattr(_m' in router_src

print("\n=== router.py patch check ===")
print(f"  is_open field:    {'YES' if has_is_open else 'NO ← MISSING!'}")
print(f"  direction field:  {'YES' if has_direction else 'NO ← MISSING!'}")
print(f"  open_trades metric: {'YES' if has_open_trades else 'NO ← MISSING!'}")

# ────────────────────────────────────────────────────────────
# 3. Запускаем бэктест и проверяем живой ответ
# ────────────────────────────────────────────────────────────
print("\n=== Live backtest check ===")
sid = "963da4df-8e09-4c8e-a361-3143914b3581"
payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00",
    "end_date": "2026-03-05T23:59:59",
    "initial_capital": 10000,
    "leverage": 10,
    "commission": 0.0007,
    "direction": "both",
    "position_size": 0.1,
    "position_size_type": "percent",
    "stop_loss_pct": 0.132,
    "take_profit_pct": 0.066,
    "market_type": "linear",
    "pyramiding": 1,
}
try:
    r = requests.post(
        f"http://localhost:8000/api/v1/strategy-builder/strategies/{sid}/backtest", json=payload, timeout=180
    )
    print(f"  HTTP status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        bt = data.get("backtest", data)
        trades = bt.get("trades", [])
        metrics = bt.get("metrics", {})

        print(f"  Trades in response: {len(trades)}")

        if trades:
            last = trades[-1]
            print("\n  --- Last trade ---")
            for k in (
                "exit_comment",
                "is_open",
                "direction",
                "entry_time",
                "exit_time",
                "entry_price",
                "exit_price",
                "pnl",
            ):
                print(f"    {k}: {last.get(k)}")

        print("\n  --- Metrics ---")
        for k in ("total_trades", "open_trades", "net_profit", "win_rate"):
            print(f"    {k}: {metrics.get(k)}")

        # Check if last trade is truly open
        if trades:
            last = trades[-1]
            ec = last.get("exit_comment", "")
            is_open = last.get("is_open", False)
            if ec == "open_position" and is_open:
                print("\n  ✅ PATCH WORKS: last trade is open_position, is_open=True")
            elif ec == "end_of_backtest":
                print(f"\n  ❌ OLD CODE: exit_comment={ec} — server loaded OLD engine!")
            else:
                print(f"\n  ⚠️  exit_comment={ec}, is_open={is_open}")
    else:
        print(f"  Error body: {r.text[:500]}")
except Exception as e:
    print(f"  Connection error: {e}")

# ────────────────────────────────────────────────────────────
# 4. Проверяем mtime файлов
# ────────────────────────────────────────────────────────────
import os
from datetime import datetime

print("\n=== File modification times ===")
files = [
    "d:/bybit_strategy_tester_v2/backend/backtesting/engine.py",
    "d:/bybit_strategy_tester_v2/backend/api/routers/strategy_builder/router.py",
    "d:/bybit_strategy_tester_v2/backend/core/metrics_calculator.py",
]
for fpath in files:
    mtime = os.path.getmtime(fpath)
    dt = datetime.fromtimestamp(mtime)
    print(f"  {fpath.split('/')[-1]}: {dt.strftime('%H:%M:%S')}")
