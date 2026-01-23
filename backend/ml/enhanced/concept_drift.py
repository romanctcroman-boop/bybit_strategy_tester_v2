"""
Concept Drift Detection for Trading ML Models

Detects when the underlying data distribution changes, which can
invalidate model predictions. Uses statistical tests:
- Kolmogorov-Smirnov test
- Population Stability Index (PSI)
- Page-Hinkley test
- ADWIN (Adaptive Windowing)
- Chi-squared test
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class DriftType(Enum):
    """Types of concept drift"""

    SUDDEN = "sudden"  # Abrupt change
    GRADUAL = "gradual"  # Slow transition
    INCREMENTAL = "incremental"  # Small continuous changes
    RECURRING = "recurring"  # Periodic patterns
    VIRTUAL = "virtual"  # Change in P(y|X) not P(X)


@dataclass
class DriftResult:
    """Result of drift detection"""

    is_drift: bool
    drift_type: Optional[DriftType]
    confidence: float
    p_value: Optional[float]
    statistic: Optional[float]
    feature_name: Optional[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DriftAlert:
    """Alert for detected drift"""

    alert_id: str
    severity: str  # "low", "medium", "high", "critical"
    drift_result: DriftResult
    recommended_action: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConceptDriftDetector:
    """
    Detects concept drift using multiple statistical methods

    Example:
        detector = ConceptDriftDetector(window_size=1000)
        detector.fit(reference_data)

        for new_batch in stream:
            result = detector.detect(new_batch)
            if result.is_drift:
                print(f"Drift detected! Confidence: {result.confidence}")
    """

    def __init__(
        self,
        window_size: int = 1000,
        significance_level: float = 0.05,
        min_samples: int = 30,
        methods: Optional[List[str]] = None,
    ):
        self.window_size = window_size
        self.significance_level = significance_level
        self.min_samples = min_samples
        self.methods = methods or ["ks", "psi", "page_hinkley"]

        # Reference distribution
        self.reference_data: Optional[np.ndarray] = None
        self.reference_stats: Dict[str, Any] = {}

        # Streaming data
        self.current_window: List[float] = []

        # Page-Hinkley state
        self.ph_sum: float = 0.0
        self.ph_min: float = float("inf")
        self.ph_threshold: float = 50.0
        self.ph_delta: float = 0.005

        # ADWIN state
        self.adwin_window: List[float] = []
        self.adwin_total: float = 0.0
        self.adwin_variance: float = 0.0
        self.adwin_width: int = 0

        # Drift history
        self.drift_history: List[DriftResult] = []

    def fit(self, reference_data: np.ndarray) -> None:
        """
        Fit detector on reference (training) distribution

        Args:
            reference_data: Reference distribution to compare against
        """
        self.reference_data = np.asarray(reference_data).flatten()

        # Calculate reference statistics
        self.reference_stats = {
            "mean": np.mean(self.reference_data),
            "std": np.std(self.reference_data),
            "median": np.median(self.reference_data),
            "q25": np.percentile(self.reference_data, 25),
            "q75": np.percentile(self.reference_data, 75),
            "min": np.min(self.reference_data),
            "max": np.max(self.reference_data),
            "histogram": np.histogram(self.reference_data, bins=10)[0],
            "bin_edges": np.histogram(self.reference_data, bins=10)[1],
        }

        logger.info(f"Fitted on {len(self.reference_data)} reference samples")

    def detect(
        self, current_data: np.ndarray, feature_name: Optional[str] = None
    ) -> DriftResult:
        """
        Detect drift between reference and current data

        Args:
            current_data: Current data window to check
            feature_name: Optional name of the feature

        Returns:
            DriftResult with detection results
        """
        if self.reference_data is None:
            raise ValueError("Must call fit() first with reference data")

        current = np.asarray(current_data).flatten()

        if len(current) < self.min_samples:
            return DriftResult(
                is_drift=False,
                drift_type=None,
                confidence=0.0,
                p_value=None,
                statistic=None,
                feature_name=feature_name,
                details={"error": "Not enough samples"},
            )

        # Run all detection methods
        results = {}

        if "ks" in self.methods:
            results["ks"] = self._ks_test(current)

        if "psi" in self.methods:
            results["psi"] = self._psi_test(current)

        if "chi2" in self.methods:
            results["chi2"] = self._chi_squared_test(current)

        if "page_hinkley" in self.methods:
            results["page_hinkley"] = self._page_hinkley_test(current)

        if "wasserstein" in self.methods:
            results["wasserstein"] = self._wasserstein_test(current)

        # Aggregate results
        drift_detected = any(r.get("is_drift", False) for r in results.values())
        confidence = np.mean([r.get("confidence", 0) for r in results.values()])

        # Determine drift type
        drift_type = self._classify_drift_type(results, current)

        result = DriftResult(
            is_drift=drift_detected,
            drift_type=drift_type if drift_detected else None,
            confidence=confidence,
            p_value=results.get("ks", {}).get("p_value"),
            statistic=results.get("ks", {}).get("statistic"),
            feature_name=feature_name,
            details=results,
        )

        self.drift_history.append(result)

        if drift_detected:
            logger.warning(
                f"Drift detected for {feature_name}: "
                f"type={drift_type}, confidence={confidence:.2f}"
            )

        return result

    def _ks_test(self, current: np.ndarray) -> Dict[str, Any]:
        """Kolmogorov-Smirnov test for distribution difference"""
        statistic, p_value = stats.ks_2samp(self.reference_data, current)
        is_drift = p_value < self.significance_level

        return {
            "method": "kolmogorov_smirnov",
            "is_drift": is_drift,
            "statistic": float(statistic),
            "p_value": float(p_value),
            "confidence": 1 - p_value if is_drift else p_value,
            "threshold": self.significance_level,
        }

    def _psi_test(self, current: np.ndarray, threshold: float = 0.25) -> Dict[str, Any]:
        """
        Population Stability Index (PSI)

        PSI < 0.1: No significant population change
        0.1 <= PSI < 0.25: Moderate population change
        PSI >= 0.25: Significant population shift
        """
        # Use same bins as reference
        bins = self.reference_stats["bin_edges"]

        # Calculate expected and actual distributions
        expected = np.histogram(self.reference_data, bins=bins)[0]
        actual = np.histogram(current, bins=bins)[0]

        # Normalize to proportions
        expected_pct = (expected + 1) / (len(self.reference_data) + len(bins) - 1)
        actual_pct = (actual + 1) / (len(current) + len(bins) - 1)

        # Calculate PSI
        psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))

        is_drift = psi >= threshold

        # Calculate confidence based on PSI value
        if psi < 0.1:
            confidence = psi / 0.1 * 0.3  # 0-30%
        elif psi < 0.25:
            confidence = 0.3 + (psi - 0.1) / 0.15 * 0.4  # 30-70%
        else:
            confidence = 0.7 + min((psi - 0.25) / 0.25, 1) * 0.3  # 70-100%

        return {
            "method": "psi",
            "is_drift": is_drift,
            "psi_value": float(psi),
            "confidence": float(confidence),
            "thresholds": {"no_change": 0.1, "moderate": 0.25, "significant": 0.5},
            "interpretation": (
                "no_change"
                if psi < 0.1
                else "moderate_change"
                if psi < 0.25
                else "significant_shift"
            ),
        }

    def _chi_squared_test(self, current: np.ndarray) -> Dict[str, Any]:
        """Chi-squared test for categorical/binned data"""
        bins = self.reference_stats["bin_edges"]

        expected = np.histogram(self.reference_data, bins=bins)[0]
        observed = np.histogram(current, bins=bins)[0]

        # Scale expected to match observed sample size
        expected_scaled = expected * len(current) / len(self.reference_data)

        # Avoid division by zero
        mask = expected_scaled > 0
        if not np.any(mask):
            return {
                "method": "chi_squared",
                "is_drift": False,
                "error": "No valid bins",
            }

        statistic, p_value = stats.chisquare(observed[mask], expected_scaled[mask])

        is_drift = p_value < self.significance_level

        return {
            "method": "chi_squared",
            "is_drift": is_drift,
            "statistic": float(statistic),
            "p_value": float(p_value),
            "confidence": 1 - p_value if is_drift else p_value,
        }

    def _page_hinkley_test(self, current: np.ndarray) -> Dict[str, Any]:
        """
        Page-Hinkley test for detecting change in mean
        Good for streaming data
        """
        ref_mean = self.reference_stats["mean"]

        # Reset if too many samples in window
        if len(self.current_window) > self.window_size * 2:
            self.ph_sum = 0.0
            self.ph_min = float("inf")
            self.current_window = []

        max_ph = 0.0
        for x in current:
            self.current_window.append(x)
            self.ph_sum += x - ref_mean - self.ph_delta
            self.ph_min = min(self.ph_min, self.ph_sum)
            max_ph = max(max_ph, self.ph_sum - self.ph_min)

        is_drift = max_ph > self.ph_threshold
        confidence = min(max_ph / self.ph_threshold, 1.0)

        return {
            "method": "page_hinkley",
            "is_drift": is_drift,
            "ph_value": float(max_ph),
            "threshold": self.ph_threshold,
            "confidence": float(confidence),
        }

    def _wasserstein_test(
        self, current: np.ndarray, threshold: float = 0.1
    ) -> Dict[str, Any]:
        """
        Wasserstein (Earth Mover's) distance
        Measures the minimum "cost" to transform one distribution into another
        """
        distance = stats.wasserstein_distance(self.reference_data, current)

        # Normalize by reference std
        normalized_distance = distance / (self.reference_stats["std"] + 1e-10)

        is_drift = normalized_distance > threshold
        confidence = min(normalized_distance / threshold, 1.0)

        return {
            "method": "wasserstein",
            "is_drift": is_drift,
            "distance": float(distance),
            "normalized_distance": float(normalized_distance),
            "threshold": threshold,
            "confidence": float(confidence),
        }

    def _classify_drift_type(
        self, results: Dict[str, Any], current: np.ndarray
    ) -> Optional[DriftType]:
        """Classify the type of drift based on detection patterns"""
        if not any(r.get("is_drift", False) for r in results.values()):
            return None

        current_mean = np.mean(current)
        ref_mean = self.reference_stats["mean"]
        ref_std = self.reference_stats["std"]

        # Check for sudden drift (large mean shift)
        mean_shift = abs(current_mean - ref_mean) / (ref_std + 1e-10)
        if mean_shift > 2.0:
            return DriftType.SUDDEN

        # Check for gradual drift using rolling statistics
        if len(self.drift_history) >= 5:
            recent_drifts = sum(1 for d in self.drift_history[-5:] if d.is_drift)
            if recent_drifts >= 3 and mean_shift < 1.0:
                return DriftType.GRADUAL

        # Check for incremental (continuous small changes)
        if len(self.drift_history) >= 10:
            confidences = [d.confidence for d in self.drift_history[-10:]]
            if np.std(confidences) < 0.1 and np.mean(confidences) > 0.5:
                return DriftType.INCREMENTAL

        # Default to gradual
        return DriftType.GRADUAL

    def reset(self) -> None:
        """Reset streaming state"""
        self.current_window = []
        self.ph_sum = 0.0
        self.ph_min = float("inf")
        self.adwin_window = []
        self.drift_history = []

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of drift detection history"""
        if not self.drift_history:
            return {"total_checks": 0, "drift_count": 0}

        drift_count = sum(1 for d in self.drift_history if d.is_drift)

        return {
            "total_checks": len(self.drift_history),
            "drift_count": drift_count,
            "drift_rate": drift_count / len(self.drift_history),
            "avg_confidence": np.mean([d.confidence for d in self.drift_history]),
            "last_drift": next(
                (
                    d.timestamp.isoformat()
                    for d in reversed(self.drift_history)
                    if d.is_drift
                ),
                None,
            ),
            "drift_types": [
                d.drift_type.value
                for d in self.drift_history
                if d.is_drift and d.drift_type
            ],
        }


class MultiVariateDriftDetector:
    """
    Detects drift across multiple features simultaneously

    Uses:
    - Per-feature univariate tests
    - Multivariate tests (Hotelling's T-squared)
    - Correlation structure monitoring
    """

    def __init__(
        self,
        feature_names: List[str],
        window_size: int = 1000,
        significance_level: float = 0.05,
    ):
        self.feature_names = feature_names
        self.window_size = window_size
        self.significance_level = significance_level

        # Per-feature detectors
        self.detectors: Dict[str, ConceptDriftDetector] = {
            name: ConceptDriftDetector(window_size, significance_level)
            for name in feature_names
        }

        # Reference correlation matrix
        self.reference_corr: Optional[np.ndarray] = None
        self.reference_mean: Optional[np.ndarray] = None
        self.reference_cov: Optional[np.ndarray] = None

    def fit(self, reference_data: np.ndarray) -> None:
        """
        Fit on reference data (n_samples, n_features)
        """
        if reference_data.shape[1] != len(self.feature_names):
            raise ValueError(
                f"Expected {len(self.feature_names)} features, "
                f"got {reference_data.shape[1]}"
            )

        # Fit individual detectors
        for i, name in enumerate(self.feature_names):
            self.detectors[name].fit(reference_data[:, i])

        # Calculate multivariate statistics
        self.reference_mean = np.mean(reference_data, axis=0)
        self.reference_cov = np.cov(reference_data, rowvar=False)
        self.reference_corr = np.corrcoef(reference_data, rowvar=False)

        logger.info(
            f"Fitted MultiVariateDriftDetector on {len(self.feature_names)} features"
        )

    def detect(self, current_data: np.ndarray) -> Dict[str, Any]:
        """
        Detect drift across all features

        Args:
            current_data: Shape (n_samples, n_features)

        Returns:
            Dict with per-feature and overall results
        """
        results = {
            "per_feature": {},
            "multivariate": {},
            "correlation_drift": {},
            "overall": {},
        }

        # Per-feature detection
        drifted_features = []
        for i, name in enumerate(self.feature_names):
            result = self.detectors[name].detect(current_data[:, i], feature_name=name)
            results["per_feature"][name] = {
                "is_drift": result.is_drift,
                "confidence": result.confidence,
                "drift_type": result.drift_type.value if result.drift_type else None,
                "p_value": result.p_value,
            }
            if result.is_drift:
                drifted_features.append(name)

        # Multivariate Hotelling's T-squared test
        results["multivariate"] = self._hotelling_t2_test(current_data)

        # Correlation structure drift
        results["correlation_drift"] = self._correlation_drift(current_data)

        # Overall assessment
        any_univariate = len(drifted_features) > 0
        multivariate_drift = results["multivariate"].get("is_drift", False)
        correlation_drift = results["correlation_drift"].get("is_drift", False)

        results["overall"] = {
            "is_drift": any_univariate or multivariate_drift or correlation_drift,
            "drifted_features": drifted_features,
            "drift_count": len(drifted_features),
            "severity": self._calculate_severity(
                len(drifted_features), multivariate_drift, correlation_drift
            ),
            "recommended_action": self._get_recommendation(
                drifted_features, multivariate_drift, correlation_drift
            ),
        }

        return results

    def _hotelling_t2_test(self, current_data: np.ndarray) -> Dict[str, Any]:
        """
        Hotelling's T-squared test for multivariate mean shift
        """
        if self.reference_mean is None or self.reference_cov is None:
            return {"error": "Not fitted"}

        n = len(current_data)
        p = len(self.feature_names)

        current_mean = np.mean(current_data, axis=0)
        diff = current_mean - self.reference_mean

        try:
            cov_inv = np.linalg.inv(self.reference_cov)
            t2 = n * diff @ cov_inv @ diff

            # Convert to F-distribution
            f_stat = t2 * (n - p) / (p * (n - 1))
            p_value = 1 - stats.f.cdf(f_stat, p, n - p)

            is_drift = p_value < self.significance_level

            return {
                "is_drift": is_drift,
                "t2_statistic": float(t2),
                "f_statistic": float(f_stat),
                "p_value": float(p_value),
                "confidence": 1 - p_value if is_drift else p_value,
            }
        except np.linalg.LinAlgError:
            return {"error": "Singular covariance matrix"}

    def _correlation_drift(self, current_data: np.ndarray) -> Dict[str, Any]:
        """
        Detect changes in feature correlation structure
        """
        if self.reference_corr is None:
            return {"error": "Not fitted"}

        current_corr = np.corrcoef(current_data, rowvar=False)

        # Frobenius norm of correlation difference
        corr_diff = np.linalg.norm(current_corr - self.reference_corr, "fro")

        # Normalize by matrix size
        normalized_diff = corr_diff / len(self.feature_names)

        # Threshold (empirically derived)
        threshold = 0.3
        is_drift = normalized_diff > threshold

        # Find most changed correlations
        diff_matrix = np.abs(current_corr - self.reference_corr)
        max_idx = np.unravel_index(np.argmax(diff_matrix), diff_matrix.shape)

        return {
            "is_drift": is_drift,
            "correlation_distance": float(normalized_diff),
            "threshold": threshold,
            "confidence": min(normalized_diff / threshold, 1.0),
            "most_changed_pair": (
                self.feature_names[max_idx[0]],
                self.feature_names[max_idx[1]],
            ),
            "max_change": float(diff_matrix[max_idx]),
        }

    def _calculate_severity(
        self, drift_count: int, multivariate_drift: bool, correlation_drift: bool
    ) -> str:
        """Calculate overall drift severity"""
        n_features = len(self.feature_names)

        if drift_count == 0 and not multivariate_drift and not correlation_drift:
            return "none"

        severity_score = 0
        severity_score += drift_count / n_features * 3  # Up to 3 points
        severity_score += 2 if multivariate_drift else 0  # 2 points
        severity_score += 1 if correlation_drift else 0  # 1 point

        if severity_score > 4:
            return "critical"
        elif severity_score > 2:
            return "high"
        elif severity_score > 1:
            return "medium"
        else:
            return "low"

    def _get_recommendation(
        self,
        drifted_features: List[str],
        multivariate_drift: bool,
        correlation_drift: bool,
    ) -> str:
        """Get recommended action based on drift detection"""
        if not drifted_features and not multivariate_drift and not correlation_drift:
            return "No action needed - no drift detected"

        recommendations = []

        if len(drifted_features) > len(self.feature_names) // 2:
            recommendations.append("Full model retraining recommended")
        elif drifted_features:
            recommendations.append(
                f"Consider retraining with focus on: {', '.join(drifted_features[:3])}"
            )

        if correlation_drift:
            recommendations.append(
                "Feature relationships have changed - review feature engineering"
            )

        if multivariate_drift:
            recommendations.append(
                "Overall data distribution has shifted significantly"
            )

        return "; ".join(recommendations) if recommendations else "Monitor closely"
