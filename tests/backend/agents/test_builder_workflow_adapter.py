"""
CP7 — Phase 7: builder_workflow.py → тонкий адаптер

Tests:
  1.  run_via_unified_pipeline() calls run_strategy_pipeline()
  2.  existing_strategy_id → _load_strategy_graph_from_db() called
  3.  no existing_strategy_id → seed_graph=None passed to pipeline
  4.  result.backtest_results populated from opt_result best_sharpe
  5.  result.iterations populated from state.opt_iterations
  6.  result.deliberation populated from state.debate_outcome
  7.  result.errors populated when state has errors
  8.  result.status = COMPLETED when no errors
  9.  result.status = FAILED when state has errors
  10. on_stage_change fired when pipeline emits node events
  11. on_agent_log fired when pipeline event has llm_response
  12. to_dict() returns all expected API keys
  13. pipeline exception → result.status = FAILED, result.errors non-empty
  14. result.used_optimizer_mode = True always
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.workflows.builder_workflow import (
    BuilderStage,
    BuilderWorkflow,
    BuilderWorkflowConfig,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _make_config(existing_id: str | None = None) -> BuilderWorkflowConfig:
    return BuilderWorkflowConfig(
        symbol="BTCUSDT",
        timeframe="15",
        existing_strategy_id=existing_id,
        blocks=[{"type": "rsi", "params": {"period": 14}}],
        connections=[],
    )


def _make_mock_state(
    sharpe: float = 1.5,
    best_params: dict | None = None,
    opt_iterations: list | None = None,
    debate_outcome: dict | None = None,
    errors: list | None = None,
) -> MagicMock:
    """Build a mock AgentState with the fields _state_to_result reads."""
    state = MagicMock()
    state.session_id = "test-session-001"
    state.errors = errors or []
    state.opt_iterations = opt_iterations or []
    state.debate_outcome = debate_outcome
    state.get_result = MagicMock(
        side_effect=lambda key: {
            "optimize_strategy": {
                "best_sharpe": sharpe,
                "best_drawdown": 10.0,
                "best_trades": 40,
                "best_params": best_params or {"rsi_period": 14},
            },
            "backtest": {
                "sharpe_ratio": sharpe,
                "max_drawdown": 10.0,
                "total_trades": 40,
                "win_rate": 0.55,
            },
            "build_graph": {"blocks": [], "connections": []},
        }.get(key)
    )
    return state


# ---------------------------------------------------------------------------
# Patch helpers
# ---------------------------------------------------------------------------


class _PipelineCtx:
    """Patches run_strategy_pipeline + _load_strategy_graph_from_db + _load_df."""

    def __init__(self, mock_state):
        self._mock_state = mock_state
        self._patches = []
        self.run_mock = None
        self.load_mock = None

    def __enter__(self):
        import pandas as pd

        p1 = patch(
            "backend.agents.trading_strategy_graph.run_strategy_pipeline",
            new=AsyncMock(return_value=self._mock_state),
        )
        p2 = patch(
            "backend.agents.trading_strategy_graph._load_strategy_graph_from_db",
            new=AsyncMock(return_value={"blocks": [], "connections": []}),
        )
        # Patch _load_df on the class so no real DB is touched
        p3 = patch.object(
            BuilderWorkflow,
            "_load_df",
            new=AsyncMock(return_value=pd.DataFrame()),
        )
        self._patches = [p1, p2, p3]
        self.run_mock = p1.__enter__()
        self.load_mock = p2.__enter__()
        p3.__enter__()
        return self

    def __exit__(self, *a):
        for p in reversed(self._patches):
            try:
                p.__exit__(*a)
            except Exception:
                pass


async def _run_adapter(config, on_stage=None, on_log=None):
    """Run run_via_unified_pipeline with the given config and mock state."""
    state = _make_mock_state()
    with _PipelineCtx(state) as ctx:
        wf = BuilderWorkflow(on_stage_change=on_stage, on_agent_log=on_log)
        result = await wf.run_via_unified_pipeline(config)
        return result, ctx


# ---------------------------------------------------------------------------
# 1. Delegates to run_strategy_pipeline
# ---------------------------------------------------------------------------


class TestDelegatesToPipeline:
    def test_run_strategy_pipeline_is_called(self):
        config = _make_config()
        state = _make_mock_state()

        async def _inner():
            with _PipelineCtx(state) as ctx:
                wf = BuilderWorkflow()
                await wf.run_via_unified_pipeline(config)
                ctx.run_mock.assert_called_once()

        _run(_inner())

    def test_correct_symbol_and_timeframe_passed(self):
        config = _make_config()
        state = _make_mock_state()

        async def _inner():
            with _PipelineCtx(state) as ctx:
                wf = BuilderWorkflow()
                await wf.run_via_unified_pipeline(config)
                call_kwargs = ctx.run_mock.call_args[1]
                assert call_kwargs.get("symbol") == "BTCUSDT"
                assert call_kwargs.get("timeframe") == "15"

        _run(_inner())


# ---------------------------------------------------------------------------
# 2-3. Seed graph loading
# ---------------------------------------------------------------------------


class TestSeedGraphLoading:
    def test_load_strategy_graph_called_when_existing_id(self):
        config = _make_config(existing_id="strat-abc-123")
        state = _make_mock_state()

        async def _inner():
            with _PipelineCtx(state) as ctx:
                wf = BuilderWorkflow()
                await wf.run_via_unified_pipeline(config)
                ctx.load_mock.assert_called_once_with("strat-abc-123")

        _run(_inner())

    def test_seed_graph_none_when_no_existing_id(self):
        config = _make_config(existing_id=None)
        state = _make_mock_state()

        async def _inner():
            with _PipelineCtx(state) as ctx:
                wf = BuilderWorkflow()
                await wf.run_via_unified_pipeline(config)
                call_kwargs = ctx.run_mock.call_args[1]
                assert call_kwargs.get("seed_graph") is None

        _run(_inner())


# ---------------------------------------------------------------------------
# 4-6. Result conversion
# ---------------------------------------------------------------------------


class TestResultConversion:
    def test_backtest_results_from_opt_sharpe(self):
        config = _make_config()
        state = _make_mock_state(sharpe=2.1, best_params={"rsi_period": 16})

        result = BuilderWorkflow._state_to_result(state, config, "2026-01-01T00:00:00", "2026-01-01T00:05:00", 300.0)
        assert result.backtest_results["sharpe_ratio"] == 2.1
        assert result.backtest_results["best_params"]["rsi_period"] == 16

    def test_iterations_from_opt_iterations(self):
        opt_iters = [
            {"iteration": 1, "best_sharpe": 1.0, "best_params": {"rsi_period": 14}},
            {"iteration": 2, "best_sharpe": 1.5, "best_params": {"rsi_period": 16}},
        ]
        config = _make_config()
        state = _make_mock_state(opt_iterations=opt_iters)

        result = BuilderWorkflow._state_to_result(state, config, "2026-01-01T00:00:00", "2026-01-01T00:05:00", 300.0)
        assert len(result.iterations) == 2
        assert result.iterations[0]["sharpe"] == 1.0
        assert result.iterations[1]["sharpe"] == 1.5

    def test_deliberation_from_debate_outcome(self):
        debate = {"decision": "conditional", "risk_score": 6, "rationale": "Looks OK but risky."}
        config = _make_config()
        state = _make_mock_state(debate_outcome=debate)

        result = BuilderWorkflow._state_to_result(state, config, "2026-01-01T00:00:00", "2026-01-01T00:05:00", 300.0)
        assert result.deliberation["decision"] == "conditional"
        assert result.deliberation["risk_score"] == 6
        assert "risky" in result.deliberation["rationale"]

    def test_no_deliberation_when_debate_outcome_none(self):
        config = _make_config()
        state = _make_mock_state(debate_outcome=None)

        result = BuilderWorkflow._state_to_result(state, config, "2026-01-01T00:00:00", "2026-01-01T00:05:00", 300.0)
        assert result.deliberation == {}


# ---------------------------------------------------------------------------
# 7-9. Status and errors
# ---------------------------------------------------------------------------


class TestStatusAndErrors:
    def test_errors_populated_from_state(self):
        config = _make_config()
        state = _make_mock_state(errors=[{"error": "DB timeout", "node": "backtest"}])

        result = BuilderWorkflow._state_to_result(state, config, "2026-01-01T00:00:00", "2026-01-01T00:05:00", 300.0)
        assert "DB timeout" in result.errors

    def test_status_completed_when_no_errors(self):
        config = _make_config()
        state = _make_mock_state(errors=[])

        result = BuilderWorkflow._state_to_result(state, config, "2026-01-01T00:00:00", "2026-01-01T00:05:00", 300.0)
        assert result.status == BuilderStage.COMPLETED

    def test_status_failed_when_state_has_errors(self):
        config = _make_config()
        state = _make_mock_state(errors=[{"error": "crash", "node": "backtest"}])

        result = BuilderWorkflow._state_to_result(state, config, "2026-01-01T00:00:00", "2026-01-01T00:05:00", 300.0)
        assert result.status == BuilderStage.FAILED


# ---------------------------------------------------------------------------
# 10-11. SSE event forwarding
# ---------------------------------------------------------------------------


class TestSSEEventForwarding:
    def test_on_stage_change_fired_for_node_events(self):
        stages_seen = []
        config = _make_config()
        state = _make_mock_state()

        async def _inner():
            with _PipelineCtx(state) as ctx:
                wf = BuilderWorkflow(on_stage_change=stages_seen.append)
                # Manually test _forward_event
                wf._forward_event("analyze_market", {})
                wf._forward_event("optimize_strategy", {})
                wf._forward_event("report", {})

        _run(_inner())
        assert BuilderStage.PLANNING in stages_seen
        assert BuilderStage.EVALUATING in stages_seen
        assert BuilderStage.COMPLETED in stages_seen

    def test_on_agent_log_fired_when_llm_response_present(self):
        logs = []
        wf = BuilderWorkflow(on_agent_log=logs.append)
        wf._forward_event(
            "generate_strategies",
            {"agent": "claude", "prompt": "Generate RSI", "llm_response": "Here is RSI strategy"},
        )
        assert len(logs) == 1
        assert logs[0]["agent"] == "claude"

    def test_no_agent_log_when_no_llm_response(self):
        logs = []
        wf = BuilderWorkflow(on_agent_log=logs.append)
        wf._forward_event("analyze_market", {"some_other_key": "value"})
        assert len(logs) == 0


# ---------------------------------------------------------------------------
# 12. API format
# ---------------------------------------------------------------------------


class TestAPIFormat:
    def test_to_dict_has_expected_keys(self):
        config = _make_config()
        state = _make_mock_state()

        result = BuilderWorkflow._state_to_result(state, config, "2026-01-01T00:00:00", "2026-01-01T00:05:00", 300.0)
        d = result.to_dict()
        for key in (
            "workflow_id",
            "strategy_id",
            "status",
            "blocks_added",
            "connections_made",
            "backtest_results",
            "iterations",
            "deliberation",
            "errors",
            "duration_seconds",
            "used_optimizer_mode",
        ):
            assert key in d, f"Missing API key: {key}"

    def test_used_optimizer_mode_always_true(self):
        config = _make_config()
        state = _make_mock_state()

        result = BuilderWorkflow._state_to_result(state, config, "2026-01-01T00:00:00", "2026-01-01T00:05:00", 300.0)
        assert result.used_optimizer_mode is True


# ---------------------------------------------------------------------------
# 13. Pipeline exception handling
# ---------------------------------------------------------------------------


class TestPipelineExceptionHandling:
    def test_pipeline_exception_status_failed(self):
        config = _make_config()

        async def _inner():
            import pandas as pd

            with (
                patch(
                    "backend.agents.trading_strategy_graph.run_strategy_pipeline",
                    new=AsyncMock(side_effect=RuntimeError("Pipeline exploded")),
                ),
                patch(
                    "backend.agents.trading_strategy_graph._load_strategy_graph_from_db",
                    new=AsyncMock(return_value=None),
                ),
                patch.object(BuilderWorkflow, "_load_df", new=AsyncMock(return_value=pd.DataFrame())),
            ):
                wf = BuilderWorkflow()
                result = await wf.run_via_unified_pipeline(config)
                assert result.status == BuilderStage.FAILED
                assert len(result.errors) > 0

        _run(_inner())

    def test_pipeline_exception_errors_contain_message(self):
        config = _make_config()

        async def _inner():
            import pandas as pd

            with (
                patch(
                    "backend.agents.trading_strategy_graph.run_strategy_pipeline",
                    new=AsyncMock(side_effect=RuntimeError("API key missing")),
                ),
                patch(
                    "backend.agents.trading_strategy_graph._load_strategy_graph_from_db",
                    new=AsyncMock(return_value=None),
                ),
                patch.object(BuilderWorkflow, "_load_df", new=AsyncMock(return_value=pd.DataFrame())),
            ):
                wf = BuilderWorkflow()
                result = await wf.run_via_unified_pipeline(config)
                assert any("API key missing" in e for e in result.errors)

        _run(_inner())
