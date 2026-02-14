"""
Coverage Gap Tests for AI Agent Pipeline components.

Targets uncovered branches in:
- PromptEngineer (market_analysis, validation, auto_detect_issues)
- StrategyController (multi-agent, walk-forward, error paths)
- LangGraph orchestrator (graph building, state management)
- Deliberation module (voting methods, consensus)
- StrategyEvolution (mutation, selection, generation)
- AgentTracker (performance tracking, recommendations)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.agents.prompts.response_parser import (
    ExitCondition,
    ExitConditions,
    Signal,
    StrategyDefinition,
)

# =============================================================================
# SHARED FIXTURES
# =============================================================================


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """OHLCV data for tests."""
    np.random.seed(42)
    n = 300
    dates = pd.date_range("2025-01-01", periods=n, freq="15min")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": close + np.random.randn(n) * 0.1,
            "high": close + abs(np.random.randn(n) * 0.5),
            "low": close - abs(np.random.randn(n) * 0.5),
            "close": close,
            "volume": np.random.randint(100, 10000, n).astype(float),
        }
    )


@pytest.fixture
def mock_strategy() -> StrategyDefinition:
    """Standard test strategy."""
    return StrategyDefinition(
        strategy_name="Test Strategy",
        signals=[
            Signal(id="s1", type="RSI", params={"period": 14, "oversold": 30, "overbought": 70}, weight=1.0),
        ],
        exit_conditions=ExitConditions(
            take_profit=ExitCondition(type="fixed_pct", value=2.0),
            stop_loss=ExitCondition(type="fixed_pct", value=1.0),
        ),
    )


# =============================================================================
# TestPromptEngineerCoverage
# =============================================================================


class TestPromptEngineerCoverage:
    """Cover untested branches in PromptEngineer."""

    def test_create_market_analysis_prompt(self, sample_ohlcv):
        """create_market_analysis_prompt generates valid prompt."""
        from backend.agents.prompts.context_builder import MarketContextBuilder
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        builder = MarketContextBuilder()
        ctx = builder.build_context("BTCUSDT", "15", sample_ohlcv)

        engineer = PromptEngineer()
        prompt = engineer.create_market_analysis_prompt(context=ctx, start_date="2025-01-01", end_date="2025-02-01")
        assert "BTCUSDT" in prompt
        assert len(prompt) > 50

    def test_create_validation_prompt(self):
        """create_validation_prompt includes commission and leverage."""
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        engineer = PromptEngineer()
        strategy_json = json.dumps({"strategy_name": "Test", "signals": []})
        prompt = engineer.create_validation_prompt(
            strategy_json=strategy_json,
            commission=0.0007,
            leverage=10,
        )
        assert "Test" in prompt
        assert "10" in prompt

    def test_create_strategy_prompt_without_examples(self, sample_ohlcv):
        """Strategy prompt without examples is shorter."""
        from backend.agents.prompts.context_builder import MarketContextBuilder
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        builder = MarketContextBuilder()
        ctx = builder.build_context("BTCUSDT", "15", sample_ohlcv)

        engineer = PromptEngineer()
        with_examples = engineer.create_strategy_prompt(
            context=ctx,
            platform_config={"commission": 0.0007},
            include_examples=True,
        )
        without_examples = engineer.create_strategy_prompt(
            context=ctx,
            platform_config={"commission": 0.0007},
            include_examples=False,
        )
        assert len(with_examples) > len(without_examples)

    def test_create_strategy_prompt_perplexity_agent(self, sample_ohlcv):
        """Strategy prompt for perplexity agent."""
        from backend.agents.prompts.context_builder import MarketContextBuilder
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        builder = MarketContextBuilder()
        ctx = builder.build_context("BTCUSDT", "15", sample_ohlcv)

        engineer = PromptEngineer()
        prompt = engineer.create_strategy_prompt(
            context=ctx,
            platform_config={"commission": 0.0007},
            agent_name="perplexity",
        )
        assert len(prompt) > 100

    def test_create_optimization_prompt_with_issues(self):
        """Optimization prompt with explicit issues list."""
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        engineer = PromptEngineer()
        prompt = engineer.create_optimization_prompt(
            strategy_name="RSI Strategy",
            strategy_type="rsi",
            strategy_params={"period": 14},
            backtest_results={"sharpe_ratio": 1.5, "win_rate": 0.6},
            issues=["High drawdown", "Few trades"],
        )
        assert "High drawdown" in prompt

    def test_auto_detect_issues_all_good(self):
        """_auto_detect_issues with all good metrics."""
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        engineer = PromptEngineer()
        result = engineer._auto_detect_issues(
            {
                "sharpe_ratio": 2.0,
                "max_drawdown_pct": 5,
                "win_rate": 0.7,
                "profit_factor": 2.5,
                "total_trades": 100,
            }
        )
        assert "No major issues" in result

    def test_auto_detect_issues_all_bad(self):
        """_auto_detect_issues detects multiple problems."""
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        engineer = PromptEngineer()
        result = engineer._auto_detect_issues(
            {
                "sharpe_ratio": -0.5,
                "max_drawdown_pct": 25,
                "win_rate": 0.3,
                "profit_factor": 0.5,
                "total_trades": 10,
            }
        )
        assert "Negative Sharpe" in result
        assert "Max Drawdown" in result
        assert "Win Rate" in result
        assert "Profit Factor" in result
        assert "Insufficient trades" in result

    def test_auto_detect_issues_moderate(self):
        """_auto_detect_issues detects moderate issues."""
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        engineer = PromptEngineer()
        result = engineer._auto_detect_issues(
            {
                "sharpe_ratio": 0.7,
                "max_drawdown_pct": 16,
                "win_rate": 0.5,
                "profit_factor": 1.2,
                "total_trades": 50,
            }
        )
        assert "Low Sharpe" in result
        assert "Elevated Max Drawdown" in result

    def test_get_system_message_all_agents(self):
        """System messages for all agent types."""
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        engineer = PromptEngineer()
        for agent in ["deepseek", "qwen", "perplexity"]:
            msg = engineer.get_system_message(agent)
            assert "JSON" in msg
            assert len(msg) > 50


# =============================================================================
# TestStrategyControllerCoverage
# =============================================================================


class TestStrategyControllerCoverage:
    """Cover untested branches in StrategyController."""

    @pytest.mark.asyncio
    async def test_generate_and_backtest_convenience(self, sample_ohlcv):
        """generate_and_backtest convenience method works."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()
        mock_response = json.dumps(
            {
                "strategy_name": "Test",
                "signals": [{"id": "s1", "type": "RSI", "params": {"period": 14}, "weight": 1.0}],
            }
        )

        with (
            patch.object(controller, "_call_llm", new_callable=AsyncMock, return_value=mock_response),
            patch.object(controller, "_run_backtest", new_callable=AsyncMock, return_value={"sharpe_ratio": 1.5}),
        ):
            result = await controller.generate_and_backtest(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                agents=["deepseek"],
                initial_capital=10000,
                leverage=1,
            )

        assert result.success

    @pytest.mark.asyncio
    async def test_pipeline_with_walk_forward(self, sample_ohlcv):
        """Pipeline with walk-forward enabled."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()
        mock_response = json.dumps(
            {
                "strategy_name": "WF Test",
                "signals": [{"id": "s1", "type": "RSI", "params": {"period": 14}, "weight": 1.0}],
                "exit_conditions": {
                    "take_profit": {"type": "fixed_pct", "value": 2.0},
                    "stop_loss": {"type": "fixed_pct", "value": 1.0},
                },
            }
        )
        mock_bt = {"sharpe_ratio": 1.5, "max_drawdown": 0.1}
        mock_wf = {"overfit_score": 0.2, "consistency_ratio": 0.8}

        with (
            patch.object(controller, "_call_llm", new_callable=AsyncMock, return_value=mock_response),
            patch.object(controller, "_run_backtest", new_callable=AsyncMock, return_value=mock_bt),
            patch.object(controller, "_run_walk_forward", new_callable=AsyncMock, return_value=mock_wf),
        ):
            result = await controller.generate_strategy(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                agents=["deepseek"],
                run_backtest=True,
                enable_walk_forward=True,
            )

        assert result.success
        assert result.walk_forward == mock_wf

    @pytest.mark.asyncio
    async def test_score_proposal_many_signals(self):
        """Scoring penalizes strategies with too many signals."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()
        strategy = StrategyDefinition(
            strategy_name="Complex",
            signals=[
                Signal(id=f"s{i}", type="RSI", params={"period": 14})
                for i in range(5)  # 5 signals = penalty
            ],
        )
        score = controller._score_proposal(strategy)
        assert score < 7.0

    @pytest.mark.asyncio
    async def test_select_best_proposal_single(self):
        """_select_best_proposal with single proposal returns it."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()
        s = StrategyDefinition(
            strategy_name="Only",
            signals=[Signal(id="s1", type="RSI", params={"period": 14})],
        )
        result = await controller._select_best_proposal([s])
        assert result is s

    @pytest.mark.asyncio
    async def test_select_best_proposal_empty(self):
        """_select_best_proposal with empty list returns None."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()
        result = await controller._select_best_proposal([])
        assert result is None


# =============================================================================
# TestLangGraphOrchestratorCoverage
# =============================================================================


class TestLangGraphOrchestratorCoverage:
    """Cover untested branches in langgraph_orchestrator."""

    def test_agent_state_messages(self):
        """AgentState message management."""
        from backend.agents.langgraph_orchestrator import AgentState

        state = AgentState()
        state.add_message("user", "Hello", "test_agent")
        state.add_message("system", "Processing", "system")

        assert len(state.messages) == 2
        assert state.messages[0]["role"] == "user"
        assert state.messages[0]["agent"] == "test_agent"

    def test_agent_state_results(self):
        """AgentState result storage and retrieval."""
        from backend.agents.langgraph_orchestrator import AgentState

        state = AgentState()
        state.set_result("node_1", {"key": "value"})
        assert state.get_result("node_1") == {"key": "value"}
        assert state.get_result("nonexistent") is None

    def test_agent_state_errors(self):
        """AgentState error tracking."""
        from backend.agents.langgraph_orchestrator import AgentState

        state = AgentState()
        state.add_error("node_1", ValueError("test error"))
        assert len(state.errors) == 1
        assert state.errors[0]["error_type"] == "ValueError"

    def test_function_agent_creation(self):
        """FunctionAgent wraps a callable correctly."""
        from backend.agents.langgraph_orchestrator import AgentState, FunctionAgent

        async def my_func(state: AgentState) -> AgentState:
            state.set_result("my_func", {"done": True})
            return state

        agent = FunctionAgent(name="test_func", func=my_func, description="Test function agent")
        assert agent.name == "test_func"

    @pytest.mark.asyncio
    async def test_function_agent_execution(self):
        """FunctionAgent executes wrapped function."""
        from backend.agents.langgraph_orchestrator import AgentState, FunctionAgent

        async def adder(state: AgentState) -> AgentState:
            val = state.context.get("input", 0)
            state.set_result("adder", {"output": val + 1})
            return state

        agent = FunctionAgent(name="adder", func=adder)
        state = AgentState()
        state.context["input"] = 5

        result = await agent.execute(state)
        assert result.get_result("adder") == {"output": 6}

    def test_agent_graph_creation(self):
        """AgentGraph can be created and has nodes dict."""
        from backend.agents.langgraph_orchestrator import AgentGraph

        graph = AgentGraph(name="test_graph")
        assert graph.name == "test_graph"

    def test_agent_graph_add_node(self):
        """AgentGraph.add_node adds a node."""
        from backend.agents.langgraph_orchestrator import (
            AgentGraph,
            AgentState,
            FunctionAgent,
        )

        async def noop(state: AgentState) -> AgentState:
            return state

        graph = AgentGraph(name="test")
        node = FunctionAgent(name="noop", func=noop)
        graph.add_node(node)
        assert "noop" in graph.nodes


# =============================================================================
# TestDeliberationCoverage
# =============================================================================


class TestDeliberationCoverage:
    """Cover untested branches in deliberation module."""

    def test_deliberation_initialization(self):
        """MultiAgentDeliberation instantiation."""
        from backend.agents.consensus.deliberation import (
            MultiAgentDeliberation,
        )

        delib = MultiAgentDeliberation(enable_parallel_calls=False)
        assert delib.stats["total_deliberations"] == 0

    def test_deliberation_stats_default(self):
        """Default stats are zero."""
        from backend.agents.consensus.deliberation import (
            MultiAgentDeliberation,
        )

        delib = MultiAgentDeliberation()
        assert delib.stats["consensus_reached"] == 0
        assert delib.stats["avg_rounds"] == 0.0
        assert delib.stats["avg_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_deliberation_with_mock_ask(self):
        """Deliberation with mocked ask function."""
        from backend.agents.consensus.deliberation import (
            MultiAgentDeliberation,
        )

        async def mock_ask(agent: str, prompt: str) -> str:
            return (
                "POSITION: Use RSI with period 14\n"
                "CONFIDENCE: 0.8\n"
                "EVIDENCE:\n- RSI is effective for mean reversion\n"
                "REASONING: RSI captures oversold/overbought conditions"
            )

        delib = MultiAgentDeliberation(
            ask_fn=mock_ask,
            enable_parallel_calls=False,
        )
        result = await delib.deliberate(
            question="Which indicator for BTC entry?",
            agents=["deepseek", "qwen"],
            max_rounds=1,
            min_confidence=0.5,
        )
        assert result is not None
        assert result.decision is not None

    def test_voting_strategy_enum(self):
        """VotingStrategy enum has expected values."""
        from backend.agents.consensus.deliberation import VotingStrategy

        assert VotingStrategy.WEIGHTED.value == "weighted"
        assert VotingStrategy.MAJORITY.value == "majority"

    def test_deliberation_history_empty(self):
        """Fresh deliberation has empty history."""
        from backend.agents.consensus.deliberation import (
            MultiAgentDeliberation,
        )

        delib = MultiAgentDeliberation()
        assert delib.deliberation_history == []


# =============================================================================
# TestStrategyEvolutionCoverage
# =============================================================================


class TestStrategyEvolutionCoverage:
    """Cover untested branches in StrategyEvolution."""

    def test_evolution_engine_creation(self):
        """StrategyEvolution instantiation."""
        from backend.agents.self_improvement.strategy_evolution import (
            StrategyEvolution,
        )

        engine = StrategyEvolution()
        assert engine is not None

    def test_evolution_has_components(self):
        """StrategyEvolution has required components."""
        from backend.agents.self_improvement.strategy_evolution import (
            StrategyEvolution,
        )

        engine = StrategyEvolution()
        assert engine.context_builder is not None
        assert engine.parser is not None
        assert engine.bridge is not None
        assert engine.rlhf is not None
        assert engine.reflection is not None

    def test_evolution_llm_client_lazy(self):
        """LLM client is lazily initialized."""
        from backend.agents.self_improvement.strategy_evolution import (
            StrategyEvolution,
        )

        engine = StrategyEvolution()
        assert engine._llm_client is None


# =============================================================================
# TestAgentTrackerCoverage
# =============================================================================


class TestAgentTrackerCoverage:
    """Cover untested branches in AgentTracker."""

    def test_tracker_creation(self):
        """AgentPerformanceTracker instantiation."""
        from backend.agents.self_improvement.agent_tracker import (
            AgentPerformanceTracker,
        )

        tracker = AgentPerformanceTracker(window_size=50)
        assert tracker.window_size == 50

    def test_tracker_record_result(self):
        """AgentPerformanceTracker records results."""
        from backend.agents.self_improvement.agent_tracker import (
            AgentPerformanceTracker,
        )

        tracker = AgentPerformanceTracker()
        record = tracker.record_result(
            agent_name="deepseek",
            metrics={
                "sharpe_ratio": 1.5,
                "win_rate": 0.6,
                "max_drawdown_pct": 10,
                "profit_factor": 2.0,
                "total_trades": 50,
            },
            strategy_type="rsi",
            passed=True,
            fitness_score=75.0,
        )
        assert record.agent_name == "deepseek"
        assert record.fitness_score == 75.0

    def test_tracker_get_profile_unknown(self):
        """get_profile for unknown agent returns empty profile."""
        from backend.agents.self_improvement.agent_tracker import (
            AgentPerformanceTracker,
        )

        tracker = AgentPerformanceTracker()
        profile = tracker.get_profile("nonexistent_agent")
        assert profile.agent_name == "nonexistent_agent"
        assert profile.total_strategies == 0

    def test_tracker_get_profile_after_records(self):
        """get_profile after recording results has data."""
        from backend.agents.self_improvement.agent_tracker import (
            AgentPerformanceTracker,
        )

        tracker = AgentPerformanceTracker()
        for i in range(5):
            tracker.record_result(
                agent_name="deepseek",
                metrics={"sharpe_ratio": 1.0 + i * 0.2, "win_rate": 0.5 + i * 0.05},
                strategy_type="rsi",
                passed=i % 2 == 0,
                fitness_score=60 + i * 5,
            )
        profile = tracker.get_profile("deepseek")
        assert profile.total_strategies == 5

    def test_tracker_leaderboard(self):
        """get_leaderboard returns sorted agents."""
        from backend.agents.self_improvement.agent_tracker import (
            AgentPerformanceTracker,
        )

        tracker = AgentPerformanceTracker()
        for agent in ["deepseek", "qwen", "perplexity"]:
            tracker.record_result(
                agent_name=agent,
                metrics={"sharpe_ratio": 1.5, "win_rate": 0.6},
                passed=True,
                fitness_score=70.0,
            )
        leaderboard = tracker.get_leaderboard()
        assert isinstance(leaderboard, list)
        assert len(leaderboard) == 3

    def test_tracker_get_stats(self):
        """get_stats returns summary statistics."""
        from backend.agents.self_improvement.agent_tracker import (
            AgentPerformanceTracker,
        )

        tracker = AgentPerformanceTracker()
        tracker.record_result(
            agent_name="deepseek",
            metrics={"sharpe_ratio": 1.5},
            passed=True,
            fitness_score=70.0,
        )
        stats = tracker.get_stats()
        assert isinstance(stats, dict)
        assert "total_records" in stats


# =============================================================================
# TestPipelineResultModel
# =============================================================================


class TestPipelineResultModel:
    """Tests for PipelineResult and StageResult models."""

    def test_pipeline_result_defaults(self):
        """PipelineResult has correct defaults."""
        from backend.agents.strategy_controller import PipelineResult, PipelineStage

        result = PipelineResult()
        assert not result.success
        assert result.final_stage == PipelineStage.FAILED
        assert result.proposals == []

    def test_pipeline_result_success(self, mock_strategy):
        """PipelineResult success when stage is COMPLETE."""
        from backend.agents.strategy_controller import PipelineResult, PipelineStage

        result = PipelineResult(
            strategy=mock_strategy,
            final_stage=PipelineStage.COMPLETE,
        )
        assert result.success

    def test_stage_result_creation(self):
        """StageResult creation with all fields."""
        from backend.agents.strategy_controller import PipelineStage, StageResult

        stage = StageResult(
            stage=PipelineStage.CONTEXT,
            success=True,
            duration_ms=150.5,
        )
        assert stage.success
        assert stage.error is None

    def test_pipeline_result_to_dict(self, mock_strategy):
        """PipelineResult.to_dict() serialization."""
        from backend.agents.strategy_controller import (
            PipelineResult,
            PipelineStage,
            StageResult,
        )

        result = PipelineResult(
            strategy=mock_strategy,
            final_stage=PipelineStage.COMPLETE,
            stages=[
                StageResult(stage=PipelineStage.CONTEXT, success=True, duration_ms=100),
                StageResult(stage=PipelineStage.GENERATION, success=True, duration_ms=2000),
            ],
        )
        d = result.to_dict()
        assert d["success"] is True
        assert len(d["stages"]) == 2
        assert "timestamp" in d
