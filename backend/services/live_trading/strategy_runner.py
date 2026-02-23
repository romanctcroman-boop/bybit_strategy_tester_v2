"""
Live Strategy Runner for Real-Time Trading.

Executes trading strategies in real-time using live market data.

Features:
- Strategy signal generation from live data
- Order execution based on signals
- Position management and tracking
- Risk management integration
- Performance tracking and logging
"""

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from backend.services.live_trading.bybit_websocket import (
    BybitWebSocketClient,
    WebSocketMessage,
    parse_kline_message,
    parse_trade_message,
)
from backend.services.live_trading.order_executor import OrderExecutor
from backend.services.live_trading.position_manager import PositionManager
from backend.services.trading_engine_interface import OrderSide, OrderType

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal type."""

    BUY = "buy"
    SELL = "sell"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    CLOSE_ALL = "close_all"
    HOLD = "hold"


@dataclass
class TradingSignal:
    """Trading signal from strategy."""

    signal_type: SignalType
    symbol: str
    price: float = 0.0
    qty: float | None = None  # None = use position sizing rules
    stop_loss: float | None = None
    take_profit: float | None = None
    confidence: float = 1.0  # 0.0 - 1.0
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = field(default_factory=dict)


@dataclass
class StrategyConfig:
    """Strategy configuration."""

    name: str
    symbol: str
    timeframe: str = "1"  # Kline interval

    # Position sizing
    position_size_percent: float = 5.0  # % of equity per trade
    max_position_size: float = 0.0  # Max position size (0 = no limit)
    leverage: float = 1.0

    # Risk management
    stop_loss_percent: float | None = 2.0  # % below entry
    take_profit_percent: float | None = 4.0  # % above entry
    max_daily_loss: float = 100.0  # Max daily loss in quote currency
    max_open_trades: int = 1

    # Execution
    order_type: OrderType = OrderType.MARKET
    cooldown_seconds: int = 60  # Min time between trades

    # Paper trading
    paper_trading: bool = False


@dataclass
class StrategyState:
    """Runtime state of a strategy."""

    is_running: bool = False
    last_signal_time: datetime | None = None
    last_trade_time: datetime | None = None
    signals_generated: int = 0
    trades_executed: int = 0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    win_count: int = 0
    loss_count: int = 0

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        total = self.win_count + self.loss_count
        if total == 0:
            return 0.0
        return self.win_count / total * 100


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.

    Implement on_candle() to generate trading signals based on price data.
    """

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.state = StrategyState()

        # Price history
        self._candles: list[dict] = []
        self._max_candles = 500

        # Indicators cache
        self._indicators: dict[str, Any] = {}

    @abstractmethod
    def on_candle(self, candle: dict) -> TradingSignal | None:
        """
        Called on each new candle. Return a signal or None.

        Args:
            candle: Dict with keys: open, high, low, close, volume, time

        Returns:
            TradingSignal or None
        """
        pass

    def on_trade(self, trade: dict) -> TradingSignal | None:
        """
        Called on each public trade tick. Override for tick-based strategies.

        Args:
            trade: Dict with keys: time, price, qty, side

        Returns:
            TradingSignal or None
        """
        return None

    def on_start(self):
        """Called when strategy starts. Override to initialize."""
        pass

    def on_stop(self):
        """Called when strategy stops. Override to cleanup."""
        pass

    def add_candle(self, candle: dict):
        """Add a candle to history."""
        self._candles.append(candle)
        if len(self._candles) > self._max_candles:
            self._candles = self._candles[-self._max_candles :]

    def get_candles(self, n: int = 0) -> list[dict]:
        """Get last n candles (0 = all)."""
        if n <= 0:
            return self._candles
        return self._candles[-n:]

    def get_closes(self, n: int = 0) -> list[float]:
        """Get close prices."""
        candles = self.get_candles(n)
        return [c["close"] for c in candles]

    def get_highs(self, n: int = 0) -> list[float]:
        """Get high prices."""
        candles = self.get_candles(n)
        return [c["high"] for c in candles]

    def get_lows(self, n: int = 0) -> list[float]:
        """Get low prices."""
        candles = self.get_candles(n)
        return [c["low"] for c in candles]

    def get_volumes(self, n: int = 0) -> list[float]:
        """Get volumes."""
        candles = self.get_candles(n)
        return [c.get("volume", 0) for c in candles]

    # ==========================================================================
    # Common Indicators
    # ==========================================================================

    def sma(self, period: int, prices: list[float] | None = None) -> float:
        """Simple Moving Average."""
        prices = prices or self.get_closes(period)
        if len(prices) < period:
            return 0.0
        return sum(prices[-period:]) / period

    def ema(self, period: int, prices: list[float] | None = None) -> float:
        """Exponential Moving Average."""
        prices = prices or self.get_closes()
        if len(prices) < period:
            return 0.0

        multiplier = 2 / (period + 1)
        ema_value = prices[0]

        for price in prices[1:]:
            ema_value = (price * multiplier) + (ema_value * (1 - multiplier))

        return ema_value

    def rsi(self, period: int = 14, prices: list[float] | None = None) -> float:
        """Relative Strength Index."""
        prices = prices or self.get_closes()
        if len(prices) < period + 1:
            return 50.0  # Neutral

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi_value = 100 - (100 / (1 + rs))

        return rsi_value

    def bollinger_bands(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        prices: list[float] | None = None,
    ) -> tuple[float, float, float]:
        """Bollinger Bands. Returns (upper, middle, lower)."""
        prices = prices or self.get_closes(period)
        if len(prices) < period:
            return (0.0, 0.0, 0.0)

        middle = sum(prices[-period:]) / period

        variance = sum((p - middle) ** 2 for p in prices[-period:]) / period
        std = variance**0.5

        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)

        return (upper, middle, lower)

    def atr(self, period: int = 14) -> float:
        """Average True Range."""
        candles = self.get_candles(period + 1)
        if len(candles) < period + 1:
            return 0.0

        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i]["high"]
            low = candles[i]["low"]
            prev_close = candles[i - 1]["close"]

            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        return sum(true_ranges[-period:]) / period

    def macd(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        prices: list[float] | None = None,
    ) -> tuple[float, float, float]:
        """MACD. Returns (macd_line, signal_line, histogram)."""
        prices = prices or self.get_closes()
        if len(prices) < slow:
            return (0.0, 0.0, 0.0)

        # Calculate EMAs
        fast_ema = self.ema(fast, prices)
        slow_ema = self.ema(slow, prices)

        macd_line = fast_ema - slow_ema

        # Signal line (simplified - should use macd history)
        signal_line = macd_line * 0.9  # Approximation

        histogram = macd_line - signal_line

        return (macd_line, signal_line, histogram)


class LiveStrategyRunner:
    """
    Live Strategy Runner - executes strategies in real-time.

    Usage:
        runner = LiveStrategyRunner(
            api_key="your_key",
            api_secret="your_secret",
            testnet=True
        )

        # Add strategy
        strategy = MyStrategy(config)
        runner.add_strategy(strategy)

        # Start trading
        await runner.start()

        # Stop trading
        await runner.stop()
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        paper_trading: bool = True,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.paper_trading = paper_trading

        # Components
        self._ws_client = BybitWebSocketClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
        )

        self._executor = OrderExecutor(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
        )

        self._position_manager = PositionManager(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
        )

        # Strategies
        self._strategies: dict[str, BaseStrategy] = {}

        # State
        self._running = False
        self._tasks: list[asyncio.Task] = []

        # Callbacks
        self._signal_callbacks: list[Callable] = []
        self._trade_callbacks: list[Callable] = []

        # Paper trading state
        self._paper_positions: dict[str, dict] = {}
        self._paper_balance: float = 10000.0  # Starting balance

        logger.info(
            f"LiveStrategyRunner initialized (testnet={testnet}, paper={paper_trading})"
        )

    def add_strategy(self, strategy: BaseStrategy):
        """Add a strategy to run."""
        key = f"{strategy.config.symbol}_{strategy.config.name}"
        self._strategies[key] = strategy
        logger.info(f"Strategy added: {key}")

    def remove_strategy(self, name: str, symbol: str):
        """Remove a strategy."""
        key = f"{symbol}_{name}"
        if key in self._strategies:
            del self._strategies[key]
            logger.info(f"Strategy removed: {key}")

    async def start(self):
        """Start all strategies."""
        if self._running:
            logger.warning("Runner already started")
            return

        self._running = True

        # Connect WebSocket
        connected = await self._ws_client.connect()
        if not connected:
            raise RuntimeError("Failed to connect WebSocket")

        # Start position manager (for real trading)
        if not self.paper_trading:
            await self._position_manager.start()

        # Subscribe to market data for each strategy
        for key, strategy in self._strategies.items():
            symbol = strategy.config.symbol
            timeframe = strategy.config.timeframe

            # Subscribe to klines
            await self._ws_client.subscribe_klines(symbol, timeframe)

            # Subscribe to trades for tick-based strategies
            await self._ws_client.subscribe_trades(symbol)

            # Call strategy on_start
            strategy.on_start()
            strategy.state.is_running = True

            logger.info(f"Strategy {key} started on {symbol} {timeframe}m")

        # Start processing loop
        self._tasks.append(asyncio.create_task(self._process_market_data()))

        logger.info(
            f"✅ LiveStrategyRunner started with {len(self._strategies)} strategies"
        )

    async def stop(self):
        """Stop all strategies."""
        self._running = False

        # Stop strategies
        for _key, strategy in self._strategies.items():
            strategy.on_stop()
            strategy.state.is_running = False

        # Cancel tasks
        for task in self._tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

        # Disconnect
        await self._ws_client.disconnect()

        if not self.paper_trading:
            await self._position_manager.stop()

        await self._executor.close()

        logger.info("LiveStrategyRunner stopped")

    async def _process_market_data(self):
        """Process incoming market data and run strategies."""
        async for message in self._ws_client.messages():
            if not self._running:
                break

            try:
                topic = message.topic

                if topic.startswith("kline."):
                    await self._process_kline(message)
                elif topic.startswith("publicTrade."):
                    await self._process_trade(message)

            except Exception as e:
                logger.error(f"Error processing market data: {e}")

    async def _process_kline(self, message: WebSocketMessage):
        """Process kline/candle update."""
        # Extract symbol and interval from topic
        # Format: kline.{interval}.{symbol}
        parts = message.topic.split(".")
        if len(parts) < 3:
            return

        interval = parts[1]
        symbol = parts[2]

        candles = parse_kline_message(message)

        for candle_data in candles:
            # Only process confirmed candles
            if not candle_data.get("confirm", False):
                continue

            candle = {
                "time": candle_data["start"],
                "open": candle_data["open"],
                "high": candle_data["high"],
                "low": candle_data["low"],
                "close": candle_data["close"],
                "volume": candle_data["volume"],
            }

            # Run matching strategies
            for _key, strategy in self._strategies.items():
                if (
                    strategy.config.symbol == symbol
                    and strategy.config.timeframe == interval
                ):
                    # Add candle to history
                    strategy.add_candle(candle)

                    # Generate signal
                    signal = strategy.on_candle(candle)

                    if signal and signal.signal_type != SignalType.HOLD:
                        await self._process_signal(strategy, signal)

    async def _process_trade(self, message: WebSocketMessage):
        """Process public trade tick."""
        # Extract symbol from topic
        parts = message.topic.split(".")
        if len(parts) < 2:
            return

        symbol = parts[1]
        trades = parse_trade_message(message)

        for trade_data in trades:
            trade = {
                "time": trade_data["time"],
                "price": trade_data["price"],
                "qty": trade_data["qty"],
                "side": trade_data["side"],
            }

            # Run matching strategies
            for _key, strategy in self._strategies.items():
                if strategy.config.symbol == symbol:
                    signal = strategy.on_trade(trade)

                    if signal and signal.signal_type != SignalType.HOLD:
                        await self._process_signal(strategy, signal)

    async def _process_signal(self, strategy: BaseStrategy, signal: TradingSignal):
        """Process a trading signal."""
        config = strategy.config
        state = strategy.state

        state.signals_generated += 1
        state.last_signal_time = datetime.now(UTC)

        logger.info(
            f"📊 Signal: {signal.signal_type.value} {signal.symbol} "
            f"@ {signal.price:.2f} (confidence: {signal.confidence:.0%}, "
            f"reason: {signal.reason})"
        )

        # Notify callbacks
        for callback in self._signal_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal)
                else:
                    callback(signal)
            except Exception as e:
                logger.error(f"Signal callback error: {e}")

        # Check cooldown
        if state.last_trade_time:
            elapsed = (
                datetime.now(UTC) - state.last_trade_time
            ).total_seconds()
            if elapsed < config.cooldown_seconds:
                logger.debug("Cooldown active, skipping signal")
                return

        # Check daily loss limit
        if state.daily_pnl < -config.max_daily_loss:
            logger.warning("Daily loss limit reached, skipping signal")
            return

        # Execute signal
        if self.paper_trading or config.paper_trading:
            await self._execute_paper_trade(strategy, signal)
        else:
            await self._execute_real_trade(strategy, signal)

    async def _execute_paper_trade(
        self,
        strategy: BaseStrategy,
        signal: TradingSignal,
    ):
        """Execute a paper trade."""
        config = strategy.config
        state = strategy.state
        symbol = signal.symbol

        # Calculate position size
        if signal.qty:
            qty = signal.qty
        else:
            # Use position sizing rules
            position_value = self._paper_balance * (config.position_size_percent / 100)
            qty = position_value / signal.price

        if signal.signal_type == SignalType.BUY:
            # Open long position
            if symbol in self._paper_positions:
                logger.info(f"Paper: Already have position in {symbol}")
                return

            self._paper_positions[symbol] = {
                "side": "long",
                "entry_price": signal.price,
                "qty": qty,
                "sl": signal.stop_loss
                or (signal.price * (1 - config.stop_loss_percent / 100))
                if config.stop_loss_percent
                else None,
                "tp": signal.take_profit
                or (signal.price * (1 + config.take_profit_percent / 100))
                if config.take_profit_percent
                else None,
            }

            logger.info(
                f"📝 Paper LONG: {symbol} {qty:.4f} @ {signal.price:.2f} "
                f"(SL: {self._paper_positions[symbol]['sl']:.2f}, "
                f"TP: {self._paper_positions[symbol]['tp']:.2f})"
            )

        elif signal.signal_type == SignalType.SELL:
            # Open short position
            if symbol in self._paper_positions:
                logger.info(f"Paper: Already have position in {symbol}")
                return

            self._paper_positions[symbol] = {
                "side": "short",
                "entry_price": signal.price,
                "qty": qty,
                "sl": signal.stop_loss
                or (signal.price * (1 + config.stop_loss_percent / 100))
                if config.stop_loss_percent
                else None,
                "tp": signal.take_profit
                or (signal.price * (1 - config.take_profit_percent / 100))
                if config.take_profit_percent
                else None,
            }

            logger.info(f"📝 Paper SHORT: {symbol} {qty:.4f} @ {signal.price:.2f}")

        elif signal.signal_type in (
            SignalType.CLOSE_LONG,
            SignalType.CLOSE_SHORT,
            SignalType.CLOSE_ALL,
        ):
            # Close position
            if symbol not in self._paper_positions:
                logger.info(f"Paper: No position to close for {symbol}")
                return

            pos = self._paper_positions[symbol]

            # Calculate P&L
            if pos["side"] == "long":
                pnl = (signal.price - pos["entry_price"]) * pos["qty"]
            else:
                pnl = (pos["entry_price"] - signal.price) * pos["qty"]

            state.total_pnl += pnl
            state.daily_pnl += pnl
            self._paper_balance += pnl

            if pnl > 0:
                state.win_count += 1
            else:
                state.loss_count += 1

            logger.info(
                f"📝 Paper CLOSE: {symbol} PnL: {pnl:+.2f} "
                f"(Balance: {self._paper_balance:.2f})"
            )

            del self._paper_positions[symbol]

        state.trades_executed += 1
        state.last_trade_time = datetime.now(UTC)

        # Notify callbacks
        for callback in self._trade_callbacks:
            try:
                trade_info = {
                    "signal": signal,
                    "paper": True,
                    "pnl": 0,  # Set for close trades
                }
                if asyncio.iscoroutinefunction(callback):
                    await callback(trade_info)
                else:
                    callback(trade_info)
            except Exception as e:
                logger.error(f"Trade callback error: {e}")

    async def _execute_real_trade(
        self,
        strategy: BaseStrategy,
        signal: TradingSignal,
    ):
        """Execute a real trade."""
        config = strategy.config
        state = strategy.state
        symbol = signal.symbol

        # Get current position
        position = self._position_manager.get_position(symbol)

        # Calculate position size
        if signal.qty:
            qty = signal.qty
        else:
            equity = self._position_manager.get_equity()
            position_value = equity * (config.position_size_percent / 100)
            qty = position_value / signal.price

        # Calculate SL/TP
        sl_price = signal.stop_loss
        tp_price = signal.take_profit

        if not sl_price and config.stop_loss_percent:
            if signal.signal_type == SignalType.BUY:
                sl_price = signal.price * (1 - config.stop_loss_percent / 100)
            else:
                sl_price = signal.price * (1 + config.stop_loss_percent / 100)

        if not tp_price and config.take_profit_percent:
            if signal.signal_type == SignalType.BUY:
                tp_price = signal.price * (1 + config.take_profit_percent / 100)
            else:
                tp_price = signal.price * (1 - config.take_profit_percent / 100)

        result = None

        if signal.signal_type == SignalType.BUY:
            if position:
                logger.info(f"Already have position in {symbol}")
                return

            result = await self._executor.place_market_order(
                symbol=symbol,
                side=OrderSide.BUY,
                qty=qty,
                stop_loss=sl_price,
                take_profit=tp_price,
            )

        elif signal.signal_type == SignalType.SELL:
            if position:
                logger.info(f"Already have position in {symbol}")
                return

            result = await self._executor.place_market_order(
                symbol=symbol,
                side=OrderSide.SELL,
                qty=qty,
                stop_loss=sl_price,
                take_profit=tp_price,
            )

        elif signal.signal_type in (
            SignalType.CLOSE_LONG,
            SignalType.CLOSE_SHORT,
            SignalType.CLOSE_ALL,
        ):
            if not position:
                logger.info(f"No position to close for {symbol}")
                return

            success = await self._position_manager.close_position(symbol)
            result = type("Result", (), {"success": success})()

        if result and result.success:
            state.trades_executed += 1
            state.last_trade_time = datetime.now(UTC)

            logger.info(
                f"✅ Trade executed: {signal.signal_type.value} {symbol} "
                f"{qty:.4f} @ {signal.price:.2f}"
            )
        elif result:
            logger.error(
                f"❌ Trade failed: {getattr(result, 'error_message', 'Unknown error')}"
            )

    # ==========================================================================
    # Callbacks
    # ==========================================================================

    def on_signal(self, callback: Callable):
        """Register callback for signals."""
        self._signal_callbacks.append(callback)

    def on_trade(self, callback: Callable):
        """Register callback for trades."""
        self._trade_callbacks.append(callback)

    # ==========================================================================
    # Status & Monitoring
    # ==========================================================================

    def get_status(self) -> dict:
        """Get runner status."""
        strategies_status = {}
        for key, strategy in self._strategies.items():
            strategies_status[key] = {
                "is_running": strategy.state.is_running,
                "signals_generated": strategy.state.signals_generated,
                "trades_executed": strategy.state.trades_executed,
                "daily_pnl": strategy.state.daily_pnl,
                "total_pnl": strategy.state.total_pnl,
                "win_rate": strategy.state.win_rate,
                "last_signal": strategy.state.last_signal_time.isoformat()
                if strategy.state.last_signal_time
                else None,
                "last_trade": strategy.state.last_trade_time.isoformat()
                if strategy.state.last_trade_time
                else None,
            }

        return {
            "running": self._running,
            "paper_trading": self.paper_trading,
            "paper_balance": self._paper_balance if self.paper_trading else None,
            "paper_positions": self._paper_positions if self.paper_trading else None,
            "strategies": strategies_status,
            "websocket_connected": self._ws_client.is_connected,
        }

    def get_paper_balance(self) -> float:
        """Get paper trading balance."""
        return self._paper_balance

    def set_paper_balance(self, balance: float):
        """Set paper trading balance."""
        self._paper_balance = balance
