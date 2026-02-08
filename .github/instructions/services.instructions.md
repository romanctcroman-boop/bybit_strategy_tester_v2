---
applyTo: "**/services/**/*.py"
---

# Services Layer Rules

## Architecture

Services contain business logic and orchestrate between:

- API layer (callers)
- Database/Repository layer (data access)
- External APIs (Bybit adapter)
- Backtesting engines

## Critical Rules

1. **Services MUST NOT import from API layer** (no circular dependencies)
2. **Services MUST NOT import FastAPI** (no HTTPException — raise domain exceptions)
3. **Use dependency injection** — pass dependencies, don't import globals
4. **All Bybit API calls MUST check `retCode`** — `0` = success
5. **Rate limiting**: Bybit API = 120 req/min — use exponential backoff on 429

## Service Pattern

```python
from loguru import logger
from typing import Optional, List

class BacktestService:
    """Orchestrates backtest execution."""

    def __init__(self, data_service: DataService, engine_factory: EngineFactory):
        self.data_service = data_service
        self.engine_factory = engine_factory

    async def run_backtest(self, config: BacktestConfig) -> BacktestResult:
        """Run a complete backtest with metrics calculation."""
        logger.info(f"Starting backtest: {config.symbol} {config.timeframe}")

        # 1. Load data
        data = await self.data_service.load_ohlcv(
            symbol=config.symbol,
            timeframe=config.timeframe,
            start_date=config.start_date,
            end_date=config.end_date
        )

        # 2. Generate signals
        strategy = StrategyFactory.create(config.strategy_type, config.strategy_params)
        signals = strategy.generate_signals(data)

        # 3. Run engine (commission_rate = 0.0007 ALWAYS)
        engine = self.engine_factory.create(config)
        result = engine.run(signals)

        # 4. Calculate metrics
        metrics = MetricsCalculator.calculate(result)

        return BacktestResult(trades=result.trades, metrics=metrics)
```

## Error Handling

```python
# Domain exceptions (NOT HTTPException)
class DataNotFoundError(Exception):
    """Raised when requested market data is not available."""
    pass

class InvalidStrategyError(Exception):
    """Raised when strategy configuration is invalid."""
    pass

# Let the API layer convert these to HTTP responses
```

## Async Pattern for SQLite

```python
import asyncio

async def get_backtests(self, symbol: str) -> List[BacktestResult]:
    """Load backtests in async context using thread pool."""
    return await asyncio.to_thread(
        self.repository.list_by_symbol, symbol
    )
```
