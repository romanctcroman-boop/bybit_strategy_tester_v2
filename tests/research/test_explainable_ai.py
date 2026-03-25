"""Tests for P3-6: Explainable AI Signals."""

import numpy as np
import pandas as pd
import pytest

from backend.research import LIMEExplainer, SHAPExplainer, SignalExplanation


class MockModel:
    """Simple mock model for testing."""

    def predict(self, X):
        # Return positive signal
        return np.array([0.7])


@pytest.fixture
def features():
    return pd.DataFrame(
        {
            "rsi": [65.0],
            "macd": [0.5],
            "volume": [1_000_000.0],
            "ema_short": [50100.0],
            "ema_long": [49800.0],
        }
    )


@pytest.fixture
def shap_explainer():
    return SHAPExplainer(model=MockModel())


@pytest.fixture
def lime_explainer():
    return LIMEExplainer(model=MockModel())


class TestSignalExplanation:
    def test_create(self):
        se = SignalExplanation(
            signal=0.7,
            confidence=0.7,
            top_features=[{"name": "rsi", "importance": 0.5}],
            regime="trending",
            recommendation="BUY",
        )
        assert se.signal == 0.7
        assert se.regime == "trending"
        assert len(se.top_features) == 1


class TestSHAPExplainer:
    def test_init_no_model(self):
        exp = SHAPExplainer()
        assert exp.model is None

    def test_init_with_model(self, shap_explainer):
        assert shap_explainer.model is not None

    def test_explain_returns_signal_explanation(self, shap_explainer, features):
        result = shap_explainer.explain(features)
        assert isinstance(result, SignalExplanation)

    def test_explain_signal_from_model(self, shap_explainer, features):
        result = shap_explainer.explain(features)
        assert result.signal == pytest.approx(0.7)

    def test_explain_confidence_non_negative(self, shap_explainer, features):
        result = shap_explainer.explain(features)
        assert result.confidence >= 0.0

    def test_explain_top_features_is_list(self, shap_explainer, features):
        result = shap_explainer.explain(features)
        assert isinstance(result.top_features, list)
        assert len(result.top_features) <= 5

    def test_explain_top_features_have_name_and_importance(self, shap_explainer, features):
        result = shap_explainer.explain(features)
        for feat in result.top_features:
            assert "name" in feat
            assert "importance" in feat

    def test_explain_regime_is_string(self, shap_explainer, features):
        result = shap_explainer.explain(features)
        assert isinstance(result.regime, str)

    def test_explain_recommendation_is_string(self, shap_explainer, features):
        result = shap_explainer.explain(features)
        assert isinstance(result.recommendation, str)

    def test_explain_with_no_model_uses_placeholder(self, features):
        exp = SHAPExplainer()
        result = exp.explain(features)
        assert isinstance(result, SignalExplanation)
        # Placeholder signal is 0.5
        assert result.signal == pytest.approx(0.5)

    def test_explain_custom_feature_names(self, shap_explainer, features):
        custom_names = ["f1", "f2", "f3", "f4", "f5"]
        result = shap_explainer.explain(features, feature_names=custom_names)
        assert isinstance(result, SignalExplanation)


class TestLIMEExplainer:
    def test_init_no_model(self):
        exp = LIMEExplainer()
        assert exp.model is None

    def test_explain_returns_signal_explanation(self, lime_explainer, features):
        result = lime_explainer.explain(features)
        assert isinstance(result, SignalExplanation)

    def test_explain_confidence_non_negative(self, lime_explainer, features):
        result = lime_explainer.explain(features)
        assert result.confidence >= 0.0

    def test_explain_top_features_is_list(self, lime_explainer, features):
        result = lime_explainer.explain(features)
        assert isinstance(result.top_features, list)

    def test_explain_with_no_model(self, features):
        exp = LIMEExplainer()
        result = exp.explain(features)
        assert isinstance(result, SignalExplanation)
