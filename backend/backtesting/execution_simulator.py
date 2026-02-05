"""
Execution Simulator for realistic order fill modeling.

Simulates latency, slippage, partial fills, and order rejections
for more accurate backtest-to-live gap estimation.

Usage:
    from backend.backtesting.execution_simulator import ExecutionSimulator, FillResult

    sim = ExecutionSimulator(
        latency_ms=50,
        slippage_bps=5,
        fill_probability=0.98,
        rejection_probability=0.01,
    )
    fill = sim.simulate_fill(order_price=50000.0, side="buy", size=0.1)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


class FillStatus(Enum):
    """Order fill status."""

    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class FillResult:
    """Result of simulated order execution."""

    status: FillStatus
    fill_price: float
    fill_size: float  # Actual filled size (may be partial)
    slippage_bps: float
    latency_ms: float
    rejected_reason: Optional[str] = None


class ExecutionSimulator:
    """
    Simulates realistic order execution with configurable friction.

    Parameters:
        latency_ms: Simulated latency in milliseconds (for backtest timing)
        slippage_bps: Slippage in basis points (1 bps = 0.01%)
        fill_probability: Probability of full fill (1.0 = always fill)
        partial_fill_probability: If not full fill, probability of partial
        min_fill_ratio: Minimum fill ratio for partial fills (0.1 = 10%)
        rejection_probability: Probability of order rejection
        seed: Random seed for reproducibility
    """

    def __init__(
        self,
        latency_ms: float = 50.0,
        slippage_bps: float = 5.0,
        fill_probability: float = 0.98,
        partial_fill_probability: float = 0.8,
        min_fill_ratio: float = 0.1,
        rejection_probability: float = 0.01,
        seed: Optional[int] = None,
    ):
        self.latency_ms = latency_ms
        self.slippage_bps = slippage_bps
        self.fill_probability = fill_probability
        self.partial_fill_probability = partial_fill_probability
        self.min_fill_ratio = min_fill_ratio
        self.rejection_probability = rejection_probability
        self._rng = np.random.default_rng(seed)

    def simulate_fill(
        self,
        order_price: float,
        side: str,
        size: float,
        order_type: str = "market",
    ) -> FillResult:
        """
        Simulate order execution and return fill result.

        Args:
            order_price: Limit price or reference price for market
            side: "buy" or "sell"
            size: Order size
            order_type: "market" or "limit"

        Returns:
            FillResult with status, fill_price, fill_size, slippage, latency
        """
        # Rejection check
        if self._rng.random() < self.rejection_probability:
            return FillResult(
                status=FillStatus.REJECTED,
                fill_price=order_price,
                fill_size=0.0,
                slippage_bps=0.0,
                latency_ms=self.latency_ms,
                rejected_reason="simulated_rejection",
            )

        # Slippage: random within 0 to slippage_bps
        slippage_bps = self._rng.uniform(0, self.slippage_bps)
        slippage_pct = slippage_bps / 10000.0

        if side.lower() == "buy":
            fill_price = order_price * (1.0 + slippage_pct)
        else:
            fill_price = order_price * (1.0 - slippage_pct)

        # Fill amount
        rejected_reason = None
        if self._rng.random() < self.fill_probability:
            fill_size = size
            status = FillStatus.FILLED
        elif self._rng.random() < self.partial_fill_probability:
            ratio = self._rng.uniform(self.min_fill_ratio, 1.0)
            fill_size = size * ratio
            status = FillStatus.PARTIAL
        else:
            fill_size = 0.0
            status = FillStatus.REJECTED
            rejected_reason = "no_fill"

        return FillResult(
            status=status,
            fill_price=fill_price,
            fill_size=fill_size,
            slippage_bps=slippage_bps,
            latency_ms=self.latency_ms,
            rejected_reason=rejected_reason,
        )

    def apply_slippage_to_price(self, price: float, side: str) -> float:
        """Apply random slippage to price (convenience)."""
        slippage_bps = self._rng.uniform(0, self.slippage_bps)
        slip = slippage_bps / 10000.0
        if side.lower() == "buy":
            return price * (1.0 + slip)
        return price * (1.0 - slip)
