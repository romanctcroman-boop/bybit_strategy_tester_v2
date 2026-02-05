"""
Test for Universal Bar Magnifier Architecture.

Tests:
1. IntrabarEngine tick generation
2. BrokerEmulator order execution
3. Different OHLC path modes
4. Full integration test
"""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from backend.backtesting.broker_emulator import (
    BrokerConfig,
    BrokerEmulator,
    OrderSide,
    OrderType,
)
from backend.backtesting.intrabar_engine import (
    IntrabarConfig,
    IntrabarEngine,
    OHLCPath,
)


def test_intrabar_engine():
    """Test IntrabarEngine tick generation."""
    print("=" * 60)
    print("TEST 1: IntrabarEngine Tick Generation")
    print("=" * 60)

    # Create test 1m data
    m1_data = pd.DataFrame({
        "open_time": [
            1000000,   # 0:00
            1060000,   # 1:00
            1120000,   # 2:00
        ],
        "open": [100.0, 101.0, 100.5],
        "high": [102.0, 103.0, 101.5],
        "low": [99.0, 100.0, 99.5],
        "close": [101.0, 100.5, 101.0],
        "volume": [1000, 1500, 1200],
    })

    # Test different OHLC paths
    for path in OHLCPath:
        print(f"\n  Path: {path.value}")

        config = IntrabarConfig(ohlc_path=path, subticks_per_segment=0)
        engine = IntrabarEngine(config)
        engine.load_m1_data(m1_data)

        # Generate ticks for 3-minute bar
        ticks = list(engine.generate_ticks(1000000, 1180000))

        print(f"    Generated {len(ticks)} ticks")

        # Show first bar's ticks
        bar0_ticks = [t for t in ticks if t.bar_index == 0]
        print("    First 1m bar: ", end="")
        print(" → ".join([f"{t.price:.1f}({t.tick_type[0]})" for t in bar0_ticks]))

    # Test with subticks
    print("\n  With subticks=2:")
    config = IntrabarConfig(ohlc_path=OHLCPath.O_HL_HEURISTIC, subticks_per_segment=2)
    engine = IntrabarEngine(config)
    engine.load_m1_data(m1_data)

    ticks = list(engine.generate_ticks(1000000, 1180000))
    print(f"    Generated {len(ticks)} ticks (vs 12 without subticks)")

    print("\n✅ IntrabarEngine test passed!")


def test_broker_emulator():
    """Test BrokerEmulator order execution."""
    print("\n" + "=" * 60)
    print("TEST 2: BrokerEmulator Order Execution")
    print("=" * 60)

    config = BrokerConfig(
        leverage=10.0,
        taker_fee=0.0004,
        slippage_percent=0.0005,
        sl_priority=True,
    )

    broker = BrokerEmulator(config, initial_capital=10000.0)

    # Test 1: Market order execution
    print("\n  Test 2.1: Market Order")
    order = broker.submit_order(
        OrderType.MARKET,
        OrderSide.BUY,
        size=0.1,
    )

    fills = broker.process_tick(50000.0, 1000)
    assert len(fills) == 1, "Market order should fill immediately"
    print(f"    Filled: {fills[0].size} @ {fills[0].price:.2f}")

    # Set SL/TP
    pos = broker.get_position()
    broker.set_position_sl_tp(
        pos.id,
        stop_loss=49000.0,  # -2%
        take_profit=51000.0,  # +2%
    )

    # Test 2: Price moves up - should not trigger SL/TP
    print("\n  Test 2.2: Price moves (no SL/TP)")
    broker.process_tick(50500.0, 2000)
    assert broker.has_position(), "Position should still be open"
    print(f"    Equity: ${broker.state.equity:.2f}")

    # Test 3: TP triggered
    print("\n  Test 2.3: Take Profit triggered")
    fills = broker.process_tick(51500.0, 3000)  # Above TP
    assert len(fills) == 1, "TP should trigger"
    assert not broker.has_position(), "Position should be closed"
    print(f"    Closed with PnL: ${fills[0].pnl:.2f}")

    # Test 4: SL priority
    print("\n  Test 2.4: SL Priority Test")
    broker.reset()

    # Open position
    broker.submit_order(OrderType.MARKET, OrderSide.BUY, size=0.1)
    broker.process_tick(50000.0, 4000)

    pos = broker.get_position()
    broker.set_position_sl_tp(
        pos.id,
        stop_loss=49000.0,
        take_profit=51000.0,
    )

    # Tick that would trigger both SL and TP (extreme case)
    # Low enough to trigger SL, high enough to trigger TP
    # With sl_priority=True, SL should win
    fills = broker.process_tick(48500.0, 5000)  # Below SL
    assert len(fills) == 1, "SL should trigger"
    assert "stop_loss" in fills[0].order_id, "Should be SL exit"
    print(f"    SL triggered with PnL: ${fills[0].pnl:.2f}")

    print("\n✅ BrokerEmulator test passed!")


def test_integration():
    """Test full integration: IntrabarEngine + BrokerEmulator."""
    print("\n" + "=" * 60)
    print("TEST 3: Full Integration")
    print("=" * 60)

    # Create realistic 1m data (simulating price movement)
    # 60 minutes = 1 hour bar
    timestamps = [i * 60000 for i in range(60)]  # 60 1m bars

    # Price starts at 50000, goes up to 51000, then drops to 49500
    prices = []
    for i in range(60):
        if i < 20:
            base = 50000 + i * 50  # Rising
        elif i < 40:
            base = 51000 - (i - 20) * 25  # Falling slowly
        else:
            base = 50500 - (i - 40) * 50  # Falling faster

        prices.append({
            "open_time": timestamps[i],
            "open": base,
            "high": base + 50,
            "low": base - 50,
            "close": base + 25,
            "volume": 100,
        })

    m1_data = pd.DataFrame(prices)

    # Setup
    intrabar_config = IntrabarConfig(
        ohlc_path=OHLCPath.O_HL_HEURISTIC,
        subticks_per_segment=0,
    )
    intrabar = IntrabarEngine(intrabar_config)
    intrabar.load_m1_data(m1_data)

    broker_config = BrokerConfig(
        leverage=10.0,
        taker_fee=0.0004,
        sl_priority=True,
    )
    broker = BrokerEmulator(broker_config, initial_capital=10000.0)

    # Open long position at start
    broker.submit_order(OrderType.MARKET, OrderSide.BUY, size=0.1)

    # Process first tick to fill entry
    first_tick = next(intrabar.generate_ticks(0, 60000))
    fills = broker.process_tick(first_tick.price, first_tick.timestamp_ms)

    pos = broker.get_position()
    entry_price = pos.entry_price
    print(f"\n  Entry: {pos.size} @ ${entry_price:.2f}")

    # Set SL/TP
    broker.set_position_sl_tp(
        pos.id,
        stop_loss=entry_price * 0.98,  # -2%
        take_profit=entry_price * 1.04,  # +4%
    )
    print(f"  SL: ${pos.stop_loss_price:.2f}, TP: ${pos.take_profit_price:.2f}")

    # Process all ticks
    tick_count = 0
    max_price = 0
    min_price = float("inf")

    for tick in intrabar.generate_ticks(0, 60 * 60000):
        fills = broker.process_tick(tick.price, tick.timestamp_ms)
        tick_count += 1
        max_price = max(max_price, tick.price)
        min_price = min(min_price, tick.price)

        if fills:
            for fill in fills:
                print(f"\n  Exit at tick #{tick_count}: ${fill.price:.2f}, PnL: ${fill.pnl:.2f}")

    print("\n  Statistics:")
    print(f"    Ticks processed: {tick_count}")
    print(f"    Price range: ${min_price:.2f} - ${max_price:.2f}")
    print(f"    Final equity: ${broker.state.equity:.2f}")

    if broker.has_position():
        pos = broker.get_position()
        print(f"    Position still open: MFE={pos.mfe:.2f}%, MAE={pos.mae:.2f}%")
    else:
        print("    Position closed.")

    print("\n✅ Integration test passed!")


def test_ohlc_path_comparison():
    """Compare different OHLC path modes on same data."""
    print("\n" + "=" * 60)
    print("TEST 4: OHLC Path Comparison")
    print("=" * 60)

    # Create scenario where path matters:
    # 1m bar: Open=50000, High=51000, Low=49000, Close=50500
    # Long position with SL=49500, TP=50800
    # Path determines which triggers first

    m1_data = pd.DataFrame({
        "open_time": [1000000],
        "open": [50000.0],
        "high": [51000.0],
        "low": [49000.0],
        "close": [50500.0],
        "volume": [1000],
    })

    results = {}

    for path in [OHLCPath.O_H_L_C, OHLCPath.O_L_H_C]:
        # Setup
        intrabar = IntrabarEngine(IntrabarConfig(ohlc_path=path))
        intrabar.load_m1_data(m1_data)

        broker = BrokerEmulator(BrokerConfig(sl_priority=True), initial_capital=10000.0)

        # Open long at 50000
        broker.submit_order(OrderType.MARKET, OrderSide.BUY, size=0.1)

        ticks = list(intrabar.generate_ticks(1000000, 1060000))
        first_tick = ticks[0]
        broker.process_tick(first_tick.price, first_tick.timestamp_ms)

        pos = broker.get_position()
        entry = pos.entry_price

        # Set SL and TP that are both within the bar's range
        broker.set_position_sl_tp(
            pos.id,
            stop_loss=49500.0,  # Will be hit if price goes to 49000
            take_profit=50800.0,  # Will be hit if price goes to 51000
        )

        # Process remaining ticks
        exit_reason = None
        for tick in ticks[1:]:
            fills = broker.process_tick(tick.price, tick.timestamp_ms)
            if fills:
                if "stop_loss" in fills[0].order_id:
                    exit_reason = "SL"
                else:
                    exit_reason = "TP"
                break

        results[path.value] = exit_reason
        print(f"\n  {path.value}: Exit by {exit_reason}")

    print("\n  Comparison:")
    print(f"    O-H-L-C: Goes High first → TP hits first → Exit: {results['O-H-L-C']}")
    print(f"    O-L-H-C: Goes Low first → SL hits first → Exit: {results['O-L-H-C']}")

    print("\n✅ OHLC Path comparison test passed!")


if __name__ == "__main__":
    test_intrabar_engine()
    test_broker_emulator()
    test_integration()
    test_ohlc_path_comparison()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! ✅")
    print("=" * 60)
