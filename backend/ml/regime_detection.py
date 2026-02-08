"""
🔮 Regime Detection Module
Implements market regime detection using ML techniques
Based on Two Sigma and industry best practices 2024-2026
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

# Optional ML dependencies
try:
    from sklearn.cluster import KMeans
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from hmmlearn import hmm

    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False


class MarketRegime(Enum):
    """Market regime types"""

    BULL_LOW_VOL = "bull_low_volatility"
    BULL_HIGH_VOL = "bull_high_volatility"
    BEAR_LOW_VOL = "bear_low_volatility"
    BEAR_HIGH_VOL = "bear_high_volatility"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


@dataclass
class RegimeState:
    """Current regime state"""

    regime: MarketRegime
    confidence: float
    duration_bars: int
    mean_return: float
    volatility: float


@dataclass
class RegimeDetectionResult:
    """Result of regime detection"""

    regimes: np.ndarray  # Regime label for each bar
    n_regimes: int
    regime_names: list[str]

    # Statistics per regime
    regime_stats: dict[int, dict[str, float]] = field(default_factory=dict)

    # Transition probabilities
    transition_matrix: np.ndarray | None = None

    # Current state
    current_regime: int = 0
    current_regime_name: str = "Unknown"

    def get_regime_at(self, index: int) -> int:
        """Get regime at specific index"""
        if 0 <= index < len(self.regimes):
            return self.regimes[index]
        return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_regimes": self.n_regimes,
            "regime_names": self.regime_names,
            "current_regime": self.current_regime_name,
            "regime_stats": self.regime_stats,
            "regime_distribution": {
                name: float(np.mean(self.regimes == i))
                for i, name in enumerate(self.regime_names)
            },
        }


class HMMRegimeDetector:
    """
    Hidden Markov Model based regime detector.

    "Gaussian Hidden Markov Models group data points into clusters
    representing different market conditions." - Two Sigma

    HMM is ideal for financial time series because:
    - Captures temporal dependencies
    - Models unobservable market states
    - Provides transition probabilities
    """

    def __init__(
        self, n_regimes: int = 3, n_iter: int = 100, covariance_type: str = "full"
    ):
        """
        Initialize HMM regime detector.

        Args:
            n_regimes: Number of hidden states (regimes)
            n_iter: Number of EM iterations
            covariance_type: 'full', 'diag', 'spherical', 'tied'
        """
        if not HMM_AVAILABLE:
            raise ImportError(
                "hmmlearn is not installed. Install with: pip install hmmlearn"
            )

        self.n_regimes = n_regimes
        self.n_iter = n_iter
        self.covariance_type = covariance_type
        self.model = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None

    def fit_predict(
        self, data: pd.DataFrame, features: list[str] | None = None
    ) -> RegimeDetectionResult:
        """
        Fit HMM and predict regimes.

        Args:
            data: OHLCV DataFrame
            features: Features to use (default: returns, volatility)

        Returns:
            RegimeDetectionResult with regime predictions
        """
        # Prepare features
        X = self._prepare_features(data, features)

        if len(X) < 50:
            logger.warning("Insufficient data for regime detection")
            return self._empty_result(len(data))

        # Scale features
        if self.scaler:
            X_scaled = self.scaler.fit_transform(X)
        else:
            X_scaled = (X - np.mean(X, axis=0)) / (np.std(X, axis=0) + 1e-8)

        # Fit HMM
        self.model = hmm.GaussianHMM(
            n_components=self.n_regimes,
            covariance_type=self.covariance_type,
            n_iter=self.n_iter,
            random_state=42,
        )

        try:
            self.model.fit(X_scaled)
            regimes = self.model.predict(X_scaled)
        except Exception as e:
            logger.error(f"HMM fitting failed: {e}")
            return self._empty_result(len(data))

        # Pad to match original length (features calculation loses some bars)
        full_regimes = np.zeros(len(data), dtype=int)
        offset = len(data) - len(regimes)
        full_regimes[offset:] = regimes
        full_regimes[:offset] = regimes[0]  # Fill with first detected regime

        # Analyze regimes
        regime_stats = self._analyze_regimes(data, full_regimes)
        regime_names = self._name_regimes(regime_stats)

        # Get transition matrix
        trans_matrix = self.model.transmat_

        return RegimeDetectionResult(
            regimes=full_regimes,
            n_regimes=self.n_regimes,
            regime_names=regime_names,
            regime_stats=regime_stats,
            transition_matrix=trans_matrix,
            current_regime=int(full_regimes[-1]),
            current_regime_name=regime_names[int(full_regimes[-1])],
        )

    def predict_next_regime(
        self, current_regime: int, n_steps: int = 1
    ) -> list[tuple[int, float]]:
        """
        Predict most likely next regime(s).

        Args:
            current_regime: Current regime index
            n_steps: Number of steps ahead

        Returns:
            List of (regime, probability) tuples sorted by probability
        """
        if self.model is None:
            return [(0, 1.0)]

        trans = self.model.transmat_
        current_probs = np.zeros(self.n_regimes)
        current_probs[current_regime] = 1.0

        for _ in range(n_steps):
            current_probs = current_probs @ trans

        predictions = [(i, prob) for i, prob in enumerate(current_probs)]
        return sorted(predictions, key=lambda x: x[1], reverse=True)

    def _prepare_features(
        self, data: pd.DataFrame, features: list[str] | None
    ) -> np.ndarray:
        """Prepare features for regime detection"""
        close = data["close"].values

        # Default features: returns and volatility
        returns = np.diff(close) / close[:-1]

        # Rolling volatility (20 periods)
        volatility = pd.Series(returns).rolling(20).std().values

        # Remove NaN
        valid_mask = ~np.isnan(volatility)
        returns = returns[valid_mask[1:]]
        volatility = volatility[valid_mask]

        # Ensure same length
        min_len = min(len(returns), len(volatility))
        returns = returns[-min_len:]
        volatility = volatility[-min_len:]

        X = np.column_stack([returns, volatility])

        return X

    def _analyze_regimes(
        self, data: pd.DataFrame, regimes: np.ndarray
    ) -> dict[int, dict[str, float]]:
        """Analyze statistics for each regime"""
        close = data["close"].values
        returns = np.diff(close) / close[:-1]
        returns = np.append([0], returns)  # Pad to match length

        stats = {}
        for regime in range(self.n_regimes):
            mask = regimes == regime
            if np.sum(mask) > 0:
                regime_returns = returns[mask]
                stats[regime] = {
                    "mean_return": float(np.mean(regime_returns)),
                    "volatility": float(np.std(regime_returns)),
                    "frequency": float(np.mean(mask)),
                    "sharpe": float(
                        np.mean(regime_returns) / np.std(regime_returns) * np.sqrt(8760)
                    )
                    if np.std(regime_returns) > 0
                    else 0,
                }
            else:
                stats[regime] = {
                    "mean_return": 0,
                    "volatility": 0,
                    "frequency": 0,
                    "sharpe": 0,
                }

        return stats

    def _name_regimes(self, stats: dict[int, dict[str, float]]) -> list[str]:
        """Assign meaningful names to regimes based on characteristics"""
        names = []

        # Calculate median values for comparison
        mean_returns = [s["mean_return"] for s in stats.values()]
        volatilities = [s["volatility"] for s in stats.values()]

        median_return = np.median(mean_returns)
        median_vol = np.median(volatilities)

        for regime, s in stats.items():
            is_bull = s["mean_return"] > median_return
            is_high_vol = s["volatility"] > median_vol

            if is_bull and is_high_vol:
                name = "Bull High Volatility"
            elif is_bull and not is_high_vol:
                name = "Bull Low Volatility"
            elif not is_bull and is_high_vol:
                name = "Bear High Volatility"
            elif not is_bull and not is_high_vol:
                name = "Bear Low Volatility"
            else:
                name = f"Regime {regime}"

            names.append(name)

        return names

    def _empty_result(self, n_bars: int) -> RegimeDetectionResult:
        """Return empty result"""
        return RegimeDetectionResult(
            regimes=np.zeros(n_bars, dtype=int),
            n_regimes=1,
            regime_names=["Unknown"],
            regime_stats={
                0: {"mean_return": 0, "volatility": 0, "frequency": 1.0, "sharpe": 0}
            },
            current_regime=0,
            current_regime_name="Unknown",
        )


class KMeansRegimeDetector:
    """
    K-Means clustering based regime detector.

    Simpler alternative to HMM, useful for quick regime identification.
    """

    def __init__(self, n_regimes: int = 3):
        if not SKLEARN_AVAILABLE:
            raise ImportError("sklearn is not installed")

        self.n_regimes = n_regimes
        self.model = None
        self.scaler = StandardScaler()

    def fit_predict(
        self, data: pd.DataFrame, lookback: int = 20
    ) -> RegimeDetectionResult:
        """
        Fit K-Means and predict regimes.

        Args:
            data: OHLCV DataFrame
            lookback: Lookback period for features

        Returns:
            RegimeDetectionResult
        """
        close = data["close"].values

        # Calculate features
        returns = pd.Series(close).pct_change()
        volatility = returns.rolling(lookback).std()
        momentum = pd.Series(close).pct_change(lookback)

        # Combine features
        features = pd.DataFrame(
            {"returns": returns, "volatility": volatility, "momentum": momentum}
        ).dropna()

        if len(features) < 50:
            return self._empty_result(len(data))

        X = self.scaler.fit_transform(features.values)

        # Fit K-Means
        self.model = KMeans(n_clusters=self.n_regimes, random_state=42, n_init=10)
        regimes = self.model.fit_predict(X)

        # Pad regimes
        full_regimes = np.zeros(len(data), dtype=int)
        offset = len(data) - len(regimes)
        full_regimes[offset:] = regimes
        full_regimes[:offset] = regimes[0]

        # Analyze - fix array length alignment
        stats = {}
        # Ensure returns array matches data length
        r = returns.fillna(0).values

        for i in range(self.n_regimes):
            mask = full_regimes == i
            # Ensure mask and returns have same length
            min_len = min(len(mask), len(r))
            regime_r = r[:min_len][mask[:min_len]]
            stats[i] = {
                "mean_return": float(np.nanmean(regime_r)) if len(regime_r) > 0 else 0,
                "volatility": float(np.nanstd(regime_r)) if len(regime_r) > 0 else 0,
                "frequency": float(np.mean(mask)),
            }

        names = [f"Cluster {i}" for i in range(self.n_regimes)]

        return RegimeDetectionResult(
            regimes=full_regimes,
            n_regimes=self.n_regimes,
            regime_names=names,
            regime_stats=stats,
            current_regime=int(full_regimes[-1]),
            current_regime_name=names[int(full_regimes[-1])],
        )

    def _empty_result(self, n_bars: int) -> RegimeDetectionResult:
        return RegimeDetectionResult(
            regimes=np.zeros(n_bars, dtype=int),
            n_regimes=1,
            regime_names=["Unknown"],
            regime_stats={0: {"mean_return": 0, "volatility": 0, "frequency": 1.0}},
            current_regime=0,
            current_regime_name="Unknown",
        )


class GMMRegimeDetector:
    """
    Gaussian Mixture Model based regime detector.

    More flexible than K-Means for overlapping regimes.
    """

    def __init__(self, n_regimes: int = 3):
        if not SKLEARN_AVAILABLE:
            raise ImportError("sklearn is not installed")

        self.n_regimes = n_regimes
        self.model = None
        self.scaler = StandardScaler()

    def fit_predict(self, data: pd.DataFrame) -> RegimeDetectionResult:
        """Fit GMM and predict regimes"""
        close = data["close"].values

        returns = pd.Series(close).pct_change()
        volatility = returns.rolling(20).std()

        features = pd.DataFrame({"returns": returns, "volatility": volatility}).dropna()

        if len(features) < 50:
            return self._empty_result(len(data))

        X = self.scaler.fit_transform(features.values)

        self.model = GaussianMixture(
            n_components=self.n_regimes, random_state=42, n_init=5
        )
        regimes = self.model.fit_predict(X)

        # Pad
        full_regimes = np.zeros(len(data), dtype=int)
        offset = len(data) - len(regimes)
        full_regimes[offset:] = regimes
        full_regimes[:offset] = regimes[0]

        return RegimeDetectionResult(
            regimes=full_regimes,
            n_regimes=self.n_regimes,
            regime_names=[f"GMM Regime {i}" for i in range(self.n_regimes)],
            current_regime=int(full_regimes[-1]),
            current_regime_name=f"GMM Regime {int(full_regimes[-1])}",
        )

    def _empty_result(self, n_bars: int) -> RegimeDetectionResult:
        return RegimeDetectionResult(
            regimes=np.zeros(n_bars, dtype=int),
            n_regimes=1,
            regime_names=["Unknown"],
            current_regime=0,
            current_regime_name="Unknown",
        )


class RegimeAdaptiveStrategy:
    """
    Wrapper for strategies that adapt to market regimes.

    Allows different parameters or strategies for different regimes.
    """

    def __init__(self, detector: Any, regime_strategies: dict[int, dict[str, Any]]):
        """
        Initialize regime-adaptive strategy.

        Args:
            detector: Regime detector instance
            regime_strategies: Dict mapping regime index to strategy params
        """
        self.detector = detector
        self.regime_strategies = regime_strategies

    def get_strategy_params(self, current_regime: int) -> dict[str, Any]:
        """Get strategy parameters for current regime"""
        return self.regime_strategies.get(
            current_regime, self.regime_strategies.get(0, {})
        )

    def should_trade(self, current_regime: int) -> bool:
        """Check if trading is allowed in current regime"""
        params = self.get_strategy_params(current_regime)
        return params.get("enabled", True)


def get_regime_detector(method: str = "hmm", n_regimes: int = 3) -> Any:
    """
    Factory function to get regime detector.

    Args:
        method: 'hmm', 'kmeans', or 'gmm'
        n_regimes: Number of regimes

    Returns:
        Regime detector instance
    """
    if method == "hmm":
        if HMM_AVAILABLE:
            return HMMRegimeDetector(n_regimes=n_regimes)
        else:
            logger.warning("hmmlearn not available, falling back to GMM")
            method = "gmm"

    if method == "kmeans":
        return KMeansRegimeDetector(n_regimes=n_regimes)

    if method == "gmm":
        return GMMRegimeDetector(n_regimes=n_regimes)

    raise ValueError(f"Unknown method: {method}")
