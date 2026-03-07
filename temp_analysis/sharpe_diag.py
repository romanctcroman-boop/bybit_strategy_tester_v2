"""
Диагностика расхождения Sharpe/Sortino с TradingView.
TV: Sharpe=0.939, Sortino=4.23
Наши: Sharpe=0.917, Sortino=4.161

Данные из z4.csv (44 сделки MACD_07 ETHUSDT 15m).
Тест: разные варианты якоря monthly equity.
"""

import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import numpy as np
import pandas as pd

# ── Реальные PnL по сделкам из z4.csv (TV export, уже net PnL) ──────────────
# exit_time, pnl
TRADES_RAW = [
    ("2025-01-04 23:45", 41.00),
    ("2025-01-11 07:30", 45.48),
    ("2025-01-13 21:00", -163.67),
    ("2025-01-17 06:15", 21.98),
    ("2025-01-19 09:30", 100.26),
    ("2025-01-21 13:15", 83.76),
    ("2025-01-24 11:15", -39.36),
    ("2025-01-24 17:30", -34.82),
    ("2025-01-25 01:15", 174.62),
    ("2025-01-25 07:15", -27.06),
    ("2025-01-25 09:30", 15.47),
    ("2025-01-27 06:45", 68.16),
    ("2025-01-27 12:30", -31.04),
    ("2025-01-30 15:45", 41.22),
    ("2025-02-02 04:30", -33.26),
    ("2025-02-03 05:00", 51.33),
    ("2025-02-07 10:45", 67.44),
    ("2025-02-09 08:15", -27.39),
    ("2025-02-09 21:15", 50.01),
    ("2025-02-12 05:45", 120.47),
    ("2025-02-14 06:00", -50.66),
    ("2025-02-17 20:00", 60.87),
    ("2025-02-18 10:45", 89.98),
    ("2025-02-19 12:45", 91.36),
    ("2025-02-19 20:00", -117.89),
    ("2025-02-21 04:30", 44.02),
    ("2025-02-21 17:15", -12.04),
    ("2025-02-24 00:00", 41.85),
    ("2025-02-26 14:00", 115.10),
    ("2025-03-05 13:15", -41.33),
    ("2025-04-07 16:00", 118.28),
    ("2025-04-09 01:15", 54.11),
    ("2025-04-09 19:30", 120.22),
    ("2025-04-11 08:30", 62.75),
    ("2025-04-12 08:45", 46.56),
    ("2025-04-15 10:00", -50.06),
    ("2025-04-17 18:30", 50.26),
    ("2025-04-28 08:00", 70.35),
    ("2025-05-06 09:15", 38.94),
    ("2025-06-04 19:00", 52.44),
    ("2025-08-27 09:30", 73.02),
    ("2025-09-23 14:00", 91.57),
    ("2025-11-26 23:30", 111.61),
    ("2026-03-05 18:30", 57.67),  # последняя закрытая сделка (если есть)
]

INITIAL_CAPITAL = 10000.0
RFR_ANNUAL = 0.02  # 2% годовых как в TV


def compute_sharpe_sortino(trades, anchor_method="month_before_first"):
    """
    anchor_method:
      'month_before_first' - якорь = конец месяца перед первым трейдом (текущий код)
      'start_of_first_month' - якорь = начало месяца первого трейда
      'floor_month_first' - якорь = первый день месяца первого трейда
      'no_anchor' - только monthly resample без якоря
      'open_first_month' - якорь = начало месяца первого трейда (как TV MonthStart)
    """
    _tc_times = []
    _tc_equity = []
    _cum_pnl = 0.0
    for ts_str, pnl in trades:
        _cum_pnl += pnl
        _tc_times.append(pd.Timestamp(ts_str))
        _tc_equity.append(INITIAL_CAPITAL + _cum_pnl)

    _tc_series = pd.Series(_tc_equity, index=pd.DatetimeIndex(_tc_times))
    _first_tc = _tc_series.index[0]

    if anchor_method == "month_before_first":
        # Текущий код: конец предыдущего месяца
        _anchor = pd.Series(
            [INITIAL_CAPITAL],
            index=[_first_tc - pd.offsets.MonthEnd(1)],
        )
        _combined = pd.concat([_anchor, _tc_series])
    elif anchor_method == "start_of_first_month":
        # Начало месяца первого трейда
        _anchor_ts = _first_tc.replace(day=1, hour=0, minute=0, second=0)
        _anchor = pd.Series([INITIAL_CAPITAL], index=[_anchor_ts])
        _combined = pd.concat([_anchor, _tc_series])
    elif anchor_method == "no_anchor":
        _combined = _tc_series
    elif anchor_method == "ms_before":
        # MonthStart перед первым трейдом
        _anchor_ts = _first_tc - pd.offsets.MonthBegin(1)
        _anchor = pd.Series([INITIAL_CAPITAL], index=[_anchor_ts])
        _combined = pd.concat([_anchor, _tc_series])

    _monthly_eq = _combined.resample("ME").last().ffill()
    _monthly_r = _monthly_eq.pct_change().dropna().values
    _rfr_m = RFR_ANNUAL / 12
    _N = len(_monthly_r)
    _mean = float(np.mean(_monthly_r))

    sharpe = sortino = 0.0
    _std0 = float(np.std(_monthly_r, ddof=0))
    if _std0 > 1e-10:
        sharpe = float(np.clip((_mean - _rfr_m) / _std0, -100, 100))

    _sneg = np.minimum(0.0, _monthly_r - _rfr_m)
    _sdd = float(np.sqrt(np.sum(_sneg**2) / _N))
    if _sdd > 1e-10:
        sortino = float(np.clip((_mean - _rfr_m) / _sdd, -100, 100))

    return sharpe, sortino, _N, _monthly_r, _monthly_eq


print("=" * 65)
print("TV:  Sharpe=0.939, Sortino=4.23")
print("=" * 65)

for method in ["month_before_first", "start_of_first_month", "ms_before", "no_anchor"]:
    s, so, N, mr, meq = compute_sharpe_sortino(TRADES_RAW, method)
    print(f"\nMethod: {method}")
    print(f"  N months = {N}")
    print(f"  Sharpe   = {s:.4f}  (diff TV: {s - 0.939:+.4f})")
    print(f"  Sortino  = {so:.4f}  (diff TV: {so - 4.23:+.4f})")
    print(f"  Monthly eq range: {meq.index[0].date()} → {meq.index[-1].date()}")
    print(f"  Monthly returns: {[round(r * 100, 2) for r in mr[:5]]}...")
