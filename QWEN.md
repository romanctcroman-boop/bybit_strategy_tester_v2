# Bybit Strategy Tester v2 — Qwen Code Configuration

## TL;DR

- **Purpose**: Professional backtesting and live trading platform for Bybit exchange with AI-powered strategy analysis and GPU acceleration
- **Key invariant**: Commission = 0.0007 (0.07%) — do not change without explicit approval (TradingView parity)
- **Quick start**: `python main.py server` → http://localhost:8000/docs
- **Python**: 3.11+ (3.14 recommended for development)
- **Stack**: FastAPI · SQLite/PostgreSQL · Redis · VectorBT · Numba · CuPy (GPU)

---

## 1. Project Overview

AI-powered cryptocurrency trading strategy backtesting platform with:

- **GPU-accelerated backtesting** (CuPy) — up to 100x faster than CPU
- **166 trading metrics** — full TradingView parity (Sharpe, Sortino, Max DD, etc.)
- **Multi-agent AI system** — DeepSeek, Qwen, Perplexity integration for strategy generation
- **Visual Strategy Builder** — block-based strategy designer (no coding required)
- **Walk-forward optimization** — out-of-sample validation with rolling windows
- **Monte Carlo simulation** — statistical validation with confidence intervals
- **Market regime detection** — automatic trending/ranging/volatile market classification
- **Production-ready** — Docker, Kubernetes, CI/CD, Prometheus monitoring

### Key URLs (when running)

| URL                                           | Description                    |
| --------------------------------------------- | ------------------------------ |
| http://localhost:8000/frontend/dashboard.html | 📊 Trading Dashboard           |
| http://localhost:8000/docs                    | 📚 API Documentation (Swagger) |
| http://localhost:8000/api/v1/health           | 💚 Health Check                |

---

## 2. Environment & Setup

### Prerequisites

- Python 3.11+ (3.12/3.13/3.14 supported; 3.14 recommended for dev)
- CUDA Toolkit 11.8+ (optional, for GPU acceleration)
- Redis (optional, for caching)
- PostgreSQL (optional, for production database)

### Installation

```powershell
# Clone repository
git clone https://github.com/RomanCTC/bybit_strategy_tester_v2.git
cd bybit_strategy_tester_v2

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r backend/requirements.txt

# Optional: GPU support
pip install cupy-cuda11x  # For CUDA 11.x
# or
pip install cupy-cuda12x  # For CUDA 12.x

# Optional: Full dev deps (numba, vectorbt, torch)
pip install .[dev-full]

# Copy environment configuration
Copy-Item .env.example .env
# Edit .env with your API keys
```

### Required Environment Variables

```ini
# Bybit API (required for live data)
BYBIT_API_KEY=your_bybit_api_key
BYBIT_API_SECRET=your_bybit_api_secret

# AI Agents (optional)
DEEPSEEK_API_KEY=sk-your_deepseek_key
QWEN_API_KEY=sk-your_qwen_key
PERPLEXITY_API_KEY=pplx-your_perplexity_key

# Database (default: SQLite)
DATABASE_URL=sqlite:///data/app.sqlite3

# Redis (optional)
REDIS_URL=redis://127.0.0.1:6379/0
```

### Validate Configuration

```powershell
.\scripts\validate_env.ps1
```

---

## 3. Architecture

### Core Data Flow

```
DataService.load_ohlcv(symbol, timeframe, start, end) → pd.DataFrame[OHLCV]
    ↓
Strategy.generate_signals(data) → SignalResult(entries, exits, ...)
    ↓
BacktestEngine.run(data, signals, config) → BacktestResult
    ↓ (commission=0.0007, engine=FallbackEngineV4)
MetricsCalculator.calculate_all(results) → Dict[166 metrics]
    ↓
FastAPI router → JSON response + warnings[]
```

### Key Modules

| Module                   | Path                                              | Responsibility                                    |
| ------------------------ | ------------------------------------------------- | ------------------------------------------------- |
| `BacktestConfig`         | `backend/backtesting/models.py`                   | All backtest parameters (single Pydantic model)   |
| `BacktestEngine`         | `backend/backtesting/engine.py`                   | FallbackEngineV4 — gold standard engine           |
| `StrategyBuilderAdapter` | `backend/backtesting/strategy_builder_adapter.py` | Graph → BaseStrategy (3575 lines)                 |
| `indicator_handlers`     | `backend/backtesting/indicator_handlers.py`       | 40+ indicator handlers (2217 lines)               |
| `MetricsCalculator`      | `backend/core/metrics_calculator.py`              | Single source of truth for 166 metrics            |
| `DataService`            | `backend/services/data_service.py`                | OHLCV loading                                     |
| `UnifiedAgentInterface`  | `backend/agents/unified_agent_interface.py`       | All AI agent calls                                |

### API Entry Points

| Endpoint                         | Router                             | Action                           |
| -------------------------------- | ---------------------------------- | -------------------------------- |
| `POST /api/backtests/`           | `routers/backtests.py`             | Run backtest (built-in strategy) |
| `POST /api/strategy-builder/run` | `routers/strategy_builder.py`      | Run builder strategy             |
| `POST /api/optimizations/`       | `routers/optimizations.py`         | Start optimization               |
| `GET /api/marketdata/ohlcv`      | `routers/marketdata.py`            | Load OHLCV                       |
| `POST /api/ai/generate-strategy` | `routers/ai_strategy_generator.py` | AI strategy generation           |

### Engine Selection

| `engine_type` value                                         | Engine class         | Use case                                    |
| ----------------------------------------------------------- | -------------------- | ------------------------------------------- |
| `"auto"`, `"single"`, `"fallback"`, `"fallback_v4"`, `"v4"` | **FallbackEngineV4** | Default for all single backtests — gold standard |
| `"optimization"`, `"numba"`                                 | NumbaEngineV2        | Optimization loops (20–40× faster, 100% parity) |
| `"dca"`, `"grid"`, `"dca_grid"`                             | DCAEngine            | DCA / Grid / Martingale strategies          |
| `"gpu"`                                                     | GPUEngineV2          | CUDA-accelerated (deprecated, use Numba)    |

> **Note**: When `dca_enabled=True` in config, DCAEngine is **always** used regardless of `engine_type`.

---

## 4. Critical Constants — NEVER CHANGE WITHOUT APPROVAL

| Constant              | Value          | Location                          | Reason                                      |
| --------------------- | -------------- | --------------------------------- | ------------------------------------------- |
| `commission_value`    | **0.0007**     | `BacktestConfig.commission_value` | TradingView parity — 10+ files depend on this |
| Engine                | **FallbackEngineV4** | `backend/backtesting/engine.py`   | Gold standard; V2 kept for parity tests only |
| `DATA_START_DATE`     | **2025-01-01** | `backend/config/database_policy.py` | Never hardcode — always import              |
| Max backtest duration | **730 days**   | `BacktestConfig.validate_dates()` | Pydantic validator; raises ValueError if exceeded |

### High-Risk Variables (grep before any refactor)

- `commission_rate` / `commission_value` — breaks TradingView parity if changed
- `strategy_params` — used in all strategies, optimizer, and UI
- `initial_capital` — engine, metrics, UI
- Port aliases in adapter — silent signal drops if broken

---

## 5. Development Commands

### Running the Application

```powershell
# Option 1: Start all services (recommended)
.\start_all.ps1

# Option 2: Using dev commands
.\dev.ps1 run

# Option 3: Direct uvicorn
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload

# Option 4: CLI entry point
python main.py server
```

### Dev Commands (Windows PowerShell)

```powershell
.\dev.ps1 help       # Show all commands
.\dev.ps1 lint       # Run linter (ruff)
.\dev.ps1 format     # Format code
.\dev.ps1 test       # Run tests
.\dev.ps1 test-cov   # Run tests with coverage
.\dev.ps1 clean      # Clean cache files
.\dev.ps1 mypy       # Type checking
```

### Dev Commands (Linux/Mac)

```bash
make help           # Show all commands
make lint           # Run linter
make format         # Format code
make test           # Run tests
make test-cov       # Tests with coverage
```

### Running Tests

```powershell
# All tests
pytest

# With coverage report
pytest --cov=backend --cov-report=html

# Specific test categories
pytest tests/test_gpu_acceleration.py -v      # GPU tests
pytest tests/test_backtest_api_integration.py # API tests
pytest tests/test_monte_carlo.py              # Monte Carlo tests

# Run with markers
pytest -m "not slow"    # Skip slow tests
pytest -m "integration" # Only integration tests
```

### Code Quality Tools

```powershell
# Linting
ruff check backend/ --fix

# Formatting
ruff format backend/

# Type checking
mypy backend/ --ignore-missing-imports

# Security scan
bandit -r backend/ -c pyproject.toml

# Pre-commit hooks
pre-commit run --all-files
```

---

## 6. Code Style & Conventions

### Linting & Formatting

This project uses **Ruff** for linting and formatting:

- **Line length**: 120 characters
- **Quote style**: Double quotes
- **Indent style**: 4 spaces
- **Import order**: future → stdlib → third-party → first-party → local

Configuration in `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py313"
line-length = 120
fix = true
```

### Type Hints

- Required for public functions
- Use `from __future__ import annotations` for forward references
- Configuration in `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.13"
warn_return_any = false
disallow_untyped_defs = false
```

### Docstrings

Use Google-style docstrings for all public functions:

```python
def calculate_sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0,
) -> float:
    """Calculate the Sharpe ratio for a series of returns.

    The Sharpe ratio measures risk-adjusted return. Higher values indicate
    better risk-adjusted performance.

    Args:
        returns: List of periodic returns as decimals (e.g., 0.05 for 5%).
        risk_free_rate: Annualized risk-free rate. Defaults to 0.0.

    Returns:
        The annualized Sharpe ratio.

    Raises:
        ValueError: If returns list is empty.

    Example:
        >>> returns = [0.01, 0.02, -0.01, 0.03]
        >>> calculate_sharpe_ratio(returns)
        1.23
    """
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:

```
feat(backtest): Add GPU acceleration support
fix(api): Handle empty response from Bybit
docs: Update QUICKSTART with Docker instructions
```

---

## 7. Testing Practices

### Test Organization

```
tests/
├── conftest.py                    # Shared fixtures
├── backend/
│   ├── backtesting/               # Engine, strategies, indicators
│   ├── api/                       # API routers, middleware
│   ├── agents/                    # AI agent tests
│   └── core/                      # Core utilities
├── advanced_backtesting/          # Advanced features
├── ai_agents/                     # Agent collaboration tests
├── backtesting/                   # GPU, MTF, optimization tests
├── chaos/                         # Chaos engineering tests
├── e2e/                           # End-to-end tests
├── frontend/                      # Frontend tests
├── integration/                   # Integration tests (DB, Redis, APIs)
├── load/                          # Load testing
└── security/                      # Security audit tests
```

### Test Standards

- Use `pytest` for all tests
- Follow AAA pattern: Arrange, Act, Assert
- Use descriptive test names: `test_function_should_do_something_when_condition`
- Mock external services (APIs, databases)
- Mark slow tests with `@pytest.mark.slow`

### Example Test

```python
class TestBacktestService:
    """Tests for BacktestService."""

    def test_run_backtest_returns_valid_metrics(self, mock_data):
        """Test that backtest returns valid performance metrics."""
        # Arrange
        service = BacktestService()
        config = BacktestConfig(symbol="BTCUSDT", strategy="MACD")

        # Act
        result = service.run(config, mock_data)

        # Assert
        assert result.success is True
        assert result.metrics.sharpe_ratio > 0
        assert result.metrics.total_trades >= 0
```

---

## 8. Project Structure

```
bybit_strategy_tester_v2/
├── main.py                        # CLI entry point
├── pyproject.toml                 # Project config (ruff, mypy, pytest)
├── pytest.ini                     # Pytest configuration
├── alembic.ini                    # Database migrations
├── requirements-dev.txt           # Development dependencies
├── requirements-ml.txt            # ML dependencies
├── backend/
│   ├── api/                       # FastAPI application
│   │   ├── routers/               # API endpoints (55+ routes)
│   │   ├── middleware/            # CORS, rate-limiting, CSRF
│   │   └── mcp/                   # MCP integration (disabled in prod)
│   ├── agents/                    # AI agent system
│   │   ├── unified_agent_interface.py
│   │   ├── agent_memory.py
│   │   └── langgraph_orchestrator.py
│   ├── backtesting/               # Core backtesting engine
│   │   ├── engine.py              # FallbackEngineV4 (gold standard)
│   │   ├── fast_optimizer.py      # GPU-accelerated optimizer
│   │   ├── monte_carlo.py         # Monte Carlo simulation
│   │   ├── market_regime.py       # Market regime detection
│   │   ├── mtf/                   # Multi-timeframe analysis
│   │   └── strategies/            # Built-in strategies
│   ├── core/                      # Core utilities
│   │   ├── metrics_calculator.py  # 166-metric suite
│   │   └── indicators/            # Technical indicators (40+)
│   ├── services/                  # Business logic
│   │   └── adapters/bybit.py      # Bybit API adapter
│   ├── database/                  # Database models & repos
│   ├── optimization/              # Optuna, Ray, grid optimization
│   ├── trading/                   # Live trading execution
│   └── migrations/                # Alembic migrations
├── frontend/                      # Static HTML/JS frontend
│   ├── dashboard.html             # Main trading dashboard
│   ├── strategy-builder.html      # Visual strategy builder
│   ├── js/                        # JavaScript modules
│   └── css/                       # Stylesheets
├── tests/                         # Test suite (150+ tests)
├── deployment/                    # Docker and K8s configs
├── docs/                          # Documentation
└── scripts/                       # Utility scripts
```

---

## 9. Docker & Deployment

### Docker

```bash
# Build image
docker build -t bybit-strategy-tester .

# Run container
docker run -p 8000:8000 --env-file .env bybit-strategy-tester

# With GPU support
docker run --gpus all -p 8000:8000 --env-file .env bybit-strategy-tester
```

### Docker Compose

```bash
# Development
docker-compose -f deployment/docker-compose.yml up -d

# Production with Redis and PostgreSQL
docker-compose -f deployment/docker-compose-prod.yml up -d
```

### Kubernetes

```bash
# Apply manifests
kubectl apply -f k8s/

# Using Helm
helm install bybit-tester ./helm/bybit-strategy-tester
```

---

## 10. Documentation

| Document                                                    | Description            |
| ----------------------------------------------------------- | ---------------------- |
| [README.md](README.md)                                      | Project overview       |
| [QUICKSTART.md](QUICKSTART.md)                              | Getting started        |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md)                    | Command cheat sheet    |
| [CONTRIBUTING.md](CONTRIBUTING.md)                          | Contribution guidelines|
| [docs/architecture/ENGINE_ARCHITECTURE.md](docs/architecture/ENGINE_ARCHITECTURE.md) | System design |
| [docs/reference/TRADINGVIEW_METRICS_REFERENCE.md](docs/reference/TRADINGVIEW_METRICS_REFERENCE.md) | Metrics mapping |
| [CHANGELOG.md](CHANGELOG.md)                                | Version history        |
| [AGENTS.MD](AGENTS.MD)                                      | Global agent rules     |
| [CLAUDE.md](CLAUDE.md)                                      | Claude-specific config |

---

## 11. AI Agent System

### Supported Agents

| Agent        | Config File                  | Use Case                          |
| ------------ | ---------------------------- | --------------------------------- |
| **DeepSeek** | `backend/agents/`            | Strategy generation, code analysis|
| **Qwen**     | `backend/agents/`            | Multi-agent collaboration         |
| **Perplexity**| `backend/agents/`           | Research, market analysis         |

### Agent Configuration

```ini
# DeepSeek
DEEPSEEK_API_KEY=sk-your_key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TEMPERATURE=0.7

# Qwen
QWEN_API_KEY=sk-your_key
QWEN_MODEL=qwen-plus
QWEN_TEMPERATURE=0.4

# Perplexity
PERPLEXITY_API_KEY=pplx-your_key
PERPLEXITY_MODEL=sonar
```

### Unified Agent Interface

```python
from backend.agents.unified_agent_interface import (
    AgentRequest,
    AgentType,
    UnifiedAgentInterface,
)

async def generate_strategy():
    agent = UnifiedAgentInterface()
    request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        prompt="Generate a momentum strategy for BTC",
        context={"symbol": "BTCUSDT"},
    )
    response = await agent.send_request(request)
    print(response.content)
```

---

## 12. Known Issues & Gotchas

### Windows-Specific

- **Bash fork errors**: Common with Cygwin — use PowerShell or WSL2 instead
- **Pre-commit hooks**: May fail on Windows — use `.\dev.ps1 lint` instead
- **Path separators**: Use `pathlib.Path` instead of string concatenation

### TradingView Parity

- Commission **MUST** be 0.07% (`commission_value=0.0007`)
- Use `FallbackEngineV4` as gold standard
- Check calibration script for metric verification

### Database

- SQLite used by default (auto-created in `data/`)
- PostgreSQL recommended for production
- Always run migrations: `alembic upgrade head`

### GPU Acceleration

- Requires CUDA Toolkit 11.8+
- Install `cupy-cuda11x` or `cupy-cuda12x`
- Numba preferred over CuPy for most optimizations

---

## 13. Self-Check Before Completing Tasks

| Check          | Question                           |
| -------------- | ---------------------------------- |
| ✅ Goal met?   | Did I do exactly what was asked?   |
| ✅ Documented? | Updated all relevant docs?         |
| ✅ Tested?     | Verified the change works?         |
| ✅ Clean?      | No lint errors or warnings?        |
| ✅ Context?    | Left enough info for next session? |
| ✅ Improved?   | Did I improve code quality?        |
| ✅ Secure?     | No security issues introduced?     |

---

## 14. Quick Reference

### Common Tasks

```powershell
# Start server
python main.py server

# Run backtest via API
curl -X POST http://localhost:8000/api/v1/backtests/ `
  -H "Content-Type: application/json" `
  -d '{
    "symbol": "BTCUSDT",
    "interval": "15m",
    "start_date": "2025-01-01",
    "end_date": "2025-01-15",
    "strategy_type": "rsi",
    "strategy_params": {"period": 14, "overbought": 70, "oversold": 30}
  }'

# Check system health
python main.py health

# Run database migrations
python main.py migrate

# Generate AI strategy
python main.py generate-strategy --prompt "momentum strategy" --symbol BTCUSDT
```

### File Locations

| File                                    | Purpose                    |
| --------------------------------------- | -------------------------- |
| `backend/backtesting/models.py`         | BacktestConfig, Result models |
| `backend/backtesting/engine.py`         | Main backtest engine       |
| `backend/core/metrics_calculator.py`    | 166 trading metrics        |
| `backend/agents/unified_agent_interface.py` | AI agent interface    |
| `backend/config/database_policy.py`     | DB constants, dates        |
| `.env`                                  | Environment variables      |

---

_Last Updated: 2026-02-26_
_Version: 2.0.0_
