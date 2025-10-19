"""
Bayesian Optimization Module

Модуль для умной оптимизации гиперпараметров стратегий используя Bayesian подход.
Использует Optuna - современную библиотеку для hyperparameter optimization.

Преимущества Bayesian optimization над Grid Search:
- Значительно быстрее (меньше итераций)
- Умнее (использует информацию из предыдущих попыток)
- Находит лучшие параметры
- Адаптивно распределяет ресурсы

Author: Bybit Strategy Tester Team
Date: October 2025
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import optuna
from loguru import logger
from optuna.samplers import TPESampler

from backend.core.backtest import BacktestEngine


class BayesianOptimizer:
    """
    Класс для Bayesian оптимизации стратегий используя Optuna
    
    Optuna использует Tree-structured Parzen Estimator (TPE) algorithm
    для умного поиска оптимальных параметров.
    
    Example:
        >>> optimizer = BayesianOptimizer(
        ...     data=df,
        ...     initial_capital=10000,
        ...     n_trials=100
        ... )
        >>> results = await optimizer.optimize_async(
        ...     strategy_config={'type': 'MA_Crossover'},
        ...     param_space={
        ...         'fast_period': {'type': 'int', 'low': 5, 'high': 50},
        ...         'slow_period': {'type': 'int', 'low': 20, 'high': 200}
        ...     },
        ...     metric='sharpe_ratio'
        ... )
    """

    def __init__(
        self,
        data,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        n_trials: int = 100,
        n_jobs: int = 1,
        random_state: Optional[int] = None,
    ):
        """
        Args:
            data: DataFrame с историческими данными (OHLCV + timestamp)
            initial_capital: Начальный капитал
            commission: Комиссия за сделку
            n_trials: Количество попыток оптимизации
            n_jobs: Количество параллельных процессов (1 = последовательно)
            random_state: Seed для воспроизводимости результатов
        """
        self.data = data
        self.initial_capital = initial_capital
        self.commission = commission
        self.n_trials = n_trials
        self.n_jobs = n_jobs
        self.random_state = random_state

        # Optuna study
        self.study: Optional[optuna.Study] = None
        self.best_params: Optional[Dict[str, Any]] = None
        self.best_value: Optional[float] = None

    async def _objective(
        self,
        trial: optuna.Trial,
        strategy_config: Dict[str, Any],
        param_space: Dict[str, Dict[str, Any]],
        metric: str
    ) -> float:
        """
        Objective function для Optuna
        
        Args:
            trial: Optuna trial object
            strategy_config: Базовая конфигурация стратегии
            param_space: Пространство параметров
            metric: Метрика для оптимизации
        
        Returns:
            Значение метрики (для максимизации)
        """
        # Генерируем параметры используя Optuna suggest_*
        params = {}
        
        for param_name, param_config in param_space.items():
            param_type = param_config.get("type", "float")
            
            if param_type == "int":
                params[param_name] = trial.suggest_int(
                    param_name,
                    param_config["low"],
                    param_config["high"],
                    step=param_config.get("step", 1)
                )
            elif param_type == "float":
                params[param_name] = trial.suggest_float(
                    param_name,
                    param_config["low"],
                    param_config["high"],
                    step=param_config.get("step"),
                    log=param_config.get("log", False)
                )
            elif param_type == "categorical":
                params[param_name] = trial.suggest_categorical(
                    param_name,
                    param_config["choices"]
                )
            else:
                raise ValueError(f"Unknown parameter type: {param_type}")

        # Объединяем с базовой конфигурацией
        test_config = {**strategy_config, **params}

        try:
            # Запускаем backtest
            engine = BacktestEngine(
                data=self.data,
                strategy_config=test_config,
                initial_capital=self.initial_capital,
                commission=self.commission,
            )
            
            result = await engine.run_async()
            
            if result and "metrics" in result:
                metrics = result["metrics"]
                metric_value = metrics.get(metric, -np.inf)
                
                # Добавляем дополнительные метрики для анализа
                trial.set_user_attr("net_profit", metrics.get("net_profit", 0))
                trial.set_user_attr("total_trades", metrics.get("total_trades", 0))
                trial.set_user_attr("win_rate", metrics.get("win_rate", 0))
                trial.set_user_attr("max_drawdown", metrics.get("max_drawdown", 0))
                
                return metric_value
            else:
                return -np.inf

        except Exception as e:
            logger.debug(f"[Bayesian] Trial failed with params {params}: {e}")
            return -np.inf

    async def optimize_async(
        self,
        strategy_config: Dict[str, Any],
        param_space: Dict[str, Dict[str, Any]],
        metric: str = "sharpe_ratio",
        direction: str = "maximize",
        pruner: Optional[optuna.pruners.BasePruner] = None,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Запускает Bayesian оптимизацию (асинхронная версия)
        
        Args:
            strategy_config: Базовая конфигурация стратегии
            param_space: Пространство параметров
            metric: Метрика для оптимизации
            direction: 'maximize' или 'minimize'
            pruner: Optuna pruner для ранней остановки неудачных trials
            show_progress: Показывать прогресс
        
        Returns:
            Словарь с результатами:
            - best_params: лучшие параметры
            - best_value: лучшее значение метрики
            - trials_data: детальная информация о всех trials
        """
        logger.info(
            f"[Bayesian] Запуск оптимизации: {self.n_trials} trials, "
            f"метрика={metric}, direction={direction}"
        )

        # Создаём Optuna study
        sampler = TPESampler(seed=self.random_state)
        
        if pruner is None:
            pruner = optuna.pruners.MedianPruner(
                n_startup_trials=10,
                n_warmup_steps=5,
                interval_steps=1
            )

        self.study = optuna.create_study(
            direction=direction,
            sampler=sampler,
            pruner=pruner
        )

        # Создаём wrapper для асинхронного вызова
        async def objective_wrapper(trial):
            return await self._objective(
                trial=trial,
                strategy_config=strategy_config,
                param_space=param_space,
                metric=metric
            )

        # Запускаем оптимизацию
        # Optuna пока не поддерживает async, поэтому используем run_in_executor
        loop = asyncio.get_event_loop()
        
        def sync_objective(trial):
            # Запускаем async функцию в синхронном контексте
            return loop.run_until_complete(objective_wrapper(trial))

        # Optimize с прогресс-баром (если нужен)
        if show_progress:
            with optuna.logging.tqdm.tqdm(total=self.n_trials) as pbar:
                def callback(study, trial):
                    pbar.update(1)
                    if trial.value is not None:
                        pbar.set_postfix({
                            "best": f"{study.best_value:.4f}",
                            "current": f"{trial.value:.4f}"
                        })
                
                self.study.optimize(
                    sync_objective,
                    n_trials=self.n_trials,
                    n_jobs=self.n_jobs,
                    callbacks=[callback]
                )
        else:
            self.study.optimize(
                sync_objective,
                n_trials=self.n_trials,
                n_jobs=self.n_jobs
            )

        # Извлекаем результаты
        self.best_params = self.study.best_params
        self.best_value = self.study.best_value

        logger.success(
            f"[Bayesian] ✅ Оптимизация завершена: "
            f"best {metric}={self.best_value:.4f}, params={self.best_params}"
        )

        # Собираем информацию о всех trials
        trials_data = []
        for trial in self.study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                trial_info = {
                    "trial_number": trial.number,
                    "value": trial.value,
                    "params": trial.params,
                    "user_attrs": trial.user_attrs,
                    "datetime_start": trial.datetime_start.isoformat() if trial.datetime_start else None,
                    "datetime_complete": trial.datetime_complete.isoformat() if trial.datetime_complete else None,
                    "duration_seconds": trial.duration.total_seconds() if trial.duration else None,
                }
                trials_data.append(trial_info)

        # Статистика
        completed_trials = [t for t in self.study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        pruned_trials = [t for t in self.study.trials if t.state == optuna.trial.TrialState.PRUNED]
        failed_trials = [t for t in self.study.trials if t.state == optuna.trial.TrialState.FAIL]

        statistics = {
            "total_trials": len(self.study.trials),
            "completed_trials": len(completed_trials),
            "pruned_trials": len(pruned_trials),
            "failed_trials": len(failed_trials),
            "best_trial_number": self.study.best_trial.number,
        }

        return {
            "best_params": self.best_params,
            "best_value": self.best_value,
            "best_trial": {
                "number": self.study.best_trial.number,
                "value": self.study.best_value,
                "params": self.study.best_params,
                "user_attrs": self.study.best_trial.user_attrs,
            },
            "trials_data": trials_data,
            "statistics": statistics,
            "metric": metric,
            "direction": direction,
        }

    def get_importance(self) -> Dict[str, float]:
        """
        Вычисляет важность параметров (feature importance)
        
        Returns:
            Словарь {param_name: importance_score}
        """
        if self.study is None:
            raise ValueError("Необходимо сначала запустить optimize_async()")

        try:
            importance = optuna.importance.get_param_importances(self.study)
            return dict(importance)
        except Exception as e:
            logger.warning(f"[Bayesian] Не удалось вычислить importance: {e}")
            return {}

    def get_pareto_front(self) -> List[optuna.trial.FrozenTrial]:
        """
        Получает Pareto front для multi-objective optimization
        
        Returns:
            Список trials на Pareto front
        """
        if self.study is None:
            raise ValueError("Необходимо сначала запустить optimize_async()")

        try:
            return self.study.best_trials
        except Exception as e:
            logger.warning(f"[Bayesian] Не удалось получить Pareto front: {e}")
            return []

    def plot_optimization_history(self, filename: Optional[str] = None):
        """
        Визуализирует историю оптимизации
        
        Args:
            filename: Путь для сохранения графика (если None - показывает)
        """
        if self.study is None:
            raise ValueError("Необходимо сначала запустить optimize_async()")

        try:
            import optuna.visualization as vis
            
            fig = vis.plot_optimization_history(self.study)
            
            if filename:
                fig.write_image(filename)
                logger.info(f"[Bayesian] График сохранён: {filename}")
            else:
                fig.show()
                
        except Exception as e:
            logger.error(f"[Bayesian] Ошибка при создании графика: {e}")

    def plot_param_importances(self, filename: Optional[str] = None):
        """
        Визуализирует важность параметров
        
        Args:
            filename: Путь для сохранения графика (если None - показывает)
        """
        if self.study is None:
            raise ValueError("Необходимо сначала запустить optimize_async()")

        try:
            import optuna.visualization as vis
            
            fig = vis.plot_param_importances(self.study)
            
            if filename:
                fig.write_image(filename)
                logger.info(f"[Bayesian] График важности сохранён: {filename}")
            else:
                fig.show()
                
        except Exception as e:
            logger.error(f"[Bayesian] Ошибка при создании графика важности: {e}")
