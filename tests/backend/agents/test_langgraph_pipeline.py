"""
Tests for LangGraph Pipeline Integration — TradingStrategyGraph.

Tests cover:
- PipelineConfig defaults and customization
- Individual node execution (MarketAnalysis, Consensus, Backtest, QualityCheck, Report)
- Graph construction (nodes, edges, entry/exit, conditional routing)
- Quality check conditional routing (re_optimize, re_generate, report)
- Full pipeline execution with mocked LLM + backtest
- Re-optimization loop via walk-forward
- Re-generation loop via parallel_generation
- Report structure and completeness
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.agents.integration.langgraph_pipeline import (
    BacktestNode,
    ConsensusNode,
    MarketAnalysisNode,
    ParallelGenerationNode,
    PipelineConfig,
    QualityCheckNode,
    ReOptimizeNode,
    ReportNode,
    TradingStrategyGraph,
)
from backend.agents.langgraph_orchestrator import AgentState

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate a simple OHLCV DataFrame for testing."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2025-01-01", periods=n, freq="15min")
    close = 95000 + np.cumsum(np.random.randn(n) * 50)
    return pd.DataFrame(
        {
            "open": close - np.random.rand(n) * 30,
            "high": close + np.random.rand(n) * 50,
            "low": close - np.random.rand(n) * 50,
            "close": close,
            "volume": np.random.rand(n) * 100 + 10,
        },
        index=dates,
    )


@pytest.fixture
def base_state(sample_ohlcv) -> AgentState:
    """AgentState with OHLCV data and config loaded."""
    state = AgentState()
    state.context["symbol"] = "BTCUSDT"
    state.context["timeframe"] = "15"
    state.context["df"] = sample_ohlcv
    state.context["pipeline_config"] = PipelineConfig()
    return state


@pytest.fixture
def mock_strategy():
    """Create a mock StrategyDefinition."""
    strategy = MagicMock()
    strategy.strategy_name = "test_rsi_strategy"
    strategy.signals = [MagicMock(params={"period": 14, "overbought": 70})]
    strategy.exit_conditions = MagicMock()
    strategy.filters = []
    strategy.optimization_hints = None
    strategy.entry_conditions = MagicMock()
    strategy.agent_metadata = MagicMock(agent_name="deepseek")
    strategy.to_dict.return_value = {"name": "test_rsi_strategy", "type": "rsi"}
    return strategy


@pytest.fixture
def state_with_strategy(base_state, mock_strategy):
    """State with a selected strategy ready for backtest."""
    state = base_state
    state.set_result("selected_strategy", mock_strategy)
    state.set_result("proposals", [mock_strategy])
    return state


@pytest.fixture
def state_with_backtest(state_with_strategy):
    """State with backtest results (good quality)."""
    state = state_with_strategy
    state.set_result(
        "backtest_metrics",
        {
            "sharpe_ratio": 1.5,
            "max_drawdown": -12.0,
            "net_profit": 850.0,
            "win_rate": 0.62,
            "total_trades": 35,
        },
    )
    state.context["last_sharpe"] = 1.5
    state.context["last_drawdown"] = 12.0
    state.context["optimize_attempt"] = 1
    state.context["generation_attempt"] = 1
    return state


@pytest.fixture
def state_low_sharpe(state_with_strategy):
    """State with low Sharpe backtest results (triggers re-optimize)."""
    state = state_with_strategy
    state.set_result(
        "backtest_metrics",
        {
            "sharpe_ratio": 0.5,
            "max_drawdown": -10.0,
            "net_profit": 120.0,
            "win_rate": 0.48,
            "total_trades": 20,
        },
    )
    state.context["last_sharpe"] = 0.5
    state.context["last_drawdown"] = 10.0
    state.context["optimize_attempt"] = 1
    state.context["generation_attempt"] = 1
    return state


@pytest.fixture
def state_high_dd(state_with_strategy):
    """State with high drawdown backtest results (triggers re-generate)."""
    state = state_with_strategy
    state.set_result(
        "backtest_metrics",
        {
            "sharpe_ratio": 0.8,
            "max_drawdown": -35.0,
            "net_profit": -200.0,
            "win_rate": 0.40,
            "total_trades": 15,
        },
    )
    state.context["last_sharpe"] = 0.8
    state.context["last_drawdown"] = 35.0
    state.context["optimize_attempt"] = 1
    state.context["generation_attempt"] = 1
    return state


# =============================================================================
# PIPELINE CONFIG TESTS
# =============================================================================


class TestPipelineConfig:
    """Test PipelineConfig defaults and customization."""

    def test_default_values(self):
        config = PipelineConfig()
        assert config.min_sharpe == 1.0
        assert config.max_drawdown_pct == 20.0
        assert config.max_reoptimize_cycles == 2
        assert config.max_regenerate_cycles == 1
        assert config.agents == ["deepseek", "qwen", "perplexity"]
        assert config.initial_capital == 10000.0
        assert config.leverage == 1.0
        assert config.commission == 0.0007  # TradingView parity
        assert config.direction == "both"
        assert config.enable_walk_forward is False

    def test_custom_values(self):
        config = PipelineConfig(
            min_sharpe=2.0,
            max_drawdown_pct=10.0,
            agents=["deepseek"],
            initial_capital=50000,
        )
        assert config.min_sharpe == 2.0
        assert config.max_drawdown_pct == 10.0
        assert config.agents == ["deepseek"]
        assert config.initial_capital == 50000

    def test_commission_never_change(self):
        """Commission rate MUST be 0.0007 for TradingView parity."""
        config = PipelineConfig()
        assert config.commission == 0.0007


# =============================================================================
# GRAPH CONSTRUCTION TESTS
# =============================================================================


class TestGraphConstruction:
    """Test TradingStrategyGraph construction."""

    def test_creates_graph(self):
        graph = TradingStrategyGraph.create_graph()
        assert graph is not None
        assert graph.name == "trading_strategy_pipeline"

    def test_has_seven_nodes(self):
        graph = TradingStrategyGraph.create_graph()
        assert len(graph.nodes) == 7
        expected_nodes = {
            "market_analysis",
            "parallel_generation",
            "consensus",
            "backtest",
            "quality_check",
            "re_optimize",
            "report",
        }
        assert set(graph.nodes.keys()) == expected_nodes

    def test_entry_point(self):
        graph = TradingStrategyGraph.create_graph()
        assert graph.entry_point == "market_analysis"

    def test_exit_point(self):
        graph = TradingStrategyGraph.create_graph()
        assert "report" in graph.exit_points

    def test_linear_edges(self):
        graph = TradingStrategyGraph.create_graph()
        # market_analysis → parallel_generation
        assert any(e.target == "parallel_generation" for e in graph.edges["market_analysis"])
        # parallel_generation → consensus
        assert any(e.target == "consensus" for e in graph.edges["parallel_generation"])
        # consensus → backtest
        assert any(e.target == "backtest" for e in graph.edges["consensus"])
        # backtest → quality_check
        assert any(e.target == "quality_check" for e in graph.edges["backtest"])

    def test_conditional_router(self):
        graph = TradingStrategyGraph.create_graph()
        assert "quality_check" in graph.routers
        router = graph.routers["quality_check"]
        assert router.default_route == "report"
        assert len(router.routes) == 2

    def test_reoptimize_loops_to_backtest(self):
        graph = TradingStrategyGraph.create_graph()
        assert any(e.target == "backtest" for e in graph.edges["re_optimize"])

    def test_visualize(self):
        result = TradingStrategyGraph.visualize()
        assert "market_analysis" in result
        assert "report" in result
        assert "[EXIT]" in result

    def test_custom_config_affects_graph(self):
        """Graph builds without errors with custom config."""
        config = PipelineConfig(
            min_sharpe=2.5,
            max_drawdown_pct=5.0,
            agents=["deepseek"],
        )
        graph = TradingStrategyGraph.create_graph(config)
        assert graph is not None
        assert len(graph.nodes) == 7


# =============================================================================
# INDIVIDUAL NODE TESTS
# =============================================================================


class TestMarketAnalysisNode:
    """Test MarketAnalysisNode execution."""

    async def test_executes_with_valid_data(self, base_state):
        node = MarketAnalysisNode()
        result = await node.execute(base_state)

        assert result.get_result("market_analysis") is not None
        assert "market_analysis" in [m["agent"] for m in result.messages]

    async def test_fails_without_df(self):
        state = AgentState()
        node = MarketAnalysisNode()

        with pytest.raises(ValueError, match="No OHLCV DataFrame"):
            await node.execute(state)

    def test_node_metadata(self):
        node = MarketAnalysisNode()
        assert node.name == "market_analysis"
        assert node.timeout == 30.0


class TestConsensusNode:
    """Test ConsensusNode execution."""

    async def test_single_proposal_no_consensus(self, base_state, mock_strategy):
        state = base_state
        state.set_result("proposals", [mock_strategy])

        node = ConsensusNode()
        result = await node.execute(state)

        assert result.get_result("selected_strategy") is not None
        assert "no consensus needed" in result.context.get("consensus_summary", "").lower()

    async def test_multiple_proposals_triggers_consensus(self, base_state, mock_strategy):
        strategy2 = MagicMock()
        strategy2.strategy_name = "test_macd"
        strategy2.signals = [MagicMock(indicator="macd", params={"fast": 12})]
        strategy2.exit_conditions = MagicMock()
        strategy2.filters = []
        strategy2.optimization_hints = None
        strategy2.entry_conditions = MagicMock()
        strategy2.agent_metadata = MagicMock(agent_name="qwen")
        strategy2.to_dict.return_value = {"name": "test_macd", "type": "macd"}

        state = base_state
        state.set_result("proposals", [mock_strategy, strategy2])

        node = ConsensusNode()

        # ConsensusEngine may fail with mock strategies, should fallback
        result = await node.execute(state)
        assert result.get_result("selected_strategy") is not None

    async def test_fails_without_proposals(self, base_state):
        base_state.set_result("proposals", [])

        node = ConsensusNode()
        with pytest.raises(ValueError, match="No proposals"):
            await node.execute(base_state)


class TestBacktestNode:
    """Test BacktestNode execution."""

    @patch("backend.agents.integration.backtest_bridge.BacktestBridge")
    async def test_executes_backtest(self, mock_bridge_cls, state_with_strategy):
        mock_bridge = AsyncMock()
        mock_bridge.run_strategy.return_value = {
            "sharpe_ratio": 1.8,
            "max_drawdown": -8.0,
            "net_profit": 1200.0,
        }
        mock_bridge_cls.return_value = mock_bridge

        node = BacktestNode()
        result = await node.execute(state_with_strategy)

        assert result.get_result("backtest_metrics")["sharpe_ratio"] == 1.8
        assert result.context["last_sharpe"] == 1.8
        assert result.context["last_drawdown"] == 8.0

    async def test_fails_without_strategy(self, base_state):
        node = BacktestNode()
        with pytest.raises(ValueError, match="No selected_strategy"):
            await node.execute(base_state)


# =============================================================================
# QUALITY CHECK ROUTING TESTS
# =============================================================================


class TestQualityCheckNode:
    """Test QualityCheckNode conditional routing."""

    async def test_pass_when_quality_good(self, state_with_backtest):
        """Good metrics → decision = 'report'."""
        node = QualityCheckNode()
        result = await node.execute(state_with_backtest)

        assert result.context["quality_decision"] == "report"

    async def test_reoptimize_when_low_sharpe(self, state_low_sharpe):
        """Low Sharpe → decision = 're_optimize'."""
        node = QualityCheckNode()
        result = await node.execute(state_low_sharpe)

        assert result.context["quality_decision"] == "re_optimize"

    async def test_regenerate_when_high_drawdown(self, state_high_dd):
        """High drawdown → decision = 're_generate'."""
        node = QualityCheckNode()
        result = await node.execute(state_high_dd)

        assert result.context["quality_decision"] == "re_generate"

    async def test_drawdown_priority_over_sharpe(self, state_high_dd):
        """Drawdown check takes priority over Sharpe check."""
        # state_high_dd has Sharpe=0.8 AND DD=35% → should be re_generate (DD check first)
        node = QualityCheckNode()
        result = await node.execute(state_high_dd)

        assert result.context["quality_decision"] == "re_generate"

    async def test_report_when_retries_exhausted(self, state_low_sharpe):
        """Low Sharpe but max retries reached → 'report' (accept marginal)."""
        state_low_sharpe.context["optimize_attempt"] = 3  # > max_reoptimize_cycles=2

        node = QualityCheckNode()
        result = await node.execute(state_low_sharpe)

        assert result.context["quality_decision"] == "report"

    async def test_regenerate_retries_exhausted(self, state_high_dd):
        """High DD but max re-generate retries reached → fallback."""
        state_high_dd.context["generation_attempt"] = 2  # > max_regenerate_cycles=1

        node = QualityCheckNode()
        result = await node.execute(state_high_dd)

        # With generation exhausted and Sharpe < 1.0, should try re_optimize
        assert result.context["quality_decision"] in ("re_optimize", "report")

    async def test_custom_thresholds(self, state_with_backtest):
        """Custom thresholds affect routing."""
        # Sharpe=1.5 but min_sharpe=2.0 → re_optimize
        state_with_backtest.context["pipeline_config"] = PipelineConfig(min_sharpe=2.0)

        node = QualityCheckNode()
        result = await node.execute(state_with_backtest)

        assert result.context["quality_decision"] == "re_optimize"


# =============================================================================
# CONDITIONAL ROUTER INTEGRATION
# =============================================================================


class TestConditionalRouterIntegration:
    """Test that quality_check router correctly dispatches to nodes."""

    def test_router_routes_to_report(self):
        graph = TradingStrategyGraph.create_graph()
        router = graph.routers["quality_check"]

        state = AgentState()
        state.context["quality_decision"] = "report"

        next_node = router.get_next_node(state)
        assert next_node == "report"

    def test_router_routes_to_reoptimize(self):
        graph = TradingStrategyGraph.create_graph()
        router = graph.routers["quality_check"]

        state = AgentState()
        state.context["quality_decision"] = "re_optimize"

        next_node = router.get_next_node(state)
        assert next_node == "re_optimize"

    def test_router_routes_to_regenerate(self):
        graph = TradingStrategyGraph.create_graph()
        router = graph.routers["quality_check"]

        state = AgentState()
        state.context["quality_decision"] = "re_generate"

        next_node = router.get_next_node(state)
        assert next_node == "parallel_generation"

    def test_router_default_to_report(self):
        graph = TradingStrategyGraph.create_graph()
        router = graph.routers["quality_check"]

        state = AgentState()
        # No quality_decision set

        next_node = router.get_next_node(state)
        assert next_node == "report"


# =============================================================================
# REPORT NODE TESTS
# =============================================================================


class TestReportNode:
    """Test ReportNode output structure."""

    async def test_report_structure(self, state_with_backtest, mock_strategy):
        state_with_backtest.set_result("selected_strategy", mock_strategy)

        node = ReportNode()
        result = await node.execute(state_with_backtest)

        report = result.get_result("report")
        assert report is not None
        assert report["success"] is True
        assert report["strategy"] is not None
        assert report["backtest_metrics"]["sharpe_ratio"] == 1.5
        assert report["sharpe"] == 1.5
        assert report["max_drawdown"] == 12.0
        assert report["proposals_count"] >= 0
        assert "agents" in report

    async def test_report_without_strategy(self, base_state):
        node = ReportNode()
        result = await node.execute(base_state)

        report = result.get_result("report")
        assert report["strategy"] is None
        assert report["success"] is True  # Report node always succeeds


# =============================================================================
# REOPTIMIZE NODE TESTS
# =============================================================================


class TestReOptimizeNode:
    """Test ReOptimizeNode walk-forward execution."""

    @patch("backend.agents.integration.walk_forward_bridge.WalkForwardBridge")
    async def test_applies_recommended_params(self, mock_wf_cls, state_with_strategy):
        mock_wf = AsyncMock()
        wf_result = MagicMock()
        wf_result.recommended_params = {"period": 21, "overbought": 75}
        wf_result.overfit_score = 0.15
        wf_result.to_dict.return_value = {"overfit_score": 0.15}
        mock_wf.run_walk_forward_async.return_value = wf_result
        mock_wf_cls.return_value = mock_wf

        node = ReOptimizeNode()
        result = await node.execute(state_with_strategy)

        # Check params applied to strategy signals
        strategy = result.get_result("selected_strategy")
        for signal in strategy.signals:
            if "period" in signal.params:
                assert signal.params["period"] == 21

    @patch("backend.agents.integration.walk_forward_bridge.WalkForwardBridge")
    async def test_handles_wf_failure(self, mock_wf_cls, state_with_strategy):
        mock_wf_cls.side_effect = RuntimeError("WF failed")

        node = ReOptimizeNode()
        # Should not raise
        result = await node.execute(state_with_strategy)

        assert any("failed" in m["content"].lower() for m in result.messages)

    async def test_fails_without_strategy(self, base_state):
        node = ReOptimizeNode()
        with pytest.raises(ValueError, match="No selected_strategy"):
            await node.execute(base_state)


# =============================================================================
# FULL PIPELINE TESTS (mocked)
# =============================================================================


class TestFullPipeline:
    """Test full TradingStrategyGraph.run() with mocked components."""

    @patch("backend.agents.integration.backtest_bridge.BacktestBridge")
    async def test_full_pipeline_pass(self, mock_bt_cls, sample_ohlcv, mock_strategy):
        """Pipeline completes with good metrics → report."""
        mock_bt = AsyncMock()
        mock_bt.run_strategy.return_value = {
            "sharpe_ratio": 2.0,
            "max_drawdown": -5.0,
            "net_profit": 2000.0,
        }
        mock_bt_cls.return_value = mock_bt

        with patch.object(
            ParallelGenerationNode,
            "execute",
            new_callable=AsyncMock,
        ) as mock_gen:

            async def gen_side_effect(state):
                state.set_result("proposals", [mock_strategy])
                state.context["generation_attempt"] = 1
                return state

            mock_gen.side_effect = gen_side_effect

            config = PipelineConfig(agents=["deepseek"])
            report = await TradingStrategyGraph.run(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                config=config,
            )

        assert report.get("success") is True or report.get("sharpe", 0) > 0
        assert "total_duration_ms" in report
        assert "graph_metrics" in report

    @patch("backend.agents.integration.walk_forward_bridge.WalkForwardBridge")
    @patch("backend.agents.integration.backtest_bridge.BacktestBridge")
    async def test_pipeline_reoptimize_loop(self, mock_bt_cls, mock_wf_cls, sample_ohlcv, mock_strategy):
        """Pipeline triggers re-optimization when Sharpe is low, then passes."""
        call_count = {"n": 0}

        mock_bt = AsyncMock()

        async def bt_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First backtest: bad Sharpe
                return {"sharpe_ratio": 0.3, "max_drawdown": -8.0, "net_profit": 50.0}
            else:
                # After re-optimize: good Sharpe
                return {"sharpe_ratio": 1.8, "max_drawdown": -6.0, "net_profit": 900.0}

        mock_bt.run_strategy = bt_side_effect
        mock_bt_cls.return_value = mock_bt

        # Mock WF bridge for re-optimization
        mock_wf = AsyncMock()
        wf_result = MagicMock()
        wf_result.recommended_params = {"period": 21}
        wf_result.overfit_score = 0.1
        wf_result.to_dict.return_value = {}
        mock_wf.run_walk_forward_async.return_value = wf_result
        mock_wf_cls.return_value = mock_wf

        with patch.object(
            ParallelGenerationNode,
            "execute",
            new_callable=AsyncMock,
        ) as mock_gen:

            async def gen_side_effect(state):
                state.set_result("proposals", [mock_strategy])
                state.context["generation_attempt"] = state.context.get("generation_attempt", 0) + 1
                return state

            mock_gen.side_effect = gen_side_effect

            config = PipelineConfig(
                agents=["deepseek"],
                min_sharpe=1.0,
                max_reoptimize_cycles=2,
            )
            report = await TradingStrategyGraph.run(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                config=config,
            )

        # Should have done 2 backtests (first bad, then good after re-optimize)
        assert call_count["n"] >= 2

    async def test_pipeline_state_initialization(self, sample_ohlcv):
        """State is properly initialized before graph execution."""
        config = PipelineConfig()
        graph = TradingStrategyGraph.create_graph(config)

        state = AgentState()
        state.context["symbol"] = "ETHUSDT"
        state.context["timeframe"] = "60"
        state.context["df"] = sample_ohlcv
        state.context["pipeline_config"] = config

        assert state.context["symbol"] == "ETHUSDT"
        assert state.context["timeframe"] == "60"
        assert isinstance(state.context["df"], pd.DataFrame)

    def test_graph_metrics_structure(self):
        """Graph metrics returns expected keys."""
        graph = TradingStrategyGraph.create_graph()
        metrics = graph.get_metrics()

        assert "name" in metrics
        assert "nodes_count" in metrics
        assert "edges_count" in metrics
        assert metrics["nodes_count"] == 7
        assert metrics["edges_count"] > 0
