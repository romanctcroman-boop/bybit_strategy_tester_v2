"""
LangGraph Multi-Agent Orchestration System

This module implements a sophisticated multi-agent orchestration framework
inspired by LangGraph patterns for coordinating AI agents in trading strategy analysis.

Features:
- Directed graph-based agent execution
- State management across agent transitions
- Conditional routing based on results
- Parallel execution where possible
- Error handling and recovery
- Agent chain composition
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# State Management
# ============================================================================


class ExecutionStatus(str, Enum):
    """Status of agent execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class AgentState:
    """State object passed between agents in the graph."""

    # Core state
    messages: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    # Execution tracking
    current_node: str | None = None
    visited_nodes: list[str] = field(default_factory=list)
    execution_path: list[tuple[str, float]] = field(default_factory=list)

    # Results storage
    results: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    session_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def add_message(self, role: str, content: str, agent: str = "system"):
        """Add a message to the state."""
        self.messages.append(
            {
                "role": role,
                "content": content,
                "agent": agent,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        self.updated_at = datetime.now(UTC)

    def set_result(self, node: str, result: Any):
        """Store result from a node execution."""
        self.results[node] = result
        self.updated_at = datetime.now(UTC)

    def get_result(self, node: str) -> Any | None:
        """Get result from a node execution."""
        return self.results.get(node)

    def add_error(self, node: str, error: Exception):
        """Add an error to the state."""
        self.errors.append(
            {
                "node": node,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        self.updated_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary."""
        return {
            "session_id": self.session_id,
            "current_node": self.current_node,
            "visited_nodes": self.visited_nodes,
            "execution_path": self.execution_path,
            "results_count": len(self.results),
            "errors_count": len(self.errors),
            "messages_count": len(self.messages),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ============================================================================
# Agent Node Definition
# ============================================================================


class AgentNode(ABC):
    """Abstract base class for agent nodes in the graph."""

    def __init__(
        self,
        name: str,
        description: str = "",
        timeout: float = 60.0,
        retry_count: int = 0,
        retry_delay: float = 1.0,
    ):
        self.name = name
        self.description = description
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.status = ExecutionStatus.PENDING
        self.execution_time: float | None = None

    @abstractmethod
    async def execute(self, state: AgentState) -> AgentState:
        """Execute the agent logic."""
        pass

    async def run(self, state: AgentState) -> AgentState:
        """Run the agent with retry logic."""
        attempts = 0
        last_error = None

        while attempts <= self.retry_count:
            try:
                self.status = ExecutionStatus.RUNNING
                start_time = time.time()

                # Execute with timeout
                result_state = await asyncio.wait_for(
                    self.execute(state), timeout=self.timeout
                )

                self.execution_time = time.time() - start_time
                self.status = ExecutionStatus.COMPLETED

                # Track execution path
                result_state.execution_path.append((self.name, self.execution_time))
                result_state.visited_nodes.append(self.name)

                logger.info(
                    f"Agent '{self.name}' completed in {self.execution_time:.2f}s"
                )
                return result_state

            except TimeoutError:
                last_error = TimeoutError(
                    f"Agent '{self.name}' timed out after {self.timeout}s"
                )
                logger.warning(f"Agent '{self.name}' timeout (attempt {attempts + 1})")

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Agent '{self.name}' failed (attempt {attempts + 1}): {e}"
                )

            attempts += 1
            if attempts <= self.retry_count:
                await asyncio.sleep(self.retry_delay)

        # All retries exhausted
        self.status = ExecutionStatus.FAILED
        state.add_error(self.name, last_error or Exception("Unknown error"))
        return state


class FunctionAgent(AgentNode):
    """Agent that wraps a simple function."""

    def __init__(
        self,
        name: str,
        func: Callable[[AgentState], AgentState],
        description: str = "",
        **kwargs,
    ):
        super().__init__(name, description, **kwargs)
        self.func = func

    async def execute(self, state: AgentState) -> AgentState:
        """Execute the wrapped function."""
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(state)
        return self.func(state)


class LLMAgent(AgentNode):
    """Agent that calls an LLM (DeepSeek/Perplexity) for processing."""

    def __init__(
        self,
        name: str,
        agent_type: str = "deepseek",  # "deepseek" or "perplexity"
        system_prompt: str = "",
        description: str = "",
        **kwargs,
    ):
        super().__init__(name, description, **kwargs)
        self.agent_type = agent_type
        self.system_prompt = system_prompt

    async def execute(self, state: AgentState) -> AgentState:
        """Execute LLM call."""
        try:
            # Import agent communicator
            from backend.agents.agent_to_agent_communicator import (
                AgentType,
                MessageType,
                get_communicator,
            )

            communicator = get_communicator()

            # Prepare prompt from state messages
            user_messages = [m for m in state.messages if m.get("role") == "user"]
            prompt = user_messages[-1]["content"] if user_messages else ""

            if self.system_prompt:
                prompt = f"{self.system_prompt}\n\n{prompt}"

            # Select agent type
            if self.agent_type == "perplexity":
                agent_type = AgentType.PERPLEXITY
            else:
                agent_type = AgentType.DEEPSEEK

            # Execute agent call
            response = await communicator.async_send_message(
                target=agent_type,
                message_type=MessageType.QUERY,
                content=prompt,
                context=state.context,
            )

            # Store result
            state.set_result(self.name, response)
            state.add_message("assistant", response.get("response", ""), self.name)

        except Exception as e:
            logger.error(f"LLM Agent '{self.name}' error: {e}")
            state.add_error(self.name, e)

        return state


# ============================================================================
# Graph Edges and Routing
# ============================================================================


class EdgeType(str, Enum):
    """Type of edge in the graph."""

    DIRECT = "direct"  # Always follow this edge
    CONDITIONAL = "conditional"  # Follow based on condition
    PARALLEL = "parallel"  # Execute target nodes in parallel


@dataclass
class Edge:
    """Edge connecting two nodes in the graph."""

    source: str
    target: str | list[str]  # Single node or list for parallel
    edge_type: EdgeType = EdgeType.DIRECT
    condition: Callable[[AgentState], bool] | None = None
    priority: int = 0

    def should_traverse(self, state: AgentState) -> bool:
        """Check if this edge should be traversed."""
        if self.edge_type == EdgeType.DIRECT:
            return True
        elif self.edge_type == EdgeType.CONDITIONAL:
            if self.condition:
                return self.condition(state)
        return True


class ConditionalRouter:
    """Router that selects next node based on state conditions."""

    def __init__(self, name: str):
        self.name = name
        self.routes: list[tuple[Callable[[AgentState], bool], str]] = []
        self.default_route: str | None = None

    def add_route(self, condition: Callable[[AgentState], bool], target: str):
        """Add a conditional route."""
        self.routes.append((condition, target))

    def set_default(self, target: str):
        """Set default route."""
        self.default_route = target

    def get_next_node(self, state: AgentState) -> str | None:
        """Get the next node based on state."""
        for condition, target in self.routes:
            if condition(state):
                return target
        return self.default_route


# ============================================================================
# Agent Graph
# ============================================================================


class AgentGraph:
    """
    Directed graph of agent nodes with execution orchestration.

    Inspired by LangGraph patterns for multi-agent coordination.
    """

    def __init__(
        self, name: str = "agent_graph", description: str = "", max_iterations: int = 50
    ):
        self.name = name
        self.description = description
        self.max_iterations = max_iterations

        # Graph structure
        self.nodes: dict[str, AgentNode] = {}
        self.edges: dict[str, list[Edge]] = {}
        self.routers: dict[str, ConditionalRouter] = {}

        # Special nodes
        self.entry_point: str | None = None
        self.exit_points: set[str] = set()

        # Execution metrics
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0

    def add_node(self, node: AgentNode) -> "AgentGraph":
        """Add a node to the graph."""
        self.nodes[node.name] = node
        self.edges[node.name] = []
        return self

    def add_edge(
        self,
        source: str,
        target: str | list[str],
        edge_type: EdgeType = EdgeType.DIRECT,
        condition: Callable[[AgentState], bool] | None = None,
        priority: int = 0,
    ) -> "AgentGraph":
        """Add an edge between nodes."""
        if source not in self.nodes:
            raise ValueError(f"Source node '{source}' not found")

        targets = [target] if isinstance(target, str) else target
        for t in targets:
            if t not in self.nodes and t != "END":
                raise ValueError(f"Target node '{t}' not found")

        edge = Edge(
            source=source,
            target=target,
            edge_type=edge_type,
            condition=condition,
            priority=priority,
        )
        self.edges[source].append(edge)
        self.edges[source].sort(key=lambda e: e.priority, reverse=True)
        return self

    def add_conditional_edges(
        self, source: str, router: ConditionalRouter
    ) -> "AgentGraph":
        """Add conditional routing from a node."""
        self.routers[source] = router
        return self

    def set_entry_point(self, node_name: str) -> "AgentGraph":
        """Set the entry point of the graph."""
        if node_name not in self.nodes:
            raise ValueError(f"Node '{node_name}' not found")
        self.entry_point = node_name
        return self

    def add_exit_point(self, node_name: str) -> "AgentGraph":
        """Add an exit point to the graph."""
        self.exit_points.add(node_name)
        return self

    def _get_next_nodes(self, current: str, state: AgentState) -> list[str]:
        """Get the next nodes to execute."""
        # Check for conditional router
        if current in self.routers:
            next_node = self.routers[current].get_next_node(state)
            return [next_node] if next_node else []

        # Check edges
        next_nodes = []
        for edge in self.edges.get(current, []):
            if edge.should_traverse(state):
                if edge.edge_type == EdgeType.PARALLEL:
                    if isinstance(edge.target, list):
                        next_nodes.extend(edge.target)
                    else:
                        next_nodes.append(edge.target)
                else:
                    targets = (
                        edge.target if isinstance(edge.target, list) else [edge.target]
                    )
                    next_nodes.extend(targets)
                    break  # Only follow first matching edge for non-parallel

        return [n for n in next_nodes if n != "END"]

    async def _execute_parallel(
        self, node_names: list[str], state: AgentState
    ) -> AgentState:
        """Execute multiple nodes in parallel."""
        tasks = []
        for name in node_names:
            node = self.nodes[name]
            tasks.append(node.run(state))

        # Execute all in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results into state
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                state.add_error(node_names[i], result)
            elif isinstance(result, AgentState):
                # Merge results
                state.results.update(result.results)
                state.messages.extend(result.messages[len(state.messages) :])

        return state

    async def execute(
        self,
        initial_state: AgentState | None = None,
        input_message: str | None = None,
    ) -> AgentState:
        """Execute the graph starting from entry point."""
        if not self.entry_point:
            raise ValueError("No entry point set for graph")

        self.total_executions += 1

        # Initialize state
        state = initial_state or AgentState()
        if input_message:
            state.add_message("user", input_message)

        # Start execution
        current_nodes = [self.entry_point]
        iterations = 0

        logger.info(f"Starting graph '{self.name}' execution")

        while current_nodes and iterations < self.max_iterations:
            iterations += 1
            state.current_node = (
                current_nodes[0] if len(current_nodes) == 1 else str(current_nodes)
            )

            # Execute current nodes (including exit points)
            if len(current_nodes) == 1:
                # Single node execution
                node = self.nodes[current_nodes[0]]
                state = await node.run(state)
            else:
                # Parallel execution
                state = await self._execute_parallel(current_nodes, state)

            # Check for exit AFTER execution
            if all(n in self.exit_points for n in current_nodes):
                logger.info(f"Graph reached exit point(s): {current_nodes}")
                break

            # Get next nodes
            all_next = []
            for current in current_nodes:
                if current not in self.exit_points:
                    all_next.extend(self._get_next_nodes(current, state))

            current_nodes = list(set(all_next))  # Deduplicate

        if iterations >= self.max_iterations:
            logger.warning(f"Graph '{self.name}' reached max iterations")
            self.failed_executions += 1
        else:
            self.successful_executions += 1

        logger.info(f"Graph '{self.name}' completed in {iterations} iterations")
        return state

    def get_metrics(self) -> dict[str, Any]:
        """Get graph execution metrics."""
        return {
            "name": self.name,
            "nodes_count": len(self.nodes),
            "edges_count": sum(len(e) for e in self.edges.values()),
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": (
                self.successful_executions / max(self.total_executions, 1) * 100
            ),
        }

    def visualize(self) -> str:
        """Generate ASCII visualization of the graph."""
        lines = [f"Graph: {self.name}"]
        lines.append("=" * 50)

        for node_name, node in self.nodes.items():
            prefix = "→ " if node_name == self.entry_point else "  "
            suffix = " [EXIT]" if node_name in self.exit_points else ""
            lines.append(f"{prefix}{node_name}{suffix}")

            for edge in self.edges.get(node_name, []):
                target = (
                    edge.target
                    if isinstance(edge.target, str)
                    else " & ".join(edge.target)
                )
                edge_symbol = "──>" if edge.edge_type == EdgeType.DIRECT else "──?"
                lines.append(f"    {edge_symbol} {target}")

        return "\n".join(lines)


# ============================================================================
# Pre-built Agent Chains
# ============================================================================


class TradingAnalysisChain:
    """
    Pre-built chain for trading strategy analysis.

    Flow:
    1. Data Preparation → 2. Technical Analysis → 3. Risk Assessment
    4. Strategy Recommendation → 5. Report Generation
    """

    @staticmethod
    def create_graph() -> AgentGraph:
        """Create the trading analysis graph."""
        graph = AgentGraph(
            name="trading_analysis_chain",
            description="Multi-step trading strategy analysis",
        )

        # Define agents
        data_prep = FunctionAgent(
            name="data_preparation",
            func=TradingAnalysisChain._data_preparation,
            description="Prepare and validate market data",
        )

        tech_analysis = LLMAgent(
            name="technical_analysis",
            agent_type="deepseek",
            system_prompt=(
                "You are a technical analysis expert. Analyze the following "
                "market data and identify patterns, trends, and key levels."
            ),
            description="Perform technical analysis",
        )

        risk_assessment = LLMAgent(
            name="risk_assessment",
            agent_type="deepseek",
            system_prompt=(
                "You are a risk management expert. Evaluate the risks and "
                "provide risk metrics for the trading strategy."
            ),
            description="Assess trading risks",
        )

        strategy_rec = LLMAgent(
            name="strategy_recommendation",
            agent_type="perplexity",
            system_prompt=(
                "Based on the analysis, recommend optimal trading strategies "
                "with entry/exit points."
            ),
            description="Generate strategy recommendations",
        )

        report_gen = FunctionAgent(
            name="report_generation",
            func=TradingAnalysisChain._generate_report,
            description="Generate final analysis report",
        )

        # Build graph
        graph.add_node(data_prep)
        graph.add_node(tech_analysis)
        graph.add_node(risk_assessment)
        graph.add_node(strategy_rec)
        graph.add_node(report_gen)

        # Add edges - parallel analysis after data prep
        graph.add_edge(
            "data_preparation",
            ["technical_analysis", "risk_assessment"],
            EdgeType.PARALLEL,
        )
        graph.add_edge("technical_analysis", "strategy_recommendation")
        graph.add_edge("risk_assessment", "strategy_recommendation")
        graph.add_edge("strategy_recommendation", "report_generation")

        # Set entry and exit
        graph.set_entry_point("data_preparation")
        graph.add_exit_point("report_generation")

        return graph

    @staticmethod
    def _data_preparation(state: AgentState) -> AgentState:
        """Prepare data for analysis."""
        state.context["data_prepared"] = True
        state.context["timestamp"] = datetime.now(UTC).isoformat()
        state.add_message("system", "Data preparation completed", "data_preparation")
        state.set_result("data_preparation", {"status": "prepared"})
        return state

    @staticmethod
    def _generate_report(state: AgentState) -> AgentState:
        """Generate final report from all results."""
        report = {
            "session_id": state.session_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "technical_analysis": state.get_result("technical_analysis"),
            "risk_assessment": state.get_result("risk_assessment"),
            "recommendations": state.get_result("strategy_recommendation"),
            "errors": state.errors,
        }
        state.set_result("report_generation", report)
        state.add_message(
            "system", "Report generated successfully", "report_generation"
        )
        return state


# ============================================================================
# Global Graph Registry
# ============================================================================


_graph_registry: dict[str, AgentGraph] = {}


def register_graph(graph: AgentGraph):
    """Register a graph in the global registry."""
    _graph_registry[graph.name] = graph


def get_graph(name: str) -> AgentGraph | None:
    """Get a graph from the registry."""
    return _graph_registry.get(name)


def list_graphs() -> list[str]:
    """List all registered graphs."""
    return list(_graph_registry.keys())


# Register pre-built chains
register_graph(TradingAnalysisChain.create_graph())
