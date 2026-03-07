import requests

payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2026-03-06T00:00:00Z",
    "initial_capital": 10000,
    "leverage": 10,
    "position_size": 10,
    "commission": 0.0007,
}

strategy_id = "f46c7cc3-1098-483a-a177-67b7867dd72e"
r = requests.post(
    f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}/backtest",
    json=payload,
    timeout=120,
)
data = r.json()
m = data.get("metrics", {})
trades = data.get("trades", [])

SEP = "=" * 55
print(SEP)
print("BACKTEST: Strategy_DCA_RSI_02 (REAL API, REAL DATA)")
print(SEP)
print(f"Total trades:      {m.get('total_trades', len(trades))}")
print(f"Win rate:          {m.get('win_rate', 0):.2f}%")
print(f"Net profit:        ${m.get('net_profit', 0):.2f}")
print(f"Net profit %:      {m.get('net_profit_pct', 0):.2f}%")
print(f"Max drawdown:      {m.get('max_drawdown', 0):.2f}%")
print(f"Sharpe ratio:      {m.get('sharpe_ratio', 0):.3f}")
print(f"Profit factor:     {m.get('profit_factor', 0):.3f}")
print(f"Long trades:       {m.get('long_trades', 0)}")
print(f"Short trades:      {m.get('short_trades', 0)}")
print(f"Commission total:  ${m.get('total_commission', 0):.2f}")

# Check if DCA grid filled multiple orders per trade
# The engine tracks total_orders_filled internally but doesn't expose it in metrics
# We can infer from avg position size vs initial order size
avg_size = sum(t.get("size", 0) for t in trades) / max(len(trades), 1)
entry_size_expected = 10000 * (10 / 100) * 10  # capital * pos_size% * leverage / avg_price
print(f"\nAvg position size: {avg_size:.4f} coins")

# Exit reason breakdown
reasons: dict[str, int] = {}
for t in trades:
    r_key = t.get("exit_comment", "unknown") or "unknown"
    reasons[r_key] = reasons.get(r_key, 0) + 1
print("\nExit reasons:")
for k, v in sorted(reasons.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print("\nFirst 5 trades:")
print(f"  {'Entry':>22} {'Exit':>10} {'PnL%':>8} {'Bars':>5}  Reason")
print("  " + "-" * 60)
for _i, t in enumerate(trades[:5]):
    et = t.get("entry_time", "?")[:19]
    ep = t.get("entry_price", 0)
    xp = t.get("exit_price", 0)
    pct = t.get("pnl_pct", 0)
    bars = t.get("duration_bars", "?")
    reason = t.get("exit_comment", "?") or "?"
    print(f"  {et} {ep:>10.2f} {pct:>8.2f}% {bars:>5}  {reason}")
