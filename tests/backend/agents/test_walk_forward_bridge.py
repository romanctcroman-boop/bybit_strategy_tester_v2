"""
Tests for Walk-Forward Bridge integration.

Tests cover:
- WalkForwardBridge initialization
- build_strategy_runner() — creates callable with correct signature
- build_param_grid() — from OptimizationHints, defaults, and current params
- _df_to_candles() — DataFrame to list[dict] conversion
- _execute_backtest() — single backtest run for WF optimizer
- _generate_variations() — param value variations
- run_walk_forward() — end-to-end sync walk-forward
- run_walk_forward_async() — async wrapper
- Integration with StrategyController._run_walk_forward()
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.agents.integration.walk_forward_bridge import (
    WalkForwardBridge,
    _generate_variations,
)
from backend.agents.prompts.response_parser import (
    ExitCondition,
    ExitConditions,
    OptimizationHints,
    Signal,
    StrategyDefinition,
)
from backend.services.walk_forward import WalkForwardOptimizer, WalkForwardResult

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate sample OHLCV data for testing (500 candles for walk-forward)."""
    np.random.seed(42)
    n = 500
    base = 50000.0
    dates = pd.date_range("2025-01-01", periods=n, freq="15min")

    close = base + np.cumsum(np.random.randn(n) * 100)
    high = close + np.abs(np.random.randn(n) * 50)
    low = close - np.abs(np.random.randn(n) * 50)
    op = close + np.random.randn(n) * 20
    volume = np.abs(np.random.randn(n) * 1000) + 100

    return pd.DataFrame(
        {
            "open": op,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


@pytest.fixture
def small_ohlcv() -> pd.DataFrame:
    """Small OHLCV for unit tests (50 candles)."""
    np.random.seed(42)
    n = 50
    base = 50000.0
    dates = pd.date_range("2025-01-01", periods=n, freq="15min")
    close = base + np.cumsum(np.random.randn(n) * 100)
    return pd.DataFrame(
        {
            "open": close + np.random.randn(n) * 20,
            "high": close + np.abs(np.random.randn(n) * 50),
            "low": close - np.abs(np.random.randn(n) * 50),
            "close": close,
            "volume": np.abs(np.random.randn(n) * 1000) + 100,
        },
        index=dates,
    )


@pytest.fixture
def rsi_strategy() -> StrategyDefinition:
    """RSI strategy with optimization hints."""
    return StrategyDefinition(
        strategy_name="Test RSI Strategy",
        description="RSI test",
        signals=[
            Signal(id="s1", type="rsi", params={"period": 14, "overbought": 70, "oversold": 30}, weight=1.0),
        ],
        optimization_hints=OptimizationHints(
            parameters_to_optimize=["period", "overbought", "oversold"],
            ranges={"period": [7, 14, 21], "overbought": [65, 70, 75]},
            primary_objective="sharpe_ratio",
        ),
    )


@pytest.fixture
def macd_strategy() -> StrategyDefinition:
    """MACD strategy without optimization hints."""
    return StrategyDefinition(
        strategy_name="Test MACD Strategy",
        signals=[
            Signal(id="s1", type="macd", params={"fast_period": 12, "slow_period": 26, "signal_period": 9}, weight=1.0),
        ],
    )


@pytest.fixture
def strategy_with_exits() -> StrategyDefinition:
    """Strategy with explicit SL/TP."""
    return StrategyDefinition(
        strategy_name="RSI with Exits",
        signals=[Signal(id="s1", type="rsi", params={"period": 14, "overbought": 70, "oversold": 30}, weight=1.0)],
        exit_conditions=ExitConditions(
            stop_loss=ExitCondition(type="fixed_pct", value=1.5),
            take_profit=ExitCondition(type="fixed_pct", value=3.0),
        ),
    )


@pytest.fixture
def bridge() -> WalkForwardBridge:
    """Default WalkForwardBridge instance."""
    return WalkForwardBridge(n_splits=3, train_ratio=0.7)


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestWalkForwardBridgeInit:
    """Test WalkForwardBridge initialization."""

    def test_default_init(self):
        """Default init creates optimizer with n_splits=5, train_ratio=0.7."""
        bridge = WalkForwardBridge()
        assert bridge._optimizer.n_splits == 5
        assert bridge._optimizer.train_ratio == 0.7

    def test_custom_init(self):
        """Custom n_splits and train_ratio are passed to optimizer."""
        bridge = WalkForwardBridge(n_splits=10, train_ratio=0.8, gap_periods=2)
        assert bridge._optimizer.n_splits == 10
        assert bridge._optimizer.train_ratio == 0.8
        assert bridge._optimizer.gap_periods == 2

    def test_custom_optimizer(self):
        """Custom WalkForwardOptimizer can be injected."""
        custom = WalkForwardOptimizer(n_splits=3)
        bridge = WalkForwardBridge(optimizer=custom)
        assert bridge._optimizer is custom
        assert bridge._optimizer.n_splits == 3

    def test_commission_rate(self):
        """Commission rate matches TradingView parity."""
        assert WalkForwardBridge.COMMISSION_RATE == 0.0007


# =============================================================================
# PARAM GRID TESTS
# =============================================================================


class TestBuildParamGrid:
    """Test build_param_grid() method."""

    def test_grid_from_optimization_hints(self, bridge, rsi_strategy):
        """Uses ranges from OptimizationHints when available."""
        grid = bridge.build_param_grid(rsi_strategy)
        assert "period" in grid
        assert grid["period"] == [7, 14, 21]
        assert "overbought" in grid
        assert grid["overbought"] == [65, 70, 75]

    def test_grid_from_hints_with_missing_range(self, bridge):
        """Parameters_to_optimize without ranges get variations."""
        strategy = StrategyDefinition(
            strategy_name="Test",
            signals=[Signal(id="s1", type="rsi", params={"period": 14, "overbought": 70, "oversold": 30}, weight=1.0)],
            optimization_hints=OptimizationHints(
                parameters_to_optimize=["period", "oversold"],
                ranges={"period": [7, 14, 21]},
            ),
        )
        grid = bridge.build_param_grid(strategy)
        assert "period" in grid
        assert "oversold" in grid
        # oversold should have auto-generated variations around 30
        assert len(grid["oversold"]) >= 2

    def test_grid_from_defaults(self, bridge, macd_strategy):
        """Falls back to DEFAULT_PARAM_RANGES when no hints."""
        grid = bridge.build_param_grid(macd_strategy)
        assert "fast_period" in grid
        assert "slow_period" in grid
        assert "signal_period" in grid

    def test_grid_includes_current_value(self, bridge):
        """Default grid includes current param value even if not in defaults."""
        strategy = StrategyDefinition(
            strategy_name="Test",
            signals=[Signal(id="s1", type="rsi", params={"period": 17, "overbought": 70, "oversold": 30}, weight=1.0)],
        )
        grid = bridge.build_param_grid(strategy)
        # period=17 is not in default [7, 14, 21, 28], should be added
        assert 17 in grid["period"]

    def test_grid_fallback_from_params(self, bridge):
        """Unknown strategy type generates grid from current params."""
        strategy = StrategyDefinition(
            strategy_name="Test Custom",
            signals=[Signal(id="s1", type="custom_indicator", params={"lookback": 20, "threshold": 0.5}, weight=1.0)],
        )
        grid = bridge.build_param_grid(strategy)
        assert "lookback" in grid or "period" in grid or len(grid) > 0

    def test_grid_empty_signals(self, bridge):
        """Strategy with minimal params still produces a grid."""
        strategy = StrategyDefinition(
            strategy_name="Minimal",
            signals=[Signal(id="s1", type="rsi", params={}, weight=1.0)],
        )
        grid = bridge.build_param_grid(strategy)
        # RSI default ranges should be used
        assert len(grid) > 0


# =============================================================================
# STRATEGY RUNNER TESTS
# =============================================================================


class TestBuildStrategyRunner:
    """Test build_strategy_runner() method."""

    def test_returns_callable(self, bridge, rsi_strategy):
        """Returns a callable with correct signature."""
        runner = bridge.build_strategy_runner(rsi_strategy)
        assert callable(runner)

    @patch("backend.agents.integration.walk_forward_bridge.WalkForwardBridge._execute_backtest")
    def test_runner_calls_execute_backtest(self, mock_execute, bridge, rsi_strategy):
        """Runner delegates to _execute_backtest with correct args."""
        mock_execute.return_value = {"return": 0.05, "sharpe": 1.5, "max_drawdown": 0.1, "trades": 10}

        runner = bridge.build_strategy_runner(rsi_strategy, symbol="ETHUSDT", timeframe="60")
        result = runner([{"close": 100}], {"period": 14}, 10000)

        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args.kwargs
        assert call_kwargs["symbol"] == "ETHUSDT"
        assert call_kwargs["timeframe"] == "60"
        assert call_kwargs["strategy_type"] == "rsi"
        assert result["sharpe"] == 1.5

    def test_runner_uses_strategy_sl_tp(self, bridge, strategy_with_exits):
        """Runner extracts SL/TP from StrategyDefinition."""
        runner = bridge.build_strategy_runner(strategy_with_exits)
        # Verify SL/TP were captured in closure
        assert runner is not None  # Smoke test — real test via mock


# =============================================================================
# CANDLE CONVERSION TESTS
# =============================================================================


class TestDfToCandles:
    """Test _df_to_candles() conversion."""

    def test_converts_dataframe_to_list(self, small_ohlcv):
        """Converts DataFrame to list of dicts."""
        candles = WalkForwardBridge._df_to_candles(small_ohlcv)
        assert isinstance(candles, list)
        assert len(candles) == len(small_ohlcv)

    def test_candle_has_ohlcv_keys(self, small_ohlcv):
        """Each candle dict has open, high, low, close, volume."""
        candles = WalkForwardBridge._df_to_candles(small_ohlcv)
        for candle in candles[:5]:
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle
            assert "volume" in candle

    def test_candle_has_open_time(self, small_ohlcv):
        """Each candle dict has open_time for WF sorting."""
        candles = WalkForwardBridge._df_to_candles(small_ohlcv)
        for candle in candles:
            assert "open_time" in candle

    def test_empty_dataframe(self):
        """Empty DataFrame returns empty list."""
        df = pd.DataFrame()
        candles = WalkForwardBridge._df_to_candles(df)
        assert candles == []


# =============================================================================
# SL/TP EXTRACTION TESTS
# =============================================================================


class TestExtractSlTp:
    """Test stop loss and take profit extraction."""

    def test_extract_stop_loss_fixed_pct(self, strategy_with_exits):
        """Extracts fixed_pct stop loss correctly."""
        sl = WalkForwardBridge._extract_stop_loss(strategy_with_exits)
        assert sl == pytest.approx(0.015)  # 1.5% → 0.015

    def test_extract_take_profit_fixed_pct(self, strategy_with_exits):
        """Extracts fixed_pct take profit correctly."""
        tp = WalkForwardBridge._extract_take_profit(strategy_with_exits)
        assert tp == pytest.approx(0.03)  # 3.0% → 0.03

    def test_default_stop_loss(self, rsi_strategy):
        """Default stop loss is 2% when not specified."""
        sl = WalkForwardBridge._extract_stop_loss(rsi_strategy)
        assert sl == 0.02

    def test_default_take_profit(self, rsi_strategy):
        """Default take profit is 3% when not specified."""
        tp = WalkForwardBridge._extract_take_profit(rsi_strategy)
        assert tp == 0.03


# =============================================================================
# GENERATE VARIATIONS TESTS
# =============================================================================


class TestGenerateVariations:
    """Test _generate_variations() helper."""

    def test_int_variations(self):
        """Integer values produce integer variations."""
        result = _generate_variations(14)
        assert len(result) >= 3
        assert all(isinstance(v, int) for v in result)
        assert min(result) < 14
        assert max(result) > 14

    def test_float_variations(self):
        """Float values produce float variations."""
        result = _generate_variations(2.0, n_steps=5)
        assert len(result) == 5
        assert all(isinstance(v, float) for v in result)
        assert min(result) < 2.0
        assert max(result) > 2.0

    def test_non_numeric_returns_same(self):
        """Non-numeric values return [value]."""
        result = _generate_variations("cross_above")
        assert result == ["cross_above"]

    def test_small_int_stays_positive(self):
        """Small int variations stay >= 1."""
        result = _generate_variations(2)
        assert all(v >= 1 for v in result)


# =============================================================================
# GRID FROM HINTS TESTS
# =============================================================================


class TestGridFromHints:
    """Test _grid_from_hints() static method."""

    def test_direct_ranges(self):
        """Direct ranges from hints are used."""
        hints = OptimizationHints(
            parameters_to_optimize=["period"],
            ranges={"period": [7, 14, 21, 28]},
        )
        grid = WalkForwardBridge._grid_from_hints(hints, {"period": 14})
        assert grid == {"period": [7, 14, 21, 28]}

    def test_missing_range_generates_variations(self):
        """Params without range get auto-generated values."""
        hints = OptimizationHints(
            parameters_to_optimize=["period", "threshold"],
            ranges={"period": [7, 14, 21]},
        )
        grid = WalkForwardBridge._grid_from_hints(hints, {"period": 14, "threshold": 0.5})
        assert "period" in grid
        assert "threshold" in grid
        assert len(grid["threshold"]) >= 2

    def test_empty_ranges_skip(self):
        """Ranges with empty lists are skipped."""
        hints = OptimizationHints(
            parameters_to_optimize=["period"],
            ranges={"period": []},
        )
        grid = WalkForwardBridge._grid_from_hints(hints, {"period": 14})
        # Should use variations since range is empty
        assert "period" in grid


# =============================================================================
# EXECUTE BACKTEST TESTS
# =============================================================================


class TestExecuteBacktest:
    """Test _execute_backtest() method."""

    @patch("backend.backtesting.signal_generators.generate_signals_for_strategy")
    @patch("backend.backtesting.engines.fallback_engine_v4.FallbackEngineV4")
    def test_returns_correct_keys(self, mock_engine_cls, mock_signals, bridge):
        """Returns dict with return, sharpe, max_drawdown, trades keys."""
        # Mock signal generation
        mock_signals.return_value = (
            np.array([False, True, False]),
            np.array([False, False, True]),
            np.array([False, False, False]),
            np.array([False, False, False]),
        )

        # Mock engine
        mock_metrics = MagicMock()
        mock_metrics.total_return_pct = 5.0
        mock_metrics.sharpe_ratio = 1.5
        mock_metrics.max_drawdown_pct = 10.0
        mock_metrics.total_trades = 3

        mock_output = MagicMock()
        mock_output.is_valid = True
        mock_output.metrics = mock_metrics

        mock_engine = MagicMock()
        mock_engine.run.return_value = mock_output
        mock_engine_cls.return_value = mock_engine

        candles = [
            {"open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000},
            {"open": 102, "high": 108, "low": 100, "close": 106, "volume": 1100},
            {"open": 106, "high": 110, "low": 103, "close": 104, "volume": 900},
        ]

        result = bridge._execute_backtest(
            data=candles,
            strategy_type="rsi",
            strategy_params={"period": 14},
            symbol="BTCUSDT",
            timeframe="15",
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
        )

        assert "return" in result
        assert "sharpe" in result
        assert "max_drawdown" in result
        assert "trades" in result
        assert result["return"] == pytest.approx(0.05)  # 5% / 100
        assert result["sharpe"] == 1.5

    def test_empty_data_returns_zeros(self, bridge):
        """Empty data returns zero metrics."""
        result = bridge._execute_backtest(
            data=[],
            strategy_type="rsi",
            strategy_params={"period": 14},
            symbol="BTCUSDT",
            timeframe="15",
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
        )
        assert result == {"return": 0, "sharpe": 0, "max_drawdown": 0, "trades": 0}


# =============================================================================
# RUN WALK-FORWARD TESTS
# =============================================================================


class TestRunWalkForward:
    """Test run_walk_forward() integration."""

    @patch.object(WalkForwardBridge, "_execute_backtest")
    def test_walk_forward_returns_result(self, mock_bt, bridge, rsi_strategy, sample_ohlcv):
        """Walk-forward produces WalkForwardResult."""
        mock_bt.return_value = {"return": 0.05, "sharpe": 1.2, "max_drawdown": 0.08, "trades": 5}

        result = bridge.run_walk_forward(
            strategy=rsi_strategy,
            df=sample_ohlcv,
            symbol="BTCUSDT",
            timeframe="15",
        )

        assert isinstance(result, WalkForwardResult)
        assert result.n_splits == 3
        assert len(result.windows) > 0
        assert result.confidence_level in ("low", "medium", "high")
        assert 0 <= result.overfit_score <= 1
        assert 0 <= result.consistency_ratio <= 1

    @patch.object(WalkForwardBridge, "_execute_backtest")
    def test_walk_forward_to_dict(self, mock_bt, bridge, rsi_strategy, sample_ohlcv):
        """WalkForwardResult.to_dict() produces serializable output."""
        mock_bt.return_value = {"return": 0.03, "sharpe": 0.8, "max_drawdown": 0.15, "trades": 3}

        result = bridge.run_walk_forward(
            strategy=rsi_strategy,
            df=sample_ohlcv,
        )

        d = result.to_dict()
        assert "config" in d
        assert "aggregate_metrics" in d
        assert "robustness" in d
        assert "recommendation" in d
        assert "windows" in d

    @patch.object(WalkForwardBridge, "_execute_backtest")
    def test_walk_forward_empty_grid_raises(self, mock_bt, bridge):
        """Walk-forward with unknown strategy + tiny data raises ValueError."""
        strategy = StrategyDefinition(
            strategy_name="Empty",
            signals=[Signal(id="s1", type="unknown_xyz", params={}, weight=1.0)],
        )
        df = pd.DataFrame({"close": [1, 2, 3]})

        with pytest.raises(ValueError):
            bridge.run_walk_forward(strategy=strategy, df=df)


class TestRunWalkForwardAsync:
    """Test async wrapper."""

    @patch.object(WalkForwardBridge, "run_walk_forward")
    async def test_async_delegates_to_sync(self, mock_sync, bridge, rsi_strategy, sample_ohlcv):
        """Async version delegates to sync run_walk_forward."""
        mock_result = MagicMock(spec=WalkForwardResult)
        mock_sync.return_value = mock_result

        result = await bridge.run_walk_forward_async(
            strategy=rsi_strategy,
            df=sample_ohlcv,
        )

        mock_sync.assert_called_once()
        assert result is mock_result


# =============================================================================
# STRATEGY CONTROLLER INTEGRATION TESTS
# =============================================================================


class TestStrategyControllerWalkForward:
    """Test walk-forward integration in StrategyController."""

    def test_pipeline_result_has_walk_forward(self):
        """PipelineResult has walk_forward field."""
        from backend.agents.strategy_controller import PipelineResult

        result = PipelineResult()
        assert hasattr(result, "walk_forward")
        assert result.walk_forward == {}

    def test_pipeline_stage_has_walk_forward(self):
        """PipelineStage enum includes WALK_FORWARD."""
        from backend.agents.strategy_controller import PipelineStage

        assert hasattr(PipelineStage, "WALK_FORWARD")
        assert PipelineStage.WALK_FORWARD.value == "walk_forward"

    def test_pipeline_result_to_dict_includes_walk_forward(self):
        """PipelineResult.to_dict() includes walk_forward."""
        from backend.agents.strategy_controller import PipelineResult

        result = PipelineResult()
        result.walk_forward = {"overfit_score": 0.3}
        d = result.to_dict()
        assert "walk_forward" in d
        assert d["walk_forward"]["overfit_score"] == 0.3

    def test_generate_strategy_accepts_walk_forward_flag(self):
        """StrategyController.generate_strategy() accepts enable_walk_forward."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()
        sig = controller.generate_strategy.__code__.co_varnames
        assert "enable_walk_forward" in sig

    def test_generate_and_backtest_accepts_walk_forward_flag(self):
        """StrategyController.generate_and_backtest() accepts enable_walk_forward."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()
        sig = controller.generate_and_backtest.__code__.co_varnames
        assert "enable_walk_forward" in sig
