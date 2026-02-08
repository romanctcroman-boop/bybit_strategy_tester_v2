"""
🎯 DCA Multi-TP Strategy - Professional DCA with Multi-Level Take Profit

Combines Dollar Cost Averaging with advanced features:
- Multi-Timeframe (MTF) filtering for trend alignment
- Multi-Level TP (TP1-TP4) with partial closes
- ATR-based dynamic TP/SL
- Tick-based calculations for precision
- Support for both Long and Short directions

Version: 1.0.0
Author: AI Agent
Date: 2026-01-27
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd


class DCADirection(Enum):
    """DCA direction."""

    LONG = "long"
    SHORT = "short"


class TPMode(Enum):
    """Take Profit mode."""

    FIXED = "fixed"  # Single TP level
    MULTI = "multi"  # Multi-level TP (TP1-TP4)
    ATR = "atr"  # ATR-based TP


class SLMode(Enum):
    """Stop Loss mode."""

    FIXED = "fixed"  # Fixed % from entry
    ATR = "atr"  # ATR-based SL
    TRAILING = "trailing"  # Trailing stop


@dataclass
class DCAMultiTPConfig:
    """
    Configuration for DCA Multi-TP Strategy.

    All parameters in one place for easy management.
    """

    # === DIRECTION ===
    direction: DCADirection = DCADirection.LONG

    # === BASE ORDER ===
    base_order_size_pct: float = 10.0  # % of capital for base order

    # === SAFETY ORDERS (DCA) ===
    max_safety_orders: int = 5  # Maximum SOs (0 = disabled)
    safety_order_size_pct: float = 10.0  # % of capital for first SO
    price_deviation_pct: float = 1.0  # First SO trigger: -1% from entry
    step_scale: float = 1.4  # Deviation multiplier: SO2 at 1.4%, SO3 at 1.96%
    volume_scale: float = 1.0  # Volume multiplier (1.0 = no martingale)

    # === TAKE PROFIT MODE ===
    tp_mode: TPMode = TPMode.MULTI

    # Fixed TP (tp_mode=FIXED)
    fixed_tp_pct: float = 3.0  # Single TP at 3%

    # Multi-TP (tp_mode=MULTI)
    tp_levels_pct: tuple[float, ...] = (0.5, 1.0, 1.5, 2.5)  # TP1=0.5%, TP2=1%, etc.
    tp_portions: tuple[float, ...] = (0.25, 0.25, 0.25, 0.25)  # 25% each

    # ATR TP (tp_mode=ATR)
    atr_tp_multiplier: float = 2.0  # TP = Entry ± ATR × multiplier

    # === STOP LOSS MODE ===
    sl_mode: SLMode = SLMode.FIXED

    # Fixed SL (sl_mode=FIXED)
    fixed_sl_pct: float = 5.0  # SL at -5% from average entry

    # ATR SL (sl_mode=ATR)
    atr_sl_multiplier: float = 1.5  # SL = Entry ∓ ATR × multiplier

    # Trailing SL (sl_mode=TRAILING)
    trailing_activation_pct: float = 1.0  # Activate after 1% profit
    trailing_distance_pct: float = 0.5  # Trail at 0.5% distance

    # === BREAKEVEN ===
    breakeven_enabled: bool = False  # Move SL to breakeven after TP1
    breakeven_offset_pct: float = 0.1  # Offset from average (+0.1%)

    # === ATR PARAMETERS ===
    atr_period: int = 14  # ATR calculation period

    # === RSI FILTER (Trade Start Condition) ===
    rsi_enabled: bool = True  # Use RSI for entry filter
    rsi_period: int = 14
    rsi_oversold: float = 30.0  # Long entry when RSI < 30
    rsi_overbought: float = 70.0  # Short entry when RSI > 70

    # === MULTI-TIMEFRAME FILTER ===
    mtf_enabled: bool = False  # Enable MTF filtering
    mtf_filter_type: str = "sma"  # "sma" or "ema"
    mtf_filter_period: int = 200  # HTF indicator period
    mtf_neutral_zone_pct: float = 0.0  # 0 = strict mode

    # === TIME FILTERS ===
    cooldown_bars: int = 4  # Min bars between deals
    max_bars_in_trade: int = 0  # Max holding time (0 = unlimited)
    max_deals: int = 0  # Max completed deals (0 = unlimited)

    # === RISK MANAGEMENT ===
    max_position_size_pct: float = 100.0  # Max position as % of capital

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "direction": self.direction.value,
            "base_order_size_pct": self.base_order_size_pct,
            "max_safety_orders": self.max_safety_orders,
            "safety_order_size_pct": self.safety_order_size_pct,
            "price_deviation_pct": self.price_deviation_pct,
            "step_scale": self.step_scale,
            "volume_scale": self.volume_scale,
            "tp_mode": self.tp_mode.value,
            "fixed_tp_pct": self.fixed_tp_pct,
            "tp_levels_pct": self.tp_levels_pct,
            "tp_portions": self.tp_portions,
            "atr_tp_multiplier": self.atr_tp_multiplier,
            "sl_mode": self.sl_mode.value,
            "fixed_sl_pct": self.fixed_sl_pct,
            "atr_sl_multiplier": self.atr_sl_multiplier,
            "trailing_activation_pct": self.trailing_activation_pct,
            "trailing_distance_pct": self.trailing_distance_pct,
            "breakeven_enabled": self.breakeven_enabled,
            "breakeven_offset_pct": self.breakeven_offset_pct,
            "atr_period": self.atr_period,
            "rsi_enabled": self.rsi_enabled,
            "rsi_period": self.rsi_period,
            "rsi_oversold": self.rsi_oversold,
            "rsi_overbought": self.rsi_overbought,
            "mtf_enabled": self.mtf_enabled,
            "mtf_filter_type": self.mtf_filter_type,
            "mtf_filter_period": self.mtf_filter_period,
            "mtf_neutral_zone_pct": self.mtf_neutral_zone_pct,
            "cooldown_bars": self.cooldown_bars,
            "max_bars_in_trade": self.max_bars_in_trade,
            "max_deals": self.max_deals,
            "max_position_size_pct": self.max_position_size_pct,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DCAMultiTPConfig":
        """Create config from dictionary."""
        direction = DCADirection(data.get("direction", "long"))
        tp_mode = TPMode(data.get("tp_mode", "multi"))
        sl_mode = SLMode(data.get("sl_mode", "fixed"))

        return cls(
            direction=direction,
            base_order_size_pct=data.get("base_order_size_pct", 10.0),
            max_safety_orders=data.get("max_safety_orders", 5),
            safety_order_size_pct=data.get("safety_order_size_pct", 10.0),
            price_deviation_pct=data.get("price_deviation_pct", 1.0),
            step_scale=data.get("step_scale", 1.4),
            volume_scale=data.get("volume_scale", 1.0),
            tp_mode=tp_mode,
            fixed_tp_pct=data.get("fixed_tp_pct", 3.0),
            tp_levels_pct=tuple(data.get("tp_levels_pct", (0.5, 1.0, 1.5, 2.5))),
            tp_portions=tuple(data.get("tp_portions", (0.25, 0.25, 0.25, 0.25))),
            atr_tp_multiplier=data.get("atr_tp_multiplier", 2.0),
            sl_mode=sl_mode,
            fixed_sl_pct=data.get("fixed_sl_pct", 5.0),
            atr_sl_multiplier=data.get("atr_sl_multiplier", 1.5),
            trailing_activation_pct=data.get("trailing_activation_pct", 1.0),
            trailing_distance_pct=data.get("trailing_distance_pct", 0.5),
            breakeven_enabled=data.get("breakeven_enabled", False),
            breakeven_offset_pct=data.get("breakeven_offset_pct", 0.1),
            atr_period=data.get("atr_period", 14),
            rsi_enabled=data.get("rsi_enabled", True),
            rsi_period=data.get("rsi_period", 14),
            rsi_oversold=data.get("rsi_oversold", 30.0),
            rsi_overbought=data.get("rsi_overbought", 70.0),
            mtf_enabled=data.get("mtf_enabled", False),
            mtf_filter_type=data.get("mtf_filter_type", "sma"),
            mtf_filter_period=data.get("mtf_filter_period", 200),
            mtf_neutral_zone_pct=data.get("mtf_neutral_zone_pct", 0.0),
            cooldown_bars=data.get("cooldown_bars", 4),
            max_bars_in_trade=data.get("max_bars_in_trade", 0),
            max_deals=data.get("max_deals", 0),
            max_position_size_pct=data.get("max_position_size_pct", 100.0),
        )


@dataclass
class DCADealState:
    """
    State of a single DCA deal (position).

    Tracks all entries, TP hits, average price, etc.
    """

    # Entry tracking
    entries: list[tuple[float, float, int]] = field(
        default_factory=list
    )  # (price, size, bar_idx)
    total_cost: float = 0.0
    total_size: float = 0.0
    avg_entry_price: float = 0.0
    base_entry_price: float = 0.0  # First entry price
    last_entry_price: float = 0.0
    entry_bar: int = 0  # Bar of first entry

    # Multi-TP state
    tp_prices: list[float] = field(default_factory=list)
    tp_hit: list[bool] = field(default_factory=list)
    remaining_size: float = 0.0  # After partial closes

    # SL state
    sl_price: float = 0.0
    breakeven_active: bool = False

    # Trailing state
    trailing_active: bool = False
    peak_price: float = 0.0  # Highest (long) or lowest (short)
    trailing_sl_price: float = 0.0

    # MFE/MAE tracking
    mfe: float = 0.0  # Maximum favorable excursion
    mae: float = 0.0  # Maximum adverse excursion

    def add_entry(self, price: float, size: float, bar_idx: int):
        """Add new entry (base order or safety order)."""
        self.entries.append((price, size, bar_idx))
        self.total_cost += price * size
        self.total_size += size
        self.avg_entry_price = (
            self.total_cost / self.total_size if self.total_size > 0 else 0.0
        )

        if len(self.entries) == 1:
            self.base_entry_price = price
            self.entry_bar = bar_idx

        self.last_entry_price = price
        self.remaining_size = self.total_size

    def get_entry_count(self) -> int:
        """Get number of entries (base + SOs)."""
        return len(self.entries)

    def is_active(self) -> bool:
        """Check if deal is active (has entries)."""
        return len(self.entries) > 0 and self.remaining_size > 0

    def update_mfe_mae(self, high: float, low: float, direction: str):
        """Update MFE/MAE based on current bar."""
        if not self.is_active() or self.avg_entry_price <= 0:
            return

        if direction == "long":
            # MFE: best profit (highest high)
            favorable = (high - self.avg_entry_price) / self.avg_entry_price
            adverse = (self.avg_entry_price - low) / self.avg_entry_price
        else:
            # SHORT: MFE when price goes down
            favorable = (self.avg_entry_price - low) / self.avg_entry_price
            adverse = (high - self.avg_entry_price) / self.avg_entry_price

        self.mfe = max(self.mfe, favorable)
        self.mae = max(self.mae, adverse)

    def reset(self):
        """Reset state for new deal."""
        self.entries = []
        self.total_cost = 0.0
        self.total_size = 0.0
        self.avg_entry_price = 0.0
        self.base_entry_price = 0.0
        self.last_entry_price = 0.0
        self.entry_bar = 0
        self.tp_prices = []
        self.tp_hit = []
        self.remaining_size = 0.0
        self.sl_price = 0.0
        self.breakeven_active = False
        self.trailing_active = False
        self.peak_price = 0.0
        self.trailing_sl_price = 0.0
        self.mfe = 0.0
        self.mae = 0.0


@dataclass
class SignalResult:
    """Result of signal generation."""

    entries: pd.Series  # Boolean series for entries
    exits: pd.Series  # Boolean series for exits
    short_entries: pd.Series | None = None
    short_exits: pd.Series | None = None
    entry_sizes: pd.Series | None = None  # Position size per entry
    short_entry_sizes: pd.Series | None = None

    # Multi-TP partial close signals
    tp1_exits: pd.Series | None = None
    tp2_exits: pd.Series | None = None
    tp3_exits: pd.Series | None = None
    tp4_exits: pd.Series | None = None


class DCAMultiTPStrategy:
    """
    DCA Strategy with Multi-Level Take Profit and MTF filtering.

    Features:
    - Multi-Timeframe trend filtering (e.g., 15m signals + 1H SMA200 filter)
    - Multi-Level TP (TP1-TP4) with partial closes
    - ATR-based dynamic TP/SL
    - Breakeven stop after TP1
    - Trailing stop option
    - Full MFE/MAE tracking

    Example:
        config = DCAMultiTPConfig(
            direction=DCADirection.LONG,
            max_safety_orders=5,
            tp_mode=TPMode.MULTI,
            tp_levels_pct=(0.5, 1.0, 1.5, 2.5),
            mtf_enabled=True,
            mtf_filter_period=200,
        )
        strategy = DCAMultiTPStrategy(config)
        signals = strategy.generate_signals(ohlcv, htf_ohlcv)
    """

    name = "dca_multi_tp"
    description = "DCA with Multi-TP, MTF filtering, ATR support"

    def __init__(self, config: DCAMultiTPConfig):
        self.config = config
        self._validate_config()
        self._precompute_so_levels()

    def _validate_config(self):
        """Validate configuration parameters."""
        cfg = self.config

        if cfg.max_safety_orders < 0:
            raise ValueError(
                f"max_safety_orders must be >= 0, got {cfg.max_safety_orders}"
            )

        if cfg.tp_mode == TPMode.MULTI:
            if len(cfg.tp_levels_pct) != len(cfg.tp_portions):
                raise ValueError("tp_levels_pct and tp_portions must have same length")
            if abs(sum(cfg.tp_portions) - 1.0) > 0.01:
                raise ValueError(
                    f"tp_portions must sum to 1.0, got {sum(cfg.tp_portions)}"
                )

        if cfg.fixed_sl_pct < 0:
            raise ValueError(f"fixed_sl_pct must be >= 0, got {cfg.fixed_sl_pct}")

    def _precompute_so_levels(self):
        """Pre-compute safety order price deviation levels."""
        cfg = self.config

        # SO levels: cumulative deviation from entry
        # SO1 at price_deviation, SO2 at price_deviation * (1 + step_scale), etc.
        self.so_levels = []
        self.so_volumes = []

        cumulative = 0.0
        current_deviation = cfg.price_deviation_pct / 100.0
        current_volume = cfg.safety_order_size_pct / 100.0

        for _ in range(cfg.max_safety_orders):
            cumulative += current_deviation
            self.so_levels.append(cumulative)
            self.so_volumes.append(current_volume)
            current_deviation *= cfg.step_scale
            current_volume *= cfg.volume_scale

    def _calculate_rsi(self, close: pd.Series) -> pd.Series:
        """Calculate RSI using Wilder's Smoothing (matches TradingView)."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        alpha = 1.0 / self.config.rsi_period
        avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_atr(
        self, high: pd.Series, low: pd.Series, close: pd.Series
    ) -> pd.Series:
        """Calculate ATR using Wilder's smoothing."""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        alpha = 1.0 / self.config.atr_period
        atr = tr.ewm(alpha=alpha, adjust=False).mean()
        return atr

    def _calculate_htf_indicator(
        self, htf_close: pd.Series, period: int, filter_type: str
    ) -> pd.Series:
        """Calculate HTF trend indicator (SMA or EMA)."""
        if filter_type.lower() == "ema":
            return htf_close.ewm(span=period, adjust=False).mean()
        else:
            return htf_close.rolling(window=period).mean()

    def _check_mtf_filter(
        self, htf_close: float, htf_indicator: float, direction: str
    ) -> bool:
        """
        Check if signal is allowed by MTF filter.

        For LONG: HTF close must be above HTF indicator
        For SHORT: HTF close must be below HTF indicator
        """
        if not self.config.mtf_enabled:
            return True

        if htf_indicator <= 0:
            return True  # No valid indicator

        neutral_zone = self.config.mtf_neutral_zone_pct / 100.0
        distance_pct = (htf_close - htf_indicator) / htf_indicator

        # In neutral zone - allow both
        if abs(distance_pct) <= neutral_zone:
            return True

        if direction == "long":
            return htf_close > htf_indicator
        else:
            return htf_close < htf_indicator

    def _calculate_tp_prices(
        self, avg_entry: float, atr: float, direction: str
    ) -> list[float]:
        """
        Calculate take profit prices based on mode.

        Returns list of TP prices (4 levels for MULTI mode).
        """
        cfg = self.config
        tp_prices = []

        if cfg.tp_mode == TPMode.FIXED:
            # Single TP
            tp_pct = cfg.fixed_tp_pct / 100.0
            if direction == "long":
                tp_prices = [avg_entry * (1 + tp_pct)]
            else:
                tp_prices = [avg_entry * (1 - tp_pct)]

        elif cfg.tp_mode == TPMode.MULTI:
            # Multi-level TP
            for tp_pct in cfg.tp_levels_pct:
                tp_pct_decimal = tp_pct / 100.0
                if direction == "long":
                    tp_prices.append(avg_entry * (1 + tp_pct_decimal))
                else:
                    tp_prices.append(avg_entry * (1 - tp_pct_decimal))

        elif cfg.tp_mode == TPMode.ATR:
            # ATR-based TP
            if atr > 0:
                if direction == "long":
                    tp_prices = [avg_entry + atr * cfg.atr_tp_multiplier]
                else:
                    tp_prices = [avg_entry - atr * cfg.atr_tp_multiplier]
            else:
                # Fallback to fixed if ATR not available
                tp_pct = cfg.fixed_tp_pct / 100.0
                if direction == "long":
                    tp_prices = [avg_entry * (1 + tp_pct)]
                else:
                    tp_prices = [avg_entry * (1 - tp_pct)]

        return tp_prices

    def _calculate_sl_price(
        self, avg_entry: float, atr: float, direction: str
    ) -> float:
        """Calculate stop loss price based on mode."""
        cfg = self.config

        if cfg.sl_mode == SLMode.FIXED:
            sl_pct = cfg.fixed_sl_pct / 100.0
            if direction == "long":
                return avg_entry * (1 - sl_pct)
            else:
                return avg_entry * (1 + sl_pct)

        elif cfg.sl_mode == SLMode.ATR:
            if atr > 0:
                if direction == "long":
                    return avg_entry - atr * cfg.atr_sl_multiplier
                else:
                    return avg_entry + atr * cfg.atr_sl_multiplier
            else:
                # Fallback to fixed
                sl_pct = cfg.fixed_sl_pct / 100.0
                if direction == "long":
                    return avg_entry * (1 - sl_pct)
                else:
                    return avg_entry * (1 + sl_pct)

        elif cfg.sl_mode == SLMode.TRAILING:
            # Initial SL same as FIXED, trailing will update later
            sl_pct = cfg.fixed_sl_pct / 100.0
            if direction == "long":
                return avg_entry * (1 - sl_pct)
            else:
                return avg_entry * (1 + sl_pct)

        return 0.0  # No SL

    def generate_signals(
        self,
        ohlcv: pd.DataFrame,
        htf_ohlcv: pd.DataFrame | None = None,
        htf_index_map: np.ndarray | None = None,
    ) -> SignalResult:
        """
        Generate trading signals with DCA, Multi-TP, and MTF filtering.

        Args:
            ohlcv: Main timeframe OHLCV data
            htf_ohlcv: Higher timeframe OHLCV data (optional)
            htf_index_map: Mapping from LTF index to HTF index (optional)

        Returns:
            SignalResult with entry/exit signals and sizes
        """
        cfg = self.config
        direction = cfg.direction.value

        # Extract OHLCV
        high_prices = ohlcv["high"]
        low_prices = ohlcv["low"]
        close_prices = ohlcv["close"]
        n = len(ohlcv)

        # Calculate indicators
        rsi = (
            self._calculate_rsi(close_prices)
            if cfg.rsi_enabled
            else pd.Series(50.0, index=close_prices.index)
        )
        atr = self._calculate_atr(high_prices, low_prices, close_prices)

        # Calculate HTF indicator if MTF enabled
        htf_indicator = None
        if cfg.mtf_enabled and htf_ohlcv is not None:
            htf_indicator = self._calculate_htf_indicator(
                htf_ohlcv["close"], cfg.mtf_filter_period, cfg.mtf_filter_type
            )

        # Warmup period
        warmup = (
            max(
                cfg.rsi_period,
                cfg.atr_period,
                cfg.mtf_filter_period if cfg.mtf_enabled else 0,
            )
            + 1
        )

        # Initialize signal arrays
        entries = pd.Series(False, index=ohlcv.index)
        exits = pd.Series(False, index=ohlcv.index)
        entry_sizes = pd.Series(0.0, index=ohlcv.index)

        # Multi-TP partial exit signals
        tp1_exits = (
            pd.Series(False, index=ohlcv.index) if cfg.tp_mode == TPMode.MULTI else None
        )
        tp2_exits = (
            pd.Series(False, index=ohlcv.index) if cfg.tp_mode == TPMode.MULTI else None
        )
        tp3_exits = (
            pd.Series(False, index=ohlcv.index) if cfg.tp_mode == TPMode.MULTI else None
        )
        tp4_exits = (
            pd.Series(False, index=ohlcv.index) if cfg.tp_mode == TPMode.MULTI else None
        )

        # Deal state
        deal = DCADealState()
        last_deal_bar = -cfg.cooldown_bars
        completed_deals = 0
        max_entries = 1 + cfg.max_safety_orders

        # Main loop
        for i in range(warmup, n):
            current_high = high_prices.iloc[i]
            current_low = low_prices.iloc[i]
            current_close = close_prices.iloc[i]
            current_atr = atr.iloc[i] if not np.isnan(atr.iloc[i]) else 0.0

            # Get HTF values for MTF filter
            htf_close = 0.0
            htf_ind_value = 0.0
            if cfg.mtf_enabled and htf_ohlcv is not None and htf_index_map is not None:
                htf_idx = htf_index_map[i] if i < len(htf_index_map) else -1
                if 0 <= htf_idx < len(htf_ohlcv):
                    htf_close = htf_ohlcv["close"].iloc[htf_idx]
                    if htf_indicator is not None and htf_idx < len(htf_indicator):
                        htf_ind_value = htf_indicator.iloc[htf_idx]

            # === EXIT LOGIC (check first) ===
            if deal.is_active():
                # Update MFE/MAE
                deal.update_mfe_mae(current_high, current_low, direction)

                # Check max holding time
                if cfg.max_bars_in_trade > 0:
                    bars_in_trade = i - deal.entry_bar
                    if bars_in_trade >= cfg.max_bars_in_trade:
                        exits.iloc[i] = True
                        deal.reset()
                        last_deal_bar = i
                        completed_deals += 1
                        continue

                # Check Stop Loss
                sl_hit = False
                if direction == "long":
                    sl_hit = current_low <= deal.sl_price
                else:
                    sl_hit = current_high >= deal.sl_price

                if sl_hit and deal.sl_price > 0:
                    exits.iloc[i] = True
                    deal.reset()
                    last_deal_bar = i
                    completed_deals += 1
                    continue

                # Check Trailing Stop
                if cfg.sl_mode == SLMode.TRAILING:
                    profit_pct = 0.0
                    if direction == "long":
                        profit_pct = (
                            current_high - deal.avg_entry_price
                        ) / deal.avg_entry_price
                    else:
                        profit_pct = (
                            deal.avg_entry_price - current_low
                        ) / deal.avg_entry_price

                    # Activate trailing
                    if profit_pct >= cfg.trailing_activation_pct / 100.0:
                        deal.trailing_active = True

                    if deal.trailing_active:
                        # Update peak
                        if direction == "long":
                            if current_high > deal.peak_price:
                                deal.peak_price = current_high
                                deal.trailing_sl_price = deal.peak_price * (
                                    1 - cfg.trailing_distance_pct / 100.0
                                )

                            if current_low <= deal.trailing_sl_price:
                                exits.iloc[i] = True
                                deal.reset()
                                last_deal_bar = i
                                completed_deals += 1
                                continue
                        else:
                            if deal.peak_price == 0 or current_low < deal.peak_price:
                                deal.peak_price = current_low
                                deal.trailing_sl_price = deal.peak_price * (
                                    1 + cfg.trailing_distance_pct / 100.0
                                )

                            if current_high >= deal.trailing_sl_price:
                                exits.iloc[i] = True
                                deal.reset()
                                last_deal_bar = i
                                completed_deals += 1
                                continue

                # Check Take Profit
                if cfg.tp_mode == TPMode.MULTI and len(deal.tp_prices) > 0:
                    # Multi-TP: check each level
                    for tp_idx, tp_price in enumerate(deal.tp_prices):
                        if tp_idx < len(deal.tp_hit) and not deal.tp_hit[tp_idx]:
                            tp_hit = False
                            if direction == "long":
                                tp_hit = current_high >= tp_price
                            else:
                                tp_hit = current_low <= tp_price

                            if tp_hit:
                                deal.tp_hit[tp_idx] = True

                                # Record partial exit
                                if tp_idx == 0 and tp1_exits is not None:
                                    tp1_exits.iloc[i] = True
                                elif tp_idx == 1 and tp2_exits is not None:
                                    tp2_exits.iloc[i] = True
                                elif tp_idx == 2 and tp3_exits is not None:
                                    tp3_exits.iloc[i] = True
                                elif tp_idx == 3 and tp4_exits is not None:
                                    tp4_exits.iloc[i] = True

                                # Update remaining size
                                portion = (
                                    cfg.tp_portions[tp_idx]
                                    if tp_idx < len(cfg.tp_portions)
                                    else 0.25
                                )
                                deal.remaining_size -= deal.total_size * portion

                                # Activate breakeven after TP1
                                if tp_idx == 0 and cfg.breakeven_enabled:
                                    deal.breakeven_active = True
                                    offset = cfg.breakeven_offset_pct / 100.0
                                    if direction == "long":
                                        deal.sl_price = deal.avg_entry_price * (
                                            1 + offset
                                        )
                                    else:
                                        deal.sl_price = deal.avg_entry_price * (
                                            1 - offset
                                        )

                                # Check if all TPs hit
                                if all(deal.tp_hit):
                                    exits.iloc[i] = True
                                    deal.reset()
                                    last_deal_bar = i
                                    completed_deals += 1
                                    break
                else:
                    # Single TP (FIXED or ATR)
                    if len(deal.tp_prices) > 0:
                        tp_price = deal.tp_prices[0]
                        tp_hit = False
                        if direction == "long":
                            tp_hit = current_high >= tp_price
                        else:
                            tp_hit = current_low <= tp_price

                        if tp_hit:
                            exits.iloc[i] = True
                            deal.reset()
                            last_deal_bar = i
                            completed_deals += 1
                            continue

            # === ENTRY LOGIC ===
            cooldown_ok = (i - last_deal_bar) >= cfg.cooldown_bars
            max_deals_ok = cfg.max_deals == 0 or completed_deals < cfg.max_deals
            can_add = deal.get_entry_count() < max_entries

            if cooldown_ok and max_deals_ok and can_add:
                if not deal.is_active():
                    # BASE ORDER: check RSI and MTF filter
                    rsi_signal = False
                    if cfg.rsi_enabled:
                        if direction == "long":
                            rsi_signal = rsi.iloc[i] < cfg.rsi_oversold
                        else:
                            rsi_signal = rsi.iloc[i] > cfg.rsi_overbought
                    else:
                        rsi_signal = True  # No RSI filter

                    mtf_ok = self._check_mtf_filter(htf_close, htf_ind_value, direction)

                    if rsi_signal and mtf_ok:
                        # Execute base order
                        entries.iloc[i] = True
                        entry_sizes.iloc[i] = cfg.base_order_size_pct / 100.0

                        deal.add_entry(
                            current_close, cfg.base_order_size_pct / 100.0, i
                        )

                        # Calculate TP/SL prices
                        deal.tp_prices = self._calculate_tp_prices(
                            deal.avg_entry_price, current_atr, direction
                        )
                        deal.tp_hit = [False] * len(deal.tp_prices)
                        deal.sl_price = self._calculate_sl_price(
                            deal.avg_entry_price, current_atr, direction
                        )
                        deal.peak_price = (
                            current_high if direction == "long" else current_low
                        )

                else:
                    # SAFETY ORDER: check price deviation
                    so_index = deal.get_entry_count() - 1  # 0-indexed

                    if so_index < len(self.so_levels):
                        so_deviation = self.so_levels[so_index]

                        if direction == "long":
                            so_trigger_price = deal.base_entry_price * (
                                1 - so_deviation
                            )
                            so_triggered = current_low <= so_trigger_price
                        else:
                            so_trigger_price = deal.base_entry_price * (
                                1 + so_deviation
                            )
                            so_triggered = current_high >= so_trigger_price

                        if so_triggered:
                            entries.iloc[i] = True
                            entry_sizes.iloc[i] = self.so_volumes[so_index]

                            deal.add_entry(current_close, self.so_volumes[so_index], i)

                            # Recalculate TP/SL based on new average
                            deal.tp_prices = self._calculate_tp_prices(
                                deal.avg_entry_price, current_atr, direction
                            )
                            deal.tp_hit = [False] * len(deal.tp_prices)
                            if (
                                not deal.breakeven_active
                            ):  # Don't reset SL if breakeven active
                                deal.sl_price = self._calculate_sl_price(
                                    deal.avg_entry_price, current_atr, direction
                                )

        # Create result based on direction
        if direction == "long":
            return SignalResult(
                entries=entries,
                exits=exits,
                short_entries=pd.Series(False, index=ohlcv.index),
                short_exits=pd.Series(False, index=ohlcv.index),
                entry_sizes=entry_sizes,
                short_entry_sizes=None,
                tp1_exits=tp1_exits,
                tp2_exits=tp2_exits,
                tp3_exits=tp3_exits,
                tp4_exits=tp4_exits,
            )
        else:
            return SignalResult(
                entries=pd.Series(False, index=ohlcv.index),
                exits=pd.Series(False, index=ohlcv.index),
                short_entries=entries,
                short_exits=exits,
                entry_sizes=None,
                short_entry_sizes=entry_sizes,
                tp1_exits=tp1_exits,
                tp2_exits=tp2_exits,
                tp3_exits=tp3_exits,
                tp4_exits=tp4_exits,
            )

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        """Get default strategy parameters."""
        return DCAMultiTPConfig().to_dict()


# === FACTORY FUNCTIONS ===


def create_dca_long_multi_tp(
    max_safety_orders: int = 5,
    tp_levels_pct: tuple[float, ...] = (0.5, 1.0, 1.5, 2.5),
    mtf_enabled: bool = True,
    **kwargs,
) -> DCAMultiTPStrategy:
    """
    Create DCA Long strategy with Multi-TP.

    Example:
        strategy = create_dca_long_multi_tp(
            max_safety_orders=5,
            tp_levels_pct=(0.5, 1.0, 1.5, 2.5),
            mtf_enabled=True,
        )
    """
    config = DCAMultiTPConfig(
        direction=DCADirection.LONG,
        max_safety_orders=max_safety_orders,
        tp_mode=TPMode.MULTI,
        tp_levels_pct=tp_levels_pct,
        mtf_enabled=mtf_enabled,
        **{k: v for k, v in kwargs.items() if hasattr(DCAMultiTPConfig, k)},
    )
    return DCAMultiTPStrategy(config)


def create_dca_short_multi_tp(
    max_safety_orders: int = 5,
    tp_levels_pct: tuple[float, ...] = (0.5, 1.0, 1.5, 2.5),
    mtf_enabled: bool = True,
    **kwargs,
) -> DCAMultiTPStrategy:
    """
    Create DCA Short strategy with Multi-TP.
    """
    config = DCAMultiTPConfig(
        direction=DCADirection.SHORT,
        max_safety_orders=max_safety_orders,
        tp_mode=TPMode.MULTI,
        tp_levels_pct=tp_levels_pct,
        mtf_enabled=mtf_enabled,
        rsi_oversold=30.0,
        rsi_overbought=70.0,
        **{k: v for k, v in kwargs.items() if hasattr(DCAMultiTPConfig, k)},
    )
    return DCAMultiTPStrategy(config)


def create_dca_long_atr_tp_sl(
    max_safety_orders: int = 5,
    atr_tp_multiplier: float = 2.0,
    atr_sl_multiplier: float = 1.5,
    mtf_enabled: bool = True,
    **kwargs,
) -> DCAMultiTPStrategy:
    """
    Create DCA Long strategy with ATR-based TP/SL.
    """
    config = DCAMultiTPConfig(
        direction=DCADirection.LONG,
        max_safety_orders=max_safety_orders,
        tp_mode=TPMode.ATR,
        sl_mode=SLMode.ATR,
        atr_tp_multiplier=atr_tp_multiplier,
        atr_sl_multiplier=atr_sl_multiplier,
        mtf_enabled=mtf_enabled,
        **{k: v for k, v in kwargs.items() if hasattr(DCAMultiTPConfig, k)},
    )
    return DCAMultiTPStrategy(config)


def create_dca_short_atr_tp_sl(
    max_safety_orders: int = 5,
    atr_tp_multiplier: float = 2.0,
    atr_sl_multiplier: float = 1.5,
    mtf_enabled: bool = True,
    **kwargs,
) -> DCAMultiTPStrategy:
    """
    Create DCA Short strategy with ATR-based TP/SL.
    """
    config = DCAMultiTPConfig(
        direction=DCADirection.SHORT,
        max_safety_orders=max_safety_orders,
        tp_mode=TPMode.ATR,
        sl_mode=SLMode.ATR,
        atr_tp_multiplier=atr_tp_multiplier,
        atr_sl_multiplier=atr_sl_multiplier,
        mtf_enabled=mtf_enabled,
        **{k: v for k, v in kwargs.items() if hasattr(DCAMultiTPConfig, k)},
    )
    return DCAMultiTPStrategy(config)


# === STRATEGY REGISTRY ===
DCA_MULTI_TP_STRATEGIES = {
    "dca_long_multi_tp": create_dca_long_multi_tp,
    "dca_short_multi_tp": create_dca_short_multi_tp,
    "dca_long_atr": create_dca_long_atr_tp_sl,
    "dca_short_atr": create_dca_short_atr_tp_sl,
}
