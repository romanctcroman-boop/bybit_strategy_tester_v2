"""
Phase 3: Production Deployment Preparation - Generator Script
Uses Perplexity AI to generate comprehensive deployment strategy

Workflow: Copilot → This Script → Perplexity API → Deployment Plan → Copilot Analysis
"""

import asyncio
import aiohttp
import json
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import secure key manager
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "backend"))
from security.key_manager import get_decrypted_key

# Perplexity API configuration
PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# Phase 1 & 2 Context
PROJECT_CONTEXT = {
    "phase_1_complete": {
        "status": "✅ 100% pass rate",
        "optimizations": [
            "Backtest Vectorization (200k bars/sec)",
            "SR RSI Async (100% edge case coverage)",
            "Data Service Async (11x speedup, production features)"
        ],
        "features": [
            "Concurrency control (Semaphore)",
            "Connection pooling (TCPConnector)",
            "Retry logic (exponential backoff)",
            "Input validation",
            "Resource cleanup"
        ]
    },
    "phase_2_complete": {
        "status": "✅ 10/10 integration tests passing",
        "categories": [
            "End-to-End Integration (2 tests)",
            "Concurrency Testing (2 tests)",
            "Error Handling (3 tests)",
            "Performance Benchmarking (3 tests)"
        ],
        "components_verified": [
            "AsyncDataService → BacktestEngine pipeline",
            "Parallel SR/RSI calculation",
            "Multi-symbol concurrent loading",
            "Edge case handling (empty data, missing columns)"
        ]
    },
    "system_architecture": {
        "backend": "Python 3.13, asyncio, aiohttp",
        "database": "PostgreSQL (planned), Redis (planned)",
        "frontend": "Electron + React (existing)",
        "data_processing": "pandas, numpy (vectorized)",
        "testing": "pytest, pytest-asyncio"
    },
    "deployment_target": {
        "environment": "Windows 10/11",
        "python_version": "3.13.3",
        "venv": ".venv (isolated environment)",
        "scale": "Single machine, multi-core CPU"
    }
}


async def query_perplexity_for_deployment_plan() -> dict:
    """
    Query Perplexity AI to generate comprehensive deployment preparation plan.
    
    Returns:
        dict: Response containing deployment strategy, checklist, and citations
    """
    
    prompt = f"""
You are an expert DevOps/SRE engineer specializing in Python production deployments.

**CONTEXT: Crypto Backtesting System - Phase 3 Deployment**

**Project Status:**
- Phase 1: ✅ COMPLETE (100% optimizations verified)
- Phase 2: ✅ COMPLETE (100% integration tests passing)
- Phase 3: 🚀 STARTING (Production deployment preparation)

**System Details:**
{json.dumps(PROJECT_CONTEXT, indent=2)}

**TASK: Generate Phase 3 Production Deployment Preparation Plan**

Create a comprehensive, actionable deployment strategy covering:

**1. RISK ASSESSMENT (Priority: CRITICAL)**

Analyze potential production risks:

a) **Concurrency Risks:**
   - Race conditions in AsyncDataService (Semaphore usage)
   - Connection pool exhaustion (TCPConnector limit=100)
   - Deadlocks in async operations
   - Thread safety in pandas/numpy operations

b) **Memory Risks:**
   - Memory leaks (unclosed connections, dangling references)
   - Large DataFrame memory consumption (1000+ bars per symbol)
   - Connection pool memory overhead
   - Async task accumulation

c) **Performance Risks:**
   - Throughput degradation under load
   - Latency spikes during concurrent operations
   - I/O bottlenecks (file system, network)
   - CPU contention (vectorized operations)

d) **Data Integrity Risks:**
   - Data corruption during parallel writes
   - NaN propagation in calculations
   - Signal lookahead bias
   - Timestamp alignment issues

**Mitigation Strategies:** For each risk, provide specific mitigation (code patterns, monitoring, testing)

**2. CI/CD PIPELINE SETUP (Priority: HIGH)**

Design automated deployment pipeline:

a) **Pre-commit Hooks:**
   - Code formatting (black, isort)
   - Linting (ruff, pylint)
   - Type checking (mypy)
   - Unit test runner (pytest)

b) **GitHub Actions Workflow:**
   - Trigger: Push to main, PR creation
   - Jobs: lint, test, build, deploy
   - Matrix testing: Python 3.11, 3.12, 3.13
   - Artifact storage: test reports, coverage

c) **Continuous Testing:**
   - Unit tests (pytest)
   - Integration tests (pytest-asyncio)
   - Performance regression tests
   - Memory leak detection (tracemalloc)

d) **Deployment Automation:**
   - Environment validation
   - Dependency installation (pip install -r requirements.txt)
   - Database migrations (if applicable)
   - Service restart (systemd, supervisor)

**Provide:** Complete GitHub Actions YAML workflow file

**3. MONITORING & LOGGING (Priority: HIGH)**

Design observability stack:

a) **Prometheus Metrics:**
   - Backtest throughput (bars/sec)
   - Data loading latency (ms)
   - Connection pool usage (%)
   - Memory consumption (MB)
   - CPU utilization (%)
   - Error rate (errors/min)

b) **Grafana Dashboards:**
   - System health overview
   - Performance metrics (charts)
   - Error tracking
   - Resource utilization

c) **Structured Logging:**
   - Log format: JSON (timestamp, level, component, message, context)
   - Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
   - Log rotation: daily, max 7 days retention
   - ELK Stack integration (Elasticsearch, Logstash, Kibana)

d) **Alerting Rules:**
   - High error rate (>5 errors/min)
   - Low throughput (<10k bars/sec)
   - High memory usage (>80%)
   - Connection pool saturation (>90%)

**Provide:** Python code for Prometheus instrumentation + Grafana dashboard JSON

**4. PERFORMANCE PROFILING (Priority: MEDIUM)**

Design profiling strategy:

a) **CPU Profiling:**
   - Tools: cProfile, py-spy
   - Metrics: Function call time, hotspots
   - Targets: Vectorized operations, async loops

b) **Memory Profiling:**
   - Tools: memory_profiler, tracemalloc
   - Metrics: Peak memory, allocation trends
   - Targets: DataFrame operations, connection pools

c) **I/O Profiling:**
   - Tools: asyncio debug mode, aiohttp tracing
   - Metrics: Request latency, throughput
   - Targets: File loading, network requests

d) **Profiling Workflow:**
   - Baseline measurement (before optimization)
   - Load testing (simulate production load)
   - Bottleneck identification
   - Optimization iteration
   - Regression testing

**Provide:** Python scripts for automated profiling

**5. DOCUMENTATION (Priority: MEDIUM)**

Create production-ready documentation:

a) **API Documentation:**
   - AsyncDataService API reference
   - BacktestEngine API reference
   - SR/RSI functions API reference
   - Code examples, best practices

b) **Deployment Guide:**
   - Prerequisites (Python, dependencies)
   - Installation steps (venv, pip install)
   - Configuration (environment variables)
   - Service management (start, stop, restart)

c) **Troubleshooting Guide:**
   - Common errors (connection timeout, memory error)
   - Debug commands (logs, metrics)
   - Recovery procedures

d) **Runbook:**
   - Incident response (high error rate, service down)
   - Escalation procedures
   - Contact information

**CONSTRAINTS:**

- Solutions must be Windows-compatible
- Use existing Python 3.13 environment
- Minimize external dependencies
- Focus on actionable, specific recommendations
- Provide code examples (not pseudocode)

**EXPECTED OUTPUT:**

Comprehensive deployment plan with:
1. Risk assessment table (risk, impact, probability, mitigation)
2. Complete GitHub Actions workflow YAML
3. Prometheus instrumentation code
4. Grafana dashboard JSON
5. Profiling scripts
6. Documentation templates

**Estimated Time:** 4-6 hours for full implementation

Generate the complete Phase 3 deployment plan now.
"""
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert DevOps/SRE engineer. Provide comprehensive, production-ready deployment strategies with specific, actionable code examples."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 8000,  # Large response for comprehensive plan
        "return_citations": True,
        "return_images": False
    }
    
    print("\n" + "="*80)
    print("📡 QUERYING PERPLEXITY AI FOR DEPLOYMENT PLAN")
    print("="*80)
    print(f"Model: sonar-pro")
    print(f"Max tokens: 8000")
    print(f"Temperature: 0.2")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nSending request...")
    
    start_time = datetime.now()
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            PERPLEXITY_API_URL,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=180)  # 3 minutes timeout
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Perplexity API error {response.status}: {error_text}")
            
            result = await response.json()
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # Extract response
    content = result["choices"][0]["message"]["content"]
    citations = result.get("citations", [])
    
    print(f"\n✅ Response received in {elapsed:.2f} seconds")
    print(f"📄 Content length: {len(content)} characters")
    print(f"📚 Citations: {len(citations)}")
    
    if citations:
        print("\n📖 Sources:")
        for i, citation in enumerate(citations, 1):
            print(f"   {i}. {citation}")
    
    return {
        "status": "success",
        "content": content,
        "citations": citations,
        "elapsed_seconds": elapsed,
        "timestamp": datetime.now().isoformat()
    }


async def main():
    """Main execution flow."""
    
    print("\n" + "="*80)
    print("🚀 PHASE 3: PRODUCTION DEPLOYMENT - GENERATION SCRIPT")
    print("="*80)
    print("\nWorkflow: Copilot → This Script → Perplexity API → Deployment Plan → Copilot")
    print(f"API Key: {PERPLEXITY_API_KEY[:10]}...{PERPLEXITY_API_KEY[-5:]}")
    
    try:
        # Step 1: Query Perplexity AI
        response = await query_perplexity_for_deployment_plan()
        
        # Step 2: Save deployment plan
        print("\n" + "="*80)
        print("💾 SAVING DEPLOYMENT PLAN")
        print("="*80)
        
        plan_file = Path("PHASE_3_DEPLOYMENT_PLAN.md")
        plan_file.write_text(response["content"], encoding="utf-8")
        
        print(f"\n✅ Deployment plan saved: {plan_file}")
        print(f"   Size: {len(response['content'])} chars")
        print(f"   Lines: {len(response['content'].splitlines())}")
        
        # Step 3: Save metadata report
        report = {
            "phase": "Phase 3: Production Deployment Preparation",
            "generated_at": response["timestamp"],
            "elapsed_seconds": response["elapsed_seconds"],
            "plan_file": str(plan_file),
            "plan_size_chars": len(response["content"]),
            "plan_lines": len(response["content"].splitlines()),
            "perplexity_response": {
                "citations_count": len(response["citations"]),
                "citations": response["citations"]
            },
            "project_context": PROJECT_CONTEXT,
            "next_steps": [
                "1. Review PHASE_3_DEPLOYMENT_PLAN.md",
                "2. Implement Risk Assessment mitigations",
                "3. Set up GitHub Actions CI/CD pipeline",
                "4. Configure Prometheus + Grafana monitoring",
                "5. Run performance profiling",
                "6. Create production documentation",
                "7. Execute deployment checklist"
            ]
        }
        
        report_file = Path("PHASE_3_GENERATION_REPORT.json")
        report_file.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        print(f"\n✅ Report saved: {report_file}")
        
        # Step 4: Summary
        print("\n" + "="*80)
        print("📊 GENERATION SUMMARY")
        print("="*80)
        print(f"Status:           ✅ SUCCESS")
        print(f"Plan file:        {plan_file}")
        print(f"Plan size:        {len(response['content'])} chars")
        print(f"Plan lines:       {len(response['content'].splitlines())}")
        print(f"Citations:        {len(response['citations'])}")
        print(f"Elapsed time:     {response['elapsed_seconds']:.2f}s")
        print(f"Report:           {report_file}")
        
        print("\n" + "="*80)
        print("🎯 PHASE 3 COMPONENTS")
        print("="*80)
        print("1. Risk Assessment (concurrency, memory, performance, data)")
        print("2. CI/CD Pipeline (GitHub Actions workflow)")
        print("3. Monitoring & Logging (Prometheus, Grafana, ELK)")
        print("4. Performance Profiling (CPU, memory, I/O)")
        print("5. Documentation (API docs, deployment guide, runbook)")
        
        print("\n" + "="*80)
        print("⏱️ ESTIMATED IMPLEMENTATION TIME")
        print("="*80)
        print("Total: 4-6 hours")
        print("├── Risk Assessment:     1 hour")
        print("├── CI/CD Setup:         1-2 hours")
        print("├── Monitoring:          1-2 hours")
        print("├── Profiling:           0.5-1 hour")
        print("└── Documentation:       0.5-1 hour")
        
        return report
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(main())
    
    if result:
        print("\n✅ Phase 3 generation complete!")
    else:
        print("\n❌ Phase 3 generation failed!")
