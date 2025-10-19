"""
Data API Router - Endpoints for market data

Provides REST API for:
- Loading historical data from Bybit
- Querying cached data
- Managing data downloads
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from backend.services.bybit_data_loader import BybitDataLoader
from backend.dependencies import get_bybit_loader

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/data",
    tags=["Market Data"],
)


# ============================================================================
# Pydantic Models
# ============================================================================

class CandleResponse(BaseModel):
    """Single OHLCV candle"""
    timestamp: int = Field(..., description="Unix timestamp in milliseconds")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: float = Field(..., description="Trading volume")


class DataLoadRequest(BaseModel):
    """Request to load historical data"""
    symbol: str = Field(..., example="BTCUSDT", description="Trading pair symbol")
    interval: str = Field(..., example="15", description="Timeframe (1, 5, 15, 60, D, etc.)")
    days_back: int = Field(30, ge=1, le=365, description="Number of days to load")


class DataLoadResponse(BaseModel):
    """Response after loading data"""
    symbol: str
    interval: str
    candles_loaded: int
    start_time: datetime
    end_time: datetime
    message: str


class DataQueryRequest(BaseModel):
    """Request to query existing data"""
    symbol: str = Field(..., example="BTCUSDT")
    interval: str = Field(..., example="15")
    start_time: Optional[datetime] = Field(None, description="Start time (ISO format)")
    end_time: Optional[datetime] = Field(None, description="End time (ISO format)")
    limit: int = Field(1000, ge=1, le=10000, description="Max number of candles")


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/")
async def data_root():
    """
    Data API root endpoint
    
    Returns available endpoints and their descriptions
    """
    return {
        "message": "Market Data API",
        "endpoints": {
            "/load": "Load historical data from Bybit",
            "/query": "Query cached data",
            "/symbols": "Get available symbols",
            "/intervals": "Get supported timeframes",
        }
    }


@router.get("/symbols", response_model=List[str])
async def get_symbols():
    """
    Get list of available trading symbols
    
    Returns commonly used USDT perpetual pairs
    """
    return [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "ADAUSDT",
        "DOGEUSDT",
        "AVAXUSDT",
        "DOTUSDT",
        "MATICUSDT",
    ]


@router.get("/intervals", response_model=List[str])
async def get_intervals():
    """
    Get list of supported timeframes
    
    Returns all available intervals from Bybit API
    """
    return [
        "1",    # 1 minute
        "3",    # 3 minutes
        "5",    # 5 minutes
        "15",   # 15 minutes
        "30",   # 30 minutes
        "60",   # 1 hour
        "120",  # 2 hours
        "240",  # 4 hours
        "360",  # 6 hours
        "720",  # 12 hours
        "D",    # 1 day
        "W",    # 1 week
        "M",    # 1 month
    ]


@router.post("/load", response_model=DataLoadResponse)
async def load_data(
    request: DataLoadRequest,
    loader: BybitDataLoader = Depends(get_bybit_loader)
):
    """
    Load historical data from Bybit API
    
    Downloads OHLCV candles for specified symbol and timeframe.
    Data is loaded from Bybit public API (no authentication required).
    
    Example request:
    ```json
    {
        "symbol": "BTCUSDT",
        "interval": "15",
        "days_back": 30
    }
    ```
    
    Returns:
    - Number of candles loaded
    - Time range covered
    - Status message
    """
    try:
        logger.info(f"Loading data: {request.symbol} {request.interval} ({request.days_back} days)")
        
        # Calculate limit based on days
        if request.interval in ['1', '5', '15', '60']:  # Minutes
            limit = min(request.days_back * 24 * 60 // int(request.interval), 1000)
        elif request.interval == 'D':
            limit = request.days_back
        elif request.interval == 'W':
            limit = request.days_back // 7
        else:
            limit = 200
        
        # Load data with error handling
        try:
            candles = loader.fetch_klines(
                symbol=request.symbol,
                timeframe=request.interval,
                limit=min(limit, 1000)
            )
        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise HTTPException(503, "Cannot connect to Bybit API")
        except TimeoutError as e:
            logger.error(f"Timeout error: {e}")
            raise HTTPException(504, "Bybit API request timed out")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(500, f"Failed to load data: {str(e)}")
        
        if not candles:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {request.symbol} {request.interval}"
            )
        
        # Normalize timestamps
        from backend.utils.timestamp_utils import normalize_timestamps
        normalize_timestamps(candles)
        
        # Get actual time range
        actual_start = candles[0]['timestamp']
        actual_end = candles[-1]['timestamp']
        
        logger.info(f"Successfully loaded {len(candles)} candles")
        
        return DataLoadResponse(
            symbol=request.symbol,
            interval=request.interval,
            candles_loaded=len(candles),
            start_time=actual_start,
            end_time=actual_end,
            message=f"Successfully loaded {len(candles)} candles from Bybit"
        )
        
    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=List[CandleResponse])
async def query_data(
    request: DataQueryRequest,
    loader: BybitDataLoader = Depends(get_bybit_loader)
):
    """
    Query historical data (from cache or fresh from Bybit)
    
    Returns OHLCV candles for specified parameters.
    If data is not cached, it will be loaded from Bybit.
    
    Example request:
    ```json
    {
        "symbol": "BTCUSDT",
        "interval": "15",
        "limit": 1000
    }
    ```
    
    Returns array of candles in descending order (newest first)
    """
    try:
        logger.info(f"Querying data: {request.symbol} {request.interval}")
        
        # Load data with error handling
        try:
            candles = loader.fetch_klines(
                symbol=request.symbol,
                timeframe=request.interval,
                limit=min(request.limit, 1000)
            )
        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise HTTPException(503, "Cannot connect to Bybit API")
        except TimeoutError as e:
            logger.error(f"Timeout error: {e}")
            raise HTTPException(504, "Bybit API request timed out")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(500, f"Failed to load data: {str(e)}")
        
        if not candles:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {request.symbol} {request.interval}"
            )
        
        # Filter by time range if specified
        if request.start_time and request.end_time:
            candles = [
                c for c in candles
                if request.start_time <= c['timestamp'] <= request.end_time
            ]
        
        # Convert to response format
        response = [
            CandleResponse(
                timestamp=int(c['timestamp'].timestamp() * 1000),
                open=float(c['open']),
                high=float(c['high']),
                low=float(c['low']),
                close=float(c['close']),
                volume=float(c['volume'])
            )
            for c in candles
        ]
        
        logger.info(f"Returning {len(response)} candles")
        
        return response
        
    except Exception as e:
        logger.error(f"Error querying data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest/{symbol}/{interval}", response_model=List[CandleResponse])
async def get_latest_candles(
    symbol: str,
    interval: str,
    limit: int = Query(100, ge=1, le=1000, description="Number of candles"),
    loader: BybitDataLoader = Depends(get_bybit_loader)
):
    """
    Get latest N candles for symbol
    
    Quick endpoint for getting recent data.
    
    Example: `/data/latest/BTCUSDT/15?limit=100`
    
    Returns array of latest candles
    """
    try:
        
        # Load data with error handling
        try:
            candles = loader.fetch_klines(
                symbol=symbol,
                timeframe=interval,
                limit=limit
            )
        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise HTTPException(503, "Cannot connect to Bybit API")
        except TimeoutError as e:
            logger.error(f"Timeout error: {e}")
            raise HTTPException(504, "Bybit API request timed out")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(500, f"Failed to load data: {str(e)}")
        
        if not candles:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {symbol} {interval}"
            )
        
        return {
            "symbol": symbol,
            "interval": interval,
            "count": len(candles),
            "candles": candles
        }
        
    except Exception as e:
        logger.error(f"Error getting latest candles: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
