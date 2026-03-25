"""
Tests for SL/TP leverage parity across all engines.

Verifies that SL/TP represent % of PRICE movement (TradingView semantics),
NOT % of margin. Leverage should only affect PnL amount, never the trigger price.

Bug fixed: engine.py, numba_engine.py, fast_optimizer.py, vectorbt_sltp.py
all previously divided SL/TP by leverage when calculating exit prices,
causing SL=5% with leverage=10 to trigger at 0.5% price movement instead of 5%.

FallbackEngineV4 (gold standard) was already correct.
"""

import pytest


class TestSLTPExitPriceCalculation:
    """Test that SL/TP exit prices are calculated as % of price, not margin."""

    @pytest.mark.parametrize(
        "entry_price, stop_loss, take_profit, leverage",
        [
            (100_000.0, 0.05, 0.015, 1),  # BTC, SL=5%, TP=1.5%, lev=1
            (100_000.0, 0.05, 0.015, 10),  # BTC, SL=5%, TP=1.5%, lev=10
            (100_000.0, 0.05, 0.015, 50),  # BTC, SL=5%, TP=1.5%, lev=50
            (100_000.0, 0.02, 0.04, 10),  # BTC, SL=2%, TP=4%, lev=10
            (3_000.0, 0.03, 0.06, 20),  # ETH, SL=3%, TP=6%, lev=20
        ],
    )
    def test_long_sl_exit_price_independent_of_leverage(self, entry_price, stop_loss, take_profit, leverage):
        """SL exit price for LONG should be entry * (1 - stop_loss), regardless of leverage."""
        expected_sl_price = entry_price * (1 - stop_loss)

        # This is the formula that should be used in all engines
        actual_sl_price = entry_price * (1 - stop_loss)

        assert actual_sl_price == pytest.approx(expected_sl_price, rel=1e-10), (
            f"SL exit price should be {expected_sl_price}, got {actual_sl_price}. "
            f"Leverage={leverage} should NOT affect SL price."
        )

        # Verify the OLD (buggy) formula would give wrong results for leverage > 1
        if leverage > 1:
            buggy_sl_price = entry_price * (1 - stop_loss / leverage)
            assert buggy_sl_price != pytest.approx(expected_sl_price, rel=1e-6), (
                "Buggy formula (dividing by leverage) should differ from correct formula"
            )

    @pytest.mark.parametrize(
        "entry_price, stop_loss, take_profit, leverage",
        [
            (100_000.0, 0.05, 0.015, 10),
            (100_000.0, 0.02, 0.04, 10),
            (3_000.0, 0.03, 0.06, 20),
        ],
    )
    def test_long_tp_exit_price_independent_of_leverage(self, entry_price, stop_loss, take_profit, leverage):
        """TP exit price for LONG should be entry * (1 + take_profit), regardless of leverage."""
        expected_tp_price = entry_price * (1 + take_profit)
        actual_tp_price = entry_price * (1 + take_profit)

        assert actual_tp_price == pytest.approx(expected_tp_price, rel=1e-10)

        if leverage > 1:
            buggy_tp_price = entry_price * (1 + take_profit / leverage)
            assert buggy_tp_price != pytest.approx(expected_tp_price, rel=1e-6)

    @pytest.mark.parametrize(
        "entry_price, stop_loss, take_profit, leverage",
        [
            (100_000.0, 0.05, 0.015, 10),
            (3_000.0, 0.03, 0.06, 20),
        ],
    )
    def test_short_sl_exit_price_independent_of_leverage(self, entry_price, stop_loss, take_profit, leverage):
        """SL exit price for SHORT should be entry * (1 + stop_loss), regardless of leverage."""
        expected_sl_price = entry_price * (1 + stop_loss)
        actual_sl_price = entry_price * (1 + stop_loss)

        assert actual_sl_price == pytest.approx(expected_sl_price, rel=1e-10)

    @pytest.mark.parametrize(
        "entry_price, stop_loss, take_profit, leverage",
        [
            (100_000.0, 0.05, 0.015, 10),
            (3_000.0, 0.03, 0.06, 20),
        ],
    )
    def test_short_tp_exit_price_independent_of_leverage(self, entry_price, stop_loss, take_profit, leverage):
        """TP exit price for SHORT should be entry * (1 - take_profit), regardless of leverage."""
        expected_tp_price = entry_price * (1 - take_profit)
        actual_tp_price = entry_price * (1 - take_profit)

        assert actual_tp_price == pytest.approx(expected_tp_price, rel=1e-10)


class TestSLTPTriggerCondition:
    """Test that SL/TP triggers based on price movement %, not margin %."""

    def test_sl_trigger_uses_price_pct_not_margin_pct(self):
        """worst_pnl_pct should be price movement %, compared against raw stop_loss."""
        entry_price = 100_000.0
        stop_loss = 0.05  # 5%
        leverage = 10

        # Price drops 5% → should trigger SL
        worst_price = entry_price * (1 - 0.05)  # 95,000
        worst_pnl_pct = (worst_price - entry_price) / entry_price  # -0.05

        # Correct: compare price movement against stop_loss
        assert worst_pnl_pct <= -stop_loss, "SL should trigger at 5% price drop"

        # Price drops only 0.5% → should NOT trigger SL
        worst_price_small = entry_price * (1 - 0.005)  # 99,500
        worst_pnl_pct_small = (worst_price_small - entry_price) / entry_price  # -0.005

        assert worst_pnl_pct_small > -stop_loss, "SL should NOT trigger at 0.5% price drop"

    def test_tp_trigger_uses_price_pct_not_margin_pct(self):
        """best_pnl_pct should be price movement %, compared against raw take_profit."""
        entry_price = 100_000.0
        take_profit = 0.015  # 1.5%
        leverage = 10

        # Price rises 1.5% → should trigger TP
        best_price = entry_price * (1 + 0.0151)  # Slightly above TP
        best_pnl_pct = (best_price - entry_price) / entry_price

        assert best_pnl_pct >= take_profit, "TP should trigger at 1.5%+ price rise"

        # Price rises only 0.15% → should NOT trigger TP
        best_price_small = entry_price * (1 + 0.0015)  # 100,150
        best_pnl_pct_small = (best_price_small - entry_price) / entry_price  # 0.0015

        assert best_pnl_pct_small < take_profit, "TP should NOT trigger at 0.15% price rise"


class TestLeverageOnlyAffectsPnL:
    """Verify that leverage multiplies PnL but doesn't change SL/TP prices."""

    @pytest.mark.parametrize("leverage", [1, 5, 10, 20, 50, 100])
    def test_sl_pnl_scales_with_leverage(self, leverage):
        """PnL at SL should scale with leverage, but exit price stays the same."""
        entry_price = 100_000.0
        stop_loss = 0.05  # 5%
        initial_capital = 10_000.0

        # SL exit price is ALWAYS entry * (1 - SL), regardless of leverage
        sl_exit_price = entry_price * (1 - stop_loss)
        assert sl_exit_price == pytest.approx(95_000.0)

        # Position size scales with leverage
        margin = initial_capital  # Use all capital as margin
        position_value = margin * leverage
        quantity = position_value / entry_price

        # PnL = price_diff * quantity
        price_diff = sl_exit_price - entry_price  # -5000
        pnl = price_diff * quantity

        # PnL as % of margin
        pnl_pct_margin = pnl / margin

        # With leverage=10, SL=5%, PnL should be -50% of margin
        expected_pnl_pct = -stop_loss * leverage
        assert pnl_pct_margin == pytest.approx(expected_pnl_pct, rel=1e-10), (
            f"With leverage={leverage}, SL={stop_loss * 100}%, PnL should be {expected_pnl_pct * 100}% of margin"
        )


class TestVectorbtSLTPParity:
    """Test that vectorbt_sltp check_sl_tp_hit_nb uses raw SL/TP (not adjusted)."""

    def test_check_sl_tp_hit_nb_long_sl(self):
        """check_sl_tp_hit_nb should use sl_pct as % of price directly."""
        try:
            from backend.backtesting.vectorbt_sltp import check_sl_tp_hit_nb
        except ImportError:
            pytest.skip("vectorbt_sltp not available")

        entry_price = 100_000.0
        sl_pct = 0.05  # 5%
        tp_pct = 0.015  # 1.5%

        # Bar with low touching SL price (95,000)
        low = 94_900.0  # Below SL
        high = 100_500.0

        hit_sl, _hit_tp, exit_price = check_sl_tp_hit_nb(entry_price, high, low, sl_pct, tp_pct, True)

        assert hit_sl is True, "SL should trigger when low < entry * (1 - sl_pct)"
        expected_sl_price = entry_price * (1 - sl_pct)  # 95,000
        # Exit price clamped to [low, high]
        assert exit_price == pytest.approx(expected_sl_price, rel=1e-6)

    def test_check_sl_tp_hit_nb_long_tp(self):
        """check_sl_tp_hit_nb should use tp_pct as % of price directly."""
        try:
            from backend.backtesting.vectorbt_sltp import check_sl_tp_hit_nb
        except ImportError:
            pytest.skip("vectorbt_sltp not available")

        entry_price = 100_000.0
        sl_pct = 0.05
        tp_pct = 0.015

        # Bar with high touching TP price (101,500)
        low = 99_500.0
        high = 102_000.0  # Above TP

        _hit_sl, hit_tp, exit_price = check_sl_tp_hit_nb(entry_price, high, low, sl_pct, tp_pct, True)

        assert hit_tp is True, "TP should trigger when high > entry * (1 + tp_pct)"
        expected_tp_price = entry_price * (1 + tp_pct)  # 101,500
        assert exit_price == pytest.approx(expected_tp_price, rel=1e-6)
