"""
Tests that _build_block_catalog() is actually injected into agent prompts.

Uses mock A2A communicator to capture the exact prompts sent to agents
without making real LLM API calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.workflows.builder_workflow import BuilderWorkflow

# ── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_BLOCKS = [
    {"id": "rsi_1", "type": "rsi", "params": {"period": 14, "cross_long_level": 45}},
    {"id": "static_sltp_1", "type": "static_sltp", "params": {"stop_loss_percent": 2.0, "take_profit_percent": 4.0}},
    {"id": "strategy_node", "type": "strategy", "params": {}},
]

SAMPLE_CONNECTIONS = [
    {
        "id": "conn_1",
        "source": {"blockId": "rsi_1", "portId": "long"},
        "target": {"blockId": "strategy_node", "portId": "entry_long"},
    },
    {
        "id": "conn_2",
        "source": {"blockId": "static_sltp_1", "portId": "sl_tp"},
        "target": {"blockId": "strategy_node", "portId": "sl_tp"},
    },
]

SAMPLE_METRICS = {
    "sharpe_ratio": -0.5,
    "win_rate": 38.0,
    "total_trades": 120,
    "max_drawdown": 25.0,
    "net_profit": -500.0,
}


def make_workflow() -> BuilderWorkflow:
    wf = BuilderWorkflow.__new__(BuilderWorkflow)
    wf._on_agent_log = None
    wf._primary_agent = "claude"

    from backend.agents.workflows.builder_workflow import BuilderWorkflowResult

    wf._result = BuilderWorkflowResult(
        workflow_id="test_wf",
        config={},
        started_at="2026-01-01T00:00:00Z",
        used_optimizer_mode=True,
    )
    return wf


# ── Tests: _suggest_topology_changes prompt ──────────────────────────────────


@pytest.mark.asyncio
async def test_topology_prompt_contains_catalog():
    """_suggest_topology_changes must inject full block catalog into the prompt."""
    wf = make_workflow()

    captured_prompt = []

    async def fake_parallel_consensus(question, agents, context=None):
        captured_prompt.append(question)
        return {"individual_responses": [{"agent": "claude", "content": "[]"}], "consensus": "[]"}

    mock_a2a = MagicMock()
    mock_a2a.parallel_consensus = fake_parallel_consensus

    with (
        patch("backend.agents.workflows.builder_workflow._get_a2a_communicator", return_value=mock_a2a),
        patch(
            "os.environ.get",
            side_effect=lambda k, d=None: "fake_key" if k in ("ANTHROPIC_API_KEY", "PERPLEXITY_API_KEY") else d,
        ),
    ):
        result = await wf._suggest_topology_changes(
            blocks=SAMPLE_BLOCKS,
            connections=SAMPLE_CONNECTIONS,
            metrics=SAMPLE_METRICS,
            iteration=1,
        )

    assert len(captured_prompt) == 1, "Expected exactly one parallel_consensus call"
    prompt = captured_prompt[0]

    # Catalog must be in the prompt
    assert "FULL BLOCK CATALOG" in prompt, "Catalog header missing from topology prompt"
    assert "ENTRY SIGNALS" in prompt, "Category header missing"
    assert "FILTER" in prompt, "Filter category missing"
    assert "EXIT BLOCKS" in prompt, "Exit category missing"

    # Must include non-RSI blocks
    for block in [
        "macd",
        "stochastic",
        "supertrend",
        "qqe",
        "keltner_bollinger",
        "atr_volatility",
        "volume_filter",
        "mfi_filter",
        "two_ma_filter",
        "close_rsi",
        "chandelier_exit",
        "break_even_exit",
    ]:
        assert block in prompt, f"Block '{block}' missing from topology prompt"

    # Port semantics must be there
    assert "OR-gate" in prompt
    assert "AND-gate" in prompt
    assert "filter_long" in prompt


@pytest.mark.asyncio
async def test_topology_prompt_has_over_trading_diagnosis():
    """When >100 trades + low WR, prompt must have over-trading diagnosis."""
    wf = make_workflow()
    captured = []

    async def fake_parallel_consensus(question, agents, context=None):
        captured.append(question)
        return {"individual_responses": [{"agent": "claude", "content": "[]"}], "consensus": "[]"}

    mock_a2a = MagicMock()
    mock_a2a.parallel_consensus = fake_parallel_consensus

    bad_metrics = dict(SAMPLE_METRICS, total_trades=180, win_rate=28.0, sharpe_ratio=-1.2)
    with (
        patch("backend.agents.workflows.builder_workflow._get_a2a_communicator", return_value=mock_a2a),
        patch(
            "os.environ.get",
            side_effect=lambda k, d=None: "fake_key" if k in ("ANTHROPIC_API_KEY", "PERPLEXITY_API_KEY") else d,
        ),
    ):
        await wf._suggest_topology_changes(
            blocks=SAMPLE_BLOCKS,
            connections=SAMPLE_CONNECTIONS,
            metrics=bad_metrics,
            iteration=1,
        )

    prompt = captured[0]
    assert "OVER-TRADING" in prompt or "over-trad" in prompt.lower()
    assert "OR-gate" in prompt


# ── Tests: _suggest_param_ranges prompt ──────────────────────────────────────


@pytest.mark.asyncio
async def test_param_ranges_prompt_contains_catalog():
    """_suggest_param_ranges must inject full block catalog into the prompt."""
    wf = make_workflow()
    captured = []

    async def fake_parallel_consensus(question, agents, context):
        captured.append(question)
        return {
            "individual_responses": [
                {
                    "agent": "claude",
                    "content": json.dumps(
                        [{"block_id": "rsi_1", "ranges": {"period": {"min": 7, "max": 50, "step": 1, "type": "int"}}}]
                    ),
                }
            ]
        }

    mock_a2a = MagicMock()
    mock_a2a.parallel_consensus = fake_parallel_consensus

    with (
        patch("backend.agents.workflows.builder_workflow._get_a2a_communicator", return_value=mock_a2a),
        patch("backend.agents.workflows.builder_workflow._get_workflow_memory") as mock_mem,
        patch(
            "os.environ.get",
            side_effect=lambda k, d=None: "fake_key" if k in ("ANTHROPIC_API_KEY", "PERPLEXITY_API_KEY") else d,
        ),
    ):
        mock_mem.return_value.recall = AsyncMock(return_value=[])
        result = await wf._suggest_param_ranges(
            blocks_added=SAMPLE_BLOCKS,
            iteration=1,
            metrics=SAMPLE_METRICS,
            connections=SAMPLE_CONNECTIONS,
        )

    assert len(captured) == 1, "Expected one A2A consensus call"
    prompt = captured[0]

    # Catalog must appear
    assert "FULL BLOCK CATALOG" in prompt, "Catalog missing from param_ranges prompt"
    assert "ENTRY SIGNALS" in prompt
    assert "FILTER" in prompt

    # Must distinguish strategy blocks from full catalog
    assert "currently in THIS strategy" in prompt or "Blocks currently" in prompt

    # Non-RSI blocks must be visible
    for block in ["macd", "qqe", "keltner_bollinger", "mfi_filter", "chandelier_exit"]:
        assert block in prompt, f"Block '{block}' missing from param_ranges prompt"


@pytest.mark.asyncio
async def test_param_ranges_prompt_strategy_blocks_separate_from_catalog():
    """Strategy's own blocks must be listed separately from the full catalog."""
    wf = make_workflow()
    captured = []

    async def fake_parallel_consensus(question, agents, context):
        captured.append(question)
        return {"individual_responses": [{"agent": "claude", "content": "[]"}]}

    mock_a2a = MagicMock()
    mock_a2a.parallel_consensus = fake_parallel_consensus

    with (
        patch("backend.agents.workflows.builder_workflow._get_a2a_communicator", return_value=mock_a2a),
        patch("backend.agents.workflows.builder_workflow._get_workflow_memory") as mock_mem,
        patch(
            "os.environ.get",
            side_effect=lambda k, d=None: "fake_key" if k in ("ANTHROPIC_API_KEY", "PERPLEXITY_API_KEY") else d,
        ),
    ):
        mock_mem.return_value.recall = AsyncMock(return_value=[])
        await wf._suggest_param_ranges(
            blocks_added=SAMPLE_BLOCKS,
            iteration=1,
            metrics=SAMPLE_METRICS,
            connections=SAMPLE_CONNECTIONS,
        )

    prompt = captured[0]
    # Should have TWO sections: current strategy blocks + full catalog
    assert "rsi_1" in prompt  # strategy block ID
    assert "static_sltp_1" in prompt  # strategy block ID
    # And also blocks NOT in the strategy
    assert "macd" in prompt
    assert "keltner_bollinger" in prompt
