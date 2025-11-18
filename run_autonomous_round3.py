"""
Round 3: Consensus + Implementation — DeepSeek финальная реализация
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

# CONSENSUS от Round 1-2
CONSENSUS = """
КОНСЕНСУС от DeepSeek + Perplexity:

1. Лимит 15 tool calls — разумный baseline для production
2. Graceful degradation (system message) — правильный подход ✅
3. Базовое логирование есть, но недостаточно для production

ТРЕБУЕМЫЕ IMPROVEMENTS:
✅ Добавить конфигурируемый лимит через env var (не хардкодить 15)
✅ Расширить метрики: время выполнения, ошибки, типы tool calls
✅ Добавить Prometheus/OpenTelemetry instrumentation
✅ Логировать причины превышения лимита (audit trail)
✅ Поддержка алертов при превышении лимита
"""

async def main():
    communicator = get_communicator()
    
    print('='*80)
    print('🎯 ROUND 3: DeepSeek Финальная Реализация')
    print('='*80)
    print()
    
    deepseek_msg = AgentMessage(
        message_id=str(uuid.uuid4()),
        from_agent=AgentType.COPILOT,
        to_agent=AgentType.DEEPSEEK,
        message_type=MessageType.QUERY,
        content=f'''
КОНТЕКСТ - CONSENSUS от Round 1-2:

{CONSENSUS}

ТВОЯ ЗАДАЧА: Реализовать ПОЛНОЕ решение с учетом фидбека Perplexity

ТРЕБОВАНИЯ:
1. Конфигурируемый лимит через env var (TOOL_CALL_BUDGET, default=15)
2. Расширенное логирование:
   - tool_calls used: X/Y (уже есть)
   - tool_calls breakdown by type
   - причина превышения лимита (если случилось)
3. Prometheus metrics (если metrics_enabled=True):
   - tool_calls_total{{tool_name=X, agent=Y}}
   - tool_call_budget_exceeded_total{{agent=X}}
   - tool_call_duration_seconds{{tool_name=X}}
4. Конфигурация в base_config.py:
   - TOOL_CALL_BUDGET = 15 (default)
   - Возможность переопределить через ENV

ИСПОЛЬЗУЙ: file_read() для чтения unified_agent_interface.py
ВЫВЕДИ: Полный финальный код с всеми улучшениями
        ''',
        context={
            'use_file_access': True,
            'task': 'code_implementation',
            'self_improvement': True,
            'complex_task': True
        },
        conversation_id=f'autonomous_self_improvement_{uuid.uuid4().hex[:8]}'
    )
    
    print("📤 Отправляю запрос DeepSeek для финальной реализации...")
    print("⏳ Ожидание ответа (до 600s для complex tasks)...")
    print()
    
    import time
    start_time = time.time()
    response = await communicator.route_message(deepseek_msg)
    elapsed = time.time() - start_time
    
    print(f"✅ Получен ответ за {elapsed:.1f}s")
    print()
    print('='*80)
    print('✅ DEEPSEEK FINAL IMPLEMENTATION:')
    print('='*80)
    print()
    print(response.content)
    print()
    print('='*80)
    
    await communicator.close()

if __name__ == '__main__':
    asyncio.run(main())
