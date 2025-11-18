"""
Прямой вопрос к DeepSeek: согласен ли он с диагнозом Perplexity о deadlock?
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from automation.deepseek_code_agent.code_agent import DeepSeekCodeAgent, CodeGenerationRequest
from dotenv import load_dotenv

load_dotenv()


async def ask_deepseek():
    print("=" * 80)
    print("ПРЯМОЙ ВОПРОС К DEEPSEEK")
    print("=" * 80)
    print()
    
    prompt = """КОНТЕКСТ: Python asyncio система с 4 API ключами DeepSeek.

КОД:
```python
class ParallelDeepSeekClientV2:
    def __init__(self, api_keys: List[str], max_concurrent: int = 3):
        self.semaphore = asyncio.Semaphore(max_concurrent)  # 3 слота
    
    async def process_single_task(self, task):
        async with self.semaphore:  # ЗАХВАТ СЛОТА
            response = await httpx.post(...)
```

СЦЕНАРИЙ:
1. User делает 3 запроса → заполняют все 3 слота семафора
2. Любой запрос внутри вызывает Perplexity → Perplexity вызывает DeepSeek обратно
3. Вложенный DeepSeek вызов пытается захватить семафор → НЕТ СВОБОДНЫХ СЛОТОВ
4. Родительский запрос ждет завершения Perplexity → Perplexity ждет DeepSeek → DeepSeek ждет слот

ВОПРОС:
Возможен ли DEADLOCK в этом сценарии? Ответь кратко ДА/НЕТ и объясни почему (2-3 предложения).

РЕШЕНИЕ PERPLEXITY:
Разделить 4 ключа на 2 пула: USER pool (2 ключа, max_concurrent=8) и NESTED pool (2 ключа, max_concurrent=2).

Правильное ли это решение? Есть ли альтернативы?

Ответь на РУССКОМ языке, структурировано:
1. Deadlock возможен? (ДА/НЕТ + объяснение)
2. Решение правильное? (ДА/НЕТ + почему)
3. Альтернативные подходы (если есть)"""
    
    agent = DeepSeekCodeAgent(model="deepseek-chat")  # Используем chat модель для диалога
    
    request = CodeGenerationRequest(
        prompt=prompt,
        language="markdown",
        max_tokens=1000
    )
    
    print("📤 Отправка запроса...")
    result = await agent.generate_code(request)
    
    if result['success']:
        print("\n" + "=" * 80)
        print("ОТВЕТ DEEPSEEK:")
        print("=" * 80)
        print(result['code'])
        print("\n" + "=" * 80)
        print(f"⏱️  {result['processing_time']:.2f}s | 🔢 {result['tokens_used']} tokens")
        
        # Сохраняем
        with open("DEEPSEEK_DEADLOCK_VERDICT.md", 'w', encoding='utf-8') as f:
            f.write("# DeepSeek Verdict - Deadlock Analysis\n\n")
            f.write(result['code'])
        print("✅ Сохранено в DEEPSEEK_DEADLOCK_VERDICT.md")
    else:
        print(f"❌ Ошибка: {result['error']}")


if __name__ == "__main__":
    asyncio.run(ask_deepseek())
