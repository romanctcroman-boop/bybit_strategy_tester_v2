"""
Enhanced Multi-Agent Orchestration System

Advanced agent collaboration features:
- Dynamic agent selection based on task
- Agent consensus mechanisms
- Shared memory between agents
- Agent performance tracking
- Automatic failover and retry

Usage:
    from backend.agents.orchestration import AgentOrchestrator
    orchestrator = AgentOrchestrator()
    result = orchestrator.execute_task("analyze_market", context={...})
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from loguru import logger


class AgentCapability(str, Enum):
    """Agent capabilities."""
    CODE_GENERATION = "code_generation"
    MARKET_ANALYSIS = "market_analysis"
    STRATEGY_OPTIMIZATION = "strategy_optimization"
    DATA_ANALYSIS = "data_analysis"
    RESEARCH = "research"
    VALIDATION = "validation"
    EXPLANATION = "explanation"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AgentPerformance:
    """Agent performance metrics."""
    agent_type: str
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    avg_response_time: float = 0.0
    total_cost_usd: float = 0.0
    last_used: str | None = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return self.successful_tasks / self.total_tasks if self.total_tasks > 0 else 0.0
    
    @property
    def avg_cost_per_task(self) -> float:
        """Calculate average cost per task."""
        return self.total_cost_usd / self.total_tasks if self.total_tasks > 0 else 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "agent_type": self.agent_type,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
            "total_cost_usd": self.total_cost_usd,
            "avg_cost_per_task": self.avg_cost_per_task,
            "last_used": self.last_used,
        }


@dataclass
class Task:
    """Task for agent execution."""
    task_id: str
    task_type: str
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    required_capabilities: list[AgentCapability] = field(default_factory=list)
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    assigned_agent: str | None = None
    result: Any = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "prompt": self.prompt,
            "context": self.context,
            "priority": self.priority.value,
            "required_capabilities": [c.value for c in self.required_capabilities],
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "assigned_agent": self.assigned_agent,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "status": self.status,
        }
    
    @property
    def status(self) -> str:
        """Get task status."""
        if self.error:
            return "failed"
        elif self.completed_at:
            return "completed"
        elif self.started_at:
            return "running"
        else:
            return "pending"


@dataclass
class AgentOrchestrationResult:
    """Result of agent orchestration."""
    task_id: str
    success: bool
    result: Any
    agent_used: str
    response_time: float
    cost_usd: float
    attempts: int
    consensus_score: float | None = None


class AgentOrchestrator:
    """
    Enhanced multi-agent orchestrator.
    
    Features:
    - Dynamic agent selection based on task requirements
    - Agent performance tracking
    - Automatic failover
    - Consensus mechanisms for critical tasks
    - Shared memory between agents
    - Task prioritization
    
    Example:
        orchestrator = AgentOrchestrator()
        result = orchestrator.execute_task(
            "analyze_market",
            prompt="Analyze BTCUSDT trend",
            capabilities=[AgentCapability.MARKET_ANALYSIS],
            priority=TaskPriority.HIGH
        )
    """
    
    # Agent capability mapping
    AGENT_CAPABILITIES: dict[str, list[AgentCapability]] = {
        "deepseek": [
            AgentCapability.CODE_GENERATION,
            AgentCapability.DATA_ANALYSIS,
            AgentCapability.VALIDATION,
        ],
        "qwen": [
            AgentCapability.CODE_GENERATION,
            AgentCapability.STRATEGY_OPTIMIZATION,
            AgentCapability.EXPLANATION,
        ],
        "perplexity": [
            AgentCapability.MARKET_ANALYSIS,
            AgentCapability.RESEARCH,
            AgentCapability.DATA_ANALYSIS,
        ],
    }
    
    def __init__(self, max_concurrent_tasks: int = 10):
        """
        Initialize orchestrator.
        
        Args:
            max_concurrent_tasks: Maximum concurrent tasks
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        
        # Agent performance tracking
        self._performance: dict[str, AgentPerformance] = {
            agent: AgentPerformance(agent_type=agent)
            for agent in self.AGENT_CAPABILITIES.keys()
        }
        
        # Task queue
        self._task_queue: list[Task] = []
        self._active_tasks: dict[str, Task] = {}
        self._completed_tasks: dict[str, Task] = {}
        
        # Shared memory
        self._shared_memory: dict[str, Any] = {}
        
        # Agent interface (lazy loaded)
        self._agent_interface = None
        
        logger.info("🎯 AgentOrchestrator initialized")
    
    async def execute_task(
        self,
        task_type: str,
        prompt: str,
        context: dict[str, Any] | None = None,
        capabilities: list[AgentCapability] | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        require_consensus: bool = False,
    ) -> AgentOrchestrationResult:
        """
        Execute a task with agent orchestration.
        
        Args:
            task_type: Type of task
            prompt: Task prompt
            context: Task context
            capabilities: Required agent capabilities
            priority: Task priority
            require_consensus: Require multi-agent consensus
        
        Returns:
            Orchestration result
        """
        # Create task
        task = Task(
            task_id=f"task_{uuid.uuid4().hex[:8]}",
            task_type=task_type,
            prompt=prompt,
            context=context or {},
            priority=priority,
            required_capabilities=capabilities or [],
        )
        
        # Add to queue
        self._task_queue.append(task)
        
        # Execute
        result = await self._execute_task(task, require_consensus)
        
        # Store completed
        self._completed_tasks[task.task_id] = task
        
        return result
    
    async def execute_batch(
        self,
        tasks: list[dict[str, Any]],
        parallel: bool = True,
    ) -> list[AgentOrchestrationResult]:
        """
        Execute multiple tasks.
        
        Args:
            tasks: List of task definitions
            parallel: Execute in parallel
        
        Returns:
            List of results
        """
        if parallel:
            # Execute in parallel (limited by max_concurrent_tasks)
            semaphore = asyncio.Semaphore(self.max_concurrent_tasks)
            
            async def execute_with_semaphore(task_def):
                async with semaphore:
                    return await self.execute_task(**task_def)
            
            results = await asyncio.gather(
                *[execute_with_semaphore(task) for task in tasks],
                return_exceptions=True
            )
            
            return [
                r if isinstance(r, AgentOrchestrationResult) else None
                for r in results
            ]
        else:
            # Execute sequentially
            results = []
            for task_def in tasks:
                result = await self.execute_task(**task_def)
                results.append(result)
            
            return results
    
    async def get_consensus(
        self,
        task_type: str,
        prompt: str,
        context: dict[str, Any] | None = None,
        min_agents: int = 2,
    ) -> AgentOrchestrationResult:
        """
        Get multi-agent consensus on a task.
        
        Args:
            task_type: Type of task
            prompt: Task prompt
            context: Task context
            min_agents: Minimum number of agents for consensus
        
        Returns:
            Consensus result with score
        """
        # Select top agents based on performance
        agents = self._select_best_agents(min_agents)
        
        if len(agents) < min_agents:
            logger.warning(f"Not enough agents for consensus: {len(agents)}/{min_agents}")
        
        # Execute task with all selected agents
        tasks = [
            self.execute_task(
                task_type=task_type,
                prompt=prompt,
                context=context,
                priority=TaskPriority.HIGH,
            )
            for _ in agents
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calculate consensus score
        consensus_score = self._calculate_consensus_score(results)
        
        # Return best result with consensus score
        best_result = max(
            [r for r in results if isinstance(r, AgentOrchestrationResult)],
            key=lambda r: r.response_time,
            default=None
        )
        
        if best_result:
            best_result.consensus_score = consensus_score
        
        return best_result or AgentOrchestrationResult(
            task_id="",
            success=False,
            result=None,
            agent_used="none",
            response_time=0,
            cost_usd=0,
            attempts=0,
            consensus_score=0,
        )
    
    def get_agent_performance(self, agent_type: str | None = None) -> dict[str, Any]:
        """
        Get agent performance metrics.
        
        Args:
            agent_type: Specific agent (None for all)
        
        Returns:
            Performance metrics
        """
        if agent_type:
            perf = self._performance.get(agent_type)
            return perf.to_dict() if perf else {}
        else:
            return {
                agent: perf.to_dict()
                for agent, perf in self._performance.items()
            }
    
    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """
        Get task status.
        
        Args:
            task_id: Task ID
        
        Returns:
            Task status dict or None
        """
        # Check active tasks
        if task_id in self._active_tasks:
            return self._active_tasks[task_id].to_dict()
        
        # Check completed tasks
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id].to_dict()
        
        return None
    
    def get_queue_stats(self) -> dict[str, Any]:
        """Get task queue statistics."""
        return {
            "pending": len(self._task_queue),
            "active": len(self._active_tasks),
            "completed": len(self._completed_tasks),
            "max_concurrent": self.max_concurrent_tasks,
        }
    
    def store_in_shared_memory(self, key: str, value: Any, ttl: int = 3600) -> None:
        """
        Store data in shared memory.
        
        Args:
            key: Memory key
            value: Value to store
            ttl: Time to live in seconds
        """
        self._shared_memory[key] = {
            "value": value,
            "expires_at": time.time() + ttl,
        }
    
    def get_from_shared_memory(self, key: str) -> Any | None:
        """
        Get data from shared memory.
        
        Args:
            key: Memory key
        
        Returns:
            Value or None if expired/not found
        """
        if key not in self._shared_memory:
            return None
        
        entry = self._shared_memory[key]
        
        if time.time() > entry["expires_at"]:
            del self._shared_memory[key]
            return None
        
        return entry["value"]
    
    async def _execute_task(
        self,
        task: Task,
        require_consensus: bool,
    ) -> AgentOrchestrationResult:
        """Execute a single task."""
        # Select best agent
        agent = self._select_best_agent(task.required_capabilities)
        
        if not agent:
            logger.error(f"No suitable agent for task {task.task_id}")
            task.error = "No suitable agent available"
            return AgentOrchestrationResult(
                task_id=task.task_id,
                success=False,
                result=None,
                agent_used="none",
                response_time=0,
                cost_usd=0,
                attempts=0,
            )
        
        # Update task
        task.assigned_agent = agent
        task.started_at = datetime.utcnow().isoformat()
        self._active_tasks[task.task_id] = task
        
        start_time = time.time()
        attempts = 0
        result = None
        error = None
        
        # Execute with retry
        while attempts < task.max_retries:
            try:
                attempts += 1
                
                # Execute with agent
                agent_result = await self._execute_with_agent(
                    agent=agent,
                    task=task,
                )
                
                result = agent_result.get("result")
                cost = agent_result.get("cost_usd", 0.0)
                error = None
                break
                
            except Exception as e:
                error = str(e)
                task.retry_count = attempts
                logger.warning(f"Task {task.task_id} attempt {attempts} failed: {e}")
                
                if attempts < task.max_retries:
                    # Try with different agent
                    agent = self._select_best_agent(
                        task.required_capabilities,
                        exclude=[agent]
                    )
                    task.assigned_agent = agent
                    
                    if not agent:
                        break
                    
                    await asyncio.sleep(1 * attempts)  # Exponential backoff
        
        # Calculate response time
        response_time = time.time() - start_time
        
        # Update task
        task.completed_at = datetime.utcnow().isoformat()
        task.result = result
        task.error = error
        
        # Update performance
        self._update_performance(
            agent=task.assigned_agent or "unknown",
            success=error is None,
            response_time=response_time,
            cost_usd=cost if cost else 0.0,
        )
        
        # Remove from active
        del self._active_tasks[task.task_id]
        
        return AgentOrchestrationResult(
            task_id=task.task_id,
            success=error is None,
            result=result,
            agent_used=task.assigned_agent or "unknown",
            response_time=response_time,
            cost_usd=cost if cost else 0.0,
            attempts=attempts,
        )
    
    async def _execute_with_agent(
        self,
        agent: str,
        task: Task,
    ) -> dict[str, Any]:
        """Execute task with specific agent."""
        # Lazy load agent interface
        if self._agent_interface is None:
            from backend.agents.unified_agent_interface import UnifiedAgentInterface
            self._agent_interface = UnifiedAgentInterface()
        
        # Execute
        response = await self._agent_interface.send_request(
            agent_type=agent,
            prompt=task.prompt,
            context=task.context,
        )
        
        return {
            "result": response.content if hasattr(response, "content") else response,
            "cost_usd": response.cost_usd if hasattr(response, "cost_usd") else 0.0,
        }
    
    def _select_best_agent(
        self,
        capabilities: list[AgentCapability],
        exclude: list[str] | None = None,
    ) -> str | None:
        """Select best agent for capabilities."""
        exclude = exclude or []
        
        # Find agents with required capabilities
        suitable_agents = []
        
        for agent, agent_caps in self.AGENT_CAPABILITIES.items():
            if agent in exclude:
                continue
            
            # Check if agent has all required capabilities
            if all(cap in agent_caps for cap in capabilities):
                perf = self._performance.get(agent)
                if perf:
                    suitable_agents.append((agent, perf.success_rate))
        
        if not suitable_agents:
            # Fallback to any available agent
            suitable_agents = [
                (agent, perf.success_rate)
                for agent, perf in self._performance.items()
                if agent not in exclude
            ]
        
        if not suitable_agents:
            return None
        
        # Select agent with highest success rate
        return max(suitable_agents, key=lambda x: x[1])[0]
    
    def _select_best_agents(self, min_count: int) -> list[str]:
        """Select top N agents by performance."""
        agents = [
            (agent, perf.success_rate)
            for agent, perf in self._performance.items()
            if perf.total_tasks > 0
        ]
        
        if not agents:
            return list(self.AGENT_CAPABILITIES.keys())[:min_count]
        
        # Sort by success rate
        agents.sort(key=lambda x: x[1], reverse=True)
        
        return [agent for agent, _ in agents[:min_count]]
    
    def _update_performance(
        self,
        agent: str,
        success: bool,
        response_time: float,
        cost_usd: float,
    ) -> None:
        """Update agent performance metrics."""
        perf = self._performance.get(agent)
        
        if not perf:
            return
        
        perf.total_tasks += 1
        
        if success:
            perf.successful_tasks += 1
        else:
            perf.failed_tasks += 1
        
        # Update average response time
        perf.avg_response_time = (
            (perf.avg_response_time * (perf.total_tasks - 1) + response_time)
            / perf.total_tasks
        )
        
        perf.total_cost_usd += cost_usd
        perf.last_used = datetime.utcnow().isoformat()
    
    def _calculate_consensus_score(
        self,
        results: list[AgentOrchestrationResult | Exception],
    ) -> float:
        """Calculate consensus score from multiple results."""
        valid_results = [
            r for r in results
            if isinstance(r, AgentOrchestrationResult) and r.success
        ]
        
        if len(valid_results) < 2:
            return 0.0
        
        # Simple consensus: check if results are similar
        # (In production, use more sophisticated comparison)
        first_result = str(valid_results[0].result)
        
        similar_count = sum(
            1 for r in valid_results[1:]
            if str(r.result) == first_result
        )
        
        return similar_count / len(valid_results)


# Global orchestrator instance
_orchestrator: AgentOrchestrator | None = None


def get_agent_orchestrator(max_concurrent_tasks: int = 10) -> AgentOrchestrator:
    """
    Get or create orchestrator instance (singleton).
    
    Args:
        max_concurrent_tasks: Maximum concurrent tasks
    
    Returns:
        AgentOrchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator(max_concurrent_tasks)
    return _orchestrator
