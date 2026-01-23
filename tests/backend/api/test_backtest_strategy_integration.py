"""
Integration tests for Backtest + Strategy integration.

Tests the endpoints that connect saved strategies with the backtest engine.
"""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.database.models import (
    Backtest,
    BacktestStatus,
    Strategy,
    StrategyStatus,
    StrategyType,
)

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override get_db dependency for testing"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def test_app():
    """Create a test FastAPI app with both strategies and backtests routers"""
    from backend.api.routers.backtests import router as backtests_router
    from backend.api.routers.strategies import router as strategies_router

    app = FastAPI()
    app.include_router(strategies_router, prefix="/api/v1/strategies")
    app.include_router(backtests_router, prefix="/api/v1/backtests")
    app.dependency_overrides[get_db] = override_get_db

    yield app


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def clean_db():
    """Ensure clean database state for each test"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_app, clean_db):
    """Create test client"""
    with TestClient(test_app) as c:
        yield c


@pytest.fixture
def sample_strategy(db_session):
    """Create a sample strategy in database"""
    strategy = Strategy(
        name="Test SMA Strategy",
        description="SMA crossover for testing",
        strategy_type=StrategyType.SMA_CROSSOVER,
        status=StrategyStatus.ACTIVE,
        parameters={"fast_period": 10, "slow_period": 30},
        symbol="BTCUSDT",
        timeframe="1h",
        initial_capital=10000.0,
        stop_loss_pct=2.0,
        take_profit_pct=5.0,
    )
    db_session.add(strategy)
    db_session.commit()
    db_session.refresh(strategy)
    return strategy


class TestStrategyBacktestRelationship:
    """Test Strategy-Backtest database relationships"""

    def test_create_backtest_for_strategy(self, db_session):
        """Test creating a backtest linked to a strategy"""
        # Create strategy
        strategy = Strategy(
            name="Parent Strategy",
            strategy_type=StrategyType.RSI,
            parameters={"period": 14, "overbought": 70, "oversold": 30},
        )
        db_session.add(strategy)
        db_session.commit()

        # Create linked backtest
        backtest = Backtest(
            strategy_id=strategy.id,
            strategy_type="rsi",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=10000.0,
            parameters=strategy.parameters,
            status=BacktestStatus.COMPLETED,
            total_return=15.5,
            sharpe_ratio=1.2,
            win_rate=0.55,
            total_trades=50,
        )
        db_session.add(backtest)
        db_session.commit()

        # Verify relationship
        db_session.refresh(strategy)
        assert backtest.strategy == strategy
        assert backtest.strategy_id == strategy.id

    def test_multiple_backtests_per_strategy(self, db_session):
        """Test that a strategy can have multiple backtests"""
        strategy = Strategy(
            name="Multi-backtest Strategy",
            strategy_type=StrategyType.MACD,
            parameters={},
        )
        db_session.add(strategy)
        db_session.commit()

        # Create multiple backtests
        for i in range(5):
            backtest = Backtest(
                strategy_id=strategy.id,
                strategy_type="macd",
                symbol="BTCUSDT",
                timeframe="1h",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 6, 1),
                initial_capital=10000.0,
                parameters={},
                total_return=10.0 + i,
            )
            db_session.add(backtest)
        db_session.commit()

        # Query backtests for strategy
        backtests = (
            db_session.query(Backtest).filter(Backtest.strategy_id == strategy.id).all()
        )
        assert len(backtests) == 5

    def test_backtest_without_strategy(self, db_session):
        """Test creating backtest without linked strategy (ad-hoc backtest)"""
        backtest = Backtest(
            strategy_type="sma_crossover",
            symbol="ETHUSDT",
            timeframe="4h",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            initial_capital=5000.0,
            parameters={"fast_period": 5, "slow_period": 20},
        )
        db_session.add(backtest)
        db_session.commit()

        assert backtest.id is not None
        assert backtest.strategy_id is None
        assert backtest.strategy is None


class TestListBacktestsForStrategy:
    """Tests for GET /backtests/by-strategy/{strategy_id}"""

    def test_list_empty(self, client, db_session):
        """Test listing backtests when none exist for strategy"""
        # Create strategy
        strategy = Strategy(
            name="Empty Backtest Strategy",
            strategy_type=StrategyType.RSI,
            parameters={},
        )
        db_session.add(strategy)
        db_session.commit()

        response = client.get(f"/api/v1/backtests/by-strategy/{strategy.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["strategy_id"] == strategy.id
        assert data["strategy_name"] == "Empty Backtest Strategy"

    def test_list_with_backtests(self, client, db_session):
        """Test listing backtests for a strategy that has some"""
        # Create strategy
        strategy = Strategy(
            name="Active Strategy",
            strategy_type=StrategyType.MACD,
            parameters={"fast": 12, "slow": 26, "signal": 9},
        )
        db_session.add(strategy)
        db_session.commit()

        # Create backtests
        for i in range(3):
            backtest = Backtest(
                strategy_id=strategy.id,
                strategy_type="macd",
                symbol="BTCUSDT",
                timeframe="1h",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 6, 1),
                initial_capital=10000.0,
                parameters=strategy.parameters,
                status=BacktestStatus.COMPLETED,
                total_return=10.0 + i * 5,
            )
            db_session.add(backtest)
        db_session.commit()

        response = client.get(f"/api/v1/backtests/by-strategy/{strategy.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_strategy_not_found(self, client):
        """Test listing backtests for non-existent strategy"""
        response = client.get("/api/v1/backtests/by-strategy/non-existent-id")
        assert response.status_code == 404

    def test_list_pagination(self, client, db_session):
        """Test pagination for strategy backtests"""
        # Create strategy
        strategy = Strategy(
            name="Paginated Strategy",
            strategy_type=StrategyType.SMA_CROSSOVER,
            parameters={},
        )
        db_session.add(strategy)
        db_session.commit()

        # Create 10 backtests
        for i in range(10):
            backtest = Backtest(
                strategy_id=strategy.id,
                strategy_type="sma_crossover",
                symbol="BTCUSDT",
                timeframe="1h",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 6, 1),
                initial_capital=10000.0,
                parameters={},
            )
            db_session.add(backtest)
        db_session.commit()

        # Test first page
        response = client.get(
            f"/api/v1/backtests/by-strategy/{strategy.id}?page=1&limit=3"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10
        assert len(data["items"]) == 3
        assert data["page"] == 1


class TestStrategyMetricsUpdate:
    """Tests for strategy metrics updates after backtest"""

    def test_update_strategy_metrics_after_backtest(self, db_session):
        """Test that strategy metrics are updated after a backtest completes"""
        # Create strategy
        strategy = Strategy(
            name="Metrics Test Strategy",
            strategy_type=StrategyType.RSI,
            parameters={"period": 14},
        )
        db_session.add(strategy)
        db_session.commit()

        assert strategy.total_return is None
        assert strategy.sharpe_ratio is None
        # backtest_count defaults to 0
        assert strategy.backtest_count == 0

        # Simulate backtest completion and metrics update
        strategy.total_return = 25.5
        strategy.sharpe_ratio = 1.8
        strategy.win_rate = 0.65
        strategy.total_trades = 100
        strategy.backtest_count = 1
        strategy.last_backtest_at = datetime.now(timezone.utc)
        db_session.commit()

        db_session.refresh(strategy)
        assert strategy.total_return == 25.5
        assert strategy.sharpe_ratio == 1.8
        assert strategy.backtest_count == 1
        assert strategy.last_backtest_at is not None

    def test_increment_backtest_count(self, db_session):
        """Test backtest count increments correctly"""
        strategy = Strategy(
            name="Count Test",
            strategy_type=StrategyType.BOLLINGER_BANDS,
            parameters={},
            backtest_count=5,
        )
        db_session.add(strategy)
        db_session.commit()

        # Simulate adding backtests
        for _ in range(3):
            strategy.backtest_count = (strategy.backtest_count or 0) + 1
        db_session.commit()

        db_session.refresh(strategy)
        assert strategy.backtest_count == 8


class TestBacktestModels:
    """Additional tests for Backtest model"""

    def test_backtest_status_enum(self, db_session):
        """Test all backtest status values"""
        for status in BacktestStatus:
            backtest = Backtest(
                strategy_type="rsi",
                symbol="BTCUSDT",
                timeframe="1h",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 3, 1),
                initial_capital=10000.0,
                parameters={},
                status=status,
            )
            db_session.add(backtest)
        db_session.commit()

        all_statuses = db_session.query(Backtest).all()
        assert len(all_statuses) == len(BacktestStatus)

    def test_backtest_metrics_fields(self, db_session):
        """Test all performance metrics fields"""
        backtest = Backtest(
            strategy_type="macd",
            symbol="BTCUSDT",
            timeframe="1d",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 1),
            initial_capital=50000.0,
            parameters={},
            status=BacktestStatus.COMPLETED,
            # All metrics
            total_return=45.5,
            annual_return=52.3,
            sharpe_ratio=2.1,
            sortino_ratio=2.8,
            calmar_ratio=1.9,
            max_drawdown=-18.5,
            win_rate=0.62,
            profit_factor=1.85,
            total_trades=200,
            winning_trades=124,
            losing_trades=76,
            avg_trade_pnl=50.5,
            best_trade=1500.0,
            worst_trade=-800.0,
            final_capital=72750.0,
        )
        db_session.add(backtest)
        db_session.commit()

        db_session.refresh(backtest)
        assert backtest.total_return == 45.5
        assert backtest.sharpe_ratio == 2.1
        assert backtest.win_rate == 0.62
        assert backtest.final_capital == 72750.0
        assert backtest.winning_trades == 124
