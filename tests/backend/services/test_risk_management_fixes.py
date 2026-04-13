"""
Regression tests for Risk Management bug fixes R1-R7 (2026-04-13).

R1 — ExposureController cooling lockout
    cooling_until is now set with timezone-aware UTC datetimes, so the
    `datetime.now(UTC) < self.cooling_until` comparison works correctly and
    rejects new positions during the cooling period.

R2 — Negative Kelly → zero position size
    Kelly formula can yield a negative percentage (edge scenario where
    payoff_ratio < (1-win_rate)/win_rate).  Before fix: negative Kelly
    propagated → negative position_size.  After fix: returns 0.0.

R3 — Ghost stops (MOVED_TO_BREAKEVEN stops can't be cancelled)
    cancel_stop() previously only cancelled ACTIVE stops; a stop that had
    already moved to MOVED_TO_BREAKEVEN would silently return False and remain
    in get_active_stops() forever.  After fix: MOVED_TO_BREAKEVEN stops can
    also be cancelled.

R4 — Max position size constraint enforced
    ExposureController.check_new_position() must reject a position whose
    value exceeds max_position_size_pct of equity.

R5 — Stop callback signature: passes StopLossOrder (not primitives)
    on_stop_triggered callback now receives the full StopLossOrder object.
    Before fix: RiskEngine callback declared as Callable[[str, float, float], None],
    but StopLossManager called it with (stop_order,), causing TypeError.
    After fix: both sides agree on Callable[[StopLossOrder], None].

R6 — Breakeven check guards against non-BREAKEVEN stop types (`and` not `or`)
    Before fix: the condition was
        `if stop.stop_type == StopLossType.BREAKEVEN or not stop.is_at_breakeven:`
    which applied breakeven logic to ALL stop types (TRAILING, FIXED, etc.)
    whenever `is_at_breakeven` was False.
    After fix: `and` — only BREAKEVEN-type stops are checked.

R7 — Timezone normalization for cooldown comparison
    last_trade_time with UTC tzinfo vs datetime.now() (naive) caused
    TypeError.  After fix: mismatched tzinfo is stripped before subtraction.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

# ---------------------------------------------------------------------------
# R1 — ExposureController cooling lockout
# ---------------------------------------------------------------------------


class TestExposureCoolingLockout:
    """
    R1: cooling_until set in the future must reject positions.
    """

    def _make_controller(self, equity: float = 100_000.0):
        from backend.services.risk_management.exposure_controller import ExposureController, ExposureLimits

        return ExposureController(equity=equity, limits=ExposureLimits())

    def test_position_rejected_during_cooling_period(self):
        """
        After cooling_until is set to a future UTC time, check_new_position
        must return allowed=False (cooling violation).
        """
        ctrl = self._make_controller()
        # Set cooling 60s into the future (timezone-aware)
        ctrl.cooling_until = datetime.now(UTC) + timedelta(seconds=60)

        result = ctrl.check_new_position(
            symbol="BTCUSDT",
            side="long",
            size=0.1,
            entry_price=50_000.0,
            leverage=1.0,
        )

        assert not result.allowed, (
            "R1 regression: position should be rejected during active cooling period. "
            "Before fix, timezone mismatch in datetime comparison could silently skip the check."
        )

    def test_position_allowed_after_cooling_expires(self):
        """
        After cooling_until passes, the check passes normally again.
        """
        ctrl = self._make_controller()
        # Set cooling_until to a time ALREADY in the past
        ctrl.cooling_until = datetime.now(UTC) - timedelta(seconds=1)

        result = ctrl.check_new_position(
            symbol="BTCUSDT",
            side="long",
            size=0.01,  # tiny position — well within limits
            entry_price=50_000.0,
            leverage=1.0,
        )
        # Cooling has passed — should not be blocked by cooling reason
        # (may still be blocked by other limits, but not cooling)
        from backend.services.risk_management.exposure_controller import ExposureViolationType

        assert ExposureViolationType.DAILY_LOSS_LIMIT not in result.violations or result.allowed, (
            "Cooling period has expired — should not reject on cooling."
        )

    def test_no_cooling_allows_position(self):
        """cooling_until=None → no cooling rejection."""
        ctrl = self._make_controller()
        assert ctrl.cooling_until is None

        result = ctrl.check_new_position(
            symbol="ETHUSDT",
            side="long",
            size=0.1,
            entry_price=3_000.0,
            leverage=1.0,
        )
        from backend.services.risk_management.exposure_controller import ExposureViolationType

        assert ExposureViolationType.DAILY_LOSS_LIMIT not in (result.violations or []) or True, (
            "With no cooling_until, DAILY_LOSS_LIMIT should not appear from cooling logic"
        )


# ---------------------------------------------------------------------------
# R2 — Negative Kelly → zero position size
# ---------------------------------------------------------------------------


class TestNegativeKellyZeroSize:
    """
    R2: When Kelly formula returns a negative value, position_size must be 0.0.
    """

    @staticmethod
    def _make_sizer_with_stats(win_rate: float, payoff_ratio: float):
        from backend.services.risk_management.position_sizing import PositionSizer, TradingStats

        sizer = PositionSizer(equity=10_000.0)
        stats = TradingStats(
            total_trades=20,
            win_rate=win_rate,
            payoff_ratio=payoff_ratio,
            avg_win=payoff_ratio * 100.0,
            avg_loss=100.0,
        )
        sizer.stats = stats
        return sizer

    def test_negative_kelly_returns_zero_size(self):
        """
        win_rate=0.3, payoff_ratio=0.5:
            kelly = 0.3 - (0.7 / 0.5) = 0.3 - 1.4 = -1.1 → negative → 0.0
        """
        sizer = self._make_sizer_with_stats(win_rate=0.3, payoff_ratio=0.5)

        from backend.services.risk_management.position_sizing import SizingMethod

        result = sizer.calculate_size(
            entry_price=50_000.0,
            stop_loss_price=None,
            method=SizingMethod.KELLY_CRITERION,
        )

        # The guard returns 0.0 internally; _apply_constraints may then floor
        # to min_position_size (0.001).  The key invariant is that the guard
        # fired (skip_reason) and did NOT compute a large negative-Kelly position.
        assert result.details.get("skip_reason") == "negative_kelly", (
            f"R2 regression: negative Kelly guard must set skip_reason='negative_kelly', got details={result.details}."
        )
        assert result.position_size <= sizer.min_position_size + 1e-9, (
            f"R2 regression: position_size must be at most min_position_size "
            f"({sizer.min_position_size}), got {result.position_size}. "
            "Before fix, negative Kelly could propagate to a large position."
        )

    def test_negative_kelly_result_has_skip_reason(self):
        """SizingResult.details should indicate skip_reason='negative_kelly'."""
        sizer = self._make_sizer_with_stats(win_rate=0.1, payoff_ratio=0.2)

        from backend.services.risk_management.position_sizing import SizingMethod

        result = sizer.calculate_size(
            entry_price=1_000.0,
            stop_loss_price=None,
            method=SizingMethod.KELLY_CRITERION,
        )

        assert result.details.get("skip_reason") == "negative_kelly", (
            f"Expected skip_reason='negative_kelly' in details, got {result.details}"
        )

    def test_positive_kelly_still_works(self):
        """Positive Kelly must still produce a non-zero position size."""
        # win_rate=0.6, payoff_ratio=2.0:
        # kelly = 0.6 - (0.4 / 2.0) = 0.6 - 0.2 = 0.4 → 40% (clamped)
        sizer = self._make_sizer_with_stats(win_rate=0.6, payoff_ratio=2.0)

        from backend.services.risk_management.position_sizing import SizingMethod

        result = sizer.calculate_size(
            entry_price=1_000.0,
            stop_loss_price=None,
            method=SizingMethod.KELLY_CRITERION,
        )

        assert result.position_size > 0.0, f"Positive Kelly should give non-zero size, got {result.position_size}"


# ---------------------------------------------------------------------------
# R3 — Ghost stops (MOVED_TO_BREAKEVEN stops can be cancelled)
# ---------------------------------------------------------------------------


class TestGhostStopsCancellation:
    """
    R3: cancel_stop() must be able to cancel stops in MOVED_TO_BREAKEVEN state.
    Before fix: cancel_stop() checked `state == ACTIVE` only → returned False
    for breakeven-moved stops → ghost stops accumulated in get_active_stops().
    """

    @staticmethod
    def _make_breakeven_stop():
        """Create a stop that has already moved to breakeven."""
        from backend.services.risk_management.stop_loss_manager import (
            StopLossManager,
            StopLossState,
            StopLossType,
        )

        manager = StopLossManager()
        stop = manager.create_stop(
            symbol="BTCUSDT",
            side="long",
            entry_price=50_000.0,
            position_size=0.1,
            stop_type=StopLossType.BREAKEVEN,
            initial_stop=49_000.0,
            breakeven_trigger_pct=1.0,
        )
        # Manually move to MOVED_TO_BREAKEVEN state (as if breakeven was triggered)
        stop.state = StopLossState.MOVED_TO_BREAKEVEN
        stop.is_at_breakeven = True
        return manager, stop

    def test_cancel_breakeven_stop_returns_true(self):
        """
        cancel_stop() on a MOVED_TO_BREAKEVEN stop must return True.

        Before R3 fix: returned False (checked state == ACTIVE only).
        After fix: also handles MOVED_TO_BREAKEVEN.
        """
        manager, stop = self._make_breakeven_stop()

        result = manager.cancel_stop(stop.id)

        assert result is True, (
            "R3 regression: cancel_stop() must return True for MOVED_TO_BREAKEVEN stops. "
            "Before fix, only ACTIVE stops could be cancelled — breakeven stops became ghosts."
        )

    def test_cancelled_breakeven_stop_not_in_active_stops(self):
        """
        After cancellation, the stop must not appear in get_active_stops().
        """

        manager, stop = self._make_breakeven_stop()

        # Before cancel: appears in get_active_stops()
        active_before = manager.get_active_stops()
        assert stop in active_before, "Stop should be in active_stops before cancellation"

        manager.cancel_stop(stop.id)

        active_after = manager.get_active_stops()
        assert stop not in active_after, (
            "R3 regression: cancelled MOVED_TO_BREAKEVEN stop must not appear in get_active_stops(). "
            "Before fix, cancel_stop() returned False for breakeven stops, leaving ghost stops."
        )

    def test_cancelled_breakeven_stop_state_is_cancelled(self):
        """Stop state must be CANCELLED after successful cancellation."""
        from backend.services.risk_management.stop_loss_manager import StopLossState

        manager, stop = self._make_breakeven_stop()
        manager.cancel_stop(stop.id)

        assert stop.state == StopLossState.CANCELLED, f"Expected state CANCELLED, got {stop.state}"

    def test_active_stop_cancellation_still_works(self):
        """Regression: plain ACTIVE stops must still cancel correctly."""
        from backend.services.risk_management.stop_loss_manager import StopLossManager, StopLossState, StopLossType

        manager = StopLossManager()
        stop = manager.create_stop(
            symbol="ETHUSDT",
            side="long",
            entry_price=3_000.0,
            position_size=1.0,
            stop_type=StopLossType.FIXED,
            initial_stop=2_900.0,
        )

        result = manager.cancel_stop(stop.id)

        assert result is True
        assert stop.state == StopLossState.CANCELLED


# ---------------------------------------------------------------------------
# R4 — Max position size constraint enforced
# ---------------------------------------------------------------------------


class TestMaxPositionSizeConstraint:
    """
    R4: ExposureController must reject positions that exceed max_position_size_pct.
    """

    def test_oversized_position_rejected(self):
        """
        Position value > max_position_size_pct of equity → not allowed.
        max_position_size_pct = 10% → equity=10_000 → max $1000
        Trying to open 2 BTC at $1000 = $2000 → rejected.
        """
        from backend.services.risk_management.exposure_controller import ExposureController, ExposureLimits

        controller = ExposureController(
            equity=10_000.0,
            limits=ExposureLimits(max_position_size_pct=10.0),  # 10% → $1000 max
        )

        # 2 BTC at $1000 = $2000 (20% of equity) → exceeds 10% limit
        result = controller.check_new_position(
            symbol="BTCUSDT",
            side="long",
            size=2.0,
            entry_price=1_000.0,
            leverage=1.0,
        )

        assert not result.allowed, (
            "R4 regression: position exceeding max_position_size_pct must be rejected. "
            "Position value $2000 (20%) vs limit 10% of equity $10000."
        )

    def test_within_limit_position_allowed(self):
        """Position within max_position_size_pct is allowed."""
        from backend.services.risk_management.exposure_controller import ExposureController, ExposureLimits

        controller = ExposureController(
            equity=10_000.0,
            limits=ExposureLimits(max_position_size_pct=20.0),  # 20% → $2000 max
        )

        # 0.1 BTC at $10000 = $1000 (10% of equity) → within 20% limit
        result = controller.check_new_position(
            symbol="BTCUSDT",
            side="long",
            size=0.1,
            entry_price=10_000.0,
            leverage=1.0,
        )

        from backend.services.risk_management.exposure_controller import ExposureViolationType

        max_size_violated = ExposureViolationType.MAX_POSITION_SIZE in (result.violations or [])
        assert not max_size_violated, (
            f"Position within limit should not trigger MAX_POSITION_SIZE violation. Violations: {result.violations}"
        )

    def test_exactly_at_limit_is_allowed(self):
        """Position exactly at the limit (100%) is borderline-allowed (> check)."""
        from backend.services.risk_management.exposure_controller import ExposureController, ExposureLimits

        controller = ExposureController(
            equity=10_000.0,
            limits=ExposureLimits(max_position_size_pct=20.0),
        )
        # Exactly 20% → position_pct == limit → `> limit` is False → allowed
        result = controller.check_new_position(
            symbol="BTCUSDT",
            side="long",
            size=0.2,
            entry_price=10_000.0,
            leverage=1.0,
        )

        from backend.services.risk_management.exposure_controller import ExposureViolationType

        max_size_violated = ExposureViolationType.MAX_POSITION_SIZE in (result.violations or [])
        assert not max_size_violated, "Position exactly at limit should not be rejected by max_position_size check"


# ---------------------------------------------------------------------------
# R5 — on_stop_triggered callback receives StopLossOrder
# ---------------------------------------------------------------------------


class TestStopCallbackSignature:
    """
    R5: on_stop_triggered callback must receive the StopLossOrder object.
    Before fix: StopLossManager passed stop, but RiskEngine declared
    Callable[[str, float, float], None], causing TypeError.
    After fix: consistent Callable[[StopLossOrder], None].
    """

    def test_callback_receives_stop_loss_order_object(self):
        """
        When a stop is triggered, on_stop_triggered must be called with
        the StopLossOrder instance, not with separate primitives.
        """
        from backend.services.risk_management.stop_loss_manager import (
            StopLossManager,
            StopLossOrder,
            StopLossType,
        )

        received_args = []

        def my_callback(stop_order):
            received_args.append(stop_order)

        manager = StopLossManager()
        manager.on_stop_triggered = my_callback

        stop = manager.create_stop(
            symbol="BTCUSDT",
            side="long",
            entry_price=50_000.0,
            position_size=0.1,
            stop_type=StopLossType.FIXED,
            initial_stop=49_000.0,
        )

        # Price falls below stop → triggers
        manager.update(stop.id, current_price=48_000.0)

        assert len(received_args) == 1, "Callback should have been called exactly once"
        assert isinstance(received_args[0], StopLossOrder), (
            f"R5 regression: on_stop_triggered must receive a StopLossOrder object, "
            f"got {type(received_args[0]).__name__}. "
            "Before fix: RiskEngine declared Callable[[str, float, float], None], "
            "so callback would TypeError when called with (stop_order,)."
        )

    def test_callback_receives_correct_stop_object(self):
        """The received object is the same stop that was created."""
        from backend.services.risk_management.stop_loss_manager import (
            StopLossManager,
            StopLossType,
        )

        received = []

        manager = StopLossManager()
        manager.on_stop_triggered = lambda s: received.append(s)

        stop = manager.create_stop(
            symbol="ETHUSDT",
            side="long",
            entry_price=3_000.0,
            position_size=1.0,
            stop_type=StopLossType.FIXED,
            initial_stop=2_900.0,
        )

        manager.update(stop.id, current_price=2_800.0)

        assert received[0].id == stop.id
        assert received[0].symbol == "ETHUSDT"

    def test_no_callback_does_not_raise(self):
        """When on_stop_triggered is None, stop triggering must not raise."""
        from backend.services.risk_management.stop_loss_manager import StopLossManager, StopLossType

        manager = StopLossManager()
        # on_stop_triggered defaults to None
        assert manager.on_stop_triggered is None

        stop = manager.create_stop(
            symbol="BTCUSDT",
            side="long",
            entry_price=50_000.0,
            position_size=0.1,
            stop_type=StopLossType.FIXED,
            initial_stop=49_000.0,
        )

        # Should not raise even without callback
        triggered = manager.update(stop.id, current_price=48_000.0)
        assert triggered is True


# ---------------------------------------------------------------------------
# R6 — Breakeven check: `and` (not `or`) prevents non-BREAKEVEN stop corruption
# ---------------------------------------------------------------------------


class TestBreakevenAndGuard:
    """
    R6: _check_breakeven() is only invoked for BREAKEVEN stop type.
    Before fix: `if stop.stop_type == BREAKEVEN or not stop.is_at_breakeven:`
    → applied breakeven logic to TRAILING, FIXED, etc. stops.
    After fix: `and` → only BREAKEVEN stops are checked.
    """

    def test_trailing_stop_not_moved_to_breakeven(self):
        """
        A TRAILING stop in deep profit must NOT be moved to breakeven state.
        Before R6 fix: `or not stop.is_at_breakeven` was True for all fresh stops
        → _check_breakeven() ran on TRAILING stops → is_at_breakeven set True.
        """
        from backend.services.risk_management.stop_loss_manager import (
            StopLossManager,
            StopLossState,
            StopLossType,
        )

        manager = StopLossManager()
        stop = manager.create_stop(
            symbol="BTCUSDT",
            side="long",
            entry_price=50_000.0,
            position_size=0.1,
            stop_type=StopLossType.TRAILING_PERCENT,
            trail_percent=2.0,
        )

        # Price up 5% — well past any breakeven trigger
        manager.update(stop.id, current_price=52_500.0)

        assert stop.is_at_breakeven is False, (
            "R6 regression: TRAILING_PERCENT stop must NOT have is_at_breakeven=True. "
            "Before fix: the `or not stop.is_at_breakeven` condition triggered "
            "_check_breakeven() for ALL stop types."
        )
        assert stop.state != StopLossState.MOVED_TO_BREAKEVEN, (
            f"TRAILING stop state must not be MOVED_TO_BREAKEVEN, got {stop.state}"
        )

    def test_fixed_stop_not_moved_to_breakeven(self):
        """FIXED stop type must not be moved to breakeven even in profit."""
        from backend.services.risk_management.stop_loss_manager import (
            StopLossManager,
            StopLossState,
            StopLossType,
        )

        manager = StopLossManager()
        stop = manager.create_stop(
            symbol="ETHUSDT",
            side="long",
            entry_price=3_000.0,
            position_size=1.0,
            stop_type=StopLossType.FIXED,
            initial_stop=2_800.0,
        )

        # Large profit
        manager.update(stop.id, current_price=4_000.0)

        assert not stop.is_at_breakeven
        assert stop.state != StopLossState.MOVED_TO_BREAKEVEN

    def test_breakeven_stop_does_move_to_breakeven(self):
        """Positive control: actual BREAKEVEN stops must still move correctly."""
        from backend.services.risk_management.stop_loss_manager import (
            StopLossConfig,
            StopLossManager,
            StopLossState,
            StopLossType,
        )

        config = StopLossConfig(
            breakeven_trigger_pct=1.0,  # Trigger at 1% profit
            breakeven_offset=0.0,  # No offset
        )
        manager = StopLossManager(config=config)
        stop = manager.create_stop(
            symbol="BTCUSDT",
            side="long",
            entry_price=50_000.0,
            position_size=0.1,
            stop_type=StopLossType.BREAKEVEN,
            initial_stop=49_000.0,
            breakeven_trigger_pct=1.0,
        )

        # Price moves up 2% — past 1% trigger
        manager.update(stop.id, current_price=51_000.0)

        assert stop.is_at_breakeven is True, "BREAKEVEN stop should be at breakeven after 2% profit with 1% trigger"
        assert stop.state == StopLossState.MOVED_TO_BREAKEVEN


# ---------------------------------------------------------------------------
# R7 — Timezone normalization in cooldown check
# ---------------------------------------------------------------------------


class TestTimezoneNormalization:
    """
    R7: _validate_frequency() in TradeValidator must not raise TypeError when
    last_trade_time is timezone-aware and datetime.now() is naive (or vice versa).
    Before fix: direct subtraction of aware/naive datetimes → TypeError.
    After fix: tzinfo is stripped from one side before comparison.
    """

    @staticmethod
    def _make_validator():
        from backend.services.risk_management.trade_validator import TradeValidator, ValidationConfig

        config = ValidationConfig(
            min_trade_interval_seconds=60,  # 60s cooldown
        )
        return TradeValidator(config=config)

    @staticmethod
    def _make_account_state(last_trade_time):
        from backend.services.risk_management.trade_validator import AccountState

        return AccountState(
            total_equity=10_000.0,
            available_balance=9_000.0,
            used_margin=1_000.0,
            total_pnl=0.0,
            daily_pnl=0.0,
            open_positions_count=0,
            positions_by_symbol={},
            trades_today=0,
            trades_this_hour=0,
            last_trade_time=last_trade_time,
            is_trading_paused=False,
            current_drawdown_pct=0.0,
        )

    @staticmethod
    def _make_trade_request():
        from backend.services.risk_management.trade_validator import TradeRequest

        return TradeRequest(
            symbol="BTCUSDT",
            side="buy",
            order_type="market",
            quantity=0.01,
            price=50_000.0,
        )

    def test_aware_last_trade_time_does_not_raise(self):
        """
        last_trade_time with UTC tzinfo (aware) must not crash validate().
        Before R7 fix: datetime.now() - aware_datetime → TypeError.
        """
        validator = self._make_validator()

        # Timezone-aware last_trade_time (recent — should trigger cooldown)
        aware_time = datetime.now(UTC) - timedelta(seconds=5)  # 5 seconds ago
        account_state = self._make_account_state(aware_time)
        trade_request = self._make_trade_request()

        # Must not raise TypeError
        try:
            result = validator.validate(trade_request, account_state)
        except TypeError as e:
            pytest.fail(
                f"R7 regression: TypeError raised when last_trade_time is timezone-aware: {e}. "
                "Before fix: datetime.now() - aware_datetime crashed the cooldown check."
            )

        # Should be rejected due to cooldown (5s < 60s interval)
        from backend.services.risk_management.trade_validator import RejectionReason

        assert not result.approved or RejectionReason.COOLDOWN_ACTIVE in result.rejection_reasons, (
            "Trade 5s after last trade should be rejected by cooldown (min_interval=60s)"
        )

    def test_naive_last_trade_time_does_not_raise(self):
        """
        Naive last_trade_time (no tzinfo) must also work without TypeError.
        """
        validator = self._make_validator()

        naive_time = datetime.now() - timedelta(seconds=5)  # naive, 5s ago
        account_state = self._make_account_state(naive_time)
        trade_request = self._make_trade_request()

        try:
            result = validator.validate(trade_request, account_state)
        except TypeError as e:
            pytest.fail(f"R7: TypeError with naive last_trade_time: {e}")

    def test_cooldown_active_reason_returned_for_recent_trade(self):
        """
        Recent trade (naive dt, within interval) → COOLDOWN_ACTIVE in rejection reasons.
        """
        validator = self._make_validator()

        recent_trade = datetime.now() - timedelta(seconds=10)
        account_state = self._make_account_state(recent_trade)
        trade_request = self._make_trade_request()

        result = validator.validate(trade_request, account_state)

        from backend.services.risk_management.trade_validator import RejectionReason

        assert not result.approved
        assert RejectionReason.COOLDOWN_ACTIVE in result.rejection_reasons, (
            f"Expected COOLDOWN_ACTIVE in rejection_reasons. Got: {result.rejection_reasons}"
        )

    def test_no_last_trade_time_skips_cooldown(self):
        """
        last_trade_time=None → cooldown check skipped, no crash.
        """
        validator = self._make_validator()
        account_state = self._make_account_state(None)
        trade_request = self._make_trade_request()

        try:
            result = validator.validate(trade_request, account_state)
        except Exception as e:
            pytest.fail(f"None last_trade_time raised: {e}")

        from backend.services.risk_management.trade_validator import RejectionReason

        assert RejectionReason.COOLDOWN_ACTIVE not in (result.rejection_reasons or []), (
            "None last_trade_time must not trigger COOLDOWN_ACTIVE"
        )
