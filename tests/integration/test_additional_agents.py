"""
Tests for Additional Agent Modules (Phase 2).

Tests cover:
1. AutonomousBacktestingWorkflow — pipeline stages and error handling
2. PatternExtractor — analysis, insights, data models
3. TaskScheduler — interval/daily/one-shot tasks, lifecycle
4. AgentPaperTrader — session management, trade execution
5. Dashboard API endpoints — workflow, patterns, paper trading, logs

pytest markers:
    @pytest.mark.slow — tests that require DB or network (deselected by default)

Run:
    pytest tests/integration/test_additional_agents.py -v
    pytest tests/integration/test_additional_agents.py -v -m "not slow"
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

# =============================================================================
# 1. AUTONOMOUS WORKFLOW TESTS
# =============================================================================


class TestAutonomousWorkflow:
    """Tests for AutonomousBacktestingWorkflow pipeline."""

    def test_import(self):
        """Workflow module imports without error."""
        from backend.agents.workflows import autonomous_backtesting as mod

        assert hasattr(mod, "AutonomousBacktestingWorkflow")
        assert hasattr(mod, "PipelineStage")
        assert hasattr(mod, "WorkflowConfig")
        assert hasattr(mod, "WorkflowResult")
        assert hasattr(mod, "WorkflowStatus")
        assert mod.PipelineStage.COMPLETED.value == "completed"

    def test_workflow_config_defaults(self):
        """WorkflowConfig has sensible defaults."""
        from backend.agents.workflows.autonomous_backtesting import WorkflowConfig

        config = WorkflowConfig()
        assert config.symbol == "BTCUSDT"
        assert config.interval == "15"
        assert config.initial_capital == 10000.0
        assert config.evolution_enabled is True
        assert config.max_generations == 3
        assert config.save_to_memory is True
        assert config.fallback_strategy_type == "rsi"

    def test_workflow_config_to_dict(self):
        """WorkflowConfig serializes correctly."""
        from backend.agents.workflows.autonomous_backtesting import WorkflowConfig

        config = WorkflowConfig(symbol="ETHUSDT", interval="60")
        d = config.to_dict()
        assert d["symbol"] == "ETHUSDT"
        assert d["interval"] == "60"
        assert "evolution_enabled" in d

    def test_workflow_status_to_dict(self):
        """WorkflowStatus serializes with all fields."""
        from backend.agents.workflows.autonomous_backtesting import (
            PipelineStage,
            WorkflowStatus,
        )

        status = WorkflowStatus(workflow_id="test-123")
        status.stage = PipelineStage.BACKTESTING
        status.progress_pct = 55.5
        d = status.to_dict()
        assert d["workflow_id"] == "test-123"
        assert d["stage"] == "backtesting"
        assert d["progress_pct"] == 55.5

    def test_workflow_result_success_property(self):
        """WorkflowResult.success reflects pipeline completion."""
        from backend.agents.workflows.autonomous_backtesting import (
            PipelineStage,
            WorkflowConfig,
            WorkflowResult,
            WorkflowStatus,
        )

        status = WorkflowStatus(workflow_id="x")
        status.stage = PipelineStage.COMPLETED
        result = WorkflowResult(workflow_id="x", config=WorkflowConfig(), status=status)
        assert result.success is True

        status.stage = PipelineStage.FAILED
        assert result.success is False

    def test_pipeline_stage_enum_values(self):
        """All pipeline stages are defined."""
        from backend.agents.workflows.autonomous_backtesting import PipelineStage

        stages = [s.value for s in PipelineStage]
        assert "idle" in stages
        assert "fetching" in stages
        assert "evolving" in stages
        assert "backtesting" in stages
        assert "reporting" in stages
        assert "learning" in stages
        assert "completed" in stages
        assert "failed" in stages

    @pytest.mark.asyncio
    async def test_workflow_run_with_mocked_steps(self):
        """Full pipeline runs with all steps mocked."""
        from backend.agents.workflows.autonomous_backtesting import (
            AutonomousBacktestingWorkflow,
            WorkflowConfig,
        )

        workflow = AutonomousBacktestingWorkflow()
        config = WorkflowConfig(evolution_enabled=False)

        # Mock all steps
        with (
            patch.object(workflow, "_step_fetch", new_callable=AsyncMock, return_value=100) as m_fetch,
            patch.object(workflow, "_step_evolve", new_callable=AsyncMock, return_value=("rsi", {"period": 14})),
            patch.object(workflow, "_step_backtest", new_callable=AsyncMock),
            patch.object(workflow, "_step_report", new_callable=AsyncMock),
            patch.object(workflow, "_step_learn", new_callable=AsyncMock),
            patch.object(workflow, "_log_action", new_callable=AsyncMock),
        ):
            result = await workflow.run(config)

        assert result.workflow_id != ""
        assert result.status.stage.value == "completed"
        assert result.total_duration_s > 0

    @pytest.mark.asyncio
    async def test_workflow_handles_backtest_error(self):
        """Pipeline marks FAILED when backtest raises."""
        from backend.agents.workflows.autonomous_backtesting import (
            AutonomousBacktestingWorkflow,
            WorkflowConfig,
        )

        workflow = AutonomousBacktestingWorkflow()
        config = WorkflowConfig(evolution_enabled=False)

        with (
            patch.object(workflow, "_step_fetch", new_callable=AsyncMock, return_value=100),
            patch.object(workflow, "_step_evolve", new_callable=AsyncMock, return_value=("rsi", {})),
            patch.object(workflow, "_step_backtest", new_callable=AsyncMock, side_effect=RuntimeError("boom")),
            patch.object(workflow, "_log_action", new_callable=AsyncMock),
        ):
            result = await workflow.run(config)

        assert result.success is False
        assert len(result.status.errors) > 0

    def test_list_active_empty(self):
        """list_active returns empty when no workflows are running."""
        from backend.agents.workflows.autonomous_backtesting import (
            AutonomousBacktestingWorkflow,
        )

        # Clear any leftover state
        AutonomousBacktestingWorkflow._active.clear()
        assert AutonomousBacktestingWorkflow.list_active() == []

    def test_get_status_missing(self):
        """get_status returns None for unknown workflow."""
        from backend.agents.workflows.autonomous_backtesting import (
            AutonomousBacktestingWorkflow,
        )

        assert AutonomousBacktestingWorkflow.get_status("nonexistent") is None


# =============================================================================
# 2. PATTERN EXTRACTOR TESTS
# =============================================================================


class TestPatternExtractor:
    """Tests for PatternExtractor module."""

    def test_import(self):
        """Module imports without errors."""
        from backend.agents.self_improvement import pattern_extractor as mod

        assert hasattr(mod, "PatternExtractor")
        assert hasattr(mod, "StrategyPattern")
        assert hasattr(mod, "ExtractionResult")
        assert hasattr(mod, "TimeframeAffinity")

    def test_strategy_pattern_to_dict(self):
        """StrategyPattern serializes correctly."""
        from backend.agents.self_improvement.pattern_extractor import StrategyPattern

        p = StrategyPattern(
            strategy_type="rsi",
            sample_count=10,
            avg_win_rate=55.5,
            avg_sharpe=1.23,
        )
        d = p.to_dict()
        assert d["strategy_type"] == "rsi"
        assert d["sample_count"] == 10
        assert d["avg_win_rate"] == 55.5

    def test_extraction_result_to_dict(self):
        """ExtractionResult serialization."""
        from backend.agents.self_improvement.pattern_extractor import ExtractionResult

        result = ExtractionResult(total_backtests_analysed=42)
        d = result.to_dict()
        assert d["total_backtests_analysed"] == 42
        assert "patterns" in d
        assert "insights" in d

    def test_analyse_strategy_static(self):
        """_analyse_strategy computes correct aggregates."""
        from backend.agents.self_improvement.pattern_extractor import PatternExtractor

        data = [
            {
                "win_rate": 60,
                "sharpe_ratio": 1.5,
                "total_return": 10,
                "max_drawdown": 5,
                "profit_factor": 2.0,
                "total_trades": 20,
                "interval": "15",
                "symbol": "BTCUSDT",
            },
            {
                "win_rate": 50,
                "sharpe_ratio": 0.8,
                "total_return": -5,
                "max_drawdown": 15,
                "profit_factor": 0.9,
                "total_trades": 30,
                "interval": "60",
                "symbol": "ETHUSDT",
            },
            {
                "win_rate": 70,
                "sharpe_ratio": 2.1,
                "total_return": 25,
                "max_drawdown": 8,
                "profit_factor": 3.0,
                "total_trades": 15,
                "interval": "15",
                "symbol": "BTCUSDT",
            },
        ]

        pattern = PatternExtractor._analyse_strategy("rsi", data)
        assert pattern.strategy_type == "rsi"
        assert pattern.sample_count == 3
        assert pattern.avg_win_rate == pytest.approx(60.0, abs=0.1)
        assert pattern.best_sharpe == pytest.approx(2.1, abs=0.01)
        assert pattern.best_return_pct == pytest.approx(25.0, abs=0.1)

    def test_generate_insights_empty(self):
        """Insights on empty data."""
        from backend.agents.self_improvement.pattern_extractor import (
            ExtractionResult,
            PatternExtractor,
        )

        result = ExtractionResult()
        insights = PatternExtractor._generate_insights(result)
        assert len(insights) >= 1
        assert "Insufficient" in insights[0]

    def test_generate_insights_with_patterns(self):
        """Insights generated for real patterns."""
        from backend.agents.self_improvement.pattern_extractor import (
            ExtractionResult,
            PatternExtractor,
            StrategyPattern,
        )

        result = ExtractionResult(
            patterns=[
                StrategyPattern(
                    strategy_type="rsi", sample_count=10, avg_sharpe=1.5, avg_win_rate=55, avg_return_pct=5
                ),
                StrategyPattern(
                    strategy_type="macd", sample_count=8, avg_sharpe=0.3, avg_win_rate=40, avg_return_pct=-3
                ),
            ]
        )
        insights = PatternExtractor._generate_insights(result)
        assert any("rsi" in i.lower() for i in insights)

    @pytest.mark.asyncio
    async def test_extract_with_empty_db(self):
        """Extract gracefully handles empty database."""
        from backend.agents.self_improvement.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(min_samples=1)

        with patch.object(extractor, "_fetch_backtest_data", new_callable=AsyncMock, return_value=[]):
            result = await extractor.extract()

        assert result.total_backtests_analysed == 0
        assert len(result.insights) >= 1

    @pytest.mark.asyncio
    async def test_extract_with_mocked_data(self):
        """Extract produces patterns from mocked data."""
        from backend.agents.self_improvement.pattern_extractor import PatternExtractor

        rows = [
            {
                "strategy_type": "rsi",
                "interval": "15",
                "symbol": "BTCUSDT",
                "win_rate": 60,
                "sharpe_ratio": 1.5,
                "total_return": 10,
                "max_drawdown": 5,
                "profit_factor": 2.0,
                "total_trades": 20,
            },
            {
                "strategy_type": "rsi",
                "interval": "15",
                "symbol": "BTCUSDT",
                "win_rate": 55,
                "sharpe_ratio": 1.2,
                "total_return": 8,
                "max_drawdown": 7,
                "profit_factor": 1.8,
                "total_trades": 25,
            },
            {
                "strategy_type": "rsi",
                "interval": "60",
                "symbol": "ETHUSDT",
                "win_rate": 65,
                "sharpe_ratio": 1.8,
                "total_return": 15,
                "max_drawdown": 4,
                "profit_factor": 2.5,
                "total_trades": 18,
            },
        ]

        extractor = PatternExtractor(min_samples=2)

        with patch.object(extractor, "_fetch_backtest_data", new_callable=AsyncMock, return_value=rows):
            result = await extractor.extract()

        assert result.total_backtests_analysed == 3
        assert len(result.patterns) >= 1
        assert result.patterns[0].strategy_type == "rsi"

    def test_timeframe_affinity_to_dict(self):
        """TimeframeAffinity serialization."""
        from backend.agents.self_improvement.pattern_extractor import TimeframeAffinity

        ta = TimeframeAffinity(timeframe="15", strategy_type="macd", avg_sharpe=1.1, sample_count=5)
        d = ta.to_dict()
        assert d["timeframe"] == "15"
        assert d["avg_sharpe"] == 1.1


# =============================================================================
# 3. TASK SCHEDULER TESTS
# =============================================================================


class TestTaskScheduler:
    """Tests for TaskScheduler module."""

    def test_import(self):
        """Scheduler module imports."""
        from backend.agents.scheduler import task_scheduler as mod

        assert hasattr(mod, "TaskScheduler")
        assert hasattr(mod, "ScheduledTask")
        assert mod.TaskType.INTERVAL.value == "interval"
        assert mod.TaskState.PENDING.value == "pending"

    def test_add_interval_task(self):
        """Register an interval task."""
        from backend.agents.scheduler.task_scheduler import TaskScheduler

        scheduler = TaskScheduler()

        async def dummy():
            pass

        scheduler.add_interval_task("test_task", dummy, interval_seconds=60)
        tasks = scheduler.list_tasks()
        assert len(tasks) == 1
        assert tasks[0]["name"] == "test_task"
        assert tasks[0]["task_type"] == "interval"
        assert tasks[0]["interval_seconds"] == 60

    def test_add_daily_task(self):
        """Register a daily task."""
        from backend.agents.scheduler.task_scheduler import TaskScheduler

        scheduler = TaskScheduler()

        async def dummy():
            pass

        scheduler.add_daily_task("nightly", dummy, hour=3, minute=30)
        tasks = scheduler.list_tasks()
        assert len(tasks) == 1
        assert tasks[0]["hour"] == 3
        assert tasks[0]["minute"] == 30

    def test_add_one_shot_task(self):
        """Register a one-shot task."""
        from backend.agents.scheduler.task_scheduler import TaskScheduler

        scheduler = TaskScheduler()

        async def dummy():
            pass

        scheduler.add_one_shot_task("once", dummy, delay_seconds=10)
        tasks = scheduler.list_tasks()
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "one_shot"
        assert tasks[0]["next_run"] is not None

    def test_remove_task(self):
        """Remove a registered task."""
        from backend.agents.scheduler.task_scheduler import TaskScheduler

        scheduler = TaskScheduler()

        async def dummy():
            pass

        scheduler.add_interval_task("removable", dummy, interval_seconds=10)
        assert len(scheduler.list_tasks()) == 1

        removed = scheduler.remove_task("removable")
        assert removed is True
        assert len(scheduler.list_tasks()) == 0

    def test_remove_nonexistent_task(self):
        """Removing a non-existent task returns False."""
        from backend.agents.scheduler.task_scheduler import TaskScheduler

        scheduler = TaskScheduler()
        assert scheduler.remove_task("ghost") is False

    def test_get_task(self):
        """Get a specific task by name."""
        from backend.agents.scheduler.task_scheduler import TaskScheduler

        scheduler = TaskScheduler()

        async def dummy():
            pass

        scheduler.add_interval_task("check", dummy, interval_seconds=30)
        task = scheduler.get_task("check")
        assert task is not None
        assert task["name"] == "check"

        assert scheduler.get_task("missing") is None

    def test_get_history_empty(self):
        """History is empty initially."""
        from backend.agents.scheduler.task_scheduler import TaskScheduler

        scheduler = TaskScheduler()
        assert scheduler.get_history() == []

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Scheduler starts and stops without errors."""
        from backend.agents.scheduler.task_scheduler import TaskScheduler

        scheduler = TaskScheduler()
        call_count = 0

        async def counter():
            nonlocal call_count
            call_count += 1

        scheduler.add_interval_task("fast", counter, interval_seconds=0.1)
        await scheduler.start()
        assert scheduler.is_running is True

        await asyncio.sleep(0.35)
        await scheduler.stop()
        assert scheduler.is_running is False
        assert call_count >= 2  # should have run 2-3 times in 0.35s

    @pytest.mark.asyncio
    async def test_task_retry_on_failure(self):
        """Failed task is retried with backoff."""
        from backend.agents.scheduler.task_scheduler import TaskScheduler

        scheduler = TaskScheduler()
        attempt = 0

        async def failing():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ValueError("fail")

        scheduler.add_interval_task("retryable", failing, interval_seconds=0.1, max_retries=2)
        await scheduler.start()
        await asyncio.sleep(2.0)  # Enough time for retries
        await scheduler.stop()

        history = scheduler.get_history()
        assert len(history) >= 1

    def test_create_default_scheduler(self):
        """Default scheduler has pre-configured tasks."""
        from backend.agents.scheduler.task_scheduler import create_default_scheduler

        scheduler = create_default_scheduler()
        tasks = scheduler.list_tasks()
        names = [t["name"] for t in tasks]
        assert "health_check" in names
        assert "pattern_extraction" in names

    def test_scheduled_task_to_dict(self):
        """ScheduledTask serializes properly."""
        from backend.agents.scheduler.task_scheduler import ScheduledTask, TaskType

        task = ScheduledTask(
            name="test",
            task_type=TaskType.INTERVAL,
            coroutine_factory=lambda: None,
            interval_seconds=60,
        )
        d = task.to_dict()
        assert d["name"] == "test"
        assert d["task_type"] == "interval"
        assert d["run_count"] == 0


# =============================================================================
# 4. PAPER TRADER TESTS
# =============================================================================


class TestPaperTrader:
    """Tests for AgentPaperTrader module."""

    def test_import(self):
        """Module imports."""
        from backend.agents.trading import paper_trader as mod

        assert hasattr(mod, "AgentPaperTrader")
        assert hasattr(mod, "PaperSession")
        assert hasattr(mod, "PaperTrade")

    def test_paper_trade_to_dict(self):
        """PaperTrade serialization."""
        from backend.agents.trading.paper_trader import PaperTrade

        trade = PaperTrade(
            trade_id="abc",
            symbol="BTCUSDT",
            side="buy",
            entry_price=50000.0,
            qty=0.1,
        )
        d = trade.to_dict()
        assert d["trade_id"] == "abc"
        assert d["side"] == "buy"
        assert d["is_open"] is True

    def test_paper_session_to_dict(self):
        """PaperSession serialization."""
        from backend.agents.trading.paper_trader import PaperSession

        session = PaperSession(
            session_id="s1",
            symbol="BTCUSDT",
            strategy_type="rsi",
            initial_balance=5000,
            current_balance=5200,
        )
        d = session.to_dict()
        assert d["session_id"] == "s1"
        assert d["current_balance"] == 5200
        assert d["is_active"] is True

    def test_close_paper_trade_long_profit(self):
        """Closing a profitable long trade updates session."""
        from backend.agents.trading.paper_trader import (
            AgentPaperTrader,
            PaperSession,
            PaperTrade,
        )

        session = PaperSession(
            session_id="t1",
            symbol="BTCUSDT",
            strategy_type="rsi",
            initial_balance=10000,
            current_balance=10000,
        )
        trade = PaperTrade(
            trade_id="t1",
            symbol="BTCUSDT",
            side="buy",
            entry_price=50000,
            qty=0.1,
        )

        AgentPaperTrader._close_paper_trade(session, trade, 51000)

        assert trade.is_open is False
        assert trade.pnl == pytest.approx(100.0, abs=0.01)  # (51000-50000)*0.1
        assert session.winning_trades == 1
        assert session.current_balance == pytest.approx(10100.0, abs=0.01)

    def test_close_paper_trade_short_loss(self):
        """Closing a losing short trade."""
        from backend.agents.trading.paper_trader import (
            AgentPaperTrader,
            PaperSession,
            PaperTrade,
        )

        session = PaperSession(
            session_id="t2",
            symbol="BTCUSDT",
            strategy_type="rsi",
            initial_balance=10000,
            current_balance=10000,
        )
        trade = PaperTrade(
            trade_id="t2",
            symbol="BTCUSDT",
            side="sell",
            entry_price=50000,
            qty=0.1,
        )

        AgentPaperTrader._close_paper_trade(session, trade, 51000)

        assert trade.pnl == pytest.approx(-100.0, abs=0.01)  # (50000-51000)*0.1
        assert session.losing_trades == 1
        assert session.current_balance == pytest.approx(9900.0, abs=0.01)

    def test_list_sessions_initially_empty(self):
        """No sessions at start."""
        from backend.agents.trading.paper_trader import AgentPaperTrader

        AgentPaperTrader._sessions.clear()
        assert AgentPaperTrader.list_sessions() == []
        assert AgentPaperTrader.list_active() == []

    @pytest.mark.asyncio
    async def test_start_and_stop_session(self):
        """Start and stop a paper trading session."""
        from backend.agents.trading.paper_trader import AgentPaperTrader

        AgentPaperTrader._sessions.clear()
        trader = AgentPaperTrader()

        # Mock the price feed and signal generation
        with (
            patch.object(AgentPaperTrader, "_get_latest_price", new_callable=AsyncMock, return_value=None),
        ):
            session = await trader.start_session(
                symbol="BTCUSDT",
                strategy_type="rsi",
                initial_balance=5000,
                duration_minutes=0.02,  # ~1 second
            )

            assert session.is_active is True
            assert session.session_id in [s["session_id"] for s in AgentPaperTrader.list_active()]

            # Wait briefly then stop
            await asyncio.sleep(0.3)
            stopped = await trader.stop_session(session.session_id)
            assert stopped is not None
            assert stopped.is_active is False

    @pytest.mark.asyncio
    async def test_generate_signal_exit(self):
        """Signal generation produces exit on take profit."""
        from backend.agents.trading.paper_trader import AgentPaperTrader, PaperTrade

        open_trade = PaperTrade(
            trade_id="x",
            symbol="BTCUSDT",
            side="buy",
            entry_price=50000,
            qty=0.1,
        )

        signal = await AgentPaperTrader._generate_signal(
            "rsi",
            {"take_profit_pct": 1.0, "stop_loss_pct": 0.5},
            "BTCUSDT",
            50600,  # +1.2% → above TP
            [open_trade],
        )
        assert signal == "close"

    @pytest.mark.asyncio
    async def test_generate_signal_hold(self):
        """Signal generation produces hold when price is within range."""
        from backend.agents.trading.paper_trader import AgentPaperTrader, PaperTrade

        open_trade = PaperTrade(
            trade_id="y",
            symbol="BTCUSDT",
            side="buy",
            entry_price=50000,
            qty=0.1,
        )

        signal = await AgentPaperTrader._generate_signal(
            "rsi",
            {"take_profit_pct": 2.0, "stop_loss_pct": 1.0},
            "BTCUSDT",
            50100,  # +0.2% → within range
            [open_trade],
        )
        assert signal == "hold"


# =============================================================================
# 5. DASHBOARD API ENDPOINT TESTS
# =============================================================================


class TestDashboardEndpoints:
    """Tests for new dashboard API endpoints (require server)."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_workflow_active_endpoint(self):
        """GET /dashboard/workflow/active returns list."""
        import httpx

        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            resp = await client.get("/api/v1/agents/dashboard/workflow/active")
            assert resp.status_code == 200
            data = resp.json()
            assert "workflows" in data

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_patterns_endpoint(self):
        """GET /dashboard/patterns returns extraction result."""
        import httpx

        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            resp = await client.get("/api/v1/agents/dashboard/patterns?min_samples=1")
            assert resp.status_code == 200
            data = resp.json()
            assert "success" in data

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_paper_sessions_endpoint(self):
        """GET /dashboard/paper-trading/sessions returns list."""
        import httpx

        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            resp = await client.get("/api/v1/agents/dashboard/paper-trading/sessions")
            assert resp.status_code == 200
            data = resp.json()
            assert "sessions" in data

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_activity_log_endpoint(self):
        """GET /dashboard/activity-log returns entries."""
        import httpx

        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            resp = await client.get("/api/v1/agents/dashboard/activity-log")
            assert resp.status_code == 200
            data = resp.json()
            assert "entries" in data

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_scheduler_tasks_endpoint(self):
        """GET /dashboard/scheduler/tasks returns response."""
        import httpx

        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            resp = await client.get("/api/v1/agents/dashboard/scheduler/tasks")
            assert resp.status_code == 200


# =============================================================================
# 6. INTEGRATION / CROSS-MODULE TESTS
# =============================================================================


class TestCrossModuleIntegration:
    """Tests for cross-module interactions."""

    def test_workflow_config_matches_backtest_tool_params(self):
        """WorkflowConfig fields match run_backtest tool parameters."""
        from backend.agents.workflows.autonomous_backtesting import WorkflowConfig

        config = WorkflowConfig()
        d = config.to_dict()
        # These must match the MCP run_backtest parameters
        assert "symbol" in d
        assert "interval" in d
        assert "start_date" in d
        assert "end_date" in d
        assert "initial_capital" in d
        assert "leverage" in d
        assert "direction" in d

    def test_pattern_extractor_in_self_improvement(self):
        """PatternExtractor is accessible from self_improvement package."""
        from backend.agents.self_improvement.pattern_extractor import PatternExtractor

        assert hasattr(PatternExtractor, "extract")
        assert hasattr(PatternExtractor, "search_similar_patterns")

    def test_scheduler_health_task_factory(self):
        """Pre-built health_check_task is importable."""
        from backend.agents.scheduler.task_scheduler import health_check_task

        assert asyncio.iscoroutinefunction(health_check_task)

    def test_scheduler_pattern_task_factory(self):
        """Pre-built pattern_extraction_task is importable."""
        from backend.agents.scheduler.task_scheduler import pattern_extraction_task

        assert asyncio.iscoroutinefunction(pattern_extraction_task)

    def test_paper_trader_session_model_complete(self):
        """PaperSession has all required fields for vector memory saving."""
        from backend.agents.trading.paper_trader import PaperSession

        session = PaperSession(session_id="x", symbol="BTC", strategy_type="rsi")
        d = session.to_dict()
        # Fields needed by save_backtest_result
        assert "strategy_type" in d
        assert "total_return_pct" in d
        assert "win_rate" in d
        assert "max_drawdown_pct" in d

    @pytest.mark.asyncio
    async def test_workflow_result_serializable(self):
        """WorkflowResult.to_dict() is JSON-serializable."""
        import json

        from backend.agents.workflows.autonomous_backtesting import (
            WorkflowConfig,
            WorkflowResult,
            WorkflowStatus,
        )

        result = WorkflowResult(
            workflow_id="test",
            config=WorkflowConfig(),
            status=WorkflowStatus(workflow_id="test"),
            backtest_result={"win_rate": 55},
            total_duration_s=10.5,
        )
        serialized = json.dumps(result.to_dict())
        assert "test" in serialized
