"""Verify TV qty rounding hypothesis for SL trades"""

import math

COMMISSION = 0.0007
CAPITAL = 10000
POS_SIZE = 0.1  # 10%
LEVERAGE = 10
MARGIN = CAPITAL * POS_SIZE  # = 1000 USDT (margin, before leverage)
SL = 0.132
TP = 0.023


# TV rounds qty to 4 decimal places (truncate down)
def tv_qty(entry_price):
    exact = MARGIN / entry_price  # TV uses margin (not leveraged notional) for qty
    return math.floor(exact * 10000) / 10000  # truncate to 4dp


def our_qty(entry_price):
    notional = MARGIN * LEVERAGE  # = 10000 USDT leveraged
    return notional / entry_price  # no rounding


def pnl(entry_price, exit_price, qty, direction):
    if direction == "short":
        gross = (entry_price - exit_price) * qty
    else:
        gross = (exit_price - entry_price) * qty
    fee = (entry_price + exit_price) * qty * COMMISSION
    return gross - fee


# ---- Trade #77: Short SL ----
ep77, xp77 = 2948.30, 3337.48
tv_q77 = tv_qty(ep77)
our_q77 = our_qty(ep77)
tv_pnl77 = pnl(ep77, xp77, tv_q77, "short")
our_pnl77 = pnl(ep77, xp77, our_q77, "short")
print(f"Trade #77 Short SL:")
print(f"  TV qty={tv_q77:.6f}  Our qty={our_q77:.6f}")
print(f"  TV PnL={tv_pnl77:.4f}  Our PnL={our_pnl77:.4f}  CSV TV=-133.46")

# ---- Trade #78: Short SL ----
ep78, xp78 = 3374.15, 3819.54
tv_q78 = tv_qty(ep78)
our_q78 = our_qty(ep78)
tv_pnl78 = pnl(ep78, xp78, tv_q78, "short")
our_pnl78 = pnl(ep78, xp78, our_q78, "short")
print(f"\nTrade #78 Short SL:")
print(f"  TV qty={tv_q78:.6f}  Our qty={our_q78:.6f}")
print(f"  TV PnL={tv_pnl78:.4f}  Our PnL={our_pnl78:.4f}  CSV TV=-133.46")

# ---- Trade #97: Long SL ----
ep97, xp97 = 4021.18, 3490.38
tv_q97 = tv_qty(ep97)
our_q97 = our_qty(ep97)
tv_pnl97 = pnl(ep97, xp97, tv_q97, "long")
our_pnl97 = pnl(ep97, xp97, our_q97, "long")
print(f"\nTrade #97 Long SL:")
print(f"  TV qty={tv_q97:.6f}  Our qty={our_q97:.6f}")
print(f"  TV PnL={tv_pnl97:.4f}  Our PnL={our_pnl97:.4f}  CSV TV=-133.26")

# ---- Trade #109: Long SL ----
ep109, xp109 = 3714.73, 3224.38
tv_q109 = tv_qty(ep109)
our_q109 = our_qty(ep109)
tv_pnl109 = pnl(ep109, xp109, tv_q109, "long")
our_pnl109 = pnl(ep109, xp109, our_q109, "long")
print(f"\nTrade #109 Long SL:")
print(f"  TV qty={tv_q109:.6f}  Our qty={our_q109:.6f}")
print(f"  TV PnL={tv_pnl109:.4f}  Our PnL={our_pnl109:.4f}  CSV TV=-133.26")

# ---- Also check a "normal" SL trade that matches (TV PnL=-133.49) ----
ep45, xp45 = 1459.32, 1651.96
tv_q45 = tv_qty(ep45)
our_q45 = our_qty(ep45)
tv_pnl45 = pnl(ep45, xp45, tv_q45, "short")
our_pnl45 = pnl(ep45, xp45, our_q45, "short")
print(f"\nTrade #45 Short SL (normal, TV=-133.49):")
print(f"  TV qty={tv_q45:.6f}  Our qty={our_q45:.6f}")
print(f"  TV PnL={tv_pnl45:.4f}  Our PnL={our_pnl45:.4f}  CSV TV=-133.49")

# ---- Check TV notional matches ----
print(f"\nNotional checks (should match CSV column 'Размер позиции (цена)'):")
for ep, tv_q, name in [
    (2948.30, 0.3391, "#77"),
    (3374.15, 0.2963, "#78"),
    (4021.18, 0.2486, "#97"),
    (3714.73, 0.2691, "#109"),
]:
    print(f"  Trade {name}: tv_qty={tv_q:.4f}  ep*tv_q={ep * tv_q:.6f}  tv_qty(calc)={tv_qty(ep):.6f}")
