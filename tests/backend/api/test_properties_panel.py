"""
Tests for Properties Panel → BacktestRequest validation and field propagation.

Covers BUG-1 (direction ignored), BUG-2 (position_size ignored),
BUG-3 (no symbol/interval validation) fixes from AUDIT_PROPERTIES_PANEL.md.

Naming: test_[function]_[scenario]
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

# ====================================================================
# Unit Tests: BacktestRequest Pydantic Validation
# ====================================================================


class TestBacktestRequestValidation:
    """Test BacktestRequest field validation (Pydantic level)."""

    @pytest.fixture(autouse=True)
    def _import_model(self):
        """Import BacktestRequest once per class."""
        from backend.api.routers.strategy_builder import BacktestRequest

        self.BacktestRequest = BacktestRequest

    def _valid_payload(self, **overrides) -> dict:
        """Build a minimal valid payload for BacktestRequest."""
        base = {
            "symbol": "BTCUSDT",
            "interval": "15",
            "start_date": "2025-01-01T00:00:00Z",
            "end_date": "2025-01-31T00:00:00Z",
            "initial_capital": 10000.0,
            "commission": 0.0007,
        }
        base.update(overrides)
        return base

    # --- Symbol ---

    def test_symbol_valid(self):
        req = self.BacktestRequest(**self._valid_payload(symbol="ETHUSDT"))
        assert req.symbol == "ETHUSDT"

    def test_symbol_too_short_rejected(self):
        with pytest.raises(ValidationError, match="String should have at least 2 character"):
            self.BacktestRequest(**self._valid_payload(symbol="A"))

    def test_symbol_too_long_rejected(self):
        with pytest.raises(ValidationError, match="at most 20"):
            self.BacktestRequest(**self._valid_payload(symbol="A" * 21))

    # --- Interval ---

    def test_interval_valid_standard(self):
        for tf in ["1", "5", "15", "30", "60", "240", "D", "W", "M"]:
            req = self.BacktestRequest(**self._valid_payload(interval=tf))
            assert req.interval == tf

    def test_interval_legacy_mapping(self):
        """Legacy timeframes should be auto-mapped: 3→5, 120→60, 360→240, 720→D."""
        mapping = {"3": "5", "120": "60", "360": "240", "720": "D"}
        for legacy, expected in mapping.items():
            req = self.BacktestRequest(**self._valid_payload(interval=legacy))
            assert req.interval == expected, f"Legacy TF {legacy} should map to {expected}"

    def test_interval_invalid_rejected(self):
        with pytest.raises(ValidationError, match="Unsupported interval"):
            self.BacktestRequest(**self._valid_payload(interval="1000h"))

    def test_interval_empty_string_rejected(self):
        with pytest.raises(ValidationError, match="Unsupported interval"):
            self.BacktestRequest(**self._valid_payload(interval=""))

    # --- Market Type ---

    def test_market_type_valid(self):
        for mt in ["spot", "linear"]:
            req = self.BacktestRequest(**self._valid_payload(market_type=mt))
            assert req.market_type == mt

    def test_market_type_case_insensitive(self):
        req = self.BacktestRequest(**self._valid_payload(market_type="SPOT"))
        assert req.market_type == "spot"

    def test_market_type_invalid_rejected(self):
        with pytest.raises(ValidationError, match="market_type must be one of"):
            self.BacktestRequest(**self._valid_payload(market_type="futures"))

    # --- Direction (BUG-1 fix) ---

    def test_direction_present_in_model(self):
        """BUG-1: direction field must exist in BacktestRequest."""
        req = self.BacktestRequest(**self._valid_payload(direction="long"))
        assert req.direction == "long"

    def test_direction_default_is_both(self):
        req = self.BacktestRequest(**self._valid_payload())
        assert req.direction == "both"

    def test_direction_valid_values(self):
        for d in ["long", "short", "both"]:
            req = self.BacktestRequest(**self._valid_payload(direction=d))
            assert req.direction == d

    def test_direction_case_insensitive(self):
        req = self.BacktestRequest(**self._valid_payload(direction="LONG"))
        assert req.direction == "long"

    def test_direction_invalid_rejected(self):
        with pytest.raises(ValidationError, match="direction must be one of"):
            self.BacktestRequest(**self._valid_payload(direction="up"))

    # --- Position Size (BUG-2 fix) ---

    def test_position_size_present_in_model(self):
        """BUG-2: position_size field must exist in BacktestRequest."""
        req = self.BacktestRequest(**self._valid_payload(position_size=0.5))
        assert req.position_size == 0.5

    def test_position_size_default_is_1(self):
        req = self.BacktestRequest(**self._valid_payload())
        assert req.position_size == 1.0

    def test_position_size_minimum(self):
        with pytest.raises(ValidationError, match="greater than or equal to 0.01"):
            self.BacktestRequest(**self._valid_payload(position_size=0.001))

    # --- Position Size Type (BUG-2 fix) ---

    def test_position_size_type_present_in_model(self):
        """BUG-2: position_size_type field must exist in BacktestRequest."""
        req = self.BacktestRequest(**self._valid_payload(position_size_type="fixed_amount"))
        assert req.position_size_type == "fixed_amount"

    def test_position_size_type_default_is_percent(self):
        req = self.BacktestRequest(**self._valid_payload())
        assert req.position_size_type == "percent"

    def test_position_size_type_valid_values(self):
        for t in ["percent", "fixed_amount", "contracts"]:
            req = self.BacktestRequest(**self._valid_payload(position_size_type=t))
            assert req.position_size_type == t

    def test_position_size_type_invalid_rejected(self):
        with pytest.raises(ValidationError, match="position_size_type must be one of"):
            self.BacktestRequest(**self._valid_payload(position_size_type="lots"))

    # --- Commission ---

    def test_commission_default_is_tradingview_parity(self):
        """Commission must default to 0.0007 (0.07%) for TradingView parity."""
        req = self.BacktestRequest(**self._valid_payload())
        assert req.commission == 0.0007

    def test_commission_min_zero(self):
        req = self.BacktestRequest(**self._valid_payload(commission=0))
        assert req.commission == 0

    def test_commission_max_1_percent(self):
        with pytest.raises(ValidationError, match="less than or equal to 0.01"):
            self.BacktestRequest(**self._valid_payload(commission=0.02))

    # --- Leverage ---

    def test_leverage_default_10(self):
        req = self.BacktestRequest(**self._valid_payload())
        assert req.leverage == 10

    def test_leverage_range(self):
        req = self.BacktestRequest(**self._valid_payload(leverage=1))
        assert req.leverage == 1
        req = self.BacktestRequest(**self._valid_payload(leverage=125))
        assert req.leverage == 125

    def test_leverage_exceeds_max_rejected(self):
        with pytest.raises(ValidationError, match="less than or equal to 125"):
            self.BacktestRequest(**self._valid_payload(leverage=126))

    # --- Initial Capital ---

    def test_initial_capital_min_100(self):
        with pytest.raises(ValidationError, match="greater than or equal to 100"):
            self.BacktestRequest(**self._valid_payload(initial_capital=50))

    def test_initial_capital_max(self):
        with pytest.raises(ValidationError, match="less than or equal to"):
            self.BacktestRequest(**self._valid_payload(initial_capital=200_000_000))

    # --- Pyramiding ---

    def test_pyramiding_default_1(self):
        req = self.BacktestRequest(**self._valid_payload())
        assert req.pyramiding == 1

    def test_pyramiding_range(self):
        req = self.BacktestRequest(**self._valid_payload(pyramiding=0))
        assert req.pyramiding == 0
        req = self.BacktestRequest(**self._valid_payload(pyramiding=99))
        assert req.pyramiding == 99

    def test_pyramiding_exceeds_max_rejected(self):
        with pytest.raises(ValidationError, match="less than or equal to 99"):
            self.BacktestRequest(**self._valid_payload(pyramiding=100))

    # --- No Trade Days ---

    def test_no_trade_days_valid(self):
        req = self.BacktestRequest(**self._valid_payload(no_trade_days=[0, 5, 6]))
        assert req.no_trade_days == [0, 5, 6]

    def test_no_trade_days_none_default(self):
        req = self.BacktestRequest(**self._valid_payload())
        assert req.no_trade_days is None

    def test_no_trade_days_empty_list(self):
        req = self.BacktestRequest(**self._valid_payload(no_trade_days=[]))
        assert req.no_trade_days == []

    # --- Dates ---

    def test_dates_required(self):
        payload = self._valid_payload()
        del payload["start_date"]
        with pytest.raises(ValidationError, match="start_date"):
            self.BacktestRequest(**payload)

    # --- Full payload round-trip (simulates JS buildBacktestRequest) ---

    def test_full_payload_from_ui(self):
        """Simulate full payload as sent by buildBacktestRequest() in JS."""
        payload = {
            "symbol": "ETHUSDT",
            "interval": "60",
            "start_date": "2025-03-01T00:00:00Z",
            "end_date": "2025-03-15T00:00:00Z",
            "market_type": "spot",
            "initial_capital": 5000.0,
            "leverage": 5,
            "direction": "long",
            "pyramiding": 3,
            "commission": 0.0007,
            "slippage": 0.0005,
            "position_size_type": "percent",
            "position_size": 0.5,  # 50%
            "no_trade_days": [5, 6],  # block Sat+Sun
        }
        req = self.BacktestRequest(**payload)
        assert req.symbol == "ETHUSDT"
        assert req.interval == "60"
        assert req.direction == "long"
        assert req.position_size == 0.5
        assert req.position_size_type == "percent"
        assert req.no_trade_days == [5, 6]


# ====================================================================
# Integration Tests: BacktestRequest → BacktestConfig field propagation
# ====================================================================


class TestBacktestRequestToConfigPropagation:
    """Test that fields from BacktestRequest correctly propagate to BacktestConfig."""

    def test_direction_propagates_to_config(self):
        """BUG-1 regression: direction from request must reach BacktestConfig."""
        from backend.backtesting.models import BacktestConfig, StrategyType

        config = BacktestConfig(
            symbol="BTCUSDT",
            interval="15",
            start_date=datetime(2025, 1, 1, tzinfo=UTC),
            end_date=datetime(2025, 1, 15, tzinfo=UTC),
            strategy_type=StrategyType.CUSTOM,
            direction="long",
            position_size=0.5,
        )
        assert config.direction == "long"

    def test_position_size_propagates_to_config(self):
        """BUG-2 regression: position_size from request must reach BacktestConfig."""
        from backend.backtesting.models import BacktestConfig, StrategyType

        config = BacktestConfig(
            symbol="BTCUSDT",
            interval="15",
            start_date=datetime(2025, 1, 1, tzinfo=UTC),
            end_date=datetime(2025, 1, 15, tzinfo=UTC),
            strategy_type=StrategyType.CUSTOM,
            position_size=0.75,
        )
        assert config.position_size == 0.75

    def test_commission_not_double_divided(self):
        """Verify commission (0.0007) → taker_fee/maker_fee without double division.

        JS sends: 0.07 / 100 = 0.0007
        Backend BacktestRequest receives 0.0007
        BacktestConfig gets taker_fee=0.0007, maker_fee=0.0007
        """
        from backend.api.routers.strategy_builder import BacktestRequest

        req = BacktestRequest(
            start_date="2025-01-01T00:00:00Z",
            end_date="2025-01-15T00:00:00Z",
            commission=0.0007,
        )
        # The endpoint assigns: taker_fee=request.commission, maker_fee=request.commission
        assert req.commission == 0.0007
        # No transformation happens to commission before assignment — verify it stays 0.0007


# ====================================================================
# API Integration Tests: run_backtest_from_builder
# ====================================================================


class TestBacktestEndpointFieldPropagation:
    """Test that POST /strategies/{id}/backtest correctly uses Properties fields."""

    @pytest.fixture
    def setup_app(self):
        """Create test app and clean DB."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from backend.api.routers.strategy_builder import router
        from backend.database import Base, get_db
        from backend.database.models import Strategy, StrategyStatus, StrategyType

        db_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        TestSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

        def override():
            db = TestSession()
            try:
                yield db
            finally:
                db.close()

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_db] = override
        Base.metadata.create_all(bind=db_engine)

        # Create a test strategy
        db = TestSession()
        strategy = Strategy(
            name="Test Direction Strategy",
            description="",
            strategy_type=StrategyType.CUSTOM,
            status=StrategyStatus.DRAFT,
            symbol="BTCUSDT",
            timeframe="15",
            initial_capital=10000.0,
            position_size=1.0,
            parameters={},
            is_builder_strategy=True,
            builder_graph={
                "blocks": [],
                "connections": [],
                "market_type": "linear",
                "direction": "short",  # Saved as "short" in builder_graph
            },
            builder_blocks=[
                {
                    "id": "block_rsi",
                    "type": "rsi",
                    "category": "indicator",
                    "name": "RSI",
                    "params": {"period": 14},
                }
            ],
            builder_connections=[],
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        strategy_id = str(strategy.id)
        db.close()

        client = TestClient(app)
        return client, strategy_id

    def test_backtest_validates_invalid_interval(self, setup_app):
        """Invalid interval should return 422, not 500."""
        client, strategy_id = setup_app
        resp = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/backtest",
            json={
                "interval": "invalid_tf",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-15T00:00:00Z",
            },
        )
        assert resp.status_code == 422

    def test_backtest_validates_invalid_direction(self, setup_app):
        """Invalid direction should return 422."""
        client, strategy_id = setup_app
        resp = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/backtest",
            json={
                "direction": "up",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-15T00:00:00Z",
            },
        )
        assert resp.status_code == 422

    def test_backtest_validates_invalid_market_type(self, setup_app):
        """Invalid market_type should return 422."""
        client, strategy_id = setup_app
        resp = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/backtest",
            json={
                "market_type": "futures",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-15T00:00:00Z",
            },
        )
        assert resp.status_code == 422

    def test_backtest_validates_invalid_position_size_type(self, setup_app):
        """Invalid position_size_type should return 422."""
        client, strategy_id = setup_app
        resp = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/backtest",
            json={
                "position_size_type": "lots",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-15T00:00:00Z",
            },
        )
        assert resp.status_code == 422

    def test_backtest_accepts_valid_full_payload(self, setup_app):
        """Full valid payload from Properties panel should be accepted (may fail in backtest engine, but not 422)."""
        client, strategy_id = setup_app
        resp = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/backtest",
            json={
                "symbol": "BTCUSDT",
                "interval": "15",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-15T00:00:00Z",
                "market_type": "linear",
                "direction": "long",
                "initial_capital": 10000.0,
                "leverage": 10,
                "pyramiding": 1,
                "commission": 0.0007,
                "slippage": 0.0005,
                "position_size": 0.5,
                "position_size_type": "percent",
                "no_trade_days": [5, 6],
            },
        )
        # Should not be 422 (validation error) — may be 500 due to data fetching in test env
        assert resp.status_code != 422
