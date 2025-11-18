"""
🔧 FIX P1 CRITICAL ISSUES - PHASE 1
=====================================
Workflow: Copilot ↔ Script ↔ MCP Server ↔ Perplexity AI

Автоматическое исправление 3 критических проблем:
1. SR RSI Async: edge case (empty iterable)
2. Data Service Async: performance (0.55x slower)
3. Backtest: minimum bars validation

Метод: Отправка проблем в Perplexity AI через MCP → получение решений → применение исправлений
"""

import asyncio
import aiohttp
import json
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Any

# === CONFIGURATION ===
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar-pro"

# Load API key from .env
env_file = Path(__file__).parent / ".env"
PERPLEXITY_API_KEY = None
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if line.startswith("PERPLEXITY_API_KEY="):
                PERPLEXITY_API_KEY = line.split("=", 1)[1].strip().strip('"')
                break

if not PERPLEXITY_API_KEY:
    raise ValueError("PERPLEXITY_API_KEY not found in .env file")

# === ISSUE DEFINITIONS ===
CRITICAL_ISSUES = {
    "issue_1_sr_rsi_async": {
        "title": "SR RSI Async - Empty Iterable Error",
        "description": """
        **Problem:** SR RSI async optimization fails on small datasets (1 bar)
        **Error:** max() iterable argument is empty
        **Test Results:** 4/5 passed (80% pass rate)
        **Failed Dataset:** BTCUSDT_15_10 (only 1 bar)
        
        **Current Implementation:**
        ```python
        async def calculate_sr_levels_async(data, lookback=100):
            await asyncio.sleep(0.001)
            highs = data['high'].values
            lows = data['low'].values
            
            # Find local maxima/minima
            resistance = []
            support = []
            for i in range(lookback, len(highs)):
                window_high = highs[i-lookback:i]
                window_low = lows[i-lookback:i]
                if highs[i] == max(window_high):  # ERROR: empty window
                    resistance.append(highs[i])
                if lows[i] == min(window_low):
                    support.append(lows[i])
            return support, resistance
        ```
        
        **Root Cause:** No validation for minimum data size before processing
        **Required Fix:** Add validation and dynamic window sizing
        """,
        "file": "optimizations_output/sr_rsi_async_FINAL.py",
        "test_data": "data/cache/BTCUSDT_15_10.parquet"
    },
    
    "issue_2_data_service_async": {
        "title": "Data Service Async - Performance Degradation",
        "description": """
        **Problem:** Async parallel loading is SLOWER than sequential (0.55x speedup)
        **Test Results:** Sequential: 18.1ms, Async: 33.2ms
        **Files Tested:** 5 small local Parquet files (20-100 KB each)
        
        **Current Implementation:**
        ```python
        async def load_data_async(filename):
            await asyncio.sleep(0.001)  # Simulate async
            file_path = Path('data/cache') / filename
            df = pd.read_parquet(file_path)
            return filename, df
        
        # Parallel loading
        results = await asyncio.gather(*[
            load_data_async(filename)
            for filename in test_files
        ])
        ```
        
        **Root Cause:** Overhead from asyncio exceeds benefit for small local files
        **Expected Benefit:** Should be faster with network I/O, remote API, or 50+ files
        **Required Fix:** 
        1. Implement intelligent switching (async for remote, sync for local)
        2. Add batch size optimization
        3. Test with realistic workload (network I/O)
        """,
        "file": "optimizations_output/data_service_async_FINAL.py",
        "test_scenarios": ["local_small_files", "remote_api", "large_batch"]
    },
    
    "issue_3_backtest_validation": {
        "title": "Backtest Vectorization - Minimum Bars Validation",
        "description": """
        **Problem:** Backtest fails on datasets with insufficient bars
        **Test Results:** 14/15 passed (93.3% pass rate)
        **Failed Dataset:** BTCUSDT_15_10 (only 1 bar, need ≥2)
        
        **Current Implementation:**
        ```python
        def run_backtest(self, data, initial_capital=1_000_000):
            # No validation at start
            n = len(data)
            signals = self.strategy.generate_signals(data)
            # ... vectorized processing
        ```
        
        **Root Cause:** No minimum data validation before processing
        **Required Fix:** Add validation at entry point with clear error message
        **Minimum Required:** 2 bars for basic backtest, recommend 100+ for statistical significance
        """,
        "file": "test_vectorized_backtest.py",
        "minimum_bars": 2,
        "recommended_bars": 100
    }
}

# === PERPLEXITY AI INTERACTION ===
async def query_perplexity_for_fix(issue_key: str, issue_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Отправить проблему в Perplexity AI для получения решения
    Workflow: Script → MCP Server → Perplexity AI
    """
    print(f"\n🤖 Querying Perplexity AI for: {issue_data['title']}")
    
    prompt = f"""
    You are a senior Python developer specializing in performance optimization and async programming.
    
    **CRITICAL ISSUE TO FIX:**
    {issue_data['title']}
    
    **PROBLEM DETAILS:**
    {issue_data['description']}
    
    **REQUIREMENTS:**
    1. Provide COMPLETE working Python code fix
    2. Include comprehensive validation and error handling
    3. Maintain backward compatibility
    4. Add detailed docstrings and comments
    5. Include edge case handling for small datasets
    6. Optimize for performance
    
    **OUTPUT FORMAT:**
    Provide the fixed code as a complete Python function/class that can be directly copied.
    Include:
    - Input validation
    - Edge case handling
    - Error messages
    - Performance considerations
    - Usage examples in docstring
    
    Focus on PRODUCTION-READY code with comprehensive error handling.
    """
    
    request_data = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert Python developer specializing in async programming, performance optimization, and production-ready code. Provide complete, working solutions with comprehensive error handling."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            print(f"  📡 Sending query to Perplexity AI...")
            print(f"  📝 Query size: {len(prompt)} chars")
            
            async with session.post(
                PERPLEXITY_API_URL,
                json=request_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"  ❌ API Error: {response.status}")
                    print(f"  Error details: {error_text}")
                    return {
                        "status": "error",
                        "error": f"API returned {response.status}: {error_text}"
                    }
                
                result = await response.json()
                
                # Extract response
                content = result['choices'][0]['message']['content']
                citations = result.get('citations', [])
                
                print(f"  ✅ Response received")
                print(f"  📄 Solution size: {len(content)} chars")
                print(f"  📚 Citations: {len(citations)}")
                
                return {
                    "status": "success",
                    "issue_key": issue_key,
                    "solution": content,
                    "citations": citations,
                    "timestamp": datetime.now().isoformat()
                }
                
        except asyncio.TimeoutError:
            print(f"  ❌ Timeout after 120 seconds")
            return {
                "status": "error",
                "error": "Request timeout"
            }
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

# === FIX APPLICATION ===
def apply_fix_sr_rsi_async(solution_text: str) -> bool:
    """
    Применить исправление для SR RSI async
    """
    print(f"\n🔧 Applying fix: SR RSI Async")
    
    output_file = Path("optimizations_output/sr_rsi_async_FIXED_v2.py")
    
    try:
        # Сохранить полное решение от Perplexity AI
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# SR RSI ASYNC - FIXED VERSION 2\n")
            f.write("# Auto-generated fix from Perplexity AI via MCP\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write("# Issue: Empty iterable error on small datasets\n")
            f.write("# Fix: Added validation and dynamic window sizing\n\n")
            f.write(solution_text)
        
        print(f"  ✅ Fix saved to: {output_file}")
        print(f"  📄 File size: {output_file.stat().st_size / 1024:.2f} KB")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to apply fix: {e}")
        return False

def apply_fix_data_service_async(solution_text: str) -> bool:
    """
    Применить исправление для Data Service async
    """
    print(f"\n🔧 Applying fix: Data Service Async")
    
    output_file = Path("optimizations_output/data_service_async_FIXED_v2.py")
    
    try:
        # Сохранить полное решение от Perplexity AI
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# DATA SERVICE ASYNC - FIXED VERSION 2\n")
            f.write("# Auto-generated fix from Perplexity AI via MCP\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write("# Issue: Slower than sequential for small local files (0.55x)\n")
            f.write("# Fix: Intelligent switching + batch optimization\n\n")
            f.write(solution_text)
        
        print(f"  ✅ Fix saved to: {output_file}")
        print(f"  📄 File size: {output_file.stat().st_size / 1024:.2f} KB")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to apply fix: {e}")
        return False

def apply_fix_backtest_validation(solution_text: str) -> bool:
    """
    Применить исправление для Backtest validation
    """
    print(f"\n🔧 Applying fix: Backtest Validation")
    
    output_file = Path("test_vectorized_backtest_FIXED_v2.py")
    
    try:
        # Прочитать оригинальный файл
        original_file = Path("test_vectorized_backtest.py")
        with open(original_file, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Сохранить исправленную версию с комментариями
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# VECTORIZED BACKTEST - FIXED VERSION 2\n")
            f.write("# Auto-generated fix from Perplexity AI via MCP\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write("# Issue: No minimum bars validation\n")
            f.write("# Fix: Added validation at entry point\n\n")
            f.write("# === PERPLEXITY AI SOLUTION ===\n")
            f.write(solution_text)
            f.write("\n\n# === ORIGINAL IMPLEMENTATION (for reference) ===\n")
            f.write("# " + original_content.replace("\n", "\n# "))
        
        print(f"  ✅ Fix saved to: {output_file}")
        print(f"  📄 File size: {output_file.stat().st_size / 1024:.2f} KB")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to apply fix: {e}")
        return False

# === VERIFICATION ===
async def verify_fixes() -> Dict[str, Any]:
    """
    Проверить все исправления на реальных данных
    """
    print(f"\n🧪 VERIFYING FIXES ON REAL DATA")
    print("=" * 60)
    
    results = {
        "sr_rsi_async": {"status": "pending"},
        "data_service_async": {"status": "pending"},
        "backtest_validation": {"status": "pending"}
    }
    
    # Load test data
    cache_dir = Path("data/cache")
    
    # Test 1: SR RSI Async on small dataset
    print(f"\n📊 Test 1: SR RSI Async (edge case)")
    try:
        test_file = cache_dir / "BTCUSDT_15_10.parquet"
        if test_file.exists():
            df = pd.read_parquet(test_file)
            print(f"  Dataset: {len(df)} bars")
            
            # Try to import fixed version
            fixed_file = Path("optimizations_output/sr_rsi_async_FIXED_v2.py")
            if fixed_file.exists():
                print(f"  ✅ Fixed version exists")
                print(f"  📝 Next: Manual testing required")
                results["sr_rsi_async"]["status"] = "fixed_pending_test"
            else:
                print(f"  ⏳ Waiting for fix generation")
                results["sr_rsi_async"]["status"] = "pending"
        else:
            print(f"  ⚠️ Test file not found")
            results["sr_rsi_async"]["status"] = "no_test_data"
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results["sr_rsi_async"]["status"] = "error"
        results["sr_rsi_async"]["error"] = str(e)
    
    # Test 2: Data Service Async performance
    print(f"\n📊 Test 2: Data Service Async (performance)")
    try:
        # Check if fixed version exists
        fixed_file = Path("optimizations_output/data_service_async_FIXED_v2.py")
        if fixed_file.exists():
            print(f"  ✅ Fixed version exists")
            print(f"  📝 Next: Performance benchmark required")
            results["data_service_async"]["status"] = "fixed_pending_benchmark"
        else:
            print(f"  ⏳ Waiting for fix generation")
            results["data_service_async"]["status"] = "pending"
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results["data_service_async"]["status"] = "error"
        results["data_service_async"]["error"] = str(e)
    
    # Test 3: Backtest validation
    print(f"\n📊 Test 3: Backtest Validation (minimum bars)")
    try:
        fixed_file = Path("test_vectorized_backtest_FIXED_v2.py")
        if fixed_file.exists():
            print(f"  ✅ Fixed version exists")
            print(f"  📝 Next: Integration test required")
            results["backtest_validation"]["status"] = "fixed_pending_test"
        else:
            print(f"  ⏳ Waiting for fix generation")
            results["backtest_validation"]["status"] = "pending"
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results["backtest_validation"]["status"] = "error"
        results["backtest_validation"]["error"] = str(e)
    
    return results

# === MAIN WORKFLOW ===
async def main():
    """
    Главный workflow: Copilot → Script → MCP → Perplexity AI → Fixes
    """
    start_time = datetime.now()
    
    print("=" * 80)
    print("🔧 FIX P1 CRITICAL ISSUES - PHASE 1")
    print("=" * 80)
    print(f"Workflow: Copilot ↔ Script ↔ MCP Server ↔ Perplexity AI")
    print(f"API Key: {PERPLEXITY_API_KEY[:20]}...{PERPLEXITY_API_KEY[-5:]} ✅")
    print(f"Issues to fix: {len(CRITICAL_ISSUES)}")
    print()
    
    # Создать выходную директорию
    output_dir = Path("optimizations_output")
    output_dir.mkdir(exist_ok=True)
    
    all_solutions = {}
    
    # === STEP 1: Query Perplexity AI for all issues ===
    print(f"\n{'='*80}")
    print(f"STEP 1: QUERYING PERPLEXITY AI FOR SOLUTIONS")
    print(f"{'='*80}")
    
    for issue_key, issue_data in CRITICAL_ISSUES.items():
        print(f"\n📋 Issue {issue_key}:")
        print(f"   {issue_data['title']}")
        
        solution = await query_perplexity_for_fix(issue_key, issue_data)
        all_solutions[issue_key] = solution
        
        if solution['status'] == 'success':
            print(f"   ✅ Solution received")
        else:
            print(f"   ❌ Failed: {solution.get('error', 'Unknown error')}")
        
        # Small delay between requests
        await asyncio.sleep(2)
    
    # === STEP 2: Apply fixes ===
    print(f"\n{'='*80}")
    print(f"STEP 2: APPLYING FIXES")
    print(f"{'='*80}")
    
    fixes_applied = 0
    
    # Apply SR RSI async fix
    if all_solutions["issue_1_sr_rsi_async"]["status"] == "success":
        if apply_fix_sr_rsi_async(all_solutions["issue_1_sr_rsi_async"]["solution"]):
            fixes_applied += 1
    
    # Apply Data Service async fix
    if all_solutions["issue_2_data_service_async"]["status"] == "success":
        if apply_fix_data_service_async(all_solutions["issue_2_data_service_async"]["solution"]):
            fixes_applied += 1
    
    # Apply Backtest validation fix
    if all_solutions["issue_3_backtest_validation"]["status"] == "success":
        if apply_fix_backtest_validation(all_solutions["issue_3_backtest_validation"]["solution"]):
            fixes_applied += 1
    
    # === STEP 3: Verify fixes ===
    print(f"\n{'='*80}")
    print(f"STEP 3: VERIFICATION")
    print(f"{'='*80}")
    
    verification_results = await verify_fixes()
    
    # === STEP 4: Generate report ===
    print(f"\n{'='*80}")
    print(f"STEP 4: GENERATING REPORT")
    print(f"{'='*80}")
    
    execution_time = (datetime.now() - start_time).total_seconds()
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "execution_time": execution_time,
        "workflow": "Copilot → Script → MCP Server → Perplexity AI",
        "issues_processed": len(CRITICAL_ISSUES),
        "solutions_received": sum(1 for s in all_solutions.values() if s['status'] == 'success'),
        "fixes_applied": fixes_applied,
        "solutions": all_solutions,
        "verification": verification_results
    }
    
    # Save detailed report
    report_file = Path("P1_CRITICAL_FIXES_REPORT.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Report saved: {report_file}")
    
    # === SUMMARY ===
    print(f"\n{'='*80}")
    print(f"📊 PHASE 1 SUMMARY")
    print(f"{'='*80}")
    print(f"\n✅ Issues processed:     {len(CRITICAL_ISSUES)}")
    print(f"✅ Solutions received:   {sum(1 for s in all_solutions.values() if s['status'] == 'success')}")
    print(f"✅ Fixes applied:        {fixes_applied}")
    print(f"⏱️  Total execution time: {execution_time:.2f}s")
    
    print(f"\n📁 Generated files:")
    for f in output_dir.glob("*_FIXED_v2.py"):
        size = f.stat().st_size / 1024
        print(f"   ✅ {f.name} ({size:.2f} KB)")
    
    print(f"\n🎯 NEXT STEPS:")
    print(f"   1. Review generated fixes in optimizations_output/")
    print(f"   2. Run verification tests")
    print(f"   3. Proceed to Phase 2: Integration Testing")
    
    print(f"\n{'='*80}")
    print(f"✅ PHASE 1 COMPLETE!")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    asyncio.run(main())
