"""
📊 L2 Order Book Module

WebSocket collector for L2 order book data.

@version: 1.0.0
@date: 2026-02-26
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import websockets

logger = logging.getLogger(__name__)


@dataclass
class L2Snapshot:
    """L2 order book snapshot"""
    symbol: str
    bids: List[Dict[str, float]]  # [{price, quantity}]
    asks: List[Dict[str, float]]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'bids': self.bids,
            'asks': self.asks,
            'timestamp': self.timestamp.isoformat(),
        }


class L2OrderBookCollector:
    """
    L2 Order Book WebSocket Collector.
    
    Collects real-time order book data from Bybit.
    """
    
    # WebSocket URLs
    MAINNET_URL = "wss://stream.bybit.com/v5/public/linear"
    TESTNET_URL = "wss://stream-testnet.bybit.com/v5/public/linear"
    
    def __init__(
        self,
        symbol: str = 'BTCUSDT',
        testnet: bool = True,
        depth: int = 50,
    ):
        """
        Args:
            symbol: Trading pair symbol
            testnet: Use testnet
            depth: Order book depth (1, 50, 500)
        """
        self.symbol = symbol
        self.testnet = testnet
        self.depth = depth
        self.url = self.TESTNET_URL if testnet else self.MAINNET_URL
        
        # WebSocket connection
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        
        # Order book state
        self.current_snapshot: Optional[L2Snapshot] = None
        self.snapshots: List[L2Snapshot] = []
        
        # Running flag
        self._running = False
    
    async def connect(self):
        """Connect to WebSocket"""
        try:
            self.ws = await websockets.connect(self.url)
            self.connected = True
            logger.info(f"Connected to {self.url}")
            
            # Subscribe to order book
            await self._subscribe()
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            raise
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self._running = False
        
        if self.ws:
            await self.ws.close()
        
        self.connected = False
        logger.info("Disconnected")
    
    async def _subscribe(self):
        """Subscribe to order book"""
        if not self.connected:
            await self.connect()
        
        topic = f"orderbook.{self.depth}.{self.symbol}"
        
        message = {
            "op": "subscribe",
            "args": [topic]
        }
        
        await self.ws.send(json.dumps(message))
        logger.info(f"Subscribed to {topic}")
    
    async def _receive_messages(self):
        """Receive messages"""
        try:
            async for message in self.ws:
                await self._handle_message(message)
        except websockets.ConnectionClosed:
            logger.warning("Connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"Receive error: {e}")
            self.connected = False
    
    async def _handle_message(self, raw_message: str):
        """Handle message"""
        try:
            data = json.loads(raw_message)
            
            # Subscription response
            if "op" in data and data["op"] == "subscribe":
                logger.debug(f"Subscribed: {data.get('topic', 'unknown')}")
                return
            
            # Data message
            if "topic" in data and "data" in data:
                snapshot = self._parse_snapshot(data["data"])
                
                if snapshot:
                    self.current_snapshot = snapshot
                    self.snapshots.append(snapshot)
                    
                    logger.debug(f"Received snapshot: {len(snapshot.bids)} bids, {len(snapshot.asks)} asks")
            
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    def _parse_snapshot(self, data: Dict[str, Any]) -> Optional[L2Snapshot]:
        """Parse snapshot from data"""
        try:
            bids = [
                {'price': float(b[0]), 'quantity': float(b[1])}
                for b in data.get('b', [])
            ]
            
            asks = [
                {'price': float(a[0]), 'quantity': float(a[1])}
                for a in data.get('a', [])
            ]
            
            return L2Snapshot(
                symbol=self.symbol,
                bids=bids,
                asks=asks,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return None
    
    async def start(self):
        """Start collector"""
        self._running = True
        
        await self.connect()
        
        # Start receive loop
        asyncio.create_task(self._receive_messages())
        
        logger.info("L2 collector started")
    
    async def run_forever(self):
        """Run forever with reconnect"""
        while True:
            try:
                await self.start()
                
                while self._running and self.connected:
                    await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error: {e}")
            
            if not self._running:
                break
            
            # Reconnect
            logger.info("Reconnecting in 5s...")
            await asyncio.sleep(5)
    
    def get_current_snapshot(self) -> Optional[L2Snapshot]:
        """Get current snapshot"""
        return self.current_snapshot
    
    def get_snapshots(self, limit: int = 100) -> List[L2Snapshot]:
        """Get recent snapshots"""
        return self.snapshots[-limit:]
    
    def save_snapshots(self, filename: str):
        """Save snapshots to file"""
        import json
        
        data = [s.to_dict() for s in self.snapshots]
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved {len(data)} snapshots to {filename}")
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate order book metrics"""
        if not self.current_snapshot:
            return {}
        
        snapshot = self.current_snapshot
        
        # Bid/ask spread
        best_bid = snapshot.bids[0]['price'] if snapshot.bids else 0
        best_ask = snapshot.asks[0]['price'] if snapshot.asks else 0
        spread = best_ask - best_bid
        spread_pct = (spread / best_bid * 100) if best_bid > 0 else 0
        
        # Order book imbalance
        bid_volume = sum(b['quantity'] for b in snapshot.bids)
        ask_volume = sum(a['quantity'] for a in snapshot.asks)
        total_volume = bid_volume + ask_volume
        imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0
        
        # Mid price
        mid_price = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0
        
        return {
            'spread': spread,
            'spread_pct': spread_pct,
            'best_bid': best_bid,
            'best_ask': best_ask,
            'mid_price': mid_price,
            'bid_volume': bid_volume,
            'ask_volume': ask_volume,
            'imbalance': imbalance,
        }


# ---------------------------------------------------------------------------
# Module-level helper (used by tests and replay utilities)
# ---------------------------------------------------------------------------

def snapshot_to_dict(snapshot: L2Snapshot) -> Dict[str, Any]:
    """Convert an :class:`L2Snapshot` to a plain dictionary.

    Args:
        snapshot: The snapshot to serialise.

    Returns:
        Dictionary with ``symbol``, ``bids``, ``asks``, and ``timestamp``.
    """
    return snapshot.to_dict()
