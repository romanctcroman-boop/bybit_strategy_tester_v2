"""
🔍 DeepSeek Agent - Complete MCP Server Analysis
DeepSeek анализирует ВЕСЬ код MCP сервера и генерирует 7 недостающих tools
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
    """DeepSeek анализирует полный код MCP сервера"""
    
    print("=" * 80)
    print("🤖 DEEPSEEK COMPLETE MCP SERVER ANALYSIS")
    print("=" * 80)
    print("\nDeepSeek Agent анализирует ВЕСЬ код MCP сервера...")
    
    # Load API keys (try multi-key)
    key_manager = get_key_manager()
    api_keys = []
    
    for i in range(1, 9):
        try:
            if i == 1:
                key = key_manager.get_decrypted_key("DEEPSEEK_API_KEY")
            else:
                key = key_manager.get_decrypted_key(f"DEEPSEEK_API_KEY_{i}")
            api_keys.append(key)
        except:
            break
    
    if not api_keys:
        print("\n❌ No API keys found!")
        return
    
    print(f"✅ Loaded {len(api_keys)} DeepSeek API keys")
    
    # Read FULL MCP server.py
    server_path = project_root / "mcp-server" / "server.py"
    
    try:
        with open(server_path, 'r', encoding='utf-8') as f:
            full_server_code = f.read()
    except Exception as e:
        print(f"\n❌ Failed to read server.py: {e}")
        return
    
    total_lines = len(full_server_code.split('\n'))
    total_chars = len(full_server_code)
    
    print(f"📄 server.py: {total_lines} lines, {total_chars:,} characters")
    
    # Extract key sections
    deepseek_section_start = full_server_code.find("# DEEPSEEK CODE GENERATION TOOLS")
    deepseek_section_end = full_server_code.find("async def initialize_providers():")
    
    if deepseek_section_start > 0 and deepseek_section_end > deepseek_section_start:
        deepseek_tools_code = full_server_code[deepseek_section_start:deepseek_section_end]
    else:
        deepseek_tools_code = "NOT FOUND"
    
    # Find Perplexity tools for comparison
    perplexity_tools = []
    for line in full_server_code.split('\n'):
        if line.strip().startswith('async def perplexity_'):
            tool_name = line.split('async def ')[1].split('(')[0]
            perplexity_tools.append(tool_name)
    
    print(f"📊 Perplexity tools found: {len(perplexity_tools)}")
    
    # Prepare comprehensive prompt
    prompt = f"""Проанализируй ПОЛНЫЙ код MCP сервера и создай 7 недостающих DeepSeek tools для достижения 100% интеграции.

📋 КОНТЕКСТ ПРОЕКТА:
- Проект: Bybit Strategy Tester v2 (MCP Server v2.0)
- Моя роль: DeepSeek Agent - AI для генерации кода торговых стратегий
- Конкурент: Perplexity Agent - {len(perplexity_tools)} tools для research/analysis
- Моя специализация: Code generation, optimization, testing

📊 ТЕКУЩЕЕ СОСТОЯНИЕ:
- MCP Server: {total_lines} lines, {total_chars:,} characters
- DeepSeek tools: 3/10 (30%) ❌
- Perplexity tools: {len(perplexity_tools)} (100%) ✅
- Оценка интеграции: 85/100%
- Для 100%: нужно +7 specialized tools

🔍 МОИ ТЕКУЩИЕ 3 TOOLS:
```python
{deepseek_tools_code[:4000]}
```

🎯 ЗАДАЧА:
Создай ПОЛНЫЙ КОД для 7 новых DeepSeek MCP tools:

1. **deepseek_analyze_strategy** - Анализ существующей стратегии
   - Принимает: strategy_code (str)
   - Анализирует: качество кода, логику, риски, производительность
   - Возвращает: детальный анализ + рекомендации

2. **deepseek_optimize_parameters** - Оптимизация параметров стратегии
   - Принимает: strategy_code, current_params (dict), optimization_goal
   - Генерирует: оптимизированные параметры
   - Возвращает: new_params + обоснование

3. **deepseek_backtest_analysis** - Анализ результатов бэктеста
   - Принимает: backtest_results (dict)
   - Анализирует: Sharpe Ratio, Drawdown, Win Rate, etc.
   - Возвращает: рекомендации по улучшению стратегии

4. **deepseek_risk_analysis** - Анализ рисков стратегии
   - Принимает: strategy_code, market_conditions (optional)
   - Оценивает: volatility risk, drawdown risk, leverage risk
   - Возвращает: risk score + митигация

5. **deepseek_compare_strategies** - Сравнение двух стратегий
   - Принимает: strategy_a_code, strategy_b_code
   - Сравнивает: производительность, риски, сложность
   - Возвращает: рекомендация какую стратегию использовать

6. **deepseek_generate_tests** - Генерация unit tests для стратегии
   - Принимает: strategy_code
   - Генерирует: полный набор pytest tests
   - Возвращает: test_code + coverage analysis

7. **deepseek_refactor_code** - Рефакторинг кода стратегии
   - Принимает: strategy_code, refactor_goals (list)
   - Улучшает: readability, performance, maintainability
   - Возвращает: refactored_code + changes_summary

📐 ТРЕБОВАНИЯ К КОДУ:

1. **Формат MCP tool:**
```python
@mcp.tool()
async def deepseek_НАЗВАНИЕ(
    param1: str,
    param2: str = "default"
) -> dict[str, Any]:
    \"\"\"
    🎯 Краткое описание (emoji + текст)
    
    Подробное описание функционала.
    
    Args:
        param1: Описание параметра
        param2: Описание параметра (default: default)
    
    Returns:
        Результат работы tool
    
    Example:
        result = await deepseek_НАЗВАНИЕ(
            param1="value",
            param2="value"
        )
        
        if result["success"]:
            print(result["data"])
    
    Use cases:
        - Случай использования 1
        - Случай использования 2
    \"\"\"
    import sys
    from pathlib import Path
    
    backend_path = Path(__file__).parent.parent / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    
    try:
        from agents.deepseek import DeepSeekAgent
        
        agent = DeepSeekAgent()
        
        # Основная логика
        result = await agent.МЕТОД(...)
        
        return {{
            "success": True,
            "data": result,
            "message": "Success message"
        }}
        
    except ImportError as e:
        return {{
            "success": False,
            "error": f"DeepSeek Agent not available: {{str(e)}}"
        }}
    except Exception as e:
        return {{
            "success": False,
            "error": f"Operation failed: {{str(e)}}"
        }}
```

2. **Обязательные элементы:**
   - ✅ @mcp.tool() декоратор
   - ✅ async def функция
   - ✅ Type hints (dict[str, Any])
   - ✅ Docstring с emoji, описанием, examples
   - ✅ Import backend/agents/deepseek.py
   - ✅ try/except с ImportError и Exception
   - ✅ return dict с success/error keys

3. **Интеграция с DeepSeekAgent:**
   - Используй существующие методы: generate_code(), fix_code(), test_code()
   - Или создай новые prompts для DeepSeek API
   - Добавь validation входных данных
   - Логируй важные операции

💡 ФОРМАТ ОТВЕТА:

Верни ГОТОВЫЙ КОД для вставки в server.py:

```python
# ═══════════════════════════════════════════════════════════════════════════
# DEEPSEEK EXTENDED TOOLS (PHASE 5) - 7 NEW TOOLS FOR 100% INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def deepseek_analyze_strategy(...):
    # ПОЛНЫЙ КОД

@mcp.tool()
async def deepseek_optimize_parameters(...):
    # ПОЛНЫЙ КОД

# ... и так далее для всех 7 tools
```

Будь максимально детальным. Код должен быть production-ready и готов к немедленному использованию."""
    
    # Call DeepSeek API with extended timeout
    import httpx
    
    print("\n🔄 Отправка запроса DeepSeek API...")
    print("⏱️  Это может занять 30-60 секунд (большой prompt)...\n")
    
    try:
        # Use first API key
        api_key = api_keys[0]
        
        async with httpx.AsyncClient(timeout=120.0) as client:
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
                            "content": "You are DeepSeek AI, expert in code generation. Create production-ready MCP tools with complete error handling, type hints, and documentation."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 8000  # Maximum for detailed code
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                tokens = data.get("usage", {}).get("total_tokens", 0)
                
                print("=" * 80)
                print("🤖 DEEPSEEK GENERATED 7 NEW TOOLS")
                print("=" * 80)
                print()
                print(content)
                print()
                print("=" * 80)
                print(f"📊 Tokens used: {tokens}")
                print("=" * 80)
                
                # Save generated code
                output_path = project_root / "DEEPSEEK_7_NEW_TOOLS_GENERATED.py"
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write("# 🤖 DeepSeek Generated 7 New MCP Tools\n")
                    f.write(f"# Generated: November 8, 2025\n")
                    f.write(f"# Model: deepseek-chat\n")
                    f.write(f"# Tokens: {tokens}\n\n")
                    f.write(content)
                
                print(f"\n💾 Code saved to: {output_path.name}")
                print("\n📋 Next steps:")
                print("   1. Review generated code")
                print("   2. Copy to mcp-server/server.py")
                print("   3. Test with test_deepseek_mcp_final.py")
                print("   4. Deploy to production")
                
            else:
                print(f"\n❌ API Error: HTTP {response.status_code}")
                print(response.text[:500])
                
    except httpx.TimeoutException:
        print("\n⏱️ Request timeout (120s exceeded) - Try with smaller max_tokens")
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
