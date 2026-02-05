"""Quick validation test for new agent modules"""
import sys

sys.path.insert(0, '.')

print("=" * 60)
print("🧪 QUICK MODULE VALIDATION")
print("=" * 60)

tests_passed = 0
tests_failed = 0

def test(name, fn):
    global tests_passed, tests_failed
    try:
        fn()
        print(f"✅ {name}")
        tests_passed += 1
    except Exception as e:
        print(f"❌ {name}: {e}")
        tests_failed += 1

# Test 1: MCP Protocol
def test_mcp():
    from backend.agents.mcp.protocol import MCPMessage, MCPResource, MCPServer
    server = MCPServer("test")
    msg = MCPMessage.request("tools/list")
    assert msg.id is not None
    server.add_resource(MCPResource(uri="test://r", name="Test"))
    assert len(server.resources) == 1

test("MCP Protocol", test_mcp)

# Test 2: Tool Registry
def test_tool_registry():
    from backend.agents.mcp.tool_registry import ToolRegistry
    registry = ToolRegistry()

    @registry.register(category="test")
    def my_tool(x: int) -> int:
        return x * 2

    assert "my_tool" in registry.tools

test("Tool Registry", test_tool_registry)

# Test 3: Resource Manager
def test_resource_manager():
    from backend.agents.mcp.resource_manager import MemoryResourceProvider, ResourceManager
    manager = ResourceManager()
    provider = MemoryResourceProvider()
    provider.add_resource("memory://test", "Test", "content")
    manager.add_provider(provider)
    assert len(manager.providers) == 1

test("Resource Manager", test_resource_manager)

# Test 4: Context Manager
def test_context_manager():
    from backend.agents.mcp.context_manager import ContextManager, ContextScope
    manager = ContextManager()
    ctx = manager.create_context(ContextScope.REQUEST)
    ctx.set("key", "value")
    assert ctx.get("key") == "value"

test("Context Manager", test_context_manager)

# Test 5: LLM Connections
def test_llm():
    from backend.agents.llm.connections import LLMConfig, LLMMessage, LLMProvider
    msg = LLMMessage(role="user", content="Hello")
    config = LLMConfig(provider=LLMProvider.DEEPSEEK, api_key="test")
    assert config.temperature == 0.7

test("LLM Connections", test_llm)

# Test 6: Shared Memory
def test_shared_memory():
    from backend.agents.memory.shared_memory import ConflictResolution, SharedMemory, SharedValue, Transaction

    # Just test the classes can be instantiated
    mem = SharedMemory()
    assert mem is not None
    assert mem.conflict_resolution == ConflictResolution.LAST_WRITE_WINS

    # Test SharedValue
    sv = SharedValue(value="test", version=1)
    assert sv.value == "test"

    # Test Transaction
    tx = Transaction(agent_id="agent1")
    tx.set("key", "value")
    assert len(tx.operations) == 1

test("Shared Memory", test_shared_memory)

# Test 7: Communication Protocol
def test_communication():
    from backend.agents.communication.protocol import AgentInfo, Message, MessageBroker
    broker = MessageBroker()
    broker.register_agent(AgentInfo("agent1", "test"))
    assert len(broker.list_agents()) == 1

    msg = Message(sender_id="a1", topic="test", payload={"x": 1})
    assert msg.id is not None

test("Communication Protocol", test_communication)

# Test 8: ML Anomaly (basic)
def test_ml_anomaly_basic():
    import numpy as np

    from backend.agents.monitoring.ml_anomaly import IQRDetector, ZScoreDetector

    data = np.array([100, 101, 99, 102, 100, 98])

    zscore = ZScoreDetector(threshold=3.0)
    zscore.fit(data)
    scores = zscore.score(data)
    assert len(scores) == len(data)

    iqr = IQRDetector()
    iqr.fit(data)
    detections = iqr.detect(data)
    assert len(detections) == len(data)

test("ML Anomaly Detection (Basic)", test_ml_anomaly_basic)

# Test 9: Prometheus/Grafana
def test_prometheus():
    from backend.agents.monitoring.prometheus_grafana import (
        PrometheusConfig,
        create_ai_agent_dashboard,
    )
    config = PrometheusConfig()
    assert config.namespace == "ai_agent"

    dashboard = create_ai_agent_dashboard()
    assert len(dashboard.panels) > 0

test("Prometheus/Grafana", test_prometheus)

# Test 10: Dashboard API Models
def test_dashboard_api():
    from backend.agents.dashboard.api import AlertCreate, MetricQuery
    query = MetricQuery(metric_name="test")
    assert query.aggregation == "avg"

    alert = AlertCreate(name="test", metric_name="m", condition="gt", threshold=100)
    assert alert.severity == "warning"

test("Dashboard API", test_dashboard_api)

# Summary
print("\n" + "=" * 60)
print(f"📊 Results: {tests_passed}/{tests_passed + tests_failed} passed")
print("=" * 60)

if tests_failed == 0:
    print("🎉 All modules validated successfully!")
else:
    print(f"⚠️ {tests_failed} test(s) failed")
    sys.exit(1)
