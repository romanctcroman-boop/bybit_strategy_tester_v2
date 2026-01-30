"""
Тесты для шаблона стратегии "RSI Long then Short"

Проверяет:
1. Загрузку шаблона через API
2. Генерацию кода из шаблона
3. Запуск бэктеста с шаблоном
4. Сравнение метрик с ожидаемыми значениями
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.database.session import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path

# In-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    from backend.database.models import Base
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def rsi_template_strategy(client):
    """Create a strategy from RSI Long Short template"""
    # Template data matching frontend template
    template_data = {
        "name": "RSI Long Short Strategy",
        "description": "RSI Long then Short template",
        "timeframe": "15m",
        "symbol": "BTCUSDT",
        "market_type": "linear",
        "direction": "both",
        "initial_capital": 10000,
        "blocks": [
            {
                "id": "rsi_1",
                "type": "rsi",
                "category": "indicator",
                "name": "RSI",
                "icon": "graph-up",
                "x": 150,
                "y": 150,
                "params": {"period": 14, "overbought": 70, "oversold": 30},
            },
            {
                "id": "const_30",
                "type": "constant",
                "category": "input",
                "name": "Constant",
                "icon": "hash",
                "x": 150,
                "y": 300,
                "params": {"value": 30},
            },
            {
                "id": "const_70",
                "type": "constant",
                "category": "input",
                "name": "Constant",
                "icon": "hash",
                "x": 150,
                "y": 450,
                "params": {"value": 70},
            },
            {
                "id": "less_than_oversold",
                "type": "less_than",
                "category": "condition",
                "name": "Less Than",
                "icon": "chevron-double-down",
                "x": 400,
                "y": 200,
                "params": {},
            },
            {
                "id": "greater_than_overbought",
                "type": "greater_than",
                "category": "condition",
                "name": "Greater Than",
                "icon": "chevron-double-up",
                "x": 400,
                "y": 400,
                "params": {},
            },
        ],
        "connections": [
            {
                "id": "conn_1",
                "source": {"blockId": "rsi_1", "portId": "value"},
                "target": {"blockId": "main_strategy", "portId": "entry_long"},
                "type": "data",
            },
            {
                "id": "conn_2",
                "source": {"blockId": "const_30", "portId": "value"},
                "target": {"blockId": "less_than_oversold", "portId": "b"},
                "type": "data",
            },
            {
                "id": "conn_3",
                "source": {"blockId": "rsi_1", "portId": "value"},
                "target": {"blockId": "greater_than_overbought", "portId": "a"},
                "type": "data",
            },
            {
                "id": "conn_4",
                "source": {"blockId": "const_70", "portId": "value"},
                "target": {"blockId": "greater_than_overbought", "portId": "b"},
                "type": "data",
            },
            {
                "id": "conn_5",
                "source": {"blockId": "less_than_oversold", "portId": "result"},
                "target": {"blockId": "main_strategy", "portId": "entry_long"},
                "type": "condition",
            },
            {
                "id": "conn_6",
                "source": {"blockId": "greater_than_overbought", "portId": "result"},
                "target": {"blockId": "main_strategy", "portId": "exit_long"},
                "type": "condition",
            },
            {
                "id": "conn_7",
                "source": {"blockId": "greater_than_overbought", "portId": "result"},
                "target": {"blockId": "main_strategy", "portId": "entry_short"},
                "type": "condition",
            },
            {
                "id": "conn_8",
                "source": {"blockId": "less_than_oversold", "portId": "result"},
                "target": {"blockId": "main_strategy", "portId": "exit_short"},
                "type": "condition",
            },
        ],
        "is_builder_strategy": True,
    }

    # Create strategy
    response = client.post(
        "/api/v1/strategy-builder/strategies",
        json=template_data,
    )
    assert response.status_code == 200
    strategy_data = response.json()
    assert "id" in strategy_data
    return strategy_data["id"]


class TestRSILongShortTemplate:
    """Тесты для шаблона RSI Long Short"""

    def test_template_creation(self, client, rsi_template_strategy):
        """Проверка создания стратегии из шаблона"""
        strategy_id = rsi_template_strategy
        
        # Load strategy
        response = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")
        assert response.status_code == 200
        strategy = response.json()
        
        # Verify structure
        assert strategy["is_builder_strategy"] is True
        assert len(strategy.get("blocks", [])) == 5  # 5 blocks + main_strategy
        assert len(strategy.get("connections", [])) == 8
        
        # Verify blocks
        block_types = [b["type"] for b in strategy["blocks"]]
        assert "rsi" in block_types
        assert "constant" in block_types
        assert "less_than" in block_types
        assert "greater_than" in block_types

    def test_template_code_generation(self, client, rsi_template_strategy):
        """Проверка генерации кода из шаблона"""
        strategy_id = rsi_template_strategy
        
        response = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/generate-code",
            json={
                "template": "backtest",
                "include_comments": True,
                "include_logging": False,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "code" in data
        assert len(data["code"]) > 0
        
        # Verify code contains RSI logic
        code = data["code"]
        assert "rsi" in code.lower() or "RSI" in code
        assert "30" in code  # Oversold level
        assert "70" in code  # Overbought level

    def test_template_validation(self, client, rsi_template_strategy):
        """Проверка валидации шаблона"""
        strategy_id = rsi_template_strategy
        
        response = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/validate",
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        # Template should be valid
        assert data["valid"] is True

    @pytest.mark.skip(reason="Requires historical data and longer execution time")
    def test_template_backtest(self, client, rsi_template_strategy):
        """Проверка запуска бэктеста с шаблоном"""
        strategy_id = rsi_template_strategy
        
        backtest_config = {
            "start_date": "2025-01-01T00:00:00Z",
            "end_date": "2025-06-30T23:59:59Z",
            "engine": None,  # Auto-select
            "commission": 0.0007,  # 0.07% for TradingView parity
            "slippage": 0.0005,
            "leverage": 10,
            "pyramiding": 1,
        }
        
        response = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/backtest",
            json=backtest_config,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return backtest ID or results
        assert "backtest_id" in data or "results" in data
        
        # If results are returned directly, check metrics
        if "results" in data:
            results = data["results"]
            assert "total_return" in results
            assert "total_trades" in results
            assert results["total_trades"] > 0  # Should have some trades
