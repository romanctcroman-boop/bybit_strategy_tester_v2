"""
Trigger a fresh backtest for Strategy_MACD_03 via API, wait for completion,
then compare results against TradingView reference (zz1-zz4.csv).
"""

import json
import sqlite3
import time

import requests

BASE_URL = "http://localhost:8000/api/v1"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRAT_ID = "bb705ba0-7eb6-420e-a740-875d03cd7629"  # has the correct params

# ── TV reference ──────────────────────────────────────────────────────────────
TV_SUMMARY = {
    "total_trades": 42,
    "long_trades": 20,
    "short_trades": 22,
    "winning_trades": 37,
    "losing_trades": 5,
    "win_rate_pct": 88.10,
    "net_profit": 1723.14,
    "net_profit_pct": 17.23,
    "gross_profit": 2389.95,
    "gross_loss": 666.81,
    "profit_factor": 3.584,
    "sharpe_ratio": 0.934,
    "sortino_ratio": 4.19,
    "max_drawdown_pct": 2.83,
    "total_commission": 58.56,
}

TV_TRADES = [
    ("short", "2025-01-04T15:30:00", 3634.97, 64.65),
    ("short", "2025-01-15T17:00:00", 3298.01, 64.64),
    ("short", "2025-02-06T01:00:00", 2785.73, 64.63),
    ("long", "2025-02-12T17:30:00", 2569.02, 64.55),
    ("short", "2025-02-18T01:00:00", 2775.53, 64.63),
    ("short", "2025-03-02T19:30:00", 2267.09, 64.63),
    ("short", "2025-03-05T22:30:00", 2212.08, 64.64),
    ("long", "2025-03-12T17:30:00", 1876.31, 64.55),
    ("long", "2025-03-21T08:30:00", 1971.59, 64.56),
    ("short", "2025-03-26T04:00:00", 2070.90, 64.64),
    ("short", "2025-04-05T12:30:00", 1817.84, 64.65),
    ("short", "2025-04-09T17:00:00", 1486.95, -133.49),
    ("long", "2025-04-16T21:00:00", 1544.39, 64.55),
    ("long", "2025-04-25T00:30:00", 1751.79, 64.55),
    ("long", "2025-05-03T20:30:00", 1819.62, 64.55),
    ("long", "2025-05-15T05:30:00", 2589.34, 64.54),
    ("short", "2025-06-04T18:30:00", 2648.61, 64.64),
    ("long", "2025-06-13T22:00:00", 2528.50, -133.28),
    ("short", "2025-06-30T01:30:00", 2477.98, -133.48),
    ("long", "2025-07-12T15:30:00", 2948.13, 64.54),
    ("long", "2025-07-22T23:00:00", 3670.11, 64.54),
    ("long", "2025-07-30T22:00:00", 3736.95, 64.53),
    ("short", "2025-08-17T06:00:00", 4433.01, 64.62),
    ("short", "2025-08-22T17:30:00", 4577.01, 64.62),
    ("short", "2025-09-03T13:00:00", 4350.79, 64.64),
    ("long", "2025-09-23T05:30:00", 4156.40, 64.53),
    ("short", "2025-10-07T14:30:00", 4694.89, 64.62),
    ("short", "2025-10-16T13:00:00", 4028.44, 64.64),
    ("short", "2025-10-19T07:00:00", 3904.71, 64.65),
    ("long", "2025-11-05T14:00:00", 3274.55, 64.54),
    ("long", "2025-11-15T00:00:00", 3135.84, -133.27),
    ("long", "2025-11-22T02:00:00", 2719.98, 64.55),
    ("long", "2025-11-30T08:30:00", 2984.36, 64.54),
    ("short", "2025-12-04T19:30:00", 3208.39, 64.63),
    ("short", "2025-12-07T04:30:00", 3046.00, 64.63),
    ("long", "2025-12-17T19:30:00", 2846.63, 64.54),
    ("long", "2025-12-26T18:00:00", 2916.05, 64.55),
    ("short", "2026-01-05T19:00:00", 3194.54, 64.64),
    ("long", "2026-01-21T20:00:00", 2889.76, -133.29),
    ("short", "2026-02-08T23:00:00", 2125.71, 64.64),
    ("long", "2026-02-13T09:30:00", 1929.90, 64.55),
    ("short", "2026-02-16T21:30:00", 1978.31, 64.64),
]


def run_backtest():
    """POST /strategy-builder/strategies/{id}/backtest (correct endpoint)."""
    payload = {
        "symbol": "ETHUSDT",
        "interval": "30",
        "start_date": "2025-01-01T00:00:00",
        "end_date": "2026-03-01T00:00:00",
        "initial_capital": 10000.0,
        "position_size": 0.1,
        "position_size_type": "percent",
        "commission": 0.0007,
        "leverage": 10.0,
        "direction": "both",
        "market_type": "linear",
        "slippage": 0,
        "pyramiding": 1,
    }
    url = f"{BASE_URL}/strategy-builder/strategies/{STRAT_ID}/backtest"
    try:
        r = requests.post(url, json=payload, timeout=300)
        print(f"POST {url} → {r.status_code}")
        return r
    except Exception as e:
        print(f"  {url}: {e}")
    return None


def wait_for_backtest(bt_id, timeout=120):
    """Poll until backtest completes."""
    for _ in range(timeout // 3):
        time.sleep(3)
        try:
            r = requests.get(f"{BASE_URL}/backtests/{bt_id}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                status = data.get("status", "")
                print(f"  status={status}")
                if status in ("COMPLETED", "FAILED", "completed", "failed"):
                    return data
        except Exception:
            pass
    return None


# ── Step 1: Trigger backtest ──────────────────────────────────────────────────
print("=" * 60)
print("Step 1: Trigger fresh backtest (synchronous — may take 30-120s)")
print("=" * 60)
resp = run_backtest()
bt_id = None
if resp and resp.status_code in (200, 201, 202):
    data = resp.json()
    print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    # The endpoint returns the backtest record directly (synchronous)
    bt_id = data.get("id") or data.get("backtest_id")
    print(f"Backtest ID from response: {bt_id}")
    print(f"Status from response: {data.get('status')}")
elif resp:
    print(f"Error {resp.status_code}: {resp.text[:1000]}")

if not bt_id:
    print("\nNo ID returned — reading latest backtest from DB directly")

# ── Step 2: Read latest backtest from DB ──────────────────────────────────────
print("\n" + "=" * 60)
print("Step 2: Read latest backtest from DB")
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute(
    "SELECT id, status, created_at, total_trades, long_trades, short_trades, "
    "winning_trades, losing_trades, win_rate, net_profit, net_profit_pct, "
    "gross_profit, gross_loss, profit_factor, sharpe_ratio, sortino_ratio, "
    "max_drawdown, total_commission, trades "
    "FROM backtests WHERE strategy_id=? ORDER BY created_at DESC LIMIT 1",
    (STRAT_ID,),
)
bt = cur.fetchone()
conn.close()

if not bt:
    print("ERROR: No backtest found in DB")
    raise SystemExit(1)

(
    bt_id,
    bt_status,
    bt_created,
    db_total,
    db_long,
    db_short,
    db_wins,
    db_losses,
    db_wr,
    db_np,
    db_np_pct,
    db_gp,
    db_gl,
    db_pf,
    db_sharpe,
    db_sortino,
    db_dd,
    db_comm,
    db_trades_raw,
) = bt

db_trades = json.loads(db_trades_raw) if db_trades_raw else []
print(f"id={bt_id}  status={bt_status}  created={bt_created}")
print(f"trades in DB: {len(db_trades)}")

# ── Step 3: Metrics comparison ────────────────────────────────────────────────
print("\n" + "=" * 60)
print("METRICS  (DB vs TV)")
print("=" * 60)

wr = float(db_wr) if db_wr is not None else None
if wr is not None and wr <= 1.0:
    wr *= 100

metrics_ok = True


def chk(label, db_val, tv_val, tol):
    global metrics_ok
    if db_val is None:
        print(f"  ❓ {label:26s}  DB=N/A              TV={tv_val}")
        metrics_ok = False
        return
    d = abs(float(db_val) - float(tv_val))
    ok = d <= tol
    if not ok:
        metrics_ok = False
    icon = "✅" if ok else "❌"
    diff_s = f"  Δ={d:.4f}" if not ok else ""
    print(f"  {icon} {label:26s}  DB={float(db_val):<14.4f}  TV={tv_val}{diff_s}")


chk("total_trades", db_total, TV_SUMMARY["total_trades"], 0)
chk("long_trades", db_long, TV_SUMMARY["long_trades"], 0)
chk("short_trades", db_short, TV_SUMMARY["short_trades"], 0)
chk("winning_trades", db_wins, TV_SUMMARY["winning_trades"], 0)
chk("losing_trades", db_losses, TV_SUMMARY["losing_trades"], 0)
chk("win_rate %", wr, TV_SUMMARY["win_rate_pct"], 0.5)
chk("net_profit USDT", db_np, TV_SUMMARY["net_profit"], 1.0)
chk("net_profit %", db_np_pct, TV_SUMMARY["net_profit_pct"], 0.05)
chk("gross_profit", db_gp, TV_SUMMARY["gross_profit"], 1.0)
chk("gross_loss", db_gl, TV_SUMMARY["gross_loss"], 1.0)
chk("profit_factor", db_pf, TV_SUMMARY["profit_factor"], 0.01)
chk("sharpe_ratio", db_sharpe, TV_SUMMARY["sharpe_ratio"], 0.01)
chk("sortino_ratio", db_sortino, TV_SUMMARY["sortino_ratio"], 0.1)
chk("max_drawdown %", db_dd, TV_SUMMARY["max_drawdown_pct"], 0.2)
chk("commission paid", db_comm, TV_SUMMARY["total_commission"], 1.0)

# ── Step 4: Trade-level comparison ────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"TRADES:  DB={len(db_trades)}   TV={len(TV_TRADES)}")
print("=" * 60)

if len(db_trades) == len(TV_TRADES):
    mismatches = 0
    for i, (tv_t, db_t) in enumerate(zip(TV_TRADES, db_trades, strict=True)):
        tv_dir, tv_entry_dt, tv_ep, tv_pnl = tv_t
        db_dir = str(db_t.get("direction", db_t.get("side", ""))).lower()
        db_ep = float(db_t.get("entry_price", db_t.get("open_price", 0)) or 0)
        db_pnl = float(db_t.get("pnl", db_t.get("profit_loss", db_t.get("net_pnl", 0))) or 0)
        db_edt = str(db_t.get("entry_time", db_t.get("entry_date", "")))

        issues = []
        # direction: TV uses long/short, DB may use buy/sell
        tv_dir_norm = "buy" if tv_dir == "long" else "sell"
        if tv_dir not in db_dir and tv_dir_norm not in db_dir:
            issues.append(f"dir:{db_dir}≠{tv_dir}")
        # entry time: allow 30-min difference (1 bar) for timezone
        try:
            from datetime import datetime

            db_dt_obj = datetime.fromisoformat(db_edt.replace("Z", ""))
            tv_dt_obj = datetime.fromisoformat(tv_entry_dt)
            dt_diff_min = abs((db_dt_obj - tv_dt_obj).total_seconds()) / 60
            if dt_diff_min > 30:
                issues.append(f"time:{db_edt}≠{tv_entry_dt}({dt_diff_min:.0f}min)")
        except Exception:
            pass
        if abs(db_ep - tv_ep) > 1.0:
            issues.append(f"ep:{db_ep:.2f}≠{tv_ep:.2f}")
        if abs(db_pnl - tv_pnl) > 1.0:
            issues.append(f"pnl:{db_pnl:.2f}≠{tv_pnl:.2f}")

        if issues:
            mismatches += 1
            print(f"  ❌ #{i + 1:2d} {tv_dir:5s} {tv_entry_dt}  pnl={tv_pnl:+7.2f}  ISSUES: {', '.join(issues)}")
        else:
            print(f"  ✅ #{i + 1:2d} {tv_dir:5s} {tv_entry_dt}  pnl={tv_pnl:+7.2f}")
    print(f"\n  Trade mismatches: {mismatches}/{len(TV_TRADES)}")
elif db_trades:
    print("\n  COUNT MISMATCH!")
    print("  First 5 DB trades:")
    for i, t in enumerate(db_trades[:5]):
        ep = t.get("entry_price", t.get("open_price", 0))
        pnl = t.get("pnl", t.get("profit_loss", t.get("net_pnl", "?")))
        dt = t.get("entry_time", t.get("entry_date", "?"))
        dr = t.get("direction", t.get("side", "?"))
        print(f"    DB #{i + 1}: {dr:5} {dt}  ep={ep}  pnl={pnl}")
    print("  First 5 TV trades:")
    for i, t in enumerate(TV_TRADES[:5]):
        print(f"    TV #{i + 1}: {t[0]:5} {t[1]}  ep={t[2]}  pnl={t[3]:+.2f}")
else:
    print("  No trades in DB")

print("\n" + "=" * 60)
print(f"RESULT:  metrics={'✅ ALL MATCH' if metrics_ok else '❌ DIFFS'}")
print("=" * 60)
