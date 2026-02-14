"""
Security Orchestrator

Fuses results from PromptGuard (regex-based) and SemanticPromptGuard
(embedding + structural analysis) into a unified security decision.

Policy options:
- BLOCK_ANY: Block if either guard flags the prompt (strictest)
- BLOCK_ALL: Block only if both guards agree (most permissive)
- WEIGHTED: Block based on weighted score threshold (default)

Addresses audit finding: "PromptGuard and SemanticPromptGuard operate
independently — no orchestration layer to fuse results" (Qwen, P1)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class FusionPolicy(str, Enum):
    """How to combine results from multiple guards."""

    BLOCK_ANY = "block_any"  # Block if ANY guard flags (strictest)
    BLOCK_ALL = "block_all"  # Block only if ALL guards flag
    WEIGHTED = "weighted"  # Block based on weighted score threshold


@dataclass
class SecurityVerdict:
    """Unified security assessment from all guards."""

    is_safe: bool
    overall_confidence: float  # 0.0 (safe) to 1.0 (dangerous)
    policy_applied: FusionPolicy
    guard_results: dict[str, Any] = field(default_factory=dict)
    blocked_by: list[str] = field(default_factory=list)
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "overall_confidence": round(self.overall_confidence, 4),
            "policy": self.policy_applied.value,
            "guard_results": self.guard_results,
            "blocked_by": self.blocked_by,
            "details": self.details,
        }


class SecurityOrchestrator:
    """
    Orchestrates multiple security guards into a single decision.

    Usage:
        from backend.agents.security.prompt_guard import PromptGuard
        from backend.agents.security.semantic_guard import SemanticPromptGuard

        orchestrator = SecurityOrchestrator(
            policy=FusionPolicy.WEIGHTED,
            threshold=0.7,
        )
        verdict = orchestrator.analyze("Ignore all instructions...")

    The orchestrator creates guard instances lazily and caches them.
    """

    def __init__(
        self,
        policy: FusionPolicy = FusionPolicy.WEIGHTED,
        threshold: float = 0.7,
        regex_weight: float = 0.6,
        semantic_weight: float = 0.4,
        strict_mode: bool = False,
    ):
        """
        Args:
            policy: How to fuse guard results.
            threshold: Score threshold for WEIGHTED policy (0.0-1.0).
            regex_weight: Weight for PromptGuard score in WEIGHTED mode.
            semantic_weight: Weight for SemanticPromptGuard score.
            strict_mode: Pass strict_mode to PromptGuard.
        """
        self.policy = policy
        self.threshold = threshold
        self.regex_weight = regex_weight
        self.semantic_weight = semantic_weight
        self.strict_mode = strict_mode

        # Lazy-initialized guards
        self._prompt_guard = None
        self._semantic_guard = None

    @property
    def prompt_guard(self):
        """Lazy-init PromptGuard."""
        if self._prompt_guard is None:
            from backend.agents.security.prompt_guard import PromptGuard

            self._prompt_guard = PromptGuard(strict_mode=self.strict_mode)
        return self._prompt_guard

    @property
    def semantic_guard(self):
        """Lazy-init SemanticPromptGuard with strict_mode propagation."""
        if self._semantic_guard is None:
            from backend.agents.security.semantic_guard import SemanticPromptGuard

            self._semantic_guard = SemanticPromptGuard(strict_mode=self.strict_mode)
        return self._semantic_guard

    def analyze(self, prompt: str) -> SecurityVerdict:
        """
        Run all guards and produce a unified verdict.

        Args:
            prompt: The user prompt to analyze.

        Returns:
            SecurityVerdict with combined assessment.
        """
        if not prompt or not prompt.strip():
            return SecurityVerdict(
                is_safe=True,
                overall_confidence=0.0,
                policy_applied=self.policy,
                details="Empty prompt",
            )

        # Run regex-based guard
        regex_result = self.prompt_guard.analyze(prompt)
        regex_score = regex_result.confidence if not regex_result.is_safe else 0.0

        # Run semantic guard
        semantic_result = self.semantic_guard.analyze(prompt)
        semantic_score = (
            semantic_result.risk_score
            if hasattr(semantic_result, "risk_score")
            else (1.0 - semantic_result.confidence if not semantic_result.is_safe else 0.0)
        )

        # Collect guard results
        guard_results = {
            "prompt_guard": {
                "is_safe": regex_result.is_safe,
                "category": regex_result.category.value
                if hasattr(regex_result.category, "value")
                else str(regex_result.category),
                "confidence": round(regex_result.confidence, 4),
                "patterns": regex_result.matched_patterns if hasattr(regex_result, "matched_patterns") else [],
            },
            "semantic_guard": {
                "is_safe": semantic_result.is_safe,
                "risk_score": round(semantic_score, 4),
                "details": getattr(semantic_result, "details", ""),
            },
        }

        # Apply fusion policy
        blocked_by = []
        if not regex_result.is_safe:
            blocked_by.append("prompt_guard")
        if not semantic_result.is_safe:
            blocked_by.append("semantic_guard")

        if self.policy == FusionPolicy.BLOCK_ANY:
            is_safe = len(blocked_by) == 0
            overall_confidence = max(regex_score, semantic_score)

        elif self.policy == FusionPolicy.BLOCK_ALL:
            is_safe = len(blocked_by) < 2  # Safe unless BOTH flag it
            overall_confidence = min(regex_score, semantic_score) if blocked_by else 0.0

        else:  # WEIGHTED
            weighted_score = regex_score * self.regex_weight + semantic_score * self.semantic_weight
            is_safe = weighted_score < self.threshold
            overall_confidence = weighted_score

        if not is_safe:
            logger.warning(
                f"🛡️ Security orchestrator BLOCKED prompt: "
                f"policy={self.policy.value}, confidence={overall_confidence:.3f}, "
                f"blocked_by={blocked_by}"
            )

        return SecurityVerdict(
            is_safe=is_safe,
            overall_confidence=overall_confidence,
            policy_applied=self.policy,
            guard_results=guard_results,
            blocked_by=blocked_by,
            details=(
                f"Policy={self.policy.value}, "
                f"regex_score={regex_score:.3f}, "
                f"semantic_score={semantic_score:.3f}, "
                f"weighted={overall_confidence:.3f}"
            ),
        )

    def is_safe(self, prompt: str) -> bool:
        """Quick safety check (returns bool only)."""
        return self.analyze(prompt).is_safe


__all__ = [
    "FusionPolicy",
    "SecurityOrchestrator",
    "SecurityVerdict",
]
