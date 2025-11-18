#!/usr/bin/env python3
"""
🔬 DeepSeek AI: Проверка применённых исправлений
Повторный аудит безопасности после CRITICAL FIXES
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


def verify_fixes():
    """
    DeepSeek AI проверяет применённые исправления
    """
    print("\n" + "=" * 80)
    print("🔬 DEEPSEEK AI: ПРОВЕРКА ПРИМЕНЁННЫХ ИСПРАВЛЕНИЙ")
    print("=" * 80)
    
    # Read updated configurations and new modules
    mcp_file = project_root / ".vscode" / "mcp.json"
    validation_file = project_root / "mcp-server" / "input_validation.py"
    retry_file = project_root / "mcp-server" / "retry_handler.py"
    fixes_report = project_root / "CRITICAL_FIXES_REPORT.json"
    
    # Check if files exist
    files_status = {
        "mcp.json": mcp_file.exists(),
        "input_validation.py": validation_file.exists(),
        "retry_handler.py": retry_file.exists(),
        "CRITICAL_FIXES_REPORT.json": fixes_report.exists()
    }
    
    print("\n📁 Проверка файлов:")
    for file, exists in files_status.items():
        status = "✅" if exists else "❌"
        print(f"   {status} {file}")
    
    if not all(files_status.values()):
        print("\n❌ Не все файлы найдены!")
        return {"status": "error", "message": "Missing files"}
    
    # Read files
    with open(mcp_file, 'r', encoding='utf-8') as f:
        mcp_config = f.read()
    
    with open(validation_file, 'r', encoding='utf-8') as f:
        validation_code = f.read()
    
    with open(retry_file, 'r', encoding='utf-8') as f:
        retry_code = f.read()
    
    with open(fixes_report, 'r', encoding='utf-8') as f:
        fixes_data = json.load(f)
    
    verification_prompt = f"""
# DeepSeek AI: Verification of Applied Critical Fixes

Ты провёл критический аудит и нашёл 5 критических проблем (Grade C - 72/100).
Твои 3 IMMEDIATE FIXES были применены:

## ✅ Applied Fixes:

### Fix #1: API Keys Security (Priority 10/10)
**Status:** APPLIED ✅
**Action:** Удалены hardcoded API ключи из mcp.json

### Fix #2: Input Validation (Priority 9/10)
**Status:** APPLIED ✅
**Action:** Создан модуль input_validation.py с комплексной валидацией

### Fix #3: Retry Mechanism (Priority 8/10)
**Status:** APPLIED ✅
**Action:** Создан модуль retry_handler.py с exponential backoff

---

## 📋 Updated mcp.json (первые 1500 символов):
```jsonc
{mcp_config[:1500]}
```

## 📋 input_validation.py (первые 2000 символов):
```python
{validation_code[:2000]}
```

## 📋 retry_handler.py (первые 2000 символов):
```python
{retry_code[:2000]}
```

## 📊 Fixes Report:
```json
{json.dumps(fixes_data, indent=2)}
```

---

## ЗАДАЧА: Критическая проверка применённых исправлений

Проверь **ВСЕ АСПЕКТЫ** исправлений и дай **ЧЕСТНУЮ ОЦЕНКУ**:

### 1. 🔐 **БЕЗОПАСНОСТЬ API КЛЮЧЕЙ**
- Действительно ли ключи удалены из mcp.json?
- Правильно ли используются environment variables?
- Нет ли других мест, где ключи могут быть в plain text?
- Достаточно ли этого исправления? ⭐ ОЦЕНКА: 0-10

### 2. 🛡️ **ВАЛИДАЦИЯ ВХОДНЫХ ДАННЫХ**
- Покрывает ли валидация ВСЕ векторы атак?
- Правильно ли написаны regex patterns?
- Нет ли способов обойти валидацию?
- Достаточно ли строгие ограничения?
- Есть ли ложные срабатывания (false positives)?
- ⭐ ОЦЕНКА: 0-10

### 3. 🔄 **RETRY МЕХАНИЗМ**
- Корректно ли реализован exponential backoff?
- Правильно ли обрабатываются исключения?
- Нет ли бесконечных циклов retry?
- Достаточно ли логирования?
- Работает ли и с async, и с sync функциями?
- ⭐ ОЦЕНКА: 0-10

### 4. 📊 **АРХИТЕКТУРА И ИНТЕГРАЦИЯ**
- Как эти модули интегрируются в существующий код?
- Нужны ли изменения в server.py для использования?
- Не сломали ли мы что-то исправлениями?
- Есть ли конфликты с существующим кодом?

### 5. 🔍 **НОВЫЕ УЯЗВИМОСТИ**
- Не создали ли мы НОВЫЕ уязвимости исправлениями?
- Есть ли потенциальные проблемы производительности?
- Корректно ли обрабатываются edge cases?

### 6. 📈 **НОВАЯ ОЦЕНКА**
- Какая теперь оценка системы? (0-100)
- Какой Grade? (A+/A/B/C/D/F)
- Сколько осталось critical/high issues?
- Стоит ли развёртывать в production?

---

## Формат ответа (ОБЯЗАТЕЛЬНЫЙ JSON):

```json
{{
    "verification_summary": {{
        "timestamp": "2024-01-01 12:00:00",
        "fixes_verified": ["fix_1", "fix_2", "fix_3"],
        "all_fixes_correct": true/false,
        "critical_issues_found": 0
    }},
    "fix_1_api_keys_verification": {{
        "status": "CORRECT/INCORRECT/PARTIAL",
        "score": "0-10",
        "findings": [
            {{
                "issue": "описание проблемы (если есть)",
                "severity": "CRITICAL/HIGH/MEDIUM/LOW",
                "recommendation": "как исправить"
            }}
        ],
        "security_level": "EXCELLENT/GOOD/ACCEPTABLE/POOR",
        "ready_for_production": true/false
    }},
    "fix_2_validation_verification": {{
        "status": "CORRECT/INCORRECT/PARTIAL",
        "score": "0-10",
        "coverage": "% покрытия векторов атак",
        "findings": [
            {{
                "issue": "описание",
                "severity": "CRITICAL/HIGH/MEDIUM/LOW",
                "attack_vector": "какая атака возможна",
                "recommendation": "как исправить"
            }}
        ],
        "bypass_possible": true/false,
        "ready_for_production": true/false
    }},
    "fix_3_retry_verification": {{
        "status": "CORRECT/INCORRECT/PARTIAL",
        "score": "0-10",
        "findings": [
            {{
                "issue": "описание",
                "severity": "CRITICAL/HIGH/MEDIUM/LOW",
                "recommendation": "как исправить"
            }}
        ],
        "reliability_level": "EXCELLENT/GOOD/ACCEPTABLE/POOR",
        "ready_for_production": true/false
    }},
    "integration_analysis": {{
        "requires_server_changes": true/false,
        "breaking_changes": [],
        "migration_steps": ["шаг 1", "шаг 2"],
        "estimated_integration_time": "часы/дни"
    }},
    "new_vulnerabilities": [
        {{
            "vulnerability": "описание новой уязвимости",
            "severity": "CRITICAL/HIGH/MEDIUM/LOW",
            "introduced_by": "fix_1/fix_2/fix_3",
            "mitigation": "как устранить"
        }}
    ],
    "remaining_issues": {{
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "total": 0
    }},
    "updated_assessment": {{
        "previous_score": 72,
        "new_score": "0-100",
        "previous_grade": "C",
        "new_grade": "A+/A/B/C/D/F",
        "improvement": "+X points",
        "confidence": "HIGH/MEDIUM/LOW"
    }},
    "production_readiness": {{
        "ready": true/false,
        "blocking_issues": [],
        "recommended_next_steps": [],
        "risk_level": "LOW/MEDIUM/HIGH/CRITICAL"
    }},
    "code_quality_review": {{
        "input_validation_py": {{
            "score": "0-10",
            "issues": [],
            "best_practices": true/false
        }},
        "retry_handler_py": {{
            "score": "0-10",
            "issues": [],
            "best_practices": true/false
        }}
    }},
    "final_verdict": {{
        "overall_assessment": "EXCELLENT/GOOD/ACCEPTABLE/NEEDS_WORK/FAILED",
        "recommendation": "DEPLOY/FIX_ISSUES/MAJOR_REFACTOR/START_OVER",
        "detailed_summary": "Подробный вывод на русском языке"
    }}
}}
```

**ВАЖНО:**
- Будь **МАКСИМАЛЬНО КРИТИЧНЫМ** - это проверка твоих же рекомендаций!
- Если найдёшь проблемы - **ЧЕСТНО** укажи их
- Не бойся поставить низкую оценку, если есть проблемы
- Проверь **КАЖДУЮ СТРОКУ КОДА** на корректность
- Дай **КОНКРЕТНЫЕ** рекомендации по улучшению

Это **PRODUCTION SECURITY AUDIT** - требуется абсолютная честность! 🔒
"""
    
    print("\n📤 Отправка запроса DeepSeek AI для проверки...")
    print("   (это займёт 30-60 секунд - DeepSeek проводит детальную проверку)")
    
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
                            "content": "You are DeepSeek Coder, a world-class security auditor and code reviewer. You are verifying your own recommendations and must be BRUTALLY HONEST about any problems. If something is wrong - say it directly. Provide detailed JSON responses with specific findings."
                        },
                        {
                            "role": "user",
                            "content": verification_prompt
                        }
                    ],
                    "temperature": 0.2,  # Lower temperature for more precise verification
                    "max_tokens": 6000,
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
            print("\n🔬 DeepSeek AI: Verification Report\n")
            print(response_text)
            print("\n" + "=" * 80)
            
            # Try to parse JSON
            try:
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    json_data = json.loads(json_match.group(1))
                    print("\n📊 Structured Verification Results:")
                    print(json.dumps(json_data, indent=2, ensure_ascii=False))
                    
                    # Save structured data
                    output_file = project_root / "DEEPSEEK_FIXES_VERIFICATION.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=2, ensure_ascii=False)
                    print(f"\n💾 Verification results saved: {output_file}")
                    
                    # Print summary
                    print("\n" + "=" * 80)
                    print("📊 SUMMARY")
                    print("=" * 80)
                    
                    assessment = json_data.get('updated_assessment', {})
                    print(f"\n🎯 Previous Score: {assessment.get('previous_score', 72)}/100 ({assessment.get('previous_grade', 'C')})")
                    print(f"🎯 New Score: {assessment.get('new_score', '?')}/100 ({assessment.get('new_grade', '?')})")
                    print(f"📈 Improvement: {assessment.get('improvement', '?')}")
                    
                    prod_ready = json_data.get('production_readiness', {})
                    ready_icon = "✅" if prod_ready.get('ready', False) else "⚠️"
                    print(f"\n{ready_icon} Production Ready: {prod_ready.get('ready', False)}")
                    print(f"🎚️  Risk Level: {prod_ready.get('risk_level', 'UNKNOWN')}")
                    
                    remaining = json_data.get('remaining_issues', {})
                    print(f"\n🔴 Critical Issues: {remaining.get('critical', 0)}")
                    print(f"🟠 High Priority: {remaining.get('high', 0)}")
                    print(f"🟡 Medium Priority: {remaining.get('medium', 0)}")
                    
                    verdict = json_data.get('final_verdict', {})
                    print(f"\n⚖️  Final Verdict: {verdict.get('overall_assessment', 'UNKNOWN')}")
                    print(f"📋 Recommendation: {verdict.get('recommendation', 'UNKNOWN')}")
                    
            except Exception as e:
                print(f"\n⚠️  Could not parse JSON: {e}")
            
            # Save raw response
            output_file = project_root / "DEEPSEEK_FIXES_VERIFICATION.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# DeepSeek AI: Verification of Applied Fixes\n\n")
                f.write(f"**Agent:** deepseek-coder\n")
                f.write(f"**Execution Time:** {execution_time:.2f}s\n")
                f.write(f"**Tokens:** {tokens_used.get('total_tokens', 0)}\n")
                f.write(f"**Date:** {os.popen('date /t').read().strip()} {os.popen('time /t').read().strip()}\n\n")
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
    print("\n🚀 Starting DeepSeek Fixes Verification...")
    result = verify_fixes()
    
    if result["status"] == "success":
        print("\n" + "=" * 80)
        print("✅ ПРОВЕРКА ЗАВЕРШЕНА!")
        print("=" * 80)
        print("\n🎯 Next Steps:")
        print("   1. Review DEEPSEEK_FIXES_VERIFICATION.md")
        print("   2. Apply any additional recommendations")
        print("   3. Re-test if needed")
        print("   4. Continue with SHORT-TERM improvements")
    else:
        print("\n❌ Verification failed.")
        sys.exit(1)
