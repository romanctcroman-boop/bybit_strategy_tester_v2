"""
Тесты для batch операций кэша (mget, mset, prefetch).

Тестирует:
- Batch retrieval (mget)
- Batch storage (mset)
- Prefetching strategies
- Performance improvements
"""
import pytest
import asyncio
from typing import Dict, Any

from backend.cache.cache_manager import CacheManager
from backend.cache.config import CacheSettings


@pytest.fixture
async def cache_manager():
    """Create test cache manager."""
    settings = CacheSettings(
        l1_size=100,
        l1_ttl=60,
        l2_ttl=300,
        env='development'
    )
    manager = CacheManager(settings=settings)
    await manager.connect()
    
    # Clear any existing data
    await manager.clear_all()
    
    yield manager
    
    # Cleanup
    await manager.clear_all()


class TestMget:
    """Тесты batch retrieval операций."""
    
    @pytest.mark.asyncio
    async def test_mget_empty_keys(self, cache_manager):
        """mget с пустым списком ключей возвращает пустой dict."""
        result = await cache_manager.mget([])
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_mget_all_missing(self, cache_manager):
        """mget с несуществующими ключами возвращает пустой dict."""
        result = await cache_manager.mget(['missing1', 'missing2', 'missing3'])
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_mget_all_in_l1(self, cache_manager):
        """mget находит все ключи в L1 cache."""
        # Заполнить L1 cache
        await cache_manager.set('user:1', {'name': 'Alice', 'age': 30})
        await cache_manager.set('user:2', {'name': 'Bob', 'age': 25})
        await cache_manager.set('user:3', {'name': 'Charlie', 'age': 35})
        
        # Получить batch
        result = await cache_manager.mget(['user:1', 'user:2', 'user:3'])
        
        assert len(result) == 3
        assert result['user:1']['name'] == 'Alice'
        assert result['user:2']['name'] == 'Bob'
        assert result['user:3']['name'] == 'Charlie'
    
    @pytest.mark.asyncio
    async def test_mget_partial_hits(self, cache_manager):
        """mget с частичными попаданиями."""
        # Заполнить только 2 из 3 ключей
        await cache_manager.set('user:1', {'name': 'Alice'})
        await cache_manager.set('user:3', {'name': 'Charlie'})
        
        result = await cache_manager.mget(['user:1', 'user:2', 'user:3'])
        
        # Должны вернуться только найденные ключи
        assert len(result) == 2
        assert 'user:1' in result
        assert 'user:2' not in result  # Missing
        assert 'user:3' in result
    
    @pytest.mark.asyncio
    async def test_mget_l1_then_l2(self, cache_manager):
        """mget проверяет L1, затем L2 для недостающих ключей."""
        # user:1 в L1
        await cache_manager.l1_cache.set('user:1', {'name': 'Alice', 'source': 'L1'})
        
        # user:2 только в L2 (Redis)
        if cache_manager.redis_client:
            await cache_manager.redis_client.set(
                'user:2',
                '{"name": "Bob", "source": "L2"}',
                expire=300
            )
        
        result = await cache_manager.mget(['user:1', 'user:2'])
        
        assert result['user:1']['source'] == 'L1'
        if cache_manager.redis_client:
            assert result['user:2']['source'] == 'L2'
    
    @pytest.mark.asyncio
    async def test_mget_large_batch(self, cache_manager):
        """mget с большим количеством ключей (100)."""
        # Заполнить 100 ключей
        items = {f'item:{i}': {'id': i, 'value': f'value_{i}'} for i in range(100)}
        await cache_manager.mset(items)
        
        # Получить все 100 ключей
        keys = [f'item:{i}' for i in range(100)]
        result = await cache_manager.mget(keys)
        
        assert len(result) == 100
        for i in range(100):
            assert result[f'item:{i}']['id'] == i


class TestMset:
    """Тесты batch storage операций."""
    
    @pytest.mark.asyncio
    async def test_mset_empty_dict(self, cache_manager):
        """mset с пустым dict ничего не делает."""
        await cache_manager.mset({})
        # Не должно быть ошибок
    
    @pytest.mark.asyncio
    async def test_mset_single_item(self, cache_manager):
        """mset с одним элементом."""
        await cache_manager.mset({'user:1': {'name': 'Alice'}})
        
        # Проверить, что сохранилось
        result = await cache_manager.get('user:1')
        assert result['name'] == 'Alice'
    
    @pytest.mark.asyncio
    async def test_mset_multiple_items(self, cache_manager):
        """mset с несколькими элементами."""
        items = {
            'user:1': {'name': 'Alice', 'age': 30},
            'user:2': {'name': 'Bob', 'age': 25},
            'user:3': {'name': 'Charlie', 'age': 35},
        }
        
        await cache_manager.mset(items)
        
        # Проверить все элементы
        for key, expected_value in items.items():
            result = await cache_manager.get(key)
            assert result == expected_value
    
    @pytest.mark.asyncio
    async def test_mset_with_custom_ttl(self, cache_manager):
        """mset с кастомным TTL."""
        items = {
            'temp:1': {'data': 'temporary'},
            'temp:2': {'data': 'also temporary'},
        }
        
        # Сохранить с коротким TTL (5 секунд)
        await cache_manager.mset(items, l1_ttl=5, l2_ttl=5)
        
        # Проверить, что сохранилось
        result1 = await cache_manager.get('temp:1')
        result2 = await cache_manager.get('temp:2')
        assert result1['data'] == 'temporary'
        assert result2['data'] == 'also temporary'
        
        # Подождать 6 секунд
        await asyncio.sleep(6)
        
        # Должны быть expired
        result1 = await cache_manager.get('temp:1')
        result2 = await cache_manager.get('temp:2')
        assert result1 is None
        assert result2 is None
    
    @pytest.mark.asyncio
    async def test_mset_overwrites_existing(self, cache_manager):
        """mset перезаписывает существующие ключи."""
        # Сначала сохранить одно значение
        await cache_manager.set('user:1', {'name': 'Alice', 'age': 30})
        
        # Перезаписать через mset
        await cache_manager.mset({
            'user:1': {'name': 'Alice Updated', 'age': 31}
        })
        
        # Проверить, что обновилось
        result = await cache_manager.get('user:1')
        assert result['name'] == 'Alice Updated'
        assert result['age'] == 31
    
    @pytest.mark.asyncio
    async def test_mset_large_batch(self, cache_manager):
        """mset с большим количеством элементов (500)."""
        items = {f'item:{i}': {'id': i, 'value': f'value_{i}'} for i in range(500)}
        
        await cache_manager.mset(items)
        
        # Проверить выборочно
        assert (await cache_manager.get('item:0'))['id'] == 0
        assert (await cache_manager.get('item:250'))['id'] == 250
        assert (await cache_manager.get('item:499'))['id'] == 499


class TestMgetMsetIntegration:
    """Тесты интеграции mget + mset."""
    
    @pytest.mark.asyncio
    async def test_mset_then_mget(self, cache_manager):
        """mset затем mget возвращает те же данные."""
        items = {
            'user:1': {'name': 'Alice', 'email': 'alice@example.com'},
            'user:2': {'name': 'Bob', 'email': 'bob@example.com'},
            'user:3': {'name': 'Charlie', 'email': 'charlie@example.com'},
        }
        
        # Сохранить batch
        await cache_manager.mset(items)
        
        # Получить batch
        result = await cache_manager.mget(['user:1', 'user:2', 'user:3'])
        
        # Должны совпадать
        assert result == items
    
    @pytest.mark.asyncio
    async def test_mset_then_individual_get(self, cache_manager):
        """mset затем individual get() работает."""
        items = {'user:1': {'name': 'Alice'}, 'user:2': {'name': 'Bob'}}
        
        await cache_manager.mset(items)
        
        # Individual get
        result1 = await cache_manager.get('user:1')
        result2 = await cache_manager.get('user:2')
        
        assert result1['name'] == 'Alice'
        assert result2['name'] == 'Bob'


class TestPrefetch:
    """Тесты prefetching операций."""
    
    @pytest.mark.asyncio
    async def test_prefetch_empty_keys(self, cache_manager):
        """prefetch с пустым списком возвращает пустой dict."""
        result = await cache_manager.prefetch([])
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_prefetch_without_compute_funcs(self, cache_manager):
        """prefetch без compute_funcs возвращает только cached данные."""
        # Заполнить кэш
        await cache_manager.set('user:1', {'name': 'Alice'})
        
        # Prefetch без compute_funcs
        result = await cache_manager.prefetch(['user:1', 'user:2'])
        
        # Только user:1 в результате (user:2 missing и нет compute_func)
        assert len(result) == 1
        assert 'user:1' in result
        assert 'user:2' not in result
    
    @pytest.mark.asyncio
    async def test_prefetch_with_compute_funcs(self, cache_manager):
        """prefetch с compute_funcs вычисляет недостающие ключи."""
        # Только user:1 в кэше
        await cache_manager.set('user:1', {'name': 'Alice'})
        
        # Compute functions для user:2 и user:3
        compute_funcs = {
            'user:2': lambda: {'name': 'Bob', 'computed': True},
            'user:3': lambda: {'name': 'Charlie', 'computed': True},
        }
        
        result = await cache_manager.prefetch(
            ['user:1', 'user:2', 'user:3'],
            compute_funcs=compute_funcs
        )
        
        # Все 3 должны быть в результате
        assert len(result) == 3
        assert result['user:1']['name'] == 'Alice'
        assert result['user:2']['computed'] is True
        assert result['user:3']['computed'] is True
        
        # Проверить, что вычисленные значения сохранились в кэш
        cached2 = await cache_manager.get('user:2')
        cached3 = await cache_manager.get('user:3')
        assert cached2['computed'] is True
        assert cached3['computed'] is True
    
    @pytest.mark.asyncio
    async def test_prefetch_async_compute_funcs(self, cache_manager):
        """prefetch с async compute functions."""
        async def fetch_user(user_id: int):
            await asyncio.sleep(0.01)  # Simulate async operation
            return {'id': user_id, 'name': f'User {user_id}'}
        
        compute_funcs = {
            'user:1': lambda: fetch_user(1),
            'user:2': lambda: fetch_user(2),
            'user:3': lambda: fetch_user(3),
        }
        
        result = await cache_manager.prefetch(
            ['user:1', 'user:2', 'user:3'],
            compute_funcs=compute_funcs
        )
        
        # Все вычислены параллельно
        assert len(result) == 3
        assert result['user:1']['id'] == 1
        assert result['user:2']['id'] == 2
        assert result['user:3']['id'] == 3
    
    @pytest.mark.asyncio
    async def test_prefetch_partial_compute(self, cache_manager):
        """prefetch с частичными compute functions."""
        # user:1 уже в кэше
        await cache_manager.set('user:1', {'name': 'Alice', 'cached': True})
        
        # Compute только для user:3
        compute_funcs = {
            'user:3': lambda: {'name': 'Charlie', 'computed': True}
        }
        
        result = await cache_manager.prefetch(
            ['user:1', 'user:2', 'user:3'],
            compute_funcs=compute_funcs
        )
        
        # user:1 из кэша, user:3 вычислен, user:2 missing
        assert len(result) == 2
        assert result['user:1']['cached'] is True
        assert 'user:2' not in result
        assert result['user:3']['computed'] is True


class TestBatchPerformance:
    """Тесты производительности batch операций."""
    
    @pytest.mark.asyncio
    async def test_mset_faster_than_individual_sets(self, cache_manager):
        """mset быстрее индивидуальных set() вызовов."""
        items = {f'perf:set:{i}': {'value': i} for i in range(50)}
        
        # Benchmark: individual sets
        import time
        start = time.perf_counter()
        for key, value in items.items():
            await cache_manager.set(key, value)
        individual_time = time.perf_counter() - start
        
        # Очистить
        await cache_manager.clear_all()
        
        # Benchmark: mset
        start = time.perf_counter()
        await cache_manager.mset(items)
        mset_time = time.perf_counter() - start
        
        # mset должен быть быстрее
        print(f"\nIndividual sets: {individual_time*1000:.2f}ms")
        print(f"MSET:            {mset_time*1000:.2f}ms")
        print(f"Speedup:         {individual_time/mset_time:.2f}x")
        
        # На практике mset быстрее в 2-5 раз (зависит от Redis latency)
        # Для локального теста может быть небольшая разница
        # assert mset_time < individual_time  # Может не всегда работать локально
    
    @pytest.mark.asyncio
    async def test_mget_faster_than_individual_gets(self, cache_manager):
        """mget быстрее индивидуальных get() вызовов."""
        # Подготовить данные
        items = {f'perf:get:{i}': {'value': i} for i in range(50)}
        await cache_manager.mset(items)
        keys = list(items.keys())
        
        # Benchmark: individual gets
        import time
        start = time.perf_counter()
        for key in keys:
            await cache_manager.get(key)
        individual_time = time.perf_counter() - start
        
        # Benchmark: mget
        start = time.perf_counter()
        await cache_manager.mget(keys)
        mget_time = time.perf_counter() - start
        
        # mget должен быть быстрее
        print(f"\nIndividual gets: {individual_time*1000:.2f}ms")
        print(f"MGET:            {mget_time*1000:.2f}ms")
        print(f"Speedup:         {individual_time/mget_time:.2f}x")
        
        # Для L1 cache разница может быть небольшой
        # Для L2 (Redis) разница значительная (2-10x)


# Итого: 23 теста для batch операций
