"""
TV Calibration Check — MACD ETHUSDT 30m
Runs backtest with exact TradingView parameters and compares all metrics.
"""

import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://localhost:8000"

# ─── TradingView Reference Data (from uploaded CSVs) ──────────────────────────
TV = {
    # === Анализ сделок ===
    "total_trades": 42,
    "long_trades": 20,
    "short_trades": 22,
    "winning_trades": 37,
    "losing_trades": 5,
    "breakeven_trades": 0,
    "win_rate_pct": 88.10,
    "long_win_rate_pct": 85.00,
    "short_win_rate_pct": 90.91,
    "avg_pnl": 41.03,
    "avg_pnl_pct": 4.10,
    "long_avg_pnl": 34.87,
    "long_avg_pnl_pct": 3.49,
    "short_avg_pnl": 46.62,
    "short_avg_pnl_pct": 4.66,
    "avg_win": 64.59,
    "avg_win_pct": 6.46,
    "long_avg_win": 64.54,
    "long_avg_win_pct": 6.45,
    "short_avg_win": 64.64,
    "short_avg_win_pct": 6.46,
    "avg_loss": 133.36,
    "avg_loss_pct": 13.33,
    "long_avg_loss": 133.28,
    "long_avg_loss_pct": 13.32,
    "short_avg_loss": 133.48,
    "short_avg_loss_pct": 13.34,
    "payoff_ratio": 0.484,
    "largest_win": 64.65,
    "largest_win_pct": 6.46,
    "long_largest_win": 64.56,
    "short_largest_win": 64.65,
    "largest_loss": 133.49,
    "largest_loss_pct": 13.34,
    "long_largest_loss": 133.29,
    "short_largest_loss": 133.49,
    "avg_bars_in_trade": 276,
    "avg_bars_winning": 266,
    "avg_bars_losing": 344,
    "avg_bars_long": 276,
    "avg_bars_short": 275,
    "avg_bars_winning_long": 254,
    "avg_bars_losing_long": 402,
    "avg_bars_winning_short": 277,
    "avg_bars_losing_short": 257,
    # === Доходность с учётом риска ===
    "sharpe_ratio": 0.934,
    "sortino_ratio": 4.19,
    "profit_factor_all": 3.584,
    "profit_factor_long": 2.744,
    "profit_factor_short": 4.842,
    "margin_calls": 0,
    # === From Список сделок (cumulative last trade) ===
    "net_profit": 1723.14,
    "net_profit_pct": 17.23,
    # Gross values derived from trades list:
    # Wins: 37 × ~64.59 = 2389.83, Losses: 5 × ~133.36 = 666.8
    # Total commission: 42 trades × 2 entries × position_value × 0.07%
    # ~1000 USDT × 0.07% × 2 × 42 = 58.80 (TV shows 58.56)
}

# ─── Backtest request ─────────────────────────────────────────────────────────
payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "strategy_type": "advanced_macd",
    "strategy_params": {
        "fast_period": 14,
        "slow_period": 15,
        "signal_period": 9,
        "use_cross_zero": True,
        "opposite_cross_zero": True,
        "use_cross_signal": True,
        "opposite_cross_signal": True,
        "zero_filter": False,
        "_commission": 0.0007,
        "_leverage": 10.0,
        "_pyramiding": 1,
        "_position_size_type": "percent",
    },
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2026-03-02T22:00:00Z",
    "initial_capital": 10000.0,
    "position_size": 0.1,
    "leverage": 10.0,
    "take_profit": 0.066,
    "stop_loss": 0.132,
    "direction": "both",
}

print("=" * 70)
print("TV CALIBRATION CHECK — MACD ETHUSDT 30m")
print("=" * 70)
print(f"Sending backtest request to {BASE_URL}/api/v1/backtests/...")

try:
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/backtests/",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body[:2000]}")
    sys.exit(1)
except urllib.error.URLError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

status = data.get("status", "?")
print(f"Status: {status}")

if status != "completed":
    print(f"Backtest not completed. Full response:")
    print(json.dumps(data, indent=2)[:2000])
    sys.exit(1)

m = data.get("metrics", {})
trades = data.get("trades", [])

print(f"\nBacktest ID: {data.get('backtest_id', '?')}")
print(f"Trades received: {len(trades)}")


# ─── Helper ──────────────────────────────────────────────────────────────────
def pct_diff(our, tv):
    if tv == 0:
        return f"{'✅' if our == 0 else '❌'} (our={our:.4f})"
    diff = (our - tv) / abs(tv) * 100
    ok = "✅" if abs(diff) < 2.0 else ("⚠️ " if abs(diff) < 5.0 else "❌")
    return f"{ok} our={our:.4f} tv={tv:.4f} diff={diff:+.2f}%"


def int_diff(our, tv):
    ok = "✅" if our == tv else "❌"
    return f"{ok} our={our} tv={tv}"


def check(label, our_val, tv_val, is_int=False, tolerance_pct=2.0):
    if is_int:
        ok = "✅" if our_val == tv_val else "❌"
        return f"{ok:3s} {label:<45s} our={our_val}  tv={tv_val}"
    if tv_val == 0:
        ok = "✅" if abs(our_val) < 0.01 else "❌"
        return f"{ok:3s} {label:<45s} our={our_val:.4f}  tv=0"
    diff = abs((our_val - tv_val) / tv_val * 100)
    ok = "✅" if diff < tolerance_pct else ("⚠️ " if diff < 5.0 else "❌")
    return f"{ok:3s} {label:<45s} our={our_val:.4f}  tv={tv_val:.4f}  diff={our_val - tv_val:+.4f} ({diff:+.2f}%)"


# ─── SECTION 1: Trade counts ──────────────────────────────────────────────────
print("\n" + "─" * 70)
print("SECTION 1: TRADE COUNTS")
print("─" * 70)

our_total = int(m.get("total_trades", 0))
our_long = int(m.get("long_trades", 0))
our_short = int(m.get("short_trades", 0))
our_wins = int(m.get("winning_trades", 0))
our_losses = int(m.get("losing_trades", 0))
our_be = int(m.get("breakeven_trades", 0))

print(check("Total trades", our_total, TV["total_trades"], is_int=True))
print(check("Long trades", our_long, TV["long_trades"], is_int=True))
print(check("Short trades", our_short, TV["short_trades"], is_int=True))
print(check("Winning trades", our_wins, TV["winning_trades"], is_int=True))
print(check("Losing trades", our_losses, TV["losing_trades"], is_int=True))
print(check("Breakeven trades", our_be, TV["breakeven_trades"], is_int=True))

# ─── SECTION 2: P&L ───────────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("SECTION 2: NET P&L")
print("─" * 70)

our_net = float(m.get("net_profit", 0))
our_net_pct = float(m.get("net_profit_pct", 0) or m.get("total_return", 0))

print(check("Net profit (USDT)", our_net, TV["net_profit"]))
print(check("Net profit (%)", our_net_pct, TV["net_profit_pct"]))

# ─── SECTION 3: Win Rate ──────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("SECTION 3: WIN RATE")
print("─" * 70)

# win_rate is stored in 0-100 percent form in PerformanceMetrics
our_wr_raw = float(m.get("win_rate", 0))
our_wr = our_wr_raw if our_wr_raw > 1.0 else our_wr_raw * 100

our_long_wr = float(m.get("long_win_rate", 0))
our_short_wr = float(m.get("short_win_rate", 0))
if our_long_wr <= 1.0:
    our_long_wr *= 100
    our_short_wr *= 100

print(check("Win rate % (all)", our_wr, TV["win_rate_pct"]))
print(check("Long win rate %", our_long_wr, TV["long_win_rate_pct"]))
print(check("Short win rate %", our_short_wr, TV["short_win_rate_pct"]))

# ─── SECTION 4: Average P&L ───────────────────────────────────────────────────
print("\n" + "─" * 70)
print("SECTION 4: AVERAGE P&L PER TRADE")
print("─" * 70)

our_avg_pnl = float(m.get("avg_profit", 0) or m.get("expectancy", 0) or (our_net / our_total if our_total else 0))
# avg_win / avg_loss in API = price-change % (e.g. 6.6% for TP=6.6%)
# avg_win_value / avg_loss_value = actual USDT amount
our_avg_win = float(m.get("avg_win_value", 0) or m.get("best_trade", 0) or m.get("avg_win", 0))
our_avg_loss = float(m.get("avg_loss_value", 0) or m.get("worst_trade", 0) or m.get("avg_loss", 0))
# For overall avg_win USDT: derive from long/short components
our_long_wins = int(m.get("long_winning_trades", 0))
our_short_wins = int(m.get("short_winning_trades", 0))
our_long_avg_win = float(m.get("long_avg_win", 0))
our_short_avg_win = float(m.get("short_avg_win", 0))
our_long_avg_loss = float(m.get("long_avg_loss", 0))
our_short_avg_loss = float(m.get("short_avg_loss", 0))
# Derived overall avg_win USDT from long/short breakdown
total_wins = our_long_wins + our_short_wins
if total_wins > 0:
    our_avg_win = (our_long_avg_win * our_long_wins + our_short_avg_win * our_short_wins) / total_wins
our_long_losses = int(m.get("long_losing_trades", 0))
our_short_losses = int(m.get("short_losing_trades", 0))
total_losses = our_long_losses + our_short_losses
if total_losses > 0:
    our_avg_loss = (our_long_avg_loss * our_long_losses + our_short_avg_loss * our_short_losses) / total_losses

# avg_pnl = net / total
our_avg_pnl2 = our_net / our_total if our_total else 0

print(check("Avg P&L (USDT)", our_avg_pnl2, TV["avg_pnl"]))
print(check("Avg win (USDT)", our_avg_win, TV["avg_win"]))
print(check("Avg loss (USDT)", abs(our_avg_loss), TV["avg_loss"]))
print(check("Long avg win (USDT)", our_long_avg_win, TV["long_avg_win"]))
print(check("Short avg win (USDT)", our_short_avg_win, TV["short_avg_win"]))
print(check("Long avg loss (USDT)", abs(our_long_avg_loss), TV["long_avg_loss"]))
print(check("Short avg loss (USDT)", abs(our_short_avg_loss), TV["short_avg_loss"]))

# ─── SECTION 5: Largest trades ────────────────────────────────────────────────
print("\n" + "─" * 70)
print("SECTION 5: LARGEST TRADES")
print("─" * 70)

our_lw = float(m.get("largest_win_value", 0) or m.get("best_trade", 0))
our_ll = float(m.get("largest_loss_value", 0) or m.get("worst_trade", 0))
# Use *_value fields for USDT amounts (non-_value fields hold price-change pct)
our_llw = float(m.get("long_largest_win_value", 0))
our_slw = float(m.get("short_largest_win_value", 0))
our_lll = float(m.get("long_largest_loss_value", 0))
our_sll = float(m.get("short_largest_loss_value", 0))

print(check("Largest win (USDT)", our_lw, TV["largest_win"]))
print(check("Largest loss (USDT)", abs(our_ll), TV["largest_loss"]))
print(check("Long largest win", our_llw, TV["long_largest_win"]))
print(check("Short largest win", our_slw, TV["short_largest_win"]))
print(check("Long largest loss", abs(our_lll), TV["long_largest_loss"]))
print(check("Short largest loss", abs(our_sll), TV["short_largest_loss"]))

# ─── SECTION 6: Payoff / Profit Factor ────────────────────────────────────────
print("\n" + "─" * 70)
print("SECTION 6: PAYOFF / PROFIT FACTOR")
print("─" * 70)

our_pf = float(m.get("profit_factor", 0))
our_long_pf = float(m.get("long_profit_factor", 0))
our_short_pf = float(m.get("short_profit_factor", 0))
our_payoff = float(m.get("payoff_ratio", 0) or m.get("avg_win_loss_ratio", 0))

print(check("Profit factor (all)", our_pf, TV["profit_factor_all"]))
print(check("Profit factor (long)", our_long_pf, TV["profit_factor_long"]))
print(check("Profit factor (short)", our_short_pf, TV["profit_factor_short"]))
print(check("Payoff ratio", our_payoff, TV["payoff_ratio"]))

# ─── SECTION 7: Sharpe / Sortino ──────────────────────────────────────────────
print("\n" + "─" * 70)
print("SECTION 7: RISK-ADJUSTED METRICS")
print("─" * 70)

our_sharpe = float(m.get("sharpe_ratio", 0))
our_sortino = float(m.get("sortino_ratio", 0))

print(check("Sharpe ratio", our_sharpe, TV["sharpe_ratio"], tolerance_pct=1.0))
print(check("Sortino ratio", our_sortino, TV["sortino_ratio"], tolerance_pct=1.0))

# ─── SECTION 8: Average bars ──────────────────────────────────────────────────
print("\n" + "─" * 70)
print("SECTION 8: AVERAGE BARS IN TRADE")
print("─" * 70)

our_avg_bars = int(round(float(m.get("avg_bars_in_trade", 0))))
our_avg_bars_win = int(round(float(m.get("avg_bars_in_winning", 0))))
our_avg_bars_los = int(round(float(m.get("avg_bars_in_losing", 0))))
our_avg_bars_l = int(round(float(m.get("avg_bars_in_long", 0))))
our_avg_bars_s = int(round(float(m.get("avg_bars_in_short", 0))))
our_avg_bars_wl = int(round(float(m.get("avg_bars_in_winning_long", 0))))
our_avg_bars_ll = int(round(float(m.get("avg_bars_in_losing_long", 0))))
our_avg_bars_ws = int(round(float(m.get("avg_bars_in_winning_short", 0))))
our_avg_bars_ls = int(round(float(m.get("avg_bars_in_losing_short", 0))))

print(check("Avg bars (all)", our_avg_bars, TV["avg_bars_in_trade"], is_int=True))
print(check("Avg bars (winning)", our_avg_bars_win, TV["avg_bars_winning"], is_int=True))
print(check("Avg bars (losing)", our_avg_bars_los, TV["avg_bars_losing"], is_int=True))
print(check("Avg bars (long)", our_avg_bars_l, TV["avg_bars_long"], is_int=True))
print(check("Avg bars (short)", our_avg_bars_s, TV["avg_bars_short"], is_int=True))
print(check("Avg bars (win-long)", our_avg_bars_wl, TV["avg_bars_winning_long"], is_int=True))
print(check("Avg bars (lose-long)", our_avg_bars_ll, TV["avg_bars_losing_long"], is_int=True))
print(check("Avg bars (win-short)", our_avg_bars_ws, TV["avg_bars_winning_short"], is_int=True))
print(check("Avg bars (lose-short)", our_avg_bars_ls, TV["avg_bars_losing_short"], is_int=True))

# ─── SECTION 9: Commission ────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("SECTION 9: COMMISSION")
print("─" * 70)

our_comm = float(m.get("total_commission", 0))
our_long_comm = float(m.get("long_commission", 0))
our_short_comm = float(m.get("short_commission", 0))

# Estimate TV commission from trades: sum of per-trade commissions
tv_comm_estimate = 58.56  # from TV screenshots (from previous session)
print(check("Total commission", our_comm, tv_comm_estimate))
print(f"    Long commission  : our={our_long_comm:.2f}")
print(f"    Short commission : our={our_short_comm:.2f}")
print(f"    Long+Short sum   : {our_long_comm + our_short_comm:.2f}  (should = {our_comm:.2f})")

# ─── SECTION 10: Trade-by-trade comparison (first 5, last 5) ─────────────────
print("\n" + "─" * 70)
print("SECTION 10: FIRST 5 TRADES vs TV (net P&L only)")
print("─" * 70)

tv_trades_pnl = [64.65, 64.64, 64.63, 64.55, 64.63]
tv_trades_pnl_neg = [-133.49, -133.28, -133.48, -133.27, -133.29]

print(f"{'#':>3}  {'Type':8}  {'Our PnL':>10}  {'TV PnL':>10}  {'Diff':>8}")
if trades:
    for i, t in enumerate(trades[:5]):
        our_pnl = float(t.get("pnl", t.get("net_pnl", t.get("profit_loss", 0))))
        tv_pnl = tv_trades_pnl[i]
        diff = our_pnl - tv_pnl
        ok = "✅" if abs(diff) < 0.10 else ("⚠️ " if abs(diff) < 1.0 else "❌")
        direction = t.get("direction", "?")
        print(f"{i + 1:>3}  {direction:8}  {our_pnl:>10.2f}  {tv_pnl:>10.2f}  {diff:>+8.2f}  {ok}")

# ─── SUMMARY ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("RAW METRICS DUMP (for debugging)")
print("=" * 70)
important_keys = [
    "total_trades",
    "long_trades",
    "short_trades",
    "winning_trades",
    "losing_trades",
    "net_profit",
    "net_profit_pct",
    "total_return",
    "gross_profit",
    "gross_loss",
    "win_rate",
    "long_win_rate",
    "short_win_rate",
    "avg_win",
    "avg_loss",
    "long_avg_win",
    "short_avg_win",
    "long_avg_loss",
    "short_avg_loss",
    "largest_win",
    "largest_loss",
    "profit_factor",
    "long_profit_factor",
    "short_profit_factor",
    "payoff_ratio",
    "avg_win_loss_ratio",
    "sharpe_ratio",
    "sortino_ratio",
    "avg_bars_in_trade",
    "avg_bars_in_winning",
    "avg_bars_in_losing",
    "avg_bars_in_long",
    "avg_bars_in_short",
    "avg_bars_in_winning_long",
    "avg_bars_in_losing_long",
    "avg_bars_in_winning_short",
    "avg_bars_in_losing_short",
    "total_commission",
    "long_commission",
    "short_commission",
    "long_pnl",
    "short_pnl",
    "long_pnl_pct",
    "long_largest_win",
    "long_largest_loss",
    "short_largest_win",
    "short_largest_loss",
    "best_trade",
    "worst_trade",
    "short_pnl_pct",
    "expectancy",
]
for k in important_keys:
    v = m.get(k)
    if v is not None:
        print(f"  {k:<40s} = {v}")
