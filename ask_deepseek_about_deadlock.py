"""
Получить рекомендации от DeepSeek по архитектуре вложенных вызовов
"""
import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from automation.deepseek_code_agent.code_agent import DeepSeekCodeAgent, CodeGenerationRequest
from dotenv import load_dotenv

load_dotenv()


async def get_deepseek_recommendations():
    """Получить экспертный анализ от DeepSeek"""
    
    print("=" * 80)
    print("ЗАПРОС ЭКСПЕРТНОГО МНЕНИЯ ОТ DEEPSEEK")
    print("=" * 80)
    print()
    
    # Загружаем контекст из анализа Perplexity
    analysis_file = Path("DEEPSEEK_MULTIKEY_NESTED_CALLS_ANALYSIS.md")
    if not analysis_file.exists():
        print("❌ Файл DEEPSEEK_MULTIKEY_NESTED_CALLS_ANALYSIS.md не найден")
        return
    
    # Читаем первые 8000 символов (ограничение токенов)
    with open(analysis_file, 'r', encoding='utf-8') as f:
        content = f.read()[:8000]
    
    # Формируем запрос к DeepSeek
    prompt = f"""Ты - старший архитектор Python систем с опытом работы с asyncio, микросервисами и высоконагруженными API.

КОНТЕКСТ ПРОЕКТА:
Разработана система DeepSeek Code Agent (аналог GitHub Copilot) с 4 API ключами для генерации кода, рефакторинга, исправления ошибок.

ПРОБЛЕМА:
Perplexity AI обнаружила КРИТИЧЕСКИЙ DEADLOCK РИСК при вложенных вызовах:
DeepSeek Agent → Perplexity → DeepSeek Agent (nested call)

ТЕКУЩАЯ АРХИТЕКТУРА:
```python
class ParallelDeepSeekClientV2:
    def __init__(self, api_keys: List[str], max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)  # ПРОБЛЕМА
        self.circuit_breakers = {{key: CircuitBreaker(...) for key in api_keys}}
    
    async def process_single_task(self, task):
        async with self.semaphore:  # Захват слота
            best_key = self._get_best_key()
            async with self.circuit_breakers[best_key].call():
                response = await httpx_client.post(...)

class DeepSeekCodeAgent:
    def __init__(self):
        api_keys = [key1, key2, key3, key4]  # 4 ключа
        self.client = ParallelDeepSeekClientV2(api_keys, max_concurrent=3)
```

СЦЕНАРИЙ DEADLOCK:
1. 3 user requests заполняют все 3 слота семафора
2. Любой request делает nested call через Perplexity
3. Nested call пытается захватить семафор → все слоты заняты
4. Родители ждут детей, дети ждут слотов → DEADLOCK

РЕШЕНИЕ ОТ PERPLEXITY:
Разделить ключи на USER пул (2 ключа, max_concurrent=8) и NESTED пул (2 ключа, max_concurrent=2).

ЗАПРОС К ТЕБЕ:
1. Согласен ли ты с диагнозом deadlock риска?
2. Правильное ли решение - разделение ключей?
3. Альтернативные подходы (если есть)?
4. Code review предложенного DeepSeekClientPool (ниже)
5. Дополнительные риски которые мы упустили?

ПРЕДЛОЖЕННОЕ РЕШЕНИЕ:
```python
class DeepSeekClientPool:
    def __init__(self):
        key_manager = get_key_manager()
        
        # USER-FACING CLIENT (2 ключа, высокий приоритет)
        user_keys = [
            key_manager.get_decrypted_key("DEEPSEEK_API_KEY"),
            key_manager.get_decrypted_key("DEEPSEEK_API_KEY_2"),
        ]
        self.user_client = ParallelDeepSeekClientV2(user_keys, max_concurrent=8)
        
        # NESTED/BACKGROUND CLIENT (2 ключа, низкий приоритет)
        nested_keys = [
            key_manager.get_decrypted_key("DEEPSEEK_API_KEY_3"),
            key_manager.get_decrypted_key("DEEPSEEK_API_KEY_4"),
        ]
        self.nested_client = ParallelDeepSeekClientV2(nested_keys, max_concurrent=2)
```

Ответь кратко (до 1500 токенов):
1. Диагноз: верный/неверный + почему
2. Решение: правильное/неправильное + альтернативы
3. Code review: что улучшить
4. Дополнительные риски
5. Production checklist (топ-5 пунктов)

Ответ структурируй чётко по пунктам, на РУССКОМ языке."""
    
    print("📤 Отправка запроса DeepSeek (deepseek-coder model)...")
    print()
    
    # Инициализация агента
    agent = DeepSeekCodeAgent(model="deepseek-coder")
    
    # Запрос
    request = CodeGenerationRequest(
        prompt=prompt,
        language="markdown",  # Ответ в markdown формате
        max_tokens=2000  # Достаточно для развернутого ответа
    )
    
    try:
        result = await agent.generate_code(request)
        
        if result['success']:
            print("=" * 80)
            print("ОТВЕТ ОТ DEEPSEEK:")
            print("=" * 80)
            print()
            print(result['code'])
            print()
            print("=" * 80)
            print(f"Processing time: {result['processing_time']:.2f}s")
            print(f"Tokens used: {result['tokens_used']}")
            print("=" * 80)
            
            # Сохраняем ответ
            output_file = Path("DEEPSEEK_EXPERT_REVIEW.md")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# DeepSeek Expert Review - Вложенные вызовы API\n")
                f.write(f"**Дата:** {asyncio.get_event_loop().time()}\n")
                f.write(f"**Model:** deepseek-coder\n")
                f.write(f"**Processing time:** {result['processing_time']:.2f}s\n")
                f.write(f"**Tokens:** {result['tokens_used']}\n\n")
                f.write("---\n\n")
                f.write(result['code'])
            
            print(f"\n✅ Ответ сохранен в {output_file}")
            
        else:
            print(f"❌ Ошибка: {result['error']}")
    
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(get_deepseek_recommendations())
