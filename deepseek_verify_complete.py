#!/usr/bin/env python3
"""
🔬 DeepSeek AI: ПОЛНАЯ проверка исправленных модулей
Отправляет ВСЕ файлы целиком (без обрезки)
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


def verify_complete_fixes():
    """
    DeepSeek AI проверяет ПОЛНЫЕ файлы (без обрезки)
    """
    print("\n" + "=" * 80)
    print("🔬 DEEPSEEK AI: ПОЛНАЯ ПРОВЕРКА (COMPLETE FILES)")
    print("=" * 80)
    
    # Read files
    validation_file = project_root / "mcp-server" / "input_validation.py"
    retry_file = project_root / "mcp-server" / "retry_handler.py"
    
    # Check existence
    if not validation_file.exists():
        print(f"❌ File not found: {validation_file}")
        return {"status": "error", "message": "input_validation.py not found"}
    
    if not retry_file.exists():
        print(f"❌ File not found: {retry_file}")
        return {"status": "error", "message": "retry_handler.py not found"}
    
    print("\n📁 Reading files:")
    
    with open(validation_file, 'r', encoding='utf-8') as f:
        validation_code = f.read()
    print(f"   ✅ input_validation.py ({len(validation_code)} chars)")
    
    with open(retry_file, 'r', encoding='utf-8') as f:
        retry_code = f.read()
    print(f"   ✅ retry_handler.py ({len(retry_code)} chars)")
    
    verification_prompt = f"""
# DeepSeek AI: ПОЛНАЯ ПРОВЕРКА исправленных модулей безопасности

Ты ранее провёл аудит и выявил критические проблемы безопасности.
Сейчас модули ПОЛНОСТЬЮ переписаны с нуля.

## 📋 ПОЛНЫЙ КОД input_validation.py ({len(validation_code)} символов):
```python
{validation_code}
```

---

## 📋 ПОЛНЫЙ КОД retry_handler.py ({len(retry_code)} символов):
```python
{retry_code}
```

---

## ЗАДАЧА: Критическая проверка ПОЛНЫХ модулей

### 1. 🛡️ **INPUT VALIDATION MODULE**

Проверь **КАЖДЫЙ АСПЕКТ**:

✅ **Полнота кода:**
- Код ЗАВЕРШЁН или обрывается?
- Все методы реализованы полностью?
- Есть ли syntax errors?

✅ **Безопасность:**
- SQL injection защита (case-insensitive?)
- XSS защита (все векторы?)
- Path traversal защита
- Command injection защита
- Regex DoS защита

✅ **Архитектура:**
- Правильная структура классов?
- Удобные convenience functions?
- Обработка ошибок?
- Правильные типы данных?

✅ **Тестируемость:**
- Можно ли легко протестировать?
- Есть ли edge cases?
- Правильные whitelist/blacklist?

**⭐ ОЦЕНКА input_validation.py: 0-10**

---

### 2. 🔄 **RETRY HANDLER MODULE**

Проверь **КАЖДЫЙ АСПЕКТ**:

✅ **Полнота кода:**
- Код ЗАВЕРШЁН или обрывается?
- Все методы реализованы?
- Есть ли syntax errors?

✅ **Функциональность:**
- Exponential backoff корректен?
- Jitter реализован правильно?
- Async и sync поддержка?
- Circuit breaker есть?

✅ **Обработка ошибок:**
- Правильные исключения?
- Логирование ошибок?
- Graceful degradation?

✅ **Конфигурация:**
- Гибкие настройки?
- Pre-configured profiles?
- Decorator support?

**⭐ ОЦЕНКА retry_handler.py: 0-10**

---

### 3. 📊 **ОБЩАЯ ОЦЕНКА СИСТЕМЫ**

После проверки ОБОИХ модулей:

- Какая НОВАЯ оценка MCP сервера? (0-100)
- Какой НОВЫЙ Grade? (A+/A/B/C/D/F)
- Сколько осталось critical issues? (0-X)
- Production ready? (YES/NO)
- Risk level? (LOW/MEDIUM/HIGH/CRITICAL)

---

## Формат ответа (ОБЯЗАТЕЛЬНЫЙ JSON):

```json
{{
    "verification_summary": {{
        "timestamp": "2024-01-01 12:00:00",
        "modules_verified": ["input_validation", "retry_handler"],
        "all_modules_complete": true/false,
        "critical_issues_found": 0
    }},
    "input_validation_review": {{
        "code_completeness": {{
            "status": "COMPLETE/INCOMPLETE",
            "percentage": "0-100%",
            "missing_parts": []
        }},
        "security_coverage": {{
            "sql_injection": "PROTECTED/VULNERABLE",
            "xss": "PROTECTED/VULNERABLE",
            "path_traversal": "PROTECTED/VULNERABLE",
            "command_injection": "PROTECTED/VULNERABLE",
            "case_insensitive": true/false,
            "regex_dos_safe": true/false
        }},
        "architecture_quality": {{
            "class_structure": "EXCELLENT/GOOD/POOR",
            "error_handling": "EXCELLENT/GOOD/POOR",
            "convenience_functions": true/false
        }},
        "score": "0-10",
        "issues": [
            {{
                "issue": "описание",
                "severity": "CRITICAL/HIGH/MEDIUM/LOW",
                "recommendation": "как исправить"
            }}
        ],
        "ready_for_production": true/false
    }},
    "retry_handler_review": {{
        "code_completeness": {{
            "status": "COMPLETE/INCOMPLETE",
            "percentage": "0-100%",
            "missing_parts": []
        }},
        "functionality_check": {{
            "exponential_backoff": "CORRECT/INCORRECT",
            "jitter_implementation": "CORRECT/INCORRECT",
            "async_support": true/false,
            "sync_support": true/false,
            "circuit_breaker": true/false
        }},
        "error_handling": {{
            "exceptions": "EXCELLENT/GOOD/POOR",
            "logging": "EXCELLENT/GOOD/POOR",
            "graceful_degradation": true/false
        }},
        "score": "0-10",
        "issues": [
            {{
                "issue": "описание",
                "severity": "CRITICAL/HIGH/MEDIUM/LOW",
                "recommendation": "как исправить"
            }}
        ],
        "ready_for_production": true/false
    }},
    "overall_assessment": {{
        "previous_score": 58,
        "new_score": "0-100",
        "previous_grade": "D",
        "new_grade": "A+/A/B/C/D/F",
        "improvement": "+X points",
        "critical_issues_remaining": 0
    }},
    "production_readiness": {{
        "ready": true/false,
        "blocking_issues": [],
        "risk_level": "LOW/MEDIUM/HIGH/CRITICAL",
        "confidence": "HIGH/MEDIUM/LOW"
    }},
    "recommendations": {{
        "immediate": [],
        "short_term": [],
        "long_term": []
    }},
    "final_verdict": {{
        "overall_assessment": "EXCELLENT/GOOD/ACCEPTABLE/NEEDS_WORK/FAILED",
        "recommendation": "DEPLOY/FIX_ISSUES/MAJOR_REFACTOR",
        "detailed_summary": "Подробный вывод на русском языке (3-5 предложений)"
    }}
}}
```

**ВАЖНО:**
- Проверь **КАЖДУЮ СТРОКУ** обоих модулей
- Убедись, что код НЕ ОБРЫВАЕТСЯ (как было раньше)
- Проверь **ВСЕ** методы на полноту реализации
- Будь **МАКСИМАЛЬНО ЧЕСТНЫМ** в оценке
- Это **PRODUCTION SECURITY AUDIT** - требуется абсолютная честность! 🔒

Если модули ДЕЙСТВИТЕЛЬНО полные и рабочие - поставь высокую оценку.
Если найдёшь проблемы - честно укажи их.
"""
    
    print("\n📤 Отправка ПОЛНЫХ файлов DeepSeek AI...")
    print("   (это может занять 60-90 секунд из-за большого объёма кода)")
    
    try:
        start_time = time.time()
        
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
                            "content": "You are DeepSeek Coder, a world-class security auditor. You are reviewing COMPLETE source code files (not truncated). Be HONEST: if code is complete and secure - say so. If there are issues - point them out specifically. Provide detailed JSON responses."
                        },
                        {
                            "role": "user",
                            "content": verification_prompt
                        }
                    ],
                    "temperature": 0.2,
                    "max_tokens": 8000,  # More tokens for detailed review
                    "stream": False
                }
            )
        
        execution_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            response_text = data['choices'][0]['message']['content']
            tokens_used = data.get('usage', {})
            
            print("\n✅ Проверка завершена!\n")
            
            print("=" * 80)
            print(f"🤖 Agent: deepseek-coder")
            print(f"⏱️  Execution Time: {execution_time:.2f}s")
            print(f"📊 Tokens: {tokens_used.get('total_tokens', 0)} (prompt: {tokens_used.get('prompt_tokens', 0)}, completion: {tokens_used.get('completion_tokens', 0)})")
            print("=" * 80)
            print("\n🔬 DeepSeek AI: COMPLETE Review\n")
            print(response_text)
            print("\n" + "=" * 80)
            
            # Parse JSON
            try:
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    json_data = json.loads(json_match.group(1))
                    print("\n📊 Structured Results:")
                    print(json.dumps(json_data, indent=2, ensure_ascii=False))
                    
                    # Save
                    output_file = project_root / "DEEPSEEK_COMPLETE_VERIFICATION.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=2, ensure_ascii=False)
                    print(f"\n💾 Results saved: {output_file}")
                    
                    # Summary
                    print("\n" + "=" * 80)
                    print("📊 FINAL SUMMARY")
                    print("=" * 80)
                    
                    assessment = json_data.get('overall_assessment', {})
                    print(f"\n🎯 Previous Score: {assessment.get('previous_score', 58)}/100 ({assessment.get('previous_grade', 'D')})")
                    print(f"🎯 New Score: {assessment.get('new_score', '?')}/100 ({assessment.get('new_grade', '?')})")
                    print(f"📈 Improvement: {assessment.get('improvement', '?')}")
                    
                    prod_ready = json_data.get('production_readiness', {})
                    ready_icon = "✅" if prod_ready.get('ready', False) else "⚠️"
                    print(f"\n{ready_icon} Production Ready: {prod_ready.get('ready', False)}")
                    print(f"🎚️  Risk Level: {prod_ready.get('risk_level', 'UNKNOWN')}")
                    print(f"🎯 Confidence: {prod_ready.get('confidence', 'UNKNOWN')}")
                    
                    verdict = json_data.get('final_verdict', {})
                    print(f"\n⚖️  Assessment: {verdict.get('overall_assessment', 'UNKNOWN')}")
                    print(f"📋 Recommendation: {verdict.get('recommendation', 'UNKNOWN')}")
                    
                    print(f"\n💬 Summary:")
                    print(f"   {verdict.get('detailed_summary', 'N/A')}")
                    
                    return json_data
                    
            except Exception as e:
                print(f"\n⚠️  Could not parse JSON: {e}")
            
            # Save raw
            output_file = project_root / "DEEPSEEK_COMPLETE_VERIFICATION.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# DeepSeek AI: Complete Verification\n\n")
                f.write(f"**Files Verified:** input_validation.py ({len(validation_code)} chars), retry_handler.py ({len(retry_code)} chars)\n")
                f.write(f"**Execution Time:** {execution_time:.2f}s\n")
                f.write(f"**Tokens:** {tokens_used.get('total_tokens', 0)}\n\n")
                f.write("---\n\n")
                f.write(response_text)
            
            print(f"\n💾 Full report saved: {output_file}")
            
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


if __name__ == "__main__":
    print("\n🚀 DeepSeek: Complete Files Verification...")
    result = verify_complete_fixes()
    
    if isinstance(result, dict) and result.get("status") == "success":
        print("\n" + "=" * 80)
        print("✅ ПОЛНАЯ ПРОВЕРКА ЗАВЕРШЕНА!")
        print("=" * 80)
    else:
        print("\n❌ Verification failed.")
        sys.exit(1)
