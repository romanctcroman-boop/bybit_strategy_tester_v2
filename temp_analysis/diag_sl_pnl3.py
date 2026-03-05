"""
Precise fee analysis for SL trades.

Ours:
  Short SL: entry_fee=0.70, exit_fee=0.7924 → total=1.4924  → pnl=-133.4924
  Long  SL: entry_fee=0.70, exit_fee=0.6076 → total=1.3076  → pnl=-133.3076

TV:
  Short SL: pnl=-133.46  → total_fee = -132 - (-133.46) = 1.46
  Long  SL: pnl=-133.26  → total_fee = -132 - (-133.26) = 1.26

Hypothesis: TV computes exit_fee on SL at ENTRY price (not exit price).
  Short SL: exit at sl_price = signal * 1.132 = entry * 1.132
  entry_fee_tv = 1000 * 0.0007 = 0.7
  exit_fee_tv  = entry_price * size * 0.0007 = 1000 * 0.0007 = 0.7
  total_fee_tv = 1.4   → BUT TV says 1.46, so that's too low.

Wait, let's re-examine. TV PnL difference:
  Short: 1.4924 - 1.46 = 0.0324
  Long:  1.3076 - 1.26 = 0.0476

If gross is always -132, then:
  TV short fee = 1.46
  TV long  fee = 1.26

Entry fee = 0.70 for both.
Exit fee TV short = 1.46 - 0.70 = 0.76
Exit fee TV long  = 1.26 - 0.70 = 0.56

Our exit_fee:
  Short: exit_price × size × 0.0007 = 3337.4756 × 0.339179 × 0.0007 = 0.7924
  Long:  exit_price × size × 0.0007 = 3490.3842 × 0.248683 × 0.0007 = 0.6076

TV exit fees:
  Short: 0.76 (we compute 0.7924, diff=0.0324)
  Long:  0.56 (we compute 0.6076, diff=0.0476)

Wait - 0.76 = 0.7000 * (3337.4756/entry=2948.30)?
  0.7 * (3337.4756/2948.30) = 0.7 * 1.132 = 0.7924 - that's ours, not TV.

TV exit_fee = 0.76 for short SL.
0.76 = entry_price * size * 0.0007 = 0.7
  No. Let me try: what if TV's exit_fee for SL is entry_fee (0.7)?
  total = 0.7 + 0.7 = 1.40. TV says 1.46. Not matching.

Hmm. Let me try commission = 0.00073 (rounded differently)?
  entry_fee = 1000 * 0.00073 = 0.73
  exit_fee_short = 3337.4756 * 0.339179 * 0.00073 = ... but we said comm=0.0007.

Actually - what if TV rounds the fee to cents?
  Our exit_fee (short) = 0.7924 → rounded to 0.79 → total = 0.70 + 0.79 = 1.49? No.

Let me look at this differently.
TV PnL = gross - fee
-133.46 = -132 - fee_tv
fee_tv = 1.46

Our fee = 1.4924
1.4924 - 1.46 = 0.0324

For long:
TV_fee = 1.26
Our_fee = 1.3076
Diff = 0.0476

CRITICAL INSIGHT:
  Exit_fee_ours(short) = exit_price_sl * size * comm = (entry * 1.132) * (notional/entry) * comm
    = entry * 1.132 * (notional/entry) * comm
    = 1.132 * notional * comm
    = 1.132 * 1000 * 0.0007
    = 0.7924

  TV_exit_fee(short) = ?
  TV seems to charge 0.76 = 1000 * 0.0007 * something
  0.76 / 0.0007 / 1000 = 1.085714...

What if TV exit fee for SL is computed on the GROSS notional without the loss?
  i.e., exit_fee_tv = notional * (1 - SL) * comm * ...? Doesn't make sense.

Wait... TV_exit_fee_short = 0.76
  = notional * (1 + SL%?) * 0.0007?
  = 1000 * 1.132 * 0.0007 = 0.7924? No that's ours.

Let me try another angle: TV might compute position value at exit differently for SL.
In TV's documentation: commission is calculated on order value.

For stop loss in TV:
  The "order value" might be computed differently from exit_price * size.
  Could TV use the "expected SL value" = entry_price * size (not exit_price * size)?
"""

import sys

import requests

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

SL = 0.132
CAPITAL = 10000
POS_SIZE = 0.1
LEVERAGE = 10
COMMISSION = 0.0007
NOTIONAL = CAPITAL * POS_SIZE  # = 1000 USDT (margin)

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

# Let's also check a winning TP short trade to compare fee behavior
# We know TP shorts win ~21.61-21.62

print("=== SL TRADE FEE ANALYSIS ===\n")
for trade_num, side in SL_TRADES.items():
    t = trades[trade_num - 1]
    entry_price = t["entry_price"]
    exit_price = t["exit_price"]
    size = t["size"]
    pnl = t["pnl"]
    fees = t.get("fees", t.get("commission", 0))
    tv_pnl = TV_PNLS[trade_num]

    gross = (entry_price - exit_price) * size if side == "short" else (exit_price - entry_price) * size
    our_entry_fee = entry_price * size * COMMISSION
    our_exit_fee = exit_price * size * COMMISSION
    our_total_fee = our_entry_fee + our_exit_fee

    tv_total_fee = gross - tv_pnl  # gross is -132, TV_pnl is known
    tv_exit_fee = tv_total_fee - our_entry_fee  # entry fee same

    print(f"Trade #{trade_num} ({side}) SL")
    print(f"  entry={entry_price:.4f}  exit={exit_price:.4f}  size={size:.6f}")
    print(f"  gross={gross:.4f}")
    print(
        f"  our:  entry_fee={our_entry_fee:.6f}  exit_fee={our_exit_fee:.6f}  total={our_total_fee:.6f}  pnl={pnl:.6f}"
    )
    print(f"  tv:   total_fee={tv_total_fee:.6f}  exit_fee={tv_exit_fee:.6f}  pnl={tv_pnl:.4f}")
    print(f"  diff in exit_fee: {our_exit_fee - tv_exit_fee:.6f}")
    print(f"  exit_fee/notional: ours={our_exit_fee / NOTIONAL:.6f}  tv={tv_exit_fee / NOTIONAL:.6f}")
    print(
        f"  our exit_fee = exit_price * size * comm = {exit_price:.4f} * {size:.6f} * {COMMISSION} = {our_exit_fee:.6f}"
    )

    # Hypothesis: TV charges exit fee on ENTRY price (not exit price)
    exit_fee_on_entry = entry_price * size * COMMISSION
    pnl_with_entry_fee = gross - our_entry_fee - exit_fee_on_entry
    print(f"  PnL if exit_fee on entry_price: {pnl_with_entry_fee:.4f}  (TV={tv_pnl:.4f})")

    # Hypothesis: TV charges exit fee at SL expressed differently
    # Our exit price for short SL = signal * (1+SL) = entry * (1+SL)
    # What if TV exit fee = entry_price * size * comm (i.e. uses entry_price as proxy)?
    # pnl_with_entry_fee = -132 - 0.7 - 0.7 = -133.4 (close but 0.06 off for short)

    # Hypothesis: TV uses (1 + SL) percent of entry_fee for exit_fee?
    # exit_fee_tv = entry_fee * (1 + SL)?  = 0.7 * 1.132 = 0.7924 - that's ours, not TV's

    # Let me check exact TV exit fees:
    print(f"  tv_exit_fee precise: {tv_exit_fee:.6f}")
    # For short: 1.46 - 0.7 = 0.76 → 0.76 / size / entry_price = 0.76 / (0.339179 * 2948.30) = 0.76/1000 = 0.00076
    ratio = tv_exit_fee / (size * entry_price)
    print(f"  tv_exit_fee / (size * entry_price) = {ratio:.6f}  (comm={COMMISSION})")
    ratio2 = tv_exit_fee / (size * exit_price)
    print(f"  tv_exit_fee / (size * exit_price) = {ratio2:.6f}  (comm={COMMISSION})")
    print()

print("\n=== COMPARISON: TP TRADE FEES vs TV ===")
# Check a TP trade to see if TV fee matches ours for non-SL exits
# Look at first short TP trades
tv_data: dict[str, object] = {
    # From a4.csv: pick a short TP trade we know matches
    # Trade #1: short TP, TV PnL = 21.62 (close to 21.61-21.62)
}
# Check trade #1 from API
t1 = trades[0]
print(f"Trade #1 ({t1['trade_type']}) {t1['exit_comment']}")
print(f"  entry={t1['entry_price']:.4f}  exit={t1['exit_price']:.4f}  size={t1['size']:.6f}  pnl={t1['pnl']:.4f}")
entry_fee = t1["entry_price"] * t1["size"] * COMMISSION
exit_fee = t1["exit_price"] * t1["size"] * COMMISSION
total_fee = entry_fee + exit_fee
if t1["trade_type"] == "sell":
    gross = (t1["entry_price"] - t1["exit_price"]) * t1["size"]
else:
    gross = (t1["exit_price"] - t1["entry_price"]) * t1["size"]
print(f"  gross={gross:.4f}  entry_fee={entry_fee:.4f}  exit_fee={exit_fee:.4f}  total_fee={total_fee:.4f}")
print(f"  computed pnl={gross - total_fee:.4f}  api pnl={t1['pnl']:.4f}")
print(f"  Trade 1 full data: {t1}")
