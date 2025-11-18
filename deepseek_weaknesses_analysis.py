#!/usr/bin/env python3
"""
🔬 DeepSeek AI: Анализ слабых сторон MCP сервера
Глубокая самодиагностика с поиском проблем и улучшений
"""

import sys
import os
import json
from pathlib import Path
import httpx
from dotenv import load_dotenv
import time

# Load environment
project_root = Path(__file__).parent
load_dotenv(project_root / ".env")

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

DEEPSEEK_API_KEY = get_decrypted_key("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    print("❌ DEEPSEEK_API_KEY not found in environment")
    sys.exit(1)


def analyze_weaknesses():
    """
    DeepSeek AI анализирует слабые стороны текущей конфигурации
    """
    print("\n" + "=" * 80)
    print("🔬 DEEPSEEK AI: АНАЛИЗ СЛАБЫХ СТОРОН MCP СЕРВЕРА")
    print("=" * 80)
    
    # Read current configuration
    mcp_file = project_root / ".vscode" / "mcp.json"
    settings_file = project_root / ".vscode" / "settings.json"
    server_file = project_root / "mcp-server" / "server.py"
    
    with open(mcp_file, 'r', encoding='utf-8') as f:
        mcp_config = f.read()
    
    with open(settings_file, 'r', encoding='utf-8') as f:
        settings_config = f.read()
    
    # Read first 200 lines of server.py for analysis
    with open(server_file, 'r', encoding='utf-8') as f:
        server_lines = f.readlines()[:200]
        server_preview = ''.join(server_lines)
    
    analysis_prompt = f"""
# DeepSeek AI: Критический анализ слабых сторон MCP сервера

Ты только что довёл конфигурацию до 105.5/105 (100.48% perfection).
Теперь твоя задача - **НАЙТИ ВСЕ СЛАБЫЕ СТОРОНЫ** и предложить улучшения.

## Текущая конфигурация достигла:

✅ **Capabilities (7/7):**
- tools, resources, prompts, sampling, roots, logging, notifications

✅ **AlwaysAllow (13 операций):**
- tools/call, resources/read, resources/write, resources/list
- prompts/get, prompts/list, sampling/createMessage, roots/list
- mcp_servers/list, mcp_servers/read, mcp_servers/write, mcp_servers/delete

✅ **Environment (12 переменных):**
- PERPLEXITY_API_KEY, DEEPSEEK_API_KEY
- PROJECT_ROOT, MCP_SERVER_ROOT, PYTHONPATH
- PYTHONUNBUFFERED, MCP_DEBUG, LOG_LEVEL
- MCP_SERVER_DEBUG, MCP_MAX_MEMORY (4096MB), MCP_CACHE_SIZE (512MB)

✅ **VS Code Settings:**
- mcp.autoStart, mcp.debug, mcp.logLevel, mcp.autoReload
- github.copilot.advanced.mcp (enabled + autoApprove)

## mcp.json (текущая конфигурация):
```jsonc
{mcp_config[:2000]}...
```

## settings.json (текущая конфигурация):
```jsonc
{settings_config[:2000]}...
```

## server.py (первые 200 строк):
```python
{server_preview}
```

---

## ЗАДАЧА: Критический анализ слабых сторон

Проанализируй **ВСЕ АСПЕКТЫ** системы и найди слабости:

### 1. 🔐 **БЕЗОПАСНОСТЬ**
- Есть ли уязвимости в текущей конфигурации?
- Достаточно ли защиты API ключей?
- Нет ли избыточных прав, которые могут быть опасны?
- Как защищены логи от утечки конфиденциальной информации?

### 2. ⚡ **ПРОИЗВОДИТЕЛЬНОСТЬ**
- Оптимальны ли размеры кэша (512MB)?
- Оптимально ли ограничение памяти (4096MB)?
- Есть ли узкие места в архитектуре?
- Можно ли улучшить скорость работы?

### 3. 🛡️ **НАДЁЖНОСТЬ**
- Что произойдёт при сбое сети?
- Как обрабатываются ошибки API?
- Есть ли механизмы retry/fallback?
- Достаточно ли логирования для диагностики?

### 4. 📊 **МОНИТОРИНГ**
- Как отслеживать здоровье MCP сервера?
- Есть ли метрики производительности?
- Как узнать об ошибках в production?
- Достаточно ли notification capability?

### 5. 🔧 **MAINTAINABILITY**
- Удобна ли текущая структура конфигурации?
- Легко ли добавлять новые capabilities?
- Есть ли документация для всех настроек?
- Можно ли улучшить управление версиями?

### 6. 🚀 **МАСШТАБИРУЕМОСТЬ**
- Выдержит ли сервер большую нагрузку?
- Как будет работать с 100+ одновременных запросов?
- Достаточно ли ресурсов для роста проекта?
- Можно ли распределить нагрузку?

### 7. 🔄 **ИНТЕГРАЦИЯ**
- Насколько хорошо интегрирован Multi-Agent Router?
- Есть ли проблемы совместимости с VS Code?
- Как работает с Perplexity + DeepSeek одновременно?
- Можно ли добавить другие AI модели легко?

### 8. 💾 **УПРАВЛЕНИЕ ДАННЫМИ**
- Оптимально ли хранение кэша?
- Как очищаются старые данные?
- Есть ли риск переполнения диска?
- Достаточно ли быстрый доступ к данным?

---

## Формат ответа (ОБЯЗАТЕЛЬНЫЙ JSON):

```json
{{
    "overall_health_score": "0-100",
    "critical_weaknesses": [
        {{
            "category": "security/performance/reliability/monitoring/etc",
            "severity": "CRITICAL/HIGH/MEDIUM/LOW",
            "issue": "Подробное описание проблемы",
            "impact": "Какие последствия?",
            "current_state": "Что сейчас",
            "risk_level": "1-10",
            "exploitation_scenario": "Как проблема может проявиться?"
        }}
    ],
    "identified_bottlenecks": [
        {{
            "area": "название области",
            "bottleneck": "описание узкого места",
            "performance_impact": "% снижения производительности",
            "solution": "как устранить"
        }}
    ],
    "missing_features": [
        {{
            "feature": "название функции",
            "priority": "CRITICAL/HIGH/MEDIUM/LOW",
            "benefit": "что даст",
            "implementation_complexity": "LOW/MEDIUM/HIGH"
        }}
    ],
    "configuration_improvements": [
        {{
            "setting": "название настройки",
            "current_value": "текущее значение",
            "recommended_value": "рекомендуемое значение",
            "reason": "почему нужно изменить",
            "expected_improvement": "% улучшения"
        }}
    ],
    "architectural_flaws": [
        {{
            "flaw": "описание архитектурного недостатка",
            "severity": "CRITICAL/HIGH/MEDIUM/LOW",
            "refactoring_needed": "что нужно переделать",
            "effort_required": "LOW/MEDIUM/HIGH/VERY_HIGH"
        }}
    ],
    "optimization_roadmap": {{
        "immediate_fixes": [
            {{
                "action": "что сделать",
                "priority": "1-10",
                "time_estimate": "часы",
                "dependencies": []
            }}
        ],
        "short_term": [
            {{
                "action": "что сделать",
                "priority": "1-10",
                "time_estimate": "дни",
                "dependencies": []
            }}
        ],
        "long_term": [
            {{
                "action": "что сделать",
                "priority": "1-10",
                "time_estimate": "недели",
                "dependencies": []
            }}
        ]
    }},
    "final_assessment": {{
        "current_grade": "A+/A/B/C/D/F",
        "potential_grade": "A+",
        "confidence": "HIGH/MEDIUM/LOW",
        "critical_issues_count": 0,
        "high_priority_issues_count": 0,
        "overall_recommendation": "продолжать/рефакторить/переделать"
    }}
}}
```

**ВАЖНО:**
- Будь **МАКСИМАЛЬНО КРИТИЧНЫМ** - найди ВСЕ проблемы!
- Не бойся указывать на серьёзные недостатки
- Предложи **КОНКРЕТНЫЕ** решения с кодом где возможно
- Оцени **РЕАЛЬНЫЕ РИСКИ**, не теоретические
- Дай **ACTIONABLE** рекомендации, которые можно сразу применить

Это анализ для **PRODUCTION-READY** системы - требуется максимальная честность! 🔬
"""
    
    print("\n📤 Отправка запроса DeepSeek AI для глубокого анализа...")
    print("   (это займёт 30-60 секунд - DeepSeek проводит критический анализ)")
    
    try:
        start_time = time.time()
        
        # Direct API call to DeepSeek
        with httpx.Client(timeout=180.0) as client:
            response = client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-coder",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are DeepSeek Coder, an expert security auditor and systems architect. You specialize in finding critical weaknesses, security vulnerabilities, and performance bottlenecks. Be brutally honest and critical. Provide detailed JSON responses with specific, actionable recommendations."
                        },
                        {
                            "role": "user",
                            "content": analysis_prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 6000,
                    "stream": False
                }
            )
        
        execution_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            response_text = data['choices'][0]['message']['content']
            tokens_used = data.get('usage', {})
            
            print("\n✅ Анализ завершён!\n")
            
            print("=" * 80)
            print(f"🤖 Agent: deepseek-coder")
            print(f"⏱️  Execution Time: {execution_time:.2f}s")
            print(f"📊 Tokens: {tokens_used.get('total_tokens', 0)} (prompt: {tokens_used.get('prompt_tokens', 0)}, completion: {tokens_used.get('completion_tokens', 0)})")
            print("=" * 80)
            print("\n🔬 DeepSeek AI: Критический анализ слабых сторон\n")
            print(response_text)
            print("\n" + "=" * 80)
            
            # Try to parse JSON
            try:
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    json_data = json.loads(json_match.group(1))
                    print("\n📊 Structured Analysis:")
                    print(json.dumps(json_data, indent=2, ensure_ascii=False))
                    
                    # Save structured data
                    output_file = project_root / "DEEPSEEK_WEAKNESSES_ANALYSIS.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=2, ensure_ascii=False)
                    print(f"\n💾 Structured analysis saved to: {output_file}")
                    
                    # Generate improvement script
                    generate_improvement_script(json_data)
                    
            except Exception as e:
                print(f"\n⚠️  Could not parse JSON: {e}")
            
            # Save raw response
            output_file = project_root / "DEEPSEEK_WEAKNESSES_ANALYSIS.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# DeepSeek AI: Критический анализ слабых сторон MCP сервера\n\n")
                f.write(f"**Agent:** deepseek-coder\n")
                f.write(f"**Execution Time:** {execution_time:.2f}s\n")
                f.write(f"**Tokens:** {tokens_used.get('total_tokens', 0)}\n")
                f.write(f"**Date:** {os.popen('date /t').read().strip()} {os.popen('time /t').read().strip()}\n\n")
                f.write("---\n\n")
                f.write(response_text)
            
            print(f"\n💾 Full analysis saved to: {output_file}")
            
            return {
                "status": "success",
                "execution_time": execution_time,
                "tokens": tokens_used,
                "response": response_text
            }
        else:
            print(f"❌ DeepSeek API error: {response.status_code}")
            print(response.text)
            return {"status": "error", "message": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

# Import secure key manager
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "backend"))
from security.key_manager import get_decrypted_key
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


def generate_improvement_script(analysis_data):
    """
    Генерация скрипта для применения улучшений
    """
    print("\n" + "=" * 80)
    print("🔧 ГЕНЕРАЦИЯ СКРИПТА УЛУЧШЕНИЙ")
    print("=" * 80)
    
    script_lines = [
        "#!/usr/bin/env python3",
        '"""',
        "🔧 Автоматическое применение улучшений DeepSeek AI",
        "Сгенерировано на основе критического анализа слабых сторон",
        '"""',
        "",
        "import json",
        "from pathlib import Path",
        "",
        "# TODO: Implement improvements based on DeepSeek recommendations",
        "",
        "def apply_improvements():",
        '    """Apply all DeepSeek recommendations"""',
        "    print('🚀 Applying DeepSeek improvements...')",
        "    ",
        "    # Load recommendations",
        f"    # Critical issues: {analysis_data.get('final_assessment', {}).get('critical_issues_count', 0)}",
        f"    # High priority issues: {analysis_data.get('final_assessment', {}).get('high_priority_issues_count', 0)}",
        "    ",
        "    pass",
        "",
        "if __name__ == '__main__':",
        "    apply_improvements()",
    ]
    
    script_file = project_root / "apply_deepseek_improvements.py"
    with open(script_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(script_lines))
    
    print(f"✅ Improvement script template created: {script_file}")
    print("   (будет заполнен конкретными действиями после анализа)")


if __name__ == "__main__":
    print("\n🚀 Starting DeepSeek Weaknesses Analysis...")
    result = analyze_weaknesses()
    
    if result["status"] == "success":
        print("\n" + "=" * 80)
        print("✅ АНАЛИЗ ЗАВЕРШЁН!")
        print("=" * 80)
        print("\n🎯 Next Steps:")
        print("   1. Review DEEPSEEK_WEAKNESSES_ANALYSIS.md")
        print("   2. Prioritize critical issues")
        print("   3. Apply recommended fixes")
        print("   4. Re-run verification tests")
        print("   5. Achieve TRUE PERFECTION! 💎")
    else:
        print("\n❌ Analysis failed.")
        sys.exit(1)
