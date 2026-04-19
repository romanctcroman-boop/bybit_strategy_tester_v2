"""
backend/backtesting/formulas.py
================================
Единый источник истины для всех формул расчёта метрик бэктеста.

Принципы:
- Все функции — чистые (pure): только входные данные → результат, без side-effects
- Нет импортов из других модулей проекта (только numpy/math)
- TradingView-совместимость: Sharpe (monthly), Win Rate (0-1 fraction), комиссия 0.0007
- Используется как MetricsCalculator, так и NumbaEngineV2

Расхождения, которые устраняет этот модуль:
  | Формула       | metrics_calculator.py     | numba_engine_v2.py          |
  |---------------|---------------------------|-----------------------------|
  | win_rate      | (w/t)*100  (%)            | w/t  (доля 0-1)             |
  | profit_factor | min(100, gp/gl)           | gp/gl if gl>0 else 10.0     |
  | max_drawdown  | (peak-eq)/peak*100        | (peak-eq)/max(peak,1)*100   |
  | sharpe        | RFR-aware, ddof=1, clamp  | mean/std*sqrt(252*24), нет RFR|
  | sortino       | downside по всем N, MAR=0 | std(negative returns)       |
  | calmar        | CAGR-based, clip -100/100 | annual_return/max_dd        |

Решение: метрики_calculator.py является "золотым стандартом" (TV-паритет).
numba_engine_v2.py обновляется для использования функций из этого модуля.

Usage:
    from backend.backtesting.formulas import (
        calc_win_rate, calc_profit_factor, calc_max_drawdown,
        calc_sharpe, calc_sortino, calc_calmar, calc_cagr,
        calc_expectancy, calc_payoff_ratio, calc_recovery_factor,
    )
"""

from __future__ import annotations

import math

import numpy as np

__all__ = [
    "ANNUALIZATION_DAILY",
    "ANNUALIZATION_HOURLY",
    "calc_cagr",
    "calc_calmar",
    "calc_expectancy",
    "calc_max_drawdown",
    "calc_payoff_ratio",
    "calc_profit_factor",
    "calc_recovery_factor",
    "calc_returns_from_equity",
    "calc_sharpe",
    "calc_sharpe_monthly_tv",
    "calc_sortino",
    "calc_sortino_monthly_tv",
    "calc_sqn",
    "calc_ulcer_index",
    "calc_win_rate",
]

# =============================================================================
# КОНСТАНТЫ (не менять без согласования — влияет на TV-паритет)
# =============================================================================

# Число периодов в году для часовых баров (365.25 * 24)
ANNUALIZATION_HOURLY: float = 8766.0

# Число периодов в году для дневных баров
ANNUALIZATION_DAILY: float = 365.25

# Annualization factor для sqrt(N) в Sharpe/Sortino
_SQRT_ANNUAL_HOURLY: float = math.sqrt(ANNUALIZATION_HOURLY)
_SQRT_ANNUAL_DAILY: float = math.sqrt(ANNUALIZATION_DAILY)

# Клипование (избегаем экстремальных значений коэффициентов)
_RATIO_CLIP_MAX: float = 100.0
_RATIO_CLIP_MIN: float = -100.0


# =============================================================================
# УТИЛИТЫ
# =============================================================================


def calc_returns_from_equity(equity_curve: np.ndarray) -> np.ndarray:
    """
    Вычислить массив доходностей из кривой капитала.

    Formula:  r[i] = (equity[i] - equity[i-1]) / max(equity[i-1], 1)

    Args:
        equity_curve: Массив значений капитала (len >= 2)

    Returns:
        Массив доходностей длиной len(equity_curve) - 1.
        NaN/Inf заменяются на 0.
    """
    if len(equity_curve) < 2:
        return np.array([], dtype=np.float64)

    equity = np.asarray(equity_curve, dtype=np.float64)
    denom = np.maximum(equity[:-1], 1.0)
    returns = np.diff(equity) / denom
    return np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)


# =============================================================================
# БАЗОВЫЕ ТОРГОВЫЕ МЕТРИКИ
# =============================================================================


def calc_win_rate(winning_trades: int, total_trades: int) -> float:
    """
    Процент выигрышных сделок (TradingView-совместимый: 0–100).

    Formula: (winning_trades / total_trades) * 100

    Args:
        winning_trades: Количество прибыльных сделок
        total_trades:   Общее количество сделок

    Returns:
        Win rate в процентах [0.0, 100.0]

    Note:
        ⚠️ numba_engine_v2.py исторически возвращал долю 0-1.
        Эта функция всегда возвращает % (TV-стандарт).
    """
    if total_trades <= 0:
        return 0.0
    return (winning_trades / total_trades) * 100.0


def calc_profit_factor(gross_profit: float, gross_loss: float) -> float:
    """
    Profit Factor (TradingView-совместимый).

    Formula: gross_profit / gross_loss

    Args:
        gross_profit: Суммарная прибыль по выигрышным сделкам (>= 0)
        gross_loss:   |Суммарный убыток| по убыточным сделкам (>= 0)

    Returns:
        Profit Factor, клипован в [0.0, 100.0].
        0.0 если нет прибыли и нет убытка.

    Note:
        Клипование в 100.0 совместимо с TradingView (отображает "∞" как ~100).
    """
    if gross_loss <= 0:
        return 100.0 if gross_profit > 0 else 0.0
    return min(100.0, gross_profit / gross_loss)


def calc_payoff_ratio(avg_win: float, avg_loss: float) -> float:
    """
    Payoff Ratio (средняя прибыль / средний убыток).

    Formula: |avg_win / avg_loss|

    Args:
        avg_win:  Средняя прибыль по выигрышным сделкам (>= 0)
        avg_loss: Средний убыток по убыточным сделкам (<= 0 или >= 0 по модулю)

    Returns:
        Payoff ratio >= 0.0
    """
    loss_abs = abs(avg_loss)
    if loss_abs <= 1e-10:
        return 0.0
    return abs(avg_win) / loss_abs


def calc_expectancy(win_rate_pct: float, avg_win: float, avg_loss: float) -> float:
    """
    Математическое ожидание сделки (в единицах валюты).

    Formula: (win_rate/100) * avg_win + (1 - win_rate/100) * avg_loss

    Args:
        win_rate_pct: Win rate в процентах (0–100)
        avg_win:      Средняя прибыль по выигрышным сделкам
        avg_loss:     Средний убыток (отрицательное или положительное — знак учитывается)

    Returns:
        Ожидаемый P&L на сделку
    """
    wr = win_rate_pct / 100.0
    return wr * avg_win + (1.0 - wr) * avg_loss


# =============================================================================
# DRAWDOWN
# =============================================================================


def calc_max_drawdown(equity_curve: np.ndarray) -> tuple[float, float, int]:
    """
    Максимальная просадка по кривой капитала.

    Formula:
        peak[i] = max(equity[0..i])
        dd[i]   = (peak[i] - equity[i]) / peak[i]   (if peak[i] > 0)
        max_dd  = max(dd) * 100   (в процентах)

    Args:
        equity_curve: Массив значений капитала (len >= 2)

    Returns:
        Tuple[max_dd_pct, max_dd_value, max_dd_duration_bars]
        - max_dd_pct:           % просадки от пика (0–100)
        - max_dd_value:         абсолютная просадка в единицах валюты
        - max_dd_duration_bars: длительность просадки в барах

    Note:
        Защита от деления на 0: если peak == 0, dd = 0.
    """
    if len(equity_curve) < 2:
        return 0.0, 0.0, 0

    equity = np.asarray(equity_curve, dtype=np.float64)
    peak = np.maximum.accumulate(equity)

    # Безопасное деление: если peak == 0 (банкротство в начале), dd = 0
    with np.errstate(divide="ignore", invalid="ignore"):
        drawdown = np.where(peak > 0, (peak - equity) / peak, 0.0)

    max_dd_fraction = float(np.max(drawdown))
    max_dd_pct = max_dd_fraction * 100.0

    # Абсолютная просадка в точке максимальной %
    max_dd_idx = int(np.argmax(drawdown))
    max_dd_value = float(peak[max_dd_idx] - equity[max_dd_idx])

    # Длительность: от последнего нового максимума до точки max_dd
    peak_idx = max_dd_idx
    while peak_idx > 0 and equity[peak_idx] < peak[peak_idx]:
        peak_idx -= 1
    duration = max_dd_idx - peak_idx

    return max_dd_pct, max_dd_value, int(duration)


def calc_ulcer_index(equity_curve: np.ndarray) -> float:
    """
    Ulcer Index — мера "болезненности" просадок.

    Formula: sqrt( mean( ((peak - equity) / peak)^2 ) ) * 100

    Args:
        equity_curve: Массив значений капитала

    Returns:
        Ulcer Index в процентах (уже умножен на 100).
        Значение 0.0 если нет просадок.
    """
    if len(equity_curve) < 2:
        return 0.0

    equity = np.asarray(equity_curve, dtype=np.float64)
    peak = np.maximum.accumulate(equity)

    with np.errstate(divide="ignore", invalid="ignore"):
        drawdown_pct = np.where(peak > 0, (peak - equity) / peak, 0.0)

    mean_sq = float(np.mean(np.square(drawdown_pct)))
    return math.sqrt(mean_sq) * 100.0


# =============================================================================
# ДОХОДНОСТЬ
# =============================================================================


def calc_cagr(
    initial_capital: float,
    final_capital: float,
    years: float,
) -> float:
    """
    Compound Annual Growth Rate (CAGR).

    Formula: ((final / initial)^(1/years) - 1) * 100

    Для периодов < 30 дней (years < 0.082): простая годовая доходность,
    чтобы избежать экстремальных значений при коротких бэктестах.

    Args:
        initial_capital: Начальный капитал (> 0)
        final_capital:   Итоговый капитал
        years:           Длительность периода в годах

    Returns:
        CAGR в процентах, клипован в [-100, 200]
    """
    if initial_capital <= 0 or years <= 0:
        return 0.0

    total_return = (final_capital - initial_capital) / initial_capital

    if years < 0.082:  # < ~30 дней — простая аннуализация
        return float(np.clip(total_return / years * 100.0, -100.0, 200.0))

    if total_return <= -1.0:
        return -100.0

    cagr = (math.pow(1.0 + total_return, 1.0 / years) - 1.0) * 100.0
    return float(np.clip(cagr, -100.0, 200.0))


def calc_recovery_factor(net_profit: float, initial_capital: float, max_drawdown_pct: float) -> float:
    """
    Recovery Factor — отношение прибыли к абсолютной просадке.

    Formula: net_profit / (initial_capital * max_drawdown_pct / 100)

    Args:
        net_profit:       Чистая прибыль
        initial_capital:  Начальный капитал
        max_drawdown_pct: Максимальная просадка в процентах

    Returns:
        Recovery factor, 0.0 если max_drawdown == 0
    """
    if max_drawdown_pct <= 0 or initial_capital <= 0:
        return 0.0
    absolute_dd = initial_capital * max_drawdown_pct / 100.0
    if absolute_dd <= 1e-10:
        return 0.0
    return float(np.clip(net_profit / absolute_dd, _RATIO_CLIP_MIN, _RATIO_CLIP_MAX))


# =============================================================================
# RISK-ADJUSTED RATIOS
# =============================================================================


def calc_sharpe(
    returns: np.ndarray,
    annualization_factor: float = ANNUALIZATION_HOURLY,
    risk_free_rate: float = 0.02,
) -> float:
    """
    Sharpe Ratio (TradingView-совместимый).

    Formula:
        period_rfr = risk_free_rate / annualization_factor
        sharpe     = (mean(r) - period_rfr) / std(r, ddof=1) * sqrt(annualization_factor)

    Args:
        returns:              Массив периодических доходностей
        annualization_factor: Периодов в году (8766 для часовых, 365.25 для дневных)
        risk_free_rate:       Годовая безрисковая ставка (0.02 = 2%)

    Returns:
        Sharpe Ratio, клипован в [-100, 100].
        0.0 если std == 0 или len < 2.

    Note:
        Использует ddof=1 (выборочное стд. откл.) — совместимо с TV.
        Очень короткие серии (len < 24 при часовых) → нет аннуализации.
    """
    if len(returns) < 2:
        return 0.0

    arr = np.asarray(returns, dtype=np.float64)
    arr = arr[np.isfinite(arr)]

    if len(arr) < 2:
        return 0.0

    mean_r = float(np.mean(arr))
    std_r = float(np.std(arr, ddof=1))

    if std_r <= 1e-10:
        return 0.0

    # Для очень коротких серий: без аннуализации (raw ratio)
    if annualization_factor == ANNUALIZATION_HOURLY and len(arr) < 24:
        return float(np.clip(mean_r / std_r, _RATIO_CLIP_MIN, _RATIO_CLIP_MAX))

    period_rfr = risk_free_rate / annualization_factor
    sharpe = (mean_r - period_rfr) / std_r * math.sqrt(annualization_factor)
    return float(np.clip(sharpe, _RATIO_CLIP_MIN, _RATIO_CLIP_MAX))


def calc_sortino(
    returns: np.ndarray,
    annualization_factor: float = ANNUALIZATION_HOURLY,
    mar: float = 0.0,
) -> float:
    """
    Sortino Ratio (TradingView-совместимый).

    TradingView использует особый знаменатель:
        downside_variance = sum(min(0, r - mar)^2) / N   (делим на ВСЕ N, не только на убыточные)
        downside_dev      = sqrt(downside_variance)
        sortino           = (mean(r) - mar) / downside_dev * sqrt(annualization_factor)

    Args:
        returns:              Массив периодических доходностей
        annualization_factor: Периодов в году
        mar:                  Minimum Acceptable Return (обычно 0)

    Returns:
        Sortino Ratio, клипован в [-100, 100].
        100.0 если нет отрицательных отклонений и mean > mar (идеальная стратегия).
    """
    if len(returns) < 2:
        return 0.0

    arr = np.asarray(returns, dtype=np.float64)
    arr = arr[np.isfinite(arr)]

    if len(arr) < 2:
        return 0.0

    mean_r = float(np.mean(arr))
    negative_dev = np.minimum(0.0, arr - mar)
    downside_variance = float(np.sum(np.square(negative_dev))) / len(arr)
    downside_dev = math.sqrt(downside_variance)

    if downside_dev <= 1e-10:
        return 100.0 if mean_r > mar else 0.0

    sortino = (mean_r - mar) / downside_dev * math.sqrt(annualization_factor)
    return float(np.clip(sortino, _RATIO_CLIP_MIN, _RATIO_CLIP_MAX))


def calc_sharpe_monthly_tv(
    equity_curve: np.ndarray,
    timestamps: np.ndarray,
    initial_capital: float,
    risk_free_rate: float = 0.02,
    trades: list | None = None,
) -> float:
    """
    TradingView-совместимый Sharpe Ratio через МЕСЯЧНЫЕ доходности.

    TV формула (верифицировано 2026-02):
        1. Equity-based monthly returns: r_i = (eq_end_month_i - eq_start_month_i) / eq_start_month_i
           — TV использует relative equity returns, не pnl/initial_capital!
           Equity строится нарастающим итогом: initial_capital + cumsum(trade_pnl)
           Месяцы группируются по EXIT_TIME сделки.
        2. rfr_monthly = risk_free_rate / 12
        3. Sharpe = (mean(r) - rfr_monthly) / std(r, ddof=0)
           — TV использует POPULATION std (ddof=0), не ddof=1!
           — БЕЗ умножения на sqrt(12). TV не аннуализирует (оставляет monthly).

    Верифицировано (Strategy_MACD_01, 42 сделки, ETHUSDT 30m):
        - equity returns + ddof=0 → 0.9336 ≈ TV=0.934 ✅ (was: 0.914 with pnl/IC + ddof=1)

    Args:
        equity_curve:    Массив значений капитала (len == len(timestamps))
        timestamps:      Массив int64 unix-ms или pd.DatetimeIndex / np.ndarray datetime64
        initial_capital: Начальный капитал (> 0)
        risk_free_rate:  Годовая безрисковая ставка (0.02 = 2%)
        trades:          Список TradeRecord (preferred); если None, используется equity_curve

    Returns:
        Sharpe Ratio (monthly, не аннуализированный), клипован в [-100, 100].
        0.0 при недостаточном количестве месяцев (< 2).
    """
    if initial_capital <= 0:
        return 0.0

    if trades is not None:
        monthly_returns = _aggregate_monthly_equity_returns_from_trades(trades, initial_capital)
    else:
        if len(equity_curve) < 2:
            return 0.0
        monthly_returns = _aggregate_monthly_returns(equity_curve, timestamps, initial_capital)

    if len(monthly_returns) < 2:
        return 0.0

    m = np.asarray(monthly_returns, dtype=np.float64)
    mean_m = float(np.mean(m))
    std_m = float(np.std(m, ddof=0))  # TV uses population std (ddof=0)

    if std_m <= 1e-10:
        return 0.0

    rfr_monthly = risk_free_rate / 12.0
    sharpe = (mean_m - rfr_monthly) / std_m
    return float(np.clip(sharpe, _RATIO_CLIP_MIN, _RATIO_CLIP_MAX))


def calc_sortino_monthly_tv(
    equity_curve: np.ndarray,
    timestamps: np.ndarray,
    initial_capital: float,
    risk_free_rate: float = 0.02,
    trades: list | None = None,
) -> float:
    """
    TradingView-совместимый Sortino Ratio через МЕСЯЧНЫЕ доходности.

    TV формула (верифицировано 2026-02, Strategy_MACD_01, 42 сделки):
        1. Equity-based monthly returns (r_i = (eq_end - eq_start) / eq_start)
           — аналогично calc_sharpe_monthly_tv
        2. rfr_monthly = risk_free_rate / 12
        3. negative_dev = min(0, r - rfr_monthly) для каждого месяца
        4. downside_dev = sqrt( sum(negative_dev^2) / N )   # ddof=0 (population)!
        5. Sortino = (mean(r) - rfr_monthly) / downside_dev
           — БЕЗ умножения на sqrt(12).

    Верифицировано:
        - equity returns + ddof=0 → 4.1903 ≈ TV=4.19 ✅ (was: 4.14 with pnl/IC + ddof=1)

    Args:
        equity_curve:    Массив значений капитала
        timestamps:      Массив временных меток (unix-ms int64 или datetime64)
        initial_capital: Начальный капитал (> 0)
        risk_free_rate:  Годовая безрисковая ставка (0.02 = 2%)
        trades:          Список TradeRecord (preferred); если None, используется equity_curve

    Returns:
        Sortino Ratio (monthly, не аннуализированный), клипован в [-100, 100].
        0.0 при < 2 месяцев.
    """
    if initial_capital <= 0:
        return 0.0

    if trades is not None:
        monthly_returns = _aggregate_monthly_equity_returns_from_trades(trades, initial_capital)
    else:
        if len(equity_curve) < 2:
            return 0.0
        monthly_returns = _aggregate_monthly_returns(equity_curve, timestamps, initial_capital)

    if len(monthly_returns) < 2:
        return 0.0

    m = np.asarray(monthly_returns, dtype=np.float64)
    N = len(m)
    mean_m = float(np.mean(m))
    rfr_monthly = risk_free_rate / 12.0

    negative_dev = np.minimum(0.0, m - rfr_monthly)
    downside_variance = float(np.sum(np.square(negative_dev))) / N  # TV uses ddof=0 (population)
    downside_dev = math.sqrt(downside_variance)

    if downside_dev <= 1e-10:
        # No downside → perfect strategy
        return _RATIO_CLIP_MAX if mean_m > rfr_monthly else 0.0

    sortino = (mean_m - rfr_monthly) / downside_dev
    return float(np.clip(sortino, _RATIO_CLIP_MIN, _RATIO_CLIP_MAX))


def _aggregate_monthly_equity_returns_from_trades(
    trades: list,
    initial_capital: float,
) -> list[float]:
    """
    TV-совместимые equity-based monthly returns из закрытых сделок.

    TV формула (верифицировано 2026-02, Strategy_MACD_01, 42 сделки):
        1. Строим running equity: eq_0=initial_capital, eq_i = eq_{i-1} + pnl_i
           Сделки сортируются по EXIT_TIME.
        2. Группируем по (year, month) через EXIT_TIME:
           equity_month_start = equity перед первой сделкой месяца
           equity_month_end   = equity после последней сделки месяца
        3. monthly_return[i] = (equity_month_end - equity_month_start) / equity_month_start
           — RELATIVE return на старт-месяц, НЕ на initial_capital!
        4. Пустые месяцы (без сделок) = 0.0, equity_start = equity_end предыдущего.

    Это отличается от _aggregate_monthly_returns_from_trades который использует
    pnl / initial_capital. TV использует relative equity returns.

    Args:
        trades:          Список TradeRecord с полями exit_time и pnl
        initial_capital: Начальный капитал (> 0)

    Returns:
        Список месячных доходностей (fraction), отсортированных по (year, month).
        Пустые месяцы включены как 0.0.
    """
    import pandas as pd

    if not trades or initial_capital <= 0:
        return []

    # Sort trades by exit_time
    def get_exit_ts(trade: object) -> pd.Timestamp:
        et = getattr(trade, "exit_time", None) or getattr(trade, "entry_time", None)
        if et is None:
            return pd.Timestamp("2099-01-01", tz="UTC")
        ts = et if isinstance(et, pd.Timestamp) else pd.Timestamp(et)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts

    sorted_trades = sorted(trades, key=get_exit_ts)

    # Accumulate monthly PnL by exit_time
    monthly_pnl: dict[tuple[int, int], float] = {}
    first_month: tuple[int, int] | None = None
    last_month: tuple[int, int] | None = None

    for trade in sorted_trades:
        et = getattr(trade, "exit_time", None) or getattr(trade, "entry_time", None)
        pnl = float(getattr(trade, "pnl", 0.0))
        if et is None:
            continue

        ts = et if isinstance(et, pd.Timestamp) else pd.Timestamp(et)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")

        key = (int(ts.year), int(ts.month))
        monthly_pnl[key] = monthly_pnl.get(key, 0.0) + pnl

        if first_month is None or key < first_month:
            first_month = key
        if last_month is None or key > last_month:
            last_month = key

    if first_month is None or last_month is None:
        return []

    # Build running equity month-by-month
    result: list[float] = []
    running_equity = float(initial_capital)

    y, m = first_month
    while (y, m) <= last_month:
        key = (y, m)
        month_pnl = monthly_pnl.get(key, 0.0)
        eq_start = running_equity
        eq_end = running_equity + month_pnl
        running_equity = eq_end

        # Relative return: (end - start) / start
        r = (eq_end - eq_start) / eq_start if eq_start > 0.0 else 0.0
        result.append(r)

        m += 1
        if m > 12:
            m = 1
            y += 1

    return result


def _aggregate_monthly_returns_from_trades(
    trades: list,
    initial_capital: float,
) -> list[float]:
    """
    Агрегировать доходности по месяцам используя ЗАКРЫТЫЕ сделки (TradeRecord).

    TV-совместимый метод (верифицировано по CSV-экспорту TV):
        - Группирует PnL сделок по (year, month) EXIT_TIME  ← TV использует exit_time!
        - monthly_return[i] = sum_pnl_in_month[i] / initial_capital
        - Покрывает все месяцы от первой до последней сделки, включая пустые месяцы (0.0)

    ВАЖНО: TV bucket-ирует сделки по времени ЗАКРЫТИЯ (exit_time), а не открытия.
    Это подтверждено сравнением с TV CSV-экспортом (Strategy_MACD_01, 42 сделки):
        - By exit_time: Sharpe=0.914≈0.934, Sortino_H=4.14≈4.19 ✅
        - By entry_time: Sharpe=0.802, Sortino_H=1.63 ✗

    Формула Sortino (TV-верифицированная):
        Sortino = (mean - rfr/12) / sqrt( sum(min(0, r - rfr/12)^2) / N )

    Это вспомогательная функция; основной метод — _aggregate_monthly_equity_returns_from_trades.
    Оставлена для совместимости с equity_curve-based вызовами.

    Args:
        trades:          Список TradeRecord с полями exit_time и pnl
        initial_capital: Начальный капитал (> 0)

    Returns:
        Список месячных доходностей (fraction), отсортированных по (year, month).
        Пустые месяцы включены как 0.0.
    """
    import pandas as pd

    if not trades or initial_capital <= 0:
        return []

    # Accumulate PnL per month using EXIT_TIME (TV-verified: TV buckets by close date)
    monthly_pnl: dict[tuple[int, int], float] = {}
    first_month: tuple[int, int] | None = None
    last_month: tuple[int, int] | None = None

    for trade in trades:
        # Use exit_time (TV-parity). Fall back to entry_time if exit_time not available.
        et = getattr(trade, "exit_time", None) or getattr(trade, "entry_time", None)
        pnl = float(getattr(trade, "pnl", 0.0))
        if et is None:
            continue

        # Normalize to pd.Timestamp
        if isinstance(et, str):
            ts = pd.Timestamp(et)
        elif isinstance(et, pd.Timestamp):
            ts = et
        else:
            ts = pd.Timestamp(et)

        # Ensure UTC-aware for consistent month extraction
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")

        key = (int(ts.year), int(ts.month))
        monthly_pnl[key] = monthly_pnl.get(key, 0.0) + pnl

        if first_month is None or key < first_month:
            first_month = key
        if last_month is None or key > last_month:
            last_month = key

    if first_month is None or last_month is None:
        return []

    # Build full month range (include months with no trades as 0.0)
    result: list[float] = []
    y, m = first_month
    while (y, m) <= last_month:
        pnl = monthly_pnl.get((y, m), 0.0)
        result.append(pnl / initial_capital)
        m += 1
        if m > 12:
            m = 1
            y += 1

    return result


def _aggregate_monthly_returns(
    equity_curve: np.ndarray,
    timestamps: np.ndarray,
    initial_capital: float,
) -> list[float]:
    """
    Вспомогательная функция: агрегировать доходности по месяцам.

    Группирует бары по (year, month) и считает:
        monthly_return = (equity_end_of_month - equity_start_of_month) / equity_start_of_month

    Используется calc_sharpe_monthly_tv() и calc_sortino_monthly_tv().

    Args:
        equity_curve:    Массив значений капитала (len >= 2)
        timestamps:      Массив временных меток.
                         Поддерживаемые форматы:
                           - int64 unix-milliseconds
                           - np.datetime64
                           - pd.DatetimeIndex (передаётся как .values)
        initial_capital: Начальный капитал для нормирования

    Returns:
        Список месячных доходностей (fraction, не %).
        Пустой список если < 1 полного месяца.
    """
    import pandas as pd

    equity = np.asarray(equity_curve, dtype=np.float64)
    ts = timestamps

    # Convert timestamps to pandas DatetimeIndex for easy month extraction
    if hasattr(ts, "values"):
        # pd.DatetimeIndex or pd.Series
        ts_pd = pd.DatetimeIndex(ts.values)
    elif isinstance(ts, np.ndarray):
        if ts.dtype.kind == "M":  # datetime64
            ts_pd = pd.DatetimeIndex(ts)
        elif ts.dtype.kind in ("i", "u"):  # int (unix ms)
            ts_pd = pd.to_datetime(ts, unit="ms", utc=True)
        else:
            try:
                ts_pd = pd.DatetimeIndex(ts)
            except Exception:
                return []
    else:
        try:
            ts_pd = pd.DatetimeIndex(ts)
        except Exception:
            return []

    if len(ts_pd) != len(equity):
        return []

    # Group by (year, month) — use first equity value in month as start, last as end
    monthly_pnl: dict[tuple[int, int], float] = {}
    monthly_start: dict[tuple[int, int], float] = {}

    for i, (eq, ts_i) in enumerate(zip(equity, ts_pd, strict=True)):
        key = (int(ts_i.year), int(ts_i.month))
        if key not in monthly_start:
            monthly_start[key] = equity[i - 1] if i > 0 else initial_capital
        monthly_pnl[key] = float(eq)  # last equity value seen in this month

    monthly_returns: list[float] = []
    for key in sorted(monthly_pnl):
        start_eq = monthly_start[key]
        end_eq = monthly_pnl[key]
        monthly_returns.append((end_eq - start_eq) / start_eq if start_eq != 0 else 0.0)

    return monthly_returns


def calc_calmar(
    total_return_pct: float,
    max_drawdown_pct: float,
    years: float = 1.0,
) -> float:
    """
    Calmar Ratio.

    Formula: CAGR / |max_drawdown_pct|

    Для years <= 1: CAGR = total_return_pct (нет смысла применять CAGR для < 1 года).
    Для years > 1:  CAGR рассчитывается через compound formula.

    Args:
        total_return_pct: Общая доходность в % (за весь период)
        max_drawdown_pct: Максимальная просадка в % (> 0 для реальных просадок)
        years:            Длительность периода в годах

    Returns:
        Calmar Ratio, клипован в [-100, 100].
        Если max_drawdown_pct <= 1.0, возвращает 10.0 (нет значимой просадки).
    """
    if abs(max_drawdown_pct) <= 1.0:
        return 10.0 if total_return_pct > 0 else 0.0

    if years > 1.0:
        total_return_frac = total_return_pct / 100.0
        cagr = -100.0 if total_return_frac <= -1.0 else (math.pow(1.0 + total_return_frac, 1.0 / years) - 1.0) * 100.0
    else:
        cagr = total_return_pct

    return float(np.clip(cagr / abs(max_drawdown_pct), _RATIO_CLIP_MIN, _RATIO_CLIP_MAX))


def calc_sqn(trades_pnl: np.ndarray) -> float:
    """
    System Quality Number (Van K. Tharp).

    Formula: (mean(pnl) / std(pnl)) * sqrt(N)

    Args:
        trades_pnl: Массив P&L по каждой сделке

    Returns:
        SQN значение. Клипован в [-100, 100].
        0.0 если N < 2 или std == 0.

    Интерпретация:
        < 1.6: Плохая система
        1.6–1.9: Ниже среднего
        2.0–2.4: Средняя
        2.5–2.9: Хорошая
        3.0–5.0: Отличная
        > 5.0: Святой Грааль :)
    """
    if len(trades_pnl) < 2:
        return 0.0

    arr = np.asarray(trades_pnl, dtype=np.float64)
    arr = arr[np.isfinite(arr)]

    if len(arr) < 2:
        return 0.0

    std_pnl = float(np.std(arr, ddof=1))
    if std_pnl <= 1e-10:
        return 0.0

    sqn = float(np.mean(arr)) / std_pnl * math.sqrt(len(arr))
    return float(np.clip(sqn, _RATIO_CLIP_MIN, _RATIO_CLIP_MAX))
