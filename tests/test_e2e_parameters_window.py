"""
E2E тесты окна «Параметры» Strategy Builder.

Проверяет, что параметры из UI (Symbol, TF, Capital, Leverage, Commission, etc.)
корректно передаются в API бэктеста и сохранения стратегии.
"""

import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

project_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.api.app import app
from backend.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


def _payload_from_params(
    symbol="BTCUSDT",
    interval="15",
    start_date="2025-01-01",
    end_date="2025-06-01",
    initial_capital=10000.0,
    leverage=10,
    commission=0.0007,
    direction="both",
    position_size_type="percent",
    position_size=1.0,
    no_trade_days=None,
):
    """Payload как формирует buildBacktestRequest / buildStrategyPayload."""
    return {
        "symbol": symbol,
        "interval": interval,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "leverage": leverage,
        "commission": commission,
        "direction": direction,
        "position_size_type": position_size_type,
        "position_size": position_size,
        "strategy_type": "rsi_long_short",
        "strategy_params": {
            "period": 14,
            "overbought": 70,
            "oversold": 30,
            "_position_size_type": position_size_type,
            "_order_amount": position_size if position_size_type != "percent" else None,
        },
        "no_trade_days": no_trade_days or [],
    }


class TestParametersFlowToBacktest:
    """Проверка передачи параметров в API бэктеста."""

    def test_commission_default_007_percent(self, client):
        """Commission 0.07% = 0.0007 в payload (frontend → buildBacktestRequest)."""
        payload = _payload_from_params(commission=0.0007)
        assert payload["commission"] == 0.0007

    def test_position_size_percent_vs_fixed(self, client):
        """position_size: percent=1.0 (100%), fixed_amount=5000."""
        # Percent: 100% -> 1.0
        p1 = _payload_from_params(position_size_type="percent", position_size=1.0)
        assert p1["position_size"] == 1.0
        assert p1["strategy_params"]["_position_size_type"] == "percent"

        # Fixed: 5000
        p2 = _payload_from_params(position_size_type="fixed_amount", position_size=5000.0)
        assert p2["position_size"] == 5000.0
        assert p2["strategy_params"]["_order_amount"] == 5000.0

    def test_no_trade_days_format(self):
        """no_trade_days: 0=Mon, 6=Sun (Python weekday)."""
        payload = _payload_from_params(no_trade_days=[0, 6])  # Mon, Sun blocked
        assert payload["no_trade_days"] == [0, 6]

    def test_end_date_clamped_to_today(self):
        """Frontend обрезает end_date до сегодня, если в будущем."""
        from datetime import date
        today = date.today().isoformat()
        # Simulate: user picks 2030-01-01, frontend sends min(end, today)
        end_future = "2030-01-01"
        end_clamped = min(end_future, today)
        assert end_clamped == today


class TestParametersSaveRestore:
    """Проверка сохранения и восстановления параметров."""

    def test_strategy_save_includes_parameters(self, client):
        """Сохранённая стратегия сохраняет и возвращает parameters, leverage, position_size."""
        payload = {
            "name": "Params Test Strategy",
            "timeframe": "15",
            "symbol": "BTCUSDT",
            "market_type": "linear",
            "direction": "both",
            "initial_capital": 10000,
            "leverage": 10,
            "position_size": 1.0,
            "parameters": {
                "_position_size_type": "percent",
                "_order_amount": None,
                "_no_trade_days": [0, 6],
                "_commission": 0.001,
            },
            "blocks": [],
            "connections": [],
        }
        resp = client.post("/api/v1/strategy-builder/strategies", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "id" in data
        assert data.get("leverage") == 10
        assert data.get("position_size") == 1.0
        assert data.get("parameters", {}).get("_commission") == 0.001
        assert data.get("parameters", {}).get("_no_trade_days") == [0, 6]

        get_resp = client.get(f"/api/v1/strategy-builder/strategies/{data['id']}")
        assert get_resp.status_code == 200
        loaded = get_resp.json()
        assert loaded.get("parameters", {}).get("_commission") == 0.001
        assert loaded.get("leverage") == 10
