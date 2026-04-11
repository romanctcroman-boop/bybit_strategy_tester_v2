"""
CP6 — Phase 6: Memory во время оптимизации (A2AParamRangeNode)

Tests:
  1.  Memory hit → prompt contains historical params text
  2.  Memory miss (empty records) → prompt has no memory section
  3.  Memory recall error → graceful degradation, no crash
  4.  _recall_opt_params called with correct namespace ("optimization_params")
  5.  _format_memory_context → empty string when records=[]
  6.  _format_memory_context → non-empty string when records present
  7.  _format_memory_context → object-style records (with .content attr)
  8.  _format_memory_context → dict-style records (with "content" key)
  9.  _format_memory_context → truncates long content to ≤200 chars per entry
  10. Prompt contains "Historical optimization memory" section when memory hit
  11. Prompt contains no memory section header when memory miss
  12. A2AParamRangeNode still writes hints even when memory call returns records
  13. MemoryUpdateNode saves to "optimization_params" when sharpe >= 0.4
  14. MemoryUpdateNode does NOT save to "optimization_params" when sharpe < 0.4
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.trading_strategy_graph import A2AParamRangeNode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


_RANGES_JSON = json.dumps({"ranges": {"rsi_period": [12, 18], "sl_pct": [0.018, 0.026]}})

_INSIGHTS = {
    "param_clusters": {"rsi_period": [14, 15]},
    "winning_zones": {"rsi_period": {"min": 12, "max": 18}},
    "risks": [],
    "next_ranges": {"rsi_period": {"min": 12, "max": 18}},
}


def _make_state(symbol: str = "BTCUSDT", regime: str = "trending_up") -> AgentState:
    state = AgentState()
    state.context["symbol"] = symbol
    state.context["regime_classification"] = {"regime": regime}
    state.opt_insights = _INSIGHTS
    return state


def _obj_record(content: str) -> SimpleNamespace:
    """Simulate a memory record with .content attribute."""
    return SimpleNamespace(content=content)


def _dict_record(content: str) -> dict:
    """Simulate a memory record as dict."""
    return {"content": content, "importance": 0.8}


# ---------------------------------------------------------------------------
# 1-3. Memory hit/miss/error in execute()
# ---------------------------------------------------------------------------


class TestMemoryHitMiss:
    def test_memory_hit_prompt_contains_historical_text(self):
        node = A2AParamRangeNode()
        state = _make_state()
        captured = {}
        historical_text = "rsi_period=14 sl_pct=0.02 sharpe=1.5"

        async def _mock_recall(symbol, regime):
            return [_obj_record(historical_text)]

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured["prompt"] = prompt
            return _RANGES_JSON

        node._recall_opt_params = _mock_recall
        node._call_llm = _mock_llm
        _run(node.execute(state))
        assert historical_text in captured["prompt"]

    def test_memory_miss_no_memory_section(self):
        node = A2AParamRangeNode()
        state = _make_state()
        captured = {}

        async def _mock_recall(symbol, regime):
            return []  # no records

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured["prompt"] = prompt
            return _RANGES_JSON

        node._recall_opt_params = _mock_recall
        node._call_llm = _mock_llm
        _run(node.execute(state))
        assert "Historical optimization memory" not in captured["prompt"]

    def test_memory_recall_error_no_crash(self):
        node = A2AParamRangeNode()
        state = _make_state()

        async def _failing_recall(symbol, regime):
            raise ConnectionError("DB unavailable")

        async def _mock_llm(*a, **kw):
            return _RANGES_JSON

        node._recall_opt_params = _failing_recall
        node._call_llm = _mock_llm
        # Should not raise
        result = _run(node.execute(state))
        assert result is not None


# ---------------------------------------------------------------------------
# 4. _recall_opt_params uses "optimization_params" namespace
# ---------------------------------------------------------------------------


class TestRecallNamespace:
    def test_recall_uses_optimization_params_namespace(self):
        node = A2AParamRangeNode()
        captured_namespace = {}

        async def fake_recall(query, top_k, agent_namespace):
            captured_namespace["ns"] = agent_namespace
            return []

        async def fake_load():
            return 5

        mock_memory = MagicMock()
        mock_memory.recall = fake_recall
        mock_memory.async_load = fake_load

        async def run():
            with (
                patch(
                    "backend.agents.trading_strategy_graph.HierarchicalMemory",
                    return_value=mock_memory,
                )
                if False
                else _noop_ctx()
            ):
                # Directly test _recall_opt_params by calling HierarchicalMemory inline
                pass

        # Test via direct call with patched imports
        async def _inner():
            from unittest.mock import patch as _patch

            with (
                _patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory") as MockHM,
                _patch("backend.agents.memory.backend_interface.SQLiteBackendAdapter"),
            ):
                instance = MockHM.return_value
                instance.async_load = AsyncMock(return_value=5)

                async def _fake_recall(query, top_k, agent_namespace):
                    captured_namespace["ns"] = agent_namespace
                    return []

                instance.recall = _fake_recall
                await node._recall_opt_params("BTCUSDT", "trending_up")

        _run(_inner())
        assert captured_namespace.get("ns") == "optimization_params"


class _noop_ctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


# ---------------------------------------------------------------------------
# 5-9. _format_memory_context
# ---------------------------------------------------------------------------


class TestFormatMemoryContext:
    def test_empty_records_returns_empty_string(self):
        result = A2AParamRangeNode._format_memory_context([])
        assert result == ""

    def test_non_empty_records_returns_non_empty_string(self):
        records = [_obj_record("rsi=14, sharpe=1.5")]
        result = A2AParamRangeNode._format_memory_context(records)
        assert result != ""
        assert "rsi=14" in result

    def test_object_style_records(self):
        records = [_obj_record("period=14"), _obj_record("period=21")]
        result = A2AParamRangeNode._format_memory_context(records)
        assert "period=14" in result

    def test_dict_style_records(self):
        records = [_dict_record("regime=trending rsi=14")]
        result = A2AParamRangeNode._format_memory_context(records)
        assert "rsi=14" in result

    def test_truncates_long_content(self):
        long_content = "x" * 500
        records = [_obj_record(long_content)]
        result = A2AParamRangeNode._format_memory_context(records)
        # Each entry truncated to ≤ 200 chars + "  - " prefix = ≤ 204
        line = [ln for ln in result.split("\n") if "x" in ln][0]
        assert len(line) <= 204


# ---------------------------------------------------------------------------
# 10-11. Prompt memory section header
# ---------------------------------------------------------------------------


class TestPromptMemorySection:
    def test_header_present_when_memory_hit(self):
        node = A2AParamRangeNode()
        state = _make_state()
        captured = {}

        async def _mock_recall(*a):
            return [_obj_record("rsi=14 sharpe=1.5")]

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured["prompt"] = prompt
            return _RANGES_JSON

        node._recall_opt_params = _mock_recall
        node._call_llm = _mock_llm
        _run(node.execute(state))
        assert "Historical optimization memory" in captured["prompt"]

    def test_header_absent_when_memory_miss(self):
        node = A2AParamRangeNode()
        state = _make_state()
        captured = {}

        async def _mock_recall(*a):
            return []

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured["prompt"] = prompt
            return _RANGES_JSON

        node._recall_opt_params = _mock_recall
        node._call_llm = _mock_llm
        _run(node.execute(state))
        assert "Historical optimization memory" not in captured["prompt"]


# ---------------------------------------------------------------------------
# 12. Hints still written even when memory returned records
# ---------------------------------------------------------------------------


class TestHintsWithMemory:
    def test_hints_written_even_with_memory_hit(self):
        node = A2AParamRangeNode()
        state = _make_state()

        async def _mock_recall(*a):
            return [_obj_record("rsi=14 sharpe=1.5")]

        async def _mock_llm(*a, **kw):
            return _RANGES_JSON

        node._recall_opt_params = _mock_recall
        node._call_llm = _mock_llm
        result = _run(node.execute(state))
        assert "agent_optimization_hints" in result.context
        assert "ranges" in result.context["agent_optimization_hints"]


# ---------------------------------------------------------------------------
# 13-14. MemoryUpdateNode saves to optimization_params based on sharpe
# ---------------------------------------------------------------------------


class TestMemoryUpdateOptParams:
    def _make_update_state(self, sharpe: float, best_params: dict) -> AgentState:
        state = AgentState()
        state.context["symbol"] = "BTCUSDT"
        state.context["timeframe"] = "15"
        state.context["regime_classification"] = {"regime": "trending_up"}
        state.set_result(
            "backtest",
            {
                "metrics": {
                    "sharpe_ratio": sharpe,
                    "max_drawdown": 10.0,
                    "total_trades": 30,
                    "win_rate": 0.55,
                    "profit_factor": 1.3,
                }
            },
        )
        state.set_result("select_best", {"selected_agent": "claude", "selected_strategy": None})
        state.set_result(
            "optimize_strategy",
            {"best_params": best_params, "best_sharpe": sharpe},
        )
        return state

    def test_saves_to_opt_params_when_sharpe_above_threshold(self):
        from backend.agents.trading_strategy_graph import MemoryUpdateNode

        node = MemoryUpdateNode()
        state = self._make_update_state(sharpe=1.5, best_params={"rsi_period": 14})
        saved_namespaces = []

        async def fake_store(**kwargs):
            saved_namespaces.append(kwargs.get("agent_namespace"))

        async def _inner():
            from unittest.mock import patch as _patch

            with (
                _patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory") as MockHM,
                _patch("backend.agents.memory.backend_interface.SQLiteBackendAdapter"),
                _patch.object(node, "_save_to_db", return_value=None),
            ):
                instance = MockHM.return_value
                instance.store = fake_store
                instance.async_load = AsyncMock(return_value=0)
                await node.execute(state)

        _run(_inner())
        assert "optimization_params" in saved_namespaces

    def test_does_not_save_to_opt_params_when_sharpe_below_threshold(self):
        from backend.agents.trading_strategy_graph import MemoryUpdateNode

        node = MemoryUpdateNode()
        state = self._make_update_state(sharpe=0.1, best_params={"rsi_period": 14})
        saved_namespaces = []

        async def fake_store(**kwargs):
            saved_namespaces.append(kwargs.get("agent_namespace"))

        async def _inner():
            from unittest.mock import patch as _patch

            with (
                _patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory") as MockHM,
                _patch("backend.agents.memory.backend_interface.SQLiteBackendAdapter"),
                _patch.object(node, "_save_to_db", return_value=None),
            ):
                instance = MockHM.return_value
                instance.store = fake_store
                instance.async_load = AsyncMock(return_value=0)
                await node.execute(state)

        _run(_inner())
        assert "optimization_params" not in saved_namespaces
