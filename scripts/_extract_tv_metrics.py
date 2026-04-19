"""Extract all computable TV metrics from tv_trades_104.csv."""

import csv
import sys
from datetime import datetime, timedelta

CSV = r"d:\bybit_strategy_tester_v2\scripts\tv_trades_104.csv"
UTC3 = timedelta(hours=3)

rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
entries = [r for r in rows if "Entry" in r["Тип"]]
exits = [r for r in rows if "Exit" in r["Тип"]]

assert len(entries) == 104, len(entries)
assert len(exits) == 104, len(exits)

PNL = [float(r["Чистая прибыль / убыток USDT"]) for r in exits]
PNL_P = [float(r["Чистая прибыль / убыток %"]) for r in exits]
SIDE = ["long" if "long" in r["Тип"].lower() else "short" for r in entries]

wins = [p for p in PNL if p > 0]
losses = [p for p in PNL if p < 0]
wins_p = [p for p in PNL_P if p > 0]
loss_p = [p for p in PNL_P if p < 0]

gross_profit = sum(wins)
gross_loss = sum(losses)
net_profit = sum(PNL)
win_rate_pct = len(wins) / len(PNL) * 100
profit_factor = abs(gross_profit / gross_loss) if gross_loss else float("inf")
avg_win_usd = gross_profit / len(wins) if wins else 0
avg_loss_usd = gross_loss / len(losses) if losses else 0
avg_win_pct = sum(wins_p) / len(wins_p) if wins_p else 0
avg_loss_pct = sum(loss_p) / len(loss_p) if loss_p else 0
largest_win_usd = max(PNL)
largest_loss_usd = min(PNL)
largest_win_pct = max(PNL_P)
largest_loss_pct = min(PNL_P)
max_consec_wins = max_consec_losses = 0
cur_w = cur_l = 0
for p in PNL:
    if p > 0:
        cur_w += 1
        cur_l = 0
    else:
        cur_l += 1
        cur_w = 0
    max_consec_wins = max(max_consec_wins, cur_w)
    max_consec_losses = max(max_consec_losses, cur_l)

long_pnl = [PNL[i] for i, s in enumerate(SIDE) if s == "long"]
short_pnl = [PNL[i] for i, s in enumerate(SIDE) if s == "short"]
long_wins = [p for p in long_pnl if p > 0]
long_loss = [p for p in long_pnl if p < 0]
short_wins = [p for p in short_pnl if p > 0]
short_loss = [p for p in short_pnl if p < 0]


# Duration (bars of 30m each)
def parse_utc(r_entry, r_exit):
    en = datetime.strptime(r_entry["Дата и время"].strip(), "%Y-%m-%d %H:%M") - UTC3
    ex = datetime.strptime(r_exit["Дата и время"].strip(), "%Y-%m-%d %H:%M") - UTC3
    return int((ex - en).total_seconds() / 1800)  # 30m bars


bars = [parse_utc(entries[i], exits[i]) for i in range(104)]
win_bars = [bars[i] for i, p in enumerate(PNL) if p > 0]
loss_bars = [bars[i] for i, p in enumerate(PNL) if p < 0]

print("=" * 60)
print("TV REFERENCE METRICS  (from tv_trades_104.csv)")
print("=" * 60)
print(f"  total_trades         = {len(PNL)}")
print(f"  winning_trades       = {len(wins)}")
print(f"  losing_trades        = {len(losses)}")
print(f"  win_rate_pct         = {win_rate_pct:.4f}")
print(f"  net_profit_usd       = {net_profit:.2f}")
print(f"  gross_profit_usd     = {gross_profit:.2f}")
print(f"  gross_loss_usd       = {gross_loss:.2f}")
print(f"  profit_factor        = {profit_factor:.4f}")
print(f"  avg_win_usd          = {avg_win_usd:.4f}")
print(f"  avg_loss_usd         = {avg_loss_usd:.4f}")
print(f"  avg_win_pct          = {avg_win_pct:.4f}")
print(f"  avg_loss_pct         = {avg_loss_pct:.4f}")
print(f"  largest_win_usd      = {largest_win_usd:.2f}")
print(f"  largest_loss_usd     = {largest_loss_usd:.2f}")
print(f"  largest_win_pct      = {largest_win_pct:.4f}")
print(f"  largest_loss_pct     = {largest_loss_pct:.4f}")
print(f"  max_consec_wins      = {max_consec_wins}")
print(f"  max_consec_losses    = {max_consec_losses}")
print(f"  avg_bars_in_trade    = {sum(bars) / len(bars):.2f}")
print(f"  avg_bars_in_win      = {sum(win_bars) / len(win_bars):.2f}" if win_bars else "  avg_bars_in_win      = n/a")
print(
    f"  avg_bars_in_loss     = {sum(loss_bars) / len(loss_bars):.2f}" if loss_bars else "  avg_bars_in_loss     = n/a"
)
print(f"  long_trades          = {len(long_pnl)}")
print(f"  long_winning         = {len(long_wins)}")
print(f"  long_losing          = {len(long_loss)}")
print(f"  long_net_profit      = {sum(long_pnl):.2f}")
print(f"  long_gross_profit    = {sum(long_wins):.2f}")
print(f"  long_gross_loss      = {sum(long_loss):.2f}")
print(f"  long_win_rate_pct    = {len(long_wins) / len(long_pnl) * 100:.4f}")
print(f"  short_trades         = {len(short_pnl)}")
print(f"  short_winning        = {len(short_wins)}")
print(f"  short_losing         = {len(short_loss)}")
print(f"  short_net_profit     = {sum(short_pnl):.2f}")
print(f"  short_gross_profit   = {sum(short_wins):.2f}")
print(f"  short_gross_loss     = {sum(short_loss):.2f}")
print(f"  short_win_rate_pct   = {len(short_wins) / len(short_pnl) * 100:.4f}")
print()
print("NOTE: Sharpe/Sortino/MaxDrawdown/CAGR not in CSV - need TV screenshot")
