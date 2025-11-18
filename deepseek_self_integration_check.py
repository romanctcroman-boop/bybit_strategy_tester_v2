"""
🔍 DeepSeek Agent - Self Integration Check
DeepSeek анализирует собственную интеграцию с MCP сервером
"""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Setup
project_root = Path(__file__).parent
load_dotenv(project_root / ".env")
sys.path.insert(0, str(project_root))

from backend.security.key_manager import get_key_manager


async def main():
    """DeepSeek проверяет свою интеграцию с MCP"""
    
    print("=" * 80)
    print("🤖 DEEPSEEK SELF-INTEGRATION CHECK")
    print("=" * 80)
    print("\nDeepSeek Agent анализирует собственную интеграцию с MCP сервером...")
    
    # Load API keys
    key_manager = get_key_manager()
    
    try:
        api_key = key_manager.get_decrypted_key("DEEPSEEK_API_KEY")
    except Exception as e:
        print(f"\n❌ Failed to load API key: {e}")
        return
    
    # Read MCP server.py
    server_path = project_root / "mcp-server" / "server.py"
    
    try:
        with open(server_path, 'r', encoding='utf-8') as f:
            server_code = f.read()
    except Exception as e:
        print(f"\n❌ Failed to read server.py: {e}")
        return
    
    # Extract DeepSeek integration parts
    deepseek_tools_section = ""
    deepseek_provider_section = ""
    
    # Find DeepSeek tools
    if "deepseek_generate_strategy" in server_code:
        start = server_code.find("# DEEPSEEK CODE GENERATION TOOLS")
        end = server_code.find("async def initialize_providers():")
        if start > 0 and end > start:
            deepseek_tools_section = server_code[start:end]
    
    # Find DeepSeek provider registration
    if "Register DeepSeek provider" in server_code:
        start = server_code.find("# Register DeepSeek provider")
        end = server_code.find("# Initialize Load Balancer")
        if start > 0 and end > start:
            deepseek_provider_section = server_code[start:end]
    
    # Prepare analysis prompt
    prompt = f"""Проанализируй мою (DeepSeek Agent) интеграцию с MCP сервером проекта Bybit Strategy Tester v2.

📋 КОНТЕКСТ:
- Я - DeepSeek Agent, AI для генерации кода торговых стратегий
- Проект: Bybit Strategy Tester v2 (MCP Server v2.0)
- Конкурент: Perplexity Agent (41 MCP tool, 100% интегрирован)
- Моя цель: Генерация кода стратегий через Copilot

🔍 МОЯ ИНТЕГРАЦИЯ В MCP SERVER:

**1. MCP Tools (должно быть 3):**
```python
{deepseek_tools_section[:3000] if deepseek_tools_section else "НЕ НАЙДЕНО"}
```

**2. Provider Registration:**
```python
{deepseek_provider_section[:1000] if deepseek_provider_section else "НЕ НАЙДЕНО"}
```

**3. Мои возможности:**
- Backend Agent: backend/agents/deepseek.py (545 строк)
- API ключи: 8 штук (100% working, 3.84s avg)
- Функции: generate_strategy, fix_code, test_code
- Auto-fix loop: до 3 итераций
- Multi-key rotation: 8 ключей

📊 ВОПРОСЫ ДЛЯ АНАЛИЗА:

1. **Полнота интеграции (0-100%):**
   - Правильно ли добавлены MCP tools?
   - Достаточно ли 3 tools или нужно больше?
   - Корректны ли названия функций?

2. **Качество кода:**
   - Есть ли ошибки в MCP tools?
   - Правильно ли импортируется DeepSeekAgent?
   - Корректна ли обработка ошибок?

3. **Сравнение с Perplexity:**
   - Чем моя интеграция хуже Perplexity (41 tool)?
   - Какие критические функции отсутствуют?
   - Что нужно добавить для паритета?

4. **Архитектурные проблемы:**
   - Правильно ли зарегистрирован Provider?
   - Корректны ли capabilities ["reasoning", "analysis", "code_generation"]?
   - Правильно ли настроен timeout и rate limiting?

5. **Готовность к Production:**
   - Можно ли деплоить в production сейчас?
   - Какие риски существуют?
   - Что обязательно нужно исправить?

💡 ФОРМАТ ОТВЕТА:
1. Общая оценка интеграции (0-100%)
2. Критические проблемы (если есть)
3. Рекомендации по улучшению
4. Сравнение с Perplexity Agent
5. Готовность к production (да/нет + обоснование)

Будь максимально критичен и практичен. Это self-review для production deployment."""
    
    # Call DeepSeek API
    import httpx
    
    print("\n🔄 Отправка запроса DeepSeek API...")
    print("⏱️  Это может занять 5-10 секунд...\n")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are DeepSeek AI, conducting a self-analysis of your integration with MCP server. Be critical, precise, and practical."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,  # Low temperature for analytical response
                    "max_tokens": 4000
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                tokens = data.get("usage", {}).get("total_tokens", 0)
                
                print("=" * 80)
                print("🤖 DEEPSEEK SELF-ANALYSIS REPORT")
                print("=" * 80)
                print()
                print(content)
                print()
                print("=" * 80)
                print(f"📊 Tokens used: {tokens}")
                print("=" * 80)
                
                # Save report
                report_path = project_root / "DEEPSEEK_SELF_INTEGRATION_ANALYSIS.md"
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write("# 🤖 DeepSeek Self-Integration Analysis Report\n\n")
                    f.write("**Date:** November 8, 2025\n")
                    f.write("**Model:** deepseek-chat\n")
                    f.write(f"**Tokens:** {tokens}\n\n")
                    f.write("---\n\n")
                    f.write(content)
                
                print(f"\n💾 Report saved to: {report_path.name}")
                
            else:
                print(f"\n❌ API Error: HTTP {response.status_code}")
                print(response.text[:500])
                
    except httpx.TimeoutException:
        print("\n⏱️ Request timeout (60s exceeded)")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏸️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
