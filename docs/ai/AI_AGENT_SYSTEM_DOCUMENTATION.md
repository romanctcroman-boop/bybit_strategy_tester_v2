# 📚 AI Agent System - Complete Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Getting Started](#getting-started)
4. [Components](#components)
   - [Memory System](#memory-system)
   - [Self-Improvement Engine](#self-improvement-engine)
   - [Multi-Agent Consensus](#multi-agent-consensus)
   - [MCP Integration](#mcp-integration)
   - [LLM Connections](#llm-connections)
   - [Communication Protocol](#communication-protocol)
   - [Monitoring & Observability](#monitoring--observability)
5. [API Reference](#api-reference)
6. [Configuration](#configuration)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The AI Agent System is a production-ready, multi-agent AI infrastructure designed for autonomous trading operations. It implements:

- **Hierarchical Memory** - 4-tier cognitive memory system
- **Self-Improvement** - RLHF/RLAIF with self-reflection
- **Multi-Agent Consensus** - Structured deliberation with domain experts
- **MCP Integration** - Model Context Protocol for tool interoperability
- **Full Observability** - Prometheus/Grafana compatible monitoring

### Key Features

| Feature | Description |
|---------|-------------|
| 🧠 **Hierarchical Memory** | Working, Episodic, Semantic, Procedural memory tiers |
| 🔄 **Self-Improvement** | RLHF/RLAIF training pipeline |
| 🤝 **Multi-Agent** | Structured debate with voting strategies |
| 🔌 **MCP Protocol** | Universal tool interoperability |
| 📊 **Observability** | Metrics, tracing, alerting, dashboards |
| 🔐 **Shared Memory** | Thread-safe cross-agent state |
| 🚨 **ML Anomaly Detection** | Isolation Forest, Z-Score, Ensemble |

---

## Architecture

```
backend/agents/
├── memory/
│   ├── hierarchical_memory.py  # 4-tier memory system
│   ├── vector_store.py         # ChromaDB embeddings
│   └── shared_memory.py        # Multi-agent shared state
├── self_improvement/
│   ├── rlhf_module.py          # RLHF/RLAIF training
│   ├── self_reflection.py      # Metacognitive analysis
│   └── performance_evaluator.py # Performance tracking
├── consensus/
│   ├── deliberation.py         # Multi-agent debate
│   └── domain_agents.py        # Specialized experts
├── mcp/
│   ├── protocol.py             # MCP server/client
│   ├── tool_registry.py        # Tool management
│   ├── resource_manager.py     # Resource handling
│   └── context_manager.py      # Context propagation
├── llm/
│   └── connections.py          # Real LLM API clients
├── communication/
│   └── protocol.py             # Agent messaging
├── local_ml/
│   ├── rl_integration.py       # RL agent integration
│   └── prediction_engine.py    # Ensemble predictions
├── monitoring/
│   ├── metrics_collector.py    # Prometheus metrics
│   ├── tracing.py              # Distributed tracing
│   ├── alerting.py             # Alert management
│   ├── ml_anomaly.py           # ML-based detection
│   ├── prometheus_grafana.py   # Integration
│   └── dashboard.py            # Dashboard data
└── dashboard/
    └── api.py                  # REST/WebSocket API
```

---

## Getting Started

### Installation

```python
# Core dependencies
pip install aiohttp loguru numpy chromadb sentence-transformers

# Optional: ML features
pip install scikit-learn torch

# Optional: Monitoring
pip install prometheus-client
```

### Quick Start

```python
import asyncio
from backend.agents.memory.hierarchical_memory import HierarchicalMemory, MemoryType
from backend.agents.llm.connections import DeepSeekClient, LLMConfig, LLMProvider, LLMMessage

async def main():
    # Initialize memory
    memory = HierarchicalMemory()
    
    # Store knowledge
    await memory.store(
        "RSI above 70 indicates overbought conditions",
        memory_type=MemoryType.SEMANTIC,
        importance=0.8,
        tags=["trading", "RSI"],
    )
    
    # Recall relevant knowledge
    results = await memory.recall("What indicates overbought?", top_k=5)
    print(f"Found {len(results)} relevant memories")
    
    # Initialize LLM client
    config = LLMConfig(
        provider=LLMProvider.DEEPSEEK,
        api_key="your-api-key",
    )
    client = DeepSeekClient(config)
    
    # Send request
    response = await client.chat([
        LLMMessage(role="user", content="Explain RSI indicator")
    ])
    print(f"Response: {response.content}")
    
    await client.close()

asyncio.run(main())
```

---

## Components

### Memory System

#### Hierarchical Memory

```python
from backend.agents.memory.hierarchical_memory import (
    HierarchicalMemory,
    MemoryType,
)

memory = HierarchicalMemory(persist_path="./agent_memory")

# Store in different tiers
await memory.store("Current market analysis", MemoryType.WORKING, importance=0.9)
await memory.store("User asked about MACD", MemoryType.EPISODIC, importance=0.6)
await memory.store("RSI is a momentum indicator", MemoryType.SEMANTIC, importance=0.8)
await memory.store("def calculate_rsi()...", MemoryType.PROCEDURAL, importance=0.7)

# Semantic search
results = await memory.recall("momentum indicators", top_k=5)

# Memory consolidation (run periodically)
await memory.consolidate()

# Intelligent forgetting
await memory.forget()
```

#### Shared Memory

```python
from backend.agents.memory.shared_memory import SharedMemory

memory = SharedMemory()

# Atomic operations
await memory.set("agent_1", "counter", 0)
await memory.increment("agent_1", "counter", 1)

# Optimistic locking
value, version = await memory.get_with_version("counter")
success = await memory.set("agent_1", "counter", value + 1, expected_version=version)

# Pessimistic locking
if await memory.acquire_lock("agent_1", "resource"):
    try:
        # Critical section
        pass
    finally:
        await memory.release_lock("agent_1", "resource")

# Transactions
async with memory.transaction("agent_1") as tx:
    tx.set("key1", "value1")
    tx.set("key2", "value2")
    # Auto-commits on exit

# Subscribe to changes
def on_change(event):
    print(f"{event.key} changed to {event.value}")

memory.subscribe("counter", on_change)
```

### Self-Improvement Engine

#### RLHF Module

```python
from backend.agents.self_improvement.rlhf_module import RLHFModule

rlhf = RLHFModule()

# Collect human feedback
await rlhf.collect_human_feedback(
    prompt="Explain RSI",
    response_a="RSI is a momentum oscillator...",
    response_b="RSI = 100 - (100 / (1 + RS))",
    preference=-1,  # Response A is better
    reasoning="More comprehensive explanation",
)

# Collect AI feedback (RLAIF)
await rlhf.collect_ai_feedback(
    prompt="Analyze BTC trend",
    response="Based on the current...",
)

# Train reward model
metrics = rlhf.train_reward_model()
print(f"Accuracy: {metrics['accuracy']:.2%}")

# Self-evaluation
score = await rlhf.self_evaluate_response(
    prompt="Calculate position size",
    response="Position size = Risk / Stop Loss",
)
print(f"Quality score: {score.overall_score}")
```

### Multi-Agent Consensus

```python
from backend.agents.consensus.deliberation import (
    MultiAgentDeliberation,
    VotingStrategy,
)
from backend.agents.consensus.domain_agents import DomainAgentRegistry

# Initialize deliberation
deliberation = MultiAgentDeliberation()

# Run structured debate
result = await deliberation.deliberate(
    question="Should we use trailing or fixed stop loss for BTC?",
    agents=["deepseek", "perplexity"],
    voting_strategy=VotingStrategy.WEIGHTED,
    max_rounds=3,
    min_confidence=0.7,
)

print(f"Decision: {result.decision}")
print(f"Confidence: {result.confidence}")
print(f"Evidence: {result.evidence_chain}")

# Use domain experts
registry = DomainAgentRegistry()

trading_agent = registry.get("trading")
analysis = await trading_agent.analyze({
    "strategy": {"type": "RSI_Crossover"},
    "market": {"trend": "bullish"},
})
```

### MCP Integration

```python
from backend.agents.mcp.protocol import MCPServer, MCPClient, InMemoryTransport

# Create MCP server with tools
server = MCPServer(name="trading-agent")

@server.tool("calculate_rsi")
async def calculate_rsi(prices: list, period: int = 14):
    """Calculate RSI indicator"""
    # Implementation
    return {"rsi": 65.5}

# Start server
await server.start()

# Connect client
client = MCPClient()
transport = InMemoryTransport()
transport.connect(server.transport)

await client.connect(transport)

# List and call tools
tools = await client.list_tools()
result = await client.call_tool("calculate_rsi", {"prices": [100, 101, 99, 102]})

print(f"RSI: {result['rsi']}")
```

### LLM Connections

```python
from backend.agents.llm.connections import (
    DeepSeekClient,
    PerplexityClient,
    OllamaClient,
    LLMConfig,
    LLMProvider,
    LLMMessage,
    LLMClientPool,
)

# DeepSeek client
config = LLMConfig(
    provider=LLMProvider.DEEPSEEK,
    api_key="your-api-key",
    model="deepseek-chat",
    temperature=0.7,
    max_tokens=4096,
)

client = DeepSeekClient(config)

messages = [
    LLMMessage(role="system", content="You are a trading assistant."),
    LLMMessage(role="user", content="Analyze BTC price action"),
]

response = await client.chat(messages)
print(f"Response: {response.content}")
print(f"Tokens: {response.total_tokens}")
print(f"Cost: ${response.estimated_cost:.4f}")

# Streaming
async for chunk in client.chat_stream(messages):
    print(chunk, end="", flush=True)

# Connection pool for high availability
pool = LLMClientPool()
pool.add_client(deepseek_client)
pool.add_client(perplexity_client)

# Auto-selects healthy client
response = await pool.chat(messages)
```

### Communication Protocol

```python
from backend.agents.communication.protocol import (
    MessageBroker,
    AgentCommunicator,
    AgentInfo,
    Message,
    MessagePriority,
)

# Create broker
broker = MessageBroker()
await broker.start()

# Register agents
broker.register_agent(AgentInfo(
    agent_id="trading_agent",
    agent_type="trading",
    capabilities=["analyze", "recommend"],
))

# Create communicator
comm = AgentCommunicator(
    broker, 
    agent_id="analysis_agent",
    agent_type="analysis",
)

# Register message handler
@comm.on("analyze")
async def handle_analyze(msg):
    return {"result": "analysis complete", "score": 0.85}

await comm.start()

# Send request to another agent
result = await comm.ask(
    receiver_id="trading_agent",
    topic="recommend",
    payload={"symbol": "BTCUSDT"},
)

# Broadcast to all
await comm.broadcast("market_update", {"price": 100000})

# Publish to topic subscribers
await comm.publish("alerts", {"level": "warning", "message": "High volatility"})
```

### Monitoring & Observability

#### Metrics

```python
from backend.agents.monitoring.metrics_collector import MetricsCollector

collector = MetricsCollector()

# Counter
collector.increment("requests_total", labels={"agent": "trading"})

# Gauge
collector.set_gauge("active_connections", 5)

# Histogram
collector.observe("latency_ms", 150.5)

# Export Prometheus format
print(collector.export_prometheus())
```

#### Tracing

```python
from backend.agents.monitoring.tracing import DistributedTracer

tracer = DistributedTracer()

async with tracer.start_span("process_request") as span:
    span.set_attribute("user_id", "user_123")
    span.add_event("processing_started")
    
    # Nested span
    async with tracer.start_span("database_query", parent=span) as db_span:
        db_span.set_attribute("query", "SELECT * FROM...")
        # Execute query
    
    span.add_event("processing_complete")
```

#### ML Anomaly Detection

```python
from backend.agents.monitoring.ml_anomaly import MLAnomalyDetector

detector = MLAnomalyDetector()

# Train on historical data
await detector.train("latency_ms", historical_values)

# Detect anomalies
anomalies = await detector.detect("latency_ms", current_values)

for anomaly in anomalies:
    print(f"Anomaly: {anomaly.value} (expected: {anomaly.expected_value})")
    print(f"Severity: {anomaly.severity.value}")
    print(f"Confidence: {anomaly.confidence:.2%}")
```

#### Prometheus/Grafana

```python
from backend.agents.monitoring.prometheus_grafana import (
    PrometheusExporter,
    GrafanaClient,
    create_ai_agent_dashboard,
)

# Export to Prometheus
exporter = PrometheusExporter(metrics_collector)
await exporter.start_server()  # http://localhost:9090/metrics

# Create Grafana dashboard
grafana = GrafanaClient(GrafanaConfig(
    url="http://localhost:3000",
    api_key="your-api-key",
))

dashboard = create_ai_agent_dashboard()
await grafana.create_dashboard(dashboard)
```

---

## API Reference

### Dashboard REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agents/health` | GET | Health check |
| `/api/agents/metrics` | GET | List available metrics |
| `/api/agents/metrics/query` | POST | Query metric data |
| `/api/agents/agents` | GET | List registered agents |
| `/api/agents/agents/{id}` | GET | Get agent details |
| `/api/agents/memory/stats` | GET | Memory statistics |
| `/api/agents/alerts` | GET | List active alerts |
| `/api/agents/alerts` | POST | Create alert rule |
| `/api/agents/traces` | GET | List recent traces |
| `/api/agents/anomalies` | GET | List detected anomalies |
| `/api/agents/ws` | WS | Real-time updates |

---

## Configuration

### Environment Variables

```bash
# LLM API Keys
DEEPSEEK_API_KEY=your-key
PERPLEXITY_API_KEY=your-key

# Memory
AGENT_MEMORY_PATH=./data/agent_memory
AGENT_MEMORY_MAX_ITEMS=10000

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_URL=http://localhost:3000
GRAFANA_API_KEY=your-key

# Communication
MESSAGE_BROKER_MAX_QUEUE=10000
```

---

## Best Practices

1. **Memory Management**
   - Use appropriate memory tiers for different data types
   - Run consolidation periodically during low-traffic periods
   - Enable persistence for production deployments

2. **Multi-Agent**
   - Use domain-specific agents for specialized tasks
   - Set appropriate confidence thresholds for consensus
   - Monitor agent performance and adjust weights

3. **Observability**
   - Export metrics to Prometheus for long-term storage
   - Set up alerts for critical metrics
   - Use distributed tracing for debugging

4. **LLM Connections**
   - Use connection pools for high availability
   - Implement rate limiting to avoid API quota issues
   - Monitor token usage and costs

---

## Troubleshooting

### Common Issues

**Memory not persisting**
- Ensure `persist_path` is set and directory is writable
- Check for disk space issues

**LLM connection timeouts**
- Increase `timeout_seconds` in LLMConfig
- Check network connectivity
- Verify API key validity

**Agent messages not delivered**
- Ensure broker is started with `await broker.start()`
- Verify agent registration
- Check message TTL settings

**Anomaly detection false positives**
- Increase training data sample size
- Adjust detector thresholds
- Use ensemble detector for more robust detection

---

*Documentation Version: 1.0.0*  
*Last Updated: January 2026*
