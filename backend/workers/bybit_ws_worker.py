"""
Bybit WebSocket Worker

Background worker that subscribes to Bybit WebSocket streams
and publishes data to Redis Pub/Sub for consumption by frontend clients.

Architecture:
    Bybit WebSocket API → BybitWebSocketWorker → Redis Pub/Sub → FastAPI WebSocket → Frontend

Usage:
    python -m backend.workers.bybit_ws_worker
    
    # With custom subscriptions
    python -m backend.workers.bybit_ws_worker --symbols BTCUSDT,ETHUSDT --timeframes 1,5,15
"""

import sys
import time
import argparse
import signal
from typing import List, Set
from loguru import logger

from backend.services.websocket_manager import WebSocketManager
from backend.services.websocket_publisher import get_publisher
from backend.core.config import settings


class BybitWebSocketWorker:
    """
    Background worker для подключения к Bybit WebSocket
    и публикации данных в Redis Pub/Sub
    
    Features:
        - Multi-symbol, multi-timeframe subscriptions
        - Automatic reconnection
        - Redis Pub/Sub publishing
        - Graceful shutdown
        - Statistics tracking
    """
    
    # Default subscriptions
    DEFAULT_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    DEFAULT_TIMEFRAMES = ['1', '5', '15']  # 1m, 5m, 15m
    
    def __init__(
        self,
        symbols: List[str] = None,
        timeframes: List[str] = None,
        testnet: bool = False
    ):
        """
        Инициализация worker
        
        Args:
            symbols: Список торговых пар (default: BTC, ETH, SOL)
            timeframes: Список таймфреймов (default: 1m, 5m, 15m)
            testnet: Использовать testnet (default: False)
        """
        self.symbols = symbols or self.DEFAULT_SYMBOLS
        self.timeframes = timeframes or self.DEFAULT_TIMEFRAMES
        self.testnet = testnet
        
        # WebSocket manager
        self.ws_manager = WebSocketManager(testnet=testnet)
        
        # Redis publisher
        self.publisher = get_publisher()
        
        # Running state
        self.running = False
        
        # Statistics
        self.candles_received = 0
        self.candles_published = 0
        self.errors_count = 0
        
        # Active subscriptions tracking
        self.active_subscriptions: Set[str] = set()
        
        logger.info("="*70)
        logger.info("Bybit WebSocket Worker Initialized")
        logger.info("="*70)
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Timeframes: {', '.join(self.timeframes)}")
        logger.info(f"Testnet: {self.testnet}")
        logger.info(f"Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        logger.info("="*70)
    
    def _handle_candle(self, symbol: str, timeframe: str):
        """
        Создать callback handler для candle updates
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм
        
        Returns:
            Callback функция
        """
        def callback(data):
            """Handle candle data from Bybit WebSocket"""
            try:
                self.candles_received += 1
                
                # Data is a list from Bybit
                if not isinstance(data, list) or len(data) == 0:
                    logger.warning(f"Invalid candle data format for {symbol} {timeframe}")
                    return
                
                # Extract first candle
                candle_raw = data[0]
                
                # Log sample (every 10th candle)
                if self.candles_received % 10 == 0:
                    logger.debug(
                        f"🕯️  {symbol} {timeframe}m: "
                        f"O={candle_raw.get('open')} "
                        f"H={candle_raw.get('high')} "
                        f"L={candle_raw.get('low')} "
                        f"C={candle_raw.get('close')} "
                        f"V={candle_raw.get('volume')} "
                        f"[{'✅' if candle_raw.get('confirm') else '⏳'}]"
                    )
                
                # Publish to Redis Pub/Sub
                success = self.publisher.publish_candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_data=candle_raw
                )
                
                if success:
                    self.candles_published += 1
                else:
                    self.errors_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Error handling candle for {symbol} {timeframe}: {e}")
                self.errors_count += 1
        
        return callback
    
    def _subscribe_all(self):
        """Подписаться на все комбинации symbol x timeframe"""
        logger.info("\n📡 Setting up subscriptions...")
        
        subscription_count = 0
        
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                try:
                    # Create callback for this specific symbol/timeframe
                    callback = self._handle_candle(symbol, timeframe)
                    
                    # Subscribe via WebSocketManager
                    self.ws_manager.subscribe_kline(
                        symbol=symbol,
                        interval=timeframe,
                        callback=callback
                    )
                    
                    # Track subscription
                    sub_key = f"{symbol}:{timeframe}"
                    self.active_subscriptions.add(sub_key)
                    
                    subscription_count += 1
                    logger.info(f"  ✅ {sub_key}")
                    
                except Exception as e:
                    logger.error(f"  ❌ Failed to subscribe {symbol} {timeframe}: {e}")
        
        logger.info(f"\n✅ Total subscriptions: {subscription_count}")
        logger.info(f"📊 Expected channels: {len(self.active_subscriptions)}\n")
    
    def start(self):
        """Запустить worker"""
        if self.running:
            logger.warning("Worker already running")
            return
        
        logger.info("🚀 Starting Bybit WebSocket Worker...")
        
        # Check Redis availability
        if not self.publisher.is_available:
            logger.error("❌ Redis is not available! Worker cannot start.")
            logger.error("   Please ensure Redis is running:")
            logger.error("   - Windows: Start-Service Redis")
            logger.error("   - Linux: sudo systemctl start redis")
            return
        
        logger.info("✅ Redis connection verified")
        
        # Set up subscriptions
        self._subscribe_all()
        
        # Start WebSocket manager
        self.ws_manager.start()
        
        # Wait for connection
        time.sleep(2)
        
        if self.ws_manager.connected:
            logger.info("✅ WebSocket connected to Bybit")
            self.running = True
        else:
            logger.error("❌ Failed to connect to Bybit WebSocket")
            return
        
        logger.info("\n" + "="*70)
        logger.info("🎉 WORKER IS RUNNING")
        logger.info("="*70)
        logger.info("Real-time candle data is being published to Redis Pub/Sub")
        logger.info("Frontend clients can subscribe via FastAPI WebSocket endpoints")
        logger.info("")
        logger.info("Press Ctrl+C to stop")
        logger.info("="*70 + "\n")
    
    def stop(self):
        """Остановить worker"""
        if not self.running:
            return
        
        logger.info("\n🛑 Stopping Bybit WebSocket Worker...")
        
        self.running = False
        
        # Stop WebSocket manager
        self.ws_manager.stop()
        
        # Close Redis publisher
        self.publisher.close()
        
        # Print statistics
        self._print_stats()
        
        logger.info("✅ Worker stopped gracefully")
    
    def _print_stats(self):
        """Вывести статистику"""
        logger.info("\n" + "="*70)
        logger.info("📊 WORKER STATISTICS")
        logger.info("="*70)
        
        # WebSocket stats
        ws_stats = self.ws_manager.get_stats()
        logger.info(f"WebSocket:")
        logger.info(f"  Messages received: {ws_stats.get('messages_received', 0)}")
        logger.info(f"  Reconnect attempts: {ws_stats.get('reconnect_attempts', 0)}")
        logger.info(f"  Last message: {ws_stats.get('last_message_time', 'N/A')}")
        
        # Publisher stats
        pub_stats = self.publisher.get_stats()
        logger.info(f"\nRedis Publisher:")
        logger.info(f"  Messages published: {pub_stats.get('messages_published', 0)}")
        logger.info(f"  Active channels: {len(pub_stats.get('channels_active', []))}")
        logger.info(f"  Errors: {pub_stats.get('errors_count', 0)}")
        
        # Worker stats
        logger.info(f"\nWorker:")
        logger.info(f"  Candles received: {self.candles_received}")
        logger.info(f"  Candles published: {self.candles_published}")
        logger.info(f"  Errors: {self.errors_count}")
        logger.info(f"  Active subscriptions: {len(self.active_subscriptions)}")
        
        # Publish rate
        if self.candles_received > 0:
            success_rate = (self.candles_published / self.candles_received) * 100
            logger.info(f"  Success rate: {success_rate:.2f}%")
        
        logger.info("="*70 + "\n")
    
    def run_forever(self):
        """Запустить и держать worker активным"""
        self.start()
        
        if not self.running:
            return
        
        try:
            # Main loop - print stats every 60 seconds
            while self.running:
                time.sleep(60)
                
                logger.info(
                    f"[Status] Candles: {self.candles_received} received, "
                    f"{self.candles_published} published, "
                    f"{self.errors_count} errors"
                )
                
        except KeyboardInterrupt:
            logger.info("\n⚠️  Received interrupt signal")
        except Exception as e:
            logger.error(f"❌ Worker error: {e}")
        finally:
            self.stop()


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main():
    """CLI entry point"""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Bybit WebSocket Worker')
    
    parser.add_argument(
        '--symbols',
        type=str,
        default='BTCUSDT,ETHUSDT,SOLUSDT',
        help='Comma-separated list of symbols (default: BTCUSDT,ETHUSDT,SOLUSDT)'
    )
    
    parser.add_argument(
        '--timeframes',
        type=str,
        default='1,5,15',
        help='Comma-separated list of timeframes in minutes (default: 1,5,15)'
    )
    
    parser.add_argument(
        '--testnet',
        action='store_true',
        help='Use Bybit testnet instead of mainnet'
    )
    
    args = parser.parse_args()
    
    # Parse symbols and timeframes
    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    timeframes = [t.strip() for t in args.timeframes.split(',')]
    
    # Create worker
    worker = BybitWebSocketWorker(
        symbols=symbols,
        timeframes=timeframes,
        testnet=args.testnet
    )
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"\n⚠️  Received signal {sig}")
        worker.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run worker
    worker.run_forever()


if __name__ == "__main__":
    main()
