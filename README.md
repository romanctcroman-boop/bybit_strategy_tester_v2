# Bybit Strategy Tester v2

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-150%2B%20passing-brightgreen)](tests/)
[![GPU Accelerated](https://img.shields.io/badge/GPU-CUDA%20Accelerated-76B900?logo=nvidia)](https://developer.nvidia.com/cuda-toolkit)

Professional-grade backtesting and live trading platform for Bybit Exchange with
AI-powered strategy analysis and GPU acceleration.

## 🌟 Key Features

| Feature                 | Description                                                      |
| ----------------------- | ---------------------------------------------------------------- |
| **🚀 GPU Backtesting**  | CUDA-accelerated backtesting with CuPy - up to 100x faster       |
| **📊 166 Metrics**      | Full TradingView metric parity including Sharpe, Sortino, Max DD |
| **🤖 AI Analysis**      | DeepSeek and Perplexity integration for strategy optimization    |
| **📈 Multi-Timeframe**  | HTF filters, MTF analysis with automatic data aggregation        |
| **🎯 Walk-Forward**     | Out-of-sample validation with rolling windows                    |
| **🎲 Monte Carlo**      | Statistical validation with confidence intervals                 |
| **📉 Market Regime**    | Automatic detection of trending/ranging/volatile markets         |
| **🔄 Real-Time Data**   | WebSocket-based live market data from Bybit                      |
| **🐳 Production Ready** | Docker, Kubernetes, CI/CD, Prometheus monitoring                 |

## 🎬 Quick Start

### Prerequisites

- Python 3.11+ (3.12/3.13/3.14 supported; 3.14 recommended for dev)
- CUDA Toolkit 11.8+ (optional, for GPU acceleration)
- Redis (optional, for caching)

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

# Optional: Install GPU support
pip install cupy-cuda11x  # For CUDA 11.x
# or
pip install cupy-cuda12x  # For CUDA 12.x

# Optional: Full dev deps (numba, vectorbt, torch) — for all tests & L2/CGAN
pip install .[dev-full]

# Copy environment configuration
Copy-Item .env.example .env
# Edit .env with your API keys
```

### Running the Application

```powershell
# Option 1: Start all services (recommended)
.\start_all.ps1

# Option 2: Using dev commands
.\dev.ps1 run

# Option 3: Direct uvicorn
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload
```

**Application URLs:**

| URL                                           | Description                    |
| --------------------------------------------- | ------------------------------ |
| http://localhost:8000/frontend/dashboard.html | 📊 Trading Dashboard           |
| http://localhost:8000/docs                    | 📚 API Documentation (Swagger) |
| http://localhost:8000/api/v1/health           | 💚 Health Check                |

## 📖 Usage Examples

### Python API

```python
from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig

# Create backtest configuration
config = BacktestConfig(
    symbol="BTCUSDT",
    interval="15m",
    start_date="2025-01-01",
    end_date="2025-01-15",
    initial_capital=10000,
    leverage=10,
    strategy_type="rsi",
    strategy_params={"period": 14, "overbought": 70, "oversold": 30},
    stop_loss=0.02,  # 2%
    take_profit=0.04,  # 4%
    direction="both"  # long, short, or both
)

# Run backtest
engine = BacktestEngine()
result = await engine.run(config)

# Access metrics
print(f"Net Profit: ${result.metrics.net_profit:.2f}")
print(f"Win Rate: {result.metrics.win_rate:.1f}%")
print(f"Sharpe Ratio: {result.metrics.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.metrics.max_drawdown:.1f}%")
print(f"Total Trades: {result.metrics.total_trades}")
```

### REST API

```bash
# Run a backtest
curl -X POST http://localhost:8000/api/v1/backtests/ \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "interval": "15m",
    "start_date": "2025-01-01",
    "end_date": "2025-01-15",
    "initial_capital": 10000,
    "leverage": 10,
    "strategy_type": "macd",
    "strategy_params": {
      "fast_period": 12,
      "slow_period": 26,
      "signal_period": 9
    },
    "stop_loss": 0.02,
    "take_profit": 0.04
  }'

# Get backtest result
curl http://localhost:8000/api/v1/backtests/{backtest_id}

# List all backtests
curl http://localhost:8000/api/v1/backtests/
```

### Strategy Optimization

```python
from backend.backtesting.fast_optimizer import FastGridOptimizer

optimizer = FastGridOptimizer()

# Define parameter grid
param_grid = {
    "period": [10, 14, 21],
    "overbought": [65, 70, 75, 80],
    "oversold": [20, 25, 30, 35],
    "stop_loss": [0.01, 0.02, 0.03],
    "take_profit": [0.02, 0.04, 0.06]
}

# Run optimization (uses GPU if available)
results = await optimizer.optimize(
    symbol="BTCUSDT",
    interval="15m",
    start_date="2025-01-01",
    end_date="2025-01-15",
    strategy_type="rsi",
    param_grid=param_grid,
    metric="sharpe_ratio",  # Optimize for Sharpe
    n_workers=4
)

print(f"Best params: {results.best_params}")
print(f"Best Sharpe: {results.best_score:.2f}")
```

### Monte Carlo Simulation

```python
from backend.backtesting.monte_carlo import MonteCarloSimulator

simulator = MonteCarloSimulator(n_simulations=1000)

# Run simulation on backtest trades
mc_result = simulator.run(backtest_result.trades)

print(f"95% CI Net Profit: ${mc_result.ci_95_low:.0f} - ${mc_result.ci_95_high:.0f}")
print(f"Probability of Profit: {mc_result.prob_profit:.1%}")
print(f"Expected Max Drawdown: {mc_result.expected_max_dd:.1%}")
print(f"Value at Risk (95%): ${mc_result.var_95:.0f}")
```

## 📁 Project Structure

```
bybit_strategy_tester_v2/
├── backend/                 # Python backend
│   ├── api/                 # FastAPI application
│   │   ├── routers/         # API endpoints
│   │   ├── mcp/             # MCP integration
│   │   └── middleware/      # Request middleware
│   ├── backtesting/         # Backtesting engine
│   │   ├── engine.py        # Main backtest engine
│   │   ├── fast_optimizer.py # GPU-accelerated optimizer
│   │   ├── monte_carlo.py   # Monte Carlo simulation
│   │   ├── market_regime.py # Market regime detection
│   │   └── mtf/             # Multi-timeframe analysis
│   ├── core/                # Core utilities
│   │   └── metrics_calculator.py  # 166-metric suite
│   ├── services/            # Business logic
│   │   └── adapters/bybit.py # Bybit API adapter
│   └── database/            # Database models & repos
├── frontend/                # Static HTML/JS frontend
│   ├── dashboard.html       # Main trading dashboard
│   ├── js/                  # JavaScript modules
│   └── css/                 # Stylesheets
├── tests/                   # Test suite (150+ tests)
├── deployment/              # Docker and K8s configs
├── docs/                    # Documentation
└── scripts/                 # Utility scripts
```

## 🛠️ Development

### Dev Commands (Windows)

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

### Code Quality

This project follows [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).

| Tool           | Purpose              | Config                    |
| -------------- | -------------------- | ------------------------- |
| **Ruff**       | Linting & Formatting | `pyproject.toml`          |
| **Mypy**       | Type Checking        | `pyproject.toml`          |
| **Pytest**     | Testing              | `pytest.ini`              |
| **Pre-commit** | Git Hooks            | `.pre-commit-config.yaml` |

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

## ⚙️ Configuration

### Environment Variables

| Variable              | Description                         | Required | Default                 |
| --------------------- | ----------------------------------- | -------- | ----------------------- |
| `BYBIT_API_KEY`       | Bybit API key                       | Yes      | -                       |
| `BYBIT_API_SECRET`    | Bybit API secret                    | Yes      | -                       |
| `DATABASE_URL`        | Database connection string          | No       | `sqlite:///app.sqlite3` |
| `REDIS_URL`           | Redis connection string             | No       | -                       |
| `DEEPSEEK_API_KEYS`   | DeepSeek API keys (comma-separated) | No       | -                       |
| `PERPLEXITY_API_KEYS` | Perplexity API keys                 | No       | -                       |
| `USE_GPU`             | Enable GPU acceleration             | No       | `true`                  |
| `LOG_LEVEL`           | Logging level                       | No       | `INFO`                  |

### Validate Environment

```powershell
.\scripts\validate_env.ps1
```

## 📊 Supported Strategies

| Strategy      | Parameters                                    | Description                               |
| ------------- | --------------------------------------------- | ----------------------------------------- |
| **RSI**       | `period`, `overbought`, `oversold`            | Relative Strength Index                   |
| **MACD**      | `fast_period`, `slow_period`, `signal_period` | Moving Average Convergence Divergence     |
| **SMA**       | `fast_period`, `slow_period`                  | Simple Moving Average Crossover           |
| **EMA**       | `fast_period`, `slow_period`                  | Exponential Moving Average Crossover      |
| **Bollinger** | `period`, `std_dev`, `mode`                   | Bollinger Bands (breakout/mean reversion) |
| **ADX**       | `period`, `threshold`                         | Average Directional Index                 |
| **Custom**    | User-defined                                  | Custom strategy via Python class          |

## 🚀 API Reference

### Backtests

```http
POST /api/v1/backtests/
Content-Type: application/json

{
    "symbol": "BTCUSDT",
    "interval": "15m",
    "start_date": "2025-01-01",
    "end_date": "2025-01-15",
    "initial_capital": 10000,
    "leverage": 10,
    "strategy_type": "macd",
    "strategy_params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
    "stop_loss": 0.02,
    "take_profit": 0.04,
    "direction": "both"
}
```

### Optimization

```http
POST /api/v1/optimize/
Content-Type: application/json

{
    "symbol": "BTCUSDT",
    "interval": "15m",
    "start_date": "2025-01-01",
    "end_date": "2025-01-15",
    "strategy_type": "rsi",
    "param_ranges": {
        "period": {"min": 10, "max": 21, "step": 1},
        "overbought": {"min": 65, "max": 80, "step": 5},
        "oversold": {"min": 20, "max": 35, "step": 5}
    },
    "optimize_metric": "sharpe_ratio"
}
```

### Health Check

```http
GET /api/v1/health
```

For full API documentation, visit http://localhost:8000/docs when the server is running.

## 🐳 Deployment

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

See [`deployment/`](deployment/) for full Kubernetes manifests and Helm charts.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Follow the code style guidelines
4. Write tests for new functionality
5. Run the test suite: `pytest`
6. Submit a pull request

### Pre-commit Hooks

```powershell
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## 📚 Documentation

| Document                                                    | Description            |
| ----------------------------------------------------------- | ---------------------- |
| [Quick Reference](QUICK_REFERENCE.md)                       | Command cheat sheet    |
| [Architecture](docs/ENGINE_ARCHITECTURE.md)                 | System design          |
| [TradingView Parity](docs/TRADINGVIEW_METRICS_REFERENCE.md) | Metrics mapping        |
| [API Docs](http://localhost:8000/docs)                      | Interactive Swagger UI |
| [Changelog](CHANGELOG.md)                                   | Version history        |

## 📈 Performance

| Metric                         | Value              |
| ------------------------------ | ------------------ |
| **Backtest Speed (CPU)**       | ~500 trades/sec    |
| **Backtest Speed (GPU)**       | ~50,000 trades/sec |
| **Optimization (1000 combos)** | ~30 seconds (GPU)  |
| **API Response Time**          | <100ms (p95)       |
| **Memory Usage**               | ~500MB base        |

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

**Built with ❤️ for algorithmic traders**

<p align="center">
  <a href="https://github.com/RomanCTC/bybit_strategy_tester_v2/stargazers">⭐ Star this repo</a> •
  <a href="https://github.com/RomanCTC/bybit_strategy_tester_v2/issues">🐛 Report Bug</a> •
  <a href="https://github.com/RomanCTC/bybit_strategy_tester_v2/issues">💡 Request Feature</a>
</p>
