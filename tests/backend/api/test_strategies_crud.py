"""
Tests for Strategies CRUD API
Unit tests that test models/schemas directly and API tests via a test-only FastAPI app
to avoid MCP lifespan issues.
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
    """Create a test FastAPI app with only the strategies router (no MCP)"""
    from backend.api.routers.strategies import router as strategies_router

    app = FastAPI()
    app.include_router(strategies_router, prefix="/api/v1/strategies")
    app.dependency_overrides[get_db] = override_get_db

    # Create tables once for module
    Base.metadata.create_all(bind=engine)

    yield app

    # Cleanup
    Base.metadata.drop_all(bind=engine)


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
def sample_strategy_data():
    """Sample strategy data for testing"""
    return {
        "name": "Test SMA Strategy",
        "description": "A test SMA crossover strategy",
        "strategy_type": "sma_crossover",
        "parameters": {"fast_period": 10, "slow_period": 30},
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "initial_capital": 10000.0,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 5.0,
    }


# ============================================================================
# UNIT TESTS FOR MODELS (no HTTP calls)
# ============================================================================


class TestStrategyModel:
    """Unit tests for Strategy SQLAlchemy model"""

    def test_create_strategy(self, db_session):
        """Test creating a basic strategy"""
        strategy = Strategy(
            name="Test Strategy",
            strategy_type=StrategyType.SMA_CROSSOVER,
            status=StrategyStatus.DRAFT,
            parameters={"fast_period": 10, "slow_period": 30},
        )
        db_session.add(strategy)
        db_session.commit()

        assert strategy.id is not None
        assert strategy.name == "Test Strategy"
        assert strategy.strategy_type == StrategyType.SMA_CROSSOVER
        assert strategy.status == StrategyStatus.DRAFT
        assert strategy.parameters == {"fast_period": 10, "slow_period": 30}

    def test_strategy_with_all_fields(self, db_session):
        """Test creating strategy with all fields"""
        strategy = Strategy(
            name="Full Strategy",
            description="A complete test strategy",
            strategy_type=StrategyType.RSI,
            status=StrategyStatus.ACTIVE,
            parameters={"period": 14, "overbought": 70, "oversold": 30},
            symbol="BTCUSDT",
            timeframe="1h",
            initial_capital=50000.0,
            position_size=2.0,
            stop_loss_pct=2.5,
            take_profit_pct=5.0,
            max_drawdown_pct=20.0,
            tags=["test", "rsi", "bitcoin"],
        )
        db_session.add(strategy)
        db_session.commit()

        assert strategy.symbol == "BTCUSDT"
        assert strategy.timeframe == "1h"
        assert strategy.initial_capital == 50000.0
        assert strategy.stop_loss_pct == 2.5
        assert strategy.tags == ["test", "rsi", "bitcoin"]

    def test_to_dict(self, db_session):
        """Test Strategy.to_dict() method"""
        strategy = Strategy(
            name="Dict Test Strategy",
            strategy_type=StrategyType.RSI,
            status=StrategyStatus.ACTIVE,
            parameters={"period": 14},
        )
        db_session.add(strategy)
        db_session.commit()

        result = strategy.to_dict()
        assert result["name"] == "Dict Test Strategy"
        assert result["strategy_type"] == "rsi"
        assert result["status"] == "active"
        assert result["parameters"] == {"period": 14}
        assert "id" in result
        assert "created_at" in result

    def test_get_default_parameters(self):
        """Test default parameters for each strategy type"""
        sma_defaults = Strategy.get_default_parameters(StrategyType.SMA_CROSSOVER)
        assert "fast_period" in sma_defaults
        assert "slow_period" in sma_defaults
        assert sma_defaults["fast_period"] == 10
        assert sma_defaults["slow_period"] == 30

        rsi_defaults = Strategy.get_default_parameters(StrategyType.RSI)
        assert "period" in rsi_defaults
        assert "overbought" in rsi_defaults
        assert "oversold" in rsi_defaults
        assert rsi_defaults["period"] == 14

        macd_defaults = Strategy.get_default_parameters(StrategyType.MACD)
        assert "fast_period" in macd_defaults
        assert "slow_period" in macd_defaults
        assert "signal_period" in macd_defaults

        bb_defaults = Strategy.get_default_parameters(StrategyType.BOLLINGER_BANDS)
        assert "period" in bb_defaults
        assert "std_dev" in bb_defaults

    def test_strategy_status_transitions(self, db_session):
        """Test strategy status changes"""
        strategy = Strategy(
            name="Status Test",
            strategy_type=StrategyType.MACD,
            status=StrategyStatus.DRAFT,
            parameters={},
        )
        db_session.add(strategy)
        db_session.commit()

        assert strategy.status == StrategyStatus.DRAFT

        # Activate
        strategy.status = StrategyStatus.ACTIVE
        db_session.commit()
        assert strategy.status == StrategyStatus.ACTIVE

        # Pause
        strategy.status = StrategyStatus.PAUSED
        db_session.commit()
        assert strategy.status == StrategyStatus.PAUSED

        # Archive
        strategy.status = StrategyStatus.ARCHIVED
        db_session.commit()
        assert strategy.status == StrategyStatus.ARCHIVED

    def test_soft_delete(self, db_session):
        """Test soft delete functionality"""
        strategy = Strategy(
            name="Delete Test",
            strategy_type=StrategyType.SMA_CROSSOVER,
            parameters={},
        )
        db_session.add(strategy)
        db_session.commit()

        assert strategy.is_deleted is False
        assert strategy.deleted_at is None

        # Soft delete
        strategy.is_deleted = True
        strategy.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        assert strategy.is_deleted is True
        assert strategy.deleted_at is not None

    def test_version_increment(self, db_session):
        """Test version tracking"""
        strategy = Strategy(
            name="Version Test",
            strategy_type=StrategyType.RSI,
            parameters={},
        )
        db_session.add(strategy)
        db_session.commit()

        assert strategy.version == 1

        strategy.version += 1
        strategy.name = "Updated Name"
        db_session.commit()

        assert strategy.version == 2

    def test_query_by_type(self, db_session):
        """Test querying strategies by type"""
        # Create multiple strategies
        for i, stype in enumerate(
            [StrategyType.SMA_CROSSOVER, StrategyType.RSI, StrategyType.RSI]
        ):
            strategy = Strategy(
                name=f"Strategy {i}",
                strategy_type=stype,
                parameters={},
            )
            db_session.add(strategy)
        db_session.commit()

        # Query by type
        rsi_strategies = (
            db_session.query(Strategy)
            .filter(Strategy.strategy_type == StrategyType.RSI)
            .all()
        )
        assert len(rsi_strategies) == 2

        sma_strategies = (
            db_session.query(Strategy)
            .filter(Strategy.strategy_type == StrategyType.SMA_CROSSOVER)
            .all()
        )
        assert len(sma_strategies) == 1

    def test_query_active_strategies(self, db_session):
        """Test querying only non-deleted active strategies"""
        # Create strategies with different statuses
        strategies_data = [
            ("Active 1", StrategyStatus.ACTIVE, False),
            ("Active 2", StrategyStatus.ACTIVE, False),
            ("Draft", StrategyStatus.DRAFT, False),
            ("Deleted", StrategyStatus.ACTIVE, True),
        ]

        for name, status, deleted in strategies_data:
            strategy = Strategy(
                name=name,
                strategy_type=StrategyType.SMA_CROSSOVER,
                status=status,
                parameters={},
                is_deleted=deleted,
            )
            db_session.add(strategy)
        db_session.commit()

        # Query active non-deleted
        active = (
            db_session.query(Strategy)
            .filter(
                Strategy.status == StrategyStatus.ACTIVE,
                Strategy.is_deleted == False,  # noqa: E712
            )
            .all()
        )
        assert len(active) == 2

    def test_performance_metrics(self, db_session):
        """Test updating performance metrics"""
        strategy = Strategy(
            name="Performance Test",
            strategy_type=StrategyType.MACD,
            parameters={},
        )
        db_session.add(strategy)
        db_session.commit()

        # Update metrics after backtest
        strategy.total_return = 25.5
        strategy.sharpe_ratio = 1.8
        strategy.win_rate = 0.65
        strategy.total_trades = 150
        strategy.backtest_count = 5
        strategy.last_backtest_at = datetime.now(timezone.utc)
        db_session.commit()

        # Verify
        db_session.refresh(strategy)
        assert strategy.total_return == 25.5
        assert strategy.sharpe_ratio == 1.8
        assert strategy.win_rate == 0.65
        assert strategy.total_trades == 150


class TestBacktestModel:
    """Unit tests for Backtest SQLAlchemy model"""

    def test_create_backtest(self, db_session):
        """Test creating a backtest"""
        backtest = Backtest(
            strategy_type="sma_crossover",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 1),
            initial_capital=10000.0,
            parameters={"fast_period": 10, "slow_period": 30},
        )
        db_session.add(backtest)
        db_session.commit()

        assert backtest.id is not None
        assert backtest.status == BacktestStatus.PENDING
        assert backtest.symbol == "BTCUSDT"

    def test_backtest_with_results(self, db_session):
        """Test backtest with performance results"""
        backtest = Backtest(
            strategy_type="rsi",
            symbol="ETHUSDT",
            timeframe="4h",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=10000.0,
            parameters={"period": 14},
            status=BacktestStatus.COMPLETED,
            total_return=15.5,
            annual_return=31.0,
            sharpe_ratio=1.5,
            max_drawdown=-12.3,
            win_rate=0.58,
            total_trades=45,
            winning_trades=26,
            losing_trades=19,
            final_capital=11550.0,
        )
        db_session.add(backtest)
        db_session.commit()

        assert backtest.status == BacktestStatus.COMPLETED
        assert backtest.total_return == 15.5
        assert backtest.sharpe_ratio == 1.5
        assert backtest.winning_trades == 26

    def test_backtest_strategy_relationship(self, db_session):
        """Test backtest linked to strategy"""
        # Create strategy first
        strategy = Strategy(
            name="Parent Strategy",
            strategy_type=StrategyType.MACD,
            parameters={"fast_period": 12, "slow_period": 26, "signal_period": 9},
        )
        db_session.add(strategy)
        db_session.commit()

        # Create linked backtest
        backtest = Backtest(
            strategy_id=strategy.id,
            strategy_type="macd",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            initial_capital=10000.0,
            parameters=strategy.parameters,
        )
        db_session.add(backtest)
        db_session.commit()

        assert backtest.strategy_id == strategy.id
        assert backtest.strategy == strategy

    def test_backtest_to_dict(self, db_session):
        """Test Backtest.to_dict() method"""
        backtest = Backtest(
            strategy_type="bollinger_bands",
            symbol="BTCUSDT",
            timeframe="1d",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=50000.0,
            parameters={"period": 20, "std_dev": 2.0},
        )
        db_session.add(backtest)
        db_session.commit()

        result = backtest.to_dict()
        assert result["symbol"] == "BTCUSDT"
        assert result["timeframe"] == "1d"
        assert result["initial_capital"] == 50000.0
        assert "id" in result
        assert "created_at" in result

    def test_get_metrics_dict(self, db_session):
        """Test get_metrics_dict method"""
        backtest = Backtest(
            strategy_type="rsi",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 1),
            initial_capital=10000.0,
            parameters={},
            status=BacktestStatus.COMPLETED,
            total_return=20.0,
            sharpe_ratio=1.2,
            max_drawdown=-15.0,
            win_rate=0.55,
            total_trades=100,
        )
        db_session.add(backtest)
        db_session.commit()

        metrics = backtest.get_metrics_dict()
        assert metrics["total_return"] == 20.0
        assert metrics["sharpe_ratio"] == 1.2
        assert metrics["max_drawdown"] == -15.0
        assert metrics["win_rate"] == 0.55
        assert metrics["total_trades"] == 100


class TestStrategyTypeEnum:
    """Tests for strategy type enumeration"""

    def test_all_strategy_types_exist(self):
        """Test all expected strategy types are defined"""
        assert StrategyType.SMA_CROSSOVER.value == "sma_crossover"
        assert StrategyType.RSI.value == "rsi"
        assert StrategyType.MACD.value == "macd"
        assert StrategyType.BOLLINGER_BANDS.value == "bollinger_bands"
        assert StrategyType.CUSTOM.value == "custom"

    def test_strategy_type_comparison(self):
        """Test strategy type comparisons work"""
        assert StrategyType.RSI == StrategyType.RSI
        assert StrategyType.RSI != StrategyType.MACD


class TestStrategyStatusEnum:
    """Tests for strategy status enumeration"""

    def test_all_statuses_exist(self):
        """Test all expected statuses are defined"""
        assert StrategyStatus.DRAFT.value == "draft"
        assert StrategyStatus.ACTIVE.value == "active"
        assert StrategyStatus.PAUSED.value == "paused"
        assert StrategyStatus.ARCHIVED.value == "archived"


class TestPydanticSchemas:
    """Tests for Pydantic schemas"""

    def test_strategy_create_schema(self):
        """Test StrategyCreate schema validation"""
        from backend.api.schemas import StrategyCreate

        data = StrategyCreate(
            name="Test Strategy",
            strategy_type="sma_crossover",
            parameters={"fast_period": 10, "slow_period": 30},
            symbol="BTCUSDT",
            timeframe="1h",
        )

        assert data.name == "Test Strategy"
        assert data.strategy_type.value == "sma_crossover"
        assert data.parameters == {"fast_period": 10, "slow_period": 30}

    def test_strategy_create_minimal(self):
        """Test StrategyCreate with minimal data"""
        from backend.api.schemas import StrategyCreate

        data = StrategyCreate(
            name="Minimal",
            strategy_type="rsi",
        )

        assert data.name == "Minimal"
        assert data.parameters == {}

    def test_strategy_update_schema(self):
        """Test StrategyUpdate schema"""
        from backend.api.schemas import StrategyUpdate

        data = StrategyUpdate(
            name="Updated Name",
            parameters={"period": 20},
        )

        assert data.name == "Updated Name"
        assert data.parameters == {"period": 20}
        assert data.status is None  # Not provided

    def test_strategy_response_schema(self):
        """Test StrategyResponse schema"""
        from backend.api.schemas import StrategyResponse

        data = StrategyResponse(
            id="test-id-123",
            name="Response Test",
            strategy_type="macd",
            status="active",
            parameters={"fast": 12, "slow": 26},
            symbol="BTCUSDT",
            version=1,
        )

        assert data.id == "test-id-123"
        assert data.name == "Response Test"
        assert data.strategy_type == "macd"
        assert data.status == "active"

    def test_strategy_list_response(self):
        """Test StrategyListResponse schema"""
        from backend.api.schemas import StrategyListResponse, StrategyResponse

        items = [
            StrategyResponse(
                id=f"id-{i}",
                name=f"Strategy {i}",
                strategy_type="sma_crossover",
                status="draft",
                parameters={},
                version=1,
            )
            for i in range(3)
        ]

        response = StrategyListResponse(
            items=items,
            total=10,
            page=1,
            page_size=3,
        )

        assert len(response.items) == 3
        assert response.total == 10
        assert response.page == 1

    def test_strategy_default_parameters(self):
        """Test StrategyDefaultParameters schema"""
        from backend.api.schemas import StrategyDefaultParameters

        data = StrategyDefaultParameters(
            strategy_type="rsi",
            parameters={"period": 14, "overbought": 70, "oversold": 30},
            description="RSI oscillator strategy",
        )

        assert data.strategy_type == "rsi"
        assert data.parameters["period"] == 14
        assert data.description == "RSI oscillator strategy"

    def test_strategy_create_name_validation(self):
        """Test name validation rejects dangerous characters"""
        from pydantic import ValidationError

        from backend.api.schemas import StrategyCreate

        with pytest.raises(ValidationError):
            StrategyCreate(
                name="<script>alert('xss')</script>",
                strategy_type="rsi",
            )

    def test_strategy_create_empty_name_rejected(self):
        """Test empty name is rejected"""
        from pydantic import ValidationError

        from backend.api.schemas import StrategyCreate

        with pytest.raises(ValidationError):
            StrategyCreate(
                name="",
                strategy_type="rsi",
            )


# ============================================================================
# API TESTS (using test-only app without MCP)
# ============================================================================


class TestListStrategies:
    """Tests for GET /strategies/"""

    def test_list_empty(self, client):
        """Test listing strategies when none exist"""
        response = client.get("/api/v1/strategies/")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_with_strategies(self, client, sample_strategy_data):
        """Test listing strategies after creating some"""
        # Create strategies
        for i in range(3):
            strategy_data = sample_strategy_data.copy()
            strategy_data["name"] = f"Strategy {i + 1}"
            client.post("/api/v1/strategies/", json=strategy_data)

        response = client.get("/api/v1/strategies/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_pagination(self, client, sample_strategy_data):
        """Test pagination parameters"""
        # Create 5 strategies
        for i in range(5):
            strategy_data = sample_strategy_data.copy()
            strategy_data["name"] = f"Strategy {i + 1}"
            client.post("/api/v1/strategies/", json=strategy_data)

        # Get first page with 2 items
        response = client.get("/api/v1/strategies/?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_list_search(self, client, sample_strategy_data):
        """Test search filter"""
        # Create strategies with different names
        for name in ["Alpha Strategy", "Beta Strategy", "Gamma Strategy"]:
            strategy_data = sample_strategy_data.copy()
            strategy_data["name"] = name
            client.post("/api/v1/strategies/", json=strategy_data)

        response = client.get("/api/v1/strategies/?search=Alpha")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Alpha Strategy"


class TestGetStrategyTypes:
    """Tests for GET /strategies/types"""

    def test_get_types(self, client):
        """Test getting strategy types"""
        response = client.get("/api/v1/strategies/types")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

        # Check structure
        assert "strategy_type" in data[0]
        assert "parameters" in data[0]
        assert "description" in data[0]

        # Check known types exist
        types = [item["strategy_type"] for item in data]
        assert "sma_crossover" in types
        assert "rsi" in types
        assert "macd" in types


class TestGetStrategy:
    """Tests for GET /strategies/{strategy_id}"""

    def test_get_existing(self, client, sample_strategy_data):
        """Test getting an existing strategy"""
        # Create strategy
        create_response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        strategy_id = create_response.json()["id"]

        # Get strategy
        response = client.get(f"/api/v1/strategies/{strategy_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == strategy_id
        assert data["name"] == sample_strategy_data["name"]

    def test_get_not_found(self, client):
        """Test getting a non-existent strategy"""
        response = client.get("/api/v1/strategies/non-existent-id")
        assert response.status_code == 404


class TestCreateStrategy:
    """Tests for POST /strategies/"""

    def test_create_success(self, client, sample_strategy_data):
        """Test successful strategy creation"""
        response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["name"] == sample_strategy_data["name"]
        assert data["strategy_type"] == sample_strategy_data["strategy_type"]
        assert data["status"] == "draft"
        assert data["parameters"] == sample_strategy_data["parameters"]

    def test_create_minimal(self, client):
        """Test creating strategy with minimal data"""
        minimal_data = {
            "name": "Minimal Strategy",
            "strategy_type": "rsi",
        }
        response = client.post("/api/v1/strategies/", json=minimal_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Strategy"
        assert data["strategy_type"] == "rsi"

    def test_create_invalid_name(self, client, sample_strategy_data):
        """Test validation rejects invalid name"""
        sample_strategy_data["name"] = "<script>alert('xss')</script>"
        response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        assert response.status_code == 422  # Validation error

    def test_create_empty_name(self, client, sample_strategy_data):
        """Test validation rejects empty name"""
        sample_strategy_data["name"] = ""
        response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        assert response.status_code == 422


class TestUpdateStrategy:
    """Tests for PUT /strategies/{strategy_id}"""

    def test_update_success(self, client, sample_strategy_data):
        """Test successful strategy update"""
        # Create strategy
        create_response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        strategy_id = create_response.json()["id"]

        # Update strategy
        update_data = {
            "name": "Updated Strategy Name",
            "parameters": {"fast_period": 15, "slow_period": 40},
        }
        response = client.put(f"/api/v1/strategies/{strategy_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Updated Strategy Name"
        assert data["parameters"]["fast_period"] == 15
        assert data["version"] == 2  # Version incremented

    def test_update_status(self, client, sample_strategy_data):
        """Test updating strategy status"""
        # Create strategy
        create_response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        strategy_id = create_response.json()["id"]

        # Update status
        response = client.put(
            f"/api/v1/strategies/{strategy_id}", json={"status": "active"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    def test_update_not_found(self, client):
        """Test updating non-existent strategy"""
        response = client.put(
            "/api/v1/strategies/non-existent-id", json={"name": "New Name"}
        )
        assert response.status_code == 404


class TestDeleteStrategy:
    """Tests for DELETE /strategies/{strategy_id}"""

    def test_soft_delete(self, client, sample_strategy_data):
        """Test soft delete (default)"""
        # Create strategy
        create_response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        strategy_id = create_response.json()["id"]

        # Delete strategy (soft)
        response = client.delete(f"/api/v1/strategies/{strategy_id}")
        assert response.status_code == 204

        # Strategy should not be accessible
        get_response = client.get(f"/api/v1/strategies/{strategy_id}")
        assert get_response.status_code == 404

    def test_permanent_delete(self, client, sample_strategy_data):
        """Test permanent delete"""
        # Create strategy
        create_response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        strategy_id = create_response.json()["id"]

        # Delete permanently
        response = client.delete(f"/api/v1/strategies/{strategy_id}?permanent=true")
        assert response.status_code == 204

    def test_delete_not_found(self, client):
        """Test deleting non-existent strategy"""
        response = client.delete("/api/v1/strategies/non-existent-id")
        assert response.status_code == 404


class TestDuplicateStrategy:
    """Tests for POST /strategies/{strategy_id}/duplicate"""

    def test_duplicate_success(self, client, sample_strategy_data):
        """Test duplicating a strategy"""
        # Create original
        create_response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        original_id = create_response.json()["id"]

        # Duplicate
        response = client.post(f"/api/v1/strategies/{original_id}/duplicate")
        assert response.status_code == 201
        data = response.json()

        assert data["id"] != original_id
        assert data["name"] == f"{sample_strategy_data['name']} (Copy)"
        assert data["status"] == "draft"
        assert data["parameters"] == sample_strategy_data["parameters"]

    def test_duplicate_with_name(self, client, sample_strategy_data):
        """Test duplicating with custom name"""
        # Create original
        create_response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        original_id = create_response.json()["id"]

        # Duplicate with custom name
        response = client.post(
            f"/api/v1/strategies/{original_id}/duplicate?new_name=My Custom Copy"
        )
        assert response.status_code == 201
        assert response.json()["name"] == "My Custom Copy"


class TestActivateStrategy:
    """Tests for POST /strategies/{strategy_id}/activate"""

    def test_activate_success(self, client, sample_strategy_data):
        """Test activating a strategy"""
        # Create strategy
        create_response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        strategy_id = create_response.json()["id"]
        assert create_response.json()["status"] == "draft"

        # Activate
        response = client.post(f"/api/v1/strategies/{strategy_id}/activate")
        assert response.status_code == 200
        assert response.json()["status"] == "active"


class TestPauseStrategy:
    """Tests for POST /strategies/{strategy_id}/pause"""

    def test_pause_success(self, client, sample_strategy_data):
        """Test pausing a strategy"""
        # Create and activate strategy
        create_response = client.post("/api/v1/strategies/", json=sample_strategy_data)
        strategy_id = create_response.json()["id"]
        client.post(f"/api/v1/strategies/{strategy_id}/activate")

        # Pause
        response = client.post(f"/api/v1/strategies/{strategy_id}/pause")
        assert response.status_code == 200
        assert response.json()["status"] == "paused"
