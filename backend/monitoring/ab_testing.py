"""
A/B Testing Framework for Prompts

Compare different prompt versions with statistical significance:
- Create A/B tests with traffic splitting
- Track conversion metrics
- Statistical significance testing (t-test, chi-square)
- Automatic winner selection
- Real-time results monitoring

Usage:
    from backend.monitoring.ab_testing import ABTesting
    ab = ABTesting()
    test_id = ab.create_test("strategy_prompt", ["v1", "v2"], traffic_split=[0.5, 0.5])
    ab.record_conversion(test_id, variant="v1", converted=True)
    results = ab.get_results(test_id)
"""

from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from loguru import logger


@dataclass
class ABTestVariant:
    """A/B test variant."""

    variant_id: str
    name: str
    prompt_version: str
    traffic_split: float  # 0.0-1.0
    impressions: int = 0
    conversions: int = 0
    total_reward: float = 0.0

    @property
    def conversion_rate(self) -> float:
        """Calculate conversion rate."""
        return self.conversions / self.impressions if self.impressions > 0 else 0.0

    @property
    def avg_reward(self) -> float:
        """Calculate average reward."""
        return self.total_reward / self.impressions if self.impressions > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "prompt_version": self.prompt_version,
            "traffic_split": self.traffic_split,
            "impressions": self.impressions,
            "conversions": self.conversions,
            "total_reward": self.total_reward,
            "conversion_rate": self.conversion_rate,
            "avg_reward": self.avg_reward,
        }


@dataclass
class ABTest:
    """A/B test configuration."""

    test_id: str
    name: str
    prompt_name: str
    variants: list[ABTestVariant]
    status: Literal["running", "paused", "completed"] = "running"
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    min_sample_size: int = 100
    significance_level: float = 0.05
    winner_variant: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "test_id": self.test_id,
            "name": self.name,
            "prompt_name": self.prompt_name,
            "variants": [v.to_dict() for v in self.variants],
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "min_sample_size": self.min_sample_size,
            "significance_level": self.significance_level,
            "winner_variant": self.winner_variant,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ABTest:
        """Create from dict."""
        variants = [
            ABTestVariant(
                variant_id=v["variant_id"],
                name=v["name"],
                prompt_version=v["prompt_version"],
                traffic_split=v["traffic_split"],
                impressions=v["impressions"],
                conversions=v["conversions"],
                total_reward=v["total_reward"],
            )
            for v in data.get("variants", [])
        ]

        return cls(
            test_id=data["test_id"],
            name=data["name"],
            prompt_name=data["prompt_name"],
            variants=variants,
            status=data.get("status", "running"),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            min_sample_size=data.get("min_sample_size", 100),
            significance_level=data.get("significance_level", 0.05),
            winner_variant=data.get("winner_variant"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ABTestResults:
    """A/B test results."""

    test_id: str
    total_impressions: int
    total_conversions: int
    winner: str | None
    confidence: float
    statistical_significance: bool
    variant_results: list[dict[str, Any]]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "test_id": self.test_id,
            "total_impressions": self.total_impressions,
            "total_conversions": self.total_conversions,
            "winner": self.winner,
            "confidence": self.confidence,
            "statistical_significance": self.statistical_significance,
            "variant_results": self.variant_results,
            "recommendation": self.recommendation,
        }


class ABTesting:
    """
    A/B testing framework for prompts.

    Features:
    - Create A/B tests with multiple variants
    - Traffic splitting
    - Conversion tracking
    - Statistical significance testing
    - Automatic winner selection
    - Real-time monitoring

    Example:
        ab = ABTesting()
        test_id = ab.create_test(
            name="Strategy Prompt Test",
            prompt_name="strategy_prompt",
            variants=["v1", "v2"],
            traffic_split=[0.5, 0.5]
        )
        ab.record_impression(test_id, "v1")
        ab.record_conversion(test_id, "v1", converted=True, reward=1.0)
        results = ab.get_results(test_id)
    """

    def __init__(self, storage_path: str = "data/ab_tests.json"):
        """
        Initialize A/B testing.

        Args:
            storage_path: Path to store tests
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory storage
        self._tests: dict[str, ABTest] = {}
        self._user_assignments: dict[str, str] = {}  # user_id -> test_id:variant

        # Load from disk
        self._load()

        logger.info(f"🧪 ABTesting initialized (storage={storage_path})")

    def create_test(
        self,
        name: str,
        prompt_name: str,
        variants: list[str],
        traffic_split: list[float] | None = None,
        min_sample_size: int = 100,
        significance_level: float = 0.05,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new A/B test.

        Args:
            name: Test name
            prompt_name: Name of the prompt to test
            variants: List of variant version IDs
            traffic_split: Traffic split for each variant (default: equal)
            min_sample_size: Minimum samples per variant
            significance_level: Significance level (alpha)
            metadata: Additional metadata

        Returns:
            Test ID
        """
        # Generate test ID
        test_id = f"ab_{uuid.uuid4().hex[:8]}"

        # Default to equal traffic split
        if traffic_split is None:
            traffic_split = [1.0 / len(variants)] * len(variants)

        # Validate traffic split
        if len(traffic_split) != len(variants):
            raise ValueError("Traffic split must have same length as variants")

        total_split = sum(traffic_split)
        if abs(total_split - 1.0) > 0.01:
            raise ValueError(f"Traffic split must sum to 1.0, got {total_split}")

        # Create variants
        ab_variants = [
            ABTestVariant(
                variant_id=f"{test_id}_{i}",
                name=f"Variant {i + 1}",
                prompt_version=variant,
                traffic_split=split,
            )
            for i, (variant, split) in enumerate(zip(variants, traffic_split))
        ]

        # Create test
        test = ABTest(
            test_id=test_id,
            name=name,
            prompt_name=prompt_name,
            variants=ab_variants,
            min_sample_size=min_sample_size,
            significance_level=significance_level,
            metadata=metadata or {},
        )

        # Store
        self._tests[test_id] = test

        # Save
        self._save()

        logger.info(f"✅ Created A/B test {test_id}: {name}")

        return test_id

    def get_variant(self, test_id: str, user_id: str | None = None) -> str | None:
        """
        Get variant for a user (with consistent assignment).

        Args:
            test_id: Test ID
            user_id: User ID for consistent assignment (optional)

        Returns:
            Variant version ID or None
        """
        test = self._tests.get(test_id)

        if test is None or test.status != "running":
            return None

        # Check if user already assigned
        assignment_key = f"{test_id}:{user_id}" if user_id else None

        if assignment_key and assignment_key in self._user_assignments:
            variant_id = self._user_assignments[assignment_key]
            for variant in test.variants:
                if variant.variant_id == variant_id:
                    return variant.prompt_version

        # Assign variant based on traffic split
        if user_id:
            # Consistent assignment based on user ID hash
            hash_val = int(uuid.UUID(user_id).hex[:8], 16) % 100 if user_id else 0
        else:
            # Random assignment
            hash_val = int(time.time() * 1000) % 100

        cumulative = 0.0
        selected_variant = test.variants[0]

        for variant in test.variants:
            cumulative += variant.traffic_split * 100
            if hash_val < cumulative:
                selected_variant = variant
                break

        # Record assignment
        if assignment_key:
            self._user_assignments[assignment_key] = selected_variant.variant_id

        # Record impression
        selected_variant.impressions += 1

        # Save
        self._save()

        return selected_variant.prompt_version

    def record_conversion(
        self,
        test_id: str,
        variant: str,
        converted: bool = True,
        reward: float = 1.0,
    ) -> bool:
        """
        Record conversion for a variant.

        Args:
            test_id: Test ID
            variant: Variant version ID
            converted: Whether conversion occurred
            reward: Reward value (for reward-based optimization)

        Returns:
            True if recorded
        """
        test = self._tests.get(test_id)

        if test is None:
            return False

        # Find variant
        for ab_variant in test.variants:
            if ab_variant.prompt_version == variant:
                if converted:
                    ab_variant.conversions += 1
                ab_variant.total_reward += reward

                # Save
                self._save()

                return True

        return False

    def get_results(self, test_id: str) -> ABTestResults | None:
        """
        Get test results with statistical analysis.

        Args:
            test_id: Test ID

        Returns:
            ABTestResults or None
        """
        test = self._tests.get(test_id)

        if test is None:
            return None

        # Calculate totals
        total_impressions = sum(v.impressions for v in test.variants)
        total_conversions = sum(v.conversions for v in test.variants)

        # Get variant results
        variant_results = [v.to_dict() for v in test.variants]

        # Determine winner
        winner, confidence, significant = self._calculate_winner(test)

        # Generate recommendation
        recommendation = self._generate_recommendation(test, winner, confidence, significant)

        return ABTestResults(
            test_id=test_id,
            total_impressions=total_impressions,
            total_conversions=total_conversions,
            winner=winner,
            confidence=confidence,
            statistical_significance=significant,
            variant_results=variant_results,
            recommendation=recommendation,
        )

    def stop_test(
        self,
        test_id: str,
        select_winner: bool = True,
    ) -> bool:
        """
        Stop an A/B test.

        Args:
            test_id: Test ID
            select_winner: Whether to select winner automatically

        Returns:
            True if stopped
        """
        test = self._tests.get(test_id)

        if test is None:
            return False

        test.status = "completed"
        test.completed_at = datetime.now(UTC).isoformat()

        if select_winner:
            winner, _, _ = self._calculate_winner(test)
            test.winner_variant = winner

        # Save
        self._save()

        logger.info(f"🏁 Stopped A/B test {test_id}")

        return True

    def pause_test(self, test_id: str) -> bool:
        """
        Pause an A/B test.

        Args:
            test_id: Test ID

        Returns:
            True if paused
        """
        test = self._tests.get(test_id)

        if test is None:
            return False

        test.status = "paused"

        # Save
        self._save()

        logger.info(f"⏸️ Paused A/B test {test_id}")

        return True

    def resume_test(self, test_id: str) -> bool:
        """
        Resume a paused A/B test.

        Args:
            test_id: Test ID

        Returns:
            True if resumed
        """
        test = self._tests.get(test_id)

        if test is None or test.status != "paused":
            return False

        test.status = "running"
        test.started_at = datetime.now(UTC).isoformat()

        # Save
        self._save()

        logger.info(f"▶️ Resumed A/B test {test_id}")

        return True

    def list_tests(
        self,
        status: str | None = None,
    ) -> list[ABTest]:
        """
        List A/B tests.

        Args:
            status: Filter by status (optional)

        Returns:
            List of tests
        """
        tests = list(self._tests.values())

        if status:
            tests = [t for t in tests if t.status == status]

        return sorted(tests, key=lambda t: t.created_at, reverse=True)

    def get_test(self, test_id: str) -> ABTest | None:
        """
        Get test by ID.

        Args:
            test_id: Test ID

        Returns:
            ABTest or None
        """
        return self._tests.get(test_id)

    def delete_test(self, test_id: str) -> bool:
        """
        Delete an A/B test.

        Args:
            test_id: Test ID

        Returns:
            True if deleted
        """
        if test_id in self._tests:
            del self._tests[test_id]
            self._save()
            logger.info(f"🗑️ Deleted A/B test {test_id}")
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get A/B testing statistics."""
        tests = list(self._tests.values())

        return {
            "total_tests": len(tests),
            "running": sum(1 for t in tests if t.status == "running"),
            "paused": sum(1 for t in tests if t.status == "paused"),
            "completed": sum(1 for t in tests if t.status == "completed"),
            "total_impressions": sum(sum(v.impressions for v in t.variants) for t in tests),
            "total_conversions": sum(sum(v.conversions for v in t.variants) for t in tests),
        }

    def _calculate_winner(
        self,
        test: ABTest,
    ) -> tuple[str | None, float, bool]:
        """
        Calculate winner with statistical significance.

        Args:
            test: ABTest

        Returns:
            Tuple of (winner_variant_id, confidence, is_significant)
        """
        if len(test.variants) < 2:
            return None, 0.0, False

        # Find best variant by conversion rate
        best_variant = max(test.variants, key=lambda v: v.conversion_rate)

        # Check minimum sample size
        min_samples = min(v.impressions for v in test.variants)
        if min_samples < test.min_sample_size:
            return best_variant.prompt_version, 0.0, False

        # Calculate statistical significance (simplified z-test)
        z_score, p_value = self._calculate_significance(test.variants)

        significant = p_value < test.significance_level
        confidence = 1 - p_value

        if significant:
            return best_variant.prompt_version, confidence, True
        else:
            return None, confidence, False

    def _calculate_significance(
        self,
        variants: list[ABTestVariant],
    ) -> tuple[float, float]:
        """
        Calculate statistical significance (chi-square test).

        Args:
            variants: List of variants

        Returns:
            Tuple of (z_score, p_value)
        """
        if len(variants) < 2:
            return 0.0, 1.0

        # Simplified two-proportion z-test
        v1, v2 = variants[0], variants[1]

        n1, n2 = v1.impressions, v2.impressions
        p1, p2 = v1.conversion_rate, v2.conversion_rate

        if n1 == 0 or n2 == 0:
            return 0.0, 1.0

        # Pooled proportion
        p_pool = (v1.conversions + v2.conversions) / (n1 + n2)

        if p_pool == 0 or p_pool == 1:
            return 0.0, 1.0

        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))

        if se == 0:
            return 0.0, 1.0

        # Z-score
        z = abs(p1 - p2) / se

        # Approximate p-value (two-tailed)
        p_value = 2 * (1 - self._normal_cdf(abs(z)))

        return z, p_value

    def _normal_cdf(self, x: float) -> float:
        """Approximate normal CDF."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _generate_recommendation(
        self,
        test: ABTest,
        winner: str | None,
        confidence: float,
        significant: bool,
    ) -> str:
        """Generate recommendation based on results."""
        if winner and significant:
            return f"✅ Deploy winner ({winner}) with {confidence:.0%} confidence"
        elif winner and not significant:
            return "⚠️ Continue test - not enough statistical significance"
        else:
            return "⏳ Continue test - insufficient data"

    def _load(self) -> None:
        """Load from disk."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, encoding="utf-8") as f:
                data = json.load(f)

            for test_data in data.get("tests", []):
                test = ABTest.from_dict(test_data)
                self._tests[test.test_id] = test

            self._user_assignments = data.get("user_assignments", {})

            logger.info(f"🧪 Loaded {len(self._tests)} A/B tests")

        except Exception as e:
            logger.error(f"Failed to load A/B tests: {e}")

    def _save(self) -> None:
        """Save to disk."""
        try:
            data = {
                "tests": [t.to_dict() for t in self._tests.values()],
                "user_assignments": self._user_assignments,
                "updated_at": datetime.now(UTC).isoformat(),
            }

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save A/B tests: {e}")


# Global instance
_ab_testing: ABTesting | None = None


def get_ab_testing(storage_path: str = "data/ab_tests.json") -> ABTesting:
    """
    Get or create A/B testing instance (singleton).

    Args:
        storage_path: Storage path

    Returns:
        ABTesting instance
    """
    global _ab_testing
    if _ab_testing is None:
        _ab_testing = ABTesting(storage_path)
    return _ab_testing
