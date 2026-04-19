# Deprecation Schedule

> Tracks all deprecated components and their planned removal dates.

| Component                    | File                 | Deprecated Since | Removal Target | Replacement                                                      |
| ---------------------------- | -------------------- | ---------------- | -------------- | ---------------------------------------------------------------- |
| `RateLimiter`                | `llm/base_client.py` | 2026-02-10       | 2026-Q2        | `llm.rate_limiter.TokenAwareRateLimiter`                         |
| `APIKeyManager`              | `key_manager.py`     | 2026-02-12       | 2026-Q2        | `api_key_pool.APIKeyPoolManager`                                 |
| `LLMResponse.estimated_cost` | `llm/base_client.py` | 2026-02-12       | 2026-Q3        | `monitoring.cost_tracker.CostTracker.record()`                   |
| `connections.py` re-exports  | `llm/connections.py` | 2026-02-13       | 2026-Q2        | Import from `llm/base_client.py`, `llm/rate_limiter.py` directly |

## Migration Guide

### RateLimiter → TokenAwareRateLimiter

```python
# Before (deprecated)
from backend.agents.llm.base_client import RateLimiter
limiter = RateLimiter(requests_per_minute=60)

# After
from backend.agents.llm.rate_limiter import TokenAwareRateLimiter, TokenBudget
limiter = TokenAwareRateLimiter("deepseek", TokenBudget(max_tokens_per_minute=100_000))
```

### APIKeyManager → APIKeyPoolManager

```python
# Before (deprecated)
from backend.agents.key_manager import APIKeyManager

# After
from backend.agents.api_key_pool import APIKeyPoolManager
```

### connections.py → direct imports

```python
# Before (deprecated)
from backend.agents.llm.connections import BaseLLMClient, LLMResponse

# After
from backend.agents.llm.base_client import BaseLLMClient, LLMResponse
```

---

_Last updated: 2026-02-13_
