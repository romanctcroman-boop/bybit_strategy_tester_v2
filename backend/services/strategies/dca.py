"""
DCA (Dollar Cost Averaging) Strategy.

Systematic buying/selling at regular intervals or on price dips.
Reduces timing risk by spreading entries over time.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.services.live_trading.strategy_runner import (
    SignalType,
    StrategyConfig,
    TradingSignal,
)
from backend.services.strategies.base import (
    LibraryStrategy,
    ParameterSpec,
    ParameterType,
    StrategyCategory,
    StrategyInfo,
    register_strategy,
)

logger = logging.getLogger(__name__)


@dataclass
class DCAParams:
    """Parameters for DCA strategy."""

    dca_interval_candles: int = 24  # Buy every N candles
    base_amount_percent: float = 1.0  # Base % of equity per buy
    dip_multiplier: float = 2.0  # Multiplier when buying dips
    dip_threshold_percent: float = 5.0  # Price drop to trigger dip buy
    take_profit_percent: float = 10.0  # Overall take profit target
    use_rsi_filter: bool = True  # Only DCA when RSI < threshold
    rsi_threshold: float = 50.0  # RSI threshold for buying
    max_positions: int = 10  # Maximum DCA entries


DCA_INFO = StrategyInfo(
    id="dca_strategy",
    name="DCA (Dollar Cost Averaging)",
    description="""
    Systematic accumulation strategy using Dollar Cost Averaging.

    How it works:
    1. Buy at regular intervals (e.g., every 24 candles)
    2. Buy more on dips (when price drops significantly)
    3. Take profit when overall position reaches target

    Benefits:
    - Reduces timing risk
    - Averages out entry price
    - Systematic, emotion-free trading

    Best for: Long-term accumulation in assets you believe will appreciate.
    Not recommended for: Short-term trading or uncertain assets.
    """,
    category=StrategyCategory.DCA,
    version="1.0.0",
    author="System",
    min_candles=30,
    recommended_timeframes=["60", "240", "D"],
    suitable_markets=["crypto", "stocks"],
    avg_trades_per_day=0.5,
    expected_win_rate=0.70,
    expected_risk_reward=3.0,
    typical_holding_period="weeks",
    risk_level="conservative",
    max_drawdown_expected=0.25,
    parameters=[
        ParameterSpec(
            name="dca_interval_candles",
            param_type=ParameterType.INT,
            default=24,
            description="Buy every N candles",
            min_value=4,
            max_value=168,
            step=4,
        ),
        ParameterSpec(
            name="base_amount_percent",
            param_type=ParameterType.FLOAT,
            default=1.0,
            description="Base buy amount (% of equity)",
            min_value=0.5,
            max_value=5.0,
            step=0.5,
        ),
        ParameterSpec(
            name="dip_multiplier",
            param_type=ParameterType.FLOAT,
            default=2.0,
            description="Amount multiplier on dips",
            min_value=1.0,
            max_value=5.0,
            step=0.5,
        ),
        ParameterSpec(
            name="dip_threshold_percent",
            param_type=ParameterType.FLOAT,
            default=5.0,
            description="% drop to trigger dip buy",
            min_value=2.0,
            max_value=15.0,
            step=1.0,
        ),
        ParameterSpec(
            name="take_profit_percent",
            param_type=ParameterType.FLOAT,
            default=10.0,
            description="Take profit target (%)",
            min_value=5.0,
            max_value=50.0,
            step=5.0,
        ),
        ParameterSpec(
            name="use_rsi_filter",
            param_type=ParameterType.BOOL,
            default=True,
            description="Only buy when RSI is favorable",
        ),
        ParameterSpec(
            name="rsi_threshold",
            param_type=ParameterType.FLOAT,
            default=50.0,
            description="Only buy when RSI below this",
            min_value=30.0,
            max_value=70.0,
            step=10.0,
        ),
        ParameterSpec(
            name="max_positions",
            param_type=ParameterType.INT,
            default=10,
            description="Maximum DCA entries",
            min_value=3,
            max_value=50,
            step=1,
        ),
    ],
    tags=["dca", "accumulation", "long-term", "systematic"],
)


@register_strategy
class DCAStrategy(LibraryStrategy):
    """
    DCA (Dollar Cost Averaging) Strategy.

    Systematic buying at regular intervals and on dips.
    """

    STRATEGY_INFO = DCA_INFO

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config, **params)

        # Position tracking
        self._entries: list = []  # List of (price, qty, time)
        self._total_cost: float = 0.0
        self._total_qty: float = 0.0
        self._avg_entry: float = 0.0

        # Timing
        self._candles_since_last_buy: int = 0
        self._last_buy_time: Optional[datetime] = None

        # Peak tracking for dips
        self._recent_high: float = 0.0

    @property
    def position_count(self) -> int:
        """Number of DCA entries made."""
        return len(self._entries)

    def _add_entry(self, price: float, qty: float, timestamp: datetime):
        """Record a new DCA entry."""
        self._entries.append((price, qty, timestamp))
        self._total_cost += price * qty
        self._total_qty += qty

        if self._total_qty > 0:
            self._avg_entry = self._total_cost / self._total_qty

    def _calculate_pnl_percent(self, current_price: float) -> float:
        """Calculate current PnL percentage."""
        if self._avg_entry <= 0:
            return 0.0
        return ((current_price - self._avg_entry) / self._avg_entry) * 100

    def _is_dip(self, current_price: float, threshold: float) -> bool:
        """Check if current price is a dip from recent high."""
        if self._recent_high <= 0:
            return False
        drop_percent = ((self._recent_high - current_price) / self._recent_high) * 100
        return drop_percent >= threshold

    def on_candle(self, candle: dict) -> Optional[TradingSignal]:
        """Process candle and generate DCA signals."""
        self.add_candle(candle)

        if not self.warmup_complete():
            return None

        # Parameters
        interval = self.get_param("dca_interval_candles", 24)
        # base_amount_percent reserved for position sizing (uses fixed amounts now)
        _ = self.get_param("base_amount_percent", 1.0)
        dip_mult = self.get_param("dip_multiplier", 2.0)
        dip_threshold = self.get_param("dip_threshold_percent", 5.0)
        tp_pct = self.get_param("take_profit_percent", 10.0)
        use_rsi = self.get_param("use_rsi_filter", True)
        rsi_thresh = self.get_param("rsi_threshold", 50.0)
        max_pos = self.get_param("max_positions", 10)

        close = candle["close"]
        high = candle["high"]
        timestamp = datetime.now(timezone.utc)

        # Update recent high
        if high > self._recent_high:
            self._recent_high = high

        # Decay recent high slowly (for long-term tracking)
        lookback = 50
        if len(self._candles) >= lookback:
            highs = self.get_highs(lookback)
            self._recent_high = max(highs) if highs else high

        self._candles_since_last_buy += 1

        signal = None

        # Check take profit first
        if self._total_qty > 0:
            pnl_pct = self._calculate_pnl_percent(close)

            if pnl_pct >= tp_pct:
                # Take profit - close all
                signal = self.create_signal(
                    signal_type=SignalType.CLOSE_ALL,
                    price=close,
                    reason=f"DCA Take Profit reached ({pnl_pct:.1f}% >= {tp_pct}%)",
                    confidence=0.9,
                    pnl_percent=pnl_pct,
                    avg_entry=self._avg_entry,
                    total_qty=self._total_qty,
                )

                # Reset tracking
                self._entries = []
                self._total_cost = 0.0
                self._total_qty = 0.0
                self._avg_entry = 0.0
                self._candles_since_last_buy = 0

                return signal

        # Check if we can add more positions
        if self.position_count >= max_pos:
            return None

        # RSI filter
        if use_rsi:
            current_rsi = self.rsi(14)
            if current_rsi > rsi_thresh:
                return None  # RSI too high, wait

        should_buy = False
        buy_reason = ""
        confidence = 0.6
        qty_multiplier = 1.0

        # Check for dip buy opportunity
        if self._is_dip(close, dip_threshold):
            should_buy = True
            buy_reason = f"DCA dip buy ({dip_threshold}% drop from high)"
            confidence = 0.75
            qty_multiplier = dip_mult
            self._candles_since_last_buy = 0  # Reset interval counter

        # Regular interval buy
        elif self._candles_since_last_buy >= interval:
            should_buy = True
            buy_reason = f"DCA scheduled buy (every {interval} candles)"
            confidence = 0.65
            qty_multiplier = 1.0

        if should_buy:
            signal = self.create_signal(
                signal_type=SignalType.BUY,
                price=close,
                reason=buy_reason,
                confidence=confidence,
                dca_entry=self.position_count + 1,
                avg_entry=self._avg_entry if self._avg_entry > 0 else close,
                qty_multiplier=qty_multiplier,
            )

            # Track entry (using 1.0 as base qty - actual qty from position sizing)
            base_qty = 1.0 * qty_multiplier
            self._add_entry(close, base_qty, timestamp)
            self._candles_since_last_buy = 0
            self._last_buy_time = timestamp

        return signal


# Factory functions
def create_standard_dca_strategy(config: StrategyConfig) -> DCAStrategy:
    """Create standard DCA strategy (daily buys, 10% TP)."""
    return DCAStrategy(
        config,
        dca_interval_candles=24,  # Assuming hourly candles = daily
        base_amount_percent=1.0,
        dip_multiplier=2.0,
        dip_threshold_percent=5.0,
        take_profit_percent=10.0,
        use_rsi_filter=True,
        rsi_threshold=50.0,
        max_positions=10,
    )


def create_aggressive_dca_strategy(config: StrategyConfig) -> DCAStrategy:
    """Create aggressive DCA strategy (more frequent, larger positions)."""
    return DCAStrategy(
        config,
        dca_interval_candles=12,  # Every 12 candles
        base_amount_percent=2.0,
        dip_multiplier=3.0,
        dip_threshold_percent=3.0,
        take_profit_percent=15.0,
        use_rsi_filter=False,  # Buy regardless of RSI
        max_positions=20,
    )
