import pandas as pd
from typing import Optional, Dict
from backend.strategies.support_resistance import SupportResistanceDetector


class SRMeanReversionStrategy:
    """
    Mean-Reversion Strategy at Support/Resistance Levels
    Simple interface: expects `on_bar(bar, data)` calls from backtest engine
    Maintains `position` attribute (0 flat, 1 long, -1 short) and `data` reference.
    """

    def __init__(
        self,
        lookback_bars: int = 100,
        level_tolerance_pct: float = 0.1,
        entry_tolerance_pct: float = 0.15,
        stop_loss_pct: float = 0.8,
        max_holding_bars: int = 48,
    ):
        self.sr_detector = SupportResistanceDetector(lookback_bars=lookback_bars, tolerance_pct=level_tolerance_pct)
        self.entry_tolerance_pct = entry_tolerance_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_holding_bars = max_holding_bars
        self.current_levels = None
        self.entry_bar = None
        self.position = 0
        self.position_entry_price = None
        # Backtest engine will set data before calling
        self.data = None

    def on_start(self, data: pd.DataFrame):
        self.data = data

    def on_bar(self, bar: pd.Series, data: pd.DataFrame) -> Optional[Dict]:
        current_price = float(bar['close'])
        idx = len(data) - 1
        self.data = data
        # Update levels periodically
        if idx % 10 == 0 or self.current_levels is None:
            self.current_levels = self.sr_detector.detect_levels(data)
        # Check exits if in position
        if self.position != 0:
            exit_signal = self._check_exit_conditions(bar, idx, current_price)
            if exit_signal:
                return exit_signal
        # If flat, check entry
        if self.position == 0:
            nearest = self.sr_detector.get_nearest_levels(current_price, self.current_levels)
            # Long at support
            ns = nearest.get('nearest_support')
            if ns is not None:
                dist = nearest.get('distance_to_support_pct')
                if dist is not None and dist <= self.entry_tolerance_pct:
                    return self._create_long_signal(current_price, ns, nearest.get('nearest_resistance'))
            # Short at resistance
            nr = nearest.get('nearest_resistance')
            if nr is not None:
                dist_r = nearest.get('distance_to_resistance_pct')
                if dist_r is not None and dist_r <= self.entry_tolerance_pct:
                    return self._create_short_signal(current_price, nr, nearest.get('nearest_support'))
        return None

    def _create_long_signal(self, current_price: float, support_level: float, resistance_level: Optional[float]) -> Dict:
        self.entry_bar = len(self.data) - 1
        self.position = 1
        self.position_entry_price = current_price
        stop_loss = support_level * (1 - self.stop_loss_pct / 100)
        take_profit = resistance_level if resistance_level is not None else current_price * 1.02
        return {
            'action': 'LONG',
            'reason': f'Near support {support_level:.2f}',
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }

    def _create_short_signal(self, current_price: float, resistance_level: float, support_level: Optional[float]) -> Dict:
        self.entry_bar = len(self.data) - 1
        self.position = -1
        self.position_entry_price = current_price
        stop_loss = resistance_level * (1 + self.stop_loss_pct / 100)
        take_profit = support_level if support_level is not None else current_price * 0.98
        return {
            'action': 'SHORT',
            'reason': f'Near resistance {resistance_level:.2f}',
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }

    def _check_exit_conditions(self, bar: pd.Series, idx: int, current_price: float) -> Optional[Dict]:
        bars_held = idx - (self.entry_bar or idx)
        if bars_held >= self.max_holding_bars:
            # Reset position on close
            self.position = 0
            self.position_entry_price = None
            return {
                'action': 'CLOSE',
                'reason': f'Max holding period {bars_held} bars',
                'exit_price': current_price
            }
        # stop loss / take profit are enforced by the backtest engine according to returned values
        return None
