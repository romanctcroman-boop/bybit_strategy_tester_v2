"""
Tests for Universal Math Engine v2.2 - Trading Enhancements Module.

Tests cover:
1. Order Types: Limit, Stop, Trailing Stop, OCO
2. Risk Management: Anti-Liquidation, Break-even, Risk-per-Trade, Drawdown Guardian
3. Trading Filters: Session, News, Cooldown
4. Market Simulation: Spread, Position Aging
"""


from backend.backtesting.universal_engine import (
    # Risk Management
    AntiLiquidationConfig,
    BreakEvenConfig,
    CooldownConfig,
    DrawdownGuardianConfig,
    NewsFilterConfig,
    OCOConfig,
    OrderManager,
    OrderSide,
    OrderStatus,
    # Order Types
    OrderType,
    PositionTracker,
    RiskManagement,
    RiskPerTradeConfig,
    SessionFilterConfig,
    # Market Simulation
    SpreadConfig,
    SpreadSimulator,
    TradingFilters,
    # Trading Filters
    TradingSession,
    TrailingStopConfig,
)

# =============================================================================
# 1. ORDER TYPES TESTS
# =============================================================================


class TestOrderManager:
    """Tests for OrderManager."""

    def test_create_market_order(self):
        """Test market order creation."""
        manager = OrderManager()
        order = manager.create_market_order(OrderSide.BUY, size=1.0)

        assert order.order_type == OrderType.MARKET
        assert order.side == OrderSide.BUY
        assert order.size == 1.0
        assert order.status == OrderStatus.PENDING

    def test_create_limit_order(self):
        """Test limit order creation."""
        manager = OrderManager()
        order = manager.create_limit_order(side=OrderSide.BUY, size=1.0, price=49000.0)

        assert order.order_type == OrderType.LIMIT
        assert order.price == 49000.0
        assert len(manager.pending_orders) == 1

    def test_create_stop_order(self):
        """Test stop-market order creation."""
        manager = OrderManager()
        order = manager.create_stop_order(
            side=OrderSide.SELL, size=1.0, stop_price=48000.0
        )

        assert order.order_type == OrderType.STOP_MARKET
        assert order.stop_price == 48000.0

    def test_create_stop_limit_order(self):
        """Test stop-limit order creation."""
        manager = OrderManager()
        order = manager.create_stop_order(
            side=OrderSide.SELL,
            size=1.0,
            stop_price=48000.0,
            limit_price=47900.0,
        )

        assert order.order_type == OrderType.STOP_LIMIT
        assert order.stop_price == 48000.0
        assert order.price == 47900.0

    def test_trailing_stop_creation(self):
        """Test trailing stop order creation."""
        manager = OrderManager()
        config = TrailingStopConfig(trail_percent=0.02)
        order = manager.create_trailing_stop(
            side=OrderSide.SELL,
            size=1.0,
            config=config,
            current_price=50000.0,
        )

        assert order.order_type == OrderType.TRAILING_STOP
        assert order.trailing_delta == 0.02
        # Initial stop = 50000 * (1 - 0.02) = 49000
        assert abs(order.stop_price - 49000.0) < 1.0

    def test_limit_order_fill(self):
        """Test limit order fill on price touch."""
        manager = OrderManager()
        manager.create_limit_order(side=OrderSide.BUY, size=1.0, price=49000.0)

        # Bar touches limit price
        filled = manager.process_bar(
            high=50100.0, low=48900.0, close=49500.0, timestamp=1000
        )

        assert len(filled) == 1
        assert filled[0].status == OrderStatus.FILLED
        assert filled[0].filled_price == 49000.0

    def test_limit_order_no_fill(self):
        """Test limit order not filled when price doesn't reach."""
        manager = OrderManager()
        manager.create_limit_order(side=OrderSide.BUY, size=1.0, price=48000.0)

        # Bar doesn't touch limit
        filled = manager.process_bar(
            high=50100.0, low=49000.0, close=49500.0, timestamp=1000
        )

        assert len(filled) == 0
        assert len(manager.pending_orders) == 1

    def test_stop_order_trigger(self):
        """Test stop order trigger on price breach."""
        manager = OrderManager()
        manager.create_stop_order(side=OrderSide.SELL, size=1.0, stop_price=49000.0)

        # Bar breaches stop
        filled = manager.process_bar(
            high=50000.0, low=48500.0, close=48800.0, timestamp=1000
        )

        assert len(filled) == 1
        assert filled[0].filled_price == 49000.0

    def test_trailing_stop_update(self):
        """Test trailing stop updates with new highs."""
        manager = OrderManager()
        config = TrailingStopConfig(trail_percent=0.02)
        order = manager.create_trailing_stop(
            side=OrderSide.SELL,
            size=1.0,
            config=config,
            current_price=50000.0,
        )

        initial_stop = order.stop_price

        # Price moves higher
        manager.process_bar(high=52000.0, low=51000.0, close=51500.0, timestamp=1000)

        # Stop should have moved up
        assert order.stop_price > initial_stop
        # New stop = 52000 * (1 - 0.02) = 50960
        assert abs(order.stop_price - 50960.0) < 1.0

    def test_trailing_stop_trigger(self):
        """Test trailing stop trigger after price reversal."""
        manager = OrderManager()
        config = TrailingStopConfig(trail_percent=0.02)
        manager.create_trailing_stop(
            side=OrderSide.SELL,
            size=1.0,
            config=config,
            current_price=50000.0,
        )

        # Price moves up
        manager.process_bar(high=52000.0, low=51000.0, close=51500.0, timestamp=1000)

        # Price drops and triggers stop (stop ~50960)
        filled = manager.process_bar(
            high=51200.0, low=50800.0, close=50900.0, timestamp=2000
        )

        assert len(filled) == 1

    def test_oco_order(self):
        """Test OCO order creation."""
        manager = OrderManager()
        config = OCOConfig(take_profit_price=52000.0, stop_loss_price=48000.0)

        tp, sl = manager.create_oco_order(side=OrderSide.SELL, size=1.0, config=config)

        assert tp.order_type == OrderType.OCO
        assert sl.order_type == OrderType.OCO
        assert len(manager.pending_orders) == 2

    def test_cancel_order(self):
        """Test order cancellation."""
        manager = OrderManager()
        order = manager.create_limit_order(side=OrderSide.BUY, size=1.0, price=49000.0)

        result = manager.cancel_order(order.order_id)

        assert result is True
        assert len(manager.pending_orders) == 0
        assert order.status == OrderStatus.CANCELLED


# =============================================================================
# 2. RISK MANAGEMENT TESTS
# =============================================================================


class TestRiskManagement:
    """Tests for RiskManagement."""

    def test_anti_liquidation_safe(self):
        """Test anti-liquidation check when safe."""
        config = AntiLiquidationConfig(trigger_margin_ratio=0.7)
        rm = RiskManagement(anti_liq_config=config)

        result = rm.check_anti_liquidation(
            margin_ratio=0.3, position_size=1.0, unrealized_pnl=-100
        )

        assert result.action == "allow"

    def test_anti_liquidation_trigger(self):
        """Test anti-liquidation trigger."""
        config = AntiLiquidationConfig(trigger_margin_ratio=0.7, reduce_percent=0.25)
        rm = RiskManagement(anti_liq_config=config)

        result = rm.check_anti_liquidation(
            margin_ratio=0.8, position_size=1.0, unrealized_pnl=-500
        )

        assert result.action == "reduce"
        assert result.suggested_size == 0.25

    def test_break_even_not_triggered(self):
        """Test break-even stop not triggered when profit too small."""
        config = BreakEvenConfig(activation_profit=0.02)
        rm = RiskManagement(break_even_config=config)

        # Only 1% profit
        new_stop = rm.check_break_even(
            entry_price=50000.0,
            current_price=50500.0,
            is_long=True,
            current_stop=49000.0,
        )

        assert new_stop is None

    def test_break_even_triggered_long(self):
        """Test break-even stop triggered for long position."""
        config = BreakEvenConfig(
            activation_profit=0.02, offset=0.001, min_bars_in_profit=1
        )
        rm = RiskManagement(break_even_config=config)

        # 3% profit
        new_stop = rm.check_break_even(
            entry_price=50000.0,
            current_price=51500.0,
            is_long=True,
            current_stop=49000.0,
        )

        assert new_stop is not None
        # Break-even stop = 50000 * 1.001 = 50050
        assert abs(new_stop - 50050.0) < 1.0

    def test_break_even_triggered_short(self):
        """Test break-even stop triggered for short position."""
        config = BreakEvenConfig(
            activation_profit=0.02, offset=0.001, min_bars_in_profit=1
        )
        rm = RiskManagement(break_even_config=config)

        # 3% profit on short
        new_stop = rm.check_break_even(
            entry_price=50000.0,
            current_price=48500.0,
            is_long=False,
            current_stop=51000.0,
        )

        assert new_stop is not None
        # Break-even stop = 50000 * 0.999 = 49950
        assert abs(new_stop - 49950.0) < 1.0

    def test_position_size_calculation(self):
        """Test position size calculation from risk."""
        config = RiskPerTradeConfig(max_risk_percent=0.02, max_position_percent=0.1)
        rm = RiskManagement(risk_per_trade_config=config)

        size, reason = rm.calculate_position_size(
            equity=10000.0,
            entry_price=50000.0,
            stop_price=49000.0,  # 2% stop
        )

        # Risk = 2% of 10000 = 200
        # Risk per unit = 2% = 0.02
        # Position = 200 / 0.02 = 10000 USD
        # But max position = 10% of 10000 = 1000 USD
        assert size == 1000.0

    def test_position_size_with_kelly(self):
        """Test Kelly criterion position sizing."""
        config = RiskPerTradeConfig(
            max_risk_percent=0.1, use_kelly=True, kelly_fraction=0.5
        )
        rm = RiskManagement(risk_per_trade_config=config)

        size, reason = rm.calculate_position_size(
            equity=10000.0,
            entry_price=50000.0,
            stop_price=49000.0,
            take_profit_price=52000.0,
            win_rate=0.6,
        )

        assert size > 0
        assert size <= 10000.0

    def test_risk_reward_check(self):
        """Test minimum risk-reward ratio check."""
        config = RiskPerTradeConfig(min_risk_reward=2.0)
        rm = RiskManagement(risk_per_trade_config=config)

        # Bad R:R (1:1)
        size, reason = rm.calculate_position_size(
            equity=10000.0,
            entry_price=50000.0,
            stop_price=49000.0,
            take_profit_price=51000.0,
        )

        assert size == 0.0
        assert "R:R ratio" in reason

    def test_drawdown_guardian_safe(self):
        """Test drawdown guardian when within limits."""
        config = DrawdownGuardianConfig(max_drawdown=0.1)
        rm = RiskManagement(drawdown_config=config)
        rm.peak_equity = 10000.0

        result = rm.check_drawdown_guardian(current_equity=9500.0)

        assert result.action == "allow"

    def test_drawdown_guardian_trigger(self):
        """Test drawdown guardian trigger."""
        config = DrawdownGuardianConfig(max_drawdown=0.1, pause_bars=24)
        rm = RiskManagement(drawdown_config=config)
        rm.peak_equity = 10000.0

        result = rm.check_drawdown_guardian(current_equity=8900.0, current_bar=100)

        assert result.action == "pause"
        assert result.pause_until_bar == 124

    def test_consecutive_losses_pause(self):
        """Test pause after consecutive losses."""
        config = DrawdownGuardianConfig(max_consecutive_losses=3, pause_bars=10)
        rm = RiskManagement(drawdown_config=config)
        rm.peak_equity = 10000.0

        # Record losses
        rm.check_drawdown_guardian(10000.0, last_trade_pnl=-100)
        rm.check_drawdown_guardian(9900.0, last_trade_pnl=-100)
        result = rm.check_drawdown_guardian(9800.0, last_trade_pnl=-100, current_bar=50)

        assert result.action == "pause"
        assert rm.consecutive_losses == 3


# =============================================================================
# 3. TRADING FILTERS TESTS
# =============================================================================


class TestTradingFilters:
    """Tests for TradingFilters."""

    def test_session_filter_allowed(self):
        """Test session filter allows trading during EU session."""
        config = SessionFilterConfig(
            allowed_sessions=[TradingSession.EUROPE],
            europe_start=8,
            europe_end=16,
        )
        filters = TradingFilters(session_config=config)

        # 10:00 UTC (in EU session)
        timestamp = 10 * 3600 * 1000  # 10:00 in ms

        allowed, reason = filters.check_session(timestamp)

        assert allowed is True
        assert "europe" in reason.lower()

    def test_session_filter_blocked(self):
        """Test session filter blocks trading outside sessions."""
        config = SessionFilterConfig(
            allowed_sessions=[TradingSession.EUROPE],
            europe_start=8,
            europe_end=16,
        )
        filters = TradingFilters(session_config=config)

        # 03:00 UTC (Asia session, not allowed)
        timestamp = 3 * 3600 * 1000

        allowed, reason = filters.check_session(timestamp)

        assert allowed is False

    def test_blocked_hours(self):
        """Test specific blocked hours."""
        config = SessionFilterConfig(
            allowed_sessions=[TradingSession.EUROPE, TradingSession.US],
            blocked_hours=[14, 15],  # Block during overlap
        )
        filters = TradingFilters(session_config=config)

        # 14:00 UTC (blocked)
        timestamp = 14 * 3600 * 1000

        allowed, reason = filters.check_session(timestamp)

        assert allowed is False
        assert "blocked" in reason.lower()

    def test_news_filter_no_events(self):
        """Test news filter when no events."""
        filters = TradingFilters()

        allowed, reason = filters.check_news(timestamp=1000000)

        assert allowed is True

    def test_news_filter_high_impact(self):
        """Test news filter blocks during high impact news."""
        config = NewsFilterConfig(
            minutes_before=30, minutes_after=30, filter_impact=["high"]
        )
        filters = TradingFilters(news_config=config)

        # Add news event
        filters.load_news_events(
            [
                {
                    "timestamp": 1000000,
                    "title": "FOMC",
                    "impact": "high",
                    "currency": "USD",
                }
            ]
        )

        # 15 minutes before news
        timestamp = 1000000 - 15 * 60 * 1000

        allowed, reason = filters.check_news(timestamp)

        assert allowed is False
        assert "FOMC" in reason

    def test_news_filter_ignores_low_impact(self):
        """Test news filter ignores low impact news."""
        config = NewsFilterConfig(filter_impact=["high"])
        filters = TradingFilters(news_config=config)

        filters.load_news_events(
            [{"timestamp": 1000000, "title": "Minor data", "impact": "low"}]
        )

        # During low impact news
        allowed, reason = filters.check_news(timestamp=1000000)

        assert allowed is True

    def test_cooldown_after_loss(self):
        """Test cooldown period after losing trade."""
        config = CooldownConfig(cooldown_after_loss=5)
        filters = TradingFilters(cooldown_config=config)

        # Record a loss
        filters.record_trade(bar=100, pnl=-100, day=1)

        # Check cooldown at bar 102 (only 2 bars later)
        allowed, reason = filters.check_cooldown(current_bar=102)

        assert allowed is False
        assert "loss" in reason.lower()

    def test_cooldown_expired(self):
        """Test cooldown expires after enough bars."""
        config = CooldownConfig(cooldown_after_loss=5)
        filters = TradingFilters(cooldown_config=config)

        filters.record_trade(bar=100, pnl=-100, day=1)

        # Check after cooldown (6 bars later)
        allowed, reason = filters.check_cooldown(current_bar=106)

        assert allowed is True

    def test_max_trades_per_day(self):
        """Test daily trade limit."""
        config = CooldownConfig(max_trades_per_day=3, cooldown_after_win=0)
        filters = TradingFilters(cooldown_config=config)

        # Record 3 trades
        filters.record_trade(bar=100, pnl=100, day=1)
        filters.record_trade(bar=110, pnl=100, day=1)
        filters.record_trade(bar=120, pnl=100, day=1)

        # Try 4th trade
        allowed, reason = filters.check_cooldown(current_bar=130)

        assert allowed is False
        assert "limit" in reason.lower()

    def test_can_trade_all_checks(self):
        """Test combined can_trade check."""
        session_config = SessionFilterConfig(allowed_sessions=[TradingSession.EUROPE])
        cooldown_config = CooldownConfig(enabled=False)
        filters = TradingFilters(
            session_config=session_config, cooldown_config=cooldown_config
        )

        # 10:00 UTC, no cooldown
        timestamp = 10 * 3600 * 1000

        allowed, reasons = filters.can_trade(timestamp, current_bar=100)

        assert allowed is True
        assert len(reasons) == 0


# =============================================================================
# 4. MARKET SIMULATION TESTS
# =============================================================================


class TestSpreadSimulator:
    """Tests for SpreadSimulator."""

    def test_basic_spread(self):
        """Test basic bid-ask spread calculation."""
        config = SpreadConfig(base_spread=0.001)
        sim = SpreadSimulator(config)

        bid, ask = sim.calculate_spread(mid_price=50000.0)

        # Spread = 0.1%, half = 0.05%
        assert abs(bid - 49975.0) < 1.0
        assert abs(ask - 50025.0) < 1.0

    def test_volatility_increases_spread(self):
        """Test volatility increases spread."""
        config = SpreadConfig(base_spread=0.001, volatility_multiplier=2.0)
        sim = SpreadSimulator(config)

        bid_low_vol, ask_low_vol = sim.calculate_spread(
            mid_price=50000.0, volatility=0.0
        )
        bid_high_vol, ask_high_vol = sim.calculate_spread(
            mid_price=50000.0, volatility=0.02
        )

        spread_low = ask_low_vol - bid_low_vol
        spread_high = ask_high_vol - bid_high_vol

        assert spread_high > spread_low

    def test_low_volume_increases_spread(self):
        """Test low volume increases spread."""
        config = SpreadConfig(
            base_spread=0.001,
            low_volume_multiplier=1.5,
            low_volume_threshold=0.5,
        )
        sim = SpreadSimulator(config)
        sim.set_average_volume(1000.0)

        bid_high_vol, ask_high_vol = sim.calculate_spread(
            mid_price=50000.0, current_volume=1000.0
        )
        bid_low_vol, ask_low_vol = sim.calculate_spread(
            mid_price=50000.0, current_volume=300.0
        )

        spread_high = ask_high_vol - bid_high_vol
        spread_low = ask_low_vol - bid_low_vol

        assert spread_low > spread_high

    def test_get_execution_price_buy(self):
        """Test execution price for buy order."""
        config = SpreadConfig(base_spread=0.001)
        sim = SpreadSimulator(config)

        price = sim.get_execution_price(mid_price=50000.0, is_buy=True)

        # Buy at ask
        assert price > 50000.0

    def test_get_execution_price_sell(self):
        """Test execution price for sell order."""
        config = SpreadConfig(base_spread=0.001)
        sim = SpreadSimulator(config)

        price = sim.get_execution_price(mid_price=50000.0, is_buy=False)

        # Sell at bid
        assert price < 50000.0


class TestPositionTracker:
    """Tests for PositionTracker."""

    def test_open_position(self):
        """Test position opening."""
        tracker = PositionTracker()
        tracker.open_position(
            entry_bar=100,
            entry_timestamp=1000000,
            entry_price=50000.0,
            is_long=True,
            size=1.0,
        )

        assert tracker.entry_bar == 100
        assert tracker.entry_price == 50000.0
        assert tracker.is_long is True

    def test_update_position(self):
        """Test position update."""
        tracker = PositionTracker()
        tracker.open_position(
            entry_bar=100,
            entry_timestamp=1000000,
            entry_price=50000.0,
            is_long=True,
            size=1.0,
        )

        pnl = tracker.update(current_bar=101, current_price=50500.0)

        assert pnl == 500.0  # (50500 - 50000) * 1

    def test_close_position_metrics(self):
        """Test position close returns metrics."""
        tracker = PositionTracker()
        tracker.open_position(
            entry_bar=100,
            entry_timestamp=1000000,
            entry_price=50000.0,
            is_long=True,
            size=1.0,
        )

        # Simulate several updates
        tracker.update(101, 50500.0)  # +500 profit
        tracker.update(102, 50200.0)  # +200 profit
        tracker.update(103, 49800.0)  # -200 loss
        tracker.update(104, 50300.0)  # +300 profit

        metrics = tracker.close_position(exit_bar=105, exit_timestamp=1005000)

        assert metrics.duration_bars == 5
        assert metrics.max_unrealized_profit == 500.0
        assert metrics.max_unrealized_loss == -200.0
        assert metrics.bars_in_profit == 3
        assert metrics.bars_in_loss == 1

    def test_short_position_pnl(self):
        """Test short position PnL calculation."""
        tracker = PositionTracker()
        tracker.open_position(
            entry_bar=100,
            entry_timestamp=1000000,
            entry_price=50000.0,
            is_long=False,  # Short
            size=1.0,
        )

        pnl = tracker.update(current_bar=101, current_price=49500.0)

        assert pnl == 500.0  # (50000 - 49500) * 1


# =============================================================================
# INTEGRATION TEST
# =============================================================================


class TestTradingEnhancementsIntegration:
    """Integration tests for all v2.2 components."""

    def test_full_trading_workflow(self):
        """Test complete trading workflow with all components."""
        # 1. Initialize all managers
        order_manager = OrderManager()
        risk_manager = RiskManagement(
            anti_liq_config=AntiLiquidationConfig(trigger_margin_ratio=0.7),
            break_even_config=BreakEvenConfig(activation_profit=0.02),
            risk_per_trade_config=RiskPerTradeConfig(max_risk_percent=0.02),
            drawdown_config=DrawdownGuardianConfig(max_drawdown=0.1),
        )
        filters = TradingFilters(
            session_config=SessionFilterConfig(
                allowed_sessions=[TradingSession.EUROPE, TradingSession.US]
            ),
            cooldown_config=CooldownConfig(cooldown_after_loss=3),
        )
        spread_sim = SpreadSimulator(SpreadConfig(base_spread=0.0005))
        position_tracker = PositionTracker()

        # 2. Check if can trade (10:00 UTC)
        timestamp = 10 * 3600 * 1000
        can_trade, reasons = filters.can_trade(timestamp, current_bar=100)
        assert can_trade is True

        # 3. Calculate position size
        size, _ = risk_manager.calculate_position_size(
            equity=10000.0,
            entry_price=50000.0,
            stop_price=49000.0,
        )
        assert size > 0

        # 4. Get execution price with spread
        entry_price = spread_sim.get_execution_price(50000.0, is_buy=True)
        assert entry_price > 50000.0

        # 5. Create orders
        order_manager.create_stop_order(
            side=OrderSide.SELL, size=size, stop_price=49000.0
        )

        # 6. Track position
        position_tracker.open_position(
            entry_bar=100,
            entry_timestamp=timestamp,
            entry_price=entry_price,
            is_long=True,
            size=size / entry_price,
        )

        # 7. Simulate price movement
        position_tracker.update(101, 50500.0)

        # 8. Check break-even
        new_stop = risk_manager.check_break_even(
            entry_price=entry_price,
            current_price=51500.0,
            is_long=True,
            current_stop=49000.0,
        )
        # May or may not trigger depending on profit threshold

        # 9. Close position
        metrics = position_tracker.close_position(102, timestamp + 120000)
        assert metrics.duration_bars == 2

    def test_v22_imports(self):
        """Test that all v2.2 classes can be imported."""
        from backend.backtesting.universal_engine import (
            # Risk Management
            OrderType,
            PositionTracker,
            RiskManagement,
            SpreadSimulator,
            TradingFilters,
        )

        # All imports successful
        assert OrderType is not None
        assert RiskManagement is not None
        assert TradingFilters is not None
        assert SpreadSimulator is not None
        assert PositionTracker is not None
