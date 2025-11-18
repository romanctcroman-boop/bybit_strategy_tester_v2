"""
🔥 Simplified Synchronous Perplexity Audit
Использует httpx synchronous client для стабильности
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import httpx
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent
AI_AUDIT_DIR = PROJECT_ROOT / "ai_audit_results"
OUTPUT_DIR = PROJECT_ROOT / "parallel_audit_results"
OUTPUT_DIR.mkdir(exist_ok=True)

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


def call_perplexity(prompt: str, max_tokens: int = 2000) -> str:
    """Синхронный вызов Perplexity API"""
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are an expert software architect and code analyst."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens
    }
    
    with httpx.Client(timeout=60.0) as client:
        response = client.post(PERPLEXITY_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def analyze_audit_files() -> Dict:
    """Быстрый анализ существующих аудитов"""
    print("📊 Analyzing audit files...")
    
    audit_files = list(AI_AUDIT_DIR.glob("*.json"))
    print(f"   Found {len(audit_files)} JSON files")
    
    return {
        "total_files": len(audit_files),
        "background_analysis": len(list(AI_AUDIT_DIR.glob("background_analysis_*.json"))),
        "test_watcher": len(list(AI_AUDIT_DIR.glob("test_watcher_audit_*.json"))),
        "deepseek_audits": len(list(AI_AUDIT_DIR.glob("deepseek_*.json")))
    }


def scan_project() -> Dict:
    """Сканирование структуры проекта"""
    print("📂 Scanning project structure...")
    
    python_files = list(PROJECT_ROOT.glob("**/*.py"))
    backend_files = list((PROJECT_ROOT / "backend").glob("**/*.py")) if (PROJECT_ROOT / "backend").exists() else []
    test_files = list((PROJECT_ROOT / "tests").glob("**/*.py")) if (PROJECT_ROOT / "tests").exists() else []
    
    print(f"   Python files: {len(python_files)}")
    print(f"   Backend files: {len(backend_files)}")
    print(f"   Test files: {len(test_files)}")
    
    return {
        "total_python": len(python_files),
        "backend": len(backend_files),
        "tests": len(test_files)
    }


def generate_comprehensive_tz(audit_summary: Dict, project_stats: Dict) -> str:
    """Генерация comprehensive ТЗ через Perplexity"""
    print("\n🤖 Generating comprehensive Technical Specification...")
    
    prompt = f"""На основе анализа проекта bybit_strategy_tester_v2, создай детальное техническое задание.

📊 **Audit Summary:**
- Всего файлов аудита: {audit_summary['total_files']}
- Background analysis: {audit_summary['background_analysis']}
- Test watcher logs: {audit_summary['test_watcher']}
- DeepSeek audits: {audit_summary['deepseek_audits']}

📂 **Project Statistics:**
- Total Python files: {project_stats['total_python']}
- Backend files: {project_stats['backend']}
- Test files: {project_stats['tests']}

🎯 **Key Findings (from previous audits):**
1. MCP Server: 0% availability (критическая проблема)
2. DeepSeek Agent: 93% uptime (стабильно работает)
3. Perplexity Agent: 90% uptime (стабильно работает)
4. Datetime.utcnow() deprecated issues (уже исправлено)
5. 16 API keys configured (8 DeepSeek + 8 Perplexity)

---

# СОЗДАЙ ТЕХНИЧЕСКОЕ ЗАДАНИЕ СО СЛЕДУЮЩИМИ РАЗДЕЛАМИ:

## 1. Executive Summary
- Текущее состояние проекта (оценка 1-10)
- Ключевые достижения
- TOP-5 критических проблем
- Рекомендуемые приоритеты

## 2. Critical Issues (Требуют немедленного внимания)
Для каждой проблемы укажи:
- Название
- Описание
- Impact (HIGH/MEDIUM/LOW)
- Effort (1-5 часов / 1-2 дня / 1-2 недели)
- Priority (P0 / P1 / P2)

## 3. Architecture Improvements
### Backend:
- Refactoring tasks
- Code quality improvements
- Database optimization

### Frontend:
- UI/UX improvements
- Performance optimization
- TypeScript migration status

### AI Agents:
- MCP Server восстановление
- DeepSeek integration enhancements
- Perplexity usage optimization

## 4. Testing & Quality Assurance
- Current test coverage analysis
- Missing test scenarios
- CI/CD recommendations
- Code quality metrics

## 5. Performance Optimization
- Bottlenecks identified
- Caching strategies
- Query optimization
- Async/await best practices

## 6. Security Hardening
- Vulnerabilities assessment
- API keys management review
- Input validation gaps
- Secure coding practices

## 7. Implementation Roadmap
### Phase 1 (1-2 weeks): Critical Fixes
- MCP Server recovery
- P0 issues resolution

### Phase 2 (2-4 weeks): Major Improvements
- Architecture refactoring
- Test coverage increase
- Performance optimization

### Phase 3 (1-2 months): Long-term Enhancements
- New features
- Advanced optimizations
- Documentation completion

## 8. Success Metrics & KPIs
- Performance targets
- Code quality benchmarks
- Test coverage goals
- System availability targets

## 9. Dependencies & Risks
- External dependencies
- Technical debt assessment
- Risk mitigation strategies

## 10. Estimated Resources
- Developer hours required
- Infrastructure costs
- Third-party services

---

**Формат:** Markdown document, comprehensive, actionable, with specific recommendations."""

    try:
        result = call_perplexity(prompt, max_tokens=4000)
        print("✅ Technical Specification generated successfully!")
        return result
    except Exception as e:
        print(f"❌ Failed to generate ТЗ: {e}")
        return f"# Error\n\nFailed to generate ТЗ: {e}"


def main():
    """Main execution"""
    print("="*80)
    print("🔥 Simplified Perplexity Audit Engine")
    print("="*80)
    print()
    
    if not PERPLEXITY_API_KEY:
        print("❌ PERPLEXITY_API_KEY not found in environment!")
        return
    
    print(f"✅ API Key loaded: {PERPLEXITY_API_KEY[:20]}...")
    print()
    
    # Step 1: Gather context
    print("📊 Step 1/3: Gathering context...")
    audit_summary = analyze_audit_files()
    project_stats = scan_project()
    print()
    
    # Step 2: Generate comprehensive ТЗ
    print("🤖 Step 2/3: Generating Technical Specification...")
    tz_content = generate_comprehensive_tz(audit_summary, project_stats)
    print()
    
    # Step 3: Save results
    print("💾 Step 3/3: Saving results...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save ТЗ
    tz_path = OUTPUT_DIR / f"COMPREHENSIVE_TZ_{timestamp}.md"
    with open(tz_path, 'w', encoding='utf-8') as f:
        f.write(tz_content)
    print(f"   ТЗ saved: {tz_path}")
    
    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "audit_summary": audit_summary,
        "project_stats": project_stats,
        "tz_generated": True,
        "tz_path": str(tz_path)
    }
    
    summary_path = OUTPUT_DIR / f"audit_summary_{timestamp}.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"   Summary saved: {summary_path}")
    
    print()
    print("="*80)
    print("✅ Audit complete!")
    print(f"📄 Check {OUTPUT_DIR}/ for results")
    print("="*80)


if __name__ == "__main__":
    main()
