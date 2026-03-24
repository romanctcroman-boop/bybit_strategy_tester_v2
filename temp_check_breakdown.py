import requests

RSI_BID = "block_1772832197062_q10k0"
SLTP_BID = "block_1772832203873_c5bgo"

body = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2026-01-01T00:00:00Z",
    "initial_capital": 10000,
    "position_size": 0.1,
    "leverage": 10,
    "direction": "both",
    "commission": 0.0007,
    "slippage": 0.0005,
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

r = requests.post(
    "http://localhost:8000/api/v1/strategy-builder/strategies/824561e0-5e27-4be4-a33a-b064a726d14c/optimize",
    json=body,
    timeout=60,
)
data = r.json()
tops = data.get("top_results", [])
if not tops:
    print("No results! Response:", data)
    exit(1)
res = tops[0]
print(f"long_winning={res.get('long_winning_trades')}  long_losing={res.get('long_losing_trades')}")
print(f"short_winning={res.get('short_winning_trades')}  short_losing={res.get('short_losing_trades')}")
print(f"long_gross_profit={res.get('long_gross_profit')}  short_gross_profit={res.get('short_gross_profit')}")
print(f"long_profit_factor={res.get('long_profit_factor')}  short_profit_factor={res.get('short_profit_factor')}")
print(f"long_avg_win={res.get('long_avg_win')}  long_avg_loss={res.get('long_avg_loss')}")
print(f"trades={res.get('total_trades')}  net_profit={res.get('net_profit')}")
