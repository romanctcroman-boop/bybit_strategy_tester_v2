"""
Backtest Tasks

Celery задачи для запуска бэктестов в фоновом режиме.
"""

from typing import Dict, Any
from datetime import datetime

from celery import Task
from loguru import logger
from sqlalchemy.orm import Session

from backend.celery_app import celery_app
from backend.database import SessionLocal, Backtest
from backend.core.backtest_engine import BacktestEngine
from backend.services.data_service import DataService


class BacktestTask(Task):
    """Базовый класс для задач бэктеста с обработкой ошибок"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Обработчик ошибок"""
        logger.error(f"❌ Backtest task {task_id} failed: {exc}")
        
        # Обновить статус в БД
        backtest_id = kwargs.get("backtest_id") or (args[0] if args else None)
        if backtest_id:
            try:
                db = SessionLocal()
                backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
                if backtest:
                    backtest.status = "failed"
                    backtest.error_message = str(exc)
                    backtest.updated_at = datetime.utcnow()
                    db.commit()
                db.close()
            except Exception as e:
                logger.error(f"Failed to update backtest status: {e}")
    
    def on_success(self, retval, task_id, args, kwargs):
        """Обработчик успешного выполнения"""
        logger.info(f"✅ Backtest task {task_id} completed successfully")


@celery_app.task(
    bind=True,
    base=BacktestTask,
    name="backend.tasks.backtest_tasks.run_backtest",
    max_retries=3,
    default_retry_delay=60
)
def run_backtest_task(
    self,
    backtest_id: int,
    strategy_config: Dict[str, Any],
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 10000.0
) -> Dict[str, Any]:
    """
    Запустить бэктест асинхронно
    
    Args:
        backtest_id: ID записи бэктеста в БД
        strategy_config: Конфигурация стратегии
        symbol: Торговая пара (например, "BTCUSDT")
        interval: Таймфрейм (например, "1h")
        start_date: Дата начала (ISO format)
        end_date: Дата окончания (ISO format)
        initial_capital: Начальный капитал
    
    Returns:
        Результаты бэктеста
    """
    logger.info(f"🚀 Starting backtest task: {backtest_id}")
    logger.info(f"   Symbol: {symbol}, Interval: {interval}")
    logger.info(f"   Period: {start_date} → {end_date}")
    
    db = SessionLocal()
    data_service = DataService(db)
    
    try:
        # Обновить статус на "running" через DataService
        backtest = data_service.get_backtest(backtest_id)
        if not backtest:
            raise ValueError(f"Backtest {backtest_id} not found")
        data_service.update_backtest(backtest_id, status="running", started_at=datetime.utcnow())
        
        # Загрузить данные
        logger.info("📥 Loading market data...")
        data_service = DataService(db)
        candles = data_service.get_market_data(
            symbol=symbol,
            timeframe=interval,
            start_time=start_date,
            end_time=end_date
        )
        
        if candles.empty:
            raise ValueError(f"No data available for {symbol} {interval}")
        
        logger.info(f"📊 Loaded {len(candles)} candles")
        
        # Запустить бэктест
        logger.info("⚙️  Running backtest engine...")
        engine = BacktestEngine(
            initial_capital=initial_capital,
            commission=0.0006,  # 0.06% Bybit taker fee
            slippage=0.0001,    # 0.01% slippage
        )
        
        results = engine.run(
            data=candles,
            strategy_config=strategy_config
        )
        
        # Сохранить результаты
        logger.info("💾 Saving results...")
        # Сохранить результаты через DataService
        data_service.update_backtest_results(
            backtest_id=backtest_id,
            final_capital=results.get('final_capital', 0),
            total_return=results.get('total_return', 0),
            total_trades=results.get('total_trades', 0),
            winning_trades=results.get('winning_trades', 0),
            losing_trades=results.get('losing_trades', 0),
            win_rate=results.get('win_rate', 0),
            sharpe_ratio=results.get('sharpe_ratio', 0),
            max_drawdown=results.get('max_drawdown', 0),
            results=results
        )
        
        logger.info(f"✅ Backtest {backtest_id} completed")
        logger.info(f"   Total Return: {results.get('total_return', 0):.2%}")
        logger.info(f"   Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
        logger.info(f"   Total Trades: {results.get('total_trades', 0)}")
        
        return {
            "backtest_id": backtest_id,
            "status": "completed",
            "results": results
        }
    
    except Exception as e:
        logger.error(f"❌ Backtest task failed: {e}")
        
        # Обновить статус на "failed"
        try:
            # Update using DataService
            data_service.update_backtest(backtest_id, status="failed", error_message=str(e), completed_at=datetime.utcnow())
        except Exception as db_error:
            logger.error(f"Failed to update backtest status: {db_error}")
        
        # Retry если возможно
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying backtest {backtest_id} (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e)
        
        raise
    
    finally:
        db.close()


@celery_app.task(name="backend.tasks.backtest_tasks.bulk_backtest")
def bulk_backtest_task(backtest_configs: list) -> Dict[str, Any]:
    """
    Запустить несколько бэктестов параллельно
    
    Args:
        backtest_configs: Список конфигураций для бэктестов
    
    Returns:
        Результаты всех бэктестов
    """
    logger.info(f"🚀 Starting bulk backtest: {len(backtest_configs)} backtests")
    
    # Запустить задачи параллельно
    from celery import group
    job = group([
        run_backtest_task.s(**config)
        for config in backtest_configs
    ])
    
    result = job.apply_async()
    
    return {
        "task_id": result.id,
        "total_backtests": len(backtest_configs),
        "status": "pending"
    }
