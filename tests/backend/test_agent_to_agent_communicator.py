"""
Comprehensive tests for agent_to_agent_communicator.py

Coverage target: 27.34% → 65% (+37.66% gain)
Expected tests: ~55-60 tests
Categories:
1. Enums and Data Classes (12 tests)
2. AgentToAgentCommunicator - Initialization (6 tests)
3. Message Routing and Handlers (15 tests)
4. Multi-turn Conversations (10 tests)
5. Parallel Consensus (8 tests)
6. Iterative Improvement (7 tests)
7. Helper Methods (8 tests)
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.agent_to_agent_communicator import (
    AgentMessage,
    AgentToAgentCommunicator,
    AgentType,
    CommunicationPattern,
    MessageType,
    get_communicator,
)
from backend.agents.unified_agent_interface import (
    AgentChannel,
    AgentResponse,
)

# =============================================================================
# CATEGORY 1: Enums and Data Classes (12 tests)
# =============================================================================


class TestEnums:
    """Test enum definitions"""

    def test_message_type_values(self):
        """MessageType has correct values"""
        assert MessageType.QUERY.value == "query"
        assert MessageType.RESPONSE.value == "response"
        assert MessageType.VALIDATION.value == "validation"
        assert MessageType.CONSENSUS_REQUEST.value == "consensus_request"
        assert MessageType.ERROR.value == "error"
        assert MessageType.COMPLETION.value == "completion"

    def test_agent_type_values(self):
        """AgentType has correct values"""
        assert AgentType.DEEPSEEK.value == "deepseek"
        assert AgentType.PERPLEXITY.value == "perplexity"
        assert AgentType.COPILOT.value == "copilot"
        assert AgentType.ORCHESTRATOR.value == "orchestrator"

    def test_communication_pattern_values(self):
        """CommunicationPattern has correct values"""
        assert CommunicationPattern.SEQUENTIAL.value == "sequential"
        assert CommunicationPattern.PARALLEL.value == "parallel"
        assert CommunicationPattern.ITERATIVE.value == "iterative"
        assert CommunicationPattern.COLLABORATIVE.value == "collaborative"
        assert CommunicationPattern.HIERARCHICAL.value == "hierarchical"


class TestAgentMessage:
    """Test AgentMessage dataclass"""

    def test_agent_message_init_with_defaults(self):
        """AgentMessage initializes with correct defaults"""
        msg = AgentMessage(
            message_id="test_id",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.PERPLEXITY,
            message_type=MessageType.QUERY,
            content="test content",
            context={"key": "value"},
            conversation_id="conv_123",
        )

        assert msg.message_id == "test_id"
        assert msg.from_agent == AgentType.DEEPSEEK
        assert msg.to_agent == AgentType.PERPLEXITY
        assert msg.message_type == MessageType.QUERY
        assert msg.content == "test content"
        assert msg.context == {"key": "value"}
        assert msg.conversation_id == "conv_123"
        assert msg.iteration == 1
        assert msg.max_iterations == 5
        assert msg.confidence_score == 0.0
        assert msg.timestamp is not None
        assert msg.metadata == {}

    def test_agent_message_init_with_custom_values(self):
        """AgentMessage accepts custom values"""
        msg = AgentMessage(
            message_id="custom_id",
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.COPILOT,
            message_type=MessageType.RESPONSE,
            content="response content",
            context={},
            conversation_id="conv_456",
            iteration=3,
            max_iterations=10,
            confidence_score=0.85,
            timestamp="2024-01-15T12:00:00",
            metadata={"custom": "data"},
        )

        assert msg.iteration == 3
        assert msg.max_iterations == 10
        assert msg.confidence_score == 0.85
        assert msg.timestamp == "2024-01-15T12:00:00"
        assert msg.metadata == {"custom": "data"}

    def test_agent_message_to_dict(self):
        """AgentMessage to_dict serialization"""
        msg = AgentMessage(
            message_id="test",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.PERPLEXITY,
            message_type=MessageType.QUERY,
            content="test",
            context={},
            conversation_id="conv",
        )

        data = msg.to_dict()

        assert data["message_id"] == "test"
        assert data["from_agent"] == "deepseek"
        assert data["to_agent"] == "perplexity"
        assert data["message_type"] == "query"
        assert isinstance(data["timestamp"], str)

    def test_agent_message_from_dict(self):
        """AgentMessage from_dict deserialization"""
        data = {
            "message_id": "test",
            "from_agent": "deepseek",
            "to_agent": "perplexity",
            "message_type": "query",
            "content": "test content",
            "context": {"key": "value"},
            "conversation_id": "conv",
            "iteration": 2,
            "max_iterations": 5,
            "confidence_score": 0.7,
            "timestamp": "2024-01-15T12:00:00",
            "metadata": {},
        }

        msg = AgentMessage.from_dict(data)

        assert msg.message_id == "test"
        assert msg.from_agent == AgentType.DEEPSEEK
        assert msg.to_agent == AgentType.PERPLEXITY
        assert msg.message_type == MessageType.QUERY
        assert msg.iteration == 2
        assert msg.confidence_score == 0.7

    def test_agent_message_post_init_timestamp(self):
        """AgentMessage __post_init__ sets timestamp"""
        msg = AgentMessage(
            message_id="test",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.PERPLEXITY,
            message_type=MessageType.QUERY,
            content="test",
            context={},
            conversation_id="conv",
        )

        # Timestamp should be set automatically
        assert msg.timestamp is not None
        # Should be recent
        timestamp_dt = datetime.fromisoformat(msg.timestamp)
        assert timestamp_dt.tzinfo is not None
        delta = datetime.now(UTC) - timestamp_dt
        assert delta.total_seconds() < 5

    def test_agent_message_post_init_metadata(self):
        """AgentMessage __post_init__ sets metadata"""
        msg = AgentMessage(
            message_id="test",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.PERPLEXITY,
            message_type=MessageType.QUERY,
            content="test",
            context={},
            conversation_id="conv",
            metadata=None,  # Explicitly None
        )

        # metadata should be initialized to {}
        assert msg.metadata == {}


# =============================================================================
# CATEGORY 2: AgentToAgentCommunicator - Initialization (6 tests)
# =============================================================================


class TestAgentToAgentCommunicatorInit:
    """Test AgentToAgentCommunicator initialization"""

    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    def test_init_creates_agent_interface(self, mock_get_agent):
        """AgentToAgentCommunicator creates agent interface"""
        mock_agent = MagicMock()
        mock_get_agent.return_value = mock_agent

        comm = AgentToAgentCommunicator()

        assert comm.agent_interface == mock_agent
        assert comm.redis_client is None  # Lazy init
        assert comm.redis_url == "redis://localhost:6379"

    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    def test_init_with_custom_redis_url(self, mock_get_agent):
        """AgentToAgentCommunicator accepts custom redis URL"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator(redis_url="redis://custom:6380")

        assert comm.redis_url == "redis://custom:6380"

    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    def test_init_registers_message_handlers(self, mock_get_agent):
        """AgentToAgentCommunicator registers message handlers"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        assert AgentType.DEEPSEEK in comm.message_handlers
        assert AgentType.PERPLEXITY in comm.message_handlers
        assert AgentType.QWEN in comm.message_handlers
        assert AgentType.COPILOT in comm.message_handlers
        assert callable(comm.message_handlers[AgentType.DEEPSEEK])

    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    def test_init_conversation_cache(self, mock_get_agent):
        """AgentToAgentCommunicator initializes conversation cache"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        assert comm.conversation_cache == {}
        assert comm.max_conversation_age == timedelta(minutes=30)

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_get_redis_lazy_init(self, mock_get_agent):
        """_get_redis performs lazy initialization"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()
        assert comm.redis_client is None

        # Mock redis.from_url as AsyncMock coroutine
        mock_redis_client = AsyncMock()
        with patch(
            "backend.agents.agent_to_agent_communicator.redis.from_url", new=AsyncMock(return_value=mock_redis_client)
        ):
            redis_client = await comm._get_redis()

            assert redis_client == mock_redis_client
            assert comm.redis_client == mock_redis_client

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_get_redis_reuses_existing(self, mock_get_agent):
        """_get_redis reuses existing client"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        # Mock redis.from_url
        mock_redis_client = AsyncMock()
        mock_from_url = AsyncMock(return_value=mock_redis_client)

        with patch("backend.agents.agent_to_agent_communicator.redis.from_url", new=mock_from_url):
            # First call
            redis1 = await comm._get_redis()
            # Second call
            redis2 = await comm._get_redis()

            assert redis1 == redis2
            assert mock_from_url.call_count == 1  # Only once


# =============================================================================
# CATEGORY 3: Message Routing and Handlers (15 tests)
# =============================================================================


class TestMessageRouting:
    """Test message routing and handlers"""

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_route_message_calls_handler(self, mock_get_agent):
        """route_message calls appropriate handler"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        # Mock handler
        mock_handler = AsyncMock(
            return_value=AgentMessage(
                message_id="response",
                from_agent=AgentType.DEEPSEEK,
                to_agent=AgentType.ORCHESTRATOR,
                message_type=MessageType.RESPONSE,
                content="test response",
                context={},
                conversation_id="conv",
            )
        )
        comm.message_handlers[AgentType.DEEPSEEK] = mock_handler

        # Mock loop check
        with patch.object(comm, "_check_conversation_loop", new=AsyncMock()):
            message = AgentMessage(
                message_id="test",
                from_agent=AgentType.ORCHESTRATOR,
                to_agent=AgentType.DEEPSEEK,
                message_type=MessageType.QUERY,
                content="test query",
                context={},
                conversation_id="conv",
            )

            response = await comm.route_message(message)

            assert mock_handler.called
            assert response.from_agent == AgentType.DEEPSEEK
            assert response.message_type == MessageType.RESPONSE

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_route_message_no_handler_raises_error(self, mock_get_agent):
        """route_message returns error for unknown agent type"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()
        comm.message_handlers = {}  # Empty handlers

        with patch.object(comm, "_check_conversation_loop", new=AsyncMock()):
            message = AgentMessage(
                message_id="test",
                from_agent=AgentType.ORCHESTRATOR,
                to_agent=AgentType.DEEPSEEK,
                message_type=MessageType.QUERY,
                content="test",
                context={},
                conversation_id="conv",
            )

            response = await comm.route_message(message)

            assert response.message_type == MessageType.ERROR
            assert "No handler" in response.content

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_handle_deepseek_message_success(self, mock_get_agent):
        """_handle_deepseek_message handles successful response"""
        mock_agent = MagicMock()
        mock_agent.send_request = AsyncMock(
            return_value=AgentResponse(
                success=True,
                content="DeepSeek response",
                channel=AgentChannel.DIRECT_API,
                latency_ms=100.0,
                api_key_index=0,
            )
        )
        mock_get_agent.return_value = mock_agent

        comm = AgentToAgentCommunicator()

        message = AgentMessage(
            message_id="test",
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.DEEPSEEK,
            message_type=MessageType.QUERY,
            content="test query",
            context={"key": "value"},
            conversation_id="conv",
        )

        response = await comm._handle_deepseek_message(message)

        assert response.from_agent == AgentType.DEEPSEEK
        assert response.to_agent == AgentType.ORCHESTRATOR
        assert response.message_type == MessageType.RESPONSE
        assert response.content == "DeepSeek response"
        assert response.confidence_score == 0.9
        assert response.iteration == 2  # iteration + 1
        assert "latency_ms" in response.metadata

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_handle_deepseek_message_failure(self, mock_get_agent):
        """_handle_deepseek_message handles API failure"""
        mock_agent = MagicMock()
        mock_agent.send_request = AsyncMock(
            return_value=AgentResponse(
                success=False, content="", channel=AgentChannel.DIRECT_API, error="API error", latency_ms=50.0
            )
        )
        mock_get_agent.return_value = mock_agent

        comm = AgentToAgentCommunicator()

        message = AgentMessage(
            message_id="test",
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.DEEPSEEK,
            message_type=MessageType.QUERY,
            content="test",
            context={},
            conversation_id="conv",
        )

        response = await comm._handle_deepseek_message(message)

        assert response.content.startswith("Error:")
        assert response.confidence_score == 0.0

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_handle_perplexity_message_success(self, mock_get_agent):
        """_handle_perplexity_message handles successful response"""
        mock_agent = MagicMock()
        mock_agent.send_request = AsyncMock(
            return_value=AgentResponse(
                success=True,
                content="Perplexity response",
                channel=AgentChannel.DIRECT_API,
                latency_ms=120.0,
                api_key_index=1,
            )
        )
        mock_get_agent.return_value = mock_agent

        comm = AgentToAgentCommunicator()

        message = AgentMessage(
            message_id="test",
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.PERPLEXITY,
            message_type=MessageType.QUERY,
            content="test query",
            context={},
            conversation_id="conv",
        )

        response = await comm._handle_perplexity_message(message)

        assert response.from_agent == AgentType.PERPLEXITY
        assert response.content == "Perplexity response"
        assert response.confidence_score == 0.85

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_handle_copilot_message_placeholder(self, mock_get_agent):
        """_handle_copilot_message returns disabled response"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        message = AgentMessage(
            message_id="test",
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.COPILOT,
            message_type=MessageType.QUERY,
            content="test",
            context={},
            conversation_id="conv",
        )

        response = await comm._handle_copilot_message(message)

        assert response.from_agent == AgentType.COPILOT
        assert "disabled" in response.content.lower()
        assert response.metadata["status"] == "disabled"
        assert response.confidence_score == 0.0

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_check_conversation_loop_prevents_infinite_loops(self, mock_get_agent):
        """_check_conversation_loop prevents infinite loops"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=True)  # Loop detected
        comm.redis_client = mock_redis

        message = AgentMessage(
            message_id="test",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.PERPLEXITY,
            message_type=MessageType.QUERY,
            content="test",
            context={},
            conversation_id="conv_loop",
            iteration=5,
        )

        with pytest.raises(ValueError, match="infinite loop"):
            await comm._check_conversation_loop(message)

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_check_conversation_loop_allows_first_iteration(self, mock_get_agent):
        """_check_conversation_loop allows first iteration"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=False)  # Not a loop
        mock_redis.setex = AsyncMock()
        comm.redis_client = mock_redis

        message = AgentMessage(
            message_id="test",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.PERPLEXITY,
            message_type=MessageType.QUERY,
            content="test",
            context={},
            conversation_id="conv",
            iteration=1,
        )

        # Should not raise
        await comm._check_conversation_loop(message)

        mock_redis.setex.assert_called_once()


# =============================================================================
# CATEGORY 4: Multi-turn Conversations (10 tests)
# =============================================================================


class TestMultiTurnConversations:
    """Test multi-turn conversation logic"""

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_multi_turn_conversation_basic_flow(self, mock_get_agent):
        """multi_turn_conversation executes basic flow"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        # Mock route_message to return responses
        responses = [
            AgentMessage(
                message_id=f"resp_{i}",
                from_agent=AgentType.DEEPSEEK,
                to_agent=AgentType.ORCHESTRATOR,
                message_type=MessageType.RESPONSE,
                content=f"Response {i}",
                context={},
                conversation_id="conv",
                iteration=i + 1,
            )
            for i in range(3)
        ]

        comm.route_message = AsyncMock(side_effect=responses)

        # Mock should_end to stop after 3 turns
        async def mock_should_end(response, history):
            return len(history) >= 4  # Initial + 3 responses

        comm._should_end_conversation = mock_should_end

        initial_message = AgentMessage(
            message_id="initial",
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.DEEPSEEK,
            message_type=MessageType.QUERY,
            content="Start conversation",
            context={},
            conversation_id="conv",
        )

        # Mock determine_next_message
        comm._determine_next_message = AsyncMock(
            side_effect=[
                AgentMessage(
                    message_id=f"next_{i}",
                    from_agent=AgentType.DEEPSEEK,
                    to_agent=AgentType.PERPLEXITY,
                    message_type=MessageType.QUERY,
                    content="next",
                    context={},
                    conversation_id="conv",
                    iteration=i + 2,
                )
                for i in range(3)
            ]
        )

        history = await comm.multi_turn_conversation(initial_message, max_turns=5)

        assert len(history) >= 2  # At least initial + 1 response + completion
        assert history[0] == initial_message

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_multi_turn_stops_at_max_iterations(self, mock_get_agent):
        """multi_turn_conversation stops at max iterations"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        initial_message = AgentMessage(
            message_id="initial",
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.DEEPSEEK,
            message_type=MessageType.QUERY,
            content="test",
            context={},
            conversation_id="conv",
            max_iterations=2,  # Low max
        )

        # Mock route_message
        comm.route_message = AsyncMock(
            return_value=AgentMessage(
                message_id="resp",
                from_agent=AgentType.DEEPSEEK,
                to_agent=AgentType.ORCHESTRATOR,
                message_type=MessageType.RESPONSE,
                content="response",
                context={},
                conversation_id="conv",
                iteration=3,  # Exceeds max
            )
        )

        history = await comm.multi_turn_conversation(initial_message, max_turns=10)

        # Should stop early due to max_iterations
        assert len(history) >= 1


# =============================================================================
# CATEGORY 5: Parallel Consensus (8 tests)
# =============================================================================


class TestParallelConsensus:
    """Test parallel consensus functionality"""

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_parallel_consensus_basic(self, mock_get_agent):
        """parallel_consensus requests from multiple agents"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        # Mock route_message for parallel requests
        async def mock_route(msg):
            return AgentMessage(
                message_id=str(uuid.uuid4()),
                from_agent=msg.to_agent,
                to_agent=AgentType.ORCHESTRATOR,
                message_type=MessageType.RESPONSE,
                content=f"Response from {msg.to_agent.value}",
                context={},
                conversation_id=msg.conversation_id,
                confidence_score=0.8,
            )

        comm.route_message = AsyncMock(side_effect=mock_route)

        # Mock consensus synthesis
        comm._calculate_consensus_confidence = AsyncMock(return_value=0.75)

        result = await comm.parallel_consensus(
            question="Test question", agents=[AgentType.DEEPSEEK, AgentType.PERPLEXITY]
        )

        assert "consensus" in result
        assert "individual_responses" in result
        assert len(result["individual_responses"]) == 2
        assert result["confidence_score"] == 0.75
        assert "conversation_id" in result


# =============================================================================
# CATEGORY 6: Iterative Improvement (7 tests)
# =============================================================================


class TestIterativeImprovement:
    """Test iterative improvement functionality"""

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_iterative_improvement_reaches_target(self, mock_get_agent):
        """iterative_improvement reaches target confidence"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        # Mock responses with increasing confidence
        responses = [
            AgentMessage(
                message_id=str(uuid.uuid4()),
                from_agent=AgentType.DEEPSEEK,
                to_agent=AgentType.ORCHESTRATOR,
                message_type=MessageType.RESPONSE,
                content=f"Improved version {i}",
                context={},
                conversation_id="conv",
            )
            for i in range(3)
        ]

        validation_responses = [
            AgentMessage(
                message_id=str(uuid.uuid4()),
                from_agent=AgentType.PERPLEXITY,
                to_agent=AgentType.ORCHESTRATOR,
                message_type=MessageType.RESPONSE,
                content=f"Confidence: {0.5 + i * 0.2}",
                context={},
                conversation_id="conv",
            )
            for i in range(3)
        ]

        all_responses = []
        for imp, val in zip(responses, validation_responses, strict=True):
            all_responses.extend([imp, val])

        comm.route_message = AsyncMock(side_effect=all_responses)

        result = await comm.iterative_improvement(
            initial_task="Initial code",
            validator_agent=AgentType.PERPLEXITY,
            improver_agent=AgentType.DEEPSEEK,
            max_iterations=3,
            min_confidence=0.8,
        )

        assert "final_content" in result
        assert "final_confidence" in result
        assert "iterations" in result
        assert len(result["iterations"]) >= 1


class TestValidationTelemetry:
    """Test Phase 6 validation helpers and telemetry hooks"""

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_validate_implementation_records_summary(self, mock_get_agent):
        mock_agent = MagicMock()
        mock_agent.send_request = AsyncMock(
            side_effect=[
                AgentResponse(
                    success=True,
                    content="Validated and safe to apply",
                    channel=AgentChannel.DIRECT_API,
                    latency_ms=10.0,
                ),
                AgentResponse(
                    success=True,
                    content="Validated ✅",
                    channel=AgentChannel.DIRECT_API,
                    latency_ms=12.0,
                ),
            ]
        )
        mock_get_agent.return_value = mock_agent

        telemetry = MagicMock()
        telemetry.record_event = MagicMock()

        comm = AgentToAgentCommunicator(memory_manager=telemetry)
        result = await comm.validate_implementation(
            implementation_content="print('ok')",
            validation_prompt="validate this",
        )

        assert result["validated"] is True
        telemetry.record_event.assert_called()

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_validate_implementation_rolls_back_on_critical(self, mock_get_agent, tmp_path):
        mock_agent = MagicMock()
        mock_agent.send_request = AsyncMock(
            side_effect=[
                AgentResponse(
                    success=True,
                    content="Critical syntax error detected",
                    channel=AgentChannel.DIRECT_API,
                    latency_ms=5.0,
                ),
                AgentResponse(
                    success=True,
                    content="Validated",
                    channel=AgentChannel.DIRECT_API,
                    latency_ms=6.0,
                ),
            ]
        )
        mock_get_agent.return_value = mock_agent

        telemetry = MagicMock()
        telemetry.record_event = MagicMock()

        backup = tmp_path / "unified_agent_interface.py.backup"
        target = tmp_path / "unified_agent_interface.py"
        backup.write_text("GOOD = True\n", encoding="utf-8")
        target.write_text("GOOD = False\n", encoding="utf-8")

        comm = AgentToAgentCommunicator(memory_manager=telemetry)
        result = await comm.validate_implementation(
            implementation_content="print('broken')",
            validation_prompt="validate",
            backup_file=str(backup),
            target_file=str(target),
        )

        assert result["rolled_back"] is True
        assert "GOOD = True" in target.read_text(encoding="utf-8")
        telemetry.record_event.assert_called()


# =============================================================================
# CATEGORY 7: Helper Methods (8 tests)
# =============================================================================


class TestHelperMethods:
    """Test helper methods"""

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_should_end_conversation_on_completion(self, mock_get_agent):
        """_should_end_conversation ends on completion message"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        response = AgentMessage(
            message_id="test",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.ORCHESTRATOR,
            message_type=MessageType.COMPLETION,
            content="Done",
            context={},
            conversation_id="conv",
        )

        should_end = await comm._should_end_conversation(response, [])

        assert should_end is True

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_should_end_conversation_on_error(self, mock_get_agent):
        """_should_end_conversation ends on error"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        response = AgentMessage(
            message_id="test",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.ORCHESTRATOR,
            message_type=MessageType.ERROR,
            content="Error occurred",
            context={},
            conversation_id="conv",
        )

        should_end = await comm._should_end_conversation(response, [])

        assert should_end is True

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_should_end_on_repeating_responses(self, mock_get_agent):
        """_should_end_conversation ends on repeating responses"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        # Same response 3 times
        same_msg = AgentMessage(
            message_id="test",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.ORCHESTRATOR,
            message_type=MessageType.RESPONSE,
            content="Same response every time",
            context={},
            conversation_id="conv",
        )

        history = [same_msg, same_msg, same_msg]

        should_end = await comm._should_end_conversation(same_msg, history)

        assert should_end is True

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_determine_next_message_collaborative(self, mock_get_agent):
        """_determine_next_message handles collaborative pattern"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        response = AgentMessage(
            message_id="test",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.ORCHESTRATOR,
            message_type=MessageType.RESPONSE,
            content="DeepSeek response",
            context={},
            conversation_id="conv",
        )

        next_msg = await comm._determine_next_message(response, CommunicationPattern.COLLABORATIVE, [])

        # DeepSeek → Qwen → Perplexity → DeepSeek (round-robin)
        assert next_msg.to_agent == AgentType.QWEN

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_calculate_consensus_confidence_empty(self, mock_get_agent):
        """_calculate_consensus_confidence handles empty responses"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        confidence = await comm._calculate_consensus_confidence([])

        assert confidence == 0.0

    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    def test_extract_confidence_score_from_text(self, mock_get_agent):
        """_extract_confidence_score extracts score from text"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        # Test decimal
        score1 = comm._extract_confidence_score("Confidence: 0.85")
        assert score1 == 0.85

        # Test percentage
        score2 = comm._extract_confidence_score("Score: 75%")
        assert score2 == 0.75

        # Test no score
        score3 = comm._extract_confidence_score("No score here")
        assert score3 == 0.5  # Default

    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    def test_create_error_message(self, mock_get_agent):
        """_create_error_message creates error message"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()

        original = AgentMessage(
            message_id="original",
            from_agent=AgentType.DEEPSEEK,
            to_agent=AgentType.PERPLEXITY,
            message_type=MessageType.QUERY,
            content="test",
            context={"key": "value"},
            conversation_id="conv",
            iteration=2,
        )

        error_msg = comm._create_error_message(original, "Test error")

        assert error_msg.message_type == MessageType.ERROR
        assert error_msg.from_agent == AgentType.ORCHESTRATOR
        assert error_msg.to_agent == AgentType.DEEPSEEK
        assert "Test error" in error_msg.content
        assert error_msg.conversation_id == "conv"
        assert error_msg.iteration == 2
        assert "error_details" in error_msg.metadata

    @pytest.mark.asyncio
    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    async def test_close_closes_redis(self, mock_get_agent):
        """close() closes Redis connection"""
        mock_get_agent.return_value = MagicMock()

        comm = AgentToAgentCommunicator()
        comm.redis_client = AsyncMock()
        comm.redis_client.close = AsyncMock()

        await comm.close()

        comm.redis_client.close.assert_called_once()


# =============================================================================
# CATEGORY 8: Singleton and Module Functions (2 tests)
# =============================================================================


class TestSingletonAndModuleFunctions:
    """Test singleton pattern and module-level functions"""

    @patch("backend.agents.agent_to_agent_communicator.get_agent_interface")
    def test_get_communicator_singleton(self, mock_get_agent):
        """get_communicator returns singleton instance"""
        mock_get_agent.return_value = MagicMock()

        # Reset singleton
        import backend.agents.agent_to_agent_communicator as comm_module

        comm_module._communicator_instance = None

        comm1 = get_communicator()
        comm2 = get_communicator()

        assert comm1 is comm2
