import pytest
from pydantic import ValidationError

from backend.agents.api_models import (
    AgentSendRequest,
    ConsensusRequest,
    ConversationStartRequest,
)


def test_consensus_request_duplicate_agents():
    with pytest.raises(ValidationError) as exc:
        ConsensusRequest(
            question="What is the best RSI period?",
            agents=["deepseek", "deepseek"],
        )
    # Ensure our custom message is present
    assert "Duplicate agents not allowed" in str(exc.value)


def test_consensus_request_unknown_agent():
    with pytest.raises(ValidationError) as exc:
        ConsensusRequest(
            question="Edge case check for agent validation",
            agents=["deepseek", "unknown_ai"],
        )
    assert "Unknown agent: unknown_ai" in str(exc.value)


def test_agent_send_request_whitespace_content():
    with pytest.raises(ValidationError) as exc:
        AgentSendRequest(
            from_agent="copilot",
            to_agent="deepseek",
            content="   \t  ",
        )
    assert "Content cannot be empty or whitespace only" in str(exc.value)


def test_agent_send_request_whitespace_from_to_agents():
    # from_agent whitespace-only
    with pytest.raises(ValidationError) as exc1:
        AgentSendRequest(
            from_agent="   ",
            to_agent="deepseek",
            content="Hello",
        )
    assert "from_agent cannot be empty or whitespace only" in str(exc1.value)

    # to_agent whitespace-only
    with pytest.raises(ValidationError) as exc2:
        AgentSendRequest(
            from_agent="copilot",
            to_agent="   \n\t",
            content="Hello",
        )
    assert "to_agent cannot be empty or whitespace only" in str(exc2.value)


def test_conversation_start_request_duplicate_participants():
    with pytest.raises(ValidationError) as exc:
        ConversationStartRequest(
            initial_message="Let's talk about scalping strategies",
            participants=["deepseek", "deepseek"],
        )
    assert "Duplicate participants not allowed" in str(exc.value)


def test_conversation_start_request_whitespace_participants():
    # Includes empty/whitespace-only items that should be rejected
    with pytest.raises(ValidationError) as exc:
        ConversationStartRequest(
            initial_message="Discuss trend following vs mean reversion",
            participants=["deepseek", "   \t   "],
        )
    assert "Participant names cannot be empty or whitespace only" in str(exc.value)
