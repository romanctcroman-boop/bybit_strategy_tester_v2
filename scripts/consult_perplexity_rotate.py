"""
Perplexity API consultation with key rotation
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from backend.security.key_manager import get_key_manager

PROMPT = """
# VectorBT Backtesting Limitations

We use VectorBT for fast optimization but found critical issues:

1. **No Intrabar SL/TP**: Only checks stops at bar CLOSE, not High/Low
2. **No MAE/MFE tracking** 
3. **Fixed Position Sizing**: Uses fixed order_value, not equity-based
4. **Quick Reversals**: Opens positions on same bar as close (+25% extra trades)
5. **No Bar Magnifier**: Can't use 1-minute data for intrabar simulation

## Our Architecture
- Stage 1: VectorBT for fast screening (~85% accurate)
- Stage 2: Custom Fallback engine for validation (100% accurate)

## Questions

1. Are there VectorBT workarounds for intrabar SL/TP?
2. Best alternatives to VectorBT in 2025-2026?
3. How to speed up bar-by-bar simulators with Numba?
4. Is our Two-Stage approach optimal?

Provide technical recommendations with code examples where possible.
"""

def main():
    print("=" * 70)
    print("PERPLEXITY CONSULTATION (with key rotation)")
    print("=" * 70)

    km = get_key_manager()

    # Try multiple keys
    key_names = ['PERPLEXITY_API_KEY', 'PERPLEXITY_API_KEY_2', 'PERPLEXITY_API_KEY_3']

    for key_name in key_names:
        try:
            api_key = km.get_decrypted_key(key_name)
            if not api_key:
                continue

            print(f"\n🔑 Trying {key_name}...")

            payload = {
                "model": "sonar",  # Simplest model
                "messages": [
                    {"role": "system", "content": "You are an expert in quantitative finance and backtesting."},
                    {"role": "user", "content": PROMPT},
                ],
                "max_tokens": 2000,
            }

            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    "https://api.perplexity.ai/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                )

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                citations = data.get("citations", [])

                # Save response
                with open("perplexity_vectorbt_consultation.md", "w", encoding="utf-8") as f:
                    f.write("# Perplexity VectorBT Consultation\n\n")
                    f.write(f"Key: {key_name}\n\n")
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
                        print(f"  {i}. {c[:60]}...")

                print("\n📄 Saved to: perplexity_vectorbt_consultation.md")
                return  # Success!

            elif response.status_code == 401:
                print("   ❌ Unauthorized (key may be expired)")
                continue
            else:
                print(f"   ❌ Error: {response.text[:200]}")
                continue

        except Exception as e:
            print(f"   ❌ Exception: {e}")
            continue

    print("\n❌ All Perplexity keys failed!")

if __name__ == "__main__":
    main()
