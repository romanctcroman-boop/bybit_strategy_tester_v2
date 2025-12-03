"""
DeepSeek Agent Full Project Audit

Runs comprehensive analysis of the project after applying critical fixes:
- Fix #1: Celery async/await verification
- Fix #2: API Keys Security (19 keys encrypted)
- Fix #3: Test Coverage (22.57% baseline)

Audit focuses on:
1. Code quality and architecture
2. Security best practices
3. Test coverage gaps
4. Performance bottlenecks
5. Technical debt assessment
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import json
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

MAX_ATTACHMENT_CHARS = 4000

from backend.agents.deepseek import DeepSeekAgent, DeepSeekConfig


def extract_total_tokens(token_entry):
    """Return best-effort total token count from varied DeepSeek responses."""
    if isinstance(token_entry, (int, float)):
        return int(token_entry)
    if isinstance(token_entry, dict):
        if "total_tokens" in token_entry:
            return int(token_entry["total_tokens"])
        if "total" in token_entry:
            return int(token_entry["total"])
        return int(sum(value for value in token_entry.values() if isinstance(value, (int, float))))
    return 0


def build_prompt_with_code(base_prompt: str, file_paths: Optional[List[str]]) -> str:
    """Append code snippets from real files so DeepSeek analyzes actual source."""
    if not file_paths:
        return base_prompt

    sections: list[str] = []
    for rel_path in file_paths:
        file_path = project_root / rel_path
        if not file_path.exists():
            sections.append(f"# File missing: {rel_path}")
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            sections.append(f"# Skipped non-text file: {rel_path}")
            continue

        snippet = content[:MAX_ATTACHMENT_CHARS]
        sections.append(f"# File: {rel_path}\n```python\n{snippet}\n```")

    if sections:
        return f"{base_prompt}\n\nAttached code for analysis:\n" + "\n\n".join(sections)
    return base_prompt


async def run_comprehensive_audit():
    """Run DeepSeek Agent audit of the entire project"""
    
    print("=" * 80)
    print("🤖 DeepSeek Agent - Comprehensive Project Audit")
    print("=" * 80)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Project: bybit_strategy_tester_v2")
    print(f"🌿 Branch: feature/deadlock-prevention-clean")
    print("=" * 80)
    print()
    
    # Initialize DeepSeek Agent
    try:
        config = DeepSeekConfig()
        agent = DeepSeekAgent(config)
        print("✅ DeepSeek Agent initialized")
        print(f"   Model: {config.model}")
        print(f"   API URL: {config.api_url}")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize DeepSeek Agent: {e}")
        return
    
    # Audit prompts focusing on applied fixes
    audit_prompts = [
        {
            "category": "Security Assessment",
            "prompt": """
Analyze the security implementation after applying encryption fixes:

Context:
- Implemented SecretsManager with Fernet AES-128 encryption
- Migrated 19 API keys to encrypted storage (.secrets.enc)
- Created audit logging system (logs/secrets_audit.log)
- Backup strategy: .env.env.backup.1762896416

Files to review:
- backend/core/secrets_manager.py (420 lines)
- migrate_secrets_to_encrypted.py (310 lines)
- .secrets.enc (encrypted storage)

Questions:
1. Is the Fernet encryption implementation secure?
2. Are there any key rotation vulnerabilities?
3. Is the master key management safe?
4. Are audit logs comprehensive enough?
5. What additional security measures are recommended?

Provide:
- Security rating (1-10)
- Critical vulnerabilities (if any)
- Best practice recommendations
- Compliance considerations (GDPR, SOC 2)
""",
            "files": [
                "backend/core/secrets_manager.py",
                "migrate_secrets_to_encrypted.py"
            ]
        },
        {
            "category": "Test Coverage Analysis",
            "prompt": """
Analyze test coverage gaps after establishing baseline:

Current Coverage: 22.57%
- Tests passed: 109
- Tests skipped: 24 (MCP tools)
- Total statements: 18,247
- Covered statements: 4,576

Coverage Distribution:
- 0% coverage: 66 files (agents, routers, ML, visualization, scaling)
- 1-50%: 39 files
- 51-90%: 30 files
- 90-100%: 14 files (complete)

Critical LOW coverage areas:
1. backend/agents/* (0% coverage)
2. backend/api/routers/* (mostly 0-20%)
3. backend/ml/* (0% coverage)
4. backend/optimization/* (18-23%)
5. backend/security/* (16-45%)

Questions:
1. Which 0% files are HIGHEST priority for testing?
2. What's the fastest path to 40% coverage?
3. Which modules are highest risk with low coverage?
4. Recommended test strategy (unit vs integration)?
5. Should we focus on breadth or depth first?

Provide:
- Priority ranking of files to test (top 10)
- Quick win opportunities (+10-15% coverage)
- Test scaffolding recommendations
- Target: 80% coverage roadmap
""",
            "files": [
                "backend/agents/unified_agent_interface.py",
                "backend/api/routers/strategies.py",
                "backend/ml/online_learner.py"
            ]
        },
        {
            "category": "Code Quality & Architecture",
            "prompt": """
Perform comprehensive code quality audit:

Project Statistics:
- Total files: ~150 Python modules
- Backend structure: FastAPI + Celery + Redis
- Frontend: Vue.js (not audited)
- Database: PostgreSQL + SQLAlchemy
- Caching: Redis with TTL

Areas to analyze:
1. **Async/Await Usage**: Verified Celery tasks are sync (Fix #1 complete)
2. **Error Handling**: Are exceptions properly caught and logged?
3. **Database Connections**: Any connection pool leaks?
4. **Memory Management**: Potential memory leaks in long-running workers?
5. **API Design**: RESTful best practices followed?
6. **Type Hints**: Coverage and correctness?
7. **Documentation**: Docstring completeness?

Focus files:
- backend/core/backtest_engine.py (475 lines, 50% coverage)
- backend/services/adapters/bybit.py (526 lines, 42% coverage)
- backend/queue/redis_queue_manager.py (205 lines, 22% coverage)
- backend/api/app.py (194 lines, 38% coverage)

Provide:
- Code quality score (1-10)
- Critical issues requiring immediate attention
- Refactoring priorities
- Architecture recommendations
- Technical debt estimate (hours)
""",
            "files": [
                "backend/core/backtest_engine.py",
                "backend/services/adapters/bybit.py",
                "backend/queue/redis_queue_manager.py",
                "backend/api/app.py"
            ]
        },
        {
            "category": "Performance & Scalability",
            "prompt": """
Analyze performance bottlenecks and scalability issues:

System Architecture:
- Backend: FastAPI (async) + Celery workers (sync)
- Message Queue: Redis Streams
- Database: PostgreSQL with connection pooling
- Caching: Redis (LRU + TTL)
- Background Jobs: Celery with 4 workers

Known Performance Areas:
1. Backtest engine: processes 1000s of candles
2. Optimization tasks: grid search, walk-forward
3. Real-time WebSocket connections (analytics_ws)
4. Database queries (no indexes audit done yet)
5. API rate limiting (middleware implemented)

Questions:
1. Where are the biggest performance bottlenecks?
2. Is the Celery worker configuration optimal?
3. Are database queries N+1 problematic?
4. Is caching strategy effective?
5. Can the system handle 100 concurrent users?
6. What's the horizontal scaling strategy?

Provide:
- Performance rating (1-10)
- Critical bottlenecks (top 5)
- Optimization recommendations
- Scalability roadmap
- Load testing recommendations
""",
            "files": [
                "backend/services/model_inference.py",
                "backend/services/strategy_arena.py",
                "backend/tasks/backtest_tasks.py"
            ]
        },
        {
            "category": "Technical Debt & Maintainability",
            "prompt": """
Assess technical debt after applying critical fixes:

Recent Improvements:
- Fix #1: Celery async/await (verified correct)
- Fix #2: API keys encrypted (19/19 migrated)
- Fix #3: Coverage baseline established (22.57%)

Remaining Known Issues:
- 24 MCP tool tests skipped (FastMCP refactoring needed)
- 66 files with 0% test coverage
- Missing database indexes (identified by DeepSeek earlier)
- Pydantic v1 deprecation warnings (3 instances)
- TypeScript strict mode disabled (frontend)

Questions:
1. What's the estimated technical debt (hours/days)?
2. Which debt items are highest priority?
3. What's the recommended debt paydown sequence?
4. Are there any "ticking time bombs" in the code?
5. How maintainable is the codebase (1-10)?

Provide:
- Technical debt score (1-10, 10 = clean)
- Debt inventory with time estimates
- Prioritized remediation plan
- Refactoring opportunities
- Code smell analysis
""",
            "files": [
                "backend/reliability/circuit_breaker.py",
                "backend/settings.py",
                "backend/api/app.py"
            ]
        }
    ]
    
    # Run each audit
    results = []
    for i, audit in enumerate(audit_prompts, 1):
        print(f"📋 Audit {i}/{len(audit_prompts)}: {audit['category']}")
        print("-" * 80)
        
        try:
            prompt_payload = build_prompt_with_code(audit['prompt'], audit.get('files'))

            analysis_result = await agent.analyze_code(
                code=prompt_payload,
                file_path=f"audit_{i}_{audit['category'].replace(' ', '_').lower()}.txt"
            )
            
            # Extract response
            if analysis_result and analysis_result.status == "completed":
                content = analysis_result.code
                
                result = {
                    "category": audit['category'],
                    "timestamp": datetime.now().isoformat(),
                    "analysis": content,
                    "tokens_used": analysis_result.tokens_used,
                    "iterations": analysis_result.iterations
                }
                results.append(result)
                
                print(f"✅ Analysis complete")
                print(f"   Tokens: {analysis_result.tokens_used}")
                print(f"   Iterations: {analysis_result.iterations}")
                print()
                print(content)
                print()
                print("=" * 80)
                print()
                
                # Rate limiting delay
                await asyncio.sleep(2)
            else:
                print(f"⚠️  Analysis incomplete: {analysis_result.status}")
                print()
                
        except Exception as e:
            print(f"❌ Audit failed: {e}")
            print()
            results.append({
                "category": audit['category'],
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
    
    # Save results
    output_file = project_root / "DEEPSEEK_AUDIT_REPORT.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("=" * 80)
    print("✅ Audit Complete!")
    print(f"📄 Full report saved to: {output_file}")
    print("=" * 80)
    print()
    
    # Generate summary
    print("📊 Audit Summary")
    print("-" * 80)
    print(f"Categories analyzed: {len(audit_prompts)}")
    print(f"Successful audits: {sum(1 for r in results if 'analysis' in r)}")
    print(f"Failed audits: {sum(1 for r in results if 'error' in r)}")
    
    total_tokens = sum(extract_total_tokens(r.get('tokens_used')) for r in results)
    print(f"Total tokens used: {total_tokens:,}")
    print()
    
    return results


if __name__ == "__main__":
    print()
    print("🚀 Starting DeepSeek Agent Audit...")
    print()
    
    try:
        results = asyncio.run(run_comprehensive_audit())
        
        print()
        print("🎉 Audit completed successfully!")
        print()
        print("📌 Next Steps:")
        print("   1. Review DEEPSEEK_AUDIT_REPORT.json")
        print("   2. Prioritize recommendations")
        print("   3. Create GitHub issues for high-priority items")
        print("   4. Update project roadmap")
        print()
        
    except KeyboardInterrupt:
        print()
        print("⚠️  Audit interrupted by user")
        print()
    except Exception as e:
        print()
        print(f"❌ Audit failed: {e}")
        print()
        import traceback
        traceback.print_exc()
