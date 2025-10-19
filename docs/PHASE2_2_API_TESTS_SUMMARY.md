# Phase 2.2 - API Integration Tests Summary

## ✅ Результаты Phase 2.1 Testing

- **14/14** базовых тестов PASSED
- **12/12** pytest tests SKIPPED (awaiting BacktestEngine)
- Все зависимости установлены (asyncpg, optuna, psycopg-binary)

## ⚠️ Phase 2.2: API Integration Tests - Статус

### Задача

Создать интеграционные тесты для API endpoints:

- POST `/api/v1/optimize/walk-forward` - запуск Walk-Forward оптимизации
- POST `/api/v1/optimize/bayesian` - запуск Bayesian оптимизации
- GET `/api/v1/optimize/{task_id}/result` - получение результата оптимизации
- DELETE `/api/v1/optimize/{task_id}` - отмена задачи оптимизации

### Проблема

**TestClient импорт**: `fastapi.testclient.TestClient` имеет несовместимый API:

```python
# Ошибка: TypeError: Client.__init__() got an unexpected keyword argument 'app'
from fastapi.testclient import TestClient
client = TestClient(app)  # ❌ Не работает
```

### Причина

FastAPI использует Starlette TestClient, но версия Starlette может иметь другой API:

- Starlette 0.x: `TestClient(app)`
- Starlette 1.x: может требовать другую инициализацию

### Решение - Упрощенный подход

Вместо TestClient использовать **прямое тестирование через httpx.AsyncClient** или **создать minimal test**:

```python
import pytest
from unittest.mock import patch, Mock

# Test 1: Mock Celery task directly without FastAPI TestClient
@pytest.mark.asyncio
async def test_walk_forward_service_layer():
    """Test Walk-Forward через сервисный слой (без API)"""
    from backend.services.optimization_service import OptimizationService
    from backend.models.optimization_schemas import WalkForwardRequest

    with patch('backend.tasks.optimize_tasks.walk_forward_task.apply_async') as mock_task:
        mock_result = Mock()
        mock_result.id = "test-wf-123"
        mock_task.return_value = mock_result

        request = WalkForwardRequest(
            strategy_class="MA_Crossover",
            symbol="BTCUSDT",
            timeframe="15",
            # ... параметры
        )

        result = OptimizationService.start_walk_forward(request)

        assert result["task_id"] == "test-wf-123"
        assert result["status"] == "PENDING"
        mock_task.assert_called_once()
```

### Альтернативы

#### Option 1: httpx.AsyncClient (рекомендуется)

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_walk_forward_endpoint():
    from backend.main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/v1/optimize/walk-forward", json={...})
        assert response.status_code == 200
```

#### Option 2: Упрощенный TestClient из httpx

```python
from httpx import Client

def test_walk_forward():
    from backend.main import app

    client = Client(app=app, base_url="http://test")
    response = client.post("/api/v1/optimize/walk-forward", json={...})
    assert response.status_code == 200
```

#### Option 3: Тестировать только сервисный слой

Пропустить API layer и тестировать `OptimizationService` напрямую.

### Файл создан

✅ `tests/backend/test_api_optimization.py` (420 строк)

- 22 теста написано
- Все мокирования Celery настроены
- Fixtures готовы (`valid_walkforward_request`, `valid_bayesian_request`)
- ❌ НЕ ЗАПУСКАЕТСЯ из-за TestClient incompatibility

### Следующие шаги

1. **Выбрать подход:**

   - A) Использовать httpx.AsyncClient ✅ Recommended
   - B) Тестировать service layer напрямую (без API)
   - C) Разобраться с TestClient version issue

2. **Переписать тесты:**

   ```bash
   # Если выбран httpx.AsyncClient
   pip install httpx
   # Переписать test_api_optimization.py
   ```

3. **Запустить тесты:**
   ```bash
   pytest tests/backend/test_api_optimization.py -v
   ```

## 📝 Техническая документация

### API Endpoints (существующие)

- ✅ `/api/v1/optimize/grid` - Grid Search optimization
- ✅ `/api/v1/optimize/walk-forward` - Walk-Forward optimization
- ✅ `/api/v1/optimize/bayesian` - Bayesian optimization
- ✅ `/api/v1/optimize/{task_id}/status` - Get task status
- ✅ `/api/v1/optimize/{task_id}/result` - Get optimization result
- ✅ `/api/v1/optimize/{task_id}` - Cancel task (DELETE)

### Celery Tasks (существующие)

- `backend.tasks.optimize_tasks.grid_search_task`
- `backend.tasks.optimize_tasks.walk_forward_task`
- `backend.tasks.optimize_tasks.bayesian_task`

### Service Layer (существующий)

- `backend.services.optimization_service.OptimizationService`
  - `start_grid_search(request)`
  - `start_walk_forward(request)`
  - `start_bayesian(request)`
  - `get_task_status(task_id)`
  - `get_task_result(task_id)`
  - `cancel_task(task_id)`

## 🎯 Рекомендация

**Переключиться на httpx.AsyncClient** для API integration tests:

```python
# tests/backend/test_api_optimization_httpx.py
import pytest
from httpx import AsyncClient
from unittest.mock import patch, Mock

@pytest.fixture
async def async_client():
    from backend.main import app
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_walk_forward_endpoint(async_client):
    with patch('backend.tasks.optimize_tasks.walk_forward_task.apply_async') as mock:
        mock_result = Mock()
        mock_result.id = "test-123"
        mock.return_value = mock_result

        response = await async_client.post("/api/v1/optimize/walk-forward", json={
            "strategy_class": "MA_Crossover",
            "symbol": "BTCUSDT",
            "timeframe": "15",
            "start_date": "2024-01-01T00:00:00",
            "end_date": "2024-06-30T23:59:59",
            "initial_capital": 10000.0,
            "parameters": {
                "fast_period": {"min": 5, "max": 20, "step": 5},
                "slow_period": {"min": 20, "max": 50, "step": 10}
            },
            "in_sample_period": 90,
            "out_of_sample_period": 30,
            "step_period": 30
        })

        assert response.status_code == 202
        data = response.json()
        assert data["task_id"] == "test-123"
        assert data["status"] == "PENDING"
```

**Это решение:**

- ✅ Совместимо с FastAPI + Starlette
- ✅ Поддерживает async/await
- ✅ Нет проблем с версиями
- ✅ Полноценное тестирование HTTP layer

---

**Дата**: 17 октября 2025  
**Статус Phase 2.2**: В процессе (тесты написаны, требуется переход на httpx)  
**Следующий шаг**: Установить httpx и переписать тесты с AsyncClient
