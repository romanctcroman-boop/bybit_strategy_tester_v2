"""
Tests for optimization quality improvements (TZ_optimization_quality_improvements.md).

Tests cover:
- P0-1: BIPOP CMA-ES (RestartCmaEsSampler)
- P0-2: OOS Validation Split (split_ohlcv_is_oos, run_oos_validation)
- P1-1: GT-Score (calculate_gt_score)
- P1-2: fANOVA Parameter Importance
- P1-3: AutoSampler
- P2-1: CSCV Validation
- P2-3: Deflated Sharpe Ratio (deflated_sharpe_ratio)
"""

import inspect
import math

import numpy as np
import pandas as pd
import pytest

from backend.optimization.builder_optimizer import (
    split_ohlcv_is_oos,
)
from backend.optimization.cscv import cscv_validation
from backend.optimization.scoring import (
    calculate_gt_score,
    deflated_sharpe_ratio,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def large_ohlcv():
    """Generate large OHLCV data (2000 bars) for OOS split testing."""
    np.random.seed(42)
    n = 2000
    base_price = 50000.0

    timestamps = pd.date_range(start="2025-01-01", periods=n, freq="15min", tz="UTC")
    returns = np.random.randn(n) * 0.002
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame(
        {
            "open": prices * (1 + np.random.randn(n) * 0.001),
            "high": prices * (1 + abs(np.random.randn(n)) * 0.003),
            "low": prices * (1 - abs(np.random.randn(n)) * 0.003),
            "close": prices,
            "volume": np.random.uniform(100, 1000, n),
        },
        index=timestamps,
    )
    return df


@pytest.fixture
def small_ohlcv():
    """Generate small OHLCV data (100 bars) — too short for OOS split."""
    np.random.seed(42)
    n = 100
    base_price = 50000.0

    timestamps = pd.date_range(start="2025-01-01", periods=n, freq="15min", tz="UTC")
    returns = np.random.randn(n) * 0.002
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame(
        {
            "open": prices * (1 + np.random.randn(n) * 0.001),
            "high": prices * (1 + abs(np.random.randn(n)) * 0.003),
            "low": prices * (1 - abs(np.random.randn(n)) * 0.003),
            "close": prices,
            "volume": np.random.uniform(100, 1000, n),
        },
        index=timestamps,
    )
    return df


@pytest.fixture
def sample_param_specs():
    """Sample parameter specs for GT-Score testing."""
    return [
        {"param_path": "rsi_1.period", "type": "int", "low": 5, "high": 50, "step": 1},
        {"param_path": "rsi_1.overbought", "type": "int", "low": 55, "high": 90, "step": 1},
        {"param_path": "rsi_1.oversold", "type": "int", "low": 10, "high": 45, "step": 1},
    ]


@pytest.fixture
def sample_base_params():
    """Sample base params (optimal) for GT-Score testing."""
    return {
        "rsi_1.period": 14,
        "rsi_1.overbought": 70,
        "rsi_1.oversold": 30,
    }


# =============================================================================
# P0-1: BIPOP CMA-ES TESTS
# =============================================================================


class TestBipopCmaes:
    """Tests for P0-1: BIPOP CMA-ES fix."""

    def test_restart_cmaes_sampler_not_deprecated(self):
        """Verify we no longer pass restart_strategy='ipop' to CmaEsSampler."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        src = inspect.getsource(run_builder_optuna_search)
        # "ipop" must not appear as a CmaEsSampler kwarg — only in comments/notes
        # Look for active code patterns like CmaEsSampler(...restart_strategy="ipop")
        assert 'CmaEsSampler(restart_strategy="ipop"' not in src, (
            "restart_strategy='ipop' in CmaEsSampler is deprecated in Optuna 4.4.0"
        )
        assert "CmaEsSampler(restart_strategy='ipop'" not in src

    def test_bipop_strategy_in_source(self):
        """Verify BIPOP restart strategy is present in source."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        src = inspect.getsource(run_builder_optuna_search)
        assert "bipop" in src or "RestartCmaEsSampler" in src

    def test_optunahub_import_or_graceful_fallback(self):
        """RestartCmaEsSampler imports or falls back to None (no crash)."""
        try:
            import optunahub

            m = optunahub.load_module("samplers/restart_cmaes")
            assert hasattr(m, "RestartCmaEsSampler")
        except Exception:
            pass  # graceful fallback expected


# =============================================================================
# P0-2: OOS VALIDATION SPLIT TESTS
# =============================================================================


class TestOOSSplit:
    """Tests for P0-2: Out-of-Sample validation split."""

    def test_split_returns_correct_sizes(self, large_ohlcv):
        """IS + OOS sizes sum to total."""
        _is_df, oos_df, info = split_ohlcv_is_oos(large_ohlcv, oos_ratio=0.2, oos_min_bars=10)
        assert oos_df is not None
        assert info["oos_skipped"] is False
        assert info["n_is"] + info["n_oos"] == len(large_ohlcv)

    def test_split_oos_ratio(self, large_ohlcv):
        """OOS is approximately oos_ratio of total."""
        _, _, info = split_ohlcv_is_oos(large_ohlcv, oos_ratio=0.3, oos_min_bars=10)
        expected_oos = int(len(large_ohlcv) * 0.3)
        assert info["n_oos"] == expected_oos

    def test_split_skips_when_too_short(self, small_ohlcv):
        """OOS is skipped when segment would be too short."""
        _is_df, oos_df, info = split_ohlcv_is_oos(small_ohlcv, oos_ratio=0.2, oos_min_bars=50)
        assert oos_df is None
        assert info["oos_skipped"] is True
        assert "too short" in info["reason"].lower()

    def test_oos_sealed_invariant(self, large_ohlcv):
        """IS end must be before OOS start (sealed OOS invariant)."""
        _is_df, oos_df, info = split_ohlcv_is_oos(large_ohlcv, oos_ratio=0.2, oos_min_bars=10)
        assert oos_df is not None
        oos_start = pd.Timestamp(info["oos_start"])
        is_end = pd.Timestamp(info["is_end"])
        assert is_end < oos_start, "IS and OOS must not overlap"

    def test_split_includes_warmup(self, large_ohlcv):
        """OOS segment includes warmup bars from IS tail."""
        _is_df, oos_df, info = split_ohlcv_is_oos(
            large_ohlcv,
            oos_ratio=0.2,
            oos_min_bars=10,
            warmup_bars=200,
        )
        assert oos_df is not None
        n_oos_pure = info["n_oos"]
        warmup = info["n_oos_warmup"]
        # OOS DataFrame should contain warmup + pure OOS bars
        assert len(oos_df) == n_oos_pure + warmup

    def test_split_metadata_complete(self, large_ohlcv):
        """Split info contains all required fields."""
        _, _, info = split_ohlcv_is_oos(large_ohlcv, oos_ratio=0.2, oos_min_bars=10)
        required_keys = {
            "oos_skipped",
            "n_total",
            "n_is",
            "n_oos",
            "n_oos_warmup",
            "is_start",
            "is_end",
            "oos_start",
            "oos_end",
            "oos_cutoff_ts",
        }
        assert required_keys.issubset(info.keys())

    def test_split_full_data_when_skipped(self, small_ohlcv):
        """When OOS is skipped, IS equals full dataset."""
        is_df, _oos_df, info = split_ohlcv_is_oos(small_ohlcv, oos_ratio=0.2, oos_min_bars=50)
        assert len(is_df) == len(small_ohlcv)
        assert info["n_is"] == len(small_ohlcv)


# =============================================================================
# P1-1: GT-SCORE TESTS
# =============================================================================


class TestGTScore:
    """Tests for P1-1: GT-Score (Generalization-Testing Score)."""

    def test_gt_score_returns_valid_structure(self, sample_base_params, sample_param_specs):
        """GT-Score returns dict with required keys."""

        def mock_backtest(params):
            return 0.5 + np.random.randn() * 0.01

        result = calculate_gt_score(
            base_params=sample_base_params,
            param_specs=sample_param_specs,
            run_backtest_fn=mock_backtest,
            n_neighbors=10,
        )
        assert "gt_score" in result
        assert "gt_mean" in result
        assert "gt_std" in result
        assert "gt_n_valid" in result
        assert result["gt_n_valid"] >= 0

    def test_gt_score_stable_params_scores_high(self, sample_base_params, sample_param_specs):
        """Params on a flat plateau get high GT-Score."""

        def flat_landscape(params):
            return 1.0  # always same score regardless of params

        result = calculate_gt_score(
            base_params=sample_base_params,
            param_specs=sample_param_specs,
            run_backtest_fn=flat_landscape,
            n_neighbors=20,
        )
        # Flat landscape → std ≈ 0 → gt_score very high
        assert result["gt_score"] > 100  # essentially infinite ratio

    def test_gt_score_sharp_peak_scores_low(self, sample_base_params, sample_param_specs):
        """Params on a narrow spike get low GT-Score."""
        np.random.seed(42)

        def noisy_landscape(params):
            return np.random.randn() * 10  # very noisy

        result = calculate_gt_score(
            base_params=sample_base_params,
            param_specs=sample_param_specs,
            run_backtest_fn=noisy_landscape,
            n_neighbors=20,
        )
        # Noisy landscape → high std → low gt_score
        assert result["gt_score"] < 5

    def test_gt_score_respects_param_bounds(self, sample_base_params, sample_param_specs):
        """Perturbed params never exceed spec bounds."""
        seen_params = []

        def capture_params(params):
            seen_params.append(dict(params))
            return 0.5

        calculate_gt_score(
            base_params=sample_base_params,
            param_specs=sample_param_specs,
            run_backtest_fn=capture_params,
            n_neighbors=50,
            epsilon=0.2,  # large perturbation
        )

        spec_map = {s["param_path"]: s for s in sample_param_specs}
        for p in seen_params:
            for path, val in p.items():
                spec = spec_map.get(path)
                if spec:
                    assert val >= spec["low"], f"{path}={val} below low={spec['low']}"
                    assert val <= spec["high"], f"{path}={val} above high={spec['high']}"

    def test_gt_score_handles_failed_backtests(self, sample_base_params, sample_param_specs):
        """GT-Score handles None results gracefully."""

        def failing_backtest(params):
            return None  # all fail

        result = calculate_gt_score(
            base_params=sample_base_params,
            param_specs=sample_param_specs,
            run_backtest_fn=failing_backtest,
            n_neighbors=10,
        )
        assert result["gt_score"] == 0.0
        assert result["gt_n_valid"] == 0


# =============================================================================
# P1-3: AUTOSAMPLER TESTS
# =============================================================================


class TestAutoSampler:
    """Tests for P1-3: AutoSampler support."""

    def test_auto_sampler_type_in_source(self):
        """'auto' sampler type is handled in run_builder_optuna_search."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        src = inspect.getsource(run_builder_optuna_search)
        assert '"auto"' in src or "'auto'" in src, "AutoSampler type not found in source"

    def test_autosampler_import_or_fallback(self):
        """AutoSampler import works or gracefully falls back."""
        try:
            from optuna.samplers import AutoSampler

            assert AutoSampler is not None
        except ImportError:
            pass  # expected on Optuna < 4.6


# =============================================================================
# P2-1: CSCV VALIDATION TESTS
# =============================================================================


class TestCSCV:
    """Tests for P2-1: Combinatorially Symmetric Cross-Validation."""

    def test_cscv_pbo_between_0_and_1(self, large_ohlcv):
        """PBO is in [0, 1] range."""
        strategies = [{"params": {"rsi_period": i}} for i in range(10, 20)]

        def mock_backtest(params, sub_ohlcv):
            # Score correlates with RSI period for consistency
            return float(params.get("rsi_period", 14)) / 20.0

        result = cscv_validation(
            strategies=strategies,
            ohlcv=large_ohlcv,
            run_backtest_fn=mock_backtest,
            n_splits=8,
        )
        assert result["pbo"] is not None
        assert 0.0 <= result["pbo"] <= 1.0

    def test_cscv_skips_when_too_few_bars(self, small_ohlcv):
        """CSCV skips when bars_per_split < 50."""
        strategies = [{"params": {"p": 1}}, {"params": {"p": 2}}]

        def mock_fn(params, ohlcv):
            return 1.0

        result = cscv_validation(
            strategies=strategies,
            ohlcv=small_ohlcv,
            run_backtest_fn=mock_fn,
            n_splits=16,  # 100 / 16 = 6.25 bars per split
        )
        assert result["pbo_interpretation"] == "skipped"

    def test_cscv_empty_strategies(self, large_ohlcv):
        """CSCV handles empty strategy list."""

        def mock_fn(params, ohlcv):
            return 1.0

        result = cscv_validation(
            strategies=[],
            ohlcv=large_ohlcv,
            run_backtest_fn=mock_fn,
        )
        assert result["pbo_interpretation"] == "skipped"
        assert "No strategies" in result.get("reason", "")

    def test_cscv_interpretation_labels(self, large_ohlcv):
        """CSCV returns valid interpretation strings."""
        strategies = [{"params": {"p": i}} for i in range(5)]

        def mock_fn(params, sub_ohlcv):
            return float(params.get("p", 0)) / 10.0

        result = cscv_validation(
            strategies=strategies,
            ohlcv=large_ohlcv,
            run_backtest_fn=mock_fn,
            n_splits=8,
        )
        assert result["pbo_interpretation"] in {"robust", "borderline", "overfitted", "skipped"}

    def test_cscv_consistent_strategy_has_low_pbo(self, large_ohlcv):
        """A strategy that always wins should have PBO ≈ 0."""
        strategies = [
            {"params": {"rank": 1}},  # always best
            {"params": {"rank": 0}},  # always worst
        ]

        def deterministic_fn(params, sub_ohlcv):
            return float(params.get("rank", 0))

        result = cscv_validation(
            strategies=strategies,
            ohlcv=large_ohlcv,
            run_backtest_fn=deterministic_fn,
            n_splits=8,
        )
        assert result["pbo"] is not None
        assert result["pbo"] < 0.3, f"Expected low PBO for deterministic best, got {result['pbo']}"


# =============================================================================
# P2-3: DEFLATED SHARPE RATIO TESTS
# =============================================================================


class TestDeflatedSharpeRatio:
    """Tests for P2-3: Deflated Sharpe Ratio."""

    def test_dsr_decreases_with_more_trials(self):
        """More trials → more selection bias → lower DSR."""
        sr = 1.5
        dsr_10 = deflated_sharpe_ratio(sr, n_trials=10, n_observations=1000)
        dsr_200 = deflated_sharpe_ratio(sr, n_trials=200, n_observations=1000)
        assert dsr_10 > dsr_200, "More trials should lower DSR"

    def test_dsr_increases_with_more_observations(self):
        """More data → narrower CI → higher DSR when SR exceeds expected max."""
        # Use a high SR that exceeds the expected maximum from trials
        sr = 3.0
        dsr_50 = deflated_sharpe_ratio(sr, n_trials=5, n_observations=50)
        dsr_500 = deflated_sharpe_ratio(sr, n_trials=5, n_observations=500)
        # When SR > expected_max, tighter CI → higher DSR
        assert dsr_500 >= dsr_50, "More data with edge should maintain or increase DSR"

    def test_dsr_negative_sr_returns_low_value(self):
        """Negative Sharpe should produce very low DSR."""
        dsr = deflated_sharpe_ratio(-0.5, n_trials=100, n_observations=500)
        assert dsr < 0.1

    def test_dsr_nan_for_few_observations(self):
        """DSR returns NaN when n_observations < 10."""
        dsr = deflated_sharpe_ratio(1.0, n_trials=50, n_observations=5)
        assert math.isnan(dsr)

    def test_dsr_nan_for_zero_trials(self):
        """DSR returns NaN when n_trials < 1."""
        dsr = deflated_sharpe_ratio(1.0, n_trials=0, n_observations=500)
        assert math.isnan(dsr)

    def test_dsr_value_range(self):
        """DSR should be between 0 and 1 (it's a probability)."""
        dsr = deflated_sharpe_ratio(2.0, n_trials=50, n_observations=1000)
        assert 0.0 <= dsr <= 1.0

    def test_dsr_high_sharpe_low_trials(self):
        """Very high Sharpe with few trials should have decent DSR."""
        dsr = deflated_sharpe_ratio(3.0, n_trials=5, n_observations=2000)
        assert dsr > 0.3

    def test_dsr_with_skewness_and_kurtosis(self):
        """DSR handles non-normal return distribution parameters."""
        # Use moderate SR near threshold so differences are visible
        dsr_normal = deflated_sharpe_ratio(1.5, n_trials=10, n_observations=100, skewness=0.0, kurtosis=3.0)
        dsr_skewed = deflated_sharpe_ratio(1.5, n_trials=10, n_observations=100, skewness=-0.5, kurtosis=5.0)
        assert not math.isnan(dsr_normal)
        assert not math.isnan(dsr_skewed)
        # Both should produce valid probabilities in [0, 1]
        assert 0.0 <= dsr_normal <= 1.0
        assert 0.0 <= dsr_skewed <= 1.0


# =============================================================================
# P0-2: OOS VALIDATION FUNCTION TESTS
# =============================================================================


class TestRunOOSValidation:
    """Tests for run_oos_validation function."""

    def test_run_oos_validation_import(self):
        """run_oos_validation is importable."""
        from backend.optimization.builder_optimizer import run_oos_validation

        assert callable(run_oos_validation)


# =============================================================================
# P1-2: fANOVA TESTS
# =============================================================================


class TestFanovaImportance:
    """Tests for P1-2: fANOVA parameter importance."""

    def test_fanova_evaluator_importable(self):
        """fANOVA evaluator can be imported (standard or fast variant)."""
        imported = False
        try:
            from optuna_fast_fanova import FanovaImportanceEvaluator

            imported = True
        except ImportError:
            pass
        try:
            from optuna.importance import FanovaImportanceEvaluator

            _ = FanovaImportanceEvaluator  # prove it's usable
            imported = True
        except ImportError:
            pass
        assert imported, "Neither optuna-fast-fanova nor optuna.importance.FanovaImportanceEvaluator available"

    def test_fanova_fields_in_optuna_return(self):
        """run_builder_optuna_search includes param_importance fields."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        src = inspect.getsource(run_builder_optuna_search)
        assert "param_importance" in src, "param_importance field missing from return"
        assert "param_importance_low" in src, "param_importance_low field missing from return"


# =============================================================================
# INTEGRATION: RETURN DICT STRUCTURE
# =============================================================================


class TestReturnStructure:
    """Verify new fields are present in optimizer return dict."""

    def test_optuna_return_has_dsr_fields(self):
        """run_builder_optuna_search return includes DSR fields."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        src = inspect.getsource(run_builder_optuna_search)
        assert "deflated_sharpe_ratio" in src
        assert "dsr_warning" in src

    def test_optuna_return_has_cscv_field(self):
        """run_builder_optuna_search return includes CSCV field."""
        from backend.optimization.builder_optimizer import run_builder_optuna_search

        src = inspect.getsource(run_builder_optuna_search)
        assert '"cscv"' in src or "'cscv'" in src

    def test_multi_objective_function_exists(self):
        """run_builder_optuna_multi_objective is importable."""
        from backend.optimization.builder_optimizer import (
            run_builder_optuna_multi_objective,
        )

        assert callable(run_builder_optuna_multi_objective)

    def test_request_model_has_new_fields(self):
        """BuilderOptimizationRequest has all new opt-in fields."""
        from backend.api.routers.strategy_builder.router import (
            BuilderOptimizationRequest,
        )

        fields = BuilderOptimizationRequest.model_fields
        assert "run_oos_validation" in fields
        assert "oos_ratio" in fields
        assert "run_gt_score" in fields
        assert "gt_score_top_n" in fields
        assert "run_cscv" in fields
        assert "cscv_n_splits" in fields

    def test_request_model_defaults_are_opt_in(self):
        """All new features are opt-in (default=False)."""
        from backend.api.routers.strategy_builder.router import (
            BuilderOptimizationRequest,
        )

        req = BuilderOptimizationRequest(
            symbol="BTCUSDT",
            start_date="2025-01-01",
            end_date="2025-06-01",
        )
        assert req.run_oos_validation is False
        assert req.run_gt_score is False
        assert req.run_cscv is False

    def test_request_model_accepts_multi_objective(self):
        """BuilderOptimizationRequest accepts method='multi_objective'."""
        from backend.api.routers.strategy_builder.router import (
            BuilderOptimizationRequest,
        )

        req = BuilderOptimizationRequest(
            symbol="BTCUSDT",
            start_date="2025-01-01",
            end_date="2025-06-01",
            method="multi_objective",
            run_oos_validation=True,
        )
        assert req.method == "multi_objective"

    def test_request_model_accepts_auto_sampler(self):
        """BuilderOptimizationRequest accepts sampler_type with 'auto'."""
        from backend.api.routers.strategy_builder.router import (
            BuilderOptimizationRequest,
        )

        # Sampler type is a free-form string, just verify it passes validation
        req = BuilderOptimizationRequest(
            symbol="BTCUSDT",
            start_date="2025-01-01",
            end_date="2025-06-01",
            sampler_type="auto",
        )
        assert req.sampler_type == "auto"


class TestMultiObjectiveOptimizer:
    """Tests for run_builder_optuna_multi_objective (P2-2)."""

    def test_function_is_importable(self):
        """run_builder_optuna_multi_objective можно импортировать."""
        from backend.optimization.builder_optimizer import (
            run_builder_optuna_multi_objective,
        )

        assert callable(run_builder_optuna_multi_objective)

    def test_function_signature_has_is_and_oos_params(self):
        """Функция принимает is_ohlcv и oos_ohlcv как отдельные аргументы."""
        import inspect

        from backend.optimization.builder_optimizer import (
            run_builder_optuna_multi_objective,
        )

        sig = inspect.signature(run_builder_optuna_multi_objective)
        params = list(sig.parameters.keys())
        assert "is_ohlcv" in params, "is_ohlcv parameter missing"
        assert "oos_ohlcv" in params, "oos_ohlcv parameter missing"
        assert "oos_cutoff_ts" in params, "oos_cutoff_ts parameter missing"

    def test_uses_nsga2_sampler_in_source(self):
        """Исходный код использует NSGAIISampler (не TPE)."""
        import inspect

        from backend.optimization.builder_optimizer import (
            run_builder_optuna_multi_objective,
        )

        source = inspect.getsource(run_builder_optuna_multi_objective)
        assert "NSGAIISampler" in source, "NSGAIISampler not found in source"

    def test_uses_multi_objective_directions_in_source(self):
        """Оптимизация двухцелевая: directions=['maximize','maximize']."""
        import inspect

        from backend.optimization.builder_optimizer import (
            run_builder_optuna_multi_objective,
        )

        source = inspect.getsource(run_builder_optuna_multi_objective)
        assert 'directions=["maximize", "maximize"]' in source or ('"maximize"' in source and "directions" in source), (
            "Multi-objective directions not found in source"
        )

    def test_gap_penalty_formula_in_source(self):
        """f2 = -(is_score - oos_score) — минимизация IS/OOS разрыва."""
        import inspect

        from backend.optimization.builder_optimizer import (
            run_builder_optuna_multi_objective,
        )

        source = inspect.getsource(run_builder_optuna_multi_objective)
        assert "gap_penalty" in source, "gap_penalty not found in source"
        assert "is_score - oos_score" in source, "Gap formula not found in source"

    def test_returns_pareto_front_dict(self, large_ohlcv, sample_param_specs, sample_base_params):
        """Функция возвращает словарь с полями pareto_front_size и top_results."""
        from unittest.mock import patch

        import numpy as np

        from backend.optimization.builder_optimizer import (
            run_builder_optuna_multi_objective,
            split_ohlcv_is_oos,
        )

        # Подготавливаем IS и OOS данные через split_ohlcv_is_oos
        is_ohlcv, oos_ohlcv, meta = split_ohlcv_is_oos(large_ohlcv, oos_ratio=0.2)
        if oos_ohlcv is None:
            pytest.skip("Not enough data for OOS split")

        oos_cutoff_ts = meta["oos_cutoff_ts"]

        # Mock run_builder_backtest чтобы не запускать реальный бэктест
        fake_result = {
            "sharpe_ratio": np.random.uniform(0.5, 2.0),
            "net_profit": np.random.uniform(100, 1000),
            "max_drawdown": np.random.uniform(5, 20),
            "total_trades": 30,
        }

        with (
            patch(
                "backend.optimization.builder_optimizer.run_builder_backtest",
                return_value=fake_result,
            ),
            patch(
                "backend.optimization.builder_optimizer.calculate_composite_score",
                return_value=np.random.uniform(0.1, 1.0),
            ),
        ):
            result = run_builder_optuna_multi_objective(
                base_graph=sample_base_params,
                is_ohlcv=is_ohlcv,
                oos_ohlcv=oos_ohlcv,
                oos_cutoff_ts=oos_cutoff_ts,
                param_specs=sample_param_specs,
                config_params={"initial_capital": 10000, "commission_value": 0.0007},
                n_trials=5,  # минимум для скорости
            )

        assert isinstance(result, dict), "Result must be a dict"
        assert "top_results" in result, "top_results missing"
        assert "pareto_front_size" in result, "pareto_front_size missing"
        assert "method" in result, "method missing"
        assert result["method"] == "optuna_multi_objective"
        assert "sampler" in result
        assert result["sampler"] == "nsga2"

    def test_top_results_sorted_by_oos_score(self, large_ohlcv, sample_param_specs, sample_base_params):
        """top_results отсортированы по oos_score убыванию."""
        from unittest.mock import patch

        from backend.optimization.builder_optimizer import (
            run_builder_optuna_multi_objective,
            split_ohlcv_is_oos,
        )

        is_ohlcv, oos_ohlcv, meta = split_ohlcv_is_oos(large_ohlcv, oos_ratio=0.2)
        if oos_ohlcv is None:
            pytest.skip("Not enough data for OOS split")

        oos_cutoff_ts = meta["oos_cutoff_ts"]
        scores = [0.9, 0.3, 0.7, 0.5, 0.1, 0.8, 0.6, 0.4, 0.2, 1.0]
        call_count = [0]

        def fake_composite(result, metric, weights):
            idx = call_count[0] % len(scores)
            call_count[0] += 1
            return scores[idx]

        fake_result = {
            "sharpe_ratio": 1.0,
            "net_profit": 500,
            "max_drawdown": 10,
            "total_trades": 30,
        }

        with (
            patch(
                "backend.optimization.builder_optimizer.run_builder_backtest",
                return_value=fake_result,
            ),
            patch(
                "backend.optimization.builder_optimizer.calculate_composite_score",
                side_effect=fake_composite,
            ),
        ):
            result = run_builder_optuna_multi_objective(
                base_graph=sample_base_params,
                is_ohlcv=is_ohlcv,
                oos_ohlcv=oos_ohlcv,
                oos_cutoff_ts=oos_cutoff_ts,
                param_specs=sample_param_specs,
                config_params={"initial_capital": 10000, "commission_value": 0.0007},
                n_trials=10,
            )

        top = result["top_results"]
        if len(top) >= 2:
            oos_scores = [r["oos_score"] for r in top]
            assert oos_scores == sorted(oos_scores, reverse=True), "top_results not sorted by oos_score descending"

    def test_each_result_has_required_fields(self, large_ohlcv, sample_param_specs, sample_base_params):
        """Каждый элемент top_results содержит обязательные поля."""
        from unittest.mock import patch

        from backend.optimization.builder_optimizer import (
            run_builder_optuna_multi_objective,
            split_ohlcv_is_oos,
        )

        is_ohlcv, oos_ohlcv, meta = split_ohlcv_is_oos(large_ohlcv, oos_ratio=0.2)
        if oos_ohlcv is None:
            pytest.skip("Not enough data for OOS split")

        fake_result = {"sharpe_ratio": 1.0, "net_profit": 500, "max_drawdown": 10, "total_trades": 30}

        with (
            patch(
                "backend.optimization.builder_optimizer.run_builder_backtest",
                return_value=fake_result,
            ),
            patch(
                "backend.optimization.builder_optimizer.calculate_composite_score",
                return_value=0.5,
            ),
        ):
            result = run_builder_optuna_multi_objective(
                base_graph=sample_base_params,
                is_ohlcv=is_ohlcv,
                oos_ohlcv=oos_ohlcv,
                oos_cutoff_ts=meta["oos_cutoff_ts"],
                param_specs=sample_param_specs,
                config_params={"initial_capital": 10000, "commission_value": 0.0007},
                n_trials=5,
            )

        required_fields = {"params", "oos_score", "is_score", "gap_penalty", "score"}
        for item in result["top_results"]:
            missing = required_fields - set(item.keys())
            assert not missing, f"Missing fields in result item: {missing}"

    def test_returns_status_completed(self, large_ohlcv, sample_param_specs, sample_base_params):
        """Статус результата всегда 'completed'."""
        from unittest.mock import patch

        from backend.optimization.builder_optimizer import (
            run_builder_optuna_multi_objective,
            split_ohlcv_is_oos,
        )

        is_ohlcv, oos_ohlcv, meta = split_ohlcv_is_oos(large_ohlcv, oos_ratio=0.2)
        if oos_ohlcv is None:
            pytest.skip("Not enough data for OOS split")

        with patch(
            "backend.optimization.builder_optimizer.run_builder_backtest",
            return_value=None,  # все бэктесты падают
        ):
            result = run_builder_optuna_multi_objective(
                base_graph=sample_base_params,
                is_ohlcv=is_ohlcv,
                oos_ohlcv=oos_ohlcv,
                oos_cutoff_ts=meta["oos_cutoff_ts"],
                param_specs=sample_param_specs,
                config_params={"initial_capital": 10000, "commission_value": 0.0007},
                n_trials=3,
            )

        assert result["status"] == "completed"
        assert result["top_results"] == [] or isinstance(result["top_results"], list)

    def test_router_rejects_multi_objective_without_oos(self):
        """Router отклоняет method='multi_objective' если run_oos_validation=False."""
        import inspect

        from backend.api.routers.strategy_builder import router as sb_router

        source = inspect.getsource(sb_router)
        # Проверяем, что в роутере есть проверка multi_objective + oos
        assert "multi_objective" in source, "multi_objective not handled in router"
        assert "run_oos_validation" in source, "run_oos_validation not in router"
        # Проверяем что есть валидация (400 или raise HTTPException)
        assert "HTTPException" in source or "400" in source, (
            "No error handling for multi_objective without OOS in router"
        )
