"""
Realistic Market Simulation Module for Universal Math Engine v2.1.

This module provides realistic market simulation features:
1. RealisticBarSimulator - Tick-by-tick simulation within OHLCV bars
2. VolumeSlippageModel - Volume-based slippage calculation
3. DynamicFundingManager - Historical funding rate management
4. PartialFillSimulator - Partial order fill simulation
5. LiquidationEngine - Accurate Bybit liquidation simulation
6. MLStrategyInterface - Machine Learning strategy interface

Author: Universal Math Engine Team
Version: 2.1.0
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 1. REALISTIC BAR SIMULATOR
# =============================================================================


class BarPathType(Enum):
    """Type of price path within a bar."""

    RANDOM_WALK = "random_walk"
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    STOP_HUNT = "stop_hunt"


@dataclass
class BarSimulatorConfig:
    """Configuration for realistic bar simulation."""

    # Number of ticks to simulate within each bar
    ticks_per_bar: int = 100

    # Path generation type
    path_type: BarPathType = BarPathType.RANDOM_WALK

    # Volatility scaling factor
    volatility_scale: float = 1.0

    # Stop-hunt probability (0-1)
    stop_hunt_probability: float = 0.1

    # Stop-hunt depth (% beyond high/low)
    stop_hunt_depth: float = 0.002

    # Random seed for reproducibility
    seed: int | None = None


class RealisticBarSimulator:
    """
    Simulates realistic tick-by-tick price movements within OHLCV bars.

    This allows for more accurate stop-loss/take-profit triggering by
    generating a plausible price path between Open, High, Low, and Close.

    Features:
    - Random walk with drift
    - Stop-hunt simulation (price spikes to trigger stops)
    - Volatility-aware path generation
    - Multiple path types (trending, mean-reverting)
    """

    def __init__(self, config: BarSimulatorConfig | None = None):
        """Initialize the bar simulator."""
        self.config = config or BarSimulatorConfig()
        self.rng = np.random.default_rng(self.config.seed)

    def simulate_bar_path(
        self,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: float = 1.0,
    ) -> NDArray[np.float64]:
        """
        Generate a realistic price path within a single bar.

        Args:
            open_price: Bar open price
            high_price: Bar high price
            low_price: Bar low price
            close_price: Bar close price
            volume: Bar volume (affects path characteristics)

        Returns:
            Array of tick prices from open to close
        """
        n_ticks = self.config.ticks_per_bar
        path = np.zeros(n_ticks, dtype=np.float64)
        path[0] = open_price
        path[-1] = close_price

        # Determine if this bar has stop-hunt behavior
        has_stop_hunt = self.rng.random() < self.config.stop_hunt_probability

        if self.config.path_type == BarPathType.RANDOM_WALK:
            path = self._generate_random_walk_path(
                open_price, high_price, low_price, close_price, n_ticks, has_stop_hunt
            )
        elif self.config.path_type == BarPathType.TRENDING:
            path = self._generate_trending_path(
                open_price, high_price, low_price, close_price, n_ticks
            )
        elif self.config.path_type == BarPathType.MEAN_REVERTING:
            path = self._generate_mean_reverting_path(
                open_price, high_price, low_price, close_price, n_ticks
            )
        elif self.config.path_type == BarPathType.STOP_HUNT:
            path = self._generate_stop_hunt_path(
                open_price, high_price, low_price, close_price, n_ticks
            )

        return path

    def _generate_random_walk_path(
        self,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        n_ticks: int,
        has_stop_hunt: bool,
    ) -> NDArray[np.float64]:
        """Generate random walk path constrained by OHLC."""
        path = np.zeros(n_ticks, dtype=np.float64)
        path[0] = open_p

        # Calculate range and drift
        bar_range = high_p - low_p
        drift = (close_p - open_p) / n_ticks
        volatility = bar_range / np.sqrt(n_ticks) * self.config.volatility_scale

        # Determine when to hit high and low
        is_bullish = close_p > open_p

        if is_bullish:
            # Bullish: typically hit low first, then high
            low_tick = self.rng.integers(1, n_ticks // 2)
            high_tick = self.rng.integers(n_ticks // 2, n_ticks - 1)
        else:
            # Bearish: typically hit high first, then low
            high_tick = self.rng.integers(1, n_ticks // 2)
            low_tick = self.rng.integers(n_ticks // 2, n_ticks - 1)

        # Generate path with random walk
        for i in range(1, n_ticks):
            noise = self.rng.normal(0, volatility)
            path[i] = path[i - 1] + drift + noise

        # Force path to hit high and low at designated ticks
        path[high_tick] = high_p
        path[low_tick] = low_p
        path[-1] = close_p

        # Apply stop-hunt spikes if enabled
        if has_stop_hunt:
            hunt_depth = bar_range * self.config.stop_hunt_depth
            # Spike above high
            spike_tick = self.rng.integers(1, n_ticks - 1)
            path[spike_tick] = max(path[spike_tick], high_p + hunt_depth)
            # Or spike below low
            if self.rng.random() > 0.5:
                path[spike_tick] = min(path[spike_tick], low_p - hunt_depth)

        # Clip to high/low bounds (except stop-hunt)
        if not has_stop_hunt:
            path = np.clip(path, low_p, high_p)

        return path

    def _generate_trending_path(
        self,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        n_ticks: int,
    ) -> NDArray[np.float64]:
        """Generate a trending path (mostly monotonic)."""
        # Linear interpolation with small noise
        t = np.linspace(0, 1, n_ticks)
        path = open_p + (close_p - open_p) * t

        # Add small noise
        noise = self.rng.normal(0, (high_p - low_p) * 0.1, n_ticks)
        path += noise

        # Ensure high/low are touched
        path[np.argmax(path)] = high_p
        path[np.argmin(path)] = low_p
        path[0] = open_p
        path[-1] = close_p

        return np.clip(path, low_p, high_p)

    def _generate_mean_reverting_path(
        self,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        n_ticks: int,
    ) -> NDArray[np.float64]:
        """Generate a mean-reverting path (oscillating)."""
        mid = (high_p + low_p) / 2
        path = np.zeros(n_ticks, dtype=np.float64)
        path[0] = open_p

        theta = 0.5  # Mean reversion speed
        sigma = (high_p - low_p) / 4

        for i in range(1, n_ticks):
            path[i] = path[i - 1] + theta * (mid - path[i - 1]) / n_ticks
            path[i] += self.rng.normal(0, sigma / np.sqrt(n_ticks))

        path[-1] = close_p

        # Scale to ensure high/low are hit
        current_max = np.max(path)
        current_min = np.min(path)
        if current_max != current_min:
            path = low_p + (path - current_min) * (high_p - low_p) / (
                current_max - current_min
            )

        path[0] = open_p
        path[-1] = close_p

        return path

    def _generate_stop_hunt_path(
        self,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        n_ticks: int,
    ) -> NDArray[np.float64]:
        """Generate path with deliberate stop-hunt behavior."""
        path = self._generate_random_walk_path(
            open_p, high_p, low_p, close_p, n_ticks, has_stop_hunt=True
        )

        # Add extra spikes at common stop levels
        hunt_depth = (high_p - low_p) * self.config.stop_hunt_depth * 2

        # Spike above high (hunting long stops)
        spike_above = self.rng.integers(n_ticks // 4, n_ticks // 2)
        path[spike_above] = high_p + hunt_depth

        # Spike below low (hunting short stops)
        spike_below = self.rng.integers(n_ticks // 2, 3 * n_ticks // 4)
        path[spike_below] = low_p - hunt_depth

        path[-1] = close_p

        return path

    def check_stop_triggered(
        self,
        path: NDArray[np.float64],
        stop_price: float,
        is_long: bool,
    ) -> tuple[bool, int, float]:
        """
        Check if a stop-loss would be triggered along the price path.

        Args:
            path: Simulated price path
            stop_price: Stop-loss price level
            is_long: True for long position, False for short

        Returns:
            Tuple of (triggered, tick_index, execution_price)
        """
        if is_long:
            # Long stop triggers when price goes below stop
            trigger_mask = path <= stop_price
        else:
            # Short stop triggers when price goes above stop
            trigger_mask = path >= stop_price

        if np.any(trigger_mask):
            trigger_idx = np.argmax(trigger_mask)
            # Execution price with small slippage
            slippage = abs(path[trigger_idx] - stop_price) * 0.1
            if is_long:
                exec_price = stop_price - slippage
            else:
                exec_price = stop_price + slippage
            return True, int(trigger_idx), exec_price

        return False, -1, 0.0


# =============================================================================
# 2. VOLUME-BASED SLIPPAGE MODEL
# =============================================================================


@dataclass
class VolumeSlippageConfig:
    """Configuration for volume-based slippage."""

    # Base slippage as percentage (0.0001 = 0.01%)
    base_slippage: float = 0.0001

    # Volume impact exponent (0.5 = square root, 1.0 = linear)
    volume_exponent: float = 0.5

    # Maximum slippage cap
    max_slippage: float = 0.01  # 1%

    # Minimum slippage floor
    min_slippage: float = 0.00005  # 0.005%

    # Volatility multiplier (higher volatility = more slippage)
    volatility_multiplier: float = 1.0


class VolumeSlippageModel:
    """
    Calculates realistic slippage based on order size relative to volume.

    Formula: slippage = base * (order_size / bar_volume) ^ exponent * volatility_factor

    Features:
    - Order size impact (larger orders = more slippage)
    - Volume-based scaling (low volume = more slippage)
    - Volatility adjustment
    - Configurable bounds
    """

    def __init__(self, config: VolumeSlippageConfig | None = None):
        """Initialize the volume slippage model."""
        self.config = config or VolumeSlippageConfig()

    def calculate_slippage(
        self,
        order_size_usd: float,
        bar_volume_usd: float,
        volatility: float = 0.0,
        is_aggressive: bool = True,
    ) -> float:
        """
        Calculate slippage percentage for an order.

        Args:
            order_size_usd: Order size in USD
            bar_volume_usd: Bar volume in USD
            volatility: Current volatility (ATR/price ratio)
            is_aggressive: True for market orders (more slippage)

        Returns:
            Slippage as a decimal (0.001 = 0.1%)
        """
        if bar_volume_usd <= 0:
            return self.config.max_slippage

        # Base impact from order size
        size_ratio = order_size_usd / bar_volume_usd
        size_impact = size_ratio**self.config.volume_exponent

        # Volatility adjustment
        vol_factor = 1.0 + volatility * self.config.volatility_multiplier

        # Aggressive order multiplier
        aggression_factor = 1.5 if is_aggressive else 1.0

        # Calculate total slippage
        slippage = (
            self.config.base_slippage * size_impact * vol_factor * aggression_factor
        )

        # Apply bounds
        slippage = np.clip(slippage, self.config.min_slippage, self.config.max_slippage)

        return float(slippage)

    def apply_slippage(
        self,
        price: float,
        order_size_usd: float,
        bar_volume_usd: float,
        is_buy: bool,
        volatility: float = 0.0,
    ) -> float:
        """
        Apply slippage to get execution price.

        Args:
            price: Intended price
            order_size_usd: Order size in USD
            bar_volume_usd: Bar volume in USD
            is_buy: True for buy orders
            volatility: Current volatility

        Returns:
            Execution price after slippage
        """
        slippage = self.calculate_slippage(order_size_usd, bar_volume_usd, volatility)

        if is_buy:
            return price * (1 + slippage)
        else:
            return price * (1 - slippage)

    def estimate_market_impact(
        self,
        order_size_usd: float,
        average_volume_usd: float,
        n_bars_to_execute: int = 1,
    ) -> dict[str, float]:
        """
        Estimate total market impact for a large order.

        Args:
            order_size_usd: Total order size
            average_volume_usd: Average bar volume
            n_bars_to_execute: Number of bars to split execution

        Returns:
            Dictionary with impact metrics
        """
        # Single execution impact
        single_slippage = self.calculate_slippage(order_size_usd, average_volume_usd)

        # Split execution impact (TWAP-style)
        chunk_size = order_size_usd / n_bars_to_execute
        chunk_slippages = [
            self.calculate_slippage(chunk_size, average_volume_usd)
            for _ in range(n_bars_to_execute)
        ]
        split_slippage = np.mean(chunk_slippages)

        return {
            "single_execution_slippage": single_slippage,
            "split_execution_slippage": split_slippage,
            "savings_from_split": single_slippage - split_slippage,
            "recommended_chunks": max(
                1, int(order_size_usd / (average_volume_usd * 0.01))
            ),
        }


# =============================================================================
# 3. DYNAMIC FUNDING MANAGER
# =============================================================================


@dataclass
class FundingRateEntry:
    """Single funding rate entry."""

    timestamp: int  # Unix timestamp in milliseconds
    funding_rate: float  # Funding rate as decimal
    mark_price: float  # Mark price at funding time


@dataclass
class DynamicFundingConfig:
    """Configuration for dynamic funding management."""

    # Default funding rate if no data available
    default_rate: float = 0.0001  # 0.01%

    # Funding interval in hours
    funding_interval_hours: int = 8

    # Enable interpolation between funding times
    enable_interpolation: bool = True

    # Cap on extreme funding rates
    max_funding_rate: float = 0.01  # 1%
    min_funding_rate: float = -0.01  # -1%


class DynamicFundingManager:
    """
    Manages historical funding rates for accurate backtesting.

    Features:
    - Load historical funding rates
    - Interpolate between 8-hour intervals
    - Calculate funding costs for positions
    - Support for multiple symbols
    """

    def __init__(self, config: DynamicFundingConfig | None = None):
        """Initialize the funding manager."""
        self.config = config or DynamicFundingConfig()
        self.funding_history: dict[str, list[FundingRateEntry]] = {}
        self._funding_arrays: dict[str, tuple[NDArray, NDArray]] = {}

    def load_funding_rates(
        self,
        symbol: str,
        rates: list[dict[str, Any]],
    ) -> None:
        """
        Load historical funding rates for a symbol.

        Args:
            symbol: Trading pair symbol
            rates: List of dicts with 'timestamp', 'funding_rate', 'mark_price'
        """
        entries = []
        for r in rates:
            entries.append(
                FundingRateEntry(
                    timestamp=int(r["timestamp"]),
                    funding_rate=float(r["funding_rate"]),
                    mark_price=float(r.get("mark_price", 0)),
                )
            )

        # Sort by timestamp
        entries.sort(key=lambda x: x.timestamp)
        self.funding_history[symbol] = entries

        # Create numpy arrays for fast lookup
        timestamps = np.array([e.timestamp for e in entries], dtype=np.int64)
        rates_arr = np.array([e.funding_rate for e in entries], dtype=np.float64)
        self._funding_arrays[symbol] = (timestamps, rates_arr)

    def get_funding_rate(
        self,
        symbol: str,
        timestamp: int,
    ) -> float:
        """
        Get funding rate at a specific timestamp.

        Args:
            symbol: Trading pair symbol
            timestamp: Unix timestamp in milliseconds

        Returns:
            Funding rate as decimal
        """
        if symbol not in self._funding_arrays:
            return self.config.default_rate

        timestamps, rates = self._funding_arrays[symbol]

        if len(timestamps) == 0:
            return self.config.default_rate

        # Find the applicable funding rate
        idx = np.searchsorted(timestamps, timestamp, side="right") - 1

        if idx < 0:
            return rates[0]
        elif idx >= len(rates):
            return rates[-1]

        rate = rates[idx]

        # Interpolate if enabled
        if self.config.enable_interpolation and idx < len(rates) - 1:
            next_ts = timestamps[idx + 1]
            curr_ts = timestamps[idx]
            if next_ts > curr_ts:
                progress = (timestamp - curr_ts) / (next_ts - curr_ts)
                rate = rate + (rates[idx + 1] - rate) * progress

        # Apply bounds
        rate = np.clip(rate, self.config.min_funding_rate, self.config.max_funding_rate)

        return float(rate)

    def calculate_funding_cost(
        self,
        symbol: str,
        position_size: float,
        entry_timestamp: int,
        exit_timestamp: int,
        is_long: bool,
    ) -> float:
        """
        Calculate total funding cost for a position.

        Args:
            symbol: Trading pair
            position_size: Position size in base currency
            entry_timestamp: Entry time (ms)
            exit_timestamp: Exit time (ms)
            is_long: True for long positions

        Returns:
            Total funding cost (negative = paid, positive = received)
        """
        interval_ms = self.config.funding_interval_hours * 3600 * 1000

        # Find all funding times in the position duration
        funding_times = []
        current = (entry_timestamp // interval_ms + 1) * interval_ms
        while current < exit_timestamp:
            funding_times.append(current)
            current += interval_ms

        if not funding_times:
            return 0.0

        total_cost = 0.0
        for ft in funding_times:
            rate = self.get_funding_rate(symbol, ft)
            # Long pays positive rate, short pays negative rate
            if is_long:
                cost = -position_size * rate  # Long pays when rate > 0
            else:
                cost = position_size * rate  # Short receives when rate > 0
            total_cost += cost

        return total_cost

    def get_funding_statistics(
        self,
        symbol: str,
        start_timestamp: int,
        end_timestamp: int,
    ) -> dict[str, float]:
        """
        Get funding rate statistics for a period.

        Args:
            symbol: Trading pair
            start_timestamp: Start time (ms)
            end_timestamp: End time (ms)

        Returns:
            Dictionary with funding statistics
        """
        if symbol not in self._funding_arrays:
            return {
                "mean_rate": self.config.default_rate,
                "std_rate": 0.0,
                "min_rate": self.config.default_rate,
                "max_rate": self.config.default_rate,
                "n_fundings": 0,
            }

        timestamps, rates = self._funding_arrays[symbol]

        # Filter to period
        mask = (timestamps >= start_timestamp) & (timestamps <= end_timestamp)
        period_rates = rates[mask]

        if len(period_rates) == 0:
            return {
                "mean_rate": self.config.default_rate,
                "std_rate": 0.0,
                "min_rate": self.config.default_rate,
                "max_rate": self.config.default_rate,
                "n_fundings": 0,
            }

        return {
            "mean_rate": float(np.mean(period_rates)),
            "std_rate": float(np.std(period_rates)),
            "min_rate": float(np.min(period_rates)),
            "max_rate": float(np.max(period_rates)),
            "n_fundings": len(period_rates),
        }


# =============================================================================
# 4. PARTIAL FILLS SIMULATOR
# =============================================================================


@dataclass
class PartialFillConfig:
    """Configuration for partial fill simulation."""

    # Enable partial fills
    enabled: bool = True

    # Minimum fill ratio per tick (0.1 = at least 10% filled)
    min_fill_ratio: float = 0.1

    # Volume threshold for guaranteed full fill
    # If order < threshold * bar_volume, guaranteed full fill
    instant_fill_threshold: float = 0.01  # 1% of volume

    # Maximum number of partial fills
    max_partial_fills: int = 10

    # Price improvement probability for limit orders
    price_improvement_prob: float = 0.3


@dataclass
class FillResult:
    """Result of a fill attempt."""

    filled_size: float
    fill_price: float
    remaining_size: float
    is_complete: bool
    n_fills: int
    fill_prices: list[float] = field(default_factory=list)
    fill_sizes: list[float] = field(default_factory=list)


class PartialFillSimulator:
    """
    Simulates partial order fills based on market volume.

    Features:
    - Volume-based fill probability
    - Multiple partial fills for large orders
    - Price improvement for limit orders
    - Realistic fill distribution
    """

    def __init__(self, config: PartialFillConfig | None = None):
        """Initialize the partial fill simulator."""
        self.config = config or PartialFillConfig()
        self.rng = np.random.default_rng()

    def simulate_market_order_fill(
        self,
        order_size: float,
        bar_volume: float,
        current_price: float,
        is_buy: bool,
        volatility: float = 0.0,
    ) -> FillResult:
        """
        Simulate fill of a market order.

        Args:
            order_size: Order size
            bar_volume: Bar volume
            current_price: Current market price
            is_buy: True for buy orders
            volatility: Current volatility

        Returns:
            FillResult with fill details
        """
        if not self.config.enabled:
            return FillResult(
                filled_size=order_size,
                fill_price=current_price,
                remaining_size=0.0,
                is_complete=True,
                n_fills=1,
                fill_prices=[current_price],
                fill_sizes=[order_size],
            )

        # Check if order qualifies for instant fill
        if order_size < bar_volume * self.config.instant_fill_threshold:
            return FillResult(
                filled_size=order_size,
                fill_price=current_price,
                remaining_size=0.0,
                is_complete=True,
                n_fills=1,
                fill_prices=[current_price],
                fill_sizes=[order_size],
            )

        # Simulate partial fills
        remaining = order_size
        fill_prices = []
        fill_sizes = []
        current_fill_price = current_price

        for _ in range(self.config.max_partial_fills):
            if remaining <= 0:
                break

            # Determine fill size based on volume
            max_fill = min(remaining, bar_volume * 0.1)  # Max 10% of volume per fill
            min_fill = remaining * self.config.min_fill_ratio
            fill_size = self.rng.uniform(min_fill, max_fill)
            fill_size = min(fill_size, remaining)

            # Price impact from each fill
            impact = (fill_size / bar_volume) * 0.001 * (1 + volatility)
            if is_buy:
                current_fill_price *= 1 + impact
            else:
                current_fill_price *= 1 - impact

            fill_prices.append(current_fill_price)
            fill_sizes.append(fill_size)
            remaining -= fill_size

        total_filled = sum(fill_sizes)
        avg_price = (
            sum(p * s for p, s in zip(fill_prices, fill_sizes)) / total_filled
            if total_filled > 0
            else current_price
        )

        return FillResult(
            filled_size=total_filled,
            fill_price=avg_price,
            remaining_size=remaining,
            is_complete=remaining <= 0,
            n_fills=len(fill_prices),
            fill_prices=fill_prices,
            fill_sizes=fill_sizes,
        )

    def simulate_limit_order_fill(
        self,
        order_size: float,
        limit_price: float,
        bar_high: float,
        bar_low: float,
        bar_volume: float,
        is_buy: bool,
    ) -> FillResult:
        """
        Simulate fill of a limit order.

        Args:
            order_size: Order size
            limit_price: Limit price
            bar_high: Bar high price
            bar_low: Bar low price
            bar_volume: Bar volume
            is_buy: True for buy orders

        Returns:
            FillResult with fill details
        """
        # Check if limit price is reachable
        if is_buy:
            if limit_price < bar_low:
                # Limit price not reached
                return FillResult(
                    filled_size=0.0,
                    fill_price=0.0,
                    remaining_size=order_size,
                    is_complete=False,
                    n_fills=0,
                )
            fillable = limit_price >= bar_low
        else:
            if limit_price > bar_high:
                # Limit price not reached
                return FillResult(
                    filled_size=0.0,
                    fill_price=0.0,
                    remaining_size=order_size,
                    is_complete=False,
                    n_fills=0,
                )
            fillable = limit_price <= bar_high

        if not fillable:
            return FillResult(
                filled_size=0.0,
                fill_price=0.0,
                remaining_size=order_size,
                is_complete=False,
                n_fills=0,
            )

        # Calculate fill probability based on how deep into the bar
        bar_range = bar_high - bar_low
        if bar_range > 0:
            if is_buy:
                depth = (limit_price - bar_low) / bar_range
            else:
                depth = (bar_high - limit_price) / bar_range
            fill_prob = min(1.0, depth * 2)  # Higher prob if limit is more aggressive
        else:
            fill_prob = 1.0

        if self.rng.random() > fill_prob:
            return FillResult(
                filled_size=0.0,
                fill_price=0.0,
                remaining_size=order_size,
                is_complete=False,
                n_fills=0,
            )

        # Determine actual fill price (possible improvement)
        if self.rng.random() < self.config.price_improvement_prob:
            if is_buy:
                fill_price = self.rng.uniform(bar_low, limit_price)
            else:
                fill_price = self.rng.uniform(limit_price, bar_high)
        else:
            fill_price = limit_price

        # Simulate partial fill based on volume
        fill_ratio = min(1.0, bar_volume * 0.05 / order_size)
        filled_size = order_size * fill_ratio

        return FillResult(
            filled_size=filled_size,
            fill_price=fill_price,
            remaining_size=order_size - filled_size,
            is_complete=filled_size >= order_size,
            n_fills=1,
            fill_prices=[fill_price],
            fill_sizes=[filled_size],
        )


# =============================================================================
# 5. LIQUIDATION ENGINE
# =============================================================================


@dataclass
class LiquidationConfig:
    """Configuration for Bybit-style liquidation."""

    # Maintenance margin rate
    maintenance_margin_rate: float = 0.005  # 0.5%

    # Initial margin rate (1/leverage)
    # Will be calculated from leverage if not set
    initial_margin_rate: float | None = None

    # Taker fee rate for liquidation
    liquidation_fee_rate: float = 0.0006  # 0.06%

    # Enable partial liquidation
    enable_partial_liquidation: bool = True

    # Partial liquidation threshold (equity/initial_margin)
    partial_liquidation_threshold: float = 0.8


@dataclass
class LiquidationResult:
    """Result of liquidation check."""

    is_liquidated: bool
    liquidation_price: float
    bankruptcy_price: float
    margin_ratio: float
    unrealized_pnl: float
    available_margin: float
    is_partial: bool = False
    liquidated_size: float = 0.0


class LiquidationEngine:
    """
    Accurate Bybit perpetual futures liquidation simulation.

    Implements:
    - Liquidation price calculation
    - Bankruptcy price calculation
    - Margin ratio monitoring
    - Partial liquidation
    - ADL simulation (simplified)

    Bybit Formulas:
    - Long Liquidation Price = Entry Price * (1 - Initial Margin Rate + Maintenance Margin Rate)
    - Short Liquidation Price = Entry Price * (1 + Initial Margin Rate - Maintenance Margin Rate)
    """

    def __init__(self, config: LiquidationConfig | None = None):
        """Initialize the liquidation engine."""
        self.config = config or LiquidationConfig()

    def calculate_liquidation_price(
        self,
        entry_price: float,
        leverage: float,
        is_long: bool,
        position_size: float = 1.0,
        additional_margin: float = 0.0,
    ) -> tuple[float, float]:
        """
        Calculate liquidation and bankruptcy prices.

        Args:
            entry_price: Position entry price
            leverage: Position leverage
            is_long: True for long positions
            position_size: Position size (for additional margin calc)
            additional_margin: Extra margin added to position

        Returns:
            Tuple of (liquidation_price, bankruptcy_price)
        """
        imr = 1.0 / leverage  # Initial Margin Rate
        mmr = self.config.maintenance_margin_rate

        # Adjust for additional margin
        if additional_margin > 0:
            position_value = position_size * entry_price
            additional_margin_rate = additional_margin / position_value
            imr += additional_margin_rate

        if is_long:
            # Long position
            liq_price = entry_price * (1 - imr + mmr)
            # Bankruptcy = when equity = 0
            bankruptcy_price = entry_price * (1 - imr)
        else:
            # Short position
            liq_price = entry_price * (1 + imr - mmr)
            bankruptcy_price = entry_price * (1 + imr)

        return max(0, liq_price), max(0, bankruptcy_price)

    def check_liquidation(
        self,
        entry_price: float,
        current_price: float,
        leverage: float,
        is_long: bool,
        position_size: float,
        wallet_balance: float,
    ) -> LiquidationResult:
        """
        Check if position should be liquidated.

        Args:
            entry_price: Position entry price
            current_price: Current mark price
            leverage: Position leverage
            is_long: True for long positions
            position_size: Position size in base currency
            wallet_balance: Total wallet balance

        Returns:
            LiquidationResult with detailed info
        """
        liq_price, bankruptcy_price = self.calculate_liquidation_price(
            entry_price, leverage, is_long, position_size
        )

        # Calculate unrealized PnL
        if is_long:
            unrealized_pnl = position_size * (current_price - entry_price)
        else:
            unrealized_pnl = position_size * (entry_price - current_price)

        # Position value
        position_value = position_size * current_price

        # Initial margin
        initial_margin = position_value / leverage

        # Available margin
        available_margin = wallet_balance + unrealized_pnl - initial_margin

        # Maintenance margin required
        maintenance_margin = position_value * self.config.maintenance_margin_rate

        # Margin ratio
        equity = wallet_balance + unrealized_pnl
        margin_ratio = maintenance_margin / equity if equity > 0 else float("inf")

        # Check liquidation condition
        is_liquidated = False
        is_partial = False
        liquidated_size = 0.0

        if is_long:
            is_liquidated = current_price <= liq_price
        else:
            is_liquidated = current_price >= liq_price

        # Check for partial liquidation
        if not is_liquidated and self.config.enable_partial_liquidation:
            if margin_ratio > self.config.partial_liquidation_threshold:
                is_partial = True
                # Liquidate enough to restore margin
                target_margin_ratio = self.config.partial_liquidation_threshold * 0.8
                liquidated_size = position_size * (
                    1 - target_margin_ratio / margin_ratio
                )

        return LiquidationResult(
            is_liquidated=is_liquidated,
            liquidation_price=liq_price,
            bankruptcy_price=bankruptcy_price,
            margin_ratio=margin_ratio,
            unrealized_pnl=unrealized_pnl,
            available_margin=available_margin,
            is_partial=is_partial,
            liquidated_size=liquidated_size,
        )

    def calculate_liquidation_loss(
        self,
        entry_price: float,
        liquidation_price: float,
        position_size: float,
        is_long: bool,
    ) -> float:
        """
        Calculate the loss from liquidation.

        Args:
            entry_price: Position entry price
            liquidation_price: Liquidation execution price
            position_size: Position size
            is_long: True for long positions

        Returns:
            Total loss from liquidation
        """
        if is_long:
            pnl = position_size * (liquidation_price - entry_price)
        else:
            pnl = position_size * (entry_price - liquidation_price)

        # Add liquidation fee
        fee = position_size * liquidation_price * self.config.liquidation_fee_rate

        return pnl - fee


# =============================================================================
# 6. ML STRATEGY INTERFACE
# =============================================================================


class MLModelProtocol(Protocol):
    """Protocol for ML models to implement."""

    def predict(self, features: NDArray[np.float64]) -> NDArray[np.float64]:
        """Predict signals from features."""
        ...

    def fit(self, X: NDArray[np.float64], y: NDArray[np.float64]) -> None:
        """Fit the model (optional for inference-only)."""
        ...


@dataclass
class MLStrategyConfig:
    """Configuration for ML strategy interface."""

    # Feature columns to use
    feature_columns: list[str] = field(default_factory=list)

    # Lookback period for feature generation
    lookback_period: int = 20

    # Signal threshold for entry
    signal_threshold: float = 0.5

    # Enable feature scaling
    enable_scaling: bool = True

    # Scaling method ('standard', 'minmax', 'robust')
    scaling_method: str = "standard"


class FeatureEngineering:
    """
    Feature engineering utilities for ML strategies.

    Generates common technical features from OHLCV data.
    """

    @staticmethod
    def generate_features(
        close: NDArray[np.float64],
        high: NDArray[np.float64],
        low: NDArray[np.float64],
        volume: NDArray[np.float64],
        lookback: int = 20,
    ) -> dict[str, NDArray[np.float64]]:
        """
        Generate common ML features from OHLCV data.

        Args:
            close: Close prices
            high: High prices
            low: Low prices
            volume: Volume
            lookback: Lookback period

        Returns:
            Dictionary of feature arrays
        """
        n = len(close)
        features = {}

        # Returns
        features["return_1"] = np.zeros(n)
        features["return_1"][1:] = (close[1:] - close[:-1]) / close[:-1]

        # Rolling returns
        for period in [5, 10, 20]:
            feat_name = f"return_{period}"
            features[feat_name] = np.zeros(n)
            if n > period:
                features[feat_name][period:] = (
                    close[period:] - close[:-period]
                ) / close[:-period]

        # Volatility (rolling std of returns)
        features["volatility"] = np.zeros(n)
        if n > lookback:
            for i in range(lookback, n):
                features["volatility"][i] = np.std(
                    features["return_1"][i - lookback : i]
                )

        # RSI
        features["rsi"] = FeatureEngineering._calculate_rsi(close, 14)

        # Moving average ratios
        for period in [10, 20, 50]:
            feat_name = f"ma_ratio_{period}"
            features[feat_name] = np.zeros(n)
            if n > period:
                ma = np.convolve(close, np.ones(period) / period, mode="valid")
                features[feat_name][period - 1 :] = close[period - 1 :] / ma - 1

        # Volume features
        features["volume_ma_ratio"] = np.zeros(n)
        if n > lookback:
            vol_ma = np.convolve(volume, np.ones(lookback) / lookback, mode="valid")
            features["volume_ma_ratio"][lookback - 1 :] = (
                volume[lookback - 1 :] / (vol_ma + 1e-10) - 1
            )

        # Range features
        features["range_ratio"] = (high - low) / (close + 1e-10)

        # High-low position
        features["hl_position"] = np.zeros(n)
        hl_range = high - low
        mask = hl_range > 0
        features["hl_position"][mask] = (close[mask] - low[mask]) / hl_range[mask]

        return features

    @staticmethod
    def _calculate_rsi(
        close: NDArray[np.float64], period: int = 14
    ) -> NDArray[np.float64]:
        """Calculate RSI indicator."""
        n = len(close)
        rsi = np.full(n, 50.0)

        if n <= period:
            return rsi

        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)

        avg_gain = np.zeros(n - 1)
        avg_loss = np.zeros(n - 1)

        # Initial SMA
        avg_gain[period - 1] = np.mean(gain[:period])
        avg_loss[period - 1] = np.mean(loss[:period])

        # EMA-style smoothing (Wilder's smoothing)
        for i in range(period, n - 1):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period

        # Calculate RSI
        rsi_values = np.full(n - 1, 50.0)

        for i in range(period - 1, n - 1):
            if avg_loss[i] == 0:
                if avg_gain[i] > 0:
                    rsi_values[i] = 100.0  # All gains, no losses
                else:
                    rsi_values[i] = 50.0  # No movement
            else:
                rs = avg_gain[i] / avg_loss[i]
                rsi_values[i] = 100 - 100 / (1 + rs)

        rsi[1:] = rsi_values

        return rsi


class MLStrategyInterface:
    """
    Interface for integrating ML models into backtesting.

    Features:
    - Sklearn-compatible model interface
    - Automatic feature generation
    - Feature scaling
    - Signal generation from predictions
    """

    def __init__(
        self,
        model: Any | None = None,
        config: MLStrategyConfig | None = None,
    ):
        """
        Initialize ML strategy interface.

        Args:
            model: ML model with predict() method
            config: Strategy configuration
        """
        self.model = model
        self.config = config or MLStrategyConfig()
        self.scaler_params: dict[str, tuple[float, float]] | None = None
        self.feature_engineer = FeatureEngineering()

    def set_model(self, model: Any) -> None:
        """Set the ML model."""
        self.model = model

    def prepare_features(
        self,
        close: NDArray[np.float64],
        high: NDArray[np.float64],
        low: NDArray[np.float64],
        volume: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """
        Prepare feature matrix from OHLCV data.

        Args:
            close: Close prices
            high: High prices
            low: Low prices
            volume: Volume

        Returns:
            Feature matrix (n_samples, n_features)
        """
        features_dict = self.feature_engineer.generate_features(
            close, high, low, volume, self.config.lookback_period
        )

        # Select features
        if self.config.feature_columns:
            selected = [
                features_dict[col]
                for col in self.config.feature_columns
                if col in features_dict
            ]
        else:
            selected = list(features_dict.values())

        # Stack into matrix
        X = np.column_stack(selected)

        # Scale if enabled
        if self.config.enable_scaling:
            X = self._scale_features(X)

        return X

    def _scale_features(self, X: NDArray[np.float64]) -> NDArray[np.float64]:
        """Scale features using configured method."""
        if self.scaler_params is None:
            # Fit scaler
            self.scaler_params = {}
            for i in range(X.shape[1]):
                col = X[:, i]
                if self.config.scaling_method == "standard":
                    mean, std = np.mean(col), np.std(col)
                    self.scaler_params[i] = (mean, std if std > 0 else 1.0)
                elif self.config.scaling_method == "minmax":
                    min_val, max_val = np.min(col), np.max(col)
                    range_val = max_val - min_val if max_val > min_val else 1.0
                    self.scaler_params[i] = (min_val, range_val)
                else:  # robust
                    median = np.median(col)
                    iqr = np.percentile(col, 75) - np.percentile(col, 25)
                    self.scaler_params[i] = (median, iqr if iqr > 0 else 1.0)

        # Apply scaling
        X_scaled = X.copy()
        for i in range(X.shape[1]):
            param1, param2 = self.scaler_params[i]
            if self.config.scaling_method == "standard" or self.config.scaling_method == "minmax":
                X_scaled[:, i] = (X[:, i] - param1) / param2
            else:  # robust
                X_scaled[:, i] = (X[:, i] - param1) / param2

        return X_scaled

    def generate_signals(
        self,
        close: NDArray[np.float64],
        high: NDArray[np.float64],
        low: NDArray[np.float64],
        volume: NDArray[np.float64],
    ) -> NDArray[np.int8]:
        """
        Generate trading signals using the ML model.

        Args:
            close: Close prices
            high: High prices
            low: Low prices
            volume: Volume

        Returns:
            Signal array (1=long, -1=short, 0=neutral)
        """
        if self.model is None:
            raise ValueError("No model set. Use set_model() first.")

        # Prepare features
        X = self.prepare_features(close, high, low, volume)

        # Get predictions
        predictions = self.model.predict(X)

        # Convert to signals
        signals = np.zeros(len(close), dtype=np.int8)

        # Handle different prediction shapes
        if predictions.ndim == 1:
            # Binary or regression output
            signals[predictions > self.config.signal_threshold] = 1
            signals[predictions < -self.config.signal_threshold] = -1
        elif predictions.ndim == 2:
            # Multi-class output (assume [short_prob, neutral_prob, long_prob])
            if predictions.shape[1] == 3:
                signals[predictions[:, 2] > self.config.signal_threshold] = 1
                signals[predictions[:, 0] > self.config.signal_threshold] = -1
            elif predictions.shape[1] == 2:
                # Binary classification
                signals[predictions[:, 1] > self.config.signal_threshold] = 1

        return signals

    def create_labels(
        self,
        close: NDArray[np.float64],
        forward_period: int = 5,
        threshold: float = 0.01,
    ) -> NDArray[np.int8]:
        """
        Create training labels from price data.

        Args:
            close: Close prices
            forward_period: Forward-looking period
            threshold: Return threshold for labeling

        Returns:
            Label array (1=positive, -1=negative, 0=neutral)
        """
        n = len(close)
        labels = np.zeros(n, dtype=np.int8)

        if n <= forward_period:
            return labels

        # Forward returns
        forward_returns = np.zeros(n)
        forward_returns[:-forward_period] = (
            close[forward_period:] - close[:-forward_period]
        ) / close[:-forward_period]

        labels[forward_returns > threshold] = 1
        labels[forward_returns < -threshold] = -1

        return labels


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Bar Simulator
    "BarPathType",
    "BarSimulatorConfig",
    "RealisticBarSimulator",
    # Volume Slippage
    "VolumeSlippageConfig",
    "VolumeSlippageModel",
    # Dynamic Funding
    "FundingRateEntry",
    "DynamicFundingConfig",
    "DynamicFundingManager",
    # Partial Fills
    "PartialFillConfig",
    "FillResult",
    "PartialFillSimulator",
    # Liquidation
    "LiquidationConfig",
    "LiquidationResult",
    "LiquidationEngine",
    # ML Interface
    "MLModelProtocol",
    "MLStrategyConfig",
    "FeatureEngineering",
    "MLStrategyInterface",
]
