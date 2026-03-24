# Tech Context — Стек и среда

## Backend
- **Python 3.14** (Windows): запуск через `py -3.14`
- **FastAPI** + Uvicorn: `python main.py server` → :8000
- **SQLAlchemy** (async) + SQLite (dev) / PostgreSQL (prod)
- **Redis**: pub/sub и кеш
- **VectorBT**: только внутри optimization pipeline (НЕ для standalone backtests)
- **Numba**: JIT-компиляция numba_engine.py (cache=True, float64!)
- **Optuna**: TPE/CMA-ES оптимизация
- **structlog**: логирование (не print, не bare logger)

## AI Agents
- **DeepSeek** (direct API, не MCP)
- **Qwen** (Alibaba DashScope, direct API)
- **Perplexity** (direct API)
- MCP **отключён**: `FORCE_DIRECT_AGENT_API=1`, `MCP_DISABLED=1`

## Frontend
- Vanilla JS/HTML/CSS — **без build step, без npm**
- ES modules (import/export)
- **Нет React, нет Vue, нет Webpack**
- TradingView Lightweight Charts (для графиков)

## Среда разработки
- **OS**: Windows 11 Home 10.0.26100
- **Shell**: Git Bash через `C:\Program Files\Git\bin\bash.exe`
- **Bash нестабилен** (Cygwin fork errors) → используй Read/Glob/Grep/Edit/Write
- **PYTHONIOENCODING=utf-8**, **PYTHONUTF8=1** (в settings.json)

## Ключевые файлы конфига
| Файл | Назначение |
|------|-----------|
| `.env` | API ключи, DATABASE_URL, REDIS_URL |
| `.env.example` | Шаблон |
| `pyproject.toml` | mypy + ruff конфиг |
| `pytest.ini` | pytest settings |
| `alembic.ini` | Миграции БД |

## Разрешённые Bash-команды (settings.json)
`git *`, `pytest *`, `python main.py *`, `python -m pytest *`, `ruff check *`, `ruff format *`, `alembic *`

## Запрещены
`rm *`, `del *`, `git push --force*`, `git reset --hard*`, `DROP *`, `curl * | bash*`

## Database
- Dev: SQLite (автоматически)
- Prod: PostgreSQL (`DATABASE_URL=postgresql://...`)
- Миграции: Alembic (13 версий в backend/migrations/versions/)
- Agent memory: SQLite (`data/agent_memory.db`)

## Тестирование
- 214 тест-файлов, 10 директорий
- Запуск: `pytest tests/ -x -q`
- НЕ вызывать реальный Bybit API в тестах — только mock
- Coverage targets: engines 95%, metrics 95%, routers 95%, остальное 80%+
