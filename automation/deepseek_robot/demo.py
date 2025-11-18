"""
🚀 DeepSeek AI Robot - Демонстрация возможностей

Полная демонстрация:
1. Циклический анализ проекта
2. Генерация исправлений через DeepSeek
3. Валидация через тесты
4. Collaborative analysis (DeepSeek + Perplexity + Copilot)
5. Достижение 100% качества

Author: DeepSeek AI + GitHub Copilot + Perplexity AI
Date: 2025-11-08
"""

import asyncio
import json
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.deepseek_robot.robot import (
    DeepSeekRobot,
    AutonomyLevel,
    QualityMetrics
)
from automation.deepseek_robot.ai_integrations import (
    DeepSeekClient,
    PerplexityClient,
    CopilotIntegration,
    AICollaborationOrchestrator
)


async def demo_1_basic_robot():
    """
    Demo 1: Базовое использование робота
    
    Показывает:
    - Создание робота
    - Запуск одного цикла
    - Метрики качества
    """
    print("\n" + "=" * 80)
    print("🎬 DEMO 1: Basic Robot Usage")
    print("=" * 80)
    
    # Создаём робота
    robot = DeepSeekRobot(
        project_root=Path.cwd(),
        autonomy_level=AutonomyLevel.SEMI_AUTO
    )
    
    # Запускаем один цикл
    print("\n📋 Running single improvement cycle...")
    result = await robot.run_improvement_cycle()
    
    # Показываем результат
    print("\n📊 Cycle Results:")
    print(f"  Problems found: {result.problems_found}")
    print(f"  Fixes applied: {result.fixes_applied}")
    print(f"  Fixes failed: {result.fixes_failed}")
    print(f"  Quality before: {result.quality_before:.1f}%")
    print(f"  Quality after: {result.quality_after:.1f}%")
    print(f"  Improvement: {result.quality_after - result.quality_before:+.1f}%")
    print(f"  Duration: {result.duration_seconds:.1f}s")
    
    return result


async def demo_2_until_perfect():
    """
    Demo 2: Улучшение до 100%
    
    Показывает:
    - Циклическое улучшение
    - Достижение target quality
    - Финальный отчёт
    """
    print("\n" + "=" * 80)
    print("🎬 DEMO 2: Improvement Until Perfect")
    print("=" * 80)
    
    robot = DeepSeekRobot(
        project_root=Path.cwd(),
        autonomy_level=AutonomyLevel.FULL_AUTO
    )
    
    # Запускаем до 95% (100% сложно достичь)
    print("\n🎯 Target: 95% quality")
    print("🔄 Max iterations: 5")
    
    result = await robot.run_until_perfect(
        target_quality=95.0,
        max_iterations=5
    )
    
    # Финальный отчёт
    print("\n📊 Final Report:")
    print(json.dumps(result, indent=2))
    
    return result


async def demo_3_deepseek_analysis():
    """
    Demo 3: DeepSeek Code Analysis
    
    Показывает:
    - Анализ кода через DeepSeek API
    - Генерация исправлений
    - Рефакторинг
    """
    print("\n" + "=" * 80)
    print("🎬 DEMO 3: DeepSeek Code Analysis")
    print("=" * 80)
    
    deepseek = DeepSeekClient(model="deepseek-coder", temperature=0.1)
    
    # Пример 1: Анализ кода с багом
    print("\n1️⃣ Analyzing buggy code...")
    buggy_code = """
def calculate_average(numbers):
    total = sum(numbers)
    return total / len(numbers)
"""
    
    result = await deepseek.analyze_code(
        code=buggy_code,
        instruction="Find potential bugs and suggest fixes",
        context="Python 3.13, production code"
    )
    
    print(f"\n📋 DeepSeek Analysis:")
    print(f"  Success: {result.success}")
    print(f"  Tokens: {result.tokens_used}")
    print(f"\n  Response:\n{result.content[:500]}...")
    
    # Пример 2: Генерация исправления
    print("\n2️⃣ Generating fix...")
    fix_result = await deepseek.generate_fix(
        problem_description="ZeroDivisionError when numbers list is empty",
        original_code=buggy_code
    )
    
    print(f"\n✅ Fixed code:\n{fix_result.content}")
    
    return result


async def demo_4_perplexity_research():
    """
    Demo 4: Perplexity Research
    
    Показывает:
    - Поиск best practices
    - Исследование технологий
    - Поиск решений проблем
    """
    print("\n" + "=" * 80)
    print("🎬 DEMO 4: Perplexity Research")
    print("=" * 80)
    
    perplexity = PerplexityClient(model="sonar-pro")
    
    # Пример 1: Best practices
    print("\n1️⃣ Researching best practices...")
    research = await perplexity.research_best_practices(
        topic="async error handling",
        language="python"
    )
    
    print(f"\n📚 Best Practices:")
    print(f"  Success: {research.success}")
    print(f"  Tokens: {research.tokens_used}")
    print(f"\n  Response:\n{research.content[:500]}...")
    
    # Пример 2: Поиск решения
    print("\n2️⃣ Finding solution...")
    solution = await perplexity.find_solution(
        problem="How to prevent memory leaks in asyncio event loops?",
        context="Python 3.13, long-running application"
    )
    
    print(f"\n💡 Solution:")
    print(f"{solution.content[:500]}...")
    
    return research


async def demo_5_collaborative_analysis():
    """
    Demo 5: Collaborative AI Analysis
    
    Показывает:
    - DeepSeek: анализ и fix
    - Perplexity: best practices
    - Copilot: валидация
    - Консолидированный результат
    """
    print("\n" + "=" * 80)
    print("🎬 DEMO 5: Collaborative AI Analysis")
    print("=" * 80)
    
    orchestrator = AICollaborationOrchestrator(Path.cwd())
    
    # Проблемный код
    problematic_code = """
async def fetch_data(url):
    response = await httpx.get(url)
    return response.json()
"""
    
    # Совместный анализ
    result = await orchestrator.collaborative_analysis(
        code=problematic_code,
        problem="Missing error handling and timeout",
        context="Production API client, Python 3.13"
    )
    
    print("\n📊 Collaborative Result:")
    print(json.dumps(result, indent=2))
    
    return result


async def demo_6_quality_metrics():
    """
    Demo 6: Quality Metrics
    
    Показывает:
    - Расчёт метрик качества
    - Весовые коэффициенты
    - Общее качество
    """
    print("\n" + "=" * 80)
    print("🎬 DEMO 6: Quality Metrics")
    print("=" * 80)
    
    # Пример метрик
    metrics = QualityMetrics(
        code_quality=85.0,       # 40% вес
        test_quality=90.0,       # 30% вес
        architecture_quality=80.0,  # 20% вес
        documentation_quality=75.0  # 10% вес
    )
    
    print(f"\n📊 Quality Breakdown:")
    print(f"  Code Quality: {metrics.code_quality:.1f}% (weight: 40%)")
    print(f"  Test Quality: {metrics.test_quality:.1f}% (weight: 30%)")
    print(f"  Architecture: {metrics.architecture_quality:.1f}% (weight: 20%)")
    print(f"  Documentation: {metrics.documentation_quality:.1f}% (weight: 10%)")
    print(f"\n  ⭐ Total Quality: {metrics.total:.1f}%")
    
    return metrics


async def demo_all():
    """Запуск всех демо"""
    
    print("=" * 80)
    print("🤖 DeepSeek AI Robot - Full Demonstration")
    print("=" * 80)
    print("\nThis demonstration will show:")
    print("1. Basic robot usage")
    print("2. Improvement until perfect")
    print("3. DeepSeek code analysis")
    print("4. Perplexity research")
    print("5. Collaborative AI analysis")
    print("6. Quality metrics")
    print("\n" + "=" * 80)
    
    # Demo 1
    try:
        await demo_1_basic_robot()
    except Exception as e:
        print(f"\n⚠️  Demo 1 failed: {e}")
    
    await asyncio.sleep(1)
    
    # Demo 2
    try:
        await demo_2_until_perfect()
    except Exception as e:
        print(f"\n⚠️  Demo 2 failed: {e}")
    
    await asyncio.sleep(1)
    
    # Demo 3
    try:
        await demo_3_deepseek_analysis()
    except Exception as e:
        print(f"\n⚠️  Demo 3 failed: {e}")
    
    await asyncio.sleep(1)
    
    # Demo 4
    try:
        await demo_4_perplexity_research()
    except Exception as e:
        print(f"\n⚠️  Demo 4 failed: {e}")
    
    await asyncio.sleep(1)
    
    # Demo 5
    try:
        await demo_5_collaborative_analysis()
    except Exception as e:
        print(f"\n⚠️  Demo 5 failed: {e}")
    
    await asyncio.sleep(1)
    
    # Demo 6
    try:
        await demo_6_quality_metrics()
    except Exception as e:
        print(f"\n⚠️  Demo 6 failed: {e}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("✅ All Demonstrations Complete!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review the outputs above")
    print("2. Check .copilot/ directory for validation requests")
    print("3. Run robot on your project: python -m automation.deepseek_robot.robot")
    print("4. Read documentation: automation/deepseek_robot/README.md")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    # Выбор демо
    import sys
    
    if len(sys.argv) > 1:
        demo_name = sys.argv[1]
        
        demos = {
            "1": demo_1_basic_robot,
            "2": demo_2_until_perfect,
            "3": demo_3_deepseek_analysis,
            "4": demo_4_perplexity_research,
            "5": demo_5_collaborative_analysis,
            "6": demo_6_quality_metrics,
            "all": demo_all
        }
        
        demo_func = demos.get(demo_name)
        if demo_func:
            asyncio.run(demo_func())
        else:
            print(f"Unknown demo: {demo_name}")
            print(f"Available: {', '.join(demos.keys())}")
    else:
        # По умолчанию запускаем все
        asyncio.run(demo_all())
