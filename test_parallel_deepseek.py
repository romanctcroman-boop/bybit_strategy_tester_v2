"""
Демонстрация ускорения параллельной обработки DeepSeek

Сравнивает производительность:
1. Последовательная обработка (1 API ключ)
2. Параллельная обработка (4 API ключа)

Ожидаемое ускорение: 20-30x
"""

import asyncio
import time
import os
import sys
from pathlib import Path

# Добавляем пути
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "automation" / "task2_key_manager"))
sys.path.insert(0, str(project_root))

from key_manager import KeyManager
from backend.api.parallel_deepseek_client import (
    ParallelDeepSeekClient,
    DeepSeekTask,
    TaskPriority
)


async def sequential_processing(tasks, api_key):
    """Последовательная обработка с одним ключом"""
    print("\n" + "="*80)
    print("  SEQUENTIAL PROCESSING (1 API key)")
    print("="*80)
    
    client = ParallelDeepSeekClient(
        api_keys=[api_key],
        max_concurrent=1,  # Только 1 запрос одновременно
        enable_cache=False  # Отключаем кэш для честного сравнения
    )
    
    start_time = time.time()
    results = await client.process_batch(tasks, show_progress=True)
    total_time = time.time() - start_time
    
    stats = client.get_statistics()
    
    print(f"\n📊 Results:")
    print(f"   ⏱️  Total Time: {total_time:.2f}s")
    print(f"   ✅ Success Rate: {stats['success_rate']}")
    print(f"   🎯 Throughput: {len(tasks) / total_time:.2f} tasks/sec")
    
    return total_time, stats


async def parallel_processing(tasks, api_keys):
    """Параллельная обработка с несколькими ключами"""
    print("\n" + "="*80)
    print(f"  PARALLEL PROCESSING ({len(api_keys)} API keys)")
    print("="*80)
    
    client = ParallelDeepSeekClient(
        api_keys=api_keys,
        max_concurrent=min(10, len(api_keys) * 3),
        enable_cache=False  # Отключаем кэш для честного сравнения
    )
    
    start_time = time.time()
    results = await client.process_batch(tasks, show_progress=True)
    total_time = time.time() - start_time
    
    stats = client.get_statistics()
    
    print(f"\n📊 Results:")
    print(f"   ⏱️  Total Time: {total_time:.2f}s")
    print(f"   ✅ Success Rate: {stats['success_rate']}")
    print(f"   🎯 Throughput: {len(tasks) / total_time:.2f} tasks/sec")
    
    return total_time, stats


async def main():
    """Main demo"""
    print("\n" + "="*80)
    print("  DEEPSEEK PARALLEL PROCESSING DEMO")
    print("="*80)
    print()
    
    # Инициализация KeyManager
    key_manager = KeyManager()
    encryption_key = os.getenv("ENCRYPTION_KEY")
    
    if not encryption_key:
        print("❌ ENCRYPTION_KEY не найден в .env!")
        print("   Запустите: python auto_encrypt_keys.py")
        return
    
    if not key_manager.initialize_encryption(encryption_key):
        print("❌ Ошибка инициализации шифрования!")
        return
    
    secrets_file = Path("encrypted_secrets.json")
    if not key_manager.load_keys(str(secrets_file)):
        print("❌ Ошибка загрузки ключей!")
        return
    
    # Получаем ВСЕ DeepSeek ключи
    api_keys = key_manager.get_all_keys("DEEPSEEK_API_KEY")
    
    if not api_keys:
        print("❌ DeepSeek API ключи не найдены!")
        print("   Запустите: python add_deepseek_keys.py")
        return
    
    print(f"✅ Загружено {len(api_keys)} DeepSeek API ключей")
    print()
    
    # Создаем тестовые задачи
    print("📝 Создание тестовых задач...")
    tasks = []
    
    for i in range(20):  # 20 задач для демонстрации
        tasks.append(DeepSeekTask(
            task_id=f"task_{i+1}",
            prompt=f"""
Analyze this Python code snippet and provide a brief review:

```python
def calculate_moving_average(data: list[float], period: int) -> list[float]:
    '''Calculate simple moving average'''
    result = []
    for i in range(len(data) - period + 1):
        window = data[i:i + period]
        avg = sum(window) / period
        result.append(avg)
    return result
```

Provide a 2-3 sentence code review focusing on:
1. Code quality
2. Performance considerations
3. Potential improvements
""",
            temperature=0.3,
            max_tokens=500,
            priority=TaskPriority.MEDIUM
        ))
    
    print(f"   Создано {len(tasks)} задач")
    print()
    
    # Тест 1: Последовательная обработка (1 ключ)
    seq_time, seq_stats = await sequential_processing(tasks, api_keys[0])
    
    # Тест 2: Параллельная обработка (все ключи)
    par_time, par_stats = await parallel_processing(tasks, api_keys)
    
    # Сравнение результатов
    print("\n" + "="*80)
    print("  COMPARISON RESULTS")
    print("="*80)
    print()
    
    speedup = seq_time / par_time if par_time > 0 else 0
    
    print(f"📊 Sequential Processing:")
    print(f"   ⏱️  Time: {seq_time:.2f}s")
    print(f"   🔑 API Keys: 1")
    print(f"   🎯 Throughput: {len(tasks) / seq_time:.2f} tasks/sec")
    print()
    
    print(f"⚡ Parallel Processing:")
    print(f"   ⏱️  Time: {par_time:.2f}s")
    print(f"   🔑 API Keys: {len(api_keys)}")
    print(f"   🎯 Throughput: {len(tasks) / par_time:.2f} tasks/sec")
    print()
    
    print(f"🚀 SPEEDUP: {speedup:.1f}x faster")
    print(f"⏱️  Time Saved: {seq_time - par_time:.2f}s ({((seq_time - par_time) / seq_time * 100):.1f}%)")
    print()
    
    print(f"{'='*80}")
    print()
    
    # Рекомендации
    print("💡 Recommendations:")
    print()
    if speedup < 5:
        print("   ⚠️  Speedup ниже ожидаемого. Возможные причины:")
        print("      - Ограничение скорости интернет-соединения")
        print("      - Rate limits от DeepSeek API")
        print("      - Малое количество задач для демонстрации")
    elif speedup < 15:
        print("   ✅ Хорошее ускорение! Параллельная обработка работает.")
        print("      Для ещё большего ускорения:")
        print("      - Увеличьте количество задач")
        print("      - Добавьте больше API ключей")
    else:
        print("   🎉 Отличное ускорение! Параллельная обработка очень эффективна.")
        print("      Можно использовать в production для:")
        print("      - Валидации тестов (Test Watcher)")
        print("      - Генерации стратегий")
        print("      - Массового анализа кода")
    
    print()
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
