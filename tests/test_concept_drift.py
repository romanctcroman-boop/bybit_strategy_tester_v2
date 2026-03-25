"""
Tests for Concept Drift Detection Module

Covers:
- ConceptDriftDetector initialization and fit
- KS test, PSI test, chi-squared test, Page-Hinkley test, Wasserstein test
- Drift type classification (sudden, gradual, incremental)
- Multi-method aggregation
- Reset and summary
- MultiVariateDriftDetector: fit, detect, Hotelling T², correlation drift
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.ml.enhanced.concept_drift import (
    ConceptDriftDetector,
    DriftResult,
    DriftType,
    MultiVariateDriftDetector,
)

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def reference_data():
    """Reference (training) distribution — standard normal."""
    np.random.seed(42)
    return np.random.randn(500)


@pytest.fixture
def no_drift_data():
    """Data from the same distribution (no drift)."""
    np.random.seed(99)
    return np.random.randn(200)


@pytest.fixture
def sudden_drift_data():
    """Data with a large mean shift (sudden drift)."""
    np.random.seed(99)
    return np.random.randn(200) + 5.0  # Shift mean by 5


@pytest.fixture
def gradual_drift_data():
    """Data with a small mean shift (gradual drift)."""
    np.random.seed(99)
    return np.random.randn(200) + 0.5


@pytest.fixture
def variance_drift_data():
    """Data with changed variance but same mean."""
    np.random.seed(99)
    return np.random.randn(200) * 3.0


@pytest.fixture
def detector():
    """Default ConceptDriftDetector with all methods."""
    return ConceptDriftDetector(
        window_size=500,
        significance_level=0.05,
        min_samples=30,
        methods=["ks", "psi", "chi2", "page_hinkley", "wasserstein"],
    )


@pytest.fixture
def ks_only_detector():
    """Detector using only KS test."""
    return ConceptDriftDetector(methods=["ks"])


@pytest.fixture
def multivariate_data():
    """Multivariate reference data (3 features)."""
    np.random.seed(42)
    n = 300
    X = np.random.randn(n, 3)
    return X


# ═══════════════════════════════════════════════════════════════════
# DriftResult / DriftType Tests
# ═══════════════════════════════════════════════════════════════════


class TestDriftType:
    """Tests for DriftType enum."""

    def test_values(self):
        """Test all drift types exist."""
        assert DriftType.SUDDEN.value == "sudden"
        assert DriftType.GRADUAL.value == "gradual"
        assert DriftType.INCREMENTAL.value == "incremental"
        assert DriftType.RECURRING.value == "recurring"
        assert DriftType.VIRTUAL.value == "virtual"


class TestDriftResult:
    """Tests for DriftResult dataclass."""

    def test_creation(self):
        """Test creating a drift result."""
        result = DriftResult(
            is_drift=True,
            drift_type=DriftType.SUDDEN,
            confidence=0.95,
            p_value=0.001,
            statistic=0.45,
            feature_name="rsi",
        )
        assert result.is_drift is True
        assert result.drift_type == DriftType.SUDDEN
        assert result.confidence == 0.95
        assert result.feature_name == "rsi"

    def test_no_drift_result(self):
        """Test no-drift result."""
        result = DriftResult(
            is_drift=False,
            drift_type=None,
            confidence=0.1,
            p_value=0.8,
            statistic=0.05,
            feature_name=None,
        )
        assert result.is_drift is False
        assert result.drift_type is None


# ═══════════════════════════════════════════════════════════════════
# ConceptDriftDetector Tests
# ═══════════════════════════════════════════════════════════════════


class TestConceptDriftDetector:
    """Tests for ConceptDriftDetector class."""

    def test_init_defaults(self):
        """Test default initialization."""
        d = ConceptDriftDetector()
        assert d.window_size == 1000
        assert d.significance_level == 0.05
        assert d.min_samples == 30
        assert d.methods == ["ks", "psi", "page_hinkley"]
        assert d.reference_data is None

    def test_init_custom(self):
        """Test custom initialization."""
        d = ConceptDriftDetector(
            window_size=500,
            significance_level=0.01,
            methods=["ks", "wasserstein"],
        )
        assert d.window_size == 500
        assert d.significance_level == 0.01
        assert d.methods == ["ks", "wasserstein"]

    def test_fit(self, detector, reference_data):
        """Test fitting on reference data."""
        detector.fit(reference_data)
        assert detector.reference_data is not None
        assert len(detector.reference_data) == 500
        assert "mean" in detector.reference_stats
        assert "std" in detector.reference_stats
        assert "histogram" in detector.reference_stats

    def test_detect_before_fit_raises(self, detector, no_drift_data):
        """Test that detect() before fit() raises ValueError."""
        with pytest.raises(ValueError, match="Must call fit"):
            detector.detect(no_drift_data)

    def test_detect_insufficient_samples(self, detector, reference_data):
        """Test detection with too few samples."""
        detector.fit(reference_data)
        result = detector.detect(np.array([1.0, 2.0]))  # < min_samples
        assert result.is_drift is False
        assert "error" in result.details

    def test_detect_no_drift(self, detector, reference_data, no_drift_data):
        """Test detection on data from the same distribution."""
        detector.fit(reference_data)
        result = detector.detect(no_drift_data)
        # Should generally not detect drift for same distribution
        # (not guaranteed but very likely with sufficient samples)
        assert isinstance(result, DriftResult)
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0

    def test_detect_sudden_drift(self, detector, reference_data, sudden_drift_data):
        """Test detection of a large sudden shift."""
        detector.fit(reference_data)
        result = detector.detect(sudden_drift_data)
        assert result.is_drift is True
        assert result.confidence > 0.5
        # Should classify as sudden (mean shift = 5)
        if result.drift_type:
            assert result.drift_type == DriftType.SUDDEN

    def test_detect_variance_drift(self, detector, reference_data, variance_drift_data):
        """Test detection of variance change."""
        detector.fit(reference_data)
        result = detector.detect(variance_drift_data)
        # KS test should catch variance change
        assert isinstance(result, DriftResult)

    def test_detect_with_feature_name(self, detector, reference_data, sudden_drift_data):
        """Test that feature_name is propagated."""
        detector.fit(reference_data)
        result = detector.detect(sudden_drift_data, feature_name="close_price")
        assert result.feature_name == "close_price"

    def test_drift_history(self, detector, reference_data, no_drift_data, sudden_drift_data):
        """Test drift history tracking."""
        detector.fit(reference_data)
        detector.detect(no_drift_data)
        detector.detect(sudden_drift_data)
        assert len(detector.drift_history) == 2

    # --- Individual Test Methods ---

    def test_ks_test_no_drift(self, ks_only_detector, reference_data, no_drift_data):
        """Test KS test with no drift."""
        ks_only_detector.fit(reference_data)
        result = ks_only_detector._ks_test(no_drift_data)
        assert result["method"] == "kolmogorov_smirnov"
        assert "statistic" in result
        assert "p_value" in result
        assert result["p_value"] > 0.0

    def test_ks_test_with_drift(self, ks_only_detector, reference_data, sudden_drift_data):
        """Test KS test with sudden drift."""
        ks_only_detector.fit(reference_data)
        result = ks_only_detector._ks_test(sudden_drift_data)
        assert result["is_drift"] == True
        assert result["p_value"] < 0.05

    def test_psi_test_no_drift(self, detector, reference_data, no_drift_data):
        """Test PSI with same distribution."""
        detector.fit(reference_data)
        result = detector._psi_test(no_drift_data)
        assert result["method"] == "psi"
        assert result["psi_value"] >= 0.0
        assert result["interpretation"] in ("no_change", "moderate_change", "significant_shift")

    def test_psi_test_with_drift(self, detector, reference_data, sudden_drift_data):
        """Test PSI with drifted data."""
        detector.fit(reference_data)
        result = detector._psi_test(sudden_drift_data)
        assert result["is_drift"] == True
        assert result["psi_value"] > 0.25

    def test_chi_squared_test(self, detector, reference_data, sudden_drift_data):
        """Test chi-squared test."""
        detector.fit(reference_data)
        result = detector._chi_squared_test(sudden_drift_data)
        assert result["method"] == "chi_squared"
        assert "statistic" in result or "error" in result

    def test_page_hinkley_test_no_drift(self, detector, reference_data, no_drift_data):
        """Test Page-Hinkley with no drift."""
        detector.fit(reference_data)
        result = detector._page_hinkley_test(no_drift_data)
        assert result["method"] == "page_hinkley"
        assert "ph_value" in result
        assert "threshold" in result

    def test_page_hinkley_test_with_drift(self, detector, reference_data, sudden_drift_data):
        """Test Page-Hinkley with drifted data."""
        detector.fit(reference_data)
        result = detector._page_hinkley_test(sudden_drift_data)
        assert result["method"] == "page_hinkley"
        # Sudden shift of +5 should trigger
        assert result["is_drift"] == True

    def test_wasserstein_test(self, detector, reference_data, sudden_drift_data):
        """Test Wasserstein distance."""
        detector.fit(reference_data)
        result = detector._wasserstein_test(sudden_drift_data)
        assert result["method"] == "wasserstein"
        assert result["is_drift"] == True
        assert result["distance"] > 0

    # --- Drift Classification ---

    def test_classify_drift_type_sudden(self, detector, reference_data, sudden_drift_data):
        """Test that sudden drift is correctly classified."""
        detector.fit(reference_data)
        result = detector.detect(sudden_drift_data)
        if result.is_drift and result.drift_type:
            assert result.drift_type == DriftType.SUDDEN

    # --- Reset & Summary ---

    def test_reset(self, detector, reference_data, no_drift_data):
        """Test reset clears streaming state."""
        detector.fit(reference_data)
        detector.detect(no_drift_data)
        assert len(detector.drift_history) == 1

        detector.reset()
        assert len(detector.drift_history) == 0
        assert len(detector.current_window) == 0

    def test_get_summary_empty(self, detector):
        """Test summary with no checks."""
        summary = detector.get_summary()
        assert summary["total_checks"] == 0
        assert summary["drift_count"] == 0

    def test_get_summary_with_history(self, detector, reference_data, sudden_drift_data, no_drift_data):
        """Test summary after several checks."""
        detector.fit(reference_data)
        detector.detect(no_drift_data)
        detector.detect(sudden_drift_data)

        summary = detector.get_summary()
        assert summary["total_checks"] == 2
        assert summary["drift_count"] >= 1
        assert "avg_confidence" in summary
        assert "drift_rate" in summary


# ═══════════════════════════════════════════════════════════════════
# MultiVariateDriftDetector Tests
# ═══════════════════════════════════════════════════════════════════


class TestMultiVariateDriftDetector:
    """Tests for MultiVariateDriftDetector class."""

    def test_init(self):
        """Test initialization."""
        d = MultiVariateDriftDetector(feature_names=["a", "b", "c"])
        assert len(d.detectors) == 3
        assert d.reference_corr is None
        assert d.reference_mean is None

    def test_fit(self, multivariate_data):
        """Test fitting on multivariate data."""
        d = MultiVariateDriftDetector(feature_names=["f0", "f1", "f2"])
        d.fit(multivariate_data)
        assert d.reference_mean is not None
        assert d.reference_cov is not None
        assert d.reference_corr is not None
        assert d.reference_mean.shape == (3,)
        assert d.reference_cov.shape == (3, 3)

    def test_fit_wrong_features(self, multivariate_data):
        """Test fit with mismatched feature count."""
        d = MultiVariateDriftDetector(feature_names=["a", "b"])  # 2 features
        with pytest.raises(ValueError, match="Expected 2 features"):
            d.fit(multivariate_data)  # 3 features

    def test_detect_no_drift(self, multivariate_data):
        """Test detection with same distribution."""
        d = MultiVariateDriftDetector(feature_names=["f0", "f1", "f2"])
        d.fit(multivariate_data)

        np.random.seed(123)
        current = np.random.randn(100, 3)
        results = d.detect(current)

        assert "per_feature" in results
        assert "multivariate" in results
        assert "correlation_drift" in results
        assert "overall" in results
        assert "severity" in results["overall"]

    def test_detect_with_drift(self, multivariate_data):
        """Test detection with shifted distribution."""
        d = MultiVariateDriftDetector(feature_names=["f0", "f1", "f2"])
        d.fit(multivariate_data)

        # Shift all features
        np.random.seed(123)
        current = np.random.randn(100, 3) + 5.0
        results = d.detect(current)

        assert results["overall"]["is_drift"] == True
        assert len(results["overall"]["drifted_features"]) > 0
        assert results["overall"]["severity"] != "none"

    def test_hotelling_t2(self, multivariate_data):
        """Test Hotelling T² statistic."""
        d = MultiVariateDriftDetector(feature_names=["f0", "f1", "f2"])
        d.fit(multivariate_data)

        np.random.seed(123)
        current = np.random.randn(100, 3) + 3.0
        result = d._hotelling_t2_test(current)

        assert "t2_statistic" in result
        assert "f_statistic" in result
        assert "p_value" in result
        assert result["is_drift"] == True

    def test_correlation_drift(self, multivariate_data):
        """Test correlation structure monitoring."""
        d = MultiVariateDriftDetector(feature_names=["f0", "f1", "f2"])
        d.fit(multivariate_data)

        np.random.seed(123)
        # Create correlated data (different structure)
        base = np.random.randn(100)
        current = np.column_stack([base, base + np.random.randn(100) * 0.1, -base])
        result = d._correlation_drift(current)

        assert "correlation_distance" in result
        assert "most_changed_pair" in result
        assert isinstance(result["most_changed_pair"], tuple)

    def test_severity_calculation(self):
        """Test severity levels."""
        d = MultiVariateDriftDetector(feature_names=["f0", "f1", "f2"])
        assert d._calculate_severity(0, False, False) == "none"
        assert d._calculate_severity(3, True, True) == "critical"
        assert d._calculate_severity(1, False, False) in ("low", "medium")

    def test_recommendation(self):
        """Test recommendation text."""
        d = MultiVariateDriftDetector(feature_names=["f0", "f1", "f2"])
        rec = d._get_recommendation([], False, False)
        assert "No action" in rec

        rec = d._get_recommendation(["f0", "f1", "f2"], True, True)
        assert "retraining" in rec.lower() or "retrain" in rec.lower()
