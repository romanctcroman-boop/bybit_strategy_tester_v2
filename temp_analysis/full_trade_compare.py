"""
Full trade-by-trade comparison: entry price, exit price, exit reason, PnL.
If entry/exit prices match but timestamps differ by exactly 3h -> timezone only.
If prices differ -> real logic difference.
"""

import csv
import sys
from datetime import UTC, datetime

import requests

STRATEGY_ID = "3fc04505-a70d-4ede-98ee-275369d1008f"
TV_CSV = r"c:\Users\roman\Downloads\a4.csv"
BASE_URL = "http://localhost:8000"
OUT_FILE = r"d:\bybit_strategy_tester_v2\temp_analysis\full_compare.txt"

out = open(OUT_FILE, "w", encoding="utf-8")  # noqa: SIM115


def p(line=""):
    print(line)
    out.write(line + "\n")
    out.flush()


# ── Load TV trades ────────────────────────────────────────────────────────────
by_num: dict[int, dict] = {}
with open(TV_CSV, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        keys = list(row.keys())
        num_str = row.get(keys[0], "").strip()
        if not num_str:
            continue
        try:
            num = int(num_str)
        except ValueError:
            continue
        trade_type = row.get("Тип", "")
        dt_str = row.get("Дата и время", "")
        price_str = (row.get("Цена USDT", "0") or "0").replace(",", ".").replace(" ", "").replace("\u202f", "")
        pnl_str = (
            (row.get("Чистая прибыль / убыток USDT", "") or "").replace(" ", "").replace("\u202f", "").replace(",", ".")
        )
        signal = row.get("Сигнал", "")
        try:
            price = float(price_str)
        except ValueError:
            price = 0.0
        try:
            pnl: float | None = float(pnl_str)
        except ValueError:
            pnl = None
        try:
            dt: datetime | None = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
        except Exception:
            dt = None
        if num not in by_num:
            by_num[num] = {}
        if "Вход" in trade_type:
            by_num[num]["direction"] = "long" if "длинн" in trade_type.lower() else "short"
            by_num[num]["entry_time"] = dt
            by_num[num]["entry_price"] = price
            by_num[num]["entry_signal"] = signal
        elif "Выход" in trade_type:
            by_num[num]["exit_time"] = dt
            by_num[num]["exit_price"] = price
            by_num[num]["pnl"] = pnl
            by_num[num]["exit_signal"] = signal

tv = [by_num[n] for n in sorted(by_num.keys()) if "entry_time" in by_num.get(n, {})]
p(f"TV trades loaded: {len(tv)}")

# ── Run our backtest ──────────────────────────────────────────────────────────
p("Running our backtest...")
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
    p(f"ERROR {resp.status_code}: {resp.text[:300]}")
    out.close()
    sys.exit(1)

data = resp.json()
ours = data.get("trades", data.get("closed_trades", []))
p(f"Our trades: {len(ours)}")

# ── Compare all trades ────────────────────────────────────────────────────────
p("")
p("=" * 110)
p(
    f"{'#':3} | {'Dir':5} | {'TV entry':16} {'ep':8} | {'Our entry':16} {'ep':8} | "
    f"{'TV exit':16} {'xp':8} | {'Our exit':16} {'xp':8} | "
    f"{'TV PnL':8} {'Our PnL':8} | {'Exit':4} | Notes"
)
p("=" * 110)

price_mismatches = 0
tz_only_diffs = 0
same = 0

for i in range(min(len(tv), len(ours))):
    t = tv[i]
    o = ours[i]

    tv_ep = t.get("entry_price", 0)
    our_ep = o.get("entry_price", 0)
    tv_xp = t.get("exit_price", 0)
    our_xp = o.get("exit_price", 0)
    tv_pnl = t.get("pnl", 0)
    our_pnl = o.get("pnl", o.get("profit", 0))
    exit_sig = t.get("exit_signal", "")
    exit_reason = "TP" if "TP" in exit_sig else ("SL" if "SL" in exit_sig else "SIG")
    our_reason = o.get("exit_reason", o.get("close_reason", "?"))

    # Format timestamps - strip TZ for display
    def fmt(ts):
        if ts is None:
            return "None            "
        s = str(ts)[:16].replace("T", " ")
        return f"{s:16}"

    tv_et_str = fmt(t.get("entry_time"))
    our_et_str = fmt(o.get("entry_time", ""))
    tv_xt_str = fmt(t.get("exit_time"))
    our_xt_str = fmt(o.get("exit_time", ""))

    # Check if it's timezone-only diff (prices match, time differs by ~3h)
    ep_match = abs(tv_ep - our_ep) < 0.01
    xp_match = abs(tv_xp - our_xp) < 0.01
    pnl_match = abs((tv_pnl or 0) - (our_pnl or 0)) < 0.5

    if ep_match and xp_match and pnl_match:
        same += 1
        note = "OK"
    elif ep_match and xp_match and not pnl_match:
        note = f"PNL_DIFF tv={tv_pnl:.2f} our={our_pnl:.2f}"
        price_mismatches += 1
    elif ep_match and not xp_match:
        note = f"EXIT_PRICE_DIFF tv={tv_xp:.2f} our={our_xp:.2f}"
        price_mismatches += 1
    elif not ep_match:
        note = f"ENTRY_PRICE_DIFF tv={tv_ep:.2f} our={our_ep:.2f}"
        price_mismatches += 1
    else:
        note = "OTHER"

    p(
        f"{i + 1:3} | {t.get('direction', '?'):5} | {tv_et_str} {tv_ep:8.2f} | {our_et_str} {our_ep:8.2f} | "
        f"{tv_xt_str} {tv_xp:8.2f} | {our_xt_str} {our_xp:8.2f} | "
        f"{(tv_pnl or 0):8.2f} {(our_pnl or 0):8.2f} | {exit_reason:4}/{our_reason:4} | {note}"
    )

p("")
p("=" * 110)
p(f"SUMMARY: {same} exact match | {price_mismatches} price/pnl differences")

out.close()
p(f"\nFull output written to {OUT_FILE}")
