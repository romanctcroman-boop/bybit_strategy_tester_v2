"""
Full-pipeline integration test: Communicator → Consensus → RiskVeto.

Verifies the three-agent communication flow end-to-end with mocked LLM
responses, ensuring signals propagate through consensus and risk veto
correctly.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.agent_to_agent_communicator import (
    AgentMessage,
    AgentToAgentCommunicator,
)
from backend.agents.consensus.risk_veto_guard import (
    RiskVetoGuard,
    VetoConfig,
    VetoReason,
)
from backend.agents.interface import AgentResponse
from backend.agents.models import AgentType, CommunicationPattern, MessageType
from backend.agents.unified_agent_interface import AgentChannel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_redis():
    """AsyncMock Redis that always allows conversation (no loop)."""
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    redis.setex = AsyncMock()
    return redis


@pytest.fixture()
def mock_agent_interface():
    """AgentInterface mock that returns a canned successful response."""

    def _make_response(content: str = "Analysis complete", **kwargs):
        return AgentResponse(
            success=True,
            content=content,
            channel=AgentChannel.DIRECT_API,
            latency_ms=42,
        )

    interface = MagicMock()
    interface.send_request = AsyncMock(side_effect=lambda req, **kw: _make_response())
    return interface


@pytest.fixture()
def communicator(mock_agent_interface, mock_redis):
    """Communicator wired to mock interface & Redis."""
    with patch(
        "backend.agents.agent_to_agent_communicator.get_agent_interface",
        return_value=mock_agent_interface,
    ):
        comm = AgentToAgentCommunicator()
        comm.redis_client = mock_redis
        return comm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCommunicatorThreeAgentRouting:
    """All four handler types are callable and return valid AgentMessages."""

    @pytest.mark.asyncio
    async def test_route_to_deepseek(self, communicator):
        msg = _make_msg(to_agent=AgentType.DEEPSEEK)
        resp = await communicator.route_message(msg)
        assert resp.from_agent == AgentType.DEEPSEEK
        assert resp.message_type == MessageType.RESPONSE
        assert resp.confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_route_to_qwen(self, communicator):
        msg = _make_msg(to_agent=AgentType.QWEN)
        resp = await communicator.route_message(msg)
        assert resp.from_agent == AgentType.QWEN
        assert resp.message_type == MessageType.RESPONSE
        assert resp.confidence_score == 0.85

    @pytest.mark.asyncio
    async def test_route_to_perplexity(self, communicator):
        msg = _make_msg(to_agent=AgentType.PERPLEXITY)
        resp = await communicator.route_message(msg)
        assert resp.from_agent == AgentType.PERPLEXITY
        assert resp.message_type == MessageType.RESPONSE
        assert resp.confidence_score == 0.85

    @pytest.mark.asyncio
    async def test_route_to_copilot_disabled(self, communicator):
        msg = _make_msg(to_agent=AgentType.COPILOT)
        resp = await communicator.route_message(msg)
        assert resp.from_agent == AgentType.COPILOT
        assert resp.metadata["status"] == "disabled"
        assert resp.confidence_score == 0.0


class TestParallelConsensus:
    """parallel_consensus gathers responses from multiple agents."""

    @pytest.mark.asyncio
    async def test_consensus_three_agents(self, communicator):
        result = await communicator.parallel_consensus(
            question="Should we enter long on BTCUSDT?",
            agents=[AgentType.DEEPSEEK, AgentType.QWEN, AgentType.PERPLEXITY],
            context={"symbol": "BTCUSDT"},
        )

        assert "consensus" in result
        assert len(result["individual_responses"]) == 3
        agents_seen = {r["agent"] for r in result["individual_responses"]}
        assert agents_seen == {"deepseek", "qwen", "perplexity"}
        assert 0.0 <= result["confidence_score"] <= 1.0


class TestConsensusToRiskVeto:
    """End-to-end: consensus result feeds into RiskVetoGuard."""

    @pytest.mark.asyncio
    async def test_high_consensus_passes_veto(self, communicator):
        """When agreement_score is high and equity is healthy → no veto."""
        result = await communicator.parallel_consensus(
            question="Enter long?",
            agents=[AgentType.DEEPSEEK, AgentType.QWEN],
        )

        guard = RiskVetoGuard(VetoConfig(enabled=True))
        decision = guard.check(
            portfolio_equity=10_000,
            peak_equity=10_000,
            open_positions=0,
            daily_pnl=50,
            initial_daily_equity=10_000,
            agreement_score=result["confidence_score"],
        )

        assert not decision.is_vetoed

    def test_drawdown_triggers_veto(self):
        """Drawdown exceeding limit blocks trade regardless of consensus."""
        guard = RiskVetoGuard(VetoConfig(enabled=True, max_drawdown_pct=10))
        decision = guard.check(
            portfolio_equity=8_000,
            peak_equity=10_000,  # 20% drawdown
            agreement_score=0.95,
        )

        assert decision.is_vetoed
        assert VetoReason.DRAWDOWN_EXCEEDED in decision.reasons

    def test_max_positions_triggers_veto(self):
        """Too many open positions blocks trade."""
        guard = RiskVetoGuard(VetoConfig(enabled=True, max_open_positions=5))
        decision = guard.check(
            portfolio_equity=10_000,
            peak_equity=10_000,
            open_positions=5,
            agreement_score=0.90,
        )

        assert decision.is_vetoed
        assert VetoReason.MAX_POSITIONS_EXCEEDED in decision.reasons

    def test_low_consensus_triggers_veto(self):
        """Low agreement score blocks trade."""
        guard = RiskVetoGuard(VetoConfig(enabled=True, min_agreement_score=0.6))
        decision = guard.check(
            portfolio_equity=10_000,
            peak_equity=10_000,
            agreement_score=0.3,
        )

        assert decision.is_vetoed
        assert VetoReason.LOW_AGREEMENT in decision.reasons

    def test_disabled_guard_never_vetoes(self):
        guard = RiskVetoGuard(VetoConfig(enabled=False))
        decision = guard.check(
            portfolio_equity=1,
            peak_equity=100_000,
            open_positions=999,
            agreement_score=0.0,
        )
        assert not decision.is_vetoed


class TestMultiTurnRotation:
    """_determine_next_message follows DeepSeek→Qwen→Perplexity cycle."""

    @pytest.mark.asyncio
    async def test_rotation_order(self, communicator):
        agents_order = [AgentType.DEEPSEEK, AgentType.QWEN, AgentType.PERPLEXITY]
        current = _make_msg(from_agent=AgentType.DEEPSEEK, to_agent=AgentType.ORCHESTRATOR)

        for expected_next in [AgentType.QWEN, AgentType.PERPLEXITY, AgentType.DEEPSEEK]:
            nxt = await communicator._determine_next_message(current, CommunicationPattern.COLLABORATIVE, [])
            assert nxt.to_agent == expected_next
            current = _make_msg(from_agent=expected_next, to_agent=AgentType.ORCHESTRATOR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_msg(
    *,
    from_agent: AgentType = AgentType.ORCHESTRATOR,
    to_agent: AgentType = AgentType.DEEPSEEK,
    content: str = "Test message",
) -> AgentMessage:
    return AgentMessage(
        message_id=str(uuid.uuid4()),
        from_agent=from_agent,
        to_agent=to_agent,
        message_type=MessageType.QUERY,
        content=content,
        context={},
        conversation_id=str(uuid.uuid4()),
    )
