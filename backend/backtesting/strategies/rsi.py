"""
RSI Strategy

Simple RSI-based trading strategy for use in portfolio backtesting.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class RSIStrategy:
    """
    Simple RSI mean-reversion strategy.

    Generates long signals when RSI drops below oversold threshold and
    short signals when RSI rises above overbought threshold.

    Args:
        period: RSI lookback period (default 14).
        oversold: RSI oversold level (default 30).
        overbought: RSI overbought level (default 70).
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ) -> None:
        self.period = int(period)
        self.oversold = oversold
        self.overbought = overbought

    # ------------------------------------------------------------------
    # Core signal generation
    # ------------------------------------------------------------------

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals from OHLCV data.

        Args:
            data: DataFrame with at least a 'close' column.

        Returns:
            DataFrame with an additional 'signal' column
            (1 = long, -1 = short, 0 = hold).
        """
        df = data.copy()
        df["signal"] = 0

        rsi = self._calculate_rsi(df["close"], self.period)

        df.loc[rsi < self.oversold, "signal"] = 1
        df.loc[rsi > self.overbought, "signal"] = -1

        return df

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _calculate_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """Calculate RSI using Wilder's smoothing."""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - (100 / (1 + rs))

    def __repr__(self) -> str:
        return f"RSIStrategy(period={self.period}, oversold={self.oversold}, overbought={self.overbought})"
