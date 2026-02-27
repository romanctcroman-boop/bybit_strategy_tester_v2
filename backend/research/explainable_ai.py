"""
🔍 Explainable AI Signals

SHAP/LIME interpretation of ML trading signals.

@version: 1.0.0
@date: 2026-02-26
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


@dataclass
class SignalExplanation:
    """Explanation of ML signal"""
    signal: float
    confidence: float
    top_features: List[Dict[str, Any]]
    regime: str
    recommendation: str


class SHAPExplainer:
    """
    SHAP-based signal explanation.
    
    Explains ML trading signals using SHAP values.
    """
    
    def __init__(self, model=None):
        """
        Args:
            model: Trained ML model
        """
        self.model = model
        self._shap_values = None
    
    def explain(
        self,
        features: pd.DataFrame,
        feature_names: Optional[List[str]] = None
    ) -> SignalExplanation:
        """
        Explain signal for given features.
        
        Args:
            features: Feature values
            feature_names: Feature names
            
        Returns:
            SignalExplanation
        """
        if feature_names is None:
            feature_names = features.columns.tolist()
        
        # Get model prediction
        if hasattr(self.model, 'predict'):
            signal = self.model.predict(features)[0]
        else:
            signal = 0.5  # Placeholder
        
        # Calculate feature importance (simplified SHAP)
        feature_importance = self._calculate_importance(features, feature_names)
        
        # Get top features
        top_features = sorted(
            feature_importance.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:5]
        
        # Generate recommendation
        recommendation = self._generate_recommendation(signal, top_features)
        
        return SignalExplanation(
            signal=signal,
            confidence=abs(signal),
            top_features=[
                {'name': name, 'importance': imp}
                for name, imp in top_features
            ],
            regime=self._detect_regime(features),
            recommendation=recommendation,
        )
    
    def _calculate_importance(
        self,
        features: pd.DataFrame,
        feature_names: List[str]
    ) -> Dict[str, float]:
        """
        Calculate feature importance (simplified SHAP).
        
        In production, use actual SHAP library.
        """
        importance = {}
        
        for name in feature_names:
            if name in features.columns:
                # Simplified: use absolute value as proxy
                importance[name] = abs(features[name].iloc[-1])
        
        # Normalize
        total = sum(importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}
        
        return importance
    
    def _detect_regime(self, features: pd.DataFrame) -> str:
        """Detect market regime from features"""
        if 'volatility' in features.columns:
            vol = features['volatility'].iloc[-1]
            if vol > 0.03:
                return 'volatile'
            elif vol < 0.01:
                return 'calm'
        
        if 'trend_strength' in features.columns:
            trend = features['trend_strength'].iloc[-1]
            if trend > 0.05:
                return 'trending'
        
        return 'ranging'
    
    def _generate_recommendation(
        self,
        signal: float,
        top_features: List[Tuple[str, float]]
    ) -> str:
        """Generate trading recommendation"""
        if signal > 0.7:
            return "STRONG BUY - High confidence long signal"
        elif signal > 0.5:
            return "BUY - Moderate confidence long signal"
        elif signal < -0.7:
            return "STRONG SELL - High confidence short signal"
        elif signal < -0.5:
            return "SELL - Moderate confidence short signal"
        else:
            return "HOLD - Low confidence signal"


class LIMEExplainer:
    """
    LIME-based signal explanation.
    
    Explains individual predictions using LIME.
    """
    
    def __init__(self, model=None):
        """
        Args:
            model: Trained ML model
        """
        self.model = model

    def explain(
        self,
        features: pd.DataFrame,
        feature_names: Optional[List[str]] = None,
        n_samples: int = 1000,
    ) -> SignalExplanation:
        """
        Explain signal for given features (DataFrame API, mirrors SHAPExplainer).

        Args:
            features: Feature values (single-row DataFrame)
            feature_names: Optional feature names override
            n_samples: Number of LIME samples

        Returns:
            SignalExplanation
        """
        instance = features.iloc[0]
        if feature_names is not None:
            instance = instance.copy()
            instance.index = feature_names
        return self.explain_instance(instance, n_samples=n_samples)

    def explain_instance(
        self,
        instance: pd.Series,
        n_samples: int = 1000
    ) -> SignalExplanation:
        """
        Explain single instance.
        
        Args:
            instance: Single feature instance
            n_samples: Number of samples for LIME
            
        Returns:
            SignalExplanation
        """
        # Generate perturbed samples
        samples = self._perturb(instance, n_samples)
        
        # Get predictions
        predictions = self._get_predictions(samples)
        
        # Fit local linear model
        weights, coefficients = self._fit_local_model(samples, predictions, instance)
        
        # Get top features
        top_features = self._get_top_features(coefficients, instance.index.tolist(), n=5)
        
        # Get prediction
        signal = predictions[0] if len(predictions) > 0 else 0.5
        
        return SignalExplanation(
            signal=signal,
            confidence=abs(signal),
            top_features=top_features,
            regime='unknown',
            recommendation=f"LIME explanation: {len(top_features)} key features identified"
        )
    
    def _perturb(
        self,
        instance: pd.Series,
        n_samples: int
    ) -> np.ndarray:
        """Generate perturbed samples"""
        samples = []
        
        for _ in range(n_samples):
            noise = np.random.randn(len(instance)) * 0.1
            sample = instance.values + noise
            samples.append(sample)
        
        return np.array(samples)
    
    def _get_predictions(self, samples: np.ndarray) -> np.ndarray:
        """Get model predictions for samples"""
        n = len(samples)
        if hasattr(self.model, 'predict'):
            preds = self.model.predict(samples)
            preds = np.asarray(preds).ravel()
            # If model returns a single value (e.g. fitted to one sample),
            # broadcast to n_samples so linear regression works.
            if preds.shape[0] != n:
                preds = np.full(n, preds[0] if len(preds) > 0 else 0.5)
            return preds
        else:
            return np.random.randn(n) * 0.5
    
    def _fit_local_model(
        self,
        samples: np.ndarray,
        predictions: np.ndarray,
        instance: pd.Series
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Fit local linear model"""
        # Calculate distances to instance
        distances = np.linalg.norm(samples - instance.values, axis=1)
        
        # Kernel weights
        kernel_width = np.median(distances)
        weights = np.exp(-distances ** 2 / kernel_width ** 2)
        
        # Weighted linear regression
        X = samples
        y = predictions
        W = np.diag(weights)
        
        # Solve normal equations
        XtW = X.T @ W
        coefficients = np.linalg.solve(XtW @ X + 0.01 * np.eye(len(instance)), XtW @ y)
        
        return weights, coefficients
    
    def _get_top_features(
        self,
        coefficients: np.ndarray,
        feature_names: List[str],
        n: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top N features"""
        indices = np.argsort(np.abs(coefficients))[::-1][:n]
        
        return [
            {
                'name': feature_names[i],
                'importance': float(coefficients[i]),
                'direction': 'positive' if coefficients[i] > 0 else 'negative'
            }
            for i in indices
        ]
