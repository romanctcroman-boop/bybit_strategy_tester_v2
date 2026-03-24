"""
Verify optimizer vs V4 API parity for RSI-1 strategy (ETHUSDT 30m, p=11).
Both use: position_size=0.1, commission=0.0007, slippage=0.0005, leverage=10.

Ground truth: whatever V4 API returns (it uses BacktestEngine._run_fallback + bar magnifier).
Optimizer: should be close but uses NumbaEngineV2 (no bar magnifier) for speed.
"""

import requests

BASE = "http://localhost:8000"
SID = "824561e0-5e27-4be4-a33a-b064a726d14c"
RSI_BID = "block_1772832197062_q10k0"
SLTP_BID = "block_1772832203873_c5bgo"

COMMON = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2026-01-01T00:00:00Z",
    "initial_capital": 10000,
    "leverage": 10,
    "position_size": 0.1,
    "commission": 0.0007,
    "slippage": 0.0005,
    "direction": "both",
}

# ─── 1. V4 API backtest (BacktestEngine + bar magnifier) ─────────────────────
print("1. V4 API backtest (p=11, SL=3.75%, TP=4.25%)...")
bt_payload = {**COMMON, "pyramiding": 1}
r = requests.post(
    f"{BASE}/api/v1/strategy-builder/strategies/{SID}/backtest",
    json=bt_payload,
    timeout=120,
)
if r.status_code == 200:
    d = r.json()
    m = d.get("metrics", {})
    print(
        f"   trades={m.get('total_trades')}, net_profit=${m.get('net_profit', 0):.2f}, "
        f"long={m.get('long_trades')}, short={m.get('short_trades')}, win={m.get('win_rate', 0):.1%}"
    )
else:
    print(f"   FAILED: HTTP {r.status_code}: {r.text[:200]}")

# ─── 2. Optimizer — single combo p=11 ────────────────────────────────────────
print("\n2. Optimizer (p=11 only, same params)...")
opt_payload = {
    **COMMON,
    "pyramiding": 1,
    "timeout_seconds": 120,
    "parameter_ranges": [
        {"param_path": f"{RSI_BID}.period", "low": 11, "high": 11, "step": 1, "enabled": True},
        {"param_path": f"{SLTP_BID}.stop_loss_percent", "low": 3.75, "high": 3.75, "step": 0.25, "enabled": True},
        {"param_path": f"{SLTP_BID}.take_profit_percent", "low": 4.25, "high": 4.25, "step": 0.25, "enabled": True},
    ],
    "top_n": 5,
    "ranking_mode": "balanced",
}
r2 = requests.post(
    f"{BASE}/api/v1/strategy-builder/strategies/{SID}/optimize",
    json=opt_payload,
    timeout=180,
)
if r2.status_code == 200:
    d2 = r2.json()
    tops = d2.get("top_results", [])
    tested = d2.get("combinations_tested", 0)
    print(f"   tested={tested}")
    for res in tops[:3]:
        p = res.get("params", {})
        print(
            f"   trades={res.get('total_trades')}, net_profit=${res.get('net_profit', 0):.2f}, "
            f"long={res.get('long_trades')}, short={res.get('short_trades')}, win={res.get('win_rate', 0):.1%} "
            f"| p={p.get(f'{RSI_BID}.period')} sl={p.get(f'{SLTP_BID}.stop_loss_percent')} tp={p.get(f'{SLTP_BID}.take_profit_percent')}"
        )
else:
    print(f"   FAILED: HTTP {r2.status_code}: {r2.text[:200]}")

print("\nDone.")
