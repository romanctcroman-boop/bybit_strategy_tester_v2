"""Unit tests for OrderExecutor (AUDIT_PROJECT_EXTENDED)."""

from backend.services.live_trading.order_executor import (
    OrderRequest,
    TimeInForce,
    TriggerDirection,
)
from backend.services.trading_engine_interface import OrderSide, OrderType


def test_order_request_dataclass():
    """OrderRequest has required fields."""
    req = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=0.001,
    )
    assert req.symbol == "BTCUSDT"
    assert req.side == OrderSide.BUY


def test_time_in_force_enum():
    """TimeInForce has expected values."""
    assert TimeInForce.GTC.value == "GTC"


def test_trigger_direction_enum():
    """TriggerDirection has expected values."""
    assert TriggerDirection.RISE.value == 1
