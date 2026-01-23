"""
Slippage Models for Realistic Backtesting

Provides various slippage models:
- Volume Impact: Slippage based on order size relative to volume
- Volatility: Slippage increases with market volatility
- Order Book: Simulates order book depth impact
- Composite: Combines multiple slippage factors

Usage:
    from backend.services.advanced_backtesting.slippage import (
        VolumeImpactSlippage,
        VolatilitySlippage,
        OrderBookSlippage,
    )

    model = VolumeImpactSlippage(impact_factor=0.1)
    slippage_pct = model.calculate(order_size=1000, volume=100000)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class SlippageType(Enum):
    """Types of slippage models."""

    FIXED = "fixed"
    VOLUME_IMPACT = "volume_impact"
    VOLATILITY = "volatility"
    ORDER_BOOK = "order_book"
    COMPOSITE = "composite"
    ADAPTIVE = "adaptive"


@dataclass
class SlippageResult:
    """Result of slippage calculation."""

    slippage_pct: float  # Percentage slippage
    slippage_amount: float  # Absolute slippage in price units
    execution_price: float  # Final execution price after slippage
    original_price: float  # Original intended price
    model_type: SlippageType
    components: dict[str, float] = field(default_factory=dict)  # Breakdown

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "slippage_pct": round(self.slippage_pct * 100, 4),
            "slippage_amount": round(self.slippage_amount, 8),
            "execution_price": round(self.execution_price, 8),
            "original_price": round(self.original_price, 8),
            "model_type": self.model_type.value,
            "components": {k: round(v * 100, 4) for k, v in self.components.items()},
        }


class SlippageModel(ABC):
    """Abstract base class for slippage models."""

    @abstractmethod
    def calculate(
        self,
        price: float,
        order_size: float,
        side: str,  # 'buy' or 'sell'
        **kwargs,
    ) -> SlippageResult:
        """
        Calculate slippage for an order.

        Args:
            price: Intended execution price
            order_size: Size of the order in base currency
            side: 'buy' or 'sell'
            **kwargs: Additional parameters (volume, volatility, etc.)

        Returns:
            SlippageResult with calculated slippage
        """
        pass

    @abstractmethod
    def get_type(self) -> SlippageType:
        """Return the type of slippage model."""
        pass


class FixedSlippage(SlippageModel):
    """
    Fixed percentage slippage model.

    Simple model that applies a constant slippage percentage.
    """

    def __init__(self, slippage_pct: float = 0.001):
        """
        Initialize fixed slippage model.

        Args:
            slippage_pct: Fixed slippage as decimal (0.001 = 0.1%)
        """
        self.slippage_pct = slippage_pct

    def calculate(
        self,
        price: float,
        order_size: float,
        side: str,
        **kwargs,
    ) -> SlippageResult:
        """Calculate fixed slippage."""
        slippage_pct = self.slippage_pct

        # Buy = price goes up, Sell = price goes down
        direction = 1 if side.lower() == "buy" else -1
        slippage_amount = price * slippage_pct * direction
        execution_price = price + slippage_amount

        return SlippageResult(
            slippage_pct=slippage_pct,
            slippage_amount=slippage_amount,
            execution_price=execution_price,
            original_price=price,
            model_type=SlippageType.FIXED,
        )

    def get_type(self) -> SlippageType:
        return SlippageType.FIXED


class VolumeImpactSlippage(SlippageModel):
    """
    Volume Impact slippage model.

    Slippage increases with order size relative to average volume.
    Based on square-root market impact model.

    Formula: slippage = impact_factor * sqrt(order_size / avg_volume) * volatility
    """

    def __init__(
        self,
        impact_factor: float = 0.1,
        min_slippage: float = 0.0001,
        max_slippage: float = 0.05,
    ):
        """
        Initialize volume impact model.

        Args:
            impact_factor: Scaling factor for impact (0.1 = 10% of sqrt term)
            min_slippage: Minimum slippage floor
            max_slippage: Maximum slippage cap
        """
        self.impact_factor = impact_factor
        self.min_slippage = min_slippage
        self.max_slippage = max_slippage

    def calculate(
        self,
        price: float,
        order_size: float,
        side: str,
        volume: float = 1_000_000,
        volatility: float = 0.02,
        **kwargs,
    ) -> SlippageResult:
        """
        Calculate volume impact slippage.

        Args:
            price: Intended execution price
            order_size: Order size in base currency
            side: 'buy' or 'sell'
            volume: Average volume for the period
            volatility: Current volatility (e.g., from ATR)
        """
        # Square-root market impact
        order_value = order_size * price
        volume_ratio = order_value / max(volume * price, 1)
        volume_ratio = max(volume_ratio, 0)

        # Almgren-Chriss style impact (guard sqrt)
        impact = self.impact_factor * np.sqrt(volume_ratio) * volatility

        # Apply bounds
        slippage_pct = max(self.min_slippage, min(impact, self.max_slippage))

        # Direction
        direction = 1 if side.lower() == "buy" else -1
        slippage_amount = price * slippage_pct * direction
        execution_price = price + slippage_amount

        return SlippageResult(
            slippage_pct=slippage_pct,
            slippage_amount=slippage_amount,
            execution_price=execution_price,
            original_price=price,
            model_type=SlippageType.VOLUME_IMPACT,
            components={
                "volume_ratio": volume_ratio,
                "volatility_component": volatility,
                "raw_impact": impact,
            },
        )

    def get_type(self) -> SlippageType:
        return SlippageType.VOLUME_IMPACT


class VolatilitySlippage(SlippageModel):
    """
    Volatility-based slippage model.

    Slippage scales with market volatility (ATR or standard deviation).
    Higher volatility = higher slippage.
    """

    def __init__(
        self,
        base_slippage: float = 0.0005,
        volatility_multiplier: float = 2.0,
        max_slippage: float = 0.03,
    ):
        """
        Initialize volatility slippage model.

        Args:
            base_slippage: Minimum base slippage
            volatility_multiplier: How much volatility affects slippage
            max_slippage: Maximum slippage cap
        """
        self.base_slippage = base_slippage
        self.volatility_multiplier = volatility_multiplier
        self.max_slippage = max_slippage

    def calculate(
        self,
        price: float,
        order_size: float,
        side: str,
        volatility: float = 0.02,
        atr: Optional[float] = None,
        **kwargs,
    ) -> SlippageResult:
        """
        Calculate volatility-based slippage.

        Args:
            price: Intended execution price
            order_size: Order size
            side: 'buy' or 'sell'
            volatility: Volatility as percentage (0.02 = 2%)
            atr: ATR value (used if volatility not provided)
        """
        # Use ATR to derive volatility if provided
        if atr is not None and price > 0:
            volatility = atr / price

        # Calculate slippage
        slippage_pct = self.base_slippage + (volatility * self.volatility_multiplier)
        slippage_pct = min(slippage_pct, self.max_slippage)

        # Direction
        direction = 1 if side.lower() == "buy" else -1
        slippage_amount = price * slippage_pct * direction
        execution_price = price + slippage_amount

        return SlippageResult(
            slippage_pct=slippage_pct,
            slippage_amount=slippage_amount,
            execution_price=execution_price,
            original_price=price,
            model_type=SlippageType.VOLATILITY,
            components={
                "base_slippage": self.base_slippage,
                "volatility_contribution": volatility * self.volatility_multiplier,
            },
        )

    def get_type(self) -> SlippageType:
        return SlippageType.VOLATILITY


class OrderBookSlippage(SlippageModel):
    """
    Order book depth slippage model.

    Simulates walking through order book levels based on order size.
    Uses bid-ask spread and liquidity depth estimates.
    """

    def __init__(
        self,
        spread_multiplier: float = 0.5,
        depth_factor: float = 0.00001,
        min_spread: float = 0.0001,
    ):
        """
        Initialize order book slippage model.

        Args:
            spread_multiplier: Portion of spread to apply (0.5 = half spread)
            depth_factor: Slippage per unit of depth consumed
            min_spread: Minimum spread assumption
        """
        self.spread_multiplier = spread_multiplier
        self.depth_factor = depth_factor
        self.min_spread = min_spread

    def calculate(
        self,
        price: float,
        order_size: float,
        side: str,
        spread: Optional[float] = None,
        bid_price: Optional[float] = None,
        ask_price: Optional[float] = None,
        book_depth: float = 100_000,
        **kwargs,
    ) -> SlippageResult:
        """
        Calculate order book slippage.

        Args:
            price: Mid price or intended price
            order_size: Order size
            side: 'buy' or 'sell'
            spread: Bid-ask spread as decimal
            bid_price: Best bid price
            ask_price: Best ask price
            book_depth: Estimated liquidity depth
        """
        # Calculate spread
        if spread is None:
            if bid_price is not None and ask_price is not None:
                spread = (ask_price - bid_price) / price
            else:
                spread = self.min_spread

        # Spread component (crossing the spread)
        spread_slippage = spread * self.spread_multiplier

        # Depth component (walking the book)
        order_value = order_size * price
        depth_ratio = order_value / max(book_depth, 1)
        depth_slippage = depth_ratio * self.depth_factor

        # Total slippage
        slippage_pct = spread_slippage + depth_slippage

        # Direction
        direction = 1 if side.lower() == "buy" else -1
        slippage_amount = price * slippage_pct * direction
        execution_price = price + slippage_amount

        return SlippageResult(
            slippage_pct=slippage_pct,
            slippage_amount=slippage_amount,
            execution_price=execution_price,
            original_price=price,
            model_type=SlippageType.ORDER_BOOK,
            components={
                "spread_slippage": spread_slippage,
                "depth_slippage": depth_slippage,
                "depth_ratio": depth_ratio,
            },
        )

    def get_type(self) -> SlippageType:
        return SlippageType.ORDER_BOOK


class CompositeSlippage(SlippageModel):
    """
    Composite slippage model.

    Combines multiple slippage models with configurable weights.
    """

    def __init__(
        self,
        models: Optional[list[tuple[SlippageModel, float]]] = None,
        # Common tunable params forwarded from API/config
        impact_factor: Optional[float] = None,
        min_slippage: Optional[float] = None,
        max_slippage: Optional[float] = None,
        base_slippage: Optional[float] = None,
        volatility_multiplier: Optional[float] = None,
        spread_multiplier: Optional[float] = None,
        depth_factor: Optional[float] = None,
        min_spread: Optional[float] = None,
    ):
        """
        Initialize composite slippage model.

        Args:
            models: Optional explicit list of (model, weight) tuples.
            Other kwargs: forwarded to sub-model constructors when provided.
        """
        if models is not None:
            # explicit models provided by caller
            self.models = models
            return

        # Build submodels using provided kwargs or defaults
        vol_impact_kwargs = {}
        if impact_factor is not None:
            vol_impact_kwargs["impact_factor"] = impact_factor
        if min_slippage is not None:
            vol_impact_kwargs["min_slippage"] = min_slippage
        if max_slippage is not None:
            vol_impact_kwargs["max_slippage"] = max_slippage

        volatility_kwargs = {}
        if base_slippage is not None:
            volatility_kwargs["base_slippage"] = base_slippage
        if volatility_multiplier is not None:
            volatility_kwargs["volatility_multiplier"] = volatility_multiplier
        if max_slippage is not None:
            volatility_kwargs["max_slippage"] = max_slippage

        orderbook_kwargs = {}
        if spread_multiplier is not None:
            orderbook_kwargs["spread_multiplier"] = spread_multiplier
        if depth_factor is not None:
            orderbook_kwargs["depth_factor"] = depth_factor
        if min_spread is not None:
            orderbook_kwargs["min_spread"] = min_spread

        self.models = [
            (VolumeImpactSlippage(**vol_impact_kwargs), 0.4),
            (VolatilitySlippage(**volatility_kwargs), 0.3),
            (OrderBookSlippage(**orderbook_kwargs), 0.3),
        ]

    def calculate(
        self,
        price: float,
        order_size: float,
        side: str,
        **kwargs,
    ) -> SlippageResult:
        """Calculate weighted average slippage from all models."""
        total_slippage = 0.0
        components = {}

        for model, weight in self.models:
            result = model.calculate(price, order_size, side, **kwargs)
            total_slippage += result.slippage_pct * weight
            components[model.get_type().value] = result.slippage_pct

        # Direction
        direction = 1 if side.lower() == "buy" else -1
        slippage_amount = price * total_slippage * direction
        execution_price = price + slippage_amount

        return SlippageResult(
            slippage_pct=total_slippage,
            slippage_amount=slippage_amount,
            execution_price=execution_price,
            original_price=price,
            model_type=SlippageType.COMPOSITE,
            components=components,
        )

    def get_type(self) -> SlippageType:
        return SlippageType.COMPOSITE


class AdaptiveSlippage(SlippageModel):
    """
    Adaptive slippage model.

    Dynamically adjusts slippage based on market conditions:
    - Time of day (higher during low-liquidity hours)
    - Market regime (higher during volatile periods)
    - Order urgency (market vs limit orders)
    """

    def __init__(
        self,
        base_model: Optional[SlippageModel] = None,
        time_multipliers: Optional[dict[int, float]] = None,
        regime_multipliers: Optional[dict[str, float]] = None,
    ):
        """
        Initialize adaptive slippage model.

        Args:
            base_model: Underlying slippage model
            time_multipliers: Hour -> multiplier mapping
            regime_multipliers: Regime -> multiplier mapping
        """
        self.base_model = base_model or VolumeImpactSlippage()

        # Default time multipliers (UTC hours)
        self.time_multipliers = time_multipliers or {
            0: 1.5,  # Midnight - low liquidity
            1: 1.5,
            2: 1.4,
            3: 1.3,
            4: 1.2,
            5: 1.1,
            6: 1.0,
            7: 0.9,
            8: 0.8,  # EU open
            9: 0.8,
            10: 0.8,
            11: 0.85,
            12: 0.9,
            13: 0.85,  # US pre-market
            14: 0.8,  # US open
            15: 0.8,
            16: 0.85,
            17: 0.9,
            18: 1.0,
            19: 1.1,
            20: 1.2,
            21: 1.3,
            22: 1.4,
            23: 1.5,
        }

        # Default regime multipliers
        self.regime_multipliers = regime_multipliers or {
            "trending": 1.0,
            "volatile": 1.5,
            "ranging": 0.8,
            "breakout": 2.0,
            "low_volatility": 0.7,
        }

    def calculate(
        self,
        price: float,
        order_size: float,
        side: str,
        timestamp: Optional[datetime] = None,
        regime: str = "trending",
        order_type: str = "market",
        **kwargs,
    ) -> SlippageResult:
        """
        Calculate adaptive slippage.

        Args:
            price: Intended execution price
            order_size: Order size
            side: 'buy' or 'sell'
            timestamp: Order timestamp
            regime: Current market regime
            order_type: 'market' or 'limit'
        """
        # Get base slippage
        base_result = self.base_model.calculate(price, order_size, side, **kwargs)
        base_slippage = base_result.slippage_pct

        # Time adjustment
        hour = timestamp.hour if timestamp else 12
        time_mult = self.time_multipliers.get(hour, 1.0)

        # Regime adjustment
        regime_mult = self.regime_multipliers.get(regime, 1.0)

        # Order type adjustment (limit orders have less slippage)
        order_mult = 0.5 if order_type.lower() == "limit" else 1.0

        # Combined slippage
        final_slippage = base_slippage * time_mult * regime_mult * order_mult

        # Direction
        direction = 1 if side.lower() == "buy" else -1
        slippage_amount = price * final_slippage * direction
        execution_price = price + slippage_amount

        return SlippageResult(
            slippage_pct=final_slippage,
            slippage_amount=slippage_amount,
            execution_price=execution_price,
            original_price=price,
            model_type=SlippageType.ADAPTIVE,
            components={
                "base_slippage": base_slippage,
                "time_multiplier": time_mult,
                "regime_multiplier": regime_mult,
                "order_type_multiplier": order_mult,
            },
        )

    def get_type(self) -> SlippageType:
        return SlippageType.ADAPTIVE


def create_slippage_model(
    model_type: str = "composite",
    **kwargs,
) -> SlippageModel:
    """
    Factory function to create slippage models.

    Args:
        model_type: Type of model ('fixed', 'volume_impact', 'volatility',
                    'order_book', 'composite', 'adaptive')
        **kwargs: Model-specific parameters

    Returns:
        Configured slippage model
    """
    models = {
        "fixed": FixedSlippage,
        "volume_impact": VolumeImpactSlippage,
        "volatility": VolatilitySlippage,
        "order_book": OrderBookSlippage,
        "composite": CompositeSlippage,
        "adaptive": AdaptiveSlippage,
    }

    model_class = models.get(model_type.lower())
    if not model_class:
        logger.warning(f"Unknown slippage model: {model_type}, using composite")
        model_class = CompositeSlippage

    return model_class(**kwargs)
