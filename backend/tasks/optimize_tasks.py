"""
Optimization Tasks

Celery задачи для оптимизации стратегий (grid search, walk-forward, Bayesian).
"""

from datetime import UTC, datetime
from itertools import product
from typing import Any

from celery import Task
from loguru import logger

from backend.celery_app import celery_app
from backend.config.constants import COMMISSION_TV
from backend.core.engine_adapter import get_engine
from backend.database import SessionLocal
from backend.models import Optimization
from backend.services.data_service import DataService


class OptimizationTask(Task):
    """Базовый класс для задач оптимизации"""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Обработчик ошибок"""
        logger.error(f"❌ Optimization task {task_id} failed: {exc}")

        optimization_id = kwargs.get("optimization_id") or (args[0] if args else None)
        if optimization_id:
            try:
                db = SessionLocal()
                opt = db.query(Optimization).filter(Optimization.id == optimization_id).first()
                if opt:
                    opt.status = "failed"
                    opt.error_message = str(exc)
                    opt.updated_at = datetime.now(UTC)
                    db.commit()
                db.close()
            except Exception as e:
                logger.error(f"Failed to update optimization status: {e}")

    def on_success(self, retval, task_id, args, kwargs):
        """Обработчик успешного выполнения"""
        logger.info(f"✅ Optimization task {task_id} completed")


@celery_app.task(
    bind=True,
    base=OptimizationTask,
    name="backend.tasks.optimize_tasks.grid_search",
    max_retries=2,
)
def grid_search_task(
    self,
    optimization_id: int,
    strategy_config: dict[str, Any],
    param_space: dict[str, list],
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    metric: str = "sharpe_ratio",
) -> dict[str, Any]:
    """
    Grid Search оптимизация

    Args:
        optimization_id: ID записи оптимизации
        strategy_config: Базовая конфигурация стратегии
        param_space: Пространство параметров {param_name: [value1, value2, ...]}
        symbol: Торговая пара
        interval: Таймфрейм
        start_date: Дата начала
        end_date: Дата окончания
        metric: Метрика для оптимизации (sharpe_ratio, total_return, profit_factor)

    Returns:
        Лучшие параметры и результаты
    """
    logger.info(f"🔍 Starting grid search: optimization {optimization_id}")
    logger.info(f"   Param space: {param_space}")

    db = SessionLocal()
    data_service = DataService(db)

    try:
        # Обновить статус через DataService
        opt = data_service.get_optimization(optimization_id)
        if not opt:
            raise ValueError(f"Optimization {optimization_id} not found")

        data_service.update_optimization(optimization_id, status="running", started_at=datetime.now(UTC))

        # Загрузить данные
        logger.info("📥 Loading market data...")
        data_service = DataService(db)
        candles = data_service.get_market_data(
            symbol=symbol, timeframe=interval, start_time=start_date, end_time=end_date
        )

        if candles.empty:
            raise ValueError(f"No data for {symbol} {interval}")

        logger.info(f"📊 Loaded {len(candles)} candles")

        # Генерация всех комбинаций параметров
        param_names = list(param_space.keys())
        param_values = list(param_space.values())
        combinations = list(product(*param_values))

        total_combinations = len(combinations)
        logger.info(f"🔢 Testing {total_combinations} parameter combinations")

        # Прогресс
        self.update_state(state="PROGRESS", meta={"current": 0, "total": total_combinations})

        # Запуск бэктестов для каждой комбинации
        results = []
        best_score = float("-inf")
        best_params = None
        best_result = None

        engine = get_engine(None, initial_capital=10000.0, commission=0.0007)  # 0.07% TradingView parity

        for idx, params in enumerate(combinations, 1):
            # Обновить конфигурацию стратегии
            test_config = strategy_config.copy()
            for param_name, param_value in zip(param_names, params, strict=False):
                test_config[param_name] = param_value

            # Запустить бэктест
            try:
                result = engine.run(data=candles, strategy_config=test_config)
                score = result.get(metric, 0)

                results.append(
                    {
                        "params": dict(zip(param_names, params, strict=False)),
                        "score": score,
                        "metrics": {
                            "total_return": result.get("total_return"),
                            "sharpe_ratio": result.get("sharpe_ratio"),
                            "max_drawdown": result.get("max_drawdown"),
                            "win_rate": result.get("win_rate"),
                            "total_trades": result.get("total_trades"),
                        },
                    }
                )

                # Обновить лучший результат
                if score > best_score:
                    best_score = score
                    best_params = dict(zip(param_names, params, strict=False))
                    best_result = result

                # Обновить прогресс
                if idx % 10 == 0 or idx == total_combinations:
                    logger.info(f"Progress: {idx}/{total_combinations} ({idx / total_combinations * 100:.1f}%)")
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": idx,
                            "total": total_combinations,
                            "best_score": best_score,
                            "best_params": best_params,
                        },
                    )

            except Exception as e:
                logger.warning(f"Backtest failed for params {params}: {e}")
                continue

        # Сортировать результаты по метрике
        results.sort(key=lambda x: x["score"], reverse=True)

        # Сохранить результаты
        logger.info("💾 Saving optimization results...")
        # Сохранить результаты через DataService
        data_service.update_optimization(
            optimization_id,
            status="completed",
            completed_at=datetime.now(UTC),
            best_params=best_params,
            best_score=best_score,
            results={
                "metric": metric,
                "total_combinations": total_combinations,
                "best_params": best_params,
                "best_score": best_score,
                "best_metrics": best_result,
                "top_10": results[:10],
            },
        )

        logger.info("✅ Grid search completed")
        logger.info(f"   Best {metric}: {best_score:.4f}")
        logger.info(f"   Best params: {best_params}")

        return {
            "optimization_id": optimization_id,
            "status": "completed",
            "best_params": best_params,
            "best_score": best_score,
            "total_combinations": total_combinations,
        }

    except Exception as e:
        logger.error(f"❌ Grid search failed: {e}")

        try:
            data_service.update_optimization(
                optimization_id,
                status="failed",
                error_message=str(e),
                completed_at=datetime.now(UTC),
            )
        except Exception as db_error:
            logger.error(f"Failed to update optimization status: {db_error}")

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        raise

    finally:
        db.close()


@celery_app.task(bind=True, base=OptimizationTask, name="backend.tasks.optimize_tasks.walk_forward")
def walk_forward_task(
    self,
    optimization_id: int,
    strategy_config: dict[str, Any],
    param_space: dict[str, list],
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    train_size: int = 120,  # Training days (IS window)
    test_size: int = 60,  # Testing days (OOS window)
    step_size: int = 30,  # Step size for rolling window
    metric: str = "sharpe_ratio",  # Optimization metric
) -> dict[str, Any]:
    """
    Walk-Forward оптимизация

    Разделяет данные на периоды train/test, оптимизирует на train,
    тестирует на test, затем сдвигает окно.

    Args:
        optimization_id: ID оптимизации
        strategy_config: Базовая конфигурация
        param_space: Пространство параметров
        symbol: Торговая пара
        interval: Таймфрейм
        start_date: Дата начала
        end_date: Дата окончания
        train_size: Размер окна обучения (в днях, IS window)
        test_size: Размер окна тестирования (в днях, OOS window)
        step_size: Шаг сдвига окна (в днях)
        metric: Метрика для оптимизации

    Returns:
        Результаты walk-forward
    """
    import asyncio
    from datetime import datetime

    from backend.core.walkforward import WalkForwardAnalyzer
    from backend.services.data_service import DataService

    logger.info(f"🚶 Starting walk-forward optimization: {optimization_id}")
    logger.info(f"   Symbol: {symbol}, Interval: {interval}")
    logger.info(f"   Train: {train_size}d, Test: {test_size}d, Step: {step_size}d")
    logger.info(f"   Metric: {metric}")

    try:
        # 1. Загружаем данные
        self.update_state(
            state="PROGRESS",
            meta={
                "optimization_id": optimization_id,
                "status": "loading_data",
                "progress": 0,
            },
        )

        data_service = DataService()
        data = data_service.get_candles(symbol=symbol, interval=interval, start_date=start_date, end_date=end_date)

        if data is None or len(data) == 0:
            raise ValueError(f"No data available for {symbol} {interval}")

        logger.info(f"📊 Loaded {len(data)} candles")

        # 2. Создаём Walk-Forward Analyzer
        self.update_state(
            state="PROGRESS",
            meta={
                "optimization_id": optimization_id,
                "status": "initializing",
                "progress": 10,
            },
        )

        analyzer = WalkForwardAnalyzer(
            data=data,
            initial_capital=strategy_config.get("initial_capital", 10000.0),
            commission=strategy_config.get("commission", COMMISSION_TV),
            is_window_days=train_size,
            oos_window_days=test_size,
            step_days=step_size,
        )

        num_windows = len(analyzer.windows)
        logger.info(f"🪟 Created {num_windows} windows for analysis")

        # 3. Запускаем Walk-Forward анализ
        self.update_state(
            state="PROGRESS",
            meta={
                "optimization_id": optimization_id,
                "status": "optimizing",
                "progress": 20,
                "num_windows": num_windows,
            },
        )

        # Запускаем асинхронную версию в event loop
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        results = loop.run_until_complete(
            analyzer.run_async(strategy_config=strategy_config, param_space=param_space, metric=metric)
        )

        # 4. Формируем результат
        self.update_state(
            state="PROGRESS",
            meta={
                "optimization_id": optimization_id,
                "status": "completed",
                "progress": 100,
            },
        )

        logger.success(
            f"✅ Walk-forward completed: {optimization_id}, processed {len(results['windows'])}/{num_windows} windows"
        )

        return {
            "optimization_id": optimization_id,
            "method": "walk_forward",
            "symbol": symbol,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date,
            "config": {
                "train_size": train_size,
                "test_size": test_size,
                "step_size": step_size,
                "metric": metric,
            },
            "results": results,
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Walk-forward failed: {optimization_id}, error: {e}")
        self.update_state(
            state="FAILURE",
            meta={
                "optimization_id": optimization_id,
                "error": str(e),
            },
        )
        raise


@celery_app.task(
    bind=True,
    base=OptimizationTask,
    name="backend.tasks.optimize_tasks.bayesian_optimization",
)
def bayesian_optimization_task(
    self,
    optimization_id: int,
    strategy_config: dict[str, Any],
    param_space: dict[str, dict[str, Any]],  # {param: {type, low, high}}
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    n_trials: int = 100,
    metric: str = "sharpe_ratio",
    direction: str = "maximize",
    n_jobs: int = 1,
    random_state: int | None = None,
) -> dict[str, Any]:
    """
    Bayesian Optimization используя Optuna

    Использует Tree-structured Parzen Estimator (TPE) для умного поиска
    оптимальных параметров. Значительно быстрее Grid Search.

    Args:
        optimization_id: ID оптимизации
        strategy_config: Базовая конфигурация
        param_space: Пространство параметров
            Формат: {param_name: {type: 'int'|'float'|'categorical', low: X, high: Y}}
            Пример: {'period': {'type': 'int', 'low': 10, 'high': 100}}
        symbol: Торговая пара
        interval: Таймфрейм
        start_date: Дата начала
        end_date: Дата окончания
        n_trials: Количество попыток оптимизации
        metric: Метрика для оптимизации
        direction: 'maximize' или 'minimize'
        n_jobs: Количество параллельных процессов
        random_state: Seed для воспроизводимости

    Returns:
        Результаты Bayesian optimization
    """
    import asyncio
    from datetime import datetime

    from backend.core.bayesian import BayesianOptimizer
    from backend.services.data_service import DataService

    logger.info(f"🧠 Starting Bayesian optimization: {optimization_id}")
    logger.info(f"   Symbol: {symbol}, Interval: {interval}")
    logger.info(f"   Trials: {n_trials}, Metric: {metric}, Direction: {direction}")

    try:
        # 1. Загружаем данные
        self.update_state(
            state="PROGRESS",
            meta={
                "optimization_id": optimization_id,
                "status": "loading_data",
                "progress": 0,
            },
        )

        data_service = DataService()
        data = data_service.get_candles(symbol=symbol, interval=interval, start_date=start_date, end_date=end_date)

        if data is None or len(data) == 0:
            raise ValueError(f"No data available for {symbol} {interval}")

        logger.info(f"📊 Loaded {len(data)} candles")

        # 2. Создаём Bayesian Optimizer
        self.update_state(
            state="PROGRESS",
            meta={
                "optimization_id": optimization_id,
                "status": "initializing",
                "progress": 10,
            },
        )

        optimizer = BayesianOptimizer(
            data=data,
            initial_capital=strategy_config.get("initial_capital", 10000.0),
            commission=strategy_config.get("commission", COMMISSION_TV),
            n_trials=n_trials,
            n_jobs=n_jobs,
            random_state=random_state,
        )

        logger.info(f"🎯 Initialized Bayesian Optimizer with {n_trials} trials")

        # 3. Запускаем Bayesian optimization
        self.update_state(
            state="PROGRESS",
            meta={
                "optimization_id": optimization_id,
                "status": "optimizing",
                "progress": 20,
                "n_trials": n_trials,
            },
        )

        # Запускаем асинхронную версию в event loop
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        results = loop.run_until_complete(
            optimizer.optimize_async(
                strategy_config=strategy_config,
                param_space=param_space,
                metric=metric,
                direction=direction,
                show_progress=False,  # Не показываем progress bar в Celery
            )
        )

        # 4. Вычисляем важность параметров
        try:
            param_importance = optimizer.get_importance()
            results["param_importance"] = param_importance
        except Exception as e:
            logger.warning(f"Could not compute param importance: {e}")
            results["param_importance"] = {}

        # 5. Формируем результат
        self.update_state(
            state="PROGRESS",
            meta={
                "optimization_id": optimization_id,
                "status": "completed",
                "progress": 100,
            },
        )

        logger.success(
            f"✅ Bayesian optimization completed: {optimization_id}, "
            f"best {metric}={results['best_value']:.4f}, "
            f"completed trials={results['statistics']['completed_trials']}/{n_trials}"
        )

        return {
            "optimization_id": optimization_id,
            "method": "bayesian",
            "symbol": symbol,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date,
            "config": {
                "n_trials": n_trials,
                "metric": metric,
                "direction": direction,
                "n_jobs": n_jobs,
            },
            "results": results,
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Bayesian optimization failed: {optimization_id}, error: {e}")
        self.update_state(
            state="FAILURE",
            meta={
                "optimization_id": optimization_id,
                "error": str(e),
            },
        )
        raise
