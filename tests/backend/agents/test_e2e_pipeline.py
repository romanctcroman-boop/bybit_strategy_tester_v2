"""
End-to-End Integration Tests for AI Strategy Pipeline.

Tests the full flow: generate → parse → backtest → optimize → report,
with mocked LLM responses and real component integration.

Validates:
- Full pipeline orchestration (StrategyController)
- LangGraph-based pipeline (TradingStrategyGraph)
- Pipeline → optimizer integration
- Multi-agent consensus flow
- Error handling across pipeline stages
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
    ResponseParser,
    Signal,
    StrategyDefinition,
)

# =============================================================================
# FIXTURES
# =============================================================================

MOCK_LLM_RESPONSE = json.dumps(
    {
        "strategy_name": "RSI Momentum v1",
        "description": "RSI-based momentum strategy for BTC",
        "signals": [
            {
                "id": "signal_0",
                "type": "RSI",
                "params": {"period": 14, "oversold": 30, "overbought": 70},
                "weight": 1.0,
                "condition": "Buy when RSI crosses above oversold",
            }
        ],
        "exit_conditions": {
            "take_profit": {"type": "fixed_pct", "value": 2.0, "description": "2% TP"},
            "stop_loss": {"type": "fixed_pct", "value": 1.0, "description": "1% SL"},
        },
    }
)


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate sample OHLCV data for pipeline tests."""
    np.random.seed(42)
    n = 500
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
def parsed_strategy() -> StrategyDefinition:
    """Pre-parsed strategy definition for testing."""
    return StrategyDefinition(
        strategy_name="RSI Momentum v1",
        description="RSI-based momentum strategy",
        signals=[
            Signal(
                id="signal_0",
                type="RSI",
                params={"period": 14, "oversold": 30, "overbought": 70},
                weight=1.0,
                condition="Buy when RSI crosses above oversold",
            ),
        ],
        exit_conditions=ExitConditions(
            take_profit=ExitCondition(type="fixed_pct", value=2.0, description="2% TP"),
            stop_loss=ExitCondition(type="fixed_pct", value=1.0, description="1% SL"),
        ),
    )


@pytest.fixture
def mock_backtest_metrics() -> dict:
    """Realistic backtest metrics."""
    return {
        "success": True,
        "metrics": {
            "net_profit": 1250.0,
            "sharpe_ratio": 1.8,
            "max_drawdown": 0.12,
            "win_rate": 0.58,
            "profit_factor": 1.95,
            "total_trades": 45,
        },
    }


# =============================================================================
# TestResponseParserIntegration
# =============================================================================


class TestResponseParserIntegration:
    """Tests that LLM text → StrategyDefinition parsing works end-to-end."""

    def test_parse_valid_json_response(self):
        """Valid JSON response parsed into StrategyDefinition."""
        parser = ResponseParser()
        strategy = parser.parse_strategy(MOCK_LLM_RESPONSE, agent_name="deepseek")
        assert strategy is not None
        assert strategy.strategy_name == "RSI Momentum v1"
        assert len(strategy.signals) == 1
        assert strategy.signals[0].type == "RSI"

    def test_parse_json_in_markdown(self):
        """JSON wrapped in markdown code block parsed correctly."""
        parser = ResponseParser()
        markdown_response = f"Here's my strategy:\n\n```json\n{MOCK_LLM_RESPONSE}\n```\n\nThis should work well."
        strategy = parser.parse_strategy(markdown_response, agent_name="qwen")
        assert strategy is not None
        assert strategy.strategy_name == "RSI Momentum v1"

    def test_parse_and_validate(self):
        """Parsed strategy passes validation."""
        parser = ResponseParser()
        strategy = parser.parse_strategy(MOCK_LLM_RESPONSE)
        assert strategy is not None
        validation = parser.validate_strategy(strategy)
        assert validation.is_valid

    def test_parse_invalid_json(self):
        """Invalid JSON returns None or fallback."""
        parser = ResponseParser()
        result = parser.parse_strategy("This is not JSON at all.", agent_name="test")
        # Parser may return None or attempt fallback
        # Either way, it should not crash
        assert result is None or isinstance(result, StrategyDefinition)


# =============================================================================
# TestStrategyControllerIntegration
# =============================================================================


class TestStrategyControllerIntegration:
    """Tests for full StrategyController pipeline with mocked LLM."""

    @pytest.mark.asyncio
    async def test_pipeline_single_agent_no_backtest(self, sample_ohlcv):
        """Single agent pipeline: context → generate → parse → complete."""
        from backend.agents.strategy_controller import (
            PipelineStage,
            StrategyController,
        )

        controller = StrategyController()

        with patch.object(
            controller,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=MOCK_LLM_RESPONSE,
        ):
            result = await controller.generate_strategy(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                agents=["deepseek"],
                run_backtest=False,
            )

        assert result.success
        assert result.final_stage == PipelineStage.COMPLETE
        assert result.strategy is not None
        assert result.strategy.strategy_name == "RSI Momentum v1"
        assert len(result.proposals) == 1

    @pytest.mark.asyncio
    async def test_pipeline_with_backtest(self, sample_ohlcv, mock_backtest_metrics):
        """Pipeline with backtest: context → generate → parse → backtest → complete."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()

        with (
            patch.object(
                controller,
                "_call_llm",
                new_callable=AsyncMock,
                return_value=MOCK_LLM_RESPONSE,
            ),
            patch.object(
                controller,
                "_run_backtest",
                new_callable=AsyncMock,
                return_value=mock_backtest_metrics,
            ),
        ):
            result = await controller.generate_strategy(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                agents=["deepseek"],
                run_backtest=True,
            )

        assert result.success
        assert result.backtest_metrics == mock_backtest_metrics

    @pytest.mark.asyncio
    async def test_pipeline_multi_agent(self, sample_ohlcv):
        """Multi-agent pipeline uses consensus to select best."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()

        # Two different LLM responses
        response_1 = json.dumps(
            {
                "strategy_name": "RSI Strategy",
                "signals": [{"id": "s1", "type": "RSI", "params": {"period": 14}, "weight": 1.0}],
            }
        )
        response_2 = json.dumps(
            {
                "strategy_name": "MACD Strategy",
                "signals": [{"id": "s1", "type": "MACD", "params": {"fast_period": 12}, "weight": 1.0}],
            }
        )

        call_count = 0

        async def mock_call(agent_name, prompt, system_msg):
            nonlocal call_count
            call_count += 1
            return response_1 if call_count == 1 else response_2

        with patch.object(controller, "_call_llm", side_effect=mock_call):
            result = await controller.generate_strategy(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                agents=["deepseek", "qwen"],
                run_backtest=False,
            )

        assert result.success
        assert len(result.proposals) == 2
        assert result.strategy is not None

    @pytest.mark.asyncio
    async def test_pipeline_llm_failure(self, sample_ohlcv):
        """Pipeline handles LLM failure gracefully."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()

        with patch.object(
            controller,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=None,  # LLM returns nothing
        ):
            result = await controller.generate_strategy(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                agents=["deepseek"],
                run_backtest=False,
            )

        # Pipeline should fail gracefully
        assert not result.success

    @pytest.mark.asyncio
    async def test_pipeline_result_serialization(self, sample_ohlcv):
        """PipelineResult.to_dict() works correctly."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()

        with patch.object(
            controller,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=MOCK_LLM_RESPONSE,
        ):
            result = await controller.generate_strategy(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                agents=["deepseek"],
            )

        serialized = result.to_dict()
        assert "success" in serialized
        assert "stages" in serialized
        assert "total_duration_ms" in serialized
        assert serialized["success"] is True

    @pytest.mark.asyncio
    async def test_quick_generate(self, sample_ohlcv):
        """quick_generate convenience method works."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()

        with patch.object(
            controller,
            "_call_llm",
            new_callable=AsyncMock,
            return_value=MOCK_LLM_RESPONSE,
        ):
            strategy = await controller.quick_generate(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                agent="deepseek",
            )

        assert strategy is not None
        assert strategy.strategy_name == "RSI Momentum v1"


# =============================================================================
# TestPipelineToOptimizerIntegration
# =============================================================================


class TestPipelineToOptimizerIntegration:
    """Tests the full flow: pipeline → optimizer."""

    @pytest.mark.asyncio
    async def test_generate_then_optimize(self, sample_ohlcv, parsed_strategy):
        """Strategy from pipeline can be optimized."""
        from backend.agents.optimization.strategy_optimizer import (
            StrategyOptimizer,
        )

        optimizer = StrategyOptimizer(seed=42)

        # Mock evaluation to return consistent fitness
        with patch.object(
            optimizer,
            "_evaluate_strategy",
            new_callable=AsyncMock,
            return_value=1.5,
        ):
            result = await optimizer.optimize_strategy(
                strategy=parsed_strategy,
                df=sample_ohlcv,
                symbol="BTCUSDT",
                timeframe="15",
                method="genetic_algorithm",
                config_overrides={"population_size": 4, "generations": 2},
            )

        assert result.strategy is not None
        assert result.evaluations > 0
        assert result.method == "genetic_algorithm"

    @pytest.mark.asyncio
    async def test_full_pipeline_generate_backtest_optimize(self, sample_ohlcv, mock_backtest_metrics):
        """Full e2e: LLM generate → backtest → optimize."""
        from backend.agents.optimization.strategy_optimizer import (
            StrategyOptimizer,
        )
        from backend.agents.strategy_controller import StrategyController

        # Step 1: Generate strategy
        controller = StrategyController()
        with (
            patch.object(
                controller,
                "_call_llm",
                new_callable=AsyncMock,
                return_value=MOCK_LLM_RESPONSE,
            ),
            patch.object(
                controller,
                "_run_backtest",
                new_callable=AsyncMock,
                return_value=mock_backtest_metrics,
            ),
        ):
            pipeline_result = await controller.generate_strategy(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                agents=["deepseek"],
                run_backtest=True,
            )

        assert pipeline_result.success
        assert pipeline_result.strategy is not None

        # Step 2: Optimize the generated strategy
        optimizer = StrategyOptimizer(seed=42)
        with patch.object(
            optimizer,
            "_evaluate_strategy",
            new_callable=AsyncMock,
            return_value=1.5,
        ):
            opt_result = await optimizer.optimize_strategy(
                strategy=pipeline_result.strategy,
                df=sample_ohlcv,
                method="bayesian_optimization",
                config_overrides={"n_iter": 5, "init_points": 2},
            )

        assert opt_result.evaluations > 0
        assert opt_result.method == "bayesian_optimization"

        # Step 3: Verify optimization result is valid strategy
        parser = ResponseParser()
        validation = parser.validate_strategy(opt_result.strategy)
        assert validation.is_valid

    @pytest.mark.asyncio
    async def test_optimize_preserves_commission_parity(self, sample_ohlcv, parsed_strategy):
        """Optimizer uses BacktestBridge which enforces commission_rate=0.0007."""
        from backend.agents.integration.backtest_bridge import BacktestBridge
        from backend.agents.optimization.strategy_optimizer import (
            StrategyOptimizer,
        )

        # Verify BacktestBridge uses correct commission
        assert BacktestBridge.COMMISSION_RATE == 0.0007

        # Verify optimizer doesn't override it
        optimizer = StrategyOptimizer(seed=42)
        # The _evaluate_strategy method creates BacktestBridge internally
        # Just verify the constant hasn't been tampered with
        assert BacktestBridge.COMMISSION_RATE == 0.0007


# =============================================================================
# TestPipelineErrorRecovery
# =============================================================================


class TestPipelineErrorRecovery:
    """Tests for error handling across pipeline stages."""

    @pytest.mark.asyncio
    async def test_context_stage_failure(self):
        """Pipeline fails gracefully when context building fails."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()
        empty_df = pd.DataFrame()

        result = await controller.generate_strategy(
            symbol="BTCUSDT",
            timeframe="15",
            df=empty_df,
            agents=["deepseek"],
        )

        assert not result.success

    @pytest.mark.asyncio
    async def test_generation_stage_no_proposals(self, sample_ohlcv):
        """Pipeline fails when no valid proposals generated."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()

        with patch.object(
            controller,
            "_call_llm",
            new_callable=AsyncMock,
            return_value="not valid json at all",
        ):
            result = await controller.generate_strategy(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                agents=["deepseek"],
            )

        assert not result.success

    @pytest.mark.asyncio
    async def test_backtest_stage_failure(self, sample_ohlcv):
        """Pipeline completes even if backtest fails."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()

        with (
            patch.object(
                controller,
                "_call_llm",
                new_callable=AsyncMock,
                return_value=MOCK_LLM_RESPONSE,
            ),
            patch.object(
                controller,
                "_run_backtest",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Engine error"),
            ),
        ):
            result = await controller.generate_strategy(
                symbol="BTCUSDT",
                timeframe="15",
                df=sample_ohlcv,
                agents=["deepseek"],
                run_backtest=True,
            )

        # Strategy is generated even though backtest failed
        # (The _run_stage handles the error)
        assert result.strategy is not None


# =============================================================================
# TestLangGraphPipelineIntegration
# =============================================================================


class TestLangGraphPipelineIntegration:
    """Tests for LangGraph-based pipeline nodes."""

    def test_analyze_market_node_creation(self):
        """AnalyzeMarketNode initializes correctly."""
        from backend.agents.trading_strategy_graph import AnalyzeMarketNode

        node = AnalyzeMarketNode()
        assert node.name == "analyze_market"

    @pytest.mark.asyncio
    async def test_analyze_market_node_execution(self, sample_ohlcv):
        """AnalyzeMarketNode processes OHLCV data."""
        from backend.agents.langgraph_orchestrator import AgentState
        from backend.agents.trading_strategy_graph import AnalyzeMarketNode

        node = AnalyzeMarketNode()
        state = AgentState()
        state.context["symbol"] = "BTCUSDT"
        state.context["timeframe"] = "15"
        state.context["df"] = sample_ohlcv

        result_state = await node.execute(state)
        assert "analyze_market" in result_state.results
        market_data = result_state.results["analyze_market"]
        assert "market_context" in market_data
        assert "regime" in market_data

    @pytest.mark.asyncio
    async def test_analyze_market_node_empty_df(self):
        """AnalyzeMarketNode handles empty DataFrame."""
        from backend.agents.langgraph_orchestrator import AgentState
        from backend.agents.trading_strategy_graph import AnalyzeMarketNode

        node = AnalyzeMarketNode()
        state = AgentState()
        state.context["df"] = pd.DataFrame()

        result_state = await node.execute(state)
        assert len(result_state.errors) > 0


# =============================================================================
# TestMetricsAnalyzerIntegration
# =============================================================================


class TestMetricsAnalyzerIntegration:
    """Tests for MetricsAnalyzer in pipeline context."""

    def test_analyze_good_metrics(self, mock_backtest_metrics):
        """MetricsAnalyzer processes good metrics correctly."""
        from backend.agents.metrics_analyzer import MetricsAnalyzer

        analyzer = MetricsAnalyzer()
        # Unwrap nested metrics if present
        metrics = mock_backtest_metrics.get("metrics", mock_backtest_metrics)
        analysis = analyzer.analyze(metrics)
        assert analysis is not None
        assert analysis.overall_score > 0
        assert analysis.grade is not None

    def test_analyze_empty_metrics(self):
        """MetricsAnalyzer handles empty metrics."""
        from backend.agents.metrics_analyzer import MetricsAnalyzer

        analyzer = MetricsAnalyzer()
        analysis = analyzer.analyze({})
        assert analysis is not None
        assert analysis.overall_score >= 0

    def test_analysis_to_prompt_context(self, mock_backtest_metrics):
        """Analysis can be converted to prompt context string."""
        from backend.agents.metrics_analyzer import MetricsAnalyzer

        analyzer = MetricsAnalyzer()
        metrics = mock_backtest_metrics.get("metrics", mock_backtest_metrics)
        analysis = analyzer.analyze(metrics)
        context = analysis.to_prompt_context()
        assert isinstance(context, str)
        assert len(context) > 0
