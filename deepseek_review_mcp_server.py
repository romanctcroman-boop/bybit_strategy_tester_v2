#!/usr/bin/env python3
"""
DeepSeek Agent: Глубокая проверка MCP Server кода

Задачи для DeepSeek:
1. Проверить интеграцию 10 DeepSeek tools в MCP сервере
2. Найти потенциальные проблемы, недостатки, уязвимости
3. Предложить улучшения архитектуры
4. Проверить правильность авто-запуска DeepSeek Agent при старте MCP сервера
5. Дать рекомендации по оптимизации и best practices
"""

import sys
import asyncio
from pathlib import Path

# Добавляем пути
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

async def deepseek_review_mcp_server():
    """DeepSeek Agent проводит глубокую проверку MCP сервера"""
    
    try:
        from agents.deepseek import DeepSeekAgent
        from security.key_manager import KeyManager
        
        print("=" * 80)
        print("🤖 DeepSeek Agent: MCP Server Code Review")
        print("=" * 80)
        print()
        
        # Инициализируем DeepSeek Agent (использует KeyManager внутри)
        agent = DeepSeekAgent()
        print("✅ DeepSeek Agent initialized")
        print()
        
        # Читаем MCP Server код
        mcp_server_path = Path(__file__).parent / "mcp-server" / "server.py"
        with open(mcp_server_path, 'r', encoding='utf-8') as f:
            server_code = f.read()
        
        total_lines = len(server_code.split('\n'))
        total_chars = len(server_code)
        
        print(f"📄 MCP Server code loaded:")
        print(f"   Lines: {total_lines:,}")
        print(f"   Characters: {total_chars:,}")
        print()
        
        # Извлекаем ключевые секции для анализа
        sections = {
            "imports_and_init": server_code[:5000],  # Импорты и инициализация
            "deepseek_tools": server_code[100000:150000],  # DeepSeek tools секция
            "initialize_providers": None,  # Найдём функцию initialize_providers
        }
        
        # Находим initialize_providers
        import_idx = server_code.find("async def initialize_providers()")
        if import_idx != -1:
            sections["initialize_providers"] = server_code[import_idx:import_idx+3000]
        
        print("🔍 Preparing comprehensive review prompt for DeepSeek...")
        print()
        
        # Создаём комплексный промпт для глубокого анализа
        review_prompt = f"""You are an expert code reviewer analyzing the MCP (Model Context Protocol) Server implementation 
for Bybit Strategy Tester project. 

MCP Server Statistics:
- Total lines: {total_lines:,}
- Total characters: {total_chars:,}
- DeepSeek tools integrated: 10 (3 basic + 7 specialized)
- Perplexity tools: 47
- Total MCP tools: 57

KEY SECTIONS TO ANALYZE:

1. IMPORTS AND INITIALIZATION (First 5000 chars):
```python
{sections['imports_and_init']}
```

2. DEEPSEEK TOOLS SECTION:
```python
{sections['deepseek_tools'][:4000]}
```

3. PROVIDER INITIALIZATION:
```python
{sections['initialize_providers'][:2000] if sections['initialize_providers'] else 'NOT FOUND'}
```

REVIEW TASKS:

1. **Architecture Review**:
   - Проверить правильность интеграции 10 DeepSeek tools
   - Оценить структуру кода и организацию
   - Найти дублирование кода (DRY principle violations)
   - Проверить dependency management

2. **DeepSeek Agent Auto-Start**:
   - Проверить инициализацию DeepSeek Agent при старте MCP сервера
   - Убедиться что API ключи загружаются правильно (KeyManager → encrypted_secrets.json)
   - Проверить error handling при недоступности ключей
   - Предложить правильную реализацию авто-запуска

3. **Security & Best Practices**:
   - Проверить безопасность загрузки API ключей
   - Проверить error handling во всех 10 DeepSeek tools
   - Найти потенциальные memory leaks
   - Проверить async/await patterns

4. **Performance & Optimization**:
   - Найти узкие места производительности
   - Проверить правильность использования async операций
   - Предложить оптимизации для больших кодовых баз

5. **Testing & Reliability**:
   - Оценить тестируемость кода
   - Найти edge cases без обработки
   - Предложить улучшения для reliability

6. **Provider Configuration**:
   - Проверить конфигурацию DeepSeek провайдера (priority, timeout, rate_limit)
   - Сравнить с Perplexity провайдером
   - Предложить оптимальные настройки

RETURN COMPREHENSIVE ANALYSIS:

Return structured JSON with the following sections:
{{
  "overall_score": 0-100,
  "architecture": {{
    "score": 0-100,
    "issues": ["list of issues"],
    "recommendations": ["list of improvements"]
  }},
  "deepseek_integration": {{
    "score": 0-100,
    "tools_quality": "assessment of 10 tools",
    "issues": ["list of issues"],
    "auto_start_correct": true/false,
    "auto_start_recommendations": ["how to properly implement auto-start"]
  }},
  "security": {{
    "score": 0-100,
    "key_management": "assessment",
    "vulnerabilities": ["list of security issues"],
    "recommendations": ["security improvements"]
  }},
  "performance": {{
    "score": 0-100,
    "bottlenecks": ["identified bottlenecks"],
    "optimizations": ["performance improvements"]
  }},
  "code_quality": {{
    "score": 0-100,
    "dry_violations": ["DRY principle violations"],
    "error_handling": "assessment",
    "async_patterns": "assessment"
  }},
  "critical_issues": ["list of CRITICAL issues requiring immediate fix"],
  "quick_wins": ["list of easy improvements with high impact"],
  "long_term_improvements": ["strategic improvements for future"],
  "final_verdict": "comprehensive summary and recommendations"
}}

Be extremely thorough and critical. Find everything that can be improved.
"""

        print("🚀 Sending MCP Server code to DeepSeek Agent for deep analysis...")
        print("   (This may take 30-60 seconds for comprehensive review)")
        print()
        
        # Отправляем на анализ
        analysis, tokens_used = await agent.generate_code(
            prompt=review_prompt,
            context={
                "review_type": "mcp_server_comprehensive",
                "total_lines": total_lines,
                "total_chars": total_chars,
                "deepseek_tools": 10
            }
        )
        
        print("=" * 80)
        print("📊 DeepSeek Agent Analysis Complete")
        print("=" * 80)
        print(f"Tokens used: {tokens_used:,}")
        print()
        
        print("=" * 80)
        print("🔍 DEEPSEEK AGENT REVIEW RESULTS")
        print("=" * 80)
        print()
        print(analysis)
        print()
        print("=" * 80)
        
        # Сохраняем результаты
        results_file = Path(__file__).parent / "DEEPSEEK_MCP_SERVER_REVIEW.md"
        with open(results_file, 'w', encoding='utf-8') as f:
            f.write(f"""# DeepSeek Agent: MCP Server Code Review
## Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Метрики MCP Server
- **Строк кода**: {total_lines:,}
- **Символов**: {total_chars:,}
- **DeepSeek tools**: 10 (3 basic + 7 specialized)
- **Perplexity tools**: 47
- **Total MCP tools**: 57
- **Tokens использовано**: {tokens_used:,}

## Результаты анализа

{analysis}

---
*Анализ проведён DeepSeek Agent v3*
""")
        
        print(f"✅ Full review saved to: {results_file.name}")
        print()
        
        # Пытаемся распарсить JSON для красивого вывода
        try:
            import json
            import re
            
            # Ищем JSON в ответе
            json_match = re.search(r'\{[\s\S]*\}', analysis)
            if json_match:
                review_data = json.loads(json_match.group())
                
                print("=" * 80)
                print("📈 SUMMARY SCORES")
                print("=" * 80)
                print(f"Overall Score:        {review_data.get('overall_score', 'N/A')}/100")
                print(f"Architecture:         {review_data.get('architecture', {}).get('score', 'N/A')}/100")
                print(f"DeepSeek Integration: {review_data.get('deepseek_integration', {}).get('score', 'N/A')}/100")
                print(f"Security:             {review_data.get('security', {}).get('score', 'N/A')}/100")
                print(f"Performance:          {review_data.get('performance', {}).get('score', 'N/A')}/100")
                print(f"Code Quality:         {review_data.get('code_quality', {}).get('score', 'N/A')}/100")
                print()
                
                # Critical issues
                critical = review_data.get('critical_issues', [])
                if critical:
                    print("🚨 CRITICAL ISSUES:")
                    for i, issue in enumerate(critical, 1):
                        print(f"  {i}. {issue}")
                    print()
                
                # Quick wins
                quick_wins = review_data.get('quick_wins', [])
                if quick_wins:
                    print("⚡ QUICK WINS (High Impact, Low Effort):")
                    for i, win in enumerate(quick_wins, 1):
                        print(f"  {i}. {win}")
                    print()
                
                # Auto-start recommendations
                auto_start = review_data.get('deepseek_integration', {}).get('auto_start_recommendations', [])
                if auto_start:
                    print("🔧 AUTO-START RECOMMENDATIONS:")
                    for i, rec in enumerate(auto_start, 1):
                        print(f"  {i}. {rec}")
                    print()
                
                print("=" * 80)
        except:
            pass  # JSON parsing failed, full text already printed
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import required modules: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Review failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    from datetime import datetime
    
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "    🤖 DeepSeek Agent: MCP Server Comprehensive Code Review".ljust(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    success = asyncio.run(deepseek_review_mcp_server())
    
    if success:
        print()
        print("✅ DeepSeek Agent review completed successfully!")
        print("📄 Check DEEPSEEK_MCP_SERVER_REVIEW.md for full analysis")
    else:
        print()
        print("❌ Review failed. Check errors above.")
    
    sys.exit(0 if success else 1)
