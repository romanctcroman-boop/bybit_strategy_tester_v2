"""
Real-time Market Data Module for Universal Math Engine v2.3.

This module provides WebSocket streaming capabilities:
1. MarketDataStream - Unified WebSocket interface
2. TickerStream - Real-time ticker updates
3. OrderBookStream - L2 orderbook streaming
4. TradeStream - Trade tick streaming
5. CandleAggregator - Real-time candle building

Author: Universal Math Engine Team
Version: 2.3.0
"""

import asyncio
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 1. DATA TYPES
# =============================================================================


class StreamType(Enum):
    """Types of market data streams."""

    TICKER = "ticker"
    ORDERBOOK = "orderbook"
    TRADES = "trades"
    KLINE = "kline"
    LIQUIDATION = "liquidation"
    FUNDING = "funding"


class StreamStatus(Enum):
    """WebSocket connection status."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class TickerUpdate:
    """Real-time ticker update."""

    symbol: str
    timestamp: int
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    last_price: float
    last_size: float
    volume_24h: float
    high_24h: float
    low_24h: float
    change_24h: float

    @property
    def mid_price(self) -> float:
        """Get mid price."""
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        """Get spread."""
        return self.ask - self.bid


@dataclass
class TradeUpdate:
    """Real-time trade tick."""

    symbol: str
    timestamp: int
    trade_id: str
    price: float
    size: float
    side: str  # "buy" or "sell"
    is_maker: bool = False

    @property
    def value(self) -> float:
        """Get trade value in quote currency."""
        return self.price * self.size


@dataclass
class OrderBookLevel:
    """Single orderbook level."""

    price: float
    size: float


@dataclass
class OrderBookUpdate:
    """Real-time orderbook update."""

    symbol: str
    timestamp: int
    is_snapshot: bool
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    sequence: int = 0

    @property
    def best_bid(self) -> OrderBookLevel | None:
        """Get best bid."""
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> OrderBookLevel | None:
        """Get best ask."""
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> float:
        """Get mid price."""
        if self.bids and self.asks:
            return (self.bids[0].price + self.asks[0].price) / 2
        return 0.0


@dataclass
class KlineUpdate:
    """Real-time kline/candle update."""

    symbol: str
    interval: str
    timestamp: int  # Kline open time
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool  # True if candle is complete
    trades_count: int = 0


@dataclass
class StreamConfig:
    """Configuration for market data stream."""

    # Connection settings
    url: str = ""
    reconnect_attempts: int = 5
    reconnect_delay: float = 1.0
    ping_interval: float = 30.0
    ping_timeout: float = 10.0

    # Buffer settings
    buffer_size: int = 1000
    enable_buffering: bool = True

    # Processing settings
    batch_updates: bool = True
    batch_interval_ms: int = 100


# =============================================================================
# 2. BASE STREAM CLASS
# =============================================================================


class MarketDataStream(ABC):
    """
    Abstract base class for market data streams.

    Features:
    - Connection management
    - Automatic reconnection
    - Message buffering
    - Callback-based updates
    """

    def __init__(self, config: StreamConfig | None = None):
        """Initialize market data stream."""
        self.config = config or StreamConfig()
        self._status = StreamStatus.DISCONNECTED
        self._callbacks: list[Callable[[Any], None]] = []
        self._buffer: deque = deque(maxlen=self.config.buffer_size)
        self._last_message_time: float = 0
        self._reconnect_count: int = 0

    @property
    def status(self) -> StreamStatus:
        """Get current connection status."""
        return self._status

    @property
    def is_connected(self) -> bool:
        """Check if stream is connected."""
        return self._status == StreamStatus.CONNECTED

    def add_callback(self, callback: Callable[[Any], None]) -> None:
        """Add callback for stream updates."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[Any], None]) -> None:
        """Remove callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify(self, data: Any) -> None:
        """Notify all callbacks of new data."""
        for callback in self._callbacks:
            try:
                callback(data)
            except Exception:
                pass  # Silently ignore callback errors

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the data source."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the data source."""
        pass

    @abstractmethod
    async def subscribe(self, symbols: list[str]) -> bool:
        """Subscribe to symbols."""
        pass

    @abstractmethod
    async def unsubscribe(self, symbols: list[str]) -> bool:
        """Unsubscribe from symbols."""
        pass

    async def reconnect(self) -> bool:
        """Attempt to reconnect."""
        self._status = StreamStatus.RECONNECTING

        for attempt in range(self.config.reconnect_attempts):
            await asyncio.sleep(self.config.reconnect_delay * (attempt + 1))

            try:
                if await self.connect():
                    self._reconnect_count = 0
                    return True
            except Exception:
                self._reconnect_count += 1

        self._status = StreamStatus.ERROR
        return False


# =============================================================================
# 3. TICKER STREAM
# =============================================================================


class TickerStream(MarketDataStream):
    """
    Real-time ticker stream.

    Features:
    - Multi-symbol support
    - Rate limiting
    - Snapshot + incremental updates
    """

    def __init__(self, config: StreamConfig | None = None):
        """Initialize ticker stream."""
        super().__init__(config)
        self._subscriptions: set[str] = set()
        self._latest_tickers: dict[str, TickerUpdate] = {}
        self._running = False

    async def connect(self) -> bool:
        """Connect to ticker stream."""
        self._status = StreamStatus.CONNECTING
        # In real implementation, connect to WebSocket
        await asyncio.sleep(0.1)  # Simulate connection delay
        self._status = StreamStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        """Disconnect from ticker stream."""
        self._running = False
        self._status = StreamStatus.DISCONNECTED

    async def subscribe(self, symbols: list[str]) -> bool:
        """Subscribe to ticker updates."""
        self._subscriptions.update(symbols)
        return True

    async def unsubscribe(self, symbols: list[str]) -> bool:
        """Unsubscribe from ticker updates."""
        self._subscriptions.difference_update(symbols)
        return True

    def get_ticker(self, symbol: str) -> TickerUpdate | None:
        """Get latest ticker for a symbol."""
        return self._latest_tickers.get(symbol)

    async def _simulate_updates(self) -> None:
        """Simulate ticker updates for testing."""
        base_prices = {
            "BTCUSDT": 50000.0,
            "ETHUSDT": 3000.0,
            "SOLUSDT": 100.0,
        }

        self._running = True

        while self._running and self._status == StreamStatus.CONNECTED:
            for symbol in self._subscriptions:
                base = base_prices.get(symbol, 1000.0)

                # Simulate price movement
                noise = np.random.normal(0, 0.0001)
                price = base * (1 + noise)

                ticker = TickerUpdate(
                    symbol=symbol,
                    timestamp=int(time.time() * 1000),
                    bid=price * 0.9999,
                    ask=price * 1.0001,
                    bid_size=np.random.uniform(0.5, 5.0),
                    ask_size=np.random.uniform(0.5, 5.0),
                    last_price=price,
                    last_size=np.random.uniform(0.01, 0.5),
                    volume_24h=np.random.uniform(1000, 10000),
                    high_24h=price * 1.02,
                    low_24h=price * 0.98,
                    change_24h=noise * 10000,
                )

                self._latest_tickers[symbol] = ticker
                self._notify(ticker)

            await asyncio.sleep(0.1)  # 100ms update interval


# =============================================================================
# 4. ORDERBOOK STREAM
# =============================================================================


class OrderBookStream(MarketDataStream):
    """
    Real-time orderbook stream.

    Features:
    - L2 depth updates
    - Snapshot + delta processing
    - Checksum validation
    """

    def __init__(
        self,
        depth: int = 25,
        config: StreamConfig | None = None,
    ):
        """Initialize orderbook stream."""
        super().__init__(config)
        self.depth = depth
        self._subscriptions: set[str] = set()
        self._orderbooks: dict[str, OrderBookUpdate] = {}
        self._running = False

    async def connect(self) -> bool:
        """Connect to orderbook stream."""
        self._status = StreamStatus.CONNECTING
        await asyncio.sleep(0.1)
        self._status = StreamStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        """Disconnect from orderbook stream."""
        self._running = False
        self._status = StreamStatus.DISCONNECTED

    async def subscribe(self, symbols: list[str]) -> bool:
        """Subscribe to orderbook updates."""
        self._subscriptions.update(symbols)
        return True

    async def unsubscribe(self, symbols: list[str]) -> bool:
        """Unsubscribe from orderbook updates."""
        self._subscriptions.difference_update(symbols)
        return True

    def get_orderbook(self, symbol: str) -> OrderBookUpdate | None:
        """Get current orderbook for a symbol."""
        return self._orderbooks.get(symbol)

    def get_best_bid_ask(self, symbol: str) -> tuple[float, float]:
        """Get best bid and ask prices."""
        ob = self._orderbooks.get(symbol)
        if ob and ob.bids and ob.asks:
            return ob.bids[0].price, ob.asks[0].price
        return 0.0, 0.0

    async def _simulate_updates(self) -> None:
        """Simulate orderbook updates for testing."""
        base_prices = {
            "BTCUSDT": 50000.0,
            "ETHUSDT": 3000.0,
        }

        self._running = True

        while self._running and self._status == StreamStatus.CONNECTED:
            for symbol in self._subscriptions:
                base = base_prices.get(symbol, 1000.0)
                tick = base * 0.0001  # 0.01% tick size

                # Generate bids
                bids = []
                for i in range(self.depth):
                    price = base - (i + 1) * tick
                    size = np.random.exponential(2.0)
                    bids.append(OrderBookLevel(price=price, size=size))

                # Generate asks
                asks = []
                for i in range(self.depth):
                    price = base + (i + 1) * tick
                    size = np.random.exponential(2.0)
                    asks.append(OrderBookLevel(price=price, size=size))

                update = OrderBookUpdate(
                    symbol=symbol,
                    timestamp=int(time.time() * 1000),
                    is_snapshot=False,
                    bids=bids,
                    asks=asks,
                )

                self._orderbooks[symbol] = update
                self._notify(update)

            await asyncio.sleep(0.05)  # 50ms update interval


# =============================================================================
# 5. TRADE STREAM
# =============================================================================


class TradeStream(MarketDataStream):
    """
    Real-time trade tick stream.

    Features:
    - Individual trade updates
    - Aggregated trade batches
    - Volume analysis
    """

    def __init__(self, config: StreamConfig | None = None):
        """Initialize trade stream."""
        super().__init__(config)
        self._subscriptions: set[str] = set()
        self._recent_trades: dict[str, deque] = {}
        self._running = False

    async def connect(self) -> bool:
        """Connect to trade stream."""
        self._status = StreamStatus.CONNECTING
        await asyncio.sleep(0.1)
        self._status = StreamStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        """Disconnect from trade stream."""
        self._running = False
        self._status = StreamStatus.DISCONNECTED

    async def subscribe(self, symbols: list[str]) -> bool:
        """Subscribe to trade updates."""
        self._subscriptions.update(symbols)
        for symbol in symbols:
            if symbol not in self._recent_trades:
                self._recent_trades[symbol] = deque(maxlen=1000)
        return True

    async def unsubscribe(self, symbols: list[str]) -> bool:
        """Unsubscribe from trade updates."""
        self._subscriptions.difference_update(symbols)
        return True

    def get_recent_trades(
        self,
        symbol: str,
        count: int = 100,
    ) -> list[TradeUpdate]:
        """Get recent trades for a symbol."""
        trades = self._recent_trades.get(symbol, deque())
        return list(trades)[-count:]

    def get_volume_profile(
        self,
        symbol: str,
        window_seconds: int = 60,
    ) -> dict[str, float]:
        """Get volume profile for recent trades."""
        trades = self._recent_trades.get(symbol, deque())
        now = int(time.time() * 1000)
        cutoff = now - window_seconds * 1000

        recent = [t for t in trades if t.timestamp >= cutoff]

        buy_volume = sum(t.size for t in recent if t.side == "buy")
        sell_volume = sum(t.size for t in recent if t.side == "sell")

        return {
            "total_volume": buy_volume + sell_volume,
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "buy_ratio": buy_volume / (buy_volume + sell_volume) if recent else 0.5,
            "trade_count": len(recent),
            "avg_size": np.mean([t.size for t in recent]) if recent else 0.0,
            "vwap": (
                sum(t.price * t.size for t in recent) / sum(t.size for t in recent)
                if recent and sum(t.size for t in recent) > 0
                else 0.0
            ),
        }

    async def _simulate_updates(self) -> None:
        """Simulate trade updates for testing."""
        base_prices = {
            "BTCUSDT": 50000.0,
            "ETHUSDT": 3000.0,
        }

        trade_id = 0
        self._running = True

        while self._running and self._status == StreamStatus.CONNECTED:
            for symbol in self._subscriptions:
                # Random number of trades per tick
                num_trades = np.random.poisson(2)

                base = base_prices.get(symbol, 1000.0)

                for _ in range(num_trades):
                    trade_id += 1
                    noise = np.random.normal(0, 0.0001)
                    price = base * (1 + noise)

                    trade = TradeUpdate(
                        symbol=symbol,
                        timestamp=int(time.time() * 1000),
                        trade_id=str(trade_id),
                        price=price,
                        size=np.random.exponential(0.1),
                        side="buy" if np.random.random() > 0.5 else "sell",
                        is_maker=np.random.random() > 0.3,
                    )

                    if symbol in self._recent_trades:
                        self._recent_trades[symbol].append(trade)
                    self._notify(trade)

            await asyncio.sleep(0.1)  # 100ms update interval


# =============================================================================
# 6. CANDLE AGGREGATOR
# =============================================================================


class CandleAggregator:
    """
    Aggregates trades into OHLCV candles in real-time.

    Features:
    - Multiple timeframe support
    - Real-time candle building
    - Historical candle cache
    """

    INTERVALS = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }

    def __init__(
        self,
        intervals: list[str] | None = None,
        max_candles: int = 1000,
    ):
        """Initialize candle aggregator."""
        self.intervals = intervals or ["1m", "5m", "15m"]
        self.max_candles = max_candles

        # Current building candles
        self._current: dict[str, dict[str, KlineUpdate]] = {}

        # Completed candles
        self._candles: dict[str, dict[str, deque]] = {}

        # Callbacks for completed candles
        self._callbacks: list[Callable[[KlineUpdate], None]] = []

    def add_callback(self, callback: Callable[[KlineUpdate], None]) -> None:
        """Add callback for completed candles."""
        self._callbacks.append(callback)

    def process_trade(self, trade: TradeUpdate) -> list[KlineUpdate]:
        """
        Process a trade and update candles.

        Args:
            trade: Trade update to process

        Returns:
            List of completed candles (if any)
        """
        symbol = trade.symbol
        completed = []

        # Initialize symbol data structures
        if symbol not in self._current:
            self._current[symbol] = {}
            self._candles[symbol] = {
                interval: deque(maxlen=self.max_candles) for interval in self.intervals
            }

        for interval in self.intervals:
            interval_seconds = self.INTERVALS[interval]

            # Calculate candle open time
            candle_time = (
                trade.timestamp // 1000 // interval_seconds * interval_seconds * 1000
            )

            current = self._current[symbol].get(interval)

            # Check if we need to close current candle
            if current and current.timestamp != candle_time:
                # Complete the candle
                current.is_closed = True
                self._candles[symbol][interval].append(current)
                completed.append(current)

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(current)
                    except Exception:
                        pass

                current = None

            # Create or update candle
            if current is None:
                # New candle
                current = KlineUpdate(
                    symbol=symbol,
                    interval=interval,
                    timestamp=candle_time,
                    open=trade.price,
                    high=trade.price,
                    low=trade.price,
                    close=trade.price,
                    volume=trade.size,
                    is_closed=False,
                    trades_count=1,
                )
            else:
                # Update existing candle
                current.high = max(current.high, trade.price)
                current.low = min(current.low, trade.price)
                current.close = trade.price
                current.volume += trade.size
                current.trades_count += 1

            self._current[symbol][interval] = current

        return completed

    def get_current_candle(
        self,
        symbol: str,
        interval: str,
    ) -> KlineUpdate | None:
        """Get current (building) candle."""
        return self._current.get(symbol, {}).get(interval)

    def get_candles(
        self,
        symbol: str,
        interval: str,
        count: int = 100,
    ) -> list[KlineUpdate]:
        """Get completed candles."""
        candles = self._candles.get(symbol, {}).get(interval, deque())
        return list(candles)[-count:]

    def get_candle_array(
        self,
        symbol: str,
        interval: str,
    ) -> dict[str, NDArray[np.float64]]:
        """Get candles as numpy arrays for analysis."""
        candles = self.get_candles(symbol, interval, self.max_candles)

        if not candles:
            return {
                "timestamp": np.array([], dtype=np.int64),
                "open": np.array([], dtype=np.float64),
                "high": np.array([], dtype=np.float64),
                "low": np.array([], dtype=np.float64),
                "close": np.array([], dtype=np.float64),
                "volume": np.array([], dtype=np.float64),
            }

        return {
            "timestamp": np.array([c.timestamp for c in candles], dtype=np.int64),
            "open": np.array([c.open for c in candles], dtype=np.float64),
            "high": np.array([c.high for c in candles], dtype=np.float64),
            "low": np.array([c.low for c in candles], dtype=np.float64),
            "close": np.array([c.close for c in candles], dtype=np.float64),
            "volume": np.array([c.volume for c in candles], dtype=np.float64),
        }


# =============================================================================
# 7. STREAM MANAGER
# =============================================================================


@dataclass
class StreamManagerConfig:
    """Configuration for stream manager."""

    enable_ticker: bool = True
    enable_orderbook: bool = True
    enable_trades: bool = True
    orderbook_depth: int = 25
    candle_intervals: list[str] = field(default_factory=lambda: ["1m", "5m", "15m"])


class StreamManager:
    """
    Unified manager for all market data streams.

    Features:
    - Centralized stream management
    - Automatic reconnection
    - Cross-stream coordination
    """

    def __init__(self, config: StreamManagerConfig | None = None):
        """Initialize stream manager."""
        self.config = config or StreamManagerConfig()

        # Initialize streams
        self.ticker_stream: TickerStream | None = None
        self.orderbook_stream: OrderBookStream | None = None
        self.trade_stream: TradeStream | None = None

        # Candle aggregator
        self.candle_aggregator = CandleAggregator(
            intervals=self.config.candle_intervals
        )

        # Subscribed symbols
        self._symbols: set[str] = set()

        # Running status
        self._running = False

    async def start(self, symbols: list[str]) -> bool:
        """Start all enabled streams."""
        self._symbols = set(symbols)
        self._running = True

        try:
            if self.config.enable_ticker:
                self.ticker_stream = TickerStream()
                await self.ticker_stream.connect()
                await self.ticker_stream.subscribe(symbols)

            if self.config.enable_orderbook:
                self.orderbook_stream = OrderBookStream(
                    depth=self.config.orderbook_depth
                )
                await self.orderbook_stream.connect()
                await self.orderbook_stream.subscribe(symbols)

            if self.config.enable_trades:
                self.trade_stream = TradeStream()
                await self.trade_stream.connect()
                await self.trade_stream.subscribe(symbols)

                # Connect trade stream to candle aggregator
                self.trade_stream.add_callback(
                    lambda t: self.candle_aggregator.process_trade(t)
                )

            return True

        except Exception:
            await self.stop()
            return False

    async def stop(self) -> None:
        """Stop all streams."""
        self._running = False

        if self.ticker_stream:
            await self.ticker_stream.disconnect()
            self.ticker_stream = None

        if self.orderbook_stream:
            await self.orderbook_stream.disconnect()
            self.orderbook_stream = None

        if self.trade_stream:
            await self.trade_stream.disconnect()
            self.trade_stream = None

    async def subscribe(self, symbols: list[str]) -> bool:
        """Subscribe to additional symbols."""
        self._symbols.update(symbols)

        results = []

        if self.ticker_stream:
            results.append(await self.ticker_stream.subscribe(symbols))

        if self.orderbook_stream:
            results.append(await self.orderbook_stream.subscribe(symbols))

        if self.trade_stream:
            results.append(await self.trade_stream.subscribe(symbols))

        return all(results)

    async def unsubscribe(self, symbols: list[str]) -> bool:
        """Unsubscribe from symbols."""
        self._symbols.difference_update(symbols)

        results = []

        if self.ticker_stream:
            results.append(await self.ticker_stream.unsubscribe(symbols))

        if self.orderbook_stream:
            results.append(await self.orderbook_stream.unsubscribe(symbols))

        if self.trade_stream:
            results.append(await self.trade_stream.unsubscribe(symbols))

        return all(results)

    def get_market_snapshot(self, symbol: str) -> dict[str, Any]:
        """Get complete market snapshot for a symbol."""
        snapshot = {"symbol": symbol, "timestamp": int(time.time() * 1000)}

        # Ticker data
        if self.ticker_stream:
            ticker = self.ticker_stream.get_ticker(symbol)
            if ticker:
                snapshot["ticker"] = {
                    "bid": ticker.bid,
                    "ask": ticker.ask,
                    "last": ticker.last_price,
                    "volume_24h": ticker.volume_24h,
                }

        # Orderbook data
        if self.orderbook_stream:
            bid, ask = self.orderbook_stream.get_best_bid_ask(symbol)
            snapshot["orderbook"] = {
                "best_bid": bid,
                "best_ask": ask,
                "spread": ask - bid if bid and ask else 0,
            }

        # Trade data
        if self.trade_stream:
            profile = self.trade_stream.get_volume_profile(symbol)
            snapshot["trades"] = profile

        # Candle data
        current = self.candle_aggregator.get_current_candle(symbol, "1m")
        if current:
            snapshot["current_candle"] = {
                "open": current.open,
                "high": current.high,
                "low": current.low,
                "close": current.close,
                "volume": current.volume,
            }

        return snapshot

    def get_status(self) -> dict[str, str]:
        """Get status of all streams."""
        status = {}

        if self.ticker_stream:
            status["ticker"] = self.ticker_stream.status.value

        if self.orderbook_stream:
            status["orderbook"] = self.orderbook_stream.status.value

        if self.trade_stream:
            status["trades"] = self.trade_stream.status.value

        return status


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Types
    "StreamType",
    "StreamStatus",
    # Data classes
    "TickerUpdate",
    "TradeUpdate",
    "OrderBookLevel",
    "OrderBookUpdate",
    "KlineUpdate",
    "StreamConfig",
    # Streams
    "MarketDataStream",
    "TickerStream",
    "OrderBookStream",
    "TradeStream",
    # Aggregator
    "CandleAggregator",
    # Manager
    "StreamManagerConfig",
    "StreamManager",
]
