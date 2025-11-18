"""
Агенты анализируют свои собственные возможности
Agent Self-Diagnosis and Improvement Task
"""

import asyncio
import httpx
import json
from datetime import datetime


async def agent_self_diagnosis():
    """
    Задача для агента: самостоятельно проанализировать проблему с tool calling
    и предложить решение
    """
    
    base_url = "http://127.0.0.1:8000"
    
    print("="*80)
    print("АГЕНТСКАЯ САМОДИАГНОСТИКА")
    print("Agent Self-Diagnosis Task")
    print("="*80)
    print()
    
    # Проверка доступности backend
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/v1/health")
            if response.status_code != 200:
                print(f"Backend недоступен: {response.status_code}")
                return
            print("Backend работает")
            print()
    except Exception as e:
        print(f"Ошибка подключения к backend: {e}")
        return
    
    # Задание для агента
    task = """
Задача: Самостоятельная диагностика и исправление проблемы с tool calling

КОНТЕКСТ:
1. Ты - DeepSeek AI агент в системе bybit_strategy_tester_v2
2. Для тебя реализована поддержка tool calling (function calling)
3. Доступны 3 MCP инструмента:
   - mcp_read_project_file: читать файлы проекта
   - mcp_list_project_structure: просматривать структуру
   - mcp_analyze_code_quality: анализировать качество кода

ПРОБЛЕМА:
При тестировании оказалось, что ты не можешь использовать эти инструменты.
Прямое тестирование DeepSeek API показало, что tool calling работает отлично.
Значит проблема в интеграции внутри нашей системы.

ИЗВЕСТНЫЕ ФАКТЫ:
- В файле backend/agents/agent_to_agent_communicator.py метод _handle_deepseek_message
  отправляет запросы через agent_interface.send_request()
- Метод send_request по умолчанию использует preferred_channel=MCP_SERVER
- MCP_SERVER не поддерживает tool calling, только DIRECT_API
- Было внесено изменение: добавлена строка для маршрутизации через DIRECT_API
  когда use_file_access=True

ТВОЯ ЗАДАЧА:
1. Прочитай файл backend/agents/agent_to_agent_communicator.py используя mcp_read_project_file
2. Найди метод _handle_deepseek_message
3. Проверь, действительно ли там есть код для выбора DIRECT_API канала
4. Если код есть - проверь, правильно ли он работает
5. Если кода нет или он неправильный - предложи точное исправление
6. Прочитай файл backend/agents/unified_agent_interface.py метод send_request
7. Убедись, что параметр preferred_channel учитывается правильно

ТРЕБОВАНИЯ:
- Используй ТОЛЬКО инструменты mcp_read_project_file и mcp_list_project_structure
- НЕ выдумывай содержимое файлов - читай их реально
- Дай точный анализ с номерами строк
- Предложи конкретное решение в виде кода

Начинай анализ!
"""

    payload = {
        "from_agent": "copilot",
        "to_agent": "deepseek",
        "content": task,
        "context": {
            "use_file_access": True,
            "task_type": "self_diagnosis",
            "priority": "high"
        }
    }
    
    print("Отправка задачи агенту DeepSeek...")
    print("Задача: Самостоятельно диагностировать проблему с tool calling")
    print()
    
    async with httpx.AsyncClient(timeout=300.0) as client:  # 5 минут на анализ
        try:
            response = await client.post(
                f"{base_url}/api/v1/agent/send",
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                
                print("="*80)
                print("ОТВЕТ АГЕНТА / AGENT RESPONSE")
                print("="*80)
                print()
                print(result.get("content", "Нет ответа"))
                print()
                print("="*80)
                print()
                print(f"Итерация: {result.get('iteration', 'N/A')}")
                print(f"Conversation ID: {result.get('conversation_id', 'N/A')}")
                print()
                
                # Сохранить результат
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"AGENT_SELF_DIAGNOSIS_{timestamp}.json"
                
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                
                print(f"Результат сохранён в: {filename}")
                
                # Анализ ответа
                content = result.get("content", "").lower()
                
                print()
                print("АНАЛИЗ ОТВЕТА:")
                
                if "mcp_read_project_file" in content or "read" in content and "file" in content:
                    print("✓ Агент упоминает чтение файлов")
                else:
                    print("✗ Агент НЕ упоминает чтение файлов")
                
                if "backend/agents" in content:
                    print("✓ Агент анализирует нужные файлы")
                else:
                    print("✗ Агент НЕ анализирует файлы агентов")
                
                if "preferred_channel" in content or "direct_api" in content or "mcp_server" in content:
                    print("✓ Агент обсуждает маршрутизацию")
                else:
                    print("✗ Агент НЕ обсуждает маршрутизацию")
                
                if result.get("iteration", 0) > 1:
                    print(f"✓ Агент выполнил {result.get('iteration')} итераций (возможно использовал tools)")
                else:
                    print("✗ Агент выполнил только 1 итерацию (tools не использовались)")
                
            else:
                print(f"Ошибка HTTP: {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"Ошибка выполнения: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(agent_self_diagnosis())
