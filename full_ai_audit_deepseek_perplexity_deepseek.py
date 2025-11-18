"""
🔍 ПОЛНЫЙ AI→AI→AI АУДИТ ПРОЕКТА
DeepSeek → Perplexity → DeepSeek

Задачи:
1. DeepSeek: Полный аудит всех файлов и логики проекта
2. Perplexity: Анализ отчета DeepSeek с рекомендациями
3. DeepSeek: Формирование подробного плана действий (ТЗ)
4. Определить текущий этап выполнения ТЗ
5. Проверить предыдущие аудиты и рефакторинги
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import httpx
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройки
PROJECT_ROOT = Path(__file__).parent
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Пути к ТЗ
TZ_FILES = [
    r"d:\PERP\Demo\Техническое задание MCP-оркестратора_1.md",
    r"d:\PERP\Demo\Техническое задание MCP-оркестратора_2.md",
    r"d:\PERP\Demo\Расширенное техническое задание_3-1.md",
    r"d:\PERP\Demo\Расширенное техническое задание_3-2.md",
]

# Файлы отчетов
AUDIT_REPORTS = [
    "AI_AUDIT_ACTION_PLAN.md",
    "AI_REVIEW_SUMMARY.md",
    "AI_COLLABORATION_SUMMARY.md",
    "AGENT_COMM_SESSION_COMPLETE.md",
    "mcp-server/DEEPSEEK_FULL_ANALYSIS.md",
    "mcp-server/MODULAR_REFACTORING_COMPLETE.md",
]

# Output файлы
OUTPUT_DIR = PROJECT_ROOT / "ai_audit_results"
OUTPUT_DIR.mkdir(exist_ok=True)

DEEPSEEK_AUDIT_FILE = OUTPUT_DIR / f"deepseek_full_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
PERPLEXITY_ANALYSIS_FILE = OUTPUT_DIR / f"perplexity_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
FINAL_TZ_FILE = OUTPUT_DIR / f"final_tz_deepseek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"


async def call_deepseek_api(prompt: str, model: str = "deepseek-chat") -> Dict[str, Any]:
    """Вызов DeepSeek API"""
    async with httpx.AsyncClient(timeout=300.0) as client:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты - эксперт по аудиту Python проектов, архитектуре ПО и технической документации."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 8000  # Уменьшил с 16000
        }
        
        try:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP Error: {e}")
            print(f"Response: {e.response.text}")
            print(f"Request payload size: {len(json.dumps(payload))} bytes")
            print(f"Prompt size: {len(prompt)} chars")
            raise


async def call_perplexity_api(prompt: str, model: str = "sonar") -> Dict[str, Any]:
    """Вызов Perplexity API"""
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Актуальные модели Perplexity (Nov 2025)
        # Доступные: sonar, sonar-pro, sonar-reasoning
        model_name = model
        
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты - эксперт по анализу технических проектов и формированию рекомендаций на основе best practices."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 4000
        }
        
        try:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP Error: {e}")
            print(f"Response: {e.response.text}")
            print(f"Request payload size: {len(json.dumps(payload))} bytes")
            print(f"Prompt size: {len(prompt)} chars")
            raise


def collect_project_structure() -> Dict[str, Any]:
    """Собирает структуру проекта"""
    print("📦 Сбор структуры проекта...")
    
    structure = {
        "root_files": [],
        "backend": {"files": [], "subdirs": {}},
        "frontend": {"files": [], "subdirs": {}},
        "mcp_server": {"files": [], "subdirs": {}},
        "tests": {"files": [], "subdirs": {}},
        "scripts": {"files": [], "subdirs": {}},
        "docs": {"files": [], "subdirs": {}},
    }
    
    # Root files
    for item in PROJECT_ROOT.iterdir():
        if item.is_file() and item.suffix in [".py", ".md", ".txt", ".json", ".yaml", ".yml"]:
            structure["root_files"].append(item.name)
    
    # Backend
    backend_dir = PROJECT_ROOT / "backend"
    if backend_dir.exists():
        for item in backend_dir.rglob("*.py"):
            rel_path = item.relative_to(backend_dir)
            structure["backend"]["files"].append(str(rel_path))
    
    # Frontend
    frontend_dir = PROJECT_ROOT / "frontend"
    if frontend_dir.exists():
        for item in frontend_dir.rglob("*"):
            if item.suffix in [".ts", ".tsx", ".js", ".jsx", ".json", ".html"]:
                rel_path = item.relative_to(frontend_dir)
                structure["frontend"]["files"].append(str(rel_path))
    
    # MCP Server
    mcp_dir = PROJECT_ROOT / "mcp-server"
    if mcp_dir.exists():
        for item in mcp_dir.rglob("*.py"):
            rel_path = item.relative_to(mcp_dir)
            structure["mcp_server"]["files"].append(str(rel_path))
    
    # Tests
    tests_dir = PROJECT_ROOT / "tests"
    if tests_dir.exists():
        for item in tests_dir.rglob("*.py"):
            rel_path = item.relative_to(tests_dir)
            structure["tests"]["files"].append(str(rel_path))
    
    print(f"✅ Собрано {len(structure['root_files'])} root файлов")
    print(f"✅ Собрано {len(structure['backend']['files'])} backend файлов")
    print(f"✅ Собрано {len(structure['frontend']['files'])} frontend файлов")
    print(f"✅ Собрано {len(structure['mcp_server']['files'])} mcp-server файлов")
    print(f"✅ Собрано {len(structure['tests']['files'])} test файлов")
    
    return structure


def read_tz_files() -> str:
    """Читает все файлы ТЗ"""
    print("📖 Чтение файлов ТЗ...")
    content = []
    
    for tz_file in TZ_FILES:
        path = Path(tz_file)
        if path.exists():
            print(f"  ✅ {path.name}")
            content.append(f"\n\n{'='*80}\n# {path.name}\n{'='*80}\n\n")
            content.append(path.read_text(encoding="utf-8"))
        else:
            print(f"  ❌ {path.name} не найден")
    
    return "".join(content)


def read_audit_reports() -> str:
    """Читает все отчеты аудита"""
    print("📊 Чтение отчетов аудита...")
    content = []
    
    for report in AUDIT_REPORTS:
        path = PROJECT_ROOT / report
        if path.exists():
            print(f"  ✅ {report}")
            content.append(f"\n\n{'='*80}\n# {report}\n{'='*80}\n\n")
            content.append(path.read_text(encoding="utf-8"))
        else:
            print(f"  ⚠️  {report} не найден")
    
    return "".join(content)


async def phase_1_deepseek_audit(structure: Dict[str, Any], tz_content: str, audit_content: str) -> str:
    """
    Фаза 1: DeepSeek проводит полный аудит проекта
    """
    print("\n" + "="*80)
    print("🤖 ФАЗА 1: DeepSeek - Полный аудит проекта")
    print("="*80)
    
    # Создаем краткую сводку структуры
    structure_summary = {
        "root_files_count": len(structure["root_files"]),
        "backend_files_count": len(structure["backend"]["files"]),
        "frontend_files_count": len(structure["frontend"]["files"]),
        "mcp_server_files_count": len(structure["mcp_server"]["files"]),
        "tests_files_count": len(structure["tests"]["files"]),
        "sample_root_files": structure["root_files"][:20],
        "sample_backend_files": structure["backend"]["files"][:20],
        "sample_mcp_files": structure["mcp_server"]["files"][:20],
    }
    
    prompt = f"""
# ЗАДАЧА: ПОЛНЫЙ АУДИТ ПРОЕКТА BYBIT STRATEGY TESTER V2

Ты - senior архитектор и аудитор. Проведи глубокий анализ проекта.

## СТРУКТУРА ПРОЕКТА (SUMMARY)

```json
{json.dumps(structure_summary, indent=2, ensure_ascii=False)}
```

## ТЕХНИЧЕСКОЕ ЗАДАНИЕ (4 документа - КРАТКАЯ ВЫЖИМКА)

{tz_content[:8000]}  # Первые 8k символов ТЗ

## ПРЕДЫДУЩИЕ АУДИТЫ И РЕФАКТОРИНГИ (КРАТКАЯ ВЫЖИМКА)

{audit_content[:8000]}  # Первые 8k символов отчетов

## ТРЕБУЕТСЯ ПРОАНАЛИЗИРОВАТЬ:

1. **Соответствие ТЗ**:
   - На каком этапе реализации находится проект?
   - Какие части ТЗ реализованы?
   - Что еще предстоит сделать?

2. **Архитектура**:
   - Правильность структуры проекта
   - Модульность и разделение ответственности
   - Соответствие паттернам из ТЗ (MCP, Redis Streams, Saga, etc.)

3. **Код и логика**:
   - Критические проблемы
   - Технический долг
   - Неиспользуемый код
   - Проблемы производительности

4. **Безопасность**:
   - Sandbox execution
   - API ключи и шифрование
   - Валидация входных данных

5. **Тестирование**:
   - Покрытие тестами
   - Качество тестов
   - Интеграционные тесты

6. **Мониторинг и observability**:
   - Метрики
   - Логирование
   - Трассировка

7. **ML/AI компоненты**:
   - LSTM модели
   - Model drift detection
   - Retraining strategy

## ФОРМАТ ОТВЕТА

Предоставь подробный JSON-отчет со структурой:

```json
{{
  "project_stage": {{
    "tz_part_1": "30% реализовано",
    "tz_part_2": "50% реализовано",
    "tz_part_3": "10% реализовано",
    "tz_part_4": "5% реализовано",
    "overall": "25% готовности"
  }},
  "architecture": {{
    "score": 7,
    "strengths": ["..."],
    "weaknesses": ["..."],
    "critical_issues": ["..."]
  }},
  "code_quality": {{
    "score": 6,
    "technical_debt": ["..."],
    "unused_code": ["..."],
    "performance_issues": ["..."]
  }},
  "security": {{
    "score": 8,
    "implemented": ["..."],
    "missing": ["..."],
    "vulnerabilities": ["..."]
  }},
  "testing": {{
    "score": 7,
    "coverage": "X%",
    "quality": "...",
    "missing_tests": ["..."]
  }},
  "observability": {{
    "score": 6,
    "metrics": "...",
    "logging": "...",
    "tracing": "..."
  }},
  "ml_ai": {{
    "score": 5,
    "model_staleness": "...",
    "drift_detection": "...",
    "retraining": "..."
  }},
  "critical_priorities": [
    {{
      "priority": 1,
      "issue": "...",
      "impact": "...",
      "effort": "...",
      "recommendation": "..."
    }}
  ],
  "quick_wins": ["..."],
  "long_term_roadmap": ["..."]
}}
```

НАЧИНАЙ АУДИТ!
"""
    
    print("📤 Отправка запроса в DeepSeek...")
    response = await call_deepseek_api(prompt)
    
    audit_report = response["choices"][0]["message"]["content"]
    
    # Сохранение отчета
    DEEPSEEK_AUDIT_FILE.write_text(
        json.dumps({
            "timestamp": datetime.now().isoformat(),
            "model": "deepseek-chat",
            "prompt_length": len(prompt),
            "response": audit_report
        }, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    print(f"✅ Аудит завершен! Сохранен в {DEEPSEEK_AUDIT_FILE.name}")
    print(f"📊 Длина отчета: {len(audit_report)} символов")
    
    return audit_report


async def phase_2_perplexity_analysis(deepseek_audit: str) -> str:
    """
    Фаза 2: Perplexity анализирует отчет DeepSeek
    """
    print("\n" + "="*80)
    print("🌐 ФАЗА 2: Perplexity - Анализ отчета DeepSeek")
    print("="*80)
    
    prompt = f"""
# ЗАДАЧА: АНАЛИЗ ОТЧЕТА DEEPSEEK ПО ПРОЕКТУ

Ты получил отчет от DeepSeek о состоянии проекта Bybit Strategy Tester V2.

## ОТЧЕТ DEEPSEEK (КРАТКАЯ ВЕРСИЯ):

{deepseek_audit[:8000]}  # Еще больше сократил - первые 8k символов

## ТВОЯ ЗАДАЧА:

1. **Критический анализ**:
   - Насколько точны выводы DeepSeek?
   - Что упущено в анализе?

2. **Best practices индустрии**:
   - Современные подходы к решению выявленных проблем
   - Проверенные паттерны и фреймворки

3. **Приоритизация**:
   - Quick wins vs long-term investments
   - ROI по каждому направлению

4. **Roadmap**:
   - Конкретные шаги на 2-4 недели
   - Метрики успеха

Предоставь структурированный анализ с конкретным action plan.

НАЧИНАЙ АНАЛИЗ!
"""
    
    print("📤 Отправка запроса в Perplexity...")
    response = await call_perplexity_api(prompt, model="sonar")
    
    analysis = response["choices"][0]["message"]["content"]
    
    # Сохранение анализа
    PERPLEXITY_ANALYSIS_FILE.write_text(
        json.dumps({
            "timestamp": datetime.now().isoformat(),
            "model": "llama-3.1-sonar-pro-128k-online",
            "prompt_length": len(prompt),
            "response": analysis,
            "citations": response.get("citations", [])
        }, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    print(f"✅ Анализ завершен! Сохранен в {PERPLEXITY_ANALYSIS_FILE.name}")
    print(f"📊 Длина анализа: {len(analysis)} символов")
    
    return analysis


async def phase_3_deepseek_final_tz(deepseek_audit: str, perplexity_analysis: str) -> str:
    """
    Фаза 3: DeepSeek формирует итоговое ТЗ
    """
    print("\n" + "="*80)
    print("📝 ФАЗА 3: DeepSeek - Формирование итогового ТЗ")
    print("="*80)
    
    prompt = f"""
# ЗАДАЧА: СОЗДАНИЕ ПОДРОБНОГО ТЕХНИЧЕСКОГО ЗАДАНИЯ

На основе:
1. Твоего аудита проекта
2. Анализа от Perplexity

Создай ПОДРОБНОЕ техническое задание на доработку проекта.

## ТВОЙ АУДИТ (КРАТКАЯ ВЕРСИЯ):

{deepseek_audit[:12000]}

## АНАЛИЗ PERPLEXITY (КРАТКАЯ ВЕРСИЯ):

{perplexity_analysis[:12000]}

## ТРЕБОВАНИЯ К ТЗ:

### 1. Executive Summary
- Текущее состояние проекта (1 абзац)
- Ключевые проблемы (топ-5)
- Планируемые улучшения (топ-5)
- Ожидаемые результаты

### 2. Детальный план по каждой проблеме

Для каждой проблемы указать:

```markdown
#### Проблема #N: [Название]

**Приоритет**: 🔴 CRITICAL / 🟡 HIGH / 🟢 MEDIUM / ⚪ LOW
**Трудоемкость**: X часов/дней
**Стоимость**: $X (если применимо)
**Влияние**: [описание impact]

##### Текущее состояние:
[детальное описание проблемы с примерами кода]

##### Решение:
[пошаговый план с примерами кода]

##### Файлы для изменения:
- `path/to/file1.py` - [что менять]
- `path/to/file2.py` - [что менять]

##### Критерии приемки:
- [ ] Критерий 1
- [ ] Критерий 2
- [ ] Критерий 3

##### Риски:
- Риск 1: [описание + митигация]
- Риск 2: [описание + митигация]
```

### 3. Roadmap с временными рамками

```markdown
#### Week 1: Critical Fixes (40 часов)
- [ ] Проблема #1 (8h)
- [ ] Проблема #2 (12h)
- [ ] Проблема #3 (10h)
- [ ] Testing (10h)

#### Week 2: High Priority (40 часов)
...

#### Week 3-4: Medium Priority
...
```

### 4. Архитектурные диаграммы

Добавь mermaid диаграммы для:
- Текущей архитектуры (as-is)
- Целевой архитектуры (to-be)
- Потока данных
- CI/CD pipeline

### 5. Метрики успеха

```markdown
| Метрика | Сейчас | Цель | Способ измерения |
|---------|--------|------|------------------|
| Code quality | 6/10 | 8/10 | SonarQube |
| Test coverage | 45% | 80% | pytest --cov |
| Performance | ... | ... | ... |
```

### 6. Зависимости и блокеры

- Внешние зависимости
- Необходимые ресурсы
- Потенциальные блокеры

## ФОРМАТ:

Создай полноценный Markdown документ (ТЗ) готовый к использованию.
Используй эмодзи для читаемости, code blocks для примеров.

СОЗДАВАЙ ТЗ!
"""
    
    print("📤 Отправка запроса в DeepSeek...")
    response = await call_deepseek_api(prompt)
    
    final_tz = response["choices"][0]["message"]["content"]
    
    # Сохранение ТЗ
    FINAL_TZ_FILE.write_text(final_tz, encoding="utf-8")
    
    print(f"✅ ТЗ сформировано! Сохранено в {FINAL_TZ_FILE.name}")
    print(f"📊 Длина ТЗ: {len(final_tz)} символов")
    
    return final_tz


async def main():
    """Главная функция"""
    print("\n" + "="*80)
    print("🚀 ЗАПУСК ПОЛНОГО AI→AI→AI АУДИТА")
    print("="*80)
    print(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    if not PERPLEXITY_API_KEY:
        print("❌ PERPLEXITY_API_KEY не установлен!")
        return
    
    if not DEEPSEEK_API_KEY:
        print("❌ DEEPSEEK_API_KEY не установлен!")
        return
    
    try:
        # Сбор данных
        structure = collect_project_structure()
        tz_content = read_tz_files()
        audit_content = read_audit_reports()
        
        # Фаза 1: DeepSeek аудит
        deepseek_audit = await phase_1_deepseek_audit(structure, tz_content, audit_content)
        
        # Фаза 2: Perplexity анализ
        perplexity_analysis = await phase_2_perplexity_analysis(deepseek_audit)
        
        # Фаза 3: DeepSeek итоговое ТЗ
        final_tz = await phase_3_deepseek_final_tz(deepseek_audit, perplexity_analysis)
        
        # Итоговый отчет
        print("\n" + "="*80)
        print("✅ АУДИТ ЗАВЕРШЕН УСПЕШНО!")
        print("="*80)
        print(f"\n📁 Результаты сохранены в: {OUTPUT_DIR}")
        print(f"\n📄 Файлы:")
        print(f"  1. {DEEPSEEK_AUDIT_FILE.name}")
        print(f"  2. {PERPLEXITY_ANALYSIS_FILE.name}")
        print(f"  3. {FINAL_TZ_FILE.name}")
        print(f"\n⏱️  Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
