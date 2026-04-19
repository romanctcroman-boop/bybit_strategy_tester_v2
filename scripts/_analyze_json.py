import json

with open(r"c:\Users\roman\Downloads\backtest_results_2026-02-23.json") as f:
    data = json.load(f)

trades = data["trades"]
cfg = data["config"]
print("Total trades:", len(trades))
print("Strategy:", cfg["strategy_params"]["strategy_id"])
print(f"taker_fee={cfg['taker_fee']}  slippage={cfg['slippage']}  commission_value={cfg['commission_value']}")
print()

# TV-104 reference: entry times in UTC+3 (naive), need to compare
# All 104 TV entry prices (from tv_trades_104.csv context)
print(f"{'#':<4} {'side':<5} {'entry_time':<18} {'ep':>9}  {'exit_time':<18} {'xp':>10}  {'pnl':>9}  exit")
print("-" * 100)
for i, t in enumerate(trades):
    print(
        f"{i + 1:<4} {t['side']:<5} {str(t['entry_time'])[:16]:<18} {t['entry_price']:>9.1f}  "
        f"{str(t['exit_time'])[:16]:<18} {t['exit_price']:>10.4f}  {t['pnl']:>9.2f}  {t['exit_comment']}"
    )
