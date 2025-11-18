"""
S/R + RSI Enhanced Mean-Reversion Strategy

Combines Support/Resistance levels with RSI confirmation:
- LONG: Price at support AND RSI oversold (<30)
- SHORT: Price at resistance AND RSI overbought (>70)

This filters false S/R entries by requiring momentum confirmation.

Expected Improvement over base S/R:
- Win rate: +5-10% (filtering false signals)
- Sharpe: +0.2-0.4 (more selective entries)
- Fewer trades but higher quality
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict
from backend.strategies.support_resistance import SupportResistanceDetector
from backend.indicators.rsi import calculate_rsi


class SRRSIEnhancedStrategy:
    def __init__(
        self,
        lookback_bars: int = 100,
        level_tolerance_pct: float = 0.1,
        entry_tolerance_pct: float = 0.15,
        stop_loss_pct: float = 0.8,
        max_holding_bars: int = 48,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0
    ):
        # S/R parameters
        self.lookback_bars = lookback_bars
        self.level_tolerance_pct = level_tolerance_pct
        self.entry_tolerance_pct = entry_tolerance_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_holding_bars = max_holding_bars
        
        # RSI parameters
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        
        # Components
        self.sr_detector = SupportResistanceDetector(
            lookback_bars=lookback_bars,
            tolerance_pct=level_tolerance_pct
        )
        
        # State
        self.position = 0  # 0: flat, 1: long, -1: short
        self.entry_bar = 0
        self.current_levels = {'support': [], 'resistance': []}
        self.rsi_series = None
    
    def on_start(self, data: pd.DataFrame):
        """Initialize strategy state"""
        self.position = 0
        self.entry_bar = 0
        self.current_levels = self.sr_detector.detect_levels(data)
        self.rsi_series = calculate_rsi(data, period=self.rsi_period)
    
    def on_bar(self, bar: pd.Series, data: pd.DataFrame) -> Optional[Dict]:
        """
        Process each bar and generate trading signals with RSI confirmation
        
        Returns:
            Dict with 'action' ('LONG', 'SHORT', 'CLOSE') and relevant prices
            None if no action
        """
        current_idx = len(data) - 1
        current_price = float(bar['close'])
        
        # Update S/R levels every 10 bars
        if current_idx % 10 == 0:
            self.current_levels = self.sr_detector.detect_levels(data)
        
        # Update RSI
        self.rsi_series = calculate_rsi(data, period=self.rsi_period)
        current_rsi = self.rsi_series.iloc[-1]
        
        # Check exit conditions if in position
        if self.position != 0:
            bars_held = current_idx - self.entry_bar
            
            # Time-based exit
            if bars_held >= self.max_holding_bars:
                return {
                    'action': 'CLOSE',
                    'reason': f'max_holding_bars ({self.max_holding_bars})',
                    'entry_price': current_price
                }
        
        # Entry logic (only if flat)
        if self.position == 0:
            nearest = self.sr_detector.get_nearest_levels(current_price, self.current_levels)
            
            if not nearest:
                return None
            
            distance_to_support = nearest.get('distance_to_support_pct')
            distance_to_resistance = nearest.get('distance_to_resistance_pct')
            support_level = nearest.get('support')
            resistance_level = nearest.get('resistance')
            
            # LONG: Price at support AND RSI oversold
            if (distance_to_support is not None and support_level is not None and 
                distance_to_support <= self.entry_tolerance_pct and current_rsi <= self.rsi_oversold):
                return self._create_long_signal(current_price, support_level, resistance_level, current_rsi)
            
            # SHORT: Price at resistance AND RSI overbought
            if (distance_to_resistance is not None and resistance_level is not None and 
                distance_to_resistance <= self.entry_tolerance_pct and current_rsi >= self.rsi_overbought):
                return self._create_short_signal(current_price, resistance_level, support_level, current_rsi)
        
        return None
    
    def _create_long_signal(self, current_price: float, support: float, resistance: Optional[float], rsi: float) -> Dict:
        """Generate LONG entry signal"""
        self.position = 1
        self.entry_bar = 0  # Will be set by backtest
        
        stop_loss = support * (1 - self.stop_loss_pct / 100)
        take_profit = resistance if resistance else current_price * 1.02
        
        return {
            'action': 'LONG',
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'reason': f'S/R+RSI: price {current_price:.2f} near support {support:.2f}, RSI {rsi:.1f} oversold'
        }
    
    def _create_short_signal(self, current_price: float, resistance: float, support: Optional[float], rsi: float) -> Dict:
        """Generate SHORT entry signal"""
        self.position = -1
        self.entry_bar = 0  # Will be set by backtest
        
        stop_loss = resistance * (1 + self.stop_loss_pct / 100)
        take_profit = support if support else current_price * 0.98
        
        return {
            'action': 'SHORT',
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'reason': f'S/R+RSI: price {current_price:.2f} near resistance {resistance:.2f}, RSI {rsi:.1f} overbought'
        }


def test_strategy():
    """Quick test with synthetic data"""
    np.random.seed(42)
    
    # Create mean-reverting price data with RSI extremes
    base_price = 50000
    prices = [base_price]
    
    for i in range(200):
        # Simulate mean-reversion
        if prices[-1] > base_price + 1000:  # Resistance
            change = np.random.randn() * 50 - 100  # Bias downward
        elif prices[-1] < base_price - 1000:  # Support
            change = np.random.randn() * 50 + 100  # Bias upward
        else:
            change = np.random.randn() * 100
        
        prices.append(prices[-1] + change)
    
    df = pd.DataFrame({
        'close': prices,
        'open': prices,
        'high': [p * 1.002 for p in prices],
        'low': [p * 0.998 for p in prices],
        'volume': [1000] * len(prices)
    })
    
    strat = SRRSIEnhancedStrategy(lookback_bars=50, rsi_period=14)
    strat.on_start(df)
    
    signals = []
    for i in range(50, len(df)):
        bar = df.iloc[i]
        sig = strat.on_bar(bar, df.iloc[:i+1])
        if sig:
            rsi = strat.rsi_series.iloc[i]
            signals.append((i, sig['action'], bar['close'], rsi))
    
    print(f"S/R+RSI Enhanced Strategy Test:")
    print(f"  Generated {len(signals)} signals (expect fewer than base S/R)")
    for idx, action, price, rsi in signals[:5]:
        print(f"  Bar {idx}: {action} at {price:.2f}, RSI {rsi:.1f}")


if __name__ == '__main__':
    test_strategy()
