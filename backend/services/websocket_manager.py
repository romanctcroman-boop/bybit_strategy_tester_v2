"""
WebSocketManager - Real-time данные через Bybit WebSocket

Функционал:
- Подключение к Bybit WebSocket API v5
- Live цены (kline, ticker)
- Trades stream
- Orderbook updates
- Auto reconnect
- Subscription management
- Callback system
"""

import json
import asyncio
import logging
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime
import websockets
from threading import Thread
import time
import redis.asyncio as aioredis
from backend.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Менеджер WebSocket подключений к Bybit
    
    API Documentation:
    https://bybit-exchange.github.io/docs/v5/ws/connect
    
    Примеры использования:
        # Создать менеджер
        ws_manager = WebSocketManager()
        
        # Подписаться на свечи
        @ws_manager.on_kline('BTCUSDT', '15')
        def handle_kline(data):
            print(f"Новая свеча: {data}")
        
        # Подписаться на сделки
        @ws_manager.on_trade('BTCUSDT')
        def handle_trade(data):
            print(f"Новая сделка: {data}")
        
        # Запустить
        ws_manager.start()
        
        # Остановить
        ws_manager.stop()
    """
    
    # WebSocket URLs
    WS_PUBLIC_URL = "wss://stream.bybit.com/v5/public/linear"
    WS_PRIVATE_URL = "wss://stream.bybit.com/v5/private"
    
    # Reconnect settings
    RECONNECT_DELAY = 5  # seconds
    PING_INTERVAL = 20  # seconds
    PONG_TIMEOUT = 10  # seconds
    # WebSocket open timeout (seconds)
    OPEN_TIMEOUT = 20
    
    def __init__(self, testnet: bool = False):
        """
        Инициализация WebSocket менеджера
        
        Args:
            testnet: Использовать testnet WebSocket
        """
        self.testnet = testnet
        if testnet:
            self.WS_PUBLIC_URL = "wss://stream-testnet.bybit.com/v5/public/linear"
            self.WS_PRIVATE_URL = "wss://stream-testnet.bybit.com/v5/private"
        
        # Connection state
        self.ws = None
        self.connected = False
        self.running = False
        self.loop = None
        self.thread = None
        
        # Subscriptions
        self.subscriptions: List[str] = []
        self.callbacks: Dict[str, List[Callable]] = {}
        
        # Reconnect
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
        # Statistics
        self.messages_received = 0
        self.last_message_time = None
        
        # Redis publisher (optional)
        self.redis = None
        self.redis_url = None
        # Open timeout (can be overridden via settings.WS_OPEN_TIMEOUT)
        self.open_timeout = getattr(settings, "WS_OPEN_TIMEOUT", self.OPEN_TIMEOUT)
    
    def _get_topic(self, channel: str, symbol: str, interval: Optional[str] = None) -> str:
        """
        Создать topic для подписки
        
        Args:
            channel: Канал (kline, trade, orderbook)
            symbol: Символ
            interval: Интервал (для kline)
            
        Returns:
            Topic строка
        """
        if channel == 'kline' and interval:
            return f"kline.{interval}.{symbol}"
        elif channel == 'trade':
            return f"publicTrade.{symbol}"
        elif channel == 'orderbook':
            return f"orderbook.50.{symbol}"
        elif channel == 'ticker':
            return f"tickers.{symbol}"
        else:
            return f"{channel}.{symbol}"
    
    async def _connect(self):
        """Установить WebSocket соединение"""
        try:
            logger.info(f"Connecting to {self.WS_PUBLIC_URL}")
            self.ws = await websockets.connect(
                self.WS_PUBLIC_URL,
                open_timeout=self.open_timeout,
                ping_interval=self.PING_INTERVAL,
                ping_timeout=self.PONG_TIMEOUT
            )
            self.connected = True
            self.reconnect_attempts = 0
            logger.info("✅ WebSocket connected")
            
            # Subscribe to all topics
            if self.subscriptions:
                await self._subscribe(self.subscriptions)
            
        except Exception as e:
            logger.exception(f"❌ Connection failed: {e}")
            self.connected = False
            raise
    
    async def _disconnect(self):
        """Закрыть WebSocket соединение"""
        if self.ws:
            try:
                await self.ws.close()
                logger.info("WebSocket disconnected")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
            finally:
                self.connected = False
                self.ws = None
    
    async def _subscribe(self, topics: List[str]):
        """
        Подписаться на топики
        
        Args:
            topics: Список топиков
        """
        if not self.ws:
            return
        
        message = {
            "op": "subscribe",
            "args": topics
        }
        
        try:
            await self.ws.send(json.dumps(message))
            logger.info(f"📡 Subscribed to {len(topics)} topics")
            for topic in topics:
                logger.debug(f"  • {topic}")
        except Exception as e:
            logger.error(f"Subscription failed: {e}")
    
    async def _unsubscribe(self, topics: List[str]):
        """Отписаться от топиков"""
        if not self.ws:
            return
        
        message = {
            "op": "unsubscribe",
            "args": topics
        }
        
        try:
            await self.ws.send(json.dumps(message))
            logger.info(f"Unsubscribed from {len(topics)} topics")
        except Exception as e:
            logger.error(f"Unsubscription failed: {e}")
    
    async def _handle_message(self, message: str):
        """
        Обработать входящее сообщение
        
        Args:
            message: JSON строка
        """
        try:
            data = json.loads(message)
            
            # Update statistics
            self.messages_received += 1
            self.last_message_time = datetime.utcnow()
            
            # Handle different message types
            if 'op' in data:
                # System message (subscribe, ping, etc.)
                if data['op'] == 'subscribe':
                    if data.get('success'):
                        logger.debug("✅ Subscription confirmed")
                    else:
                        logger.error(f"❌ Subscription failed: {data.get('ret_msg')}")
                
                elif data['op'] == 'pong':
                    logger.debug("Pong received")
                
            elif 'topic' in data:
                # Data message
                topic = data['topic']
                msg_data = data.get('data', [])
                
                # Call registered callbacks
                if topic in self.callbacks:
                    for callback in self.callbacks[topic]:
                        try:
                            callback(msg_data)
                        except Exception as e:
                            logger.error(f"Callback error for {topic}: {e}")
                # Publish to Redis channel if configured (format expected by live.py)
                try:
                    if self.redis:
                        channel = self._topic_to_channel(topic)
                        # Build standardized payload
                        subscription, sym, tf, payload_body = self._parse_topic(topic, msg_data)

                        payload = {
                            "type": "update",
                            "subscription": subscription,
                            "symbol": sym,
                            "timeframe": tf,
                        }

                        # Merge body (candle/trades/ticker/orderbook or raw data)
                        payload.update(payload_body)

                        payload["received_at"] = datetime.utcnow().isoformat() + "Z"

                        # Use Redis Streams (XADD) for durable delivery in production.
                        # Stream key pattern: stream:<channel> e.g. stream:candles:BTCUSDT:1
                        try:
                            stream_key = f"stream:{channel}"
                            # store entire payload as single field 'payload'
                            await self.redis.xadd(stream_key, {"payload": json.dumps(payload)})
                        except Exception as ex:
                            logger.warning(f"Failed to XADD to Redis stream {stream_key}: {ex}")
                except Exception as e:
                    logger.warning(f"Failed to publish to Redis for topic {topic}: {e}")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    async def _listen(self):
        """Слушать входящие сообщения"""
        while self.running:
            try:
                if not self.connected:
                    await self._reconnect()
                
                if self.ws:
                    message = await self.ws.recv()
                    await self._handle_message(message)
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection closed")
                self.connected = False
                if self.running:
                    await self._reconnect()
                    
            except Exception as e:
                logger.error(f"Listen error: {e}")
                await asyncio.sleep(1)
    
    async def _reconnect(self):
        """Переподключиться к WebSocket"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnect attempts ({self.max_reconnect_attempts}) reached")
            self.running = False
            return
        
        self.reconnect_attempts += 1
        delay = self.RECONNECT_DELAY * self.reconnect_attempts
        
        logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        await asyncio.sleep(delay)
        
        try:
            await self._connect()
        except Exception as e:
            logger.error(f"Reconnect failed: {e}")
    
    async def _run_async(self):
        """Async event loop"""
        try:
            await self._connect()
            await self._listen()
        except Exception as e:
            logger.error(f"Async run error: {e}")
        finally:
            await self._disconnect()
    
    def _run_thread(self):
        """Запустить async event loop в потоке"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._run_async())
        except Exception as e:
            logger.error(f"Thread error: {e}")
        finally:
            self.loop.close()
    
    def start(self):
        """Запустить WebSocket менеджер"""
        if self.running:
            logger.warning("WebSocket already running")
            return
        
        self.running = True
        self.thread = Thread(target=self._run_thread, daemon=True)
        self.thread.start()
        
        logger.info("🚀 WebSocket manager started")
        
        # Wait for connection
        timeout = 10
        start_time = time.time()
        while not self.connected and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        if not self.connected:
            logger.warning("Connection timeout")

        # Initialize Redis client if URL provided via env var
        try:
            from backend.core.config import settings
            self.redis_url = settings.redis_url
            # create redis client for publishing
            self.redis = aioredis.from_url(self.redis_url, encoding='utf-8', decode_responses=True)
        except Exception:
            # non-fatal: keep running without redis
            logger.debug("Redis not configured for WebSocketManager")
    
    def stop(self):
        """Остановить WebSocket менеджер"""
        if not self.running:
            return
        
        logger.info("Stopping WebSocket manager")
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=5)
        
        logger.info("✅ WebSocket manager stopped")
    
    def subscribe_kline(self, symbol: str, interval: str, callback: Callable):
        """
        Подписаться на свечи
        
        Args:
            symbol: Торговая пара (BTCUSDT)
            interval: Интервал (1, 5, 15, 60, D)
            callback: Функция обработки данных
        """
        topic = self._get_topic('kline', symbol, interval)
        
        if topic not in self.subscriptions:
            self.subscriptions.append(topic)
        
        if topic not in self.callbacks:
            self.callbacks[topic] = []
        
        self.callbacks[topic].append(callback)
        
        # Subscribe if already connected
        if self.connected and self.loop:
            asyncio.run_coroutine_threadsafe(
                self._subscribe([topic]),
                self.loop
            )
        
        logger.info(f"📊 Subscribed to kline: {symbol} {interval}")
    
    def subscribe_trade(self, symbol: str, callback: Callable):
        """
        Подписаться на сделки
        
        Args:
            symbol: Торговая пара
            callback: Функция обработки данных
        """
        topic = self._get_topic('trade', symbol)
        
        if topic not in self.subscriptions:
            self.subscriptions.append(topic)
        
        if topic not in self.callbacks:
            self.callbacks[topic] = []
        
        self.callbacks[topic].append(callback)
        
        if self.connected and self.loop:
            asyncio.run_coroutine_threadsafe(
                self._subscribe([topic]),
                self.loop
            )
        
        logger.info(f"💱 Subscribed to trades: {symbol}")
    
    def subscribe_ticker(self, symbol: str, callback: Callable):
        """
        Подписаться на тикер (24h статистика)
        
        Args:
            symbol: Торговая пара
            callback: Функция обработки данных
        """
        topic = self._get_topic('ticker', symbol)
        
        if topic not in self.subscriptions:
            self.subscriptions.append(topic)
        
        if topic not in self.callbacks:
            self.callbacks[topic] = []
        
        self.callbacks[topic].append(callback)
        
        if self.connected and self.loop:
            asyncio.run_coroutine_threadsafe(
                self._subscribe([topic]),
                self.loop
            )
        
        logger.info(f"📈 Subscribed to ticker: {symbol}")
    
    def subscribe_orderbook(self, symbol: str, callback: Callable):
        """
        Подписаться на ордербук
        
        Args:
            symbol: Торговая пара
            callback: Функция обработки данных
        """
        topic = self._get_topic('orderbook', symbol)
        
        if topic not in self.subscriptions:
            self.subscriptions.append(topic)
        
        if topic not in self.callbacks:
            self.callbacks[topic] = []
        
        self.callbacks[topic].append(callback)
        
        if self.connected and self.loop:
            asyncio.run_coroutine_threadsafe(
                self._subscribe([topic]),
                self.loop
            )
        
        logger.info(f"📖 Subscribed to orderbook: {symbol}")

    def _topic_to_channel(self, topic: str) -> str:
        """Convert Bybit topic to Redis channel name"""
        # Example: kline.1.BTCUSDT -> candles:BTCUSDT:1
        try:
            parts = topic.split('.')
            if parts[0] == 'kline' and len(parts) >= 3:
                interval = parts[1]
                symbol = parts[2]
                return f"candles:{symbol}:{interval}"
            if parts[0].startswith('publicTrade') or parts[0] == 'publicTrade':
                # publicTrade.BTCUSDT
                symbol = parts[-1]
                return f"trades:{symbol}"
            if parts[0].startswith('tickers') or parts[0] == 'tickers':
                symbol = parts[-1]
                return f"ticker:{symbol}"
            if parts[0].startswith('orderbook'):
                symbol = parts[-1]
                return f"orderbook:{symbol}"
        except Exception:
            pass
        # Fallback
        return topic.replace('.', ':')

    def _parse_topic(self, topic: str, msg_data: Any):
        """Parse Bybit topic and message data into subscription, symbol, timeframe and body.

        Returns: (subscription, symbol, timeframe, body_dict)
        """
        try:
            parts = topic.split('.')
            # kline.{interval}.{symbol}
            if parts[0] == 'kline' and len(parts) >= 3:
                interval = parts[1]
                symbol = parts[2]
                # Bybit kline data usually in a list; take first item if list
                candle = None
                if isinstance(msg_data, list) and len(msg_data) > 0:
                    candle = msg_data[0]
                elif isinstance(msg_data, dict):
                    candle = msg_data

                normalized = self._normalize_candle(candle) if candle is not None else None
                body = {"candle": normalized}
                return 'candles', symbol, interval, body

            # publicTrade.{symbol}
            if parts[0].startswith('publicTrade') or parts[0] == 'publicTrade':
                symbol = parts[-1]
                # trades as list
                trades = msg_data if isinstance(msg_data, list) else [msg_data]
                normalized_trades = [self._normalize_trade(t) for t in trades]
                body = {"trades": normalized_trades}
                return 'trades', symbol, None, body

            # tickers.{symbol}
            if parts[0].startswith('tickers') or parts[0] == 'tickers':
                symbol = parts[-1]
                ticker = None
                if isinstance(msg_data, list) and len(msg_data) > 0:
                    ticker = msg_data[0]
                elif isinstance(msg_data, dict):
                    ticker = msg_data
                body = {"ticker": ticker}
                return 'ticker', symbol, None, body

            # orderbook.{level}.{symbol}
            if parts[0].startswith('orderbook') and len(parts) >= 2:
                symbol = parts[-1]
                body = {"orderbook": msg_data}
                return 'orderbook', symbol, None, body

        except Exception:
            pass

        # Fallback: return raw data
        return 'raw', None, None, {"data": msg_data}

    def _normalize_candle(self, raw: Any) -> Optional[Dict[str, Any]]:
        """Normalize raw Bybit kline object to expected shape for frontend.

        Expected fields: timestamp (ms int), open, high, low, close (strings), volume (string), confirm (bool)
        """
        if not raw:
            return None

        try:
            # Bybit fields may vary; prefer common names
            ts = raw.get('start') or raw.get('t') or raw.get('timestamp') or raw.get('open_time')
            # Convert to ms if needed (assume seconds -> ms if ts looks small)
            if isinstance(ts, (int, float)):
                if ts < 1e12:
                    ts = int(ts * 1000)
                else:
                    ts = int(ts)
            else:
                # try parseable string
                try:
                    ts = int(float(ts))
                    if ts < 1e12:
                        ts = int(ts * 1000)
                except Exception:
                    ts = None

            o = str(raw.get('open') or raw.get('o') or raw.get('openPrice') or '')
            h = str(raw.get('high') or raw.get('h') or raw.get('highPrice') or '')
            l = str(raw.get('low') or raw.get('l') or raw.get('lowPrice') or '')
            c = str(raw.get('close') or raw.get('c') or raw.get('closePrice') or '')
            v = str(raw.get('volume') or raw.get('v') or raw.get('volume24h') or '')
            confirm = bool(raw.get('confirm')) if 'confirm' in raw else False

            return {
                'timestamp': ts,
                'open': o,
                'high': h,
                'low': l,
                'close': c,
                'volume': v,
                'confirm': confirm
            }

        except Exception:
            return {'raw': raw}

    def _normalize_trade(self, raw: Any) -> Dict[str, Any]:
        """Normalize raw trade object to expected shape.

        Expected: timestamp (ms), side (Buy/Sell), price (string), size (string), trade_id
        """
        try:
            ts = raw.get('t') or raw.get('timestamp') or raw.get('trade_time') or raw.get('T')
            if isinstance(ts, (int, float)):
                if ts < 1e12:
                    ts = int(ts * 1000)
                else:
                    ts = int(ts)
            else:
                try:
                    ts = int(float(ts))
                    if ts < 1e12:
                        ts = int(ts * 1000)
                except Exception:
                    ts = None

            price = str(raw.get('p') or raw.get('price') or raw.get('quotePrice') or '')
            size = str(raw.get('v') or raw.get('size') or raw.get('volume') or '')
            side = raw.get('S') or raw.get('side') or raw.get('direction') or ''
            trade_id = raw.get('trade_id') or raw.get('id') or raw.get('i') or ''

            return {
                'timestamp': ts,
                'side': side,
                'price': price,
                'size': size,
                'trade_id': trade_id
            }

        except Exception:
            return {'raw': raw}
    
    def on_kline(self, symbol: str, interval: str):
        """Decorator для подписки на свечи"""
        def decorator(callback: Callable):
            self.subscribe_kline(symbol, interval, callback)
            return callback
        return decorator
    
    def on_trade(self, symbol: str):
        """Decorator для подписки на сделки"""
        def decorator(callback: Callable):
            self.subscribe_trade(symbol, callback)
            return callback
        return decorator
    
    def on_ticker(self, symbol: str):
        """Decorator для подписки на тикер"""
        def decorator(callback: Callable):
            self.subscribe_ticker(symbol, callback)
            return callback
        return decorator
    
    def on_orderbook(self, symbol: str):
        """Decorator для подписки на ордербук"""
        def decorator(callback: Callable):
            self.subscribe_orderbook(symbol, callback)
            return callback
        return decorator
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получить статистику
        
        Returns:
            Словарь со статистикой
        """
        return {
            'connected': self.connected,
            'running': self.running,
            'subscriptions': len(self.subscriptions),
            'topics': self.subscriptions,
            'messages_received': self.messages_received,
            'last_message_time': self.last_message_time,
            'reconnect_attempts': self.reconnect_attempts
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Создать менеджер
    ws = WebSocketManager()
    
    # Счётчики
    kline_count = 0
    trade_count = 0
    
    # Подписаться на свечи
    @ws.on_kline('BTCUSDT', '1')
    def handle_kline(data):
        global kline_count
        kline_count += 1
        if isinstance(data, list) and len(data) > 0:
            candle = data[0]
            print(f"🕯️  Kline: {candle.get('start')} - Close: {candle.get('close')}")
    
    # Подписаться на сделки
    @ws.on_trade('BTCUSDT')
    def handle_trade(data):
        global trade_count
        trade_count += 1
        if isinstance(data, list) and len(data) > 0:
            trade = data[0]
            print(f"💱 Trade: {trade.get('p')} x {trade.get('v')} ({trade.get('S')})")
    
    # Подписаться на тикер
    @ws.on_ticker('BTCUSDT')
    def handle_ticker(data):
        if isinstance(data, dict):
            print(f"📈 Ticker: {data.get('lastPrice')} | 24h Vol: {data.get('volume24h')}")
    
    # Запустить
    print("🚀 Starting WebSocket Manager...")
    ws.start()
    
    try:
        # Слушать 30 секунд
        print("Listening for 30 seconds...")
        time.sleep(30)
        
        # Статистика
        stats = ws.get_stats()
        print("\n" + "="*70)
        print("📊 Statistics:")
        print(f"  Connected: {stats['connected']}")
        print(f"  Subscriptions: {stats['subscriptions']}")
        print(f"  Messages received: {stats['messages_received']}")
        print(f"  Klines received: {kline_count}")
        print(f"  Trades received: {trade_count}")
        print("="*70)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    
    finally:
        # Остановить
        ws.stop()
        print("✅ Done")
