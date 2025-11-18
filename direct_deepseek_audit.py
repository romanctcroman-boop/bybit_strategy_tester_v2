"""
Прямой аудит агентов DeepSeek (без обёрток)
===========================================
Прямой HTTP запрос к DeepSeek API для аудита системы агентов
"""
import asyncio
import httpx
import json
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

async def direct_deepseek_audit():
    """Прямой запрос к DeepSeek API"""
    
    # Загрузить API ключ напрямую из .env
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    # Попробовать все возможные DeepSeek ключи
    deepseek_key = None
    for i in range(1, 9):
        key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
        if key:
            deepseek_key = key
            print(f"✅ Найден ключ: DEEPSEEK_API_KEY_{i}")
            break
    
    if not deepseek_key:
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            print("✅ Найден ключ: DEEPSEEK_API_KEY")
    
    if not deepseek_key:
        print("❌ No DeepSeek API key found in .env!")
        return
    
    print("=" * 100)
    print("🔍 ПРЯМОЙ АУДИТ АГЕНТОВ ЧЕРЕЗ DeepSeek API")
    print("=" * 100)
    print(f"API Key: {deepseek_key[:20]}...{deepseek_key[-10:]}")
    print()
    
    # Прочитать код агентов для аудита
    agent_file = project_root / "backend" / "agents" / "unified_agent_interface.py"
    mcp_file = project_root / "backend" / "mcp" / "mcp_integration.py"
    
    with open(agent_file, 'r', encoding='utf-8') as f:
        agent_code = f.read()
    
    with open(mcp_file, 'r', encoding='utf-8') as f:
        mcp_code = f.read()
    
    # Формируем промпт для аудита
    audit_prompt = f"""🔍 ТЕХНИЧЕСКИЙ АУДИТ СИСТЕМЫ АГЕНТОВ

Ты - эксперт по системам AI агентов. Проведи глубокий аудит кодовой базы.

**UNIFIED AGENT INTERFACE (backend/agents/unified_agent_interface.py)**
Основной файл: {len(agent_code)} символов
Ключевые компоненты:
- Multi-channel fallback (MCP → Direct API → Backup keys)
- Key rotation (8 DeepSeek + 8 Perplexity keys)
- Health monitoring every 30s
- Circuit breakers

**MCP INTEGRATION (backend/mcp/mcp_integration.py)**
Размер: {len(mcp_code)} символов
Интеграция с MCP Server

**ПРОБЛЕМЫ, КОТОРЫЕ ЗАМЕЧЕНЫ:**
1. DeepSeek API возвращает 500 Internal Server Error
2. Perplexity через MCP таймаутит после 120s
3. Логи показывают "Perplexity URL" когда отправляется запрос DeepSeek
4. 4 из 8 Perplexity keys неактивны
5. Агенты "работают криво" по словам пользователя

**ЗАДАЧИ АУДИТА:**

1. **КРИТИЧЕСКИЕ БАГИ** - найди и опиши точно:
   - Почему DeepSeek запросы идут на Perplexity URL?
   - Логическая ошибка в URL routing?
   - Проблемы с agent_type передачей?
   - Баги в fallback logic?

2. **АРХИТЕКТУРНЫЕ ПРОБЛЕМЫ:**
   - Правильно ли организован multi-channel fallback?
   - Корректна ли работа MCP интеграции?
   - Есть ли race conditions или deadlocks?
   - Проблемы с async/await?

3. **КОНКРЕТНЫЕ РЕКОМЕНДАЦИИ:**
   - Что именно сломано (файл, функция, строка)?
   - Как исправить (точный код)?
   - Почему это происходит?
   - Как протестировать fix?

**ФОРМАТ ОТВЕТА:**
```
КРИТИЧЕСКИЕ БАГИ:
1. [Название бага]
   Файл: backend/agents/...
   Функция: _название_функции
   Проблема: [точное описание]
   Код с ошибкой:
   ```python
   # проблемный код
   ```
   Исправление:
   ```python
   # исправленный код
   ```

АРХИТЕКТУРНЫЕ ПРОБЛЕМЫ:
...

РЕКОМЕНДАЦИИ:
...
```

Будь максимально конкретным. Укажи точные строки кода, где баги."""

    # Прямой HTTP запрос к DeepSeek
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {deepseek_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "Ты - эксперт по системам AI агентов и отладке сложных багов. Проводишь технический аудит с глубоким анализом кода."
            },
            {
                "role": "user",
                "content": audit_prompt
            }
        ],
        "temperature": 0.1,  # Низкая температура для точности
        "max_tokens": 4000
    }
    
    print("📤 Отправка запроса к DeepSeek API...")
    print(f"URL: {url}")
    print(f"Timeout: 600s")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            print(f"📊 Статус: {response.status_code}")
            print(f"📊 Headers: {dict(response.headers)}")
            print()
            
            if response.status_code == 200:
                data = response.json()
                
                # Извлечь ответ
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                
                print("=" * 100)
                print("✅ РЕЗУЛЬТАТ АУДИТА ОТ DeepSeek")
                print("=" * 100)
                print()
                print(content)
                print()
                print("=" * 100)
                print(f"📊 Токены: prompt={usage.get('prompt_tokens')}, completion={usage.get('completion_tokens')}, total={usage.get('total_tokens')}")
                print("=" * 100)
                
                # Сохранить в файл
                report_path = project_root / f"DEEPSEEK_DIRECT_AUDIT_{Path(__file__).stem.split('_')[-1]}.md"
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write("# DeepSeek Direct Audit Report\n\n")
                    f.write(f"**Date**: {Path(__file__).stem}\n")
                    f.write(f"**API**: DeepSeek v1 (direct HTTP)\n")
                    f.write(f"**Status**: {response.status_code}\n")
                    f.write(f"**Tokens**: {usage.get('total_tokens')}\n\n")
                    f.write("---\n\n")
                    f.write(content)
                
                print(f"\n💾 Отчёт сохранён: {report_path.name}")
                
            else:
                print(f"❌ ОШИБКА HTTP {response.status_code}")
                print(f"Response: {response.text}")
                
    except httpx.TimeoutException:
        print("❌ TIMEOUT после 600 секунд!")
        
    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(direct_deepseek_audit())
