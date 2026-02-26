"""Count trade types and stats."""

import json
import sqlite3

conn = sqlite3.connect("d:\\bybit_strategy_tester_v2\\data.sqlite3")
c = conn.cursor()
c.execute("SELECT trades FROM backtests WHERE id = 'c634b8c8-aa35-45bf-9137-07d3cbe8ec61'")
row = c.fetchone()
conn.close()

trades = json.loads(row[0])
sells = [t for t in trades if t.get("side") == "sell"]
buys = [t for t in trades if t.get("side") == "buy"]
sell_wins = [t for t in sells if t.get("pnl", 0) > 0]
sell_losses = [t for t in sells if t.get("pnl", 0) <= 0 and t.get("exit_comment") == "SL"]
sell_open = [t for t in sells if t.get("exit_comment") == "end_of_backtest"]
buy_wins = [t for t in buys if t.get("pnl", 0) > 0]
buy_losses = [t for t in buys if t.get("pnl", 0) <= 0 and t.get("exit_comment") == "SL"]
buy_open = [t for t in buys if t.get("exit_comment") == "end_of_backtest"]

print(f"Total: {len(trades)} trades")
print(f"\nSell (short) trades: {len(sells)}")
print(f"  Wins:   {len(sell_wins)}")
print(f"  Losses: {len(sell_losses)}")
print(f"  Open:   {len(sell_open)}")

print(f"\nBuy (long) trades: {len(buys)}")
print(f"  Wins:   {len(buy_wins)}")
print(f"  Losses: {len(buy_losses)}")
print(f"  Open:   {len(buy_open)}")

print(f"\nTotal wins: {len(sell_wins) + len(buy_wins)}")
print(f"Total losses: {len(sell_losses) + len(buy_losses)}")
print(f"Open: {len(sell_open) + len(buy_open)}")

sell_win_pnl = sum(t.get("pnl", 0) for t in sell_wins)
buy_win_pnl = sum(t.get("pnl", 0) for t in buy_wins)
sell_loss_pnl = sum(t.get("pnl", 0) for t in sell_losses)
buy_loss_pnl = sum(t.get("pnl", 0) for t in buy_losses)
print(f"\nShort win PnL: {sell_win_pnl:.4f}")
print(f"Long win PnL: {buy_win_pnl:.4f}")
print(f"Short loss PnL: {sell_loss_pnl:.4f}")
print(f"Long loss PnL: {buy_loss_pnl:.4f}")
total_fees = sum(t.get("fees", 0) for t in trades)
print(f"Total fees: {total_fees:.4f}")
