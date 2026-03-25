# Test Suite — Bybit Strategy Tester v2

## Directory Structure

```
tests/
├── ai_agents/              # AI agent behaviour tests (56 divergence tests)
│   ├── test_divergence_block_ai_agents.py
│   ├── test_universal_filters_ai_agents.py
│   └── test_universal_filters_b2_ai_agents.py
│
├── backend/
│   ├── agents/             # Agent pipeline unit tests
│   ├── api/
│   │   ├── routers/        # Router-level tests (one file per router)
│   │   │   ├── test_backtests.py           (38 tests)
│   │   │   ├── test_strategy_builder.py    (65 tests)
│   │   │   ├── test_optimizations.py       (54 tests)
│   │   │   ├── test_marketdata.py
│   │   │   ├── test_dashboard_metrics.py
│   │   │   ├── test_health_monitoring.py
│   │   │   └── test_chat_history.py
│   │   └── mcp/            # MCP tool tests
│   ├── backtesting/        # Engine parity & correctness tests
│   │   ├── test_equity_pnl_parity.py
│   │   ├── test_margin_fee_parity.py
│   │   └── test_sltp_leverage_parity.py
│   ├── core/               # Core utilities (metrics, circuit breakers)
│   └── services/           # Service-layer unit tests
│
├── integration/            # End-to-end integration tests (require DB + Redis)
│   ├── test_collaborative_agents.py
│   ├── test_collaborative_agents_live.py  # requires real API keys
│   ├── test_alembic_migration.py
│   ├── test_postgres_upsert.py
│   └── test_redis_streams_live.py
│
├── e2e/                    # Browser/API end-to-end tests
├── security/               # Security hardening tests
├── advanced_backtesting/   # Advanced engine tests
├── backtesting/            # Backtest scenario tests
│
└── test_*.py               # Legacy root-level tests (to be migrated)
```

> **Note:** ~45 `test_*.py` files remain at the root level for backward compatibility.
> New tests should be placed in the appropriate subdirectory above.

---

## Running Tests

### Unit tests (fast, no external deps)
```bash
pytest tests/ -q -m "not live" --ignore=tests/integration
```

### Full test suite (requires PostgreSQL + Redis)
```bash
# Set env vars first
export DATABASE_URL=postgresql://user:pass@localhost:5432/test_db
export REDIS_URL=redis://localhost:6379/0

pytest tests/ -q -m "not live"
```

### With coverage report
```bash
pytest tests/ --cov=backend --cov-report=html --cov-report=term-missing -m "not live"
# Open htmlcov/index.html in browser
```

### Specific test categories
```bash
# AI agent tests
pytest tests/ai_agents/ -v

# Divergence block tests (56 tests)
pytest tests/ai_agents/test_divergence_block_ai_agents.py -v

# Router tests
pytest tests/backend/api/routers/ -v

# Parity tests (engine accuracy)
pytest tests/backend/backtesting/ -v

# Integration tests (requires DB + Redis)
pytest tests/integration/ -v -m "not live"
```

---

## Live API Tests

Some integration tests make **real calls** to external APIs (DeepSeek, Qwen).
They are marked with `@pytest.mark.live` and are **skipped by default** when
API keys are not present.

### Running live tests locally

```bash
# Requires real API keys
DEEPSEEK_API_KEY=sk-... QWEN_API_KEY=sk-... \
  pytest tests/integration/test_collaborative_agents_live.py -v -m live
```

### Skipping live tests (default in CI)
```bash
pytest tests/ -m "not live"
```

### Environment check
The live test files include automatic skip logic:
```python
_DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
_HAS_DEEPSEEK = bool(_DEEPSEEK_KEY) and "YOUR" not in _DEEPSEEK_KEY
# Tests are skipped if key is missing or placeholder
```

---

## Test Markers

| Marker | Description | Run |
|--------|-------------|-----|
| `live` | Requires real API keys | `pytest -m live` |
| `integration` | Requires DB + Redis | `pytest -m integration` |
| `slow` | Long-running tests | `pytest -m slow` |
| `e2e` | Full end-to-end | `pytest -m e2e` |

---

## Critical Constants in Tests

- `commission_rate = 0.0007` — TradingView parity constant; **never change**
- Engine: `FallbackEngineV4` — used in all parity tests
- Test DB: `sqlite:///:memory:` for unit tests; PostgreSQL for integration

---

## conftest.py

Shared fixtures are in `tests/conftest.py`. Sub-directories inherit from it automatically.
Do NOT create duplicate fixtures in sub-directory conftest files.
