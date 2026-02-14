"""
FULL Perplexity API consultation about VectorBT limitations
Uses sonar-pro model for analysis with web search capabilities
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import httpx

from backend.security.key_manager import get_key_manager

FULL_PROMPT = """
# VectorBT vs Custom Fallback Engine: Technical Consultation

## Context

We are developing a cryptocurrency trading strategy backtesting system (Bybit Strategy Tester).
We use VectorBT for fast parameter optimization screening, but discovered significant limitations.
Our Fallback engine is a custom bar-by-bar simulator that provides accurate results.

## Current Two-Stage Architecture

```
STAGE 1: VectorBT (vectorized)
  - Tests 10,000+ parameter combinations
  - Speed: 5,000-80,000 combinations/sec
  - Accuracy: ~85%
  - Uses: vectorbt.Portfolio.from_signals()
  
STAGE 2: Fallback (sequential)  
  - Validates TOP-50 candidates from Stage 1
  - Speed: ~1 combination/sec
  - Accuracy: 100%
  - Full bar-by-bar simulator with intrabar processing
```

## VectorBT Problems We Discovered (Production Testing)

| # | Limitation | Detailed Explanation |
|---|------------|----------------------|
| 1 | **❌ Intrabar SL/TP** | VectorBT.Portfolio checks stops only at bar CLOSE price, not by High/Low within the bar. Example: bar Open=100, High=105, Low=96, Close=104 with StopLoss=97 (3%). VectorBT: position STAYS OPEN (Close=104 > SL=97). Fallback: position CLOSED (Low=96 < SL=97, stop triggered within bar). This leads to 10-15% metric divergence. |
| 2 | **❌ MAE/MFE** | Maximum Adverse Excursion and Maximum Favorable Excursion not tracked. These metrics are critical for entry quality assessment and stop-loss optimization. |
| 3 | **❌ Equity-Based Sizing** | VectorBT uses fixed `order_value` or `size`. Does not recalculate position size based on current equity. After +20% profit, position size should increase, but VectorBT uses initial size. |
| 4 | **❌ Quick Reversals** | VectorBT can open new position on the same bar where previous one closed. Result: VectorBT generates +25% more trades than Fallback. Test: VectorBT=10 trades, Fallback=8 trades for direction="both". |
| 5 | **❌ Bar Magnifier** | Our Fallback can use 1-minute candles to simulate movements within a 30-minute bar. VectorBT works only with main timeframe. |
| 6 | **❌ Trailing Stop** | VectorBT doesn't support trailing stop loss. |
| 7 | **❌ Sequential Processing** | VectorBT processes all signals in parallel (vectorized), but real trading is sequential. This affects equity curve calculation. |

## Empirical Test Results (Real Data)

### Trade Count Divergence:
| Direction | VectorBT trades | Fallback trades | Difference |
|-----------|-----------------|-----------------|------------|
| LONG only | 5               | 4               | +25%       |
| SHORT only| 6               | 6               | 0%         |
| BOTH      | 10              | 8               | +25%       |

### Metric Divergence:
| Metric       | VectorBT | Fallback | Difference |
|--------------|----------|----------|------------|
| Net Profit   | -$8,500  | -$9,200  | ~8%        |
| Sharpe Ratio | -1.2     | -1.4     | ~15%       |
| Win Rate     | 28%      | 25%      | ~12%       |
| Max Drawdown | 45%      | 52%      | ~15%       |

## Questions for Expert Consultation

### 1. Intrabar SL/TP in VectorBT
Are there ways to implement stop loss and take profit checks using HIGH/LOW within the bar?
- Maybe via `sl_trail`, `sl_stop` with custom functions?
- Or via `order_func_nb` with OHLC access?
- Is this a fundamental architectural limitation of VectorBT?

### 2. VectorBT Alternatives
What fast vectorized backtesting alternatives exist in 2025-2026?
- Are there Numba-based backtesters with intrabar support?
- GPU-accelerated options (CUDA/OpenCL)?
- Any new libraries that solve these problems?

### 3. Optimal Architecture
Is our Two-Stage approach (VectorBT screening → Fallback validation) optimal?
- Should we try to improve VectorBT or focus on accelerating Fallback?
- What speedup methods are recommended for bar-by-bar simulators?

### 4. Numba/Cython Optimization
For our Fallback engine (~1 combo/sec), what are the best practices for acceleration?
- Numba JIT vs Cython?
- How to preserve intrabar SL/TP accuracy while speeding up?
- Parallelization strategies for independent parameter combinations?

### 5. Industry Best Practices
What do professional quant trading firms use for backtesting?
- QuantConnect, Zipline, Backtrader - which is best for crypto?
- Are there commercial solutions worth considering?

## Expected Response Format

Please provide:
1. **Technical recommendations** for each problem
2. **Code examples** where possible (Python, NumPy, VectorBT API)
3. **Feasibility assessment** (possible/impossible/partial)
4. **Priority ranking**: which problems to solve first
5. **Architecture recommendations** for our Two-Stage approach
6. **Links to relevant documentation or research papers**
"""


def main():
    print("=" * 70)
    print("PERPLEXITY FULL CONSULTATION: VectorBT Limitations")
    print("=" * 70)

    # Get API key
    km = get_key_manager()
    api_key = km.get_decrypted_key("PERPLEXITY_API_KEY")

    if not api_key:
        print("❌ Perplexity API key not found")
        return

    print("✅ API key loaded")

    # Use sonar-pro for analysis with web search
    payload = {
        "model": "sonar-pro",  # Cost-effective model
        "messages": [
            {
                "role": "system",
                "content": "You are an expert in quantitative finance, algorithmic trading, backtesting engines, and high-performance computing. You have deep knowledge of VectorBT, Numba, NumPy, and vectorized computation. Provide technical, actionable advice with code examples.",
            },
            {"role": "user", "content": FULL_PROMPT},
        ],
        "max_tokens": 4000,
        "temperature": 0.2,
        "web_search_options": {
            "search_recency_filter": "month"  # Recent results
        },
    }

    print("\n📤 Sending FULL request to Perplexity...")
    print(f"   Model: {payload['model']} (reasoning + web search)")
    print(f"   Prompt length: {len(FULL_PROMPT)} chars")
    print(f"   Max tokens: {payload['max_tokens']}")
    print("\n⏳ This may take 1-3 minutes for deep analysis with web search...")

    # Make request with long timeout
    try:
        with httpx.Client(timeout=300.0) as client:  # 5 minute timeout
            response = client.post(
                "https://api.perplexity.ai/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )

        print(f"\n📥 Response received: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content", "")
            citations = data.get("citations", [])
            usage = data.get("usage", {})

            print(f"   Total tokens: {usage.get('total_tokens', 'N/A')}")
            print(f"   Citations: {len(citations)} sources")

            # Save full response
            with open("perplexity_vectorbt_consultation.md", "w", encoding="utf-8") as f:
                f.write("# Perplexity VectorBT Consultation\n\n")
                f.write(f"Model: {payload['model']}\n")
                f.write(f"Tokens: {usage.get('total_tokens', 'N/A')}\n\n")

                f.write("## Response\n\n")
                f.write(content)

                if citations:
                    f.write("\n\n---\n\n## Citations\n\n")
                    for i, citation in enumerate(citations, 1):
                        f.write(f"{i}. {citation}\n")

            print("\n" + "=" * 70)
            print("PERPLEXITY RESPONSE")
            print("=" * 70)

            print("\n--- ANSWER ---")
            print(content[:6000])
            if len(content) > 6000:
                print(f"\n... ({len(content)} chars total, see file)")

            if citations:
                print(f"\n--- CITATIONS ({len(citations)} sources) ---")
                for i, citation in enumerate(citations[:5], 1):
                    print(f"  {i}. {citation[:80]}...")
                if len(citations) > 5:
                    print(f"  ... and {len(citations) - 5} more")

            print("\n📄 Full response saved to: perplexity_vectorbt_consultation.md")

        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)

    except httpx.TimeoutException:
        print("❌ Request timed out (5 minutes)")
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
