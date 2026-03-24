"""
Integration tests for the multi-agent system additions.

All LLM calls are mocked — no real API keys needed.

Run with:
    pytest tests/test_multi_agent_integration.py -v
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────
# 1. LLMResponseCache
# ─────────────────────────────────────────────────────────────────


class TestLLMResponseCache:
    def _make_cache(self):
        import backend.agents.llm_response_cache as m

        m._instance = None
        from backend.agents.llm_response_cache import LLMResponseCache

        return LLMResponseCache()

    def test_miss_returns_none(self):
        cache = self._make_cache()
        key = cache.key([{"role": "user", "content": "hello"}], "deepseek-chat", "deepseek")
        assert cache.get(key) is None

    def test_set_then_get(self):
        cache = self._make_cache()
        msgs = [{"role": "user", "content": "what is BTC regime?"}]
        key = cache.key(msgs, "sonar", "perplexity")
        cache.set(key, {"content": "bullish", "citations": []}, "perplexity")
        hit = cache.get(key)
        assert hit is not None
        assert hit["content"] == "bullish"

    def test_normalize_strips_timestamps(self):
        from backend.agents.llm_response_cache import _normalize_text

        t1 = _normalize_text("BTC price on 2026-03-19 is up")
        t2 = _normalize_text("BTC price on 2026-03-20 is up")
        assert t1 == t2

    def test_normalize_strips_dollar_prices(self):
        from backend.agents.llm_response_cache import _normalize_text

        t1 = _normalize_text("BTC is trading at $84,000.00 right now")
        t2 = _normalize_text("BTC is trading at $91,500.00 right now")
        assert t1 == t2

    def test_same_key_for_semantically_equal_prompts(self):
        cache = self._make_cache()
        msgs_a = [{"role": "user", "content": "BTC at $84,000 regime?"}]
        msgs_b = [{"role": "user", "content": "BTC at $91,000 regime?"}]
        key_a = cache.key(msgs_a, "sonar", "perplexity")
        key_b = cache.key(msgs_b, "sonar", "perplexity")
        assert key_a == key_b

    def test_different_agents_different_keys(self):
        cache = self._make_cache()
        msgs = [{"role": "user", "content": "hello"}]
        k1 = cache.key(msgs, "sonar", "perplexity")
        k2 = cache.key(msgs, "deepseek-chat", "deepseek")
        assert k1 != k2

    def test_stats_reflect_hits(self):
        cache = self._make_cache()
        msgs = [{"role": "user", "content": "test"}]
        key = cache.key(msgs, "sonar", "perplexity")
        cache.set(key, {"content": "ok"}, "perplexity")
        cache.get(key)
        cache.get(key)
        stats = cache.get_stats()
        assert stats["hits"] >= 2

    def test_invalidate(self):
        cache = self._make_cache()
        msgs = [{"role": "user", "content": "test"}]
        key = cache.key(msgs, "sonar", "perplexity")
        cache.set(key, {"content": "x"}, "perplexity")
        assert cache.get(key) is not None
        cache.invalidate(key)
        assert cache.get(key) is None

    def test_singleton(self):
        import backend.agents.llm_response_cache as m

        m._instance = None
        from backend.agents.llm_response_cache import get_llm_response_cache

        c1 = get_llm_response_cache()
        c2 = get_llm_response_cache()
        assert c1 is c2


# ─────────────────────────────────────────────────────────────────
# 2. CostCircuitBreaker
# ─────────────────────────────────────────────────────────────────


class TestCostCircuitBreaker:
    def _make_breaker(self, per_call=2.0, per_hour=20.0, per_day=50.0):
        from backend.agents.cost_circuit_breaker import CostCircuitBreaker

        return CostCircuitBreaker(
            limit_per_call_usd=per_call,
            limit_per_hour_usd=per_hour,
            limit_per_day_usd=per_day,
        )

    def test_ok_when_under_limits(self):
        b = self._make_breaker()
        b.check_before_call("perplexity", estimated_cost_usd=0.001)  # should not raise

    def test_blocks_over_per_call(self):
        from backend.agents.cost_circuit_breaker import CostLimitExceededError

        b = self._make_breaker(per_call=0.50)
        with pytest.raises(CostLimitExceededError) as exc:
            b.check_before_call("perplexity", estimated_cost_usd=0.60)
        assert exc.value.limit_type == "per_call"

    def test_blocks_over_per_hour(self):
        from backend.agents.cost_circuit_breaker import CostLimitExceededError

        b = self._make_breaker(per_hour=1.0)
        b.record_actual("perplexity", cost_usd=0.90)
        with pytest.raises(CostLimitExceededError) as exc:
            b.check_before_call("perplexity", estimated_cost_usd=0.20)
        assert exc.value.limit_type == "per_hour"

    def test_blocks_over_per_day(self):
        from backend.agents.cost_circuit_breaker import CostLimitExceededError

        b = self._make_breaker(per_day=1.0)
        b.record_actual("perplexity", cost_usd=0.95)
        with pytest.raises(CostLimitExceededError) as exc:
            b.check_before_call("perplexity", estimated_cost_usd=0.10)
        assert exc.value.limit_type == "per_day"

    def test_reset_clears_records(self):
        b = self._make_breaker(per_hour=1.0)
        b.record_actual("perplexity", cost_usd=0.95)
        b.reset()
        b.check_before_call("perplexity", estimated_cost_usd=0.10)  # should pass

    def test_record_actual_accumulates(self):
        b = self._make_breaker()
        b.record_actual("deepseek", 0.001)
        b.record_actual("deepseek", 0.002)
        summary = b.get_spend_summary()
        assert summary["hourly_spend_usd"] >= 0.003

    def test_singleton(self):
        import backend.agents.cost_circuit_breaker as m

        m._breaker = None
        from backend.agents.cost_circuit_breaker import get_cost_circuit_breaker

        b1 = get_cost_circuit_breaker()
        b2 = get_cost_circuit_breaker()
        assert b1 is b2


# ─────────────────────────────────────────────────────────────────
# 3. prompts_alerting — cache alert suppression fix
# Patch the source module where PromptsMonitor is defined, not the caller
# ─────────────────────────────────────────────────────────────────


class TestPromptsAlertingCacheFix:
    def _make_alerting(self):
        from backend.monitoring.prompts_alerting import AlertConfig, PromptsAlerting

        return PromptsAlerting(config=AlertConfig(min_cache_hit_rate=0.5))

    def test_no_alert_when_zero_ops(self):
        alerting = self._make_alerting()
        with patch("backend.monitoring.prompts_monitor.PromptsMonitor") as MockMonitor:
            MockMonitor.return_value.get_cache_stats.return_value = {
                "cache_hit_rate": 0.0,
                "cache_hits": 0,
                "cache_misses": 0,
                "cache_size": 0,
            }
            alerts = alerting._check_cache_performance()
        assert alerts == []

    def test_alert_fires_when_low_hit_rate_with_ops(self):
        alerting = self._make_alerting()
        with patch("backend.monitoring.prompts_monitor.PromptsMonitor") as MockMonitor:
            MockMonitor.return_value.get_cache_stats.return_value = {
                "cache_hit_rate": 0.10,
                "cache_hits": 10,
                "cache_misses": 90,
                "cache_size": 5,
            }
            alerts = alerting._check_cache_performance()
        assert len(alerts) == 1
        assert alerts[0].alert_type.value == "low_cache_hit"

    def test_no_alert_when_hit_rate_above_threshold(self):
        alerting = self._make_alerting()
        with patch("backend.monitoring.prompts_monitor.PromptsMonitor") as MockMonitor:
            MockMonitor.return_value.get_cache_stats.return_value = {
                "cache_hit_rate": 0.80,
                "cache_hits": 80,
                "cache_misses": 20,
                "cache_size": 15,
            }
            alerts = alerting._check_cache_performance()
        assert alerts == []


# ─────────────────────────────────────────────────────────────────
# 4. GenerateStrategiesNode — Self-MoA
# Mock _prompt_engineer to avoid needing a real MarketContext object
# ─────────────────────────────────────────────────────────────────


class TestGenerateStrategiesNodeMoA:
    def _make_state(self, agents=None):
        try:
            from backend.agents.langgraph_orchestrator import AgentState
        except ImportError:
            pytest.skip("langgraph_orchestrator not importable")

        state = AgentState()
        market_ctx = MagicMock()
        market_ctx.market_regime = "bullish"
        state.set_result("analyze_market", {"market_context": market_ctx})
        state.context["agents"] = agents or ["deepseek", "qwen"]
        return state

    @pytest.mark.asyncio
    async def test_three_deepseek_calls_made(self):
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        node = GenerateStrategiesNode()
        # Mock prompt engineer so we don't need real MarketContext
        node._prompt_engineer = MagicMock()
        node._prompt_engineer.create_strategy_prompt.return_value = "test prompt"
        node._prompt_engineer.get_system_message.return_value = "test system"

        state = self._make_state(agents=["deepseek"])
        call_temps = []

        async def fake_call_llm(agent_name, prompt, system_msg, temperature=None, state=None):
            if agent_name == "deepseek":
                call_temps.append(temperature)
            return f'{{"strategy": "rsi", "temp": {temperature}}}'

        node._call_llm = fake_call_llm
        await node.execute(state)

        deepseek_calls = [t for t in call_temps if t in (0.3, 0.7, 1.1)]
        assert len(deepseek_calls) == 3

    @pytest.mark.asyncio
    async def test_qwen_critic_called_with_three_variants(self):
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        node = GenerateStrategiesNode()
        node._prompt_engineer = MagicMock()
        node._prompt_engineer.create_strategy_prompt.return_value = "test prompt"
        node._prompt_engineer.get_system_message.return_value = "test system"

        state = self._make_state(agents=["deepseek"])
        critic_prompt_received = []

        async def fake_call_llm(agent_name, prompt, system_msg, temperature=None, state=None):
            if agent_name == "qwen":
                critic_prompt_received.append(prompt)
                return '{"synthesised": true}'
            return f'{{"variant": {temperature}}}'

        node._call_llm = fake_call_llm
        await node.execute(state)

        assert len(critic_prompt_received) == 1
        assert "VARIANT 1" in critic_prompt_received[0]
        assert "VARIANT 2" in critic_prompt_received[0]
        assert "VARIANT 3" in critic_prompt_received[0]

    @pytest.mark.asyncio
    async def test_fallback_when_qwen_critic_fails(self):
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        node = GenerateStrategiesNode()
        node._prompt_engineer = MagicMock()
        node._prompt_engineer.create_strategy_prompt.return_value = "test prompt"
        node._prompt_engineer.get_system_message.return_value = "test system"

        state = self._make_state(agents=["deepseek"])

        async def fake_call_llm(agent_name, prompt, system_msg, temperature=None, state=None):
            if agent_name == "qwen":
                raise RuntimeError("QWEN unavailable")
            return f'{{"variant": {temperature}}}'

        node._call_llm = fake_call_llm
        result = await node.execute(state)
        gen = result.get_result("generate_strategies")
        assert gen is not None
        assert len(gen["responses"]) == 1
        assert "0.7" in gen["responses"][0]["response"]

    @pytest.mark.asyncio
    async def test_non_deepseek_agent_called_normally(self):
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        node = GenerateStrategiesNode()
        node._prompt_engineer = MagicMock()
        node._prompt_engineer.create_strategy_prompt.return_value = "test prompt"
        node._prompt_engineer.get_system_message.return_value = "test system"

        state = self._make_state(agents=["deepseek", "perplexity"])
        perplexity_calls = []

        async def fake_call_llm(agent_name, prompt, system_msg, temperature=None, state=None):
            if agent_name == "perplexity":
                perplexity_calls.append(1)
                return '{"market": "bullish"}'
            if agent_name == "qwen":
                return '{"synthesised": true}'
            return f'{{"variant": {temperature}}}'

        node._call_llm = fake_call_llm
        await node.execute(state)
        assert len(perplexity_calls) == 1


# ─────────────────────────────────────────────────────────────────
# 5. ConsensusNode — patch source modules for local imports
# ─────────────────────────────────────────────────────────────────


class TestConsensusNode:
    def _make_state(self, proposals):
        try:
            from backend.agents.langgraph_orchestrator import AgentState
        except ImportError:
            pytest.skip("langgraph_orchestrator not importable")

        state = AgentState()
        state.set_result("parse_responses", {"proposals": proposals})
        return state

    def _mock_strategy(self, name="rsi", exit_cond=True, filters=True):
        s = MagicMock()
        s.strategy_name = name
        s.exit_conditions = [MagicMock()] if exit_cond else []
        s.filters = [MagicMock()] if filters else []
        return s

    def _mock_validation(self, score=0.8):
        v = MagicMock()
        v.quality_score = score
        return v

    @pytest.mark.asyncio
    async def test_consensus_engine_used(self):
        from backend.agents.trading_strategy_graph import ConsensusNode

        proposals = [
            {"agent": "deepseek", "strategy": self._mock_strategy("s1"), "validation": self._mock_validation(0.9)},
            {"agent": "qwen", "strategy": self._mock_strategy("s2"), "validation": self._mock_validation(0.7)},
        ]
        state = self._make_state(proposals)

        mock_result = MagicMock()
        mock_result.strategy = proposals[0]["strategy"]
        mock_result.agreement_score = 0.85
        mock_result.agent_weights = {"deepseek": 0.6, "qwen": 0.4}

        # Patch source modules — local imports inside execute() resolve from here
        with (
            patch("backend.agents.consensus.consensus_engine.ConsensusEngine") as MockCE,
            patch("backend.agents.self_improvement.agent_tracker.AgentPerformanceTracker") as MockAT,
        ):
            MockCE.return_value.aggregate.return_value = mock_result
            MockCE.return_value.update_performance.return_value = None
            MockAT.return_value.compute_dynamic_weights.return_value = {"deepseek": 0.6, "qwen": 0.4}

            node = ConsensusNode()
            result_state = await node.execute(state)

        sel = result_state.get_result("select_best")
        assert sel is not None
        assert sel["agreement_score"] == 0.85

    @pytest.mark.asyncio
    async def test_fallback_to_best_of_on_error(self):
        """Falls back to quality-score ranking when ConsensusEngine raises."""
        from backend.agents.trading_strategy_graph import ConsensusNode

        s_low = self._mock_strategy("s1")
        s_high = self._mock_strategy("s2")
        proposals = [
            {"agent": "deepseek", "strategy": s_low, "validation": self._mock_validation(0.5)},
            {"agent": "qwen", "strategy": s_high, "validation": self._mock_validation(0.9)},
        ]
        state = self._make_state(proposals)

        with (
            patch("backend.agents.consensus.consensus_engine.ConsensusEngine", side_effect=Exception("CE unavailable")),
            patch(
                "backend.agents.self_improvement.agent_tracker.AgentPerformanceTracker",
                side_effect=Exception("tracker unavailable"),
            ),
        ):
            node = ConsensusNode()
            result_state = await node.execute(state)

        sel = result_state.get_result("select_best")
        assert sel is not None
        assert sel["selected_agent"] == "qwen"


# ─────────────────────────────────────────────────────────────────
# 6. MemoryUpdateNode — patch source module
# ─────────────────────────────────────────────────────────────────


class TestMemoryUpdateNode:
    def _make_state(self, metrics, selected_agent="deepseek"):
        try:
            from backend.agents.langgraph_orchestrator import AgentState
        except ImportError:
            pytest.skip("langgraph_orchestrator not importable")

        state = AgentState()
        strategy = MagicMock()
        strategy.strategy_name = "RSI_test"
        strategy.strategy_type = "rsi"
        state.set_result(
            "select_best",
            {
                "selected_strategy": strategy,
                "selected_agent": selected_agent,
            },
        )
        state.set_result("backtest", {"metrics": metrics})
        state.context.update({"symbol": "BTCUSDT", "timeframe": "15"})
        return state

    @pytest.mark.asyncio
    async def test_store_called_on_successful_backtest(self):
        from backend.agents.trading_strategy_graph import MemoryUpdateNode

        metrics = {
            "sharpe_ratio": 1.5,
            "max_drawdown": 10.0,
            "total_trades": 20,
            "win_rate": 0.55,
            "profit_factor": 1.8,
        }
        state = self._make_state(metrics)

        mock_memory = AsyncMock()
        mock_memory.store = AsyncMock(return_value=MagicMock())

        # Patch source module
        with patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory", return_value=mock_memory):
            node = MemoryUpdateNode()
            await node.execute(state)

        mock_memory.store.assert_called_once()
        call_kwargs = mock_memory.store.call_args.kwargs
        assert "BTCUSDT" in call_kwargs["tags"]
        assert call_kwargs["importance"] > 0

    @pytest.mark.asyncio
    async def test_no_error_when_memory_raises(self):
        from backend.agents.trading_strategy_graph import MemoryUpdateNode

        metrics = {"sharpe_ratio": 2.0, "max_drawdown": 5.0, "total_trades": 30, "win_rate": 0.6, "profit_factor": 2.2}
        state = self._make_state(metrics)

        with patch(
            "backend.agents.memory.hierarchical_memory.HierarchicalMemory", side_effect=Exception("DB unavailable")
        ):
            node = MemoryUpdateNode()
            result = await node.execute(state)

        assert result is not None  # pipeline continues

    @pytest.mark.asyncio
    async def test_skipped_when_no_backtest_metrics(self):
        from backend.agents.trading_strategy_graph import MemoryUpdateNode

        try:
            from backend.agents.langgraph_orchestrator import AgentState
        except ImportError:
            pytest.skip()

        state = AgentState()
        state.set_result("select_best", {"selected_agent": "deepseek"})
        state.set_result("backtest", {"metrics": {}})

        mock_memory = AsyncMock()
        with patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory", return_value=mock_memory):
            node = MemoryUpdateNode()
            await node.execute(state)

        mock_memory.store.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# 7. DebateNode — patch source module
# ─────────────────────────────────────────────────────────────────


class TestDebateNode:
    def _make_state(self, regime="bullish"):
        try:
            from backend.agents.langgraph_orchestrator import AgentState
        except ImportError:
            pytest.skip("langgraph_orchestrator not importable")

        state = AgentState()
        ctx = MagicMock()
        ctx.market_regime = regime
        state.set_result("analyze_market", {"market_context": ctx})
        state.context.update({"symbol": "BTCUSDT", "agents": ["deepseek", "qwen"]})
        return state

    @pytest.mark.asyncio
    async def test_debate_enriches_context(self):
        from backend.agents.trading_strategy_graph import DebateNode

        mock_result = MagicMock()
        mock_result.confidence_score = 0.82
        mock_result.consensus_answer = "Trade long with moderate risk"
        mock_result.rounds_completed = 2

        # Patch the function in its source module
        with patch(
            "backend.agents.consensus.real_llm_deliberation.deliberate_with_llm",
            new=AsyncMock(return_value=mock_result),
        ):
            node = DebateNode()
            state = self._make_state()
            result = await node.execute(state)

        debate = result.context.get("debate_consensus")
        assert debate is not None
        assert debate["confidence"] == pytest.approx(0.82)
        assert "long" in debate["consensus"].lower()

    @pytest.mark.asyncio
    async def test_debate_failure_is_nonfatal(self):
        from backend.agents.trading_strategy_graph import DebateNode

        with patch(
            "backend.agents.consensus.real_llm_deliberation.deliberate_with_llm",
            new=AsyncMock(side_effect=RuntimeError("API down")),
        ):
            node = DebateNode()
            state = self._make_state()
            result = await node.execute(state)

        debate_result = result.get_result("debate")
        assert debate_result is not None
        assert debate_result["consensus"] is None

    @pytest.mark.asyncio
    async def test_debate_skips_without_market_analysis(self):
        from backend.agents.trading_strategy_graph import DebateNode

        try:
            from backend.agents.langgraph_orchestrator import AgentState
        except ImportError:
            pytest.skip()

        state = AgentState()  # no market analysis
        node = DebateNode()
        result = await node.execute(state)
        assert result.get_result("debate") is None


# ─────────────────────────────────────────────────────────────────
# 8. Full pipeline graph smoke test
# ─────────────────────────────────────────────────────────────────


class TestGraphBuilds:
    def test_full_graph_build_with_all_nodes(self):
        from backend.agents.trading_strategy_graph import build_trading_strategy_graph

        graph = build_trading_strategy_graph(run_backtest=True, run_debate=True)
        assert graph is not None

    def test_graph_without_debate(self):
        from backend.agents.trading_strategy_graph import build_trading_strategy_graph

        graph = build_trading_strategy_graph(run_backtest=True, run_debate=False)
        assert graph is not None

    def test_graph_without_backtest(self):
        from backend.agents.trading_strategy_graph import build_trading_strategy_graph

        graph = build_trading_strategy_graph(run_backtest=False, run_debate=False)
        assert graph is not None


# ─────────────────────────────────────────────────────────────────
# 9. CostCircuitBreaker wired into UnifiedAgentInterface
# Patch source module — get_cost_circuit_breaker is imported locally
# ─────────────────────────────────────────────────────────────────


class TestCostCircuitBreakerInAgent:
    @pytest.mark.asyncio
    async def test_agent_blocked_by_cost_breaker(self):
        try:
            from backend.agents.models import AgentType
            from backend.agents.unified_agent_interface import UnifiedAgentInterface
        except ImportError:
            pytest.skip("unified_agent_interface not importable")

        from backend.agents.cost_circuit_breaker import CostLimitExceededError

        interface = UnifiedAgentInterface.__new__(UnifiedAgentInterface)
        interface.key_manager = AsyncMock()
        interface.key_manager.get_active_key = AsyncMock(return_value=MagicMock(index=0, value="fake"))

        request = MagicMock()
        request.agent_type = AgentType.PERPLEXITY
        request.context = {}
        request.strict_mode = False
        request.task_type = "test"

        # Patch in the source module so the local import inside _execute_api_call sees it
        with patch("backend.agents.cost_circuit_breaker.get_cost_circuit_breaker") as mock_fn:
            mock_breaker = MagicMock()
            mock_breaker.check_before_call.side_effect = CostLimitExceededError("over budget", "per_hour", 20.0, 21.0)
            mock_fn.return_value = mock_breaker

            response = await interface._execute_api_call(request, time.time())

        assert response.success is False
        assert "Cost budget exceeded" in response.error
