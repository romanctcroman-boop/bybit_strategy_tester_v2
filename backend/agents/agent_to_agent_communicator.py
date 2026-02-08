"""Agent-to-agent communication orchestrator.

This module wires DeepSeek, Perplexity, and Copilot style agents together so
that they can exchange structured messages, run multi-turn conversations, build
parallel consensus, and iterate toward better answers. It intentionally mirrors
what the original implementation provided (see WEEK2_DAY3_AGENT_TO_AGENT_COMPLETE)
so that the extensive pytest suite in
``tests/backend/test_agent_to_agent_communicator.py`` keeps passing.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger
from redis import asyncio as redis

from backend.agents.agent_memory import AgentMemoryManager
from backend.agents.base_config import FORCE_DIRECT_AGENT_API
from backend.agents.interface import (
    AgentRequest,
    AgentResponse,
    get_agent_interface,
)
from backend.agents.models import AgentType, CommunicationPattern, MessageType
from backend.agents.unified_agent_interface import AgentChannel

PROJECT_ROOT = Path(__file__).resolve().parents[2]


MessageHandler = Callable[["AgentMessage"], Awaitable["AgentMessage"]]


@dataclass
class AgentMessage:
    """Lightweight dataclass for cross-agent messaging."""

    message_id: str
    from_agent: AgentType
    to_agent: AgentType
    message_type: MessageType
    content: str
    conversation_id: str
    context: dict[str, Any] = field(default_factory=dict)
    iteration: int = 1
    max_iterations: int = 5
    confidence_score: float = 0.0
    timestamp: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC).isoformat()
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent.value,
            "to_agent": self.to_agent.value,
            "message_type": self.message_type.value,
            "content": self.content,
            "context": self.context,
            "conversation_id": self.conversation_id,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "confidence_score": self.confidence_score,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessage:
        return cls(
            message_id=data["message_id"],
            from_agent=AgentType(data["from_agent"]),
            to_agent=AgentType(data["to_agent"]),
            message_type=MessageType(data["message_type"]),
            content=data["content"],
            context=data.get("context", {}),
            conversation_id=data["conversation_id"],
            iteration=data.get("iteration", 1),
            max_iterations=data.get("max_iterations", 5),
            confidence_score=data.get("confidence_score", 0.0),
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata"),
        )


class AgentToAgentCommunicator:
    """Coordinates messaging flows between agents."""

    _VALIDATION_KEYWORDS = ("validated", "safe to apply", "looks good", "approved")
    _CRITICAL_KEYWORDS = (
        "critical syntax",
        "syntax error",
        "unsafe",
        "do not apply",
        "fatal",
        "rollback",
    )

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        memory_manager: AgentMemoryManager | None = None,
    ):
        self.agent_interface = get_agent_interface()
        self.redis_url = redis_url
        self.redis_client: redis.Redis | None = None
        self.message_handlers: dict[AgentType, MessageHandler] = {
            AgentType.DEEPSEEK: self._handle_deepseek_message,
            AgentType.PERPLEXITY: self._handle_perplexity_message,
            AgentType.COPILOT: self._handle_copilot_message,
        }
        self.conversation_cache: dict[str, list[AgentMessage]] = {}
        self.max_conversation_age = timedelta(minutes=30)
        self.memory_manager = memory_manager or self._create_memory_manager()

    async def _get_redis(self) -> redis.Redis:
        if self.redis_client is not None:
            return self.redis_client

        client = redis.from_url(self.redis_url, decode_responses=True)
        if asyncio.iscoroutine(client):
            client = await client

        self.redis_client = client
        return self.redis_client

    def _create_memory_manager(self) -> AgentMemoryManager | None:
        try:
            return AgentMemoryManager(PROJECT_ROOT)
        except Exception as exc:  # pragma: no cover - best effort init
            logger.debug(f"Telemetry memory manager unavailable: {exc}")
            return None

    def _record_telemetry(self, event: str, payload: dict[str, Any]) -> None:
        if not self.memory_manager:
            return
        try:
            self.memory_manager.record_event(event, payload)
        except Exception as exc:  # pragma: no cover - logging best effort
            logger.debug(f"Telemetry write skipped ({event}): {exc}")

    async def route_message(self, message: AgentMessage) -> AgentMessage:
        await self._check_conversation_loop(message)
        handler = self.message_handlers.get(message.to_agent)
        if not handler:
            error_response = self._create_error_message(
                message, f"No handler for agent {message.to_agent.value}"
            )
            self._record_telemetry(
                "communicator_route",
                {
                    "status": "missing_handler",
                    "from": message.from_agent.value,
                    "to": message.to_agent.value,
                    "message_type": message.message_type.value,
                    "conversation_id": message.conversation_id,
                    "iteration": message.iteration,
                },
            )
            return error_response

        try:
            response = await handler(message)
            self._record_history(message, response)
            self._record_telemetry(
                "communicator_route",
                {
                    "status": "ok",
                    "from": message.from_agent.value,
                    "to": message.to_agent.value,
                    "message_type": message.message_type.value,
                    "response_type": response.message_type.value,
                    "confidence": response.confidence_score,
                    "conversation_id": message.conversation_id,
                    "iteration": message.iteration,
                },
            )
            return response
        except Exception as exc:  # pragma: no cover - guardrail
            logger.error(f"agent handler failure: {exc}")
            error_response = self._create_error_message(message, str(exc))
            self._record_telemetry(
                "communicator_route",
                {
                    "status": "error",
                    "from": message.from_agent.value,
                    "to": message.to_agent.value,
                    "message_type": message.message_type.value,
                    "conversation_id": message.conversation_id,
                    "iteration": message.iteration,
                    "error": str(exc),
                },
            )
            return error_response

    async def _check_conversation_loop(self, message: AgentMessage) -> None:
        redis_client = await self._get_redis()
        key = f"agent-conv:{message.conversation_id}:{message.iteration}"
        exists = await redis_client.exists(key)
        if exists:
            raise ValueError("Potential infinite loop detected")

        ttl = int(self.max_conversation_age.total_seconds())
        await redis_client.setex(key, ttl, message.from_agent.value)

    async def _handle_deepseek_message(self, message: AgentMessage) -> AgentMessage:
        from_mcp_tool = message.context.get("from_mcp_tool", False)
        use_file_access = message.context.get("use_file_access", False)
        force_direct = FORCE_DIRECT_AGENT_API or use_file_access or from_mcp_tool
        preferred_channel = (
            AgentChannel.DIRECT_API if force_direct else AgentChannel.MCP_SERVER
        )
        logger.info(
            "🔀 DeepSeek routing via {} (use_file_access={}, from_mcp={})",
            preferred_channel.value,
            use_file_access,
            from_mcp_tool,
        )
        request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type=message.context.get("task_type", "analyze"),
            prompt=message.content,
            code=message.context.get("code"),
            context=message.context,
        )
        agent_response = await self.agent_interface.send_request(
            request,
            preferred_channel=preferred_channel,
        )
        return self._build_agent_reply(
            original_message=message,
            agent_type=AgentType.DEEPSEEK,
            agent_response=agent_response,
            success_confidence=0.9,
        )

    async def _handle_perplexity_message(self, message: AgentMessage) -> AgentMessage:
        from_mcp_tool = message.context.get("from_mcp_tool", False)
        force_direct = FORCE_DIRECT_AGENT_API or from_mcp_tool
        preferred_channel = (
            AgentChannel.DIRECT_API if force_direct else AgentChannel.MCP_SERVER
        )
        logger.info(
            "🔀 Perplexity routing via {} (from_mcp={})",
            preferred_channel.value,
            from_mcp_tool,
        )
        request = AgentRequest(
            agent_type=AgentType.PERPLEXITY,
            task_type=message.context.get("task_type", "analyze"),
            prompt=message.content,
            code=message.context.get("code"),
            context=message.context,
        )
        agent_response = await self.agent_interface.send_request(
            request,
            preferred_channel=preferred_channel,
        )
        return self._build_agent_reply(
            original_message=message,
            agent_type=AgentType.PERPLEXITY,
            agent_response=agent_response,
            success_confidence=0.85,
        )

    async def _handle_copilot_message(self, message: AgentMessage) -> AgentMessage:
        placeholder = (
            "Copilot placeholder — VS Code extension bridge pending integration."
        )
        return AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=AgentType.COPILOT,
            to_agent=message.from_agent,
            message_type=MessageType.RESPONSE,
            content=placeholder,
            context=message.context,
            conversation_id=message.conversation_id,
            iteration=message.iteration + 1,
            confidence_score=0.5,
            metadata={"status": "placeholder_response"},
        )

    def _build_agent_reply(
        self,
        original_message: AgentMessage,
        agent_type: AgentType,
        agent_response: AgentResponse,
        success_confidence: float,
    ) -> AgentMessage:
        metadata = {
            "channel": agent_response.channel.value,
            "latency_ms": agent_response.latency_ms,
        }
        if agent_response.api_key_index is not None:
            metadata["api_key_index"] = agent_response.api_key_index
        if agent_response.error:
            metadata["error"] = agent_response.error

        if agent_response.success:
            return AgentMessage(
                message_id=str(uuid.uuid4()),
                from_agent=agent_type,
                to_agent=original_message.from_agent,
                message_type=MessageType.RESPONSE,
                content=agent_response.content or "",
                context=original_message.context,
                conversation_id=original_message.conversation_id,
                iteration=original_message.iteration + 1,
                confidence_score=success_confidence,
                metadata=metadata,
            )

        return self._create_error_message(
            original_message,
            agent_response.error or "Unknown agent error",
        )

    async def multi_turn_conversation(
        self,
        initial_message: AgentMessage,
        max_turns: int = 10,
        pattern: CommunicationPattern = CommunicationPattern.SEQUENTIAL,
    ) -> list[AgentMessage]:
        history = [initial_message]
        current_message = initial_message

        for _ in range(max_turns):
            response = await self.route_message(current_message)
            history.append(response)

            if await self._should_end_conversation(response, history):
                break

            if response.iteration >= response.max_iterations:
                break

            current_message = await self._determine_next_message(
                response, pattern, history
            )

        return history

    async def parallel_consensus(
        self,
        question: str,
        agents: list[AgentType],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        conversation_id = str(uuid.uuid4())
        context = context or {}

        async def _ask(agent: AgentType) -> AgentMessage:
            message = AgentMessage(
                message_id=str(uuid.uuid4()),
                from_agent=AgentType.ORCHESTRATOR,
                to_agent=agent,
                message_type=MessageType.CONSENSUS_REQUEST,
                content=question,
                context=context,
                conversation_id=conversation_id,
            )
            return await self.route_message(message)

        responses = await asyncio.gather(*[_ask(agent) for agent in agents])
        confidence = await self._calculate_consensus_confidence(responses)

        individual = [
            {
                "agent": resp.from_agent.value,
                "content": resp.content,
                "confidence": resp.confidence_score,
            }
            for resp in responses
        ]
        combined_answer = "\n\n".join(
            f"{resp.from_agent.value}: {resp.content}" for resp in responses
        )

        return {
            "question": question,
            "consensus": combined_answer,
            "individual_responses": individual,
            "confidence_score": confidence,
            "conversation_id": conversation_id,
        }

    async def iterative_improvement(
        self,
        initial_task: str,
        validator_agent: AgentType,
        improver_agent: AgentType,
        max_iterations: int = 5,
        min_confidence: float = 0.8,
    ) -> dict[str, Any]:
        conversation_id = str(uuid.uuid4())
        current_content = initial_task
        iteration_log: list[dict[str, Any]] = []
        final_confidence = 0.0

        for iteration in range(1, max_iterations + 1):
            improvement_message = AgentMessage(
                message_id=str(uuid.uuid4()),
                from_agent=AgentType.ORCHESTRATOR,
                to_agent=improver_agent,
                message_type=MessageType.QUERY,
                content=current_content,
                context={},
                conversation_id=conversation_id,
                iteration=iteration,
                max_iterations=max_iterations,
            )
            improvement = await self.route_message(improvement_message)

            validation_message = AgentMessage(
                message_id=str(uuid.uuid4()),
                from_agent=AgentType.ORCHESTRATOR,
                to_agent=validator_agent,
                message_type=MessageType.VALIDATION,
                content=improvement.content,
                context={},
                conversation_id=conversation_id,
                iteration=iteration + 1,
                max_iterations=max_iterations,
            )
            validation = await self.route_message(validation_message)

            confidence = self._extract_confidence_score(validation.content)
            iteration_log.append(
                {
                    "iteration": iteration,
                    "improvement": improvement.content,
                    "validation": validation.content,
                    "confidence": confidence,
                }
            )

            current_content = improvement.content
            final_confidence = confidence

            if confidence >= min_confidence:
                break

        return {
            "final_content": current_content,
            "final_confidence": final_confidence,
            "iterations": iteration_log,
            "conversation_id": conversation_id,
        }

    async def validate_implementation(
        self,
        implementation_content: str,
        validation_prompt: str,
        backup_file: str | None = None,
        target_file: str | None = None,
        cycle: int | None = None,
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        """Run Phase 6-style validation via both agents with telemetry hooks."""

        request_context = {
            "timeout_override": timeout_seconds,
            "phase": "phase6_validation",
        }

        ds_request = AgentRequest(
            agent_type=AgentType.DEEPSEEK,
            task_type="review",
            prompt=validation_prompt,
            code=(implementation_content or "")[:5000],
            context=request_context,
        )
        pp_request = AgentRequest(
            agent_type=AgentType.PERPLEXITY,
            task_type="review",
            prompt=validation_prompt,
            code=None,
            context=request_context,
        )

        ds_response = await self._run_validation_request(ds_request, AgentType.DEEPSEEK)
        pp_response = await self._run_validation_request(
            pp_request, AgentType.PERPLEXITY
        )

        ds_summary = self._summarize_validation_response(
            AgentType.DEEPSEEK, ds_response
        )
        pp_summary = self._summarize_validation_response(
            AgentType.PERPLEXITY, pp_response
        )

        validated = (
            ds_summary["verdict"] == "VALIDATED"
            and pp_summary["verdict"] == "VALIDATED"
            and not ds_summary["critical_issues"]
            and not pp_summary["critical_issues"]
        )

        rolled_back = False
        if (
            (ds_summary["critical_issues"] or pp_summary["critical_issues"])
            and backup_file
            and target_file
        ):
            rolled_back = await self._rollback_to_backup(backup_file, target_file)

        payload = {
            "success": True,
            "validated": validated,
            "rolled_back": rolled_back,
            "deepseek_validation": ds_summary,
            "perplexity_validation": pp_summary,
        }

        self._record_telemetry(
            "phase6_validation",
            {
                "cycle": cycle,
                "validated": validated,
                "rolled_back": rolled_back,
                "deepseek": ds_summary,
                "perplexity": pp_summary,
                "backup_available": bool(backup_file),
            },
        )

        return payload

    async def _run_validation_request(
        self, request: AgentRequest, agent_type: AgentType
    ) -> AgentResponse:
        try:
            return await self.agent_interface.send_request(request)
        except Exception as exc:  # pragma: no cover - network/agent failure
            logger.error(f"Validation request failed for {agent_type.value}: {exc}")
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.DIRECT_API,
                error=str(exc),
            )

    def _summarize_validation_response(
        self, agent_type: AgentType, response: AgentResponse
    ) -> dict[str, Any]:
        text = (response.content or "").strip()
        text_lower = text.lower()
        validated = response.success and any(
            keyword in text_lower for keyword in self._VALIDATION_KEYWORDS
        )
        critical = any(keyword in text_lower for keyword in self._CRITICAL_KEYWORDS)
        verdict = "VALIDATED" if validated and not critical else "NOT_VALIDATED"
        return {
            "agent": agent_type.value,
            "success": response.success,
            "content": text[:1000],
            "verdict": verdict,
            "critical_issues": critical,
            "channel": response.channel.value,
            "latency_ms": response.latency_ms,
            "error": response.error,
        }

    async def _rollback_to_backup(self, backup_file: str, target_file: str) -> bool:
        backup_path = Path(backup_file)
        target_path = Path(target_file)

        if not backup_path.exists():
            logger.warning(f"Backup file missing for rollback: {backup_file}")
            return False

        def _copy() -> bool:
            shutil.copy2(backup_path, target_path)
            return True

        try:
            return await asyncio.to_thread(_copy)
        except Exception as exc:  # pragma: no cover - catastrophic IO error
            logger.error(f"Rollback failed: {exc}")
            return False

    async def _should_end_conversation(
        self, response: AgentMessage, history: list[AgentMessage]
    ) -> bool:
        if response.message_type in (MessageType.COMPLETION, MessageType.ERROR):
            return True
        if response.iteration >= response.max_iterations:
            return True
        if len(history) >= 3:
            last_three = history[-3:]
            contents = [msg.content[:100] for msg in last_three]
            if len(set(contents)) == 1:
                return True
        return False

    async def _determine_next_message(
        self,
        response: AgentMessage,
        pattern: CommunicationPattern,
        history: list[AgentMessage],
    ) -> AgentMessage:
        next_iteration = response.iteration + 1
        next_agent = response.from_agent

        if pattern == CommunicationPattern.COLLABORATIVE:
            next_agent = (
                AgentType.PERPLEXITY
                if response.from_agent == AgentType.DEEPSEEK
                else AgentType.DEEPSEEK
            )
        elif pattern == CommunicationPattern.SEQUENTIAL:
            next_agent = (
                AgentType.DEEPSEEK
                if response.from_agent != AgentType.DEEPSEEK
                else AgentType.PERPLEXITY
            )
        else:
            return response

        return AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=next_agent,
            message_type=MessageType.QUERY,
            content=response.content,
            context=response.context,
            conversation_id=response.conversation_id,
            iteration=next_iteration,
            max_iterations=response.max_iterations,
        )

    async def _calculate_consensus_confidence(
        self, responses: list[AgentMessage]
    ) -> float:
        if not responses:
            return 0.0
        scores = [msg.confidence_score for msg in responses if msg.confidence_score]
        if not scores:
            return 0.0
        avg = sum(scores) / len(scores)
        diversity_penalty = max(0, len({msg.content for msg in responses}) - 1) * 0.05
        return max(0.0, min(1.0, avg - diversity_penalty))

    def _extract_confidence_score(self, text: str) -> float:
        decimal_match = re.search(r"(0\.\d+|1\.0)", text)
        if decimal_match:
            return float(decimal_match.group(1))
        percent_match = re.search(r"(\d{1,3})%", text)
        if percent_match:
            percent = float(percent_match.group(1))
            if 0 <= percent <= 100:
                return percent / 100.0
        return 0.5

    def _create_error_message(self, original: AgentMessage, error: str) -> AgentMessage:
        return AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=original.from_agent,
            message_type=MessageType.ERROR,
            content=f"Error: {error}",
            context=original.context,
            conversation_id=original.conversation_id,
            iteration=original.iteration,
            max_iterations=original.max_iterations,
            confidence_score=0.0,
            metadata={"error_details": error},
        )

    def _record_history(self, request: AgentMessage, response: AgentMessage) -> None:
        history = self.conversation_cache.setdefault(request.conversation_id, [])
        history.append(request)
        history.append(response)
        # keep cache lightweight
        if len(history) > 50:
            self.conversation_cache[request.conversation_id] = history[-50:]

    async def close(self) -> None:
        if self.redis_client:
            await self.redis_client.close()


_communicator_instance: AgentToAgentCommunicator | None = None


def get_communicator() -> AgentToAgentCommunicator:
    global _communicator_instance
    if _communicator_instance is None:
        _communicator_instance = AgentToAgentCommunicator()
    return _communicator_instance


# Alias for backward compatibility and tests
AgentCommunicator = AgentToAgentCommunicator


__all__ = [
    "AgentCommunicator",
    "AgentMessage",
    "AgentToAgentCommunicator",
    "get_communicator",
]
