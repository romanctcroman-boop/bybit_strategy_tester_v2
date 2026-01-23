# Bybit Strategy Tester v2

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Professional-grade backtesting and live trading platform for Bybit Exchange with
AI-powered strategy analysis.

## Features

- **High-Performance Backtesting** — GPU-accelerated backtesting engine with
  TradingView metric parity
- **AI Analysis** — DeepSeek and Perplexity integration for trade analysis
  and strategy optimization
- **Real-Time Data** — WebSocket-based live market data from Bybit
- **Strategy Management** — MACD, RSI, SMA, and custom strategy support
- **Risk Metrics** — Sortino, Sharpe, Max Drawdown, Win Rate, Profit Factor
- **MCP Integration** — Model Context Protocol for AI assistant integration
- **Production Ready** — Docker, Kubernetes, CI/CD, monitoring included

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Redis (optional, for caching)
- PostgreSQL (optional, SQLite works for development)

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

# Copy environment configuration
Copy-Item .env.example .env
# Edit .env with your API keys
```

### Running the Application

```powershell
# Option 1: Using start script (recommended)
.\start_all.ps1

# Option 2: Using dev commands
.\dev.ps1 run

# Option 3: Direct uvicorn
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload
```

**Application URLs:**

- Dashboard: http://localhost:8000/frontend/dashboard.html
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## Project Structure

```
bybit_strategy_tester_v2/
├── backend/                 # Python backend
│   ├── api/                 # FastAPI application
│   │   ├── routers/         # API endpoints
│   │   ├── mcp/             # MCP integration
│   │   └── middleware/      # Request middleware
│   ├── agents/              # AI agents
│   ├── backtesting/         # Backtesting engine
│   ├── services/            # Business logic
│   └── models/              # Database models
├── frontend/                # Static HTML/JS frontend
├── deployment/              # Docker and K8s configs
├── tests/                   # Test suite
├── docs/                    # Documentation
│   ├── api/                 # API documentation
│   ├── architecture/        # Architecture docs
│   └── archive/             # Historical docs
└── scripts/                 # Utility scripts
```

## Development

### Dev Commands (Windows)

```powershell
.\dev.ps1 help       # Show all commands
.\dev.ps1 lint       # Run linter (ruff)
.\dev.ps1 format     # Format code
.\dev.ps1 test       # Run tests
.\dev.ps1 clean      # Clean cache files
```

### Dev Commands (Linux/Mac)

```bash
make help           # Show all commands
make lint           # Run linter
make format         # Format code
make test           # Run tests
```

### Code Quality

This project follows [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).

- **Linting**: Ruff with Google-compatible rules
- **Formatting**: Ruff format (Black-compatible)
- **Type Hints**: Required for public APIs
- **Docstrings**: Google-style docstrings

### Running Tests

```powershell
# All tests
.\dev.ps1 test

# With coverage
.\dev.ps1 test-cov

# Specific test file
pytest tests/backend/api/mcp/test_mcp_tools.py -v
```

## Configuration

### Environment Variables

| Variable              | Description                         | Required            |
| --------------------- | ----------------------------------- | ------------------- |
| `BYBIT_API_KEY`       | Bybit API key                       | Yes                 |
| `BYBIT_API_SECRET`    | Bybit API secret                    | Yes                 |
| `DATABASE_URL`        | Database connection string          | No (SQLite default) |
| `REDIS_URL`           | Redis connection string             | No                  |
| `DEEPSEEK_API_KEYS`   | DeepSeek API keys (comma-separated) | No                  |
| `PERPLEXITY_API_KEYS` | Perplexity API keys                 | No                  |

### Validate Environment

```powershell
.\scripts\validate_env.ps1
```

## API Reference

### Backtests

```http
POST /api/v1/backtests
Content-Type: application/json

{
    "symbol": "BTCUSDT",
    "interval": "15",
    "strategy": "MACD",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
}
```

### Health Check

```http
GET /api/v1/health
```

For full API documentation, see http://localhost:8000/docs when the server
is running.

## Deployment

### Docker

```bash
# Build image
docker build -t bybit-strategy-tester .

# Run container
docker run -p 8000:8000 --env-file .env bybit-strategy-tester
```

### Docker Compose

```bash
# Development
docker-compose -f deployment/docker-compose.yml up -d

# Production
docker-compose -f deployment/docker-compose-prod.yml up -d
```

See [`deployment/`](deployment/) for Kubernetes manifests and Helm charts.

## Contributing

1.  Fork the repository
2.  Create a feature branch: `git checkout -b feature/my-feature`
3.  Follow the code style guidelines
4.  Write tests for new functionality
5.  Submit a pull request

### Pre-commit Hooks

```powershell
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Documentation

- [Quick Reference](docs/QUICK_REFERENCE.md) — Command cheat sheet
- [Architecture](docs/ENGINE_ARCHITECTURE.md) — System design
- [TradingView Parity](docs/TRADINGVIEW_METRICS_REFERENCE.md) — Metrics mapping
- [API Docs](http://localhost:8000/docs) — Interactive Swagger UI

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

**Built with ❤️ for algorithmic traders**
