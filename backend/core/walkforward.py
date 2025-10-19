"""
Walk-Forward Analysis Module

Модуль для пошаговой оптимизации и проверки устойчивости торговых стратегий.
Портирован из legacy_walkforward.py с улучшениями для современной архитектуры.

Основная идея Walk-Forward:
1. Разбиваем данные на окна (In-Sample + Out-of-Sample)
2. Оптимизируем параметры на IS окне
3. Тестируем найденные параметры на OOS окне
4. Сдвигаем окно и повторяем процесс

Author: Bybit Strategy Tester Team
Date: October 2025
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger

from backend.core.backtest import BacktestEngine
from backend.models.legacy_base_strategy import BaseStrategy


class WalkForwardWindow:
    """Одно окно Walk-Forward анализа"""

    def __init__(
        self,
        window_id: int,
        is_start: datetime,
        is_end: datetime,
        oos_start: datetime,
        oos_end: datetime,
        best_params: Optional[Dict[str, Any]] = None,
        is_metrics: Optional[Dict[str, float]] = None,
        oos_metrics: Optional[Dict[str, float]] = None,
    ):
        self.window_id = window_id
        self.is_start = is_start
        self.is_end = is_end
        self.oos_start = oos_start
        self.oos_end = oos_end
        self.best_params = best_params
        self.is_metrics = is_metrics
        self.oos_metrics = oos_metrics

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для сериализации"""
        return {
            "window_id": self.window_id,
            "is_start": self.is_start.isoformat() if self.is_start else None,
            "is_end": self.is_end.isoformat() if self.is_end else None,
            "oos_start": self.oos_start.isoformat() if self.oos_start else None,
            "oos_end": self.oos_end.isoformat() if self.oos_end else None,
            "best_params": self.best_params,
            "is_metrics": self.is_metrics,
            "oos_metrics": self.oos_metrics,
        }

    def __repr__(self):
        return (
            f"WFWindow #{self.window_id}: "
            f"IS({self.is_start.date()}→{self.is_end.date()}) "
            f"OOS({self.oos_start.date()}→{self.oos_end.date()})"
        )


class WalkForwardAnalyzer:
    """
    Класс для Walk-Forward оптимизации стратегий
    
    Разбивает исторические данные на окна:
    - In-Sample (IS) - период обучения для поиска оптимальных параметров
    - Out-of-Sample (OOS) - период проверки найденных параметров
    
    Example:
        >>> analyzer = WalkForwardAnalyzer(
        ...     data=df,
        ...     initial_capital=10000,
        ...     is_window_days=120,
        ...     oos_window_days=60,
        ...     step_days=30
        ... )
        >>> results = await analyzer.run_async(
        ...     strategy_class=MACrossoverStrategy,
        ...     param_space={'fast_period': [5, 10, 20], 'slow_period': [20, 50]},
        ...     metric='sharpe_ratio'
        ... )
    """

    def __init__(
        self,
        data: pd.DataFrame,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        is_window_days: int = 120,
        oos_window_days: int = 60,
        step_days: int = 30,
    ):
        """
        Args:
            data: DataFrame с историческими данными (OHLCV + timestamp)
            initial_capital: Начальный капитал
            commission: Комиссия за сделку
            is_window_days: Размер In-Sample окна (период обучения)
            oos_window_days: Размер Out-of-Sample окна (период проверки)
            step_days: Шаг сдвига окон
        """
        self.data = data.copy()
        self.initial_capital = initial_capital
        self.commission = commission
        self.is_window_days = is_window_days
        self.oos_window_days = oos_window_days
        self.step_days = step_days

        self.windows: List[WalkForwardWindow] = []
        self._create_windows()

    def _create_windows(self):
        """Создаёт список окон для Walk-Forward анализа"""
        if "timestamp" not in self.data.columns:
            raise ValueError("DataFrame должен содержать колонку 'timestamp'")

        # Сортируем по времени
        self.data = self.data.sort_values("timestamp").reset_index(drop=True)

        start_date = self.data["timestamp"].iloc[0]
        end_date = self.data["timestamp"].iloc[-1]

        current_start = start_date
        window_id = 0

        while True:
            # Определяем границы IS окна
            is_start = current_start
            is_end = is_start + timedelta(days=self.is_window_days)

            # Определяем границы OOS окна
            oos_start = is_end
            oos_end = oos_start + timedelta(days=self.oos_window_days)

            # Проверяем что OOS окно ещё помещается
            if oos_end > end_date:
                break

            window = WalkForwardWindow(
                window_id=window_id,
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
            )
            self.windows.append(window)

            # Сдвигаем на step_days
            current_start += timedelta(days=self.step_days)
            window_id += 1

        window_size_days = self.is_window_days + self.oos_window_days
        
        if len(self.windows) == 0:
            raise ValueError(
                f"Недостаточно данных для создания окон. "
                f"Требуется минимум {window_size_days} дней, "
                f"доступно {(end_date - start_date).days} дней"
            )

        logger.info(f"[WalkForward] Создано {len(self.windows)} окон для анализа")
        for window in self.windows[:3]:  # Показываем первые 3
            logger.debug(f"  {window}")
        if len(self.windows) > 3:
            logger.debug(f"  ... и ещё {len(self.windows) - 3} окон")

    def _get_window_data(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Получает данные для конкретного окна"""
        mask = (self.data["timestamp"] >= start) & (self.data["timestamp"] < end)
        return self.data[mask].copy()

    async def _optimize_window(
        self,
        window: WalkForwardWindow,
        strategy_config: Dict[str, Any],
        param_space: Dict[str, List],
        metric: str = "sharpe_ratio"
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Оптимизирует параметры на IS окне
        
        Args:
            window: Окно для оптимизации
            strategy_config: Базовая конфигурация стратегии
            param_space: Пространство параметров для оптимизации
            metric: Метрика для оценки (sharpe_ratio, net_profit, etc.)
        
        Returns:
            (best_params, best_metrics)
        """
        is_data = self._get_window_data(window.is_start, window.is_end)

        if len(is_data) == 0:
            logger.warning(f"[WalkForward] Нет данных для окна {window}")
            return {}, {}

        # Генерируем все комбинации параметров
        from itertools import product
        
        param_names = list(param_space.keys())
        param_values = list(param_space.values())
        all_combinations = list(product(*param_values))

        logger.info(
            f"[WalkForward] Окно #{window.window_id}: "
            f"оптимизация {len(all_combinations)} комбинаций на {len(is_data)} барах"
        )

        best_params = None
        best_metric_value = -np.inf
        best_metrics = {}

        # Тестируем каждую комбинацию
        for combination in all_combinations:
            params = dict(zip(param_names, combination))
            
            # Объединяем с базовой конфигурацией
            test_config = {**strategy_config, **params}

            try:
                # Запускаем backtest
                engine = BacktestEngine(
                    data=is_data,
                    strategy_config=test_config,
                    initial_capital=self.initial_capital,
                    commission=self.commission,
                )
                
                result = await engine.run_async()
                
                if result and "metrics" in result:
                    metrics = result["metrics"]
                    current_value = metrics.get(metric, -np.inf)
                    
                    if current_value > best_metric_value:
                        best_metric_value = current_value
                        best_params = params
                        best_metrics = metrics

            except Exception as e:
                logger.debug(f"[WalkForward] Ошибка при тестировании {params}: {e}")
                continue

        if best_params:
            logger.success(
                f"[WalkForward] Окно #{window.window_id}: "
                f"найдены параметры {best_params}, {metric}={best_metric_value:.4f}"
            )
        else:
            logger.warning(f"[WalkForward] Окно #{window.window_id}: не найдено параметров")

        return best_params, best_metrics

    async def _test_window(
        self,
        window: WalkForwardWindow,
        strategy_config: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Тестирует параметры на OOS окне
        
        Args:
            window: Окно для тестирования
            strategy_config: Базовая конфигурация стратегии
            params: Параметры для тестирования
        
        Returns:
            Словарь с метриками производительности
        """
        oos_data = self._get_window_data(window.oos_start, window.oos_end)

        if len(oos_data) == 0:
            logger.warning(f"[WalkForward] Нет OOS данных для окна {window}")
            return {}

        # Объединяем с базовой конфигурацией
        test_config = {**strategy_config, **params}

        try:
            # Запускаем backtest на OOS данных
            engine = BacktestEngine(
                data=oos_data,
                strategy_config=test_config,
                initial_capital=self.initial_capital,
                commission=self.commission,
            )
            
            result = await engine.run_async()
            
            if result and "metrics" in result:
                metrics = result["metrics"]
                logger.info(
                    f"[WalkForward] Окно #{window.window_id} OOS: "
                    f"profit={metrics.get('net_profit', 0):.2f}, "
                    f"trades={metrics.get('total_trades', 0)}"
                )
                return metrics
            else:
                return {}

        except Exception as e:
            logger.error(f"[WalkForward] Ошибка при тестировании OOS: {e}")
            return {}

    async def run_async(
        self,
        strategy_config: Dict[str, Any],
        param_space: Dict[str, List],
        metric: str = "sharpe_ratio"
    ) -> Dict[str, Any]:
        """
        Запускает Walk-Forward анализ (асинхронная версия)
        
        Args:
            strategy_config: Базовая конфигурация стратегии
            param_space: Пространство параметров для оптимизации
            metric: Метрика для оценки
        
        Returns:
            Словарь с результатами:
            - windows: список результатов по окнам
            - summary: агрегированная статистика
        """
        logger.info(
            f"[WalkForward] Запуск анализа: {len(self.windows)} окон, "
            f"метрика={metric}"
        )

        all_results = []

        for window in self.windows:
            # 1. Оптимизация на IS окне
            logger.info(f"[WalkForward] Обработка окна #{window.window_id}")
            
            best_params, is_metrics = await self._optimize_window(
                window=window,
                strategy_config=strategy_config,
                param_space=param_space,
                metric=metric
            )

            if not best_params:
                logger.warning(
                    f"[WalkForward] Окно #{window.window_id}: "
                    f"пропускаем (не найдено параметров)"
                )
                continue

            window.best_params = best_params
            window.is_metrics = is_metrics

            # 2. Тестирование на OOS окне
            oos_metrics = await self._test_window(
                window=window,
                strategy_config=strategy_config,
                params=best_params
            )

            window.oos_metrics = oos_metrics

            # Сохраняем результат
            result_row = window.to_dict()
            all_results.append(result_row)

        # Вычисляем сводную статистику
        summary = self._calculate_summary(all_results, metric)

        logger.success(
            f"[WalkForward] ✅ Анализ завершён: "
            f"{len(all_results)}/{len(self.windows)} окон обработано"
        )

        return {
            "windows": all_results,
            "summary": summary,
            "config": {
                "is_window_days": self.is_window_days,
                "oos_window_days": self.oos_window_days,
                "step_days": self.step_days,
                "metric": metric,
                "total_windows": len(self.windows),
                "successful_windows": len(all_results),
            }
        }

    def _calculate_summary(
        self,
        results: List[Dict[str, Any]],
        metric: str
    ) -> Dict[str, Any]:
        """Вычисляет сводную статистику по всем окнам"""
        if not results:
            return {}

        # Извлекаем OOS метрики
        oos_profits = []
        oos_trades = []
        oos_metric_values = []
        positive_windows = 0

        for result in results:
            oos_metrics = result.get("oos_metrics", {})
            if oos_metrics:
                profit = oos_metrics.get("net_profit", 0)
                trades = oos_metrics.get("total_trades", 0)
                metric_value = oos_metrics.get(metric, 0)

                oos_profits.append(profit)
                oos_trades.append(trades)
                oos_metric_values.append(metric_value)

                if profit > 0:
                    positive_windows += 1

        total_windows = len(results)

        summary = {
            "total_windows": total_windows,
            "positive_windows": positive_windows,
            "positive_window_rate": positive_windows / total_windows if total_windows > 0 else 0,
            "total_oos_profit": sum(oos_profits),
            "average_oos_profit": np.mean(oos_profits) if oos_profits else 0,
            "median_oos_profit": np.median(oos_profits) if oos_profits else 0,
            "std_oos_profit": np.std(oos_profits) if oos_profits else 0,
            "total_oos_trades": sum(oos_trades),
            "average_oos_trades": np.mean(oos_trades) if oos_trades else 0,
            f"average_oos_{metric}": np.mean(oos_metric_values) if oos_metric_values else 0,
            f"median_oos_{metric}": np.median(oos_metric_values) if oos_metric_values else 0,
        }

        return summary


def calculate_wfo_windows(
    total_days: int,
    is_window: int,
    oos_window: int,
    step: int
) -> int:
    """
    Вычисляет количество Walk-Forward окон
    
    Args:
        total_days: Общий период данных (дней)
        is_window: Размер In-Sample окна (дней)
        oos_window: Размер Out-of-Sample окна (дней)
        step: Шаг сдвига окон (дней)
    
    Returns:
        Количество окон
    """
    window_size = is_window + oos_window
    available_range = total_days - window_size

    if available_range < 0:
        return 0

    num_windows = (available_range // step) + 1
    return num_windows
