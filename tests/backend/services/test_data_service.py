"""
Tests for DataService (Repository Pattern)

Coverage target: ~16% → 70%+

Test categories:
1. Strategy CRUD operations (real DB)
2. Backtest CRUD operations (real DB)
3. Trade CRUD operations (real DB)
4. Optimization CRUD operations (real DB)
5. OptimizationResult operations (real DB)
6. MarketData operations (real DB)
7. claim_backtest_to_run logic (atomicity, staleness)
8. Context manager behavior
9. Query filtering and pagination
10. Error handling
"""

import pytest
import pandas as pd
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.services.data_service import DataService, ClaimResult
from backend.models import (
    Base,
    Backtest,
    Strategy,
    Trade,
    Optimization,
    OptimizationResult,
    MarketData,
)


# ==================== FIXTURES ====================


@pytest.fixture
def db_engine():
    """Create in-memory SQLite database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create database session for testing."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def data_service(db_session):
    """Create DataService with real test database."""
    return DataService(db=db_session)


@pytest.fixture
def sample_strategy(data_service):
    """Create sample strategy for tests."""
    return data_service.create_strategy(
        name="Test Strategy",
        description="Test description",
        strategy_type="Indicator-Based",
        config={"param1": 10},
        is_active=True,
    )


@pytest.fixture
def sample_backtest(data_service, sample_strategy):
    """Create sample backtest for tests."""
    return data_service.create_backtest(
        strategy_id=sample_strategy.id,
        symbol="BTCUSDT",
        timeframe="60",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
        initial_capital=10000.0,
        leverage=1,
        commission=0.0006,
        status="queued",
    )


@pytest.fixture
def sample_optimization(data_service, sample_strategy):
    """Create sample optimization for tests."""
    return data_service.create_optimization(
        strategy_id=sample_strategy.id,
        optimization_type="grid_search",
        symbol="BTCUSDT",
        timeframe="60",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
        param_ranges={"period": [10, 14, 20]},
        metric="sharpe_ratio",
        initial_capital=10000.0,
        total_combinations=3,
        status="pending",
    )


@pytest.fixture
def mock_db_session():
    """Create mock database session (legacy tests)."""
    session = MagicMock()
    session.query = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.close = MagicMock()
    return session



# ==================== TEST CLASSES ====================


class TestStrategyOperations:
    """Test Strategy CRUD operations with real DB."""

    def test_create_strategy_success(self, data_service):
        """Test successful strategy creation."""
        strategy = data_service.create_strategy(
            name="Bollinger Bands",
            description="Mean reversion",
            strategy_type="Indicator-Based",
            config={"period": 20},
            is_active=True,
        )

        assert strategy.id is not None
        assert strategy.name == "Bollinger Bands"
        assert strategy.strategy_type == "Indicator-Based"
        assert strategy.is_active is True

    def test_get_strategy_found(self, data_service, sample_strategy):
        """Test getting existing strategy."""
        result = data_service.get_strategy(sample_strategy.id)

        assert result is not None
        assert result.id == sample_strategy.id
        assert result.name == sample_strategy.name

    def test_get_strategy_not_found(self, data_service):
        """Test getting non-existent strategy."""
        result = data_service.get_strategy(99999)
        assert result is None

    def test_get_strategies_no_filter(self, data_service, sample_strategy):
        """Test get all strategies."""
        strategies = data_service.get_strategies()
        assert len(strategies) >= 1
        assert any(s.id == sample_strategy.id for s in strategies)

    def test_get_strategies_with_active_filter(self, data_service):
        """Test filtering by is_active."""
        data_service.create_strategy("Active1", "desc", "Indicator-Based", {}, is_active=True)
        data_service.create_strategy("Inactive1", "desc", "Pattern-Based", {}, is_active=False)

        active = data_service.get_strategies(is_active=True)
        assert all(s.is_active for s in active)

        inactive = data_service.get_strategies(is_active=False)
        assert all(not s.is_active for s in inactive)

    def test_get_strategies_with_type_filter(self, data_service):
        """Test filtering by strategy_type."""
        data_service.create_strategy("Indicator1", "desc", "Indicator-Based", {})
        data_service.create_strategy("Pattern1", "desc", "Pattern-Based", {})

        indicator_strats = data_service.get_strategies(strategy_type="Indicator-Based")
        assert all(s.strategy_type == "Indicator-Based" for s in indicator_strats)

    def test_get_strategies_pagination(self, data_service):
        """Test pagination with limit and offset."""
        for i in range(5):
            data_service.create_strategy(f"Strategy{i}", "desc", "Indicator-Based", {})

        page1 = data_service.get_strategies(limit=2, offset=0)
        assert len(page1) == 2

        page2 = data_service.get_strategies(limit=2, offset=2)
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    def test_count_strategies(self, data_service, sample_strategy):
        """Test counting strategies."""
        count = data_service.count_strategies()
        assert count >= 1

        count_active = data_service.count_strategies(is_active=True)
        assert count_active >= 1

    def test_update_strategy_success(self, data_service, sample_strategy):
        """Test updating strategy."""
        updated = data_service.update_strategy(
            sample_strategy.id,
            name="Updated Name",
            is_active=False,
        )

        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.is_active is False

    def test_update_strategy_not_found(self, data_service):
        """Test update non-existent strategy."""
        result = data_service.update_strategy(99999, name="Test")
        assert result is None

    def test_delete_strategy_success(self, data_service, sample_strategy):
        """Test deleting strategy."""
        strategy_id = sample_strategy.id
        result = data_service.delete_strategy(strategy_id)
        assert result is True

        # Verify deletion
        strategy = data_service.get_strategy(strategy_id)
        assert strategy is None

    def test_delete_strategy_not_found(self, data_service):
        """Test delete non-existent strategy."""
        result = data_service.delete_strategy(99999)
        assert result is False


class TestBacktestOperations:
    """Test Backtest CRUD operations with real DB."""

    def test_create_backtest_success(self, data_service, sample_strategy):
        """Test successful backtest creation."""
        backtest = data_service.create_backtest(
            strategy_id=sample_strategy.id,
            symbol="ETHUSDT",
            timeframe="240",
            start_date=datetime(2024, 2, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 2, 28, tzinfo=timezone.utc),
            initial_capital=5000.0,
            leverage=2,
            commission=0.0004,
            config={"stop_loss": 0.02},
            status="queued",
        )

        assert backtest.id is not None
        assert backtest.symbol == "ETHUSDT"
        assert backtest.leverage == 2
        assert backtest.status == "queued"

    def test_get_backtest_found(self, data_service, sample_backtest):
        """Test getting existing backtest."""
        result = data_service.get_backtest(sample_backtest.id)
        assert result is not None
        assert result.id == sample_backtest.id

    def test_get_backtest_not_found(self, data_service):
        """Test get non-existent backtest."""
        result = data_service.get_backtest(99999)
        assert result is None

    def test_get_backtests_no_filter(self, data_service, sample_backtest):
        """Test get all backtests."""
        backtests = data_service.get_backtests()
        assert len(backtests) >= 1
        assert any(b.id == sample_backtest.id for b in backtests)

    def test_get_backtests_with_filters(self, data_service, sample_strategy):
        """Test filtering by symbol and status."""
        data_service.create_backtest(
            sample_strategy.id, "BTCUSDT", "60",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
            10000.0, status="completed"
        )
        data_service.create_backtest(
            sample_strategy.id, "ETHUSDT", "240",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
            10000.0, status="running"
        )

        btc_backtests = data_service.get_backtests(symbol="BTCUSDT")
        assert all(b.symbol == "BTCUSDT" for b in btc_backtests)

        completed = data_service.get_backtests(status="completed")
        assert all(b.status == "completed" for b in completed)

    def test_get_backtests_ordering(self, data_service, sample_strategy):
        """Test ordering by created_at."""
        bt1 = data_service.create_backtest(
            sample_strategy.id, "BTCUSDT", "60",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc), 10000.0
        )
        bt2 = data_service.create_backtest(
            sample_strategy.id, "ETHUSDT", "60",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc), 10000.0
        )

        # Default: desc
        backtests_desc = data_service.get_backtests(order_dir="desc")
        assert backtests_desc[0].created_at >= backtests_desc[-1].created_at

        # Asc
        backtests_asc = data_service.get_backtests(order_dir="asc")
        assert backtests_asc[0].created_at <= backtests_asc[-1].created_at

    def test_count_backtests(self, data_service, sample_backtest):
        """Test counting backtests."""
        count = data_service.count_backtests()
        assert count >= 1

        count_queued = data_service.count_backtests(status="queued")
        assert count_queued >= 1

    def test_update_backtest_success(self, data_service, sample_backtest):
        """Test updating backtest."""
        updated = data_service.update_backtest(
            sample_backtest.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )

        assert updated is not None
        assert updated.status == "running"
        assert updated.started_at is not None

    def test_claim_backtest_not_found(self, data_service):
        """Test claim non-existent backtest."""
        now = datetime.now(timezone.utc)
        result = data_service.claim_backtest_to_run(99999, now)
        assert result["status"] == "not_found"
        assert result["backtest"] is None

    def test_claim_backtest_already_completed(self, data_service, sample_backtest):
        """Test claim completed backtest."""
        data_service.update_backtest(sample_backtest.id, status="completed")

        now = datetime.now(timezone.utc)
        result = data_service.claim_backtest_to_run(sample_backtest.id, now)
        assert result["status"] == "completed"
        assert result["backtest"] is not None

    def test_claim_backtest_already_running_not_stale(self, data_service, sample_backtest):
        """Test claim recently running backtest."""
        recent = datetime.now(timezone.utc) - timedelta(seconds=10)
        data_service.update_backtest(
            sample_backtest.id, status="running", started_at=recent
        )

        now = datetime.now(timezone.utc)
        result = data_service.claim_backtest_to_run(sample_backtest.id, now, stale_seconds=3600)
        assert result["status"] == "running"

    def test_claim_backtest_success_from_queued(self, data_service, sample_backtest):
        """Test successfully claim queued backtest."""
        now = datetime.now(timezone.utc)
        result = data_service.claim_backtest_to_run(sample_backtest.id, now)

        assert result["status"] == "claimed"
        assert result["backtest"] is not None
        assert result["backtest"].status == "running"
        assert result["backtest"].started_at is not None

    def test_claim_backtest_success_from_stale_running(self, data_service, sample_backtest):
        """Test claim stale running backtest."""
        stale = datetime.now(timezone.utc) - timedelta(hours=48)
        data_service.update_backtest(
            sample_backtest.id, status="running", started_at=stale
        )

        now = datetime.now(timezone.utc)
        result = data_service.claim_backtest_to_run(sample_backtest.id, now, stale_seconds=3600)
        assert result["status"] == "claimed"

    def test_update_backtest_results(self, data_service, sample_backtest):
        """Test updating backtest with results."""
        updated = data_service.update_backtest_results(
            sample_backtest.id,
            final_capital=12000.0,
            total_return=20.0,
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            win_rate=60.0,
            sharpe_ratio=1.5,
            max_drawdown=8.5,
        )

        assert updated is not None
        assert updated.final_capital == 12000.0
        assert updated.status == "completed"
        assert updated.completed_at is not None

    def test_delete_backtest_success(self, data_service, sample_backtest):
        """Test deleting backtest."""
        backtest_id = sample_backtest.id
        result = data_service.delete_backtest(backtest_id)
        assert result is True

        backtest = data_service.get_backtest(backtest_id)
        assert backtest is None





class TestTradeOperations:
    """Test Trade CRUD operations with real DB."""

    def test_create_trade_success(self, data_service, sample_backtest):
        """Test creating single trade."""
        trade = data_service.create_trade(
            backtest_id=sample_backtest.id,
            entry_time=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            exit_time=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            entry_price=50000.0,
            exit_price=51000.0,
            quantity=0.1,
            position_size=5000.0,
            side="LONG",
            pnl=100.0,
            pnl_pct=2.0,
        )

        assert trade.id is not None
        assert trade.entry_price == 50000.0
        assert trade.pnl == 100.0

    def test_create_trades_batch(self, data_service, sample_backtest):
        """Test batch trade creation."""
        trades_data = [
            {
                "backtest_id": sample_backtest.id,
                "entry_time": datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                "exit_time": datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                "entry_price": 50000.0,
                "exit_price": 51000.0,
                "quantity": 0.1,
                "side": "LONG",
                "pnl": 100.0,
            },
            {
                "backtest_id": sample_backtest.id,
                "entry_time": datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
                "exit_time": datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc),
                "entry_price": 51000.0,
                "exit_price": 50500.0,
                "quantity": 0.1,
                "side": "SHORT",
                "pnl": 50.0,
            },
        ]

        count = data_service.create_trades_batch(trades_data)
        assert count == 2

        trades = data_service.get_trades(sample_backtest.id)
        assert len(trades) == 2

    def test_get_trade(self, data_service, sample_backtest):
        """Test get trade by ID."""
        trade = data_service.create_trade(
            sample_backtest.id,
            datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            "LONG", 50000.0, 0.1, 5000.0,
        )

        retrieved = data_service.get_trade(trade.id)
        assert retrieved is not None
        assert retrieved.id == trade.id

    def test_get_trades_with_side_filter(self, data_service, sample_backtest):
        """Test filtering trades by side."""
        data_service.create_trade(
            sample_backtest.id,
            datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            "LONG", 50000.0, 0.1, 5000.0,
        )
        data_service.create_trade(
            sample_backtest.id,
            datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
            "SHORT", 51000.0, 0.1, 5100.0,
        )

        long_trades = data_service.get_trades(sample_backtest.id, side="LONG")
        assert all(t.side == "LONG" for t in long_trades)

        short_trades = data_service.get_trades(sample_backtest.id, side="SHORT")
        assert all(t.side == "SHORT" for t in short_trades)

    def test_get_trades_count(self, data_service, sample_backtest):
        """Test counting trades."""
        for i in range(3):
            data_service.create_trade(
                sample_backtest.id,
                datetime(2024, 1, 1 + i, 10, 0, tzinfo=timezone.utc),
                "LONG", 50000.0, 0.1, 5000.0,
            )

        count = data_service.get_trades_count(sample_backtest.id)
        assert count == 3

    def test_delete_trades_by_backtest(self, data_service, sample_backtest):
        """Test deleting all trades for backtest."""
        for i in range(3):
            data_service.create_trade(
                sample_backtest.id,
                datetime(2024, 1, 1 + i, 10, 0, tzinfo=timezone.utc),
                "LONG", 50000.0, 0.1, 5000.0,
            )

        deleted = data_service.delete_trades_by_backtest(sample_backtest.id)
        assert deleted == 3

        remaining = data_service.get_trades_count(sample_backtest.id)
        assert remaining == 0


class TestOptimizationOperations:
    """Test Optimization CRUD operations with real DB."""

    def test_create_optimization_success(self, data_service, sample_strategy):
        """Test optimization creation."""
        optimization = data_service.create_optimization(
            strategy_id=sample_strategy.id,
            optimization_type="bayesian",
            symbol="ETHUSDT",
            timeframe="60",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
            param_ranges={"period": [10, 30]},
            metric="total_return",
            initial_capital=20000.0,
            total_combinations=50,
        )

        assert optimization.id is not None
        assert optimization.optimization_type == "bayesian"

    def test_get_optimization(self, data_service, sample_optimization):
        """Test get optimization by ID."""
        result = data_service.get_optimization(sample_optimization.id)
        assert result is not None
        assert result.id == sample_optimization.id

    def test_get_optimizations_with_filters(self, data_service, sample_strategy):
        """Test filtering optimizations."""
        data_service.create_optimization(
            sample_strategy.id, "grid_search", "BTCUSDT", "60",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
            {}, "sharpe_ratio", 10000.0, 10, status="completed"
        )

        completed = data_service.get_optimizations(status="completed")
        assert all(o.status == "completed" for o in completed)

    def test_update_optimization(self, data_service, sample_optimization):
        """Test updating optimization."""
        updated = data_service.update_optimization(
            sample_optimization.id,
            status="completed",
        )

        assert updated is not None
        assert updated.status == "completed"


class TestOptimizationResultOperations:
    """Test OptimizationResult operations with real DB."""

    def test_create_optimization_result(self, data_service, sample_optimization):
        """Test optimization result creation."""
        result = data_service.create_optimization_result(
            optimization_id=sample_optimization.id,
            params={"period": 14},
            score=1.8,
        )

        assert result.id is not None
        assert result.metric_value == 1.8
        assert result.parameters["period"] == 14

    def test_create_optimization_results_batch(self, data_service, sample_optimization):
        """Test batch result creation."""
        results_data = [
            {
                "optimization_id": sample_optimization.id,
                "parameters": {"period": 10},
                "metric_value": 1.2,
            },
            {
                "optimization_id": sample_optimization.id,
                "parameters": {"period": 20},
                "metric_value": 1.9,
            },
        ]

        count = data_service.create_optimization_results_batch(results_data)
        assert count == 2

    def test_get_optimization_results(self, data_service, sample_optimization):
        """Test get optimization results."""
        for i in range(3):
            data_service.create_optimization_result(
                sample_optimization.id,
                params={"period": 10 + i * 5},
                score=1.0 + i * 0.5,
            )

        results = data_service.get_optimization_results(sample_optimization.id)
        assert len(results) == 3
        # Verify desc ordering by metric_value
        assert results[0].metric_value >= results[-1].metric_value

    def test_get_best_optimization_result(self, data_service, sample_optimization):
        """Test get best result."""
        data_service.create_optimization_result(
            sample_optimization.id, params={"period": 10}, score=1.2
        )
        data_service.create_optimization_result(
            sample_optimization.id, params={"period": 14}, score=2.5  # Best
        )
        data_service.create_optimization_result(
            sample_optimization.id, params={"period": 20}, score=1.8
        )

        best = data_service.get_best_optimization_result(sample_optimization.id)
        assert best is not None
        assert best.metric_value == 2.5
        assert best.parameters["period"] == 14


class TestMarketDataOperations:
    """Test MarketData CRUD operations with real DB."""

    def test_create_market_data(self, data_service):
        """Test single candle creation."""
        candle = data_service.create_market_data(
            symbol="BTCUSDT",
            timeframe="60",
            timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            open=45000.0,
            high=46000.0,
            low=44500.0,
            close=45800.0,
            volume=1234.56,
        )

        assert candle.id is not None
        assert candle.close == 45800.0

    def test_create_market_data_batch(self, data_service):
        """Test batch candle creation."""
        candles_data = [
            {
                "symbol": "BTCUSDT",
                "interval": "60",  # Model uses 'interval' not 'timeframe'
                "timestamp": datetime(2024, 1, 1, i, 0, tzinfo=timezone.utc),
                "open": 45000.0,
                "high": 46000.0,
                "low": 44500.0,
                "close": 45800.0,
                "volume": 1000.0,
            }
            for i in range(24)
        ]

        count = data_service.create_market_data_batch(candles_data)
        assert count == 24

    def test_get_market_data(self, data_service):
        """Test get market data as DataFrame."""
        for i in range(10):
            data_service.create_market_data(
                symbol="ETHUSDT",
                timeframe="60",
                timestamp=datetime(2024, 1, 1, i, 0, tzinfo=timezone.utc),
                open=3000.0,
                high=3100.0,
                low=2900.0,
                close=3050.0,
                volume=500.0,
            )

        df = data_service.get_market_data(
            symbol="ETHUSDT",
            timeframe="60",
            start_time=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 23, 59, tzinfo=timezone.utc),
        )

        assert df is not None
        assert len(df) == 10
        assert isinstance(df, pd.DataFrame)

    def test_get_market_data_empty(self, data_service):
        """Test get market data returns None when empty."""
        df = data_service.get_market_data(
            symbol="XRPUSDT",
            timeframe="60",
            start_time=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 23, 59, tzinfo=timezone.utc),
        )

        assert df is None

    def test_get_latest_candle(self, data_service):
        """Test get latest candle."""
        for i in range(5):
            data_service.create_market_data(
                symbol="BTCUSDT",
                timeframe="240",
                timestamp=datetime(2024, 1, 1 + i, 0, 0, tzinfo=timezone.utc),
                open=45000.0,
                high=46000.0,
                low=44500.0,
                close=45800.0,
                volume=1000.0,
            )

        latest = data_service.get_latest_candle("BTCUSDT", "240")
        assert latest is not None
        # SQLite doesn't preserve timezone, so compare naive datetime
        assert latest.timestamp == datetime(2024, 1, 5, 0, 0)

    def test_delete_market_data(self, data_service):
        """Test delete market data before date."""
        for i in range(10):
            data_service.create_market_data(
                symbol="BTCUSDT",
                timeframe="60",
                timestamp=datetime(2024, 1, 1 + i, 0, 0, tzinfo=timezone.utc),
                open=45000.0,
                high=46000.0,
                low=44500.0,
                close=45800.0,
                volume=1000.0,
            )

        count = data_service.delete_market_data(
            symbol="BTCUSDT",
            timeframe="60",
            before_date=datetime(2024, 1, 5, 0, 0, tzinfo=timezone.utc),
        )

        assert count == 4  # Jan 1-4


class TestContextManagerAndUtility:
    """Test context manager and utility methods."""

    @patch('backend.services.data_service.SessionLocal')
    def test_context_manager_auto_close(self, mock_session_local):
        """Test context manager closes auto-created session."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        with DataService() as service:
            assert service.db is mock_session

        mock_session.close.assert_called_once()

    def test_context_manager_no_auto_close(self, db_session):
        """Test context manager doesn't close external session."""
        with DataService(db=db_session) as service:
            assert service.db == db_session
        # External session not closed

    def test_commit(self, db_session):
        """Test manual commit."""
        ds = DataService(db=db_session)
        ds.db.commit = MagicMock()
        ds.commit()
        ds.db.commit.assert_called_once()

    def test_rollback(self, db_session):
        """Test manual rollback."""
        ds = DataService(db=db_session)
        ds.db.rollback = MagicMock()
        ds.rollback()
        ds.db.rollback.assert_called_once()

    def test_close(self, db_session):
        """Test manual close."""
        ds = DataService(db=db_session)
        ds._auto_close = True
        ds.db.close = MagicMock()
        ds.close()
        ds.db.close.assert_called_once()


class TestErrorHandling:
    """Test error handling."""

    def test_claim_backtest_db_error(self, data_service, sample_backtest):
        """Test claim_backtest handles DB errors."""
        with patch.object(data_service.db, 'commit', side_effect=Exception("DB Error")):
            now = datetime.now(timezone.utc)
            result = data_service.claim_backtest_to_run(sample_backtest.id, now)

            assert result["status"] == "error"
            assert "DB Error" in result["message"]

    def test_claim_backtest_with_for_update_fallback(self, data_service, sample_backtest):
        """Test claim_backtest falls back when with_for_update not supported."""
        with patch.object(data_service.db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.with_for_update.side_effect = Exception("Not supported")

            with patch.object(data_service, 'get_backtest', return_value=sample_backtest):
                now = datetime.now(timezone.utc)
                result = data_service.claim_backtest_to_run(sample_backtest.id, now)

                assert result["status"] == "claimed"
