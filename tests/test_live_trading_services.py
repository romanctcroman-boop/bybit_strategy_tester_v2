"""
Tests for Live Trading services: OrderExecutor, PositionManager.

Uses mocks to avoid real Bybit API calls.
"""


from backend.services.trading_engine_interface import OrderSide, OrderType


class TestOrderExecutor:
    """Tests for OrderExecutor."""

    def test_order_executor_imports(self):
        """OrderExecutor and related classes should import."""
        from backend.services.live_trading.order_executor import (
            OrderExecutor,
            OrderRequest,
            TimeInForce,
            TriggerDirection,
        )

        assert OrderExecutor is not None
        assert OrderRequest is not None
        assert TimeInForce.GTC.value == "GTC"
        assert TriggerDirection.RISE.value == 1

    def test_order_request_creation(self):
        """OrderRequest should accept required params."""
        from backend.services.live_trading.order_executor import OrderRequest

        req = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=0.001,
        )
        assert req.symbol == "BTCUSDT"
        assert req.side == OrderSide.BUY
        assert req.order_type == OrderType.MARKET
        assert req.qty == 0.001

    def test_order_executor_has_place_methods(self):
        """OrderExecutor should have place_market_order and place_limit_order."""
        from backend.services.live_trading.order_executor import OrderExecutor

        executor = OrderExecutor(api_key="test", api_secret="test")
        assert hasattr(executor, "place_market_order")
        assert callable(executor.place_market_order)
        assert hasattr(executor, "place_limit_order")
        assert callable(executor.place_limit_order)


class TestPositionManager:
    """Tests for PositionManager."""

    def test_position_manager_imports(self):
        """PositionManager and PositionSnapshot should import."""
        from backend.services.live_trading.position_manager import (
            PositionManager,
            PositionMode,
            PositionSnapshot,
        )

        assert PositionManager is not None
        assert PositionSnapshot is not None
        assert PositionMode.ONE_WAY is not None

    def test_position_snapshot_creation(self):
        """PositionSnapshot should accept required params."""

        from backend.services.live_trading.position_manager import (
            PositionSide,
            PositionSnapshot,
        )

        snap = PositionSnapshot(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            size=0.1,
            entry_price=50000.0,
            mark_price=50100.0,
            unrealized_pnl=10.0,
            realized_pnl=0.0,
            leverage=10.0,
            margin=500.0,
            liquidation_price=45000.0,
            take_profit=55000.0,
            stop_loss=48000.0,
        )
        assert snap.symbol == "BTCUSDT"
        assert snap.side == PositionSide.LONG
        assert snap.size == 0.1
        assert snap.entry_price == 50000.0
        assert snap.unrealized_pnl == 10.0
