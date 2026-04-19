# Redis Cache Integration Guide

**Версия:** 1.0  
**Дата:** 2026-03-03  
**Статус:** ✅ Production Ready

---

## 📊 Обзор

Redis-backed distributed cache для AI prompt system с automatic fallback to in-memory cache.

### Features:

- ✅ **Distributed caching** — Redis backend
- ✅ **Automatic fallback** — In-memory if Redis unavailable
- ✅ **LRU eviction** — Redis native
- ✅ **TTL expiration** — Automatic key expiration
- ✅ **Connection pooling** — Efficient connections
- ✅ **JSON serialization** — Automatic (de)serialization
- ✅ **Unicode support** — Full UTF-8 support

---

## 🚀 Quick Start

### Basic Usage

```python
from backend.monitoring.redis_cache import RedisContextCache

# Create cache (auto-connects to Redis)
cache = RedisContextCache()

# Set value
cache.set("market:BTCUSDT:15m", {"regime": "trending"}, ttl=300)

# Get value
data = cache.get("market:BTCUSDT:15m")
print(data)  # {"regime": "trending"}

# Get stats
stats = cache.get_stats()
print(f"Backend: {stats['backend']}")
print(f"Hit rate: {stats['hit_rate']:.0%}")
```

### Configuration

```python
from backend.monitoring.redis_cache import RedisCacheConfig

config = RedisCacheConfig(
    host="redis.example.com",
    port=6379,
    db=0,
    password="secret",
    default_ttl=300,
    prefix="prompts:",
    enabled=True,
    fallback_to_memory=True,
)

cache = RedisContextCache(config)
```

---

## 📡 Environment Variables

Configure via environment:

```ini
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password
REDIS_ENABLED=true
REDIS_FALLBACK=true
```

### Initialize from Environment

```python
from backend.monitoring.redis_cache import init_redis_cache_from_env

cache = init_redis_cache_from_env()
```

---

## 🔧 API Reference

### RedisContextCache

#### `__init__(config: RedisCacheConfig | None = None)`

Initialize Redis cache.

**Args:**
- `config`: Redis configuration (optional)

**Example:**
```python
cache = RedisContextCache()
```

---

#### `set(key: str, value: Any, ttl: int | None = None) -> bool`

Set value in cache.

**Args:**
- `key`: Cache key
- `value`: Value to cache (any JSON-serializable type)
- `ttl`: Time to live in seconds (default: config.default_ttl)

**Returns:**
- `True` if successful

**Example:**
```python
cache.set("key", {"data": "value"}, ttl=600)
```

---

#### `get(key: str) -> Any | None`

Get value from cache.

**Args:**
- `key`: Cache key

**Returns:**
- Cached value or `None`

**Example:**
```python
data = cache.get("key")
```

---

#### `delete(key: str) -> bool`

Delete key from cache.

**Args:**
- `key`: Cache key

**Returns:**
- `True` if deleted

**Example:**
```python
cache.delete("key")
```

---

#### `exists(key: str) -> bool`

Check if key exists.

**Args:**
- `key`: Cache key

**Returns:**
- `True` if exists

**Example:**
```python
if cache.exists("key"):
    data = cache.get("key")
```

---

#### `clear() -> int`

Clear all keys with prefix.

**Returns:**
- Number of keys deleted

**Example:**
```python
deleted = cache.clear()
print(f"Cleared {deleted} keys")
```

---

#### `get_stats() -> dict[str, Any]`

Get cache statistics.

**Returns:**
- Statistics dict

**Example:**
```python
stats = cache.get_stats()
print(f"Backend: {stats['backend']}")
print(f"Size: {stats['size']}")
print(f"Hit rate: {stats['hit_rate']:.0%}")
```

**Response:**
```json
{
  "backend": "redis",
  "connected": true,
  "size": 42,
  "used_memory_mb": 1.5,
  "hits": 100,
  "misses": 10,
  "hit_rate": 0.91,
  "prefix": "prompts:",
  "default_ttl": 300
}
```

---

#### `is_using_fallback() -> bool`

Check if using in-memory fallback.

**Returns:**
- `True` if using fallback

**Example:**
```python
if cache.is_using_fallback():
    print("Redis unavailable, using memory")
```

---

#### `reconnect() -> bool`

Attempt to reconnect to Redis.

**Returns:**
- `True` if reconnected

**Example:**
```python
if cache.is_using_fallback():
    success = cache.reconnect()
    if success:
        print("Reconnected to Redis!")
```

---

## 🔄 Fallback Behavior

### Automatic Fallback

If Redis is unavailable, automatically falls back to in-memory cache:

```python
cache = RedisContextCache()

# If Redis connection fails:
# - Logs warning
# - Switches to in-memory fallback
# - Continues working normally

if cache.is_using_fallback():
    # Using in-memory cache
    pass
```

### Fallback Scenarios:

1. **Redis package not installed** → In-memory
2. **Redis server unavailable** → In-memory
3. **Connection timeout** → In-memory
4. **Redis disabled in config** → In-memory

---

## 📊 Integration with ContextCache

### Use Redis with ContextCache

```python
from backend.agents.prompts.context_cache import ContextCache

# Enable Redis
cache = ContextCache(
    max_size=1000,
    default_ttl=300,
    use_redis=True,  # Enable Redis
)

# Works same as before, but uses Redis backend
key = cache.set({"symbol": "BTCUSDT", "regime": "trending"})
data = cache.get(key)
```

### Hybrid Mode

Redis + In-memory (Redis first, memory fallback):

```python
cache = ContextCache(
    use_redis=True,
    redis_config={
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "default_ttl": 300,
    }
)
```

---

## 🧪 Testing

### Run Tests

```bash
pytest tests/monitoring/test_redis_cache.py -v
```

### Test Fixtures

```python
@pytest.fixture
def cache():
    return RedisContextCache(RedisCacheConfig(db=1))  # Use DB 1 for tests

@pytest.fixture(autouse=True)
def cleanup(cache):
    yield
    cache.clear()  # Clean up after each test
```

---

## 🎯 Best Practices

### 1. Use Meaningful Keys

```python
# ✅ Good
cache.set("market:BTCUSDT:15m", data)
cache.set("prompt:strategy:qwen:12345", data)

# ❌ Bad
cache.set("key1", data)
cache.set("test", data)
```

### 2. Set Appropriate TTL

```python
# Short-lived data
cache.set("temp:data", data, ttl=60)

# Long-lived data
cache.set("config:indicators", data, ttl=3600)

# Default TTL
cache.set("default:data", data)  # Uses config.default_ttl
```

### 3. Monitor Hit Rate

```python
stats = cache.get_stats()
hit_rate = stats["hit_rate"]

if hit_rate < 0.5:
    print("Low hit rate, consider increasing TTL or cache size")
```

### 4. Handle Fallback Gracefully

```python
cache = RedisContextCache()

if cache.is_using_fallback():
    logger.warning("Using in-memory fallback, Redis unavailable")
```

---

## 🐛 Troubleshooting

### Problem: Redis connection failed

**Solution:**
```python
# Check Redis is running
redis-cli ping  # Should return PONG

# Check configuration
config = RedisCacheConfig(
    host="localhost",  # Correct host
    port=6379,         # Correct port
    password="secret", # Correct password (if set)
)
cache = RedisContextCache(config)
```

### Problem: High memory usage

**Solution:**
```python
# Reduce max_size
cache = ContextCache(max_size=500)  # Default: 1000

# Reduce TTL
cache.set("key", data, ttl=60)  # Default: 300

# Clear old keys
cache.clear()
```

### Problem: Keys not expiring

**Solution:**
```python
# Check TTL is set
cache.set("key", data, ttl=300)

# Redis should auto-expire, but you can manually delete
cache.delete("key")
```

---

## 📚 Additional Resources

- [Redis Documentation](https://redis.io/documentation)
- [Redis Python Client](https://redis-py.readthedocs.io/)
- [ContextCache Guide](../prompts/CONTEXT_CACHE.md)

---

**Redis cache integration ready for production!** 🚀
