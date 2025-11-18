"""
🚀 SR RSI ASYNC OPTIMIZATION
==============================

Optimize Support/Resistance + RSI strategy with async parallel calculation.

Current bottleneck: Sequential SR level calculation + RSI on multiple timeframes
Target: Async parallel calculation with asyncio

Expected speedup: 3-5x for multi-timeframe strategies

Method: Copilot ↔ Perplexity AI ↔ Copilot (via MCP Server)
"""

import sys
import os
import asyncio
import aiohttp
import json
from pathlib import Path
from datetime import datetime

# MCP Server configuration
MCP_SERVER_URL = "http://localhost:3000"  # Adjust if different
PERPLEXITY_MODEL = "sonar-pro"
PERPLEXITY_TIMEOUT = 90  # seconds

print("=" * 80)
print("  🚀 SR RSI ASYNC OPTIMIZATION")
print("  Method: Copilot ↔ Perplexity AI ↔ Copilot (MCP Server)")
print("=" * 80)

# ============================================================================
# STEP 1: READ CURRENT SR RSI CODE
# ============================================================================

def read_sr_rsi_code() -> str:
    """Read current SR RSI strategy implementation"""
    print("\n📄 STEP 1: Reading current SR RSI strategy...")
    
    # Check multiple possible locations
    possible_paths = [
        Path("backend/strategies/sr_rsi_strategy.py"),
        Path("backend/strategies/support_resistance_rsi.py"),
        Path("optimizations_output/sr_rsi_async_optimized.py"),
    ]
    
    for path in possible_paths:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
            print(f"  ✅ Loaded: {path} ({len(code)} chars)")
            return code
    
    # If not found, create template
    print("  ⚠️ SR RSI strategy not found, creating template...")
    
    template_code = '''
# SR RSI Strategy Template (Sequential - needs optimization)

class SRRSIStrategy:
    """Support/Resistance + RSI Strategy"""
    
    def __init__(self, rsi_period=14, sr_lookback=100):
        self.rsi_period = rsi_period
        self.sr_lookback = sr_lookback
    
    def calculate_sr_levels(self, data):
        """Calculate support/resistance levels (SLOW - sequential)"""
        # Current: Sequential loop through history
        # Target: Vectorized or parallel calculation
        pass
    
    def calculate_rsi(self, data):
        """Calculate RSI (SLOW for multiple timeframes)"""
        # Current: Sequential RSI calculation
        # Target: Async parallel for multiple timeframes
        pass
    
    def generate_signal(self, data):
        """Generate trading signal"""
        # Wait for SR levels (blocking)
        sr_levels = self.calculate_sr_levels(data)
        
        # Wait for RSI (blocking)
        rsi = self.calculate_rsi(data)
        
        # Generate signal
        # Target: Async parallel calculation
        pass
'''
    
    return template_code

# ============================================================================
# STEP 2: CALL PERPLEXITY AI VIA MCP SERVER
# ============================================================================

async def perplexity_optimize_sr_rsi(current_code: str) -> dict:
    """
    Ask Perplexity AI to optimize SR RSI with async parallel calculation.
    
    Uses MCP Server to call Perplexity AI API.
    """
    print("\n🤖 STEP 2: Asking Perplexity AI to optimize SR RSI (async)...")
    print(f"  Model: {PERPLEXITY_MODEL}")
    print(f"  Timeout: {PERPLEXITY_TIMEOUT}s")
    
    prompt = f"""
TASK: Optimize Support/Resistance + RSI strategy for async parallel calculation

CURRENT CODE (Sequential):
```python
{current_code[:3000]}  # First 3000 chars for context
```

OPTIMIZATION REQUIREMENTS:

1. **Support/Resistance Calculation (Vectorized + Async)**
   - Current: Sequential loop through price history
   - Target: NumPy vectorized calculation of local maxima/minima
   - Use scipy.signal.find_peaks for efficient peak detection
   - Async parallel calculation for multiple lookback periods

2. **RSI Calculation (Async Parallel)**
   - Current: Sequential RSI calculation
   - Target: Async parallel RSI for multiple timeframes (e.g., 14, 28, 50)
   - Use pandas_ta or ta-lib for optimized RSI
   - Cache RSI results to avoid recalculation

3. **Signal Generation (Async Aggregation)**
   - Current: Blocking wait for SR + RSI
   - Target: Async gather all calculations in parallel
   - Use asyncio.gather() to run SR and RSI concurrently
   - Aggregate results efficiently

4. **Edge Cases**
   - Handle empty data gracefully
   - Handle insufficient data for calculation
   - Prevent lookahead bias (use only historical data)
   - Add NaN handling for incomplete indicators

EXPECTED SPEEDUP: 3-5x for multi-timeframe strategies

OUTPUT FORMAT:
- Complete Python code with async/await
- Use asyncio, numpy, pandas
- Include docstrings explaining optimization
- Add example usage
- Mention any dependencies (scipy, pandas_ta, etc.)

CONSTRAINTS:
- Must maintain same API interface
- Must produce same signals as original (correctness)
- Must be production-ready (error handling, logging)

Please provide COMPLETE, production-ready code with all optimizations applied.
"""
    
    try:
        async with aiohttp.ClientSession() as session:
            # Call MCP Server which calls Perplexity AI
            payload = {
                "model": PERPLEXITY_MODEL,
                "prompt": prompt,
                "timeout": PERPLEXITY_TIMEOUT,
                "return_citations": True
            }
            
            print("  📡 Sending request to MCP Server...")
            
            async with session.post(
                f"{MCP_SERVER_URL}/api/perplexity/query",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=PERPLEXITY_TIMEOUT + 10)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    optimized_code = result.get('response', '')
                    citations = result.get('citations', [])
                    
                    print(f"  ✅ Optimization received")
                    print(f"  📚 Citations: {len(citations)}")
                    print(f"  📄 Code size: {len(optimized_code)} chars")
                    
                    return {
                        'optimized_code': optimized_code,
                        'citations': citations,
                        'model': PERPLEXITY_MODEL,
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    error_text = await response.text()
                    raise Exception(f"MCP Server error: {response.status} - {error_text}")
    
    except Exception as e:
        print(f"  ❌ Error calling Perplexity AI: {e}")
        print("\n  ⚠️ Falling back to direct Perplexity API (if PERPLEXITY_API_KEY set)...")
        
        # Fallback: Direct Perplexity API call
        api_key = os.getenv('PERPLEXITY_API_KEY')
        if not api_key:
            raise Exception("No PERPLEXITY_API_KEY found. Please set it or start MCP Server.")
        
        return await call_perplexity_direct(prompt, api_key)

async def call_perplexity_direct(prompt: str, api_key: str) -> dict:
    """Direct call to Perplexity API (fallback)"""
    print("  📡 Calling Perplexity API directly...")
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {api_key}",
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
                
                print(f"  ✅ Direct call successful")
                print(f"  📚 Citations: {len(citations)}")
                
                return {
                    'optimized_code': optimized_code,
                    'citations': citations,
                    'model': PERPLEXITY_MODEL,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                error_text = await response.text()
                raise Exception(f"Perplexity API error: {response.status} - {error_text}")

# ============================================================================
# STEP 3: VERIFY OPTIMIZATION
# ============================================================================

async def perplexity_verify_sr_rsi(optimized_code: str) -> dict:
    """Ask Perplexity AI to verify the optimization"""
    print("\n🔍 STEP 3: Asking Perplexity AI to verify optimization...")
    
    prompt = f"""
TASK: Verify the SR RSI async optimization for correctness and performance

OPTIMIZED CODE:
```python
{optimized_code[:5000]}  # First 5000 chars
```

VERIFICATION CHECKLIST:

1. **Correctness (0-10 score)**
   - Does async version produce same signals as sequential?
   - Are there any lookahead bias risks?
   - Is NaN handling correct?
   - Are edge cases handled?

2. **Performance (Expected Speedup)**
   - Is async properly used with asyncio.gather()?
   - Are vectorized operations used where possible?
   - Is caching implemented to avoid recalculation?
   - Expected speedup: 3-5x?

3. **Code Quality (0-10 score)**
   - Is error handling comprehensive?
   - Are docstrings clear?
   - Is the code production-ready?
   - Are dependencies clearly stated?

4. **Test Cases**
   - Suggest 2-3 test cases to validate correctness
   - Include expected input/output for each test
   - Cover edge cases (empty data, insufficient data, NaN)

OUTPUT:
- Correctness score (0-10)
- Performance score (0-10)
- Code quality score (0-10)
- Issues found (if any)
- Test cases (2-3 cases)
- Suggested improvements
"""
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": PERPLEXITY_MODEL,
                "prompt": prompt,
                "timeout": 60,
                "return_citations": True
            }
            
            async with session.post(
                f"{MCP_SERVER_URL}/api/perplexity/query",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=70)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    verification = result.get('response', '')
                    citations = result.get('citations', [])
                    
                    print(f"  ✅ Verification completed")
                    print(f"  📚 Citations: {len(citations)}")
                    
                    return {
                        'verification': verification,
                        'citations': citations,
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    # Fallback: Skip verification
                    print(f"  ⚠️ Verification skipped (MCP Server error: {response.status})")
                    return {
                        'verification': 'Verification skipped',
                        'citations': [],
                        'timestamp': datetime.now().isoformat()
                    }
    
    except Exception as e:
        print(f"  ⚠️ Verification skipped: {e}")
        return {
            'verification': f'Verification skipped: {e}',
            'citations': [],
            'timestamp': datetime.now().isoformat()
        }

# ============================================================================
# STEP 4: SAVE RESULTS
# ============================================================================

def save_optimization(current_code: str, optimization: dict, verification: dict):
    """Save optimization results"""
    print("\n💾 STEP 4: Saving optimization results...")
    
    output_dir = Path("optimizations_output")
    output_dir.mkdir(exist_ok=True)
    
    # Save optimized code
    code_path = output_dir / "sr_rsi_async_OPTIMIZED.py"
    with open(code_path, 'w', encoding='utf-8') as f:
        f.write("# SR RSI ASYNC OPTIMIZATION\n")
        f.write(f"# Generated: {optimization['timestamp']}\n")
        f.write(f"# Model: {optimization['model']}\n")
        f.write(f"# Citations: {len(optimization['citations'])}\n")
        f.write("\n")
        f.write(optimization['optimized_code'])
    
    print(f"  ✅ Optimized code saved: {code_path}")
    
    # Save metadata
    metadata = {
        'optimization': {
            'timestamp': optimization['timestamp'],
            'model': optimization['model'],
            'citations': optimization['citations'],
            'code_size': len(optimization['optimized_code'])
        },
        'verification': verification,
        'original_code_size': len(current_code)
    }
    
    metadata_path = output_dir / "SR_RSI_ASYNC_OPTIMIZATION.json"
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
    """Main optimization workflow"""
    try:
        # Step 1: Read current SR RSI code
        current_code = read_sr_rsi_code()
        
        # Step 2: Optimize with Perplexity AI
        optimization = await perplexity_optimize_sr_rsi(current_code)
        
        # Step 3: Verify optimization
        verification = await perplexity_verify_sr_rsi(optimization['optimized_code'])
        
        # Step 4: Save results
        paths = save_optimization(current_code, optimization, verification)
        
        print("\n" + "=" * 80)
        print("📊 SR RSI ASYNC OPTIMIZATION SUMMARY")
        print("=" * 80)
        print(f"\n✅ Original code: {len(current_code)} chars")
        print(f"✅ Optimized code: {len(optimization['optimized_code'])} chars")
        print(f"✅ Optimization citations: {len(optimization['citations'])}")
        print(f"✅ Verification citations: {len(verification['citations'])}")
        print(f"\n📄 Files created:")
        print(f"   - {paths['code_path']}")
        print(f"   - {paths['metadata_path']}")
        
        print("\n🎯 NEXT STEPS:")
        print("   1. Review optimized code")
        print("   2. Create test cases from verification")
        print("   3. Benchmark async vs sequential")
        print("   4. Deploy if tests pass")
        print("   5. Continue with Data Service Async optimization")
        
        print("\n✅ SR RSI ASYNC OPTIMIZATION COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
