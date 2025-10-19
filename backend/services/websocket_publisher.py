"""
WebSocket Publisher

Publishes real-time data from Bybit WebSocket to Redis Pub/Sub channels.
Frontend clients subscribe to these channels via FastAPI WebSocket endpoints.
"""

import json
import redis
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from loguru import logger

from backend.core.config import settings
from backend.models.websocket_schemas import (
    CandleData,
    CandleUpdate,
    TradeUpdate,
    TickerUpdate,
    MessageType,
    SubscriptionType
)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder для Decimal типов"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class WebSocketPublisher:
    """
    Публикация WebSocket данных в Redis Pub/Sub
    
    Архитектура:
        Bybit WebSocket → WebSocketPublisher → Redis Pub/Sub → FastAPI WebSocket → Frontend
    
    Channels:
        - candles:{symbol}:{timeframe}  - OHLCV updates (BTCUSDT:1, ETHUSDT:5)
        - trades:{symbol}               - Trade stream
        - ticker:{symbol}               - 24h ticker updates
        - orderbook:{symbol}            - Orderbook snapshots
    
    Usage:
        publisher = WebSocketPublisher()
        
        # Publish candle update
        publisher.publish_candle('BTCUSDT', '1', candle_data)
        
        # Publish trade
        publisher.publish_trade('BTCUSDT', trade_data)
    """
    
    # Redis Pub/Sub channel prefixes
    CHANNEL_CANDLES = "candles"
    CHANNEL_TRADES = "trades"
    CHANNEL_TICKER = "ticker"
    CHANNEL_ORDERBOOK = "orderbook"
    
    def __init__(self):
        """Инициализация Redis Pub/Sub клиента"""
        self._redis: Optional[redis.Redis] = None
        self._connect()
        
        # Statistics
        self.messages_published = 0
        self.errors_count = 0
        self.channels_active = set()
    
    def _connect(self):
        """Подключение к Redis"""
        try:
            self._redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=False,  # Pub/Sub uses bytes
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # Test connection
            self._redis.ping()
            logger.info(f"✅ WebSocketPublisher connected to Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except redis.ConnectionError as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self._redis = None
        except Exception as e:
            logger.error(f"❌ Redis initialization error: {e}")
            self._redis = None
    
    @property
    def is_available(self) -> bool:
        """Проверка доступности Redis"""
        if self._redis is None:
            return False
        try:
            self._redis.ping()
            return True
        except:
            return False
    
    def _get_channel(self, prefix: str, symbol: str, timeframe: Optional[str] = None) -> str:
        """
        Сформировать имя канала
        
        Args:
            prefix: Префикс канала (candles, trades, ticker)
            symbol: Торговая пара
            timeframe: Таймфрейм (для candles)
        
        Returns:
            Полное имя канала (candles:BTCUSDT:1)
        """
        symbol = symbol.upper()
        
        if timeframe:
            return f"{prefix}:{symbol}:{timeframe}"
        else:
            return f"{prefix}:{symbol}"
    
    def _publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """
        Опубликовать сообщение в канал Redis Pub/Sub
        
        Args:
            channel: Имя канала
            message: Сообщение (dict)
        
        Returns:
            True если успешно
        """
        if not self.is_available:
            logger.warning("Redis unavailable, skipping publish")
            return False
        
        try:
            # Serialize with Decimal support
            json_message = json.dumps(message, cls=DecimalEncoder)
            
            # Publish to Redis
            subscribers_count = self._redis.publish(channel, json_message)
            
            # Update statistics
            self.messages_published += 1
            self.channels_active.add(channel)
            
            logger.debug(f"📡 Published to {channel} ({subscribers_count} subscribers)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Publish error to {channel}: {e}")
            self.errors_count += 1
            return False
    
    def publish_candle(
        self, 
        symbol: str, 
        timeframe: str, 
        candle_data: Dict[str, Any]
    ) -> bool:
        """
        Опубликовать обновление свечи
        
        Args:
            symbol: Торговая пара (BTCUSDT)
            timeframe: Таймфрейм (1, 5, 15, 60, D)
            candle_data: Данные свечи от Bybit WebSocket
        
        Returns:
            True если успешно
        
        Example:
            candle_data = {
                'start': 1697520000000,
                'end': 1697520060000,
                'open': '28350.50',
                'high': '28365.00',
                'low': '28340.00',
                'close': '28355.25',
                'volume': '125.345',
                'turnover': '3551234.56',
                'confirm': False
            }
            
            publisher.publish_candle('BTCUSDT', '1', candle_data)
        """
        try:
            # Validate and convert to Pydantic model
            candle = CandleData(
                timestamp=candle_data.get('start', 0),
                start=candle_data.get('start', 0),
                end=candle_data.get('end', 0),
                open=Decimal(str(candle_data.get('open', 0))),
                high=Decimal(str(candle_data.get('high', 0))),
                low=Decimal(str(candle_data.get('low', 0))),
                close=Decimal(str(candle_data.get('close', 0))),
                volume=Decimal(str(candle_data.get('volume', 0))),
                turnover=Decimal(str(candle_data.get('turnover', 0))) if candle_data.get('turnover') else None,
                confirm=candle_data.get('confirm', False)
            )
            
            # Create CandleUpdate message
            update = CandleUpdate(
                type=MessageType.UPDATE,
                subscription=SubscriptionType.CANDLES,
                symbol=symbol.upper(),
                timeframe=timeframe,
                candle=candle,
                received_at=datetime.utcnow()
            )
            
            # Get channel name
            channel = self._get_channel(self.CHANNEL_CANDLES, symbol, timeframe)
            
            # Publish
            return self._publish(channel, update.model_dump(mode='json'))
            
        except Exception as e:
            logger.error(f"❌ Error publishing candle for {symbol} {timeframe}: {e}")
            self.errors_count += 1
            return False
    
    def publish_trade(self, symbol: str, trade_data: Dict[str, Any]) -> bool:
        """
        Опубликовать сделку
        
        Args:
            symbol: Торговая пара
            trade_data: Данные сделки от Bybit WebSocket
        
        Returns:
            True если успешно
        """
        try:
            # Create TradeUpdate message
            # (simplified for now, full implementation would validate trade data)
            
            channel = self._get_channel(self.CHANNEL_TRADES, symbol)
            
            message = {
                'type': MessageType.UPDATE.value,
                'subscription': SubscriptionType.TRADES.value,
                'symbol': symbol.upper(),
                'trade': trade_data,
                'received_at': datetime.utcnow().isoformat()
            }
            
            return self._publish(channel, message)
            
        except Exception as e:
            logger.error(f"❌ Error publishing trade for {symbol}: {e}")
            self.errors_count += 1
            return False
    
    def publish_ticker(self, symbol: str, ticker_data: Dict[str, Any]) -> bool:
        """
        Опубликовать обновление тикера
        
        Args:
            symbol: Торговая пара
            ticker_data: Данные тикера от Bybit WebSocket
        
        Returns:
            True если успешно
        """
        try:
            channel = self._get_channel(self.CHANNEL_TICKER, symbol)
            
            message = {
                'type': MessageType.UPDATE.value,
                'subscription': SubscriptionType.TICKER.value,
                'symbol': symbol.upper(),
                'ticker': ticker_data,
                'received_at': datetime.utcnow().isoformat()
            }
            
            return self._publish(channel, message)
            
        except Exception as e:
            logger.error(f"❌ Error publishing ticker for {symbol}: {e}")
            self.errors_count += 1
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получить статистику публикации
        
        Returns:
            Словарь со статистикой
        """
        return {
            'messages_published': self.messages_published,
            'errors_count': self.errors_count,
            'channels_active': list(self.channels_active),
            'is_available': self.is_available
        }
    
    def close(self):
        """Закрыть подключение к Redis"""
        if self._redis:
            try:
                self._redis.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self._redis = None


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_publisher_instance: Optional[WebSocketPublisher] = None


def get_publisher() -> WebSocketPublisher:
    """
    Получить singleton instance WebSocketPublisher
    
    Returns:
        WebSocketPublisher instance
    """
    global _publisher_instance
    
    if _publisher_instance is None:
        _publisher_instance = WebSocketPublisher()
    
    return _publisher_instance


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Initialize publisher
    publisher = get_publisher()
    
    # Example candle data from Bybit
    candle_data = {
        'start': 1697520000000,
        'end': 1697520060000,
        'open': '28350.50',
        'high': '28365.00',
        'low': '28340.00',
        'close': '28355.25',
        'volume': '125.345',
        'turnover': '3551234.56',
        'confirm': False
    }
    
    # Publish candle
    success = publisher.publish_candle('BTCUSDT', '1', candle_data)
    
    if success:
        print("✅ Candle published successfully")
        print(f"📊 Stats: {publisher.get_stats()}")
    else:
        print("❌ Failed to publish candle")
    
    # Close
    publisher.close()
