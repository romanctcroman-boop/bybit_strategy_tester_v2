"""
Round 1: DeepSeek Technical Analysis для Quick Win #1 - Tool Call Budget Counter
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

async def main():
    communicator = get_communicator()
    
    # Round 1: DeepSeek technical analysis
    print('='*80)
    print('🎯 ROUND 1: DeepSeek Technical Analysis')
    print('='*80)
    print()
    
    deepseek_msg = AgentMessage(
        message_id=str(uuid.uuid4()),
        from_agent=AgentType.COPILOT,
        to_agent=AgentType.DEEPSEEK,
        message_type=MessageType.QUERY,
        content='''
ЗАДАЧА: Технический анализ Quick Win #1 - Tool Call Budget Counter

КОНТЕКСТ:
Файл: backend/agents/unified_agent_interface.py
Проблема: В lines 596-673 есть tool calling loop без ограничения на количество tool calls
Риск: Agent может запросить 5 tools × 5 iterations = 25 MCP calls → timeout cascade

ТВОЯ ЗАДАЧА:
1. Прочитай файл backend/agents/unified_agent_interface.py (используй tool)
2. Найди tool calling loop (lines ~596-673)
3. Предложи точную имплементацию budget counter:
   - Где добавить счетчик
   - Какой лимит (10? 15? 20?)
   - Как обрабатывать превышение лимита
   - Как логировать для debugging
4. Напиши ПОЛНЫЙ код изменений с context (3-5 строк до/после)

ВАЖНО: Используй file_read("backend/agents/unified_agent_interface.py") для точного анализа
        ''',
        context={
            'use_file_access': True,
            'task': 'technical_analysis',
            'self_improvement': True
        },
        conversation_id=f'autonomous_self_improvement_{uuid.uuid4().hex[:8]}'
    )
    
    print("📤 Отправляю запрос DeepSeek...")
    print("⏳ Ожидание ответа (до 600s для сложных задач с file access)...")
    
    import time
    start_time = time.time()
    response = await communicator.route_message(deepseek_msg)
    elapsed = time.time() - start_time
    
    print(f"✅ Получен ответ за {elapsed:.1f}s")
    print()
    print('='*80)
    print('✅ DEEPSEEK RESPONSE:')
    print('='*80)
    print()
    print(response.content)
    print()
    print('='*80)
    
    await communicator.close()

if __name__ == '__main__':
    asyncio.run(main())
