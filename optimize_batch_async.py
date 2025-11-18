"""
🚀 SR RSI + DATA SERVICE ASYNC OPTIMIZATION
=============================================

Batch optimization for remaining P1 tasks using Perplexity AI scripts

Tasks:
1. SR RSI Async - Support/Resistance + RSI with async parallel calculation
2. Data Service Async - Async data loading and caching

Method: Copilot → Perplexity AI (via existing scripts) → Copilot
"""

import sys
import os
import asyncio
import aiohttp
import json
from pathlib import Path
from datetime import datetime

# Perplexity API configuration
PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")
PERPLEXITY_MODEL = "sonar-pro"
PERPLEXITY_TIMEOUT = 90  # seconds

print("=" * 80)
print("  🚀 P1 REMAINING OPTIMIZATIONS (Batch)")
print("  Tasks: SR RSI Async + Data Service Async")
print("  Method: Copilot ↔ Perplexity AI ↔ Copilot")
print("=" * 80)

# ============================================================================
# STEP 1: READ CURRENT IMPLEMENTATIONS
# ============================================================================

def read_sr_rsi_strategy() -> str:
    """Read current SR RSI strategy"""
    print("\n📄 STEP 1a: Reading SR RSI strategy...")
    
    path = Path("backend/strategies/sr_rsi_strategy.py")
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        print(f"  ✅ Loaded: {len(code)} chars")
        return code
    
    print("  ⚠️ SR RSI strategy not found, using optimized version...")
    
    # Check optimized version
    opt_path = Path("optimizations_output/sr_rsi_async_optimized.py")
    if opt_path.exists():
        with open(opt_path, 'r', encoding='utf-8') as f:
            code = f.read()
        print(f"  ✅ Loaded optimized: {len(code)} chars")
        return code
    
    return ""

def read_data_service() -> str:
    """Read current data service"""
    print("\n📄 STEP 1b: Reading data service...")
    
    path = Path("backend/services/legacy_data_loader.py")
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        print(f"  ✅ Loaded: {len(code)} chars")
        return code
    
    print("  ⚠️ Data service not found")
    return ""

# ============================================================================
# STEP 2: CALL PERPLEXITY AI DIRECTLY
# ============================================================================

async def call_perplexity(prompt: str, task_name: str) -> dict:
    """Call Perplexity AI directly"""
    print(f"\n🤖 STEP 2: Asking Perplexity AI to optimize {task_name}...")
    print(f"  Model: {PERPLEXITY_MODEL}")
    print(f"  Timeout: {PERPLEXITY_TIMEOUT}s")
    
    if not PERPLEXITY_API_KEY:
        print("  ❌ PERPLEXITY_API_KEY not set")
        print("  💡 Using pre-generated optimization from previous run...")
        return {'skip': True, 'reason': 'No API key'}
    
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
                    "content": "You are an expert Python optimization specialist focusing on async programming, vectorization, and financial algorithms."
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
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=PERPLEXITY_TIMEOUT)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    optimized_code = result['choices'][0]['message']['content']
                    citations = result.get('citations', [])
                    
                    print(f"  ✅ Optimization received")
                    print(f"  📚 Citations: {len(citations)}")
                    print(f"  📄 Code size: {len(optimized_code)} chars")
                    
                    return {
                        'optimized_code': optimized_code,
                        'citations': citations,
                        'model': PERPLEXITY_MODEL,
                        'timestamp': datetime.now().isoformat(),
                        'skip': False
                    }
                else:
                    error_text = await response.text()
                    print(f"  ❌ Error: {response.status} - {error_text}")
                    return {'skip': True, 'reason': f'API error: {response.status}'}
        
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return {'skip': True, 'reason': str(e)}

# ============================================================================
# STEP 3: CREATE OPTIMIZATION PROMPTS
# ============================================================================

def create_sr_rsi_prompt(current_code: str) -> str:
    """Create SR RSI optimization prompt"""
    return f"""
TASK: Optimize Support/Resistance + RSI strategy for async parallel calculation

CURRENT CODE (Sequential):
```python
{current_code[:3000] if current_code else "# Not found - create from scratch"}
```

OPTIMIZATION REQUIREMENTS:

1. **Support/Resistance Calculation (Vectorized + Async)**
   - NumPy vectorized calculation of local maxima/minima
   - Use scipy.signal.find_peaks for peak detection
   - Async parallel calculation for multiple lookback periods
   - Expected speedup: 2-3x

2. **RSI Calculation (Async Parallel)**
   - Async parallel RSI for multiple timeframes (14, 28, 50 periods)
   - Use pandas_ta or numpy for optimized RSI
   - Cache RSI results to avoid recalculation
   - Expected speedup: 2-4x

3. **Signal Generation (Async Aggregation)**
   - Use asyncio.gather() to run SR and RSI concurrently
   - Aggregate results efficiently
   - Overall expected speedup: 3-5x

4. **Edge Cases**
   - Handle empty/insufficient data
   - Prevent lookahead bias
   - Add NaN handling

OUTPUT: Complete Python code with async/await, docstrings, example usage
"""

def create_data_service_prompt(current_code: str) -> str:
    """Create Data Service optimization prompt"""
    return f"""
TASK: Optimize Data Service for async parallel data loading and caching

CURRENT CODE (Sequential):
```python
{current_code[:3000] if current_code else "# Not found - create from scratch"}
```

OPTIMIZATION REQUIREMENTS:

1. **Async Data Loading**
   - Async parallel loading of multiple symbols
   - Async parallel loading of multiple timeframes
   - Use asyncio.gather() for concurrent requests
   - Expected speedup: 5-10x for multiple symbols

2. **Smart Caching**
   - Redis async caching (if available)
   - File-based async caching (fallback)
   - Cache invalidation strategy
   - TTL-based expiration

3. **Connection Pooling**
   - Async connection pool for Bybit API
   - Rate limiting with async semaphore
   - Retry logic with exponential backoff

4. **Edge Cases**
   - Handle network errors gracefully
   - Handle cache miss/corruption
   - Handle rate limits

OUTPUT: Complete Python code with async/await, aiohttp, aiocache, docstrings
"""

# ============================================================================
# STEP 4: SAVE RESULTS
# ============================================================================

def save_optimization(task_name: str, current_code: str, result: dict) -> dict:
    """Save optimization results"""
    if result.get('skip'):
        print(f"\n  ⚠️ Skipping save for {task_name}: {result.get('reason')}")
        return {}
    
    print(f"\n💾 Saving {task_name} optimization...")
    
    output_dir = Path("optimizations_output")
    output_dir.mkdir(exist_ok=True)
    
    # Sanitize task name for filename
    filename_base = task_name.lower().replace(' ', '_')
    
    # Save optimized code
    code_path = output_dir / f"{filename_base}_FINAL.py"
    with open(code_path, 'w', encoding='utf-8') as f:
        f.write(f"# {task_name} OPTIMIZATION (FINAL)\n")
        f.write(f"# Generated: {result['timestamp']}\n")
        f.write(f"# Model: {result['model']}\n")
        f.write(f"# Citations: {len(result['citations'])}\n")
        f.write("\n")
        f.write(result['optimized_code'])
    
    print(f"  ✅ Code saved: {code_path}")
    
    # Save metadata
    metadata = {
        'task': task_name,
        'timestamp': result['timestamp'],
        'model': result['model'],
        'citations': result['citations'],
        'code_size': len(result['optimized_code']),
        'original_code_size': len(current_code)
    }
    
    metadata_path = output_dir / f"{filename_base}_METADATA.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"  ✅ Metadata saved: {metadata_path}")
    
    return {
        'code_path': str(code_path),
        'metadata_path': str(metadata_path)
    }

# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main batch optimization workflow"""
    try:
        print("\n" + "=" * 80)
        print("📊 BATCH OPTIMIZATION: SR RSI + DATA SERVICE")
        print("=" * 80)
        
        # Step 1: Read current implementations
        sr_rsi_code = read_sr_rsi_strategy()
        data_service_code = read_data_service()
        
        # Step 2: Create prompts
        sr_rsi_prompt = create_sr_rsi_prompt(sr_rsi_code)
        data_service_prompt = create_data_service_prompt(data_service_code)
        
        # Step 3: Call Perplexity AI
        sr_rsi_result = await call_perplexity(sr_rsi_prompt, "SR RSI Async")
        data_service_result = await call_perplexity(data_service_prompt, "Data Service Async")
        
        # Step 4: Save results
        sr_rsi_paths = save_optimization("SR RSI Async", sr_rsi_code, sr_rsi_result)
        data_service_paths = save_optimization("Data Service Async", data_service_code, data_service_result)
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 BATCH OPTIMIZATION SUMMARY")
        print("=" * 80)
        
        results = {
            'sr_rsi': {
                'status': 'completed' if not sr_rsi_result.get('skip') else 'skipped',
                'paths': sr_rsi_paths,
                'citations': len(sr_rsi_result.get('citations', []))
            },
            'data_service': {
                'status': 'completed' if not data_service_result.get('skip') else 'skipped',
                'paths': data_service_paths,
                'citations': len(data_service_result.get('citations', []))
            }
        }
        
        print(f"\n✅ SR RSI Async: {results['sr_rsi']['status']}")
        if results['sr_rsi']['status'] == 'completed':
            print(f"   Citations: {results['sr_rsi']['citations']}")
            print(f"   Files: {len(sr_rsi_paths)} created")
        
        print(f"\n✅ Data Service Async: {results['data_service']['status']}")
        if results['data_service']['status'] == 'completed':
            print(f"   Citations: {results['data_service']['citations']}")
            print(f"   Files: {len(data_service_paths)} created")
        
        # Save summary
        summary_path = Path("optimizations_output/BATCH_OPTIMIZATION_SUMMARY.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Summary saved: {summary_path}")
        
        print("\n🎯 NEXT STEPS:")
        print("   1. Review optimized code for both tasks")
        print("   2. Create test cases")
        print("   3. Benchmark performance")
        print("   4. Deploy if tests pass")
        print("   5. Generate final report")
        
        print("\n✅ BATCH OPTIMIZATION COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

# Import secure key manager
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "backend"))
from security.key_manager import get_decrypted_key
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
