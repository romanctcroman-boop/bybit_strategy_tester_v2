"""
🔥 Multithreaded DeepSeek Code Review & Fix Generator
Использует ThreadPoolExecutor + 8 DeepSeek API ключей для параллельного анализа

Features:
- 7x critical issues analysis (parallel execution)
- Detailed fix plans generation
- Code review + refactoring recommendations
- Ready-to-apply code patches
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
from dotenv import load_dotenv
import time

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "deepseek_fix_plans"
OUTPUT_DIR.mkdir(exist_ok=True)

# Load 8 DeepSeek API keys
DEEPSEEK_KEYS = [
    os.getenv("DEEPSEEK_API_KEY"),
    os.getenv("DEEPSEEK_API_KEY_1"),
    os.getenv("DEEPSEEK_API_KEY_2"),
    os.getenv("DEEPSEEK_API_KEY_3"),
    os.getenv("DEEPSEEK_API_KEY_4"),
    os.getenv("DEEPSEEK_API_KEY_5"),
    os.getenv("DEEPSEEK_API_KEY_6"),
    os.getenv("DEEPSEEK_API_KEY_7"),
]
DEEPSEEK_KEYS = [k for k in DEEPSEEK_KEYS if k]

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MAX_WORKERS = min(7, len(DEEPSEEK_KEYS))  # 7 critical issues

print(f"🔑 Loaded {len(DEEPSEEK_KEYS)} DeepSeek API keys")
print(f"🚀 Max parallel workers: {MAX_WORKERS}")

# ═══════════════════════════════════════════════════════════════════════════
# CRITICAL ISSUES (from Perplexity audit)
# ═══════════════════════════════════════════════════════════════════════════

CRITICAL_ISSUES = [
    {
        "id": 1,
        "priority": "HIGH",
        "category": "Backend Tasks (Celery + async/await)",
        "problem": """
Неправильное использование async/await с Celery tasks.
Celery не поддерживает async def нативно.

Файл: backend/tasks/optimize_tasks.py (3KB)

Проблема:
- Использование async def для Celery tasks
- Отсутствие правильной интеграции с eventlet/gevent
- Возможны блокировки и неожиданное поведение
""",
        "task": """
Проведи глубокий code review backend/tasks/optimize_tasks.py:

1. Найди все async def Celery tasks
2. Проанализируй, действительно ли нужен async/await
3. Предложи рефакторинг:
   - Вариант A: конвертировать в sync функции
   - Вариант B: настроить Celery с eventlet/gevent workers
4. Сгенерируй готовый код-патч для применения
5. Оцени риски и breaking changes

Формат ответа: JSON с полями:
- analysis: детальный анализ проблемы
- current_code_issues: конкретные строки с проблемами
- refactoring_options: 2-3 варианта решения
- recommended_solution: лучший вариант с обоснованием
- code_patch: готовый код для замены
- migration_steps: пошаговый план миграции
- risks: потенциальные риски
- testing_strategy: как протестировать изменения
""",
        "files": ["backend/tasks/optimize_tasks.py"]
    },
    {
        "id": 2,
        "priority": "CRITICAL",
        "category": "Security (API Keys & Secrets)",
        "problem": """
Потенциальная утечка secrets в JSON файлах и неправильное хранение API ключей.

Файлы:
- backend/agents/deepseek.py (41KB)
- backend/agents/deepseek_cli.py (13KB)
- Multiple *_RESULTS.json files (145KB+)

Проблемы:
- Возможно hardcoded API ключи
- Нет secrets vault интеграции
- JSON файлы могут содержать чувствительные данные
""",
        "task": """
Проведи security audit API key management:

1. Проанализируй backend/agents/deepseek.py и deepseek_cli.py
2. Найди все места хранения/использования API ключей
3. Проверь JSON результаты на утечку secrets
4. Разработай secure architecture:
   - Environment variables best practices
   - Secrets rotation механизм
   - Encryption at rest
   - Audit logging
5. Создай implementation plan

Формат ответа: JSON с полями:
- security_audit: найденные уязвимости
- current_implementation: как сейчас работает
- threat_model: потенциальные атаки
- secure_architecture: новая архитектура
- code_changes: конкретные изменения кода
- secrets_management_strategy: как управлять ключами
- encryption_approach: шифрование данных
- compliance_checklist: требования безопасности
""",
        "files": ["backend/agents/deepseek.py", "backend/agents/deepseek_cli.py"]
    },
    {
        "id": 3,
        "priority": "HIGH",
        "category": "API Design (RESTful principles)",
        "problem": """
Неконсистентное именование API endpoints, нарушение RESTful принципов.

Файлы: backend/api/* (45 файлов)

Проблемы:
- Глагольное именование (/createBacktest, /getData)
- Несоответствие HTTP методов и действий
- Отсутствие версионирования API
""",
        "task": """
Проведи архитектурный review API endpoints:

1. Проанализируй все 45 файлов в backend/api/
2. Составь список нарушений RESTful принципов
3. Разработай новую naming convention
4. Создай migration plan для изменения API
5. Предложи backward compatibility strategy

Формат ответа: JSON с полями:
- current_api_analysis: анализ существующих endpoints
- violations: список нарушений RESTful
- naming_convention: новые правила именования
- endpoint_mapping: old -> new URLs
- http_method_corrections: исправления методов
- versioning_strategy: как версионировать API
- backward_compatibility: как не сломать клиентов
- migration_timeline: поэтапный план миграции
- documentation_updates: изменения в документации
""",
        "files": ["backend/api/"]
    },
    {
        "id": 4,
        "priority": "HIGH",
        "category": "Test Coverage",
        "problem": """
Неизвестный процент test coverage, отсутствие Coverage.py интеграции.

Файлы: tests/* (163 теста)

Проблемы:
- Нет автоматического измерения coverage
- Непонятно, какие части кода покрыты тестами
- Отсутствие CI/CD integration для coverage reports
""",
        "task": """
Разработай comprehensive testing strategy:

1. Проанализируй существующие 163 теста
2. Определи gaps в coverage (какие модули не покрыты)
3. Настрой Coverage.py integration
4. Создай CI/CD pipeline для coverage tracking
5. Установи target coverage метрики (80%+ рекомендуется)

Формат ответа: JSON с полями:
- current_tests_analysis: что тестируется сейчас
- coverage_gaps: непокрытые критичные модули
- coverage_setup: как настроить Coverage.py
- ci_cd_integration: интеграция с pytest + coverage
- target_metrics: целевые показатели (% по модулям)
- test_generation_plan: где нужны новые тесты
- critical_paths_to_test: приоритетные сценарии
- automation_strategy: автоматизация запуска тестов
""",
        "files": ["tests/", "pytest.ini", ".github/workflows/"]
    },
    {
        "id": 5,
        "priority": "MEDIUM",
        "category": "TypeScript Strictness (Frontend)",
        "problem": """
Недостаточная строгость TypeScript, возможное использование 'any' типов.

Файлы: frontend/src/components/* (50 компонентов)

Проблемы:
- Нет strict mode в tsconfig.json
- Возможно использование any вместо explicit types
- Отсутствие type safety для props
""",
        "task": """
Проведи TypeScript quality audit:

1. Проанализируй tsconfig.json на strict settings
2. Найди все использования 'any' типа в компонентах
3. Проверь type coverage для props и state
4. Разработай migration plan к strict TypeScript
5. Создай type definitions для всех компонентов

Формат ответа: JSON с полями:
- tsconfig_analysis: текущая конфигурация
- any_usage_report: где используется 'any'
- type_coverage: процент typed vs untyped кода
- strict_mode_migration: как включить strict
- interface_definitions: новые type definitions
- refactoring_priorities: какие файлы фиксить первыми
- breaking_changes: что может сломаться
- gradual_migration_plan: поэтапное внедрение
""",
        "files": ["frontend/tsconfig.json", "frontend/src/components/"]
    },
    {
        "id": 6,
        "priority": "HIGH",
        "category": "Database Schema Design",
        "problem": """
Schema normalization не подтверждена (3NF?), отсутствует оптимизация индексов.

Файлы: backend/models/* (8 моделей)

Проблемы:
- Неясно, соответствует ли schema 3NF
- Отсутствие документации по indexes
- Нет migration strategy для schema changes
""",
        "task": """
Проведи database architecture review:

1. Проанализируй все 8 моделей на соответствие 3NF
2. Проверь foreign key relationships
3. Оцени index optimization opportunities
4. Разработай migration strategy
5. Создай performance optimization plan

Формат ответа: JSON с полями:
- schema_analysis: анализ структуры БД
- normalization_assessment: соответствие 3NF
- denormalization_candidates: где можно денормализовать
- index_optimization: рекомендации по индексам
- query_performance: анализ медленных запросов
- migration_strategy: как изменять schema
- alembic_setup: настройка миграций
- performance_benchmarks: метрики до/после
""",
        "files": ["backend/models/", "alembic/"]
    },
    {
        "id": 7,
        "priority": "MEDIUM",
        "category": "Error Handling & Logging",
        "problem": """
Недостаточная детализация error handling, отсутствие structured logging.

Файлы: backend/services/* (33 файла)

Проблемы:
- Generic exception handling (catch Exception)
- Нет structured logging (JSON logs)
- Отсутствие correlation IDs для трейсинга
""",
        "task": """
Разработай comprehensive error handling strategy:

1. Проанализируй существующий error handling в services
2. Найди все generic exception handlers
3. Разработай custom exception hierarchy
4. Настрой structured logging (JSON format)
5. Внедри distributed tracing (correlation IDs)

Формат ответа: JSON с полями:
- current_error_handling: как обрабатываются ошибки сейчас
- exception_analysis: типы и частота исключений
- custom_exceptions_design: иерархия кастомных exceptions
- structured_logging_setup: настройка JSON logging
- correlation_ids_implementation: как трейсить запросы
- monitoring_integration: интеграция с мониторингом
- alerting_rules: когда отправлять алерты
- best_practices_guide: рекомендации для разработчиков
""",
        "files": ["backend/services/"]
    }
]


# ═══════════════════════════════════════════════════════════════════════════
# DEEPSEEK API CLIENT
# ═══════════════════════════════════════════════════════════════════════════

def call_deepseek_with_key(api_key: str, prompt: str, max_tokens: int = 4000) -> str:
    """Call DeepSeek API with specific key"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert software architect and security consultant. "
                          "Provide detailed, actionable code reviews and fix plans in valid JSON format. "
                          "Focus on practical solutions with ready-to-use code patches."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,  # Lower for more focused analysis
        "max_tokens": max_tokens
    }
    
    with httpx.Client(timeout=120.0) as client:
        response = client.post(DEEPSEEK_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════════════════════
# FILE READING
# ═══════════════════════════════════════════════════════════════════════════

def read_file_content(file_path: Path, max_lines: int = 500) -> str:
    """Read file content with size limit"""
    try:
        if not file_path.exists():
            return f"[File not found: {file_path}]"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:max_lines]
            content = ''.join(lines)
            
            if len(lines) >= max_lines:
                content += f"\n... (truncated, total lines: {len(lines)})"
            
            return content
    except Exception as e:
        return f"[Error reading file: {e}]"


def get_files_context(files: List[str]) -> str:
    """Get context from multiple files"""
    context = []
    
    for file_pattern in files:
        file_path = PROJECT_ROOT / file_pattern
        
        if file_path.is_dir():
            # List directory contents
            py_files = list(file_path.glob("**/*.py"))[:20]  # First 20 files
            context.append(f"\n📁 Directory: {file_pattern}")
            context.append(f"Total Python files: {len(list(file_path.glob('**/*.py')))}")
            context.append(f"\nKey files (first 20):")
            for f in py_files:
                context.append(f"- {f.relative_to(PROJECT_ROOT)} ({f.stat().st_size // 1024}KB)")
        else:
            # Read file content
            content = read_file_content(file_path, max_lines=300)
            context.append(f"\n📄 File: {file_pattern}")
            context.append(f"```python\n{content}\n```")
    
    return "\n".join(context)


# ═══════════════════════════════════════════════════════════════════════════
# ANALYSIS EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════

def execute_issue_analysis(issue_index: int, issue: Dict, api_key: str) -> Dict:
    """Execute single issue analysis with DeepSeek"""
    start_time = time.time()
    
    try:
        print(f"🔍 [{issue_index+1}/{len(CRITICAL_ISSUES)}] Analyzing: {issue['category']}...")
        
        # Prepare context
        files_context = get_files_context(issue["files"])
        
        # Build full prompt
        full_prompt = f"""
# CRITICAL ISSUE #{issue['id']}: {issue['category']}

## Priority: {issue['priority']}

## Problem Description:
{issue['problem']}

## Files Context:
{files_context}

## Your Task:
{issue['task']}

IMPORTANT: Return ONLY valid JSON (no markdown, no code blocks). Start directly with {{
"""
        
        # Call DeepSeek
        result = call_deepseek_with_key(api_key, full_prompt, max_tokens=4000)
        
        # Clean result (remove markdown if present)
        result_clean = result.strip()
        if result_clean.startswith("```json"):
            result_clean = result_clean[7:]
        if result_clean.startswith("```"):
            result_clean = result_clean[3:]
        if result_clean.endswith("```"):
            result_clean = result_clean[:-3]
        result_clean = result_clean.strip()
        
        duration = time.time() - start_time
        print(f"✅ [{issue_index+1}/{len(CRITICAL_ISSUES)}] Completed {issue['category']} in {duration:.1f}s")
        
        # Try to parse as JSON
        try:
            parsed_result = json.loads(result_clean)
        except json.JSONDecodeError:
            parsed_result = {"raw_response": result_clean, "note": "Failed to parse as JSON"}
        
        return {
            "issue_id": issue["id"],
            "category": issue["category"],
            "priority": issue["priority"],
            "status": "success",
            "analysis": parsed_result,
            "api_key_index": issue_index,
            "duration": duration,
            "prompt_tokens": len(full_prompt.split()),
            "response_tokens": len(result.split())
        }
        
    except Exception as e:
        print(f"❌ [{issue_index+1}/{len(CRITICAL_ISSUES)}] Failed {issue['category']}: {e}")
        return {
            "issue_id": issue["id"],
            "category": issue["category"],
            "priority": issue["priority"],
            "status": "error",
            "error": str(e),
            "api_key_index": issue_index,
            "duration": time.time() - start_time
        }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Main execution with ThreadPoolExecutor"""
    print("="*80)
    print("🔥 Multithreaded DeepSeek Code Review & Fix Generator")
    print("="*80)
    print()
    
    if len(DEEPSEEK_KEYS) == 0:
        print("❌ No DeepSeek API keys found!")
        return
    
    print(f"✅ Using {len(DEEPSEEK_KEYS)} API keys")
    print(f"📊 Analyzing {len(CRITICAL_ISSUES)} critical issues in parallel")
    print()
    
    # Execute analysis in parallel
    results = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all issues
        futures = []
        for i, issue in enumerate(CRITICAL_ISSUES):
            api_key = DEEPSEEK_KEYS[i % len(DEEPSEEK_KEYS)]
            future = executor.submit(execute_issue_analysis, i, issue, api_key)
            futures.append(future)
        
        # Collect results
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    total_duration = time.time() - start_time
    
    # Statistics
    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "error")
    
    print()
    print("="*80)
    print("📊 Analysis Statistics")
    print("="*80)
    print(f"✅ Successful: {successful}/{len(CRITICAL_ISSUES)}")
    print(f"❌ Failed: {failed}/{len(CRITICAL_ISSUES)}")
    print(f"⏱️  Total duration: {total_duration:.1f}s")
    print(f"🚀 Average speed: {total_duration/len(CRITICAL_ISSUES):.1f}s per issue")
    print()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Full results JSON
    results_path = OUTPUT_DIR / f"deepseek_analysis_{timestamp}.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "api_keys_used": len(DEEPSEEK_KEYS),
            "issues_total": len(CRITICAL_ISSUES),
            "duration_seconds": total_duration,
            "statistics": {
                "successful": successful,
                "failed": failed
            },
            "results": sorted(results, key=lambda r: r["issue_id"])
        }, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Full results: {results_path}")
    
    # Generate comprehensive fix plan
    fix_plan_path = OUTPUT_DIR / f"FIX_PLAN_{timestamp}.md"
    with open(fix_plan_path, 'w', encoding='utf-8') as f:
        f.write(f"# 🔧 Comprehensive Fix Plan for 7 Critical Issues\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Analysis Duration:** {total_duration:.1f}s\n")
        f.write(f"**Success Rate:** {successful}/{len(CRITICAL_ISSUES)} ({successful/len(CRITICAL_ISSUES)*100:.1f}%)\n\n")
        
        f.write(f"## 📊 Executive Summary\n\n")
        f.write(f"| Priority | Category | Status | Duration |\n")
        f.write(f"|----------|----------|--------|----------|\n")
        for result in sorted(results, key=lambda r: r["issue_id"]):
            status_icon = "✅" if result["status"] == "success" else "❌"
            f.write(f"| {result['priority']} | {result['category']} | {status_icon} {result['status']} | {result.get('duration', 0):.1f}s |\n")
        
        f.write(f"\n---\n\n")
        
        # Detailed analysis for each issue
        for result in sorted(results, key=lambda r: r["issue_id"]):
            f.write(f"## Issue #{result['issue_id']}: {result['category']}\n\n")
            f.write(f"**Priority:** {result['priority']}\n")
            f.write(f"**Status:** {result['status']}\n")
            f.write(f"**Analysis Duration:** {result.get('duration', 0):.1f}s\n\n")
            
            if result["status"] == "success":
                analysis = result.get("analysis", {})
                
                # Write analysis sections
                f.write(f"### 📋 Analysis\n\n")
                f.write(f"```json\n")
                f.write(json.dumps(analysis, indent=2, ensure_ascii=False))
                f.write(f"\n```\n\n")
                
                # Extract key recommendations
                if isinstance(analysis, dict):
                    if "recommended_solution" in analysis:
                        f.write(f"### ✅ Recommended Solution\n\n")
                        f.write(f"{analysis['recommended_solution']}\n\n")
                    
                    if "code_patch" in analysis:
                        f.write(f"### 💻 Code Patch\n\n")
                        f.write(f"```python\n{analysis['code_patch']}\n```\n\n")
                    
                    if "migration_steps" in analysis:
                        f.write(f"### 🚀 Migration Steps\n\n")
                        steps = analysis['migration_steps']
                        if isinstance(steps, list):
                            for i, step in enumerate(steps, 1):
                                f.write(f"{i}. {step}\n")
                        else:
                            f.write(f"{steps}\n")
                        f.write(f"\n")
            else:
                f.write(f"### ❌ Error\n\n")
                f.write(f"```\n{result.get('error', 'Unknown error')}\n```\n\n")
            
            f.write(f"---\n\n")
    
    print(f"📄 Fix Plan: {fix_plan_path}")
    
    print()
    print("="*80)
    print("✅ DeepSeek analysis complete!")
    print("="*80)


if __name__ == "__main__":
    main()
