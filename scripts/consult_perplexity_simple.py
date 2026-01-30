"""
Perplexity API consultation about VectorBT limitations (sonar-pro model)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import json

from backend.security.key_manager import get_key_manager

PROMPT = """
# VectorBT Backtesting Limitations Analysis

We discovered VectorBT has critical limitations for accurate backtesting:

1. **Intrabar SL/TP**: Checks stops only at bar CLOSE, not by High/Low. Example: bar O=100, H=105, L=96, C=104 with SL=97. VectorBT keeps position open (C>SL), but SL should trigger (L<SL).

2. **No MAE/MFE tracking**: Can't calculate Maximum Adverse/Favorable Excursion.

3. **Fixed Position Sizing**: Uses fixed order_value, not equity-based sizing.

4. **Quick Reversals**: Can open new position on same bar where previous closed. Creates 25% more trades.

5. **No Bar Magnifier**: Can't use 1-minute data for intrabar simulation.

6. **No Trailing Stop**: Not supported.

## Our Two-Stage Architecture
- Stage 1: VectorBT for fast screening (10,000+ combinations, ~85% accurate)
- Stage 2: Custom Fallback engine for validation (1 combo/sec, 100% accurate)

## Questions

1. Are there VectorBT workarounds for intrabar SL/TP?
2. What are the best alternatives to VectorBT for fast vectorized backtesting in 2025?
3. Is our Two-Stage approach optimal?
4. How to speed up a bar-by-bar simulator using Numba?
5. What do professional quant firms use for crypto backtesting?

Please provide technical recommendations with code examples.
"""

def main():
    print("=" * 70)
    print("PERPLEXITY CONSULTATION: VectorBT Limitations")
    print("=" * 70)
    
    km = get_key_manager()
    api_key = km.get_decrypted_key("PERPLEXITY_API_KEY")
    
    if not api_key:
        print("❌ Perplexity API key not found")
        return
    
    print("✅ API key loaded")
    
    # Use sonar-pro (simpler, faster)
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system", 
                "content": "You are an expert in quantitative finance, algorithmic trading, and high-performance backtesting. Provide technical, actionable advice."
            },
            {"role": "user", "content": PROMPT},
        ],
        "max_tokens": 4000,
        "temperature": 0.2,
    }
    
    print(f"\n📤 Sending request to Perplexity...")
    print(f"   Model: {payload['model']}")
    print(f"   Prompt length: {len(PROMPT)} chars")
    
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                "https://api.perplexity.ai/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
        
        print(f"\n📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            usage = data.get("usage", {})
            
            print(f"   Tokens: {usage.get('total_tokens', 'N/A')}")
            print(f"   Citations: {len(citations)}")
            
            # Save response
            with open("perplexity_vectorbt_consultation.md", "w", encoding="utf-8") as f:
                f.write("# Perplexity VectorBT Consultation\n\n")
                f.write(f"Model: {payload['model']}\n\n")
                f.write("## Response\n\n")
                f.write(content)
                
                if citations:
                    f.write("\n\n---\n\n## Citations\n\n")
                    for i, c in enumerate(citations, 1):
                        f.write(f"{i}. {c}\n")
            
            print("\n" + "=" * 70)
            print("PERPLEXITY RESPONSE")
            print("=" * 70)
            print(content)
            
            if citations:
                print(f"\n--- CITATIONS ({len(citations)}) ---")
                for i, c in enumerate(citations[:5], 1):
                    print(f"  {i}. {c[:80]}...")
            
            print("\n📄 Response saved to: perplexity_vectorbt_consultation.md")
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
