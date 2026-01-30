"""
🎯 FALLBACK ENGINE V4 - Эталонный движок с Multi-level TP и ATR

Расширение V3 с дополнительными функциями:
- Multi-level TP (TP1, TP2, TP3, TP4) с частичным закрытием
- ATR-based TP/SL (динамические уровни на основе волатильности)
- Trailing Stop с активацией
- Полная совместимость с DCA (Safety Orders)

Скорость: ~1x (базовая, эталон для верификации)
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from backend.backtesting.atr_calculator import calculate_atr_fast
from backend.backtesting.interfaces import (
    BacktestInput,
    BacktestMetrics,
    BacktestOutput,
    BaseBacktestEngine,
    ExitReason,
    TradeDirection,
    TradeRecord,
)
from backend.backtesting.pyramiding import PyramidingManager


@dataclass
class MultiTPState:
    """Состояние Multi-level TP для одной позиции."""

    # Какие уровни TP уже сработали
    tp_hit: List[bool] = field(default_factory=lambda: [False, False, False, False])

    # Цены уровней TP (рассчитываются при входе)
    tp_prices: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])

    # Доли для каждого уровня
    tp_portions: Tuple[float, ...] = (0.25, 0.25, 0.25, 0.25)

    def reset(self):
        """Сброс состояния при закрытии позиции."""
        self.tp_hit = [False, False, False, False]
        self.tp_prices = [0.0, 0.0, 0.0, 0.0]

    def set_prices(self, prices: List[float], portions: Tuple[float, ...]):
        """Установить цены TP при открытии позиции."""
        self.tp_prices = prices[:4] if len(prices) >= 4 else prices + [0.0] * (4 - len(prices))
        self.tp_portions = portions
        self.tp_hit = [False] * len(self.tp_prices)

    def get_next_tp_level(self) -> Optional[int]:
        """Получить индекс следующего несработавшего TP."""
        for i, hit in enumerate(self.tp_hit):
            if not hit and self.tp_prices[i] > 0:
                return i
        return None

    def mark_hit(self, level: int) -> float:
        """Отметить TP как сработавший, вернуть долю закрытия."""
        if level < len(self.tp_hit):
            self.tp_hit[level] = True
            return self.tp_portions[level] if level < len(self.tp_portions) else 0.0
        return 0.0

    def all_hit(self) -> bool:
        """Все ли TP сработали."""
        return all(self.tp_hit)


@dataclass
class TrailingStopState:
    """Состояние Trailing Stop для позиции."""

    activated: bool = False
    highest_price: float = 0.0  # Для LONG
    lowest_price: float = float("inf")  # Для SHORT
    trailing_stop_price: float = 0.0

    def reset(self):
        """Сброс при закрытии позиции."""
        self.activated = False
        self.highest_price = 0.0
        self.lowest_price = float("inf")
        self.trailing_stop_price = 0.0

    def update_long(
        self,
        high_price: float,
        entry_price: float,
        activation_pct: float,
        distance_pct: float,
    ) -> Optional[float]:
        """
        Обновить trailing stop для LONG.

        Returns:
            Цена срабатывания trailing stop или None если не активирован
        """
        # Проверить активацию
        profit_pct = (high_price - entry_price) / entry_price
        if profit_pct >= activation_pct:
            self.activated = True

        if not self.activated:
            return None

        # Обновить максимум
        if high_price > self.highest_price:
            self.highest_price = high_price
            self.trailing_stop_price = self.highest_price * (1 - distance_pct)

        return self.trailing_stop_price

    def update_short(
        self,
        low_price: float,
        entry_price: float,
        activation_pct: float,
        distance_pct: float,
    ) -> Optional[float]:
        """
        Обновить trailing stop для SHORT.

        Returns:
            Цена срабатывания trailing stop или None если не активирован
        """
        # Проверить активацию
        profit_pct = (entry_price - low_price) / entry_price
        if profit_pct >= activation_pct:
            self.activated = True

        if not self.activated:
            return None

        # Обновить минимум
        if low_price < self.lowest_price:
            self.lowest_price = low_price
            self.trailing_stop_price = self.lowest_price * (1 + distance_pct)

        return self.trailing_stop_price


@dataclass
class BreakevenState:
    """
    Состояние Breakeven SL (стоп в безубыток) для позиции.

    После срабатывания первого TP, SL переносится:
    - mode="average": на среднюю цену входа + offset
    - mode="tp": на цену предыдущего сработавшего TP
    """

    enabled: bool = False  # Активирован ли breakeven
    current_sl_price: float = 0.0  # Текущая цена SL (0 = использовать базовый SL)
    last_tp_price: float = 0.0  # Цена последнего сработавшего TP
    tp_count: int = 0  # Количество сработавших TP

    def reset(self):
        """Сброс при закрытии позиции."""
        self.enabled = False
        self.current_sl_price = 0.0
        self.last_tp_price = 0.0
        self.tp_count = 0

    def activate_on_tp(
        self,
        direction: str,
        avg_entry_price: float,
        tp_price: float,
        mode: str,
        offset: float,
    ):
        """
        Активировать/обновить breakeven при срабатывании TP.

        Args:
            direction: "long" или "short"
            avg_entry_price: Средняя цена входа
            tp_price: Цена сработавшего TP
            mode: "average" или "tp"
            offset: Отступ от безубытка (0.001 = +0.1%)
        """
        self.tp_count += 1

        if self.tp_count == 1:
            # Первый TP - SL переносится на среднюю цену
            self.enabled = True
            if direction == "long":
                self.current_sl_price = avg_entry_price * (1 + offset)
            else:
                self.current_sl_price = avg_entry_price * (1 - offset)
        else:
            # Последующие TP - SL на предыдущий TP (если mode="tp")
            if mode == "tp" and self.last_tp_price > 0:
                self.current_sl_price = self.last_tp_price

        self.last_tp_price = tp_price

    def get_sl_price(self) -> Optional[float]:
        """Получить текущую цену SL (или None если breakeven не активен)."""
        if self.enabled and self.current_sl_price > 0:
            return self.current_sl_price
        return None


class AdaptiveATRMultiplier:
    """
    Адаптивный множитель ATR на основе volatility regime.

    Идея: В периоды низкой волатильности используем бОльший множитель (шире SL/TP),
    в периоды высокой волатильности - меньший множитель (уже SL/TP).

    Режимы:
    - LOW (percentile < 25): mult * 1.5 (шире SL, даём больше пространства)
    - NORMAL (25-75 percentile): mult * 1.0 (стандартный)
    - HIGH (percentile > 75): mult * 0.7 (уже SL, фиксируем раньше)
    """

    def __init__(self, lookback: int = 100):
        self.lookback = lookback
        self.atr_history: List[float] = []

    def update(self, atr_value: float) -> None:
        """Добавить новое значение ATR в историю."""
        if atr_value > 0 and not np.isnan(atr_value):
            self.atr_history.append(atr_value)
            # Храним только последние N значений
            if len(self.atr_history) > self.lookback:
                self.atr_history = self.atr_history[-self.lookback :]

    def get_regime(self) -> str:
        """Определить текущий volatility regime."""
        if len(self.atr_history) < self.lookback // 2:
            return "normal"  # Недостаточно данных

        current_atr = self.atr_history[-1]
        percentile = self._get_percentile(current_atr)

        if percentile < 25:
            return "low"
        elif percentile > 75:
            return "high"
        return "normal"

    def get_multiplier(self, base_mult: float = 1.0) -> float:
        """
        Получить адаптивный множитель ATR.

        Args:
            base_mult: Базовый множитель (например, 2.0 для SL)

        Returns:
            Адаптированный множитель
        """
        regime = self.get_regime()

        if regime == "low":
            # Низкая волатильность -> шире SL/TP
            return base_mult * 1.5
        elif regime == "high":
            # Высокая волатильность -> уже SL/TP
            return base_mult * 0.7
        return base_mult  # Normal

    def _get_percentile(self, value: float) -> float:
        """Получить percentile значения в истории."""
        if not self.atr_history:
            return 50.0
        count_below = sum(1 for v in self.atr_history if v < value)
        return (count_below / len(self.atr_history)) * 100

    def reset(self) -> None:
        """Сброс истории."""
        self.atr_history = []


class MarketRegimeDetector:
    """
    Детектор рыночного режима.

    Определяет текущий режим рынка на основе:
    1. Hurst Exponent (тренд vs mean-reversion)
    2. Volatility regime (high/normal/low)
    3. Volume anomaly (z-score)

    Режимы:
    - TRENDING: Hurst > 0.55 (устойчивый тренд)
    - RANGING: Hurst < 0.45 (mean-reversion, боковик)
    - VOLATILE: ATR percentile > 80
    - NORMAL: всё остальное
    """

    def __init__(self, lookback: int = 50):
        self.lookback = lookback
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.atr_history: List[float] = []

    def update(self, close_price: float, volume: float = 0.0, atr: float = 0.0) -> None:
        """Добавить новые данные."""
        if close_price > 0:
            self.price_history.append(close_price)
            if len(self.price_history) > self.lookback * 2:
                self.price_history = self.price_history[-self.lookback * 2 :]

        if volume > 0:
            self.volume_history.append(volume)
            if len(self.volume_history) > self.lookback:
                self.volume_history = self.volume_history[-self.lookback :]

        if atr > 0 and not np.isnan(atr):
            self.atr_history.append(atr)
            if len(self.atr_history) > self.lookback:
                self.atr_history = self.atr_history[-self.lookback :]

    def get_regime(self) -> Dict[str, Any]:
        """
        Определить текущий рыночный режим.

        Returns:
            Dict с информацией о режиме:
            - regime: "trending" | "ranging" | "volatile" | "normal"
            - hurst: float (0-1)
            - volatility_percentile: float (0-100)
            - volume_zscore: float
        """
        if len(self.price_history) < self.lookback:
            return {
                "regime": "normal",
                "hurst": 0.5,
                "volatility_percentile": 50.0,
                "volume_zscore": 0.0,
            }

        # 1. Calculate Hurst Exponent (simplified R/S method)
        hurst = self._calculate_hurst()

        # 2. Volatility percentile
        vol_percentile = self._get_volatility_percentile()

        # 3. Volume z-score
        vol_zscore = self._get_volume_zscore()

        # Determine regime
        if vol_percentile > 80:
            regime = "volatile"
        elif hurst > 0.55:
            regime = "trending"
        elif hurst < 0.45:
            regime = "ranging"
        else:
            regime = "normal"

        return {
            "regime": regime,
            "hurst": hurst,
            "volatility_percentile": vol_percentile,
            "volume_zscore": vol_zscore,
        }

    def _calculate_hurst(self) -> float:
        """
        Simplified Hurst Exponent calculation using R/S method.
        H > 0.5 = trending (persistent)
        H < 0.5 = mean-reverting (anti-persistent)
        H = 0.5 = random walk
        """
        if len(self.price_history) < self.lookback:
            return 0.5

        prices = np.array(self.price_history[-self.lookback :])
        returns = np.diff(np.log(prices))

        if len(returns) < 10:
            return 0.5

        # R/S analysis
        try:
            n = len(returns)
            mean_return = np.mean(returns)
            deviations = returns - mean_return
            cumulative_deviations = np.cumsum(deviations)

            R: float = float(np.max(cumulative_deviations) - np.min(cumulative_deviations))
            S = np.std(returns)

            if S == 0:
                return 0.5

            RS = R / S

            # Estimate Hurst: E[R/S] ~ c * n^H
            # For simple estimate, use log(RS) / log(n)
            # But we'll use a more stable approximation
            if RS > 0 and n > 0:
                # Simplified: H ≈ log(RS) / log(n) for large n
                # With adjustment for small samples
                H = np.log(RS) / np.log(n) * 0.7 + 0.15
                return float(np.clip(H, 0, 1))
        except (ValueError, ZeroDivisionError):
            pass

        return 0.5

    def _get_volatility_percentile(self) -> float:
        """Get current ATR percentile."""
        if len(self.atr_history) < 2:
            return 50.0

        current_atr = self.atr_history[-1]
        count_below = sum(1 for v in self.atr_history[:-1] if v < current_atr)
        return (count_below / (len(self.atr_history) - 1)) * 100

    def _get_volume_zscore(self) -> float:
        """Get current volume z-score."""
        if len(self.volume_history) < 2:
            return 0.0

        current_vol = self.volume_history[-1]
        mean_vol = np.mean(self.volume_history[:-1])
        std_vol = np.std(self.volume_history[:-1])

        if std_vol == 0:
            return 0.0

        return float((current_vol - mean_vol) / std_vol)

    def should_trade(self, regime_filter: str = "all") -> bool:
        """
        Проверить, разрешена ли торговля в текущем режиме.

        Args:
            regime_filter: "all" | "trending" | "ranging" | "volatile" | "not_volatile"
        """
        regime_info = self.get_regime()
        current_regime: str = regime_info["regime"]

        if regime_filter == "all":
            return True
        elif regime_filter == "not_volatile":
            return bool(current_regime != "volatile")
        else:
            return bool(current_regime == regime_filter)

    def reset(self) -> None:
        """Сброс истории."""
        self.price_history = []
        self.volume_history = []
        self.atr_history = []


class DirectionHandler:
    """
    Обработчик направления для унификации Long/Short логики.
    Позволяет избежать дублирования кода для разных направлений.
    """

    @staticmethod
    def get_entry_price_with_slippage(close_price: float, slippage: float, direction: str) -> float:
        """
        Рассчитать цену входа с учётом slippage.
        LONG: покупаем дороже (+ slippage)
        SHORT: продаём дешевле (- slippage)
        """
        if direction == "long":
            return close_price * (1 + slippage)
        else:
            return close_price * (1 - slippage)

    @staticmethod
    def get_exit_price_with_slippage(close_price: float, slippage: float, direction: str) -> float:
        """
        Рассчитать цену выхода с учётом slippage.
        LONG: продаём дешевле (- slippage)
        SHORT: покупаем дороже (+ slippage)
        """
        if direction == "long":
            return close_price * (1 - slippage)
        else:
            return close_price * (1 + slippage)

    @staticmethod
    def check_tp_hit(high_price: float, low_price: float, tp_price: float, direction: str) -> bool:
        """Проверить срабатывание Take Profit."""
        if direction == "long":
            return high_price >= tp_price
        else:
            return low_price <= tp_price

    @staticmethod
    def check_sl_hit(high_price: float, low_price: float, sl_price: float, direction: str) -> bool:
        """Проверить срабатывание Stop Loss."""
        if direction == "long":
            return low_price <= sl_price
        else:
            return high_price >= sl_price

    @staticmethod
    def calculate_tp_price(entry_price: float, take_profit_pct: float, direction: str) -> float:
        """Рассчитать цену Take Profit."""
        if direction == "long":
            return entry_price * (1 + take_profit_pct)
        else:
            return entry_price * (1 - take_profit_pct)

    @staticmethod
    def calculate_sl_price(entry_price: float, stop_loss_pct: float, direction: str) -> float:
        """Рассчитать цену Stop Loss."""
        if direction == "long":
            return entry_price * (1 - stop_loss_pct)
        else:
            return entry_price * (1 + stop_loss_pct)

    @staticmethod
    def calculate_unrealized_pnl(entry_price: float, current_price: float, size: float, direction: str) -> float:
        """Рассчитать нереализованный PnL."""
        if direction == "long":
            return size * (current_price - entry_price)
        else:
            return size * (entry_price - current_price)

    @staticmethod
    def calculate_mfe(
        entry_price: float,
        high_price: float,
        low_price: float,
        size: float,
        direction: str,
    ) -> float:
        """
        Рассчитать MFE (Maximum Favorable Excursion).
        LONG: (high - entry) * size
        SHORT: (entry - low) * size
        """
        if direction == "long":
            return max(0, (high_price - entry_price) * size)
        else:
            return max(0, (entry_price - low_price) * size)

    @staticmethod
    def calculate_mae(
        entry_price: float,
        high_price: float,
        low_price: float,
        size: float,
        direction: str,
    ) -> float:
        """
        Рассчитать MAE (Maximum Adverse Excursion).
        LONG: (entry - low) * size
        SHORT: (high - entry) * size
        """
        if direction == "long":
            return max(0, (entry_price - low_price) * size)
        else:
            return max(0, (high_price - entry_price) * size)

    @staticmethod
    def check_trailing_activation(price: float, entry_price: float, activation_pct: float, direction: str) -> bool:
        """Проверить активацию trailing stop."""
        if direction == "long":
            profit_pct = (price - entry_price) / entry_price
        else:
            profit_pct = (entry_price - price) / entry_price
        return profit_pct >= activation_pct

    @staticmethod
    def update_trailing_stop(current_extreme: float, best_extreme: float, distance_pct: float, direction: str) -> tuple:
        """
        Обновить trailing stop.
        Returns: (new_best_extreme, trailing_stop_price)
        """
        if direction == "long":
            new_best = max(current_extreme, best_extreme)
            trailing_stop = new_best * (1 - distance_pct)
        else:
            new_best = min(current_extreme, best_extreme) if best_extreme != float("inf") else current_extreme
            trailing_stop = new_best * (1 + distance_pct)
        return new_best, trailing_stop


class FallbackEngineV4(BaseBacktestEngine):
    """
    Fallback Engine V4 - Эталонный движок с расширенными функциями.

    Новые возможности:
    - Multi-level TP (TP1-TP4) с частичным закрытием
    - ATR-based TP/SL
    - Trailing Stop с активацией
    - Полная совместимость с DCA/Pyramiding
    - Time-Based Exits
    - Advanced Position Sizing (Risk-based, Kelly, Volatility)
    - Re-entry Rules
    - Limit/Stop Orders
    - Scale-In
    - Dynamic Slippage Models
    - Funding Rate Calculations
    """

    @property
    def name(self) -> str:
        return "FallbackEngineV4"

    @property
    def supports_bar_magnifier(self) -> bool:
        return True

    @property
    def supports_parallel(self) -> bool:
        return False

    @property
    def supports_pyramiding(self) -> bool:
        return True

    def _calculate_slippage(
        self,
        base_slippage: float,
        slippage_model: str,
        volume: float = 0.0,
        atr: float = 0.0,
        avg_volume: float = 1.0,
        price: float = 0.0,
        volume_impact: float = 0.1,
        volatility_mult: float = 0.5,
    ) -> float:
        """
        Рассчитать динамический slippage по модели.

        Args:
            base_slippage: Базовый slippage (фиксированный %)
            slippage_model: "fixed", "volume", "volatility", "combined"
            volume: Объём текущей свечи
            atr: ATR для волатильности
            avg_volume: Средний объём
            price: Текущая цена
            volume_impact: Коэффициент влияния объёма
            volatility_mult: Множитель волатильности

        Returns:
            Итоговый slippage в %
        """
        if slippage_model == "fixed":
            return base_slippage

        elif slippage_model == "volume":
            # Большой объём = больший slippage (market impact)
            if avg_volume > 0 and volume > 0:
                volume_ratio = volume / avg_volume
                return base_slippage * (1 + volume_impact * (volume_ratio - 1))
            return base_slippage

        elif slippage_model == "volatility":
            # Высокая волатильность = больший slippage
            if atr > 0 and price > 0:
                atr_pct = atr / price
                return base_slippage + (atr_pct * volatility_mult)
            return base_slippage

        elif slippage_model == "combined":
            # Комбинация volume + volatility
            result = base_slippage
            if avg_volume > 0 and volume > 0:
                volume_ratio = volume / avg_volume
                result *= 1 + volume_impact * (volume_ratio - 1)
            if atr > 0 and price > 0:
                atr_pct = atr / price
                result += atr_pct * volatility_mult
            return result

        return base_slippage

    def _calculate_funding_fee(
        self,
        position_value: float,
        funding_rate: float,
        hours_in_position: float,
        funding_interval_hours: float,
    ) -> float:
        """
        Рассчитать комиссию за финансирование (Funding Fee).

        Funding выплачивается каждые N часов. Если позиция
        держалась дольше интервала - начисляется funding.

        Args:
            position_value: Стоимость позиции (notional)
            funding_rate: Ставка funding (напр. 0.0001 = 0.01%)
            hours_in_position: Сколько часов в позиции
            funding_interval_hours: Интервал funding (8 часов по умолчанию)

        Returns:
            Сумма funding fee (может быть отрицательной = получаем)
        """
        if funding_interval_hours <= 0:
            return 0.0

        # Количество funding intervals за время удержания позиции
        num_fundings = int(hours_in_position / funding_interval_hours)

        if num_fundings <= 0:
            return 0.0

        # Funding fee = position_value * funding_rate * num_intervals
        return position_value * funding_rate * num_fundings

    def _calculate_position_size_dynamic(
        self,
        mode: str,
        capital: float,
        price: float,
        stop_loss_pct: float,
        atr: float,
        risk_per_trade: float,
        kelly_fraction: float,
        volatility_target: float,
        win_rate: float = 0.5,
        avg_win_loss_ratio: float = 1.5,
        leverage: float = 1.0,
        min_size: float = 0.01,
        max_size: float = 1.0,
    ) -> float:
        """
        Рассчитать размер позиции по выбранному методу.

        Args:
            mode: "fixed", "risk", "kelly", "volatility"
            capital: Текущий капитал
            price: Цена входа
            stop_loss_pct: % до стоп-лосса
            atr: ATR для volatility sizing
            risk_per_trade: Риск на сделку (0.01 = 1%)
            kelly_fraction: Доля от Kelly (0.5 = half-Kelly)
            volatility_target: Целевая волатильность (0.02 = 2%)
            win_rate: Винрейт для Kelly (0.5 = 50%)
            avg_win_loss_ratio: Соотношение win/loss для Kelly
            leverage: Плечо
            min_size: Минимальный размер позиции
            max_size: Максимальный размер позиции

        Returns:
            Размер позиции как доля от капитала (0.0 - 1.0)
        """
        if mode == "fixed":
            return max(min_size, min(max_size, 1.0))

        elif mode == "risk":
            # Риск-ориентированный: position_size = risk / stop_loss
            if stop_loss_pct > 0:
                size = risk_per_trade / stop_loss_pct
            else:
                size = risk_per_trade  # fallback
            return max(min_size, min(max_size, size))

        elif mode == "kelly":
            # Kelly Criterion: f* = (p * b - q) / b
            # p = win_rate, q = 1 - p, b = avg_win_loss_ratio
            if avg_win_loss_ratio > 0:
                kelly = (win_rate * avg_win_loss_ratio - (1 - win_rate)) / avg_win_loss_ratio
                kelly = max(0, kelly)  # Не может быть отрицательным
                size = kelly * kelly_fraction  # Используем fractional Kelly
            else:
                size = risk_per_trade
            return max(min_size, min(max_size, size))

        elif mode == "volatility":
            # Volatility targeting: position_size = target_vol / actual_vol
            if atr > 0 and price > 0:
                actual_vol = atr / price  # Дневная волатильность
                size = volatility_target / actual_vol
            else:
                size = risk_per_trade
            return max(min_size, min(max_size, size))

        return max(min_size, min(max_size, 1.0))

    def run(self, input_data: BacktestInput) -> BacktestOutput:
        """
        Запуск бэктеста с расширенными функциями TP/SL.
        """
        start_time = time.time()

        # Валидация
        is_valid, errors = self.validate_input(input_data)
        if not is_valid:
            return BacktestOutput(
                is_valid=False,
                validation_errors=errors,
                engine_name=self.name,
            )

        # Подготовка данных
        candles = input_data.candles
        candles_1m = input_data.candles_1m
        n = len(candles)

        # Извлечение OHLC
        open_prices = candles["open"].values.astype(np.float64)
        high_prices = candles["high"].values.astype(np.float64)
        low_prices = candles["low"].values.astype(np.float64)
        close_prices = candles["close"].values.astype(np.float64)

        # Timestamps
        if isinstance(candles.index, pd.DatetimeIndex):
            timestamps = candles.index.to_numpy()
        else:
            timestamps = pd.to_datetime(candles.index).to_numpy()

        # Сигналы
        long_entries = input_data.long_entries if input_data.long_entries is not None else np.zeros(n, dtype=bool)
        long_exits = input_data.long_exits if input_data.long_exits is not None else np.zeros(n, dtype=bool)
        short_entries = input_data.short_entries if input_data.short_entries is not None else np.zeros(n, dtype=bool)
        short_exits = input_data.short_exits if input_data.short_exits is not None else np.zeros(n, dtype=bool)

        # === БАЗОВЫЕ ПАРАМЕТРЫ ===
        capital = input_data.initial_capital
        position_size = input_data.position_size
        use_fixed_amount = input_data.use_fixed_amount
        fixed_amount = input_data.fixed_amount
        leverage = input_data.leverage
        stop_loss = input_data.stop_loss
        take_profit = input_data.take_profit
        taker_fee = input_data.taker_fee
        slippage = input_data.slippage
        direction = input_data.direction
        use_bar_magnifier = input_data.use_bar_magnifier and candles_1m is not None

        # Пирамидинг
        pyramiding = input_data.pyramiding
        close_entries_rule = getattr(input_data, "close_entries_rule", "ALL")

        # === РЕЖИМЫ ВЫХОДА (НОВАЯ СИСТЕМА) ===
        # Импортируем Enum'ы если доступны
        try:
            from backend.backtesting.interfaces import SlMode, TpMode

            tp_mode, sl_mode = input_data.get_effective_modes()
            sl_max_limit = getattr(input_data, "sl_max_limit_enabled", True)
        except (ImportError, AttributeError):
            # Fallback для legacy кода
            from enum import Enum

            class TpMode(Enum):  # type: ignore[no-redef]
                FIXED = "fixed"
                ATR = "atr"
                MULTI = "multi"

            class SlMode(Enum):  # type: ignore[no-redef]
                FIXED = "fixed"
                ATR = "atr"

            tp_mode = TpMode.FIXED
            sl_mode = SlMode.FIXED
            sl_max_limit = True

        # === LEGACY COMPATIBILITY ===
        # Если используются старые флаги, преобразуем их
        multi_tp_enabled = getattr(input_data, "multi_tp_enabled", False)
        atr_enabled = getattr(input_data, "atr_enabled", False)

        if multi_tp_enabled and tp_mode == TpMode.FIXED:
            tp_mode = TpMode.MULTI
        if atr_enabled:
            if tp_mode == TpMode.FIXED and not multi_tp_enabled:
                tp_mode = TpMode.ATR
            if sl_mode == SlMode.FIXED:
                sl_mode = SlMode.ATR

        # === MULTI-LEVEL TP (tp_mode=MULTI) ===
        tp_levels = getattr(input_data, "tp_levels", (0.005, 0.010, 0.015, 0.020))
        tp_portions = getattr(input_data, "tp_portions", (0.25, 0.25, 0.25, 0.25))

        # === ATR ПАРАМЕТРЫ ===
        atr_period = getattr(input_data, "atr_period", 14)
        atr_tp_multiplier = getattr(input_data, "atr_tp_multiplier", 2.0)
        atr_sl_multiplier = getattr(input_data, "atr_sl_multiplier", 1.5)
        adaptive_atr_enabled = getattr(input_data, "adaptive_atr_enabled", False)
        adaptive_atr_lookback = getattr(input_data, "adaptive_atr_lookback", 100)

        # Предрасчитать ATR если используется
        atr_values = None
        if tp_mode == TpMode.ATR or sl_mode == SlMode.ATR:
            atr_values = calculate_atr_fast(high_prices, low_prices, close_prices, atr_period)

        # Инициализировать Adaptive ATR Multiplier если включён
        adaptive_atr = AdaptiveATRMultiplier(lookback=adaptive_atr_lookback) if adaptive_atr_enabled else None

        # === TRAILING STOP ===
        trailing_stop_enabled = getattr(input_data, "trailing_stop_enabled", False)
        trailing_activation = getattr(input_data, "trailing_stop_activation", 0.01)
        trailing_distance = getattr(input_data, "trailing_stop_distance", 0.005)

        # === BREAKEVEN STOP ===
        breakeven_enabled = getattr(input_data, "breakeven_enabled", False)
        breakeven_mode = getattr(input_data, "breakeven_mode", "average")
        breakeven_offset = getattr(input_data, "breakeven_offset", 0.0)

        # === DCA ПАРАМЕТРЫ ===
        dca_enabled = getattr(input_data, "dca_enabled", False)
        dca_safety_orders = getattr(input_data, "dca_safety_orders", 0)
        dca_price_deviation = getattr(input_data, "dca_price_deviation", 0.01)
        dca_step_scale = getattr(input_data, "dca_step_scale", 1.4)
        dca_volume_scale = getattr(input_data, "dca_volume_scale", 1.0)
        dca_base_order_size = getattr(input_data, "dca_base_order_size", 0.1)
        dca_safety_order_size = getattr(input_data, "dca_safety_order_size", 0.1)

        # === TIME-BASED EXITS ===
        max_bars_in_trade = getattr(input_data, "max_bars_in_trade", 0)
        exit_on_session_close = getattr(input_data, "exit_on_session_close", False)
        session_start_hour = getattr(input_data, "session_start_hour", 0)  # noqa: F841
        session_end_hour = getattr(input_data, "session_end_hour", 24)
        no_trade_days = getattr(input_data, "no_trade_days", ())
        no_trade_hours = getattr(input_data, "no_trade_hours", ())
        exit_end_of_week = getattr(input_data, "exit_end_of_week", False)
        exit_before_weekend = getattr(input_data, "exit_before_weekend", 0)
        # Timezone for time filters (e.g., "UTC", "US/Eastern", "Europe/London", "Asia/Tokyo")
        timezone_str = getattr(input_data, "timezone", "UTC")

        # === POSITION SIZING ===
        position_sizing_mode = getattr(input_data, "position_sizing_mode", "fixed")
        risk_per_trade = getattr(input_data, "risk_per_trade", 0.01)
        kelly_fraction = getattr(input_data, "kelly_fraction", 0.5)
        volatility_target = getattr(input_data, "volatility_target", 0.02)
        max_position_size = getattr(input_data, "max_position_size", 1.0)
        min_position_size = getattr(input_data, "min_position_size", 0.01)

        # === RE-ENTRY RULES ===
        allow_re_entry = getattr(input_data, "allow_re_entry", True)
        re_entry_delay_bars = getattr(input_data, "re_entry_delay_bars", 0)
        max_trades_per_day = getattr(input_data, "max_trades_per_day", 0)
        max_trades_per_week = getattr(input_data, "max_trades_per_week", 0)
        max_consecutive_losses = getattr(input_data, "max_consecutive_losses", 0)
        cooldown_after_loss = getattr(input_data, "cooldown_after_loss", 0)

        # === ADVANCED ORDERS (for future limit/stop order execution) ===
        entry_order_type = getattr(input_data, "entry_order_type", "market")  # noqa: F841
        limit_entry_offset = getattr(input_data, "limit_entry_offset", 0.001)  # noqa: F841
        limit_entry_timeout_bars = getattr(input_data, "limit_entry_timeout_bars", 5)  # noqa: F841
        stop_entry_offset = getattr(input_data, "stop_entry_offset", 0.001)  # noqa: F841

        # === SCALE-IN (for future scale-in execution) ===
        scale_in_enabled = getattr(input_data, "scale_in_enabled", False)  # noqa: F841
        scale_in_levels = getattr(input_data, "scale_in_levels", (1.0,))
        scale_in_portions = getattr(input_data, "scale_in_portions", (1.0,))  # noqa: F841

        # === VALIDATION: scale_in_portions must sum to 1.0 ===
        if scale_in_enabled:
            portions_sum = sum(scale_in_portions)
            if abs(portions_sum - 1.0) > 0.001:
                return BacktestOutput(
                    is_valid=False,
                    validation_errors=[f"scale_in_portions must sum to 1.0, got {portions_sum:.4f}"],
                    trades=[],
                    metrics=BacktestMetrics(),
                    equity_curve=np.array([]),
                )
            if len(scale_in_levels) != len(scale_in_portions):
                return BacktestOutput(
                    is_valid=False,
                    validation_errors=[
                        f"scale_in_levels ({len(scale_in_levels)}) and "
                        f"scale_in_portions ({len(scale_in_portions)}) must have same length"
                    ],
                    trades=[],
                    metrics=BacktestMetrics(),
                    equity_curve=np.array([]),
                )

        # === PORTFOLIO ===
        hedge_mode = getattr(input_data, "hedge_mode", False)

        # === SLIPPAGE MODEL ===
        slippage_model = getattr(input_data, "slippage_model", "fixed")
        slippage_volume_impact = getattr(input_data, "slippage_volume_impact", 0.1)
        slippage_volatility_mult = getattr(input_data, "slippage_volatility_mult", 0.5)

        # === FUNDING ===
        include_funding = getattr(input_data, "include_funding", False)
        funding_rate = getattr(input_data, "funding_rate", 0.0001)
        funding_interval_hours = getattr(input_data, "funding_interval_hours", 8)

        # === MARKET CONDITION FILTERS ===
        volatility_filter_enabled = getattr(input_data, "volatility_filter_enabled", False)
        min_volatility_percentile = getattr(input_data, "min_volatility_percentile", 10.0)
        max_volatility_percentile = getattr(input_data, "max_volatility_percentile", 90.0)
        volatility_lookback = getattr(input_data, "volatility_lookback", 100)

        volume_filter_enabled = getattr(input_data, "volume_filter_enabled", False)
        min_volume_percentile = getattr(input_data, "min_volume_percentile", 20.0)
        volume_lookback = getattr(input_data, "volume_lookback", 50)

        trend_filter_enabled = getattr(input_data, "trend_filter_enabled", False)
        trend_filter_period = getattr(input_data, "trend_filter_period", 200)
        trend_filter_mode = getattr(input_data, "trend_filter_mode", "with")

        momentum_filter_enabled = getattr(input_data, "momentum_filter_enabled", False)
        momentum_oversold = getattr(input_data, "momentum_oversold", 30.0)
        momentum_overbought = getattr(input_data, "momentum_overbought", 70.0)
        momentum_period = getattr(input_data, "momentum_period", 14)

        range_filter_enabled = getattr(input_data, "range_filter_enabled", False)
        range_adr_min = getattr(input_data, "range_adr_min", 0.01)
        range_lookback = getattr(input_data, "range_lookback", 20)

        # === MARKET REGIME DETECTOR ===
        market_regime_enabled = getattr(input_data, "market_regime_enabled", False)
        market_regime_filter = getattr(input_data, "market_regime_filter", "not_volatile")
        market_regime_lookback = getattr(input_data, "market_regime_lookback", 50)

        # === MULTI-TIMEFRAME (MTF) FILTER ===
        mtf_enabled = getattr(input_data, "mtf_enabled", False)
        mtf_htf_interval = getattr(input_data, "mtf_htf_interval", "60")  # noqa: F841
        mtf_htf_candles = getattr(input_data, "mtf_htf_candles", None)
        mtf_htf_index_map: List[int] | None = getattr(input_data, "mtf_htf_index_map", None)
        mtf_filter_type = getattr(input_data, "mtf_filter_type", "sma")
        mtf_filter_period = getattr(input_data, "mtf_filter_period", 200)
        mtf_neutral_zone_pct = getattr(input_data, "mtf_neutral_zone_pct", 0.0)
        mtf_lookahead_mode = getattr(input_data, "mtf_lookahead_mode", "none")  # noqa: F841 - reserved for future
        # BTC Correlation filter
        mtf_btc_filter_enabled = getattr(input_data, "mtf_btc_filter_enabled", False)
        mtf_btc_candles = getattr(input_data, "mtf_btc_candles", None)
        mtf_btc_index_map: List[int] | None = getattr(input_data, "mtf_btc_index_map", None)
        mtf_btc_filter_period = getattr(input_data, "mtf_btc_filter_period", 50)

        # Рассчитать уровни DCA
        dca_levels: List[float] = []
        dca_volumes: List[float] = []
        if dca_enabled and dca_safety_orders > 0:
            cumulative_deviation = 0.0
            current_deviation = dca_price_deviation
            current_volume = dca_safety_order_size
            for _ in range(dca_safety_orders):
                cumulative_deviation += current_deviation
                dca_levels.append(cumulative_deviation)
                dca_volumes.append(current_volume)
                current_deviation *= dca_step_scale
                current_volume *= dca_volume_scale

        dca_state: Optional[Dict] = None

        # Менеджер пирамидинга
        pyramid_mgr = PyramidingManager(
            pyramiding=pyramiding,
            close_rule=close_entries_rule,
        )

        # === СОСТОЯНИЕ MULTI-LEVEL TP ===
        long_tp_state = MultiTPState(tp_portions=tp_portions)
        short_tp_state = MultiTPState(tp_portions=tp_portions)

        # === СОСТОЯНИЕ TRAILING STOP ===
        long_trailing = TrailingStopState()
        short_trailing = TrailingStopState()

        # === СОСТОЯНИЕ BREAKEVEN STOP ===
        long_breakeven = BreakevenState()
        short_breakeven = BreakevenState()

        # === СОСТОЯНИЕ RE-ENTRY & TRADE LIMITS ===
        last_exit_bar = -999  # Бар последнего выхода
        consecutive_losses = 0  # Счётчик убытков подряд
        cooldown_until_bar = -1  # Кулдаун до этого бара
        trades_today = 0  # Сделок сегодня
        trades_this_week = 0  # Сделок на этой неделе
        current_day = None  # Текущий день для подсчёта
        current_week = None  # Текущая неделя для подсчёта

        # === СОСТОЯНИЕ PENDING LIMIT/STOP ORDERS ===
        # These will be used when limit/stop order execution logic is added
        pending_limit_long = None  # noqa: F841 {"price": float, "timeout_bar": int}
        pending_limit_short = None  # noqa: F841
        pending_stop_long = None  # noqa: F841
        pending_stop_short = None  # noqa: F841

        # === СОСТОЯНИЕ SCALE-IN ===
        # Scale-in: входить в позицию частями по сетке цен
        # levels = (0.0, -0.01, -0.02) -> вход по текущей, -1%, -2%
        # portions = (0.5, 0.3, 0.2) -> 50% сразу, 30% на -1%, 20% на -2%
        scale_in_state_long: Optional[Dict] = None  # Активный scale-in для лонга
        scale_in_state_short: Optional[Dict] = None  # Активный scale-in для шорта

        # === СОСТОЯНИЕ FUNDING ===
        last_funding_bar = 0  # noqa: F841 - track last funding bar
        accumulated_funding = 0.0  # Track total funding paid/received

        # === PRE-CALCULATE FILTER INDICATORS ===
        # Trend filter: SMA for trend direction
        trend_sma = None
        if trend_filter_enabled and trend_filter_period > 0:
            trend_sma = np.full(n, np.nan)
            for i_t in range(trend_filter_period - 1, n):
                trend_sma[i_t] = np.mean(close_prices[i_t - trend_filter_period + 1 : i_t + 1])

        # Momentum filter: RSI
        rsi_values = None
        if momentum_filter_enabled and momentum_period > 0:
            rsi_values = np.full(n, 50.0)  # Default to neutral
            for i_r in range(momentum_period, n):
                gains = []
                losses = []
                for j in range(i_r - momentum_period + 1, i_r + 1):
                    change = close_prices[j] - close_prices[j - 1]
                    if change > 0:
                        gains.append(change)
                    else:
                        losses.append(abs(change))
                avg_gain = np.mean(gains) if gains else 0.0001
                avg_loss = np.mean(losses) if losses else 0.0001
                rs = avg_gain / avg_loss
                rsi_values[i_r] = 100 - (100 / (1 + rs))

        # Volume percentiles (rolling)
        volume_percentiles = None
        if volume_filter_enabled and "volume" in candles.columns:
            volumes = candles["volume"].values
            volume_percentiles = np.full(n, 50.0)
            for i_v in range(volume_lookback, n):
                window = volumes[i_v - volume_lookback : i_v]
                current_vol = volumes[i_v]
                volume_percentiles[i_v] = (np.sum(window < current_vol) / len(window)) * 100

        # ATR percentiles for volatility filter
        atr_percentiles = None
        if volatility_filter_enabled and atr_values is not None:
            atr_percentiles = np.full(n, 50.0)
            for i_a in range(volatility_lookback, n):
                window = atr_values[i_a - volatility_lookback : i_a]
                current_atr_val = atr_values[i_a]
                if not np.isnan(current_atr_val) and len(window) > 0:
                    atr_percentiles[i_a] = (np.sum(window < current_atr_val) / len(window)) * 100

        # ADR (Average Daily Range) for range filter
        adr_values = None
        if range_filter_enabled:
            adr_values = np.full(n, 0.0)
            for i_d in range(range_lookback, n):
                daily_ranges = []
                for j in range(i_d - range_lookback, i_d):
                    daily_range = (high_prices[j] - low_prices[j]) / close_prices[j]
                    daily_ranges.append(daily_range)
                adr_values[i_d] = np.mean(daily_ranges) if daily_ranges else 0.0

        # === MARKET REGIME DETECTOR ===
        regime_detector = MarketRegimeDetector(lookback=market_regime_lookback) if market_regime_enabled else None

        # === MTF (MULTI-TIMEFRAME) INDICATORS ===
        mtf_htf_indicator = None  # SMA/EMA на HTF для фильтрации
        mtf_btc_indicator = None  # SMA на BTC для корреляции

        if mtf_enabled and mtf_htf_candles is not None:
            htf_closes = mtf_htf_candles["close"].values
            htf_n = len(htf_closes)
            mtf_htf_indicator = np.full(htf_n, np.nan)

            if mtf_filter_type == "ema":
                # EMA calculation
                alpha = 2.0 / (mtf_filter_period + 1)
                for i_htf in range(htf_n):
                    if i_htf == 0:
                        mtf_htf_indicator[i_htf] = htf_closes[i_htf]
                    else:
                        mtf_htf_indicator[i_htf] = (
                            alpha * htf_closes[i_htf] + (1 - alpha) * mtf_htf_indicator[i_htf - 1]
                        )
            else:
                # SMA calculation (default)
                for i_htf in range(mtf_filter_period - 1, htf_n):
                    mtf_htf_indicator[i_htf] = np.mean(htf_closes[i_htf - mtf_filter_period + 1 : i_htf + 1])

        if mtf_btc_filter_enabled and mtf_btc_candles is not None:
            btc_closes = mtf_btc_candles["close"].values
            btc_n = len(btc_closes)
            mtf_btc_indicator = np.full(btc_n, np.nan)
            # BTC SMA
            for i_btc in range(mtf_btc_filter_period - 1, btc_n):
                mtf_btc_indicator[i_btc] = np.mean(btc_closes[i_btc - mtf_btc_filter_period + 1 : i_btc + 1])

        # === ОСНОВНОЕ СОСТОЯНИЕ ===
        cash = capital
        equity_curve = [capital]
        trades: List[TradeRecord] = []

        # Pending exits
        pending_long_exit = False
        pending_long_exit_reason = None
        pending_long_exit_price = 0.0
        pending_short_exit = False
        pending_short_exit_reason = None
        pending_short_exit_price = 0.0

        # === MFE/MAE TRACKING ===
        # MFE = Maximum Favorable Excursion (лучшая нереализованная прибыль)
        # MAE = Maximum Adverse Excursion (худший нереализованный убыток)
        long_accumulated_mfe = 0.0
        long_accumulated_mae = 0.0
        short_accumulated_mfe = 0.0
        short_accumulated_mae = 0.0
        # Pending MFE/MAE для записи трейда
        pending_long_mfe = 0.0  # noqa: F841
        pending_long_mae = 0.0  # noqa: F841
        pending_short_mfe = 0.0  # noqa: F841
        pending_short_mae = 0.0  # noqa: F841

        # Bar Magnifier (для будущего использования)
        _bar_magnifier_index = self._build_bar_magnifier_index(candles, candles_1m) if use_bar_magnifier else None

        # === WARM-UP PERIOD ===
        # Пропускаем первые N баров пока индикаторы не станут валидными
        warmup_periods = [1]  # Минимум 1 бар
        if atr_enabled and atr_period > 0:
            warmup_periods.append(atr_period + 1)
        if trend_filter_enabled and trend_filter_period > 0:
            warmup_periods.append(trend_filter_period + 1)
        if momentum_filter_enabled and momentum_period > 0:
            warmup_periods.append(momentum_period + 1)
        if volatility_filter_enabled and volatility_lookback > 0:
            warmup_periods.append(volatility_lookback + 1)
        if volume_filter_enabled and volume_lookback > 0:
            warmup_periods.append(volume_lookback + 1)
        if range_filter_enabled and range_lookback > 0:
            warmup_periods.append(range_lookback + 1)
        if market_regime_enabled and market_regime_lookback > 0:
            warmup_periods.append(market_regime_lookback + 1)
        warmup_bars = max(warmup_periods)

        # Заполняем equity_curve для warmup периода (no trading)
        for _ in range(1, warmup_bars):
            equity_curve.append(capital)

        # === ADVANCED SLIPPAGE CALCULATION ===
        slippage_model = getattr(input_data, "slippage_model", "fixed")
        use_advanced_slippage = slippage_model == "advanced"
        slippage_multipliers = np.ones(n, dtype=np.float64)

        if use_advanced_slippage:
            # Calculate dynamic slippage multipliers based on volatility and volume
            lookback = 50
            volumes = candles["volume"].values if "volume" in candles.columns else None

            for i_slip in range(lookback, n):
                # Volatility multiplier based on ATR
                if atr_values is not None and close_prices[i_slip] > 0:
                    atr_pct = atr_values[i_slip] / close_prices[i_slip]
                    # Higher ATR% = higher slippage
                    # Assume normal ATR% is around 1%, scale 0.5-2x
                    volatility_mult = min(2.0, max(0.5, atr_pct / 0.01))
                    slippage_multipliers[i_slip] *= volatility_mult

                # Volume multiplier if volume available
                if volumes is not None:
                    window = volumes[max(0, i_slip - lookback) : i_slip]
                    if len(window) > 0:
                        avg_volume = np.mean(window)
                        if avg_volume > 0:
                            volume_ratio = volumes[i_slip] / avg_volume
                            # Lower volume = higher slippage
                            # Volume 50% of avg = 1.5x slippage
                            volume_mult = min(2.0, max(0.5, 1.0 / volume_ratio))
                            slippage_multipliers[i_slip] *= volume_mult

        # === ОСНОВНОЙ ЦИКЛ ===
        for i in range(warmup_bars, n):
            current_time = (
                pd.Timestamp(timestamps[i]).to_pydatetime()
                if hasattr(timestamps[i], "to_pydatetime")
                else timestamps[i]
            )
            _open_price = open_prices[i]  # noqa: F841 - для bar magnifier
            high_price = high_prices[i]
            low_price = low_prices[i]
            close_price = close_prices[i]
            # ATR используется если SL или TP в ATR-режиме
            current_atr = (
                atr_values[i] if atr_values is not None and (sl_mode == SlMode.ATR or tp_mode == TpMode.ATR) else 0.0
            )

            # Calculate effective slippage (dynamic if advanced model enabled)
            effective_slippage = (
                slippage * slippage_multipliers[i] if use_advanced_slippage else slippage
            )

            # === MARKET REGIME DETECTOR UPDATE ===
            # Обновляем детектор на каждом баре
            if regime_detector is not None:
                volume_val = candles["volume"].iloc[i] if "volume" in candles.columns else 0.0
                atr_val = atr_values[i] if atr_values is not None else 0.0
                regime_detector.update(close_price, volume_val, atr_val)

            # === ADAPTIVE ATR MULTIPLIER ===
            # Обновляем историю ATR и получаем адаптивные множители
            # Переопределяем локальные переменные для использования в остальном коде
            if adaptive_atr is not None and atr_values is not None:
                adaptive_atr.update(atr_values[i])
                # Локально переопределяем множители для этого бара
                atr_tp_multiplier_local = adaptive_atr.get_multiplier(atr_tp_multiplier)  # noqa: F841
                atr_sl_multiplier_local = adaptive_atr.get_multiplier(atr_sl_multiplier)  # noqa: F841
            else:
                atr_tp_multiplier_local = atr_tp_multiplier  # noqa: F841
                atr_sl_multiplier_local = atr_sl_multiplier  # noqa: F841

            # === MFE/MAE TRACKING ===
            # Аккумулируем MFE/MAE для открытых позиций на каждом баре
            if pyramid_mgr.has_position("long"):
                avg_entry = pyramid_mgr.get_avg_entry_price("long")
                total_size = pyramid_mgr.get_total_size("long")
                if total_size > 0 and avg_entry > 0:
                    # MFE: максимальная благоприятная экскурсия (high - entry для long)
                    current_mfe = max(0, (high_price - avg_entry) * total_size)
                    long_accumulated_mfe = max(long_accumulated_mfe, current_mfe)
                    # MAE: максимальная неблагоприятная экскурсия (entry - low для long)
                    current_mae = max(0, (avg_entry - low_price) * total_size)
                    long_accumulated_mae = max(long_accumulated_mae, current_mae)

            if pyramid_mgr.has_position("short"):
                avg_entry = pyramid_mgr.get_avg_entry_price("short")
                total_size = pyramid_mgr.get_total_size("short")
                if total_size > 0 and avg_entry > 0:
                    # MFE: максимальная благоприятная экскурсия (entry - low для short)
                    current_mfe = max(0, (avg_entry - low_price) * total_size)
                    short_accumulated_mfe = max(short_accumulated_mfe, current_mfe)
                    # MAE: максимальная неблагоприятная экскурсия (high - entry для short)
                    current_mae = max(0, (high_price - avg_entry) * total_size)
                    short_accumulated_mae = max(short_accumulated_mae, current_mae)

            # === ВЫПОЛНЕНИЕ ОТЛОЖЕННЫХ ВЫХОДОВ ===
            if pending_long_exit and pyramid_mgr.has_position("long"):
                exit_price = pending_long_exit_price
                # Ensure exit_reason is not None
                effective_exit_reason = pending_long_exit_reason or ExitReason.UNKNOWN
                closed_trades = pyramid_mgr.close_position(
                    direction="long",
                    exit_price=exit_price,
                    exit_bar_idx=i,
                    exit_time=current_time,
                    exit_reason=effective_exit_reason.value
                    if hasattr(effective_exit_reason, "value")
                    else str(effective_exit_reason),
                    taker_fee=taker_fee,
                )

                for trade_data in closed_trades:
                    cash += trade_data["allocated"] + trade_data["pnl"]
                    trade_record = TradeRecord(
                        entry_time=trade_data["entry_time"],
                        exit_time=trade_data["exit_time"],
                        direction="long",
                        entry_price=trade_data["entry_price"],
                        exit_price=trade_data["exit_price"],
                        size=trade_data["size"],
                        pnl=trade_data["pnl"],
                        pnl_pct=trade_data["pnl_pct"],
                        fees=trade_data["fees"],
                        exit_reason=effective_exit_reason,
                        duration_bars=trade_data["duration_bars"],
                        mfe=long_accumulated_mfe,
                        mae=long_accumulated_mae,
                    )
                    trades.append(trade_record)

                    # === UPDATE RE-ENTRY STATE ===
                    last_exit_bar = i
                    trades_today += 1
                    trades_this_week += 1
                    if trade_record.pnl < 0:
                        consecutive_losses += 1
                        if cooldown_after_loss > 0:
                            cooldown_until_bar = i + cooldown_after_loss
                    else:
                        consecutive_losses = 0

                # Сброс состояний
                pending_long_exit = False
                pending_long_exit_reason = None
                long_tp_state.reset()
                long_trailing.reset()
                long_breakeven.reset()
                dca_state = None
                scale_in_state_long = None  # Очистить scale-in при закрытии
                # Сброс MFE/MAE для следующего трейда
                long_accumulated_mfe = 0.0
                long_accumulated_mae = 0.0

            if pending_short_exit and pyramid_mgr.has_position("short"):
                exit_price = pending_short_exit_price
                # Ensure exit_reason is not None
                effective_short_exit_reason = pending_short_exit_reason or ExitReason.UNKNOWN
                closed_trades = pyramid_mgr.close_position(
                    direction="short",
                    exit_price=exit_price,
                    exit_bar_idx=i,
                    exit_time=current_time,
                    exit_reason=effective_short_exit_reason.value
                    if hasattr(effective_short_exit_reason, "value")
                    else str(effective_short_exit_reason),
                    taker_fee=taker_fee,
                )

                for trade_data in closed_trades:
                    cash += trade_data["allocated"] + trade_data["pnl"]
                    trade_record = TradeRecord(
                        entry_time=trade_data["entry_time"],
                        exit_time=trade_data["exit_time"],
                        direction="short",
                        entry_price=trade_data["entry_price"],
                        exit_price=trade_data["exit_price"],
                        size=trade_data["size"],
                        pnl=trade_data["pnl"],
                        pnl_pct=trade_data["pnl_pct"],
                        fees=trade_data["fees"],
                        exit_reason=effective_short_exit_reason,
                        duration_bars=trade_data["duration_bars"],
                        mfe=short_accumulated_mfe,
                        mae=short_accumulated_mae,
                    )
                    trades.append(trade_record)

                    # === UPDATE RE-ENTRY STATE ===
                    last_exit_bar = i
                    trades_today += 1
                    trades_this_week += 1
                    if trade_record.pnl < 0:
                        consecutive_losses += 1
                        if cooldown_after_loss > 0:
                            cooldown_until_bar = i + cooldown_after_loss
                    else:
                        consecutive_losses = 0

                pending_short_exit = False
                pending_short_exit_reason = None
                short_tp_state.reset()
                short_trailing.reset()
                short_breakeven.reset()
                dca_state = None
                scale_in_state_short = None  # Очистить scale-in при закрытии
                # Сброс MFE/MAE для следующего трейда
                short_accumulated_mfe = 0.0
                short_accumulated_mae = 0.0

            # === ОБРАБОТКА PENDING LIMIT/STOP ORDERS ===
            # Проверяем исполнение отложенных ордеров на вход

            # LONG Limit Order: исполняется если low <= limit_price
            if pending_limit_long is not None:
                limit_price = pending_limit_long["price"]
                timeout_bar = pending_limit_long["timeout_bar"]
                order_capital = pending_limit_long["capital"]

                if i >= timeout_bar:
                    # Таймаут - отменяем ордер
                    pending_limit_long = None
                elif low_price <= limit_price:
                    # Исполнение limit ордера
                    entry_price = limit_price
                    if pyramid_mgr.can_add_entry("long") and order_capital > 0:
                        order_size = (order_capital * leverage) / entry_price
                        pyramid_mgr.add_entry(
                            "long",
                            entry_price,
                            order_size,
                            order_capital,
                            i,
                            current_time,
                        )
                        cash -= order_capital
                    pending_limit_long = None

            # SHORT Limit Order: исполняется если high >= limit_price
            if pending_limit_short is not None:
                limit_price = pending_limit_short["price"]
                timeout_bar = pending_limit_short["timeout_bar"]
                order_capital = pending_limit_short["capital"]

                if i >= timeout_bar:
                    pending_limit_short = None
                elif high_price >= limit_price:
                    entry_price = limit_price
                    if pyramid_mgr.can_add_entry("short") and order_capital > 0:
                        order_size = (order_capital * leverage) / entry_price
                        pyramid_mgr.add_entry(
                            "short",
                            entry_price,
                            order_size,
                            order_capital,
                            i,
                            current_time,
                        )
                        cash -= order_capital
                    pending_limit_short = None

            # LONG Stop Order: исполняется если high >= stop_price (breakout)
            if pending_stop_long is not None:
                stop_price = pending_stop_long["price"]
                timeout_bar = pending_stop_long["timeout_bar"]
                order_capital = pending_stop_long["capital"]

                if i >= timeout_bar:
                    pending_stop_long = None
                elif high_price >= stop_price:
                    entry_price = stop_price * (1 + effective_slippage)  # Slippage на breakout
                    if pyramid_mgr.can_add_entry("long") and order_capital > 0:
                        order_size = (order_capital * leverage) / entry_price
                        pyramid_mgr.add_entry(
                            "long",
                            entry_price,
                            order_size,
                            order_capital,
                            i,
                            current_time,
                        )
                        cash -= order_capital
                    pending_stop_long = None

            # SHORT Stop Order: исполняется если low <= stop_price (breakdown)
            if pending_stop_short is not None:
                stop_price = pending_stop_short["price"]
                timeout_bar = pending_stop_short["timeout_bar"]
                order_capital = pending_stop_short["capital"]

                if i >= timeout_bar:
                    pending_stop_short = None
                elif low_price <= stop_price:
                    entry_price = stop_price * (1 - effective_slippage)
                    if pyramid_mgr.can_add_entry("short") and order_capital > 0:
                        order_size = (order_capital * leverage) / entry_price
                        pyramid_mgr.add_entry(
                            "short",
                            entry_price,
                            order_size,
                            order_capital,
                            i,
                            current_time,
                        )
                        cash -= order_capital
                    pending_stop_short = None

            # === SCALE-IN EXECUTION FOR LONG ===
            # Исполняем pending scale-in ордера для лонга
            if scale_in_state_long is not None and pyramid_mgr.has_position("long"):
                base_price = scale_in_state_long["base_price"]
                for level_idx, (level, portion) in enumerate(zip(scale_in_levels, scale_in_portions)):
                    if scale_in_state_long["filled"][level_idx]:
                        continue  # Уже исполнен

                    # Цена для входа: base_price * (1 + level)
                    # level отрицательный = ниже базовой цены
                    target_price = base_price * (1 + level)

                    # Для лонга: входим если low <= target_price
                    if low_price <= target_price:
                        entry_price = target_price * (1 + effective_slippage)
                        portion_capital = scale_in_state_long["total_capital"] * portion

                        if portion_capital > 0 and cash >= portion_capital:
                            order_size = (portion_capital * leverage) / entry_price
                            pyramid_mgr.add_entry(
                                "long",
                                entry_price,
                                order_size,
                                portion_capital,
                                i,
                                current_time,
                            )
                            cash -= portion_capital
                            scale_in_state_long["filled"][level_idx] = True

                # Если все уровни заполнены - очистить состояние
                if all(scale_in_state_long["filled"]):
                    scale_in_state_long = None

            # === SCALE-IN EXECUTION FOR SHORT ===
            # Исполняем pending scale-in ордера для шорта
            if scale_in_state_short is not None and pyramid_mgr.has_position("short"):
                base_price = scale_in_state_short["base_price"]
                for level_idx, (level, portion) in enumerate(zip(scale_in_levels, scale_in_portions)):
                    if scale_in_state_short["filled"][level_idx]:
                        continue  # Уже исполнен

                    # Цена для входа: base_price * (1 - level)
                    # level отрицательный для лонга, для шорта инвертируем
                    target_price = base_price * (1 - level)

                    # Для шорта: входим если high >= target_price
                    if high_price >= target_price:
                        entry_price = target_price * (1 - effective_slippage)
                        portion_capital = scale_in_state_short["total_capital"] * portion

                        if portion_capital > 0 and cash >= portion_capital:
                            order_size = (portion_capital * leverage) / entry_price
                            pyramid_mgr.add_entry(
                                "short",
                                entry_price,
                                order_size,
                                portion_capital,
                                i,
                                current_time,
                            )
                            cash -= portion_capital
                            scale_in_state_short["filled"][level_idx] = True

                # Если все уровни заполнены - очистить состояние
                if all(scale_in_state_short["filled"]):
                    scale_in_state_short = None

            # === MULTI-LEVEL TP ДЛЯ LONG ===
            # Работает только когда tp_mode == MULTI
            if tp_mode == TpMode.MULTI and pyramid_mgr.has_position("long") and not pending_long_exit:
                next_tp = long_tp_state.get_next_tp_level()
                if next_tp is not None:
                    tp_price = long_tp_state.tp_prices[next_tp]
                    if high_price >= tp_price > 0:
                        # Сработал TP уровень - частичное закрытие
                        portion = long_tp_state.mark_hit(next_tp)

                        trade_data = pyramid_mgr.close_partial(
                            direction="long",
                            exit_price=tp_price,
                            portion=portion,
                            exit_bar_idx=i,
                            exit_time=current_time,
                            exit_reason=f"tp{next_tp + 1}",
                            taker_fee=taker_fee,
                        )

                        if trade_data is not None:
                            cash += trade_data["allocated"] + trade_data["pnl"]
                            trades.append(
                                TradeRecord(
                                    entry_time=trade_data["entry_time"],
                                    exit_time=trade_data["exit_time"],
                                    direction="long",
                                    entry_price=trade_data["entry_price"],
                                    exit_price=trade_data["exit_price"],
                                    size=trade_data["size"],
                                    pnl=trade_data["pnl"],
                                    pnl_pct=trade_data["pnl_pct"],
                                    fees=trade_data["fees"],
                                    exit_reason=ExitReason.TAKE_PROFIT,
                                    duration_bars=trade_data["duration_bars"],
                                    mfe=long_accumulated_mfe,
                                    mae=long_accumulated_mae,
                                )
                            )

                            # === BREAKEVEN: Обновить SL после срабатывания TP ===
                            if breakeven_enabled:
                                avg_entry = pyramid_mgr.get_avg_entry_price("long")
                                long_breakeven.activate_on_tp(
                                    direction="long",
                                    avg_entry_price=avg_entry,
                                    tp_price=tp_price,
                                    mode=breakeven_mode,
                                    offset=breakeven_offset,
                                )

                        # Если все TP сработали - полное закрытие
                        if long_tp_state.all_hit():
                            pending_long_exit = True
                            pending_long_exit_reason = ExitReason.TAKE_PROFIT
                            pending_long_exit_price = close_price

            # === MULTI-LEVEL TP ДЛЯ SHORT ===
            # Работает только когда tp_mode == MULTI
            if tp_mode == TpMode.MULTI and pyramid_mgr.has_position("short") and not pending_short_exit:
                next_tp = short_tp_state.get_next_tp_level()
                if next_tp is not None:
                    tp_price = short_tp_state.tp_prices[next_tp]
                    if low_price <= tp_price > 0:
                        portion = short_tp_state.mark_hit(next_tp)

                        trade_data = pyramid_mgr.close_partial(
                            direction="short",
                            exit_price=tp_price,
                            portion=portion,
                            exit_bar_idx=i,
                            exit_time=current_time,
                            exit_reason=f"tp{next_tp + 1}",
                            taker_fee=taker_fee,
                        )

                        if trade_data is not None:
                            cash += trade_data["allocated"] + trade_data["pnl"]
                            trades.append(
                                TradeRecord(
                                    entry_time=trade_data["entry_time"],
                                    exit_time=trade_data["exit_time"],
                                    direction="short",
                                    entry_price=trade_data["entry_price"],
                                    exit_price=trade_data["exit_price"],
                                    size=trade_data["size"],
                                    pnl=trade_data["pnl"],
                                    pnl_pct=trade_data["pnl_pct"],
                                    fees=trade_data["fees"],
                                    exit_reason=ExitReason.TAKE_PROFIT,
                                    duration_bars=trade_data["duration_bars"],
                                    mfe=short_accumulated_mfe,
                                    mae=short_accumulated_mae,
                                )
                            )

                            # === BREAKEVEN: Обновить SL после срабатывания TP ===
                            if breakeven_enabled:
                                avg_entry = pyramid_mgr.get_avg_entry_price("short")
                                short_breakeven.activate_on_tp(
                                    direction="short",
                                    avg_entry_price=avg_entry,
                                    tp_price=tp_price,
                                    mode=breakeven_mode,
                                    offset=breakeven_offset,
                                )

                        if short_tp_state.all_hit():
                            pending_short_exit = True
                            pending_short_exit_reason = ExitReason.TAKE_PROFIT
                            pending_short_exit_price = close_price

            # === BREAKEVEN SL CHECK В РЕЖИМЕ MULTI-TP ===
            # Проверяем breakeven SL если tp_mode=MULTI (стандартная проверка SL пропускается)
            if tp_mode == TpMode.MULTI and breakeven_enabled:
                # LONG breakeven check
                if pyramid_mgr.has_position("long") and not pending_long_exit and long_breakeven.enabled:
                    breakeven_sl = long_breakeven.get_sl_price()
                    if breakeven_sl and low_price <= breakeven_sl:
                        pending_long_exit = True
                        pending_long_exit_reason = ExitReason.STOP_LOSS
                        pending_long_exit_price = breakeven_sl

                # SHORT breakeven check
                if pyramid_mgr.has_position("short") and not pending_short_exit and short_breakeven.enabled:
                    breakeven_sl = short_breakeven.get_sl_price()
                    if breakeven_sl and high_price >= breakeven_sl:
                        pending_short_exit = True
                        pending_short_exit_reason = ExitReason.STOP_LOSS
                        pending_short_exit_price = breakeven_sl

            # === БАЗОВЫЙ SL В РЕЖИМЕ MULTI-TP (когда breakeven ещё не активен) ===
            if tp_mode == TpMode.MULTI:
                # LONG SL check
                if pyramid_mgr.has_position("long") and not pending_long_exit and not long_breakeven.enabled:
                    # Определяем SL по режиму
                    if sl_mode == SlMode.ATR and atr_values is not None and current_atr > 0:
                        sl_price = pyramid_mgr.get_atr_sl_price("long", current_atr, atr_sl_multiplier)
                        if sl_max_limit and stop_loss > 0:
                            fixed_sl = pyramid_mgr.get_sl_price("long", stop_loss)
                            if fixed_sl and sl_price < fixed_sl:
                                sl_price = fixed_sl
                    elif sl_mode == SlMode.FIXED and stop_loss > 0:
                        sl_price = pyramid_mgr.get_sl_price("long", stop_loss)
                    else:
                        sl_price = None

                    if sl_price and low_price <= sl_price:
                        pending_long_exit = True
                        pending_long_exit_reason = ExitReason.STOP_LOSS
                        pending_long_exit_price = sl_price

                # SHORT SL check
                if pyramid_mgr.has_position("short") and not pending_short_exit and not short_breakeven.enabled:
                    if sl_mode == SlMode.ATR and atr_values is not None and current_atr > 0:
                        sl_price = pyramid_mgr.get_atr_sl_price("short", current_atr, atr_sl_multiplier)
                        if sl_max_limit and stop_loss > 0:
                            fixed_sl = pyramid_mgr.get_sl_price("short", stop_loss)
                            if fixed_sl and sl_price > fixed_sl:
                                sl_price = fixed_sl
                    elif sl_mode == SlMode.FIXED and stop_loss > 0:
                        sl_price = pyramid_mgr.get_sl_price("short", stop_loss)
                    else:
                        sl_price = None

                    if sl_price and high_price >= sl_price:
                        pending_short_exit = True
                        pending_short_exit_reason = ExitReason.STOP_LOSS
                        pending_short_exit_price = sl_price

            # === TRAILING STOP ДЛЯ LONG ===
            if trailing_stop_enabled and pyramid_mgr.has_position("long") and not pending_long_exit:
                avg_entry = pyramid_mgr.get_avg_entry_price("long")
                ts_price = long_trailing.update_long(high_price, avg_entry, trailing_activation, trailing_distance)
                if ts_price and low_price <= ts_price:
                    pending_long_exit = True
                    pending_long_exit_reason = ExitReason.TRAILING_STOP
                    pending_long_exit_price = ts_price

            # === TRAILING STOP ДЛЯ SHORT ===
            if trailing_stop_enabled and pyramid_mgr.has_position("short") and not pending_short_exit:
                avg_entry = pyramid_mgr.get_avg_entry_price("short")
                ts_price = short_trailing.update_short(low_price, avg_entry, trailing_activation, trailing_distance)
                if ts_price and high_price >= ts_price:
                    pending_short_exit = True
                    pending_short_exit_reason = ExitReason.TRAILING_STOP
                    pending_short_exit_price = ts_price

            # === СТАНДАРТНАЯ ПРОВЕРКА SL/TP ДЛЯ LONG ===
            # Работает только когда tp_mode != MULTI
            if pyramid_mgr.has_position("long") and not pending_long_exit and tp_mode != TpMode.MULTI:
                avg_entry = pyramid_mgr.get_avg_entry_price("long")

                # === ОПРЕДЕЛЕНИЕ TP ЦЕНЫ (по режиму) ===
                tp_price_long: float | None = None
                if tp_mode == TpMode.ATR and atr_values is not None and current_atr > 0:
                    tp_price_long = pyramid_mgr.get_atr_tp_price("long", current_atr, atr_tp_multiplier)
                elif tp_mode == TpMode.FIXED and take_profit > 0:
                    tp_price_long = pyramid_mgr.get_tp_price("long", take_profit)

                # === ОПРЕДЕЛЕНИЕ SL ЦЕНЫ (по режиму) ===
                sl_price_long: float | None = None
                if sl_mode == SlMode.ATR and atr_values is not None and current_atr > 0:
                    sl_price_long = pyramid_mgr.get_atr_sl_price("long", current_atr, atr_sl_multiplier)
                    # MAX limit: не выходить за пределы fixed SL
                    if sl_max_limit and stop_loss > 0:
                        fixed_sl = pyramid_mgr.get_sl_price("long", stop_loss)
                        if fixed_sl and sl_price_long < fixed_sl:
                            sl_price_long = fixed_sl
                elif sl_mode == SlMode.FIXED and stop_loss > 0:
                    sl_price_long = pyramid_mgr.get_sl_price("long", stop_loss)

                # === BREAKEVEN SL: Если активен, использовать breakeven цену ===
                breakeven_sl = long_breakeven.get_sl_price()
                if breakeven_sl is not None:
                    sl_price_long = breakeven_sl

                # Проверка условий
                if sl_price_long and low_price <= sl_price_long:
                    pending_long_exit = True
                    pending_long_exit_reason = ExitReason.STOP_LOSS
                    pending_long_exit_price = sl_price_long
                elif tp_price_long and high_price >= tp_price_long:
                    pending_long_exit = True
                    pending_long_exit_reason = ExitReason.TAKE_PROFIT
                    pending_long_exit_price = tp_price_long

            # === СТАНДАРТНАЯ ПРОВЕРКА SL/TP ДЛЯ SHORT ===
            # Работает только когда tp_mode != MULTI
            if pyramid_mgr.has_position("short") and not pending_short_exit and tp_mode != TpMode.MULTI:
                avg_entry = pyramid_mgr.get_avg_entry_price("short")

                # === ОПРЕДЕЛЕНИЕ TP ЦЕНЫ (по режиму) ===
                tp_price_short: float | None = None
                if tp_mode == TpMode.ATR and atr_values is not None and current_atr > 0:
                    tp_price_short = pyramid_mgr.get_atr_tp_price("short", current_atr, atr_tp_multiplier)
                elif tp_mode == TpMode.FIXED and take_profit > 0:
                    tp_price_short = pyramid_mgr.get_tp_price("short", take_profit)

                # === ОПРЕДЕЛЕНИЕ SL ЦЕНЫ (по режиму) ===
                sl_price_short: float | None = None
                if sl_mode == SlMode.ATR and atr_values is not None and current_atr > 0:
                    sl_price_short = pyramid_mgr.get_atr_sl_price("short", current_atr, atr_sl_multiplier)
                    # MAX limit: не выходить за пределы fixed SL
                    if sl_max_limit and stop_loss > 0:
                        fixed_sl = pyramid_mgr.get_sl_price("short", stop_loss)
                        if fixed_sl and sl_price_short and sl_price_short > fixed_sl:
                            sl_price_short = fixed_sl
                elif sl_mode == SlMode.FIXED and stop_loss > 0:
                    sl_price_short = pyramid_mgr.get_sl_price("short", stop_loss)

                # === BREAKEVEN SL: Если активен, использовать breakeven цену ===
                breakeven_sl = short_breakeven.get_sl_price()
                if breakeven_sl is not None:
                    sl_price_short = breakeven_sl

                if sl_price_short and high_price >= sl_price_short:
                    pending_short_exit = True
                    pending_short_exit_reason = ExitReason.STOP_LOSS
                    pending_short_exit_price = sl_price_short
                elif tp_price_short and low_price <= tp_price_short:
                    pending_short_exit = True
                    pending_short_exit_reason = ExitReason.TAKE_PROFIT
                    pending_short_exit_price = tp_price_short

            # === СИГНАЛЬНЫЕ ВЫХОДЫ ===
            if long_exits[i] and pyramid_mgr.has_position("long") and not pending_long_exit:
                pending_long_exit = True
                pending_long_exit_reason = ExitReason.SIGNAL
                pending_long_exit_price = close_price

            if short_exits[i] and pyramid_mgr.has_position("short") and not pending_short_exit:
                pending_short_exit = True
                pending_short_exit_reason = ExitReason.SIGNAL
                pending_short_exit_price = close_price

            # === DCA: SAFETY ORDERS ===
            if dca_enabled and dca_state is not None:
                base_price = dca_state["base_price"]
                filled = dca_state["filled"]
                dca_direction = dca_state["direction"]

                for so_idx, (deviation, volume) in enumerate(zip(dca_levels, dca_volumes)):
                    if filled[so_idx]:
                        continue

                    if dca_direction == "long":
                        so_price = base_price * (1 - deviation)
                        if low_price <= so_price and pyramid_mgr.can_add_entry("long"):
                            so_capital = cash * volume
                            if so_capital > 0:
                                so_size = (so_capital * leverage) / so_price
                                pyramid_mgr.add_entry(
                                    "long",
                                    so_price,
                                    so_size,
                                    so_capital,
                                    i,
                                    current_time,
                                )
                                cash -= so_capital
                                filled[so_idx] = True

                                # Обновить уровни TP при добавлении SO
                                if tp_mode == TpMode.MULTI:
                                    self._update_tp_prices(
                                        pyramid_mgr,
                                        "long",
                                        long_tp_state,
                                        tp_levels,
                                        current_atr if sl_mode == SlMode.ATR or tp_mode == TpMode.ATR else 0,
                                        take_profit,
                                        tp_mode == TpMode.ATR,
                                        atr_tp_multiplier,
                                    )

                    elif dca_direction == "short":
                        so_price = base_price * (1 + deviation)
                        if high_price >= so_price and pyramid_mgr.can_add_entry("short"):
                            so_capital = cash * volume
                            if so_capital > 0:
                                so_size = (so_capital * leverage) / so_price
                                pyramid_mgr.add_entry(
                                    "short",
                                    so_price,
                                    so_size,
                                    so_capital,
                                    i,
                                    current_time,
                                )
                                cash -= so_capital
                                filled[so_idx] = True

                                if tp_mode == TpMode.MULTI:
                                    self._update_tp_prices(
                                        pyramid_mgr,
                                        "short",
                                        short_tp_state,
                                        tp_levels,
                                        current_atr if sl_mode == SlMode.ATR or tp_mode == TpMode.ATR else 0,
                                        take_profit,
                                        tp_mode == TpMode.ATR,
                                        atr_tp_multiplier,
                                    )

            # === ПРОВЕРКА TIME-BASED CONSTRAINTS ===
            # Извлечь час и день недели из текущего времени (с учётом timezone)
            if hasattr(current_time, "hour"):
                # Apply timezone conversion if specified
                if timezone_str and timezone_str != "UTC":
                    try:
                        import pytz

                        tz = pytz.timezone(timezone_str)
                        # Convert to target timezone
                        if hasattr(current_time, "tzinfo") and current_time.tzinfo is None:
                            # Naive datetime - assume UTC
                            utc_time = pytz.UTC.localize(current_time)
                        else:
                            utc_time = current_time
                        local_time = utc_time.astimezone(tz)
                        current_hour = local_time.hour
                        current_weekday = local_time.weekday()
                    except Exception:
                        # Fallback to UTC if timezone conversion fails
                        current_hour = current_time.hour
                        current_weekday = current_time.weekday()
                else:
                    current_hour = current_time.hour
                    current_weekday = current_time.weekday()
            else:
                current_hour = 0
                current_weekday = 0

            # Проверка на запрещённые дни/часы для входа
            time_allows_entry = True
            if current_weekday in no_trade_days:
                time_allows_entry = False
            if current_hour in no_trade_hours:
                time_allows_entry = False
            if exit_on_session_close and current_hour >= session_end_hour:
                time_allows_entry = False

            # Проверка RE-ENTRY RULES
            reentry_allowed = allow_re_entry
            if re_entry_delay_bars > 0 and (i - last_exit_bar) < re_entry_delay_bars:
                reentry_allowed = False
            if cooldown_after_loss > 0 and i < cooldown_until_bar:
                reentry_allowed = False
            if max_consecutive_losses > 0 and consecutive_losses >= max_consecutive_losses:
                reentry_allowed = False
            if max_trades_per_day > 0 and trades_today >= max_trades_per_day:
                reentry_allowed = False
            if max_trades_per_week > 0 and trades_this_week >= max_trades_per_week:
                reentry_allowed = False

            # Обновить счётчики дня/недели
            if current_day is None or (hasattr(current_time, "date") and current_time.date() != current_day):
                current_day = current_time.date() if hasattr(current_time, "date") else None
                trades_today = 0
            if current_week is None or (
                hasattr(current_time, "isocalendar") and current_time.isocalendar()[1] != current_week
            ):
                current_week = current_time.isocalendar()[1] if hasattr(current_time, "isocalendar") else None
                trades_this_week = 0

            # === MARKET CONDITION FILTERS ===
            market_conditions_allow = True

            # Volatility Filter
            if volatility_filter_enabled and atr_percentiles is not None:
                current_atr_pct = atr_percentiles[i]
                if current_atr_pct < min_volatility_percentile:
                    market_conditions_allow = False  # Слишком низкая волатильность
                elif current_atr_pct > max_volatility_percentile:
                    market_conditions_allow = False  # Слишком высокая волатильность

            # Volume Filter
            if volume_filter_enabled and volume_percentiles is not None:
                if volume_percentiles[i] < min_volume_percentile:
                    market_conditions_allow = False  # Слишком низкий объём

            # Range Filter (ADR)
            if range_filter_enabled and adr_values is not None:
                if adr_values[i] < range_adr_min:
                    market_conditions_allow = False  # Боковик, слишком узкий диапазон

            # === MARKET REGIME FILTER ===
            if market_regime_enabled and regime_detector is not None:
                if not regime_detector.should_trade(market_regime_filter):
                    market_conditions_allow = False  # Режим рынка не подходит

            # Trend Filter - применяется отдельно для long и short
            trend_allows_long = True
            trend_allows_short = True
            if trend_filter_enabled and trend_sma is not None:
                sma_val = trend_sma[i]
                if not np.isnan(sma_val):
                    if trend_filter_mode == "with":
                        # Торговать по тренду
                        trend_allows_long = close_price > sma_val  # Long только выше SMA
                        trend_allows_short = close_price < sma_val  # Short только ниже SMA
                    elif trend_filter_mode == "against":
                        # Контртренд
                        trend_allows_long = close_price < sma_val
                        trend_allows_short = close_price > sma_val

            # Momentum Filter - применяется отдельно для long и short
            momentum_allows_long = True
            momentum_allows_short = True
            if momentum_filter_enabled and rsi_values is not None:
                rsi_val = rsi_values[i]
                # Long только в oversold, Short только в overbought
                momentum_allows_long = rsi_val < momentum_oversold
                momentum_allows_short = rsi_val > momentum_overbought

            # === MTF (MULTI-TIMEFRAME) FILTER ===
            # Фильтрует входы на основе старшего таймфрейма
            mtf_allows_long = True
            mtf_allows_short = True

            if (
                mtf_enabled
                and mtf_htf_indicator is not None
                and mtf_htf_index_map is not None
                and mtf_htf_candles is not None
            ):
                # Получить индекс HTF бара для текущего LTF бара
                htf_idx = mtf_htf_index_map[i] if i < len(mtf_htf_index_map) else -1

                if htf_idx >= 0 and htf_idx < len(mtf_htf_indicator):
                    htf_close = mtf_htf_candles["close"].iloc[htf_idx]
                    htf_ind_val = mtf_htf_indicator[htf_idx]

                    if not np.isnan(htf_ind_val):
                        # Neutral zone: зона неопределённости вокруг индикатора
                        neutral_band = htf_ind_val * mtf_neutral_zone_pct
                        upper_band = htf_ind_val + neutral_band
                        lower_band = htf_ind_val - neutral_band

                        # Long только если HTF close > HTF SMA (с учётом зоны)
                        if htf_close < lower_band:
                            mtf_allows_long = False
                        # Short только если HTF close < HTF SMA (с учётом зоны)
                        if htf_close > upper_band:
                            mtf_allows_short = False

            # BTC Correlation Filter (если торгуем альткоин)
            if (
                mtf_btc_filter_enabled
                and mtf_btc_indicator is not None
                and mtf_btc_index_map is not None
                and mtf_btc_candles is not None
            ):
                btc_idx = mtf_btc_index_map[i] if i < len(mtf_btc_index_map) else -1

                if btc_idx >= 0 and btc_idx < len(mtf_btc_indicator):
                    btc_close = mtf_btc_candles["close"].iloc[btc_idx]
                    btc_ind_val = mtf_btc_indicator[btc_idx]

                    if not np.isnan(btc_ind_val):
                        # BTC trend определяет разрешённые направления
                        if btc_close < btc_ind_val:
                            mtf_allows_long = False  # BTC в даунтренде - не входим в лонг
                        if btc_close > btc_ind_val:
                            mtf_allows_short = False  # BTC в аптренде - не входим в шорт

            # === ПРОВЕРКА TIME-BASED EXIT (max_bars_in_trade) ===
            if max_bars_in_trade > 0:
                # LONG: проверить время в позиции
                if pyramid_mgr.has_position("long"):
                    long_pos = pyramid_mgr.get_position("long")
                    if long_pos.entries:
                        bars_in_trade = i - long_pos.first_entry_bar
                        if bars_in_trade >= max_bars_in_trade:
                            pending_long_exit = True
                            pending_long_exit_reason = ExitReason.TIME_EXIT
                            pending_long_exit_price = close_price * (1 - effective_slippage)

                # SHORT: проверить время в позиции
                if pyramid_mgr.has_position("short"):
                    short_pos = pyramid_mgr.get_position("short")
                    if short_pos.entries:
                        bars_in_trade = i - short_pos.first_entry_bar
                        if bars_in_trade >= max_bars_in_trade:
                            pending_short_exit = True
                            pending_short_exit_reason = ExitReason.TIME_EXIT
                            pending_short_exit_price = close_price * (1 + effective_slippage)

            # === EXIT ON SESSION CLOSE ===
            if exit_on_session_close and current_hour >= session_end_hour - 1:
                if pyramid_mgr.has_position("long"):
                    pending_long_exit = True
                    pending_long_exit_reason = ExitReason.SESSION_CLOSE
                    pending_long_exit_price = close_price * (1 - effective_slippage)
                if pyramid_mgr.has_position("short"):
                    pending_short_exit = True
                    pending_short_exit_reason = ExitReason.SESSION_CLOSE
                    pending_short_exit_price = close_price * (1 + effective_slippage)

            # === EXIT END OF WEEK (Friday close) ===
            if exit_end_of_week and current_weekday == 4 and current_hour >= (24 - exit_before_weekend):
                if pyramid_mgr.has_position("long"):
                    pending_long_exit = True
                    pending_long_exit_reason = ExitReason.WEEKEND_CLOSE
                    pending_long_exit_price = close_price * (1 - effective_slippage)
                if pyramid_mgr.has_position("short"):
                    pending_short_exit = True
                    pending_short_exit_reason = ExitReason.WEEKEND_CLOSE
                    pending_short_exit_price = close_price * (1 + effective_slippage)

            # === ВХОДЫ ===
            can_long = direction in (
                TradeDirection.LONG,
                TradeDirection.BOTH,
                "long",
                "both",
            )
            can_short = direction in (
                TradeDirection.SHORT,
                TradeDirection.BOTH,
                "short",
                "both",
            )

            # Проверка hedge_mode: если нет - нельзя открывать противоположную позицию
            if not hedge_mode:
                if pyramid_mgr.has_position("short"):
                    can_long = False
                if pyramid_mgr.has_position("long"):
                    can_short = False

            # LONG Entry
            if (
                long_entries[i]
                and can_long
                and not pending_long_exit
                and time_allows_entry
                and reentry_allowed
                and market_conditions_allow
                and trend_allows_long
                and momentum_allows_long
                and mtf_allows_long
            ):
                if pyramid_mgr.can_add_entry("long"):
                    # === DYNAMIC SLIPPAGE ===
                    effective_slippage = self._calculate_slippage(
                        base_slippage=slippage,
                        slippage_model=slippage_model,
                        volume=candles["volume"].iloc[i] if "volume" in candles.columns else 0.0,
                        atr=current_atr if atr_values is not None else 0.0,
                        avg_volume=candles["volume"].mean() if "volume" in candles.columns else 1.0,
                        price=close_price,
                        volume_impact=slippage_volume_impact,
                        volatility_mult=slippage_volatility_mult,
                    )
                    entry_price = close_price * (1 + effective_slippage)

                    # === POSITION SIZING ===
                    if position_sizing_mode == "risk" and stop_loss > 0:
                        # Размер = (капитал × риск) / (SL% × леверидж)
                        order_capital = (cash * risk_per_trade) / (stop_loss * leverage)
                        order_capital = min(order_capital, cash * max_position_size)
                        order_capital = max(order_capital, cash * min_position_size)
                    elif position_sizing_mode == "volatility" and current_atr > 0:
                        # Размер обратно пропорционален волатильности
                        atr_pct = current_atr / close_price
                        vol_factor = volatility_target / max(atr_pct, 0.001)
                        order_capital = cash * position_size * vol_factor
                        order_capital = min(order_capital, cash * max_position_size)
                        order_capital = max(order_capital, cash * min_position_size)
                    elif position_sizing_mode == "kelly" and len(trades) >= 10:
                        # Half-Kelly based on recent trades
                        recent_trades = trades[-20:] if len(trades) >= 20 else trades
                        wins = [t for t in recent_trades if t.pnl > 0]
                        win_rate = len(wins) / len(recent_trades) if recent_trades else 0.5
                        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 1
                        losses = [t for t in recent_trades if t.pnl <= 0]
                        avg_loss = abs(sum(t.pnl for t in losses) / len(losses)) if losses else 1
                        win_loss_ratio = avg_win / max(avg_loss, 0.001)
                        kelly = win_rate - (1 - win_rate) / max(win_loss_ratio, 0.001)
                        kelly = max(0, min(kelly * kelly_fraction, max_position_size))
                        order_capital = cash * kelly
                    elif dca_enabled:
                        order_capital = cash * dca_base_order_size
                    elif use_fixed_amount:
                        order_capital = min(fixed_amount, cash)
                    else:
                        order_capital = cash * position_size

                    if order_capital > 0:
                        # === ENTRY ORDER TYPE ===
                        if entry_order_type == "market":
                            # === SCALE-IN MODE ===
                            if scale_in_enabled and len(scale_in_levels) > 1:
                                # Входим первой частью сразу, остальные по сетке
                                first_portion = scale_in_portions[0]
                                first_capital = order_capital * first_portion

                                if first_capital > 0:
                                    order_size = (first_capital * leverage) / entry_price
                                    pyramid_mgr.add_entry(
                                        "long",
                                        entry_price,
                                        order_size,
                                        first_capital,
                                        i,
                                        current_time,
                                    )
                                    cash -= first_capital

                                # Инициализировать scale-in состояние
                                filled = [False] * len(scale_in_levels)
                                filled[0] = True  # Первый уровень уже исполнен
                                scale_in_state_long = {
                                    "base_price": entry_price,
                                    "total_capital": order_capital,
                                    "filled": filled,
                                }
                            else:
                                # Обычный полный вход
                                order_size = (order_capital * leverage) / entry_price
                                pyramid_mgr.add_entry(
                                    "long",
                                    entry_price,
                                    order_size,
                                    order_capital,
                                    i,
                                    current_time,
                                )
                                cash -= order_capital

                            # Инициализировать DCA состояние
                            if dca_enabled and dca_safety_orders > 0:
                                dca_state = {
                                    "direction": "long",
                                    "base_price": entry_price,
                                    "filled": [False] * dca_safety_orders,
                                }

                            # Установить Multi-level TP prices
                            if tp_mode == TpMode.MULTI:
                                self._update_tp_prices(
                                    pyramid_mgr,
                                    "long",
                                    long_tp_state,
                                    tp_levels,
                                    current_atr if sl_mode == SlMode.ATR or tp_mode == TpMode.ATR else 0,
                                    take_profit,
                                    tp_mode == TpMode.ATR,
                                    atr_tp_multiplier,
                                )
                        elif entry_order_type == "limit":
                            # Limit order: размещаем ниже текущей цены
                            limit_price = close_price * (1 - limit_entry_offset)
                            pending_limit_long = {
                                "price": limit_price,
                                "timeout_bar": i + limit_entry_timeout_bars,
                                "capital": order_capital,
                            }
                        elif entry_order_type == "stop":
                            # Stop order: размещаем выше текущей цены (breakout)
                            stop_price = close_price * (1 + stop_entry_offset)
                            pending_stop_long = {
                                "price": stop_price,
                                "timeout_bar": i + limit_entry_timeout_bars,
                                "capital": order_capital,
                            }

            # SHORT Entry
            if (
                short_entries[i]
                and can_short
                and not pending_short_exit
                and time_allows_entry
                and reentry_allowed
                and market_conditions_allow
                and trend_allows_short
                and momentum_allows_short
                and mtf_allows_short
            ):
                if pyramid_mgr.can_add_entry("short"):
                    # === DYNAMIC SLIPPAGE ===
                    effective_slippage = self._calculate_slippage(
                        base_slippage=slippage,
                        slippage_model=slippage_model,
                        volume=candles["volume"].iloc[i] if "volume" in candles.columns else 0.0,
                        atr=current_atr if atr_values is not None else 0.0,
                        avg_volume=candles["volume"].mean() if "volume" in candles.columns else 1.0,
                        price=close_price,
                        volume_impact=slippage_volume_impact,
                        volatility_mult=slippage_volatility_mult,
                    )
                    entry_price = close_price * (1 - effective_slippage)

                    # === POSITION SIZING ===
                    if position_sizing_mode == "risk" and stop_loss > 0:
                        order_capital = (cash * risk_per_trade) / (stop_loss * leverage)
                        order_capital = min(order_capital, cash * max_position_size)
                        order_capital = max(order_capital, cash * min_position_size)
                    elif position_sizing_mode == "volatility" and current_atr > 0:
                        atr_pct = current_atr / close_price
                        vol_factor = volatility_target / max(atr_pct, 0.001)
                        order_capital = cash * position_size * vol_factor
                        order_capital = min(order_capital, cash * max_position_size)
                        order_capital = max(order_capital, cash * min_position_size)
                    elif position_sizing_mode == "kelly" and len(trades) >= 10:
                        recent_trades = trades[-20:] if len(trades) >= 20 else trades
                        wins = [t for t in recent_trades if t.pnl > 0]
                        win_rate = len(wins) / len(recent_trades) if recent_trades else 0.5
                        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 1
                        losses = [t for t in recent_trades if t.pnl <= 0]
                        avg_loss = abs(sum(t.pnl for t in losses) / len(losses)) if losses else 1
                        win_loss_ratio = avg_win / max(avg_loss, 0.001)
                        kelly = win_rate - (1 - win_rate) / max(win_loss_ratio, 0.001)
                        kelly = max(0, min(kelly * kelly_fraction, max_position_size))
                        order_capital = cash * kelly
                    elif dca_enabled:
                        order_capital = cash * dca_base_order_size
                    elif use_fixed_amount:
                        order_capital = min(fixed_amount, cash)
                    else:
                        order_capital = cash * position_size

                    if order_capital > 0:
                        # === ENTRY ORDER TYPE ===
                        if entry_order_type == "market":
                            # === SCALE-IN MODE ===
                            if scale_in_enabled and len(scale_in_levels) > 1:
                                # Входим первой частью сразу, остальные по сетке
                                first_portion = scale_in_portions[0]
                                first_capital = order_capital * first_portion

                                if first_capital > 0:
                                    order_size = (first_capital * leverage) / entry_price
                                    pyramid_mgr.add_entry(
                                        "short",
                                        entry_price,
                                        order_size,
                                        first_capital,
                                        i,
                                        current_time,
                                    )
                                    cash -= first_capital

                                # Инициализировать scale-in состояние
                                filled = [False] * len(scale_in_levels)
                                filled[0] = True  # Первый уровень уже исполнен
                                scale_in_state_short = {
                                    "base_price": entry_price,
                                    "total_capital": order_capital,
                                    "filled": filled,
                                }
                            else:
                                # Обычный полный вход
                                order_size = (order_capital * leverage) / entry_price
                                pyramid_mgr.add_entry(
                                    "short",
                                    entry_price,
                                    order_size,
                                    order_capital,
                                    i,
                                    current_time,
                                )
                                cash -= order_capital

                            if dca_enabled and dca_safety_orders > 0:
                                dca_state = {
                                    "direction": "short",
                                    "base_price": entry_price,
                                    "filled": [False] * dca_safety_orders,
                                }

                            if tp_mode == TpMode.MULTI:
                                self._update_tp_prices(
                                    pyramid_mgr,
                                    "short",
                                    short_tp_state,
                                    tp_levels,
                                    current_atr if sl_mode == SlMode.ATR or tp_mode == TpMode.ATR else 0,
                                    take_profit,
                                    tp_mode == TpMode.ATR,
                                    atr_tp_multiplier,
                                )
                        elif entry_order_type == "limit":
                            # Limit order: размещаем выше текущей цены (для short)
                            limit_price = close_price * (1 + limit_entry_offset)
                            pending_limit_short = {
                                "price": limit_price,
                                "timeout_bar": i + limit_entry_timeout_bars,
                                "capital": order_capital,
                            }
                        elif entry_order_type == "stop":
                            # Stop order: размещаем ниже текущей цены (breakdown)
                            stop_price = close_price * (1 - stop_entry_offset)
                            pending_stop_short = {
                                "price": stop_price,
                                "timeout_bar": i + limit_entry_timeout_bars,
                                "capital": order_capital,
                            }

            # === FUNDING FEE CALCULATION ===
            if include_funding and funding_interval_hours > 0:
                # Determine if this bar crosses a funding interval
                # Funding is applied every N hours (e.g., 8h for Bybit perpetuals)
                current_hour_ts = pd.Timestamp(timestamps[i])
                prev_hour_ts = pd.Timestamp(timestamps[i - 1]) if i > 0 else current_hour_ts

                # Check if we crossed a funding hour (0, 8, 16 for 8h intervals)
                funding_hours = [h for h in range(0, 24, funding_interval_hours)]
                current_hour = current_hour_ts.hour
                prev_hour = prev_hour_ts.hour

                # Crossed funding time if current hour is in funding_hours and prev hour wasn't
                crossed_funding = current_hour in funding_hours and (
                    prev_hour not in funding_hours or current_hour_ts.day != prev_hour_ts.day
                )

                if crossed_funding:
                    # Apply funding to open positions
                    if pyramid_mgr.has_position("long"):
                        position_value = pyramid_mgr.get_total_allocated("long") * leverage
                        funding_fee = position_value * funding_rate
                        # Long pays funding when rate is positive
                        accumulated_funding += funding_fee
                        cash -= funding_fee  # Deduct from cash

                    if pyramid_mgr.has_position("short"):
                        position_value = pyramid_mgr.get_total_allocated("short") * leverage
                        funding_fee = position_value * funding_rate
                        # Short receives funding when rate is positive (so we add it)
                        accumulated_funding -= funding_fee
                        cash += funding_fee  # Add to cash

                    last_funding_bar = i  # noqa: F841 - track for debugging

            # === ОБНОВЛЕНИЕ EQUITY ===
            unrealized_pnl = 0.0
            if pyramid_mgr.has_position("long"):
                avg_entry = pyramid_mgr.get_avg_entry_price("long")
                total_size = pyramid_mgr.get_total_size("long")
                unrealized_pnl += total_size * (close_price - avg_entry)

            if pyramid_mgr.has_position("short"):
                avg_entry = pyramid_mgr.get_avg_entry_price("short")
                total_size = pyramid_mgr.get_total_size("short")
                unrealized_pnl += total_size * (avg_entry - close_price)

            equity = (
                cash
                + pyramid_mgr.get_total_allocated("long")
                + pyramid_mgr.get_total_allocated("short")
                + unrealized_pnl
            )
            equity_curve.append(equity)

        # === ЗАКРЫТИЕ ОСТАВШИХСЯ ПОЗИЦИЙ ===
        final_time = timestamps[-1]
        final_price = close_prices[-1]

        for direction in ["long", "short"]:
            if pyramid_mgr.has_position(direction):
                closed = pyramid_mgr.close_position(
                    direction=direction,
                    exit_price=final_price,
                    exit_bar_idx=n - 1,
                    exit_time=final_time,
                    exit_reason="end_of_data",
                    taker_fee=taker_fee,
                )
                # Получаем накопленные MFE/MAE для позиции
                if direction == "long":
                    final_mfe, final_mae = long_accumulated_mfe, long_accumulated_mae
                else:
                    final_mfe, final_mae = short_accumulated_mfe, short_accumulated_mae

                for trade_data in closed:
                    cash += trade_data["allocated"] + trade_data["pnl"]
                    trades.append(
                        TradeRecord(
                            entry_time=trade_data["entry_time"],
                            exit_time=trade_data["exit_time"],
                            direction=direction,
                            entry_price=trade_data["entry_price"],
                            exit_price=trade_data["exit_price"],
                            size=trade_data["size"],
                            pnl=trade_data["pnl"],
                            pnl_pct=trade_data["pnl_pct"],
                            fees=trade_data["fees"],
                            exit_reason=ExitReason.END_OF_DATA,
                            duration_bars=trade_data["duration_bars"],
                            mfe=final_mfe,
                            mae=final_mae,
                        )
                    )

        equity_curve[-1] = cash

        # === РАСЧЁТ МЕТРИК ===
        metrics = self._calculate_metrics(trades, equity_curve, capital)

        execution_time = time.time() - start_time

        return BacktestOutput(
            is_valid=True,
            trades=trades,
            metrics=metrics,
            equity_curve=np.array(equity_curve),
            execution_time=execution_time,
            engine_name=self.name,
            bars_processed=n,
        )

    def _update_tp_prices(
        self,
        pyramid_mgr: PyramidingManager,
        direction: str,
        tp_state: MultiTPState,
        tp_levels: Tuple[float, ...],
        current_atr: float,
        take_profit: float,
        atr_enabled: bool,
        atr_tp_multiplier: float,
    ):
        """Обновить цены TP при входе или добавлении SO."""
        if atr_enabled and current_atr > 0:
            # ATR-based TP levels
            tp_prices = pyramid_mgr.get_atr_multi_tp_prices(
                direction,
                current_atr,
                tuple(level * atr_tp_multiplier for level in tp_levels),
            )
        else:
            # Percentage-based TP levels
            # tp_levels are absolute percentages (0.01=1%), so use 1.0 as base
            tp_prices = pyramid_mgr.get_multi_tp_prices(direction, 1.0, tp_levels)

        tp_state.set_prices(tp_prices, tp_state.tp_portions)

    def _build_bar_magnifier_index(self, candles: pd.DataFrame, candles_1m: pd.DataFrame) -> Optional[Dict]:
        """
        Build index for bar magnifier (1m data lookup).
        Returns: bar_idx -> (start_1m_idx, end_1m_idx)
        """
        if candles_1m is None or len(candles_1m) == 0:
            return None

        index = {}

        # Get timestamps - prioritize 'timestamp' column, then index
        if "timestamp" in candles.columns:
            bar_times = pd.to_datetime(candles["timestamp"])
        elif isinstance(candles.index, pd.DatetimeIndex):
            bar_times = candles.index
        else:
            bar_times = pd.to_datetime(candles.index)

        if "timestamp" in candles_1m.columns:
            m1_times = pd.to_datetime(candles_1m["timestamp"])
        elif isinstance(candles_1m.index, pd.DatetimeIndex):
            m1_times = candles_1m.index
        else:
            m1_times = pd.to_datetime(candles_1m.index)

        # For each bar of main timeframe, find corresponding 1m bars
        for i in range(len(candles)):
            bar_start = bar_times.iloc[i] if hasattr(bar_times, "iloc") else bar_times[i]
            bar_end = (
                bar_times.iloc[i + 1]
                if i + 1 < len(candles) and hasattr(bar_times, "iloc")
                else bar_times[i + 1]
                if i + 1 < len(candles)
                else bar_start + pd.Timedelta(hours=1)
            )

            # Find 1m bars in this range
            mask = (m1_times >= bar_start) & (m1_times < bar_end)
            matching_indices = np.where(mask)[0]

            if len(matching_indices) > 0:
                index[i] = (matching_indices[0], matching_indices[-1] + 1)

        return index

    def _calculate_metrics(
        self,
        trades: List[TradeRecord],
        equity_curve: List[float],
        initial_capital: float,
    ) -> BacktestMetrics:
        """Calculate backtest metrics."""
        metrics = BacktestMetrics()

        if not trades:
            return metrics

        pnls = [t.pnl for t in trades]

        metrics.total_trades = len(trades)
        metrics.winning_trades = sum(1 for p in pnls if p > 0)
        metrics.losing_trades = sum(1 for p in pnls if p < 0)
        metrics.win_rate = metrics.winning_trades / metrics.total_trades if metrics.total_trades > 0 else 0

        metrics.gross_profit = sum(p for p in pnls if p > 0)
        metrics.gross_loss = abs(sum(p for p in pnls if p < 0))
        metrics.net_profit = sum(pnls)
        metrics.total_return = (metrics.net_profit / initial_capital) * 100

        metrics.profit_factor = metrics.gross_profit / metrics.gross_loss if metrics.gross_loss > 0 else float("inf")

        winning_pnls = [p for p in pnls if p > 0]
        losing_pnls = [p for p in pnls if p < 0]
        metrics.avg_win = float(np.mean(winning_pnls)) if winning_pnls else 0.0
        metrics.avg_loss = float(np.mean(losing_pnls)) if losing_pnls else 0.0

        # Drawdown
        equity_arr = np.array(equity_curve)
        peak = np.maximum.accumulate(equity_arr)
        drawdown = (peak - equity_arr) / peak
        metrics.max_drawdown = float(np.max(drawdown)) * 100

        # Sharpe
        if len(pnls) > 1:
            returns = np.array(pnls) / initial_capital
            if np.std(returns) > 0:
                metrics.sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)

        return metrics

    def optimize(
        self,
        input_data: BacktestInput,
        param_ranges: Dict[str, List[Any]],
        metric: str = "sharpe_ratio",
        top_n: int = 10,
    ) -> List[Tuple[Dict[str, Any], BacktestOutput]]:
        """Optimization not implemented for V4."""
        return []
