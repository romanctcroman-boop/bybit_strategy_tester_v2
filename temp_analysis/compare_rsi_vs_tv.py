"""
Compare Strategy_RSI_L\\S_15 backtest vs TradingView reference (a4.csv).
Uses /api/v1/strategy-builder/strategies/{id}/backtest endpoint.
"""

import csv
import json
from datetime import datetime, timedelta

import requests

STRATEGY_ID = "2e5bb802-572b-473f-9ee9-44d38bf9c531"
API_BASE = "http://localhost:8000"
TV_TRADES_CSV = r"d:\bybit_strategy_tester_v2\temp_analysis\a4.csv"

# ── TV reference data ────────────────────────────────────────────────────────
TV_RESULTS = {
    "net_profit": 1001.98,
    "total_trades": 154,
    "winning_trades": 139,
    "losing_trades": 15,
    "win_rate": 90.26,
    "profit_factor": 1.501,
    "total_commission": 215.03,
    "long_trades": 30,
    "short_trades": 124,
}

# ── Parse TV trades from CSV ─────────────────────────────────────────────────
ENTRY_TYPES = {"Вход в короткую позицию", "Вход в длинную позицию"}
EXIT_TYPES = {"Выход из короткой позиции", "Выход из длинной позиции"}
SIDE_MAP = {
    "Вход в короткую позицию": "short",
    "Вход в длинную позицию": "long",
    "Выход из короткой позиции": "short",
    "Выход из длинной позиции": "long",
}

tv_raw: dict[int, dict] = {}
with open(TV_TRADES_CSV, encoding="utf-8-sig") as f:
    reader = csv.reader(f, delimiter=";")
    next(reader)  # skip header
    for row in reader:
        if not row or not row[0].strip().isdigit():
            continue
        num = int(row[0].strip())
        rtype = row[1].strip()
        dt_str = row[2].strip()  # "YYYY-MM-DD HH:MM" — UTC+3 (Moscow)
        price = float(row[4].replace(",", ".").strip())
        pnl = float(row[7].replace(",", ".").strip())

        if num not in tv_raw:
            tv_raw[num] = {}
        if rtype in ENTRY_TYPES:
            tv_raw[num]["entry_time"] = dt_str
            tv_raw[num]["entry_price"] = price
            tv_raw[num]["side"] = SIDE_MAP[rtype]
        elif rtype in EXIT_TYPES:
            tv_raw[num]["exit_time"] = dt_str
            tv_raw[num]["exit_price"] = price
            tv_raw[num]["exit_signal"] = row[3].strip()
            tv_raw[num]["pnl"] = pnl

tv_trades = [tv_raw[k] for k in sorted(tv_raw.keys())]
print(f"TV trades loaded: {len(tv_trades)}")
print(
    f"  First: {tv_trades[0]['side']} @ {tv_trades[0]['entry_time']} -> {tv_trades[0]['exit_time']} PnL={tv_trades[0]['pnl']}"
)
print(
    f"  Last:  {tv_trades[-1]['side']} @ {tv_trades[-1]['entry_time']} -> {tv_trades[-1]['exit_time']} PnL={tv_trades[-1]['pnl']}"
)

# ── Run backtest via API ─────────────────────────────────────────────────────
print("\nRunning backtest via API...")
payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00+00:00",
    "end_date": "2026-02-27T23:30:00+00:00",
    "initial_capital": 10000,
    "commission": 0.0007,
    "slippage": 0.0,
    "position_size": 0.1,  # 10% of capital (fraction)
    "position_size_type": "percent",
    "leverage": 10,
    "pyramiding": 1,
    "direction": "both",
    "market_type": "linear",
}

url = f"{API_BASE}/api/v1/strategy-builder/strategies/{STRATEGY_ID}/backtest"
try:
    resp = requests.post(url, json=payload, timeout=180)
    resp.raise_for_status()
    result = resp.json()
except Exception as e:
    print(f"ERROR: {e}")
    if hasattr(e, "response") and e.response is not None:
        print(f"Response: {e.response.text[:500]}")
    # Try to show what body looks like
    print("\nTrying to get endpoint schema...")
    schema_resp = requests.get(f"{API_BASE}/openapi.json")
    paths = schema_resp.json().get("paths", {})
    key = "/api/v1/strategy-builder/strategies/{strategy_id}/backtest"
    if key in paths:
        print("POST schema:", json.dumps(paths[key].get("post", {}).get("requestBody", {}), indent=2)[:1000])
    raise

# ── Extract results ──────────────────────────────────────────────────────────
print("  Backtest complete!")
metrics = result.get("metrics", result.get("summary", {}))
our_trades_raw = result.get("trades", [])

print(f"\n  Total trades: {metrics.get('total_trades', len(our_trades_raw))}")
print(f"  Net profit: {metrics.get('net_profit')}")
print(f"  Win rate: {metrics.get('win_rate')}")
print(f"  Profit factor: {metrics.get('profit_factor')}")

# ── Print comparison table ───────────────────────────────────────────────────
print("\n" + "=" * 80)
print("COMPARISON: Our Backtest vs TradingView")
print("=" * 80)
print(f"{'Metric':<35} {'TV':<15} {'Ours':<15} {'Match'}")
print("-" * 80)

pairs = [
    ("Total trades", TV_RESULTS["total_trades"], metrics.get("total_trades", "?")),
    ("Net profit (USDT)", TV_RESULTS["net_profit"], metrics.get("net_profit")),
    ("Win rate (%)", TV_RESULTS["win_rate"], metrics.get("win_rate")),
    ("Profit factor", TV_RESULTS["profit_factor"], metrics.get("profit_factor")),
    ("Commission (USDT)", TV_RESULTS["total_commission"], metrics.get("total_commission")),
    ("Long trades", TV_RESULTS["long_trades"], metrics.get("long_trades")),
    ("Short trades", TV_RESULTS["short_trades"], metrics.get("short_trades")),
]
for name, tv_v, our_v in pairs:
    try:
        diff = abs(float(our_v) - float(tv_v)) / (abs(float(tv_v)) or 1) * 100
        ok = "OK" if diff < 2 else "MISMATCH"
        print(f"  {name:<33} {tv_v:<15} {(our_v or '?')!s:<15} {ok} ({diff:.1f}%)")
    except Exception:
        print(f"  {name:<33} {tv_v:<15} {our_v!s:<15}")

# ── Trade-by-trade comparison ────────────────────────────────────────────────
if our_trades_raw:
    print("\n\nTrade-by-trade comparison (first 5 mismatches):")
    our_trades = [t for t in our_trades_raw if t.get("status") != "open" and t.get("exit_reason") != "end_of_backtest"]
    print(f"  Our closed trades: {len(our_trades)},  TV trades: {len(tv_trades)}")

    mismatches = 0
    for i, (tv, our) in enumerate(zip(tv_trades[: len(our_trades)], our_trades, strict=False)):
        # TV times are UTC+3, our are UTC → add 3h
        try:
            our_entry_utc = datetime.fromisoformat(our["entry_time"])
            our_exit_utc = datetime.fromisoformat(our["exit_time"])
            our_entry_u3 = (our_entry_utc + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
            our_exit_u3 = (our_exit_utc + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")

            ok_entry = our_entry_u3 == tv["entry_time"]
            ok_exit = our_exit_u3 == tv["exit_time"]
            ok_pnl = abs(our["pnl"] - tv["pnl"]) < 0.02

            if not (ok_entry and ok_exit and ok_pnl) and mismatches < 10:
                mismatches += 1
                print(f"\n  Trade #{i + 1} MISMATCH:")
                print(f"    TV:  {tv['side']} entry={tv['entry_time']} exit={tv['exit_time']} pnl={tv['pnl']}")
                print(f"    Our: {our.get('side', '?')} entry={our_entry_u3} exit={our_exit_u3} pnl={our['pnl']:.2f}")
                if not ok_entry:
                    print("    → Entry time differs!")
                if not ok_exit:
                    print("    → Exit time differs!")
                if not ok_pnl:
                    print(f"    → PnL differs: TV={tv['pnl']} Our={our['pnl']:.2f}")
        except Exception as ex:
            print(f"  Trade #{i + 1}: error comparing - {ex}")

    if mismatches == 0:
        print(f"\n  ALL {min(len(our_trades), len(tv_trades))} trades match!")
