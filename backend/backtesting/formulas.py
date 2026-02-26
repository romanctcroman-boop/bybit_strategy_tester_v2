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
    "calc_sortino",
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
