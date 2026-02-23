"""
Bybit WebSocket Client for Live Trading.

Connects to Bybit V5 WebSocket API for real-time:
- Market data (klines, trades, orderbook, tickers)
- Private data (orders, positions, executions, wallet)

Features:
- Automatic reconnection with exponential backoff
- Heartbeat/ping-pong for connection health
- Thread-safe message queue for data distribution
- Multiple subscription support
"""

import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import time
from asyncio import Queue
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

import websockets
from websockets import ClientConnection

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """WebSocket channel types."""

    # Public channels
    KLINE = "kline"
    TRADE = "publicTrade"
    ORDERBOOK = "orderbook"
    TICKER = "tickers"
    LIQUIDATION = "liquidation"

    # Private channels
    POSITION = "position"
    EXECUTION = "execution"
    ORDER = "order"
    WALLET = "wallet"
    GREEK = "greeks"


@dataclass
class WebSocketMessage:
    """Parsed WebSocket message."""

    topic: str
    data: Any
    timestamp: int
    type: str = "snapshot"  # snapshot or delta
    raw: dict = field(default_factory=dict)


@dataclass
class SubscriptionConfig:
    """Subscription configuration."""

    channel: ChannelType
    symbol: str | None = None
    interval: str | None = None  # For klines: 1, 5, 15, 60, etc.
    depth: int = 50  # For orderbook: 1, 50, 200, 500


class BybitWebSocketClient:
    """
    Bybit V5 WebSocket Client for live trading.

    Usage:
        client = BybitWebSocketClient(
            api_key="your_key",
            api_secret="your_secret",
            testnet=False
        )

        # Subscribe to market data
        await client.subscribe_klines("BTCUSDT", "1")
        await client.subscribe_trades("BTCUSDT")

        # Subscribe to private data (requires authentication)
        await client.subscribe_positions()
        await client.subscribe_orders()

        # Start receiving messages
        async for message in client.messages():
            print(message)
    """

    # Bybit WebSocket endpoints
    PUBLIC_MAINNET = "wss://stream.bybit.com/v5/public/linear"
    PUBLIC_TESTNET = "wss://stream-testnet.bybit.com/v5/public/linear"
    PRIVATE_MAINNET = "wss://stream.bybit.com/v5/private"
    PRIVATE_TESTNET = "wss://stream-testnet.bybit.com/v5/private"

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        testnet: bool = False,
        category: str = "linear",  # linear, inverse, spot, option
        max_reconnect_attempts: int = 10,
        reconnect_delay: float = 1.0,
        ping_interval: float = 20.0,
    ):
        # Store encrypted credentials (XOR with session key for basic obfuscation)
        # NOTE: For production, use proper secrets management (Vault, AWS Secrets, etc.)
        self._session_key = uuid4().bytes[:16]  # 16-byte random key
        self._api_key_encrypted = self._xor_encrypt(api_key.encode(), self._session_key) if api_key else b""
        self._api_secret_encrypted = self._xor_encrypt(api_secret.encode(), self._session_key) if api_secret else b""

        self.testnet = testnet
        self.category = category
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.ping_interval = ping_interval

        # WebSocket connections
        self._public_ws: ClientConnection | None = None
        self._private_ws: ClientConnection | None = None

        # Message queue for consumers
        self._message_queue: Queue[WebSocketMessage] = Queue()

        # Subscription tracking
        self._public_subscriptions: set[str] = set()
        self._private_subscriptions: set[str] = set()

        # Connection state
        self._running = False
        self._authenticated = False
        self._reconnect_count = 0

        # Callbacks
        self._callbacks: dict[str, list[Callable]] = {}

        # Background tasks
        self._tasks: list[asyncio.Task] = []

        logger.info(f"BybitWebSocketClient initialized (testnet={testnet}, category={category})")

    @staticmethod
    def _xor_encrypt(data: bytes, key: bytes) -> bytes:
        """Simple XOR encryption for in-memory credential obfuscation."""
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

    @property
    def api_key(self) -> str | None:
        """Decrypt and return API key."""
        if not self._api_key_encrypted:
            return None
        return self._xor_encrypt(self._api_key_encrypted, self._session_key).decode()

    @property
    def api_secret(self) -> str | None:
        """Decrypt and return API secret."""
        if not self._api_secret_encrypted:
            return None
        return self._xor_encrypt(self._api_secret_encrypted, self._session_key).decode()

    @property
    def public_url(self) -> str:
        """Get public WebSocket URL."""
        base = self.PUBLIC_TESTNET if self.testnet else self.PUBLIC_MAINNET
        return base.replace("/linear", f"/{self.category}")

    @property
    def private_url(self) -> str:
        """Get private WebSocket URL."""
        return self.PRIVATE_TESTNET if self.testnet else self.PRIVATE_MAINNET

    async def connect(self) -> bool:
        """
        Connect to Bybit WebSocket.

        Returns True if connection successful.
        """
        try:
            self._running = True

            # Connect to public stream
            logger.info(f"Connecting to public WebSocket: {self.public_url}")
            self._public_ws = await websockets.connect(
                self.public_url,
                ping_interval=self.ping_interval,
                ping_timeout=10.0,
            )
            logger.info("✅ Public WebSocket connected")

            # Connect to private stream if credentials provided
            if self.api_key and self.api_secret:
                logger.info(f"Connecting to private WebSocket: {self.private_url}")
                self._private_ws = await websockets.connect(
                    self.private_url,
                    ping_interval=self.ping_interval,
                    ping_timeout=10.0,
                )
                logger.info("✅ Private WebSocket connected")

                # Authenticate
                await self._authenticate()

            # Start background tasks
            self._tasks.append(asyncio.create_task(self._receive_public_messages()))
            if self._private_ws:
                self._tasks.append(asyncio.create_task(self._receive_private_messages()))

            self._reconnect_count = 0
            return True

        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            return await self._handle_reconnect()

    async def disconnect(self):
        """Disconnect from WebSocket."""
        self._running = False

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

        # Close connections
        if self._public_ws:
            await self._public_ws.close()
            self._public_ws = None
        if self._private_ws:
            await self._private_ws.close()
            self._private_ws = None

        self._authenticated = False
        logger.info("WebSocket disconnected")

    async def _authenticate(self):
        """Authenticate private WebSocket connection."""
        if not self._private_ws or not self.api_key or not self.api_secret:
            return

        expires = int((time.time() + 10) * 1000)  # 10 seconds expiry
        signature = self._generate_signature(expires)

        auth_message = {"op": "auth", "args": [self.api_key, expires, signature]}

        await self._private_ws.send(json.dumps(auth_message))

        # Wait for auth response
        response = await self._private_ws.recv()
        data = json.loads(response)

        if data.get("success"):
            self._authenticated = True
            logger.info("✅ WebSocket authenticated successfully")
        else:
            logger.error(f"❌ WebSocket authentication failed: {data}")
            raise Exception(f"Authentication failed: {data.get('ret_msg', 'Unknown error')}")

    def _generate_signature(self, expires: int) -> str:
        """Generate HMAC signature for authentication."""
        param_str = f"GET/realtime{expires}"
        return hmac.new(self.api_secret.encode("utf-8"), param_str.encode("utf-8"), hashlib.sha256).hexdigest()

    async def _handle_reconnect(self) -> bool:
        """Handle reconnection with exponential backoff."""
        if not self._running:
            return False

        self._reconnect_count += 1

        if self._reconnect_count > self.max_reconnect_attempts:
            logger.error(f"Max reconnect attempts ({self.max_reconnect_attempts}) reached. Giving up.")
            return False

        delay = self.reconnect_delay * (2 ** (self._reconnect_count - 1))
        delay = min(delay, 60.0)  # Max 60 seconds

        logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_count}/{self.max_reconnect_attempts})")
        await asyncio.sleep(delay)

        return await self.connect()

    # ==========================================================================
    # Public Subscriptions
    # ==========================================================================

    async def subscribe_klines(self, symbol: str, interval: str = "1"):
        """
        Subscribe to kline/candlestick updates.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Kline interval (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
        """
        topic = f"kline.{interval}.{symbol}"
        await self._subscribe_public(topic)

    async def subscribe_trades(self, symbol: str):
        """Subscribe to public trades."""
        topic = f"publicTrade.{symbol}"
        await self._subscribe_public(topic)

    async def subscribe_orderbook(self, symbol: str, depth: int = 50):
        """
        Subscribe to orderbook updates.

        Args:
            symbol: Trading pair
            depth: Orderbook depth (1, 50, 200, 500)
        """
        topic = f"orderbook.{depth}.{symbol}"
        await self._subscribe_public(topic)

    async def subscribe_ticker(self, symbol: str):
        """Subscribe to ticker updates."""
        topic = f"tickers.{symbol}"
        await self._subscribe_public(topic)

    async def subscribe_liquidations(self, symbol: str):
        """Subscribe to liquidation events."""
        topic = f"liquidation.{symbol}"
        await self._subscribe_public(topic)

    async def _subscribe_public(self, topic: str):
        """Subscribe to a public topic."""
        if not self._public_ws:
            raise RuntimeError("Public WebSocket not connected")

        if topic in self._public_subscriptions:
            logger.debug(f"Already subscribed to {topic}")
            return

        message = {"op": "subscribe", "args": [topic]}

        await self._public_ws.send(json.dumps(message))
        self._public_subscriptions.add(topic)
        logger.info(f"📡 Subscribed to public topic: {topic}")

    async def unsubscribe_public(self, topic: str):
        """Unsubscribe from a public topic."""
        if not self._public_ws or topic not in self._public_subscriptions:
            return

        message = {"op": "unsubscribe", "args": [topic]}

        await self._public_ws.send(json.dumps(message))
        self._public_subscriptions.discard(topic)
        logger.info(f"📡 Unsubscribed from public topic: {topic}")

    # ==========================================================================
    # Private Subscriptions (requires authentication)
    # ==========================================================================

    async def subscribe_positions(self):
        """Subscribe to position updates."""
        await self._subscribe_private("position")

    async def subscribe_executions(self):
        """Subscribe to execution/fill updates."""
        await self._subscribe_private("execution")

    async def subscribe_orders(self):
        """Subscribe to order updates."""
        await self._subscribe_private("order")

    async def subscribe_wallet(self):
        """Subscribe to wallet/balance updates."""
        await self._subscribe_private("wallet")

    async def subscribe_all_private(self):
        """Subscribe to all private channels."""
        await self.subscribe_positions()
        await self.subscribe_executions()
        await self.subscribe_orders()
        await self.subscribe_wallet()

    async def _subscribe_private(self, topic: str):
        """Subscribe to a private topic."""
        if not self._private_ws:
            raise RuntimeError("Private WebSocket not connected")

        if not self._authenticated:
            raise RuntimeError("WebSocket not authenticated")

        if topic in self._private_subscriptions:
            logger.debug(f"Already subscribed to private:{topic}")
            return

        message = {"op": "subscribe", "args": [topic]}

        await self._private_ws.send(json.dumps(message))
        self._private_subscriptions.add(topic)
        logger.info(f"🔒 Subscribed to private topic: {topic}")

    # ==========================================================================
    # Message Handling
    # ==========================================================================

    async def _receive_public_messages(self):
        """Receive and process public WebSocket messages."""
        while self._running and self._public_ws:
            try:
                raw = await self._public_ws.recv()
                await self._process_message(raw, is_private=False)
            except websockets.ConnectionClosed:
                logger.warning("Public WebSocket connection closed")
                if self._running:
                    await self._handle_reconnect()
                break
            except Exception as e:
                logger.error(f"Error receiving public message: {e}")

    async def _receive_private_messages(self):
        """Receive and process private WebSocket messages."""
        while self._running and self._private_ws:
            try:
                raw = await self._private_ws.recv()
                await self._process_message(raw, is_private=True)
            except websockets.ConnectionClosed:
                logger.warning("Private WebSocket connection closed")
                if self._running:
                    await self._handle_reconnect()
                break
            except Exception as e:
                logger.error(f"Error receiving private message: {e}")

    async def _process_message(self, raw: str, is_private: bool):
        """Process incoming WebSocket message."""
        try:
            data = json.loads(raw)

            # Handle system messages
            if "success" in data:
                if data.get("op") == "subscribe":
                    logger.debug(f"Subscription confirmed: {data}")
                elif data.get("op") == "auth":
                    logger.debug(f"Auth response: {data}")
                return

            # Handle pong
            if data.get("op") == "pong":
                return

            # Parse data message
            topic = data.get("topic", "")
            msg_data = data.get("data", [])
            msg_type = data.get("type", "snapshot")
            ts = data.get("ts", int(time.time() * 1000))

            if not topic:
                return

            message = WebSocketMessage(topic=topic, data=msg_data, timestamp=ts, type=msg_type, raw=data)

            # Put in queue for consumers
            await self._message_queue.put(message)

            # Call registered callbacks
            await self._dispatch_callbacks(message)

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {raw[:100]}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def _dispatch_callbacks(self, message: WebSocketMessage):
        """Dispatch message to registered callbacks."""
        topic = message.topic

        # Exact match callbacks
        if topic in self._callbacks:
            for callback in self._callbacks[topic]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    logger.error(f"Callback error for {topic}: {e}")

        # Wildcard callbacks (e.g., "kline.*" for all klines)
        for pattern, callbacks in self._callbacks.items():
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if topic.startswith(prefix):
                    for callback in callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(message)
                            else:
                                callback(message)
                        except Exception as e:
                            logger.error(f"Wildcard callback error for {pattern}: {e}")

    def register_callback(self, topic: str, callback: Callable):
        """
        Register a callback for a topic.

        Args:
            topic: Topic pattern (e.g., "kline.1.BTCUSDT" or "kline.*")
            callback: Async or sync callback function
        """
        if topic not in self._callbacks:
            self._callbacks[topic] = []
        self._callbacks[topic].append(callback)
        logger.debug(f"Registered callback for topic: {topic}")

    def unregister_callback(self, topic: str, callback: Callable):
        """Unregister a callback."""
        if topic in self._callbacks:
            self._callbacks[topic] = [cb for cb in self._callbacks[topic] if cb != callback]

    async def messages(self):
        """
        Async generator that yields incoming messages.

        Usage:
            async for message in client.messages():
                print(message.topic, message.data)
        """
        while self._running:
            message = await self._message_queue.get()
            yield message

    async def get_message(self, timeout: float | None = None) -> WebSocketMessage | None:
        """
        Get next message with optional timeout.

        Returns None if timeout reached.
        """
        try:
            if timeout:
                return await asyncio.wait_for(self._message_queue.get(), timeout=timeout)
            return await self._message_queue.get()
        except TimeoutError:
            return None

    # ==========================================================================
    # Utility Methods
    # ==========================================================================

    @property
    def is_connected(self) -> bool:
        """Check if connected to WebSocket."""
        return self._public_ws is not None and self._public_ws.open

    @property
    def is_authenticated(self) -> bool:
        """Check if authenticated for private channels."""
        return self._authenticated

    def get_subscription_count(self) -> dict:
        """Get subscription counts."""
        return {
            "public": len(self._public_subscriptions),
            "private": len(self._private_subscriptions),
        }

    async def ping(self):
        """Send ping to keep connection alive."""
        ping_msg = json.dumps({"op": "ping"})

        if self._public_ws and self._public_ws.open:
            await self._public_ws.send(ping_msg)

        if self._private_ws and self._private_ws.open:
            await self._private_ws.send(ping_msg)


# =============================================================================
# Message Parsers
# =============================================================================


def parse_kline_message(message: WebSocketMessage) -> list[dict]:
    """Parse kline message into candle dicts."""
    candles = []
    for item in message.data:
        candles.append(
            {
                "start": int(item.get("start", 0)),
                "end": int(item.get("end", 0)),
                "interval": item.get("interval", ""),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": float(item.get("volume", 0)),
                "turnover": float(item.get("turnover", 0)),
                "confirm": item.get("confirm", False),
                "timestamp": int(item.get("timestamp", 0)),
            }
        )
    return candles


def parse_trade_message(message: WebSocketMessage) -> list[dict]:
    """Parse public trade message."""
    trades = []
    for item in message.data:
        trades.append(
            {
                "id": item.get("i", ""),
                "time": int(item.get("T", 0)),
                "symbol": item.get("s", ""),
                "side": item.get("S", "").lower(),
                "price": float(item.get("p", 0)),
                "qty": float(item.get("v", 0)),
                "is_block_trade": item.get("BT", False),
            }
        )
    return trades


def parse_orderbook_message(message: WebSocketMessage) -> dict:
    """Parse orderbook message."""
    data = message.data
    if isinstance(data, list) and len(data) > 0:
        data = data[0]

    return {
        "symbol": data.get("s", ""),
        "bids": [[float(p), float(q)] for p, q in data.get("b", [])],
        "asks": [[float(p), float(q)] for p, q in data.get("a", [])],
        "update_id": data.get("u", 0),
        "seq": data.get("seq", 0),
    }


def parse_position_message(message: WebSocketMessage) -> list[dict]:
    """Parse position update message."""
    positions = []
    for item in message.data:
        positions.append(
            {
                "symbol": item.get("symbol", ""),
                "side": item.get("side", "").lower(),
                "size": float(item.get("size", 0)),
                "entry_price": float(item.get("entryPrice", 0) or 0),
                "mark_price": float(item.get("markPrice", 0) or 0),
                "position_value": float(item.get("positionValue", 0) or 0),
                "unrealized_pnl": float(item.get("unrealisedPnl", 0) or 0),
                "cum_realized_pnl": float(item.get("cumRealisedPnl", 0) or 0),
                "leverage": float(item.get("leverage", 1) or 1),
                "liq_price": float(item.get("liqPrice", 0) or 0) if item.get("liqPrice") else None,
                "bust_price": float(item.get("bustPrice", 0) or 0) if item.get("bustPrice") else None,
                "position_im": float(item.get("positionIM", 0) or 0),
                "position_mm": float(item.get("positionMM", 0) or 0),
                "take_profit": float(item.get("takeProfit", 0) or 0) if item.get("takeProfit") else None,
                "stop_loss": float(item.get("stopLoss", 0) or 0) if item.get("stopLoss") else None,
                "trailing_stop": float(item.get("trailingStop", 0) or 0) if item.get("trailingStop") else None,
                "created_time": int(item.get("createdTime", 0) or 0),
                "updated_time": int(item.get("updatedTime", 0) or 0),
            }
        )
    return positions


def parse_order_message(message: WebSocketMessage) -> list[dict]:
    """Parse order update message."""
    orders = []
    for item in message.data:
        orders.append(
            {
                "order_id": item.get("orderId", ""),
                "order_link_id": item.get("orderLinkId", ""),
                "symbol": item.get("symbol", ""),
                "side": item.get("side", "").lower(),
                "order_type": item.get("orderType", "").lower(),
                "price": float(item.get("price", 0) or 0),
                "qty": float(item.get("qty", 0)),
                "leaves_qty": float(item.get("leavesQty", 0)),
                "leaves_value": float(item.get("leavesValue", 0) or 0),
                "cum_exec_qty": float(item.get("cumExecQty", 0)),
                "cum_exec_value": float(item.get("cumExecValue", 0) or 0),
                "cum_exec_fee": float(item.get("cumExecFee", 0) or 0),
                "avg_price": float(item.get("avgPrice", 0) or 0),
                "order_status": item.get("orderStatus", "").lower(),
                "time_in_force": item.get("timeInForce", ""),
                "reduce_only": item.get("reduceOnly", False),
                "close_on_trigger": item.get("closeOnTrigger", False),
                "stop_loss": float(item.get("stopLoss", 0) or 0) if item.get("stopLoss") else None,
                "take_profit": float(item.get("takeProfit", 0) or 0) if item.get("takeProfit") else None,
                "created_time": int(item.get("createdTime", 0)),
                "updated_time": int(item.get("updatedTime", 0)),
            }
        )
    return orders


def parse_execution_message(message: WebSocketMessage) -> list[dict]:
    """Parse execution/fill message."""
    executions = []
    for item in message.data:
        executions.append(
            {
                "exec_id": item.get("execId", ""),
                "order_id": item.get("orderId", ""),
                "order_link_id": item.get("orderLinkId", ""),
                "symbol": item.get("symbol", ""),
                "side": item.get("side", "").lower(),
                "exec_price": float(item.get("execPrice", 0)),
                "exec_qty": float(item.get("execQty", 0)),
                "exec_value": float(item.get("execValue", 0)),
                "exec_fee": float(item.get("execFee", 0)),
                "fee_rate": float(item.get("feeRate", 0) or 0),
                "exec_type": item.get("execType", ""),
                "leaves_qty": float(item.get("leavesQty", 0)),
                "closed_size": float(item.get("closedSize", 0)),
                "is_maker": item.get("isMaker", False),
                "exec_time": int(item.get("execTime", 0)),
            }
        )
    return executions


def parse_wallet_message(message: WebSocketMessage) -> list[dict]:
    """Parse wallet/balance update message."""
    wallets = []
    for item in message.data:
        coins = item.get("coin", [])
        for coin in coins:
            wallets.append(
                {
                    "account_type": item.get("accountType", ""),
                    "coin": coin.get("coin", ""),
                    "equity": float(coin.get("equity", 0) or 0),
                    "wallet_balance": float(coin.get("walletBalance", 0)),
                    "available_balance": float(coin.get("availableToWithdraw", 0)),
                    "position_margin": float(coin.get("positionMargin", 0) or 0),
                    "order_margin": float(coin.get("orderMargin", 0) or 0),
                    "unrealized_pnl": float(coin.get("unrealisedPnl", 0) or 0),
                    "cum_realized_pnl": float(coin.get("cumRealisedPnl", 0) or 0),
                }
            )
    return wallets
