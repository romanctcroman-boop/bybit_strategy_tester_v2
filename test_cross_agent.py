"""
🔄 Cross-Agent Testing: DeepSeek Agent ↔ Perplexity Agent
Multi-threaded performance and integration test

Цели теста:
1. Проверить взаимодействие между агентами
2. Оценить производительность при параллельных запросах
3. Протестировать кэширование и ротацию ключей
4. Сравнить скорость ответов
5. Проверить надёжность при нагрузке
"""

import asyncio
import time
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import statistics
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add paths
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from api.providers.perplexity import PerplexityProvider

# Try to import DeepSeek Agent
try:
    from services.deepseek_agent import DeepSeekAgent
    DEEPSEEK_AVAILABLE = True
except ImportError:
    DEEPSEEK_AVAILABLE = False
    DeepSeekAgent = None
    print("⚠️  DeepSeek Agent not available, will skip DeepSeek tests")


class CrossAgentTester:
    """
    Перекрёстный тестер для DeepSeek и Perplexity агентов
    """
    
    def __init__(self, use_real_keys=False):
        # Load real API key from environment if requested
        if use_real_keys:
            # Load all Perplexity API keys (multi-key rotation)
            perplexity_keys = []
            for i in range(1, 5):  # 4 keys
                key = os.getenv(f"PERPLEXITY_API_KEY_{i}")
                if key:
                    perplexity_keys.append(key)
                    print(f"✅ Loaded Perplexity API key #{i}: {key[:10]}...")
            
            if not perplexity_keys:
                # Fallback to single key
                single_key = os.getenv("PERPLEXITY_API_KEY")
                if single_key:
                    perplexity_keys = [single_key]
                    print(f"✅ Using single Perplexity API key: {single_key[:10]}...")
                else:
                    print("⚠️  PERPLEXITY_API_KEY not found in .env, using test keys")
                    perplexity_keys = ["test_key_1", "test_key_2", "test_key_3"]
        else:
            perplexity_keys = ["test_key_1", "test_key_2", "test_key_3"]
        
        self.perplexity = PerplexityProvider(
            api_keys=perplexity_keys,
            enable_exponential_backoff=True
        )
        
        if DEEPSEEK_AVAILABLE:
            try:
                self.deepseek = DeepSeekAgent()
            except Exception as e:
                print(f"⚠️  Failed to initialize DeepSeek Agent: {e}")
                self.deepseek = None
        else:
            self.deepseek = None
        
        self.results = {
            "perplexity": [],
            "deepseek": [],
            "cross_validation": []
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Форматированный вывод"""
        timestamp = time.strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️",
            "PERF": "📊"
        }.get(level, "•")
        
        print(f"[{timestamp}] {prefix} {message}")
    
    async def test_perplexity_query(self, query: str, test_id: int) -> Dict[str, Any]:
        """Тест одного запроса к Perplexity"""
        start_time = time.time()
        
        try:
            # Используем generate_response (правильный API метод)
            response = await self.perplexity.generate_response(
                query=query,
                model="sonar",
                temperature=0.7,
                max_tokens=1000,
                timeout=30.0
            )
            
            elapsed = time.time() - start_time
            
            # Extract content from response
            content = response.get("content", "") or response.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            result = {
                "test_id": test_id,
                "query": query,
                "success": True,
                "elapsed": elapsed,
                "response_length": len(content),
                "cached": response.get("cached", False),
                "error": None
            }
            
            self.log(
                f"Perplexity #{test_id}: {elapsed:.2f}s, "
                f"len={result['response_length']}, "
                f"cached={result['cached']}",
                "SUCCESS"
            )
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            
            result = {
                "test_id": test_id,
                "query": query,
                "success": False,
                "elapsed": elapsed,
                "response_length": 0,
                "cached": False,
                "error": str(e)
            }
            
            self.log(f"Perplexity #{test_id} failed: {e}", "ERROR")
            return result
    
    async def test_deepseek_query(self, query: str, test_id: int) -> Dict[str, Any]:
        """Тест одного запроса к DeepSeek"""
        
        if not self.deepseek:
            return {
                "test_id": test_id,
                "query": query,
                "success": False,
                "elapsed": 0,
                "response_length": 0,
                "cached": False,
                "error": "DeepSeek Agent not available"
            }
        
        start_time = time.time()
        
        try:
            # DeepSeek Agent может быть синхронным или асинхронным
            # Проверяем наличие метода
            if hasattr(self.deepseek, 'analyze_async'):
                response = await self.deepseek.analyze_async(query)
            else:
                # Fallback на синхронный вызов в executor
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    self.deepseek.analyze,
                    query
                )
            
            elapsed = time.time() - start_time
            
            result = {
                "test_id": test_id,
                "query": query,
                "success": True,
                "elapsed": elapsed,
                "response_length": len(str(response)),
                "cached": False,  # DeepSeek может не иметь кэша
                "error": None
            }
            
            self.log(
                f"DeepSeek #{test_id}: {elapsed:.2f}s, "
                f"len={result['response_length']}",
                "SUCCESS"
            )
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            
            result = {
                "test_id": test_id,
                "query": query,
                "success": False,
                "elapsed": elapsed,
                "response_length": 0,
                "cached": False,
                "error": str(e)
            }
            
            self.log(f"DeepSeek #{test_id} failed: {e}", "ERROR")
            return result
    
    async def test_parallel_queries(self, queries: List[str], agent: str = "both"):
        """
        Параллельное выполнение запросов к одному или обоим агентам
        """
        # Skip DeepSeek if not available
        if agent in ("deepseek", "both") and not self.deepseek:
            self.log(f"⚠️  Skipping DeepSeek tests (agent not available)", "WARNING")
            if agent == "deepseek":
                return 0
            agent = "perplexity"
        
        self.log(f"\n{'='*80}", "INFO")
        self.log(f"🔄 Parallel Test: {agent.upper()}", "INFO")
        self.log(f"Queries: {len(queries)}", "INFO")
        self.log(f"{'='*80}\n", "INFO")
        
        tasks = []
        
        if agent in ("perplexity", "both"):
            for i, query in enumerate(queries):
                tasks.append(("perplexity", i, self.test_perplexity_query(query, i)))
        
        if agent in ("deepseek", "both"):
            for i, query in enumerate(queries):
                tasks.append(("deepseek", i, self.test_deepseek_query(query, i)))
        
        # Выполняем все задачи параллельно
        start_time = time.time()
        
        results = await asyncio.gather(*[task[2] for task in tasks], return_exceptions=True)
        
        total_elapsed = time.time() - start_time
        
        # Группируем результаты
        for (agent_name, test_id, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                self.log(f"{agent_name} #{test_id} exception: {result}", "ERROR")
            else:
                self.results[agent_name].append(result)
        
        self.log(f"\n⏱️  Total parallel execution time: {total_elapsed:.2f}s", "PERF")
        
        return total_elapsed
    
    async def test_cross_validation(self, query: str):
        """
        Перекрёстная валидация: один запрос к обоим агентам
        """
        self.log(f"\n{'='*80}", "INFO")
        self.log(f"🔍 Cross-Validation Test", "INFO")
        self.log(f"Query: {query[:60]}...", "INFO")
        self.log(f"{'='*80}\n", "INFO")
        
        # Запускаем оба агента параллельно
        start_time = time.time()
        
        perplexity_task = self.test_perplexity_query(query, 0)
        deepseek_task = self.test_deepseek_query(query, 0)
        
        perplexity_result, deepseek_result = await asyncio.gather(
            perplexity_task,
            deepseek_task,
            return_exceptions=True
        )
        
        total_elapsed = time.time() - start_time
        
        # Сравниваем результаты
        comparison = {
            "query": query,
            "perplexity": perplexity_result if not isinstance(perplexity_result, Exception) else {"error": str(perplexity_result)},
            "deepseek": deepseek_result if not isinstance(deepseek_result, Exception) else {"error": str(deepseek_result)},
            "total_time": total_elapsed,
            "winner": None
        }
        
        # Определяем "победителя" по скорости
        if (not isinstance(perplexity_result, Exception) and 
            not isinstance(deepseek_result, Exception)):
            
            p_time = perplexity_result.get("elapsed", float('inf'))
            d_time = deepseek_result.get("elapsed", float('inf'))
            
            if p_time < d_time:
                comparison["winner"] = "perplexity"
                time_diff = d_time - p_time
                self.log(f"🏆 Winner: Perplexity (faster by {time_diff:.2f}s)", "SUCCESS")
            else:
                comparison["winner"] = "deepseek"
                time_diff = p_time - d_time
                self.log(f"🏆 Winner: DeepSeek (faster by {time_diff:.2f}s)", "SUCCESS")
        
        self.results["cross_validation"].append(comparison)
        
        return comparison
    
    def print_statistics(self):
        """Вывод статистики по тестам"""
        self.log(f"\n{'='*80}", "INFO")
        self.log(f"📊 STATISTICS SUMMARY", "INFO")
        self.log(f"{'='*80}\n", "INFO")
        
        for agent_name in ["perplexity", "deepseek"]:
            results = self.results[agent_name]
            
            if not results:
                continue
            
            successful = [r for r in results if r["success"]]
            failed = [r for r in results if not r["success"]]
            
            if successful:
                times = [r["elapsed"] for r in successful]
                lengths = [r["response_length"] for r in successful]
                cached_count = sum(1 for r in successful if r.get("cached", False))
                
                self.log(f"\n{agent_name.upper()} Agent:", "INFO")
                self.log(f"  Total requests: {len(results)}", "INFO")
                self.log(f"  Successful: {len(successful)} ({len(successful)/len(results)*100:.1f}%)", "SUCCESS")
                self.log(f"  Failed: {len(failed)} ({len(failed)/len(results)*100:.1f}%)", "ERROR" if failed else "INFO")
                
                if agent_name == "perplexity":
                    self.log(f"  Cache hits: {cached_count} ({cached_count/len(successful)*100:.1f}%)", "INFO")
                
                self.log(f"\n  Response Times:", "PERF")
                self.log(f"    Min: {min(times):.2f}s", "INFO")
                self.log(f"    Max: {max(times):.2f}s", "INFO")
                self.log(f"    Avg: {statistics.mean(times):.2f}s", "INFO")
                self.log(f"    Median: {statistics.median(times):.2f}s", "INFO")
                
                if len(times) > 1:
                    self.log(f"    StdDev: {statistics.stdev(times):.2f}s", "INFO")
                
                self.log(f"\n  Response Lengths:", "PERF")
                self.log(f"    Min: {min(lengths)} chars", "INFO")
                self.log(f"    Max: {max(lengths)} chars", "INFO")
                self.log(f"    Avg: {statistics.mean(lengths):.0f} chars", "INFO")
        
        # Cross-validation stats
        if self.results["cross_validation"]:
            self.log(f"\n\nCROSS-VALIDATION:", "INFO")
            
            perplexity_wins = sum(1 for c in self.results["cross_validation"] if c.get("winner") == "perplexity")
            deepseek_wins = sum(1 for c in self.results["cross_validation"] if c.get("winner") == "deepseek")
            total = len(self.results["cross_validation"])
            
            self.log(f"  Total comparisons: {total}", "INFO")
            self.log(f"  Perplexity wins: {perplexity_wins} ({perplexity_wins/total*100:.1f}%)", "SUCCESS")
            self.log(f"  DeepSeek wins: {deepseek_wins} ({deepseek_wins/total*100:.1f}%)", "SUCCESS")


async def main():
    """
    Основная функция тестирования
    """
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Cross-Agent Testing Framework')
    parser.add_argument('--real-keys', action='store_true', 
                       help='Use real Perplexity API keys from .env')
    parser.add_argument('--extended', action='store_true',
                       help='Run extended stress test (50-100 parallel requests)')
    parser.add_argument('--parallel', type=int, default=10,
                       help='Number of parallel requests for stress test (default: 10)')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🔄 CROSS-AGENT TESTING: DeepSeek ↔ Perplexity")
    print("="*80)
    print(f"Mode: {'🔑 REAL API KEYS' if args.real_keys else '🧪 TEST KEYS'}")
    print(f"Extended: {'✅ YES' if args.extended else '❌ NO'}")
    print(f"Parallel stress test: {args.parallel} requests")
    print("="*80 + "\n")
    
    tester = CrossAgentTester(use_real_keys=args.real_keys)
    
    # Тестовые запросы
    test_queries = [
        "What is quantum computing?",
        "Explain blockchain technology",
        "How does machine learning work?",
        "What are the benefits of cryptocurrency?",
        "Describe neural networks"
    ]
    
    try:
        # Test 1: Параллельные запросы к Perplexity
        tester.log("🎯 TEST 1: Parallel Perplexity Queries", "INFO")
        await tester.test_parallel_queries(test_queries[:3], agent="perplexity")
        await asyncio.sleep(1)  # Небольшая пауза между тестами
        
        # Test 2: Параллельные запросы к DeepSeek
        tester.log("\n🎯 TEST 2: Parallel DeepSeek Queries", "INFO")
        await tester.test_parallel_queries(test_queries[:3], agent="deepseek")
        await asyncio.sleep(1)
        
        # Test 3: Параллельные запросы к обоим агентам
        tester.log("\n🎯 TEST 3: Parallel Both Agents", "INFO")
        await tester.test_parallel_queries(test_queries[:2], agent="both")
        await asyncio.sleep(1)
        
        # Test 4: Перекрёстная валидация (один запрос к обоим)
        tester.log("\n🎯 TEST 4: Cross-Validation", "INFO")
        for query in test_queries[:2]:
            await tester.test_cross_validation(query)
            await asyncio.sleep(0.5)
        
        # Test 5: Stress test
        if args.extended:
            tester.log(f"\n🎯 TEST 5: EXTENDED Stress Test ({args.parallel} parallel)", "INFO")
            stress_queries = test_queries * (args.parallel // len(test_queries) + 1)
            stress_queries = stress_queries[:args.parallel]
        else:
            tester.log(f"\n🎯 TEST 5: Stress Test ({args.parallel} parallel)", "INFO")
            stress_queries = test_queries * (args.parallel // len(test_queries) + 1)
            stress_queries = stress_queries[:args.parallel]
        
        await tester.test_parallel_queries(stress_queries, agent="perplexity")
        
        # Вывод статистики
        tester.print_statistics()
        
        print("\n" + "="*80)
        print("✅ ALL CROSS-AGENT TESTS COMPLETED")
        print("="*80 + "\n")
        
    except Exception as e:
        tester.log(f"\n❌ TEST SUITE FAILED: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
