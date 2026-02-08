"""
Tests for Strategy Builder API
Tests CRUD operations for visual block-based strategies.
"""


import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.database.models import Strategy, StrategyStatus, StrategyType

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
    """Create a test FastAPI app with strategy builder router"""
    from backend.api.routers.strategy_builder import router as strategy_builder_router

    app = FastAPI()
    # Match real application mounting:
    # backend/api/app.py uses: app.include_router(strategy_builder_router, prefix="/api/v1")
    # Router itself has prefix="/strategy-builder", so final path is
    # /api/v1/strategy-builder/..., which is what tests expect.
    app.include_router(strategy_builder_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_get_db

    # Create tables once for module
    Base.metadata.create_all(bind=engine)

    yield app

    # Cleanup
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
def sample_strategy_graph():
    """Sample strategy graph data for testing"""
    return {
        "name": "Test RSI Strategy",
        "description": "A test RSI oversold strategy",
        "timeframe": "1h",
        "symbol": "BTCUSDT",
        "market_type": "linear",
        "direction": "both",
        "initial_capital": 10000.0,
        "blocks": [
            {
                "id": "block_rsi",
                "type": "rsi",
                "category": "indicator",
                "name": "RSI",
                "icon": "graph-up",
                "x": 100,
                "y": 200,
                "params": {"period": 14, "overbought": 70, "oversold": 30},
            },
            {
                "id": "block_const_30",
                "type": "constant",
                "category": "input",
                "name": "Constant",
                "icon": "hash",
                "x": 100,
                "y": 300,
                "params": {"value": 30},
            },
            {
                "id": "block_less_than",
                "type": "less_than",
                "category": "condition",
                "name": "Less Than",
                "icon": "chevron-double-down",
                "x": 350,
                "y": 250,
                "params": {},
            },
        ],
        "connections": [
            {
                "id": "conn_1",
                "source": {"blockId": "block_rsi", "portId": "value"},
                "target": {"blockId": "block_less_than", "portId": "a"},
                "type": "data",
            },
            {
                "id": "conn_2",
                "source": {"blockId": "block_const_30", "portId": "value"},
                "target": {"blockId": "block_less_than", "portId": "b"},
                "type": "data",
            },
        ],
    }


class TestCreateStrategy:
    """Test creating strategies via Strategy Builder API"""

    def test_create_strategy_success(self, client, sample_strategy_graph):
        """Test successful strategy creation"""
        response = client.post("/api/v1/strategy-builder/strategies", json=sample_strategy_graph)

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert data["name"] == sample_strategy_graph["name"]
        assert data["timeframe"] == sample_strategy_graph["timeframe"]
        assert data["symbol"] == sample_strategy_graph["symbol"]
        assert data["market_type"] == sample_strategy_graph["market_type"]
        assert data["direction"] == sample_strategy_graph["direction"]
        assert len(data["blocks"]) == len(sample_strategy_graph["blocks"])
        assert len(data["connections"]) == len(sample_strategy_graph["connections"])
        assert data["is_builder_strategy"] is True

    def test_create_strategy_minimal(self, client):
        """Test creating strategy with minimal required fields"""
        minimal_data = {
            "name": "Minimal Strategy",
            "timeframe": "1h",
            "symbol": "BTCUSDT",
        }

        response = client.post("/api/v1/strategy-builder/strategies", json=minimal_data)

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Minimal Strategy"
        assert data["blocks"] == []
        assert data["connections"] == []

    def test_create_strategy_validation_error(self, client):
        """Test validation error on invalid data"""
        invalid_data = {
            "name": "",  # Empty name should fail
            "timeframe": "1h",
        }

        response = client.post("/api/v1/strategy-builder/strategies", json=invalid_data)

        assert response.status_code == 422  # Validation error


class TestGetStrategy:
    """Test retrieving strategies"""

    def test_get_strategy_success(self, client, sample_strategy_graph):
        """Test successful strategy retrieval"""
        # Create strategy first
        create_response = client.post("/api/v1/strategy-builder/strategies", json=sample_strategy_graph)
        assert create_response.status_code == 200
        strategy_id = create_response.json()["id"]

        # Get strategy
        response = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == strategy_id
        assert data["name"] == sample_strategy_graph["name"]
        assert len(data["blocks"]) == len(sample_strategy_graph["blocks"])
        assert len(data["connections"]) == len(sample_strategy_graph["connections"])

    def test_get_strategy_not_found(self, client):
        """Test getting non-existent strategy"""
        response = client.get("/api/v1/strategy-builder/strategies/nonexistent_id")

        assert response.status_code == 404

    def test_get_strategy_not_builder_strategy(self, client):
        """Test getting regular strategy (not builder strategy)"""
        # Create regular strategy directly in DB
        db = next(override_get_db())
        try:
            regular_strategy = Strategy(
                name="Regular Strategy",
                strategy_type=StrategyType.SMA_CROSSOVER,
                status=StrategyStatus.DRAFT,
                is_builder_strategy=False,
            )
            db.add(regular_strategy)
            db.commit()
            strategy_id = regular_strategy.id

            # Try to get via builder API
            response = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")

            assert response.status_code == 404
        finally:
            db.close()


class TestUpdateStrategy:
    """Test updating strategies"""

    def test_update_strategy_success(self, client, sample_strategy_graph):
        """Test successful strategy update"""
        # Create strategy first
        create_response = client.post("/api/v1/strategy-builder/strategies", json=sample_strategy_graph)
        strategy_id = create_response.json()["id"]

        # Update strategy
        update_data = {
            **sample_strategy_graph,
            "name": "Updated Strategy Name",
            "blocks": sample_strategy_graph["blocks"] + [
                {
                    "id": "block_new",
                    "type": "ema",
                    "category": "indicator",
                    "name": "EMA",
                    "icon": "graph-up-arrow",
                    "x": 200,
                    "y": 200,
                    "params": {"period": 20},
                }
            ],
        }

        response = client.put(f"/api/v1/strategy-builder/strategies/{strategy_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Updated Strategy Name"
        assert len(data["blocks"]) == len(update_data["blocks"])

    def test_update_strategy_not_found(self, client, sample_strategy_graph):
        """Test updating non-existent strategy"""
        response = client.put("/api/v1/strategy-builder/strategies/nonexistent_id", json=sample_strategy_graph)

        assert response.status_code == 404


class TestDeleteStrategy:
    """Test deleting strategies"""

    def test_delete_strategy_success(self, client, sample_strategy_graph):
        """Test successful strategy deletion (soft delete)"""
        # Create strategy first
        create_response = client.post("/api/v1/strategy-builder/strategies", json=sample_strategy_graph)
        strategy_id = create_response.json()["id"]

        # Delete strategy
        response = client.delete(f"/api/v1/strategy-builder/strategies/{strategy_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["strategy_id"] == strategy_id

        # Verify strategy is soft-deleted (should not be retrievable)
        get_response = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")
        assert get_response.status_code == 404

    def test_delete_strategy_not_found(self, client):
        """Test deleting non-existent strategy"""
        response = client.delete("/api/v1/strategy-builder/strategies/nonexistent_id")

        assert response.status_code == 404


class TestListStrategies:
    """Test listing strategies"""

    def test_list_strategies_empty(self, client):
        """Test listing when no strategies exist"""
        response = client.get("/api/v1/strategy-builder/strategies")

        assert response.status_code == 200
        data = response.json()

        assert "strategies" in data
        assert len(data["strategies"]) == 0
        assert data["total"] == 0

    def test_list_strategies_with_data(self, client, sample_strategy_graph):
        """Test listing with strategies"""
        # Create multiple strategies
        for i in range(3):
            strategy_data = {**sample_strategy_graph, "name": f"Strategy {i+1}"}
            client.post("/api/v1/strategy-builder/strategies", json=strategy_data)

        response = client.get("/api/v1/strategy-builder/strategies")

        assert response.status_code == 200
        data = response.json()

        assert len(data["strategies"]) == 3
        assert data["total"] == 3
        assert all("id" in s for s in data["strategies"])
        assert all("name" in s for s in data["strategies"])

    def test_list_strategies_pagination(self, client, sample_strategy_graph):
        """Test pagination"""
        # Create 5 strategies
        for i in range(5):
            strategy_data = {**sample_strategy_graph, "name": f"Strategy {i+1}"}
            client.post("/api/v1/strategy-builder/strategies", json=strategy_data)

        # Get first page
        response = client.get("/api/v1/strategy-builder/strategies?page=1&page_size=2")

        assert response.status_code == 200
        data = response.json()

        assert len(data["strategies"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] == 5


class TestGenerateCodeFromDb:
    """Tests for /strategies/{id}/generate-code endpoint"""

    def _create_codegen_strategy(self, client):
        """Create a simple strategy suitable for code generation (has data + action)."""
        data = {
            "name": "Codegen Strategy",
            "description": "Strategy for code generation tests",
            "timeframe": "1h",
            "symbol": "BTCUSDT",
            "market_type": "linear",
            "direction": "both",
            "initial_capital": 10000.0,
            "blocks": [
                {
                    "id": "block_price",
                    "type": "price",
                    "category": "input",
                    "name": "Price",
                    "icon": "currency-dollar",
                    "x": 100,
                    "y": 100,
                    "params": {},
                },
                {
                    "id": "block_rsi",
                    "type": "rsi",
                    "category": "indicator",
                    "name": "RSI",
                    "icon": "graph-up",
                    "x": 300,
                    "y": 100,
                    "params": {"period": 14, "overbought": 70, "oversold": 30},
                },
                {
                    "id": "block_buy",
                    "type": "buy",
                    "category": "action",
                    "name": "Buy",
                    "icon": "arrow-up-circle",
                    "x": 500,
                    "y": 80,
                    "params": {},
                },
            ],
            "connections": [
                {
                    "id": "conn_price_rsi",
                    "source": {"blockId": "block_price", "portId": "value"},
                    "target": {"blockId": "block_rsi", "portId": "source"},
                    "type": "data",
                },
                {
                    "id": "conn_rsi_buy",
                    "source": {"blockId": "block_rsi", "portId": "signal"},
                    "target": {"blockId": "block_buy", "portId": "trigger"},
                    "type": "data",
                },
            ],
        }

        response = client.post("/api/v1/strategy-builder/strategies", json=data)
        assert response.status_code == 200
        return response.json()["id"]

    def test_generate_code_success(self, client):
        """Generated code should be returned for a valid builder strategy in DB."""
        strategy_id = self._create_codegen_strategy(client)

        response = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/generate-code",
            json={
                "template": "backtest",
                "include_comments": True,
                "include_logging": True,
                "async_mode": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert isinstance(data.get("code"), str)
        assert len(data["code"]) > 0
        assert "class" in data["code"]
        assert data["strategy_id"] == strategy_id

    def test_generate_code_empty_graph(self, client):
        """Code generation should fail for strategies without blocks."""
        # Create minimal strategy with no blocks
        minimal = {
            "name": "Empty Strategy",
            "timeframe": "1h",
            "symbol": "BTCUSDT",
        }
        create_resp = client.post(
            "/api/v1/strategy-builder/strategies", json=minimal
        )
        assert create_resp.status_code == 200
        strategy_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/generate-code",
            json={"template": "backtest"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "no blocks" in data["detail"].lower()

    def test_generate_code_strategy_not_found(self, client):
        """Code generation for non-existent strategy should return 404."""
        response = client.post(
            "/api/v1/strategy-builder/strategies/nonexistent_id/generate-code",
            json={"template": "backtest"},
        )

        assert response.status_code == 404


class TestBacktestEndpoint:
    """Test backtest endpoint"""

    def test_backtest_endpoint_exists(self, client, sample_strategy_graph):
        """Test that backtest endpoint exists and accepts requests"""
        # Create strategy first
        create_response = client.post("/api/v1/strategy-builder/strategies", json=sample_strategy_graph)
        strategy_id = create_response.json()["id"]

        # Request backtest
        backtest_data = {
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T23:59:59Z",
        }

        response = client.post(f"/api/v1/strategy-builder/strategies/{strategy_id}/backtest", json=backtest_data)

        # Should return 200 (even if it's a stub)
        assert response.status_code == 200
        data = response.json()

        assert "strategy_id" in data
        assert data["strategy_id"] == strategy_id
        assert "status" in data

    def test_backtest_no_strategy(self, client):
        """Test backtest with non-existent strategy"""
        backtest_data = {
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T23:59:59Z",
        }

        response = client.post(
            "/api/v1/strategy-builder/strategies/nonexistent_id/backtest", json=backtest_data
        )

        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
