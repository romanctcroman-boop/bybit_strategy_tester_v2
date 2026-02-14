"""
Strategy-Specific Evaluation Module

Evaluates AI agent quality in the context of trading strategy analysis:
- Signal quality assessment (does the agent correctly interpret trading signals?)
- Backtest metric reasoning (can the agent explain PnL, Sharpe, drawdown?)
- Strategy recommendation quality (are recommendations actionable and sound?)

Usage:
    evaluator = StrategyEval()
    result = evaluator.evaluate_signal_analysis(response, expected_signals)
    print(result.score, result.grade)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

# ═══════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════


class StrategyGrade(str, Enum):
    """Grade for strategy evaluation."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAIL = "fail"

    @classmethod
    def from_score(cls, score: float) -> StrategyGrade:
        """Convert numeric score to grade."""
        if score >= 0.90:
            return cls.EXCELLENT
        if score >= 0.75:
            return cls.GOOD
        if score >= 0.60:
            return cls.ACCEPTABLE
        if score >= 0.40:
            return cls.POOR
        return cls.FAIL


@dataclass
class SignalQualityResult:
    """Result of evaluating signal analysis quality."""

    direction_correct: bool = False
    indicators_mentioned: list[str] = field(default_factory=list)
    risk_addressed: bool = False
    confidence_stated: bool = False
    actionable: bool = False
    score: float = 0.0

    @property
    def grade(self) -> StrategyGrade:
        return StrategyGrade.from_score(self.score)

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction_correct": self.direction_correct,
            "indicators_mentioned": self.indicators_mentioned,
            "risk_addressed": self.risk_addressed,
            "confidence_stated": self.confidence_stated,
            "actionable": self.actionable,
            "score": round(self.score, 4),
            "grade": self.grade.value,
        }


@dataclass
class StrategyEvalResult:
    """Aggregated strategy evaluation result."""

    signal_quality: SignalQualityResult | None = None
    metric_reasoning_score: float = 0.0
    recommendation_score: float = 0.0
    overall_score: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def grade(self) -> StrategyGrade:
        return StrategyGrade.from_score(self.overall_score)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_quality": self.signal_quality.to_dict() if self.signal_quality else None,
            "metric_reasoning_score": round(self.metric_reasoning_score, 4),
            "recommendation_score": round(self.recommendation_score, 4),
            "overall_score": round(self.overall_score, 4),
            "grade": self.grade.value,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════
# Known Indicators (for pattern matching)
# ═══════════════════════════════════════════════════════════════════

KNOWN_INDICATORS = [
    "rsi",
    "macd",
    "ema",
    "sma",
    "bollinger",
    "bb",
    "stochastic",
    "adx",
    "atr",
    "obv",
    "vwap",
    "ichimoku",
    "fibonacci",
    "supertrend",
    "cci",
    "williams",
    "mfi",
    "parabolic sar",
    "dmi",
    "keltner",
    "donchian",
]

RISK_KEYWORDS = [
    "risk",
    "stop.?loss",
    "take.?profit",
    "drawdown",
    "position.?size",
    "leverage",
    "margin",
    "liquidation",
    "risk.?reward",
    "r:r",
]

CONFIDENCE_KEYWORDS = [
    "confidence",
    "probability",
    "likely",
    "uncertain",
    "strong",
    "moderate",
    "weak",
    "high.?conviction",
    "low.?conviction",
]

ACTION_KEYWORDS = [
    "buy",
    "sell",
    "long",
    "short",
    "enter",
    "exit",
    "hold",
    "close",
    "open.?position",
    "take.?profit",
    "stop.?loss",
]


# ═══════════════════════════════════════════════════════════════════
# Strategy Evaluator
# ═══════════════════════════════════════════════════════════════════


class StrategyEval:
    """
    Evaluates AI agent responses in a trading strategy context.

    Measures:
    - Signal analysis quality
    - Backtest metric reasoning
    - Recommendation quality
    """

    def evaluate_signal_analysis(
        self,
        response: str,
        expected_direction: str = "long",
    ) -> SignalQualityResult:
        """
        Evaluate how well the agent analyzed a trading signal.

        Args:
            response: Agent's response text
            expected_direction: Expected trade direction ("long", "short", "neutral")

        Returns:
            SignalQualityResult with sub-scores
        """
        response_lower = response.lower()

        # Check direction correctness
        direction_correct = self._check_direction(response_lower, expected_direction)

        # Find mentioned indicators
        indicators_mentioned = [ind for ind in KNOWN_INDICATORS if re.search(rf"\b{re.escape(ind)}\b", response_lower)]

        # Check risk awareness
        risk_addressed = any(re.search(pattern, response_lower) for pattern in RISK_KEYWORDS)

        # Check confidence statement
        confidence_stated = any(re.search(pattern, response_lower) for pattern in CONFIDENCE_KEYWORDS)

        # Check actionability
        actionable = any(re.search(rf"\b{re.escape(kw)}\b", response_lower) for kw in ACTION_KEYWORDS)

        # Compute score
        score = self._compute_signal_score(
            direction_correct=direction_correct,
            indicators_count=len(indicators_mentioned),
            risk_addressed=risk_addressed,
            confidence_stated=confidence_stated,
            actionable=actionable,
            response_length=len(response),
        )

        return SignalQualityResult(
            direction_correct=direction_correct,
            indicators_mentioned=indicators_mentioned,
            risk_addressed=risk_addressed,
            confidence_stated=confidence_stated,
            actionable=actionable,
            score=score,
        )

    def evaluate_metric_reasoning(
        self,
        response: str,
        metrics: dict[str, float] | None = None,
    ) -> float:
        """
        Evaluate how well the agent reasons about backtest metrics.

        Args:
            response: Agent's analysis of backtest results
            metrics: Optional dict of actual metric values for context

        Returns:
            Score 0.0-1.0
        """
        response_lower = response.lower()

        checks = {
            "mentions_sharpe": bool(re.search(r"(?i)sharpe", response_lower)),
            "mentions_drawdown": bool(re.search(r"(?i)(drawdown|max.?dd)", response_lower)),
            "mentions_win_rate": bool(re.search(r"(?i)(win\s*rate|win\s*%)", response_lower)),
            "mentions_pnl": bool(re.search(r"(?i)(pnl|profit|loss|p&l|net.?profit)", response_lower)),
            "provides_interpretation": bool(
                re.search(
                    r"(?i)(good|bad|strong|weak|acceptable|excellent|poor|above|below|average)",
                    response_lower,
                )
            ),
            "suggests_improvement": bool(
                re.search(
                    r"(?i)(improve|adjust|optimize|recommend|suggest|consider|try)",
                    response_lower,
                )
            ),
            "quantitative": bool(re.search(r"\d+\.?\d*%?", response)),
        }

        # Weighted scoring
        weights = {
            "mentions_sharpe": 1.5,
            "mentions_drawdown": 1.5,
            "mentions_win_rate": 1.0,
            "mentions_pnl": 1.0,
            "provides_interpretation": 2.0,
            "suggests_improvement": 1.5,
            "quantitative": 1.0,
        }

        total_weight = sum(weights.values())
        weighted_sum = sum(weights[k] for k, v in checks.items() if v)

        return min(1.0, weighted_sum / total_weight)

    def evaluate_recommendation(self, response: str) -> float:
        """
        Evaluate quality of strategy recommendation.

        Args:
            response: Agent's strategy recommendation

        Returns:
            Score 0.0-1.0
        """
        response_lower = response.lower()
        score = 0.0
        max_score = 5.0

        # Has specific parameters
        if re.search(r"(?i)(period|length|threshold|level)\s*[:=]?\s*\d+", response):
            score += 1.0

        # Mentions entry/exit conditions
        if re.search(r"(?i)(entry|exit|enter|close)", response_lower):
            score += 1.0

        # Mentions risk management
        if any(re.search(p, response_lower) for p in RISK_KEYWORDS):
            score += 1.0

        # Has reasoning/justification
        if re.search(r"(?i)(because|since|due to|based on|reason)", response_lower):
            score += 1.0

        # Mentions timeframe context
        if re.search(r"(?i)(timeframe|tf|1m|5m|15m|30m|1h|4h|daily|weekly)", response_lower):
            score += 1.0

        return min(1.0, score / max_score)

    def evaluate_full(
        self,
        response: str,
        expected_direction: str = "long",
        metrics: dict[str, float] | None = None,
    ) -> StrategyEvalResult:
        """
        Run full evaluation across all dimensions.

        Args:
            response: Agent's full response
            expected_direction: Expected trade direction
            metrics: Optional backtest metrics for context

        Returns:
            StrategyEvalResult with aggregated scores
        """
        signal_quality = self.evaluate_signal_analysis(response, expected_direction)
        metric_score = self.evaluate_metric_reasoning(response, metrics)
        recommendation_score = self.evaluate_recommendation(response)

        # Weighted overall
        overall = signal_quality.score * 0.4 + metric_score * 0.3 + recommendation_score * 0.3

        return StrategyEvalResult(
            signal_quality=signal_quality,
            metric_reasoning_score=metric_score,
            recommendation_score=recommendation_score,
            overall_score=overall,
            details={
                "signal_grade": signal_quality.grade.value,
                "indicators_found": signal_quality.indicators_mentioned,
            },
        )

    # ─── Private Methods ─────────────────────────────────────────

    @staticmethod
    def _check_direction(response: str, expected: str) -> bool:
        """Check if the response mentions the expected direction."""
        if expected == "long":
            return bool(re.search(r"\b(long|buy|bullish)\b", response))
        if expected == "short":
            return bool(re.search(r"\b(short|sell|bearish)\b", response))
        if expected == "neutral":
            return bool(re.search(r"\b(neutral|sideways|flat|no.?trade|hold)\b", response))
        return False

    @staticmethod
    def _compute_signal_score(
        direction_correct: bool,
        indicators_count: int,
        risk_addressed: bool,
        confidence_stated: bool,
        actionable: bool,
        response_length: int,
    ) -> float:
        """Compute weighted signal quality score."""
        score = 0.0
        max_score = 6.0

        # Direction (highest weight)
        if direction_correct:
            score += 2.0

        # Indicators used
        score += min(1.5, indicators_count * 0.5)

        # Risk awareness
        if risk_addressed:
            score += 1.0

        # Confidence
        if confidence_stated:
            score += 0.5

        # Actionability
        if actionable:
            score += 0.5

        # Penalize very short responses
        if response_length < 30:
            score *= 0.5

        return min(1.0, score / max_score)
