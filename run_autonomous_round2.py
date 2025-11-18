"""
Round 2: Perplexity Best Practices Review для Quick Win #1
"""

import asyncio
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from backend.agents.agent_to_agent_communicator import AgentMessage, AgentType, MessageType, get_communicator
import uuid

# DeepSeek's solution from Round 1
DEEPSEEK_SOLUTION = """
Quick Win #1 - Tool Call Budget Counter Implementation:
- Добавлен tool_call_budget = 15 (максимум tool calls)
- Добавлен total_tool_calls = 0 (счетчик)
- Проверка бюджета перед выполнением tool calls
- Логирование: tool_call #{total_tool_calls}/{tool_call_budget}
- Graceful degradation: при превышении → системное сообщение вместо ошибки

Код изменений:
```python
# В начале tool calling loop:
tool_call_budget = 15
total_tool_calls = 0

# Перед выполнением tool calls:
if total_tool_calls + len(tool_calls) > tool_call_budget:
    logger.warning(f"⚠️ Tool call budget exceeded: {total_tool_calls + len(tool_calls)} > {tool_call_budget}")
    messages.append({
        "role": "system",
        "content": f"Tool call budget exceeded ({tool_call_budget} calls). Please provide final analysis."
    })
    continue

# После каждого tool call:
total_tool_calls += 1
logger.debug(f"Tool call #{total_tool_calls}/{tool_call_budget} completed")

# В конце итерации:
logger.info(f"Tool calls used: {total_tool_calls}/{tool_call_budget}")
```
"""

async def main():
    communicator = get_communicator()
    
    print('='*80)
    print('🎯 ROUND 2: Perplexity Best Practices Review')
    print('='*80)
    print()
    
    perplexity_msg = AgentMessage(
        message_id=str(uuid.uuid4()),
        from_agent=AgentType.COPILOT,
        to_agent=AgentType.PERPLEXITY,
        message_type=MessageType.QUERY,
        content=f'''
КОНТЕКСТ: DeepSeek предложил следующее решение для tool call budget:

{DEEPSEEK_SOLUTION}

ТВОЯ ЗАДАЧА:
1. Изучи best practices для tool calling limits в AI agent systems
2. Проверь рекомендации OpenAI/Anthropic/DeepSeek по function calling limits
3. Предложи оптимальный лимит для production (15 правильно? Или 10/20/30?)
4. Оцени решение DeepSeek с точки зрения:
   - Production reliability (защита от cascading timeouts)
   - Observability (достаточно ли логирования?)
   - Error handling (graceful degradation правильный подход?)
5. Предложи improvements если есть

FOCUS: Industry best practices, production reliability, observability

ОЖИДАЕМЫЙ ОТВЕТ:
- Оценка лимита 15 (слишком мало/достаточно/слишком много)
- Рекомендации по логированию/мониторингу
- Дополнительные улучшения (если нужны)
        ''',
        context={
            'task': 'best_practices_review',
            'self_improvement': True
        },
        conversation_id=f'autonomous_self_improvement_{uuid.uuid4().hex[:8]}'
    )
    
    print("📤 Отправляю запрос Perplexity...")
    print("⏳ Ожидание ответа (до 120s для research задач)...")
    
    import time
    start_time = time.time()
    response = await communicator.route_message(perplexity_msg)
    elapsed = time.time() - start_time
    
    print(f"✅ Получен ответ за {elapsed:.1f}s")
    print()
    print('='*80)
    print('✅ PERPLEXITY RESPONSE:')
    print('='*80)
    print()
    print(response.content)
    print()
    print('='*80)
    
    await communicator.close()

if __name__ == '__main__':
    asyncio.run(main())
