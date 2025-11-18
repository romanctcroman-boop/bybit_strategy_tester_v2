"""
ПРЯМОЙ вопрос к DeepSeek API (не через Perplexity MCP)
Используем ParallelDeepSeekClientV2 напрямую для получения текстового ответа
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.api.parallel_deepseek_client_v2 import (
    ParallelDeepSeekClientV2,
    DeepSeekTask,
    TaskPriority
)
from backend.security.key_manager import get_key_manager
from dotenv import load_dotenv

load_dotenv()


async def ask_deepseek_directly():
    """Прямой вопрос к DeepSeek Chat API"""
    
    print("=" * 80)
    print("ПРЯМОЙ ЗАПРОС К DEEPSEEK CHAT API (без Perplexity)")
    print("=" * 80)
    print()
    
    # Загружаем ключи
    key_manager = get_key_manager()
    api_keys = []
    
    # Загружаем все 4 DeepSeek ключа
    try:
        api_keys.append(key_manager.get_decrypted_key("DEEPSEEK_API_KEY"))
    except:
        pass
    
    for i in range(2, 10):
        try:
            api_keys.append(key_manager.get_decrypted_key(f"DEEPSEEK_API_KEY_{i}"))
        except:
            break
    
    print(f"✅ Загружено {len(api_keys)} DeepSeek API ключей")
    print()
    
    # Создаем клиент
    client = ParallelDeepSeekClientV2(
        api_keys=api_keys,
        max_concurrent=1  # Один запрос для чистоты эксперимента
    )
    
    # Формируем вопрос
    prompt = """Ты - эксперт по архитектуре асинхронных Python систем и API интеграции.

КОНТЕКСТ ПРОЕКТА:
Создана система с двумя AI API:
1. DeepSeek Code Agent - 4 API ключа для генерации/рефакторинга кода
2. Perplexity MCP Server - 1 API ключ для поиска информации

ТЕКУЩАЯ АРХИТЕКТУРА:
```python
class ParallelDeepSeekClientV2:
    def __init__(self, api_keys: List[str], max_concurrent: int = 3):
        self.semaphore = asyncio.Semaphore(max_concurrent)  # 3 слота для 4 ключей
        
    async def process_single_task(self, task):
        async with self.semaphore:  # ЗАХВАТ СЛОТА
            response = await httpx.post("https://api.deepseek.com/...")

class DeepSeekCodeAgent:
    def __init__(self):
        api_keys = [key1, key2, key3, key4]  # ВСЕ 4 ключа в одном пуле
        self.client = ParallelDeepSeekClientV2(api_keys, max_concurrent=3)
```

КРИТИЧЕСКИЕ СЦЕНАРИИ ВЗАИМОДЕЙСТВИЯ:

Сценарий 1: DeepSeek → Perplexity → DeepSeek (вложенные вызовы)
- User вызывает DeepSeekAgent.generate_code() → захватывает 1 из 3 слотов семафора
- DeepSeek генерирует код, но решает искать best practices через Perplexity
- Perplexity получает результаты и решает попросить DeepSeek проанализировать код
- DeepSeek пытается захватить семафор, но осталось только 2 слота

Сценарий 2: 3 параллельных вызова Code Agent (все слоты семафора заняты)
```python
tasks = [
    agent.generate_code(req1),  # slot 1
    agent.generate_code(req2),  # slot 2  
    agent.generate_code(req3),  # slot 3
]
await asyncio.gather(*tasks)
```
Если любой из них вызовет Perplexity → DeepSeek, возникнет DEADLOCK.

ВОПРОСЫ К ТЕБЕ:

1. DEADLOCK РИСК: Возможен ли deadlock в описанных сценариях? ДА или НЕТ и почему?

2. РЕШЕНИЕ: Правильное ли решение - разделить 4 ключа на 2 пула?
   - USER pool: 2 ключа (DEEPSEEK_API_KEY, DEEPSEEK_API_KEY_2), max_concurrent=8
   - NESTED pool: 2 ключа (DEEPSEEK_API_KEY_3, DEEPSEEK_API_KEY_4), max_concurrent=2

3. АРХИТЕКТУРА: Как должен выглядеть DeepSeekClientPool для production?

4. PERPLEXITY INTEGRATION: Если Perplexity (1 API ключ) может вызывать DeepSeek, 
   как организовать взаимодействие чтобы не было deadlock?

5. МАСШТАБИРОВАНИЕ: Что если нагрузка 100+ requests/sec? Достаточно ли 4 ключей?

Ответь кратко и структурированно на РУССКОМ языке (до 2000 токенов):
1. Deadlock: ДА/НЕТ + объяснение (2-3 предложения)
2. Решение с пулами: правильно/неправильно + почему
3. Рекомендованная архитектура DeepSeekClientPool (3-5 пунктов)
4. Integration с Perplexity (2-3 рекомендации)
5. Scaling рекомендации (2-3 пункта)"""

    print("📤 Отправка вопроса к DeepSeek Chat API...")
    print("   Model: deepseek-chat")
    print("   Max tokens: 2000")
    print()
    
    # Создаем задачу
    task = DeepSeekTask(
        task_id="architectural_analysis_001",
        prompt=prompt,
        model="deepseek-chat",  # CHAT модель для текстовых ответов
        temperature=0.7,
        max_tokens=2000,
        priority=TaskPriority.HIGH
    )
    
    try:
        # Выполняем запрос
        results = await client.process_batch([task], show_progress=True)
        result = results[0]
        
        if result.success:
            print("\n" + "=" * 80)
            print("ОТВЕТ ОТ DEEPSEEK:")
            print("=" * 80)
            print()
            print(result.response)
            print()
            print("=" * 80)
            print(f"⏱️  Processing time: {result.processing_time:.2f}s")
            print(f"🔢 Tokens used: {result.tokens_used}")
            print(f"🔄 Retries: {result.retry_count}")
            print(f"🔑 API key used: ...{result.api_key_used[-6:]}")
            print("=" * 80)
            
            # Сохраняем ответ
            output_file = Path("DEEPSEEK_DIRECT_ANSWER.md")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("# DeepSeek Direct Answer - Архитектура вложенных вызовов\n\n")
                f.write(f"**Дата:** 8 ноября 2025\n")
                f.write(f"**Model:** deepseek-chat\n")
                f.write(f"**Processing time:** {result.processing_time:.2f}s\n")
                f.write(f"**Tokens:** {result.tokens_used}\n")
                f.write(f"**API key:** ...{result.api_key_used[-6:]}\n\n")
                f.write("---\n\n")
                f.write(result.response)
            
            print(f"\n✅ Ответ сохранен в {output_file}")
            
        else:
            print(f"\n❌ Ошибка от DeepSeek API:")
            print(f"   {result.error}")
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Статистика
        print("\n" + "=" * 80)
        print("СТАТИСТИКА КЛИЕНТА:")
        print("=" * 80)
        stats = client.get_statistics()
        print(f"Total requests: {stats['total_requests']}")
        print(f"Successful: {stats['successful_requests']}")
        print(f"Failed: {stats['failed_requests']}")
        print(f"Total tokens: {stats['total_tokens']}")
        # Конвертируем в float если это строка
        total_time = stats['total_processing_time']
        if isinstance(total_time, str):
            total_time = float(total_time)
        print(f"Total time: {total_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(ask_deepseek_directly())
