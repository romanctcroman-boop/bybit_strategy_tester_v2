"""
DeepSeek Agent Comprehensive Code Audit

Analyzes actual Python code files after critical fixes applied:
- Fix #1: Celery async/await (verified)
- Fix #2: API Keys Security (19 keys encrypted)
- Fix #3: Test Coverage (22.57% baseline)
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.agents.deepseek import DeepSeekAgent, DeepSeekConfig


async def analyze_file(agent: DeepSeekAgent, file_path: Path, category: str, focus: str):
    """Analyze a single file with specific focus"""
    
    print(f"📄 Analyzing: {file_path.name}")
    print(f"   Category: {category}")
    print(f"   Focus: {focus}")
    
    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
        
        print(f"   Size: {len(code_content)} bytes, {len(code_content.splitlines())} lines")
        
        # Call DeepSeek to analyze
        result = await agent.analyze_code(
            code=code_content,
            file_path=str(file_path),
            error_types=["syntax", "logic", "performance", "security"]
        )
        
        if result.status == "completed":
            print(f"✅ Analysis complete ({result.tokens_used} tokens, {result.iterations} iterations)")
            return {
                "file": str(file_path),
                "category": category,
                "focus": focus,
                "status": "success",
                "analysis": result.code,
                "tokens": result.tokens_used,
                "iterations": result.iterations,
                "timestamp": datetime.now().isoformat()
            }
        else:
            print(f"⚠️  Analysis incomplete: {result.status}")
            return {
                "file": str(file_path),
                "category": category,
                "focus": focus,
                "status": result.status,
                "error": result.error_message,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        return {
            "file": str(file_path),
            "category": category,
            "focus": focus,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def run_code_audit():
    """Run comprehensive code audit on key files"""
    
    print("=" * 80)
    print("🤖 DeepSeek Agent - Code Quality Audit")
    print("=" * 80)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    # Initialize agent
    try:
        config = DeepSeekConfig()
        agent = DeepSeekAgent(config)
        print("✅ DeepSeek Agent initialized")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return
    
    # Files to audit (prioritized by importance and coverage)
    audit_targets = [
        # Security (Fix #2)
        {
            "file": "backend/core/secrets_manager.py",
            "category": "Security",
            "focus": "Encryption implementation (Fernet), key rotation, audit logging"
        },
        # Core Engine (50% coverage)
        {
            "file": "backend/core/backtest_engine.py",
            "category": "Performance",
            "focus": "Backtest logic, memory leaks, optimization opportunities"
        },
        # API Integration (42% coverage)
        {
            "file": "backend/services/adapters/bybit.py",
            "category": "Integration",
            "focus": "API calls, error handling, rate limiting, connection pooling"
        },
        # Queue Management (22% coverage)
        {
            "file": "backend/queue/redis_queue_manager.py",
            "category": "Concurrency",
            "focus": "Redis streams, task distribution, deadlock prevention"
        },
        # Web API (38% coverage)
        {
            "file": "backend/api/app.py",
            "category": "Architecture",
            "focus": "FastAPI setup, middleware, CORS, error handling"
        },
        # DeepSeek Agent (62% coverage)
        {
            "file": "backend/agents/deepseek.py",
            "category": "AI Integration",
            "focus": "API calls, retry logic, caching, auto-fix loop"
        },
        # Database Models (100% coverage)
        {
            "file": "backend/models/data_types.py",
            "category": "Data Modeling",
            "focus": "Type safety, validation, schema correctness"
        },
        # Security Layer (16% coverage - HIGH PRIORITY)
        {
            "file": "backend/security/rate_limiter.py",
            "category": "Security",
            "focus": "Rate limiting algorithm, Redis storage, attack prevention"
        }
    ]
    
    results = []
    
    for i, target in enumerate(audit_targets, 1):
        print(f"📋 Audit {i}/{len(audit_targets)}")
        print("-" * 80)
        
        file_path = project_root / target["file"]
        
        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            print()
            continue
        
        result = await analyze_file(
            agent,
            file_path,
            target["category"],
            target["focus"]
        )
        results.append(result)
        
        print()
        print("🔍 Analysis Result:")
        print("-" * 80)
        if result["status"] == "success":
            print(result["analysis"])
        else:
            print(f"❌ {result.get('error', 'Unknown error')}")
        print()
        print("=" * 80)
        print()
        
        # Rate limiting
        await asyncio.sleep(3)
    
    # Save results
    output_file = project_root / "DEEPSEEK_CODE_AUDIT.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Summary
    print("=" * 80)
    print("✅ Code Audit Complete!")
    print(f"📄 Report saved: {output_file}")
    print("=" * 80)
    print()
    
    print("📊 Audit Summary")
    print("-" * 80)
    print(f"Files analyzed: {len(audit_targets)}")
    print(f"Successful: {sum(1 for r in results if r['status'] == 'success')}")
    print(f"Failed: {sum(1 for r in results if r['status'] != 'success')}")
    
    total_tokens = sum(r.get('tokens', 0) for r in results if r['status'] == 'success')
    print(f"Total tokens: {total_tokens:,}")
    print()
    
    # Category breakdown
    print("📂 By Category:")
    categories = {}
    for r in results:
        cat = r['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)
    
    for cat, items in categories.items():
        success = sum(1 for i in items if i['status'] == 'success')
        print(f"   {cat}: {success}/{len(items)} successful")
    print()
    
    return results


if __name__ == "__main__":
    print()
    print("🚀 Starting DeepSeek Code Audit...")
    print()
    
    try:
        results = asyncio.run(run_code_audit())
        
        print()
        print("🎉 Audit completed!")
        print()
        print("📌 Review DEEPSEEK_CODE_AUDIT.json for detailed findings")
        print()
        
    except KeyboardInterrupt:
        print()
        print("⚠️  Interrupted by user")
        print()
    except Exception as e:
        print()
        print(f"❌ Audit failed: {e}")
        print()
        import traceback
        traceback.print_exc()
