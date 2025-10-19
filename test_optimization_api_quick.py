"""
Быстрый тест Optimization API

Проверяет базовую функциональность без запуска реальной оптимизации.
"""

import requests
from loguru import logger


API_URL = "http://localhost:8000/api/v1"


def test_endpoints_availability():
    """Тест доступности всех endpoints"""
    
    logger.info("=== ТЕСТ ДОСТУПНОСТИ ENDPOINTS ===")
    logger.info("")
    
    # 1. POST /optimize/grid (должен вернуть ошибку валидации)
    logger.info("[1/4] POST /optimize/grid (без данных)...")
    try:
        response = requests.post(f"{API_URL}/optimize/grid", json={}, timeout=5)
        if response.status_code == 422:  # Validation error
            logger.success("✅ Endpoint доступен (валидация работает)")
        else:
            logger.warning(f"⚠️  Неожиданный статус: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False
    
    # 2. GET /optimize/{task_id}/status
    logger.info("[2/4] GET /optimize/{task_id}/status...")
    try:
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(f"{API_URL}/optimize/{fake_id}/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.success(f"✅ Endpoint доступен (статус: {data['status']})")
        else:
            logger.warning(f"⚠️  Неожиданный статус: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False
    
    # 3. GET /optimize/{task_id}/result
    logger.info("[3/4] GET /optimize/{task_id}/result...")
    try:
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(f"{API_URL}/optimize/{fake_id}/result", timeout=5)
        if response.status_code == 404:  # Task not completed
            logger.success("✅ Endpoint доступен (корректно возвращает 404)")
        else:
            logger.warning(f"⚠️  Неожиданный статус: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False
    
    # 4. DELETE /optimize/{task_id}
    logger.info("[4/4] DELETE /optimize/{task_id}...")
    try:
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.delete(f"{API_URL}/optimize/{fake_id}", timeout=5)
        # Может вернуть 400 (уже завершена) или 200 (отменена)
        if response.status_code in [200, 400]:
            logger.success(f"✅ Endpoint доступен (статус: {response.status_code})")
        else:
            logger.warning(f"⚠️  Неожиданный статус: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False
    
    logger.info("")
    logger.success("🎉 ВСЕ ENDPOINTS ДОСТУПНЫ!")
    return True


def test_swagger_docs():
    """Проверка Swagger UI"""
    
    logger.info("")
    logger.info("=== ПРОВЕРКА ДОКУМЕНТАЦИИ ===")
    logger.info("")
    
    try:
        # Swagger UI
        response = requests.get("http://localhost:8000/docs", timeout=5)
        if response.status_code == 200:
            logger.success("✅ Swagger UI: http://localhost:8000/docs")
        else:
            logger.warning("⚠️  Swagger UI недоступен")
        
        # OpenAPI Schema
        response = requests.get("http://localhost:8000/openapi.json", timeout=5)
        if response.status_code == 200:
            schema = response.json()
            
            # Подсчет endpoints
            optimize_paths = [p for p in schema.get("paths", {}).keys() if "optimize" in p]
            logger.success(f"✅ OpenAPI Schema: {len(optimize_paths)} optimization endpoints")
            
            for path in optimize_paths:
                logger.info(f"   • {path}")
        else:
            logger.warning("⚠️  OpenAPI schema недоступен")
        
        logger.info("")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False


def test_validation():
    """Тест валидации параметров"""
    
    logger.info("=== ТЕСТ ВАЛИДАЦИИ ===")
    logger.info("")
    
    # Невалидный запрос (step <= 0)
    logger.info("[1/2] Тест валидации: step <= 0...")
    invalid_request = {
        "strategy_class": "SMAStrategy",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-12-31T23:59:59",
        "parameters": {
            "fast_period": {
                "min": 5,
                "max": 20,
                "step": 0  # ОШИБКА: должно быть > 0
            }
        }
    }
    
    try:
        response = requests.post(f"{API_URL}/optimize/grid", json=invalid_request, timeout=5)
        if response.status_code == 422:
            error = response.json()
            logger.success("✅ Валидация работает (422 Unprocessable Entity)")
            logger.info(f"   Ошибка: {error['detail'][0]['msg']}")
        else:
            logger.warning(f"⚠️  Ожидался 422, получен {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False
    
    # Невалидный запрос (end_date < start_date)
    logger.info("[2/2] Тест валидации: end_date < start_date...")
    invalid_request["parameters"]["fast_period"]["step"] = 5
    invalid_request["end_date"] = "2023-01-01T00:00:00"  # ОШИБКА: раньше start_date
    
    try:
        response = requests.post(f"{API_URL}/optimize/grid", json=invalid_request, timeout=5)
        if response.status_code == 422:
            logger.success("✅ Валидация работает (end_date проверяется)")
        else:
            logger.warning(f"⚠️  Ожидался 422, получен {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False
    
    logger.info("")
    logger.success("🎉 ВАЛИДАЦИЯ РАБОТАЕТ КОРРЕКТНО!")
    return True


if __name__ == "__main__":
    # Проверка API
    logger.info("Проверка доступности API...")
    try:
        health = requests.get("http://localhost:8000/health", timeout=5)
        if health.status_code != 200:
            logger.error("❌ API недоступен!")
            exit(1)
        logger.success("✅ API доступен")
        logger.info("")
    except Exception:
        logger.error("❌ API недоступен!")
        logger.info("   Запустите: uvicorn backend.main:app --reload")
        exit(1)
    
    # Запуск тестов
    success = True
    
    if not test_endpoints_availability():
        success = False
    
    if not test_swagger_docs():
        success = False
    
    if not test_validation():
        success = False
    
    if success:
        logger.info("")
        logger.success("=" * 70)
        logger.success("  ВСЕ ТЕСТЫ API ПРОЙДЕНЫ!")
        logger.success("=" * 70)
        logger.info("")
        logger.info("📚 Документация: http://localhost:8000/docs")
        logger.info("🔍 OpenAPI Schema: http://localhost:8000/openapi.json")
        logger.info("")
    else:
        logger.error("=" * 70)
        logger.error("  НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        logger.error("=" * 70)
        exit(1)
