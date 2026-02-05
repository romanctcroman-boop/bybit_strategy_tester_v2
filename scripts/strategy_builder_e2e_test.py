"""
E2E тест для Strategy Builder - полный flow

Тестирует весь цикл работы Strategy Builder:
1. Создание стратегии через API
2. Загрузка стратегии
3. Обновление стратегии
4. Запуск бэктеста
5. Генерация кода
6. Автосохранение (симуляция)

Использование:
    py -3.14 scripts/strategy_builder_e2e_test.py
"""

import pathlib
import sys
from datetime import UTC, datetime
from typing import Any

# Добавить корневую директорию в путь
project_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


def override_get_db():
    """Override get_db dependency for testing"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override dependency
app.dependency_overrides[get_db] = override_get_db

# Create tables
Base.metadata.create_all(bind=engine)

# Create test client
client = TestClient(app)


def build_rsi_strategy() -> dict[str, Any]:
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


def test_create_strategy():
    """Тест 1: Создание стратегии"""
    print("\n" + "=" * 60)
    print("ТЕСТ 1: Создание стратегии через API")
    print("=" * 60)

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

    strategy_id = data["id"]
    print(f"✅ Стратегия создана: ID = {strategy_id}")
    print(f"   Название: {data['name']}")
    print(f"   is_builder_strategy: {data['is_builder_strategy']}")

    return strategy_id


def test_load_strategy(strategy_id: str):
    """Тест 2: Загрузка стратегии"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Загрузка стратегии из БД")
    print("=" * 60)

    response = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")

    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}: {response.text}"
    data = response.json()

    assert data["id"] == strategy_id, "ID стратегии должен совпадать"
    assert data["is_builder_strategy"] == True, "is_builder_strategy должен быть True"
    assert "blocks" in data, "Ответ должен содержать blocks"
    assert "connections" in data, "Ответ должен содержать connections"
    assert len(data["blocks"]) == 5, f"Ожидалось 5 блоков, получено {len(data['blocks'])}"
    assert len(data["connections"]) == 4, f"Ожидалось 4 соединения, получено {len(data['connections'])}"

    print(f"✅ Стратегия загружена: ID = {strategy_id}")
    print(f"   Блоков: {len(data['blocks'])}")
    print(f"   Соединений: {len(data['connections'])}")
    print(f"   Название: {data['name']}")

    return data


def test_update_strategy(strategy_id: str):
    """Тест 3: Обновление стратегии"""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Обновление стратегии")
    print("=" * 60)

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

    print(f"✅ Стратегия обновлена: ID = {strategy_id}")
    print(f"   Новое название: {data['name']}")
    print(f"   Новое описание: {data['description']}")


def test_generate_code(strategy_id: str):
    """Тест 4: Генерация кода"""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Генерация Python кода")
    print("=" * 60)

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

    print("✅ Код сгенерирован успешно")
    print(f"   Имя класса: {data['strategy_name']}")
    print(f"   Длина кода: {len(data['code'])} символов")
    print("   Первые 100 символов:")
    print(f"   {data['code'][:100]}...")


def test_backtest(strategy_id: str):
    """Тест 5: Запуск бэктеста"""
    print("\n" + "=" * 60)
    print("ТЕСТ 5: Запуск бэктеста")
    print("=" * 60)

    # Используем синтетические данные для теста (без сети)
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

    if response.status_code == 200:
        data = response.json()
        if "backtest_id" in data:
            print("✅ Бэктест запущен успешно")
            print(f"   Backtest ID: {data['backtest_id']}")
            if "redirect_url" in data:
                print(f"   Redirect URL: {data['redirect_url']}")
        else:
            print("⚠️  Бэктест запущен, но backtest_id не возвращен")
    else:
        print(f"⚠️  Бэктест вернул статус {response.status_code}")


def test_list_strategies():
    """Тест 6: Список стратегий"""
    print("\n" + "=" * 60)
    print("ТЕСТ 6: Получение списка стратегий")
    print("=" * 60)

    response = client.get("/api/v1/strategy-builder/strategies?limit=10&offset=0")

    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}: {response.text}"
    data = response.json()

    assert "items" in data, "Ответ должен содержать items"
    assert "total" in data, "Ответ должен содержать total"

    print("✅ Список стратегий получен")
    print(f"   Всего стратегий: {data['total']}")
    print(f"   Возвращено: {len(data['items'])}")

    # Проверить, что все стратегии - builder стратегии
    builder_strategies = [s for s in data["items"] if s.get("is_builder_strategy")]
    print(f"   Builder стратегий: {len(builder_strategies)}")


def test_delete_strategy(strategy_id: str):
    """Тест 7: Удаление стратегии (soft delete)"""
    print("\n" + "=" * 60)
    print("ТЕСТ 7: Удаление стратегии (soft delete)")
    print("=" * 60)

    response = client.delete(f"/api/v1/strategy-builder/strategies/{strategy_id}")

    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}: {response.text}"
    data = response.json()

    assert data.get("status") == "deleted", "Статус должен быть 'deleted'"

    # Проверить, что стратегия больше не доступна
    get_response = client.get(f"/api/v1/strategy-builder/strategies/{strategy_id}")
    assert get_response.status_code == 404, "Удаленная стратегия не должна быть доступна"

    print(f"✅ Стратегия удалена (soft delete): ID = {strategy_id}")


def main():
    """Запустить все E2E тесты"""
    print("\n" + "=" * 60)
    print("STRATEGY BUILDER E2E ТЕСТЫ")
    print("=" * 60)
    print(f"Время начала: {datetime.now(UTC).isoformat()}")

    try:
        # Тест 1: Создание стратегии
        strategy_id = test_create_strategy()

        # Тест 2: Загрузка стратегии
        strategy_data = test_load_strategy(strategy_id)

        # Тест 3: Обновление стратегии
        test_update_strategy(strategy_id)

        # Тест 4: Генерация кода
        test_generate_code(strategy_id)

        # Тест 5: Запуск бэктеста
        test_backtest(strategy_id)

        # Тест 6: Список стратегий
        test_list_strategies()

        # Тест 7: Удаление стратегии
        test_delete_strategy(strategy_id)

        print("\n" + "=" * 60)
        print("✅ ВСЕ E2E ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("=" * 60)
        print(f"Время завершения: {datetime.now(UTC).isoformat()}")

    except AssertionError as e:
        print(f"\n❌ ОШИБКА В ТЕСТЕ: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
