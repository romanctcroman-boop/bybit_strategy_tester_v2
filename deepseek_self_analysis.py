"""
🔍 DeepSeek AI Robot - Глубокий Самоанализ через DeepSeek API
==============================================================

Этот скрипт выполняет:
1. Анализ собственного кода через DeepSeek API
2. Выявление недостатков и проблем
3. Консультацию с Perplexity для best practices
4. Генерацию улучшений
5. Применение улучшений
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List
from automation.deepseek_robot.ai_integrations import DeepSeekClient, PerplexityClient


async def analyze_robot_code_with_deepseek() -> Dict[str, Any]:
    """
    Шаг 1: Анализ кода робота через DeepSeek API
    """
    print("\n" + "="*80)
    print("🔍 ШАГ 1: Глубокий анализ кода DeepSeek Robot через DeepSeek API")
    print("="*80)
    
    client = DeepSeekClient()
    robot_file = Path("d:/bybit_strategy_tester_v2/automation/deepseek_robot/robot.py")
    
    if not robot_file.exists():
        print(f"❌ Файл не найден: {robot_file}")
        return {"success": False, "error": "File not found"}
    
    # Читаем код
    code = robot_file.read_text(encoding='utf-8')
    print(f"\n📄 Анализируемый файл: {robot_file}")
    print(f"📊 Размер кода: {len(code)} символов ({len(code.splitlines())} строк)")
    
    # Разбиваем код на части для анализа (DeepSeek имеет ограничения)
    # Берём только ключевые части: классы и основные методы
    lines = code.splitlines()
    
    # Извлекаем основные компоненты
    code_summary = []
    in_class = False
    indent_level = 0
    
    for line in lines:
        stripped = line.strip()
        
        # Классы и их методы
        if stripped.startswith('class ') or stripped.startswith('async def ') or stripped.startswith('def '):
            code_summary.append(line)
            in_class = True
        # Docstrings
        elif in_class and ('"""' in stripped or "'''" in stripped):
            code_summary.append(line)
        # Первые строки методов
        elif in_class and stripped and not stripped.startswith('#'):
            if len(code_summary) < 500:  # Ограничение
                code_summary.append(line)
    
    # Формируем упрощённый код для анализа
    code_for_analysis = '\n'.join(code_summary[:400])  # Первые 400 строк
    
    print(f"📊 Для анализа отобрано: {len(code_for_analysis)} символов ({len(code_summary[:400])} строк)")
    
    # Детальный анализ через DeepSeek
    analysis_instruction = """
Проведи ЧЕСТНЫЙ и КРИТИЧНЫЙ анализ этого кода DeepSeek AI Robot.

Оцени по критериям:

1. АРХИТЕКТУРА (0-10):
   - Чистота архитектуры
   - Separation of concerns
   - SOLID принципы
   - Слабые места в дизайне

2. КОД-КАЧЕСТВО (0-10):
   - Читаемость
   - Сложность (cyclomatic complexity)
   - Дублирование кода
   - Naming conventions
   - Type hints coverage

3. АВТОНОМНОСТЬ (0-10):
   - Насколько робот действительно автономен?
   - Есть ли manual interventions?
   - Self-healing capabilities
   - Error recovery

4. ПРОИЗВОДИТЕЛЬНОСТЬ (0-10):
   - Оптимизация алгоритмов
   - Async/await usage
   - Memory efficiency
   - Scalability

5. НАДЁЖНОСТЬ (0-10):
   - Error handling
   - Edge cases coverage
   - Logging and monitoring
   - Rollback mechanisms

6. ФУНКЦИОНАЛЬНОСТЬ (0-10):
   - Полнота реализации
   - Missing features
   - Bugs and limitations
   - API design

Выдай результат в JSON:
{
  "overall_score": 0-10,
  "scores": {
    "architecture": {"score": 0-10, "issues": [...]},
    "code_quality": {"score": 0-10, "issues": [...]},
    "autonomy": {"score": 0-10, "issues": [...]},
    "performance": {"score": 0-10, "issues": [...]},
    "reliability": {"score": 0-10, "issues": [...]},
    "functionality": {"score": 0-10, "issues": [...]}
  },
  "critical_issues": [...],
  "high_priority_issues": [...],
  "medium_priority_issues": [...],
  "recommendations": [...]
}

БУДЬ ЧЕСТНЫМ! Не занижай и не завышай оценки. Найди реальные проблемы!
"""
    
    print("\n🤖 Отправка запроса в DeepSeek API...")
    print("⏳ Ожидание анализа (это может занять 30-60 секунд)...")
    
    result = await client.analyze_code(
        code=code_for_analysis,  # Используем упрощённый код
        instruction=analysis_instruction,
        context={
            "file": str(robot_file),
            "purpose": "Self-analysis and improvement",
            "language": "Python 3.13",
            "framework": "asyncio",
            "note": "Analyzing key components and architecture"
        }
    )
    
    if result.success:
        print(f"\n✅ Анализ завершён!")
        print(f"📊 Использовано токенов: {result.tokens_used}")
        print(f"📝 Размер ответа: {len(result.content)} символов")
        
        # Сохраняем полный результат
        output_file = Path("d:/bybit_strategy_tester_v2/deepseek_self_analysis_result.json")
        output_file.write_text(json.dumps({
            "timestamp": "2025-11-08",
            "tokens_used": result.tokens_used,
            "analysis": result.content
        }, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"💾 Результат сохранён: {output_file}")
        
        # Пытаемся распарсить JSON
        try:
            # Ищем JSON в ответе
            content = result.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            analysis_data = json.loads(content.strip())
            
            print("\n" + "="*80)
            print("📊 РЕЗУЛЬТАТЫ АНАЛИЗА DeepSeek")
            print("="*80)
            
            # Общая оценка
            overall = analysis_data.get("overall_score", 0)
            print(f"\n🎯 ОБЩАЯ ОЦЕНКА: {overall}/10")
            
            # Детальные оценки
            scores = analysis_data.get("scores", {})
            print("\n📈 Детальные оценки:")
            for category, data in scores.items():
                score = data.get("score", 0)
                emoji = "🟢" if score >= 8 else "🟡" if score >= 6 else "🔴"
                print(f"  {emoji} {category.title()}: {score}/10")
                if data.get("issues"):
                    for issue in data["issues"][:3]:  # Первые 3
                        print(f"    • {issue}")
            
            # Критичные проблемы
            critical = analysis_data.get("critical_issues", [])
            if critical:
                print(f"\n🚨 КРИТИЧНЫЕ ПРОБЛЕМЫ ({len(critical)}):")
                for i, issue in enumerate(critical, 1):
                    print(f"  {i}. {issue}")
            
            # High priority
            high = analysis_data.get("high_priority_issues", [])
            if high:
                print(f"\n⚠️  HIGH PRIORITY ({len(high)}):")
                for i, issue in enumerate(high[:5], 1):  # Первые 5
                    print(f"  {i}. {issue}")
            
            # Рекомендации
            recommendations = analysis_data.get("recommendations", [])
            if recommendations:
                print(f"\n💡 РЕКОМЕНДАЦИИ ({len(recommendations)}):")
                for i, rec in enumerate(recommendations[:5], 1):
                    print(f"  {i}. {rec}")
            
            return {
                "success": True,
                "analysis": analysis_data,
                "raw_content": result.content
            }
            
        except json.JSONDecodeError as e:
            print(f"\n⚠️  Не удалось распарсить JSON: {e}")
            print("\n📄 Сырой ответ (первые 1000 символов):")
            print(result.content[:1000])
            return {
                "success": True,
                "analysis": None,
                "raw_content": result.content
            }
    else:
        print(f"\n❌ Ошибка анализа: {result.error}")
        return {"success": False, "error": result.error}


async def consult_perplexity_for_improvements() -> Dict[str, Any]:
    """
    Шаг 2: Консультация с Perplexity для best practices
    """
    print("\n" + "="*80)
    print("🔍 ШАГ 2: Консультация с Perplexity AI для улучшений")
    print("="*80)
    
    client = PerplexityClient()
    
    # Читаем результаты анализа DeepSeek
    analysis_file = Path("d:/bybit_strategy_tester_v2/deepseek_self_analysis_result.json")
    if analysis_file.exists():
        analysis_data = json.loads(analysis_file.read_text(encoding='utf-8'))
        analysis_content = analysis_data.get("analysis", "")
        print(f"✅ Загружен анализ DeepSeek")
    else:
        analysis_content = "No previous analysis available"
        print(f"⚠️  Анализ DeepSeek не найден")
    
    # Консультация 1: Autonomous AI Agents
    print("\n🔍 Консультация 1: Advanced Autonomous AI Agent Patterns...")
    query1 = """
Latest 2025 best practices for building truly autonomous AI code analysis agents:

1. Self-improvement algorithms
2. Multi-AI collaboration patterns (DeepSeek + Perplexity + Copilot)
3. Cyclic analysis until 100% quality
4. Advanced error recovery and self-healing
5. Production-grade architecture patterns
6. Performance optimization for AI agents

Focus on: Python asyncio, production deployment, real-world challenges.
"""
    
    result1 = await client.search(query1, focus="detailed_technical")
    
    if result1.success:
        print(f"✅ Получено! Tokens: {result1.tokens_used}")
        consultation1 = result1.content
    else:
        print(f"❌ Ошибка: {result1.error}")
        consultation1 = ""
    
    # Консультация 2: Code Quality
    print("\n🔍 Консультация 2: Production-Grade Python Code Quality...")
    query2 = """
Python 3.13+ production code quality best practices for autonomous systems:

1. Architecture patterns (Clean Architecture, Hexagonal, DDD)
2. Async/await optimization patterns
3. Error handling and resilience patterns
4. Type safety and static analysis
5. Performance profiling and optimization
6. Testing strategies for AI systems

Real-world production examples from 2025.
"""
    
    result2 = await client.search(query2, focus="code_examples")
    
    if result2.success:
        print(f"✅ Получено! Tokens: {result2.tokens_used}")
        consultation2 = result2.content
    else:
        print(f"❌ Ошибка: {result2.error}")
        consultation2 = ""
    
    # Консультация 3: Specific Improvements
    print("\n🔍 Консультация 3: How to improve autonomous code robot...")
    query3 = f"""
Based on this code analysis, how to improve autonomous AI code analysis robot?

Analysis summary:
{str(analysis_content)[:1000]}

Specific questions:
1. How to achieve TRUE autonomy (no manual interventions)?
2. How to implement effective self-healing?
3. How to optimize async/await for AI API calls?
4. How to improve error recovery and rollback?
5. Architecture improvements for scalability?

Provide concrete Python 3.13 code examples and patterns.
"""
    
    result3 = await client.search(query3, focus="specific_solutions")
    
    if result3.success:
        print(f"✅ Получено! Tokens: {result3.tokens_used}")
        consultation3 = result3.content
    else:
        print(f"❌ Ошибка: {result3.error}")
        consultation3 = ""
    
    # Сохраняем результаты
    perplexity_results = {
        "timestamp": "2025-11-08",
        "consultations": {
            "autonomous_patterns": consultation1,
            "code_quality": consultation2,
            "specific_improvements": consultation3
        },
        "total_tokens": (
            result1.tokens_used if result1.success else 0 +
            result2.tokens_used if result2.success else 0 +
            result3.tokens_used if result3.success else 0
        )
    }
    
    output_file = Path("d:/bybit_strategy_tester_v2/perplexity_consultation_result.json")
    output_file.write_text(
        json.dumps(perplexity_results, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    print(f"\n💾 Результаты консультации сохранены: {output_file}")
    
    # Выводим краткую сводку
    print("\n" + "="*80)
    print("📊 КРАТКАЯ СВОДКА КОНСУЛЬТАЦИИ PERPLEXITY")
    print("="*80)
    
    for title, content in [
        ("Autonomous Patterns", consultation1),
        ("Code Quality", consultation2),
        ("Specific Improvements", consultation3)
    ]:
        print(f"\n📚 {title}:")
        preview = content[:300].replace('\n', ' ') if content else "Не получено"
        print(f"  {preview}...")
    
    return {
        "success": True,
        "consultations": perplexity_results
    }


async def generate_improvements_with_deepseek() -> Dict[str, Any]:
    """
    Шаг 3: Генерация улучшений через DeepSeek на основе анализа и консультации
    """
    print("\n" + "="*80)
    print("🔧 ШАГ 3: Генерация улучшений через DeepSeek API")
    print("="*80)
    
    client = DeepSeekClient()
    
    # Загружаем анализ и консультацию
    analysis_file = Path("d:/bybit_strategy_tester_v2/deepseek_self_analysis_result.json")
    perplexity_file = Path("d:/bybit_strategy_tester_v2/perplexity_consultation_result.json")
    
    analysis_data = json.loads(analysis_file.read_text(encoding='utf-8')) if analysis_file.exists() else {}
    perplexity_data = json.loads(perplexity_file.read_text(encoding='utf-8')) if perplexity_file.exists() else {}
    
    # Читаем текущий код
    robot_file = Path("d:/bybit_strategy_tester_v2/automation/deepseek_robot/robot.py")
    current_code = robot_file.read_text(encoding='utf-8')
    
    print(f"📄 Текущий код: {len(current_code)} символов")
    print(f"📊 Анализ загружен: {'✅' if analysis_data else '❌'}")
    print(f"📊 Консультация загружена: {'✅' if perplexity_data else '❌'}")
    
    # Инструкция для генерации улучшений
    improvement_instruction = f"""
На основе проведённого анализа и консультации с Perplexity, сгенерируй КОНКРЕТНЫЕ улучшения кода.

АНАЛИЗ DeepSeek:
{json.dumps(analysis_data.get('analysis', {}), indent=2, ensure_ascii=False)[:2000]}

КОНСУЛЬТАЦИЯ Perplexity:
{str(perplexity_data.get('consultations', {}))[:2000]}

ЗАДАЧИ:
1. Исправить все critical issues
2. Улучшить автономность до 10/10
3. Оптимизировать производительность
4. Улучшить архитектуру (SOLID, Clean Architecture)
5. Добавить advanced error recovery
6. Реализовать true self-healing

Выдай результат в формате:

{{
  "improvements": [
    {{
      "priority": "critical|high|medium",
      "category": "architecture|autonomy|performance|reliability",
      "title": "Short title",
      "description": "Detailed description",
      "implementation": {{
        "file": "path/to/file.py",
        "method": "method_name or 'new_class'",
        "code": "Full implementation code",
        "explanation": "Why this improves the code"
      }}
    }}
  ],
  "expected_improvements": {{
    "architecture": "+X points",
    "autonomy": "+X points",
    "performance": "+X points",
    "overall": "+X points"
  }}
}}

Генерируй РЕАЛЬНЫЙ, РАБОТАЮЩИЙ КОД! Не placeholders!
"""
    
    print("\n🤖 Отправка запроса на генерацию улучшений...")
    print("⏳ Ожидание (может занять 60-90 секунд)...")
    
    result = await client.analyze_code(
        code=current_code[:10000],  # Первые 10k символов для контекста
        instruction=improvement_instruction,
        context={
            "analysis": str(analysis_data)[:1000],
            "consultation": str(perplexity_data)[:1000]
        }
    )
    
    if result.success:
        print(f"\n✅ Улучшения сгенерированы!")
        print(f"📊 Использовано токенов: {result.tokens_used}")
        
        # Сохраняем
        output_file = Path("d:/bybit_strategy_tester_v2/deepseek_improvements.json")
        output_file.write_text(json.dumps({
            "timestamp": "2025-11-08",
            "tokens_used": result.tokens_used,
            "improvements": result.content
        }, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"💾 Улучшения сохранены: {output_file}")
        
        # Пытаемся распарсить
        try:
            content = result.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            improvements_data = json.loads(content.strip())
            
            print("\n" + "="*80)
            print("🔧 СГЕНЕРИРОВАННЫЕ УЛУЧШЕНИЯ")
            print("="*80)
            
            improvements_list = improvements_data.get("improvements", [])
            print(f"\n📊 Всего улучшений: {len(improvements_list)}")
            
            # Группировка по приоритету
            by_priority = {"critical": [], "high": [], "medium": []}
            for imp in improvements_list:
                priority = imp.get("priority", "medium")
                by_priority.get(priority, []).append(imp)
            
            for priority in ["critical", "high", "medium"]:
                items = by_priority[priority]
                if items:
                    emoji = "🚨" if priority == "critical" else "⚠️" if priority == "high" else "ℹ️"
                    print(f"\n{emoji} {priority.upper()} ({len(items)}):")
                    for i, imp in enumerate(items, 1):
                        print(f"  {i}. [{imp.get('category', 'other')}] {imp.get('title', 'Untitled')}")
            
            # Ожидаемые улучшения
            expected = improvements_data.get("expected_improvements", {})
            if expected:
                print(f"\n📈 ОЖИДАЕМЫЕ УЛУЧШЕНИЯ:")
                for category, improvement in expected.items():
                    print(f"  • {category.title()}: {improvement}")
            
            return {
                "success": True,
                "improvements": improvements_data,
                "raw_content": result.content
            }
            
        except json.JSONDecodeError as e:
            print(f"\n⚠️  Не удалось распарсить JSON: {e}")
            print("\n📄 Сырой ответ (первые 500 символов):")
            print(result.content[:500])
            return {
                "success": True,
                "improvements": None,
                "raw_content": result.content
            }
    else:
        print(f"\n❌ Ошибка: {result.error}")
        return {"success": False, "error": result.error}


async def create_comprehensive_report() -> None:
    """
    Шаг 4: Создание комплексного отчёта
    """
    print("\n" + "="*80)
    print("📊 ШАГ 4: Создание комплексного отчёта")
    print("="*80)
    
    # Загружаем все данные
    analysis_file = Path("d:/bybit_strategy_tester_v2/deepseek_self_analysis_result.json")
    perplexity_file = Path("d:/bybit_strategy_tester_v2/perplexity_consultation_result.json")
    improvements_file = Path("d:/bybit_strategy_tester_v2/deepseek_improvements.json")
    
    analysis_data = json.loads(analysis_file.read_text(encoding='utf-8')) if analysis_file.exists() else {}
    perplexity_data = json.loads(perplexity_file.read_text(encoding='utf-8')) if perplexity_file.exists() else {}
    improvements_data = json.loads(improvements_file.read_text(encoding='utf-8')) if improvements_file.exists() else {}
    
    # Создаём детальный отчёт
    report = f"""# 🔍 DeepSeek AI Robot - Глубокий Самоанализ и Улучшения

**Дата**: 8 ноября 2025  
**Цель**: Честный анализ и доведение до совершенства

---

## 📊 РЕЗУЛЬТАТЫ АНАЛИЗА DeepSeek

{json.dumps(analysis_data.get('analysis', {}), indent=2, ensure_ascii=False)}

---

## 💡 КОНСУЛЬТАЦИЯ Perplexity

### Autonomous Patterns
{perplexity_data.get('consultations', {}).get('autonomous_patterns', 'N/A')[:1000]}...

### Code Quality
{perplexity_data.get('consultations', {}).get('code_quality', 'N/A')[:1000]}...

### Specific Improvements
{perplexity_data.get('consultations', {}).get('specific_improvements', 'N/A')[:1000]}...

---

## 🔧 СГЕНЕРИРОВАННЫЕ УЛУЧШЕНИЯ

{json.dumps(improvements_data.get('improvements', {}), indent=2, ensure_ascii=False)}

---

## 📈 СЛЕДУЮЩИЕ ШАГИ

1. Применить critical улучшения
2. Применить high priority улучшения
3. Протестировать все изменения
4. Повторить анализ для проверки

---

**Статус**: Анализ завершён, улучшения сгенерированы, готовы к применению
"""
    
    report_file = Path("d:/bybit_strategy_tester_v2/DEEPSEEK_SELF_IMPROVEMENT_REPORT.md")
    report_file.write_text(report, encoding='utf-8')
    
    print(f"✅ Отчёт создан: {report_file}")
    print(f"📊 Размер отчёта: {len(report)} символов")


async def main():
    """
    Главная функция - полный цикл самоанализа и улучшений
    """
    print("\n" + "="*80)
    print("🚀 DeepSeek AI Robot - Глубокий Самоанализ и Улучшение")
    print("="*80)
    print("\nЭтот процесс включает:")
    print("  1️⃣ Анализ кода через DeepSeek API")
    print("  2️⃣ Консультация с Perplexity AI")
    print("  3️⃣ Генерация улучшений через DeepSeek")
    print("  4️⃣ Создание комплексного отчёта")
    print("\n⏳ Это займёт 3-5 минут...")
    
    try:
        # Шаг 1: Анализ
        analysis_result = await analyze_robot_code_with_deepseek()
        if not analysis_result["success"]:
            print("\n❌ Анализ провалился, остановка")
            return
        
        # Шаг 2: Консультация
        consultation_result = await consult_perplexity_for_improvements()
        if not consultation_result["success"]:
            print("\n⚠️  Консультация частично провалилась, продолжаем")
        
        # Шаг 3: Генерация улучшений
        improvements_result = await generate_improvements_with_deepseek()
        if not improvements_result["success"]:
            print("\n❌ Генерация улучшений провалилась, остановка")
            return
        
        # Шаг 4: Отчёт
        await create_comprehensive_report()
        
        print("\n" + "="*80)
        print("✅ САМОАНАЛИЗ ЗАВЕРШЁН УСПЕШНО!")
        print("="*80)
        print("\n📄 Созданные файлы:")
        print("  • deepseek_self_analysis_result.json")
        print("  • perplexity_consultation_result.json")
        print("  • deepseek_improvements.json")
        print("  • DEEPSEEK_SELF_IMPROVEMENT_REPORT.md")
        
        print("\n🔧 Следующий шаг: Применить улучшения")
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
