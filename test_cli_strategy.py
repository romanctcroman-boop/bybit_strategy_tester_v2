import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict, Any


class SMACrossoverStrategy:
    """
    Simple Moving Average Crossover Strategy
    
    This strategy generates buy/sell signals based on the crossover
    of two simple moving averages (SMA).
    
    Parameters:
    -----------
    fast_period : int
        Period for the fast moving average (default: 20)
    slow_period : int
        Period for the slow moving average (default: 50)
    """
    
    def __init__(self, fast_period: int = 20, slow_period: int = 50):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.validate_parameters()
        
    def validate_parameters(self) -> None:
        """Validate strategy parameters"""
        if self.fast_period >= self.slow_period:
            raise ValueError("Fast period must be less than slow period")
        if self.fast_period <= 0 or self.slow_period <= 0:
            raise ValueError("Periods must be positive integers")
    
    def calculate_sma(self, data: pd.Series, period: int) -> pd.Series:
        """
        Calculate Simple Moving Average
        
        Parameters:
        -----------
        data : pd.Series
            Price data series
        period : int
            Moving average period
            
        Returns:
        --------
        pd.Series
            Simple moving average values
        """
        try:
            return data.rolling(window=period, min_periods=period).mean()
        except Exception as e:
            raise ValueError(f"Error calculating SMA: {str(e)}")
    
    def generate_signals(self, df: pd.DataFrame, price_column: str = 'close') -> pd.DataFrame:
        """
        Generate trading signals based on SMA crossover
        
        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame containing price data with datetime index
        price_column : str
            Column name containing price data (default: 'close')
            
        Returns:
        --------
        pd.DataFrame
            Original DataFrame with added signal columns:
            - fast_sma: Fast moving average
            - slow_sma: Slow moving average  
            - signal: Trading signals (1: buy, -1: sell, 0: hold)
            - position: Current position (1: long, 0: flat, -1: short)
        """
        try:
            # Validate input data
            if not isinstance(df, pd.DataFrame):
                raise TypeError("Input must be a pandas DataFrame")
            
            if price_column not in df.columns:
                raise ValueError(f"Price column '{price_column}' not found in DataFrame")
            
            if df.empty:
                raise ValueError("DataFrame is empty")
            
            # Create a copy to avoid modifying original data
            result_df = df.copy()
            
            # Calculate moving averages
            result_df['fast_sma'] = self.calculate_sma(result_df[price_column], self.fast_period)
            result_df['slow_sma'] = self.calculate_sma(result_df[price_column], self.slow_period)
            
            # Generate signals based on crossover
            # Buy signal: fast SMA crosses above slow SMA
            # Sell signal: fast SMA crosses below slow SMA
            result_df['signal'] = 0
            
            # Create conditions for crossovers
            fast_above_slow = result_df['fast_sma'] > result_df['slow_sma']
            fast_below_slow = result_df['fast_sma'] < result_df['slow_sma']
            fast_above_slow_prev = fast_above_slow.shift(1)
            fast_below_slow_prev = fast_below_slow.shift(1)
            
            # Buy signal: fast crosses above slow
            buy_condition = fast_above_slow & fast_below_slow_prev
            result_df.loc[buy_condition, 'signal'] = 1
            
            # Sell signal: fast crosses below slow
            sell_condition = fast_below_slow & fast_above_slow_prev
            result_df.loc[sell_condition, 'signal'] = -1
            
            # Calculate position (simplified - always in market)
            result_df['position'] = result_df['signal'].replace(to_replace=0, method='ffill').fillna(0)
            
            return result_df
            
        except Exception as e:
            raise RuntimeError(f"Error generating signals: {str(e)}")
    
    def get_strategy_parameters(self) -> Dict[str, Any]:
        """Return strategy parameters"""
        return {
            'fast_period': self.fast_period,
            'slow_period': self.slow_period,
            'strategy_name': 'SMA Crossover'
        }


def backtest_sma_crossover(df: pd.DataFrame, fast_period: int = 20, slow_period: int = 50, 
                          price_column: str = 'close') -> pd.DataFrame:
    """
    Convenience function to backtest SMA crossover strategy
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with price data and datetime index
    fast_period : int
        Fast moving average period (default: 20)
    slow_period : int
        Slow moving average period (default: 50)
    price_column : str
        Column name for price data (default: 'close')
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with strategy signals and positions
    """
    try:
        strategy = SMACrossoverStrategy(fast_period=fast_period, slow_period=slow_period)
        return strategy.generate_signals(df, price_column)
    except Exception as e:
        raise RuntimeError(f"Backtest failed: {str(e)}")


# Example usage (commented out for import safety)
if __name__ == "__main__":
    # Sample data creation for testing
    dates = pd.date_range('2023-01-01', periods=100, freq='H')
    sample_data = pd.DataFrame({
        'close': 50000 + np.cumsum(np.random.randn(100) * 1000)
    }, index=dates)
    
    # Test the strategy
    try:
        result = backtest_sma_crossover(sample_data, fast_period=10, slow_period=20)
        print("Strategy executed successfully")
        print(f"Signals generated: {len(result[result['signal'] != 0])}")
        print(f"Parameters: {SMACrossoverStrategy(10, 20).get_strategy_parameters()}")
    except Exception as e:
        print(f"Error: {e}")