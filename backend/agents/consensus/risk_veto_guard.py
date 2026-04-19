"""
Risk Veto Guard — Hard Safety Override for Consensus Decisions.

Provides a mandatory risk check that can block ANY consensus decision,
regardless of agent voting results. This is the "last line of defense"
before a trade signal is acted upon.

Veto Conditions (any one triggers a block):
1. Portfolio drawdown exceeds threshold (default 5%)
2. Maximum concurrent open positions exceeded
3. Daily loss limit reached
4. Emergency stop is active

This guard is independent of the soft consensus mechanisms in
ConsensusEngine (weighted voting, Bayesian, etc.) — it operates
as a mandatory post-consensus filter.

Added 2026-02-14 per audit gap analysis — P2 safety requirement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from loguru import logger

from backend.agents.structured_logging import (
    agent_log,
    get_correlation_id,
)

# =============================================================================
# DATA MODELS
# =============================================================================


class VetoReason(str, Enum):
    """Reasons for vetoing a consensus decision."""

    DRAWDOWN_EXCEEDED = "drawdown_exceeded"
    MAX_POSITIONS_EXCEEDED = "max_positions_exceeded"
    DAILY_LOSS_EXCEEDED = "daily_loss_exceeded"
    EMERGENCY_STOP_ACTIVE = "emergency_stop_active"
    LOW_AGREEMENT = "low_agreement"
    MANUAL_BLOCK = "manual_block"


@dataclass
class VetoDecision:
    """Result of a veto check."""

    is_vetoed: bool
    reasons: list[VetoReason] = field(default_factory=list)
    details: list[str] = field(default_factory=list)
    drawdown_pct: float = 0.0
    agreement_score: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_vetoed": self.is_vetoed,
            "reasons": [r.value for r in self.reasons],
            "details": self.details,
            "drawdown_pct": round(self.drawdown_pct, 4),
            "agreement_score": round(self.agreement_score, 4),
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
        }


@dataclass
class VetoConfig:
    """Configuration for the veto guard thresholds."""

    max_drawdown_pct: float = 5.0  # Block if drawdown > 5%
    max_open_positions: int = 5  # Block if too many open positions
    max_daily_loss_pct: float = 3.0  # Block if daily loss > 3%
    min_agreement_score: float = 0.3  # Block if consensus agreement < 30%
    enabled: bool = True  # Master switch

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_open_positions": self.max_open_positions,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "min_agreement_score": self.min_agreement_score,
            "enabled": self.enabled,
        }


# =============================================================================
# RISK VETO GUARD
# =============================================================================


class RiskVetoGuard:
    """
    Hard safety override that can block consensus decisions.

    This guard is INDEPENDENT of voting — it's a mandatory filter
    applied AFTER consensus is reached but BEFORE execution.

    Usage:
        guard = RiskVetoGuard(config=VetoConfig(max_drawdown_pct=5.0))

        # After consensus engine produces a result
        decision = guard.check(
            portfolio_equity=9400,
            peak_equity=10000,
            open_positions=3,
            daily_pnl=-250,
            initial_daily_equity=10000,
            agreement_score=0.85,
        )

        if decision.is_vetoed:
            logger.warning(f"Trade blocked by RiskVetoGuard: {decision.reasons}")
            return  # Do NOT execute

        # Safe to proceed with trade
        execute_trade(consensus_result)
    """

    def __init__(self, config: VetoConfig | None = None) -> None:
        self.config = config or VetoConfig()
        self._veto_history: list[VetoDecision] = []
        self._manual_block: bool = False
        self._manual_block_reason: str = ""

    def check(
        self,
        portfolio_equity: float = 0.0,
        peak_equity: float = 0.0,
        open_positions: int = 0,
        daily_pnl: float = 0.0,
        initial_daily_equity: float = 0.0,
        agreement_score: float = 1.0,
    ) -> VetoDecision:
        """
        Run all veto checks and return a decision.

        All checks are independent — if ANY check triggers, the trade
        is blocked. This is a hard veto, not a soft suggestion.

        Args:
            portfolio_equity: Current total equity
            peak_equity: Historical peak equity (for drawdown calc)
            open_positions: Number of currently open positions
            daily_pnl: Today's P&L in absolute terms
            initial_daily_equity: Equity at start of day
            agreement_score: Consensus agreement score (0-1)

        Returns:
            VetoDecision with is_vetoed=True if any check fails
        """
        if not self.config.enabled:
            return VetoDecision(
                is_vetoed=False,
                correlation_id=get_correlation_id(),
            )

        reasons: list[VetoReason] = []
        details: list[str] = []
        drawdown_pct = 0.0

        # Check 1: Portfolio drawdown
        if peak_equity > 0:
            drawdown_pct = ((peak_equity - portfolio_equity) / peak_equity) * 100
            if drawdown_pct >= self.config.max_drawdown_pct:
                reasons.append(VetoReason.DRAWDOWN_EXCEEDED)
                details.append(f"Drawdown {drawdown_pct:.2f}% exceeds limit {self.config.max_drawdown_pct}%")

        # Check 2: Maximum open positions
        if open_positions >= self.config.max_open_positions:
            reasons.append(VetoReason.MAX_POSITIONS_EXCEEDED)
            details.append(f"{open_positions} open positions >= limit {self.config.max_open_positions}")

        # Check 3: Daily loss limit
        if initial_daily_equity > 0:
            daily_loss_pct = abs(min(0, daily_pnl)) / initial_daily_equity * 100
            if daily_loss_pct >= self.config.max_daily_loss_pct:
                reasons.append(VetoReason.DAILY_LOSS_EXCEEDED)
                details.append(f"Daily loss {daily_loss_pct:.2f}% exceeds limit {self.config.max_daily_loss_pct}%")

        # Check 4: Emergency stop
        try:
            from backend.agents.trading.emergency_stop import get_emergency_stop

            estop = get_emergency_stop()
            if estop.should_halt():
                reasons.append(VetoReason.EMERGENCY_STOP_ACTIVE)
                details.append("Portfolio emergency stop is active")
        except Exception:
            pass  # Emergency stop not initialized — skip check

        # Check 5: Low consensus agreement
        if agreement_score < self.config.min_agreement_score:
            reasons.append(VetoReason.LOW_AGREEMENT)
            details.append(f"Agreement score {agreement_score:.2%} below minimum {self.config.min_agreement_score:.2%}")

        # Check 6: Manual block
        if self._manual_block:
            reasons.append(VetoReason.MANUAL_BLOCK)
            details.append(f"Manual block: {self._manual_block_reason}")

        is_vetoed = len(reasons) > 0
        decision = VetoDecision(
            is_vetoed=is_vetoed,
            reasons=reasons,
            details=details,
            drawdown_pct=drawdown_pct,
            agreement_score=agreement_score,
            correlation_id=get_correlation_id(),
        )

        if is_vetoed:
            agent_log(
                "WARNING",
                f"🚫 VETO: {len(reasons)} check(s) failed — {', '.join(r.value for r in reasons)}",
                component="risk_veto",
            )

        self._record(decision)
        return decision

    # ------------------------------------------------------------------
    # Manual Control
    # ------------------------------------------------------------------

    def block(self, reason: str = "Manual block") -> None:
        """Manually block all trades."""
        self._manual_block = True
        self._manual_block_reason = reason
        agent_log("WARNING", f"Manual trade block activated: {reason}", component="risk_veto")

    def unblock(self) -> None:
        """Remove manual trade block."""
        self._manual_block = False
        self._manual_block_reason = ""
        agent_log("INFO", "Manual trade block removed", component="risk_veto")

    # ------------------------------------------------------------------
    # Status & History
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Get current veto guard status."""
        recent_vetoes = sum(1 for d in self._veto_history[-50:] if d.is_vetoed)
        total_recent = min(50, len(self._veto_history))
        return {
            "config": self.config.to_dict(),
            "manual_block": self._manual_block,
            "manual_block_reason": self._manual_block_reason,
            "total_checks": len(self._veto_history),
            "recent_veto_rate": recent_vetoes / total_recent if total_recent > 0 else 0,
        }

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent veto decisions."""
        return [d.to_dict() for d in self._veto_history[-limit:]]

    def _record(self, decision: VetoDecision) -> None:
        """Record a decision to history."""
        self._veto_history.append(decision)
        # Keep last 500 decisions
        if len(self._veto_history) > 500:
            self._veto_history = self._veto_history[-500:]


# =============================================================================
# SINGLETON
# =============================================================================

_guard: RiskVetoGuard | None = None


def get_risk_veto_guard(config: VetoConfig | None = None) -> RiskVetoGuard:
    """Get or create the global RiskVetoGuard instance."""
    global _guard
    if _guard is None:
        _guard = RiskVetoGuard(config=config)
        logger.info("🛡️ RiskVetoGuard initialized")
    return _guard


__all__ = [
    "RiskVetoGuard",
    "VetoConfig",
    "VetoDecision",
    "VetoReason",
    "get_risk_veto_guard",
]
