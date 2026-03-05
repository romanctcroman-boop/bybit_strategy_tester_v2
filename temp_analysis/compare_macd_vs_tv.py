"""
Compare Strategy_MACD_06 backtest vs TradingView reference files (a4.csv, a1.csv, a2.csv)
"""

import csv
import sys
from datetime import UTC, datetime, timedelta

import requests

STRATEGY_ID = "fb9fa6d0-b431-4730-81b7-83767d76fd61"  # Strategy_MACD_06
TV_TRADES_CSV = r"c:\Users\roman\Downloads\a4.csv"
TV_METRICS_CSV = r"c:\Users\roman\Downloads\a1.csv"
TV_STATS_CSV = r"c:\Users\roman\Downloads\a2.csv"
BASE_URL = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Load TV reference trades
# ---------------------------------------------------------------------------
def parse_tv_trades(path):
    """Parse TV trades CSV. Each trade has 2 rows: Exit first, then Entry."""
    by_num = {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            num_str = (row.get("\ufeff№ Сделки") or row.get("№ Сделки") or "").strip()
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
                (row.get("Чистая прибыль / убыток USDT", "") or "")
                .replace(" ", "")
                .replace("\u202f", "")
                .replace(",", ".")
            )
            signal = row.get("Сигнал", "")
            qty_str = (row.get("Размер позиции (кол-во)", "") or "0").replace(",", ".")

            try:
                price = float(price_str)
            except ValueError:
                price = 0.0
            try:
                qty = float(qty_str)
            except ValueError:
                qty = 0.0

            # Parse datetime — TV CSV timestamps are UTC (no timezone conversion needed)
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                dt = dt.replace(tzinfo=UTC)
            except ValueError:
                dt = None

            if num not in by_num:
                by_num[num] = {}
            rec = by_num[num]

            if "Вход" in trade_type:
                direction = "long" if "длинн" in trade_type.lower() else "short"
                rec["direction"] = direction
                rec["entry_time"] = dt
                rec["entry_price"] = price
                rec["qty"] = qty
                rec["entry_signal"] = signal
            elif "Выход" in trade_type:
                try:
                    pnl = float(pnl_str)
                except ValueError:
                    pnl = 0.0
                exit_reason = "TP" if "TP" in signal else ("SL" if "SL" in signal else "signal")
                rec["exit_time"] = dt
                rec["exit_price"] = price
                rec["pnl"] = pnl
                rec["exit_reason"] = exit_reason

    # Convert to sorted list
    trades = []
    for num in sorted(by_num.keys()):
        rec = by_num[num]
        if "entry_time" in rec and "exit_time" in rec:
            trades.append(rec)
    return trades


tv_trades = parse_tv_trades(TV_TRADES_CSV)
print(f"TV trades loaded: {len(tv_trades)}")
if tv_trades:
    t0, tN = tv_trades[0], tv_trades[-1]
    print(f"  First: {t0['direction']} @ {t0['entry_time']} -> {t0['exit_time']} PnL={t0['pnl']}")
    print(f"  Last:  {tN['direction']} @ {tN['entry_time']} -> {tN['exit_time']} PnL={tN['pnl']}")


# Load TV summary metrics
def load_tv_metrics(path):
    metrics = {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            # first column is the metric name (no header)
            cols = list(row.values())
            keys = list(row.keys())
            if keys:
                metrics[cols[0]] = cols[1] if len(cols) > 1 else ""
    return metrics


# ---------------------------------------------------------------------------
# Run backtest via API
# ---------------------------------------------------------------------------
print("\nRunning backtest via API...")
payload = {
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
}

resp = requests.post(
    f"{BASE_URL}/api/v1/strategy-builder/strategies/{STRATEGY_ID}/backtest",
    json=payload,
    timeout=120,
)
if resp.status_code != 200:
    print(f"ERROR {resp.status_code}: {resp.text[:500]}")
    sys.exit(1)

data = resp.json()
trades_raw = data.get("trades", data.get("closed_trades", []))
metrics = data.get("metrics", data.get("summary", {}))

print(f"  Total trades: {len(trades_raw)}")
print(f"  Net profit: {metrics.get('net_profit', 'N/A')}")
print(f"  Win rate: {metrics.get('win_rate', 'N/A')}")
print(f"  Profit factor: {metrics.get('profit_factor', 'N/A')}")
print(f"  Commission: {metrics.get('total_commission', metrics.get('commission_paid', 'N/A'))}")


# ---------------------------------------------------------------------------
# Parse our trades
# ---------------------------------------------------------------------------
def parse_our_trades(raw):
    trades = []
    for t in raw:
        entry_t = t.get("entry_time") or t.get("open_time") or ""
        exit_t = t.get("exit_time") or t.get("close_time") or ""
        try:
            et = datetime.fromisoformat(entry_t.replace("Z", "+00:00")) if entry_t else None
        except Exception:
            et = None
        try:
            xt = datetime.fromisoformat(exit_t.replace("Z", "+00:00")) if exit_t else None
        except Exception:
            xt = None
        # Ensure timezone-aware
        if et and et.tzinfo is None:
            et = et.replace(tzinfo=UTC)
        if xt and xt.tzinfo is None:
            xt = xt.replace(tzinfo=UTC)
        trades.append(
            {
                "direction": t.get("side", t.get("direction", "")).lower(),
                "entry_time": et,
                "exit_time": xt,
                "entry_price": float(t.get("entry_price", 0)),
                "exit_price": float(t.get("exit_price", 0)),
                "pnl": float(t.get("pnl", 0)),
                "exit_reason": t.get("exit_reason", t.get("exit_comment", "")),
                "size": float(t.get("size", 0)),
            }
        )
    return trades


our_trades = parse_our_trades(trades_raw)

# TV timestamps are UTC+3 — convert to UTC by subtracting 3 hours
# (timedelta already imported at top)
for t in tv_trades:
    if t["entry_time"]:
        t["entry_time"] = t["entry_time"] - timedelta(hours=3)
    if t["exit_time"]:
        t["exit_time"] = t["exit_time"] - timedelta(hours=3)

# ---------------------------------------------------------------------------
# Compare TV summary metrics
# ---------------------------------------------------------------------------
tv_net_profit = sum(t["pnl"] for t in tv_trades)
our_net_profit = metrics.get("net_profit", 0)

print("\n" + "=" * 80)
print("COMPARISON: Our Backtest vs TradingView")
print("=" * 80)
print(f"{'Metric':<35} {'TV':>15} {'Ours':>25} {'Match'}")
print("-" * 80)


def ok(tv, ours, tol=0.01):
    try:
        diff = abs(float(tv) - float(ours)) / (abs(float(tv)) + 1e-9)
        return "OK" if diff < tol else f"DIFF {diff * 100:.1f}%"
    except Exception:
        return "?"


rows = [
    ("Total trades", len(tv_trades), len(our_trades)),
    ("Net profit (USDT)", round(tv_net_profit, 2), round(float(our_net_profit), 2)),
    ("Win rate (%)", 88.37, round(float(metrics.get("win_rate", 0)), 2)),
    ("Profit factor", 3.681, round(float(metrics.get("profit_factor", 0)), 3)),
    ("Commission (USDT)", 60.0, round(float(metrics.get("total_commission", metrics.get("commission_paid", 0))), 2)),
    ("Long trades", 21, sum(1 for t in our_trades if "buy" in t["direction"] or "long" in t["direction"])),
    ("Short trades", 22, sum(1 for t in our_trades if "sell" in t["direction"] or "short" in t["direction"])),
]

for name, tv_v, our_v in rows:
    match = ok(tv_v, our_v)
    print(f"  {name:<33} {tv_v!s:>15} {our_v!s:>25} {match}")

# ---------------------------------------------------------------------------
# Trade-by-trade comparison
# ---------------------------------------------------------------------------
print("\n\nTrade-by-trade comparison (first 5 mismatches):")
print(f"  Our closed trades: {len(our_trades)},  TV trades: {len(tv_trades)}")

mismatches = 0
for i, (tv, ours) in enumerate(zip(tv_trades, our_trades, strict=False), 1):
    issues = []
    # Compare entry time (within 30 min tolerance for timezone edge cases)
    if tv["entry_time"] and ours["entry_time"]:
        diff_min = abs((tv["entry_time"] - ours["entry_time"]).total_seconds()) / 60
        if diff_min > 30:
            issues.append(
                f"entry time diff={diff_min:.0f}min TV={tv['entry_time'].strftime('%Y-%m-%d %H:%M')} Ours={ours['entry_time'].strftime('%Y-%m-%d %H:%M')}"
            )
    # Compare exit time
    if tv["exit_time"] and ours["exit_time"]:
        diff_min = abs((tv["exit_time"] - ours["exit_time"]).total_seconds()) / 60
        if diff_min > 30:
            issues.append(
                f"exit time diff={diff_min:.0f}min TV={tv['exit_time'].strftime('%Y-%m-%d %H:%M')} Ours={ours['exit_time'].strftime('%Y-%m-%d %H:%M')}"
            )
    # Compare PnL
    if abs(tv["pnl"] - ours["pnl"]) > 0.02:
        issues.append(f"PnL diff TV={tv['pnl']:.4f} Ours={ours['pnl']:.4f} diff={ours['pnl'] - tv['pnl']:.4f}")

    if issues:
        mismatches += 1
        if mismatches <= 5:
            dir_tv = tv["direction"]
            et = tv["entry_time"].strftime("%Y-%m-%d %H:%M") if tv["entry_time"] else "?"
            xt = tv["exit_time"].strftime("%Y-%m-%d %H:%M") if tv["exit_time"] else "?"
            print(f"\n  Trade #{i} MISMATCH ({dir_tv} {tv['exit_reason']}):")
            print(f"    TV:  entry={et} exit={xt} pnl={tv['pnl']:.2f}")
            eto = ours["entry_time"].strftime("%Y-%m-%d %H:%M") if ours["entry_time"] else "?"
            xto = ours["exit_time"].strftime("%Y-%m-%d %H:%M") if ours["exit_time"] else "?"
            print(f"    Our: entry={eto} exit={xto} pnl={ours['pnl']:.2f}")
            for iss in issues:
                print(f"    -> {iss}")

if mismatches == 0:
    print(f"\n  ALL {len(tv_trades)} trades match!")
else:
    print(f"\n  Total mismatches: {mismatches} out of {len(tv_trades)}")
