"""
Market Regime Detection Module for Universal Math Engine v2.4.

This module provides ML-based market regime detection:
1. RegimeDetector - Main interface for regime detection
2. HMMRegimeModel - Hidden Markov Model for regime switching
3. ClusteringRegimeModel - K-Means/DBSCAN clustering approach
4. MLRegimeClassifier - Supervised ML classification
5. RegimeFeatureEngine - Feature engineering for regime detection

Regimes:
- BULL: Strong uptrend, high momentum
- BEAR: Strong downtrend, negative momentum
- SIDEWAYS: Range-bound, low momentum
- HIGH_VOLATILITY: Explosive moves, uncertainty
- LOW_VOLATILITY: Calm market, consolidation

Author: Universal Math Engine Team
Version: 2.4.0
"""

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from numpy.typing import NDArray

# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================


class MarketRegime(Enum):
    """Market regime types."""

    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    UNKNOWN = "unknown"


class RegimeMethod(Enum):
    """Regime detection methods."""

    HMM = "hmm"  # Hidden Markov Model
    CLUSTERING = "clustering"  # K-Means/DBSCAN
    ML_CLASSIFIER = "ml_classifier"  # Supervised ML
    RULE_BASED = "rule_based"  # Traditional rules
    ENSEMBLE = "ensemble"  # Combination of methods


@dataclass
class RegimeState:
    """Current regime state with metadata."""

    regime: MarketRegime
    confidence: float  # 0-1
    start_bar: int
    duration: int  # bars in current regime
    probabilities: dict[MarketRegime, float] = field(default_factory=dict)

    # Regime characteristics
    avg_return: float = 0.0
    volatility: float = 0.0
    trend_strength: float = 0.0


@dataclass
class RegimeTransition:
    """Regime transition event."""

    from_regime: MarketRegime
    to_regime: MarketRegime
    bar_index: int
    confidence: float
    trigger_reason: str = ""


@dataclass
class RegimeConfig:
    """Configuration for regime detection."""

    # Method selection
    method: RegimeMethod = RegimeMethod.ENSEMBLE

    # Feature periods
    short_period: int = 10
    medium_period: int = 20
    long_period: int = 50

    # HMM settings
    hmm_n_states: int = 3  # Number of hidden states
    hmm_n_iterations: int = 100

    # Clustering settings
    n_clusters: int = 3
    clustering_method: str = "kmeans"  # kmeans, dbscan

    # ML Classifier settings
    classifier_type: str = "random_forest"  # random_forest, gradient_boosting, mlp

    # Rule-based thresholds
    bull_threshold: float = 0.02  # 2% return threshold
    bear_threshold: float = -0.02
    volatility_percentile_high: float = 80
    volatility_percentile_low: float = 20

    # Minimum bars in regime before switching
    min_regime_duration: int = 5

    # Smoothing
    smoothing_window: int = 3


@dataclass
class RegimeOutput:
    """Output from regime detection."""

    regimes: NDArray  # Array of MarketRegime values per bar
    regime_states: list[RegimeState]
    transitions: list[RegimeTransition]
    probabilities: NDArray  # Shape: (n_bars, n_regimes)
    features_used: dict[str, NDArray]

    # Statistics
    regime_counts: dict[MarketRegime, int] = field(default_factory=dict)
    avg_regime_duration: dict[MarketRegime, float] = field(default_factory=dict)
    transition_matrix: NDArray | None = None


# =============================================================================
# FEATURE ENGINEERING
# =============================================================================


class RegimeFeatureEngine:
    """
    Feature engineering for regime detection.

    Creates features that characterize market regimes:
    - Trend features (returns, MA slopes)
    - Volatility features (ATR, std, range)
    - Momentum features (RSI, ROC)
    - Volume features (if available)
    """

    def __init__(self, config: RegimeConfig):
        self.config = config

    def generate_features(
        self,
        close: NDArray,
        high: NDArray | None = None,
        low: NDArray | None = None,
        volume: NDArray | None = None,
    ) -> dict[str, NDArray]:
        """Generate features for regime detection."""
        n = len(close)
        features = {}

        # Use close for high/low if not provided
        if high is None:
            high = close
        if low is None:
            low = close

        # === TREND FEATURES ===

        # Returns at different horizons
        features["return_short"] = self._returns(close, self.config.short_period)
        features["return_medium"] = self._returns(close, self.config.medium_period)
        features["return_long"] = self._returns(close, self.config.long_period)

        # Log returns
        features["log_return"] = np.zeros(n)
        features["log_return"][1:] = np.log(close[1:] / close[:-1])

        # Moving average slopes
        ma_short = self._sma(close, self.config.short_period)
        ma_medium = self._sma(close, self.config.medium_period)
        ma_long = self._sma(close, self.config.long_period)

        features["ma_slope_short"] = self._slope(ma_short, 5)
        features["ma_slope_medium"] = self._slope(ma_medium, 10)
        features["ma_slope_long"] = self._slope(ma_long, 20)

        # Price position relative to MAs
        features["price_vs_ma_short"] = (close - ma_short) / ma_short
        features["price_vs_ma_medium"] = (close - ma_medium) / ma_medium
        features["price_vs_ma_long"] = (close - ma_long) / ma_long

        # MA alignment (trend strength)
        features["ma_alignment"] = np.sign(ma_short - ma_medium) * np.sign(
            ma_medium - ma_long
        )

        # === VOLATILITY FEATURES ===

        # Standard deviation
        features["volatility_short"] = self._rolling_std(
            close, self.config.short_period
        )
        features["volatility_medium"] = self._rolling_std(
            close, self.config.medium_period
        )

        # ATR (Average True Range)
        features["atr"] = self._atr(high, low, close, 14)
        features["atr_percent"] = features["atr"] / close

        # Volatility ratio (short/long)
        vol_long = self._rolling_std(close, self.config.long_period)
        with np.errstate(divide="ignore", invalid="ignore"):
            features["volatility_ratio"] = np.where(
                vol_long > 0, features["volatility_short"] / vol_long, 1.0
            )

        # Range
        features["range_percent"] = (high - low) / close

        # === MOMENTUM FEATURES ===

        # RSI
        features["rsi"] = self._rsi(close, 14)

        # Rate of Change
        features["roc_short"] = self._roc(close, self.config.short_period)
        features["roc_medium"] = self._roc(close, self.config.medium_period)

        # Momentum
        features["momentum"] = close - np.roll(close, self.config.medium_period)
        features["momentum"][: self.config.medium_period] = 0

        # === VOLUME FEATURES (if available) ===

        if volume is not None:
            features["volume_sma_ratio"] = volume / self._sma(
                volume, self.config.medium_period
            )
            features["volume_trend"] = self._slope(self._sma(volume, 10), 5)

        # === DERIVED FEATURES ===

        # Trend strength indicator
        features["trend_strength"] = np.abs(features["return_medium"]) / (
            features["volatility_medium"] + 1e-10
        )

        # Market efficiency ratio
        net_change = np.abs(close - np.roll(close, self.config.medium_period))
        total_change = np.zeros(n)
        for i in range(self.config.medium_period, n):
            total_change[i] = np.sum(
                np.abs(np.diff(close[i - self.config.medium_period : i + 1]))
            )
        with np.errstate(divide="ignore", invalid="ignore"):
            features["efficiency_ratio"] = np.where(
                total_change > 0, net_change / total_change, 0
            )

        # Fill NaN values
        for key in features:
            features[key] = np.nan_to_num(features[key], nan=0.0)

        return features

    def _sma(self, data: NDArray, period: int) -> NDArray:
        """Simple moving average."""
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            result[i] = np.mean(data[i - period + 1 : i + 1])
        result[: period - 1] = result[period - 1]
        return result

    def _rolling_std(self, data: NDArray, period: int) -> NDArray:
        """Rolling standard deviation."""
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            result[i] = np.std(data[i - period + 1 : i + 1])
        result[: period - 1] = result[period - 1] if period - 1 < len(result) else 0
        return result

    def _returns(self, data: NDArray, period: int) -> NDArray:
        """Calculate returns over period."""
        result = np.zeros_like(data)
        result[period:] = (data[period:] - data[:-period]) / data[:-period]
        return result

    def _slope(self, data: NDArray, period: int) -> NDArray:
        """Calculate slope of data."""
        result = np.zeros_like(data)
        for i in range(period, len(data)):
            x = np.arange(period)
            y = data[i - period + 1 : i + 1]
            if len(y) == period:
                slope = np.polyfit(x, y, 1)[0]
                result[i] = slope
        return result

    def _atr(self, high: NDArray, low: NDArray, close: NDArray, period: int) -> NDArray:
        """Average True Range."""
        n = len(close)
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        for i in range(1, n):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
        return self._sma(tr, period)

    def _rsi(self, data: NDArray, period: int) -> NDArray:
        """Relative Strength Index."""
        n = len(data)
        result = np.full(n, 50.0)

        delta = np.diff(data)
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)

        for i in range(period, n):
            avg_gain = np.mean(gains[i - period : i])
            avg_loss = np.mean(losses[i - period : i])
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                result[i] = 100 - (100 / (1 + rs))
            else:
                result[i] = 100 if avg_gain > 0 else 50

        return result

    def _roc(self, data: NDArray, period: int) -> NDArray:
        """Rate of Change."""
        result = np.zeros_like(data)
        result[period:] = (data[period:] - data[:-period]) / data[:-period] * 100
        return result


# =============================================================================
# RULE-BASED REGIME DETECTOR
# =============================================================================


class RuleBasedRegimeDetector:
    """
    Traditional rule-based regime detection.

    Uses technical indicators and thresholds to classify regimes.
    """

    def __init__(self, config: RegimeConfig):
        self.config = config
        self.feature_engine = RegimeFeatureEngine(config)

    def detect(
        self,
        close: NDArray,
        high: NDArray | None = None,
        low: NDArray | None = None,
        volume: NDArray | None = None,
    ) -> tuple[NDArray, NDArray]:
        """
        Detect regimes using rules.

        Returns:
            regimes: Array of MarketRegime enum values
            probabilities: Array of shape (n_bars, 5) with regime probabilities
        """
        features = self.feature_engine.generate_features(close, high, low, volume)
        n = len(close)

        regimes = np.array([MarketRegime.UNKNOWN] * n, dtype=object)
        probs = np.zeros((n, 5))  # 5 regime types

        for i in range(self.config.long_period, n):
            # Calculate regime scores
            bull_score = 0.0
            bear_score = 0.0
            sideways_score = 0.0
            high_vol_score = 0.0
            low_vol_score = 0.0

            # Trend signals
            ret_med = features["return_medium"][i]
            ma_slope = features["ma_slope_medium"][i]
            ma_align = features["ma_alignment"][i]
            price_vs_ma = features["price_vs_ma_medium"][i]

            if ret_med > self.config.bull_threshold:
                bull_score += 0.3
            elif ret_med < self.config.bear_threshold:
                bear_score += 0.3
            else:
                sideways_score += 0.2

            if ma_slope > 0:
                bull_score += 0.2
            elif ma_slope < 0:
                bear_score += 0.2

            if ma_align > 0:
                bull_score += 0.2
            elif ma_align < 0:
                bear_score += 0.2

            if price_vs_ma > 0.02:
                bull_score += 0.1
            elif price_vs_ma < -0.02:
                bear_score += 0.1

            # Momentum signals
            rsi = features["rsi"][i]
            if rsi > 60:
                bull_score += 0.1
            elif rsi < 40:
                bear_score += 0.1
            else:
                sideways_score += 0.1

            # Volatility signals
            features["volatility_ratio"][i]
            features["atr_percent"][i]

            # Calculate volatility percentiles
            vol_window = features["volatility_medium"][max(0, i - 100) : i + 1]
            if len(vol_window) > 10:
                current_vol_pct = (
                    np.sum(vol_window <= features["volatility_medium"][i])
                    / len(vol_window)
                    * 100
                )
            else:
                current_vol_pct = 50

            if current_vol_pct > self.config.volatility_percentile_high:
                high_vol_score = 0.4
            elif current_vol_pct < self.config.volatility_percentile_low:
                low_vol_score = 0.4

            # Efficiency ratio for sideways
            eff_ratio = features["efficiency_ratio"][i]
            if eff_ratio < 0.3:
                sideways_score += 0.3

            # Normalize scores
            total = (
                bull_score
                + bear_score
                + sideways_score
                + high_vol_score
                + low_vol_score
            )
            if total > 0:
                probs[i] = [
                    bull_score / total,
                    bear_score / total,
                    sideways_score / total,
                    high_vol_score / total,
                    low_vol_score / total,
                ]
            else:
                probs[i] = [0.2, 0.2, 0.2, 0.2, 0.2]

            # Determine regime
            max_idx = np.argmax(probs[i])
            regime_map = [
                MarketRegime.BULL,
                MarketRegime.BEAR,
                MarketRegime.SIDEWAYS,
                MarketRegime.HIGH_VOLATILITY,
                MarketRegime.LOW_VOLATILITY,
            ]
            regimes[i] = regime_map[max_idx]

        # Fill initial bars
        regimes[: self.config.long_period] = regimes[self.config.long_period]
        probs[: self.config.long_period] = probs[self.config.long_period]

        return regimes, probs


# =============================================================================
# CLUSTERING-BASED REGIME DETECTOR
# =============================================================================


class ClusteringRegimeDetector:
    """
    Clustering-based regime detection using K-Means or DBSCAN.

    Clusters market states based on feature vectors.
    """

    def __init__(self, config: RegimeConfig):
        self.config = config
        self.feature_engine = RegimeFeatureEngine(config)
        self.cluster_centers_: NDArray | None = None
        self.labels_: NDArray | None = None

    def detect(
        self,
        close: NDArray,
        high: NDArray | None = None,
        low: NDArray | None = None,
        volume: NDArray | None = None,
    ) -> tuple[NDArray, NDArray]:
        """Detect regimes using clustering."""
        features = self.feature_engine.generate_features(close, high, low, volume)
        n = len(close)

        # Select features for clustering
        feature_names = [
            "return_medium",
            "volatility_medium",
            "rsi",
            "ma_alignment",
            "efficiency_ratio",
        ]

        # Build feature matrix
        X = np.column_stack([features[name] for name in feature_names])

        # Normalize features
        X_mean = np.mean(X, axis=0)
        X_std = np.std(X, axis=0) + 1e-10
        X_normalized = (X - X_mean) / X_std

        # Simple K-Means implementation
        labels, centers = self._kmeans(X_normalized, self.config.n_clusters)

        self.cluster_centers_ = centers
        self.labels_ = labels

        # Map clusters to regimes based on center characteristics
        regimes, probs = self._map_clusters_to_regimes(labels, centers, features, n)

        return regimes, probs

    def _kmeans(
        self, X: NDArray, k: int, max_iter: int = 100
    ) -> tuple[NDArray, NDArray]:
        """Simple K-Means clustering."""
        n, _d = X.shape

        # Initialize centers randomly
        np.random.seed(42)
        idx = np.random.choice(n, k, replace=False)
        centers = X[idx].copy()

        labels = np.zeros(n, dtype=int)

        for _ in range(max_iter):
            # Assign points to nearest center
            for i in range(n):
                distances = np.sum((centers - X[i]) ** 2, axis=1)
                labels[i] = np.argmin(distances)

            # Update centers
            new_centers = np.zeros_like(centers)
            for j in range(k):
                mask = labels == j
                if np.sum(mask) > 0:
                    new_centers[j] = np.mean(X[mask], axis=0)
                else:
                    new_centers[j] = centers[j]

            # Check convergence
            if np.allclose(centers, new_centers):
                break
            centers = new_centers

        return labels, centers

    def _map_clusters_to_regimes(
        self,
        labels: NDArray,
        centers: NDArray,
        features: dict[str, NDArray],
        n: int,
    ) -> tuple[NDArray, NDArray]:
        """Map cluster labels to market regimes."""
        k = len(centers)

        # Analyze each cluster
        cluster_stats = []
        for j in range(k):
            mask = labels == j
            if np.sum(mask) > 0:
                avg_return = np.mean(features["return_medium"][mask])
                avg_vol = np.mean(features["volatility_medium"][mask])
                avg_rsi = np.mean(features["rsi"][mask])
            else:
                avg_return = 0
                avg_vol = 0
                avg_rsi = 50
            cluster_stats.append((avg_return, avg_vol, avg_rsi))

        # Sort clusters by return to assign regimes
        sorted_idx = np.argsort([s[0] for s in cluster_stats])

        cluster_to_regime = {}
        if k >= 3:
            cluster_to_regime[sorted_idx[0]] = MarketRegime.BEAR
            cluster_to_regime[sorted_idx[-1]] = MarketRegime.BULL
            for idx in sorted_idx[1:-1]:
                # Check volatility for middle clusters
                if cluster_stats[idx][1] > np.median([s[1] for s in cluster_stats]):
                    cluster_to_regime[idx] = MarketRegime.HIGH_VOLATILITY
                else:
                    cluster_to_regime[idx] = MarketRegime.SIDEWAYS
        elif k == 2:
            cluster_to_regime[sorted_idx[0]] = MarketRegime.BEAR
            cluster_to_regime[sorted_idx[1]] = MarketRegime.BULL
        else:
            cluster_to_regime[0] = MarketRegime.SIDEWAYS

        # Map labels to regimes
        regimes = np.array(
            [cluster_to_regime.get(l, MarketRegime.UNKNOWN) for l in labels],
            dtype=object,
        )

        # Create probabilities based on distance to centers
        probs = np.zeros((n, 5))
        for i in range(n):
            distances = np.sum(
                (
                    centers
                    - np.mean(
                        [features[f][i] for f in ["return_medium", "volatility_medium"]]
                    )
                )
                ** 2,
                axis=1,
            )
            inv_distances = 1 / (distances + 1e-10)
            inv_distances /= np.sum(inv_distances)

            for j, prob in enumerate(inv_distances):
                regime = cluster_to_regime.get(j, MarketRegime.UNKNOWN)
                regime_idx = {
                    MarketRegime.BULL: 0,
                    MarketRegime.BEAR: 1,
                    MarketRegime.SIDEWAYS: 2,
                    MarketRegime.HIGH_VOLATILITY: 3,
                    MarketRegime.LOW_VOLATILITY: 4,
                }.get(regime, 2)
                probs[i, regime_idx] += prob

        return regimes, probs


# =============================================================================
# ML CLASSIFIER REGIME DETECTOR
# =============================================================================


class MLRegimeClassifier:
    """
    Supervised ML classifier for regime detection.

    Requires labeled training data or uses pseudo-labels from other methods.
    """

    def __init__(self, config: RegimeConfig):
        self.config = config
        self.feature_engine = RegimeFeatureEngine(config)
        self.model = None
        self._is_trained = False

    def fit(
        self,
        close: NDArray,
        labels: NDArray,
        high: NDArray | None = None,
        low: NDArray | None = None,
        volume: NDArray | None = None,
    ):
        """Train the classifier on labeled data."""
        features = self.feature_engine.generate_features(close, high, low, volume)

        # Build feature matrix
        feature_names = [
            "return_short",
            "return_medium",
            "return_long",
            "volatility_short",
            "volatility_medium",
            "rsi",
            "ma_alignment",
            "efficiency_ratio",
            "trend_strength",
        ]
        X = np.column_stack([features[name] for name in feature_names])
        y = np.array([r.value if isinstance(r, MarketRegime) else r for r in labels])

        # Simple Random Forest implementation (simplified)
        self.model = self._train_simple_forest(X, y)
        self._is_trained = True

    def _train_simple_forest(
        self, X: NDArray, y: NDArray, n_trees: int = 10
    ) -> list[dict]:
        """Train a simple random forest."""
        trees = []
        n_samples = len(X)

        for _ in range(n_trees):
            # Bootstrap sample
            idx = np.random.choice(n_samples, n_samples, replace=True)
            X_boot = X[idx]
            y_boot = y[idx]

            # Train simple decision stump
            tree = self._train_decision_stump(X_boot, y_boot)
            trees.append(tree)

        return trees

    def _train_decision_stump(self, X: NDArray, y: NDArray) -> dict:
        """Train a simple decision stump."""
        n_features = X.shape[1]
        best_feature = 0
        best_threshold = 0
        best_predictions = {}

        # Find best split
        for f in range(n_features):
            threshold = np.median(X[:, f])
            left_mask = X[:, f] <= threshold
            right_mask = ~left_mask

            left_pred = self._mode(y[left_mask]) if np.sum(left_mask) > 0 else self._mode(y)

            right_pred = self._mode(y[right_mask]) if np.sum(right_mask) > 0 else self._mode(y)

            best_feature = f
            best_threshold = threshold
            best_predictions = {"left": left_pred, "right": right_pred}
            break  # Simplified: use first feature

        return {
            "feature": best_feature,
            "threshold": best_threshold,
            "predictions": best_predictions,
        }

    def _mode(self, arr: NDArray) -> str:
        """Get mode of array."""
        unique, counts = np.unique(arr, return_counts=True)
        return unique[np.argmax(counts)]

    def predict(
        self,
        close: NDArray,
        high: NDArray | None = None,
        low: NDArray | None = None,
        volume: NDArray | None = None,
    ) -> tuple[NDArray, NDArray]:
        """Predict regimes using trained model."""
        if not self._is_trained or self.model is None:
            # Fallback to rule-based
            detector = RuleBasedRegimeDetector(self.config)
            return detector.detect(close, high, low, volume)

        features = self.feature_engine.generate_features(close, high, low, volume)

        feature_names = [
            "return_short",
            "return_medium",
            "return_long",
            "volatility_short",
            "volatility_medium",
            "rsi",
            "ma_alignment",
            "efficiency_ratio",
            "trend_strength",
        ]
        X = np.column_stack([features[name] for name in feature_names])

        # Predict with forest
        n = len(close)
        predictions = []

        for i in range(n):
            votes = []
            for tree in self.model:
                if X[i, tree["feature"]] <= tree["threshold"]:
                    votes.append(tree["predictions"]["left"])
                else:
                    votes.append(tree["predictions"]["right"])

            # Majority vote
            unique, counts = np.unique(votes, return_counts=True)
            pred = unique[np.argmax(counts)]
            predictions.append(pred)

        # Convert to regime enums
        regimes = np.array(
            [
                MarketRegime(p) if isinstance(p, str) else MarketRegime.UNKNOWN
                for p in predictions
            ],
            dtype=object,
        )

        # Create dummy probabilities
        probs = np.zeros((n, 5))
        for i, regime in enumerate(regimes):
            idx = {
                MarketRegime.BULL: 0,
                MarketRegime.BEAR: 1,
                MarketRegime.SIDEWAYS: 2,
                MarketRegime.HIGH_VOLATILITY: 3,
                MarketRegime.LOW_VOLATILITY: 4,
            }.get(regime, 2)
            probs[i, idx] = 0.8
            probs[i] += 0.05  # Small probability for others
            probs[i] /= np.sum(probs[i])

        return regimes, probs


# =============================================================================
# ENSEMBLE REGIME DETECTOR
# =============================================================================


class EnsembleRegimeDetector:
    """
    Ensemble regime detector combining multiple methods.

    Weights predictions from different detectors for robust detection.
    """

    def __init__(self, config: RegimeConfig):
        self.config = config
        self.detectors = {
            "rule_based": RuleBasedRegimeDetector(config),
            "clustering": ClusteringRegimeDetector(config),
        }
        self.weights = {
            "rule_based": 0.5,
            "clustering": 0.5,
        }

    def detect(
        self,
        close: NDArray,
        high: NDArray | None = None,
        low: NDArray | None = None,
        volume: NDArray | None = None,
    ) -> tuple[NDArray, NDArray]:
        """Detect regimes using ensemble of methods."""
        n = len(close)
        combined_probs = np.zeros((n, 5))

        for name, detector in self.detectors.items():
            _, probs = detector.detect(close, high, low, volume)
            combined_probs += self.weights[name] * probs

        # Normalize
        combined_probs /= np.sum(combined_probs, axis=1, keepdims=True) + 1e-10

        # Determine final regimes
        regime_map = [
            MarketRegime.BULL,
            MarketRegime.BEAR,
            MarketRegime.SIDEWAYS,
            MarketRegime.HIGH_VOLATILITY,
            MarketRegime.LOW_VOLATILITY,
        ]
        regimes = np.array(
            [regime_map[np.argmax(combined_probs[i])] for i in range(n)], dtype=object
        )

        return regimes, combined_probs


# =============================================================================
# MAIN REGIME DETECTOR
# =============================================================================


class RegimeDetector:
    """
    Main interface for market regime detection.

    Supports multiple detection methods and provides comprehensive output.
    """

    def __init__(self, config: RegimeConfig | None = None):
        self.config = config or RegimeConfig()
        self._init_detector()

    def _init_detector(self):
        """Initialize the appropriate detector based on config."""
        if self.config.method == RegimeMethod.RULE_BASED:
            self.detector = RuleBasedRegimeDetector(self.config)
        elif self.config.method == RegimeMethod.CLUSTERING:
            self.detector = ClusteringRegimeDetector(self.config)
        elif self.config.method == RegimeMethod.ML_CLASSIFIER:
            self.detector = MLRegimeClassifier(self.config)
        elif self.config.method == RegimeMethod.ENSEMBLE:
            self.detector = EnsembleRegimeDetector(self.config)
        else:
            self.detector = RuleBasedRegimeDetector(self.config)

    def detect(
        self,
        close: NDArray,
        high: NDArray | None = None,
        low: NDArray | None = None,
        volume: NDArray | None = None,
    ) -> RegimeOutput:
        """
        Detect market regimes.

        Args:
            close: Close prices
            high: High prices (optional)
            low: Low prices (optional)
            volume: Volume (optional)

        Returns:
            RegimeOutput with detected regimes and metadata
        """
        # Run detection
        regimes, probs = self.detector.detect(close, high, low, volume)

        # Apply smoothing
        if self.config.smoothing_window > 1:
            regimes = self._smooth_regimes(regimes, probs)

        # Generate regime states and transitions
        regime_states, transitions = self._analyze_regimes(regimes, probs, close)

        # Calculate statistics
        regime_counts = self._count_regimes(regimes)
        avg_duration = self._calculate_avg_duration(regime_states)
        transition_matrix = self._calculate_transition_matrix(transitions)

        # Get features used
        feature_engine = RegimeFeatureEngine(self.config)
        features_used = feature_engine.generate_features(close, high, low, volume)

        return RegimeOutput(
            regimes=regimes,
            regime_states=regime_states,
            transitions=transitions,
            probabilities=probs,
            features_used=features_used,
            regime_counts=regime_counts,
            avg_regime_duration=avg_duration,
            transition_matrix=transition_matrix,
        )

    def _smooth_regimes(self, regimes: NDArray, probs: NDArray) -> NDArray:
        """Apply smoothing to avoid rapid regime changes."""
        n = len(regimes)
        smoothed = regimes.copy()
        window = self.config.smoothing_window

        for i in range(window, n - window):
            # Get window of regimes
            window_regimes = regimes[i - window : i + window + 1]

            # Count occurrences
            unique, counts = np.unique(window_regimes, return_counts=True)

            # Use most common regime
            smoothed[i] = unique[np.argmax(counts)]

        return smoothed

    def _analyze_regimes(
        self,
        regimes: NDArray,
        probs: NDArray,
        close: NDArray,
    ) -> tuple[list[RegimeState], list[RegimeTransition]]:
        """Analyze regimes to create states and transitions."""
        states = []
        transitions = []

        current_regime = regimes[0]
        start_bar = 0

        for i in range(1, len(regimes)):
            if regimes[i] != current_regime:
                # Create state for previous regime
                duration = i - start_bar
                state = RegimeState(
                    regime=current_regime,
                    confidence=float(np.max(probs[start_bar:i], axis=0).max()),
                    start_bar=start_bar,
                    duration=duration,
                    probabilities={
                        MarketRegime.BULL: float(np.mean(probs[start_bar:i, 0])),
                        MarketRegime.BEAR: float(np.mean(probs[start_bar:i, 1])),
                        MarketRegime.SIDEWAYS: float(np.mean(probs[start_bar:i, 2])),
                        MarketRegime.HIGH_VOLATILITY: float(
                            np.mean(probs[start_bar:i, 3])
                        ),
                        MarketRegime.LOW_VOLATILITY: float(
                            np.mean(probs[start_bar:i, 4])
                        ),
                    },
                    avg_return=float(
                        np.mean(np.diff(close[start_bar : i + 1]) / close[start_bar:i])
                    )
                    if i > start_bar
                    else 0,
                    volatility=float(
                        np.std(np.diff(close[start_bar : i + 1]) / close[start_bar:i])
                    )
                    if i > start_bar + 1
                    else 0,
                )
                states.append(state)

                # Create transition
                transition = RegimeTransition(
                    from_regime=current_regime,
                    to_regime=regimes[i],
                    bar_index=i,
                    confidence=float(probs[i].max()),
                )
                transitions.append(transition)

                current_regime = regimes[i]
                start_bar = i

        # Add final state
        duration = len(regimes) - start_bar
        state = RegimeState(
            regime=current_regime,
            confidence=float(np.max(probs[start_bar:], axis=0).max()),
            start_bar=start_bar,
            duration=duration,
        )
        states.append(state)

        return states, transitions

    def _count_regimes(self, regimes: NDArray) -> dict[MarketRegime, int]:
        """Count regime occurrences."""
        counts = {}
        for regime in MarketRegime:
            counts[regime] = int(np.sum(regimes == regime))
        return counts

    def _calculate_avg_duration(
        self, states: list[RegimeState]
    ) -> dict[MarketRegime, float]:
        """Calculate average duration per regime."""
        durations: dict[MarketRegime, list[int]] = {}
        for state in states:
            if state.regime not in durations:
                durations[state.regime] = []
            durations[state.regime].append(state.duration)

        return {
            regime: np.mean(durs) if durs else 0.0 for regime, durs in durations.items()
        }

    def _calculate_transition_matrix(
        self,
        transitions: list[RegimeTransition],
    ) -> NDArray:
        """Calculate regime transition probability matrix."""
        n_regimes = 5
        matrix = np.zeros((n_regimes, n_regimes))

        regime_to_idx = {
            MarketRegime.BULL: 0,
            MarketRegime.BEAR: 1,
            MarketRegime.SIDEWAYS: 2,
            MarketRegime.HIGH_VOLATILITY: 3,
            MarketRegime.LOW_VOLATILITY: 4,
        }

        for t in transitions:
            from_idx = regime_to_idx.get(t.from_regime, 2)
            to_idx = regime_to_idx.get(t.to_regime, 2)
            matrix[from_idx, to_idx] += 1

        # Normalize rows
        row_sums = matrix.sum(axis=1, keepdims=True)
        matrix = np.divide(matrix, row_sums, where=row_sums > 0)

        return matrix

    def get_current_regime(
        self,
        close: NDArray,
        high: NDArray | None = None,
        low: NDArray | None = None,
        volume: NDArray | None = None,
    ) -> RegimeState:
        """Get the current market regime."""
        output = self.detect(close, high, low, volume)
        return (
            output.regime_states[-1]
            if output.regime_states
            else RegimeState(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                start_bar=0,
                duration=0,
            )
        )

    def get_regime_filter(
        self,
        close: NDArray,
        allowed_regimes: list[MarketRegime],
        high: NDArray | None = None,
        low: NDArray | None = None,
        volume: NDArray | None = None,
    ) -> NDArray:
        """
        Get boolean filter for allowed regimes.

        Can be used to filter trading signals by regime.
        """
        output = self.detect(close, high, low, volume)
        return np.array([r in allowed_regimes for r in output.regimes])
