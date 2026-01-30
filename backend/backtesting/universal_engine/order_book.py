"""
Order Book Simulation Module for Universal Math Engine v2.3.

This module provides realistic order book simulation:
1. OrderBookSimulator - Full L2 order book with bid/ask levels
2. MarketDepthAnalyzer - Liquidity analysis and depth metrics
3. MarketImpactCalculator - Price impact from large orders
4. LiquidationCascadeSimulator - Cascading liquidation simulation
5. OrderFlowAnalyzer - Order flow imbalance and toxicity

Author: Universal Math Engine Team
Version: 2.3.0
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 1. ORDER BOOK SIMULATOR
# =============================================================================


class OrderBookSide(Enum):
    """Side of the order book."""

    BID = "bid"
    ASK = "ask"


@dataclass
class OrderBookLevel:
    """Single price level in the order book."""

    price: float
    size: float  # Total size at this level
    order_count: int = 1  # Number of orders at this level


@dataclass
class OrderBookSnapshot:
    """Complete order book snapshot."""

    timestamp: int
    bids: list[OrderBookLevel]  # Sorted descending by price
    asks: list[OrderBookLevel]  # Sorted ascending by price

    @property
    def best_bid(self) -> Optional[float]:
        """Get best bid price."""
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        """Get best ask price."""
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        """Get mid price."""
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread(self) -> Optional[float]:
        """Get bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    @property
    def spread_bps(self) -> Optional[float]:
        """Get spread in basis points."""
        if self.spread and self.mid_price:
            return (self.spread / self.mid_price) * 10000
        return None


@dataclass
class OrderBookConfig:
    """Configuration for order book simulation."""

    # Number of price levels to maintain
    depth_levels: int = 50

    # Tick size (minimum price increment)
    tick_size: float = 0.01

    # Base liquidity per level (will be randomized)
    base_liquidity: float = 10.0

    # Liquidity decay factor (deeper levels have less liquidity)
    liquidity_decay: float = 0.95

    # Spread volatility factor
    spread_volatility: float = 0.1

    # Enable order book imbalance effects
    enable_imbalance: bool = True

    # Random seed for reproducibility
    seed: Optional[int] = None


class OrderBookSimulator:
    """
    Simulates a realistic L2 order book.

    Features:
    - Dynamic bid/ask levels with realistic liquidity distribution
    - Order book updates based on price movements
    - Market order execution with price impact
    - Limit order placement and fills
    - Order book imbalance calculation
    """

    def __init__(self, config: Optional[OrderBookConfig] = None):
        """Initialize order book simulator."""
        self.config = config or OrderBookConfig()
        self.rng = np.random.default_rng(self.config.seed)

        self.bids: list[OrderBookLevel] = []
        self.asks: list[OrderBookLevel] = []
        self.last_mid_price: float = 0.0
        self.timestamp: int = 0

    def initialize(self, mid_price: float, timestamp: int = 0) -> OrderBookSnapshot:
        """
        Initialize order book around a mid price.

        Args:
            mid_price: Initial mid price
            timestamp: Initial timestamp

        Returns:
            Initial order book snapshot
        """
        self.last_mid_price = mid_price
        self.timestamp = timestamp

        # Generate bid levels (descending from mid)
        self.bids = []
        price = mid_price - self.config.tick_size
        for i in range(self.config.depth_levels):
            liquidity = self.config.base_liquidity * (self.config.liquidity_decay**i)
            # Add randomness
            liquidity *= self.rng.uniform(0.5, 1.5)
            self.bids.append(
                OrderBookLevel(
                    price=round(price, 8),
                    size=liquidity,
                    order_count=max(1, int(liquidity / 2)),
                )
            )
            price -= self.config.tick_size

        # Generate ask levels (ascending from mid)
        self.asks = []
        price = mid_price + self.config.tick_size
        for i in range(self.config.depth_levels):
            liquidity = self.config.base_liquidity * (self.config.liquidity_decay**i)
            liquidity *= self.rng.uniform(0.5, 1.5)
            self.asks.append(
                OrderBookLevel(
                    price=round(price, 8),
                    size=liquidity,
                    order_count=max(1, int(liquidity / 2)),
                )
            )
            price += self.config.tick_size

        return self.get_snapshot()

    def update(
        self,
        new_mid_price: float,
        timestamp: int,
        volatility: float = 0.0,
    ) -> OrderBookSnapshot:
        """
        Update order book based on new mid price.

        Args:
            new_mid_price: New mid price
            timestamp: New timestamp
            volatility: Current volatility (affects spread)

        Returns:
            Updated order book snapshot
        """
        self.timestamp = timestamp
        price_change = new_mid_price - self.last_mid_price
        self.last_mid_price = new_mid_price

        # Adjust spread based on volatility
        spread_adjustment = 1 + volatility * self.config.spread_volatility * 10

        # Shift bid levels
        new_bids = []
        price = new_mid_price - self.config.tick_size * spread_adjustment
        for i in range(self.config.depth_levels):
            # Reuse existing liquidity with some randomization
            if i < len(self.bids):
                old_size = self.bids[i].size
                # Liquidity changes based on price movement direction
                if price_change > 0:  # Price up, bids get filled
                    new_size = old_size * self.rng.uniform(0.8, 1.0)
                else:  # Price down, more bids appear
                    new_size = old_size * self.rng.uniform(1.0, 1.2)
            else:
                new_size = self.config.base_liquidity * (self.config.liquidity_decay**i)

            new_bids.append(
                OrderBookLevel(
                    price=round(price, 8),
                    size=new_size,
                    order_count=max(1, int(new_size / 2)),
                )
            )
            price -= self.config.tick_size

        # Shift ask levels
        new_asks = []
        price = new_mid_price + self.config.tick_size * spread_adjustment
        for i in range(self.config.depth_levels):
            if i < len(self.asks):
                old_size = self.asks[i].size
                if price_change < 0:  # Price down, asks get filled
                    new_size = old_size * self.rng.uniform(0.8, 1.0)
                else:  # Price up, more asks appear
                    new_size = old_size * self.rng.uniform(1.0, 1.2)
            else:
                new_size = self.config.base_liquidity * (self.config.liquidity_decay**i)

            new_asks.append(
                OrderBookLevel(
                    price=round(price, 8),
                    size=new_size,
                    order_count=max(1, int(new_size / 2)),
                )
            )
            price += self.config.tick_size

        self.bids = new_bids
        self.asks = new_asks

        return self.get_snapshot()

    def execute_market_order(
        self,
        side: OrderBookSide,
        size: float,
    ) -> tuple[float, float, list[tuple[float, float]]]:
        """
        Execute a market order against the order book.

        Args:
            side: BID (buy) or ASK (sell)
            size: Order size

        Returns:
            Tuple of (average_price, total_cost, fills)
            where fills = [(price, size), ...]
        """
        remaining = size
        fills: list[tuple[float, float]] = []
        total_cost = 0.0

        if side == OrderBookSide.BID:
            # Buy order - consume asks
            levels = self.asks
        else:
            # Sell order - consume bids
            levels = self.bids

        i = 0
        while remaining > 0 and i < len(levels):
            level = levels[i]
            fill_size = min(remaining, level.size)
            fill_price = level.price

            fills.append((fill_price, fill_size))
            total_cost += fill_price * fill_size
            remaining -= fill_size

            # Update level
            level.size -= fill_size
            if level.size <= 0:
                i += 1

            if remaining <= 0:
                break

        # Remove depleted levels
        if side == OrderBookSide.BID:
            self.asks = [l for l in self.asks if l.size > 0]
        else:
            self.bids = [l for l in self.bids if l.size > 0]

        filled_size = size - remaining
        avg_price = total_cost / filled_size if filled_size > 0 else 0

        return avg_price, total_cost, fills

    def get_snapshot(self) -> OrderBookSnapshot:
        """Get current order book snapshot."""
        return OrderBookSnapshot(
            timestamp=self.timestamp,
            bids=self.bids.copy(),
            asks=self.asks.copy(),
        )

    def get_depth_at_price(self, price: float, side: OrderBookSide) -> float:
        """Get total liquidity available up to a price level."""
        total = 0.0
        levels = self.bids if side == OrderBookSide.BID else self.asks

        for level in levels:
            if side == OrderBookSide.BID:
                if level.price >= price:
                    total += level.size
            else:
                if level.price <= price:
                    total += level.size

        return total

    def get_vwap_for_size(self, size: float, side: OrderBookSide) -> float:
        """Calculate VWAP for executing a given size."""
        avg_price, _, _ = self.execute_market_order(side, size)
        # Restore order book (this was a simulation)
        self.update(self.last_mid_price, self.timestamp)
        return avg_price


# =============================================================================
# 2. MARKET DEPTH ANALYZER
# =============================================================================


@dataclass
class DepthMetrics:
    """Metrics from order book depth analysis."""

    # Basic metrics
    bid_depth_total: float = 0.0
    ask_depth_total: float = 0.0
    depth_ratio: float = 1.0  # bid/ask ratio

    # Imbalance metrics
    imbalance: float = 0.0  # (bid - ask) / (bid + ask)
    imbalance_5_levels: float = 0.0
    imbalance_10_levels: float = 0.0

    # Liquidity metrics
    liquidity_score: float = 0.0  # 0-100
    bid_wall_price: Optional[float] = None
    ask_wall_price: Optional[float] = None

    # Spread metrics
    spread_bps: float = 0.0
    effective_spread_bps: float = 0.0

    # Depth at key levels
    depth_1_pct: float = 0.0  # Liquidity within 1% of mid
    depth_2_pct: float = 0.0  # Liquidity within 2% of mid


class MarketDepthAnalyzer:
    """
    Analyzes order book depth and liquidity.

    Features:
    - Depth metrics calculation
    - Order book imbalance detection
    - Liquidity wall detection
    - Support/resistance from order book
    """

    def __init__(self, wall_threshold: float = 3.0):
        """
        Initialize depth analyzer.

        Args:
            wall_threshold: Multiplier for detecting walls (3x avg = wall)
        """
        self.wall_threshold = wall_threshold

    def analyze(self, snapshot: OrderBookSnapshot) -> DepthMetrics:
        """
        Analyze order book snapshot.

        Args:
            snapshot: Order book snapshot

        Returns:
            DepthMetrics with analysis results
        """
        if not snapshot.bids or not snapshot.asks:
            return DepthMetrics()

        mid_price = snapshot.mid_price or 0

        # Calculate total depths
        bid_depth = sum(l.size for l in snapshot.bids)
        ask_depth = sum(l.size for l in snapshot.asks)

        # Depth ratio
        depth_ratio = bid_depth / ask_depth if ask_depth > 0 else 1.0

        # Imbalance
        total_depth = bid_depth + ask_depth
        imbalance = (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0

        # Imbalance at different depths
        bid_5 = sum(l.size for l in snapshot.bids[:5])
        ask_5 = sum(l.size for l in snapshot.asks[:5])
        imbalance_5 = (bid_5 - ask_5) / (bid_5 + ask_5) if (bid_5 + ask_5) > 0 else 0

        bid_10 = sum(l.size for l in snapshot.bids[:10])
        ask_10 = sum(l.size for l in snapshot.asks[:10])
        imbalance_10 = (
            (bid_10 - ask_10) / (bid_10 + ask_10) if (bid_10 + ask_10) > 0 else 0
        )

        # Detect walls
        avg_bid_size = bid_depth / len(snapshot.bids) if snapshot.bids else 0
        avg_ask_size = ask_depth / len(snapshot.asks) if snapshot.asks else 0

        bid_wall_price = None
        for level in snapshot.bids:
            if level.size > avg_bid_size * self.wall_threshold:
                bid_wall_price = level.price
                break

        ask_wall_price = None
        for level in snapshot.asks:
            if level.size > avg_ask_size * self.wall_threshold:
                ask_wall_price = level.price
                break

        # Liquidity score (0-100)
        # Based on depth, spread, and distribution
        spread_score = max(0, 100 - (snapshot.spread_bps or 0) * 10)
        depth_score = min(100, total_depth / 100)
        liquidity_score = (spread_score + depth_score) / 2

        # Depth at percentage levels
        if mid_price > 0:
            depth_1_pct = self._depth_within_pct(snapshot, mid_price, 0.01)
            depth_2_pct = self._depth_within_pct(snapshot, mid_price, 0.02)
        else:
            depth_1_pct = 0
            depth_2_pct = 0

        # Effective spread (considering depth)
        if mid_price > 0 and snapshot.bids and snapshot.asks:
            # VWAP for small order
            small_size = min(bid_depth, ask_depth) * 0.01  # 1% of depth
            if small_size > 0:
                buy_vwap = self._calculate_vwap(snapshot.asks, small_size)
                sell_vwap = self._calculate_vwap(snapshot.bids, small_size)
                effective_spread = (buy_vwap - sell_vwap) / mid_price * 10000
            else:
                effective_spread = snapshot.spread_bps or 0
        else:
            effective_spread = snapshot.spread_bps or 0

        return DepthMetrics(
            bid_depth_total=bid_depth,
            ask_depth_total=ask_depth,
            depth_ratio=depth_ratio,
            imbalance=imbalance,
            imbalance_5_levels=imbalance_5,
            imbalance_10_levels=imbalance_10,
            liquidity_score=liquidity_score,
            bid_wall_price=bid_wall_price,
            ask_wall_price=ask_wall_price,
            spread_bps=snapshot.spread_bps or 0,
            effective_spread_bps=effective_spread,
            depth_1_pct=depth_1_pct,
            depth_2_pct=depth_2_pct,
        )

    def _depth_within_pct(
        self, snapshot: OrderBookSnapshot, mid_price: float, pct: float
    ) -> float:
        """Calculate total depth within percentage of mid price."""
        lower = mid_price * (1 - pct)
        upper = mid_price * (1 + pct)

        total = 0.0
        for level in snapshot.bids:
            if level.price >= lower:
                total += level.size
        for level in snapshot.asks:
            if level.price <= upper:
                total += level.size

        return total

    def _calculate_vwap(self, levels: list[OrderBookLevel], size: float) -> float:
        """Calculate VWAP for a given size."""
        remaining = size
        total_cost = 0.0

        for level in levels:
            fill = min(remaining, level.size)
            total_cost += fill * level.price
            remaining -= fill
            if remaining <= 0:
                break

        filled = size - remaining
        return total_cost / filled if filled > 0 else 0


# =============================================================================
# 3. MARKET IMPACT CALCULATOR
# =============================================================================


@dataclass
class MarketImpactConfig:
    """Configuration for market impact calculation."""

    # Permanent impact coefficient
    permanent_impact_coef: float = 0.1

    # Temporary impact coefficient
    temporary_impact_coef: float = 0.5

    # Price decay rate (how fast temporary impact fades)
    decay_rate: float = 0.1

    # Volume exponent (0.5 = square root, 1.0 = linear)
    volume_exponent: float = 0.5

    # Volatility multiplier
    volatility_multiplier: float = 1.0


@dataclass
class MarketImpactResult:
    """Result of market impact calculation."""

    # Total impact in price units
    total_impact: float = 0.0

    # Permanent price impact
    permanent_impact: float = 0.0

    # Temporary price impact
    temporary_impact: float = 0.0

    # Impact in basis points
    impact_bps: float = 0.0

    # Execution cost (slippage + impact)
    execution_cost: float = 0.0

    # Estimated execution price
    execution_price: float = 0.0

    # Optimal execution time (bars)
    optimal_execution_time: int = 1


class MarketImpactCalculator:
    """
    Calculates market impact of orders.

    Based on the Almgren-Chriss model with modifications for crypto markets.

    Features:
    - Permanent vs temporary impact separation
    - Volume-based impact scaling
    - Volatility adjustment
    - Optimal execution timing
    """

    def __init__(self, config: Optional[MarketImpactConfig] = None):
        """Initialize market impact calculator."""
        self.config = config or MarketImpactConfig()

    def calculate_impact(
        self,
        order_size: float,
        average_volume: float,
        current_price: float,
        volatility: float,
        is_buy: bool,
        time_horizon: int = 1,
    ) -> MarketImpactResult:
        """
        Calculate market impact of an order.

        Args:
            order_size: Order size (in base currency)
            average_volume: Average bar volume
            current_price: Current mid price
            volatility: Current volatility (e.g., ATR/price)
            is_buy: True for buy orders
            time_horizon: Execution time in bars

        Returns:
            MarketImpactResult with impact breakdown
        """
        if average_volume <= 0 or current_price <= 0:
            return MarketImpactResult()

        # Participation rate (order size / volume)
        participation = order_size / (average_volume * time_horizon)

        # Volatility adjustment
        vol_adj = 1 + volatility * self.config.volatility_multiplier

        # Permanent impact: η * sign(Q) * |Q|^α * σ
        permanent = (
            self.config.permanent_impact_coef
            * (participation**self.config.volume_exponent)
            * vol_adj
        )

        # Temporary impact: γ * Q / T * σ
        temporary = (
            self.config.temporary_impact_coef * participation / time_horizon * vol_adj
        )

        # Total impact
        total_impact = permanent + temporary

        # Convert to price units
        impact_price = current_price * total_impact

        # Direction
        if not is_buy:
            impact_price = -impact_price

        # Execution price
        execution_price = (
            current_price + impact_price
            if is_buy
            else current_price - abs(impact_price)
        )

        # Execution cost (value of impact)
        execution_cost = abs(impact_price) * order_size

        # Optimal execution time (minimize total cost)
        optimal_time = self._calculate_optimal_time(
            order_size, average_volume, volatility
        )

        return MarketImpactResult(
            total_impact=abs(total_impact),
            permanent_impact=permanent,
            temporary_impact=temporary,
            impact_bps=abs(total_impact) * 10000,
            execution_cost=execution_cost,
            execution_price=execution_price,
            optimal_execution_time=optimal_time,
        )

    def _calculate_optimal_time(
        self,
        order_size: float,
        average_volume: float,
        volatility: float,
    ) -> int:
        """Calculate optimal execution time to minimize total cost."""
        # Simple heuristic: larger orders need more time
        participation_ratio = order_size / average_volume

        if participation_ratio < 0.01:
            return 1  # Small order - execute immediately
        elif participation_ratio < 0.05:
            return 3
        elif participation_ratio < 0.1:
            return 5
        elif participation_ratio < 0.25:
            return 10
        else:
            return max(10, int(participation_ratio * 20))

    def calculate_twap_impact(
        self,
        order_size: float,
        average_volume: float,
        current_price: float,
        volatility: float,
        is_buy: bool,
        n_slices: int = 10,
    ) -> list[MarketImpactResult]:
        """
        Calculate impact for TWAP execution.

        Args:
            order_size: Total order size
            average_volume: Average bar volume
            current_price: Current price
            volatility: Current volatility
            is_buy: Buy or sell
            n_slices: Number of TWAP slices

        Returns:
            List of impact results for each slice
        """
        slice_size = order_size / n_slices
        results = []
        cumulative_permanent = 0.0

        for i in range(n_slices):
            result = self.calculate_impact(
                order_size=slice_size,
                average_volume=average_volume,
                current_price=current_price * (1 + cumulative_permanent),
                volatility=volatility,
                is_buy=is_buy,
                time_horizon=1,
            )
            results.append(result)
            cumulative_permanent += result.permanent_impact

        return results


# =============================================================================
# 4. LIQUIDATION CASCADE SIMULATOR
# =============================================================================


@dataclass
class LiquidationLevel:
    """Liquidation level in the market."""

    price: float
    total_size: float  # Total position size at this level
    leverage: float  # Average leverage
    n_positions: int  # Number of positions


@dataclass
class CascadeConfig:
    """Configuration for liquidation cascade simulation."""

    # Liquidation levels to track
    levels_per_side: int = 20

    # Price step between levels (as percentage)
    level_step: float = 0.005  # 0.5%

    # Average position size per level
    avg_position_size: float = 10000

    # Position size standard deviation
    position_size_std: float = 5000

    # Average leverage
    avg_leverage: float = 20

    # Cascade amplification factor
    cascade_factor: float = 1.5

    # Maximum cascade depth
    max_cascade_depth: int = 5


@dataclass
class CascadeResult:
    """Result of cascade simulation."""

    # Total liquidated volume
    total_liquidated: float = 0.0

    # Number of cascade waves
    cascade_waves: int = 0

    # Price movement from cascade
    price_impact: float = 0.0

    # Final price after cascade
    final_price: float = 0.0

    # Triggered levels
    triggered_levels: list[LiquidationLevel] = field(default_factory=list)

    # Was cascade stopped by support/resistance
    stopped_by_wall: bool = False


class LiquidationCascadeSimulator:
    """
    Simulates liquidation cascades in leveraged markets.

    Features:
    - Multi-level liquidation tracking
    - Cascade propagation simulation
    - Price impact from liquidations
    - Stop-loss hunting effects
    """

    def __init__(self, config: Optional[CascadeConfig] = None):
        """Initialize cascade simulator."""
        self.config = config or CascadeConfig()
        self.rng = np.random.default_rng()

        self.long_liquidations: list[LiquidationLevel] = []
        self.short_liquidations: list[LiquidationLevel] = []

    def initialize(self, current_price: float) -> None:
        """
        Initialize liquidation levels around current price.

        Args:
            current_price: Current market price
        """
        self.long_liquidations = []
        self.short_liquidations = []

        # Generate long liquidation levels (below current price)
        for i in range(1, self.config.levels_per_side + 1):
            price = current_price * (1 - i * self.config.level_step)
            size = max(
                100,
                self.rng.normal(
                    self.config.avg_position_size, self.config.position_size_std
                ),
            )
            leverage = max(2, self.rng.normal(self.config.avg_leverage, 5))
            n_positions = max(1, int(size / 1000))

            self.long_liquidations.append(
                LiquidationLevel(
                    price=price,
                    total_size=size,
                    leverage=leverage,
                    n_positions=n_positions,
                )
            )

        # Generate short liquidation levels (above current price)
        for i in range(1, self.config.levels_per_side + 1):
            price = current_price * (1 + i * self.config.level_step)
            size = max(
                100,
                self.rng.normal(
                    self.config.avg_position_size, self.config.position_size_std
                ),
            )
            leverage = max(2, self.rng.normal(self.config.avg_leverage, 5))
            n_positions = max(1, int(size / 1000))

            self.short_liquidations.append(
                LiquidationLevel(
                    price=price,
                    total_size=size,
                    leverage=leverage,
                    n_positions=n_positions,
                )
            )

    def simulate_cascade(
        self,
        trigger_price: float,
        is_downward: bool,
        order_book: Optional[OrderBookSimulator] = None,
    ) -> CascadeResult:
        """
        Simulate a liquidation cascade.

        Args:
            trigger_price: Price that triggers initial liquidations
            is_downward: True for downward cascade (long liquidations)
            order_book: Optional order book for liquidity absorption

        Returns:
            CascadeResult with cascade details
        """
        current_price = trigger_price
        total_liquidated = 0.0
        triggered_levels = []
        cascade_waves = 0

        levels = self.long_liquidations if is_downward else self.short_liquidations

        for _ in range(self.config.max_cascade_depth):
            wave_liquidations = 0.0
            wave_triggered = []

            # Find triggered levels
            for level in levels:
                if is_downward:
                    if current_price <= level.price and level.total_size > 0:
                        wave_liquidations += level.total_size
                        wave_triggered.append(level)
                else:
                    if current_price >= level.price and level.total_size > 0:
                        wave_liquidations += level.total_size
                        wave_triggered.append(level)

            if wave_liquidations == 0:
                break

            cascade_waves += 1
            total_liquidated += wave_liquidations
            triggered_levels.extend(wave_triggered)

            # Mark levels as liquidated
            for level in wave_triggered:
                level.total_size = 0

            # Calculate price impact from liquidations
            impact = wave_liquidations * 0.00001 * self.config.cascade_factor
            if is_downward:
                current_price *= 1 - impact
            else:
                current_price *= 1 + impact

            # Check if order book can absorb
            if order_book:
                depth = order_book.get_depth_at_price(
                    current_price,
                    OrderBookSide.BID if is_downward else OrderBookSide.ASK,
                )
                if depth > wave_liquidations * 2:
                    # Sufficient liquidity to stop cascade
                    break

        price_impact = (current_price - trigger_price) / trigger_price

        return CascadeResult(
            total_liquidated=total_liquidated,
            cascade_waves=cascade_waves,
            price_impact=price_impact,
            final_price=current_price,
            triggered_levels=triggered_levels,
            stopped_by_wall=order_book is not None
            and cascade_waves < self.config.max_cascade_depth,
        )

    def get_liquidation_heatmap(
        self, price_range: tuple[float, float], n_buckets: int = 50
    ) -> NDArray[np.float64]:
        """
        Get liquidation volume heatmap.

        Args:
            price_range: (min_price, max_price)
            n_buckets: Number of price buckets

        Returns:
            Array of liquidation volumes per bucket
        """
        min_price, max_price = price_range
        bucket_size = (max_price - min_price) / n_buckets
        heatmap = np.zeros(n_buckets)

        all_levels = self.long_liquidations + self.short_liquidations

        for level in all_levels:
            if min_price <= level.price <= max_price:
                bucket = int((level.price - min_price) / bucket_size)
                bucket = min(bucket, n_buckets - 1)
                heatmap[bucket] += level.total_size

        return heatmap


# =============================================================================
# 5. ORDER FLOW ANALYZER
# =============================================================================


@dataclass
class OrderFlowMetrics:
    """Metrics from order flow analysis."""

    # Volume metrics
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    net_volume: float = 0.0
    volume_imbalance: float = 0.0  # -1 to 1

    # Trade metrics
    buy_trades: int = 0
    sell_trades: int = 0
    avg_trade_size: float = 0.0

    # Toxicity metrics
    vpin: float = 0.0  # Volume-synchronized probability of informed trading
    toxicity_score: float = 0.0  # 0-100

    # Aggressor metrics
    taker_buy_ratio: float = 0.5
    large_trade_ratio: float = 0.0

    # Delta metrics
    cumulative_delta: float = 0.0
    delta_divergence: float = 0.0  # Delta vs price divergence


class OrderFlowAnalyzer:
    """
    Analyzes order flow for market microstructure insights.

    Features:
    - Buy/sell volume classification
    - VPIN (toxicity) calculation
    - Cumulative delta tracking
    - Large trade detection
    """

    def __init__(self, vpin_window: int = 50, large_trade_threshold: float = 2.0):
        """
        Initialize order flow analyzer.

        Args:
            vpin_window: Window for VPIN calculation
            large_trade_threshold: Multiplier for large trade detection
        """
        self.vpin_window = vpin_window
        self.large_trade_threshold = large_trade_threshold

        self._buy_volumes: list[float] = []
        self._sell_volumes: list[float] = []
        self._cumulative_delta: float = 0.0
        self._price_at_delta_start: float = 0.0

    def classify_trades(
        self,
        prices: NDArray[np.float64],
        volumes: NDArray[np.float64],
        method: str = "tick",
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """
        Classify trades as buy or sell.

        Args:
            prices: Trade prices
            volumes: Trade volumes
            method: Classification method ('tick', 'quote', 'lr')

        Returns:
            Tuple of (buy_volumes, sell_volumes)
        """
        n = len(prices)
        buy_volumes = np.zeros(n)
        sell_volumes = np.zeros(n)

        if method == "tick":
            # Tick rule: up-tick = buy, down-tick = sell
            for i in range(1, n):
                if prices[i] > prices[i - 1]:
                    buy_volumes[i] = volumes[i]
                elif prices[i] < prices[i - 1]:
                    sell_volumes[i] = volumes[i]
                else:
                    # Same price - use previous classification
                    if i > 1:
                        if buy_volumes[i - 1] > 0:
                            buy_volumes[i] = volumes[i]
                        else:
                            sell_volumes[i] = volumes[i]
                    else:
                        # Default to 50/50
                        buy_volumes[i] = volumes[i] / 2
                        sell_volumes[i] = volumes[i] / 2

        return buy_volumes, sell_volumes

    def analyze(
        self,
        buy_volume: float,
        sell_volume: float,
        n_buy_trades: int,
        n_sell_trades: int,
        current_price: float,
    ) -> OrderFlowMetrics:
        """
        Analyze order flow for a period.

        Args:
            buy_volume: Total buy volume
            sell_volume: Total sell volume
            n_buy_trades: Number of buy trades
            n_sell_trades: Number of sell trades
            current_price: Current price

        Returns:
            OrderFlowMetrics with analysis results
        """
        # Update history
        self._buy_volumes.append(buy_volume)
        self._sell_volumes.append(sell_volume)

        # Keep window size
        if len(self._buy_volumes) > self.vpin_window:
            self._buy_volumes.pop(0)
            self._sell_volumes.pop(0)

        # Calculate metrics
        total_volume = buy_volume + sell_volume
        net_volume = buy_volume - sell_volume

        if total_volume > 0:
            volume_imbalance = net_volume / total_volume
        else:
            volume_imbalance = 0.0

        # Average trade size
        n_trades = n_buy_trades + n_sell_trades
        avg_trade_size = total_volume / n_trades if n_trades > 0 else 0

        # Taker buy ratio
        taker_buy_ratio = buy_volume / total_volume if total_volume > 0 else 0.5

        # VPIN calculation (simplified)
        if len(self._buy_volumes) >= self.vpin_window:
            window_buy = sum(self._buy_volumes)
            window_sell = sum(self._sell_volumes)
            window_total = window_buy + window_sell
            if window_total > 0:
                vpin = abs(window_buy - window_sell) / window_total
            else:
                vpin = 0.0
        else:
            vpin = abs(volume_imbalance)

        # Toxicity score (0-100)
        toxicity_score = vpin * 100

        # Cumulative delta
        self._cumulative_delta += net_volume

        # Delta divergence (simplified)
        if self._price_at_delta_start == 0:
            self._price_at_delta_start = current_price
            delta_divergence = 0.0
        else:
            price_change = (
                current_price - self._price_at_delta_start
            ) / self._price_at_delta_start
            expected_delta_direction = 1 if price_change > 0 else -1
            actual_delta_direction = 1 if self._cumulative_delta > 0 else -1
            delta_divergence = (
                1.0 if expected_delta_direction != actual_delta_direction else 0.0
            )

        return OrderFlowMetrics(
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            net_volume=net_volume,
            volume_imbalance=volume_imbalance,
            buy_trades=n_buy_trades,
            sell_trades=n_sell_trades,
            avg_trade_size=avg_trade_size,
            vpin=vpin,
            toxicity_score=toxicity_score,
            taker_buy_ratio=taker_buy_ratio,
            cumulative_delta=self._cumulative_delta,
            delta_divergence=delta_divergence,
        )

    def reset(self) -> None:
        """Reset analyzer state."""
        self._buy_volumes = []
        self._sell_volumes = []
        self._cumulative_delta = 0.0
        self._price_at_delta_start = 0.0


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Order Book
    "OrderBookSide",
    "OrderBookLevel",
    "OrderBookSnapshot",
    "OrderBookConfig",
    "OrderBookSimulator",
    # Market Depth
    "DepthMetrics",
    "MarketDepthAnalyzer",
    # Market Impact
    "MarketImpactConfig",
    "MarketImpactResult",
    "MarketImpactCalculator",
    # Liquidation Cascade
    "LiquidationLevel",
    "CascadeConfig",
    "CascadeResult",
    "LiquidationCascadeSimulator",
    # Order Flow
    "OrderFlowMetrics",
    "OrderFlowAnalyzer",
]
