"""
E2E тест для Strategy Builder - полный flow (pytest версия)

Тестирует весь цикл работы Strategy Builder через pytest.
Использует тот же код, что и scripts/strategy_builder_e2e_test.py,
но адаптирован для pytest.

Запуск:
    py -3.14 -m pytest tests/e2e/test_strategy_builder_full_flow.py -v
"""

import sys
import pathlib
from datetime import datetime, timezone
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Добавить корневую директорию в путь
project_root = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.app import app
from backend.database import Base, get_db

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="class")
def client():
    """Create test client with in-memory database"""
    # Override dependency
    app.dependency_overrides[get_db] = override_get_db

    # Create tables
    Base.metadata.create_all(bind=engine)

    yield TestClient(app)

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture(scope="class")
def strategy_id_storage():
    """Storage for strategy ID between tests"""
    return {"id": None}


def override_get_db():
    """Override get_db dependency for testing"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def build_rsi_strategy() -> Dict[str, Any]:
    """Создать простую RSI стратегию для тестирования"""
    return {
        "name": "E2E Test RSI Strategy",
        "description": "RSI oversold strategy for E2E testing",
        "timeframe": "1h",
        "symbols": ["BTCUSDT"],
        "market_type": "spot",
        "direction": "long",
        "initial_capital": 10000.0,
        "blocks": [
            {
                "id": "block_price",
                "type": "price",
                "category": "input",
                "name": "Price",
                "x": 100,
                "y": 100,
                "params": {},
            },
            {
                "id": "block_rsi",
                "type": "rsi",
                "category": "indicator",
                "name": "RSI",
                "x": 300,
                "y": 100,
                "params": {"period": 14, "overbought": 70, "oversold": 30},
            },
            {
                "id": "block_const_30",
                "type": "constant",
                "category": "input",
                "name": "Constant 30",
                "x": 100,
                "y": 200,
                "params": {"value": 30},
            },
            {
                "id": "block_less_than",
                "type": "less_than",
                "category": "condition",
                "name": "Less Than",
                "x": 500,
                "y": 150,
                "params": {},
            },
            {
                "id": "main_strategy",
                "type": "strategy",
                "category": "main",
                "name": "Strategy",
                "isMain": True,
                "x": 700,
                "y": 150,
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
                "id": "conn_rsi_lt",
                "source": {"blockId": "block_rsi", "portId": "value"},
                "target": {"blockId": "block_less_than", "portId": "a"},
                "type": "data",
            },
            {
                "id": "conn_const_lt",
                "source": {"blockId": "block_const_30", "portId": "value"},
                "target": {"blockId": "block_less_than", "portId": "b"},
                "type": "data",
            },
            {
                "id": "conn_lt_entry",
                "source": {"blockId": "block_less_than", "portId": "result"},
                "target": {"blockId": "main_strategy", "portId": "entry_long"},
                "type": "data",
            },
        ],
    }


class TestStrategyBuilderE2E:
    """E2E тесты для Strategy Builder - полный flow"""

    def test_01_create_strategy(self, client, strategy_id_storage):
        """Тест 1: Создание стратегии через API"""
        strategy_data = build_rsi_strategy()

        response = client.post(
            "/api/v1/strategy-builder/strategies",
            json=strategy_data,
        )

        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}: {response.text}"
        data = response.json()

        assert "id" in data, "Ответ должен содержать id стратегии"
        assert data["name"] == strategy_data["name"], "Имя стратегии должно совпадать"
        assert data["is_builder_strategy"] == True, "is_builder_strategy должен быть True"

        # Сохранить ID для следующих тестов
        strategy_id_storage["id"] = data["id"]

    def test_02_load_strategy(self, client, strategy_id_storage):
        """Тест 2: Загрузка стратегии из БД"""
        if not strategy_id_storage["id"]:
            pytest.skip("Требуется strategy_id из предыдущего теста")

        strategy_id = strategy_id_storage["id"]
        response = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")

        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}: {response.text}"
        data = response.json()

        assert data["id"] == strategy_id, "ID стратегии должен совпадать"
        assert data["is_builder_strategy"] == True, "is_builder_strategy должен быть True"
        assert "blocks" in data, "Ответ должен содержать blocks"
        assert "connections" in data, "Ответ должен содержать connections"
        assert len(data["blocks"]) == 5, f"Ожидалось 5 блоков, получено {len(data['blocks'])}"
        assert len(data["connections"]) == 4, f"Ожидалось 4 соединения, получено {len(data['connections'])}"

    def test_03_update_strategy(self, client, strategy_id_storage):
        """Тест 3: Обновление стратегии"""
        if not strategy_id_storage["id"]:
            pytest.skip("Требуется strategy_id из предыдущего теста")

        strategy_id = strategy_id_storage["id"]
        updated_data = build_rsi_strategy()
        updated_data["name"] = "Updated E2E Test RSI Strategy"
        updated_data["description"] = "Updated description"

        response = client.put(
            f"/api/v1/strategy-builder/strategies/{strategy_id}",
            json=updated_data,
        )

        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}: {response.text}"
        data = response.json()

        assert data["name"] == updated_data["name"], "Имя должно быть обновлено"
        assert data["description"] == updated_data["description"], "Описание должно быть обновлено"

    def test_04_generate_code(self, client, strategy_id_storage):
        """Тест 4: Генерация Python кода"""
        if not strategy_id_storage["id"]:
            pytest.skip("Требуется strategy_id из предыдущего теста")

        strategy_id = strategy_id_storage["id"]
        response = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/generate-code",
            json={"template": "backtest", "include_comments": True},
        )

        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}: {response.text}"
        data = response.json()

        assert data["success"] == True, f"Генерация кода должна быть успешной: {data.get('errors')}"
        assert "code" in data, "Ответ должен содержать сгенерированный код"
        assert "strategy_name" in data, "Ответ должен содержать имя класса стратегии"
        assert len(data["code"]) > 0, "Код не должен быть пустым"

    def test_05_backtest(self, client, strategy_id_storage):
        """Тест 5: Запуск бэктеста"""
        if not strategy_id_storage["id"]:
            pytest.skip("Требуется strategy_id из предыдущего теста")

        strategy_id = strategy_id_storage["id"]
        backtest_params = {
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-31T23:59:59Z",
            "engine": "auto",
            "commission": 0.0007,
            "slippage": 0.0005,
            "leverage": 1.0,
            "pyramiding": 1,
        }

        response = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/backtest",
            json=backtest_params,
        )

        # Бэктест может использовать синтетические данные в тестовой среде
        assert response.status_code in [200, 201], f"Ожидался статус 200/201, получен {response.status_code}: {response.text}"

    def test_06_list_strategies(self, client):
        """Тест 6: Получение списка стратегий"""
        # API использует page и page_size вместо limit и offset
        response = client.get("/api/v1/strategy-builder/strategies?page=1&page_size=10")

        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}: {response.text}"
        data = response.json()

        # API возвращает "strategies" и "total"
        assert "strategies" in data or "items" in data, f"Ответ должен содержать strategies или items. Получено: {list(data.keys())}"
        assert "total" in data, f"Ответ должен содержать total. Получено: {list(data.keys())}"

    def test_07_delete_strategy(self, client, strategy_id_storage):
        """Тест 7: Удаление стратегии (soft delete)"""
        if not strategy_id_storage["id"]:
            pytest.skip("Требуется strategy_id из предыдущего теста")

        strategy_id = strategy_id_storage["id"]
        response = client.delete(f"/api/v1/strategy-builder/strategies/{strategy_id}")

        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}: {response.text}"
        data = response.json()

        assert data.get("status") == "deleted", "Статус должен быть 'deleted'"

        # Проверить, что стратегия больше не доступна
        get_response = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")
        assert get_response.status_code == 404, "Удаленная стратегия не должна быть доступна"
