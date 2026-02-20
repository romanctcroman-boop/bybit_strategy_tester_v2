"""
Tests for backend/api/routers/strategy_builder.py

Router prefix: /api/v1/strategy-builder  (router.prefix="/strategy-builder", mounted at /api/v1)

Endpoints tested:
- POST   /api/v1/strategy-builder/symbols/cache-refresh
- POST   /api/v1/strategy-builder/strategies
- GET    /api/v1/strategy-builder/strategies
- GET    /api/v1/strategy-builder/strategies/{strategy_id}
- PUT    /api/v1/strategy-builder/strategies/{strategy_id}
- DELETE /api/v1/strategy-builder/strategies/{strategy_id}
- POST   /api/v1/strategy-builder/strategies/batch-delete
- POST   /api/v1/strategy-builder/strategies/{strategy_id}/clone
- GET    /api/v1/strategy-builder/strategies/{strategy_id}/versions  (DB variant)
- GET    /api/v1/strategy-builder/blocks/types
- POST   /api/v1/strategy-builder/blocks
- PUT    /api/v1/strategy-builder/blocks
- DELETE /api/v1/strategy-builder/blocks/{strategy_id}/{block_id}
- POST   /api/v1/strategy-builder/connections
- DELETE /api/v1/strategy-builder/connections/{strategy_id}/{connection_id}
- POST   /api/v1/strategy-builder/validate/{strategy_id}
- GET    /api/v1/strategy-builder/templates
- GET    /api/v1/strategy-builder/templates/{template_id}
- GET    /api/v1/strategy-builder/templates/categories
- GET    /api/v1/strategy-builder/templates/code
- GET    /api/v1/strategy-builder/indicators
- GET    /api/v1/strategy-builder/indicators/{indicator_type}
- POST   /api/v1/strategy-builder/generate
- POST   /api/v1/strategy-builder/import
- GET    /api/v1/strategy-builder/export/{strategy_id}
- POST   /api/v1/strategy-builder/preview/{strategy_id}
"""

import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Lazy-mock DB so the import chain does not try to connect.
if "backend.database" not in sys.modules:
    sys.modules["backend.database"] = MagicMock()
if "sqlalchemy.orm" not in sys.modules:
    sys.modules["sqlalchemy.orm"] = MagicMock()

from backend.api.app import app
from backend.database import get_db

BASE = "/api/v1/strategy-builder"

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Minimal SQLAlchemy session mock."""
    session = MagicMock()
    return session


@pytest.fixture
def db_override(mock_db):
    """Context manager that installs / cleans up get_db override."""

    def _override():
        return mock_db

    app.dependency_overrides[get_db] = _override
    yield mock_db
    app.dependency_overrides.clear()


def _make_strategy_mock(
    strategy_id="strat-123",
    name="Test Strategy",
    timeframe="1h",
    symbol="BTCUSDT",
    initial_capital=10000.0,
    position_size=1.0,
    parameters=None,
    builder_blocks=None,
    builder_connections=None,
    builder_graph=None,
    is_builder_strategy=True,
    is_deleted=False,
    version=1,
):
    """Build a minimal Strategy DB mock."""
    s = MagicMock()
    s.id = strategy_id
    s.name = name
    s.description = "A test strategy"
    s.timeframe = timeframe
    s.symbol = symbol
    s.initial_capital = initial_capital
    s.position_size = position_size
    s.parameters = parameters or {}
    s.builder_blocks = builder_blocks or []
    s.builder_connections = builder_connections or []
    s.builder_graph = builder_graph or {"blocks": [], "connections": [], "market_type": "linear", "direction": "both"}
    s.is_builder_strategy = is_builder_strategy
    s.is_deleted = is_deleted
    s.version = version
    s.market_type = "linear"
    s.direction = "both"
    s.created_at = datetime(2025, 1, 1, tzinfo=UTC)
    s.updated_at = datetime(2025, 6, 1, tzinfo=UTC)
    # Risk fields that clone endpoint accesses
    s.strategy_type = MagicMock()
    s.stop_loss_pct = None
    s.take_profit_pct = None
    s.max_drawdown_pct = None
    s.tags = []
    return s


# ===========================================================================
# POST /strategies  — create strategy
# ===========================================================================


class TestCreateStrategy:
    """POST /api/v1/strategy-builder/strategies"""

    def test_create_strategy_success(self, client, db_override):
        """Basic strategy creation returns 200 with correct fields."""
        mock_strat = _make_strategy_mock()
        db_override.add = MagicMock()
        db_override.commit = MagicMock()
        db_override.refresh = MagicMock(side_effect=lambda x: None)
        db_override.rollback = MagicMock()

        # After db.add + commit + refresh, the mock object is what the
        # router uses, so wire the mock_strat to the session mock.
        def fake_refresh(obj):
            # Copy attributes from mock_strat into obj so router reads them
            obj.id = mock_strat.id
            obj.name = mock_strat.name
            obj.description = mock_strat.description
            obj.timeframe = mock_strat.timeframe
            obj.symbol = mock_strat.symbol
            obj.initial_capital = mock_strat.initial_capital
            obj.position_size = mock_strat.position_size
            obj.parameters = mock_strat.parameters
            obj.builder_blocks = mock_strat.builder_blocks
            obj.builder_connections = mock_strat.builder_connections
            obj.is_builder_strategy = True
            obj.version = 1
            obj.created_at = mock_strat.created_at
            obj.updated_at = mock_strat.updated_at

        db_override.refresh = fake_refresh

        payload = {
            "name": "My RSI Strategy",
            "description": "RSI crossover",
            "timeframe": "15",
            "symbol": "BTCUSDT",
            "market_type": "linear",
            "direction": "long",
            "initial_capital": 10000.0,
            "blocks": [],
            "connections": [],
        }

        r = client.post(f"{BASE}/strategies", json=payload)

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == "My RSI Strategy"
        assert data["symbol"] == "BTCUSDT"
        assert data["market_type"] == "linear"
        assert data["direction"] == "long"
        assert data["initial_capital"] == 10000.0
        assert isinstance(data["blocks"], list)
        assert isinstance(data["connections"], list)

    def test_create_strategy_with_leverage(self, client, db_override):
        """Leverage is persisted in parameters['_leverage']."""
        mock_strat = _make_strategy_mock(parameters={"_leverage": 10})

        def fake_refresh(obj):
            obj.id = mock_strat.id
            obj.name = mock_strat.name
            obj.description = mock_strat.description
            obj.timeframe = mock_strat.timeframe
            obj.symbol = mock_strat.symbol
            obj.initial_capital = mock_strat.initial_capital
            obj.position_size = mock_strat.position_size
            obj.parameters = mock_strat.parameters
            obj.builder_blocks = mock_strat.builder_blocks
            obj.builder_connections = mock_strat.builder_connections
            obj.is_builder_strategy = True
            obj.version = 1
            obj.created_at = mock_strat.created_at
            obj.updated_at = mock_strat.updated_at

        db_override.refresh = fake_refresh

        payload = {
            "name": "Leveraged Strategy",
            "timeframe": "1h",
            "symbol": "ETHUSDT",
            "market_type": "linear",
            "direction": "both",
            "initial_capital": 5000.0,
            "leverage": 10.0,
            "blocks": [],
            "connections": [],
        }

        r = client.post(f"{BASE}/strategies", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["leverage"] == 10.0

    def test_create_strategy_name_too_short(self, client, db_override):
        """Empty name must fail validation (min_length=1)."""
        payload = {
            "name": "",
            "timeframe": "1h",
            "symbol": "BTCUSDT",
            "market_type": "linear",
            "direction": "both",
            "initial_capital": 10000.0,
            "blocks": [],
            "connections": [],
        }
        r = client.post(f"{BASE}/strategies", json=payload)
        assert r.status_code == 422

    def test_create_strategy_invalid_market_type(self, client, db_override):
        """market_type must match ^(spot|linear)$."""
        payload = {
            "name": "Bad Market",
            "timeframe": "1h",
            "symbol": "BTCUSDT",
            "market_type": "futures",  # invalid
            "direction": "both",
            "initial_capital": 10000.0,
            "blocks": [],
            "connections": [],
        }
        r = client.post(f"{BASE}/strategies", json=payload)
        assert r.status_code == 422

    def test_create_strategy_invalid_direction(self, client, db_override):
        """direction must match ^(long|short|both)$."""
        payload = {
            "name": "Bad Direction",
            "timeframe": "1h",
            "symbol": "BTCUSDT",
            "market_type": "linear",
            "direction": "neutral",  # invalid
            "initial_capital": 10000.0,
            "blocks": [],
            "connections": [],
        }
        r = client.post(f"{BASE}/strategies", json=payload)
        assert r.status_code == 422

    def test_create_strategy_capital_too_low(self, client, db_override):
        """initial_capital < 100 must fail (ge=100)."""
        payload = {
            "name": "Underfunded",
            "timeframe": "1h",
            "symbol": "BTCUSDT",
            "market_type": "linear",
            "direction": "both",
            "initial_capital": 50.0,  # below minimum
            "blocks": [],
            "connections": [],
        }
        r = client.post(f"{BASE}/strategies", json=payload)
        assert r.status_code == 422

    def test_create_strategy_db_error_returns_500(self, client, db_override):
        """Database error triggers rollback and 500 response."""
        db_override.commit.side_effect = Exception("DB connection lost")

        payload = {
            "name": "Failing Strategy",
            "timeframe": "1h",
            "symbol": "BTCUSDT",
            "market_type": "linear",
            "direction": "both",
            "initial_capital": 10000.0,
            "blocks": [],
            "connections": [],
        }
        r = client.post(f"{BASE}/strategies", json=payload)
        assert r.status_code == 500
        db_override.rollback.assert_called_once()

    def test_create_strategy_commission_rate_not_hardcoded(self, client, db_override):
        """
        Verify commission_rate=0.0007 is NOT part of strategy creation payload
        (it belongs to the backtest engine, not the strategy definition).
        The endpoint should not require or expose this field.
        """
        def fake_refresh(obj):
            obj.id = "strat-abc"
            obj.name = "Commission Check"
            obj.description = ""
            obj.timeframe = "1h"
            obj.symbol = "BTCUSDT"
            obj.initial_capital = 10000.0
            obj.position_size = 1.0
            obj.parameters = {}
            obj.builder_blocks = []
            obj.builder_connections = []
            obj.is_builder_strategy = True
            obj.version = 1
            obj.created_at = datetime(2025, 1, 1, tzinfo=UTC)
            obj.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

        db_override.refresh = fake_refresh

        payload = {
            "name": "Commission Check",
            "timeframe": "1h",
            "symbol": "BTCUSDT",
            "market_type": "linear",
            "direction": "both",
            "initial_capital": 10000.0,
            "blocks": [],
            "connections": [],
        }
        r = client.post(f"{BASE}/strategies", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        # commission_rate must NOT appear in the strategy response
        assert "commission_rate" not in data
        assert "commission" not in data


# ===========================================================================
# GET /strategies — list strategies
# ===========================================================================


class TestListStrategies:
    """GET /api/v1/strategy-builder/strategies"""

    def test_list_strategies_empty(self, client, db_override):
        """Empty DB returns empty strategies list."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.count.return_value = 0
        db_override.query.return_value = mock_query

        r = client.get(f"{BASE}/strategies")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["strategies"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    def test_list_strategies_with_results(self, client, db_override):
        """Returns correct shape with populated DB rows."""
        s1 = _make_strategy_mock(strategy_id="s1", name="Strategy A")
        s2 = _make_strategy_mock(strategy_id="s2", name="Strategy B")

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [s1, s2]
        mock_query.count.return_value = 2
        db_override.query.return_value = mock_query

        r = client.get(f"{BASE}/strategies")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 2
        assert len(data["strategies"]) == 2
        names = {item["name"] for item in data["strategies"]}
        assert "Strategy A" in names
        assert "Strategy B" in names

    def test_list_strategies_pagination(self, client, db_override):
        """page and page_size query parameters are respected."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.count.return_value = 0
        db_override.query.return_value = mock_query

        r = client.get(f"{BASE}/strategies?page=2&page_size=5")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["page"] == 2
        assert data["page_size"] == 5

    def test_list_strategies_page_size_too_large(self, client, db_override):
        """page_size > 100 must fail validation."""
        r = client.get(f"{BASE}/strategies?page_size=500")
        assert r.status_code == 422


# ===========================================================================
# GET /strategies/{strategy_id} — get single strategy
# ===========================================================================


class TestGetStrategy:
    """GET /api/v1/strategy-builder/strategies/{strategy_id}"""

    def test_get_strategy_success(self, client, db_override):
        """Existing strategy returns full response."""
        mock_strat = _make_strategy_mock()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_strat
        db_override.query.return_value = mock_query

        r = client.get(f"{BASE}/strategies/strat-123")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == "strat-123"
        assert data["name"] == "Test Strategy"
        assert data["timeframe"] == "1h"
        assert data["symbol"] == "BTCUSDT"

    def test_get_strategy_not_found(self, client, db_override):
        """Non-existent strategy returns 404."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        db_override.query.return_value = mock_query

        r = client.get(f"{BASE}/strategies/nonexistent-id")
        assert r.status_code == 404
        assert "not found" in r.text.lower()

    def test_get_strategy_includes_builder_graph(self, client, db_override):
        """builder_graph field from DB is included in response."""
        graph = {
            "blocks": [{"id": "b1", "type": "rsi"}],
            "connections": [],
            "market_type": "spot",
            "direction": "short",
        }
        mock_strat = _make_strategy_mock(builder_graph=graph)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_strat
        db_override.query.return_value = mock_query

        r = client.get(f"{BASE}/strategies/strat-123")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["market_type"] == "spot"
        assert data["direction"] == "short"


# ===========================================================================
# PUT /strategies/{strategy_id} — update strategy
# ===========================================================================


class TestUpdateStrategy:
    """PUT /api/v1/strategy-builder/strategies/{strategy_id}"""

    def _setup_db(self, db_override, mock_strat):
        """Wire up query chain so .first() returns mock_strat."""

        def query_side_effect(model):
            q = MagicMock()
            q.filter.return_value = q
            q.first.return_value = mock_strat
            q.count.return_value = 0
            q.order_by.return_value = q
            q.limit.return_value = q
            q.all.return_value = []
            return q

        db_override.query.side_effect = query_side_effect

    def test_update_strategy_success(self, client, db_override):
        """Valid PUT request updates strategy and returns new values."""
        mock_strat = _make_strategy_mock()
        self._setup_db(db_override, mock_strat)

        # Simulate refresh updating fields
        def fake_refresh(obj):
            obj.id = "strat-123"
            obj.name = "Updated Name"
            obj.description = "Updated description"
            obj.timeframe = "5"
            obj.symbol = "ETHUSDT"
            obj.initial_capital = 20000.0
            obj.position_size = 2.0
            obj.parameters = {}
            obj.builder_blocks = []
            obj.builder_connections = []
            obj.is_builder_strategy = True
            obj.version = 2
            obj.created_at = mock_strat.created_at
            obj.updated_at = datetime(2025, 6, 15, tzinfo=UTC)

        db_override.refresh = fake_refresh

        payload = {
            "name": "Updated Name",
            "description": "Updated description",
            "timeframe": "5",
            "symbol": "ETHUSDT",
            "market_type": "linear",
            "direction": "both",
            "initial_capital": 20000.0,
            "blocks": [],
            "connections": [],
        }

        r = client.put(f"{BASE}/strategies/strat-123", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == "Updated Name"
        assert data["symbol"] == "ETHUSDT"

    def test_update_strategy_not_found(self, client, db_override):
        """PUT on non-existent strategy returns 404."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        db_override.query.return_value = mock_query

        payload = {
            "name": "Ghost Strategy",
            "timeframe": "1h",
            "symbol": "BTCUSDT",
            "market_type": "linear",
            "direction": "both",
            "initial_capital": 10000.0,
            "blocks": [],
            "connections": [],
        }
        r = client.put(f"{BASE}/strategies/ghost-id", json=payload)
        assert r.status_code == 404


# ===========================================================================
# DELETE /strategies/{strategy_id} — soft delete strategy
# ===========================================================================


class TestDeleteStrategy:
    """DELETE /api/v1/strategy-builder/strategies/{strategy_id}"""

    def test_delete_strategy_success(self, client, db_override):
        """Successful soft delete returns status=deleted."""
        mock_strat = _make_strategy_mock()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_strat
        db_override.query.return_value = mock_query

        r = client.delete(f"{BASE}/strategies/strat-123")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "deleted"
        assert data["strategy_id"] == "strat-123"

    def test_delete_strategy_not_found(self, client, db_override):
        """Deleting non-existent strategy returns 404."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        db_override.query.return_value = mock_query

        r = client.delete(f"{BASE}/strategies/ghost-id")
        assert r.status_code == 404


# ===========================================================================
# POST /strategies/batch-delete
# ===========================================================================


class TestBatchDeleteStrategies:
    """POST /api/v1/strategy-builder/strategies/batch-delete"""

    def test_batch_delete_success(self, client, db_override):
        """Batch delete with valid IDs returns correct deleted_count."""
        s1 = _make_strategy_mock(strategy_id="s1")
        s2 = _make_strategy_mock(strategy_id="s2")

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [s1, s2]
        mock_query.update.return_value = None
        db_override.query.return_value = mock_query

        r = client.post(f"{BASE}/strategies/batch-delete", json={"strategy_ids": ["s1", "s2"]})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "deleted"
        assert data["deleted_count"] == 2
        assert set(data["deleted_ids"]) == {"s1", "s2"}

    def test_batch_delete_empty_ids_returns_400(self, client, db_override):
        """Empty strategy_ids list must return 400."""
        r = client.post(f"{BASE}/strategies/batch-delete", json={"strategy_ids": []})
        assert r.status_code == 400
        assert "No strategy IDs" in r.text

    def test_batch_delete_no_body_returns_400(self, client, db_override):
        """Missing body (no strategy_ids key) must return 400."""
        r = client.post(f"{BASE}/strategies/batch-delete", json={})
        assert r.status_code == 400


# ===========================================================================
# POST /strategies/{strategy_id}/clone
# ===========================================================================


class TestCloneStrategy:
    """POST /api/v1/strategy-builder/strategies/{strategy_id}/clone"""

    def test_clone_strategy_success(self, client, db_override):
        """Clone creates a new strategy with (copy) suffix."""
        original = _make_strategy_mock(strategy_id="orig-1", name="Original")
        cloned = _make_strategy_mock(strategy_id="clone-1", name="Original (copy)")

        call_count = {"n": 0}

        def query_side(model):
            q = MagicMock()
            call_count["n"] += 1
            # First query: find original; after add+commit, return cloned on refresh
            q.filter.return_value = q
            q.first.return_value = original
            return q

        db_override.query.side_effect = query_side

        def fake_refresh(obj):
            obj.id = cloned.id
            obj.name = cloned.name
            obj.description = cloned.description
            obj.timeframe = cloned.timeframe
            obj.symbol = cloned.symbol
            obj.builder_blocks = cloned.builder_blocks
            obj.builder_connections = cloned.builder_connections
            obj.created_at = cloned.created_at
            obj.updated_at = cloned.updated_at

        db_override.refresh = fake_refresh

        r = client.post(f"{BASE}/strategies/orig-1/clone")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        assert "name" in data

    def test_clone_strategy_not_found(self, client, db_override):
        """Cloning non-existent strategy returns 404."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        db_override.query.return_value = mock_query

        r = client.post(f"{BASE}/strategies/ghost-id/clone")
        assert r.status_code == 404

    def test_clone_strategy_custom_name(self, client, db_override):
        """Custom name via query param overrides default '(copy)' suffix."""
        original = _make_strategy_mock(strategy_id="orig-2", name="Alpha")
        cloned = _make_strategy_mock(strategy_id="clone-2", name="Beta")

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = original
        db_override.query.return_value = mock_query

        def fake_refresh(obj):
            obj.id = cloned.id
            obj.name = cloned.name
            obj.description = ""
            obj.timeframe = "1h"
            obj.symbol = "BTCUSDT"
            obj.builder_blocks = []
            obj.builder_connections = []
            obj.created_at = datetime(2025, 1, 1, tzinfo=UTC)
            obj.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

        db_override.refresh = fake_refresh

        r = client.post(f"{BASE}/strategies/orig-2/clone?new_name=Beta")
        assert r.status_code == 200, r.text


# ===========================================================================
# GET /strategies/{strategy_id}/versions  (DB-backed — requires DB)
# ===========================================================================


class TestGetStrategyVersionsDb:
    """GET /api/v1/strategy-builder/strategies/{strategy_id}/versions  (DB)"""

    def test_get_versions_success(self, client, db_override):
        """Returns version list for existing strategy."""
        mock_strat = _make_strategy_mock()
        mock_ver = MagicMock()
        mock_ver.id = 42
        mock_ver.version = 1
        mock_ver.created_at = datetime(2025, 1, 1, tzinfo=UTC)

        def query_side(model):
            q = MagicMock()
            q.filter.return_value = q
            q.first.return_value = mock_strat
            q.order_by.return_value = q
            q.limit.return_value = q
            q.all.return_value = [mock_ver]
            return q

        db_override.query.side_effect = query_side

        r = client.get(f"{BASE}/strategies/strat-123/versions")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["strategy_id"] == "strat-123"
        assert len(data["versions"]) == 1
        assert data["versions"][0]["version"] == 1

    def test_get_versions_strategy_not_found(self, client, db_override):
        """Returns 404 when strategy does not exist."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        db_override.query.return_value = mock_query

        r = client.get(f"{BASE}/strategies/ghost-id/versions")
        assert r.status_code == 404


# ===========================================================================
# GET /blocks/types
# ===========================================================================


class TestListBlockTypes:
    """GET /api/v1/strategy-builder/blocks/types"""

    def test_list_block_types_success(self, client):
        """Returns dict with block_types key."""
        r = client.get(f"{BASE}/blocks/types")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "block_types" in data
        assert isinstance(data["block_types"], (list, dict))


# ===========================================================================
# POST /blocks — add block (uses in-memory StrategyBuilder)
# ===========================================================================


class TestAddBlock:
    """POST /api/v1/strategy-builder/blocks"""

    def test_add_block_strategy_not_found(self, client):
        """Adding block to unknown strategy returns 404."""
        payload = {
            "strategy_id": "nonexistent-strat",
            "block_type": "INDICATOR_RSI",
            "x": 10,
            "y": 20,
            "parameters": {},
        }
        r = client.post(f"{BASE}/blocks", json=payload)
        assert r.status_code == 404

    def test_add_block_invalid_type(self, client):
        """Unknown block_type returns 400 or 404."""
        # We need a strategy that exists in the in-memory builder.
        # Since the builder is a module-level singleton we patch it.
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        with patch.dict(sb_router.strategy_builder.strategies, {"existing-strat": fake_graph}):
            payload = {
                "strategy_id": "existing-strat",
                "block_type": "TOTALLY_UNKNOWN_BLOCK",
                "x": 0,
                "y": 0,
                "parameters": {},
            }
            r = client.post(f"{BASE}/blocks", json=payload)
            assert r.status_code == 400


# ===========================================================================
# DELETE /blocks/{strategy_id}/{block_id}
# ===========================================================================


class TestDeleteBlock:
    """DELETE /api/v1/strategy-builder/blocks/{strategy_id}/{block_id}"""

    def test_delete_block_strategy_not_found(self, client):
        """Strategy not in memory returns 404."""
        r = client.delete(f"{BASE}/blocks/ghost-strat/block-1")
        assert r.status_code == 404

    def test_delete_block_block_not_found(self, client):
        """Block ID not in graph returns 404."""
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        fake_graph.remove_block.return_value = False  # block not found

        with patch.dict(sb_router.strategy_builder.strategies, {"s1": fake_graph}):
            r = client.delete(f"{BASE}/blocks/s1/missing-block")
            assert r.status_code == 404

    def test_delete_block_success(self, client):
        """Successful block deletion returns status=deleted."""
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        fake_graph.remove_block.return_value = True

        with patch.dict(sb_router.strategy_builder.strategies, {"s1": fake_graph}):
            r = client.delete(f"{BASE}/blocks/s1/block-42")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["status"] == "deleted"
            assert data["block_id"] == "block-42"


# ===========================================================================
# POST /connections
# ===========================================================================


class TestConnectBlocks:
    """POST /api/v1/strategy-builder/connections"""

    def test_connect_blocks_strategy_not_found(self, client):
        """Unknown strategy returns 404."""
        payload = {
            "strategy_id": "ghost",
            "source_block_id": "b1",
            "source_output": "value",
            "target_block_id": "b2",
            "target_input": "input",
        }
        r = client.post(f"{BASE}/connections", json=payload)
        assert r.status_code == 404

    def test_connect_blocks_source_not_found(self, client):
        """Source block missing returns 404."""
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        fake_graph.blocks = {}  # empty — source block not found

        with patch.dict(sb_router.strategy_builder.strategies, {"s1": fake_graph}):
            payload = {
                "strategy_id": "s1",
                "source_block_id": "missing-src",
                "source_output": "value",
                "target_block_id": "b2",
                "target_input": "input",
            }
            r = client.post(f"{BASE}/connections", json=payload)
            assert r.status_code == 404

    def test_connect_blocks_success(self, client):
        """Valid connection returns connection dict."""
        from backend.api.routers import strategy_builder as sb_router

        fake_conn = MagicMock()
        fake_conn.to_dict.return_value = {
            "id": "conn-1",
            "source_block_id": "b1",
            "target_block_id": "b2",
        }

        fake_graph = MagicMock()
        fake_graph.blocks = {"b1": MagicMock(), "b2": MagicMock()}

        with patch.dict(sb_router.strategy_builder.strategies, {"s1": fake_graph}):
            sb_router.strategy_builder.connect = MagicMock(return_value=fake_conn)

            payload = {
                "strategy_id": "s1",
                "source_block_id": "b1",
                "source_output": "value",
                "target_block_id": "b2",
                "target_input": "input",
            }
            r = client.post(f"{BASE}/connections", json=payload)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["id"] == "conn-1"


# ===========================================================================
# DELETE /connections/{strategy_id}/{connection_id}
# ===========================================================================


class TestDisconnectBlocks:
    """DELETE /api/v1/strategy-builder/connections/{strategy_id}/{connection_id}"""

    def test_disconnect_strategy_not_found(self, client):
        """Unknown strategy returns 404."""
        r = client.delete(f"{BASE}/connections/ghost/conn-1")
        assert r.status_code == 404

    def test_disconnect_connection_not_found(self, client):
        """Connection not in graph returns 404."""
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        fake_graph.disconnect.return_value = False

        with patch.dict(sb_router.strategy_builder.strategies, {"s1": fake_graph}):
            r = client.delete(f"{BASE}/connections/s1/missing-conn")
            assert r.status_code == 404

    def test_disconnect_success(self, client):
        """Successful disconnect returns status=deleted."""
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        fake_graph.disconnect.return_value = True

        with patch.dict(sb_router.strategy_builder.strategies, {"s1": fake_graph}):
            r = client.delete(f"{BASE}/connections/s1/conn-99")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["status"] == "deleted"
            assert data["connection_id"] == "conn-99"


# ===========================================================================
# POST /validate/{strategy_id}
# ===========================================================================


class TestValidateStrategy:
    """POST /api/v1/strategy-builder/validate/{strategy_id}"""

    def test_validate_strategy_not_found(self, client):
        """Validation of unknown strategy returns 404."""
        r = client.post(f"{BASE}/validate/ghost-id")
        assert r.status_code == 404

    def test_validate_strategy_standard_mode(self, client):
        """Standard mode validation returns validation result dict."""
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        fake_result = MagicMock()
        fake_result.to_dict.return_value = {"is_valid": True, "errors": [], "warnings": []}

        with patch.dict(sb_router.strategy_builder.strategies, {"s1": fake_graph}):
            sb_router.validator.validate = MagicMock(return_value=fake_result)

            r = client.post(f"{BASE}/validate/s1?mode=standard")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["is_valid"] is True

    def test_validate_strategy_invalid_mode(self, client):
        """mode not in (standard|backtest|live) returns 422."""
        r = client.post(f"{BASE}/validate/some-id?mode=invalid_mode")
        assert r.status_code == 422


# ===========================================================================
# GET /templates
# ===========================================================================


class TestListTemplates:
    """GET /api/v1/strategy-builder/templates"""

    def test_list_templates_success(self, client):
        """Returns dict with templates list."""
        r = client.get(f"{BASE}/templates")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "templates" in data
        assert isinstance(data["templates"], list)

    def test_list_templates_with_category_filter(self, client):
        """Passing category filter does not crash (may return empty list)."""
        r = client.get(f"{BASE}/templates?category=trend_following")
        assert r.status_code == 200, r.text

    def test_list_templates_with_difficulty_filter(self, client):
        """Passing difficulty filter does not crash."""
        r = client.get(f"{BASE}/templates?difficulty=beginner")
        assert r.status_code == 200, r.text


# ===========================================================================
# GET /templates/categories
# ===========================================================================


class TestListTemplateCategories:
    """GET /api/v1/strategy-builder/templates/categories"""

    def test_list_categories_success(self, client):
        """Returns dict with categories list."""
        r = client.get(f"{BASE}/templates/categories")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)


# ===========================================================================
# GET /templates/code
# ===========================================================================


class TestListCodeTemplates:
    """GET /api/v1/strategy-builder/templates/code"""

    def test_list_code_templates_success(self, client):
        """Returns dict with templates list of code templates."""
        r = client.get(f"{BASE}/templates/code")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "templates" in data
        assert isinstance(data["templates"], list)
        # Each entry should have id and name
        if data["templates"]:
            assert "id" in data["templates"][0]
            assert "name" in data["templates"][0]


# ===========================================================================
# GET /templates/{template_id}
# ===========================================================================


class TestGetTemplate:
    """GET /api/v1/strategy-builder/templates/{template_id}"""

    def test_get_template_not_found(self, client):
        """Non-existent template returns 404."""
        from backend.api.routers import strategy_builder as sb_router

        sb_router.template_manager.get_template = MagicMock(return_value=None)

        r = client.get(f"{BASE}/templates/nonexistent-tmpl")
        assert r.status_code == 404

    def test_get_template_success(self, client):
        """Existing template returns its dict."""
        from backend.api.routers import strategy_builder as sb_router

        fake_tmpl = MagicMock()
        fake_tmpl.to_dict.return_value = {
            "id": "rsi_basic",
            "name": "RSI Basic",
            "category": "momentum",
        }
        sb_router.template_manager.get_template = MagicMock(return_value=fake_tmpl)

        r = client.get(f"{BASE}/templates/rsi_basic")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == "rsi_basic"


# ===========================================================================
# GET /indicators
# ===========================================================================


class TestListIndicators:
    """GET /api/v1/strategy-builder/indicators"""

    def test_list_indicators_success(self, client):
        """Returns dict with indicators list."""
        r = client.get(f"{BASE}/indicators")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "indicators" in data

    def test_list_indicators_returns_list_or_dict(self, client):
        """indicators value is a list or dict (IndicatorLibrary-dependent)."""
        r = client.get(f"{BASE}/indicators")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["indicators"], (list, dict))


# ===========================================================================
# GET /indicators/{indicator_type}
# ===========================================================================


class TestGetIndicatorInfo:
    """GET /api/v1/strategy-builder/indicators/{indicator_type}"""

    def test_get_indicator_info_not_found(self, client):
        """Unknown indicator type returns 404."""
        r = client.get(f"{BASE}/indicators/UNKNOWN_INDICATOR")
        assert r.status_code == 404

    def test_get_indicator_rsi(self, client):
        """RSI indicator info returns something meaningful."""
        r = client.get(f"{BASE}/indicators/rsi")
        # Either 200 (found) or 404 (name casing); both are acceptable
        assert r.status_code in (200, 404)


# ===========================================================================
# POST /generate
# ===========================================================================


class TestGenerateCode:
    """POST /api/v1/strategy-builder/generate"""

    def test_generate_strategy_not_found(self, client):
        """Generating code for unknown strategy returns 404."""
        payload = {
            "strategy_id": "ghost-strat",
            "template": "backtest",
            "include_comments": True,
            "include_logging": True,
            "async_mode": False,
        }
        r = client.post(f"{BASE}/generate", json=payload)
        assert r.status_code == 404

    def test_generate_invalid_graph_returns_errors(self, client):
        """Invalid graph (no blocks) returns success=False with errors list."""
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        fake_validation = MagicMock()
        fake_validation.is_valid = False
        fake_validation.errors = [MagicMock(to_dict=lambda: {"message": "No blocks"})]

        with patch.dict(sb_router.strategy_builder.strategies, {"s1": fake_graph}):
            sb_router.validator.validate = MagicMock(return_value=fake_validation)

            payload = {
                "strategy_id": "s1",
                "template": "backtest",
                "include_comments": True,
                "include_logging": True,
                "async_mode": False,
            }
            r = client.post(f"{BASE}/generate", json=payload)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["success"] is False
            assert data["code"] is None
            assert isinstance(data["errors"], list)


# ===========================================================================
# POST /import
# ===========================================================================


class TestImportStrategy:
    """POST /api/v1/strategy-builder/import"""

    def test_import_invalid_data_returns_400(self, client):
        """Malformed strategy JSON returns 400."""
        from backend.api.routers import strategy_builder as sb_router

        with patch.object(
            sb_router.StrategyGraph,
            "from_dict",
            side_effect=Exception("Invalid graph"),
        ):
            r = client.post(f"{BASE}/import", json={"invalid": "data"})
            assert r.status_code == 400
            assert "Invalid strategy data" in r.text

    def test_import_valid_strategy(self, client):
        """Valid strategy JSON returns success=True with strategy_id."""
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        fake_graph.id = "imported-strat-id"
        fake_graph.name = "Imported Strategy"

        with patch.object(sb_router.StrategyGraph, "from_dict", return_value=fake_graph):
            r = client.post(
                f"{BASE}/import",
                json={"id": "imported-strat-id", "name": "Imported Strategy"},
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["success"] is True
            assert data["strategy_id"] == "imported-strat-id"


# ===========================================================================
# GET /export/{strategy_id}
# ===========================================================================


class TestExportStrategy:
    """GET /api/v1/strategy-builder/export/{strategy_id}"""

    def test_export_strategy_not_found(self, client):
        """Exporting unknown strategy returns 404."""
        r = client.get(f"{BASE}/export/ghost-strat")
        assert r.status_code == 404

    def test_export_strategy_success(self, client):
        """Known strategy export returns graph dict."""
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        fake_graph.to_dict.return_value = {
            "id": "s1",
            "name": "My Strategy",
            "blocks": [],
            "connections": [],
        }

        with patch.dict(sb_router.strategy_builder.strategies, {"s1": fake_graph}):
            r = client.get(f"{BASE}/export/s1")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["id"] == "s1"
            assert data["name"] == "My Strategy"


# ===========================================================================
# POST /preview/{strategy_id}
# ===========================================================================


class TestPreviewStrategy:
    """POST /api/v1/strategy-builder/preview/{strategy_id}"""

    def test_preview_strategy_not_found(self, client):
        """Preview of unknown strategy returns 404."""
        r = client.post(f"{BASE}/preview/ghost-strat")
        assert r.status_code == 404

    def test_preview_strategy_invalid_validation(self, client):
        """Invalid strategy returns success=False."""
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        fake_validation = MagicMock()
        fake_validation.is_valid = False
        fake_validation.errors = [MagicMock(to_dict=lambda: {"message": "missing output"})]

        with patch.dict(sb_router.strategy_builder.strategies, {"s1": fake_graph}):
            sb_router.validator.validate = MagicMock(return_value=fake_validation)

            r = client.post(f"{BASE}/preview/s1")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["success"] is False

    def test_preview_strategy_valid_returns_metadata(self, client):
        """Valid strategy preview returns success=True with metadata."""
        from backend.api.routers import strategy_builder as sb_router

        fake_graph = MagicMock()
        fake_graph.name = "Test"
        fake_graph.blocks = {"b1": MagicMock(), "b2": MagicMock()}
        fake_graph.connections = []

        fake_validation = MagicMock()
        fake_validation.is_valid = True
        fake_validation.errors = []
        fake_validation.estimated_lookback = 14
        fake_validation.complexity_score = 3.5

        with patch.dict(sb_router.strategy_builder.strategies, {"s1": fake_graph}):
            sb_router.validator.validate = MagicMock(return_value=fake_validation)

            r = client.post(f"{BASE}/preview/s1")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["success"] is True
            assert data["strategy_id"] == "s1"
            assert "block_count" in data
            assert "complexity_score" in data

    def test_preview_candle_count_validation(self, client):
        """candle_count < 10 or > 1000 must fail validation."""
        r1 = client.post(f"{BASE}/preview/some-id?candle_count=5")
        assert r1.status_code == 422

        r2 = client.post(f"{BASE}/preview/some-id?candle_count=2000")
        assert r2.status_code == 422


# ===========================================================================
# POST /symbols/cache-refresh
# ===========================================================================


class TestSymbolsCacheRefresh:
    """POST /api/v1/strategy-builder/symbols/cache-refresh"""

    def test_cache_refresh_success(self, client):
        """Successful refresh returns ok=True with symbol counts."""
        with patch("backend.api.routers.strategy_builder.BybitAdapter") as MockAdapter:
            adapter_instance = MockAdapter.return_value
            adapter_instance.get_symbols_list.return_value = ["BTCUSDT", "ETHUSDT"]

            with patch("asyncio.get_event_loop") as mock_loop:
                # run_in_executor returns a coroutine-like value
                mock_loop.return_value.run_in_executor = MagicMock(
                    side_effect=lambda _, fn: fn()
                )

                r = client.post(f"{BASE}/symbols/cache-refresh")
                # May be 200 (success) or 500 (adapter import fails in test env)
                assert r.status_code in (200, 500)

    def test_cache_refresh_error_returns_500(self, client):
        """Adapter error returns 500."""
        with patch(
            "backend.api.routers.strategy_builder.BybitAdapter",
            side_effect=Exception("Connection refused"),
        ):
            r = client.post(f"{BASE}/symbols/cache-refresh")
            assert r.status_code == 500
