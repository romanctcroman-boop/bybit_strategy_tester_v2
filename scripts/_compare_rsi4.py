import json
import sqlite3

STRATEGY_ID = "8597c9e0-c147-4d9a-8025-92994b4cdf1b"
BT_ID = "aa920b43-e2bf-49f8-b0ae-9d8cb11a681e"

TV_SUMMARY = {
    "net_profit": 440.91,
    "gross_profit": 1289.36,
    "gross_loss": 848.46,
    "commission_paid": 170.04,
    "total_trades": 121,
    "winning_trades": 94,
    "losing_trades": 27,
    "win_rate": 77.69,
    "profit_factor": 1.52,
    "sharpe_ratio": -23.37,
    "sortino_ratio": -0.999,
    "long_trades": 59,
    "short_trades": 62,
    "long_net_profit": 182.45,
    "short_net_profit": 258.46,
    "avg_trade": 3.64,
    "avg_win": 13.72,
    "avg_loss": 31.42,
    "best_trade": 24.5,
    "worst_trade": -31.42,
    "max_drawdown_close_value": 80.61,
    "max_drawdown_intrabar_value": 105.36,
    "avg_bars_in_trade": 72,
}

TV_TRADES = [
    (1, "short", "2025-11-01 14:30", 110003.6, "2025-11-03 06:00", 108353.5, 13.61, "TP Hit"),
    (2, "long", "2025-11-03 08:15", 107903.8, "2025-11-04 08:45", 104666.6, -31.38, "SL Hit"),
    (3, "long", "2025-11-04 09:15", 104835.7, "2025-11-04 20:00", 101690.6, -31.38, "SL Hit"),
    (4, "long", "2025-11-04 21:45", 101212.5, "2025-11-05 15:15", 102730.7, 13.59, "TP Hit"),
    (5, "short", "2025-11-06 00:00", 103789.8, "2025-11-06 17:30", 102232.9, 13.61, "TP Hit"),
    (6, "long", "2025-11-06 20:00", 100806.7, "2025-11-07 06:00", 102318.9, 13.59, "TP Hit"),
    (7, "short", "2025-11-07 07:45", 101766.1, "2025-11-07 14:00", 100239.6, 13.61, "TP Hit"),
    (8, "long", "2025-11-07 14:45", 100110.0, "2025-11-07 19:15", 101611.7, 13.59, "TP Hit"),
    (9, "short", "2025-11-08 05:45", 103087.8, "2025-11-08 17:00", 101541.4, 13.61, "TP Hit"),
    (10, "short", "2025-11-09 00:15", 101983.3, "2025-11-09 23:00", 105042.8, -31.42, "SL Hit"),
    (11, "short", "2025-11-10 13:30", 106119.0, "2025-11-11 15:45", 104527.2, 13.61, "TP Hit"),
    (12, "long", "2025-11-11 19:15", 103486.0, "2025-11-12 12:15", 105038.3, 13.59, "TP Hit"),
    (13, "short", "2025-11-12 17:45", 104667.2, "2025-11-12 18:30", 103097.1, 13.61, "TP Hit"),
    (14, "long", "2025-11-12 22:45", 101351.2, "2025-11-13 08:45", 102871.5, 13.59, "TP Hit"),
    (15, "long", "2025-11-14 00:15", 98578.3, "2025-11-14 02:00", 100057.0, 13.59, "TP Hit"),
    (16, "short", "2025-11-14 06:00", 99573.6, "2025-11-14 07:30", 98079.9, 13.61, "TP Hit"),
    (17, "long", "2025-11-14 08:00", 97769.2, "2025-11-14 15:30", 94836.1, -31.38, "SL Hit"),
    (18, "long", "2025-11-14 16:00", 95326.8, "2025-11-14 17:45", 96756.8, 13.59, "TP Hit"),
    (19, "short", "2025-11-14 19:15", 96466.9, "2025-11-14 21:45", 95019.8, 13.61, "TP Hit"),
    (20, "short", "2025-11-15 09:45", 96063.2, "2025-11-16 18:45", 94622.2, 13.61, "TP Hit"),
    (21, "long", "2025-11-16 21:00", 94317.8, "2025-11-17 10:30", 95732.6, 13.59, "TP Hit"),
    (22, "short", "2025-11-17 15:00", 95530.9, "2025-11-17 16:30", 94097.9, 13.61, "TP Hit"),
    (23, "long", "2025-11-17 17:15", 94028.8, "2025-11-17 17:30", 95439.3, 13.59, "TP Hit"),
    (24, "long", "2025-11-17 23:30", 91735.2, "2025-11-18 19:00", 93111.3, 13.59, "TP Hit"),
    (25, "long", "2025-11-19 09:30", 90767.0, "2025-11-19 18:00", 92128.6, 13.59, "TP Hit"),
    (26, "long", "2025-11-20 21:15", 87656.8, "2025-11-21 10:30", 85027.0, -31.38, "SL Hit"),
    (27, "long", "2025-11-21 11:15", 84450.6, "2025-11-21 13:00", 81917.0, -31.38, "SL Hit"),
    (28, "long", "2025-11-21 14:00", 82671.2, "2025-11-21 16:15", 83911.3, 13.59, "TP Hit"),
    (29, "short", "2025-11-21 17:15", 83778.9, "2025-11-21 19:00", 82522.2, 13.61, "TP Hit"),
    (30, "short", "2025-11-21 22:45", 84409.8, "2025-11-23 17:00", 86942.1, -31.42, "SL Hit"),
    (31, "short", "2025-11-23 20:00", 86642.9, "2025-11-24 17:45", 85343.2, 13.61, "TP Hit"),
    (32, "short", "2025-11-25 02:45", 88369.8, "2025-11-25 11:45", 87044.2, 13.61, "TP Hit"),
    (33, "long", "2025-11-25 12:45", 87032.4, "2025-11-26 20:15", 88337.9, 13.59, "TP Hit"),
    (34, "short", "2025-11-27 08:45", 90919.8, "2025-12-01 03:00", 89556.0, 13.61, "TP Hit"),
    (35, "long", "2025-12-01 09:00", 85964.2, "2025-12-02 04:00", 87253.7, 13.59, "TP Hit"),
    (36, "short", "2025-12-02 06:30", 86306.8, "2025-12-02 17:45", 88896.1, -31.42, "SL Hit"),
    (37, "short", "2025-12-03 03:00", 91241.7, "2025-12-04 01:45", 93979.0, -31.42, "SL Hit"),
    (38, "short", "2025-12-04 04:30", 93336.1, "2025-12-04 17:45", 91936.0, 13.61, "TP Hit"),
    (39, "long", "2025-12-04 18:15", 92602.0, "2025-12-05 19:00", 89823.9, -31.38, "SL Hit"),
    (40, "long", "2025-12-05 20:00", 88760.0, "2025-12-06 17:15", 90091.4, 13.59, "TP Hit"),
]

conn = sqlite3.connect("data.sqlite3")
cur = conn.cursor()
cur.execute(
    "SELECT parameters, trades, metrics_json, initial_capital, symbol, timeframe, "
    "start_date, end_date, net_profit, gross_profit, gross_loss, total_trades, "
    "winning_trades, losing_trades, win_rate, profit_factor, sharpe_ratio, "
    "sortino_ratio, total_commission, long_trades, short_trades, long_pnl, short_pnl "
    "FROM backtests WHERE id=?",
    (BT_ID,),
)
bt = cur.fetchone()
conn.close()

(
    params_json,
    trades_json,
    metrics_json,
    ic,
    symbol,
    tf,
    start_dt,
    end_dt,
    net_profit,
    gross_profit,
    gross_loss,
    total_trades,
    winning_trades,
    losing_trades,
    win_rate,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
    commission,
    long_trades,
    short_trades,
    long_pnl,
    short_pnl,
) = bt

params = json.loads(params_json) if params_json else {}
our_trades = json.loads(trades_json) if trades_json else []
metrics = json.loads(metrics_json) if metrics_json else {}

print("=" * 80)
print(f"Strategy : {STRATEGY_ID}")
print(f"Backtest : {BT_ID}")
print(f"Period   : {start_dt} -> {end_dt}")
print(f"Symbol   : {symbol}  TF={tf}  IC={ic:,.0f}")
print("=" * 80)

# ── Section 1: Config ────────────────────────────────────────────────────────
print("\n-- CONFIG -----------------------------------------------------------")
tv_cfg = {
    "initial_capital": 1_000_000,
    "commission_value": 0.07,
    "position_size": 0.10,
    "leverage": 10.0,
    "direction": "both",
    "stop_loss": 3.0,
    "take_profit": 1.5,
}
our_cfg_map = {
    "initial_capital": ic,
    "commission_value": params.get("commission_value", params.get("commission")),
    "position_size": params.get("position_size"),
    "leverage": params.get("leverage"),
    "direction": params.get("direction"),
    "stop_loss": params.get("stop_loss", params.get("sl", params.get("stop_loss_pct"))),
    "take_profit": params.get("take_profit", params.get("tp", params.get("take_profit_pct"))),
}
for k, tv_v in tv_cfg.items():
    our_v = our_cfg_map.get(k, "MISSING")
    try:
        ok = abs(float(str(our_v)) - float(str(tv_v))) < 0.001
    except (ValueError, TypeError):
        ok = str(our_v) == str(tv_v)
    print(f"  {'OK' if ok else 'DIFF':<5} {k:<22}: TV={tv_v!s:<12} OUR={our_v}")


def cmp_m(label, tv_val, our_val, tol=0.5):
    if our_val is None:
        tag = "MISS "
    else:
        diff = abs(float(our_val) - float(tv_val))
        pct = diff / abs(float(tv_val)) * 100 if tv_val != 0 else diff
        tag = f"OK    (d={diff:.3f})" if pct <= tol else f"DIFF  diff={diff:.3f} ({pct:.2f}%)"
    print(f"  {tag:<22} {label:<38}: TV={tv_val!s:<15} OUR={our_val!s}")


# ── Section 2: Summary metrics ───────────────────────────────────────────────
print("\n-- SUMMARY METRICS --------------------------------------------------")

our_m = {
    "net_profit": net_profit,
    "gross_profit": gross_profit,
    "gross_loss": gross_loss,
    "commission_paid": commission,
    "total_trades": total_trades,
    "winning_trades": winning_trades,
    "losing_trades": losing_trades,
    "win_rate": win_rate,
    "profit_factor": profit_factor,
    "sharpe_ratio": sharpe_ratio,
    "sortino_ratio": sortino_ratio,
    "long_trades": long_trades,
    "short_trades": short_trades,
    "long_net_profit": long_pnl,
    "short_net_profit": short_pnl,
    "avg_trade": metrics.get("avg_trade") or metrics.get("expectancy"),
    "avg_win": metrics.get("avg_win"),
    "avg_loss": metrics.get("avg_loss"),
    "best_trade": metrics.get("best_trade"),
    "worst_trade": metrics.get("worst_trade"),
    "max_drawdown_close_value": metrics.get("max_drawdown_value"),
    "max_drawdown_intrabar_value": metrics.get("max_drawdown_intrabar_value"),
    "avg_bars_in_trade": metrics.get("avg_bars_in_trade"),
}

for k, tv_v in TV_SUMMARY.items():
    cmp_m(k, tv_v, our_m.get(k))

# ── Section 3: Trade-by-trade ────────────────────────────────────────────────
print("\n-- TRADE-BY-TRADE (first 40 TV trades) ------------------------------")
print(f"  TV={len(TV_TRADES)} | Our={len(our_trades)} total")


def gf(t, *keys):
    for k in keys:
        if k in t:
            return t[k]
    return None


our_by_entry = {}
for t in our_trades:
    et = str(gf(t, "entry_time", "entry_dt") or "")[:16]
    d = str(gf(t, "direction", "side") or "").lower()
    our_by_entry[(et, d)] = t

mismatches = 0
for num, direction, entry_time, entry_price, exit_time, exit_price, tv_pnl, reason in TV_TRADES:
    key = (entry_time[:16], direction)
    our = our_by_entry.get(key)
    if our is None:
        print(f"  MISS #{num:>3} {direction:<6} {entry_time} entry_price={entry_price}")
        mismatches += 1
        continue

    our_ep = float(gf(our, "entry_price", "entry") or 0)
    our_xp = float(gf(our, "exit_price", "exit") or 0)
    our_pnl = float(gf(our, "pnl", "net_pnl", "profit") or 0)
    our_xt = str(gf(our, "exit_time", "exit_dt") or "")[:16]
    our_rsn = str(gf(our, "exit_reason", "reason") or "")

    ep_d = abs(our_ep - entry_price)
    xp_d = abs(our_xp - exit_price)
    pnl_d = abs(our_pnl - tv_pnl)
    xt_ok = our_xt[:16] == exit_time[:16]
    rsn_ok = (reason.lower() in our_rsn.lower()) or (our_rsn.lower() in reason.lower())

    ok = ep_d < 0.5 and xp_d < 0.5 and pnl_d < 0.05 and xt_ok and rsn_ok
    tag = "OK" if ok else "DIFF"
    if not ok:
        mismatches += 1
        details = f"  EP_d={ep_d:.1f} XP_d={xp_d:.1f} PnL_d={pnl_d:.4f} xt={'OK' if xt_ok else our_xt + ' vs ' + exit_time[:16]} rsn={'OK' if rsn_ok else repr(our_rsn)}"
    else:
        details = ""
    print(
        f"  {tag:<5} #{num:>3} {direction:<6} {entry_time} EP={entry_price:>9.1f} "
        f"tv_pnl={tv_pnl:>7.2f} our_pnl={our_pnl:>7.2f}{details}"
    )

print(f"\n  Trade result: {'ALL MATCH' if mismatches == 0 else str(mismatches) + ' MISMATCHES'}")

# ── Section 4: Our full trade list ───────────────────────────────────────────
print("\n-- OUR FULL TRADE LIST ----------------------------------------------")
for i, t in enumerate(our_trades):
    num = gf(t, "trade_num") or i + 1
    d = str(gf(t, "direction", "side") or "?")[:5]
    et = str(gf(t, "entry_time", "entry_dt") or "")[:16]
    xt = str(gf(t, "exit_time", "exit_dt") or "")[:16]
    ep = float(gf(t, "entry_price", "entry") or 0)
    xp = float(gf(t, "exit_price", "exit") or 0)
    pnl = float(gf(t, "pnl", "net_pnl", "profit") or 0)
    rsn = str(gf(t, "exit_reason", "reason") or "")
    print(f"  {num!s:>4} {d:<6} {et:<17} {xt:<17} {ep:>9.1f} {xp:>9.1f} {pnl:>8.2f} {rsn}")

print("\n=== DONE ===")
