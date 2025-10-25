"""
Generate synthetic market data for testing.
"""

import os
import sys
from datetime import datetime, timedelta, UTC

import pandas as pd
import numpy as np

sys.path.insert(0, "D:/bybit_strategy_tester_v2")

from backend.database import SessionLocal
from backend.models import MarketData


def generate_synthetic_candles(
    start_date: datetime,
    end_date: datetime,
    interval_minutes: int = 15,
    initial_price: float = 67000.0,
    volatility: float = 0.01,
    trend: float = 0.0001,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV candles.
    
    Args:
        start_date: Start time
        end_date: End time
        interval_minutes: Candle interval in minutes
        initial_price: Starting price
        volatility: Price volatility (std dev as fraction of price)
        trend: Trend (drift per candle as fraction of price)
    
    Returns:
        DataFrame with timestamp, open, high, low, close, volume
    """
    # Generate timestamps
    current = start_date
    timestamps = []
    
    while current <= end_date:
        timestamps.append(current)
        current += timedelta(minutes=interval_minutes)
    
    n_candles = len(timestamps)
    
    # Generate price movement
    np.random.seed(42)  # For reproducibility
    
    prices = [initial_price]
    
    for i in range(1, n_candles):
        # Random walk with drift
        change = np.random.normal(trend, volatility)
        new_price = prices[-1] * (1 + change)
        prices.append(max(new_price, 1000.0))  # Prevent negative prices
    
    # Generate OHLC from close prices
    data = []
    
    for i, (ts, close) in enumerate(zip(timestamps, prices)):
        # Randomize intrabar movement
        high_factor = 1 + abs(np.random.normal(0, volatility / 2))
        low_factor = 1 - abs(np.random.normal(0, volatility / 2))
        
        open_price = prices[i - 1] if i > 0 else close
        high = max(open_price, close) * high_factor
        low = min(open_price, close) * low_factor
        volume = np.random.uniform(100, 1000)
        
        data.append({
            'timestamp': ts,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
        })
    
    return pd.DataFrame(data)


def main():
    """Generate and save synthetic data."""
    print("🧪 Generating synthetic market data...")
    
    # Generate 7 days of 15min candles
    end_date = datetime.now(UTC).replace(microsecond=0)
    start_date = end_date - timedelta(days=7)
    
    df = generate_synthetic_candles(
        start_date=start_date,
        end_date=end_date,
        interval_minutes=15,
        initial_price=67000.0,
        volatility=0.01,  # 1% volatility
        trend=0.0001,  # Slight uptrend
    )
    
    print(f"✅ Generated {len(df)} candles")
    print(f"   Period: {df['timestamp'].min()} → {df['timestamp'].max()}")
    print(f"   Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    
    # Save to database
    print("\n💾 Saving to database...")
    
    with SessionLocal() as session:
        # Delete existing data for this symbol/interval
        existing = session.query(MarketData).filter(
            MarketData.symbol == 'BTCUSDT',
            MarketData.interval == '15'
        ).count()
        
        if existing > 0:
            print(f"   Deleting {existing} existing candles...")
            session.query(MarketData).filter(
                MarketData.symbol == 'BTCUSDT',
                MarketData.interval == '15'
            ).delete()
            session.commit()
        
        # Insert new data
        for idx, row in df.iterrows():
            candle = MarketData(
                symbol='BTCUSDT',
                interval='15',
                timestamp=row['timestamp'],
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume'],
            )
            session.add(candle)
        
        session.commit()
        print(f"✅ Saved {len(df)} candles to database")
    
    # Verify
    with SessionLocal() as session:
        count = session.query(MarketData).filter(
            MarketData.symbol == 'BTCUSDT',
            MarketData.interval == '15'
        ).count()
        print(f"\n✅ Verification: {count} candles in database")


if __name__ == "__main__":
    main()
