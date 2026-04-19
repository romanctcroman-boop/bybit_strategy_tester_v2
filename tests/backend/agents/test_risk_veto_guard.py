"""
Tests for RiskVetoGuard — hard safety override for consensus decisions.

Tests cover:
- Default configuration
- Drawdown veto check
- Max open positions check
- Daily loss limit check
- Low agreement score check
- Manual block/unblock
- Multiple simultaneous veto reasons
- Disabled guard (pass-through)
- VetoDecision serialization
- History tracking
- Singleton behavior
"""

from __future__ import annotations

import pytest

from backend.agents.consensus.risk_veto_guard import (
    RiskVetoGuard,
    VetoConfig,
    VetoReason,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def guard() -> RiskVetoGuard:
    """Fresh RiskVetoGuard with default config."""
    return RiskVetoGuard(config=VetoConfig())


@pytest.fixture
def strict_guard() -> RiskVetoGuard:
    """Strict guard with lower thresholds."""
    return RiskVetoGuard(
        config=VetoConfig(
            max_drawdown_pct=3.0,
            max_open_positions=2,
            max_daily_loss_pct=1.0,
            min_agreement_score=0.5,
        )
    )


# =============================================================================
# DEFAULT CONFIG
# =============================================================================


class TestVetoConfig:
    """Tests for VetoConfig defaults."""

    def test_default_max_drawdown(self):
        """Default max drawdown is 5%."""
        config = VetoConfig()
        assert config.max_drawdown_pct == 5.0

    def test_default_max_positions(self):
        """Default max positions is 5."""
        config = VetoConfig()
        assert config.max_open_positions == 5

    def test_default_daily_loss(self):
        """Default daily loss limit is 3%."""
        config = VetoConfig()
        assert config.max_daily_loss_pct == 3.0

    def test_default_min_agreement(self):
        """Default min agreement is 30%."""
        config = VetoConfig()
        assert config.min_agreement_score == 0.3

    def test_config_to_dict(self):
        """Config serializes to dict."""
        config = VetoConfig()
        d = config.to_dict()
        assert "max_drawdown_pct" in d
        assert "max_open_positions" in d
        assert "enabled" in d


# =============================================================================
# DRAWDOWN CHECK
# =============================================================================


class TestDrawdownVeto:
    """Tests for drawdown-based veto."""

    def test_no_veto_below_threshold(self, guard):
        """No veto when drawdown < 5%."""
        decision = guard.check(
            portfolio_equity=9600,
            peak_equity=10000,
        )
        assert decision.is_vetoed is False

    def test_veto_at_threshold(self, guard):
        """Veto at exactly 5% drawdown."""
        decision = guard.check(
            portfolio_equity=9500,
            peak_equity=10000,
        )
        assert decision.is_vetoed is True
        assert VetoReason.DRAWDOWN_EXCEEDED in decision.reasons

    def test_veto_beyond_threshold(self, guard):
        """Veto when drawdown > 5%."""
        decision = guard.check(
            portfolio_equity=9000,
            peak_equity=10000,
        )
        assert decision.is_vetoed is True
        assert VetoReason.DRAWDOWN_EXCEEDED in decision.reasons

    def test_drawdown_pct_in_decision(self, guard):
        """Decision includes drawdown percentage."""
        decision = guard.check(
            portfolio_equity=9000,
            peak_equity=10000,
        )
        assert abs(decision.drawdown_pct - 10.0) < 0.01


# =============================================================================
# POSITION CHECK
# =============================================================================


class TestPositionVeto:
    """Tests for max positions veto."""

    def test_no_veto_below_max(self, guard):
        """No veto when positions < max."""
        decision = guard.check(open_positions=3)
        assert VetoReason.MAX_POSITIONS_EXCEEDED not in decision.reasons

    def test_veto_at_max(self, guard):
        """Veto at max positions (default 5)."""
        decision = guard.check(open_positions=5)
        assert decision.is_vetoed is True
        assert VetoReason.MAX_POSITIONS_EXCEEDED in decision.reasons

    def test_veto_above_max(self, guard):
        """Veto above max positions."""
        decision = guard.check(open_positions=10)
        assert decision.is_vetoed is True


# =============================================================================
# DAILY LOSS CHECK
# =============================================================================


class TestDailyLossVeto:
    """Tests for daily loss limit veto."""

    def test_no_veto_small_loss(self, guard):
        """No veto for small daily loss."""
        decision = guard.check(
            daily_pnl=-100,
            initial_daily_equity=10000,
        )
        assert VetoReason.DAILY_LOSS_EXCEEDED not in decision.reasons

    def test_veto_at_daily_limit(self, guard):
        """Veto at 3% daily loss."""
        decision = guard.check(
            daily_pnl=-300,
            initial_daily_equity=10000,
        )
        assert decision.is_vetoed is True
        assert VetoReason.DAILY_LOSS_EXCEEDED in decision.reasons

    def test_no_veto_for_profit(self, guard):
        """No veto when daily PnL is positive."""
        decision = guard.check(
            daily_pnl=500,
            initial_daily_equity=10000,
        )
        assert VetoReason.DAILY_LOSS_EXCEEDED not in decision.reasons


# =============================================================================
# AGREEMENT CHECK
# =============================================================================


class TestAgreementVeto:
    """Tests for low consensus agreement veto."""

    def test_no_veto_high_agreement(self, guard):
        """No veto when agreement > minimum."""
        decision = guard.check(agreement_score=0.8)
        assert VetoReason.LOW_AGREEMENT not in decision.reasons

    def test_veto_low_agreement(self, guard):
        """Veto when agreement < 30%."""
        decision = guard.check(agreement_score=0.2)
        assert decision.is_vetoed is True
        assert VetoReason.LOW_AGREEMENT in decision.reasons

    def test_no_veto_at_threshold(self, guard):
        """No veto at exactly 30% agreement."""
        decision = guard.check(agreement_score=0.3)
        assert VetoReason.LOW_AGREEMENT not in decision.reasons


# =============================================================================
# MANUAL BLOCK
# =============================================================================


class TestManualBlock:
    """Tests for manual block/unblock."""

    def test_manual_block(self, guard):
        """Manual block vetoes all trades."""
        guard.block(reason="Testing")
        decision = guard.check()
        assert decision.is_vetoed is True
        assert VetoReason.MANUAL_BLOCK in decision.reasons

    def test_manual_unblock(self, guard):
        """Manual unblock allows trades."""
        guard.block(reason="Testing")
        guard.unblock()
        decision = guard.check()
        assert decision.is_vetoed is False

    def test_block_reason_in_details(self, guard):
        """Block reason appears in details."""
        guard.block(reason="Market closed")
        decision = guard.check()
        assert any("Market closed" in d for d in decision.details)


# =============================================================================
# MULTIPLE REASONS
# =============================================================================


class TestMultipleReasons:
    """Tests for multiple simultaneous veto reasons."""

    def test_multiple_veto_reasons(self, guard):
        """Multiple veto conditions report all reasons."""
        decision = guard.check(
            portfolio_equity=9000,
            peak_equity=10000,
            open_positions=10,
            agreement_score=0.1,
        )
        assert decision.is_vetoed is True
        assert len(decision.reasons) >= 3
        assert VetoReason.DRAWDOWN_EXCEEDED in decision.reasons
        assert VetoReason.MAX_POSITIONS_EXCEEDED in decision.reasons
        assert VetoReason.LOW_AGREEMENT in decision.reasons


# =============================================================================
# DISABLED GUARD
# =============================================================================


class TestDisabledGuard:
    """Tests for disabled veto guard."""

    def test_disabled_guard_passes_all(self):
        """Disabled guard never vetoes."""
        guard = RiskVetoGuard(config=VetoConfig(enabled=False))
        decision = guard.check(
            portfolio_equity=5000,
            peak_equity=10000,
            open_positions=100,
            daily_pnl=-5000,
            initial_daily_equity=10000,
            agreement_score=0.0,
        )
        assert decision.is_vetoed is False


# =============================================================================
# SERIALIZATION
# =============================================================================


class TestSerialization:
    """Tests for VetoDecision serialization."""

    def test_decision_to_dict(self, guard):
        """VetoDecision.to_dict produces complete dict."""
        decision = guard.check(
            portfolio_equity=9000,
            peak_equity=10000,
        )
        d = decision.to_dict()
        assert "is_vetoed" in d
        assert "reasons" in d
        assert "details" in d
        assert "drawdown_pct" in d
        assert "timestamp" in d

    def test_reasons_are_strings_in_dict(self, guard):
        """Serialized reasons are string values, not enum objects."""
        decision = guard.check(
            portfolio_equity=9000,
            peak_equity=10000,
        )
        d = decision.to_dict()
        for reason in d["reasons"]:
            assert isinstance(reason, str)


# =============================================================================
# STATUS & HISTORY
# =============================================================================


class TestStatusAndHistory:
    """Tests for status and history tracking."""

    def test_get_status(self, guard):
        """get_status returns complete status."""
        status = guard.get_status()
        assert "config" in status
        assert "total_checks" in status
        assert "recent_veto_rate" in status

    def test_history_grows(self, guard):
        """History grows with each check."""
        guard.check()
        guard.check()
        guard.check()
        assert len(guard.get_history()) == 3

    def test_history_limit(self, guard):
        """History respects limit parameter."""
        for _ in range(10):
            guard.check()
        history = guard.get_history(limit=5)
        assert len(history) == 5


# =============================================================================
# STRICT CONFIG
# =============================================================================


class TestStrictGuard:
    """Tests with stricter thresholds."""

    def test_strict_drawdown(self, strict_guard):
        """3% drawdown threshold triggers earlier."""
        decision = strict_guard.check(
            portfolio_equity=9700,
            peak_equity=10000,
        )
        assert decision.is_vetoed is True

    def test_strict_positions(self, strict_guard):
        """2 max positions triggers earlier."""
        decision = strict_guard.check(open_positions=2)
        assert decision.is_vetoed is True

    def test_strict_agreement(self, strict_guard):
        """50% min agreement triggers for 40%."""
        decision = strict_guard.check(agreement_score=0.4)
        assert decision.is_vetoed is True
