"""
Simulated Order Executor — симуляция исполнения для backtest и paper.

Использует ExecutionSimulator для latency, slippage, partial fills, rejections.
"""

from typing import Any
from uuid import uuid4

from backend.backtesting.execution_simulator import (
    ExecutionSimulator,
    FillStatus,
)
from backend.services.unified_trading.interfaces import OrderExecutorInterface, OrderResult


class SimulatedExecutor(OrderExecutorInterface):
    """
    Симуляция исполнения ордеров.

    Для backtest и paper trading. Использует ExecutionSimulator.
    """

    def __init__(
        self,
        latency_ms: float = 0,
        slippage_bps: float = 5.0,
        fill_probability: float = 1.0,
        rejection_probability: float = 0.0,
        seed: int | None = None,
    ):
        self._sim = ExecutionSimulator(
            latency_ms=latency_ms,
            slippage_bps=slippage_bps,
            fill_probability=fill_probability,
            rejection_probability=rejection_probability,
            seed=seed,
        )
        self._price_provider = None  # Set via set_price_provider(callable)

    def set_price_provider(self, fn):
        """Установить функцию (symbol) -> current_price для симуляции."""
        self._price_provider = fn

    def _get_price(self, symbol: str) -> float:
        if self._price_provider:
            return self._price_provider(symbol)
        return 0.0

    def place_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        reduce_only: bool = False,
        **kwargs: Any,
    ) -> OrderResult:
        """Симуляция рыночного ордера."""
        price = self._get_price(symbol)
        if price <= 0:
            return OrderResult(
                order_id=str(uuid4()),
                symbol=symbol,
                side=side,
                status="rejected",
                error="No price available",
            )

        fill = self._sim.simulate_fill(price, side, qty, "market")

        if fill.status == FillStatus.REJECTED:
            return OrderResult(
                order_id=str(uuid4()),
                symbol=symbol,
                side=side,
                status="rejected",
                filled_qty=0,
                filled_price=price,
                error=fill.rejected_reason or "rejected",
            )

        return OrderResult(
            order_id=str(uuid4()),
            symbol=symbol,
            side=side,
            status="filled" if fill.fill_size >= qty else "partial",
            filled_qty=fill.fill_size,
            filled_price=fill.fill_price,
        )

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        reduce_only: bool = False,
        **kwargs: Any,
    ) -> OrderResult:
        """Симуляция лимитного ордера (упрощённо: fill по цене или лучше)."""
        fill = self._sim.simulate_fill(price, side, qty, "limit")

        if fill.status == FillStatus.REJECTED:
            return OrderResult(
                order_id=str(uuid4()),
                symbol=symbol,
                side=side,
                status="rejected",
                filled_qty=0,
                filled_price=price,
                error=fill.rejected_reason or "rejected",
            )

        return OrderResult(
            order_id=str(uuid4()),
            symbol=symbol,
            side=side,
            status="filled" if fill.fill_size >= qty else "partial",
            filled_qty=fill.fill_size,
            filled_price=fill.fill_price,
        )

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """В симуляции — всегда успешно."""
        return True
