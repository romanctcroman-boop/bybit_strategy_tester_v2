"""
Comprehensive tests for backtest_tasks.py

Coverage targets: 0% → 60%+

Test categories:
1. Task Registration & Discovery (verify Celery tasks registered)
2. Transform Results (frontend format conversion)
3. Backtest Execution (happy path with mocked dependencies)
4. Error Handling & Retries (DB failures, retry logic)
5. Task Chaining (bulk backtest delegation)
6. Database Transactions (atomic claims, status updates)
7. Metrics & Monitoring (Prometheus counters, histograms)
"""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from backend.tasks.backtest_tasks import (
    BacktestTask,
    _transform_results_for_frontend,
    bulk_backtest_task,
    run_backtest_task,
)


# ==================== FIXTURES ====================


@pytest.fixture
def sample_engine_results():
    """Sample BacktestEngine results for transformation testing."""
    return {
        "final_capital": 11500.0,
        "total_return": 1500.0,
        "total_trades": 10,
        "winning_trades": 6,
        "losing_trades": 4,
        "win_rate": 60.0,
        "sharpe_ratio": 1.5,
        "sortino_ratio": 2.0,
        "profit_factor": 1.8,
        "max_drawdown": -500.0,
        "metrics": {
            "net_profit": 1500.0,
            "net_profit_pct": 15.0,
            "max_drawdown_abs": -500.0,
            "max_drawdown_pct": -5.0,
            "buy_hold_return": 1000.0,
        },
        "trades": [
            {
                "entry_time": "2024-01-01T00:00:00",
                "exit_time": "2024-01-01T01:00:00",
                "side": "LONG",
                "entry_price": 50000.0,
                "exit_price": 50500.0,
                "quantity": 0.1,
                "pnl": 200.0,
                "pnl_pct": 1.0,
                "run_up": 300.0,
                "run_up_pct": 1.5,
                "drawdown": -50.0,
                "drawdown_pct": -0.25,
                "cumulative_pnl": 200.0,
                "commission": 7.5,
                "bars_held": 12,
            },
            {
                "entry_time": "2024-01-01T02:00:00",
                "exit_time": "2024-01-01T03:00:00",
                "side": "SHORT",
                "entry_price": 50500.0,
                "exit_price": 50000.0,
                "quantity": 0.1,
                "pnl": 300.0,
                "pnl_pct": 1.5,
                "run_up": 400.0,
                "run_up_pct": 2.0,
                "drawdown": -100.0,
                "drawdown_pct": -0.5,
                "cumulative_pnl": 500.0,
                "commission": 7.5,
                "bars_held": 8,
            },
            {
                "entry_time": "2024-01-01T04:00:00",
                "exit_time": "2024-01-01T05:00:00",
                "side": "LONG",
                "entry_price": 50000.0,
                "exit_price": 49500.0,
                "quantity": 0.1,
                "pnl": -100.0,
                "pnl_pct": -0.5,
                "run_up": 50.0,
                "run_up_pct": 0.25,
                "drawdown": -150.0,
                "drawdown_pct": -0.75,
                "cumulative_pnl": 400.0,
                "commission": 7.5,
                "bars_held": 6,
            },
        ],
        "equity_curve": [
            {"timestamp": "2024-01-01T00:00:00", "equity": 10000.0},
            {"timestamp": "2024-01-01T01:00:00", "equity": 10200.0},
            {"timestamp": "2024-01-01T02:00:00", "equity": 10500.0},
            {"timestamp": "2024-01-01T03:00:00", "equity": 10400.0},
        ],
    }


@pytest.fixture
def mock_celery_task():
    """Mock Celery task object for testing task methods."""
    task = MagicMock()
    task.request.retries = 0
    task.max_retries = 3
    task.retry = Mock(side_effect=Exception("Retry triggered"))
    return task


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    db = MagicMock()
    db.query = MagicMock()
    db.commit = MagicMock()
    db.close = MagicMock()
    return db


@pytest.fixture
def mock_backtest_model():
    """Mock Backtest SQLAlchemy model."""
    backtest = MagicMock()
    backtest.id = 1
    backtest.status = "pending"
    backtest.started_at = None
    backtest.completed_at = None
    backtest.error_message = None
    backtest.updated_at = datetime.now(UTC)
    return backtest


# ==================== TEST CLASSES ====================


class TestTaskRegistration:
    """Test that Celery tasks are properly registered."""

    def test_run_backtest_task_registered(self):
        """Verify run_backtest_task is registered with correct name."""
        assert hasattr(run_backtest_task, "name")
        assert run_backtest_task.name == "backend.tasks.backtest_tasks.run_backtest"

    def test_bulk_backtest_task_registered(self):
        """Verify bulk_backtest_task is registered."""
        assert hasattr(bulk_backtest_task, "name")
        assert bulk_backtest_task.name == "backend.tasks.backtest_tasks.bulk_backtest"

    def test_run_backtest_task_has_retry_config(self):
        """Verify run_backtest_task has retry configuration."""
        assert hasattr(run_backtest_task, "max_retries")
        assert run_backtest_task.max_retries == 3
        assert hasattr(run_backtest_task, "default_retry_delay")
        assert run_backtest_task.default_retry_delay == 60


class TestTransformResultsForFrontend:
    """Test the _transform_results_for_frontend function."""

    def test_transform_empty_results(self):
        """Test transformation with no trades."""
        engine_results = {
            "final_capital": 10000.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "metrics": {},
            "trades": [],
            "equity_curve": [],
        }

        result = _transform_results_for_frontend(engine_results, 10000.0)

        assert result["overview"]["total_trades"] == 0
        assert result["overview"]["net_pnl"] == 0.0
        assert result["by_side"]["all"]["total_trades"] == 0
        assert result["by_side"]["all"]["wins"] == 0
        assert result["by_side"]["long"]["total_trades"] == 0
        assert result["by_side"]["short"]["total_trades"] == 0
        assert len(result["equity"]) == 0

    def test_transform_with_trades(self, sample_engine_results):
        """Test transformation with sample trades."""
        result = _transform_results_for_frontend(sample_engine_results, 10000.0)

        # Verify overview
        assert result["overview"]["net_pnl"] == 1500.0
        assert result["overview"]["net_pct"] == 15.0
        assert result["overview"]["total_trades"] == 10
        assert result["overview"]["wins"] == 6
        assert result["overview"]["losses"] == 4

        # Verify by_side stats
        assert result["by_side"]["all"]["total_trades"] == 3
        assert result["by_side"]["all"]["wins"] == 2
        assert result["by_side"]["all"]["losses"] == 1
        assert result["by_side"]["long"]["total_trades"] == 2
        assert result["by_side"]["short"]["total_trades"] == 1

    def test_transform_calculates_profit_factor(self, sample_engine_results):
        """Test profit factor calculation."""
        result = _transform_results_for_frontend(sample_engine_results, 10000.0)

        all_stats = result["by_side"]["all"]
        assert all_stats["profit_factor"] > 0
        # (200 + 300) / 100 = 5.0
        assert all_stats["profit_factor"] == pytest.approx(5.0, rel=0.01)

    def test_transform_calculates_win_rate(self, sample_engine_results):
        """Test win rate calculation."""
        result = _transform_results_for_frontend(sample_engine_results, 10000.0)

        all_stats = result["by_side"]["all"]
        # 2 wins out of 3 trades = 66.67%
        assert all_stats["win_rate"] == pytest.approx(66.67, rel=0.01)

    def test_transform_equity_curve(self, sample_engine_results):
        """Test equity curve transformation."""
        result = _transform_results_for_frontend(sample_engine_results, 10000.0)

        equity = result["equity"]
        assert len(equity) == 4
        assert equity[0]["time"] == "2024-01-01T00:00:00"
        assert equity[0]["equity"] == 10000.0
        assert equity[-1]["equity"] == 10400.0

    def test_transform_pnl_bars(self, sample_engine_results):
        """Test PnL bars transformation."""
        result = _transform_results_for_frontend(sample_engine_results, 10000.0)

        pnl_bars = result["pnl_bars"]
        assert len(pnl_bars) == 4
        assert pnl_bars[0]["pnl"] == 0.0  # 10000 - 10000
        assert pnl_bars[1]["pnl"] == 200.0  # 10200 - 10000
        assert pnl_bars[-1]["pnl"] == 400.0  # 10400 - 10000

    def test_transform_dynamics(self, sample_engine_results):
        """Test dynamics calculations."""
        result = _transform_results_for_frontend(sample_engine_results, 10000.0)

        dynamics = result["dynamics"]["all"]
        assert dynamics["net_abs"] == pytest.approx(400.0, rel=0.01)  # 200 + 300 - 100
        assert dynamics["gross_profit_abs"] == 500.0  # 200 + 300
        assert dynamics["gross_loss_abs"] == 100.0  # abs(-100)
        assert dynamics["fees_abs"] == pytest.approx(22.5, rel=0.01)  # 7.5 * 3

    def test_transform_risk_metrics(self, sample_engine_results):
        """Test risk metrics extraction."""
        result = _transform_results_for_frontend(sample_engine_results, 10000.0)

        risk = result["risk"]
        assert risk["sharpe"] == 1.5
        assert risk["sortino"] == 2.0
        assert risk["profit_factor"] == 1.8


class TestBacktestTaskExecution:
    """Test backtest task execution with mocked dependencies."""

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    @patch("backend.tasks.backtest_tasks.get_engine")
    def test_run_backtest_happy_path(
        self, mock_get_engine, mock_session_local, mock_backtest_model, sample_engine_results
    ):
        """Test successful backtest execution."""
        # Mock database
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # Mock DataService
        mock_ds = MagicMock()
        mock_ds.get_backtest.return_value = mock_backtest_model
        mock_ds.get_market_data.return_value = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="1h"),
                "close": [50000] * 100,
            }
        )

        # Mock BacktestEngine
        mock_engine = MagicMock()
        mock_engine.run.return_value = sample_engine_results
        mock_get_engine.return_value = mock_engine

        with patch("backend.tasks.backtest_tasks.DataService", return_value=mock_ds):
            # Execute task
            result = run_backtest_task(
                backtest_id=1,
                strategy_config={"type": "ema_crossover", "fast": 10, "slow": 30},
                symbol="BTCUSDT",
                interval="1h",
                start_date="2024-01-01",
                end_date="2024-01-31",
                initial_capital=10000.0,
            )

        # Verify result
        assert result["backtest_id"] == 1
        assert result["status"] == "completed"
        assert "results" in result

        # Verify DataService calls
        mock_ds.get_backtest.assert_called_once_with(1)
        mock_ds.get_market_data.assert_called_once()
        mock_ds.update_backtest_results.assert_called_once()

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    def test_run_backtest_not_found(self, mock_session_local):
        """Test backtest not found error."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_ds = MagicMock()
        mock_ds.get_backtest.return_value = None

        with patch("backend.tasks.backtest_tasks.DataService", return_value=mock_ds):
            with pytest.raises(ValueError, match="Backtest 999 not found"):
                run_backtest_task(
                    backtest_id=999,
                    strategy_config={},
                    symbol="BTCUSDT",
                    interval="1h",
                    start_date="2024-01-01",
                    end_date="2024-01-31",
                )

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    def test_run_backtest_already_completed(self, mock_session_local, mock_backtest_model):
        """Test skipping already completed backtest."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # Mark backtest as completed
        mock_backtest_model.status = "completed"

        mock_ds = MagicMock()
        mock_ds.get_backtest.return_value = mock_backtest_model

        with patch("backend.tasks.backtest_tasks.DataService", return_value=mock_ds):
            result = run_backtest_task(
                backtest_id=1,
                strategy_config={},
                symbol="BTCUSDT",
                interval="1h",
                start_date="2024-01-01",
                end_date="2024-01-31",
            )

        assert result["status"] == "completed"
        # Should not call update_backtest_results since already completed
        mock_ds.update_backtest_results.assert_not_called()

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    def test_run_backtest_no_market_data(self, mock_session_local, mock_backtest_model):
        """Test error when no market data available."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_ds = MagicMock()
        mock_ds.get_backtest.return_value = mock_backtest_model
        mock_ds.get_market_data.return_value = None  # No data

        with patch("backend.tasks.backtest_tasks.DataService", return_value=mock_ds):
            with pytest.raises(ValueError, match="No data available"):
                run_backtest_task(
                    backtest_id=1,
                    strategy_config={},
                    symbol="INVALIDPAIR",
                    interval="1h",
                    start_date="2024-01-01",
                    end_date="2024-01-31",
                )

        # Verify error was saved to database
        mock_ds.update_backtest.assert_called()
        call_args = mock_ds.update_backtest.call_args
        assert call_args[0][0] == 1  # backtest_id
        assert call_args[1]["status"] == "failed"


class TestErrorHandlingAndRetries:
    """Test error handling, DB rollback, and Celery retries."""

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    def test_backtest_task_on_failure_callback(self, mock_session_local, mock_backtest_model):
        """Test BacktestTask.on_failure updates DB status."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # Setup query chain
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_backtest_model
        mock_db.query.return_value = mock_query

        # Create task instance
        task = BacktestTask()

        # Simulate failure
        exc = Exception("Simulated failure")
        task.on_failure(
            exc=exc,
            task_id="test-task-id",
            args=[],
            kwargs={"backtest_id": 1},
            einfo=None,
        )

        # Verify backtest status updated
        assert mock_backtest_model.status == "failed"
        assert mock_backtest_model.error_message == "Simulated failure"
        mock_db.commit.assert_called_once()

    def test_backtest_task_on_success_callback(self):
        """Test BacktestTask.on_success logs completion."""
        task = BacktestTask()

        # Should not raise any errors
        task.on_success(
            retval={"status": "completed"},
            task_id="test-task-id",
            args=[],
            kwargs={"backtest_id": 1},
        )

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    def test_run_backtest_updates_status_on_error(
        self, mock_session_local, mock_backtest_model
    ):
        """Test backtest status updated to 'failed' on exception."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_ds = MagicMock()
        mock_ds.get_backtest.return_value = mock_backtest_model
        mock_ds.get_market_data.side_effect = Exception("Simulated failure")

        with patch("backend.tasks.backtest_tasks.DataService", return_value=mock_ds):
            with pytest.raises(Exception):
                run_backtest_task(
                    backtest_id=1,
                    strategy_config={},
                    symbol="BTCUSDT",
                    interval="1h",
                    start_date="2024-01-01",
                    end_date="2024-01-31",
                )

        # Verify status updated to failed
        mock_ds.update_backtest.assert_called()
        call_args = mock_ds.update_backtest.call_args
        assert call_args[1]["status"] == "failed"
        assert "Simulated failure" in call_args[1]["error_message"]


class TestTaskChaining:
    """Test bulk backtest and task chaining."""

    @patch("celery.group")
    def test_bulk_backtest_creates_group(self, mock_group):
        """Test bulk_backtest_task creates Celery group."""
        configs = [
            {
                "backtest_id": 1,
                "strategy_config": {},
                "symbol": "BTCUSDT",
                "interval": "1h",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
            {
                "backtest_id": 2,
                "strategy_config": {},
                "symbol": "ETHUSDT",
                "interval": "1h",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
        ]

        mock_result = MagicMock()
        mock_result.id = "group-task-id"
        mock_group.return_value.apply_async.return_value = mock_result

        result = bulk_backtest_task(configs)

        assert result["total_backtests"] == 2
        assert result["status"] == "pending"
        assert result["task_id"] == "group-task-id"
        mock_group.assert_called_once()


class TestDatabaseTransactions:
    """Test database transaction handling and atomic operations."""

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    def test_atomic_claim_backtest(self, mock_session_local, mock_backtest_model):
        """Test atomic claim_backtest_to_run flow."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_ds = MagicMock()
        mock_ds.get_backtest.return_value = mock_backtest_model
        # Simulate atomic claim success
        mock_ds.claim_backtest_to_run.return_value = {"status": "claimed"}
        mock_ds.get_market_data.return_value = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=10, freq="1h"),
                "close": [50000] * 10,
            }
        )

        with patch("backend.tasks.backtest_tasks.DataService", return_value=mock_ds):
            with patch("backend.tasks.backtest_tasks.get_engine") as mock_engine:
                mock_engine.return_value.run.return_value = {
                    "final_capital": 10000,
                    "total_trades": 0,
                    "metrics": {},
                    "trades": [],
                    "equity_curve": [],
                }

                run_backtest_task(
                    backtest_id=1,
                    strategy_config={},
                    symbol="BTCUSDT",
                    interval="1h",
                    start_date="2024-01-01",
                    end_date="2024-01-02",
                )

        # Verify atomic claim was attempted
        mock_ds.claim_backtest_to_run.assert_called_once()

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    def test_claim_backtest_already_running(self, mock_session_local, mock_backtest_model):
        """Test skipping when claim returns 'running' status."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_ds = MagicMock()
        mock_ds.get_backtest.return_value = mock_backtest_model
        # Simulate claim returns "running" (another worker claimed it)
        mock_ds.claim_backtest_to_run.return_value = {"status": "running"}

        with patch("backend.tasks.backtest_tasks.DataService", return_value=mock_ds):
            result = run_backtest_task(
                backtest_id=1,
                strategy_config={},
                symbol="BTCUSDT",
                interval="1h",
                start_date="2024-01-01",
                end_date="2024-01-02",
            )

        assert result["status"] == "running"
        # Should not proceed to get_market_data
        mock_ds.get_market_data.assert_not_called()


class TestMetricsAndMonitoring:
    """Test Prometheus metrics integration."""

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    @patch("backend.tasks.backtest_tasks.get_engine")
    @patch("backend.tasks.backtest_tasks.BACKTEST_STARTED")
    @patch("backend.tasks.backtest_tasks.BACKTEST_COMPLETED")
    @patch("backend.tasks.backtest_tasks.BACKTEST_DURATION")
    def test_metrics_incremented_on_success(
        self,
        mock_duration,
        mock_completed,
        mock_started,
        mock_get_engine,
        mock_session_local,
        mock_backtest_model,
        sample_engine_results,
    ):
        """Test Prometheus metrics are incremented on successful backtest."""
        if mock_started is None or mock_completed is None:
            pytest.skip("Prometheus metrics not available")

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_ds = MagicMock()
        mock_ds.get_backtest.return_value = mock_backtest_model
        mock_ds.get_market_data.return_value = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=10, freq="1h"),
                "close": [50000] * 10,
            }
        )

        mock_engine = MagicMock()
        mock_engine.run.return_value = sample_engine_results
        mock_get_engine.return_value = mock_engine

        with patch("backend.tasks.backtest_tasks.DataService", return_value=mock_ds):
            run_backtest_task(
                backtest_id=1,
                strategy_config={},
                symbol="BTCUSDT",
                interval="1h",
                start_date="2024-01-01",
                end_date="2024-01-02",
            )

        # Verify metrics called
        mock_started.inc.assert_called_once()
        mock_completed.inc.assert_called_once()
        mock_duration.observe.assert_called_once()

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    @patch("backend.tasks.backtest_tasks.BACKTEST_FAILED")
    def test_metrics_incremented_on_failure(
        self, mock_failed, mock_session_local, mock_backtest_model
    ):
        """Test Prometheus FAILED counter incremented on error."""
        if mock_failed is None:
            pytest.skip("Prometheus metrics not available")

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_ds = MagicMock()
        mock_ds.get_backtest.return_value = mock_backtest_model
        mock_ds.get_market_data.side_effect = Exception("Simulated error")

        with patch("backend.tasks.backtest_tasks.DataService", return_value=mock_ds):
            with pytest.raises(Exception):
                run_backtest_task(
                    backtest_id=1,
                    strategy_config={},
                    symbol="BTCUSDT",
                    interval="1h",
                    start_date="2024-01-01",
                    end_date="2024-01-02",
                )

        # Verify failed counter incremented
        mock_failed.inc.assert_called()


# ==================== INTEGRATION TESTS ====================


class TestBacktestTasksIntegration:
    """Integration tests combining multiple components."""

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    @patch("backend.tasks.backtest_tasks.get_engine")
    def test_full_workflow_with_trades_saved(
        self, mock_get_engine, mock_session_local, mock_backtest_model, sample_engine_results
    ):
        """Test complete workflow: backtest execution + trades saved to DB."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_ds = MagicMock()
        mock_ds.get_backtest.return_value = mock_backtest_model
        mock_ds.get_market_data.return_value = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=10, freq="1h"),
                "close": [50000] * 10,
            }
        )

        mock_engine = MagicMock()
        mock_engine.run.return_value = sample_engine_results
        mock_get_engine.return_value = mock_engine

        with patch("backend.tasks.backtest_tasks.DataService", return_value=mock_ds):
            result = run_backtest_task(
                backtest_id=1,
                strategy_config={"type": "ema_crossover"},
                symbol="BTCUSDT",
                interval="1h",
                start_date="2024-01-01",
                end_date="2024-01-02",
            )

        # Verify trades saved
        mock_ds.create_trades_batch.assert_called_once()
        trades_data = mock_ds.create_trades_batch.call_args[0][0]
        assert len(trades_data) == 3  # sample_engine_results has 3 trades
        assert trades_data[0]["backtest_id"] == 1
        assert trades_data[0]["pnl"] == 200.0

    @patch("backend.tasks.backtest_tasks.SessionLocal")
    @patch("backend.tasks.backtest_tasks.get_engine")
    def test_leverage_and_commission_passed_to_engine(
        self, mock_get_engine, mock_session_local, mock_backtest_model, sample_engine_results
    ):
        """Test that leverage and commission parameters are passed to engine."""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_ds = MagicMock()
        mock_ds.get_backtest.return_value = mock_backtest_model
        mock_ds.get_market_data.return_value = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=10, freq="1h"),
                "close": [50000] * 10,
            }
        )

        mock_engine = MagicMock()
        mock_engine.run.return_value = sample_engine_results
        mock_get_engine.return_value = mock_engine

        with patch("backend.tasks.backtest_tasks.DataService", return_value=mock_ds):
            run_backtest_task(
                backtest_id=1,
                strategy_config={"type": "ema_crossover", "leverage": 5, "order_size_usd": 1000},
                symbol="BTCUSDT",
                interval="1h",
                start_date="2024-01-01",
                end_date="2024-01-02",
                initial_capital=10000.0,
            )

        # Verify get_engine called with correct parameters
        mock_get_engine.assert_called_once()
        call_kwargs = mock_get_engine.call_args[1]
        assert call_kwargs["leverage"] == 5
        assert call_kwargs["order_size_usd"] == 1000
        assert call_kwargs["commission"] == 0.00075  # Bybit 0.075%
        assert call_kwargs["slippage_pct"] == 0.05
