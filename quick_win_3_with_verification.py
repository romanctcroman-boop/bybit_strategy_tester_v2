"""
Quick Win Implementation & Verification Script
Реализация с двойным контролем через DeepSeek
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "mcp-server"))

from multi_agent_router import get_router, TaskType


async def verify_implementation(task_name: str, changes_description: str, files_modified: list[str]):
    """Проверка реализации через DeepSeek"""
    router = get_router()
    
    prompt = f"""
VERIFICATION REQUEST: {task_name}

Changes made:
{changes_description}

Files modified:
{', '.join(files_modified)}

Please verify:
1. Code quality - are the changes well-structured?
2. Best practices - does it follow Python/TypeScript standards?
3. Potential issues - any bugs or problems?
4. Testing needs - what tests should be added?
5. Overall assessment - approve or suggest improvements?

Provide a detailed code review.
"""
    
    result = await router.route(
        task_type=TaskType.DEEP_REASONING,
        data={"query": prompt}
    )
    
    return result


async def implement_quick_win_3():
    """Quick Win #3: Refactor utility functions"""
    print("=" * 80)
    print("🚀 Quick Win #3: Refactor Utility Functions")
    print("=" * 80)
    
    # Step 1: Find utility functions
    print("\n📋 Step 1: Scanning codebase for utility functions...")
    
    files_to_check = [
        "backend/services/data_service.py",
        "backend/core/backtest.py",
        "frontend/src/pages/BacktestDetailPage.tsx",
        "frontend/src/components/MonteCarloTab.tsx",
    ]
    
    router = get_router()
    
    scan_prompt = """
Please identify common utility functions that should be extracted to a separate module.
Look for:
1. Formatting functions (numbers, dates, currencies)
2. Calculation helpers (percentages, ratios)
3. Data transformation utilities
4. Repeated code patterns

List files to check:
- backend/services/data_service.py
- backend/core/backtest.py  
- frontend/src/pages/BacktestDetailPage.tsx

Provide specific function names and their locations.
"""
    
    print("   Analyzing backend files with DeepSeek...")
    scan_result = await router.route(
        task_type=TaskType.AUDIT,
        data={"query": scan_prompt}
    )
    
    if scan_result.get("status") == "success":
        print(f"\n✅ Scan complete! Agent: {scan_result.get('agent')}")
        print(f"\n{scan_result.get('result')[:500]}...\n")
    
    return scan_result


async def main():
    """Main execution with verification"""
    print("\n" + "=" * 80)
    print("🔍 QUICK WIN #3: IMPLEMENTATION WITH DEEPSEEK VERIFICATION")
    print("=" * 80 + "\n")
    
    # Implement
    result = await implement_quick_win_3()
    
    print("\n" + "=" * 80)
    print("⏳ Waiting 3 seconds before verification...")
    print("=" * 80)
    await asyncio.sleep(3)
    
    # Verify
    print("\n" + "=" * 80)
    print("🔍 VERIFICATION PHASE - DeepSeek Code Review")
    print("=" * 80 + "\n")
    
    verification = await verify_implementation(
        task_name="Quick Win #3: Utility Functions Refactor",
        changes_description="""
        Identified utility functions scattered across codebase.
        Plan to create:
        - backend/utils/formatting.py (number, date, currency formatters)
        - frontend/src/utils/formatting.ts (same for frontend)
        """,
        files_modified=["(pending - analysis phase)"]
    )
    
    if verification.get("status") == "success":
        print(f"✅ Verification complete! Agent: {verification.get('agent')}")
        print(f"\n{verification.get('result')}\n")
    
    print("\n" + "=" * 80)
    print("✅ Quick Win #3 Analysis Complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
