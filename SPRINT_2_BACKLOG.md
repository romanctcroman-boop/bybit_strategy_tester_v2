# Sprint 2 Backlog - Week 2 (Nov 6 - Nov 12, 2025)

**Sprint Goal:** Implement Mean-Reversion Strategies (Perplexity Priority #1-3)

**Context:** Sprint 1 revealed EMA Crossover is not viable for BTCUSDT 5-minute timeframe (1/4 Perplexity benchmarks passed, -8.88% avg OOS return). Pivoting to mean-reversion strategies as recommended by Perplexity AI audit.

---

## 🎯 PERPLEXITY AI STRATEGY RECOMMENDATIONS

From comprehensive project audit (Round 3, Question 8):

### Why Mean-Reversion for 5-Minute Timeframe?

**EMA Crossover Problems (Confirmed by Sprint 1 WFO):**
- High noise-to-signal ratio on 5-minute bars
- Whipsaw trades (54 trades/period, 20-25% win rate)
- Trend-following in range-bound market
- Lagging indicators miss optimal entry/exit

**Mean-Reversion Advantages:**
- Captures price bounces at key levels
- Higher win rate (45-55% vs 20-25%)
- Better Sharpe ratios (1.0-2.0 vs -0.894)
- Matches BTCUSDT 5min behavior (range-bound with short trends)

---

## 🔴 PRIORITY #1: Support/Resistance Strategy (Backend Team, 3 days)

### Task 2.1: S/R Level Detection Algorithm (Day 1)

**Rationale:** Identify key price levels where reversals occur

**File:** `backend/strategies/support_resistance.py`

**Implementation:**

```python
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple

class SupportResistanceDetector:
    """
    Detects support and resistance levels using swing highs/lows
    """
    
    def __init__(self, lookback_bars: int = 100, tolerance_pct: float = 0.1):
        """
        Args:
            lookback_bars: How many bars to analyze for S/R levels
            tolerance_pct: Price tolerance around level (e.g., 0.1%)
        """
        self.lookback_bars = lookback_bars
        self.tolerance_pct = tolerance_pct
    
    def find_swing_highs(self, data: pd.DataFrame, window: int = 5) -> List[float]:
        """
        Find swing highs (local maxima) in price data
        
        Swing high = price[i] > price[i-window:i] AND price[i] > price[i+1:i+window]
        """
        highs = []
        for i in range(window, len(data) - window):
            current_high = data['high'].iloc[i]
            left_window = data['high'].iloc[i-window:i]
            right_window = data['high'].iloc[i+1:i+window+1]
            
            if (current_high > left_window.max() and 
                current_high > right_window.max()):
                highs.append(current_high)
        
        return highs
    
    def find_swing_lows(self, data: pd.DataFrame, window: int = 5) -> List[float]:
        """
        Find swing lows (local minima) in price data
        
        Swing low = price[i] < price[i-window:i] AND price[i] < price[i+1:i+window]
        """
        lows = []
        for i in range(window, len(data) - window):
            current_low = data['low'].iloc[i]
            left_window = data['low'].iloc[i-window:i]
            right_window = data['low'].iloc[i+1:i+window+1]
            
            if (current_low < left_window.min() and 
                current_low < right_window.min()):
                lows.append(current_low)
        
        return lows
    
    def cluster_levels(self, levels: List[float], tolerance_pct: float) -> List[float]:
        """
        Cluster nearby price levels into single S/R levels
        
        Example:
            Input: [100.5, 100.7, 100.6, 105.0, 105.2]
            Output: [100.6, 105.1] (clustered within 0.1%)
        """
        if not levels:
            return []
        
        sorted_levels = sorted(levels)
        clusters = []
        current_cluster = [sorted_levels[0]]
        
        for level in sorted_levels[1:]:
            # If within tolerance of current cluster, add to it
            if abs(level - current_cluster[-1]) / current_cluster[-1] * 100 <= tolerance_pct:
                current_cluster.append(level)
            else:
                # Finalize current cluster, start new one
                clusters.append(np.mean(current_cluster))
                current_cluster = [level]
        
        # Don't forget last cluster
        clusters.append(np.mean(current_cluster))
        
        return clusters
    
    def detect_levels(self, data: pd.DataFrame) -> Dict[str, List[float]]:
        """
        Main method: Detect support and resistance levels
        
        Returns:
            {
                'resistance': [level1, level2, ...],
                'support': [level1, level2, ...]
            }
        """
        # Get recent data only
        recent_data = data.tail(self.lookback_bars)
        
        # Find swing points
        swing_highs = self.find_swing_highs(recent_data, window=5)
        swing_lows = self.find_swing_lows(recent_data, window=5)
        
        # Cluster into S/R levels
        resistance_levels = self.cluster_levels(swing_highs, self.tolerance_pct)
        support_levels = self.cluster_levels(swing_lows, self.tolerance_pct)
        
        return {
            'resistance': resistance_levels,
            'support': support_levels
        }
    
    def get_nearest_levels(
        self, 
        current_price: float, 
        levels: Dict[str, List[float]]
    ) -> Dict[str, float]:
        """
        Get nearest support below and resistance above current price
        
        Returns:
            {
                'nearest_resistance': float,
                'nearest_support': float,
                'distance_to_resistance_pct': float,
                'distance_to_support_pct': float
            }
        """
        resistance_above = [r for r in levels['resistance'] if r > current_price]
        support_below = [s for s in levels['support'] if s < current_price]
        
        nearest_resistance = min(resistance_above) if resistance_above else None
        nearest_support = max(support_below) if support_below else None
        
        result = {
            'nearest_resistance': nearest_resistance,
            'nearest_support': nearest_support
        }
        
        if nearest_resistance:
            result['distance_to_resistance_pct'] = (
                (nearest_resistance - current_price) / current_price * 100
            )
        
        if nearest_support:
            result['distance_to_support_pct'] = (
                (current_price - nearest_support) / current_price * 100
            )
        
        return result
```

**Acceptance Criteria:**
- ✅ Detects swing highs/lows with configurable window
- ✅ Clusters nearby levels within tolerance
- ✅ Returns nearest support/resistance to current price
- ✅ Unit tests with synthetic data validate clustering

**Estimate:** 1 day

---

### Task 2.2: S/R Mean-Reversion Strategy (Day 2)

**File:** `backend/strategies/sr_mean_reversion.py`

**Implementation:**

```python
from backend.strategies.support_resistance import SupportResistanceDetector
from backend.models.base_strategy import BaseStrategy
import pandas as pd
from typing import Dict, Optional

class SRMeanReversionStrategy(BaseStrategy):
    """
    Mean-Reversion Strategy at Support/Resistance Levels
    
    Entry Logic:
    - LONG: Price touches support ± tolerance → expect bounce up
    - SHORT: Price touches resistance ± tolerance → expect bounce down
    
    Exit Logic:
    - Take profit at opposite level (S→R or R→S)
    - Stop loss: 0.5-1.0% beyond entry level
    - Time-based exit: 2-4 hours max holding period
    
    Expected Performance (per Perplexity):
    - Win Rate: 45-55%
    - Sharpe Ratio: 1.0-2.0
    - Efficiency: 140-160%
    """
    
    def __init__(
        self,
        lookback_bars: int = 100,
        level_tolerance_pct: float = 0.1,
        entry_tolerance_pct: float = 0.15,
        stop_loss_pct: float = 0.8,
        max_holding_bars: int = 48  # 4 hours at 5min
    ):
        super().__init__()
        self.sr_detector = SupportResistanceDetector(
            lookback_bars=lookback_bars,
            tolerance_pct=level_tolerance_pct
        )
        self.entry_tolerance_pct = entry_tolerance_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_holding_bars = max_holding_bars
        
        self.current_levels = None
        self.entry_bar = None
    
    def on_bar(self, bar: pd.Series, data: pd.DataFrame) -> Optional[Dict]:
        """
        Process each new bar and generate signals
        
        Returns:
            {
                'action': 'LONG' | 'SHORT' | 'CLOSE',
                'reason': str,
                'entry_price': float,
                'stop_loss': float,
                'take_profit': float
            }
        """
        current_price = bar['close']
        current_bar_idx = len(data) - 1
        
        # Update S/R levels every 10 bars (reduce computation)
        if current_bar_idx % 10 == 0:
            self.current_levels = self.sr_detector.detect_levels(data)
        
        if self.current_levels is None:
            return None
        
        # Check exit conditions first (if in position)
        if self.position != 0:
            exit_signal = self._check_exit_conditions(
                bar, current_bar_idx, current_price
            )
            if exit_signal:
                return exit_signal
        
        # Entry conditions (if flat)
        if self.position == 0:
            nearest = self.sr_detector.get_nearest_levels(
                current_price, self.current_levels
            )
            
            # LONG at support
            if nearest['nearest_support']:
                distance_pct = nearest['distance_to_support_pct']
                if distance_pct <= self.entry_tolerance_pct:
                    return self._create_long_signal(
                        current_price,
                        nearest['nearest_support'],
                        nearest['nearest_resistance']
                    )
            
            # SHORT at resistance
            if nearest['nearest_resistance']:
                distance_pct = nearest['distance_to_resistance_pct']
                if distance_pct <= self.entry_tolerance_pct:
                    return self._create_short_signal(
                        current_price,
                        nearest['nearest_resistance'],
                        nearest['nearest_support']
                    )
        
        return None
    
    def _create_long_signal(
        self, 
        current_price: float,
        support_level: float,
        resistance_level: Optional[float]
    ) -> Dict:
        """Create LONG signal at support"""
        self.entry_bar = len(self.data) - 1
        
        # Stop loss below support
        stop_loss = support_level * (1 - self.stop_loss_pct / 100)
        
        # Take profit at resistance (or +2% if no clear resistance)
        take_profit = resistance_level if resistance_level else current_price * 1.02
        
        return {
            'action': 'LONG',
            'reason': f'Price {current_price:.2f} near support {support_level:.2f}',
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
    
    def _create_short_signal(
        self,
        current_price: float,
        resistance_level: float,
        support_level: Optional[float]
    ) -> Dict:
        """Create SHORT signal at resistance"""
        self.entry_bar = len(self.data) - 1
        
        # Stop loss above resistance
        stop_loss = resistance_level * (1 + self.stop_loss_pct / 100)
        
        # Take profit at support (or -2% if no clear support)
        take_profit = support_level if support_level else current_price * 0.98
        
        return {
            'action': 'SHORT',
            'reason': f'Price {current_price:.2f} near resistance {resistance_level:.2f}',
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
    
    def _check_exit_conditions(
        self,
        bar: pd.Series,
        current_bar_idx: int,
        current_price: float
    ) -> Optional[Dict]:
        """
        Check if any exit condition is met:
        1. Stop loss hit
        2. Take profit hit
        3. Time-based exit (max holding period)
        """
        bars_held = current_bar_idx - self.entry_bar
        
        # Time-based exit
        if bars_held >= self.max_holding_bars:
            return {
                'action': 'CLOSE',
                'reason': f'Max holding period ({bars_held} bars)',
                'exit_price': current_price
            }
        
        # Stop loss / Take profit handled by backtest engine
        # (we return them in entry signal)
        
        return None
```

**Acceptance Criteria:**
- ✅ Generates LONG signals at support
- ✅ Generates SHORT signals at resistance
- ✅ Sets stop loss 0.5-1.0% beyond entry level
- ✅ Takes profit at opposite level
- ✅ Time-based exit after 2-4 hours
- ✅ Unit tests with synthetic S/R levels

**Estimate:** 1 day

---

### Task 2.3: S/R Strategy 22-Cycle WFO Validation (Day 3)

**Goal:** Run full Walk-Forward Optimization and validate against Perplexity benchmarks

**File:** `run_wfo_sr_strategy.py` (adapt from `run_wfo_full.py`)

**Key Changes:**
```python
# Replace EMA strategy with S/R strategy
from backend.strategies.sr_mean_reversion import SRMeanReversionStrategy

# Parameter space (grid search)
param_space = {
    'lookback_bars': [80, 100, 120],           # 3 values
    'level_tolerance_pct': [0.08, 0.10, 0.12], # 3 values
    'entry_tolerance_pct': [0.10, 0.15, 0.20], # 3 values
    'stop_loss_pct': [0.6, 0.8, 1.0],          # 3 values
    'max_holding_bars': [36, 48, 60]           # 3 values (3-5 hours)
}
# Total: 3^5 = 243 combinations (feasible for 14 min WFO)

# Same WFO config as Sprint 1
in_sample = 8000
out_sample = 2000
step = 2000
# 22 cycles
```

**Expected Results (per Perplexity):**
- ✅ Efficiency: 140-160% (vs 0.0% for EMA)
- ✅ Win Rate: 45-55% (vs 20-25% for EMA)
- ✅ Sharpe Ratio: 1.0-2.0 (vs -0.894 for EMA)
- ✅ Param Stability: 0.70-0.90
- ✅ Consistency CV: 0.20-0.40

**Acceptance Criteria:**
- ✅ 22 cycles executed successfully
- ✅ Minimum 2 out of 4 Perplexity benchmarks PASS (improvement over EMA)
- ✅ Avg OOS return > 0% (profitable!)
- ✅ Detailed report generated (similar to WFO_22_CYCLES_REPORT.md)

**Estimate:** 1 day (script adaptation 2h + WFO execution 15min + analysis 2h)

---

## 🟡 PRIORITY #2: Bollinger Bands Strategy (Backend Team, 2 days)

### Task 2.4: Bollinger Bands Mean-Reversion (Day 4)

**File:** `backend/strategies/bollinger_mean_reversion.py`

**Implementation:**

```python
import pandas as pd
import numpy as np
from backend.models.base_strategy import BaseStrategy
from typing import Dict, Optional

class BollingerMeanReversionStrategy(BaseStrategy):
    """
    Mean-Reversion using Bollinger Bands
    
    Entry Logic:
    - LONG: Price touches lower band → expect bounce to middle band
    - SHORT: Price touches upper band → expect drop to middle band
    
    Exit Logic:
    - Take profit at middle band (SMA)
    - Stop loss: 1.5% or opposite band touch
    - Time-based exit: 3-6 hours max
    
    Expected Performance (per Perplexity):
    - Win Rate: 40-50%
    - Sharpe Ratio: 0.8-1.5
    - Efficiency: 120-150%
    """
    
    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        entry_threshold_pct: float = 0.95,  # Enter at 95% of band width
        stop_loss_pct: float = 1.5,
        max_holding_bars: int = 60  # 5 hours at 5min
    ):
        super().__init__()
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.entry_threshold_pct = entry_threshold_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_holding_bars = max_holding_bars
        
        self.entry_bar = None
    
    def calculate_bollinger_bands(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Calculate Bollinger Bands
        
        Returns:
            {
                'upper': pd.Series,
                'middle': pd.Series (SMA),
                'lower': pd.Series
            }
        """
        close = data['close']
        
        # Middle band = Simple Moving Average
        middle = close.rolling(window=self.bb_period).mean()
        
        # Standard deviation
        std = close.rolling(window=self.bb_period).std()
        
        # Upper/Lower bands
        upper = middle + (self.bb_std * std)
        lower = middle - (self.bb_std * std)
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }
    
    def on_bar(self, bar: pd.Series, data: pd.DataFrame) -> Optional[Dict]:
        """Process each bar and generate signals"""
        
        # Need enough data for BB calculation
        if len(data) < self.bb_period + 1:
            return None
        
        # Calculate Bollinger Bands
        bb = self.calculate_bollinger_bands(data)
        current_price = bar['close']
        current_bar_idx = len(data) - 1
        
        upper_band = bb['upper'].iloc[-1]
        middle_band = bb['middle'].iloc[-1]
        lower_band = bb['lower'].iloc[-1]
        
        # Check exit conditions first
        if self.position != 0:
            exit_signal = self._check_exit_conditions(
                bar, current_bar_idx, current_price, middle_band
            )
            if exit_signal:
                return exit_signal
        
        # Entry conditions
        if self.position == 0:
            band_width = upper_band - lower_band
            
            # LONG at lower band (oversold)
            distance_to_lower = current_price - lower_band
            if distance_to_lower / band_width <= (1 - self.entry_threshold_pct):
                return self._create_long_signal(
                    current_price, lower_band, middle_band, upper_band
                )
            
            # SHORT at upper band (overbought)
            distance_to_upper = upper_band - current_price
            if distance_to_upper / band_width <= (1 - self.entry_threshold_pct):
                return self._create_short_signal(
                    current_price, upper_band, middle_band, lower_band
                )
        
        return None
    
    def _create_long_signal(
        self,
        current_price: float,
        lower_band: float,
        middle_band: float,
        upper_band: float
    ) -> Dict:
        """Create LONG signal at lower Bollinger Band"""
        self.entry_bar = len(self.data) - 1
        
        # Stop loss: 1.5% below entry OR opposite band
        stop_loss = min(
            current_price * (1 - self.stop_loss_pct / 100),
            lower_band * 0.995  # Slightly below lower band
        )
        
        # Take profit: Middle band (SMA)
        take_profit = middle_band
        
        return {
            'action': 'LONG',
            'reason': f'Price {current_price:.2f} at lower BB {lower_band:.2f}',
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
    
    def _create_short_signal(
        self,
        current_price: float,
        upper_band: float,
        middle_band: float,
        lower_band: float
    ) -> Dict:
        """Create SHORT signal at upper Bollinger Band"""
        self.entry_bar = len(self.data) - 1
        
        # Stop loss: 1.5% above entry OR opposite band
        stop_loss = max(
            current_price * (1 + self.stop_loss_pct / 100),
            upper_band * 1.005  # Slightly above upper band
        )
        
        # Take profit: Middle band (SMA)
        take_profit = middle_band
        
        return {
            'action': 'SHORT',
            'reason': f'Price {current_price:.2f} at upper BB {upper_band:.2f}',
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
    
    def _check_exit_conditions(
        self,
        bar: pd.Series,
        current_bar_idx: int,
        current_price: float,
        middle_band: float
    ) -> Optional[Dict]:
        """Check time-based exit"""
        bars_held = current_bar_idx - self.entry_bar
        
        if bars_held >= self.max_holding_bars:
            return {
                'action': 'CLOSE',
                'reason': f'Max holding period ({bars_held} bars)',
                'exit_price': current_price
            }
        
        return None
```

**Acceptance Criteria:**
- ✅ Calculates Bollinger Bands (20-period SMA, 2.0 std)
- ✅ LONG signal at lower band
- ✅ SHORT signal at upper band
- ✅ Take profit at middle band
- ✅ Stop loss at 1.5% or opposite band
- ✅ Unit tests validate BB calculation

**Estimate:** 1 day

---

### Task 2.5: Bollinger Bands 22-Cycle WFO (Day 5)

**Goal:** Compare Bollinger Bands vs S/R strategy performance

**File:** `run_wfo_bb_strategy.py`

**Parameter Space:**
```python
param_space = {
    'bb_period': [18, 20, 22],              # 3 values
    'bb_std': [1.8, 2.0, 2.2],              # 3 values
    'entry_threshold_pct': [0.90, 0.95, 0.98], # 3 values
    'stop_loss_pct': [1.0, 1.5, 2.0],       # 3 values
    'max_holding_bars': [48, 60, 72]        # 3 values (4-6 hours)
}
# Total: 3^5 = 243 combinations
```

**Expected Results (per Perplexity):**
- ✅ Efficiency: 120-150%
- ✅ Win Rate: 40-50%
- ✅ Sharpe Ratio: 0.8-1.5
- ✅ Param Stability: 0.65-0.85
- ✅ Consistency CV: 0.25-0.45

**Deliverable:** Comparison report (S/R vs BB vs EMA)

**Estimate:** 1 day

---

## 🟢 PRIORITY #3: RSI Confirmation Filter (Backend Team, 2 days)

### Task 2.6: RSI Indicator Implementation (Day 6)

**File:** `backend/indicators/rsi.py`

**Implementation:**

```python
import pandas as pd
import numpy as np

class RSI:
    """
    Relative Strength Index (RSI)
    
    Measures momentum: overbought (>70) / oversold (<30)
    """
    
    def __init__(self, period: int = 14):
        self.period = period
    
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate RSI
        
        Formula:
        1. Calculate price changes (deltas)
        2. Separate gains and losses
        3. Average gain = EMA of gains
        4. Average loss = EMA of losses
        5. RS = Average Gain / Average Loss
        6. RSI = 100 - (100 / (1 + RS))
        
        Returns:
            pd.Series with RSI values (0-100)
        """
        close = data['close']
        
        # Calculate price changes
        delta = close.diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        # Calculate average gains/losses using EMA
        avg_gain = gains.ewm(span=self.period, adjust=False).mean()
        avg_loss = losses.ewm(span=self.period, adjust=False).mean()
        
        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
```

**Acceptance Criteria:**
- ✅ Calculates RSI with configurable period
- ✅ Returns values in 0-100 range
- ✅ Unit tests match known RSI values from TradingView

**Estimate:** 0.5 day

---

### Task 2.7: Enhanced S/R Strategy with RSI Filter (Day 6-7)

**File:** `backend/strategies/sr_rsi_strategy.py`

**Implementation:**

```python
from backend.strategies.sr_mean_reversion import SRMeanReversionStrategy
from backend.indicators.rsi import RSI
from typing import Dict, Optional
import pandas as pd

class SRStrategyWithRSI(SRMeanReversionStrategy):
    """
    Support/Resistance strategy enhanced with RSI confirmation
    
    Additional Entry Rules:
    - LONG at support: RSI < 30 (oversold confirmation)
    - SHORT at resistance: RSI > 70 (overbought confirmation)
    
    Expected Improvement (per Perplexity):
    - Win Rate: +5-10% (from 45-55% to 50-60%)
    - Sharpe Ratio: +0.2-0.4 (from 1.0-2.0 to 1.2-2.4)
    - Trade Frequency: -30-40% (more selective)
    """
    
    def __init__(
        self,
        lookback_bars: int = 100,
        level_tolerance_pct: float = 0.1,
        entry_tolerance_pct: float = 0.15,
        stop_loss_pct: float = 0.8,
        max_holding_bars: int = 48,
        rsi_period: int = 14,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70
    ):
        super().__init__(
            lookback_bars=lookback_bars,
            level_tolerance_pct=level_tolerance_pct,
            entry_tolerance_pct=entry_tolerance_pct,
            stop_loss_pct=stop_loss_pct,
            max_holding_bars=max_holding_bars
        )
        
        self.rsi = RSI(period=rsi_period)
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
    
    def on_bar(self, bar: pd.Series, data: pd.DataFrame) -> Optional[Dict]:
        """
        Process bar with RSI confirmation
        
        Overrides parent method to add RSI filtering
        """
        # Calculate RSI
        rsi_values = self.rsi.calculate(data)
        current_rsi = rsi_values.iloc[-1]
        
        # Get base signal from parent S/R strategy
        base_signal = super().on_bar(bar, data)
        
        if base_signal is None:
            return None
        
        # Filter signals with RSI confirmation
        if base_signal['action'] == 'LONG':
            # Only enter LONG if RSI confirms oversold
            if current_rsi < self.rsi_oversold:
                base_signal['reason'] += f' + RSI {current_rsi:.1f} oversold'
                return base_signal
            else:
                # Reject signal
                return None
        
        elif base_signal['action'] == 'SHORT':
            # Only enter SHORT if RSI confirms overbought
            if current_rsi > self.rsi_overbought:
                base_signal['reason'] += f' + RSI {current_rsi:.1f} overbought'
                return base_signal
            else:
                # Reject signal
                return None
        
        # CLOSE signals pass through (no RSI filtering on exits)
        return base_signal
```

**Acceptance Criteria:**
- ✅ Inherits from S/R strategy
- ✅ Adds RSI confirmation filter
- ✅ Only enters LONG if RSI < 30
- ✅ Only enters SHORT if RSI > 70
- ✅ Unit tests validate filtering logic

**Estimate:** 1 day

---

### Task 2.8: S/R+RSI 22-Cycle WFO Comparison (Day 7)

**Goal:** Measure RSI filter impact on performance

**File:** `run_wfo_sr_rsi_strategy.py`

**Parameter Space:**
```python
param_space = {
    'lookback_bars': [80, 100, 120],       # 3 values
    'entry_tolerance_pct': [0.10, 0.15],   # 2 values
    'stop_loss_pct': [0.6, 0.8, 1.0],      # 3 values
    'rsi_period': [12, 14, 16],            # 3 values
    'rsi_oversold': [25, 30, 35],          # 3 values
    'rsi_overbought': [65, 70, 75]         # 3 values
}
# Total: 3*2*3*3*3*3 = 486 combinations (may need reduction)
```

**Key Comparisons:**
1. **S/R baseline** (Task 2.3)
2. **S/R + RSI** (this task)

**Expected Results:**
- Win Rate: 50-60% (up from 45-55%)
- Sharpe: 1.2-2.4 (up from 1.0-2.0)
- Trade count: -30-40% (more selective)

**Deliverable:** Final comparison report (3 strategies)

**Estimate:** 1 day

---

## 📊 SPRINT 2 DELIVERABLES

### Code Artifacts
1. ✅ `backend/strategies/support_resistance.py` - S/R level detector
2. ✅ `backend/strategies/sr_mean_reversion.py` - S/R strategy
3. ✅ `backend/strategies/bollinger_mean_reversion.py` - BB strategy
4. ✅ `backend/indicators/rsi.py` - RSI indicator
5. ✅ `backend/strategies/sr_rsi_strategy.py` - Enhanced S/R+RSI
6. ✅ `run_wfo_sr_strategy.py` - S/R WFO script
7. ✅ `run_wfo_bb_strategy.py` - BB WFO script
8. ✅ `run_wfo_sr_rsi_strategy.py` - S/R+RSI WFO script

### Reports
1. ✅ `WFO_SR_STRATEGY_REPORT.md` - S/R validation results
2. ✅ `WFO_BB_STRATEGY_REPORT.md` - Bollinger Bands results
3. ✅ `WFO_SR_RSI_STRATEGY_REPORT.md` - Enhanced S/R+RSI results
4. ✅ `SPRINT_2_STRATEGY_COMPARISON.md` - Final comparison:
   - EMA Crossover (Sprint 1 baseline)
   - S/R Mean-Reversion
   - Bollinger Bands
   - S/R + RSI Enhanced

### Unit Tests
1. ✅ `tests/test_support_resistance.py` - S/R detection tests
2. ✅ `tests/test_sr_strategy.py` - S/R strategy tests
3. ✅ `tests/test_bollinger_strategy.py` - BB strategy tests
4. ✅ `tests/test_rsi.py` - RSI calculation tests
5. ✅ `tests/test_sr_rsi_strategy.py` - Enhanced strategy tests

---

## 📈 SUCCESS CRITERIA

### Minimum Viable Success (MVS)
At least **ONE** mean-reversion strategy must pass **3 out of 4** Perplexity benchmarks:

| Benchmark | Target | EMA Baseline |
|-----------|--------|--------------|
| Efficiency | 120-160% | 0.0% ❌ |
| Param Stability | 0.60-0.95 | 0.559 ❌ |
| Consistency CV | 0.15-0.45 | 0.474 ❌ |
| Periods | 10+ | 22 ✅ |

**Pass Threshold:** 3/4 benchmarks (vs 1/4 for EMA)

### Target Success (TS)
- **S/R Strategy:** 3/4 benchmarks PASS
- **BB Strategy:** 2/4 benchmarks PASS
- **S/R+RSI Strategy:** 4/4 benchmarks PASS (best performer)

### Stretch Goal (SG)
- Average OOS Return > +5% per period
- Win Rate > 55%
- Sharpe Ratio > 2.0
- Ready for Task 1.3 (true OOS validation on unseen data)

---

## 🚫 WHAT WE'RE NOT DOING (Sprint 2)

### Deliberately Excluded:
1. ❌ **Frontend Development** - Backend validation first
2. ❌ **Live Trading Connector** - Strategies not proven yet
3. ❌ **Parameter Optimization Beyond WFO** - Grid search sufficient
4. ❌ **Machine Learning Approaches** - Keep it simple, interpretable
5. ❌ **Additional Timeframes** - 5-minute only for now
6. ❌ **Additional Symbols** - BTCUSDT only for consistency

### Rationale:
Focus all effort on proving mean-reversion strategies work. Once we have a viable strategy (3/4 benchmarks), we can expand scope in Sprint 3.

---

## ⏱️ TIME ESTIMATES

| Task | Estimate | Priority |
|------|----------|----------|
| 2.1: S/R Detection | 1 day | P1 🔴 |
| 2.2: S/R Strategy | 1 day | P1 🔴 |
| 2.3: S/R WFO | 1 day | P1 🔴 |
| 2.4: BB Strategy | 1 day | P2 🟡 |
| 2.5: BB WFO | 1 day | P2 🟡 |
| 2.6: RSI Indicator | 0.5 day | P3 🟢 |
| 2.7: S/R+RSI Strategy | 1 day | P3 🟢 |
| 2.8: S/R+RSI WFO | 1 day | P3 🟢 |
| **Total** | **7.5 days** | |

**Team:** 1-2 Backend Developers  
**Sprint Duration:** 7 days (Nov 6-12, buffer for issues)

---

## 🔄 RISK MANAGEMENT

### Risk 1: Mean-Reversion Also Fails
**Probability:** Low (Perplexity recommendation based on timeframe analysis)  
**Impact:** High (need to pivot strategy type again)  
**Mitigation:**
- Test S/R first (highest confidence)
- If S/R fails, immediately analyze why before BB/RSI
- Have backup plan: longer timeframes (15m, 30m)

### Risk 2: Parameter Space Too Large
**Probability:** Medium (243-486 combinations per strategy)  
**Impact:** Medium (WFO execution time)  
**Mitigation:**
- WFO runs fast (~15 min for 22 cycles)
- Can reduce parameter ranges if needed
- Use parallel processing if available

### Risk 3: S/R Detection Not Robust
**Probability:** Medium (algorithmic challenge)  
**Impact:** High (entire S/R strategy depends on it)  
**Mitigation:**
- Start with simple swing high/low detection
- Validate visually with known S/R levels
- Compare vs TradingView S/R pivot indicators

### Risk 4: Over-Optimization with RSI Filter
**Probability:** Medium (more parameters = more overfitting risk)  
**Impact:** Medium (strategy looks good in WFO but fails OOS)  
**Mitigation:**
- Keep RSI thresholds standard (30/70)
- Limit parameter variations
- Reserve final 20% of data for Task 1.3 (true OOS test)

---

## 📝 DEFINITION OF DONE (Sprint 2)

### Per Task:
- ✅ Code implemented and passes unit tests
- ✅ Integration tests pass with synthetic data
- ✅ Code reviewed (if team > 1 person)
- ✅ Documentation complete (docstrings)

### Per Strategy:
- ✅ 22-cycle WFO executed successfully
- ✅ All 4 Perplexity benchmarks calculated
- ✅ Detailed report generated (similar to WFO_22_CYCLES_REPORT.md)
- ✅ Results compared to EMA baseline

### Sprint Complete:
- ✅ At least ONE strategy passes 3/4 Perplexity benchmarks (MVS)
- ✅ Final comparison report published
- ✅ Recommendation for Sprint 3 (which strategy to productionize)
- ✅ All code committed to Git
- ✅ Sprint retrospective completed

---

## 🔮 SPRINT 3 PREVIEW (Conditional)

**IF Sprint 2 Success:**
- Task 1.3: True OOS Validation (holdout 20% of data never seen)
- Task 1.4: Parameter Sensitivity Analysis (robustness testing)
- Production deployment preparation (API endpoints)
- Frontend integration (display mean-reversion signals)

**IF Sprint 2 Failure:**
- Pivot to longer timeframes (15m, 30m, 1h)
- Re-run EMA crossover on 15m (may work better)
- Consider hybrid strategies (trend + mean-reversion)

---

## 📚 REFERENCES

### Perplexity AI Audit
- **Source:** PROJECT_AUDIT_2025.md (Round 3, Question 8)
- **Date:** October 29, 2025
- **Key Insight:** "EMA crossovers fail on 5-min due to noise. Use mean-reversion at S/R levels."

### Sprint 1 WFO Results
- **Source:** WFO_22_CYCLES_REPORT.md
- **Date:** October 29, 2025
- **Key Finding:** EMA Crossover 1/4 benchmarks, -8.88% avg OOS return

### Technical Resources
- **Bollinger Bands:** John Bollinger (inventor), 20-period SMA + 2 std dev standard
- **RSI:** J. Welles Wilder (1978), 14-period default, 30/70 oversold/overbought
- **S/R Levels:** Classical technical analysis, swing high/low clustering

---

**Sprint Start Date:** November 6, 2025  
**Sprint End Date:** November 12, 2025  
**Sprint Review:** November 12, 2025, 3 PM  
**Sprint Retrospective:** November 12, 2025, 5 PM

---

**Created:** October 29, 2025 21:30  
**Author:** GitHub Copilot + Perplexity AI Recommendations  
**Based On:** Sprint 1 results, Perplexity audit insights, industry best practices
