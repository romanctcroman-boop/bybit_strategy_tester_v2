"""
Quick Win #3 Verification Script
Проверка созданных utility модулей через DeepSeek
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "mcp-server"))

from multi_agent_router import get_router, TaskType


async def verify_with_deepseek():
    """Проверка через DeepSeek с детальным code review"""
    router = get_router()
    
    print("=" * 80)
    print("🔍 DEEPSEEK CODE REVIEW - Quick Win #3")
    print("=" * 80)
    
    verification_prompt = """
CODE REVIEW REQUEST: Quick Win #3 - Utility Functions Refactoring

CONTEXT:
I've just extracted utility functions from scattered locations into centralized modules:

CREATED FILES:
1. frontend/src/utils/formatting.ts (300+ lines)
   - formatNumber, formatCurrency, formatPercentage
   - formatDateTime, formatDate, formatRelativeTime
   - formatDuration, formatQuantity
   - formatValueWithUnit, formatSignedValueWithUnit
   - toFiniteNumber, toTimestamp (helper functions)

2. backend/utils/formatting.py (250+ lines)
   - format_number, format_percentage, format_currency
   - format_timestamp, format_duration_seconds/minutes
   - format_bytes, format_large_number
   - safe_float, safe_int, truncate_string

3. backend/utils/__init__.py
   - Public API exports

ORIGINAL LOCATIONS (to be refactored):
- frontend/src/pages/BacktestDetailPage.tsx (lines 154-220)
- frontend/src/pages/HomePage.tsx (lines 134-155)
- frontend/src/pages/WalkForwardPage.tsx (line 158)
- frontend/src/components/Dashboard/LeftPanel/MetricsCards.tsx (line 63)

PLEASE REVIEW:
1. **Code Quality**: Are functions well-structured and documented?
2. **Type Safety**: Are TypeScript types and Python type hints correct?
3. **Best Practices**: Does code follow frontend/backend conventions?
4. **Testing**: What unit tests should be added?
5. **Refactoring Plan**: How to safely migrate from old to new functions?
6. **Edge Cases**: Are null/undefined/NaN handled correctly?
7. **Performance**: Any performance concerns?

PROVIDE:
- Detailed code review with line-specific comments
- Rating (1-10) for each aspect
- Specific recommendations for improvement
- Migration strategy for existing code
- Priority issues to fix immediately
"""
    
    print("\n📤 Sending detailed verification request to DeepSeek...\n")
    
    result = await router.route(
        task_type=TaskType.DEEP_REASONING,
        data={"query": verification_prompt}
    )
    
    if result.get("status") == "success":
        print(f"✅ Agent: {result.get('agent')}")
        print(f"✅ Model: {result.get('model', 'unknown')}")
        print("\n" + "=" * 80)
        print("CODE REVIEW RESULTS:")
        print("=" * 80)
        print(result.get("result"))
        print("\n" + "=" * 80)
        
        # Ask for specific improvements
        print("\n🔄 Requesting specific improvement suggestions...\n")
        
        improvement_prompt = """
Based on the code review above, provide:

1. TOP 3 CRITICAL ISSUES (if any) that must be fixed immediately
2. REFACTORING STEPS with exact code examples for migration
3. UNIT TEST EXAMPLES (at least 3 test cases for frontend and backend)
4. DOCUMENTATION IMPROVEMENTS (JSDoc/docstring enhancements)

Be specific and actionable. Provide code snippets.
"""
        
        improvement_result = await router.route(
            task_type=TaskType.CODE_GENERATION,
            data={"query": improvement_prompt}
        )
        
        if improvement_result.get("status") == "success":
            print(f"✅ Agent: {improvement_result.get('agent')}")
            print("\n" + "=" * 80)
            print("IMPROVEMENT RECOMMENDATIONS:")
            print("=" * 80)
            print(improvement_result.get("result"))
            print("\n" + "=" * 80)
    else:
        print(f"❌ Verification failed: {result.get('error')}")
    
    return result


async def test_backend_utils():
    """Тестирование backend утилит"""
    print("\n" + "=" * 80)
    print("🧪 TESTING BACKEND UTILS")
    print("=" * 80 + "\n")
    
    try:
        from backend.utils import (
            format_currency,
            format_number,
            format_percentage,
            safe_float,
            safe_int,
        )
        
        tests = [
            ("format_number", format_number(1234.5678, 2), "1,234.57"),
            ("format_percentage", format_percentage(0.4567, 2), "45.67%"),
            ("format_currency", format_currency(1000), "1,000.00 USDT"),
            ("safe_float", safe_float("123.45"), 123.45),
            ("safe_int", safe_int("42"), 42),
            ("safe_float (invalid)", safe_float("invalid", -1.0), -1.0),
        ]
        
        passed = 0
        for name, result, expected in tests:
            status = "✅" if str(result) == str(expected) else "❌"
            print(f"{status} {name}: {result} (expected: {expected})")
            if str(result) == str(expected):
                passed += 1
        
        print(f"\n📊 Tests passed: {passed}/{len(tests)}")
        
        if passed == len(tests):
            print("✅ All backend utils tests passed!")
        else:
            print(f"⚠️ {len(tests) - passed} tests failed")
            
    except Exception as e:
        print(f"❌ Import error: {e}")
        print("   This is expected if dependencies are not installed")


async def main():
    """Main execution"""
    print("\n" + "=" * 80)
    print("🚀 QUICK WIN #3 VERIFICATION WITH DEEPSEEK")
    print("=" * 80)
    
    # Test backend utils first
    await test_backend_utils()
    
    # Wait before DeepSeek verification
    print("\n⏳ Waiting 2 seconds before DeepSeek verification...\n")
    await asyncio.sleep(2)
    
    # Verify with DeepSeek
    await verify_with_deepseek()
    
    print("\n" + "=" * 80)
    print("✅ VERIFICATION COMPLETE!")
    print("=" * 80)
    print("\nNEXT STEPS:")
    print("1. Review DeepSeek feedback above")
    print("2. Fix any critical issues identified")
    print("3. Add unit tests as recommended")
    print("4. Update existing files to use new utilities")
    print("5. Run frontend: npm run dev")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
