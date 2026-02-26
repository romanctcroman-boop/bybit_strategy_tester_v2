"""Trace the cascade: Starting from TV#1's early entry, track how divergences propagate.

KEY QUESTION: If all divergences are caused by TV entering at a DIFFERENT crossunder
(earlier or later), is there a single root cause?

TV#1: enters 2025-01-01 13:30 (NO bar-close cross — intra-bar)
Engine#1: enters 2025-01-02 22:30 (1st bar-close cross)

If TV#1 enters earlier, it exits earlier too. Then TV gets free to enter TV#2,#3,#4,#5
which the engine's trade #1 is still blocking (because engine#1 entered later).

This is a POSITION STATE cascade.
"""

import sys

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

TV_CSV = r"c:\Users\roman\Downloads\as4.csv"


def parse_tv_trades(csv_path):
    tv_raw = pd.read_csv(csv_path, sep=";")
    trades = []
    for i in range(0, len(tv_raw), 2):
        exit_row = tv_raw.iloc[i]
        entry_row = tv_raw.iloc[i + 1]
        entry_type = str(entry_row["Тип"]).strip()
        direction = "short" if "short" in entry_type.lower() else "long"
        entry_msk = pd.Timestamp(str(entry_row["Дата и время"]).strip())
        exit_msk = pd.Timestamp(str(exit_row["Дата и время"]).strip())
        entry_utc = entry_msk - pd.Timedelta(hours=3)
        exit_utc = exit_msk - pd.Timedelta(hours=3)
        pnl = float(str(exit_row["Чистая прибыль / убыток USDT"]).replace(",", ".").strip())
        trades.append(
            {
                "tv_num": i // 2 + 1,
                "direction": direction,
                "entry_time": entry_utc,
                "exit_time": exit_utc,
                "pnl": pnl,
            }
        )
    return trades


def main():
    tv = parse_tv_trades(TV_CSV)

    # From _match_trades.py output, here are the matched pairs:
    # I'll list all divergent trades and trace the cascade

    # The ALIGNED comparison shows:
    # - TV has 3 more trades than engine (151 vs 148)
    # - The 3 "extra" TV trades exist because TV#1 enters earlier → cascade

    # Let me trace: for each divergent pair, check if engine's previous trade
    # was still open when the 1st crossunder fired

    # From the match output, the divergence points are:
    divergences = [
        # (type, tv_num, desc)
        ("INTRA-BAR", 1, "TV#1: no bar-close cross at 13:00 (RSI=52.007, prev=53.79)"),
        ("CASCADE", 2, "TV#2: only exists because TV#1 exited earlier → engine still in trade"),
        ("CASCADE", 3, "TV#3: only exists because TV#1→#2 cascade"),
        ("CASCADE", 4, "TV#4: cascade"),
        ("CASCADE", 5, "TV#5: cascade (LONG)"),
        # After TV#5 exits (2025-01-14 00:00), TV#6 = Engine#3 at 2025-01-14 16:30 → MATCH!
        ("INTRA-BAR", 9, "TV#9/E#6: Root #9, RSI=52.055 (no bar-close cross)"),
        # TV#9 exits at 2025-01-28 20:30, TV#10=E#7 at 2025-01-29 05:00 → MATCH!
        ("UNKNOWN", 22, "TV#22/E#20: engine 4h earlier (10:30 vs 14:30 signal). Both valid crosses"),
        # Then TV#22 exits at 2025-02-24 10:00, TV#23=E#21 at 2025-02-24 13:00 → MATCH!
        ("UNKNOWN", 56, "TV#56/E#54: engine 4h earlier (15:00 vs 19:00 signal). Both valid crosses"),
        ("CASCADE", None, "E#55: engine-only (TV#56 still open)"),
        ("CASCADE", None, "E#56: engine-only (TV#56 still open)"),
        ("CASCADE", 57, "TV#57/E#57: engine 15.5h earlier (cascade from TV#56 long exit)"),
        ("CASCADE", 58, "TV#58: only exists because TV#57 exited at 14:08:30 instead of later"),
        ("CASCADE", 59, "TV#59: cascade"),
        ("CASCADE", 60, "TV#60: cascade"),
        # After TV#60, TV#61=E#58 → MATCH!
        ("UNKNOWN", 85, "TV#85/E#82: engine 12.5h earlier"),
        ("UNKNOWN", 89, "TV#89/E#86: engine 9.5h earlier"),
        ("UNKNOWN", 91, "TV#91/E#88: engine 7h earlier"),
        ("CASCADE", None, "E#89: engine-only (TV#91 still open)"),
        ("UNKNOWN", 119, "TV#119/E#117: engine 5h earlier"),
        ("SAME_BAR_TP", 47, "TV#47/E#45: same entry, TP on entry bar"),
        ("SAME_BAR_TP", 105, "TV#105/E#103: same entry, TP on entry bar"),
        ("INTRA-BAR", 136, "TV#136: no bar-close cross (prev=51.97, cur=51.51, both < 52)"),
        ("END_OF_DATA", 151, "TV#151/E#148: last trade, different exit handling"),
    ]

    # Count by category
    from collections import Counter

    cats = Counter(d[0] for d in divergences)
    print("DIVERGENCE CATEGORIES:")
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")

    print(f"\nTotal divergences: {len(divergences)}")

    # Now check: are CASCADE divergences truly cascades?
    # A CASCADE means the divergence only exists because a PREVIOUS divergence
    # changed the position state.

    # Let me trace position state for TV vs Engine around each UNKNOWN case
    print("\n\n" + "=" * 80)
    print("UNKNOWN DIVERGENCES - Need investigation")
    print("=" * 80)

    unknowns = [d for d in divergences if d[0] == "UNKNOWN"]
    for _, tv_num, desc in unknowns:
        t = tv[tv_num - 1]
        prev_t = tv[tv_num - 2]
        print(f"\n  {desc}")
        print(
            f"  Prev TV#{prev_t['tv_num']}: {prev_t['direction']} "
            f"entry={prev_t['entry_time']} exit={prev_t['exit_time']}"
        )
        print(f"  TV#{t['tv_num']}: {t['direction']} entry={t['entry_time']} exit={t['exit_time']}")
        gap = t["entry_time"] - prev_t["exit_time"]
        print(f"  Gap between prev exit and entry: {gap}")

    # The REAL question: do these UNKNOWN cases have the SAME previous trade exit
    # in both engine and TV? If the prev trade matched perfectly, then the divergence
    # is NOT a cascade — it's a genuine root cause.

    # From _match_trades output:
    # E#20/TV#22: prev is E#19/TV#21 (both short, 2025-02-19 18:30 → 2025-02-21 19:00) → EXACT MATCH
    # E#54/TV#56: prev is E#53/TV#55 (both short, 2025-05-09 13:00 → 2025-05-09 14:30) → EXACT MATCH
    # E#82/TV#85: prev is E#81/TV#84 (both short, 2025-08-12 18:00 → 2025-08-15 15:30) → EXACT MATCH
    # E#86/TV#89: prev is E#85/TV#88 (both short, 2025-08-25 16:00 → 2025-08-25 19:00) → EXACT MATCH
    # E#88/TV#91: prev is E#87/TV#90 (both short, 2025-08-30 09:30 → 2025-09-01 20:30) → EXACT MATCH
    # E#117/TV#119: prev is E#116/TV#118 (both long, 2025-11-20 21:30 → 2025-11-24 17:30) → EXACT MATCH

    print("\n\n" + "=" * 80)
    print("KEY FINDING: All UNKNOWN divergences have PERFECTLY MATCHING previous trades!")
    print("This means they are NOT cascades. They are GENUINE root causes.")
    print("The engine and TV are in the SAME state (flat) when the 1st crossunder fires,")
    print("but TV does NOT enter on the 1st crossunder — it enters on a LATER one.")
    print("=" * 80)

    print("""
HYPOTHESIS: TradingView's broker emulator has additional entry conditions
that our engine doesn't implement. Possibilities:

1. RSI must be RISING when it crosses under 52 (momentum direction)
   - 1st cross: RSI falling fast → valid cross but TV rejects
   - 2nd cross: RSI rising back near 52 then crossing → TV accepts

2. RSI must have been ABOVE 52 for N consecutive bars before crossing
   - 1st cross: RSI was briefly above 52 (1-2 bars)
   - 2nd cross: RSI was above 52 for longer

3. TV evaluates signals at a different point in the bar cycle
   - Different signal evaluation order (exits before entries)
   
4. TV applies a "cooldown" after exit before allowing new entry
   - After exiting a trade, TV waits N bars before re-entering

5. MOST LIKELY: These are ALSO intra-bar detection cases
   - TV detects the cross intra-bar on a LATER bar
   - The bar where TV enters has no bar-close cross either
   - But intra-bar RSI dips below 52 during that bar

Let me check: does the TV signal bar (the bar BEFORE TV entry) show a bar-close cross?
""")

    # Check TV signal bars
    # TV entry = signal_bar + 30min (entry_on_next_bar_open)
    # So TV signal bar = TV entry - 30min

    print("TV signal bars for UNKNOWN cases:")
    for _, tv_num, desc in unknowns:
        t = tv[tv_num - 1]
        signal_bar = t["entry_time"] - pd.Timedelta(minutes=30)
        print(f"  TV#{tv_num}: signal_bar={signal_bar}")
        # From _check_rsi_at_divergences_v2.py results:
        # E#20/TV#22: TV signal at 14:30 → RSI=49.5525, prev was from cross (YES)
        # E#54/TV#56: TV signal at 19:00 → RSI=51.0807 (YES - valid cross)
        # E#82/TV#85: TV signal at 13:30 → RSI=51.9076 (YES - valid cross)
        # E#86/TV#89: TV signal at 12:00 → RSI=51.6987 (YES - valid cross)
        # E#88/TV#91: TV signal at 18:00 → RSI=51.3785 (YES - valid cross)
        # E#117/TV#119: TV signal at 05:00 → RSI=51.2247 (YES - valid cross)
        # All TV signal bars ALSO show valid bar-close crosses!

    print("""
ALL TV signal bars for UNKNOWN cases show VALID bar-close crosses.
So TV is NOT using intra-bar detection for these — it's skipping valid crosses.

The only remaining hypothesis is that the ENGINE enters on the WRONG cross.
Perhaps the engine's cross detection considers a cross that shouldn't be valid.

Let me check: For each case, what does the BTC RSI look like around the 1st cross
(the one engine uses but TV skips)?
Maybe the 1st cross is actually a "false cross" — RSI barely dips below 52
and immediately bounces back. TV might have a "confirmation" requirement.

From _check_rsi_at_divergences_v2.py:
Engine signal bar RSI values (the 1st cross that TV skips):
  E#20: RSI=51.1230 (valid cross, 0.877 below 52)
  E#54: RSI=50.0107 (valid cross, 1.989 below 52)
  E#82: RSI=51.5481 (valid cross, 0.452 below 52)
  E#86: RSI=51.8081 (valid cross, 0.192 below 52)
  E#88: RSI=50.0639 (valid cross, 1.936 below 52)
  E#117: RSI=50.0656 (valid cross, 1.934 below 52)

These are clearly valid crosses with RSI well below 52.
TV should definitely fire on these. But it doesn't.

CONCLUSION: There must be something else going on.
Maybe the issue is with the PREVIOUS bar's RSI being above 52.
Our signal logic: cross_short = (rsi_prev >= 52) & (rsi < 52)

Let me check the prev bar RSI for each case to ensure it's really >= 52.
""")


main()
