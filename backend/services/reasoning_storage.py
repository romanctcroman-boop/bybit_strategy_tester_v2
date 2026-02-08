"""
Reasoning Storage Service
Handles storage and retrieval of reasoning traces for knowledge base.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ReasoningStorageService:
    """
    Service for storing and retrieving reasoning traces.

    Stores reasoning chains, chain-of-thought steps, and strategy evolution
    data for analysis and knowledge base building.
    """

    def __init__(self, storage_path: str = "logs/reasoning_traces"):
        """
        Initialize reasoning storage service.

        Args:
            storage_path: Directory path for storing reasoning traces
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Reasoning storage initialized: {self.storage_path}")

    async def store_reasoning_trace(
        self,
        agent_type: str,
        task_type: str,
        input_prompt: str,
        reasoning_chain: Any,
        final_conclusion: str,
        processing_time: float,
        metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> str:
        """
        Store a reasoning trace.

        Args:
            agent_type: Type of agent (e.g., 'tournament_orchestrator', 'optimizer')
            task_type: Type of task (e.g., 'drift_monitoring', 'optimization')
            input_prompt: Original input/prompt
            reasoning_chain: Chain of reasoning steps (dict or list)
            final_conclusion: Final conclusion/result
            processing_time: Time taken to process (seconds)
            metadata: Additional metadata
            trace_id: Optional trace ID (generated if not provided)

        Returns:
            Trace ID
        """
        if not trace_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            trace_id = f"{agent_type}_{task_type}_{timestamp}"

        trace = {
            "trace_id": trace_id,
            "agent_type": agent_type,
            "task_type": task_type,
            "timestamp": datetime.now().isoformat(),
            "input_prompt": input_prompt,
            "reasoning_chain": reasoning_chain,
            "final_conclusion": final_conclusion,
            "processing_time": processing_time,
            "metadata": metadata or {},
        }

        try:
            # Store as JSONL (one trace per line)
            trace_file = self.storage_path / f"{agent_type}_{task_type}.jsonl"
            with open(trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace) + "\n")

            logger.debug(f"Stored reasoning trace: {trace_id}")
            return trace_id

        except Exception as exc:
            logger.error(f"Failed to store reasoning trace: {exc}")
            raise

    async def store_tournament_trace(
        self,
        tournament_id: str,
        tournament_name: str,
        strategies: list[dict[str, Any]],
        winner: dict[str, Any] | None,
        market_regime: str | None,
        metrics: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Store a tournament trace.

        Args:
            tournament_id: Tournament ID
            tournament_name: Tournament name
            strategies: List of strategy data
            winner: Winner strategy data
            market_regime: Detected market regime
            metrics: Tournament metrics
            metadata: Additional metadata

        Returns:
            Trace ID
        """
        trace_id = f"tournament_{tournament_id}"

        reasoning_chain = {
            "tournament_id": tournament_id,
            "tournament_name": tournament_name,
            "strategies": strategies,
            "winner": winner,
            "market_regime": market_regime,
            "metrics": metrics,
        }

        final_conclusion = (
            f"Tournament '{tournament_name}' completed. "
            f"Winner: {winner['strategy_name'] if winner else 'None'}"
        )

        return await self.store_reasoning_trace(
            agent_type="tournament_orchestrator",
            task_type="tournament",
            input_prompt=f"Run tournament: {tournament_name}",
            reasoning_chain=reasoning_chain,
            final_conclusion=final_conclusion,
            processing_time=metrics.get("total_duration", 0),
            metadata=metadata,
            trace_id=trace_id,
        )

    async def get_recent_traces(
        self,
        agent_type: str | None = None,
        task_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get recent reasoning traces.

        Args:
            agent_type: Filter by agent type (optional)
            task_type: Filter by task type (optional)
            limit: Maximum number of traces to return

        Returns:
            List of reasoning traces
        """
        traces = []

        try:
            # Find matching files
            if agent_type and task_type:
                pattern = f"{agent_type}_{task_type}.jsonl"
            elif agent_type:
                pattern = f"{agent_type}_*.jsonl"
            else:
                pattern = "*.jsonl"

            trace_files = list(self.storage_path.glob(pattern))

            # Read traces from files
            for trace_file in trace_files:
                try:
                    with open(trace_file, encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                trace = json.loads(line)
                                traces.append(trace)
                except Exception as exc:
                    logger.warning(f"Failed to read trace file {trace_file}: {exc}")

            # Sort by timestamp (most recent first)
            traces.sort(key=lambda t: t.get("timestamp", ""), reverse=True)

            # Apply limit
            return traces[:limit]

        except Exception as exc:
            logger.error(f"Failed to get recent traces: {exc}")
            return []

    async def get_trace_by_id(self, trace_id: str) -> dict[str, Any] | None:
        """
        Get a specific reasoning trace by ID.

        Args:
            trace_id: Trace ID to retrieve

        Returns:
            Trace data, or None if not found
        """
        try:
            # Search all trace files
            for trace_file in self.storage_path.glob("*.jsonl"):
                with open(trace_file, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            trace = json.loads(line)
                            if trace.get("trace_id") == trace_id:
                                return trace

            return None

        except Exception as exc:
            logger.error(f"Failed to get trace by ID: {exc}")
            return None

    async def search_traces(
        self,
        query: str,
        agent_type: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Search reasoning traces by keyword.

        Args:
            query: Search query string
            agent_type: Filter by agent type (optional)
            task_type: Filter by task type (optional)
            limit: Maximum number of results

        Returns:
            List of matching traces
        """
        all_traces = await self.get_recent_traces(
            agent_type=agent_type,
            task_type=task_type,
            limit=limit * 2,  # Get more, filter later
        )

        query_lower = query.lower()

        matching_traces = []
        for trace in all_traces:
            # Search in prompt, conclusion, and reasoning chain
            search_text = " ".join(
                [
                    str(trace.get("input_prompt", "")),
                    str(trace.get("final_conclusion", "")),
                    json.dumps(trace.get("reasoning_chain", {})),
                ]
            ).lower()

            if query_lower in search_text:
                matching_traces.append(trace)

            if len(matching_traces) >= limit:
                break

        return matching_traces

    async def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about stored reasoning traces.

        Returns:
            Dictionary with statistics
        """
        try:
            trace_files = list(self.storage_path.glob("*.jsonl"))

            stats = {
                "total_files": len(trace_files),
                "total_traces": 0,
                "by_agent_type": {},
                "by_task_type": {},
                "storage_path": str(self.storage_path.absolute()),
            }

            for trace_file in trace_files:
                file_trace_count = 0
                with open(trace_file, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            file_trace_count += 1
                            try:
                                trace = json.loads(line)
                                agent_type = trace.get("agent_type", "unknown")
                                task_type = trace.get("task_type", "unknown")

                                stats["by_agent_type"][agent_type] = (
                                    stats["by_agent_type"].get(agent_type, 0) + 1
                                )
                                stats["by_task_type"][task_type] = (
                                    stats["by_task_type"].get(task_type, 0) + 1
                                )
                            except json.JSONDecodeError:
                                pass

                stats["total_traces"] += file_trace_count

            return stats

        except Exception as exc:
            logger.error(f"Failed to get statistics: {exc}")
            return {
                "error": str(exc),
                "storage_path": str(self.storage_path.absolute()),
            }
