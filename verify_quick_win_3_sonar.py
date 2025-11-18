"""
Quick Win #3 Verification with Sonar Pro
Используем Sonar Pro для детального code review
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "mcp-server"))

from multi_agent_router import get_router, TaskType


async def verify_with_sonar():
    """Верификация через Sonar Pro"""
    router = get_router()
    
    print("=" * 80)
    print("🔍 SONAR PRO CODE REVIEW - Quick Win #3")
    print("=" * 80)
    
    review_prompt = """
Analyze utility functions refactoring in Bybit Strategy Tester project:

FILES CREATED:
1. frontend/src/utils/formatting.ts - TypeScript formatting utilities (15 functions)
2. backend/utils/formatting.py - Python formatting utilities (11 functions)
3. backend/utils/__init__.py - Module exports

REVIEW ASPECTS:
1. Code quality and structure (rate 1-10)
2. Documentation completeness (JSDoc/docstrings)
3. Type safety (TypeScript types, Python type hints)
4. Error handling (null/None/NaN cases)
5. Performance considerations
6. Best practices adherence
7. Testing recommendations

FUNCTIONS IMPLEMENTED:
Frontend: formatNumber, formatCurrency, formatPercentage, formatDateTime, formatDate, 
formatDuration, formatRelativeTime, formatValueWithUnit, formatSignedValueWithUnit, 
formatQuantity, toFiniteNumber, toTimestamp

Backend: format_number, format_percentage, format_currency, format_timestamp, 
format_duration_seconds, format_duration_minutes, format_bytes, format_large_number,
safe_float, safe_int, truncate_string

Provide detailed code review with ratings and specific recommendations.
"""
    
    print("\n📤 Sending to Sonar Pro...\n")
    
    result = await router.route(
        task_type=TaskType.AUDIT,
        data={"query": review_prompt}
    )
    
    if result.get("status") == "success":
        print(f"✅ Agent: {result.get('agent')}")
        print(f"✅ Model: {result.get('model', 'unknown')}")
        print("\n" + "=" * 80)
        print("CODE REVIEW:")
        print("=" * 80)
        print(result.get("result"))
        print("\n" + "=" * 80)
    else:
        print(f"❌ Error: {result.get('error')}")
    
    return result


async def get_migration_strategy():
    """Получить стратегию миграции"""
    router = get_router()
    
    print("\n" + "=" * 80)
    print("📋 MIGRATION STRATEGY REQUEST")
    print("=" * 80)
    
    migration_prompt = """
Provide step-by-step migration strategy for utility functions refactoring:

CURRENT STATE:
- formatNumber duplicated in BacktestDetailPage.tsx (line 154)
- formatCurrency in HomePage.tsx (line 134)
- formatPercentage in HomePage.tsx (line 140)
- formatDate in WalkForwardPage.tsx (line 158)
- formatNumber in MetricsCards.tsx (line 63)

NEW MODULES:
- frontend/src/utils/formatting.ts (centralized)
- backend/utils/formatting.py (centralized)

PROVIDE:
1. Import statements to add
2. Functions to remove from each file
3. Testing checklist before migration
4. Risk mitigation steps
5. Rollback plan if issues occur

Be specific with line numbers and code examples.
"""
    
    print("\n📤 Requesting migration strategy...\n")
    
    result = await router.route(
        task_type=TaskType.DEEP_REASONING,
        data={"query": migration_prompt}
    )
    
    if result.get("status") == "success":
        print(f"✅ Agent: {result.get('agent')}")
        print("\n" + "=" * 80)
        print("MIGRATION STRATEGY:")
        print("=" * 80)
        print(result.get("result"))
        print("\n" + "=" * 80)
    
    return result


async def main():
    """Main execution"""
    print("\n" + "=" * 80)
    print("🚀 QUICK WIN #3 - SONAR PRO VERIFICATION")
    print("=" * 80)
    
    # Code review
    review = await verify_with_sonar()
    
    # Wait
    await asyncio.sleep(2)
    
    # Migration strategy
    migration = await get_migration_strategy()
    
    print("\n" + "=" * 80)
    print("✅ VERIFICATION COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
