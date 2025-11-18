"""
Тесты для обработчиков задач Redis Queue (backend/queue/task_handlers.py)

Coverage target: 80 lines, 8.5% → 100%
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pandas as pd

from backend.queue.task_handlers import (
    backtest_handler,
    optimization_handler,
    data_fetch_handler
)


# ==================== FIXTURES ====================

@pytest.fixture
def mock_db_session():
    """Mock SQLAlchemy session"""
    session = MagicMock()
    session.close = Mock()
    return session


@pytest.fixture
def mock_data_service():
    """Mock DataService with common methods"""
    ds = MagicMock()
    
    # Default successful claim
    ds.claim_backtest_to_run.return_value = {
        "status": "claimed",
        "message": "Backtest claimed successfully"
    }
    
    # Default market data
    ds.get_market_data.return_value = pd.DataFrame({
        'timestamp': [1609459200000, 1609462800000, 1609466400000],
        'open': [29000.0, 29100.0, 29200.0],
        'high': [29150.0, 29250.0, 29350.0],
        'low': [28950.0, 29050.0, 29150.0],
        'close': [29100.0, 29200.0, 29300.0],
        'volume': [100.0, 150.0, 120.0]
    })
    
    ds.update_backtest_results = Mock()
    ds.update_backtest = Mock()
    ds.update_optimization = Mock()
    
    return ds


@pytest.fixture
def mock_engine():
    """Mock backtest engine"""
    engine = MagicMock()
    engine.run.return_value = {
        'final_capital': 11500.0,
        'total_return': 15.0,
        'total_trades': 10,
        'winning_trades': 7,
        'losing_trades': 3,
        'win_rate': 70.0,
        'sharpe_ratio': 1.5,
        'max_drawdown': -5.0,
        'sortino_ratio': 2.0,
        'profit_factor': 2.5,
        'trades': []  # Non-scalar, should be filtered
    }
    return engine


@pytest.fixture
def backtest_payload():
    """Standard backtest payload"""
    return {
        "backtest_id": 123,
        "strategy_config": {
            "strategy_type": "bollinger_mean_reversion",
            "params": {"bb_period": 20, "bb_std": 2.0}
        },
        "symbol": "BTCUSDT",
        "interval": "1h",
        "start_date": "2021-01-01",
        "end_date": "2021-12-31",
        "initial_capital": 10000.0
    }


# ==================== TEST CLASS: backtest_handler ====================

class TestBacktestHandler:
    """Тесты для backtest_handler"""
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    @patch('backend.queue.task_handlers.get_engine')
    async def test_backtest_handler_success(
        self, mock_get_engine, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service, mock_engine, backtest_payload
    ):
        """Успешное выполнение бэктеста"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service
        mock_get_engine.return_value = mock_engine
        
        result = await backtest_handler(backtest_payload)
        
        # Проверяем результат
        assert result["backtest_id"] == 123
        assert result["status"] == "completed"
        assert result["results"]["final_capital"] == 11500.0
        
        # Проверяем вызовы
        mock_data_service.claim_backtest_to_run.assert_called_once()
        mock_data_service.get_market_data.assert_called_once_with(
            symbol="BTCUSDT",
            timeframe="1h",
            start_time="2021-01-01",
            end_time="2021-12-31"
        )
        
        # Проверяем фильтрацию scalar метрик
        call_kwargs = mock_data_service.update_backtest_results.call_args.kwargs
        assert 'final_capital' in call_kwargs
        assert 'sharpe_ratio' in call_kwargs
        assert 'trades' not in call_kwargs  # Non-scalar filtered
        
        mock_data_service.update_backtest.assert_called_with(123, status="completed")
        mock_db_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    async def test_backtest_already_completed(
        self, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service, backtest_payload
    ):
        """Бэктест уже завершён"""
        mock_session_local.return_value = mock_db_session
        mock_data_service.claim_backtest_to_run.return_value = {
            "status": "completed",
            "message": "Already completed"
        }
        mock_ds_class.return_value = mock_data_service
        
        result = await backtest_handler(backtest_payload)
        
        assert result["status"] == "completed"
        mock_data_service.get_market_data.assert_not_called()
        mock_db_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    async def test_backtest_already_running(
        self, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service, backtest_payload
    ):
        """Бэктест уже запущен другим воркером"""
        mock_session_local.return_value = mock_db_session
        mock_data_service.claim_backtest_to_run.return_value = {
            "status": "running",
            "message": "Running by another worker"
        }
        mock_ds_class.return_value = mock_data_service
        
        result = await backtest_handler(backtest_payload)
        
        assert result["status"] == "running"
        mock_data_service.get_market_data.assert_not_called()
        mock_db_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    async def test_backtest_claim_failed(
        self, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service, backtest_payload
    ):
        """Не удалось захватить бэктест (claim failed)"""
        mock_session_local.return_value = mock_db_session
        mock_data_service.claim_backtest_to_run.return_value = {
            "status": "error",
            "message": "Database locked"
        }
        mock_ds_class.return_value = mock_data_service
        
        with pytest.raises(ValueError, match="Failed to claim backtest"):
            await backtest_handler(backtest_payload)
        
        mock_db_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    async def test_backtest_no_market_data(
        self, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service, backtest_payload
    ):
        """Нет данных для бэктеста (None)"""
        mock_session_local.return_value = mock_db_session
        mock_data_service.get_market_data.return_value = None
        mock_ds_class.return_value = mock_data_service
        
        with pytest.raises(ValueError, match="No market data"):
            await backtest_handler(backtest_payload)
        
        # Должен обновить статус на failed
        mock_data_service.update_backtest.assert_called_with(
            123,
            status="failed",
            error_message="No market data for BTCUSDT 1h"
        )
        mock_db_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    async def test_backtest_empty_dataframe(
        self, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service, backtest_payload
    ):
        """Пустой DataFrame"""
        mock_session_local.return_value = mock_db_session
        mock_data_service.get_market_data.return_value = pd.DataFrame()
        mock_ds_class.return_value = mock_data_service
        
        with pytest.raises(ValueError, match="No market data"):
            await backtest_handler(backtest_payload)
        
        mock_data_service.update_backtest.assert_called_with(
            123,
            status="failed",
            error_message="No market data for BTCUSDT 1h"
        )
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    @patch('backend.queue.task_handlers.get_engine')
    async def test_backtest_engine_failure(
        self, mock_get_engine, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service, backtest_payload
    ):
        """Engine выбрасывает исключение"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service
        
        mock_engine = MagicMock()
        mock_engine.run.side_effect = RuntimeError("Engine crash")
        mock_get_engine.return_value = mock_engine
        
        with pytest.raises(RuntimeError, match="Engine crash"):
            await backtest_handler(backtest_payload)
        
        # Должен обновить статус на failed
        mock_data_service.update_backtest.assert_called_with(
            123,
            status="failed",
            error_message="Engine crash"
        )
        mock_db_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    @patch('backend.queue.task_handlers.get_engine')
    async def test_backtest_default_initial_capital(
        self, mock_get_engine, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service, mock_engine
    ):
        """Используется дефолтный initial_capital"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service
        mock_get_engine.return_value = mock_engine
        
        payload_no_capital = {
            "backtest_id": 456,
            "strategy_config": {},
            "symbol": "ETHUSDT",
            "interval": "4h",
            "start_date": "2021-01-01",
            "end_date": "2021-12-31"
        }
        
        await backtest_handler(payload_no_capital)
        
        # Проверяем, что передан дефолтный initial_capital=10000.0
        mock_get_engine.assert_called_once()
        call_kwargs = mock_get_engine.call_args.kwargs
        assert call_kwargs['initial_capital'] == 10000.0
        assert call_kwargs['commission'] == 0.0006
        assert call_kwargs['slippage_pct'] == 0.0001


# ==================== TEST CLASS: optimization_handler ====================

class TestOptimizationHandler:
    """Тесты для optimization_handler"""
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    async def test_optimization_grid_type(
        self, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service
    ):
        """Grid optimization (TODO не реализовано)"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service

        # Mock the import statement inside the function
        import sys
        grid_module = MagicMock()
        grid_module.GridSearchOptimizer = MagicMock()
        sys.modules['backend.optimization.grid'] = grid_module

        payload = {
            "optimization_id": 789,
            "optimization_type": "grid",
            "strategy_config": {},
            "param_space": {},
            "symbol": "BTCUSDT",
            "interval": "1h",
            "start_date": "2021-01-01",
            "end_date": "2021-12-31",
            "metric": "sharpe_ratio"
        }

        try:
            result = await optimization_handler(payload)

            assert result["optimization_id"] == 789
            assert result["status"] == "completed"
            mock_data_service.update_optimization.assert_called_with(789, status="completed")
            mock_db_session.close.assert_called_once()
        finally:
            # Cleanup
            if 'backend.optimization.grid' in sys.modules:
                del sys.modules['backend.optimization.grid']
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    async def test_optimization_bayesian_type(
        self, mock_ds_class, mock_session_local, 
        mock_db_session, mock_data_service
    ):
        """Bayesian optimization"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service
        
        # Mock the import
        import sys
        bayesian_module = MagicMock()
        bayesian_module.BayesianOptimizer = MagicMock()
        sys.modules['backend.core.bayesian'] = bayesian_module
        
        payload = {
            "optimization_id": 790,
            "optimization_type": "bayesian",
            "strategy_config": {},
            "param_space": {},
            "symbol": "ETHUSDT",
            "interval": "4h",
            "start_date": "2021-01-01",
            "end_date": "2021-12-31",
            "metric": "total_return"
        }
        
        try:
            result = await optimization_handler(payload)
            
            assert result["status"] == "completed"
            mock_data_service.update_optimization.assert_called_once()
        finally:
            if 'backend.core.bayesian' in sys.modules:
                del sys.modules['backend.core.bayesian']
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    async def test_optimization_walk_forward_type(
        self, mock_ds_class, mock_session_local, 
        mock_db_session, mock_data_service
    ):
        """Walk-forward optimization"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service
        
        # Mock the import
        import sys
        wf_module = MagicMock()
        wf_module.WalkForwardAnalyzer = MagicMock()
        sys.modules['backend.core.walkforward'] = wf_module
        
        payload = {
            "optimization_id": 791,
            "optimization_type": "walk_forward",
            "strategy_config": {},
            "param_space": {},
            "symbol": "SOLUSDT",
            "interval": "15m",
            "start_date": "2021-01-01",
            "end_date": "2021-12-31",
            "metric": "sortino_ratio"
        }
        
        try:
            result = await optimization_handler(payload)
            
            assert result["optimization_id"] == 791
            assert result["status"] == "completed"
        finally:
            if 'backend.core.walkforward' in sys.modules:
                del sys.modules['backend.core.walkforward']
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    async def test_optimization_unknown_type(
        self, mock_ds_class, mock_session_local, mock_db_session, mock_data_service
    ):
        """Неизвестный тип оптимизации"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service
        
        payload = {
            "optimization_id": 999,
            "optimization_type": "quantum_annealing",  # Unsupported
            "strategy_config": {},
            "param_space": {},
            "symbol": "BTCUSDT",
            "interval": "1h",
            "start_date": "2021-01-01",
            "end_date": "2021-12-31",
            "metric": "sharpe_ratio"
        }
        
        with pytest.raises(ValueError, match="Unknown optimization type"):
            await optimization_handler(payload)
        
        # Должен обновить статус на failed
        mock_data_service.update_optimization.assert_called_with(
            999,
            status="failed",
            error_message="Unknown optimization type: quantum_annealing"
        )
        mock_db_session.close.assert_called_once()


# ==================== TEST CLASS: data_fetch_handler ====================

class TestDataFetchHandler:
    """Тесты для data_fetch_handler"""
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    @patch('backend.core.cache.redis.Redis')  # Mock Redis connection to prevent hang
    @patch('backend.services.adapters.bybit.BybitAdapter')  # Patch at import location
    async def test_data_fetch_success(
        self, mock_adapter_class, mock_redis, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service
    ):
        """Успешная загрузка данных"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service
        
        # Mock Redis to prevent connection attempts
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True
        mock_redis.return_value = mock_redis_instance
        
        # Mock BybitAdapter
        mock_adapter = AsyncMock()
        mock_adapter.get_historical_klines.return_value = pd.DataFrame({
            'timestamp': [1609459200000, 1609462800000],
            'open': [29000.0, 29100.0],
            'close': [29100.0, 29200.0]
        })
        mock_adapter_class.return_value = mock_adapter
        
        payload = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "start_date": "2021-01-01",
            "end_date": "2021-01-02",
            "force_refresh": False
        }
        
        result = await data_fetch_handler(payload)
        
        assert result["symbol"] == "BTCUSDT"
        assert result["interval"] == "1h"
        assert result["candles_count"] == 2
        assert result["status"] == "completed"
        
        mock_adapter.get_historical_klines.assert_called_once_with(
            symbol="BTCUSDT",
            interval="1h",
            start_time="2021-01-01",
            end_time="2021-01-02"
        )
        mock_db_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    @patch('backend.core.cache.redis.Redis')  # Mock Redis connection to prevent hang
    @patch('backend.services.adapters.bybit.BybitAdapter')  # Patch at import location
    async def test_data_fetch_adapter_failure(
        self, mock_adapter_class, mock_redis, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service
    ):
        """BybitAdapter выбрасывает исключение"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service
        
        # Mock Redis to prevent connection attempts
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True
        mock_redis.return_value = mock_redis_instance
        
        mock_adapter = AsyncMock()
        mock_adapter.get_historical_klines.side_effect = RuntimeError("API rate limit")
        mock_adapter_class.return_value = mock_adapter
        
        payload = {
            "symbol": "ETHUSDT",
            "interval": "4h",
            "start_date": "2021-01-01",
            "end_date": "2021-12-31"
        }
        
        with pytest.raises(RuntimeError, match="API rate limit"):
            await data_fetch_handler(payload)
        
        mock_db_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    @patch('backend.core.cache.redis.Redis')  # Mock Redis connection to prevent hang
    @patch('backend.services.adapters.bybit.BybitAdapter')  # Patch at import location
    async def test_data_fetch_empty_response(
        self, mock_adapter_class, mock_redis, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service
    ):
        """API вернул пустой DataFrame"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service
        
        # Mock Redis to prevent connection attempts
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True
        mock_redis.return_value = mock_redis_instance
        
        mock_adapter = AsyncMock()
        mock_adapter.get_historical_klines.return_value = pd.DataFrame()  # Empty
        mock_adapter_class.return_value = mock_adapter
        
        payload = {
            "symbol": "UNUSUALCOIN",
            "interval": "1h",
            "start_date": "2021-01-01",
            "end_date": "2021-01-02"
        }
        
        result = await data_fetch_handler(payload)
        
        # Должен вернуть 0 candles без ошибки
        assert result["candles_count"] == 0
        assert result["status"] == "completed"


# ==================== INTEGRATION TESTS ====================

class TestTaskHandlersIntegration:
    """Интеграционные тесты"""
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    @patch('backend.queue.task_handlers.get_engine')
    async def test_backtest_logs_info_and_success(
        self, mock_get_engine, mock_ds_class, mock_session_local,
        mock_db_session, mock_data_service, mock_engine, backtest_payload
    ):
        """Проверяем, что логи вызываются (info, success)"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service
        mock_get_engine.return_value = mock_engine
        
        with patch('backend.queue.task_handlers.logger') as mock_logger:
            await backtest_handler(backtest_payload)
            
            # Проверяем логи
            assert mock_logger.info.call_count >= 3  # Starting, claimed, loaded candles
            mock_logger.success.assert_called_once()  # Completed
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    async def test_backtest_logs_error_on_failure(
        self, mock_ds_class, mock_session_local, mock_db_session, mock_data_service
    ):
        """Проверяем логи при ошибке"""
        mock_session_local.return_value = mock_db_session
        mock_data_service.claim_backtest_to_run.side_effect = RuntimeError("DB error")
        mock_ds_class.return_value = mock_data_service
        
        payload = {"backtest_id": 111}
        
        with patch('backend.queue.task_handlers.logger') as mock_logger:
            with pytest.raises(RuntimeError):
                await backtest_handler(payload)
            
            mock_logger.error.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.queue.task_handlers.SessionLocal')
    @patch('backend.queue.task_handlers.DataService')
    async def test_optimization_logs_info(
        self, mock_ds_class, mock_session_local, 
        mock_db_session, mock_data_service
    ):
        """Проверяем логи оптимизации"""
        mock_session_local.return_value = mock_db_session
        mock_ds_class.return_value = mock_data_service
        
        # Mock the import
        import sys
        grid_module = MagicMock()
        grid_module.GridSearchOptimizer = MagicMock()
        sys.modules['backend.optimization.grid'] = grid_module
        
        payload = {
            "optimization_id": 555,
            "optimization_type": "grid",
            "strategy_config": {},
            "param_space": {},
            "symbol": "BTCUSDT",
            "interval": "1h",
            "start_date": "2021-01-01",
            "end_date": "2021-12-31",
            "metric": "sharpe_ratio"
        }
        
        try:
            with patch('backend.queue.task_handlers.logger') as mock_logger:
                await optimization_handler(payload)
                
                mock_logger.info.assert_called()
                mock_logger.success.assert_called_once()
        finally:
            if 'backend.optimization.grid' in sys.modules:
                del sys.modules['backend.optimization.grid']
