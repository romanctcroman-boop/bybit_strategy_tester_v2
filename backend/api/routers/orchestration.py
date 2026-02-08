"""
LangGraph Orchestration Router
Provides API endpoints for managing and executing multi-agent graphs.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.langgraph_orchestrator import (
    AgentState,
    get_graph,
    list_graphs,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/orchestration", tags=["Orchestration"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ExecutionRequest(BaseModel):
    """Request to execute a graph."""

    graph_name: str = Field(..., description="Name of the graph to execute")
    input_message: str | None = Field(None, description="Initial input message")
    context: dict[str, Any] | None = Field(
        default_factory=dict, description="Additional context"
    )


class ExecutionResult(BaseModel):
    """Result of graph execution."""

    session_id: str
    graph_name: str
    status: str
    execution_path: list[tuple]
    results: dict[str, Any]
    errors: list[dict[str, Any]]
    messages_count: int
    total_duration_ms: float
    completed_at: str


class GraphInfo(BaseModel):
    """Information about a registered graph."""

    name: str
    description: str
    nodes_count: int
    edges_count: int
    entry_point: str | None
    exit_points: list[str]
    metrics: dict[str, Any]


class GraphVisualization(BaseModel):
    """ASCII visualization of a graph."""

    name: str
    visualization: str


class OrchestratorStatus(BaseModel):
    """Overall orchestrator status."""

    registered_graphs: int
    graph_names: list[str]
    total_executions: int
    successful_executions: int
    overall_success_rate: float


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=OrchestratorStatus)
async def get_orchestrator_status():
    """
    Get overall orchestrator status.

    Returns:
        Summary of registered graphs and execution statistics
    """
    try:
        graphs = list_graphs()
        total_exec = 0
        successful_exec = 0

        for name in graphs:
            graph = get_graph(name)
            if graph:
                total_exec += graph.total_executions
                successful_exec += graph.successful_executions

        return OrchestratorStatus(
            registered_graphs=len(graphs),
            graph_names=graphs,
            total_executions=total_exec,
            successful_executions=successful_exec,
            overall_success_rate=(successful_exec / max(total_exec, 1) * 100),
        )
    except Exception as e:
        logger.error(f"Error getting orchestrator status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graphs", response_model=list[GraphInfo])
async def list_registered_graphs():
    """
    List all registered graphs with their information.

    Returns:
        List of graph information objects
    """
    try:
        graphs = []
        for name in list_graphs():
            graph = get_graph(name)
            if graph:
                graphs.append(
                    GraphInfo(
                        name=graph.name,
                        description=graph.description,
                        nodes_count=len(graph.nodes),
                        edges_count=sum(len(e) for e in graph.edges.values()),
                        entry_point=graph.entry_point,
                        exit_points=list(graph.exit_points),
                        metrics=graph.get_metrics(),
                    )
                )
        return graphs
    except Exception as e:
        logger.error(f"Error listing graphs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graphs/{graph_name}", response_model=GraphInfo)
async def get_graph_info(graph_name: str):
    """
    Get detailed information about a specific graph.

    Args:
        graph_name: Name of the graph

    Returns:
        Detailed graph information
    """
    try:
        graph = get_graph(graph_name)
        if not graph:
            raise HTTPException(
                status_code=404,
                detail=f"Graph '{graph_name}' not found. Available: {list_graphs()}",
            )

        return GraphInfo(
            name=graph.name,
            description=graph.description,
            nodes_count=len(graph.nodes),
            edges_count=sum(len(e) for e in graph.edges.values()),
            entry_point=graph.entry_point,
            exit_points=list(graph.exit_points),
            metrics=graph.get_metrics(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting graph info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graphs/{graph_name}/visualize", response_model=GraphVisualization)
async def visualize_graph(graph_name: str):
    """
    Get ASCII visualization of a graph.

    Args:
        graph_name: Name of the graph

    Returns:
        ASCII representation of the graph structure
    """
    try:
        graph = get_graph(graph_name)
        if not graph:
            raise HTTPException(
                status_code=404,
                detail=f"Graph '{graph_name}' not found",
            )

        return GraphVisualization(
            name=graph.name,
            visualization=graph.visualize(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error visualizing graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=ExecutionResult)
async def execute_graph(request: ExecutionRequest):
    """
    Execute a registered graph with the given input.

    Args:
        request: Execution request with graph name and input

    Returns:
        Execution result with all outputs and metrics
    """
    import time

    try:
        graph = get_graph(request.graph_name)
        if not graph:
            raise HTTPException(
                status_code=404,
                detail=f"Graph '{request.graph_name}' not found. Available: {list_graphs()}",
            )

        # Create initial state with context
        initial_state = AgentState(context=request.context or {})

        # Execute graph
        start_time = time.time()
        result_state = await graph.execute(
            initial_state=initial_state,
            input_message=request.input_message,
        )
        duration_ms = (time.time() - start_time) * 1000

        return ExecutionResult(
            session_id=result_state.session_id,
            graph_name=request.graph_name,
            status="completed" if not result_state.errors else "completed_with_errors",
            execution_path=result_state.execution_path,
            results=result_state.results,
            errors=result_state.errors,
            messages_count=len(result_state.messages),
            total_duration_ms=round(duration_ms, 2),
            completed_at=datetime.now(UTC).isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graphs/{graph_name}/nodes")
async def get_graph_nodes(graph_name: str):
    """
    Get all nodes in a graph with their details.

    Args:
        graph_name: Name of the graph

    Returns:
        List of node information
    """
    try:
        graph = get_graph(graph_name)
        if not graph:
            raise HTTPException(
                status_code=404,
                detail=f"Graph '{graph_name}' not found",
            )

        nodes = []
        for name, node in graph.nodes.items():
            nodes.append(
                {
                    "name": name,
                    "description": node.description,
                    "timeout": node.timeout,
                    "retry_count": node.retry_count,
                    "status": node.status.value,
                    "execution_time": node.execution_time,
                    "is_entry": name == graph.entry_point,
                    "is_exit": name in graph.exit_points,
                }
            )

        return {"graph": graph_name, "nodes": nodes}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting graph nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graphs/{graph_name}/metrics")
async def get_graph_metrics(graph_name: str):
    """
    Get execution metrics for a specific graph.

    Args:
        graph_name: Name of the graph

    Returns:
        Detailed execution metrics
    """
    try:
        graph = get_graph(graph_name)
        if not graph:
            raise HTTPException(
                status_code=404,
                detail=f"Graph '{graph_name}' not found",
            )

        return {
            "graph": graph_name,
            "metrics": graph.get_metrics(),
            "node_metrics": {
                name: {
                    "status": node.status.value,
                    "execution_time": node.execution_time,
                }
                for name, node in graph.nodes.items()
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting graph metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
