"""
Universal Math Engine v2.2 - Usage Examples.

Comprehensive examples demonstrating all features of the Universal Math Engine.
Run this file to see outputs: python -m backend.backtesting.universal_engine.examples

Author: Universal Math Engine Team
Version: 2.2.0
"""


# =============================================================================
# Example 1: Basic Order Management
# =============================================================================


def example_order_management():
    """Demonstrate order types and management."""
    print("\n" + "=" * 60)
    print("Example 1: Order Management")
    print("=" * 60)

    from backend.backtesting.universal_engine import (
        OCOConfig,
        OrderManager,
        OrderSide,
        TrailingStopConfig,
    )

    manager = OrderManager()

    # Create different order types
    print("\n1. Creating orders...")

    # Limit order
    limit_order = manager.create_limit_order(
        side=OrderSide.BUY, size=0.1, price=49500.0, time_in_force="GTC"
    )
    print(f"   Limit Order: {limit_order.order_id} - BUY 0.1 @ $49,500")

    # Stop order
    stop_order = manager.create_stop_order(
        side=OrderSide.SELL, size=0.1, stop_price=48000.0
    )
    print(f"   Stop Order: {stop_order.order_id} - SELL 0.1 @ stop $48,000")

    # Trailing stop
    trailing = manager.create_trailing_stop(
        side=OrderSide.SELL,
        size=0.1,
        config=TrailingStopConfig(trail_percent=0.02),
        current_price=50000.0,
    )
    print(
        f"   Trailing Stop: {trailing.order_id} - 2% trail from $50,000 "
        f"(stop at ${trailing.stop_price:,.2f})"
    )

    # OCO order
    _tp_order, _sl_order = manager.create_oco_order(
        side=OrderSide.SELL,
        size=0.1,
        config=OCOConfig(take_profit_price=55000.0, stop_loss_price=47000.0),
    )
    print("   OCO Orders: TP @ $55,000, SL @ $47,000")

    # Simulate price movement
    print("\n2. Processing price bars...")
    bars = [
        {"high": 50500, "low": 49400, "close": 49800},  # Limit fills
        {"high": 51000, "low": 50200, "close": 50800},  # Price rises
        {"high": 51500, "low": 50500, "close": 51200},  # Trailing updates
    ]

    for i, bar in enumerate(bars):
        filled = manager.process_bar(
            high=bar["high"], low=bar["low"], close=bar["close"], timestamp=i * 60000
        )
        print(f"   Bar {i + 1}: H={bar['high']}, L={bar['low']}, C={bar['close']}")

        for order in filled:
            print(f"      → Filled: {order.order_id} @ ${order.filled_price:,.2f}")

        # Check trailing stop update
        for o in manager.pending_orders:
            if o.order_id == trailing.order_id:
                print(f"      → Trailing stop updated to ${o.stop_price:,.2f}")

    print(f"\n   Pending orders: {len(manager.pending_orders)}")
    print(f"   Filled orders: {len(manager.filled_orders)}")


# =============================================================================
# Example 2: Risk Management
# =============================================================================


def example_risk_management():
    """Demonstrate risk management features."""
    print("\n" + "=" * 60)
    print("Example 2: Risk Management")
    print("=" * 60)

    from backend.backtesting.universal_engine import (
        BreakEvenConfig,
        DrawdownGuardianConfig,
        RiskManagement,
        RiskPerTradeConfig,
    )

    risk_mgr = RiskManagement(
        break_even_config=BreakEvenConfig(activation_profit=0.01, offset=0.001),
        risk_per_trade_config=RiskPerTradeConfig(
            max_risk_percent=0.02,
            min_risk_reward=1.5,
            use_kelly=True,
            kelly_fraction=0.5,
        ),
        drawdown_config=DrawdownGuardianConfig(
            max_drawdown=0.1, max_consecutive_losses=5
        ),
    )

    # Position sizing
    print("\n1. Position Sizing (Kelly + Risk-per-Trade)...")
    size, reason = risk_mgr.calculate_position_size(
        equity=100000,
        entry_price=50000,
        stop_price=49000,  # 2% risk
        take_profit_price=53000,  # 6% reward = 3:1 R:R
        win_rate=0.55,
    )
    print("   Equity: $100,000")
    print("   Entry: $50,000, Stop: $49,000, TP: $53,000")
    print("   Win Rate: 55%")
    print(f"   → Position Size: ${size:,.2f}")
    print(f"   → Reason: {reason}")

    # Break-even stop
    print("\n2. Break-Even Stop...")
    for price in [50000, 50300, 50600, 50800]:
        new_stop = risk_mgr.check_break_even(
            entry_price=50000, current_price=price, is_long=True, current_stop=49000
        )
        profit_pct = (price - 50000) / 50000 * 100
        if new_stop:
            print(
                f"   Price ${price:,} (+{profit_pct:.1f}%) → "
                f"Break-even stop activated: ${new_stop:,.2f}"
            )
        else:
            print(f"   Price ${price:,} (+{profit_pct:.1f}%) → No change")

    # Drawdown guardian
    print("\n3. Drawdown Guardian...")
    risk_mgr.reset_all(equity=100000)

    scenarios = [
        (98000, -500, "Small loss"),
        (96000, -800, "Another loss"),
        (93000, -1200, "Third loss"),
        (90000, -1500, "Fourth loss"),
        (87000, -2000, "Fifth loss"),
    ]

    for equity, pnl, desc in scenarios:
        action = risk_mgr.check_drawdown_guardian(
            current_equity=equity, last_trade_pnl=pnl, current_bar=10
        )
        dd = (100000 - equity) / 100000 * 100
        print(f"   {desc}: Equity ${equity:,} (DD: {dd:.1f}%) → {action.action}")
        if action.action != "allow":
            print(f"      Reason: {action.reason}")


# =============================================================================
# Example 3: Trading Filters
# =============================================================================


def example_trading_filters():
    """Demonstrate trading filters."""
    print("\n" + "=" * 60)
    print("Example 3: Trading Filters")
    print("=" * 60)

    from backend.backtesting.universal_engine import (
        CooldownConfig,
        NewsFilterConfig,
        SessionFilterConfig,
        TradingFilters,
        TradingSession,
    )

    filters = TradingFilters(
        session_config=SessionFilterConfig(
            allowed_sessions=[TradingSession.EUROPE, TradingSession.US],
            blocked_hours=[0, 1, 2],
        ),
        news_config=NewsFilterConfig(
            minutes_before=30, minutes_after=15, filter_impact=["high"]
        ),
        cooldown_config=CooldownConfig(cooldown_after_loss=3, max_trades_per_day=10),
    )

    # Load news events
    base_time = 1706400000000  # Some timestamp
    filters.load_news_events(
        [
            {
                "timestamp": base_time + 3600000,  # 1 hour later
                "title": "FOMC Meeting",
                "impact": "high",
                "currency": "USD",
            },
        ]
    )

    print("\n1. Session Filter...")
    # Convert timestamp to hour for testing
    test_times = [
        (base_time, "00:00 UTC (Asia)"),
        (base_time + 8 * 3600000, "08:00 UTC (Europe open)"),
        (base_time + 14 * 3600000, "14:00 UTC (EU/US overlap)"),
        (base_time + 20 * 3600000, "20:00 UTC (US session)"),
    ]

    for ts, desc in test_times:
        allowed, reason = filters.check_session(ts)
        status = "✓" if allowed else "✗"
        print(f"   {status} {desc}: {reason}")

    print("\n2. News Filter...")
    test_times = [
        (base_time, "1 hour before FOMC"),
        (base_time + 2400000, "40 min before FOMC"),  # Within 30 min
        (base_time + 3600000, "During FOMC"),
        (base_time + 4500000, "15 min after FOMC"),  # Within 15 min
        (base_time + 5400000, "30 min after FOMC"),
    ]

    for ts, desc in test_times:
        allowed, reason = filters.check_news(ts)
        status = "✓" if allowed else "✗"
        print(f"   {status} {desc}: {reason}")

    print("\n3. Cooldown Filter...")
    # Simulate losing trades
    for i in range(3):
        filters.record_trade(bar=i, pnl=-100, day=1)
        allowed, reason = filters.check_cooldown(current_bar=i + 1)
        status = "✓" if allowed else "✗"
        print(f"   After trade {i + 1} (loss): {status} - {reason}")


# =============================================================================
# Example 4: Spread Simulation
# =============================================================================


def example_spread_simulation():
    """Demonstrate spread simulation."""
    print("\n" + "=" * 60)
    print("Example 4: Spread Simulation")
    print("=" * 60)

    from backend.backtesting.universal_engine import SpreadConfig, SpreadSimulator

    simulator = SpreadSimulator(
        SpreadConfig(
            base_spread=0.0001,  # 0.01%
            volatility_multiplier=2.0,
            low_volume_multiplier=1.5,
            low_volume_threshold=0.5,
            max_spread=0.005,
        )
    )
    simulator.set_average_volume(1000000)

    print("\n1. Spread under different conditions...")
    scenarios = [
        (50000, 0.01, 1000000, "Normal (1% vol, avg volume)"),
        (50000, 0.01, 300000, "Low volume (30% of avg)"),
        (50000, 0.05, 1000000, "High volatility (5%)"),
        (50000, 0.05, 300000, "High vol + Low volume"),
    ]

    for mid_price, volatility, volume, desc in scenarios:
        bid, ask = simulator.calculate_spread(mid_price, volatility, volume)
        spread_pct = (ask - bid) / mid_price * 100
        print(f"\n   {desc}:")
        print(f"      Bid: ${bid:,.2f} | Ask: ${ask:,.2f}")
        print(f"      Spread: ${ask - bid:.2f} ({spread_pct:.4f}%)")

    print("\n2. Execution prices...")
    exec_buy = simulator.get_execution_price(50000, is_buy=True, volatility=0.02)
    exec_sell = simulator.get_execution_price(50000, is_buy=False, volatility=0.02)
    print("   Mid price: $50,000")
    print(f"   Buy execution: ${exec_buy:,.2f} (pay spread)")
    print(f"   Sell execution: ${exec_sell:,.2f} (pay spread)")


# =============================================================================
# Example 5: Position Tracking
# =============================================================================


def example_position_tracking():
    """Demonstrate position age tracking."""
    print("\n" + "=" * 60)
    print("Example 5: Position Age Tracking")
    print("=" * 60)

    from backend.backtesting.universal_engine import PositionTracker

    tracker = PositionTracker()

    # Open position
    print("\n1. Opening long position...")
    tracker.open_position(
        entry_bar=0,
        entry_timestamp=1706400000000,
        entry_price=50000,
        is_long=True,
        size=1.0,
    )
    print("   Entry: $50,000 (1 BTC long)")

    # Simulate price path
    print("\n2. Simulating price movement...")
    prices = [50200, 50800, 51200, 50500, 50900, 51500, 51000, 50600, 51200, 50800]

    for i, price in enumerate(prices):
        unrealized = tracker.update(current_bar=i + 1, current_price=price)
        pnl_pct = (price - 50000) / 50000 * 100
        print(f"   Bar {i + 1}: ${price:,} → PnL: ${unrealized:,.2f} ({pnl_pct:+.2f}%)")

    # Close position
    print("\n3. Closing position...")
    metrics = tracker.close_position(exit_bar=10, exit_timestamp=1706400000000 + 600000)

    print("\n   Position Age Metrics:")
    print(f"   ├─ Duration: {metrics.duration_bars} bars")
    print(f"   ├─ Time to max profit: bar {metrics.time_to_max_profit_bars}")
    print(f"   ├─ Max unrealized profit: ${metrics.max_unrealized_profit:,.2f}")
    print(f"   ├─ Max unrealized loss: ${metrics.max_unrealized_loss:,.2f}")
    print(f"   ├─ Average unrealized PnL: ${metrics.average_unrealized_pnl:,.2f}")
    print(f"   ├─ Bars in profit: {metrics.bars_in_profit}")
    print(f"   └─ Bars in loss: {metrics.bars_in_loss}")


# =============================================================================
# Example 6: Realistic Bar Simulation
# =============================================================================


def example_bar_simulation():
    """Demonstrate realistic bar simulation."""
    print("\n" + "=" * 60)
    print("Example 6: Realistic Bar Simulation")
    print("=" * 60)

    from backend.backtesting.universal_engine import (
        BarPathType,
        BarSimulatorConfig,
        RealisticBarSimulator,
    )

    simulator = RealisticBarSimulator(
        BarSimulatorConfig(
            ticks_per_bar=50,
            path_type=BarPathType.RANDOM_WALK,
            stop_hunt_probability=0.2,
            stop_hunt_depth=0.003,
            seed=42,
        )
    )

    print("\n1. Simulating bar path...")
    path = simulator.simulate_bar_path(
        open_price=50000, high_price=50500, low_price=49700, close_price=50300
    )

    print("   Bar: O=$50,000 H=$50,500 L=$49,700 C=$50,300")
    print(f"   Generated {len(path)} ticks")
    print(f"   Path range: ${min(path):,.2f} - ${max(path):,.2f}")

    # Show first and last few ticks
    print(f"   First 5 ticks: {[f'${p:,.0f}' for p in path[:5]]}")
    print(f"   Last 5 ticks: {[f'${p:,.0f}' for p in path[-5:]]}")

    print("\n2. Stop-loss trigger detection...")
    test_stops = [49800, 49700, 49600]

    for stop in test_stops:
        triggered, tick_idx, _exec_price = simulator.check_stop_triggered(
            path=path, stop_price=stop, is_long=True
        )
        if triggered:
            print(f"   Stop $49,{stop % 1000}: ✓ Triggered at tick {tick_idx}")
        else:
            print(f"   Stop $49,{stop % 1000}: ✗ Not triggered")


# =============================================================================
# Example 7: Liquidation Engine
# =============================================================================


def example_liquidation():
    """Demonstrate liquidation engine."""
    print("\n" + "=" * 60)
    print("Example 7: Liquidation Engine")
    print("=" * 60)

    from backend.backtesting.universal_engine import (
        LiquidationConfig,
        LiquidationEngine,
    )

    engine = LiquidationEngine(
        LiquidationConfig(
            maintenance_margin_rate=0.005,  # 0.5%
            liquidation_fee_rate=0.0006,  # 0.06%
        )
    )

    print("\n1. Liquidation prices at different leverages...")
    for leverage in [5, 10, 20, 50, 100]:
        liq_long, _bank_long = engine.calculate_liquidation_price(
            entry_price=50000, leverage=leverage, is_long=True
        )
        liq_short, _bank_short = engine.calculate_liquidation_price(
            entry_price=50000, leverage=leverage, is_long=False
        )
        print(
            f"   {leverage}x: Long liq ${liq_long:,.0f} | Short liq ${liq_short:,.0f}"
        )

    print("\n2. Position monitoring (10x long)...")
    entry = 50000
    leverage = 10
    size = 1.0  # 1 BTC
    wallet = 5000  # Initial margin for 10x

    prices = [49000, 48000, 47000, 46000, 45500, 45000]

    for price in prices:
        result = engine.check_liquidation(
            entry_price=entry,
            current_price=price,
            leverage=leverage,
            is_long=True,
            position_size=size,
            wallet_balance=wallet,
        )
        loss_pct = (entry - price) / entry * 100
        status = "❌ LIQUIDATED" if result.is_liquidated else "✓ Safe"
        print(
            f"   Price ${price:,} ({loss_pct:.1f}% loss): {status} "
            f"| Margin ratio: {result.margin_ratio:.1%}"
        )

        if result.is_liquidated:
            loss = engine.calculate_liquidation_loss(
                entry, result.liquidation_price, size, True
            )
            print(f"      Total loss: ${abs(loss):,.2f}")
            break


# =============================================================================
# Example 8: Volume Slippage Model
# =============================================================================


def example_volume_slippage():
    """Demonstrate volume-based slippage."""
    print("\n" + "=" * 60)
    print("Example 8: Volume Slippage Model")
    print("=" * 60)

    from backend.backtesting.universal_engine import (
        VolumeSlippageConfig,
        VolumeSlippageModel,
    )

    model = VolumeSlippageModel(
        VolumeSlippageConfig(
            base_slippage=0.0001, volume_exponent=0.5, max_slippage=0.01
        )
    )

    print("\n1. Slippage by order size...")
    bar_volume = 1000000  # $1M volume

    for order_size in [1000, 10000, 50000, 100000, 500000]:
        slippage = model.calculate_slippage(order_size, bar_volume, volatility=0.01)
        print(
            f"   ${order_size:>7,} order: {slippage:.4%} slippage "
            f"(${order_size * slippage:.2f} cost)"
        )

    print("\n2. Market impact analysis for large order...")
    impact = model.estimate_market_impact(
        order_size_usd=500000, average_volume_usd=1000000, n_bars_to_execute=10
    )

    print("   Order: $500,000 | Avg Volume: $1,000,000")
    print(f"   Single execution slippage: {impact['single_execution_slippage']:.4%}")
    print(f"   TWAP (10 bars) slippage: {impact['split_execution_slippage']:.4%}")
    print(f"   Savings from TWAP: {impact['savings_from_split']:.4%}")
    print(f"   Recommended chunks: {impact['recommended_chunks']}")


# =============================================================================
# Run All Examples
# =============================================================================


def run_all_examples():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("UNIVERSAL MATH ENGINE v2.2 - EXAMPLES")
    print("=" * 60)

    example_order_management()
    example_risk_management()
    example_trading_filters()
    example_spread_simulation()
    example_position_tracking()
    example_bar_simulation()
    example_liquidation()
    example_volume_slippage()

    print("\n" + "=" * 60)
    print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_all_examples()
