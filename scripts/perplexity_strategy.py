"""
Perplexity Sonar Pro: Стратегический анализ (отдельный запрос)
"""

import requests

PERPLEXITY_API_KEY = "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"

def send_to_perplexity(query: str) -> dict:
    """Отправляет запрос в Perplexity API"""
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar",
        "messages": [{"role": "user", "content": query}],
        "max_tokens": 2000,
        "temperature": 0.3
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Perplexity API call failed: {e}")
        return {"error": str(e)}

def main():
    print("="*80)
    print("PERPLEXITY SONAR PRO: СТРАТЕГИЧЕСКИЙ АНАЛИЗ")
    print("="*80)
    print()
    
    # Простой промпт на основе анализа DeepSeek
    prompt = """
You are a strategic consultant analyzing the Bybit Strategy Tester project.

PROJECT STATUS:
- Multi-agent system for automated trading strategy generation and testing
- Current TZ compliance: 58%
- Production readiness: 42%
- Security score: 35% (CRITICAL)

KEY MODULES IMPLEMENTED:
✅ MCP Server (75% compliance)
✅ Reasoning agents (Perplexity AI) - 68% compliance
✅ Code generation (DeepSeek) - 55% compliance

KEY MODULES MISSING:
❌ ML/AutoML (0% - CRITICAL)
❌ Sandbox Execution (0% - CRITICAL SECURITY RISK)
❌ Trader Psychology Agent (0%)
❌ Knowledge Base (reasoning chains storage)

PROVIDE STRATEGIC ANALYSIS:

1. BUSINESS VALUE ASSESSMENT
- Which modules provide MAXIMUM value to users?
- What can be deferred without losing core functionality?
- ROI estimation for each module

2. TIME-TO-MARKET ANALYSIS
- Minimum viable product (MVP) requirements
- Quick wins (1-2 weeks)
- Full production readiness roadmap (3-6 months)

3. RISK ASSESSMENT
- Security risks (sandbox, code execution)
- Technical risks (ML integration, scalability)
- Business risks (competition, API dependencies)

4. PRIORITIZATION (MoSCoW Method)
MUST HAVE: Critical for MVP
SHOULD HAVE: Important but can be deferred
COULD HAVE: Nice to have
WON'T HAVE: Out of scope for Phase 1

5. COMPETITIVE POSITIONING
How does this compare to:
- QuantConnect
- TradingView Pine Script
- MetaTrader Expert Advisors
- Freqtrade

6. FINAL VERDICT
Overall strategic score: X/100
Market fit assessment
Go/No-Go recommendation

FORMAT: Executive summary + detailed analysis with tables and concrete recommendations.
"""
    
    print("Sending request to Perplexity Sonar Pro...")
    result = send_to_perplexity(prompt)
    
    if "error" not in result:
        analysis = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        citations = result.get("citations", [])
        
        print(f"   ✅ SUCCESS: Perplexity analysis received ({len(analysis)} chars)")
        print(f"   📚 Citations: {len(citations)} sources")
        
        # Сохраняем отчёт
        report_path = r"d:\bybit_strategy_tester_v2\FULL_TZ_PERPLEXITY_STRATEGY.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# Perplexity Sonar Pro: Стратегический анализ\n\n")
            f.write(f"**Дата**: 2025-11-01\n\n")
            f.write(f"**На основе**: DeepSeek технического аудита (TZ compliance: 58%)\n\n")
            f.write(f"**Citations**: {len(citations)} sources\n\n")
            f.write(f"---\n\n")
            f.write(analysis)
            
            if citations:
                f.write(f"\n\n---\n\n## 📚 Sources\n\n")
                for i, citation in enumerate(citations, 1):
                    f.write(f"{i}. {citation}\n")
        
        print(f"   📄 Report saved: {report_path}")
        
        # Preview
        print("\n   Preview:")
        print("   " + "\n   ".join(analysis[:600].split("\n")))
    else:
        print(f"   ❌ FAILED: {result['error']}")
    
    print()
    print("="*80)
    print("✅ СТРАТЕГИЧЕСКИЙ АНАЛИЗ ЗАВЕРШЁН")
    print("="*80)

if __name__ == "__main__":
    main()
