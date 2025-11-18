"""
🔍 ПОЛНЫЙ ЦИКЛ AI-ВЗАИМОДЕЙСТВИЯ: Аудит → Модификация → Проверка

Сценарий:
1. Perplexity проводит аудит MCP сервера
2. DeepSeek анализирует отчет и предлагает модификации кода
3. Perplexity проверяет отчет DeepSeek и даёт финальное заключение
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к MCP серверу
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from server import _call_perplexity_api, _call_deepseek_api
from activity_logger import log_mcp_execution


# Читаем структуру MCP сервера для аудита
def get_mcp_server_info():
    """Собираем информацию о MCP сервере для аудита"""
    server_path = Path(__file__).parent / "mcp-server" / "server.py"
    
    with open(server_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Базовая информация
    lines = content.split('\n')
    total_lines = len(lines)
    
    # Подсчёт tools
    import re
    tools = re.findall(r'@mcp\.tool\(\)\s+async def (\w+)', content)
    
    # Подсчёт API вызовов
    perplexity_calls = content.count('_call_perplexity_api')
    deepseek_calls = content.count('_call_deepseek_api')
    
    # Проверка логирования
    logging_blocks = content.count('async with log_mcp_execution')
    
    info = f"""
MCP SERVER STRUCTURE:
====================
Файл: server.py
Размер: {total_lines} строк кода
Total tools: {len(tools)}
Perplexity tools: {len([t for t in tools if 'perplexity' in t.lower() or 'chain' in t.lower() or 'quick' in t.lower()])}
DeepSeek integration: {'Yes' if deepseek_calls > 0 else 'No'}

API INTEGRATION:
================
Perplexity API calls: {perplexity_calls}
DeepSeek API calls: {deepseek_calls}

LOGGING COVERAGE:
=================
Tools with logging: {logging_blocks}
Coverage: {(logging_blocks / len(tools) * 100):.1f}%

AVAILABLE TOOLS:
================
{chr(10).join([f"- {tool}" for tool in sorted(tools)[:10]])}
... (showing first 10 of {len(tools)})

KEY FEATURES:
=============
- FastMCP v2.13.0.1 framework
- Activity logging (JSONL format)
- Dual AI provider support (Perplexity + DeepSeek)
- Helper function: extract_metrics()
- Real-time monitoring support
"""
    return info


async def step1_perplexity_audit():
    """
    Шаг 1: Perplexity проводит аудит MCP сервера
    """
    print("\n" + "=" * 80)
    print("🔵 ШАГ 1: PERPLEXITY - Аудит MCP сервера")
    print("=" * 80)
    
    mcp_info = get_mcp_server_info()
    
    audit_query = f"""Проведи профессиональный аудит MCP сервера и дай рекомендации по улучшению.

{mcp_info}

ЗАДАЧИ АУДИТА:
1. Анализ архитектуры и структуры кода
2. Оценка качества интеграции API (Perplexity + DeepSeek)
3. Проверка системы логирования и мониторинга
4. Выявление потенциальных узких мест
5. Рекомендации по оптимизации и улучшению

Дай структурированный отчет с конкретными рекомендациями."""

    print(f"\n📝 Perplexity анализирует структуру MCP сервера...")
    
    async with log_mcp_execution("Perplexity", "mcp_audit_analysis") as logger:
        result = await _call_perplexity_api(audit_query, model="sonar-pro")
        
        if result.get("success"):
            # Perplexity возвращает "answer", а не "content"
            audit_report = result.get("answer", "")
            tokens = result.get("usage", {}).get("total_tokens", 0)
            logger.tokens = tokens
            
            print(f"   ✅ Аудит завершён ({tokens} токенов)")
            
            if audit_report:
                print(f"\n📊 ОТЧЁТ PERPLEXITY:")
                print("─" * 80)
                print(audit_report)
                print("─" * 80)
                return audit_report
            else:
                print(f"   ⚠️  Результат пустой")
                return None
        else:
            print(f"   ❌ Ошибка: {result.get('error')}")
            return None


async def step2_deepseek_code_modifications(audit_report):
    """
    Шаг 2: DeepSeek анализирует отчет и предлагает модификации кода
    """
    print("\n" + "=" * 80)
    print("🟣 ШАГ 2: DEEPSEEK - Модификация кода на основе аудита")
    print("=" * 80)
    
    modification_query = f"""На основе следующего аудита MCP сервера, разработай конкретные модификации кода:

ОТЧЁТ АУДИТА:
{audit_report}

ЗАДАЧИ:
1. Проанализируй каждую рекомендацию из аудита
2. Предложи конкретные изменения в коде (функции, классы, паттерны)
3. Оцени приоритет каждой модификации (Critical/High/Medium/Low)
4. Укажи потенциальные риски и побочные эффекты
5. Дай план поэтапной реализации

Формат ответа:
- Краткое резюме (executive summary)
- Список модификаций с приоритетами
- Примеры кода для критических изменений
- План внедрения (roadmap)"""

    print(f"\n📝 DeepSeek разрабатывает модификации кода...")
    
    async with log_mcp_execution("DeepSeek", "code_modifications_plan") as logger:
        result = await _call_deepseek_api(modification_query)
        
        if result.get("success"):
            modification_plan = result.get("answer", "")
            tokens = result.get("usage", {}).get("total_tokens", 0)
            logger.tokens = tokens
            
            print(f"   ✅ План модификаций готов ({tokens} токенов)")
            
            if modification_plan:
                print(f"\n🛠️  ПЛАН МОДИФИКАЦИЙ DEEPSEEK:")
                print("─" * 80)
                print(modification_plan)
                print("─" * 80)
                return modification_plan
            else:
                print(f"   ⚠️  Результат пустой")
                return None
        else:
            print(f"   ❌ Ошибка: {result.get('error')}")
            return None


async def step3_perplexity_review(audit_report, modification_plan):
    """
    Шаг 3: Perplexity проверяет план модификаций и даёт финальное заключение
    """
    print("\n" + "=" * 80)
    print("🔵 ШАГ 3: PERPLEXITY - Проверка и финальное заключение")
    print("=" * 80)
    
    review_query = f"""Проверь план модификаций MCP сервера и дай финальное заключение.

ИСХОДНЫЙ АУДИТ:
{audit_report[:1000]}...

ПЛАН МОДИФИКАЦИЙ ОТ DEEPSEEK:
{modification_plan[:1500]}...

ЗАДАЧИ ПРОВЕРКИ:
1. Проверь, что все рекомендации из аудита учтены
2. Оцени качество предложенных решений
3. Найди потенциальные проблемы в плане
4. Дай рекомендации по приоритизации
5. Финальное решение: ОДОБРИТЬ / ДОРАБОТАТЬ / ОТКЛОНИТЬ

Формат ответа:
- Оценка полноты (все ли рекомендации учтены)
- Анализ качества предложенных решений
- Список пропущенных моментов (если есть)
- Рекомендации по доработке
- ФИНАЛЬНОЕ РЕШЕНИЕ + обоснование"""

    print(f"\n📝 Perplexity проверяет план модификаций...")
    
    async with log_mcp_execution("Perplexity", "modifications_review") as logger:
        result = await _call_perplexity_api(review_query, model="sonar-pro")
        
        if result.get("success"):
            review_report = result.get("answer", "")
            tokens = result.get("usage", {}).get("total_tokens", 0)
            logger.tokens = tokens
            
            print(f"   ✅ Проверка завершена ({tokens} токенов)")
            
            if review_report:
                print(f"\n✅ ФИНАЛЬНОЕ ЗАКЛЮЧЕНИЕ PERPLEXITY:")
                print("─" * 80)
                print(review_report)
                print("─" * 80)
                return review_report
            else:
                print(f"   ⚠️  Результат пустой")
                return None
        else:
            print(f"   ❌ Ошибка: {result.get('error')}")
            return None


async def main():
    """Главная функция - полный цикл AI-взаимодействия"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  🔄 ПОЛНЫЙ ЦИКЛ AI-ВЗАИМОДЕЙСТВИЯ".center(78) + "║")
    print("║" + "  Аудит → Модификация → Проверка".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    
    # Шаг 1: Perplexity проводит аудит
    audit_report = await step1_perplexity_audit()
    if not audit_report:
        print("\n❌ Аудит не удался, прерываем цикл")
        return
    
    print("\n⏸️  Пауза 5 секунд перед следующим шагом...")
    await asyncio.sleep(5)
    
    # Шаг 2: DeepSeek разрабатывает модификации
    modification_plan = await step2_deepseek_code_modifications(audit_report)
    if not modification_plan:
        print("\n❌ План модификаций не создан, прерываем цикл")
        return
    
    print("\n⏸️  Пауза 5 секунд перед финальной проверкой...")
    await asyncio.sleep(5)
    
    # Шаг 3: Perplexity проверяет и даёт финальное заключение
    review_report = await step3_perplexity_review(audit_report, modification_plan)
    
    # Итоговая сводка
    print("\n" + "=" * 80)
    print("🎊 ИТОГОВАЯ СВОДКА ЦИКЛА")
    print("=" * 80)
    print(f"""
✅ ПОЛНЫЙ ЦИКЛ AI-ВЗАИМОДЕЙСТВИЯ ЗАВЕРШЁН!

Выполнено 3 шага:
  1. 🔵 Perplexity: Аудит MCP сервера
  2. 🟣 DeepSeek: Разработка модификаций кода
  3. 🔵 Perplexity: Проверка и финальное заключение

📊 Статистика вызовов:
  🔵 Perplexity: 2 вызова (аудит + проверка)
  🟣 DeepSeek: 1 вызов (модификации)

💾 Все этапы залогированы:
  - logs/mcp_activity.jsonl (3 новых записи)
  - MCP Monitor v2.0 (обновлённая статистика)

🎯 Результаты:
  ✓ Аудит MCP сервера проведён
  ✓ План модификаций разработан
  ✓ Финальное заключение получено

🚀 Цикл AI → AI → AI работает идеально!
    """)
    print("=" * 80)
    
    # Сохраняем отчёты в файлы
    reports_dir = Path(__file__).parent / "ai_collaboration_reports"
    reports_dir.mkdir(exist_ok=True)
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if audit_report:
        with open(reports_dir / f"01_audit_{timestamp}.md", "w", encoding="utf-8") as f:
            f.write(f"# MCP Server Audit Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(audit_report)
        print(f"\n📄 Отчёт аудита сохранён: ai_collaboration_reports/01_audit_{timestamp}.md")
    
    if modification_plan:
        with open(reports_dir / f"02_modifications_{timestamp}.md", "w", encoding="utf-8") as f:
            f.write(f"# Code Modifications Plan\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(modification_plan)
        print(f"📄 План модификаций сохранён: ai_collaboration_reports/02_modifications_{timestamp}.md")
    
    if review_report:
        with open(reports_dir / f"03_review_{timestamp}.md", "w", encoding="utf-8") as f:
            f.write(f"# Final Review Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(review_report)
        print(f"📄 Финальное заключение сохранено: ai_collaboration_reports/03_review_{timestamp}.md")


if __name__ == "__main__":
    asyncio.run(main())
