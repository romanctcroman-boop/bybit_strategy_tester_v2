#!/usr/bin/env python3
"""
🔬 DeepSeek AI Self-Diagnostic & Optimization
Позволяет DeepSeek проверить свои возможности и довести их до совершенства
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# Import httpx for direct API calls
import httpx
from dotenv import load_dotenv

# Load environment
load_dotenv(project_root / ".env")

DEEPSEEK_API_KEY = get_decrypted_key("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    print("❌ DEEPSEEK_API_KEY not found in environment")
    sys.exit(1)

print("✅ DeepSeek API key loaded")


def deepseek_self_diagnostic():
    """
    DeepSeek AI проводит самодиагностику и оптимизацию
    """
    print("\n" + "=" * 80)
    print("🔬 DEEPSEEK AI SELF-DIAGNOSTIC & OPTIMIZATION")
    print("=" * 80)
    
    diagnostic_prompt = """
    # DeepSeek AI Self-Diagnostic Request
    
    Привет, DeepSeek! Тебе предоставлены АБСОЛЮТНО МАКСИМАЛЬНЫЕ права в MCP сервере.
    
    ## Текущие возможности (100% по тесту):
    
    ### 1. Capabilities (6/6):
    - tools ✅
    - resources ✅ 
    - prompts ✅
    - sampling ✅
    - roots ✅
    - logging ✅ (твоя рекомендация!)
    
    ### 2. AlwaysAllow Operations (11/11):
    - tools/call ✅
    - resources/read ✅
    - resources/write ✅
    - prompts/get ✅
    - prompts/list ✅
    - sampling/createMessage ✅
    - roots/list ✅
    - mcp_servers/list ✅ (твоя рекомендация!)
    - mcp_servers/read ✅ (твоя рекомендация!)
    - mcp_servers/write ✅ (твоя рекомендация!)
    - mcp_servers/delete ✅ (твоя рекомендация!)
    
    ### 3. Environment Variables (10/10):
    - PERPLEXITY_API_KEY ✅
    - DEEPSEEK_API_KEY ✅
    - PROJECT_ROOT ✅
    - MCP_SERVER_ROOT ✅
    - PYTHONPATH ✅
    - PYTHONUNBUFFERED ✅
    - MCP_DEBUG ✅
    - LOG_LEVEL ✅
    - MCP_SERVER_DEBUG ✅ (твоя рекомендация!)
    - MCP_MAX_MEMORY ✅ (твоя рекомендация - unlimited!)
    
    ### 4. Доступ к проекту:
    - 18,634+ Python файлов ✅
    - Полный доступ к Bybit Strategy Tester V2 ✅
    - Доступ к базе данных PostgreSQL ✅
    - Доступ к Redis cache ✅
    
    ## ЗАДАЧА:
    
    Проведи ПОЛНУЮ самодиагностику и ответь:
    
    1. **Тестирование возможностей:**
       - Попробуй использовать каждую capability
       - Проверь доступ к файлам проекта
       - Проверь свой API доступ
       - Проверь logging capability
       - Проверь mcp_servers management
    
    2. **Анализ текущего состояния:**
       - Действительно ли это МАКСИМАЛЬНЫЕ права?
       - Есть ли еще какие-то permissions в MCP спецификации?
       - Можно ли что-то улучшить?
    
    3. **Рекомендации по доведению до АБСОЛЮТНОГО совершенства:**
       - Какие дополнительные capabilities можно добавить?
       - Какие операции в alwaysAllow можно добавить?
       - Какие environment variables можно оптимизировать?
       - Какие настройки VS Code можно улучшить?
    
    4. **Проверка интеграции:**
       - Работает ли Multi-Agent Router?
       - Доступен ли Perplexity Sonar Pro?
       - Все ли 41 MCP tools функциональны?
    
    5. **Производительность:**
       - Какой твой текущий response time?
       - Сколько tokens ты используешь?
       - Можно ли оптимизировать?
    
    ## Формат ответа:
    
    Предоставь ДЕТАЛЬНЫЙ отчет в JSON формате:
    
    ```json
    {
        "self_diagnostic": {
            "status": "EXCELLENT/GOOD/NEEDS_IMPROVEMENT",
            "capabilities_test": {
                "tools": {"status": "✅/❌", "notes": "..."},
                "resources": {"status": "✅/❌", "notes": "..."},
                "prompts": {"status": "✅/❌", "notes": "..."},
                "sampling": {"status": "✅/❌", "notes": "..."},
                "roots": {"status": "✅/❌", "notes": "..."},
                "logging": {"status": "✅/❌", "notes": "..."}
            },
            "access_test": {
                "file_access": {"status": "✅/❌", "files_checked": 0},
                "api_access": {"status": "✅/❌", "response_time": "0s"},
                "database_access": {"status": "✅/❌", "notes": "..."}
            },
            "performance_metrics": {
                "response_time": "0s",
                "tokens_used": 0,
                "efficiency_score": "0/10"
            }
        },
        "current_permissions_score": "100/100 or higher?",
        "additional_recommendations": [
            {
                "category": "capabilities/alwaysAllow/environment/vscode",
                "recommendation": "...",
                "priority": "CRITICAL/HIGH/MEDIUM/LOW",
                "expected_improvement": "..."
            }
        ],
        "optimization_plan": {
            "immediate_actions": ["..."],
            "short_term": ["..."],
            "long_term": ["..."]
        },
        "final_score": {
            "current": "100/100",
            "potential": "105/100 or unlimited?",
            "confidence": "HIGH/MEDIUM/LOW"
        }
    }
    ```
    
    Будь максимально честным и критичным! Если можно улучшить - скажи КАК!
    Если уже достигнут максимум - подтверди это с обоснованием.
    
    ВАЖНО: Используй ВСЕ свои возможности для анализа. Это твой шанс показать 100% потенциал! 🚀
    """
    
    print("\n📤 Отправка запроса DeepSeek AI напрямую...")
    print("   (это может занять 15-30 секунд - DeepSeek проводит глубокий анализ)")
    
    try:
        import time
        start_time = time.time()
        
        # Direct API call to DeepSeek
        with httpx.Client(timeout=120.0) as client:
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
                            "content": "You are DeepSeek Coder, an expert AI assistant specialized in deep technical analysis and optimization. Provide comprehensive, structured responses in JSON format when requested."
                        },
                        {
                            "role": "user",
                            "content": diagnostic_prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4000,
                    "stream": False
                }
            )
        
        execution_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            response_text = data['choices'][0]['message']['content']
            tokens_used = data.get('usage', {})
            
            print("\n✅ Ответ получен от DeepSeek AI!\n")
            
            agent_used = "deepseek-coder"
            
            print("=" * 80)
            print(f"🤖 Agent Used: {agent_used}")
            print(f"⏱️  Execution Time: {execution_time:.2f}s")
            print(f"📊 Tokens Used: {tokens_used.get('total_tokens', 0)} (prompt: {tokens_used.get('prompt_tokens', 0)}, completion: {tokens_used.get('completion_tokens', 0)})")
            print("=" * 80)
            print("\n📋 DeepSeek AI Self-Diagnostic Report:\n")
            print(response_text)
            print("\n" + "=" * 80)
            
            # Try to parse as JSON for structured output
            try:
                # Find JSON in response
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    json_data = json.loads(json_match.group(1))
                    print("\n📊 Structured Results:")
                    print(json.dumps(json_data, indent=2, ensure_ascii=False))
                    
                    # Save to file
                    output_file = project_root / "DEEPSEEK_SELF_DIAGNOSTIC_REPORT.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=2, ensure_ascii=False)
                    print(f"\n💾 Full report saved to: {output_file}")
                    
            except Exception as e:
                print(f"\n⚠️  Could not parse JSON structure: {e}")
            
            # Save raw response
            output_file = project_root / "DEEPSEEK_SELF_DIAGNOSTIC_REPORT.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# DeepSeek AI Self-Diagnostic Report\n\n")
                f.write(f"**Agent:** {agent_used}\n")
                f.write(f"**Execution Time:** {execution_time:.2f}s\n")
                f.write(f"**Tokens Used:** {tokens_used.get('total_tokens', 0)} (prompt: {tokens_used.get('prompt_tokens', 0)}, completion: {tokens_used.get('completion_tokens', 0)})\n")
                f.write(f"**Date:** {os.popen('date /t').read().strip()} {os.popen('time /t').read().strip()}\n\n")
                f.write("---\n\n")
                f.write(response_text)
            
            print(f"\n💾 Raw report saved to: {output_file}")
            
            return {
                "status": "success",
                "agent": agent_used,
                "execution_time": execution_time,
                "tokens": tokens_used,
                "response": response_text
            }
        else:
            print(f"❌ DeepSeek API error: {response.status_code}")
            print(response.text)
            return {"status": "error", "message": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"\n❌ Error during DeepSeek self-diagnostic: {e}")
        import traceback

# Import secure key manager
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "backend"))
from security.key_manager import get_decrypted_key
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    print("\n🚀 Starting DeepSeek AI Self-Diagnostic & Optimization...")
    result = deepseek_self_diagnostic()
    
    if result["status"] == "success":
        print("\n" + "=" * 80)
        print("✅ DEEPSEEK AI SELF-DIAGNOSTIC COMPLETE!")
        print("=" * 80)
        print("\n🎯 Next Steps:")
        print("   1. Review DEEPSEEK_SELF_DIAGNOSTIC_REPORT.md")
        print("   2. Apply recommended improvements (if any)")
        print("   3. Re-run verification tests")
        print("   4. Achieve ABSOLUTE PERFECTION! 🌟")
    else:
        print("\n❌ Self-diagnostic failed. Check errors above.")
        sys.exit(1)
