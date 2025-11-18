"""
Phase 2: Integration Testing - Generator Script
Uses Perplexity AI to generate comprehensive integration test suite

Workflow: Copilot → This Script → Perplexity API → Results → Copilot Analysis
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

# Phase 1 completion context
PHASE_1_CONTEXT = {
    "completed_optimizations": [
        {
            "name": "Backtest Vectorization",
            "file": "optimizations_output/test_vectorized_backtest_FIXED_v2.py",
            "status": "✅ 100% pass rate",
            "performance": "200,000 bars/sec",
            "validation": "Minimum 2 bars required"
        },
        {
            "name": "SR RSI Async",
            "file": "optimizations_output/sr_rsi_async_FIXED_v3.py",
            "status": "✅ 100% pass rate",
            "features": ["Input validation", "Dynamic window sizing", "NaN-safe operations"],
            "edge_cases": ["1 bar", "10 bars", "100 bars", "1000 bars"]
        },
        {
            "name": "Data Service Async",
            "file": "optimizations_output/data_service_async_PRODUCTION_clean.py",
            "status": "✅ Production-ready",
            "features": [
                "Concurrency control (Semaphore, max=10)",
                "Connection pooling (TCPConnector, limit=100)",
                "Intelligent switching (11.09x speedup)",
                "Retry logic (exponential backoff)",
                "Resource cleanup"
            ],
            "benchmarks": {
                "small_local": "11.09x speedup",
                "large_local": "1.04x speedup"
            }
        }
    ],
    "integration_requirements": {
        "end_to_end_flow": "Data Service → Backtest Engine → SR RSI Indicators → Results",
        "concurrency_testing": "Multiple parallel backtests with shared data service",
        "error_scenarios": "Network failures, data corruption, edge cases",
        "performance_thresholds": "≥20% speedup vs sequential baseline"
    }
}


async def query_perplexity_for_integration_tests() -> dict:
    """
    Query Perplexity AI to generate comprehensive integration test suite.
    
    Returns:
        dict: Response containing test suite code, test scenarios, and citations
    """
    
    prompt = f"""
You are an expert Python testing architect specializing in asyncio, pandas, and financial backtesting systems.

**CONTEXT: Phase 1 Completion**
We have completed 3 critical optimizations for a crypto backtesting system:

1. **Backtest Vectorization** (test_vectorized_backtest_FIXED_v2.py)
   - Vectorized numpy operations (200k bars/sec)
   - Minimum 2 bars validation
   - 100% test pass rate

2. **SR RSI Async** (sr_rsi_async_FIXED_v3.py)
   - Async support/resistance + RSI calculation
   - Input validation, dynamic window sizing
   - NaN-safe operations (np.nanmax/nanmin)
   - Edge case handling (1-1000 bars)

3. **Data Service Async** (data_service_async_PRODUCTION_clean.py)
   - asyncio.Semaphore(max_concurrent=10)
   - aiohttp.TCPConnector(limit=100)
   - Intelligent switching (11x speedup for small local files)
   - Exponential backoff retry (max 3 attempts)
   - Proper resource cleanup

**TASK: Generate Phase 2 Integration Test Suite**

Create a comprehensive Python test suite that:

**1. End-to-End Integration Tests**
   - Test complete flow: Data Service loads CSV → Backtest Engine processes → SR RSI indicators calculated → Results validated
   - Verify data integrity through entire pipeline
   - Test with realistic BTCUSDT datasets (1k-10k bars)

**2. Concurrency Integration Tests**
   - Multiple parallel backtests using shared AsyncDataService
   - Verify Semaphore correctly limits concurrent operations
   - Test connection pool efficiency (no leaks, proper reuse)
   - Validate results consistency across parallel runs

**3. Error Handling Integration Tests**
   - Network failure simulation (Data Service async)
   - Data corruption scenarios (missing columns, NaN values)
   - Edge case combinations (1-bar dataset + SR RSI + Backtest)
   - Verify graceful degradation and clear error messages

**4. Performance Integration Tests**
   - Benchmark complete pipeline with/without optimizations
   - Verify ≥20% speedup threshold
   - Memory profiling (connection pool usage)
   - CPU profiling (async efficiency)

**TECHNICAL REQUIREMENTS:**

1. **Test Framework:** Use pytest with pytest-asyncio
2. **File Structure:** Single file `test_phase2_integration.py` with clear test classes
3. **Fixtures:** Create realistic test data (CSV files, DataFrames)
4. **Assertions:** Comprehensive validation of results, performance, error handling
5. **Logging:** Detailed logging for debugging integration issues
6. **Documentation:** Docstrings for each test explaining scenario and expected outcome

**CONSTRAINTS:**

- All 3 optimizations must work together seamlessly
- Tests must be reproducible (use fixed random seeds)
- Mock external dependencies (network, file I/O when needed)
- Performance tests must have realistic thresholds (not flaky)
- Error scenarios must not leave zombie processes/connections

**EXPECTED OUTPUT:**

Provide complete, production-ready Python code for `test_phase2_integration.py` including:
- All necessary imports
- Test fixtures for data generation
- 4 test classes (E2E, Concurrency, Errors, Performance)
- At least 12 comprehensive test methods
- Helper functions for assertions and validation
- Clear comments explaining integration points

Focus on **INTEGRATION** between components, not unit testing individual functions.
Provide executable code ready for pytest execution.

Generate the complete test suite now.
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
                "content": "You are an expert Python testing architect. Provide complete, executable test code with comprehensive integration scenarios."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 8000,  # Large response expected
        "return_citations": True,
        "return_images": False
    }
    
    print("\n" + "="*80)
    print("📡 QUERYING PERPLEXITY AI FOR INTEGRATION TEST SUITE")
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


def extract_python_code(content: str) -> str:
    """
    Extract Python code from markdown wrapper if present.
    
    Args:
        content: Raw content from Perplexity AI
        
    Returns:
        Clean Python code
    """
    lines = content.split('\n')
    code_lines = []
    in_code_block = False
    
    for line in lines:
        if line.strip().startswith('```python'):
            in_code_block = True
            continue
        elif line.strip() == '```' and in_code_block:
            in_code_block = False
            continue
        
        if in_code_block:
            code_lines.append(line)
        elif not line.strip().startswith('```'):
            # Include lines outside code blocks (might be pure code without wrapper)
            code_lines.append(line)
    
    return '\n'.join(code_lines)


async def main():
    """Main execution flow."""
    
    print("\n" + "="*80)
    print("🚀 PHASE 2: INTEGRATION TESTING - GENERATION SCRIPT")
    print("="*80)
    print("\nWorkflow: Copilot → This Script → Perplexity API → Results → Copilot")
    print(f"API Key: {PERPLEXITY_API_KEY[:10]}...{PERPLEXITY_API_KEY[-5:]}")
    
    try:
        # Step 1: Query Perplexity AI
        response = await query_perplexity_for_integration_tests()
        
        # Step 2: Extract clean code
        print("\n" + "="*80)
        print("🔧 EXTRACTING PYTHON CODE")
        print("="*80)
        
        raw_content = response["content"]
        clean_code = extract_python_code(raw_content)
        
        print(f"Raw content: {len(raw_content)} chars")
        print(f"Clean code: {len(clean_code)} chars")
        
        # Step 3: Save test suite
        output_dir = Path("tests/integration")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        test_file = output_dir / "test_phase2_integration.py"
        test_file.write_text(clean_code, encoding="utf-8")
        
        print(f"\n✅ Test suite saved: {test_file}")
        print(f"   Size: {len(clean_code)} chars")
        print(f"   Lines: {len(clean_code.splitlines())}")
        
        # Step 4: Save metadata report
        report = {
            "phase": "Phase 2: Integration Testing",
            "generated_at": response["timestamp"],
            "elapsed_seconds": response["elapsed_seconds"],
            "test_file": str(test_file),
            "test_file_size_chars": len(clean_code),
            "test_file_lines": len(clean_code.splitlines()),
            "perplexity_response": {
                "content_length": len(raw_content),
                "citations_count": len(response["citations"]),
                "citations": response["citations"]
            },
            "phase_1_context": PHASE_1_CONTEXT,
            "next_steps": [
                "1. Review generated test suite",
                "2. Install pytest-asyncio: pip install pytest-asyncio",
                "3. Run tests: pytest tests/integration/test_phase2_integration.py -v",
                "4. Analyze results and fix any integration issues",
                "5. Generate Phase 2 completion report"
            ]
        }
        
        report_file = Path("PHASE_2_GENERATION_REPORT.json")
        report_file.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        print(f"\n✅ Report saved: {report_file}")
        
        # Step 5: Summary
        print("\n" + "="*80)
        print("📊 GENERATION SUMMARY")
        print("="*80)
        print(f"Status:           ✅ SUCCESS")
        print(f"Test suite:       {test_file}")
        print(f"Code size:        {len(clean_code)} chars")
        print(f"Code lines:       {len(clean_code.splitlines())}")
        print(f"Citations:        {len(response['citations'])}")
        print(f"Elapsed time:     {response['elapsed_seconds']:.2f}s")
        print(f"Report:           {report_file}")
        
        print("\n" + "="*80)
        print("🎯 NEXT STEPS")
        print("="*80)
        print("1. Review generated test suite")
        print("2. Install pytest-asyncio if needed:")
        print("   pip install pytest-asyncio")
        print("3. Run integration tests:")
        print(f"   pytest {test_file} -v")
        print("4. Analyze results and iterate if needed")
        
        return report
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(main())
    
    if result:
        print("\n✅ Phase 2 generation complete!")
    else:
        print("\n❌ Phase 2 generation failed!")
