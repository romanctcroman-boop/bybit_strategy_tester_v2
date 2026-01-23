import json
import sys

import requests

BASE = "http://localhost:8000/api/v1"

try:
    r = requests.get(f"{BASE}/backtests/?limit=5", timeout=10)
    r.raise_for_status()
    data = r.json()
    # normalize list
    items = data.get("items") if isinstance(data, dict) and "items" in data else data
    if not items:
        print("No backtests returned from list endpoint")
        sys.exit(0)

    to_check = items[:3]
    for b in to_check:
        bid = b.get("id") if isinstance(b, dict) else str(b)
        print("=" * 60)
        print("Backtest ID:", bid)
        try:
            r2 = requests.get(f"{BASE}/backtests/{bid}", timeout=10)
            if r2.status_code != 200:
                print("  GET detail failed:", r2.status_code, r2.text[:200])
                continue
            o = r2.json()
            trades = o.get("trades") or []
            print("  status:", o.get("status"))
            print("  trades_len:", len(trades))
            if trades:
                print("  sample_trade_keys:", list(trades[0].keys())[:40])
            metric_keys = [
                "net_profit",
                "avg_win",
                "avg_win_value",
                "avg_loss",
                "avg_loss_value",
                "profit_factor",
                "cagr",
                "total_trades",
                "winning_trades",
                "losing_trades",
            ]
            metrics = {k: o.get(k) for k in metric_keys}
            print("  metrics:", json.dumps(metrics))
        except Exception as e:
            print("  error fetching detail:", e)

except Exception as e:
    print("ERROR listing backtests:", e)
    sys.exit(2)
