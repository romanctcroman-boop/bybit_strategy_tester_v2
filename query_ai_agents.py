"""
Query DeepSeek and Perplexity agents for project recommendations
"""
import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project context for AI agents
PROJECT_CONTEXT = """
# Bybit Strategy Tester v2 - Project Context

## Current State
- **Quick Win Campaign**: COMPLETED ✅
  - Test coverage improvements: 6 modules improved
  - 2 modules at 100%, 1 at 99%, 3 at practical max
  - 47 tests created, +4.18% average coverage gain
  
- **Tech Stack**:
  - Backend: FastAPI, SQLAlchemy, PostgreSQL
  - Frontend: React + Vite, TypeScript
  - AI: Multi-agent (Copilot, DeepSeek, Perplexity)
  - Testing: Pytest (95%+), Playwright E2E (16/16 passing)
  - Infrastructure: Docker-ready, CI/CD pipeline setup
  
- **Features Working**:
  - Backtest engine with multi-timeframe support
  - Strategy management (CRUD)
  - Parameter optimization
  - Real-time data from Bybit API v5
  - 51 MCP tools for AI integration
  - E2E testing suite

## 5 Proposed Development Plans

### Plan 1: Testing Excellence 🧪 (10-13 hours)
**Goal**: Production-ready test coverage
- Fix 13 failing tests in test_backtests.py
- Add 30+ E2E tests for main workflows
- Create 20+ integration tests
- CI/CD with automated coverage checks
**Priority**: ⭐⭐⭐⭐⭐ (critical for production)

### Plan 2: Multi-Agent AI Enhancement 🤖 (12-18 hours)
**Goal**: Expand AI capabilities for strategy development
- 15+ new MCP tools (strategy analyzer, risk calculator, etc.)
- 3-agent collaboration framework
- AI-powered strategy generation
- Automated code review pipeline
**Priority**: ⭐⭐⭐⭐ (unique feature)

### Plan 3: Live Trading Integration 🚀 (13-19 hours)
**Goal**: Production-ready live trading
- Bybit order execution (market, limit, stop)
- Position management & tracking
- Real-time WebSocket feeds
- Risk management system
- Paper trading mode
- Live trading dashboard
**Priority**: ⭐⭐⭐⭐⭐ (maximum business value)

### Plan 4: Advanced Analytics & ML 📊 (15-21 hours)
**Goal**: ML-driven features
- Market regime detection (HMM, clustering)
- Bayesian optimization (Optuna)
- LSTM price prediction
- Ensemble methods & AutoML
**Priority**: ⭐⭐⭐ (advanced feature)

### Plan 5: Infrastructure & Scalability 🏗️ (12-18 hours)
**Goal**: Production deployment infrastructure
- Celery + Redis distributed processing
- Docker Compose multi-container setup
- GitHub Actions CI/CD pipeline
- Prometheus + Grafana monitoring
**Priority**: ⭐⭐⭐⭐ (production necessity)

## Questions for AI Agents

1. **Priority Ranking**: Which plan provides maximum ROI considering:
   - Business value (monetization potential)
   - Technical foundation (enables other features)
   - Time investment vs. impact
   - Risk mitigation

2. **Hybrid Approach**: Best combination of plans for 2-3 weeks?

3. **Hidden Risks**: What critical issues are we missing?

4. **Quick Wins**: Any 2-4 hour high-impact additions?

5. **Architecture Review**: Are we on the right track technically?
"""

def query_deepseek(context: str) -> dict:
    """Query DeepSeek API for recommendations"""
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        return {"error": "DEEPSEEK_API_KEY not found in environment"}
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are a senior software architect and trading systems expert. Provide detailed technical analysis with specific recommendations, risks, and implementation strategies."
            },
            {
                "role": "user",
                "content": f"{context}\n\nProvide:\n1. Priority ranking (1-5) with detailed justification\n2. Recommended hybrid approach for 2-3 weeks\n3. Critical risks we're missing\n4. Quick wins (2-4 hours) we should add\n5. Technical architecture assessment\n\nBe specific and actionable."
            }
        ],
        "temperature": 0.7,
        "max_tokens": 4000
    }
    
    try:
        print("🤖 Querying DeepSeek API...")
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        content = result['choices'][0]['message']['content']
        return {
            "agent": "DeepSeek",
            "status": "success",
            "response": content,
            "model": result.get('model'),
            "usage": result.get('usage')
        }
    except Exception as e:
        return {
            "agent": "DeepSeek",
            "status": "error",
            "error": str(e)
        }

def query_perplexity(context: str) -> dict:
    """Query Perplexity Sonar Pro API for recommendations"""
    api_key = os.getenv('PERPLEXITY_API_KEY')
    if not api_key:
        return {"error": "PERPLEXITY_API_KEY not found in environment"}
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": "You are a fintech industry analyst and software development consultant. Provide research-backed recommendations with industry best practices and market insights."
            },
            {
                "role": "user",
                "content": f"{context}\n\nProvide research-backed analysis:\n1. Industry best practices for trading platforms\n2. Priority ranking based on market trends\n3. Monetization potential for each plan\n4. Competitive analysis (what similar platforms do)\n5. Risk assessment from business perspective\n\nInclude references to industry standards and competitor strategies where relevant."
            }
        ],
        "temperature": 0.5,
        "max_tokens": 4000
    }
    
    try:
        print("🔍 Querying Perplexity Sonar Pro API...")
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        content = result['choices'][0]['message']['content']
        return {
            "agent": "Perplexity",
            "status": "success",
            "response": content,
            "model": result.get('model'),
            "usage": result.get('usage'),
            "citations": result.get('citations', [])
        }
    except Exception as e:
        return {
            "agent": "Perplexity",
            "status": "error",
            "error": str(e)
        }

def main():
    """Query both agents and save results"""
    print("=" * 80)
    print("🚀 Querying AI Agents for Project Recommendations")
    print("=" * 80)
    print()
    
    # Query DeepSeek
    deepseek_result = query_deepseek(PROJECT_CONTEXT)
    print()
    
    if deepseek_result.get('status') == 'success':
        print("✅ DeepSeek response received")
        print(f"   Model: {deepseek_result.get('model')}")
        print(f"   Tokens: {deepseek_result.get('usage')}")
    else:
        print(f"❌ DeepSeek error: {deepseek_result.get('error')}")
    
    print()
    print("-" * 80)
    print()
    
    # Query Perplexity
    perplexity_result = query_perplexity(PROJECT_CONTEXT)
    print()
    
    if perplexity_result.get('status') == 'success':
        print("✅ Perplexity response received")
        print(f"   Model: {perplexity_result.get('model')}")
        print(f"   Tokens: {perplexity_result.get('usage')}")
        citations = perplexity_result.get('citations', [])
        if citations:
            print(f"   Citations: {len(citations)}")
    else:
        print(f"❌ Perplexity error: {perplexity_result.get('error')}")
    
    # Save results
    results = {
        "timestamp": "2025-11-14T00:00:00Z",
        "project": "Bybit Strategy Tester v2",
        "context": PROJECT_CONTEXT,
        "deepseek": deepseek_result,
        "perplexity": perplexity_result
    }
    
    output_file = "AI_AGENTS_RECOMMENDATIONS.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 80)
    print(f"💾 Results saved to: {output_file}")
    print("=" * 80)
    print()
    
    # Print recommendations
    if deepseek_result.get('status') == 'success':
        print("\n" + "=" * 80)
        print("🤖 DEEPSEEK RECOMMENDATIONS")
        print("=" * 80)
        print(deepseek_result['response'])
    
    if perplexity_result.get('status') == 'success':
        print("\n" + "=" * 80)
        print("🔍 PERPLEXITY RECOMMENDATIONS")
        print("=" * 80)
        print(perplexity_result['response'])
    
    print("\n" + "=" * 80)
    print("✅ Analysis Complete")
    print("=" * 80)

if __name__ == "__main__":
    main()
