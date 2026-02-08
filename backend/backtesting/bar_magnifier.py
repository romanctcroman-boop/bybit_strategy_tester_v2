"""
Bar Magnifier Module

TradingView Premium feature: Uses lower timeframe data for precise intrabar order execution.
Instead of OHLC assumptions, uses actual price movements within the bar.

TradingView behavior:
- If use_bar_magnifier = true, strategy uses LTF data for fills
- Maximum 200,000 bars from lower TF
- Auto-selects appropriate LTF based on chart TF
"""


import pandas as pd
from loguru import logger


def get_magnifier_timeframe(chart_tf: str) -> str:
    """
    Get appropriate lower timeframe for bar magnifier.

    TradingView auto-selection logic:
    - 1D, 4H, 1H charts → 1m data
    - 15m, 30m charts → 1m data
    - 5m charts → 1m data
    - 1m charts → cannot use (already lowest)

    Args:
        chart_tf: Chart timeframe (e.g., "60", "240", "D", "1h", "4h")

    Returns:
        Lower timeframe string for magnifier
    """
    # Normalize timeframe
    tf_map = {
        "1": "1",
        "1m": "1",
        "3": "1",
        "3m": "1",
        "5": "1",
        "5m": "1",
        "15": "1",
        "15m": "1",
        "30": "1",
        "30m": "1",
        "60": "1",
        "1h": "1",
        "120": "1",
        "2h": "1",
        "240": "1",
        "4h": "1",
        "360": "1",
        "6h": "1",
        "720": "1",
        "12h": "1",
        "D": "1",
        "1d": "1",
        "W": "60",
        "1w": "60",  # Weekly uses 1h
        "M": "240",
        "1M": "240",  # Monthly uses 4h
    }

    return tf_map.get(chart_tf, "1")


def calculate_bars_ratio(chart_tf: str, magnifier_tf: str) -> int:
    """
    Calculate how many magnifier bars fit in one chart bar.

    Args:
        chart_tf: Chart timeframe
        magnifier_tf: Magnifier (lower) timeframe

    Returns:
        Number of LTF bars per chart bar
    """
    # Convert to minutes
    tf_minutes = {
        "1": 1,
        "1m": 1,
        "3": 3,
        "3m": 3,
        "5": 5,
        "5m": 5,
        "15": 15,
        "15m": 15,
        "30": 30,
        "30m": 30,
        "60": 60,
        "1h": 60,
        "120": 120,
        "2h": 120,
        "240": 240,
        "4h": 240,
        "360": 360,
        "6h": 360,
        "720": 720,
        "12h": 720,
        "D": 1440,
        "1d": 1440,
        "W": 10080,
        "1w": 10080,
        "M": 43200,
        "1M": 43200,
    }

    chart_minutes = tf_minutes.get(chart_tf, 60)
    mag_minutes = tf_minutes.get(magnifier_tf, 1)

    return chart_minutes // mag_minutes


def get_intrabar_path(
    ohlc_bar: dict, ltf_data: pd.DataFrame | None = None
) -> list[float]:
    """
    Get the intrabar price path for precise order execution.

    TradingView logic:
    1. If LTF data available → use actual OHLC sequence from LTF bars
    2. If no LTF data → use heuristic based on Open proximity to High/Low

    Args:
        ohlc_bar: Dict with 'open', 'high', 'low', 'close'
        ltf_data: Optional DataFrame with lower TF bars for this period

    Returns:
        List of prices representing intrabar path
    """
    o = ohlc_bar["open"]
    h = ohlc_bar["high"]
    low = ohlc_bar["low"]
    c = ohlc_bar["close"]

    # If we have LTF data, use it
    if ltf_data is not None and len(ltf_data) > 0:
        # Build path from LTF OHLC
        path = []
        for _, bar in ltf_data.iterrows():
            # Add O, H/L based on proximity, then C
            bar_o = bar.get("open", bar.get("Open", o))
            bar_h = bar.get("high", bar.get("High", h))
            bar_l = bar.get("low", bar.get("Low", low))
            bar_c = bar.get("close", bar.get("Close", c))

            # Infer direction within LTF bar
            if abs(bar_o - bar_h) < abs(bar_o - bar_l):
                # Open closer to High → went up first
                path.extend([bar_o, bar_h, bar_l, bar_c])
            else:
                # Open closer to Low → went down first
                path.extend([bar_o, bar_l, bar_h, bar_c])

        return path

    # Fallback: TradingView default heuristic
    # If Open is closer to High → path is O → H → L → C
    # If Open is closer to Low → path is O → L → H → C
    if abs(o - h) < abs(o - low):
        return [o, h, low, c]
    else:
        return [o, low, h, c]


def check_order_fill_on_path(
    order_type: str,
    order_price: float,
    intrabar_path: list[float],
    slippage_ticks: int = 0,
    min_tick: float = 0.01,
) -> tuple[bool, float, int]:
    """
    Check if an order would be filled on the intrabar path.

    Args:
        order_type: 'limit_long', 'limit_short', 'stop_long', 'stop_short'
        order_price: Target order price
        intrabar_path: List of prices representing intrabar movement
        slippage_ticks: Slippage in ticks to add
        min_tick: Minimum price increment

    Returns:
        Tuple of (filled: bool, fill_price: float, fill_index: int)
    """
    slippage = slippage_ticks * min_tick

    for i, price in enumerate(intrabar_path):
        if order_type == "limit_long":
            # Buy limit: fill when price drops to or below limit
            if price <= order_price:
                fill_price = min(price, order_price) + slippage
                return True, fill_price, i

        elif order_type == "limit_short":
            # Sell limit: fill when price rises to or above limit
            if price >= order_price:
                fill_price = max(price, order_price) - slippage
                return True, fill_price, i

        elif order_type == "stop_long":
            # Buy stop: fill when price rises above stop (breakout)
            if price >= order_price:
                fill_price = max(price, order_price) + slippage
                return True, fill_price, i

        elif order_type == "stop_short":
            # Sell stop: fill when price drops below stop (breakdown)
            if price <= order_price:
                fill_price = min(price, order_price) - slippage
                return True, fill_price, i

    return False, 0.0, -1


def check_sl_tp_on_path(
    position_side: str,  # 'long' or 'short'
    entry_price: float,
    sl_price: float | None,
    tp_price: float | None,
    intrabar_path: list[float],
    sl_priority: bool = True,
) -> tuple[str, float, int]:
    """
    Check if SL or TP would be hit on the intrabar path.

    Precisely determines which exit would trigger first.

    Args:
        position_side: 'long' or 'short'
        entry_price: Position entry price
        sl_price: Stop loss price (None if not set)
        tp_price: Take profit price (None if not set)
        intrabar_path: List of prices
        sl_priority: If both triggered at same point, SL wins

    Returns:
        Tuple of (exit_type: 'sl'/'tp'/'none', exit_price: float, exit_index: int)
    """
    sl_triggered = False
    tp_triggered = False
    sl_index = -1
    tp_index = -1
    sl_fill = 0.0
    tp_fill = 0.0

    for i, price in enumerate(intrabar_path):
        if position_side == "long":
            # Long: SL if price drops to sl_price, TP if price rises to tp_price
            if sl_price is not None and not sl_triggered and price <= sl_price:
                sl_triggered = True
                sl_index = i
                sl_fill = min(price, sl_price)

            if tp_price is not None and not tp_triggered and price >= tp_price:
                tp_triggered = True
                tp_index = i
                tp_fill = max(price, tp_price)
        else:
            # Short: SL if price rises to sl_price, TP if price drops to tp_price
            if sl_price is not None and not sl_triggered and price >= sl_price:
                sl_triggered = True
                sl_index = i
                sl_fill = max(price, sl_price)

            if tp_price is not None and not tp_triggered and price <= tp_price:
                tp_triggered = True
                tp_index = i
                tp_fill = min(price, tp_price)

    # Determine which triggered first
    if sl_triggered and tp_triggered:
        if sl_index < tp_index:
            return "sl", sl_fill, sl_index
        elif tp_index < sl_index:
            return "tp", tp_fill, tp_index
        else:
            # Same index - use priority
            if sl_priority:
                return "sl", sl_fill, sl_index
            else:
                return "tp", tp_fill, tp_index
    elif sl_triggered:
        return "sl", sl_fill, sl_index
    elif tp_triggered:
        return "tp", tp_fill, tp_index
    else:
        return "none", 0.0, -1


class BarMagnifier:
    """
    Bar Magnifier for precise intrabar order execution.

    TradingView Premium feature simulation.
    """

    def __init__(
        self, chart_tf: str, magnifier_tf: str | None = None, max_bars: int = 200000
    ):
        """
        Initialize Bar Magnifier.

        Args:
            chart_tf: Chart timeframe
            magnifier_tf: Lower timeframe for magnification (auto if None)
            max_bars: Maximum LTF bars to load
        """
        self.chart_tf = chart_tf
        self.magnifier_tf = magnifier_tf or get_magnifier_timeframe(chart_tf)
        self.max_bars = max_bars
        self.bars_ratio = calculate_bars_ratio(chart_tf, self.magnifier_tf)
        self.ltf_data: pd.DataFrame | None = None

        logger.info(
            f"Bar Magnifier initialized: {chart_tf} → {self.magnifier_tf} "
            f"({self.bars_ratio}x resolution)"
        )

    def load_ltf_data(self, ltf_data: pd.DataFrame) -> None:
        """
        Load lower timeframe data for magnification.

        Args:
            ltf_data: DataFrame with LTF OHLCV data
        """
        if len(ltf_data) > self.max_bars:
            logger.warning(
                f"LTF data ({len(ltf_data)} bars) exceeds max ({self.max_bars}). "
                f"Using last {self.max_bars} bars."
            )
            ltf_data = ltf_data.tail(self.max_bars)

        self.ltf_data = ltf_data
        logger.info(f"Loaded {len(ltf_data)} LTF bars for magnification")

    def get_bar_path(self, bar_timestamp: pd.Timestamp, ohlc: dict) -> list[float]:
        """
        Get intrabar price path for a specific bar.

        Args:
            bar_timestamp: Bar timestamp
            ohlc: Dict with 'open', 'high', 'low', 'close'

        Returns:
            List of intrabar prices
        """
        if self.ltf_data is None or len(self.ltf_data) == 0:
            return get_intrabar_path(ohlc)

        # Find LTF bars within this chart bar
        bar_end = bar_timestamp
        bar_start = bar_timestamp - pd.Timedelta(
            minutes=self._get_tf_minutes(self.chart_tf)
        )

        ltf_mask = (self.ltf_data.index >= bar_start) & (self.ltf_data.index < bar_end)
        ltf_bars = self.ltf_data[ltf_mask]

        return get_intrabar_path(ohlc, ltf_bars if len(ltf_bars) > 0 else None)

    def _get_tf_minutes(self, tf: str) -> int:
        """Get timeframe duration in minutes."""
        tf_map = {
            "1": 1,
            "1m": 1,
            "3": 3,
            "3m": 3,
            "5": 5,
            "5m": 5,
            "15": 15,
            "15m": 15,
            "30": 30,
            "30m": 30,
            "60": 60,
            "1h": 60,
            "120": 120,
            "2h": 120,
            "240": 240,
            "4h": 240,
            "360": 360,
            "6h": 360,
            "720": 720,
            "12h": 720,
            "D": 1440,
            "1d": 1440,
            "W": 10080,
            "1w": 10080,
            "M": 43200,
            "1M": 43200,
        }
        return tf_map.get(tf, 60)
