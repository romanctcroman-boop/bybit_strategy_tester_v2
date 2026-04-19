"""
📈 Bybit WebSocket Client

Real-time data streaming from Bybit exchange.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import websockets

logger = logging.getLogger(__name__)


@dataclass
class WSMessage:
    """WebSocket message"""

    topic: str
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WSConnection:
    """WebSocket connection info"""

    url: str
    connected: bool = False
    last_ping: datetime | None = None
    last_pong: datetime | None = None
    reconnect_count: int = 0


class BybitWebSocketClient:
    """
    Bybit WebSocket client for real-time data.

    Поддерживает:
    - kline (candlestick) data
    - trades
    - ticker
    - orderbook

    Пример использования:
    ```python
    client = BybitWebSocketClient()

    # Подписка на kline
    await client.subscribe_kline('BTCUSDT', '1h')

    # Получение данных
    async for message in client.kline_stream:
        print(f"Kline: {message}")
    ```
    """

    # WebSocket URLs
    MAINNET_URL = "wss://stream.bybit.com/v5/public/linear"
    TESTNET_URL = "wss://stream-testnet.bybit.com/v5/public/linear"

    def __init__(
        self,
        testnet: bool = False,
        reconnect_delay: float = 5.0,
        ping_interval: float = 30.0,
        ping_timeout: float = 10.0,
    ):
        """
        Args:
            testnet: Использовать testnet
            reconnect_delay: Задержка перед переподключением
            ping_interval: Интервал ping
            ping_timeout: Timeout ping
        """
        self.testnet = testnet
        self.url = self.TESTNET_URL if testnet else self.MAINNET_URL
        self.reconnect_delay = reconnect_delay
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout

        # WebSocket connection
        self.ws: websockets.WebSocketClientProtocol | None = None
        self.connection = WSConnection(url=self.url)

        # Streams
        self.kline_stream: asyncio.Queue = asyncio.Queue()
        self.trade_stream: asyncio.Queue = asyncio.Queue()
        self.ticker_stream: asyncio.Queue = asyncio.Queue()
        self.orderbook_stream: asyncio.Queue = asyncio.Queue()

        # Subscriptions
        self.subscriptions: list[str] = []

        # Callbacks
        self.callbacks: dict[str, Callable] = {}

        # Running flag
        self._running = False
        self._ping_task: asyncio.Task | None = None
        self._receive_task: asyncio.Task | None = None

    async def connect(self):
        """Подключение к WebSocket"""
        try:
            self.ws = await websockets.connect(
                self.url,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
            )

            self.connection.connected = True
            self.connection.last_ping = datetime.now()

            logger.info(f"Connected to {self.url}")

            # Resubscribe
            if self.subscriptions:
                await self._resubscribe()

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connection.connected = False
            raise

    async def disconnect(self):
        """Отключение от WebSocket"""
        self._running = False

        if self._ping_task:
            self._ping_task.cancel()

        if self._receive_task:
            self._receive_task.cancel()

        if self.ws:
            await self.ws.close()

        self.connection.connected = False
        logger.info("Disconnected")

    async def subscribe_kline(self, symbol: str, interval: str):
        """
        Подписка на kline (candlestick) data.

        Args:
            symbol: Symbol (e.g., BTCUSDT)
            interval: Interval (1m, 5m, 15m, 1h, 4h, 1d)
        """
        topic = f"kline.{interval}.{symbol}"
        await self._subscribe(topic)
        self.subscriptions.append(topic)
        logger.info(f"Subscribed to {topic}")

    async def subscribe_trades(self, symbol: str):
        """
        Подписка на trades.

        Args:
            symbol: Symbol
        """
        topic = f"publicTrade.{symbol}"
        await self._subscribe(topic)
        self.subscriptions.append(topic)
        logger.info(f"Subscribed to {topic}")

    async def subscribe_ticker(self, symbol: str):
        """
        Подписка на ticker.

        Args:
            symbol: Symbol
        """
        topic = f"tickers.{symbol}"
        await self._subscribe(topic)
        self.subscriptions.append(topic)
        logger.info(f"Subscribed to {topic}")

    async def subscribe_orderbook(self, symbol: str, depth: int = 50):
        """
        Подписка на orderbook.

        Args:
            symbol: Symbol
            depth: Depth (1, 50, 500)
        """
        topic = f"orderbook.{depth}.{symbol}"
        await self._subscribe(topic)
        self.subscriptions.append(topic)
        logger.info(f"Subscribed to {topic}")

    async def _subscribe(self, topic: str):
        """Отправка subscribe запроса"""
        if not self.connection.connected:
            await self.connect()

        message = {"op": "subscribe", "args": [topic]}

        await self.ws.send(json.dumps(message))
        logger.debug(f"Sent subscribe: {topic}")

    async def _resubscribe(self):
        """Переподписка после reconnect"""
        for topic in self.subscriptions:
            await self._subscribe(topic)

    async def _receive_messages(self):
        """Получение сообщений"""
        try:
            async for message in self.ws:
                await self._handle_message(message)
        except websockets.ConnectionClosed:
            logger.warning("Connection closed")
            self.connection.connected = False
        except Exception as e:
            logger.error(f"Receive error: {e}")
            self.connection.connected = False

    async def _handle_message(self, raw_message: str):
        """
        Обработка сообщения.

        Args:
            raw_message: Raw JSON message
        """
        try:
            data = json.loads(raw_message)

            # Ping/pong
            if "op" in data and data["op"] == "ping":
                await self._send_pong()
                return

            # Subscription response
            if "op" in data and data["op"] == "subscribe":
                logger.debug(f"Subscribed: {data.get('topic', 'unknown')}")
                return

            # Data message
            if "topic" in data:
                topic = data["topic"]
                message = WSMessage(topic=topic, data=data.get("data", {}), timestamp=datetime.now())

                # Dispatch to appropriate stream
                if topic.startswith("kline"):
                    await self.kline_stream.put(message)
                elif topic.startswith("publicTrade"):
                    await self.trade_stream.put(message)
                elif topic.startswith("tickers"):
                    await self.ticker_stream.put(message)
                elif topic.startswith("orderbook"):
                    await self.orderbook_stream.put(message)

                # Call callback if registered
                if topic in self.callbacks:
                    await self.callbacks[topic](message)

        except Exception as e:
            logger.error(f"Message handling error: {e}")

    async def _send_pong(self):
        """Отправка pong"""
        if self.ws:
            await self.ws.send(json.dumps({"op": "pong"}))
            self.connection.last_pong = datetime.now()

    async def _ping_loop(self):
        """Ping loop для проверки connection"""
        while self._running and self.connection.connected:
            await asyncio.sleep(self.ping_interval)

            try:
                if self.ws:
                    await self.ws.ping()
                    self.connection.last_ping = datetime.now()
            except Exception as e:
                logger.warning(f"Ping failed: {e}")
                self.connection.connected = False

    async def start(self):
        """Запуск WebSocket client"""
        self._running = True

        await self.connect()

        # Запуск задач
        self._receive_task = asyncio.create_task(self._receive_messages())
        self._ping_task = asyncio.create_task(self._ping_loop())

        logger.info("WebSocket client started")

    async def run_forever(self):
        """Запуск в цикле с autoreconnect"""
        while True:
            try:
                await self.start()

                while self._running and self.connection.connected:
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error: {e}")

            if not self._running:
                break

            # Reconnect
            self.connection.reconnect_count += 1
            logger.info(f"Reconnecting in {self.reconnect_delay}s (attempt {self.connection.reconnect_count})")
            await asyncio.sleep(self.reconnect_delay)

    def set_callback(self, topic: str, callback: Callable):
        """
        Установить callback для topic.

        Args:
            topic: Topic string
            callback: Async callback function
        """
        self.callbacks[topic] = callback
        logger.debug(f"Callback set for {topic}")

    def get_kline(self) -> asyncio.Queue:
        """Get kline stream queue"""
        return self.kline_stream

    def get_trades(self) -> asyncio.Queue:
        """Get trades stream queue"""
        return self.trade_stream

    def get_ticker(self) -> asyncio.Queue:
        """Get ticker stream queue"""
        return self.ticker_stream

    def get_orderbook(self) -> asyncio.Queue:
        """Get orderbook stream queue"""
        return self.orderbook


# Convenience alias
WSClient = BybitWebSocketClient
