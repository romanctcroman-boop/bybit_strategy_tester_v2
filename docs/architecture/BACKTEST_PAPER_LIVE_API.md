# Backtest → Paper → Live — единый API (дизайн)

**Цель:** Один код стратегии для backtest, paper и live с переключаемыми провайдерами.

## Абстракции

### DataProvider (абстрактный)

```python
from abc import ABC, abstractmethod

class DataProvider(ABC):
    @abstractmethod
    def get_klines(self, symbol: str, interval: str, limit: int, ...) -> pd.DataFrame:
        """OHLCV данные."""
        pass

    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        pass
```

**Реализации:**
- `HistoricalDataProvider` — из БД/файла (backtest)
- `LiveDataProvider` — Bybit WebSocket/REST (paper, live)

### OrderExecutor (абстрактный)

```python
class OrderExecutor(ABC):
    @abstractmethod
    def place_market_order(self, symbol: str, side: str, qty: float, ...) -> OrderResult:
        pass

    @abstractmethod
    def place_limit_order(self, symbol: str, side: str, qty: float, price: float, ...) -> OrderResult:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass
```

**Реализации:**
- `SimulatedExecutor` — симуляция fills (backtest, paper)
- `BybitExecutor` — реальные ордера (live)

## Режимы

| Режим | DataProvider | OrderExecutor |
|-------|--------------|---------------|
| Backtest | HistoricalDataProvider (БД) | SimulatedExecutor |
| Paper | LiveDataProvider | SimulatedExecutor |
| Live | LiveDataProvider | BybitExecutor |

## Текущее состояние

- `backend/services/live_trading/order_executor.py` — BybitExecutor (live)
- `backend/services/data_service.py` — доступ к историческим данным
- **backend/services/unified_trading/** (2026-01-31):
  - `interfaces.py` — DataProvider, OrderExecutorInterface, OrderResult
  - `historical_data_provider.py` — HistoricalDataProvider (БД)
  - `simulated_executor.py` — SimulatedExecutor (ExecutionSimulator)
- **backend/services/unified_trading/** (2026-01-31):
  - `live_data_provider.py` — LiveDataProvider (SmartKlineService)
  - `strategy_runner.py` — StrategyRunner(data_provider, order_executor)

## Ссылки

- ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md §10
- backend/services/live_trading/
