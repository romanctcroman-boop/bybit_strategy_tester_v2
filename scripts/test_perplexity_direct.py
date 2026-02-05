"""
Direct Perplexity test with new API key
"""
import os

import httpx
from dotenv import load_dotenv

# Force reload .env
load_dotenv(override=True)

PROMPT = """
# VectorBT Backtesting Limitations

We use VectorBT for fast optimization but found critical issues:

1. **No Intrabar SL/TP**: Only checks stops at bar CLOSE, not High/Low
2. **No MAE/MFE tracking** 
3. **Fixed Position Sizing**: Uses fixed order_value, not equity-based
4. **Quick Reversals**: Opens positions on same bar as close (+25% extra trades)
5. **No Bar Magnifier**: Can't use 1-minute data for intrabar simulation

## Our Two-Stage Architecture
- Stage 1: VectorBT for fast screening (~85% accurate)
- Stage 2: Custom Fallback engine for validation (100% accurate)

## Questions
1. Are there VectorBT workarounds for intrabar SL/TP?
2. Best alternatives to VectorBT in 2025?
3. How to speed up bar-by-bar simulators with Numba?
4. Is our Two-Stage approach optimal?

Provide technical recommendations with code examples.
"""

def main():
    print("=" * 70)
    print("PERPLEXITY DIRECT TEST")
    print("=" * 70)

    # Get key from environment
    api_key = os.getenv("PERPLEXITY_API_KEY")
    print(f"API Key: {api_key[:25]}...")

    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "You are an expert in quantitative finance and backtesting."},
            {"role": "user", "content": PROMPT},
        ],
        "max_tokens": 2000,
    }

    print("\n📤 Sending request...")

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

        print(f"📥 Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])

            # Save
            with open("perplexity_vectorbt_consultation.md", "w", encoding="utf-8") as f:
                f.write("# Perplexity VectorBT Consultation\n\n")
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
                for c in citations[:5]:
                    print(f"  • {c[:70]}...")

            print("\n📄 Saved to: perplexity_vectorbt_consultation.md")
        else:
            print(f"❌ Error: {response.text[:500]}")

    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
