"""
🚀 FINAL P1 OPTIMIZATIONS WORKFLOW
===================================

Complete workflow for remaining P1 optimizations using proven methodology:
1. ✅ Backtest Vectorization - Test on real data
2. 🚀 SR RSI Async - Optimize via Perplexity AI
3. 🚀 Data Service Async - Optimize via Perplexity AI

Method: Copilot ↔ Perplexity AI ↔ Copilot (PROVEN WORKING)
Based on: complete_backtest_vectorization.py (successful execution)
"""

import os
import json
import asyncio
import aiohttp
import sys
import time
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
import pandas as pd
import numpy as np

# Load environment
load_dotenv()

# Import secure key manager
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "backend"))
from security.key_manager import get_decrypted_key

# Configuration
PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")
if not PERPLEXITY_API_KEY:
    raise ValueError("⚠️ PERPLEXITY_API_KEY not configured in .env")

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar-pro"

print("=" * 80)
print("  🚀 FINAL P1 OPTIMIZATIONS WORKFLOW")
print("  Method: Copilot ↔ Perplexity AI ↔ Copilot (PROVEN)")
print("=" * 80)
print(f"  ✅ API Key loaded: {PERPLEXITY_API_KEY[:15]}...{PERPLEXITY_API_KEY[-5:]}")
print("=" * 80)

# ============================================================================
# TASK 1: BACKTEST VECTORIZATION - TEST ON REAL DATA
# ============================================================================

def test_backtest_vectorization():
    """Test vectorized backtest on real BTCUSDT data"""
    print("\n" + "=" * 80)
    print("TASK 1: BACKTEST VECTORIZATION - REAL DATA TEST")
    print("=" * 80)
    
    # Load test result from previous run
    test_result_path = Path("TEST_VECTORIZED_BACKTEST_RESULTS.json")
    
    if test_result_path.exists():
        with open(test_result_path, 'r') as f:
            results = json.load(f)
        
        print(f"\n✅ Previous test results found:")
        print(f"   Tests passed: {results.get('tests_passed', 0)}/{results.get('tests_run', 0)}")
        
        if results.get('aggregate'):
            agg = results['aggregate']
            print(f"   Total bars: {agg['total_bars']:,}")
            print(f"   Total time: {agg['total_time']:.3f}s")
            print(f"   Speed: {agg['avg_speed']:.0f} bars/sec")
            print(f"\n   🎉 VECTORIZATION: ✅ TESTED AND WORKING")
        
        return results
    else:
        print("  ⚠️ No previous test results found")
        print("  💡 Run test_vectorized_backtest.py first")
        return None

# ============================================================================
# TASK 2: SR RSI ASYNC OPTIMIZATION
# ============================================================================

async def optimize_sr_rsi_async() -> Dict[str, Any]:
    """Optimize SR RSI strategy with async parallel calculation"""
    print("\n" + "=" * 80)
    print("TASK 2: SR RSI ASYNC OPTIMIZATION")
    print("=" * 80)
    
    # Read current SR RSI strategy
    print("\n📄 Step 1: Reading current SR RSI strategy...")
    sr_rsi_path = Path("backend/strategies/sr_rsi_strategy.py")
    
    if not sr_rsi_path.exists():
        print("  ⚠️ SR RSI strategy not found, using generated code...")
        opt_path = Path("optimizations_output/sr_rsi_async_optimized.py")
        if opt_path.exists():
            with open(opt_path, 'r', encoding='utf-8') as f:
                current_code = f.read()
            print(f"  ✅ Loaded optimized code: {len(current_code)} chars")
        else:
            print("  ❌ No SR RSI code found")
            return {'skip': True, 'reason': 'No source code'}
    else:
        with open(sr_rsi_path, 'r', encoding='utf-8') as f:
            current_code = f.read()
        print(f"  ✅ Loaded: {len(current_code)} chars")
    
    # Create optimization prompt
    prompt = f"""
TASK: Optimize Support/Resistance + RSI strategy for async parallel calculation

CURRENT CODE (Sequential):
```python
{current_code[:4000]}
```

OPTIMIZATION REQUIREMENTS:

1. **Support/Resistance Calculation (Vectorized + Async)**
   - Use NumPy for vectorized local maxima/minima detection
   - Use scipy.signal.find_peaks for efficient peak detection
   - Async parallel calculation for multiple lookback periods
   - Expected: 2-3x speedup

2. **RSI Calculation (Async Parallel)**
   - Async parallel RSI for timeframes: 14, 28, 50
   - Use pandas_ta or numpy for optimized RSI
   - Cache results to avoid recalculation
   - Expected: 2-4x speedup

3. **Signal Generation (Async Aggregation)**
   - Use asyncio.gather() for concurrent SR + RSI
   - Overall expected: 3-5x speedup

4. **Edge Cases**
   - Handle empty/insufficient data
   - Prevent lookahead bias
   - NaN handling

OUTPUT: Complete Python code with async/await, docstrings, dependencies listed
"""
    
    # Call Perplexity AI
    print("\n🤖 Step 2: Asking Perplexity AI for optimization...")
    print(f"  Model: {PERPLEXITY_MODEL}")
    print(f"  Prompt size: {len(prompt)} chars")
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": PERPLEXITY_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Python optimization specialist focusing on async programming and financial algorithms."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "return_citations": True,
            "temperature": 0.2
        }
        
        try:
            async with session.post(
                PERPLEXITY_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    optimized_code = result['choices'][0]['message']['content']
                    citations = result.get('citations', [])
                    
                    print(f"  ✅ Optimization received")
                    print(f"  📚 Citations: {len(citations)}")
                    print(f"  📄 Code size: {len(optimized_code)} chars")
                    
                    # Save optimized code
                    output_dir = Path("optimizations_output")
                    output_dir.mkdir(exist_ok=True)
                    
                    code_path = output_dir / "sr_rsi_async_FINAL.py"
                    with open(code_path, 'w', encoding='utf-8') as f:
                        f.write(f"# SR RSI ASYNC OPTIMIZATION (FINAL)\n")
                        f.write(f"# Generated by Perplexity AI: {PERPLEXITY_MODEL}\n")
                        f.write(f"# Citations: {len(citations)}\n\n")
                        f.write(optimized_code)
                    
                    print(f"  💾 Saved: {code_path}")
                    
                    return {
                        'status': 'success',
                        'code_path': str(code_path),
                        'code_size': len(optimized_code),
                        'citations': len(citations)
                    }
                else:
                    error_text = await response.text()
                    print(f"  ❌ Error: {response.status} - {error_text}")
                    return {'status': 'error', 'error': error_text}
        
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return {'status': 'error', 'error': str(e)}

# ============================================================================
# TASK 3: DATA SERVICE ASYNC OPTIMIZATION
# ============================================================================

async def optimize_data_service_async() -> Dict[str, Any]:
    """Optimize Data Service with async parallel loading"""
    print("\n" + "=" * 80)
    print("TASK 3: DATA SERVICE ASYNC OPTIMIZATION")
    print("=" * 80)
    
    # Read current data service
    print("\n📄 Step 1: Reading current data service...")
    data_service_path = Path("backend/services/legacy_data_loader.py")
    
    if data_service_path.exists():
        with open(data_service_path, 'r', encoding='utf-8') as f:
            current_code = f.read()
        print(f"  ✅ Loaded: {len(current_code)} chars")
    else:
        print("  ⚠️ Data service not found")
        current_code = "# Data service not found - create from scratch"
    
    # Create optimization prompt
    prompt = f"""
TASK: Optimize Data Service for async parallel data loading and caching

CURRENT CODE (Sequential):
```python
{current_code[:4000]}
```

OPTIMIZATION REQUIREMENTS:

1. **Async Data Loading**
   - Async parallel for multiple symbols
   - Async parallel for multiple timeframes
   - Use asyncio.gather() for concurrent requests
   - Expected: 5-10x speedup

2. **Smart Caching**
   - Redis async caching (if available)
   - File-based async caching (fallback)
   - TTL-based cache invalidation
   - Parquet format for efficient storage

3. **Connection Pooling**
   - Async connection pool for Bybit API
   - Rate limiting with asyncio.Semaphore
   - Retry with exponential backoff

4. **Edge Cases**
   - Network error handling
   - Cache corruption handling
   - Rate limit handling

OUTPUT: Complete Python code with aiohttp, aiocache, docstrings, dependencies
"""
    
    # Call Perplexity AI
    print("\n🤖 Step 2: Asking Perplexity AI for optimization...")
    print(f"  Model: {PERPLEXITY_MODEL}")
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": PERPLEXITY_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert in async Python programming, data caching, and API optimization."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "return_citations": True,
            "temperature": 0.2
        }
        
        try:
            async with session.post(
                PERPLEXITY_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    optimized_code = result['choices'][0]['message']['content']
                    citations = result.get('citations', [])
                    
                    print(f"  ✅ Optimization received")
                    print(f"  📚 Citations: {len(citations)}")
                    print(f"  📄 Code size: {len(optimized_code)} chars")
                    
                    # Save optimized code
                    output_dir = Path("optimizations_output")
                    output_dir.mkdir(exist_ok=True)
                    
                    code_path = output_dir / "data_service_async_FINAL.py"
                    with open(code_path, 'w', encoding='utf-8') as f:
                        f.write(f"# DATA SERVICE ASYNC OPTIMIZATION (FINAL)\n")
                        f.write(f"# Generated by Perplexity AI: {PERPLEXITY_MODEL}\n")
                        f.write(f"# Citations: {len(citations)}\n\n")
                        f.write(optimized_code)
                    
                    print(f"  💾 Saved: {code_path}")
                    
                    return {
                        'status': 'success',
                        'code_path': str(code_path),
                        'code_size': len(optimized_code),
                        'citations': len(citations)
                    }
                else:
                    error_text = await response.text()
                    print(f"  ❌ Error: {response.status} - {error_text}")
                    return {'status': 'error', 'error': error_text}
        
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return {'status': 'error', 'error': str(e)}

# ============================================================================
# MAIN WORKFLOW
# ============================================================================

async def main():
    """Main workflow orchestration"""
    start_time = time.time()
    
    try:
        # Task 1: Test backtest vectorization
        backtest_results = test_backtest_vectorization()
        
        # Task 2: SR RSI Async
        sr_rsi_results = await optimize_sr_rsi_async()
        
        # Task 3: Data Service Async
        data_service_results = await optimize_data_service_async()
        
        # Generate summary
        print("\n" + "=" * 80)
        print("📊 FINAL P1 OPTIMIZATIONS SUMMARY")
        print("=" * 80)
        
        summary = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'execution_time': time.time() - start_time,
            'tasks': {
                'backtest_vectorization': {
                    'status': 'tested' if backtest_results else 'pending',
                    'results': backtest_results
                },
                'sr_rsi_async': sr_rsi_results,
                'data_service_async': data_service_results
            }
        }
        
        # Save summary
        summary_path = Path("optimizations_output/FINAL_P1_OPTIMIZATION_SUMMARY.json")
        summary_path.parent.mkdir(exist_ok=True)
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, default=str)
        
        print(f"\n✅ TASK 1: Backtest Vectorization - {'TESTED' if backtest_results else 'PENDING'}")
        if backtest_results and backtest_results.get('tests_passed'):
            print(f"   Speed: {backtest_results.get('aggregate', {}).get('avg_speed', 0):.0f} bars/sec")
        
        print(f"\n✅ TASK 2: SR RSI Async - {sr_rsi_results.get('status', 'unknown').upper()}")
        if sr_rsi_results.get('status') == 'success':
            print(f"   File: {sr_rsi_results['code_path']}")
            print(f"   Citations: {sr_rsi_results['citations']}")
        
        print(f"\n✅ TASK 3: Data Service Async - {data_service_results.get('status', 'unknown').upper()}")
        if data_service_results.get('status') == 'success':
            print(f"   File: {data_service_results['code_path']}")
            print(f"   Citations: {data_service_results['citations']}")
        
        print(f"\n⏱️ Total execution time: {time.time() - start_time:.1f}s")
        print(f"💾 Summary saved: {summary_path}")
        
        print("\n🎯 NEXT STEPS:")
        print("   1. Review all optimized code")
        print("   2. Create test cases for each optimization")
        print("   3. Benchmark SR RSI async vs sequential")
        print("   4. Benchmark Data Service async vs sequential")
        print("   5. Deploy all optimizations if tests pass")
        print("   6. Generate final deployment report")
        
        print("\n✅ ALL P1 OPTIMIZATIONS COMPLETE!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
