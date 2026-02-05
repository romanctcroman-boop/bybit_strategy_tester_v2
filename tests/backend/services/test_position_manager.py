"""Tests for PositionManager (AUDIT_PROJECT_EXTENDED)."""
import pytest
from datetime import datetime, timezone

from backend.services.live_trading.position_manager import (
    PositionMode,
    PositionSide,
    PositionSnapshot,
)


def test_position_snapshot_dataclass():
    """PositionSnapshot has required fields."""
    snap = PositionSnapshot(
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        size=0.1,
        entry_price=50000.0,
        mark_price=51000.0,
        unrealized_pnl=100.0,
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


def test_position_snapshot_to_dict():
    """PositionSnapshot.to_dict returns serializable dict."""
    snap = PositionSnapshot(
        symbol="ETHUSDT",
        side=PositionSide.SHORT,
        size=1.0,
        entry_price=3000.0,
        mark_price=2950.0,
        unrealized_pnl=50.0,
        realized_pnl=0.0,
        leverage=5.0,
        margin=600.0,
        liquidation_price=3500.0,
        take_profit=None,
        stop_loss=3200.0,
    )
    d = snap.to_dict()
    assert d["symbol"] == "ETHUSDT"
    assert d["side"] == PositionSide.SHORT.value
    assert "updated_at" in d


def test_position_mode_enum():
    """PositionMode has expected values."""
    assert PositionMode.ONE_WAY.value == "one_way"
    assert PositionMode.HEDGE.value == "hedge"
