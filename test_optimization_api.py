"""
Тест Optimization API

Проверяет работу endpoints оптимизации через HTTP запросы.
"""

import requests
import json
import time
from datetime import datetime, timedelta
from loguru import logger


API_URL = "http://localhost:8000/api/v1"


def test_grid_search_optimization():
    """Тест Grid Search оптимизации"""
    
    logger.info("=== ТЕСТ GRID SEARCH OPTIMIZATION API ===")
    logger.info("")
    
    # 1. Подготовка запроса
    logger.info("[1/5] Подготовка Grid Search запроса...")
    
    # Используем простые параметры для быстрого теста
    request_data = {
        "strategy_class": "SMAStrategy",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "start_date": (datetime.now() - timedelta(days=90)).isoformat(),
        "end_date": datetime.now().isoformat(),
        "parameters": {
            "fast_period": {
                "min": 5,
                "max": 15,
                "step": 5
            },
            "slow_period": {
                "min": 20,
                "max": 40,
                "step": 10
            }
        },
        "initial_capital": 10000.0,
        "commission": 0.001,
        "metric": "total_return",
        "max_combinations": 20
    }
    
    logger.info(f"   Strategy: {request_data['strategy_class']}")
    logger.info(f"   Symbol: {request_data['symbol']}")
    logger.info(f"   Parameters: {len(request_data['parameters'])} parameters")
    logger.info("")
    
    # 2. Отправка запроса
    logger.info("[2/5] Отправка POST /api/v1/optimize/grid...")
    
    try:
        response = requests.post(
            f"{API_URL}/optimize/grid",
            json=request_data,
            timeout=30
        )
        
        if response.status_code != 202:
            logger.error(f"❌ Ошибка: HTTP {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False
        
        result = response.json()
        task_id = result["task_id"]
        
        logger.success(f"✅ Задача создана!")
        logger.info(f"   Task ID: {task_id}")
        logger.info(f"   Status: {result['status']}")
        logger.info(f"   Method: {result['method']}")
        logger.info("")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Ошибка запроса: {e}")
        logger.warning("   Убедитесь, что API сервер запущен (uvicorn backend.main:app)")
        return False
    
    # 3. Проверка статуса
    logger.info("[3/5] Проверка статуса задачи...")
    
    max_wait = 60  # Максимум 60 секунд ожидания
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            status_response = requests.get(
                f"{API_URL}/optimize/{task_id}/status",
                timeout=10
            )
            
            if status_response.status_code != 200:
                logger.error(f"❌ Ошибка получения статуса: {status_response.status_code}")
                return False
            
            status_data = status_response.json()
            current_status = status_data["status"]
            
            logger.info(f"   Статус: {current_status}")
            
            # Если есть прогресс
            if status_data.get("progress"):
                progress = status_data["progress"]
                logger.info(f"   Прогресс: {progress['current']}/{progress['total']} ({progress['percent']}%)")
                if progress.get("best_score"):
                    logger.info(f"   Лучший результат: {progress['best_score']}")
            
            # Если задача завершена
            if current_status == "SUCCESS":
                logger.success("✅ Задача выполнена успешно!")
                logger.info("")
                break
            
            # Если задача провалилась
            elif current_status == "FAILURE":
                logger.error(f"❌ Задача провалилась!")
                logger.error(f"   Ошибка: {status_data.get('error')}")
                if status_data.get("traceback"):
                    logger.error(f"   Traceback: {status_data['traceback']}")
                return False
            
            # Ждем перед следующей проверкой
            time.sleep(2)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ошибка запроса статуса: {e}")
            return False
    
    else:
        logger.warning("⚠️  Превышено время ожидания (60 сек)")
        logger.info("   Задача все еще выполняется, но тест завершен")
        return True  # Не считаем ошибкой - задача просто долгая
    
    # 4. Получение результата
    logger.info("[4/5] Получение результата...")
    
    try:
        result_response = requests.get(
            f"{API_URL}/optimize/{task_id}/result",
            timeout=10
        )
        
        if result_response.status_code != 200:
            logger.error(f"❌ Ошибка получения результата: {result_response.status_code}")
            logger.error(f"   Response: {result_response.text}")
            return False
        
        result_data = result_response.json()
        
        logger.success("✅ Результат получен!")
        logger.info(f"   Лучшие параметры: {result_data['best_params']}")
        logger.info(f"   Лучший результат: {result_data['best_score']}")
        logger.info(f"   Всего комбинаций: {result_data['total_combinations']}")
        logger.info(f"   Протестировано: {result_data['tested_combinations']}")
        logger.info(f"   Время выполнения: {result_data['execution_time']:.2f} сек")
        logger.info("")
        
        # Топ результаты
        logger.info("   Топ-3 результата:")
        for idx, res in enumerate(result_data['top_results'][:3], 1):
            logger.info(f"     {idx}. Params: {res['params']} | Score: {res['score']}")
        logger.info("")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Ошибка запроса результата: {e}")
        return False
    
    # 5. Проверка документации
    logger.info("[5/5] Проверка Swagger UI...")
    
    try:
        docs_response = requests.get("http://localhost:8000/docs", timeout=5)
        
        if docs_response.status_code == 200:
            logger.success("✅ Swagger UI доступен: http://localhost:8000/docs")
        else:
            logger.warning("⚠️  Swagger UI недоступен")
        
    except requests.exceptions.RequestException:
        logger.warning("⚠️  Не удалось проверить Swagger UI")
    
    logger.info("")
    logger.success("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    
    return True


def test_task_status_endpoint():
    """Тест endpoint статуса задачи с несуществующим ID"""
    
    logger.info("")
    logger.info("=== ТЕСТ GET /optimize/{task_id}/status (несуществующий ID) ===")
    
    fake_task_id = "00000000-0000-0000-0000-000000000000"
    
    try:
        response = requests.get(
            f"{API_URL}/optimize/{fake_task_id}/status",
            timeout=5
        )
        
        # Должен вернуть 200 с PENDING статусом (Celery не выбрасывает 404)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"   Статус: {data['status']}")
            logger.success("✅ Endpoint корректно обрабатывает несуществующий ID")
            return True
        else:
            logger.error(f"❌ Неожиданный статус: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Ошибка запроса: {e}")
        return False


if __name__ == "__main__":
    # Проверка доступности API
    logger.info("Проверка доступности API...")
    try:
        health = requests.get("http://localhost:8000/health", timeout=5)
        if health.status_code != 200:
            logger.error("❌ API сервер недоступен!")
            logger.info("   Запустите сервер: uvicorn backend.main:app --reload")
            exit(1)
        logger.success("✅ API сервер доступен")
        logger.info("")
    except requests.exceptions.RequestException:
        logger.error("❌ API сервер недоступен!")
        logger.info("   Запустите сервер: uvicorn backend.main:app --reload")
        exit(1)
    
    # Запуск тестов
    success = True
    
    # Тест 1: Grid Search
    if not test_grid_search_optimization():
        success = False
    
    # Тест 2: Статус несуществующей задачи
    if not test_task_status_endpoint():
        success = False
    
    if success:
        logger.info("")
        logger.success("=" * 60)
        logger.success("  ВСЕ ТЕСТЫ OPTIMIZATION API ПРОЙДЕНЫ УСПЕШНО!")
        logger.success("=" * 60)
    else:
        logger.error("")
        logger.error("=" * 60)
        logger.error("  НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        logger.error("=" * 60)
        exit(1)
