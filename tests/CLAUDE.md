# tests/ — Инфраструктура тестирования

## Статистика (as of 2026-02-26)

- **214 test files** across 10 test directories
- **179+ tests passing** (full parity suite + AI agents + E2E)

## conftest.py layout

| File                 | Purpose                                                              |
| -------------------- | -------------------------------------------------------------------- |
| `conftest.py` (root) | Adds project root to `sys.path`; pre-imports `backend` package       |
| `tests/conftest.py`  | Fixes import resolution between `tests/backend/` and real `backend/` |

## Test directories

| Directory                    | Purpose                                                    | Key Tests                                                    |
| ---------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------ |
| `tests/backend/backtesting/` | Core backtesting tests                                     | `test_engine.py`, `test_strategy_builder_parity.py`          |
| `tests/backend/api/`         | API router tests                                           | `test_strategies_crud.py`, `test_strategy_builder.py`        |
| `tests/backend/agents/`      | Agent system tests                                         | 40+ agent tests (memory, pipeline, LLM clients)              |
| `tests/backend/core/`        | Core module tests                                          | `test_metrics_calculator_comprehensive.py`                   |
| `tests/ai_agents/`           | AI agent integration tests                                 | 56+ divergence + agent tests                                 |
| `tests/e2e/`                 | End-to-end tests                                           | `test_strategy_builder_full_flow.py`                         |
| `tests/integration/`         | Integration tests                                          | Postgres upsert, Redis streams, agent collaboration          |
| `tests/advanced_backtesting/`| Advanced backtesting features                              | Engine basic tests                                           |
| `tests/backtesting/`         | Engine-specific tests                                      | GPU, MTF, universal engine tests                             |
| `tests/chaos/`               | Chaos engineering tests                                    | Fault tolerance, failure scenarios                           |
| `tests/frontend/`            | Frontend tests                                             | JavaScript module tests (759/759 passing 2026-03-24)         |
| `tests/load/`                | Load testing                                               | Performance under load                                       |
| `tests/security/`            | Security audit tests                                       | API security, vulnerability scans                            |

## Key fixtures (defined in test files / conftest)

- `sample_ohlcv` — standard OHLCV DataFrame with 100+ bars for indicator/engine tests
- `mock_adapter` — mocked Bybit adapter (never calls real API in unit tests)
- `db_session` — in-memory SQLite session for repository tests
- `backtest_config` — pre-configured `BacktestConfig` with safe defaults

> **Rule:** Never call real Bybit API in unit tests — always mock via `mock_adapter`.

## Правила написания тестов

- **No shell commands in tests** — mock subprocess calls; Bash unreliable on this machine
- `asyncio.run()` — OK; `asyncio.get_event_loop().run_until_complete()` — ЛОМАЕТСЯ в Python 3.13
- Никогда не вызывать реальный Bybit API — только через `mock_adapter`
- Для integration тестов на реальных данных: `tests/integration/test_optimizer_real_data.py`

## Running tests

```bash
# All tests
pytest tests/ -x -q

# Specific test suites
pytest tests/backend/backtesting/test_engine.py -v
pytest tests/backend/backtesting/test_strategy_builder_parity.py -v
pytest tests/ai_agents/test_divergence_block_ai_agents.py -v
pytest tests/e2e/test_strategy_builder_full_flow.py -v

# Agent pipeline tests
pytest tests/test_p1_features.py -v          # 35 тестов
pytest tests/test_p2_features.py -v          # 45 тестов
pytest tests/test_pipeline_streaming_hitl.py -v  # 18 тестов
pytest tests/test_graph_converter.py -v      # 28 тестов

# With coverage
pytest tests/ --cov=backend --cov-report=html
```

## Hook test mapping

`post_edit_tests.py` hook автоматически запускает targeted тесты при редактировании backend файлов:
- Редактирование `backend/backtesting/engine.py` → запускает `tests/backend/backtesting/test_engine.py`
- Маппинг настроен в `.claude/hooks/post_edit_tests.py`
