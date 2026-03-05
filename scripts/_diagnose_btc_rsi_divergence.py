"""
Diagnose BTC RSI divergence around the 2026-02-01 10:00 signal.

TV expects crossunder(rsi,52) at 2026-02-01 10:00 but our engine does NOT fire.
Our engine has prev_rsi=51.97 (<52) — so crossunder is False.
TV must see prev_rsi>=52.

This script:
1. Prints BTC close prices and RSI for the 30 bars around the divergence point
2. Checks if using 15m BTC (resampled to 30m) changes the RSI
3. Checks what happens if we use a different RSI warmup length

Also checks the 21 extra signals our engine fires (2026-02-04 07:00, etc.)
— for those, TV's BTC RSI must have prev<52 (no crossunder),
  but we have prev>=52.
"""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="ERROR")

import numpy as np
import pandas as pd

from backend.backtesting.service import BacktestService


def rsi_series(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI (EWM alpha=1/period) - same as TradingView."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_g = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_l = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# Key divergent bars (UTC):
TV_ONLY_SHORT = [pd.Timestamp("2026-02-01 10:00", tz="UTC")]
ENGINE_ONLY_SHORT = [
    pd.Timestamp("2026-02-04 07:00", tz="UTC"),
    pd.Timestamp("2026-02-07 13:30", tz="UTC"),
    pd.Timestamp("2026-02-07 15:30", tz="UTC"),
    pd.Timestamp("2026-02-08 20:30", tz="UTC"),
    pd.Timestamp("2026-02-10 02:00", tz="UTC"),
    pd.Timestamp("2026-02-11 22:30", tz="UTC"),
    pd.Timestamp("2026-02-12 02:30", tz="UTC"),
    pd.Timestamp("2026-02-14 14:00", tz="UTC"),
    pd.Timestamp("2026-02-16 10:00", tz="UTC"),
    pd.Timestamp("2026-02-17 01:30", tz="UTC"),
    pd.Timestamp("2026-02-17 03:00", tz="UTC"),
    pd.Timestamp("2026-02-17 19:00", tz="UTC"),
    pd.Timestamp("2026-02-18 05:30", tz="UTC"),
    pd.Timestamp("2026-02-19 02:30", tz="UTC"),
    pd.Timestamp("2026-02-19 08:00", tz="UTC"),
    pd.Timestamp("2026-02-19 22:00", tz="UTC"),
    pd.Timestamp("2026-02-20 19:00", tz="UTC"),
    pd.Timestamp("2026-02-20 20:00", tz="UTC"),
    pd.Timestamp("2026-02-21 03:00", tz="UTC"),
    pd.Timestamp("2026-02-21 12:00", tz="UTC"),
    pd.Timestamp("2026-02-23 13:30", tz="UTC"),
]
ALL_DIVERGENT = sorted(TV_ONLY_SHORT + ENGINE_ONLY_SHORT)


async def main():
    svc = BacktestService()

    # Fetch BTC 30m with warmup from 2020
    btc_start = pd.Timestamp("2020-01-01", tz="UTC")
    end = pd.Timestamp("2026-02-25", tz="UTC")

    print("Fetching BTC 30m 2020..2026-02-25 ...")
    btc_w = await svc._fetch_historical_data("BTCUSDT", "30", btc_start, pd.Timestamp("2025-01-01", tz="UTC"))
    btc_m = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2025-01-01", tz="UTC"), end)
    btc = pd.concat([btc_w, btc_m]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]
    if btc.index.tz is None:
        btc.index = btc.index.tz_localize("UTC")
    print(f"BTC 30m bars: {len(btc)}  [{btc.index[0].date()} .. {btc.index[-1].date()}]")

    btc_rsi_30m = rsi_series(btc["close"], 14)

    # ── 1. Print BTC bars around the TV-only signal 2026-02-01 10:00 ────────
    t_focus = pd.Timestamp("2026-02-01 10:00", tz="UTC")
    loc = btc.index.get_loc(t_focus)
    window = btc.iloc[max(0, loc - 5) : loc + 4]
    window_rsi = btc_rsi_30m.iloc[max(0, loc - 5) : loc + 4]
    print(f"\n── BTC bars around {t_focus} (TV expects crossunder here) ──")
    print(f"{'Time (UTC)':22s}  {'close':10s}  {'RSI_14':8s}  note")
    for i, (ts, row) in enumerate(window.iterrows()):
        rsi_val = window_rsi.loc[ts]
        note = ""
        if ts == t_focus:
            note = "<<<TV signal bar (crossunder expected)"
        elif ts == window.index[max(0, loc - 5 - max(0, loc - 5))]:
            note = ""
        print(f"{str(ts)[:22]:22s}  {row['close']:10.2f}  {rsi_val:8.4f}  {note}")

    # The prev bar RSI for t_focus
    prev_t = btc.index[loc - 1]
    prev_rsi = btc_rsi_30m.loc[prev_t]
    cur_rsi = btc_rsi_30m.loc[t_focus]
    print(f"\n  prev bar ({str(prev_t)[:16]}): RSI = {prev_rsi:.4f}  (need >=52 for crossunder)")
    print(f"  curr bar ({str(t_focus)[:16]}): RSI = {cur_rsi:.4f}  (need  <52 for crossunder)")
    print(f"  crossunder 52 = {prev_rsi >= 52 and cur_rsi < 52}")
    print(
        f"  PROBLEM: prev_rsi={prev_rsi:.4f} is {'<52 — NO crossunder (bug)' if prev_rsi < 52 else '>=52 — crossunder OK'}"
    )

    # ── 2. Try different RSI period / warmup ─────────────────────────────────
    print(f"\n── RSI sensitivity at {t_focus} for different periods/warmup ──")
    for period in [13, 14, 15]:
        r = rsi_series(btc["close"], period)
        pv = r.loc[prev_t]
        cv = r.loc[t_focus]
        print(f"  period={period}: prev={pv:.4f}, cur={cv:.4f}, cross52={pv >= 52 and cv < 52}")

    # ── 3. Check how many engine-only signals have TV prev_rsi actually >=52 ─
    # (i.e., how many does TV filter out? All 21 should be crossunder=True in
    # our engine but TV does NOT fire → TV's RSI must have a different value
    # OR TV applies a different filter like use_short_range [52..100] that
    # requires RSI to also be <= some upper threshold or just came from above)
    print("\n── Engine-only signals: BTC RSI prev/cur at our data ──")
    print("  (These fire in our engine but NOT in TV)")
    print("  All have our crossunder=True (prev>=52, cur<52).")
    print("  TV must NOT see them — possible reasons:")
    print("  a) TV's BTC RSI values are different (price data difference)")
    print("  b) TV applies additional range filter: short_range=[20..52] requires")
    print("     RSI to have been in [20..52] before the crossunder")
    print("  c) TV applies 'use_long_range' to filter short signals too")
    print()
    print(f"  {'Time (UTC)':22s}  {'prev_RSI':8s}  {'cur_RSI':8s}  delta  margin_from_52")
    for ts in ENGINE_ONLY_SHORT[:10]:
        if ts not in btc_rsi_30m.index:
            continue
        cur_loc = btc_rsi_30m.index.get_loc(ts)
        cur_val = btc_rsi_30m.iloc[cur_loc]
        prev_val = btc_rsi_30m.iloc[cur_loc - 1]
        margin = prev_val - 52.0
        print(f"  {str(ts)[:22]:22s}  {prev_val:8.4f}  {cur_val:8.4f}  {cur_val - prev_val:+.4f}  +{margin:.4f}")

    # ── 4. What if TV uses a DIFFERENT RSI period? Try period=14 on 30m but
    #       also try Wilder's using SMA init (pandas default) vs EWM ──────────
    print("\n── Alternative RSI calculation at TV-only bar 2026-02-01 10:00 ──")

    # RMA (Wilder's Moving Average = EWM with alpha=1/period, adjust=False)
    # This is what TradingView uses — same as our current implementation.
    # Let's verify by also trying the SMA-seeded version.
    def rsi_sma_seed(series, period=14):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        # Seed with SMA for first value, then EWM
        avg_g = gain.copy()
        avg_l = loss.copy()
        for i in range(period, len(gain)):
            if i == period:
                avg_g.iloc[i] = gain.iloc[1 : period + 1].mean()
                avg_l.iloc[i] = loss.iloc[1 : period + 1].mean()
            else:
                avg_g.iloc[i] = (avg_g.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
                avg_l.iloc[i] = (avg_l.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period
        avg_g.iloc[:period] = np.nan
        avg_l.iloc[:period] = np.nan
        rs = avg_g / avg_l.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    r_sma = rsi_sma_seed(btc["close"], 14)
    r_sma = r_sma.reindex(btc.index)

    print(f"  Using EWM-only (current):   prev={btc_rsi_30m.loc[prev_t]:.6f}, cur={btc_rsi_30m.loc[t_focus]:.6f}")
    print(f"  Using SMA-seeded Wilder's:  prev={r_sma.loc[prev_t]:.6f}, cur={r_sma.loc[t_focus]:.6f}")
    print(f"  SMA-seeded crossunder 52 = {r_sma.loc[prev_t] >= 52 and r_sma.loc[t_focus] < 52}")

    # ── 5. Check if the RSI filter "use_short_range" is being applied ────────
    # The strategy uses: use_short_range=True, short_range=[20, 52]
    # short entry fires when crossunder(rsi, 52) AND rsi was in [20..52]
    # Actually crossunder(rsi, 52) already implies rsi just crossed BELOW 52
    # So "rsi in range [20..52]" at crossunder time means rsi just went below 52
    # which means cur_rsi <= 52 (already satisfied by definition of crossunder)
    # and prev_rsi was >= 52 and now cur < 52
    # Maybe the range is applied to the PREVIOUS bar? Let's check all engine-only signals
    print("\n── Checking use_short_range=[20,52] filter on engine-only signals ──")
    print("  If TV also checks: rsi_prev MUST have been in [20..52] (not possible if >=52?)")
    print("  OR: after crossunder, TV checks if current rsi is in [20..52]")
    print()
    # Actually crossunder fires at bar where RSI just went below 52
    # After crossunder: cur_rsi < 52, so if range is [20..52], cur in range = cur>=20 AND cur<=52
    # cur < 52 by definition, so just need cur >= 20
    # Let's check: do any engine-only signals have cur_rsi < 20?
    print(f"  {'Time (UTC)':22s}  {'prev_RSI':8s}  {'cur_RSI':8s}  cur_in_[20,52]?")
    for ts in ENGINE_ONLY_SHORT:
        if ts not in btc_rsi_30m.index:
            continue
        cur_loc = btc_rsi_30m.index.get_loc(ts)
        cur_val = btc_rsi_30m.iloc[cur_loc]
        prev_val = btc_rsi_30m.iloc[cur_loc - 1]
        in_range = 20 <= cur_val <= 52
        print(f"  {str(ts)[:22]:22s}  {prev_val:8.4f}  {cur_val:8.4f}  {in_range!s}")

    # ── 6. Summary ─────────────────────────────────────────────────────────────
    print("\n══════════════════════════════════════════════════════════════")
    print("SUMMARY:")
    print(f"  TV-only signal (2026-02-01 10:00): our prev_rsi={btc_rsi_30m.loc[prev_t]:.4f}")
    print("  => prev_rsi < 52 means our BTC data shows NO crossunder at this bar")
    print("  => TV must have a slightly different BTC price => different RSI")
    print()
    print("  Engine fires 21 extra signals that TV does NOT fire.")
    print("  Check the 'use_short_range' filter — TV may apply it differently.")
    print("  If all engine-only signals have cur_rsi in [20,52], that's not the filter.")
    print("  Root cause is likely: TV uses a slightly different BTC close price stream")
    print("  (TV real-time feed vs Bybit REST API historical — different rounding/aggregation)")


asyncio.run(main())
