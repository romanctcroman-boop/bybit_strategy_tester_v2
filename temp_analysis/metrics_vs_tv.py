import sqlite3

conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
    SELECT total_trades, winning_trades, losing_trades, win_rate,
           net_profit, net_profit_pct, gross_profit, gross_loss,
           total_commission, sharpe_ratio, sortino_ratio,
           profit_factor, max_drawdown, annual_return,
           long_trades, short_trades, long_pnl, short_pnl,
           long_win_rate, short_win_rate, cagr, cagr_long, cagr_short,
           expectancy, recovery_factor, max_consecutive_wins, max_consecutive_losses
    FROM backtests
    WHERE id = 'ace544ad-9cce-473a-8fe8-0662854c45a4'
""")
row = dict(cur.fetchone())

# TV значения из z1.csv и z2.csv
tv = {
    "net_profit": (1786.98, 17.87, "%"),
    "gross_profit": (2454.49, 24.54, "%"),
    "gross_loss": (667.51, 6.68, "%"),
    "total_commission": (60.70, None, ""),
    "total_trades": (43, None, ""),
    "winning_trades": (38, None, ""),
    "losing_trades": (5, None, ""),
    "win_rate": (88.37, None, "%"),
    "long_trades": (21, None, ""),
    "short_trades": (22, None, ""),
    "long_pnl": (761.94, 7.62, "%"),
    "short_pnl": (1025.04, 10.25, "%"),
    "long_win_rate": (85.71, None, "%"),
    "short_win_rate": (90.91, None, "%"),
    "profit_factor": (3.677, None, ""),
    "sharpe_ratio": (0.939, None, ""),
    "sortino_ratio": (4.23, None, ""),
    "max_drawdown": (2.83, None, "%"),  # TV: "Макс. просадка в % от начального" = 2.83%
    "annual_return": (15.03, None, "%"),  # TV: CAGR = 15.03%
    "expectancy": (41.56, None, ""),
    "recovery_factor": (6.41, None, ""),
}

print(f"{'Metric':<30} {'DB value':>15}  {'TV value':>12}  {'Diff':>12}  Status")
print("-" * 90)

for key, (tv_val, tv_pct, unit) in tv.items():
    db_raw = row.get(key)
    if db_raw is None:
        print(f"{key:<30} {'N/A':>15}  {tv_val:>12}  {'???':>12}  ❌ MISSING")
        continue

    db_val = float(db_raw)

    # Normalize: annual_return хранится как 0.15 а TV показывает 15.03%
    if key == "annual_return":
        db_val_display = db_val * 100  # convert to %
    elif key == "max_drawdown":
        db_val_display = db_val  # уже в % (3.04 vs TV 2.83)
    elif key in (
        "total_trades",
        "winning_trades",
        "losing_trades",
        "long_trades",
        "short_trades",
        "max_consecutive_wins",
        "max_consecutive_losses",
    ):
        db_val_display = int(db_val)
    else:
        db_val_display = db_val

    diff = db_val_display - tv_val
    pct_diff = abs(diff / tv_val * 100) if tv_val != 0 else 0
    ok = pct_diff < 1.0 or abs(diff) < 1.0
    status = "✅" if ok else f"❌ ({pct_diff:.1f}%)"
    print(f"{key:<30} {db_val_display:>15.4f}  {tv_val:>12}  {diff:>+12.4f}  {status}")
