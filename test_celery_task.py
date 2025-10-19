"""
Тест выполнения Celery задачи debug_task

Запускает задачу и проверяет результат.
"""

from loguru import logger
from backend.celery_app import debug_task

logger.info("=== ТЕСТ CELERY ЗАДАЧИ ===")
logger.info("")

# 1. Отправка задачи в очередь
logger.info("[1/4] Отправляем задачу в очередь...")
result = debug_task.delay()
logger.success(f"✅ Задача отправлена: task_id={result.id}")
logger.info(f"   Статус: {result.state}")
logger.info("")

# 2. Ожидание выполнения
logger.info("[2/4] Ожидаем выполнения (timeout 10 секунд)...")
try:
    task_result = result.get(timeout=10)
    logger.success("✅ Задача выполнена успешно!")
    logger.info("")
    
    # 3. Проверка результата
    logger.info("[3/4] Проверяем результат...")
    logger.info(f"   Результат: {task_result}")
    logger.info(f"   Статус: {result.state}")
    logger.info(f"   Успешно: {result.successful()}")
    logger.info("")
    
    # 4. Проверка метаданных
    logger.info("[4/4] Метаданные задачи...")
    logger.info(f"   Task ID: {result.id}")
    logger.info(f"   Backend: {result.backend}")
    logger.info("")
    
    logger.success("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    
except Exception as e:
    logger.error(f"❌ ОШИБКА: {e}")
    logger.error(f"   Статус: {result.state}")
    if result.state == 'PENDING':
        logger.warning("   Задача не выполнена - возможно, worker не запущен или не слушает правильную очередь")
    elif result.state == 'FAILURE':
        logger.error(f"   Traceback: {result.traceback}")
