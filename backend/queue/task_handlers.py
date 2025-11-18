"""
Обработчики задач для Redis Queue Manager
"""

from datetime import UTC
from typing import Any

from loguru import logger

from backend.core.engine_adapter import get_engine
from backend.database import SessionLocal
from backend.services.data_service import DataService


async def backtest_handler(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Обработчик задачи бэктестинга
    
    Payload должен содержать:
        backtest_id: int - ID бэктеста в БД
        strategy_config: dict - Конфигурация стратегии
        symbol: str - Символ (например, "BTCUSDT")
        interval: str - Интервал (например, "1h")
        start_date: str - Начальная дата
        end_date: str - Конечная дата
        initial_capital: float - Начальный капитал (default: 10000.0)
    """
    backtest_id = payload["backtest_id"]
    logger.info(f"🚀 Starting backtest {backtest_id}")
    
    db = SessionLocal()
    ds = DataService(db)
    
    try:
        # 1. Claim backtest (атомарная операция)
        from datetime import datetime
        now = datetime.now(UTC)
        claimed = ds.claim_backtest_to_run(backtest_id, now, stale_seconds=300)
        
        if claimed["status"] == "completed":
            logger.info(f"Backtest {backtest_id} already completed")
            return {"backtest_id": backtest_id, "status": "completed"}
        
        if claimed["status"] == "running":
            logger.info(f"Backtest {backtest_id} already running by another worker")
            return {"backtest_id": backtest_id, "status": "running"}
        
        if claimed["status"] != "claimed":
            raise ValueError(f"Failed to claim backtest: {claimed['message']}")
        
        logger.info(f"✅ Claimed backtest {backtest_id}")
        
        # 2. Загрузить market data
        candles = ds.get_market_data(
            symbol=payload["symbol"],
            timeframe=payload["interval"],
            start_time=payload["start_date"],
            end_time=payload["end_date"]
        )
        
        if candles is None or candles.empty:
            raise ValueError(f"No market data for {payload['symbol']} {payload['interval']}")
        
        logger.info(f"📊 Loaded {len(candles)} candles")
        
        # 3. Запустить backtest engine
        engine = get_engine(
            None,
            initial_capital=payload.get("initial_capital", 10000.0),
            commission=0.0006,  # 0.06% комиссия Bybit
            slippage_pct=0.0001     # 0.01% slippage
        )
        
        results = engine.run(
            data=candles,
            strategy_config=payload["strategy_config"]
        )
        
        # 4. Сохранить результаты в БД
        # Извлечь только scalar метрики для update_backtest_results
        scalar_results = {
            k: v for k, v in results.items()
            if k in ('final_capital', 'total_return', 'total_trades', 'winning_trades',
                     'losing_trades', 'win_rate', 'sharpe_ratio', 'max_drawdown',
                     'sortino_ratio', 'profit_factor')
        }
        
        ds.update_backtest_results(
            backtest_id=backtest_id,
            **scalar_results
        )
        
        # 5. Обновить статус на completed
        ds.update_backtest(backtest_id, status="completed")
        
        logger.success(f"✅ Backtest {backtest_id} completed: final_capital={results.get('final_capital', 0):.2f}")
        
        return {
            "backtest_id": backtest_id,
            "status": "completed",
            "results": results
        }
    
    except Exception as e:
        logger.error(f"❌ Backtest {backtest_id} failed: {e}", exc_info=True)
        
        # Обновить статус на failed
        ds.update_backtest(
            backtest_id,
            status="failed",
            error_message=str(e)
        )
        
        raise
    
    finally:
        db.close()


async def optimization_handler(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Обработчик задачи оптимизации
    
    Payload должен содержать:
        optimization_id: int - ID оптимизации в БД
        optimization_type: str - Тип ('grid', 'bayesian', 'walk_forward')
        strategy_config: dict - Базовая конфигурация стратегии
        param_space: dict - Пространство параметров для оптимизации
        symbol: str
        interval: str
        start_date: str
        end_date: str
        metric: str - Метрика для оптимизации ('sharpe_ratio', 'total_return', etc.)
    """
    optimization_id = payload["optimization_id"]
    opt_type = payload["optimization_type"]
    
    logger.info(f"🔍 Starting {opt_type} optimization {optimization_id}")
    
    db = SessionLocal()
    ds = DataService(db)
    
    try:
        # TODO: Реализовать логику оптимизации
        # В зависимости от типа делегировать соответствующему оптимизатору
        
        if opt_type == "grid":
            # optimizer = GridSearchOptimizer(...)
            # results = optimizer.optimize(...)
            pass
        elif opt_type == "bayesian":
            # optimizer = BayesianOptimizer(...)
            # results = optimizer.optimize(...)
            pass
        elif opt_type == "walk_forward":
            # analyzer = WalkForwardAnalyzer(...)
            # results = analyzer.run(...)
            pass
        else:
            raise ValueError(f"Unknown optimization type: {opt_type}")
        
        # Обновить статус
        ds.update_optimization(optimization_id, status="completed")
        
        logger.success(f"✅ Optimization {optimization_id} completed")
        
        return {
            "optimization_id": optimization_id,
            "status": "completed",
            # "results": results
        }
    
    except Exception as e:
        logger.error(f"❌ Optimization {optimization_id} failed: {e}", exc_info=True)
        
        ds.update_optimization(
            optimization_id,
            status="failed",
            error_message=str(e)
        )
        
        raise
    
    finally:
        db.close()


async def data_fetch_handler(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Обработчик задачи загрузки market data
    
    Payload:
        symbol: str
        interval: str
        start_date: str
        end_date: str
        force_refresh: bool (default: False)
    """
    symbol = payload["symbol"]
    interval = payload["interval"]
    
    logger.info(f"📥 Fetching market data: {symbol} {interval}")
    
    db = SessionLocal()
    ds = DataService(db)
    
    try:
        # TODO: Использовать BybitAdapter для загрузки данных
        from backend.services.adapters.bybit import BybitAdapter
        
        adapter = BybitAdapter()
        candles = await adapter.get_historical_klines(
            symbol=symbol,
            interval=interval,
            start_time=payload["start_date"],
            end_time=payload["end_date"]
        )
        
        # Сохранить в БД
        # ds.bulk_insert_market_data(candles)
        
        logger.success(f"✅ Fetched {len(candles)} candles for {symbol}")
        
        return {
            "symbol": symbol,
            "interval": interval,
            "candles_count": len(candles),
            "status": "completed"
        }
    
    except Exception as e:
        logger.error(f"❌ Data fetch failed: {e}", exc_info=True)
        raise
    
    finally:
        db.close()
