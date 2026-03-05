"""
Diagnose SL PnL discrepancy for trades #77, #78 (Short SL) and #97, #109 (Long SL).

TV:  Short SL PnL = -133.46
Our: Short SL PnL = -133.49 (off by 0.03)

TV:  Long SL PnL = -133.26
Our: Long SL PnL = -133.31 (off by 0.05)

Strategy params:
- capital=10000, position_size=10%, leverage=10
- commission=0.0007 (0.07%)
- stop_loss=13.2%, take_profit=2.3%
- sl_type=average_price (uses signal_price as reference)
"""

import sys
from datetime import timedelta

import pandas as pd
import requests

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

df = pd.read_csv(r"d:\bybit_strategy_tester_v2\data\eth_30m_cache.csv")
df["time"] = pd.to_datetime(df["timestamp"])
df = df.set_index("time")

SL = 0.132
TP = 0.023
CAPITAL = 10000
POS_SIZE = 0.1
LEVERAGE = 10
COMMISSION = 0.0007
NOTIONAL = CAPITAL * POS_SIZE * LEVERAGE  # = 10000 USDT

# ─── Get backtest data ───
r = requests.post(
    "http://localhost:8000/api/v1/strategy-builder/strategies/2e5bb802-572b-473f-9ee9-44d38bf9c531/backtest",
    json={
        "symbol": "ETHUSDT",
        "interval": "30",
        "start_date": "2025-01-01T00:00:00+00:00",
        "end_date": "2026-02-27T23:30:00+00:00",
        "initial_capital": CAPITAL,
        "commission": COMMISSION,
        "slippage": 0.0,
        "position_size": POS_SIZE,
        "position_size_type": "percent",
        "leverage": LEVERAGE,
        "pyramiding": 1,
        "direction": "both",
        "market_type": "linear",
    },
    timeout=120,
)
data = r.json()
trades = data.get("trades", [])

SL_TRADES = {77: "short", 78: "short", 97: "long", 109: "long"}
TV_PNLS = {77: -133.46, 78: -133.46, 97: -133.26, 109: -133.26}

for trade_num, side in SL_TRADES.items():
    t = trades[trade_num - 1]
    entry_dt = pd.to_datetime(t["entry_time"])
    exit_dt = pd.to_datetime(t["exit_time"])
    entry_utc3 = entry_dt + timedelta(hours=3)
    exit_utc3 = exit_dt + timedelta(hours=3)

    entry_price = t["entry_price"]
    exit_price = t["exit_price"]
    size = t["size"]
    pnl = t["pnl"]
    fees = t["fees"]
    tv_pnl = TV_PNLS[trade_num]
    ec = t["exit_comment"]

    print(f"\n{'=' * 60}")
    print(f"Trade #{trade_num} ({side}) - {ec}")
    print(f"  Entry: {entry_utc3} @ {entry_price:.4f}")
    print(f"  Exit:  {exit_utc3} @ {exit_price:.4f}")
    print(f"  Size: {size:.6f} ETH, Notional: {size * entry_price:.2f} USDT")
    print(f"  PnL (ours): {pnl:.4f}  PnL (TV): {tv_pnl:.4f}  Diff: {pnl - tv_pnl:.4f}")
    print(f"  Fees (ours): {fees:.4f}")

    # Verify our calculation
    # notional = CAPITAL * POS_SIZE * LEVERAGE = 10000 USDT (fixed)
    notional = NOTIONAL
    size_calc = notional / entry_price
    entry_fee = notional * COMMISSION
    exit_fee = exit_price * size_calc * COMMISSION
    total_fee_calc = entry_fee + exit_fee

    if side == "short":
        gross_pnl = (entry_price - exit_price) * size_calc
    else:
        gross_pnl = (exit_price - entry_price) * size_calc
    net_pnl = gross_pnl - total_fee_calc

    print(f"\n  Manual calculation:")
    print(f"    size = {notional}/{entry_price:.4f} = {size_calc:.6f} ETH")
    print(f"    entry_fee = {notional} × {COMMISSION} = {entry_fee:.4f}")
    print(f"    exit_fee = {exit_price:.4f} × {size_calc:.6f} × {COMMISSION} = {exit_fee:.4f}")
    print(f"    gross_pnl = {gross_pnl:.4f}")
    print(f"    net_pnl = {net_pnl:.4f}  (matches ours: {'YES' if abs(net_pnl - pnl) < 0.01 else 'NO'})")

    # SL price calculation: what is the SL price?
    # sl_ref_price = signal_price = close[signal_bar]
    # SL for short: sl_ref_price * (1 + SL)
    # We need to find the signal bar close
    if side == "short":
        sl_price_calc = exit_price  # exit_price is the SL price
        signal_price = sl_price_calc / (1 + SL)
        print(f"\n    SL price (our exit): {exit_price:.4f}")
        print(f"    signal_price inferred: {signal_price:.4f}")
        # Find the signal bar in kline data
        signal_bar_approx = df[df.index < str(entry_dt)].iloc[-1]
        print(f"    Signal bar close (actual): {signal_bar_approx['close']:.4f}")
        expected_sl = signal_bar_approx["close"] * (1 + SL)
        print(f"    Expected SL price from signal close: {expected_sl:.4f}")
        # What if TV uses entry_price instead of signal_price for SL anchor?
        entry_based_sl = entry_price * (1 + SL)
        print(f"    SL from entry_price: {entry_based_sl:.4f}")
    else:
        sl_price_calc = exit_price
        signal_price = sl_price_calc / (1 - SL)
        print(f"\n    SL price (our exit): {exit_price:.4f}")
        print(f"    signal_price inferred: {signal_price:.4f}")
        signal_bar_approx = df[df.index < str(entry_dt)].iloc[-1]
        print(f"    Signal bar close (actual): {signal_bar_approx['close']:.4f}")
        expected_sl = signal_bar_approx["close"] * (1 - SL)
        print(f"    Expected SL price from signal close: {expected_sl:.4f}")
        entry_based_sl = entry_price * (1 - SL)
        print(f"    SL from entry_price: {entry_based_sl:.4f}")

    # What exit_price would give TV's PnL?
    if side == "short":
        # TV_pnl = (entry - exit_tv) * size - entry_fee - exit_fee_tv
        # TV_pnl = (entry - exit_tv) * size - entry_fee - exit_tv * size * commission
        # TV_pnl + entry_fee = (entry - exit_tv) * size - exit_tv * size * commission
        # TV_pnl + entry_fee = size * entry - size * exit_tv - size * exit_tv * commission
        # TV_pnl + entry_fee = size * entry - size * exit_tv * (1 + commission)
        # size * exit_tv * (1 + commission) = size * entry - tv_pnl - entry_fee
        # exit_tv = (size * entry - tv_pnl - entry_fee) / (size * (1 + commission))
        target_exit = (size_calc * entry_price - tv_pnl - entry_fee) / (size_calc * (1 + COMMISSION))
    else:
        # TV_pnl = (exit_tv - entry) * size - entry_fee - exit_tv * size * commission
        # TV_pnl + entry_fee = size * exit_tv - size * entry - exit_tv * size * commission
        # TV_pnl + entry_fee + size * entry = size * exit_tv * (1 - commission)
        # exit_tv = (TV_pnl + entry_fee + size * entry) / (size * (1 - commission))
        target_exit = (tv_pnl + entry_fee + size_calc * entry_price) / (size_calc * (1 - COMMISSION))

    print(f"\n    To match TV PnL ({tv_pnl:.4f}), exit price should be: {target_exit:.4f}")
    print(f"    Our exit price: {exit_price:.4f}, difference: {exit_price - target_exit:.4f}")
