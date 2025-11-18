"""
RSI (Relative Strength Index) Indicator
Standard 14-period RSI implementation using Wilder's smoothing
"""

import pandas as pd
import numpy as np
from typing import Union


def calculate_rsi(data: pd.DataFrame, period: int = 14, price_col: str = 'close') -> pd.Series:
    """
    Calculate RSI (Relative Strength Index)
    
    Args:
        data: DataFrame with OHLCV data
        period: RSI period (default 14)
        price_col: Column name for price (default 'close')
    
    Returns:
        Series with RSI values (0-100)
    
    Formula:
        RS = Average Gain / Average Loss (using Wilder's smoothing)
        RSI = 100 - (100 / (1 + RS))
    """
    if len(data) < period + 1:
        return pd.Series([50.0] * len(data), index=data.index)  # Neutral RSI
    
    close = data[price_col].values
    
    # Calculate price changes
    deltas = np.diff(close)
    
    # Separate gains and losses
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    # Initialize with simple moving average for first value
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    # Wilder's smoothing (exponential moving average with alpha = 1/period)
    rsi_values = [50.0]  # First value (before enough data)
    
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        
        rsi_values.append(rsi)
    
    # Pad beginning with neutral RSI
    rsi_values = [50.0] * (len(close) - len(rsi_values)) + rsi_values
    
    return pd.Series(rsi_values, index=data.index)


def get_rsi_signal(rsi: float, oversold: float = 30.0, overbought: float = 70.0) -> str:
    """
    Get RSI signal based on thresholds
    
    Args:
        rsi: RSI value (0-100)
        oversold: Oversold threshold (default 30)
        overbought: Overbought threshold (default 70)
    
    Returns:
        'OVERSOLD', 'OVERBOUGHT', or 'NEUTRAL'
    """
    if rsi <= oversold:
        return 'OVERSOLD'
    elif rsi >= overbought:
        return 'OVERBOUGHT'
    else:
        return 'NEUTRAL'


def test_rsi():
    """Test RSI calculation with synthetic data"""
    # Create synthetic price data with known RSI behavior
    np.random.seed(42)
    
    # Uptrend (should have high RSI)
    uptrend = [50000 + i * 100 + np.random.randn() * 50 for i in range(30)]
    
    # Downtrend (should have low RSI)
    downtrend = [53000 - i * 100 + np.random.randn() * 50 for i in range(30)]
    
    prices = uptrend + downtrend
    
    df = pd.DataFrame({
        'close': prices,
        'open': prices,
        'high': [p * 1.002 for p in prices],
        'low': [p * 0.998 for p in prices],
        'volume': [1000] * len(prices)
    })
    
    rsi = calculate_rsi(df, period=14)
    
    print("RSI Test Results:")
    print(f"  Uptrend (bars 20-30): RSI={rsi.iloc[20:30].mean():.2f} (expect >60)")
    print(f"  Downtrend (bars 40-50): RSI={rsi.iloc[40:50].mean():.2f} (expect <40)")
    print(f"  Last 5 RSI values: {list(rsi.tail(5).values)}")
    
    # Test signal generation
    for i in [20, 30, 50]:
        signal = get_rsi_signal(rsi.iloc[i])
        print(f"  Bar {i}: RSI={rsi.iloc[i]:.2f} → {signal}")


if __name__ == '__main__':
    test_rsi()
