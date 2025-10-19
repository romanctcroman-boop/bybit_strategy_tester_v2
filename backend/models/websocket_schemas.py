"""
WebSocket Data Schemas

Pydantic models for WebSocket real-time data validation
and serialization.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class SubscriptionType(str, Enum):
    """WebSocket subscription types"""
    CANDLES = "candles"
    TRADES = "trades"
    TICKER = "ticker"
    ORDERBOOK = "orderbook"


class CandleStatus(str, Enum):
    """Candle status from Bybit"""
    ONGOING = "ongoing"      # Candle is being updated
    CONFIRMED = "confirmed"  # Candle is closed and final


class MessageType(str, Enum):
    """WebSocket message types"""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    UPDATE = "update"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    SNAPSHOT = "snapshot"


# ============================================================================
# CANDLE DATA MODELS
# ============================================================================

class CandleData(BaseModel):
    """
    Single candle (kline) from Bybit WebSocket
    
    Based on Bybit API v5 kline format:
    https://bybit-exchange.github.io/docs/v5/websocket/public/kline
    """
    
    # Timing
    timestamp: int = Field(..., description="Candle start time (ms)")
    start: int = Field(..., description="Candle start time (ms)")
    end: int = Field(..., description="Candle end time (ms)")
    
    # OHLCV
    open: Decimal = Field(..., description="Open price")
    high: Decimal = Field(..., description="High price")
    low: Decimal = Field(..., description="Low price")
    close: Decimal = Field(..., description="Close price")
    volume: Decimal = Field(..., description="Trading volume")
    
    # Trading metadata
    turnover: Optional[Decimal] = Field(None, description="Turnover (volume * price)")
    
    # Candle state
    confirm: bool = Field(..., description="True if candle is closed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": 1697520000000,
                "start": 1697520000000,
                "end": 1697520060000,
                "open": "28350.50",
                "high": "28365.00",
                "low": "28340.00",
                "close": "28355.25",
                "volume": "125.345",
                "turnover": "3551234.56",
                "confirm": False
            }
        }
    
    @validator('timestamp', 'start', 'end')
    def validate_timestamp(cls, v):
        """Validate timestamp is reasonable (after 2020-01-01)"""
        if v < 1577836800000:  # 2020-01-01 in milliseconds
            raise ValueError("Timestamp must be after 2020-01-01")
        return v
    
    @validator('high')
    def validate_high(cls, v, values):
        """High must be >= open, close, low"""
        if 'open' in values and v < values['open']:
            raise ValueError("High must be >= open")
        if 'close' in values and v < values['close']:
            raise ValueError("High must be >= close")
        if 'low' in values and v < values['low']:
            raise ValueError("High must be >= low")
        return v
    
    @validator('low')
    def validate_low(cls, v, values):
        """Low must be <= open, close"""
        if 'open' in values and v > values['open']:
            raise ValueError("Low must be <= open")
        if 'close' in values and v > values['close']:
            raise ValueError("Low must be <= close")
        return v
    
    @validator('volume', 'turnover')
    def validate_positive(cls, v):
        """Volume and turnover must be positive"""
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative")
        return v


class CandleUpdate(BaseModel):
    """
    WebSocket candle update message
    
    Sent to frontend clients when new candle data arrives
    """
    
    type: MessageType = Field(MessageType.UPDATE, description="Message type")
    subscription: SubscriptionType = Field(SubscriptionType.CANDLES, description="Subscription type")
    
    symbol: str = Field(..., description="Trading pair (BTCUSDT)")
    timeframe: str = Field(..., description="Timeframe (1, 5, 15, 60, D)")
    
    candle: CandleData = Field(..., description="Candle data")
    
    received_at: datetime = Field(default_factory=datetime.utcnow, description="Server receive time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "update",
                "subscription": "candles",
                "symbol": "BTCUSDT",
                "timeframe": "1",
                "candle": {
                    "timestamp": 1697520000000,
                    "start": 1697520000000,
                    "end": 1697520060000,
                    "open": "28350.50",
                    "high": "28365.00",
                    "low": "28340.00",
                    "close": "28355.25",
                    "volume": "125.345",
                    "confirm": False
                },
                "received_at": "2024-10-17T10:00:00.123456Z"
            }
        }
    
    @validator('symbol')
    def validate_symbol(cls, v):
        """Symbol must be uppercase"""
        return v.upper()
    
    @validator('timeframe')
    def validate_timeframe(cls, v):
        """Validate timeframe is supported"""
        valid_timeframes = ['1', '3', '5', '15', '30', '60', '120', '240', 'D', 'W', 'M']
        if v not in valid_timeframes:
            raise ValueError(f"Invalid timeframe. Must be one of: {', '.join(valid_timeframes)}")
        return v


# ============================================================================
# TRADE DATA MODELS
# ============================================================================

class TradeData(BaseModel):
    """Single trade from Bybit WebSocket"""
    
    timestamp: int = Field(..., description="Trade timestamp (ms)")
    symbol: str = Field(..., description="Trading pair")
    side: str = Field(..., description="Buy or Sell")
    price: Decimal = Field(..., description="Trade price")
    size: Decimal = Field(..., description="Trade size")
    trade_id: str = Field(..., description="Unique trade ID")
    
    @validator('side')
    def validate_side(cls, v):
        """Side must be Buy or Sell"""
        if v not in ['Buy', 'Sell']:
            raise ValueError("Side must be 'Buy' or 'Sell'")
        return v


class TradeUpdate(BaseModel):
    """WebSocket trade update message"""
    
    type: MessageType = Field(MessageType.UPDATE, description="Message type")
    subscription: SubscriptionType = Field(SubscriptionType.TRADES, description="Subscription type")
    
    symbol: str = Field(..., description="Trading pair")
    trades: List[TradeData] = Field(..., description="List of trades")
    
    received_at: datetime = Field(default_factory=datetime.utcnow, description="Server receive time")


# ============================================================================
# TICKER DATA MODELS
# ============================================================================

class TickerData(BaseModel):
    """24h ticker statistics from Bybit WebSocket"""
    
    symbol: str = Field(..., description="Trading pair")
    last_price: Decimal = Field(..., description="Last traded price")
    prev_price_24h: Optional[Decimal] = Field(None, description="Price 24h ago")
    price_24h_pcnt: Optional[Decimal] = Field(None, description="24h price change %")
    high_price_24h: Optional[Decimal] = Field(None, description="24h high")
    low_price_24h: Optional[Decimal] = Field(None, description="24h low")
    volume_24h: Optional[Decimal] = Field(None, description="24h volume")
    turnover_24h: Optional[Decimal] = Field(None, description="24h turnover")


class TickerUpdate(BaseModel):
    """WebSocket ticker update message"""
    
    type: MessageType = Field(MessageType.UPDATE, description="Message type")
    subscription: SubscriptionType = Field(SubscriptionType.TICKER, description="Subscription type")
    
    ticker: TickerData = Field(..., description="Ticker data")
    
    received_at: datetime = Field(default_factory=datetime.utcnow, description="Server receive time")


# ============================================================================
# SUBSCRIPTION MANAGEMENT
# ============================================================================

class WebSocketSubscription(BaseModel):
    """WebSocket subscription request from client"""
    
    action: str = Field(..., description="subscribe or unsubscribe")
    type: SubscriptionType = Field(..., description="Subscription type")
    
    symbol: str = Field(..., description="Trading pair (BTCUSDT)")
    timeframe: Optional[str] = Field(None, description="Timeframe for candles (1, 5, 15, etc.)")
    
    @validator('action')
    def validate_action(cls, v):
        """Action must be subscribe or unsubscribe"""
        if v not in ['subscribe', 'unsubscribe']:
            raise ValueError("Action must be 'subscribe' or 'unsubscribe'")
        return v
    
    @validator('symbol')
    def validate_symbol(cls, v):
        """Symbol must be uppercase"""
        return v.upper()
    
    @validator('timeframe')
    def validate_timeframe_required(cls, v, values):
        """Timeframe required for candles subscription"""
        if 'type' in values and values['type'] == SubscriptionType.CANDLES and not v:
            raise ValueError("Timeframe is required for candles subscription")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "action": "subscribe",
                "type": "candles",
                "symbol": "BTCUSDT",
                "timeframe": "1"
            }
        }


class SubscriptionResponse(BaseModel):
    """Response to subscription request"""
    
    success: bool = Field(..., description="Subscription successful")
    message: str = Field(..., description="Response message")
    subscription: Optional[WebSocketSubscription] = Field(None, description="Subscription details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Successfully subscribed to BTCUSDT candles (1m)",
                "subscription": {
                    "action": "subscribe",
                    "type": "candles",
                    "symbol": "BTCUSDT",
                    "timeframe": "1"
                }
            }
        }


# ============================================================================
# ERROR HANDLING
# ============================================================================

class WebSocketError(BaseModel):
    """WebSocket error message"""
    
    type: MessageType = Field(MessageType.ERROR, description="Message type")
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "error",
                "error_code": "INVALID_SYMBOL",
                "error_message": "Trading pair 'INVALID' not found",
                "details": {"symbol": "INVALID"},
                "timestamp": "2024-10-17T10:00:00.123456Z"
            }
        }


# ============================================================================
# HEARTBEAT
# ============================================================================

class HeartbeatMessage(BaseModel):
    """WebSocket heartbeat/ping message"""
    
    type: MessageType = Field(MessageType.HEARTBEAT, description="Message type")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Heartbeat timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "heartbeat",
                "timestamp": "2024-10-17T10:00:00.123456Z"
            }
        }


# ============================================================================
# SNAPSHOT (Initial State)
# ============================================================================

class CandleSnapshot(BaseModel):
    """Initial snapshot of recent candles"""
    
    type: MessageType = Field(MessageType.SNAPSHOT, description="Message type")
    subscription: SubscriptionType = Field(SubscriptionType.CANDLES, description="Subscription type")
    
    symbol: str = Field(..., description="Trading pair")
    timeframe: str = Field(..., description="Timeframe")
    
    candles: List[CandleData] = Field(..., description="Recent candles (e.g., last 100)")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Snapshot timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "snapshot",
                "subscription": "candles",
                "symbol": "BTCUSDT",
                "timeframe": "1",
                "candles": [
                    {
                        "timestamp": 1697520000000,
                        "start": 1697520000000,
                        "end": 1697520060000,
                        "open": "28350.50",
                        "high": "28365.00",
                        "low": "28340.00",
                        "close": "28355.25",
                        "volume": "125.345",
                        "confirm": True
                    }
                ],
                "timestamp": "2024-10-17T10:00:00.123456Z"
            }
        }
