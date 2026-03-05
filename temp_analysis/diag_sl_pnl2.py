"""
Second pass: correctly compute PnL with actual size from the trade.

Trade #77: size=0.339179 (not 3.391785) → notional = 0.339179 * 2948.30 = 1000 USDT (YES: 10% of 10000)
BUT: leverage=10 → position_value = 1000 USDT (notional without leverage?)

Let's figure out the actual formula used.
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
CAPITAL = 10000
POS_SIZE = 0.1
LEVERAGE = 10
COMMISSION = 0.0007

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
    entry_price = t["entry_price"]
    exit_price = t["exit_price"]
    size = t["size"]  # actual ETH size from API
    pnl = t["pnl"]
    fees = t.get("fees", t.get("commission", 0))
    tv_pnl = TV_PNLS[trade_num]

    # Figure out notional from actual size
    actual_notional = size * entry_price

    print(f"\n{'=' * 60}")
    print(f"Trade #{trade_num} ({side}) SL")
    print(f"  entry={entry_price:.4f}  exit={exit_price:.4f}")
    print(f"  size={size:.6f} ETH  actual_notional={actual_notional:.4f} USDT")
    print(f"  pnl(ours)={pnl:.4f}  pnl(TV)={tv_pnl:.4f}  diff={pnl - tv_pnl:.4f}")
    print(f"  fees(ours)={fees:.4f}")

    # Verify pnl with actual size
    if side == "short":
        gross = (entry_price - exit_price) * size
    else:
        gross = (exit_price - entry_price) * size
    ef = actual_notional * COMMISSION
    xf = exit_price * size * COMMISSION
    net = gross - ef - xf
    print(
        f"  Verify: gross={gross:.4f}  entry_fee={ef:.4f}  exit_fee={xf:.4f}  net={net:.4f}  matches_api={'YES' if abs(net - pnl) < 0.01 else 'NO'}"
    )

    # KEY: The gross PnL should be -13.2% of notional for a full SL hit
    # gross = -SL * actual_notional  (for a full SL exit)
    expected_gross_from_notional = -SL * actual_notional
    print(f"  Expected gross (SL = {SL * 100}% of notional={actual_notional:.4f}): {expected_gross_from_notional:.4f}")
    print(f"  Actual gross: {gross:.4f}  (diff: {gross - expected_gross_from_notional:.4f})")

    # Signal_price and entry_price
    signal_bar = df[df.index < str(pd.to_datetime(t["entry_time"]))].iloc[-1]
    sp = signal_bar["close"]
    print(f"  signal_price (close before entry): {sp:.4f}")
    print(f"  entry_price (open of entry bar):   {entry_price:.4f}")

    # SL price calculations
    if side == "short":
        sl_from_signal = sp * (1 + SL)
        sl_from_entry = entry_price * (1 + SL)
    else:
        sl_from_signal = sp * (1 - SL)
        sl_from_entry = entry_price * (1 - SL)
    print(f"  SL from signal_price: {sl_from_signal:.4f}")
    print(f"  SL from entry_price:  {sl_from_entry:.4f}")
    print(f"  Actual exit_price:    {exit_price:.4f}")
    print(f"  exit matches signal-based SL: {'YES' if abs(exit_price - sl_from_signal) < 0.01 else 'NO'}")
    print(f"  exit matches entry-based SL:  {'YES' if abs(exit_price - sl_from_entry) < 0.01 else 'NO'}")

    # Position sizing: TV might compute size at signal_price instead of entry_price
    # If size = notional / signal_price:
    size_at_signal = actual_notional / sp
    print(f"\n  Size alternatives:")
    print(f"    Actual size:            {size:.6f} = notional/{entry_price:.2f}")
    print(f"    Size at signal_price:   {size_at_signal:.6f} = notional/{sp:.2f}")

    # PnL if size is computed at signal_price (TV hypothesis)
    if side == "short":
        gross_tv_hyp = (entry_price - exit_price) * size_at_signal
        net_tv_hyp = (
            gross_tv_hyp - (entry_price * size_at_signal * COMMISSION) - (exit_price * size_at_signal * COMMISSION)
        )
    else:
        gross_tv_hyp = (exit_price - entry_price) * size_at_signal
        net_tv_hyp = (
            gross_tv_hyp - (entry_price * size_at_signal * COMMISSION) - (exit_price * size_at_signal * COMMISSION)
        )
    print(f"  PnL with size@signal_price: {net_tv_hyp:.4f} (TV={tv_pnl})")

    # TV fee calc difference: TV entry_fee = entry_price * size * commission (not notional * commission)
    # These should be same if notional = entry_price * size
    ef2 = entry_price * size * COMMISSION
    print(f"\n  Fee calc check:")
    print(f"    entry_fee method 1 (notional * comm): {ef:.4f}")
    print(f"    entry_fee method 2 (entry*size*comm): {ef2:.4f}")
    print(f"    same: {'YES' if abs(ef - ef2) < 0.0001 else 'NO'}")

    # TV might compute PnL as percentage of notional without leverage
    # In TV, if strategy sets position_size=10%, leverage=10, initial_capital=10000:
    # TV trade notional = initial_capital * 0.1 = 1000 (WITHOUT leverage?)
    # PnL = gross_pct * notional - fees
    # Or TV uses a different fee basis?

    # Hypothesis 3: TV uses percentage-based PnL calculation
    # TV gross PnL% = (exit - entry)/entry * leverage for long
    # TV gross PnL = TV gross PnL% * (capital * pos_size)
    if side == "short":
        pct_return = (entry_price - exit_price) / entry_price
    else:
        pct_return = (exit_price - entry_price) / entry_price
    leveraged_return = pct_return * LEVERAGE
    pnl_from_pct = leveraged_return * (CAPITAL * POS_SIZE)
    print(f"\n  Percentage-based calc:")
    print(f"    price return: {pct_return * 100:.4f}%")
    print(f"    leveraged return: {leveraged_return * 100:.4f}%")
    print(f"    gross (capital*pos*lev*ret): {pnl_from_pct:.4f}")

    # TV commission: might be on total leveraged value, not just the margin
    # entry_fee_tv = capital * pos_size * leverage * commission
    #              = 10000 * 0.1 * 10 * 0.0007 = 7.0
    ef_tv = CAPITAL * POS_SIZE * LEVERAGE * COMMISSION
    print(f"    entry_fee (TV style): {ef_tv:.4f}")
    print(f"    Hmm - same as ours: {ef_tv:.4f}")

print("\n\n--- SUMMARY ---")
print("Signal price = close of signal bar = entry_price (open of next bar = same as close?)")
print("Let's check if signal_price == entry_price for these trades:")
for trade_num, side in SL_TRADES.items():
    t = trades[trade_num - 1]
    ep = t["entry_price"]
    signal_bar = df[df.index < str(pd.to_datetime(t["entry_time"]))].iloc[-1]
    sp = signal_bar["close"]
    print(f"  Trade #{trade_num}: signal_close={sp:.4f}  entry_open={ep:.4f}  ratio={ep / sp:.6f}  diff={ep - sp:.4f}")
