"""
🔗 Unified Trading API

Unified interface for backtest → live trading.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class DataProvider(ABC):
    """Abstract data provider"""

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        """Get OHLCV data"""
        pass

    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Get current price"""
        pass


class HistoricalDataProvider(DataProvider):
    """Historical data provider for backtesting"""

    def __init__(self, data_dict: dict[str, pd.DataFrame]):
        self.data_dict = data_dict

    def get_ohlcv(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        """Get historical OHLCV"""
        key = f"{symbol}_{timeframe}"
        if key in self.data_dict:
            data = self.data_dict[key]
            return data[(data.index >= start) & (data.index <= end)]
        return pd.DataFrame()

    def get_current_price(self, symbol: str) -> float:
        """Get last price"""
        for key, data in self.data_dict.items():
            if key.startswith(symbol) and len(data) > 0:
                return data["close"].iloc[-1]
        return 0.0


class LiveDataProvider(DataProvider):
    """Live data provider"""

    def __init__(self, websocket_client=None):
        self.ws_client = websocket_client
        self.current_prices: dict[str, float] = {}

    def get_ohlcv(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        """Get live OHLCV (recent data)"""
        # Fetch from WebSocket or API
        logger.info(f"Fetching live data for {symbol}")
        return pd.DataFrame()

    def get_current_price(self, symbol: str) -> float:
        """Get current live price"""
        return self.current_prices.get(symbol, 0.0)

    def update_price(self, symbol: str, price: float):
        """Update current price"""
        self.current_prices[symbol] = price


class OrderExecutor(ABC):
    """Abstract order executor"""

    @abstractmethod
    def submit_order(self, symbol: str, side: str, quantity: float, **kwargs) -> dict[str, Any]:
        """Submit order"""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        pass


class SimulatedExecutor(OrderExecutor):
    """Simulated order executor for paper trading"""

    def __init__(self, initial_balance: float = 10000.0):
        self.balance = initial_balance
        self.positions: dict[str, float] = {}
        self.orders: dict[str, dict[str, Any]] = {}

    def submit_order(self, symbol: str, side: str, quantity: float, **kwargs) -> dict[str, Any]:
        """Simulate order execution"""
        price = kwargs.get("price", 50000.0)  # Mock price

        order_id = f"sim_{len(self.orders)}"

        self.orders[order_id] = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "status": "filled",
        }

        # Update position
        if side == "buy":
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
            self.balance -= quantity * price
        else:
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity
            self.balance += quantity * price

        return {
            "order_id": order_id,
            "status": "filled",
            "price": price,
            "quantity": quantity,
        }

    def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        if order_id in self.orders:
            self.orders[order_id]["status"] = "cancelled"
            return True
        return False


class LiveExecutor(OrderExecutor):
    """Live order executor"""

    def __init__(self, exchange_client=None):
        self.exchange = exchange_client
        self.orders: dict[str, dict[str, Any]] = {}

    def submit_order(self, symbol: str, side: str, quantity: float, **kwargs) -> dict[str, Any]:
        """Submit live order"""
        logger.info(f"Submitting {side} order for {quantity} {symbol}")

        # In production, submit to exchange
        return {
            "order_id": "live_123",
            "status": "pending",
        }

    def cancel_order(self, order_id: str) -> bool:
        """Cancel live order"""
        logger.info(f"Cancelling order {order_id}")
        return True


class UnifiedTradingAPI:
    """
    Unified trading API.

    Single interface for backtest and live trading.

    Example:
    ```python
    # Backtest mode
    api = UnifiedTradingAPI(mode='backtest', data=data_dict)
    result = api.run_strategy(strategy)

    # Live mode
    api = UnifiedTradingAPI(mode='live', ws_client=ws, exchange=exchange)
    result = api.run_strategy(strategy)
    ```
    """

    def __init__(
        self,
        mode: str = "backtest",
        data: dict[str, pd.DataFrame] | None = None,
        ws_client=None,
        exchange_client=None,
        initial_balance: float = 10000.0,
    ):
        """
        Args:
            mode: 'backtest' or 'live'
            data: Historical data (for backtest)
            ws_client: WebSocket client (for live)
            exchange_client: Exchange client (for live)
            initial_balance: Initial balance
        """
        self.mode = mode

        # Setup data provider
        if mode == "backtest":
            self.data_provider = HistoricalDataProvider(data or {})
            self.order_executor = SimulatedExecutor(initial_balance)
        else:
            self.data_provider = LiveDataProvider(ws_client)
            self.order_executor = LiveExecutor(exchange_client)

    def get_data(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        """Get data"""
        return self.data_provider.get_ohlcv(symbol, timeframe, start, end)

    def get_price(self, symbol: str) -> float:
        """Get current price"""
        return self.data_provider.get_current_price(symbol)

    def submit_order(self, symbol: str, side: str, quantity: float, **kwargs) -> dict[str, Any]:
        """Submit order"""
        return self.order_executor.submit_order(symbol, side, quantity, **kwargs)

    def run_strategy(self, strategy: Any) -> dict[str, Any]:
        """
        Run strategy.

        Args:
            strategy: Strategy instance with generate_signals() method

        Returns:
            Results dictionary
        """
        logger.info(f"Running strategy in {self.mode} mode")

        # Get signals from strategy
        signals = strategy.generate_signals(self.data_provider)

        # Execute trades
        trades = []
        for signal in signals:
            order = self.order_executor.submit_order(
                symbol=signal["symbol"],
                side=signal["side"],
                quantity=signal["quantity"],
                price=signal.get("price"),
            )
            trades.append(order)

        return {
            "mode": self.mode,
            "trades": trades,
            "total_trades": len(trades),
        }
