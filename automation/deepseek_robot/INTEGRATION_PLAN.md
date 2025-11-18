# 🔧 Integration Plan: Advanced Architecture → Robot.py

## Цель

Интеграция advanced architecture (4-8 API ключей, ML, async, многопоточность) в существующий `robot.py`.

---

## Этапы интеграции

### Phase 1: Подготовка (1-2 часа)

#### 1.1. Установка зависимостей

```bash
pip install numpy scikit-learn httpx aiofiles
```

#### 1.2. Настройка .env

Добавить в `.env`:
```env
# DeepSeek API Keys (минимум 4, максимум 8)
DEEPSEEK_API_KEY_1=your_key_1
DEEPSEEK_API_KEY_2=your_key_2
DEEPSEEK_API_KEY_3=your_key_3
DEEPSEEK_API_KEY_4=your_key_4
DEEPSEEK_API_KEY_5=your_key_5  # Optional
DEEPSEEK_API_KEY_6=your_key_6  # Optional
DEEPSEEK_API_KEY_7=your_key_7  # Optional
DEEPSEEK_API_KEY_8=your_key_8  # Optional

# Cache settings
CACHE_MAX_SIZE=1000
CACHE_TTL_SECONDS=3600
CACHE_DIR=.cache/deepseek

# Performance tuning
MAX_PARALLEL_WORKERS=4  # Увеличить до 8 если 8 ключей
RATE_LIMIT_PER_KEY=60   # requests per minute
```

#### 1.3. Проверка существующего кода

```bash
# Запуск demo для тестирования
python automation/deepseek_robot/demo_advanced_architecture.py
```

**Expected output:**
```
✅ All 6 demos executed successfully!
🚀 Ready for production integration!
```

---

### Phase 2: Интеграция в robot.py (2-3 часа)

#### 2.1. Импорты

**Добавить в начало `robot.py`:**

```python
# Advanced Architecture Components
from automation.deepseek_robot.advanced_architecture import (
    APIKeyPool,
    IntelligentCache,
    ParallelDeepSeekExecutor,
    AdvancedWorkflowOrchestrator,
    MLContextManager,
    ContextSnapshot
)

import numpy as np
from pathlib import Path
```

#### 2.2. Обновление __init__

**Было:**
```python
class DeepSeekAIRobot:
    def __init__(self, config_path: str, base_dir: str):
        self.config = self._load_config(config_path)
        self.base_dir = Path(base_dir)
        self.logger = logging.getLogger(__name__)
```

**Стало:**
```python
class DeepSeekAIRobot:
    def __init__(self, config_path: str, base_dir: str):
        self.config = self._load_config(config_path)
        self.base_dir = Path(base_dir)
        self.logger = logging.getLogger(__name__)
        
        # 🚀 NEW: Advanced Architecture Components
        
        # 1. Load multiple API keys
        self.deepseek_keys = self._load_api_keys()
        
        # 2. Initialize Intelligent Cache with ML
        cache_dir = Path(os.getenv("CACHE_DIR", ".cache/deepseek"))
        self.cache = IntelligentCache(
            max_size=int(os.getenv("CACHE_MAX_SIZE", 1000)),
            ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", 3600)),
            cache_dir=cache_dir
        )
        
        # 3. Initialize Parallel Executor
        self.executor = ParallelDeepSeekExecutor(
            api_keys=self.deepseek_keys,
            cache=self.cache,
            max_workers=int(os.getenv("MAX_PARALLEL_WORKERS", 4))
        )
        
        # 4. Initialize Workflow Orchestrator
        self.orchestrator = AdvancedWorkflowOrchestrator(
            deepseek_keys=self.deepseek_keys,
            perplexity_key=os.getenv("PERPLEXITY_API_KEY"),
            cache_dir=cache_dir
        )
        
        # 5. Load previous context
        self._load_previous_context()
        
        self.logger.info(f"🚀 Advanced Architecture initialized:")
        self.logger.info(f"   • API Keys: {len(self.deepseek_keys)}")
        self.logger.info(f"   • Max Workers: {self.executor.max_workers}")
        self.logger.info(f"   • Cache Size: {self.cache.max_size}")
        self.logger.info(f"   • ML Features: {'Enabled' if self.cache.ml_manager.vectorizer else 'Disabled'}")
    
    def _load_api_keys(self) -> List[str]:
        """Load all DeepSeek API keys from .env"""
        keys = []
        for i in range(1, 9):  # Support up to 8 keys
            key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
            if key:
                keys.append(key)
        
        if not keys:
            raise ValueError("No DeepSeek API keys found in .env!")
        
        self.logger.info(f"✅ Loaded {len(keys)} API keys")
        return keys
    
    def _load_previous_context(self):
        """Load previous context if exists"""
        latest = self.cache.ml_manager.load_latest_context()
        
        if latest:
            self.logger.info(f"✅ Loaded context from {latest.timestamp}")
            self.logger.info(f"   • Files analyzed: {latest.project_state.get('files_analyzed', 0)}")
            self.logger.info(f"   • Quality: {latest.quality_metrics.get('cache_hit_rate', 0):.0%} cache hit rate")
        else:
            self.logger.info("ℹ️  No previous context found (first run)")
```

#### 2.3. Обновление методов анализа

**Было (sequential):**
```python
async def analyze_project(self, max_iterations: int = 5):
    """Analyze project sequentially"""
    for iteration in range(max_iterations):
        issues = await self._scan_for_issues()
        for issue in issues:
            await self._analyze_single_issue(issue)
```

**Стало (parallel):**
```python
async def analyze_project(self, max_iterations: int = 5):
    """Analyze project with parallel execution"""
    for iteration in range(max_iterations):
        self.logger.info(f"🔄 Iteration {iteration + 1}/{max_iterations}")
        
        # 1. Scan for issues
        issues = await self._scan_for_issues()
        self.logger.info(f"   Found {len(issues)} potential issues")
        
        # 2. Prepare batch requests
        requests = [
            {
                "query": f"Analyze issue: {issue['description']}",
                "file": issue.get("file"),
                "line": issue.get("line"),
                "context": issue
            }
            for issue in issues
        ]
        
        # 3. Execute in parallel (4-8x faster!)
        self.logger.info(f"   ⚡ Analyzing {len(requests)} issues in parallel...")
        results = await self.executor.execute_batch(
            requests=requests,
            use_cache=True
        )
        
        # 4. Process results
        cached_count = sum(1 for r in results if r.get("cached"))
        self.logger.info(f"   ✅ Completed: {len(results)} analyses")
        self.logger.info(f"      • Cached: {cached_count} ({cached_count/len(results):.0%})")
        self.logger.info(f"      • New: {len(results) - cached_count}")
        
        # 5. Apply fixes (if needed)
        fixes_applied = 0
        for result in results:
            if result.get("fix_suggested"):
                success = await self._apply_fix(result)
                if success:
                    fixes_applied += 1
        
        self.logger.info(f"   🔧 Applied {fixes_applied} fixes")
        
        # 6. Save context snapshot
        await self._save_context_snapshot(iteration, issues, results)
```

#### 2.4. Добавление метода для full workflow

**Новый метод:**
```python
async def execute_advanced_workflow(self, tasks: List[Dict[str, Any]]):
    """
    Execute full workflow: DeepSeek → Perplexity → DeepSeek → Copilot
    
    Args:
        tasks: List of analysis tasks
        
    Returns:
        Results with all stages
    """
    self.logger.info(f"🚀 Starting advanced workflow")
    self.logger.info(f"   • Tasks: {len(tasks)}")
    self.logger.info(f"   • Pipeline: DeepSeek → Perplexity → DeepSeek → Copilot")
    
    # Execute through orchestrator
    results = await self.orchestrator.execute_workflow(
        tasks=tasks,
        save_context=True
    )
    
    # Log results
    self.logger.info(f"✅ Workflow completed!")
    self.logger.info(f"   • Duration: {results.get('total_duration', 0):.2f}s")
    self.logger.info(f"   • Cache hit rate: {self.cache.get_stats().get('hit_rate')}")
    
    return results
```

#### 2.5. Обновление _scan_for_issues

**Добавить ML semantic search:**

```python
async def _scan_for_issues(self) -> List[Dict[str, Any]]:
    """Scan for issues with semantic deduplication"""
    issues = []
    
    # 1. Run linters (mypy, black, isort)
    raw_issues = await self._run_all_linters()
    
    # 2. Deduplicate using semantic search
    for issue in raw_issues:
        issue_text = f"{issue['file']} {issue['description']}"
        
        # Check if similar issue already processed
        similar = self.cache.find_similar(issue_text, threshold=0.85)
        
        if similar:
            # Found similar cached analysis
            _, cached_result, similarity = similar[0]
            self.logger.info(f"   🔍 Similar issue found (similarity: {similarity:.0%})")
            self.logger.info(f"      Reusing cached analysis")
            issue["cached_analysis"] = cached_result
        
        issues.append(issue)
    
    # 3. Train ML on new issues
    issue_texts = [f"{i['file']} {i['description']}" for i in issues]
    self.cache.ml_manager.fit_on_history(issue_texts)
    
    return issues
```

---

### Phase 3: Тестирование (1-2 часа)

#### 3.1. Unit Tests

**Создать `test_advanced_integration.py`:**

```python
import pytest
import asyncio
from automation.deepseek_robot.robot import DeepSeekAIRobot

@pytest.mark.asyncio
async def test_parallel_execution():
    """Test parallel execution with 4 API keys"""
    robot = DeepSeekAIRobot(
        config_path="config.yaml",
        base_dir="d:/bybit_strategy_tester_v2"
    )
    
    # Create test tasks
    tasks = [
        {"query": f"test query {i}"}
        for i in range(8)
    ]
    
    # Execute in parallel
    results = await robot.executor.execute_batch(tasks)
    
    assert len(results) == 8
    assert all("response" in r for r in results)

@pytest.mark.asyncio
async def test_cache_hit():
    """Test cache hit on second run"""
    robot = DeepSeekAIRobot(
        config_path="config.yaml",
        base_dir="d:/bybit_strategy_tester_v2"
    )
    
    tasks = [{"query": "test cache"}]
    
    # First run (no cache)
    results1 = await robot.executor.execute_batch(tasks)
    assert not results1[0].get("cached")
    
    # Second run (should be cached)
    results2 = await robot.executor.execute_batch(tasks)
    assert results2[0].get("cached")

@pytest.mark.asyncio
async def test_semantic_search():
    """Test semantic search in cache"""
    robot = DeepSeekAIRobot(
        config_path="config.yaml",
        base_dir="d:/bybit_strategy_tester_v2"
    )
    
    # Add to cache
    robot.cache.set("key1", {"result": "test"}, text_for_ml="find bugs in code")
    
    # Search for similar
    similar = robot.cache.find_similar("check code for errors", threshold=0.7)
    
    assert len(similar) > 0
    assert similar[0][2] > 0.7  # Similarity > 70%
```

**Запуск тестов:**
```bash
pytest automation/deepseek_robot/test_advanced_integration.py -v
```

**Expected output:**
```
test_parallel_execution PASSED
test_cache_hit PASSED
test_semantic_search PASSED

3 passed in 2.34s
```

#### 3.2. Integration Test

**Реальный запуск на проекте:**

```bash
python -m automation.deepseek_robot.robot
```

**Ожидаемый вывод:**
```
🚀 Advanced Architecture initialized:
   • API Keys: 4
   • Max Workers: 4
   • Cache Size: 1000
   • ML Features: Enabled

✅ Loaded context from 2025-11-08T10:00:00
   • Files analyzed: 15
   • Quality: 67% cache hit rate

🔄 Iteration 1/5
   Found 12 potential issues
   ⚡ Analyzing 12 issues in parallel...
   ✅ Completed: 12 analyses
      • Cached: 8 (67%)
      • New: 4
   🔧 Applied 10 fixes

...
```

#### 3.3. Performance Benchmark

**Создать `benchmark_advanced.py`:**

```python
import asyncio
import time
from automation.deepseek_robot.robot import DeepSeekAIRobot

async def benchmark_sequential_vs_parallel():
    """Compare sequential vs parallel performance"""
    robot = DeepSeekAIRobot(
        config_path="config.yaml",
        base_dir="d:/bybit_strategy_tester_v2"
    )
    
    # Test data
    tasks = [{"query": f"analyze file_{i}.py"} for i in range(16)]
    
    # Parallel (4 workers)
    start = time.time()
    results = await robot.executor.execute_batch(tasks)
    parallel_time = time.time() - start
    
    # Calculate expected sequential time
    sequential_time = len(tasks) * 10  # Assume 10s per request
    
    print(f"📊 Performance Benchmark:")
    print(f"   Tasks: {len(tasks)}")
    print(f"   Sequential (estimated): {sequential_time:.1f}s")
    print(f"   Parallel (actual): {parallel_time:.1f}s")
    print(f"   Speedup: {sequential_time/parallel_time:.1f}x")
    
    # Cache test
    print(f"\n💾 Cache Test:")
    start = time.time()
    results = await robot.executor.execute_batch(tasks)  # Same tasks
    cached_time = time.time() - start
    
    cached_count = sum(1 for r in results if r.get("cached"))
    print(f"   Cached: {cached_count}/{len(tasks)} ({cached_count/len(tasks):.0%})")
    print(f"   Time: {cached_time:.2f}s")
    print(f"   Speedup vs parallel: {parallel_time/cached_time:.0f}x")
    print(f"   Speedup vs sequential: {sequential_time/cached_time:.0f}x")

if __name__ == "__main__":
    asyncio.run(benchmark_sequential_vs_parallel())
```

**Expected output:**
```
📊 Performance Benchmark:
   Tasks: 16
   Sequential (estimated): 160.0s
   Parallel (actual): 40.2s
   Speedup: 4.0x

💾 Cache Test:
   Cached: 16/16 (100%)
   Time: 0.8s
   Speedup vs parallel: 50x
   Speedup vs sequential: 200x
```

---

### Phase 4: Мониторинг (30 минут)

#### 4.1. Добавление метрик

**Добавить в robot.py:**

```python
def get_advanced_metrics(self) -> Dict[str, Any]:
    """Get advanced architecture metrics"""
    cache_stats = self.cache.get_stats()
    pool_stats = self.executor.key_pool.get_stats()
    
    return {
        "cache": {
            "size": cache_stats.get("size"),
            "max_size": cache_stats.get("max_size"),
            "hit_rate": cache_stats.get("hit_rate"),
            "evictions": cache_stats.get("evictions")
        },
        "api_keys": {
            "total_keys": pool_stats.get("total_keys"),
            "total_requests": pool_stats.get("total_requests"),
            "total_errors": pool_stats.get("total_errors"),
            "requests_per_key": pool_stats.get("total_requests") / pool_stats.get("total_keys")
        },
        "ml": {
            "enabled": cache_stats.get("ml_enabled"),
            "documents_trained": len(self.cache.ml_manager.documents) if hasattr(self.cache.ml_manager, 'documents') else 0
        }
    }
```

#### 4.2. Logging

**Добавить периодический вывод метрик:**

```python
async def analyze_project(self, max_iterations: int = 5):
    # ... existing code ...
    
    # Log metrics every iteration
    metrics = self.get_advanced_metrics()
    self.logger.info(f"\n📊 Metrics:")
    self.logger.info(f"   Cache hit rate: {metrics['cache']['hit_rate']}")
    self.logger.info(f"   API requests: {metrics['api_keys']['total_requests']}")
    self.logger.info(f"   Avg requests per key: {metrics['api_keys']['requests_per_key']:.1f}")
```

---

## Контрольный список

### Перед интеграцией

- [ ] Установлены все зависимости (`numpy`, `scikit-learn`, `httpx`, `aiofiles`)
- [ ] Настроены 4-8 API ключей в `.env`
- [ ] Demo запущена и работает (`demo_advanced_architecture.py`)
- [ ] Существующий `robot.py` работает корректно

### После интеграции

- [ ] `robot.py` обновлён с новыми компонентами
- [ ] Все импорты работают без ошибок
- [ ] Unit tests проходят (`test_advanced_integration.py`)
- [ ] Integration test показывает parallel execution
- [ ] Cache hit rate > 50% на втором запуске
- [ ] Semantic search находит похожие запросы
- [ ] Context сохраняется и загружается корректно
- [ ] Metrics собираются и логируются

### Performance

- [ ] Parallel execution даёт 3-4x speedup (для 4 ключей)
- [ ] Cache даёт 50-200x speedup (для повторных запросов)
- [ ] Semantic search работает с threshold > 0.7
- [ ] API key pool равномерно распределяет запросы
- [ ] Rate limiting соблюдается (60 req/min per key)

---

## Rollback Plan

Если интеграция не работает:

### Option 1: Gradual Rollback

1. Отключить ML features:
   ```python
   cache = IntelligentCache(max_size=100, ttl_seconds=3600)
   # ML автоматически отключится если sklearn не установлен
   ```

2. Уменьшить количество workers:
   ```python
   executor = ParallelDeepSeekExecutor(
       api_keys=[keys[0]],  # Только 1 ключ
       cache=cache,
       max_workers=1  # Sequential
   )
   ```

3. Отключить cache:
   ```python
   results = await executor.execute_batch(requests, use_cache=False)
   ```

### Option 2: Complete Rollback

```bash
# Вернуться к предыдущей версии
git checkout HEAD~1 automation/deepseek_robot/robot.py

# Или использовать backup
cp automation/deepseek_robot/robot.py.backup automation/deepseek_robot/robot.py
```

---

## Ожидаемые результаты

### Производительность

| Метрика | До (Sequential) | После (Parallel) | Улучшение |
|---------|----------------|------------------|-----------|
| 10 файлов (первый запуск) | 100s | 25s | **4x** |
| 10 файлов (второй запуск) | 100s | 0.5s | **200x** |
| Похожий запрос | 10s | 0.1s (semantic) | **100x** |
| Одновременных запросов | 1 | 4-8 | **4-8x** |

### Автономность

- ✅ **Context persistence**: Agent помнит предыдущие анализы
- ✅ **Semantic search**: Находит похожие cached результаты
- ✅ **ML learning**: Автоматически обучается на истории
- ✅ **Failover**: Automatic retry с разными API ключами

### Надёжность

- ✅ **Rate limiting**: Соблюдается на каждом ключе
- ✅ **Load balancing**: Равномерное распределение
- ✅ **Error handling**: Automatic retry
- ✅ **Cache eviction**: ML-based (удаляет наименее полезное)

---

## Следующие шаги

После успешной интеграции:

1. **Phase 5: Perplexity Integration** (1-2 часа)
   - Реализовать реальные API calls к Perplexity
   - Добавить в workflow Stage 2

2. **Phase 6: Copilot Integration** (1 час)
   - Интеграция с VS Code Copilot API
   - Добавить в workflow Stage 4

3. **Phase 7: Advanced ML** (2-3 часа)
   - BERT embeddings вместо TF-IDF
   - Автоматическое обучение на feedback
   - Quality prediction

4. **Phase 8: Production Monitoring** (1-2 часа)
   - Prometheus metrics
   - Grafana dashboard
   - Alerting

---

## 🎯 Итого

**Время интеграции:** 5-8 часов

**Ожидаемый результат:**
- ⚡ **4-8x speedup** для новых запросов
- ⚡ **100-200x speedup** для cached запросов
- 🧠 **Semantic search** для похожих запросов
- 💾 **Context persistence** для автономности
- 📊 **Полная статистика** и мониторинг

**Готово к интеграции!** 🚀
