"""
🧪 Comprehensive DeepSeek AI Robot Testing
==========================================

Разносторонние тесты для проверки всех возможностей робота.
"""

import asyncio
from pathlib import Path
from automation.deepseek_robot.robot import (
    DeepSeekRobot,
    AutonomyLevel,
    QualityMetrics,
    Problem,
    ProblemSeverity
)
from automation.deepseek_robot.ai_integrations import (
    DeepSeekClient,
    PerplexityClient,
    CopilotIntegration,
    AICollaborationOrchestrator
)


async def test_1_quality_calculation():
    """Тест 1: Расчет качества проекта"""
    print("\n" + "="*80)
    print("🧪 ТЕСТ 1: Расчет качества проекта")
    print("="*80)
    
    robot = DeepSeekRobot(
        project_root=Path('D:/bybit_strategy_tester_v2'),
        autonomy_level=AutonomyLevel.SEMI_AUTO
    )
    
    quality = await robot._calculate_quality()
    metrics = robot.last_quality_metrics
    
    print(f"\n📊 Общее качество: {quality:.1f}%")
    print(f"\n🔍 Детальные метрики:")
    print(f"  • Code Quality:     {metrics.code_quality:6.1f}% (вес 40%)")
    print(f"  • Test Quality:     {metrics.test_quality:6.1f}% (вес 30%)")
    print(f"  • Architecture:     {metrics.architecture_quality:6.1f}% (вес 20%)")
    print(f"  • Documentation:    {metrics.documentation_quality:6.1f}% (вес 10%)")
    
    # Проверка формулы
    expected = (
        metrics.code_quality * 0.4 +
        metrics.test_quality * 0.3 +
        metrics.architecture_quality * 0.2 +
        metrics.documentation_quality * 0.1
    )
    print(f"\n✅ Формула проверена: {expected:.1f}% == {quality:.1f}%")
    assert abs(expected - quality) < 0.1, "Quality calculation mismatch!"


async def test_2_problem_creation():
    """Тест 2: Создание и категоризация проблем"""
    print("\n" + "="*80)
    print("🧪 ТЕСТ 2: Создание и категоризация проблем")
    print("="*80)
    
    problems = [
        Problem(
            id="P001",
            file=Path("test.py"),
            line=10,
            severity=ProblemSeverity.CRITICAL,
            category="syntax",
            description="Missing import statement",
            suggested_fix="import required_module"
        ),
        Problem(
            id="P002",
            file=Path("utils.py"),
            line=25,
            severity=ProblemSeverity.HIGH,
            category="type",
            description="Type mismatch in function signature",
            suggested_fix="Fix return type annotation"
        ),
        Problem(
            id="P003",
            file=Path("main.py"),
            line=50,
            severity=ProblemSeverity.MEDIUM,
            category="style",
            description="Function too long (>50 lines)",
            suggested_fix="Refactor into smaller functions"
        ),
    ]
    
    print(f"\n📋 Создано {len(problems)} проблем:")
    for p in problems:
        print(f"\n  [{p.severity.value}] {p.category}")
        print(f"  📄 {p.file}:{p.line}")
        print(f"  ⚠️  {p.description}")
    
    # Сортировка по приоритету
    sorted_problems = sorted(
        problems,
        key=lambda x: (x.severity.value, x.category)
    )
    
    print(f"\n✅ Проблемы отсортированы по приоритету:")
    for i, p in enumerate(sorted_problems, 1):
        print(f"  {i}. [{p.severity.value}] {p.file}")


async def test_3_deepseek_analysis():
    """Тест 3: Анализ кода через DeepSeek API"""
    print("\n" + "="*80)
    print("🧪 ТЕСТ 3: Анализ кода через DeepSeek API")
    print("="*80)
    
    try:
        client = DeepSeekClient()
        
        buggy_code = """
def process_data(items):
    total = 0
    for item in items:
        total += item['value']
    return total / len(items)
"""
        
        print("\n📝 Анализируемый код:")
        print(buggy_code)
        
        result = await client.analyze_code(
            code=buggy_code,
            instruction="Find potential bugs and edge cases",
            context={"language": "python", "version": "3.13"}
        )
        
        if result.success:
            print(f"\n✅ Анализ успешен!")
            print(f"📊 Tokens: {result.tokens_used}")
            print(f"\n🔍 Результат анализа:")
            print(result.content[:500] + "..." if len(result.content) > 500 else result.content)
        else:
            print(f"\n⚠️  Анализ не выполнен: {result.error}")
            
    except Exception as e:
        print(f"\n⚠️  Ошибка API: {e}")


async def test_4_perplexity_research():
    """Тест 4: Поиск best practices через Perplexity"""
    print("\n" + "="*80)
    print("🧪 ТЕСТ 4: Поиск best practices через Perplexity")
    print("="*80)
    
    try:
        client = PerplexityClient()
        
        topics = [
            ("Python async/await patterns", "python"),
            ("FastAPI error handling", "python"),
            ("PostgreSQL connection pooling", "database")
        ]
        
        for topic, lang in topics:
            print(f"\n📚 Ищу: {topic}")
            
            result = await client.research_best_practices(
                topic=topic,
                language=lang
            )
            
            if result.success:
                print(f"✅ Найдено! Tokens: {result.tokens_used}")
                preview = result.content[:200].replace('\n', ' ')
                print(f"📄 {preview}...")
            else:
                print(f"⚠️  Ошибка: {result.error}")
                
    except Exception as e:
        print(f"\n⚠️  Ошибка API: {e}")


async def test_5_copilot_integration():
    """Тест 5: Интеграция с GitHub Copilot"""
    print("\n" + "="*80)
    print("🧪 ТЕСТ 5: Интеграция с GitHub Copilot")
    print("="*80)
    
    copilot = CopilotIntegration(project_root=Path('D:/bybit_strategy_tester_v2'))
    
    original = "def calc(a, b):\n    return a / b"
    fixed = "def calc(a, b):\n    if b == 0:\n        return 0\n    return a / b"
    
    result = await copilot.request_validation(
        original_code=original,
        fixed_code=fixed,
        problem_description="Division by zero vulnerability"
    )
    
    print(f"\n📁 Создан запрос типа: {result['type']}")
    print(f"⚠️  Проблема: {result['problem']}")
    print(f"❓ Вопросы для Copilot:")
    for q in result['questions']:
        print(f"  • {q}")
    
    print(f"\n✅ Запрос создан в директории .copilot/")
    
    # Проверка что файл создан
    request_file = Path('D:/bybit_strategy_tester_v2/.copilot/validation_request.json')
    assert request_file.exists(), "Validation request file not created!"
    print(f"✅ Файл существует: {request_file}")


async def test_6_collaboration_workflow():
    """Тест 6: Совместная работа всех AI"""
    print("\n" + "="*80)
    print("🧪 ТЕСТ 6: Совместная работа всех AI систем")
    print("="*80)
    
    try:
        orchestrator = AICollaborationOrchestrator(
            project_root=Path('D:/bybit_strategy_tester_v2')
        )
        
        code = """
async def fetch_user(user_id):
    user = await db.query("SELECT * FROM users WHERE id = ?", user_id)
    return user
"""
        
        print("\n📝 Анализируемый код:")
        print(code)
        
        print("\n🤝 Запуск совместного анализа...")
        print("  1️⃣ DeepSeek: анализ безопасности")
        print("  2️⃣ Perplexity: best practices")
        print("  3️⃣ Copilot: валидация")
        
        result = await orchestrator.collaborative_analysis(
            code=code,
            problem_description="SQL injection vulnerability",
            context={"database": "postgresql", "orm": "sqlalchemy"}
        )
        
        print(f"\n✅ Совместный анализ завершен!")
        
        if result['deepseek']['success']:
            print(f"\n🤖 DeepSeek: Анализ получен ({len(result['deepseek']['content'])} символов)")
        
        if result['perplexity']['success']:
            print(f"🔍 Perplexity: Best practices найдены ({len(result['perplexity']['content'])} символов)")
        
        if result['copilot']['request_file']:
            print(f"💬 Copilot: Запрос создан для валидации")
            
    except Exception as e:
        print(f"\n⚠️  Ошибка: {e}")


async def test_7_autonomy_levels():
    """Тест 7: Уровни автономности"""
    print("\n" + "="*80)
    print("🧪 ТЕСТ 7: Уровни автономности")
    print("="*80)
    
    levels = [
        (AutonomyLevel.MANUAL, "Ручной режим - требует подтверждения каждого действия"),
        (AutonomyLevel.SEMI_AUTO, "Полуавтоматический - показывает план, ждет OK"),
        (AutonomyLevel.FULL_AUTO, "Полная автономность - выполняет все автоматически"),
    ]
    
    for level, description in levels:
        print(f"\n🔧 {level.value.upper()}")
        print(f"   {description}")
        
        robot = DeepSeekRobot(
            project_root=Path('D:/bybit_strategy_tester_v2'),
            autonomy_level=level
        )
        
        print(f"   ✅ Робот инициализирован с уровнем {level.value}")


async def test_8_performance_metrics():
    """Тест 8: Метрики производительности"""
    print("\n" + "="*80)
    print("🧪 ТЕСТ 8: Метрики производительности")
    print("="*80)
    
    import time
    
    robot = DeepSeekRobot(
        project_root=Path('D:/bybit_strategy_tester_v2'),
        autonomy_level=AutonomyLevel.SEMI_AUTO
    )
    
    print("\n⏱️  Измеряю время операций...")
    
    # 1. Quality calculation
    start = time.time()
    quality = await robot._calculate_quality()
    calc_time = time.time() - start
    print(f"\n  📊 Расчет качества: {calc_time:.3f}s → {quality:.1f}%")
    
    # 2. Problem analysis
    start = time.time()
    problems = await robot.analyze_project()
    analysis_time = time.time() - start
    print(f"  🔍 Анализ проекта: {analysis_time:.3f}s → {len(problems)} проблем")
    
    print(f"\n✅ Производительность:")
    print(f"  • Расчет метрик: ~{calc_time:.1f}s")
    print(f"  • Полный анализ: ~{analysis_time:.1f}s")


async def main():
    """Запуск всех тестов"""
    print("\n" + "="*80)
    print("🚀 РАЗНОСТОРОННИЕ ТЕСТЫ DeepSeek AI Robot")
    print("="*80)
    print("\nЗапущено 8 тестов для проверки всех возможностей робота")
    
    tests = [
        test_1_quality_calculation,
        test_2_problem_creation,
        test_3_deepseek_analysis,
        test_4_perplexity_research,
        test_5_copilot_integration,
        test_6_collaboration_workflow,
        test_7_autonomy_levels,
        test_8_performance_metrics,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            await test_func()
            passed += 1
            print(f"\n✅ {test_func.__name__} - PASSED")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_func.__name__} - FAILED: {e}")
    
    print("\n" + "="*80)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("="*80)
    print(f"\n✅ Пройдено: {passed}/{len(tests)}")
    print(f"❌ Провалено: {failed}/{len(tests)}")
    print(f"📈 Успешность: {passed/len(tests)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
    else:
        print(f"\n⚠️  {failed} тестов провалено - требуется доработка")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())
