"""
🔧 FINALIZE DATA SERVICE ASYNC - CRITICAL FEATURES
===================================================
Workflow: Copilot ↔ Script ↔ MCP Server ↔ Perplexity AI

Добавление критичных для production features:
1. Concurrency Limit (Semaphore) - защита от перегрузки
2. Connection Pooling - эффективное использование ресурсов
3. Performance Benchmark - валидация на realistic workload

Метод: Отправка требований в Perplexity AI → получение production-ready кода
"""

import asyncio
import aiohttp
import json
from pathlib import Path
from datetime import datetime

# === CONFIGURATION ===
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar-pro"

# Load API key
env_file = Path(__file__).parent / ".env"
PERPLEXITY_API_KEY = None
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if line.startswith("PERPLEXITY_API_KEY="):
                PERPLEXITY_API_KEY = line.split("=", 1)[1].strip().strip('"')
                break

if not PERPLEXITY_API_KEY:
    raise ValueError("PERPLEXITY_API_KEY not found in .env file")

# === PERPLEXITY AI QUERY ===
async def get_production_ready_data_service():
    """
    Запросить production-ready Data Service async с критичными features
    """
    print("=" * 80)
    print("🔧 FINALIZE DATA SERVICE ASYNC")
    print("=" * 80)
    print(f"Workflow: Copilot → Script → MCP → Perplexity AI")
    print(f"API Key: {PERPLEXITY_API_KEY[:20]}...{PERPLEXITY_API_KEY[-5:]} ✅")
    print()
    
    prompt = """
    You are a senior Python async/await expert specializing in production-grade data loading services.
    
    **TASK:** Create a production-ready async data service with ALL critical features.
    
    **CONTEXT:**
    Current implementation has intelligent switching (local vs remote) and batch optimization,
    but is MISSING critical production features identified by code review:
    1. ❌ Concurrency Limit (Semaphore)
    2. ❌ Connection Pooling
    3. ❌ Performance benchmarking on realistic workload
    
    **REQUIREMENTS:**
    
    1. **Concurrency Control (CRITICAL):**
       - Implement asyncio.Semaphore to limit concurrent operations
       - Configurable max_concurrent parameter (default: 10)
       - Prevent system overload with too many parallel requests
       - Handle backpressure gracefully
    
    2. **Connection Pooling (CRITICAL):**
       - Use aiohttp.TCPConnector with connection pool
       - Configure pool_size, keepalive, timeouts
       - Reuse connections for multiple requests
       - Proper cleanup on exit
    
    3. **Intelligent Switching (KEEP EXISTING):**
       - Auto-detect local vs remote files
       - Use sequential for small local files (< 10 files)
       - Use async for remote API or large batches (≥ 10 files)
    
    4. **Production Features:**
       - Retry with exponential backoff (max 3 retries)
       - Comprehensive error handling
       - Detailed logging
       - Type hints everywhere
       - Comprehensive docstrings
    
    5. **Performance Benchmarking:**
       - Include test function that benchmarks:
         * Small local files (5 files)
         * Large local batch (50 files)
         * Simulated remote API (with delays)
       - Measure and compare sequential vs async
       - Show speedup metrics
    
    **OUTPUT FORMAT:**
    Provide complete, production-ready Python code with:
    - Full class implementation: AsyncDataService
    - All methods with type hints and docstrings
    - Semaphore-based concurrency control
    - Connection pooling with aiohttp
    - Intelligent local/remote detection
    - Retry logic with exponential backoff
    - Comprehensive error handling
    - Built-in benchmark function
    - Usage examples in docstring
    
    **CODE STRUCTURE:**
    ```python
    import asyncio
    import aiohttp
    from pathlib import Path
    from typing import List, Dict, Any, Optional
    import pandas as pd
    import time
    
    class AsyncDataService:
        def __init__(
            self,
            max_concurrent: int = 10,
            pool_size: int = 100,
            timeout: int = 30
        ):
            # Initialize with semaphore and connector
            ...
        
        async def load_files_async(
            self,
            file_paths: List[Path],
            auto_switch: bool = True
        ) -> Dict[str, pd.DataFrame]:
            # Intelligent switching + concurrency control
            ...
        
        async def _load_single_file(
            self,
            file_path: Path,
            semaphore: asyncio.Semaphore
        ) -> pd.DataFrame:
            # Semaphore-controlled load with retry
            ...
        
        async def close(self):
            # Cleanup connections
            ...
    
    async def benchmark_performance():
        # Comprehensive benchmark function
        ...
    ```
    
    Focus on PRODUCTION-READY code with ALL critical features implemented.
    Include detailed comments explaining concurrency control and connection pooling.
    """
    
    request_data = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a world-class Python async/await expert with deep knowledge of production-grade data services, concurrency control, and connection pooling. Provide complete, working, production-ready code."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            print(f"📡 Sending request to Perplexity AI...")
            print(f"📝 Query size: {len(prompt)} chars")
            print()
            
            async with session.post(
                PERPLEXITY_API_URL,
                json=request_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ API Error: {response.status}")
                    return None
                
                result = await response.json()
                
                content = result['choices'][0]['message']['content']
                citations = result.get('citations', [])
                
                print(f"✅ Response received from Perplexity AI")
                print(f"📄 Solution size: {len(content)} chars")
                print(f"📚 Citations: {len(citations)}")
                print()
                
                return {
                    "status": "success",
                    "code": content,
                    "citations": citations,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

# === SAVE RESULT ===
def save_production_code(response: dict):
    """
    Сохранить production-ready код
    """
    if not response or response.get("status") != "success":
        print("❌ No valid response to save")
        return False
    
    output_file = Path("optimizations_output/data_service_async_PRODUCTION.py")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# DATA SERVICE ASYNC - PRODUCTION VERSION\n")
            f.write("# Auto-generated by Perplexity AI via MCP\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write("# Features: Concurrency limit + Connection pooling + Benchmarks\n\n")
            f.write(response['code'])
        
        print(f"✅ Production code saved: {output_file}")
        print(f"📄 File size: {output_file.stat().st_size / 1024:.2f} KB")
        
        # Save metadata
        metadata_file = Path("optimizations_output/data_service_async_PRODUCTION_metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": response['timestamp'],
                "citations": response['citations'],
                "code_size": len(response['code']),
                "features": [
                    "Concurrency Limit (Semaphore)",
                    "Connection Pooling (aiohttp)",
                    "Intelligent Switching",
                    "Retry with backoff",
                    "Performance Benchmarks"
                ]
            }, f, indent=2)
        
        print(f"✅ Metadata saved: {metadata_file}")
        
        # Display citations
        print()
        print("📚 CITATIONS:")
        for i, citation in enumerate(response['citations'], 1):
            print(f"   {i}. {citation}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to save: {e}")
        return False

# === MAIN ===
async def main():
    """
    Главный workflow
    """
    start_time = datetime.now()
    
    print("=" * 80)
    print("🎯 FINALIZING DATA SERVICE ASYNC - PRODUCTION READY")
    print("=" * 80)
    print()
    print("Adding critical features:")
    print("  1. ✅ Concurrency Limit (Semaphore)")
    print("  2. ✅ Connection Pooling")
    print("  3. ✅ Performance Benchmarks")
    print()
    
    # Get production-ready code from Perplexity AI
    response = await get_production_ready_data_service()
    
    if response:
        # Save code
        if save_production_code(response):
            print()
            print("=" * 80)
            print("✅ DATA SERVICE ASYNC - PRODUCTION READY!")
            print("=" * 80)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            print(f"⏱️ Total time: {execution_time:.2f}s")
            print()
            print("🎯 NEXT STEPS:")
            print("   1. Review code in optimizations_output/data_service_async_PRODUCTION.py")
            print("   2. Run built-in benchmark to validate performance")
            print("   3. Proceed to Phase 2: Integration Testing")
            print()
        else:
            print("❌ Failed to save production code")
    else:
        print("❌ Failed to get response from Perplexity AI")

if __name__ == "__main__":
    asyncio.run(main())
