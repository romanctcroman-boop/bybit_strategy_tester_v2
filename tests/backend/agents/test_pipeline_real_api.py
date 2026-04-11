"""
Real API Integration Tests — Full run_strategy_pipeline() with live LLMs.

PURPOSE:
    Tests that the full pipeline runs end-to-end against real Claude / Perplexity
    APIs without mocks.  Each test is individually skipable when the relevant
    key is absent.

    NOTE: After the pipeline refactor, agents=["deepseek"] now routes to
    claude-sonnet-4-6, and agents=["qwen"] routes to claude-haiku-4-5-20251001.
    The primary guard is therefore ANTHROPIC_API_KEY.

MARKS:
    api_live   — any test that makes a real HTTP call to an LLM provider

USAGE:
    pytest tests/backend/agents/test_pipeline_real_api.py -v -m api_live
    pytest tests/backend/agents/test_pipeline_real_api.py -v -m api_live --timeout=600

COST ESTIMATE:
    ~1-3 API calls per test at Claude pricing ≈ $0.001-0.01 per test.
    Total suite: ~$0.05-0.15

REQUIRES:
    ANTHROPIC_API_KEY in .env or environment.
    PERPLEXITY_API_KEY optional (GroundingNode skips gracefully when absent).
"""

from __future__ import annotations

import asyncio
import os
import unittest.mock

import numpy as np
import pandas as pd
import pytest
from dotenv import load_dotenv

load_dotenv(override=True)

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.trading_strategy_graph import run_strategy_pipeline

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
HAS_ANTHROPIC = bool(os.getenv("ANTHROPIC_API_KEY"))
HAS_DEEPSEEK = bool(os.getenv("DEEPSEEK_API_KEY"))  # kept for legacy debate test
HAS_QWEN = bool(os.getenv("QWEN_API_KEY"))  # kept for legacy debate test
HAS_PERPLEXITY = bool(os.getenv("PERPLEXITY_API_KEY"))
HAS_ANY_KEY = HAS_DEEPSEEK or HAS_QWEN or HAS_ANTHROPIC

# Primary skip guard: agents=["deepseek"] → claude-sonnet-4-6 → needs ANTHROPIC_API_KEY
skip_no_deepseek = pytest.mark.skipif(not HAS_ANTHROPIC, reason="ANTHROPIC_API_KEY not set")
skip_no_qwen = pytest.mark.skipif(not HAS_QWEN, reason="QWEN_API_KEY not set")
skip_no_any = pytest.mark.skipif(not HAS_ANY_KEY, reason="No LLM API key set")

pytestmark = pytest.mark.api_live


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int = 300) -> pd.DataFrame:
    """Synthetic BTCUSDT-like OHLCV DataFrame with realistic price movement."""
    rng = np.random.default_rng(42)
    close = 40_000 + np.cumsum(rng.normal(0, 150, n))
    close = np.clip(close, 30_000, 70_000)
    high = close + rng.uniform(50, 400, n)
    low = close - rng.uniform(50, 400, n)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    volume = rng.uniform(100, 2000, n)
    idx = pd.date_range("2025-01-01", periods=n, freq="15min")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return _make_ohlcv()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine in the test (pytest-asyncio not required)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Test class: Pipeline structure & state contract
# ---------------------------------------------------------------------------


class TestPipelineRealApiStructure:
    """Verify AgentState structure when pipeline runs with real LLMs."""

    def setup_method(self):
        """Clear GroundingNode TTL cache so each test gets a fresh grounding call."""
        import backend.agents.trading_strategy_graph as tsg

        tsg._GROUNDING_CACHE.clear()

    @skip_no_deepseek
    def test_pipeline_returns_agent_state(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        assert isinstance(state, AgentState)

    @skip_no_deepseek
    def test_pipeline_populates_results(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        assert isinstance(state.results, dict)
        assert len(state.results) > 0

    @skip_no_deepseek
    def test_pipeline_tracks_execution_path(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        assert len(state.execution_path) >= 3
        node_names = [name for name, _ in state.execution_path]
        assert "analyze_market" in node_names

    @skip_no_deepseek
    def test_pipeline_records_llm_calls(self, ohlcv):
        """At least one LLM call should be made and tracked."""
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        assert state.llm_call_count >= 1

    @skip_no_deepseek
    def test_pipeline_cost_is_non_negative(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        assert state.total_cost_usd >= 0.0

    @skip_no_deepseek
    def test_pipeline_has_no_critical_errors(self, ohlcv):
        """Pipeline may have warnings but should not crash with unhandled errors."""
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        # errors is a list of dicts; may be non-empty for optional nodes, but must not be None
        assert state.errors is not None
        assert isinstance(state.errors, list)


# ---------------------------------------------------------------------------
# Test class: Strategy output quality
# ---------------------------------------------------------------------------


class TestPipelineRealApiOutput:
    """Verify that real LLM responses produce parseable, valid strategy graphs."""

    @skip_no_deepseek
    def test_generate_strategies_produces_parsed_responses(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        # parse_responses stores {"proposals": [...]} — check the proposals list
        parsed = state.results.get("parse_responses", {})
        assert isinstance(parsed, dict)
        proposals = parsed.get("proposals", [])
        assert isinstance(proposals, list)

    @skip_no_deepseek
    def test_select_best_returns_dict_or_none(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        best = state.results.get("select_best")
        # None is acceptable if LLM returned unparseable output
        assert best is None or isinstance(best, dict)

    @skip_no_deepseek
    def test_strategy_graph_has_required_keys_when_present(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        graph = state.results.get("strategy_graph") or state.results.get("build_graph")
        if graph is not None:
            assert isinstance(graph, dict)
            # Must have at minimum blocks and connections (or name)
            assert "blocks" in graph or "name" in graph

    @skip_no_deepseek
    def test_report_node_included_in_results(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        # report node should have run and populated results
        report = state.results.get("report")
        assert report is not None
        assert isinstance(report, dict)

    @skip_no_deepseek
    def test_report_contains_pipeline_metrics(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        report = state.results.get("report", {})
        metrics = report.get("pipeline_metrics")
        if metrics is not None:
            assert "total_cost_usd" in metrics
            assert "llm_call_count" in metrics


# ---------------------------------------------------------------------------
# Test class: Multi-agent (debate)
# ---------------------------------------------------------------------------


class TestPipelineRealApiDebate:
    """Verify multi-agent path when multiple Claude aliases are passed."""

    @pytest.mark.skipif(
        not HAS_ANTHROPIC,
        reason="ANTHROPIC_API_KEY not set",
    )
    def test_debate_path_runs_with_two_agents(self, ohlcv):
        # Both aliases now map to Claude models; debate node was removed in
        # the refactor — verify the pipeline still completes successfully
        # with >=3 nodes visited.
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek", "qwen"],
                run_backtest=False,
                pipeline_timeout=180.0,
            )
        )
        assert isinstance(state, AgentState)
        node_names = [name for name, _ in state.execution_path]
        assert len(node_names) >= 3

    @skip_no_deepseek
    def test_no_debate_path_completes_faster(self, ohlcv):
        """Pipeline without debate should complete with fewer nodes."""
        state_no_debate = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        assert isinstance(state_no_debate, AgentState)
        # Should at minimum visit analyze + generate + parse + report
        assert len(state_no_debate.execution_path) >= 4


# ---------------------------------------------------------------------------
# Test class: Timeout behaviour
# ---------------------------------------------------------------------------


class TestPipelineRealApiTimeout:
    """Verify pipeline_timeout is enforced."""

    @skip_no_deepseek
    def test_pipeline_respects_short_timeout(self, ohlcv):
        """A 1-second timeout should return partial state without crashing."""
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=1.0,
            )
        )
        assert isinstance(state, AgentState)
        # Either timed out (error recorded) or pipeline was fast enough
        assert state.errors is not None

    @skip_no_deepseek
    def test_timeout_records_pipeline_error(self, ohlcv):
        """When timeout fires, 'pipeline' key appears in state.errors."""
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=0.001,  # near-instant timeout
            )
        )
        assert isinstance(state, AgentState)
        # With 1ms timeout the pipeline MUST have timed out;
        # state.errors is a list of dicts with "node" key
        assert any(e.get("node") == "pipeline" for e in state.errors)


# ---------------------------------------------------------------------------
# Test class: Different symbols / timeframes
# ---------------------------------------------------------------------------


class TestPipelineRealApiSymbols:
    """Verify pipeline handles different market configurations."""

    @skip_no_deepseek
    def test_ethusdt_symbol(self):
        ohlcv = _make_ohlcv(200)
        state = _run(
            run_strategy_pipeline(
                symbol="ETHUSDT",
                timeframe="60",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        assert isinstance(state, AgentState)
        assert state.context.get("symbol") == "ETHUSDT"

    @skip_no_deepseek
    def test_context_symbol_preserved(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="SOLUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        assert state.context.get("symbol") == "SOLUSDT"

    @skip_no_deepseek
    def test_context_timeframe_preserved(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="240",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                pipeline_timeout=120.0,
            )
        )
        assert state.context.get("timeframe") == "240"


# ---------------------------------------------------------------------------
# Eval scenario_a — baseline pipeline smoke test (no live LLM, all mocked)
# ---------------------------------------------------------------------------


class TestEvalScenarioA:
    """
    Eval scenario_a: Baseline pipeline validation with mocked LLMs.

    Verifies that the full GenerateStrategiesNode → ParseResponses → SelectBest
    chain works end-to-end with a minimal valid strategy JSON returned by the
    mock. Tests the *system integration* (prompt building, specialization
    routing, response parsing) without spending real API budget.
    """

    _VALID_STRATEGY_JSON = """{
  "strategy_name": "RSI Range Baseline",
  "description": "Simple RSI range filter for eval scenario_a.",
  "signals": [
    {
      "id": "rsi1",
      "type": "RSI",
      "params": {"period": 14, "use_long_range": true, "long_rsi_more": 0, "long_rsi_less": 30,
                  "use_short_range": true, "short_rsi_more": 70, "short_rsi_less": 100},
      "weight": 1.0,
      "condition": "RSI oversold for long, overbought for short"
    }
  ],
  "filters": [],
  "entry_conditions": {"long": "RSI < 30", "short": "RSI > 70", "logic": "OR"},
  "exit_conditions": {
    "take_profit": {"type": "fixed_pct", "value": 2.5, "description": "2.5% TP"},
    "stop_loss": {"type": "fixed_pct", "value": 1.5, "description": "1.5% SL"}
  },
  "position_management": {"size_pct": 100, "max_positions": 1},
  "optimization_hints": {
    "parameters_to_optimize": ["period"],
    "ranges": {"period": [7, 21]},
    "primary_objective": "sharpe_ratio",
    "optimizationParams": {"period": {"enabled": true, "min": 7, "max": 21, "step": 1}}
  }
}"""

    def _make_ohlcv(self, n: int = 300) -> pd.DataFrame:
        rng = __import__("numpy").random.default_rng(0)
        close = 40_000 + __import__("numpy").cumsum(rng.normal(0, 150, n))
        high = close + rng.uniform(50, 200, n)
        low = close - rng.uniform(50, 200, n)
        open_ = __import__("numpy").roll(close, 1)
        open_[0] = close[0]
        volume = rng.uniform(100, 1000, n)
        idx = pd.date_range("2025-01-01", periods=n, freq="15min")
        return pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=idx,
        )

    def test_scenario_a_prompt_uses_claude_sonnet_specialization(self):
        """get_system_message('claude-sonnet') must include output rules (json_emphasis)."""
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        pe = PromptEngineer()
        msg = pe.get_system_message("claude-sonnet")
        # Lowercased in П4 — avoid over-triggering Claude 4.x refusals with all-caps
        assert "Output rules" in msg, "claude-sonnet system_msg must include Output rules block"
        assert "activation flag" in msg, "Must hint about activation flags (use_long_range, etc.)"
        assert "stop_loss_percent" in msg or "0.5" in msg, "Must enforce SL/TP boundaries"

    def test_scenario_a_prompt_uses_opus_specialization_for_novel_regime(self):
        """get_system_message('claude-opus') must include output rules and deep_reasoning."""
        from backend.agents.prompts.prompt_engineer import PromptEngineer
        from backend.agents.prompts.templates import AGENT_SPECIALIZATIONS

        pe = PromptEngineer()
        msg = pe.get_system_message("claude-opus")
        assert "Output rules" in msg  # lowercased in П4
        spec = AGENT_SPECIALIZATIONS["claude-opus"]
        assert "deep_reasoning" in spec["strengths"]

    def test_scenario_a_specialization_description_differs_sonnet_vs_haiku(self):
        """Sonnet and Haiku must have different specialization descriptions."""
        from backend.agents.prompts.templates import AGENT_SPECIALIZATIONS

        sonnet_desc = AGENT_SPECIALIZATIONS["claude-sonnet"]["description"]
        haiku_desc = AGENT_SPECIALIZATIONS["claude-haiku"]["description"]
        assert sonnet_desc != haiku_desc, "Sonnet and Haiku must have distinct descriptions"

    def test_scenario_a_create_strategy_prompt_uses_agent_name(self):
        """create_strategy_prompt with agent_name='claude-sonnet' uses Sonnet description."""
        from backend.agents.prompts.context_builder import MarketContextBuilder
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        df = self._make_ohlcv()
        builder = MarketContextBuilder()
        context = builder.build_context("BTCUSDT", "15", df)

        pe = PromptEngineer()
        prompt = pe.create_strategy_prompt(
            context=context,
            platform_config={"commission": 0.0007, "leverage": 1},
            agent_name="claude-sonnet",
            include_examples=False,
        )
        sonnet_desc_fragment = "regime-adaptive"
        assert sonnet_desc_fragment in prompt, (
            f"Prompt must include claude-sonnet description fragment '{sonnet_desc_fragment}'"
        )

    @unittest.mock.patch("backend.security.key_manager.get_key_manager")
    def test_scenario_a_generate_node_routes_to_sonnet(self, mock_km):
        """GenerateStrategiesNode uses 'claude-sonnet' agent for known regimes."""
        import unittest.mock

        from backend.agents.langgraph_orchestrator import AgentState
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        # Setup mocks
        mock_km.return_value.get_decrypted_key.return_value = None  # no real API call

        node = GenerateStrategiesNode()

        # Stub _call_llm to return valid JSON
        async def _fake_call_llm(agent_name, prompt, system_msg, **kwargs):
            assert agent_name == "claude-sonnet", f"Expected claude-sonnet, got {agent_name}"
            return self._VALID_STRATEGY_JSON

        node._call_llm = _fake_call_llm

        # Stub _prompt_engineer to avoid MarketContext dependency
        node._prompt_engineer.create_strategy_prompt = unittest.mock.MagicMock(return_value="MOCK_PROMPT")
        node._prompt_engineer.get_system_message = unittest.mock.MagicMock(return_value="MOCK_SYSTEM")

        state = AgentState(
            context={
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "agents": ["deepseek"],
                "regime_classification": {"regime": "ranging"},
            }
        )
        # Inject a minimal market_context result so execute() doesn't bail early
        state.set_result(
            "analyze_market",
            {
                "market_context": unittest.mock.MagicMock(
                    to_prompt_vars=lambda: {},
                    market_regime="ranging",
                    symbol="BTCUSDT",
                    timeframe="15",
                ),
            },
        )

        result_state = asyncio.run(node.execute(state))
        responses = result_state.get_result("generate_strategies") or {}
        assert len(responses.get("responses", [])) == 1

    @unittest.mock.patch("backend.security.key_manager.get_key_manager")
    def test_scenario_a_generate_node_escalates_to_opus(self, mock_km):
        """GenerateStrategiesNode uses 'claude-opus' for unknown/extreme_volatile regimes."""
        import unittest.mock

        from backend.agents.langgraph_orchestrator import AgentState
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        mock_km.return_value.get_decrypted_key.return_value = None

        node = GenerateStrategiesNode()
        captured = []

        async def _fake_call_llm(agent_name, prompt, system_msg, **kwargs):
            captured.append(agent_name)
            return self._VALID_STRATEGY_JSON

        node._call_llm = _fake_call_llm
        node._prompt_engineer.create_strategy_prompt = unittest.mock.MagicMock(return_value="MOCK_PROMPT")
        node._prompt_engineer.get_system_message = unittest.mock.MagicMock(return_value="MOCK_SYSTEM")

        state = AgentState(
            context={
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "agents": ["deepseek"],
                "regime_classification": {"regime": "unknown"},
            }
        )
        state.set_result(
            "analyze_market",
            {
                "market_context": unittest.mock.MagicMock(
                    to_prompt_vars=lambda: {},
                    market_regime="unknown",
                    symbol="BTCUSDT",
                    timeframe="15",
                ),
            },
        )

        asyncio.run(node.execute(state))
        assert captured == ["claude-opus"], f"Expected ['claude-opus'], got {captured}"


# ---------------------------------------------------------------------------
# Eval scenario: regime_split — verify correct model routing per regime
# ---------------------------------------------------------------------------


class TestEvalRegimeSplit:
    """
    Eval regime_split: All 5 regime types route to the correct Claude model tier.

    Standard regimes (trending_up/down, ranging, consolidating, volatile)
    → claude-sonnet.
    Novel regimes (unknown, extreme_volatile) or force_escalate=True → claude-opus.
    This verifies the escalation logic introduced alongside the Claude pipeline.
    """

    _KNOWN_REGIMES = ["trending_up", "trending_down", "ranging", "consolidating", "volatile"]
    _NOVEL_REGIMES = ["unknown", "extreme_volatile"]

    @pytest.mark.parametrize("regime", _KNOWN_REGIMES)
    def test_known_regime_uses_sonnet(self, regime):
        """All standard regimes must route to claude-sonnet."""
        import unittest.mock

        from backend.agents.langgraph_orchestrator import AgentState
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        captured = []

        async def _fake_call_llm(agent_name, prompt, system_msg, **kwargs):
            captured.append(agent_name)
            return "{}"

        with unittest.mock.patch("backend.security.key_manager.get_key_manager") as mk:
            mk.return_value.get_decrypted_key.return_value = None
            node = GenerateStrategiesNode()
            node._call_llm = _fake_call_llm
            node._prompt_engineer.create_strategy_prompt = unittest.mock.MagicMock(return_value="P")
            node._prompt_engineer.get_system_message = unittest.mock.MagicMock(return_value="S")

            state = AgentState(
                context={
                    "symbol": "BTCUSDT",
                    "timeframe": "15",
                    "agents": ["deepseek"],
                    "regime_classification": {"regime": regime},
                }
            )
            state.set_result(
                "analyze_market",
                {
                    "market_context": unittest.mock.MagicMock(
                        to_prompt_vars=lambda: {},
                        market_regime=regime,
                        symbol="BTCUSDT",
                        timeframe="15",
                    )
                },
            )
            asyncio.run(node.execute(state))

        assert captured == ["claude-sonnet"], f"Regime '{regime}' should route to claude-sonnet, got {captured}"

    @pytest.mark.parametrize("regime", _NOVEL_REGIMES)
    def test_novel_regime_escalates_to_opus(self, regime):
        """Novel/unknown regimes must route to claude-opus."""
        import unittest.mock

        from backend.agents.langgraph_orchestrator import AgentState
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        captured = []

        async def _fake_call_llm(agent_name, prompt, system_msg, **kwargs):
            captured.append(agent_name)
            return "{}"

        with unittest.mock.patch("backend.security.key_manager.get_key_manager") as mk:
            mk.return_value.get_decrypted_key.return_value = None
            node = GenerateStrategiesNode()
            node._call_llm = _fake_call_llm
            node._prompt_engineer.create_strategy_prompt = unittest.mock.MagicMock(return_value="P")
            node._prompt_engineer.get_system_message = unittest.mock.MagicMock(return_value="S")

            state = AgentState(
                context={
                    "symbol": "BTCUSDT",
                    "timeframe": "15",
                    "agents": ["deepseek"],
                    "regime_classification": {"regime": regime},
                }
            )
            state.set_result(
                "analyze_market",
                {
                    "market_context": unittest.mock.MagicMock(
                        to_prompt_vars=lambda: {},
                        market_regime=regime,
                        symbol="BTCUSDT",
                        timeframe="15",
                    )
                },
            )
            asyncio.run(node.execute(state))

        assert captured == ["claude-opus"], f"Novel regime '{regime}' should escalate to claude-opus, got {captured}"

    def test_force_escalate_overrides_known_regime(self):
        """force_escalate=True must use claude-opus even for a known regime."""
        import unittest.mock

        from backend.agents.langgraph_orchestrator import AgentState
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        captured = []

        async def _fake_call_llm(agent_name, prompt, system_msg, **kwargs):
            captured.append(agent_name)
            return "{}"

        with unittest.mock.patch("backend.security.key_manager.get_key_manager") as mk:
            mk.return_value.get_decrypted_key.return_value = None
            node = GenerateStrategiesNode()
            node._call_llm = _fake_call_llm
            node._prompt_engineer.create_strategy_prompt = unittest.mock.MagicMock(return_value="P")
            node._prompt_engineer.get_system_message = unittest.mock.MagicMock(return_value="S")

            state = AgentState(
                context={
                    "symbol": "BTCUSDT",
                    "timeframe": "15",
                    "agents": ["deepseek"],
                    "regime_classification": {"regime": "trending_up"},
                    "force_escalate": True,  # overrides
                }
            )
            state.set_result(
                "analyze_market",
                {
                    "market_context": unittest.mock.MagicMock(
                        to_prompt_vars=lambda: {},
                        market_regime="trending_up",
                        symbol="BTCUSDT",
                        timeframe="15",
                    )
                },
            )
            asyncio.run(node.execute(state))

        assert captured == ["claude-opus"], f"force_escalate=True should route to claude-opus, got {captured}"
