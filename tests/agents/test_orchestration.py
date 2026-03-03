"""
Tests for Enhanced Multi-Agent Orchestration

Run: pytest tests/agents/test_orchestration.py -v
"""

import sys
import asyncio

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import pytest

from backend.agents.orchestration import (
    AgentOrchestrator,
    AgentCapability,
    TaskPriority,
    AgentPerformance,
    Task,
    get_agent_orchestrator,
)


class TestAgentPerformance:
    """Tests for AgentPerformance."""

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        perf = AgentPerformance(
            agent_type="test",
            total_tasks=10,
            successful_tasks=8,
            failed_tasks=2,
        )
        
        assert perf.success_rate == 0.8

    def test_success_rate_zero_tasks(self):
        """Test success rate with zero tasks."""
        perf = AgentPerformance(agent_type="test")
        assert perf.success_rate == 0.0

    def test_avg_cost_per_task(self):
        """Test average cost calculation."""
        perf = AgentPerformance(
            agent_type="test",
            total_tasks=10,
            total_cost_usd=5.0,
        )
        
        assert perf.avg_cost_per_task == 0.5

    def test_to_dict(self):
        """Test conversion to dict."""
        perf = AgentPerformance(
            agent_type="qwen",
            total_tasks=100,
            successful_tasks=90,
        )
        
        data = perf.to_dict()
        
        assert data["agent_type"] == "qwen"
        assert data["total_tasks"] == 100
        assert data["success_rate"] == 0.9


class TestTask:
    """Tests for Task."""

    def test_task_creation(self):
        """Test task creation."""
        task = Task(
            task_id="task_123",
            task_type="test",
            prompt="Test prompt",
        )
        
        assert task.task_id == "task_123"
        assert task.status == "pending"
        assert task.retry_count == 0

    def test_task_status_pending(self):
        """Test pending status."""
        task = Task(task_id="t1", task_type="test", prompt="p")
        assert task.status == "pending"

    def test_task_status_running(self, mocker):
        """Test running status."""
        task = Task(task_id="t1", task_type="test", prompt="p")
        task.started_at = "2026-03-03T00:00:00"
        assert task.status == "running"

    def test_task_status_completed(self):
        """Test completed status."""
        task = Task(task_id="t1", task_type="test", prompt="p")
        task.completed_at = "2026-03-03T00:00:00"
        assert task.status == "completed"

    def test_task_status_failed(self):
        """Test failed status."""
        task = Task(task_id="t1", task_type="test", prompt="p")
        task.error = "Test error"
        assert task.status == "failed"

    def test_task_to_dict(self):
        """Test task serialization."""
        task = Task(
            task_id="t1",
            task_type="analysis",
            prompt="Analyze data",
            priority=TaskPriority.HIGH,
        )
        
        data = task.to_dict()
        
        assert data["task_id"] == "t1"
        assert data["priority"] == "high"


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance."""
        return AgentOrchestrator(max_concurrent_tasks=5)

    def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator initialization."""
        assert orchestrator is not None
        assert orchestrator.max_concurrent_tasks == 5
        assert len(orchestrator._performance) == 3  # deepseek, qwen, perplexity

    def test_select_best_agent_no_capabilities(self, orchestrator):
        """Test agent selection without capabilities."""
        agent = orchestrator._select_best_agent([])
        
        # Should return best performing agent
        assert agent in orchestrator.AGENT_CAPABILITIES.keys()

    def test_select_best_agent_with_capabilities(self, orchestrator):
        """Test agent selection with capabilities."""
        agent = orchestrator._select_best_agent(
            [AgentCapability.CODE_GENERATION]
        )
        
        # deepseek and qwen support code generation
        assert agent in ["deepseek", "qwen"]

    def test_select_best_agent_exclude(self, orchestrator):
        """Test agent selection with exclusion."""
        agent = orchestrator._select_best_agent(
            [],
            exclude=["deepseek", "qwen"]
        )
        
        # Should return perplexity
        assert agent == "perplexity"

    def test_get_agent_performance(self, orchestrator):
        """Test getting agent performance."""
        perf = orchestrator.get_agent_performance("deepseek")
        
        assert "agent_type" in perf
        assert perf["agent_type"] == "deepseek"

    def test_get_all_agent_performance(self, orchestrator):
        """Test getting all agent performance."""
        all_perf = orchestrator.get_agent_performance()
        
        assert len(all_perf) == 3
        assert "deepseek" in all_perf
        assert "qwen" in all_perf
        assert "perplexity" in all_perf

    def test_get_queue_stats(self, orchestrator):
        """Test getting queue statistics."""
        stats = orchestrator.get_queue_stats()
        
        assert "pending" in stats
        assert "active" in stats
        assert "completed" in stats
        assert "max_concurrent" in stats

    def test_shared_memory_store_and_get(self, orchestrator):
        """Test shared memory operations."""
        orchestrator.store_in_shared_memory("test_key", {"data": "value"})
        
        value = orchestrator.get_from_shared_memory("test_key")
        
        assert value == {"data": "value"}

    def test_shared_memory_expired(self, orchestrator):
        """Test shared memory expiration."""
        # Store with 0 second TTL (already expired)
        orchestrator.store_in_shared_memory("test_key", "value", ttl=0)
        
        # Wait a bit
        import time
        time.sleep(0.1)
        
        # Should be expired
        value = orchestrator.get_from_shared_memory("test_key")
        assert value is None

    def test_shared_memory_nonexistent(self, orchestrator):
        """Test getting nonexistent key."""
        value = orchestrator.get_from_shared_memory("nonexistent")
        assert value is None

    def test_update_performance(self, orchestrator):
        """Test performance update."""
        orchestrator._update_performance(
            agent="deepseek",
            success=True,
            response_time=1.0,
            cost_usd=0.01,
        )
        
        perf = orchestrator._performance["deepseek"]
        
        assert perf.total_tasks == 1
        assert perf.successful_tasks == 1
        assert perf.avg_response_time == 1.0
        assert perf.total_cost_usd == 0.01

    def test_select_best_agents(self, orchestrator):
        """Test selecting multiple best agents."""
        # First add some performance data
        orchestrator._update_performance("deepseek", True, 1.0, 0.01)
        orchestrator._update_performance("qwen", True, 1.0, 0.01)
        
        agents = orchestrator._select_best_agents(2)
        
        assert len(agents) >= 2

    def test_get_task_status_nonexistent(self, orchestrator):
        """Test getting nonexistent task status."""
        status = orchestrator.get_task_status("nonexistent")
        assert status is None

    @pytest.mark.asyncio
    async def test_execute_task_mock(self, orchestrator, mocker):
        """Test task execution (mocked)."""
        # Mock agent interface
        mock_interface = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.content = "Test result"
        mock_response.cost_usd = 0.01
        mock_interface.send_request = mocker.AsyncMock(return_value=mock_response)
        orchestrator._agent_interface = mock_interface
        
        result = await orchestrator.execute_task(
            task_type="test",
            prompt="Test prompt",
            priority=TaskPriority.NORMAL,
        )
        
        assert result.task_id
        assert result.success is True
        assert result.agent_used in orchestrator.AGENT_CAPABILITIES.keys()

    def test_agent_capabilities_mapping(self, orchestrator):
        """Test agent capabilities mapping."""
        capabilities = orchestrator.AGENT_CAPABILITIES
        
        assert "deepseek" in capabilities
        assert "qwen" in capabilities
        assert "perplexity" in capabilities
        
        # Check deepseek capabilities
        assert AgentCapability.CODE_GENERATION in capabilities["deepseek"]
        
        # Check perplexity capabilities
        assert AgentCapability.MARKET_ANALYSIS in capabilities["perplexity"]


class TestGlobalOrchestrator:
    """Tests for global orchestrator functions."""

    def test_get_agent_orchestrator_singleton(self):
        """Test singleton pattern."""
        o1 = get_agent_orchestrator()
        o2 = get_agent_orchestrator()
        
        # Should be same instance
        assert o1 is o2

    def test_get_agent_orchestrator_custom_concurrency(self):
        """Test custom concurrency setting."""
        orchestrator = AgentOrchestrator(max_concurrent_tasks=20)
        assert orchestrator.max_concurrent_tasks == 20


class TestTaskPriority:
    """Tests for TaskPriority enum."""

    def test_priority_values(self):
        """Test priority enum values."""
        assert TaskPriority.LOW.value == "low"
        assert TaskPriority.NORMAL.value == "normal"
        assert TaskPriority.HIGH.value == "high"
        assert TaskPriority.CRITICAL.value == "critical"


class TestAgentCapability:
    """Tests for AgentCapability enum."""

    def test_capability_values(self):
        """Test capability enum values."""
        assert AgentCapability.CODE_GENERATION.value == "code_generation"
        assert AgentCapability.MARKET_ANALYSIS.value == "market_analysis"
        assert AgentCapability.VALIDATION.value == "validation"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
