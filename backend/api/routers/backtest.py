"""
Backtest API Router - Endpoints for running backtests

Provides REST API for:
- Running backtests on historical data
- Querying backtest results
- Managing backtest configurations
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from backend.core.backtest_engine import BacktestEngine, BacktestConfig
from backend.core.order_manager import OrderType, OrderSide
from backend.services.bybit_data_loader import BybitDataLoader
from backend.dependencies import get_bybit_loader

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/backtest",
    tags=["Backtesting"],
)

# Thread pool for running backtests
executor = ThreadPoolExecutor(max_workers=4)


# ============================================================================
# Pydantic Models
# ============================================================================

class BacktestRequest(BaseModel):
    """Request to run a backtest"""
    symbol: str = Field(..., example="BTCUSDT", description="Trading pair")
    interval: str = Field(..., example="15", description="Timeframe")
    
    # Time range
    start_date: datetime = Field(..., description="Start date (ISO format)")
    end_date: datetime = Field(..., description="End date (ISO format)")
    
    # Strategy configuration
    strategy_name: str = Field(..., example="RSI Mean Reversion", description="Strategy name")
    strategy_type: str = Field("indicator", example="indicator", description="Strategy type")
    
    # Backtest parameters
    initial_capital: float = Field(10000.0, ge=100, description="Initial capital in USDT")
    leverage: float = Field(1.0, ge=1.0, le=100.0, description="Leverage multiplier")
    commission_rate: float = Field(0.0006, ge=0, description="Commission rate (0.06% = 0.0006)")
    slippage_rate: float = Field(0.0001, ge=0, description="Slippage rate (0.01% = 0.0001)")
    
    # Strategy parameters (flexible JSON)
    strategy_params: Dict[str, Any] = Field(
        default_factory=dict,
        example={"rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70},
        description="Strategy-specific parameters"
    )


class TradeResult(BaseModel):
    """Single trade result"""
    entry_time: datetime
    exit_time: datetime
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_percentage: float
    commission: float
    duration_minutes: int


class BacktestMetrics(BaseModel):
    """Backtest performance metrics"""
    total_return: float = Field(..., description="Total return %")
    annual_return: float = Field(..., description="Annualized return %")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    sortino_ratio: float = Field(..., description="Sortino ratio")
    max_drawdown: float = Field(..., description="Maximum drawdown %")
    win_rate: float = Field(..., description="Winning trades %")
    profit_factor: float = Field(..., description="Profit factor")
    total_trades: int = Field(..., description="Total number of trades")
    winning_trades: int = Field(..., description="Number of winning trades")
    losing_trades: int = Field(..., description="Number of losing trades")


class BacktestResponse(BaseModel):
    """Response after running backtest"""
    backtest_id: str
    symbol: str
    interval: str
    start_date: datetime
    end_date: datetime
    strategy_name: str
    
    # Results
    initial_capital: float
    final_capital: float
    total_return: float
    
    # Metrics
    metrics: BacktestMetrics
    
    # Trades
    total_trades: int
    trades: List[TradeResult]
    
    # Execution info
    execution_time: float = Field(..., description="Execution time in seconds")
    candles_processed: int


# ============================================================================
# Helper Functions
# ============================================================================

def run_simple_strategy(candles: List[dict], config: BacktestConfig, strategy_params: dict) -> tuple:
    """
    Run a simple indicator-based strategy
    
    This is a demo implementation. Real strategies would be in Block 5.
    """
    import pandas as pd
    from backend.core.backtest_engine import BacktestEngine
    from backend.utils.timestamp_utils import candles_to_dataframe
    
    # Convert candles to DataFrame with proper timestamp handling
    df = candles_to_dataframe(candles, set_index=True)
    
    # Validate and sanitize strategy parameters
    rsi_period = max(2, min(200, strategy_params.get('rsi_period', 14)))
    rsi_oversold = max(0, min(100, strategy_params.get('rsi_oversold', 30)))
    rsi_overbought = max(0, min(100, strategy_params.get('rsi_overbought', 70)))
    
    # Ensure logical order: oversold < overbought
    if rsi_oversold >= rsi_overbought:
        rsi_oversold = 30
        rsi_overbought = 70
    
    def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator"""
        if len(prices) < period + 1:
            return 50.0
        
        delta = prices.diff()
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        avg_gain = gains.rolling(window=period).mean().iloc[-1]
        avg_loss = losses.rolling(window=period).mean().iloc[-1]
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    # Strategy function matching BacktestEngine signature
    def strategy_func(data: pd.DataFrame, state: dict) -> dict:
        """
        Generate trading signals
        
        Args:
            data: Historical OHLCV DataFrame up to current point
            state: Strategy state dictionary
            
        Returns:
            Signal dict with 'action', 'quantity', etc.
        """
        if len(data) < rsi_period + 1:
            return {}
        
        # Calculate RSI
        rsi = calculate_rsi(data['close'], rsi_period)
        
        # Get current price
        current_price = data['close'].iloc[-1]
        
        # Determine position (from state if available)
        has_position = state.get('has_position', False)
        
        # Generate signals
        if not has_position and rsi < rsi_oversold:
            # Buy signal
            quantity = (config.initial_capital * config.leverage) / current_price
            state['has_position'] = True
            return {
                'action': 'BUY',
                'quantity': quantity,
                'price': current_price
            }
        elif has_position and rsi > rsi_overbought:
            # Sell signal
            state['has_position'] = False
            return {
                'action': 'SELL',
                'quantity': 'ALL',  # Close position
                'price': current_price
            }
        
        return {}
    
    # Run backtest
    engine = BacktestEngine(config)
    result = engine.run(df, strategy_func, warmup_periods=rsi_period)
    
    # Extract only what we need to prevent memory leak
    # (engine holds reference to full DataFrame)
    final_capital = float(engine.capital)
    
    # Clear DataFrame reference to free memory
    del df
    
    return result, final_capital


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/")
async def backtest_root():
    """
    Backtest API root endpoint
    """
    return {
        "message": "Backtest API",
        "endpoints": {
            "/run": "Run a new backtest",
            "/strategies": "Get available strategies",
            "/results/{id}": "Get backtest results by ID",
        }
    }


@router.get("/strategies")
async def get_strategies():
    """
    Get list of available strategies
    
    Returns built-in strategies that can be used for backtesting.
    (Full strategy library will be in Block 5)
    """
    return [
        {
            "name": "RSI Mean Reversion",
            "type": "indicator",
            "description": "Buy when RSI < 30, sell when RSI > 70",
            "parameters": {
                "rsi_period": {"type": "int", "default": 14, "min": 5, "max": 50},
                "rsi_oversold": {"type": "float", "default": 30, "min": 10, "max": 40},
                "rsi_overbought": {"type": "float", "default": 70, "min": 60, "max": 90},
            }
        },
        {
            "name": "SMA Crossover",
            "type": "indicator",
            "description": "Buy when fast SMA crosses above slow SMA",
            "parameters": {
                "fast_period": {"type": "int", "default": 20, "min": 5, "max": 50},
                "slow_period": {"type": "int", "default": 50, "min": 20, "max": 200},
            }
        },
        {
            "name": "Buy and Hold",
            "type": "simple",
            "description": "Buy at start, hold until end",
            "parameters": {}
        }
    ]


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    loader: BybitDataLoader = Depends(get_bybit_loader)
):
    """
    Run a backtest on historical data
    
    Example request:
    ```json
    {
        "symbol": "BTCUSDT",
        "interval": "15",
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-31T23:59:59",
        "strategy_name": "RSI Mean Reversion",
        "initial_capital": 10000,
        "leverage": 1.0,
        "strategy_params": {
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70
        }
    }
    ```
    
    Returns complete backtest results including:
    - Performance metrics (return, Sharpe, drawdown, etc.)
    - All trades executed
    - Equity curve data
    """
    try:
        logger.info(f"Starting backtest: {request.symbol} {request.interval} ({request.strategy_name})")
        
        # Normalize datetime from Pydantic (may have timezone)
        from backend.utils.timestamp_utils import normalize_timestamps
        start_date = request.start_date.replace(tzinfo=None) if request.start_date.tzinfo else request.start_date
        end_date = request.end_date.replace(tzinfo=None) if request.end_date.tzinfo else request.end_date
        
        # 1. Load historical data with error handling (using singleton loader from DI)
        try:
            candles = loader.fetch_klines_range(
                symbol=request.symbol,
                timeframe=request.interval,
                start_time=start_date,
                end_time=end_date
            )
        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise HTTPException(503, "Cannot connect to Bybit API")
        except TimeoutError as e:
            logger.error(f"Timeout error: {e}")
            raise HTTPException(504, "Bybit API request timed out")
        except Exception as e:
            logger.error(f"Unexpected error loading data: {e}")
            raise HTTPException(500, f"Failed to load data: {str(e)}")
        
        if not candles:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {request.symbol} in specified date range"
            )
        
        logger.info(f"Loaded {len(candles)} candles")
        
        # Normalize timestamps
        from backend.utils.timestamp_utils import normalize_timestamps
        normalize_timestamps(candles)
        
        # 2. Configure backtest
        config = BacktestConfig(
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            commission_rate=request.commission_rate,
            slippage_rate=request.slippage_rate,
            maintenance_margin_rate=0.005,
            liquidation_fee_rate=0.001,
            risk_free_rate=0.02,
            stop_on_liquidation=False
        )
        
        # 3. Run backtest
        import time
        start_time = time.time()
        
        result, final_capital = run_simple_strategy(candles, config, request.strategy_params)
        
        execution_time = time.time() - start_time
        
        logger.info(f"Backtest completed in {execution_time:.2f}s")
        
        # 4. Extract trades
        trades = []
        for trade in result.trades:
            trades.append(TradeResult(
                entry_time=trade.get('entry_time', datetime.now()),
                exit_time=trade.get('exit_time', datetime.now()),
                side=trade.get('side', 'LONG'),
                entry_price=float(trade.get('entry_price', 0)),
                exit_price=float(trade.get('exit_price', 0)),
                quantity=float(trade.get('quantity', 0)),
                pnl=float(trade.get('pnl', 0)),
                pnl_percentage=float(trade.get('return_pct', 0)),
                commission=float(trade.get('commission', 0)),
                duration_minutes=int(trade.get('duration_minutes', 0))
            ))
        
        # 5. Extract metrics
        metrics_data = result.metrics
        # final_capital now passed from function (no engine reference)
        total_return = ((final_capital - config.initial_capital) / config.initial_capital) * 100
        
        metrics = BacktestMetrics(
            total_return=total_return,
            annual_return=metrics_data.get('annual_return', 0),
            sharpe_ratio=metrics_data.get('sharpe_ratio', 0),
            sortino_ratio=metrics_data.get('sortino_ratio', 0),
            max_drawdown=metrics_data.get('max_drawdown', 0),
            win_rate=metrics_data.get('win_rate', 0),
            profit_factor=metrics_data.get('profit_factor', 0),
            total_trades=len(result.trades),
            winning_trades=metrics_data.get('winning_trades', 0),
            losing_trades=metrics_data.get('losing_trades', 0)
        )
        
        # 6. Build response
        response = BacktestResponse(
            backtest_id=f"bt_{int(time.time())}",
            symbol=request.symbol,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            strategy_name=request.strategy_name,
            initial_capital=request.initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            metrics=metrics,
            total_trades=len(trades),
            trades=trades,
            execution_time=execution_time,
            candles_processed=len(candles)
        )
        
        logger.info(f"Backtest successful: {len(trades)} trades, {total_return:.2f}% return")
        
        return response
        
    except Exception as e:
        logger.error(f"Backtest failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick/{symbol}/{interval}")
async def quick_backtest(
    symbol: str,
    interval: str,
    days: int = 30,
    strategy: str = "rsi"
):
    """
    Quick backtest with default parameters
    
    Convenient endpoint for testing without full configuration.
    
    Example: `/backtest/quick/BTCUSDT/15?days=30&strategy=rsi`
    """
    try:
        # Default request - use timezone-aware datetime
        now = datetime.now(timezone.utc).replace(tzinfo=None)  # UTC but naive for compatibility
        request = BacktestRequest(
            symbol=symbol,
            interval=interval,
            start_date=now - timedelta(days=days),
            end_date=now,
            strategy_name="RSI Mean Reversion" if strategy == "rsi" else "SMA Crossover",
            initial_capital=10000.0,
            leverage=1.0,
            commission_rate=0.0006,
            slippage_rate=0.0001,
            strategy_params={
                "rsi_period": 14,
                "rsi_oversold": 30,
                "rsi_overbought": 70
            }
        )
        
        return await run_backtest(request)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
