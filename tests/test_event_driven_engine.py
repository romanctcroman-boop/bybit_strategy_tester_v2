"""Tests for EventDrivenEngine (event-driven backtest skeleton)."""

import numpy as np
import pandas as pd
import pytest

from backend.backtesting.engines.event_driven_engine import (
    BarEvent,
    EventDrivenEngine,
    EventQueue,
    EventType,
    OrderEvent,
    SimulationConfig,
    SimulationExecutionHandler,
)


def test_event_queue_fifo():
    """EventQueue processes events in timestamp order."""
    q = EventQueue()
    q.push(BarEvent(timestamp=200, event_type=EventType.BAR, payload={"close": 2}))
    q.push(BarEvent(timestamp=100, event_type=EventType.BAR, payload={"close": 1}))
    q.push(BarEvent(timestamp=150, event_type=EventType.BAR, payload={"close": 1.5}))
    assert not q.empty()
    e1 = q.pop()
    assert e1 is not None and e1.timestamp == 100
    e2 = q.pop()
    assert e2 is not None and e2.timestamp == 150
    e3 = q.pop()
    assert e3 is not None and e3.timestamp == 200
    assert q.empty()


def test_event_driven_engine_load_and_run():
    """EventDrivenEngine loads bars and runs event loop."""
    df = pd.DataFrame({
        "open": [100.0] * 10,
        "high": [101.0] * 10,
        "low": [99.0] * 10,
        "close": np.linspace(100, 109, 10),
        "volume": [1000.0] * 10,
    })
    orders_seen = []

    def on_bar(event: BarEvent):
        if event.close > 105:
            orders_seen.append({"close": event.close})
            return [{"symbol": "X", "side": "buy", "qty": 1.0}]
        return []

    eng = EventDrivenEngine(initial_capital=10000, on_bar=on_bar)
    eng.load_bars(df)
    result = eng.run()
    assert result["bar_count"] == 10
    assert result["final_equity"] == 10000  # no real PnL in skeleton
    assert len(orders_seen) >= 1


def test_event_driven_engine_empty_df():
    """EventDrivenEngine handles empty DataFrame."""
    eng = EventDrivenEngine()
    eng.load_bars(pd.DataFrame(columns=["open", "high", "low", "close", "volume"]))
    result = eng.run()
    assert result["bar_count"] == 0
    assert result["final_equity"] == 10000
    assert result["trades"] == []


def test_run_event_driven_with_adapter():
    """run_event_driven_with_adapter integrates StrategyBuilderAdapter."""
    pytest.importorskip("vectorbt")

    from backend.backtesting.engines.event_driven_engine import run_event_driven_with_adapter
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    graph = {
        "blocks": [
            {"id": "main_strategy", "type": "strategy", "isMain": True, "params": {}},
            {"id": "rsi_1", "type": "rsi", "category": "indicator", "params": {"period": 14}},
            {"id": "less_1", "type": "less_than", "category": "condition", "params": {}},
            {"id": "const_30", "type": "constant", "category": "input", "params": {"value": 30}},
        ],
        "connections": [
            {"source": {"blockId": "rsi_1", "portId": "value"}, "target": {"blockId": "less_1", "portId": "left"}},
            {"source": {"blockId": "const_30", "portId": "value"}, "target": {"blockId": "less_1", "portId": "right"}},
            {"source": {"blockId": "less_1", "portId": "result"}, "target": {"blockId": "main_strategy", "portId": "entry_long"}},
        ],
    }
    n = 50
    df = pd.DataFrame({
        "open": 100.0 + np.arange(n) * 0.1,
        "high": 101.0 + np.arange(n) * 0.1,
        "low": 99.0 + np.arange(n) * 0.1,
        "close": 100.0 + np.arange(n) * 0.2,
        "volume": [1000.0] * n,
    })
    df["open_time"] = pd.date_range("2024-01-01", periods=n, freq="1h")

    adapter = StrategyBuilderAdapter(graph)
    result = run_event_driven_with_adapter(adapter, df, initial_capital=10000, symbol="TEST")
    assert "final_equity" in result
    assert "bar_count" in result
    assert result["bar_count"] == n
    assert "trades" in result


def test_simulation_execution_handler():
    """SimulationExecutionHandler applies slippage and partial fills."""
    df = pd.DataFrame({
        "open": [100.0, 101.0],
        "high": [102.0, 103.0],
        "low": [99.0, 100.0],
        "close": [101.0, 102.0],
        "volume": [1000.0, 1000.0],
    })
    order = OrderEvent(
        timestamp=1000.0,
        event_type=EventType.ORDER,
        payload={"symbol": "X", "side": "buy", "qty": 10.0, "order_type": "market"},
    )
    # No slippage, full fill
    cfg = SimulationConfig(slippage_bps=0, fill_ratio=1.0, reject_probability=0)
    handler = SimulationExecutionHandler(cfg)
    fills = handler.execute(order, df, 0, 101.0)
    assert len(fills) == 1
    assert fills[0].fill_qty == 10.0
    # With high/low slippage: buy fills at high * (1 + slip)
    cfg2 = SimulationConfig(slippage_bps=100, use_high_low_slippage=True)
    handler2 = SimulationExecutionHandler(cfg2)
    fills2 = handler2.execute(order, df, 0, 101.0)
    assert len(fills2) == 1
    assert fills2[0].fill_price > 102.0  # high=102, +1% = 103.02
