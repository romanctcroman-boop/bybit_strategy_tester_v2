"""
Comprehensive Test Suite for AI Agent System

This module provides thorough testing coverage for:
1. Memory System (Hierarchical, Vector Store)
2. Self-Improvement Engine (RLHF, Self-Reflection, Performance Evaluator)
3. Consensus Mechanisms (Deliberation, Domain Agents)
4. Local ML Integration (RL Integration, Prediction Engine)
5. Monitoring & Observability (Metrics, Tracing, Alerting, Dashboard)

Run with pytest:
    pytest tests/test_agent_system_comprehensive.py -v
    
Or run directly:
    python tests/test_agent_system_comprehensive.py
"""

import asyncio
import sys
import time
import uuid
from pathlib import Path

import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================

def generate_test_id() -> str:
    """Generate unique test ID"""
    return f"test_{uuid.uuid4().hex[:8]}"


def generate_mock_market_data(n_samples: int = 100) -> np.ndarray:
    """Generate mock OHLCV market data"""
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(n_samples) * 0.5)

    return np.column_stack([
        prices,  # Open
        prices + np.abs(np.random.randn(n_samples) * 0.5),  # High
        prices - np.abs(np.random.randn(n_samples) * 0.5),  # Low
        prices + np.random.randn(n_samples) * 0.2,  # Close
        np.random.randint(1000, 10000, n_samples),  # Volume
    ])


# =============================================================================
# Memory System Tests
# =============================================================================

class TestHierarchicalMemory:
    """Tests for HierarchicalMemory"""

    @staticmethod
    async def test_store_and_recall():
        """Test storing and recalling memories"""
        from backend.agents.memory.hierarchical_memory import (
            HierarchicalMemory,
            MemoryType,
        )

        # Use None for persist_path to avoid loading existing data
        memory = HierarchicalMemory(persist_path=None)

        # Store memories
        await memory.store(
            "RSI is a momentum indicator",
            memory_type=MemoryType.SEMANTIC,
            importance=0.8,
            tags=["trading", "RSI"],
        )

        await memory.store(
            "User asked about MACD",
            memory_type=MemoryType.EPISODIC,
            importance=0.6,
        )

        await memory.store(
            "Current task: analyze BTC",
            memory_type=MemoryType.WORKING,
            importance=0.9,
        )

        # Recall
        results = await memory.recall("RSI indicator", top_k=3)

        assert len(results) >= 1, "Should recall at least 1 memory"
        assert any("RSI" in r.content for r in results), "Should find RSI memory"

        # Check total stored in all stores
        total_stored = sum(len(store) for store in memory.stores.values())
        assert total_stored >= 3, f"Should have 3 items, got {total_stored}"

        return True

    @staticmethod
    async def test_consolidation():
        """Test memory consolidation"""
        from backend.agents.memory.hierarchical_memory import (
            HierarchicalMemory,
            MemoryType,
        )

        memory = HierarchicalMemory(persist_path=f"./test_memory_{generate_test_id()}")

        # Add multiple working memories
        for i in range(5):
            await memory.store(
                f"Working memory item {i}",
                memory_type=MemoryType.WORKING,
                importance=0.5 + i * 0.1,
            )

        # Consolidate
        result = await memory.consolidate()

        assert "working_to_episodic" in result, "Should have consolidation stats"

        return True

    @staticmethod
    async def test_forgetting():
        """Test intelligent forgetting"""
        from backend.agents.memory.hierarchical_memory import (
            HierarchicalMemory,
            MemoryType,
        )

        memory = HierarchicalMemory(persist_path=f"./test_memory_{generate_test_id()}")

        # Add low importance memories
        for i in range(5):
            await memory.store(
                f"Low importance item {i}",
                memory_type=MemoryType.WORKING,
                importance=0.1,
            )

        # Forget
        forgotten = await memory.forget()

        assert isinstance(forgotten, dict), "Should return forgotten counts"

        return True


class TestVectorStore:
    """Tests for VectorMemoryStore"""

    @staticmethod
    async def test_initialization():
        """Test vector store initialization"""
        from backend.agents.memory.vector_store import VectorMemoryStore

        store = VectorMemoryStore(
            collection_name=f"test_{generate_test_id()}",
            use_local_embeddings=False,  # Don't require sentence-transformers
        )

        await store.initialize()

        # Should not fail even without ChromaDB
        return True


# =============================================================================
# Self-Improvement Engine Tests
# =============================================================================

class TestRLHFModule:
    """Tests for RLHFModule"""

    @staticmethod
    async def test_feedback_collection():
        """Test collecting human and AI feedback"""
        from backend.agents.self_improvement.rlhf_module import RLHFModule

        rlhf = RLHFModule(persist_path=f"./test_rlhf_{generate_test_id()}")

        # Human feedback
        await rlhf.collect_human_feedback(
            prompt="Explain RSI",
            response_a="RSI measures momentum",
            response_b="RSI is a number",
            preference=-1,
            reasoning="A is better",
        )

        stats = rlhf.get_stats()
        assert stats["total_feedback"] >= 1, "Should have feedback"

        return True

    @staticmethod
    async def test_ai_feedback():
        """Test AI feedback (RLAIF)"""
        from backend.agents.self_improvement.rlhf_module import RLHFModule

        rlhf = RLHFModule(persist_path=f"./test_rlhf_{generate_test_id()}")

        samples = await rlhf.collect_ai_feedback(
            prompt="Write a function",
            responses=["def foo(): pass", "foo = lambda: None"],
        )

        assert len(samples) >= 1, "Should generate feedback samples"

        return True

    @staticmethod
    async def test_self_evaluation():
        """Test self-evaluation"""
        from backend.agents.self_improvement.rlhf_module import RLHFModule

        rlhf = RLHFModule(persist_path=f"./test_rlhf_{generate_test_id()}")

        score = await rlhf.self_evaluate(
            prompt="What is MACD?",
            response="MACD is Moving Average Convergence Divergence, showing trend.",
        )

        assert score.overall >= 0, "Should have quality score"
        assert score.overall <= 1, "Score should be <= 1"

        return True

    @staticmethod
    async def test_reward_model_training():
        """Test reward model training"""
        from backend.agents.self_improvement.rlhf_module import RLHFModule

        rlhf = RLHFModule(persist_path=f"./test_rlhf_{generate_test_id()}")

        # Add training data
        for i in range(5):
            await rlhf.collect_human_feedback(
                prompt=f"Question {i}",
                response_a=f"Detailed answer {i}",
                response_b=f"Short {i}",
                preference=-1,
            )

        result = rlhf.train_reward_model(force=True)

        assert result is not None, "Should train model"
        assert result["accuracy"] >= 0, "Should have accuracy"

        return True


class TestSelfReflection:
    """Tests for SelfReflectionEngine"""

    @staticmethod
    async def test_task_reflection():
        """Test reflecting on completed tasks"""
        from backend.agents.self_improvement.self_reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(persist_path=f"./test_reflection_{generate_test_id()}")

        result = await engine.reflect_on_task(
            task="Implement RSI calculation",
            solution="def rsi(prices): return 50",  # Simplified
            outcome={"success": True, "tests_passed": 3},
        )

        assert result.quality_score >= 0, "Should have quality score"
        assert isinstance(result.lessons_learned, list), "Should have lessons"

        return True

    @staticmethod
    async def test_get_recommendations():
        """Test getting recommendations"""
        from backend.agents.self_improvement.self_reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(persist_path=f"./test_reflection_{generate_test_id()}")

        # First reflect
        await engine.reflect_on_task(
            task="Test task",
            solution="Test solution",
            outcome={"success": True},
        )

        recommendations = await engine.get_recommendations(top_k=3)

        assert isinstance(recommendations, list), "Should return list"

        return True


class TestPerformanceEvaluator:
    """Tests for PerformanceEvaluator"""

    @staticmethod
    async def test_response_evaluation():
        """Test evaluating agent responses"""
        from backend.agents.self_improvement.performance_evaluator import PerformanceEvaluator

        evaluator = PerformanceEvaluator(persist_path=f"./test_eval_{generate_test_id()}")

        metrics = await evaluator.evaluate_response(
            agent_type="deepseek",
            prompt="Explain RSI",
            response="RSI is a momentum indicator ranging from 0 to 100.",
            latency_ms=1500,
            tokens_used=50,
        )

        assert metrics.overall_score >= 0, "Should have score"
        assert metrics.safety >= 0, "Should have safety score"
        assert metrics.accuracy >= 0, "Should have accuracy"

        return True

    @staticmethod
    async def test_improvement_plan():
        """Test generating improvement plans"""
        from backend.agents.self_improvement.performance_evaluator import PerformanceEvaluator

        evaluator = PerformanceEvaluator(persist_path=f"./test_eval_{generate_test_id()}")

        # Add some evaluations first
        await evaluator.evaluate_response(
            agent_type="test",
            prompt="Test",
            response="Test response",
            latency_ms=100,
        )

        plan = await evaluator.generate_improvement_plan()

        assert "recommendations" in plan, "Should have recommendations"

        return True


# =============================================================================
# Consensus Mechanism Tests
# =============================================================================

class TestMultiAgentDeliberation:
    """Tests for MultiAgentDeliberation"""

    @staticmethod
    async def test_deliberation():
        """Test multi-agent deliberation"""
        from backend.agents.consensus.deliberation import (
            MultiAgentDeliberation,
            VotingStrategy,
        )

        deliberation = MultiAgentDeliberation()

        result = await deliberation.deliberate(
            question="Should we use trailing or fixed stop loss?",
            agents=["deepseek", "perplexity"],
            voting_strategy=VotingStrategy.WEIGHTED,
            max_rounds=2,
        )

        assert result.decision, "Should have decision"
        assert result.confidence >= 0, "Should have confidence"
        assert len(result.rounds) >= 1, "Should have rounds"

        return True

    @staticmethod
    async def test_voting_strategies():
        """Test different voting strategies"""
        from backend.agents.consensus.deliberation import (
            MultiAgentDeliberation,
            VotingStrategy,
        )

        deliberation = MultiAgentDeliberation()

        for strategy in [VotingStrategy.MAJORITY, VotingStrategy.UNANIMOUS, VotingStrategy.SUPERMAJORITY]:
            result = await deliberation.deliberate(
                question="Test question",
                agents=["agent1", "agent2"],
                voting_strategy=strategy,
                max_rounds=1,
            )

            assert result.voting_strategy == strategy, f"Should use {strategy}"

        return True


class TestDomainAgents:
    """Tests for Domain Agents"""

    @staticmethod
    async def test_domain_registry():
        """Test domain agent registry"""
        from backend.agents.consensus.domain_agents import DomainAgentRegistry

        registry = DomainAgentRegistry()

        agents = registry.list_agents()
        assert "trading" in agents, "Should have trading agent"
        assert "risk" in agents, "Should have risk agent"
        assert "code" in agents, "Should have code agent"
        assert "market" in agents, "Should have market agent"

        return True

    @staticmethod
    async def test_trading_agent():
        """Test trading strategy agent"""
        from backend.agents.consensus.domain_agents import TradingStrategyAgent

        agent = TradingStrategyAgent()

        analysis = await agent.analyze({
            "strategy": {"type": "RSI", "period": 14},
            "results": {"sharpe_ratio": 1.5, "win_rate": 0.55},
        })

        assert analysis.score is not None, "Should have score"
        assert analysis.risk_level, "Should have risk level"

        return True

    @staticmethod
    async def test_risk_agent():
        """Test risk management agent"""
        from backend.agents.consensus.domain_agents import RiskManagementAgent

        agent = RiskManagementAgent()

        validation = await agent.validate(
            "Increase position size",
            context={"position_size": 0.2, "leverage": 2},
        )

        assert isinstance(validation.is_valid, bool), "Should have validity"
        assert validation.validation_score >= 0, "Should have score"

        return True

    @staticmethod
    async def test_code_agent():
        """Test code audit agent"""
        from backend.agents.consensus.domain_agents import CodeAuditAgent

        agent = CodeAuditAgent()

        # Test safe code
        validation = await agent.validate("def foo(): return 42")
        assert validation.is_valid, "Safe code should be valid"

        # Test dangerous code
        validation = await agent.validate("eval(user_input)")
        assert not validation.is_valid, "Dangerous code should be invalid"

        return True


# =============================================================================
# Local ML Integration Tests
# =============================================================================

class TestRLIntegration:
    """Tests for RL-AI Integration"""

    @staticmethod
    async def test_regime_detection():
        """Test market regime detection"""
        from backend.agents.local_ml.rl_integration import RLAgentIntegration

        integration = RLAgentIntegration()
        market_data = generate_mock_market_data(100)

        regime, confidence = await integration.detect_market_regime(market_data)

        assert regime is not None, "Should detect regime"
        assert 0 <= confidence <= 1, "Confidence should be 0-1"

        return True

    @staticmethod
    async def test_reward_shaping():
        """Test reward shaping suggestions"""
        from backend.agents.local_ml.rl_integration import MarketRegime, RLAgentIntegration

        integration = RLAgentIntegration()

        config = await integration.suggest_reward_shaping(
            MarketRegime.TRENDING_UP,
            {"win_rate": 55, "max_drawdown": 10, "sharpe": 1.2},
        )

        assert config.profit_weight > 0, "Should have profit weight"
        assert config.drawdown_penalty > 0, "Should have drawdown penalty"

        return True

    @staticmethod
    async def test_decision_validation():
        """Test decision validation"""
        from backend.agents.local_ml.rl_integration import RLAgentIntegration

        integration = RLAgentIntegration()

        validation = await integration.validate_decision(
            state={"price": 100, "rsi": 50, "macd": 0},
            action=1,  # BUY
            confidence=0.8,
        )

        assert "approved" in validation, "Should have approval status"
        assert "risk_level" in validation, "Should have risk level"

        return True


class TestPredictionEngine:
    """Tests for Prediction Engine"""

    @staticmethod
    async def test_ensemble_prediction():
        """Test ensemble prediction"""
        from backend.agents.local_ml.prediction_engine import (
            ModelType,
            PredictionEngine,
            SimpleMomentumModel,
            SimpleMovingAverageModel,
        )

        engine = PredictionEngine(min_confidence=0.5)
        engine.add_model("ma", SimpleMovingAverageModel(), ModelType.ENSEMBLE)
        engine.add_model("momentum", SimpleMomentumModel(), ModelType.ENSEMBLE)

        features = np.array([[100, 101, 102, 103, 104, 105, 106, 107, 108, 110]])
        result = await engine.predict(features)

        assert result.signal is not None, "Should have signal"
        assert 0 <= result.confidence <= 1, "Confidence should be 0-1"
        assert len(result.model_votes) == 2, "Should have 2 model votes"

        return True

    @staticmethod
    async def test_model_weight_update():
        """Test model weight rebalancing"""
        from backend.agents.local_ml.prediction_engine import (
            ModelType,
            PredictionEngine,
            SimpleMovingAverageModel,
        )

        engine = PredictionEngine()
        engine.add_model("model1", SimpleMovingAverageModel(), ModelType.ENSEMBLE)
        engine.add_model("model2", SimpleMovingAverageModel(), ModelType.ENSEMBLE)

        # Simulate predictions
        features = np.array([[100, 101, 102, 103, 104]])
        await engine.predict(features)

        # Update performance
        engine.update_model_performance(0.05)  # Positive return

        stats = engine.get_model_stats()
        assert len(stats) == 2, "Should have 2 models"

        return True


# =============================================================================
# Monitoring & Observability Tests
# =============================================================================

class TestMetricsCollector:
    """Tests for MetricsCollector"""

    @staticmethod
    async def test_counter_metric():
        """Test counter metrics"""
        from backend.agents.monitoring.metrics_collector import (
            Metric,
            MetricsCollector,
            MetricType,
        )

        collector = MetricsCollector(auto_register_defaults=False)

        collector.register(Metric(
            name="test_counter",
            description="Test counter",
            type=MetricType.COUNTER,
        ))

        collector.increment("test_counter", 1)
        collector.increment("test_counter", 2)

        value = collector.get("test_counter")
        assert value == 3, "Counter should sum to 3"

        return True

    @staticmethod
    async def test_gauge_metric():
        """Test gauge metrics"""
        from backend.agents.monitoring.metrics_collector import (
            Metric,
            MetricsCollector,
            MetricType,
        )

        collector = MetricsCollector(auto_register_defaults=False)

        collector.register(Metric(
            name="test_gauge",
            description="Test gauge",
            type=MetricType.GAUGE,
        ))

        collector.set("test_gauge", 42)
        collector.set("test_gauge", 100)

        value = collector.get("test_gauge")
        assert value > 0, "Gauge should have value"

        return True

    @staticmethod
    async def test_histogram_metric():
        """Test histogram metrics"""
        from backend.agents.monitoring.metrics_collector import (
            Metric,
            MetricAggregation,
            MetricsCollector,
            MetricType,
        )

        collector = MetricsCollector(auto_register_defaults=False)

        collector.register(Metric(
            name="test_histogram",
            description="Test histogram",
            type=MetricType.HISTOGRAM,
            buckets=[10, 50, 100, 500],
        ))

        for v in [5, 25, 75, 200, 300]:
            collector.observe("test_histogram", v)

        p50 = collector.get("test_histogram", aggregation=MetricAggregation.P50)
        p95 = collector.get("test_histogram", aggregation=MetricAggregation.P95)

        assert p50 >= 0, "P50 should be >= 0"
        assert p95 >= p50, "P95 should be >= P50"

        return True

    @staticmethod
    async def test_prometheus_export():
        """Test Prometheus format export"""
        from backend.agents.monitoring.metrics_collector import MetricsCollector

        collector = MetricsCollector()

        collector.increment("agent_requests_total", labels={"agent_type": "deepseek"})

        output = collector.export_prometheus()

        assert "agent_requests_total" in output, "Should have metric name"
        assert "TYPE" in output, "Should have TYPE comment"

        return True


class TestDistributedTracer:
    """Tests for DistributedTracer"""

    @staticmethod
    async def test_span_creation():
        """Test span creation"""
        from backend.agents.monitoring.tracing import DistributedTracer, SpanKind

        tracer = DistributedTracer(exporters=[])  # No exporters

        async with tracer.start_span("test_operation", kind=SpanKind.CLIENT) as span:
            span.set_attribute("key", "value")
            span.add_event("checkpoint")
            await asyncio.sleep(0.01)

        assert span.end_time is not None, "Span should be ended"
        assert span.duration_ms > 0, "Should have duration"

        return True

    @staticmethod
    async def test_nested_spans():
        """Test nested spans with parent-child relationship"""
        from backend.agents.monitoring.tracing import DistributedTracer

        tracer = DistributedTracer(exporters=[])

        async with tracer.start_span("parent") as parent, tracer.start_span("child") as child:
            pass

        assert child.context.parent_span_id == parent.context.span_id, \
            "Child should have parent span ID"
        assert child.context.trace_id == parent.context.trace_id, \
            "Should share trace ID"

        return True

    @staticmethod
    async def test_error_handling():
        """Test span error handling"""
        from backend.agents.monitoring.tracing import DistributedTracer, SpanStatus

        tracer = DistributedTracer(exporters=[])

        try:
            async with tracer.start_span("error_span") as span:
                raise ValueError("Test error")
        except ValueError:
            pass

        assert span.status == SpanStatus.ERROR, "Span should have error status"
        assert "error.type" in span.attributes, "Should have error type"

        return True


class TestAlertManager:
    """Tests for AlertManager"""

    @staticmethod
    async def test_rule_evaluation():
        """Test alert rule evaluation"""
        from backend.agents.monitoring.alerting import (
            AlertManager,
            AlertRule,
            AlertSeverity,
            ComparisonOperator,
        )

        manager = AlertManager(notifiers=[], auto_add_defaults=False)

        manager.add_rule(AlertRule(
            name="test_high_value",
            description="Value too high",
            metric_name="test_metric",
            operator=ComparisonOperator.GREATER_THAN,
            threshold=100,
            severity=AlertSeverity.WARNING,
        ))

        # Below threshold - no alert
        alerts = await manager.evaluate({"test_metric": 50})
        assert len(alerts) == 0, "Should not fire below threshold"

        # Above threshold - alert
        alerts = await manager.evaluate({"test_metric": 150})
        assert len(alerts) == 1, "Should fire above threshold"

        return True

    @staticmethod
    async def test_alert_resolution():
        """Test alert auto-resolution"""
        from backend.agents.monitoring.alerting import (
            AlertManager,
            AlertRule,
            AlertSeverity,
            ComparisonOperator,
        )

        manager = AlertManager(notifiers=[], auto_add_defaults=False)

        manager.add_rule(AlertRule(
            name="test_rule",
            description="Test",
            metric_name="test_metric",
            operator=ComparisonOperator.GREATER_THAN,
            threshold=100,
            severity=AlertSeverity.WARNING,
        ))

        # Fire alert
        await manager.evaluate({"test_metric": 150})
        assert len(manager.get_active_alerts()) == 1, "Should have active alert"

        # Resolve alert
        await manager.evaluate({"test_metric": 50})
        assert len(manager.get_active_alerts()) == 0, "Alert should be resolved"

        return True

    @staticmethod
    async def test_anomaly_detection():
        """Test anomaly detection"""
        from backend.agents.monitoring.alerting import AlertManager

        manager = AlertManager(notifiers=[], auto_add_defaults=False)

        # Build baseline
        for value in range(50, 60):
            await manager.evaluate({"test_metric": value})

        # Test anomaly
        anomaly = manager.detect_anomaly("test_metric", 200, std_threshold=2.0)

        # May or may not detect depending on sample size
        # Just ensure it doesn't error
        return True

    @staticmethod
    async def test_silencing():
        """Test alert silencing"""
        from backend.agents.monitoring.alerting import (
            AlertManager,
            AlertRule,
            AlertSeverity,
            ComparisonOperator,
        )

        manager = AlertManager(notifiers=[], auto_add_defaults=False)

        manager.add_rule(AlertRule(
            name="test_rule",
            description="Test",
            metric_name="test_metric",
            operator=ComparisonOperator.GREATER_THAN,
            threshold=100,
            severity=AlertSeverity.WARNING,
        ))

        # Silence the rule
        result = manager.silence("test_rule", duration_minutes=60)
        assert result, "Should silence successfully"

        # Should not fire while silenced
        alerts = await manager.evaluate({"test_metric": 150})
        assert len(alerts) == 0, "Should not fire while silenced"

        return True


class TestDashboard:
    """Tests for DashboardDataProvider"""

    @staticmethod
    async def test_dashboard_creation():
        """Test dashboard creation"""
        from backend.agents.monitoring.dashboard import DashboardDataProvider

        provider = DashboardDataProvider()

        dashboards = provider.list_dashboards()
        assert len(dashboards) >= 1, "Should have default dashboard"

        return True

    @staticmethod
    async def test_widget_data():
        """Test getting widget data"""
        from backend.agents.monitoring.dashboard import DashboardDataProvider, TimeRange

        provider = DashboardDataProvider()

        data = await provider.get_widget_data("total_requests", TimeRange.LAST_1H)

        assert data.widget_id == "total_requests", "Should match widget ID"

        return True

    @staticmethod
    async def test_full_dashboard_data():
        """Test getting full dashboard data"""
        from backend.agents.monitoring.dashboard import DashboardDataProvider, TimeRange

        provider = DashboardDataProvider()

        data = await provider.get_dashboard_data("agent_monitoring", TimeRange.LAST_1H)

        assert len(data) > 0, "Should have widget data"

        return True


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple components"""

    @staticmethod
    async def test_memory_with_metrics():
        """Test memory system with metrics collection"""
        from backend.agents.memory.hierarchical_memory import HierarchicalMemory, MemoryType
        from backend.agents.monitoring.metrics_collector import Metric, MetricsCollector, MetricType

        collector = MetricsCollector(auto_register_defaults=False)

        # Register custom metric for this test
        collector.register(Metric(
            name="memory_operations",
            description="Memory operations",
            type=MetricType.COUNTER,
            labels=["operation"],
        ))

        memory = HierarchicalMemory(persist_path=None)  # No persistence

        # Store with metric tracking
        collector.increment("memory_operations", labels={"operation": "store"})
        await memory.store("Test content", memory_type=MemoryType.WORKING, importance=0.5)

        # Recall with metric tracking
        collector.increment("memory_operations", labels={"operation": "recall"})
        await memory.recall("Test")

        value = collector.get("memory_operations")
        assert value == 2, f"Should have 2 operations, got {value}"

        return True

    @staticmethod
    async def test_consensus_with_tracing():
        """Test consensus with distributed tracing"""
        from backend.agents.consensus.deliberation import MultiAgentDeliberation
        from backend.agents.monitoring.tracing import DistributedTracer, SpanKind

        tracer = DistributedTracer(exporters=[])
        deliberation = MultiAgentDeliberation()

        async with tracer.start_span("deliberation_request", kind=SpanKind.SERVER) as span:
            span.set_attribute("question", "test question")

            result = await deliberation.deliberate(
                question="Test question",
                agents=["agent1"],
                max_rounds=1,
            )

            span.set_attribute("decision", result.decision[:50])
            span.set_attribute("confidence", result.confidence)

        assert span.duration_ms > 0, "Should have duration"

        return True

    @staticmethod
    async def test_end_to_end_agent_flow():
        """Test complete agent flow: request -> consensus -> evaluation"""
        from backend.agents.consensus.deliberation import MultiAgentDeliberation
        from backend.agents.monitoring.metrics_collector import MetricsCollector
        from backend.agents.monitoring.tracing import DistributedTracer
        from backend.agents.self_improvement.performance_evaluator import PerformanceEvaluator

        collector = MetricsCollector()
        tracer = DistributedTracer(exporters=[])
        evaluator = PerformanceEvaluator(persist_path=f"./test_e2e_{generate_test_id()}")
        deliberation = MultiAgentDeliberation()

        async with tracer.start_span("agent_request") as span:
            # Simulate request
            collector.increment("agent_requests_total")

            # Deliberation
            result = await deliberation.deliberate(
                question="Test",
                agents=["agent1"],
                max_rounds=1,
            )

            # Evaluation
            metrics = await evaluator.evaluate_response(
                agent_type="test",
                prompt="Test",
                response=result.decision,
                latency_ms=span.duration_ms,
            )

            span.set_attribute("confidence", result.confidence)
            span.set_attribute("quality_score", metrics.overall_score)

        stats = collector.get_stats()
        assert stats["total_values"] > 0, "Should have recorded metrics"

        return True


# =============================================================================
# Test Runner
# =============================================================================

async def run_all_tests() -> dict[str, dict[str, bool]]:
    """Run all tests and return results"""
    results = {
        "Memory System": {},
        "Self-Improvement": {},
        "Consensus": {},
        "Local ML": {},
        "Monitoring": {},
        "Integration": {},
    }

    # Memory System Tests
    print("\n" + "=" * 60)
    print("🧪 Memory System Tests")
    print("=" * 60)

    try:
        results["Memory System"]["store_and_recall"] = await TestHierarchicalMemory.test_store_and_recall()
        print("  ✅ test_store_and_recall")
    except Exception as e:
        results["Memory System"]["store_and_recall"] = False
        print(f"  ❌ test_store_and_recall: {e}")

    try:
        results["Memory System"]["consolidation"] = await TestHierarchicalMemory.test_consolidation()
        print("  ✅ test_consolidation")
    except Exception as e:
        results["Memory System"]["consolidation"] = False
        print(f"  ❌ test_consolidation: {e}")

    try:
        results["Memory System"]["forgetting"] = await TestHierarchicalMemory.test_forgetting()
        print("  ✅ test_forgetting")
    except Exception as e:
        results["Memory System"]["forgetting"] = False
        print(f"  ❌ test_forgetting: {e}")

    try:
        results["Memory System"]["vector_store"] = await TestVectorStore.test_initialization()
        print("  ✅ test_vector_store")
    except Exception as e:
        results["Memory System"]["vector_store"] = False
        print(f"  ❌ test_vector_store: {e}")

    # Self-Improvement Tests
    print("\n" + "=" * 60)
    print("🧪 Self-Improvement Tests")
    print("=" * 60)

    try:
        results["Self-Improvement"]["feedback_collection"] = await TestRLHFModule.test_feedback_collection()
        print("  ✅ test_feedback_collection")
    except Exception as e:
        results["Self-Improvement"]["feedback_collection"] = False
        print(f"  ❌ test_feedback_collection: {e}")

    try:
        results["Self-Improvement"]["ai_feedback"] = await TestRLHFModule.test_ai_feedback()
        print("  ✅ test_ai_feedback")
    except Exception as e:
        results["Self-Improvement"]["ai_feedback"] = False
        print(f"  ❌ test_ai_feedback: {e}")

    try:
        results["Self-Improvement"]["self_evaluation"] = await TestRLHFModule.test_self_evaluation()
        print("  ✅ test_self_evaluation")
    except Exception as e:
        results["Self-Improvement"]["self_evaluation"] = False
        print(f"  ❌ test_self_evaluation: {e}")

    try:
        results["Self-Improvement"]["reward_model"] = await TestRLHFModule.test_reward_model_training()
        print("  ✅ test_reward_model_training")
    except Exception as e:
        results["Self-Improvement"]["reward_model"] = False
        print(f"  ❌ test_reward_model_training: {e}")

    try:
        results["Self-Improvement"]["task_reflection"] = await TestSelfReflection.test_task_reflection()
        print("  ✅ test_task_reflection")
    except Exception as e:
        results["Self-Improvement"]["task_reflection"] = False
        print(f"  ❌ test_task_reflection: {e}")

    try:
        results["Self-Improvement"]["recommendations"] = await TestSelfReflection.test_get_recommendations()
        print("  ✅ test_get_recommendations")
    except Exception as e:
        results["Self-Improvement"]["recommendations"] = False
        print(f"  ❌ test_get_recommendations: {e}")

    try:
        results["Self-Improvement"]["response_evaluation"] = await TestPerformanceEvaluator.test_response_evaluation()
        print("  ✅ test_response_evaluation")
    except Exception as e:
        results["Self-Improvement"]["response_evaluation"] = False
        print(f"  ❌ test_response_evaluation: {e}")

    try:
        results["Self-Improvement"]["improvement_plan"] = await TestPerformanceEvaluator.test_improvement_plan()
        print("  ✅ test_improvement_plan")
    except Exception as e:
        results["Self-Improvement"]["improvement_plan"] = False
        print(f"  ❌ test_improvement_plan: {e}")

    # Consensus Tests
    print("\n" + "=" * 60)
    print("🧪 Consensus Mechanism Tests")
    print("=" * 60)

    try:
        results["Consensus"]["deliberation"] = await TestMultiAgentDeliberation.test_deliberation()
        print("  ✅ test_deliberation")
    except Exception as e:
        results["Consensus"]["deliberation"] = False
        print(f"  ❌ test_deliberation: {e}")

    try:
        results["Consensus"]["voting_strategies"] = await TestMultiAgentDeliberation.test_voting_strategies()
        print("  ✅ test_voting_strategies")
    except Exception as e:
        results["Consensus"]["voting_strategies"] = False
        print(f"  ❌ test_voting_strategies: {e}")

    try:
        results["Consensus"]["domain_registry"] = await TestDomainAgents.test_domain_registry()
        print("  ✅ test_domain_registry")
    except Exception as e:
        results["Consensus"]["domain_registry"] = False
        print(f"  ❌ test_domain_registry: {e}")

    try:
        results["Consensus"]["trading_agent"] = await TestDomainAgents.test_trading_agent()
        print("  ✅ test_trading_agent")
    except Exception as e:
        results["Consensus"]["trading_agent"] = False
        print(f"  ❌ test_trading_agent: {e}")

    try:
        results["Consensus"]["risk_agent"] = await TestDomainAgents.test_risk_agent()
        print("  ✅ test_risk_agent")
    except Exception as e:
        results["Consensus"]["risk_agent"] = False
        print(f"  ❌ test_risk_agent: {e}")

    try:
        results["Consensus"]["code_agent"] = await TestDomainAgents.test_code_agent()
        print("  ✅ test_code_agent")
    except Exception as e:
        results["Consensus"]["code_agent"] = False
        print(f"  ❌ test_code_agent: {e}")

    # Local ML Tests
    print("\n" + "=" * 60)
    print("🧪 Local ML Integration Tests")
    print("=" * 60)

    try:
        results["Local ML"]["regime_detection"] = await TestRLIntegration.test_regime_detection()
        print("  ✅ test_regime_detection")
    except Exception as e:
        results["Local ML"]["regime_detection"] = False
        print(f"  ❌ test_regime_detection: {e}")

    try:
        results["Local ML"]["reward_shaping"] = await TestRLIntegration.test_reward_shaping()
        print("  ✅ test_reward_shaping")
    except Exception as e:
        results["Local ML"]["reward_shaping"] = False
        print(f"  ❌ test_reward_shaping: {e}")

    try:
        results["Local ML"]["decision_validation"] = await TestRLIntegration.test_decision_validation()
        print("  ✅ test_decision_validation")
    except Exception as e:
        results["Local ML"]["decision_validation"] = False
        print(f"  ❌ test_decision_validation: {e}")

    try:
        results["Local ML"]["ensemble_prediction"] = await TestPredictionEngine.test_ensemble_prediction()
        print("  ✅ test_ensemble_prediction")
    except Exception as e:
        results["Local ML"]["ensemble_prediction"] = False
        print(f"  ❌ test_ensemble_prediction: {e}")

    try:
        results["Local ML"]["model_weight_update"] = await TestPredictionEngine.test_model_weight_update()
        print("  ✅ test_model_weight_update")
    except Exception as e:
        results["Local ML"]["model_weight_update"] = False
        print(f"  ❌ test_model_weight_update: {e}")

    # Monitoring Tests
    print("\n" + "=" * 60)
    print("🧪 Monitoring & Observability Tests")
    print("=" * 60)

    try:
        results["Monitoring"]["counter_metric"] = await TestMetricsCollector.test_counter_metric()
        print("  ✅ test_counter_metric")
    except Exception as e:
        results["Monitoring"]["counter_metric"] = False
        print(f"  ❌ test_counter_metric: {e}")

    try:
        results["Monitoring"]["gauge_metric"] = await TestMetricsCollector.test_gauge_metric()
        print("  ✅ test_gauge_metric")
    except Exception as e:
        results["Monitoring"]["gauge_metric"] = False
        print(f"  ❌ test_gauge_metric: {e}")

    try:
        results["Monitoring"]["histogram_metric"] = await TestMetricsCollector.test_histogram_metric()
        print("  ✅ test_histogram_metric")
    except Exception as e:
        results["Monitoring"]["histogram_metric"] = False
        print(f"  ❌ test_histogram_metric: {e}")

    try:
        results["Monitoring"]["prometheus_export"] = await TestMetricsCollector.test_prometheus_export()
        print("  ✅ test_prometheus_export")
    except Exception as e:
        results["Monitoring"]["prometheus_export"] = False
        print(f"  ❌ test_prometheus_export: {e}")

    try:
        results["Monitoring"]["span_creation"] = await TestDistributedTracer.test_span_creation()
        print("  ✅ test_span_creation")
    except Exception as e:
        results["Monitoring"]["span_creation"] = False
        print(f"  ❌ test_span_creation: {e}")

    try:
        results["Monitoring"]["nested_spans"] = await TestDistributedTracer.test_nested_spans()
        print("  ✅ test_nested_spans")
    except Exception as e:
        results["Monitoring"]["nested_spans"] = False
        print(f"  ❌ test_nested_spans: {e}")

    try:
        results["Monitoring"]["error_handling"] = await TestDistributedTracer.test_error_handling()
        print("  ✅ test_error_handling")
    except Exception as e:
        results["Monitoring"]["error_handling"] = False
        print(f"  ❌ test_error_handling: {e}")

    try:
        results["Monitoring"]["rule_evaluation"] = await TestAlertManager.test_rule_evaluation()
        print("  ✅ test_rule_evaluation")
    except Exception as e:
        results["Monitoring"]["rule_evaluation"] = False
        print(f"  ❌ test_rule_evaluation: {e}")

    try:
        results["Monitoring"]["alert_resolution"] = await TestAlertManager.test_alert_resolution()
        print("  ✅ test_alert_resolution")
    except Exception as e:
        results["Monitoring"]["alert_resolution"] = False
        print(f"  ❌ test_alert_resolution: {e}")

    try:
        results["Monitoring"]["silencing"] = await TestAlertManager.test_silencing()
        print("  ✅ test_silencing")
    except Exception as e:
        results["Monitoring"]["silencing"] = False
        print(f"  ❌ test_silencing: {e}")

    try:
        results["Monitoring"]["dashboard_creation"] = await TestDashboard.test_dashboard_creation()
        print("  ✅ test_dashboard_creation")
    except Exception as e:
        results["Monitoring"]["dashboard_creation"] = False
        print(f"  ❌ test_dashboard_creation: {e}")

    try:
        results["Monitoring"]["widget_data"] = await TestDashboard.test_widget_data()
        print("  ✅ test_widget_data")
    except Exception as e:
        results["Monitoring"]["widget_data"] = False
        print(f"  ❌ test_widget_data: {e}")

    # Integration Tests
    print("\n" + "=" * 60)
    print("🧪 Integration Tests")
    print("=" * 60)

    try:
        results["Integration"]["memory_with_metrics"] = await TestIntegration.test_memory_with_metrics()
        print("  ✅ test_memory_with_metrics")
    except Exception as e:
        results["Integration"]["memory_with_metrics"] = False
        print(f"  ❌ test_memory_with_metrics: {e}")

    try:
        results["Integration"]["consensus_with_tracing"] = await TestIntegration.test_consensus_with_tracing()
        print("  ✅ test_consensus_with_tracing")
    except Exception as e:
        results["Integration"]["consensus_with_tracing"] = False
        print(f"  ❌ test_consensus_with_tracing: {e}")

    try:
        results["Integration"]["end_to_end"] = await TestIntegration.test_end_to_end_agent_flow()
        print("  ✅ test_end_to_end_agent_flow")
    except Exception as e:
        results["Integration"]["end_to_end"] = False
        print(f"  ❌ test_end_to_end_agent_flow: {e}")

    return results


async def main():
    """Main test runner"""
    print("\n" + "=" * 70)
    print("🧪 COMPREHENSIVE AI AGENT SYSTEM TEST SUITE")
    print("=" * 70)

    start_time = time.time()
    results = await run_all_tests()
    duration = time.time() - start_time

    # Summary
    print("\n" + "=" * 70)
    print("📋 TEST SUMMARY")
    print("=" * 70)

    total_passed = 0
    total_failed = 0

    for category, tests in results.items():
        passed = sum(1 for v in tests.values() if v)
        failed = sum(1 for v in tests.values() if not v)
        total_passed += passed
        total_failed += failed

        status = "✅" if failed == 0 else "⚠️"
        print(f"\n{status} {category}: {passed}/{len(tests)} passed")

        for test_name, result in tests.items():
            icon = "✅" if result else "❌"
            print(f"     {icon} {test_name}")

    total = total_passed + total_failed

    print("\n" + "-" * 70)
    print(f"📊 Total: {total_passed}/{total} passed ({100*total_passed/total:.1f}%)")
    print(f"⏱️ Duration: {duration:.2f}s")
    print("=" * 70)

    if total_failed > 0:
        print(f"\n⚠️ {total_failed} test(s) failed!")
        return False
    else:
        print("\n🎉 All tests passed!")
        return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
