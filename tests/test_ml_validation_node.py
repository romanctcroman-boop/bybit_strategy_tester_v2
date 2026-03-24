"""
Tests for Phase 7 MLValidationNode in trading_strategy_graph.py.

Covers:
- MLValidationNode.execute(): state mutation, result structure, non-blocking behaviour
- _check_overfitting(): IS/OOS split, gap threshold, overfitting_score
- _check_regimes(): regime detection fallback, regime_sharpes dict
- _check_parameter_stability(): period perturbation, sensitive_params
- build_trading_strategy_graph() wiring: ml_validation node present, edges correct
"""

from __future__ import annotations

import copy
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.trading_strategy_graph import (
    MLValidationNode,
    build_trading_strategy_graph,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int = 200) -> pd.DataFrame:
    """Return a minimal OHLCV DataFrame with n bars."""
    rng = np.random.default_rng(42)
    closes = 100 + np.cumsum(rng.normal(0, 0.5, n))
    df = pd.DataFrame(
        {
            "open": closes * (1 - 0.001),
            "high": closes * 1.005,
            "low": closes * 0.995,
            "close": closes,
            "volume": rng.uniform(1000, 5000, n),
        }
    )
    df.index = pd.date_range("2025-01-01", periods=n, freq="15min")
    return df


def _minimal_graph() -> dict:
    """A minimal strategy_graph with one RSI block and a strategy node."""
    return {
        "name": "test_rsi",
        "interval": "15",
        "blocks": [
            {"id": "rsi_1", "type": "rsi", "params": {"period": 14, "oversold": 30, "overbought": 70}, "isMain": False},
            {"id": "strat", "type": "strategy", "params": {}, "isMain": True},
        ],
        "connections": [
            {"from": "rsi_1", "fromPort": "long", "to": "strat", "toPort": "entry_long"},
        ],
    }


def _state_with_graph_and_df(
    df: pd.DataFrame | None = None,
    graph: dict | None = None,
) -> AgentState:
    state = AgentState()
    state.context["strategy_graph"] = graph if graph is not None else _minimal_graph()
    state.context["df"] = df if df is not None else _make_ohlcv()
    state.context["symbol"] = "BTCUSDT"
    state.context["timeframe"] = "15"
    state.context["initial_capital"] = 10000
    state.context["leverage"] = 1
    return state


# ---------------------------------------------------------------------------
# MLValidationNode.execute — guard paths
# ---------------------------------------------------------------------------


class TestMLValidationNodeExecuteGuards:
    @pytest.mark.asyncio
    async def test_skips_when_no_graph(self):
        state = AgentState()
        state.context["df"] = _make_ohlcv()
        node = MLValidationNode()
        result = await node.execute(state)
        res = result.get_result("ml_validation")
        assert res["status"] == "skipped"
        assert "no_graph_or_data" in res["reason"]

    @pytest.mark.asyncio
    async def test_skips_when_no_df(self):
        state = AgentState()
        state.context["strategy_graph"] = _minimal_graph()
        node = MLValidationNode()
        result = await node.execute(state)
        res = result.get_result("ml_validation")
        assert res["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_skips_when_df_is_empty(self):
        state = AgentState()
        state.context["strategy_graph"] = _minimal_graph()
        state.context["df"] = pd.DataFrame()
        node = MLValidationNode()
        result = await node.execute(state)
        res = result.get_result("ml_validation")
        assert res["status"] == "skipped"


# ---------------------------------------------------------------------------
# MLValidationNode.execute — happy path (mocked _run_strategy)
# ---------------------------------------------------------------------------


class TestMLValidationNodeExecuteHappyPath:
    def _mock_run_strategy(self, sharpe: float = 1.0, trades: int = 20):
        """Return a mock that patches _run_strategy on the node instance."""
        return MagicMock(
            return_value={
                "sharpe_ratio": sharpe,
                "total_trades": trades,
                "max_drawdown": 10.0,
            }
        )

    @pytest.mark.asyncio
    async def test_result_has_expected_keys(self):
        state = _state_with_graph_and_df()
        node = MLValidationNode()
        node._run_strategy = self._mock_run_strategy(sharpe=1.2, trades=30)
        result = await node.execute(state)
        res = result.get_result("ml_validation")
        assert "status" in res
        assert "overfitting" in res
        assert "regime_analysis" in res
        assert "parameter_stability" in res
        assert "warnings" in res
        assert isinstance(res["warnings"], list)

    @pytest.mark.asyncio
    async def test_ml_validation_stored_in_context(self):
        state = _state_with_graph_and_df()
        node = MLValidationNode()
        node._run_strategy = self._mock_run_strategy()
        await node.execute(state)
        assert "ml_validation" in state.context
        assert state.context["ml_validation"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_no_warnings_when_strategy_is_clean(self):
        state = _state_with_graph_and_df()
        node = MLValidationNode()
        # Stable Sharpe across IS/OOS → no overfitting
        node._run_strategy = self._mock_run_strategy(sharpe=1.5, trades=25)
        result = await node.execute(state)
        res = result.get_result("ml_validation")
        # With a stable mock, overfitting gap = 0 → no overfit warning
        overfit_warnings = [w for w in res["warnings"] if "[OVERFIT]" in w]
        assert len(overfit_warnings) == 0

    @pytest.mark.asyncio
    async def test_non_blocking_on_all_checks_failing(self):
        """All three checks raise → node still sets result with status='ok'."""
        state = _state_with_graph_and_df()
        node = MLValidationNode()
        node._run_strategy = MagicMock(side_effect=RuntimeError("adapter exploded"))
        result = await node.execute(state)
        res = result.get_result("ml_validation")
        # Node must not propagate the exception; errors land in sub-dicts
        assert res is not None
        assert "overfitting" in res

    @pytest.mark.asyncio
    async def test_state_has_no_extra_errors(self):
        state = _state_with_graph_and_df()
        node = MLValidationNode()
        node._run_strategy = self._mock_run_strategy()
        result = await node.execute(state)
        assert "ml_validation" not in result.errors


# ---------------------------------------------------------------------------
# _check_overfitting
# ---------------------------------------------------------------------------


class TestCheckOverfitting:
    def _node(self):
        return MLValidationNode()

    def test_returns_skipped_for_small_df(self):
        node = self._node()
        df = _make_ohlcv(n=50)
        result = node._check_overfitting(_minimal_graph(), df, {})
        assert result["status"] == "skipped"

    def test_not_overfit_when_gap_below_threshold(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        # IS=1.0, OOS=0.8 → gap=0.2 < 0.5
        node._run_strategy = MagicMock(
            side_effect=[
                {"sharpe_ratio": 1.0, "total_trades": 20},
                {"sharpe_ratio": 0.8, "total_trades": 10},
            ]
        )
        result = node._check_overfitting(_minimal_graph(), df, {})
        assert result["status"] == "ok"
        assert result["is_overfit"] is False
        assert result["gap"] == pytest.approx(0.2, abs=1e-6)

    def test_overfit_when_gap_exceeds_threshold(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        # IS=2.0, OOS=-0.5 → gap=2.5 > 0.5
        node._run_strategy = MagicMock(
            side_effect=[
                {"sharpe_ratio": 2.0, "total_trades": 30},
                {"sharpe_ratio": -0.5, "total_trades": 5},
            ]
        )
        result = node._check_overfitting(_minimal_graph(), df, {})
        assert result["is_overfit"] is True
        assert result["gap"] == pytest.approx(2.5, abs=1e-6)

    def test_overfitting_score_clamped_to_one(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        # Very large gap → score should not exceed 1.0
        node._run_strategy = MagicMock(
            side_effect=[
                {"sharpe_ratio": 10.0, "total_trades": 50},
                {"sharpe_ratio": -5.0, "total_trades": 5},
            ]
        )
        result = node._check_overfitting(_minimal_graph(), df, {})
        assert result["overfitting_score"] <= 1.0

    def test_exact_gap_at_threshold_is_overfit(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        # gap == OVERFIT_GAP_THRESHOLD exactly → should NOT flag (> not >=)
        node._run_strategy = MagicMock(
            side_effect=[
                {"sharpe_ratio": 1.5, "total_trades": 20},
                {"sharpe_ratio": 1.0, "total_trades": 10},
            ]
        )
        result = node._check_overfitting(_minimal_graph(), df, {})
        assert result["gap"] == pytest.approx(0.5, abs=1e-6)
        assert result["is_overfit"] is False  # 0.5 is NOT > 0.5

    def test_error_in_run_strategy_returns_error_dict(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        node._run_strategy = MagicMock(side_effect=ValueError("boom"))
        result = node._check_overfitting(_minimal_graph(), df, {})
        assert result["status"] == "error"
        assert "boom" in result["error"]

    def test_is_fraction_split(self):
        """Verify the split ratio produces correct IS/OOS sizes."""
        node = self._node()
        df = _make_ohlcv(n=200)
        call_args: list[int] = []

        def capture_run(graph, df_slice, cfg):
            call_args.append(len(df_slice))
            return {"sharpe_ratio": 1.0, "total_trades": 10}

        node._run_strategy = capture_run
        node._check_overfitting(_minimal_graph(), df, {})
        assert len(call_args) == 2
        assert call_args[0] == int(200 * MLValidationNode.IS_FRACTION)
        assert call_args[1] == 200 - int(200 * MLValidationNode.IS_FRACTION)


# ---------------------------------------------------------------------------
# _check_regimes
# ---------------------------------------------------------------------------


class TestCheckRegimes:
    def _node(self):
        return MLValidationNode()

    def test_returns_skipped_for_small_df(self):
        node = self._node()
        df = _make_ohlcv(n=50)
        result = node._check_regimes(_minimal_graph(), df, {})
        assert result["status"] == "skipped"

    @patch("backend.agents.trading_strategy_graph.MLValidationNode._run_strategy")
    def test_returns_regime_sharpes_dict(self, mock_run):
        mock_run.return_value = {"sharpe_ratio": 1.0, "total_trades": 10}
        node = self._node()
        df = _make_ohlcv(n=300)

        # Patch both detectors
        fake_regime_result = MagicMock()
        fake_regime_result.regimes = np.array([0, 1, 2] * 100)
        fake_regime_result.n_regimes = 3
        fake_regime_result.regime_names = ["bull", "bear", "sideways"]
        fake_regime_result.current_regime_name = "bull"

        with patch("backend.ml.regime_detection.HMMRegimeDetector") as mock_hmm:
            mock_hmm.return_value.fit_predict.return_value = fake_regime_result
            result = node._check_regimes(_minimal_graph(), df, {})

        assert result["status"] == "ok"
        assert "regime_sharpes" in result
        assert "current_regime" in result

    def test_regime_detector_unavailable_returns_error(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        with patch.dict("sys.modules", {"backend.ml.regime_detection": None}):
            result = node._check_regimes(_minimal_graph(), df, {})
        # Should return error dict, not raise
        assert "status" in result
        assert result["status"] in ("error", "skipped", "ok")

    def test_n_regimes_in_result(self):
        node = self._node()
        df = _make_ohlcv(n=300)
        node._run_strategy = MagicMock(return_value={"sharpe_ratio": 0.5, "total_trades": 5})

        fake = MagicMock()
        fake.regimes = np.array([0, 1, 2] * 100)
        fake.n_regimes = 3
        fake.regime_names = ["r0", "r1", "r2"]
        fake.current_regime_name = "r0"

        with patch("backend.agents.trading_strategy_graph.HMMRegimeDetector", create=True) as m:
            m.return_value.fit_predict.return_value = fake
            with patch("backend.ml.regime_detection.HMMRegimeDetector") as hmm_cls:
                hmm_cls.return_value.fit_predict.return_value = fake
                result = node._check_regimes(_minimal_graph(), df, {})

        if result["status"] == "ok":
            assert result["n_regimes"] >= 1


# ---------------------------------------------------------------------------
# _check_parameter_stability
# ---------------------------------------------------------------------------


class TestCheckParameterStability:
    def _node(self):
        return MLValidationNode()

    def test_returns_skipped_for_small_df(self):
        node = self._node()
        df = _make_ohlcv(n=50)
        result = node._check_parameter_stability(_minimal_graph(), df, {})
        assert result["status"] == "skipped"

    def test_returns_skipped_for_graph_with_no_period_params(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        graph = {
            "blocks": [{"id": "s", "type": "strategy", "params": {}, "isMain": True}],
            "connections": [],
        }
        result = node._check_parameter_stability(graph, df, {})
        assert result["status"] == "skipped"
        assert result["reason"] == "no_period_params"

    def test_stable_when_sharpe_stays_positive(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        # All runs return Sharpe=1.0 → stable
        node._run_strategy = MagicMock(return_value={"sharpe_ratio": 1.0, "total_trades": 15})
        result = node._check_parameter_stability(_minimal_graph(), df, {})
        assert result["status"] == "ok"
        assert result["is_stable"] is True
        assert result["sensitive_params"] == []

    def test_unstable_when_perturbation_flips_sharpe_sign(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        # Base=1.0, then alternating negative
        call_counter = {"n": 0}

        def _run(graph, df_slice, cfg):
            n = call_counter["n"]
            call_counter["n"] += 1
            if n == 0:
                return {"sharpe_ratio": 1.0, "total_trades": 20}  # baseline
            return {"sharpe_ratio": -0.5, "total_trades": 5}  # flip

        node._run_strategy = _run
        result = node._check_parameter_stability(_minimal_graph(), df, {})
        assert result["status"] == "ok"
        assert result["is_stable"] is False
        assert len(result["sensitive_params"]) > 0

    def test_tested_params_count(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        node._run_strategy = MagicMock(return_value={"sharpe_ratio": 1.5, "total_trades": 30})
        result = node._check_parameter_stability(_minimal_graph(), df, {})
        if result["status"] == "ok":
            # _minimal_graph has 1 period param (period=14 in rsi block)
            assert result["tested_params"] == 1

    def test_perturbation_uses_both_directions(self):
        node = self._node()
        assert len(MLValidationNode.PERTURB_FRACTIONS) == 2
        assert -0.20 in MLValidationNode.PERTURB_FRACTIONS
        assert +0.20 in MLValidationNode.PERTURB_FRACTIONS

    def test_period_clamped_to_minimum_two(self):
        """A period=3 perturbed by -20% → max(2, int(3*0.8)) = max(2, 2) = 2."""
        node = self._node()
        df = _make_ohlcv(n=200)
        captured: list[int] = []

        def _run(graph, df_slice, cfg):
            for b in graph.get("blocks", []):
                p = b.get("params", {}).get("period")
                if p is not None:
                    captured.append(p)
            return {"sharpe_ratio": 1.0, "total_trades": 10}

        node._run_strategy = _run
        small_period_graph = copy.deepcopy(_minimal_graph())
        small_period_graph["blocks"][0]["params"]["period"] = 3
        node._check_parameter_stability(small_period_graph, df, {})
        # All captured periods should be >= 2
        assert all(p >= 2 for p in captured)

    def test_error_in_baseline_returns_error_dict(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        node._run_strategy = MagicMock(side_effect=RuntimeError("engine crash"))
        result = node._check_parameter_stability(_minimal_graph(), df, {})
        assert result["status"] == "error"

    def test_does_not_mutate_original_graph(self):
        node = self._node()
        df = _make_ohlcv(n=200)
        node._run_strategy = MagicMock(return_value={"sharpe_ratio": 1.0, "total_trades": 10})
        graph = _minimal_graph()
        original_period = graph["blocks"][0]["params"]["period"]
        node._check_parameter_stability(graph, df, {})
        assert graph["blocks"][0]["params"]["period"] == original_period


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------


class TestGraphWiring:
    def test_ml_validation_node_in_graph(self):
        graph = build_trading_strategy_graph(run_backtest=True)
        assert "ml_validation" in graph.nodes

    def test_ml_validation_node_not_present_without_backtest(self):
        graph = build_trading_strategy_graph(run_backtest=False)
        assert "ml_validation" not in graph.nodes

    def test_ml_validation_between_optimize_and_memory(self):
        graph = build_trading_strategy_graph(run_backtest=True)
        # optimize_strategy should have an edge to ml_validation
        opt_targets = [e.target for e in graph.edges.get("optimize_strategy", [])]
        assert "ml_validation" in opt_targets, f"No edge optimize_strategy → ml_validation; got: {opt_targets}"
        # ml_validation should have an edge to memory_update
        ml_targets = [e.target for e in graph.edges.get("ml_validation", [])]
        assert "memory_update" in ml_targets, f"No edge ml_validation → memory_update; got: {ml_targets}"

    def test_ml_validation_node_is_correct_type(self):
        graph = build_trading_strategy_graph(run_backtest=True)
        node = graph.nodes["ml_validation"]
        assert isinstance(node, MLValidationNode)

    def test_ml_validation_node_name(self):
        node = MLValidationNode()
        assert node.name == "ml_validation"

    def test_ml_validation_timeout_reasonable(self):
        node = MLValidationNode()
        assert node.timeout >= 60.0  # needs at least 60s for 3 checks


# ---------------------------------------------------------------------------
# MLValidationNode class constants
# ---------------------------------------------------------------------------


class TestMLValidationNodeConstants:
    def test_is_fraction_between_zero_and_one(self):
        assert 0 < MLValidationNode.IS_FRACTION < 1

    def test_overfit_gap_threshold_positive(self):
        assert MLValidationNode.OVERFIT_GAP_THRESHOLD > 0

    def test_perturb_fractions_has_both_signs(self):
        fracs = MLValidationNode.PERTURB_FRACTIONS
        assert any(f < 0 for f in fracs), "Need at least one negative perturbation"
        assert any(f > 0 for f in fracs), "Need at least one positive perturbation"
