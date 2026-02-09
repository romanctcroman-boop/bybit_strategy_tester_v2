# Quick Start

This guide helps you set up and run Bybit Strategy Tester in 5 minutes.

## Prerequisites

Before you begin, ensure you have:

- Python 3.11 or higher installed
- Git installed
- (Optional) PostgreSQL or Docker for production database

## Installation

### Step 1: Clone and setup environment

```powershell
# Clone the repository
git clone https://github.com/romanctcroman-boop/bybit_strategy_tester_v2.git
cd bybit_strategy_tester_v2

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r backend/requirements.txt
```

### Step 2: Configure environment

```powershell
# Copy example configuration
Copy-Item .env.example .env

# Edit .env with your API keys
notepad .env
```

Required variables in `.env`:

```ini
BYBIT_API_KEY=your_bybit_api_key
BYBIT_API_SECRET=your_bybit_api_secret
```

Optional variables for AI features:

```ini
DEEPSEEK_API_KEYS=sk-your-key
PERPLEXITY_API_KEYS=pplx-your-key
```

### Step 3: Validate configuration

```powershell
.\scripts\validate_env.ps1
```

### Step 4: Start the server

```powershell
# Option 1: Full stack (recommended)
.\start_all.ps1

# Option 2: API server only
.\dev.ps1 run

# Option 3: Direct uvicorn
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload
```

## Verify installation

Open your browser and navigate to:

| URL                                           | Description                 |
| --------------------------------------------- | --------------------------- |
| http://localhost:8000/docs                    | API documentation (Swagger) |
| http://localhost:8000/api/v1/health           | Health check endpoint       |
| http://localhost:8000/frontend/dashboard.html | Web dashboard               |

## Run your first backtest

### Using the API

```powershell
# Run a MACD backtest on BTCUSDT
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/backtests" `
    -Method POST `
    -ContentType "application/json" `
    -Body '{
        "symbol": "BTCUSDT",
        "interval": "15",
        "strategy": "MACD",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31"
    }'
```

### Using the dashboard

1.  Open http://localhost:8000/frontend/dashboard.html
2.  Select symbol (e.g., BTCUSDT)
3.  Choose strategy (e.g., MACD)
4.  Set date range
5.  Click "Run Backtest"

## Development commands

Use `dev.ps1` for common development tasks:

```powershell
.\dev.ps1 help       # Show all commands
.\dev.ps1 lint       # Check code quality
.\dev.ps1 format     # Format code
.\dev.ps1 test       # Run tests
.\dev.ps1 clean      # Clean cache files
```

> **Windows users**: Use `dev.ps1` instead of `pre-commit` for code quality
> checks. Pre-commit runs automatically in GitHub Actions CI/CD.

## Docker deployment

For production deployment:

```powershell
# Build and run with Docker Compose
docker-compose -f deployment/docker-compose.yml up -d

# View logs
docker-compose -f deployment/docker-compose.yml logs -f
```

## Troubleshooting

### Server won't start

1.  Check Python version: `python --version` (must be 3.11+)
2.  Verify dependencies: `pip install -r backend/requirements.txt`
3.  Check port availability: `netstat -an | findstr 8000`

### Database errors

If using SQLite (default):

```powershell
# Database is auto-created in project root
# Check if data.sqlite3 exists
Test-Path data.sqlite3
```

If using PostgreSQL:

```powershell
# Set DATABASE_URL in .env
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname

# Apply migrations
python -m alembic upgrade head
```

### API errors

Check the server logs for detailed error messages:

```powershell
# Logs are printed to console
# For file logs, check: logs/app.log
```

## Next steps

- Read [API Documentation](http://localhost:8000/docs)
- Explore [Architecture](docs/architecture/ENGINE_ARCHITECTURE.md)
- Review [TradingView Metrics](docs/reference/TRADINGVIEW_METRICS_REFERENCE.md)
- Check [AI Agent Guide](docs/ai/AI_AGENT_SYSTEM_DOCUMENTATION.md)

## Getting help

- Open an issue on GitHub
- Check existing documentation in `docs/`
- Review API docs at `/docs` endpoint
