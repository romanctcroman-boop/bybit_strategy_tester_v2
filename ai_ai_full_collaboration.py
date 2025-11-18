"""
Финальный AI → AI анализ: Perplexity → DeepSeek
Perplexity проводит глубокий анализ реализованных улучшений,
затем DeepSeek оценивает качество и даёт рекомендации
"""

import asyncio
import httpx
import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Загрузка переменных окружения
project_root = Path(__file__).parent
load_dotenv(project_root / ".env")

# API ключи
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# ═══════════════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

TIMEOUT = 120

# ═══════════════════════════════════════════════════════════════════════════
# ФУНКЦИИ API
# ═══════════════════════════════════════════════════════════════════════════

async def call_perplexity(query: str, model: str = "sonar") -> dict:
    """Вызов Perplexity AI"""
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a senior software architect conducting code review and technical audits. Provide detailed, objective analysis with specific examples and metrics."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }
    
    print(f"\n📡 Вызов Perplexity API (model={model})...")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(PERPLEXITY_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # Извлечение ответа
        answer = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        citations = result.get("citations", [])
        
        return {
            "answer": answer,
            "citations": citations,
            "model": model,
            "timestamp": datetime.now().isoformat()
        }

async def call_deepseek(query: str, model: str = "deepseek-chat") -> dict:
    """Вызов DeepSeek AI"""
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are DeepSeek Coder, an expert in code quality, architecture, and best practices. Provide actionable recommendations with code examples where appropriate."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }
    
    print(f"\n📡 Вызов DeepSeek API (model={model})...")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # Извлечение ответа
        answer = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        return {
            "answer": answer,
            "model": model,
            "timestamp": datetime.now().isoformat()
        }

# ═══════════════════════════════════════════════════════════════════════════
# АНАЛИЗ УЛУЧШЕНИЙ
# ═══════════════════════════════════════════════════════════════════════════

async def stage_1_perplexity_audit() -> dict:
    """Stage 1: Perplexity проводит аудит реализованных улучшений"""
    
    # Загрузка отчёта о сравнении
    comparison_file = project_root / "ai_collaboration_reports" / "mcp_improvements_comparison_20251106_234838.json"
    
    with open(comparison_file, 'r', encoding='utf-8') as f:
        comparison_data = json.load(f)
    
    query = f"""Conduct a professional code review and quality assessment of MCP server improvements.

CONTEXT:
A previous audit (November 6, 2025 19:01) identified 7 critical issues in an MCP (Model Context Protocol) server implementation:

1. Monolithic structure (3933 lines in one file)
2. No modular architecture
3. No unified API layer for AI providers
4. Logging coverage only 61.2%
5. Missing centralized error handling
6. No API response caching
7. Imbalanced AI provider usage

CURRENT STATE AFTER REFACTORING (November 6, 2025 23:48):

**Improvements Implemented:**
{json.dumps(comparison_data['improvements'], indent=2, ensure_ascii=False)}

**Remaining Issues:**
{json.dumps(comparison_data['remaining_issues'], indent=2, ensure_ascii=False)}

**Metrics:**
- Code reduction: 3933 → 1909 lines (-51.5%)
- Architecture: monolithic → modular
- Modules created: analysis, project, search, strategy, utility
- Unified API: Yes (ProviderManager)
- Error handling: Yes (retry, timeout, 4 error types)
- Security: Yes (key_manager with encryption)
- Documentation: Yes (README, ARCHITECTURE.md)

AUDIT QUESTIONS:

1. **Quality of Implementation (1-10 scale)**
   - Is the 51.5% code reduction genuine improvement or just code movement?
   - Does modular structure follow best practices (separation of concerns, SOLID principles)?
   - How robust is the ProviderManager implementation?

2. **Remaining Concerns**
   - Logging coverage dropped from 61.2% to 20% - is this acceptable?
   - Missing caching - how critical is this for performance?
   - Are there hidden technical debts introduced during refactoring?

3. **Production Readiness**
   - Can this server handle production workloads?
   - What are the potential failure points?
   - Performance implications of the new architecture?

4. **Best Practices Compliance**
   - Does it follow MCP protocol standards?
   - Is error handling truly production-grade?
   - Security: Is key encryption implementation secure?

5. **Next Steps Priority**
   - What should be tackled first: logging or caching?
   - Are there critical issues not captured in the analysis?
   - What are the quick wins vs long-term improvements?

Provide a detailed, objective assessment with specific examples and actionable recommendations. Use a rating system (A-F) for different aspects."""

    result = await call_perplexity(query, model="sonar-pro")
    
    print("\n✅ Stage 1 Complete: Perplexity Audit")
    print(f"   Response length: {len(result['answer'])} characters")
    
    return result

async def stage_2_deepseek_recommendations(perplexity_audit: dict) -> dict:
    """Stage 2: DeepSeek анализирует аудит Perplexity и даёт конкретные рекомендации"""
    
    query = f"""You are DeepSeek Coder reviewing a Perplexity AI audit of MCP server refactoring.

PERPLEXITY AUDIT RESULTS:
{perplexity_audit['answer']}

YOUR TASK:
Based on Perplexity's assessment, provide:

1. **Implementation Plan for Remaining Issues**
   - Logging coverage: 20% → 90%
     * Which tools need logging added?
     * Code template for standardized logging
     * Estimated effort and priority
   
   - API Caching implementation
     * Cache strategy (LRU, TTL-based, hybrid)
     * Where to implement (provider level, tool level, both)
     * Code example for cache decorator
     * Estimated impact on performance

2. **Code Quality Improvements**
   - Specific refactoring suggestions with code examples
   - Type hints completion
   - Documentation improvements
   - Testing recommendations

3. **Risk Assessment**
   - Identify any critical issues Perplexity might have missed
   - Rate severity (Critical, High, Medium, Low)
   - Provide mitigation strategies

4. **Priority Matrix**
   Create a 2x2 matrix:
   - High Impact / Low Effort (do first)
   - High Impact / High Effort (plan carefully)
   - Low Impact / Low Effort (quick wins)
   - Low Impact / High Effort (reconsider)

5. **Concrete Action Items**
   Provide 5-10 specific, actionable tasks with:
   - Task description
   - Estimated time
   - Required skills
   - Success criteria
   - Code examples where applicable

Be specific, practical, and focus on actionable improvements. Include code snippets for key recommendations."""

    result = await call_deepseek(query)
    
    print("\n✅ Stage 2 Complete: DeepSeek Recommendations")
    print(f"   Response length: {len(result['answer'])} characters")
    
    return result

async def stage_3_perplexity_validation(deepseek_recommendations: dict) -> dict:
    """Stage 3: Perplexity проверяет рекомендации DeepSeek (BONUS)"""
    
    query = f"""You are Perplexity AI reviewing DeepSeek Coder's implementation recommendations for an MCP server.

DEEPSEEK RECOMMENDATIONS:
{deepseek_recommendations['answer']}

YOUR TASK: Quality Control Review

1. **Feasibility Check**
   - Are the recommendations realistic and achievable?
   - Is the effort estimation accurate?
   - Any missing considerations?

2. **Best Practices Validation**
   - Do the suggestions align with current industry standards?
   - Are there better alternatives for any recommendations?
   - Any potential pitfalls in the proposed approach?

3. **Priority Re-Ranking**
   - Do you agree with DeepSeek's priority matrix?
   - Would you reorder any tasks? Why?

4. **Additional Recommendations**
   - What did DeepSeek miss?
   - Any emerging best practices to consider?

5. **Final Approval**
   - Overall assessment of DeepSeek's recommendations (A-F grade)
   - Top 3 must-do items
   - Top 3 can-wait items
   - Red flags or concerns

Be critical but constructive. Point out any gaps or potential issues."""

    result = await call_perplexity(query, model="sonar-pro")
    
    print("\n✅ Stage 3 Complete: Perplexity Validation")
    print(f"   Response length: {len(result['answer'])} characters")
    
    return result

# ═══════════════════════════════════════════════════════════════════════════
# СОХРАНЕНИЕ РЕЗУЛЬТАТОВ
# ═══════════════════════════════════════════════════════════════════════════

def save_ai_collaboration_report(results: dict):
    """Сохранение полного отчёта AI → AI взаимодействия"""
    
    output_dir = project_root / "ai_collaboration_reports"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON отчёт
    json_file = output_dir / f"ai_ai_collaboration_full_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 JSON отчёт сохранён: {json_file}")
    
    # Markdown отчёт
    md_file = output_dir / f"ai_ai_collaboration_full_{timestamp}.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# AI → AI Collaborative Analysis: MCP Server Improvements\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 🔄 Analysis Workflow\n\n")
        f.write("```\n")
        f.write("Stage 1: Perplexity Audit → Professional code review and quality assessment\n")
        f.write("           ↓\n")
        f.write("Stage 2: DeepSeek Recommendations → Concrete action items and code examples\n")
        f.write("           ↓\n")
        f.write("Stage 3: Perplexity Validation → Quality control and final approval\n")
        f.write("```\n\n")
        
        f.write("---\n\n")
        
        # Stage 1
        f.write("## 📊 Stage 1: Perplexity Professional Audit\n\n")
        f.write(f"**Model:** {results['stage_1']['model']}\n")
        f.write(f"**Timestamp:** {results['stage_1']['timestamp']}\n\n")
        f.write("### Audit Results:\n\n")
        f.write(results['stage_1']['answer'])
        f.write("\n\n")
        
        if results['stage_1'].get('citations'):
            f.write("### Citations:\n\n")
            for i, citation in enumerate(results['stage_1']['citations'], 1):
                f.write(f"{i}. {citation}\n")
            f.write("\n")
        
        f.write("---\n\n")
        
        # Stage 2
        f.write("## 🛠️ Stage 2: DeepSeek Implementation Recommendations\n\n")
        f.write(f"**Model:** {results['stage_2']['model']}\n")
        f.write(f"**Timestamp:** {results['stage_2']['timestamp']}\n\n")
        f.write("### Recommendations:\n\n")
        f.write(results['stage_2']['answer'])
        f.write("\n\n")
        
        f.write("---\n\n")
        
        # Stage 3
        f.write("## ✅ Stage 3: Perplexity Quality Control\n\n")
        f.write(f"**Model:** {results['stage_3']['model']}\n")
        f.write(f"**Timestamp:** {results['stage_3']['timestamp']}\n\n")
        f.write("### Validation Results:\n\n")
        f.write(results['stage_3']['answer'])
        f.write("\n\n")
        
        if results['stage_3'].get('citations'):
            f.write("### Citations:\n\n")
            for i, citation in enumerate(results['stage_3']['citations'], 1):
                f.write(f"{i}. {citation}\n")
            f.write("\n")
        
        f.write("---\n\n")
        
        f.write("## 🎯 Summary\n\n")
        f.write("This report demonstrates a complete AI → AI collaborative workflow:\n\n")
        f.write("1. **Perplexity** provided professional audit with objective assessment\n")
        f.write("2. **DeepSeek** delivered concrete implementation plan with code examples\n")
        f.write("3. **Perplexity** validated recommendations and provided quality control\n\n")
        f.write("This three-stage approach ensures:\n")
        f.write("- Objective external review\n")
        f.write("- Actionable implementation guidance\n")
        f.write("- Quality assurance and validation\n\n")
        f.write("**Result:** Production-ready recommendations for MCP server improvements\n")
    
    print(f"📄 Markdown отчёт сохранён: {md_file}")
    
    return json_file, md_file

# ═══════════════════════════════════════════════════════════════════════════
# ОСНОВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """Основная функция: полный цикл AI → AI анализа"""
    
    print("\n" + "=" * 80)
    print("🤖 AI → AI COLLABORATIVE ANALYSIS")
    print("=" * 80)
    print("\nPerplexity → DeepSeek → Perplexity (3-stage validation)")
    print("\n" + "=" * 80 + "\n")
    
    try:
        # Stage 1: Perplexity Audit
        print("\n🔍 STAGE 1: Perplexity Professional Audit")
        print("-" * 80)
        stage_1 = await stage_1_perplexity_audit()
        print(f"\n📝 Preview:\n{stage_1['answer'][:500]}...\n")
        
        # Stage 2: DeepSeek Recommendations
        print("\n🛠️  STAGE 2: DeepSeek Implementation Recommendations")
        print("-" * 80)
        stage_2 = await stage_2_deepseek_recommendations(stage_1)
        print(f"\n📝 Preview:\n{stage_2['answer'][:500]}...\n")
        
        # Stage 3: Perplexity Validation
        print("\n✅ STAGE 3: Perplexity Quality Control")
        print("-" * 80)
        stage_3 = await stage_3_perplexity_validation(stage_2)
        print(f"\n📝 Preview:\n{stage_3['answer'][:500]}...\n")
        
        # Сохранение результатов
        results = {
            "workflow": "Perplexity → DeepSeek → Perplexity",
            "stages": 3,
            "stage_1": stage_1,
            "stage_2": stage_2,
            "stage_3": stage_3,
            "completed_at": datetime.now().isoformat()
        }
        
        json_file, md_file = save_ai_collaboration_report(results)
        
        print("\n" + "=" * 80)
        print("✅ AI → AI COLLABORATIVE ANALYSIS COMPLETE")
        print("=" * 80)
        print(f"\n📁 Results available at:")
        print(f"   - {json_file}")
        print(f"   - {md_file}\n")
        
        return results
        
    except Exception as e:
        print(f"\n❌ Error during AI → AI collaboration: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(main())
