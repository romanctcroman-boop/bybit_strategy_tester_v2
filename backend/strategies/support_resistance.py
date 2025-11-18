import pandas as pd
import numpy as np
from typing import List, Dict, Optional


class SupportResistanceDetector:
    """
    Detects support and resistance levels using swing highs/lows

    Methods
    -------
    find_swing_highs(data, window)
    find_swing_lows(data, window)
    cluster_levels(levels, tolerance_pct)
    detect_levels(data)
    get_nearest_levels(current_price, levels)
    """

    def __init__(self, lookback_bars: int = 100, tolerance_pct: float = 0.1):
        self.lookback_bars = lookback_bars
        self.tolerance_pct = tolerance_pct

    def find_swing_highs(self, data: pd.DataFrame, window: int = 5) -> List[float]:
        highs: List[float] = []
        if len(data) < window * 2 + 1:
            return highs
        for i in range(window, len(data) - window):
            current_high = float(data['high'].iat[i])
            left_window = data['high'].iloc[i - window:i]
            right_window = data['high'].iloc[i + 1:i + window + 1]
            if current_high > float(left_window.max()) and current_high > float(right_window.max()):
                highs.append(current_high)
        return highs

    def find_swing_lows(self, data: pd.DataFrame, window: int = 5) -> List[float]:
        lows: List[float] = []
        if len(data) < window * 2 + 1:
            return lows
        for i in range(window, len(data) - window):
            current_low = float(data['low'].iat[i])
            left_window = data['low'].iloc[i - window:i]
            right_window = data['low'].iloc[i + 1:i + window + 1]
            if current_low < float(left_window.min()) and current_low < float(right_window.min()):
                lows.append(current_low)
        return lows

    def cluster_levels(self, levels: List[float], tolerance_pct: float) -> List[float]:
        if not levels:
            return []
        sorted_levels = sorted(levels)
        clusters: List[List[float]] = []
        current_cluster: List[float] = [sorted_levels[0]]
        for level in sorted_levels[1:]:
            last = current_cluster[-1]
            if abs(level - last) / last * 100 <= tolerance_pct:
                current_cluster.append(level)
            else:
                clusters.append(current_cluster)
                current_cluster = [level]
        clusters.append(current_cluster)
        # Represent cluster by mean
        return [float(np.mean(c)) for c in clusters]

    def detect_levels(self, data: pd.DataFrame) -> Dict[str, List[float]]:
        recent = data.tail(self.lookback_bars)
        swing_highs = self.find_swing_highs(recent, window=5)
        swing_lows = self.find_swing_lows(recent, window=5)
        resistance_levels = self.cluster_levels(swing_highs, self.tolerance_pct)
        support_levels = self.cluster_levels(swing_lows, self.tolerance_pct)
        return {
            'resistance': resistance_levels,
            'support': support_levels
        }

    def get_nearest_levels(self, current_price: float, levels: Dict[str, List[float]]) -> Dict[str, Optional[float]]:
        resistance_above = [r for r in levels.get('resistance', []) if r > current_price]
        support_below = [s for s in levels.get('support', []) if s < current_price]
        nearest_resistance = float(min(resistance_above)) if resistance_above else None
        nearest_support = float(max(support_below)) if support_below else None
        result: Dict[str, Optional[float]] = {
            'nearest_resistance': nearest_resistance,
            'nearest_support': nearest_support
        }
        if nearest_resistance is not None:
            result['distance_to_resistance_pct'] = (nearest_resistance - current_price) / current_price * 100
        else:
            result['distance_to_resistance_pct'] = None
        if nearest_support is not None:
            result['distance_to_support_pct'] = (current_price - nearest_support) / current_price * 100
        else:
            result['distance_to_support_pct'] = None
        return result
