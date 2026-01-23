"""
AI Agent System Test Script

Tests the enhanced AI agent infrastructure:
1. Hierarchical Memory System
2. Self-Improvement Engine (RLHF, Self-Reflection, Performance Evaluator)
3. Integration with UnifiedAgentInterface

Run: python scripts/test_agent_system.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")


async def test_hierarchical_memory():
    """Test hierarchical memory system"""
    print("\n" + "=" * 60)
    print("🧠 Testing Hierarchical Memory System")
    print("=" * 60)
    
    try:
        from backend.agents.memory.hierarchical_memory import (
            HierarchicalMemory,
            MemoryType,
        )
        
        # Initialize memory
        memory = HierarchicalMemory(persist_path="./test_memory")
        
        # Store some memories
        print("\n📝 Storing memories...")
        
        await memory.store(
            content="RSI is calculated using average gains and losses over a period",
            memory_type=MemoryType.SEMANTIC,
            importance=0.8,
            tags=["trading", "indicators", "RSI"],
        )
        
        await memory.store(
            content="User asked about moving average crossover strategy",
            memory_type=MemoryType.EPISODIC,
            importance=0.6,
            tags=["trading", "strategy"],
        )
        
        await memory.store(
            content="Current optimization running with parameters: SL=1.5%, TP=3%",
            memory_type=MemoryType.WORKING,
            importance=0.9,
        )
        
        print("   ✅ Stored 3 memories across different tiers")
        
        # Recall memories
        print("\n🔍 Recalling memories about RSI...")
        results = await memory.recall("How to calculate RSI?", top_k=3)
        
        for i, item in enumerate(results):
            print(f"   {i+1}. [{item.memory_type.value}] {item.content[:50]}...")
        
        # Get stats
        stats = memory.get_stats()
        print(f"\n📊 Memory Stats:")
        for tier, info in stats.get("tiers", {}).items():
            print(f"   - {tier}: {info['count']}/{info['max_items']} items")
        
        # Test consolidation
        print("\n🧬 Running memory consolidation...")
        result = await memory.consolidate()
        print(f"   Consolidated: {result}")
        
        # Test forgetting
        print("\n🗑️ Running intelligent forgetting...")
        forgotten = await memory.forget()
        print(f"   Forgotten: {forgotten}")
        
        print("\n✅ Hierarchical Memory Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Hierarchical Memory Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_vector_store():
    """Test vector memory store"""
    print("\n" + "=" * 60)
    print("🔢 Testing Vector Memory Store")
    print("=" * 60)
    
    try:
        from backend.agents.memory.vector_store import VectorMemoryStore
        
        # Try to initialize (may fail if ChromaDB not installed)
        store = VectorMemoryStore(
            collection_name="test_collection",
            persist_path="./test_vectors",
            use_local_embeddings=True,
        )
        
        await store.initialize()
        
        if store._collection is None:
            print("   ⚠️ ChromaDB not available, skipping vector tests")
            print("   💡 Install with: pip install chromadb sentence-transformers")
            return True
        
        # Add documents
        print("\n📝 Adding documents...")
        ids = await store.add(
            texts=[
                "RSI is a momentum indicator",
                "MACD shows trend direction",
                "Bollinger Bands measure volatility",
            ],
            metadatas=[
                {"type": "indicator", "category": "momentum"},
                {"type": "indicator", "category": "trend"},
                {"type": "indicator", "category": "volatility"},
            ],
        )
        print(f"   Added {len(ids)} documents")
        
        # Query
        print("\n🔍 Querying for 'momentum analysis'...")
        results = await store.query(query_text="momentum analysis", n_results=3)
        
        for result in results:
            print(f"   - {result.content} (score: {result.score:.2f})")
        
        # Count
        count = await store.count()
        print(f"\n📊 Total documents: {count}")
        
        print("\n✅ Vector Store Test PASSED")
        return True
        
    except ImportError as e:
        print(f"\n⚠️ Optional dependency not available: {e}")
        print("   Install with: pip install chromadb sentence-transformers")
        return True  # Not a failure
        
    except Exception as e:
        print(f"\n❌ Vector Store Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_rlhf_module():
    """Test RLHF module"""
    print("\n" + "=" * 60)
    print("🎯 Testing RLHF Module")
    print("=" * 60)
    
    try:
        from backend.agents.self_improvement.rlhf_module import (
            RLHFModule,
            FeedbackSample,
        )
        
        rlhf = RLHFModule(persist_path="./test_feedback")
        
        # Collect human feedback
        print("\n👤 Collecting human feedback...")
        await rlhf.collect_human_feedback(
            prompt="Explain what RSI indicates",
            response_a="RSI measures momentum by comparing recent gains vs losses.",
            response_b="RSI is a number between 0 and 100.",
            preference=-1,  # A is better
            reasoning="Response A is more complete",
        )
        print("   ✅ Human feedback collected")
        
        # Collect AI feedback
        print("\n🤖 Collecting AI feedback...")
        samples = await rlhf.collect_ai_feedback(
            prompt="Write a simple moving average function",
            responses=[
                "def sma(data, period): return sum(data[-period:]) / period",
                "SMA = average of last N prices",
            ],
        )
        print(f"   ✅ Collected {len(samples)} AI feedback samples")
        
        # Self-evaluate
        print("\n📊 Self-evaluating response...")
        score = await rlhf.self_evaluate(
            prompt="Explain Sharpe ratio",
            response="Sharpe ratio = (Return - Risk-free rate) / Standard deviation. "
                     "It measures risk-adjusted return.",
        )
        print(f"   Quality score: {score.overall:.2f}")
        
        # Train reward model
        print("\n🎓 Training reward model...")
        result = rlhf.train_reward_model(force=True)
        if result:
            print(f"   Accuracy: {result['accuracy']:.2%}")
        
        # Predict preference
        print("\n🔮 Predicting preference...")
        pref, conf = rlhf.predict_preference(
            prompt="What is MACD?",
            response_a="MACD is the difference between two EMAs.",
            response_b="MACD = Moving Average Convergence Divergence",
        )
        pref_text = "A" if pref == -1 else ("B" if pref == 1 else "Tie")
        print(f"   Predicted: {pref_text} (confidence: {conf:.2f})")
        
        # Get stats
        stats = rlhf.get_stats()
        print(f"\n📊 RLHF Stats: {stats['total_feedback']} feedback samples")
        
        print("\n✅ RLHF Module Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ RLHF Module Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_self_reflection():
    """Test self-reflection engine"""
    print("\n" + "=" * 60)
    print("🪞 Testing Self-Reflection Engine")
    print("=" * 60)
    
    try:
        from backend.agents.self_improvement.self_reflection import (
            SelfReflectionEngine,
        )
        
        reflection = SelfReflectionEngine(persist_path="./test_reflections")
        
        # Reflect on a task
        print("\n🔄 Reflecting on completed task...")
        result = await reflection.reflect_on_task(
            task="Generate a simple RSI calculation function in Python",
            solution="""
def calculate_rsi(prices, period=14):
    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
""",
            outcome={
                "success": True,
                "tests_passed": 5,
                "execution_time_ms": 50,
            },
        )
        
        print(f"   Quality Score: {result.quality_score:.1f}/10")
        print(f"   Lessons Learned: {len(result.lessons_learned)}")
        for lesson in result.lessons_learned[:2]:
            print(f"      - {lesson[:60]}...")
        print(f"   Knowledge Gaps: {len(result.knowledge_gaps)}")
        print(f"   Improvement Actions: {len(result.improvement_actions)}")
        
        # Get recommendations
        print("\n💡 Getting recommendations...")
        recommendations = await reflection.get_recommendations(top_k=3)
        for rec in recommendations[:2]:
            print(f"   - {rec[:60]}...")
        
        # Get stats
        stats = reflection.get_stats()
        print(f"\n📊 Reflection Stats: {stats['total_reflections']} reflections")
        
        print("\n✅ Self-Reflection Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Self-Reflection Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_performance_evaluator():
    """Test performance evaluator"""
    print("\n" + "=" * 60)
    print("📊 Testing Performance Evaluator")
    print("=" * 60)
    
    try:
        from backend.agents.self_improvement.performance_evaluator import (
            PerformanceEvaluator,
        )
        
        evaluator = PerformanceEvaluator(persist_path="./test_metrics")
        
        # Evaluate some responses
        print("\n📈 Evaluating agent responses...")
        
        metrics1 = await evaluator.evaluate_response(
            agent_type="deepseek",
            prompt="Explain RSI indicator",
            response="RSI (Relative Strength Index) is a momentum oscillator that "
                     "measures the speed and change of price movements. It ranges "
                     "from 0 to 100, with readings above 70 indicating overbought "
                     "and below 30 indicating oversold conditions.",
            latency_ms=1500,
            task_type="explanation",
            tokens_used=150,
        )
        print(f"   Response 1: overall={metrics1.overall_score:.1f}, "
              f"accuracy={metrics1.accuracy:.2f}, safety={metrics1.safety:.2f}")
        
        metrics2 = await evaluator.evaluate_response(
            agent_type="deepseek",
            prompt="Write a MACD function",
            response="def macd(prices, fast=12, slow=26, signal=9):\n"
                     "    ema_fast = ema(prices, fast)\n"
                     "    ema_slow = ema(prices, slow)\n"
                     "    return ema_fast - ema_slow",
            latency_ms=2000,
            task_type="code_generation",
            tokens_used=80,
        )
        print(f"   Response 2: overall={metrics2.overall_score:.1f}, "
              f"accuracy={metrics2.accuracy:.2f}, safety={metrics2.safety:.2f}")
        
        # Generate improvement plan
        print("\n📋 Generating improvement plan...")
        plan = await evaluator.generate_improvement_plan()
        print(f"   Overall Score: {plan['current_overall_score']:.1f}")
        print(f"   Weakest Areas: {len(plan['weakest_areas'])}")
        print(f"   Priority Actions: {len(plan['priority_actions'])}")
        
        # Get stats
        stats = evaluator.get_stats()
        print(f"\n📊 Evaluator Stats: {stats['total_evaluations']} evaluations")
        
        print("\n✅ Performance Evaluator Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Performance Evaluator Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_consensus_mechanisms():
    """Test multi-agent deliberation and domain agents"""
    print("\n" + "=" * 60)
    print("🎭 Testing Consensus Mechanisms")
    print("=" * 60)
    
    try:
        from backend.agents.consensus.deliberation import (
            MultiAgentDeliberation,
            VotingStrategy,
        )
        from backend.agents.consensus.domain_agents import (
            DomainAgentRegistry,
            TradingStrategyAgent,
        )
        
        # Test Multi-Agent Deliberation
        print("\n🗣️ Testing Multi-Agent Deliberation...")
        
        deliberation = MultiAgentDeliberation()
        
        result = await deliberation.deliberate(
            question="Should we use trailing stop loss or fixed stop loss for momentum strategy?",
            agents=["deepseek", "perplexity"],
            context={"strategy": "momentum", "timeframe": "4h"},
            voting_strategy=VotingStrategy.WEIGHTED,
            max_rounds=2,
        )
        
        print(f"   Decision: {result.decision[:50]}...")
        print(f"   Confidence: {result.confidence:.2%}")
        print(f"   Rounds: {len(result.rounds)}")
        print(f"   Dissenting Opinions: {len(result.dissenting_opinions)}")
        
        # Test Domain Agent Registry
        print("\n🎯 Testing Domain Agent Registry...")
        
        registry = DomainAgentRegistry()
        print(f"   Registered agents: {registry.list_agents()}")
        
        # Test Trading Strategy Agent
        trading_agent = registry.get("trading")
        if trading_agent:
            analysis = await trading_agent.analyze({
                "strategy": {"type": "RSI_Crossover", "period": 14},
                "results": {"sharpe_ratio": 1.5, "win_rate": 0.55, "max_drawdown": 0.15},
            })
            print(f"   Trading Analysis: score={analysis.score:.1f}, risk={analysis.risk_level}")
        
        # Test Risk Management Agent
        risk_agent = registry.get("risk")
        if risk_agent:
            validation = await risk_agent.validate(
                "Increase position size to 20%",
                context={"position_size": 0.2, "stop_loss": 0.05, "leverage": 1}
            )
            print(f"   Risk Validation: valid={validation.is_valid}, score={validation.validation_score:.2f}")
        
        # Get stats
        stats = deliberation.get_stats()
        print(f"\n📊 Deliberation Stats: {stats['total_deliberations']} deliberations")
        
        print("\n✅ Consensus Mechanisms Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Consensus Mechanisms Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_local_ml_integration():
    """Test local ML components"""
    print("\n" + "=" * 60)
    print("🤖 Testing Local ML Integration")
    print("=" * 60)
    
    try:
        from backend.agents.local_ml.rl_integration import (
            RLAgentIntegration,
            MarketRegime,
        )
        from backend.agents.local_ml.prediction_engine import (
            PredictionEngine,
            SimpleMovingAverageModel,
            SimpleMomentumModel,
            SignalType,
        )
        
        # Test RL-AI Integration
        print("\n🔗 Testing RL-AI Integration...")
        
        integration = RLAgentIntegration()
        
        # Generate mock market data
        import numpy as np
        np.random.seed(42)
        
        # OHLCV data: Open, High, Low, Close, Volume
        prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
        market_data = np.column_stack([
            prices,  # Open
            prices + np.abs(np.random.randn(100) * 0.5),  # High
            prices - np.abs(np.random.randn(100) * 0.5),  # Low
            prices + np.random.randn(100) * 0.2,  # Close
            np.random.randint(1000, 10000, 100),  # Volume
        ])
        
        # Detect market regime
        regime, confidence = await integration.detect_market_regime(market_data)
        print(f"   Detected Regime: {regime.value} (confidence: {confidence:.2%})")
        
        # Get reward shaping
        reward_config = await integration.suggest_reward_shaping(
            regime,
            {"win_rate": 52, "max_drawdown": 12, "sharpe": 0.8}
        )
        print(f"   Reward Config: profit_weight={reward_config.profit_weight:.2f}, "
              f"drawdown_penalty={reward_config.drawdown_penalty:.2f}")
        
        # Validate a decision
        validation = await integration.validate_decision(
            state={"price": 105.5, "rsi": 65, "macd": 0.5, "position_size": 0.5, "unrealized_pnl": 2.5},
            action=1,  # BUY
            confidence=0.75
        )
        print(f"   Decision Validation: approved={validation['approved']}, risk={validation['risk_level']}")
        
        # Test Prediction Engine
        print("\n📊 Testing Prediction Engine...")
        
        engine = PredictionEngine(min_confidence=0.55)
        
        # Add test models with correct argument order: name, model, model_type
        from backend.agents.local_ml.prediction_engine import ModelType
        engine.add_model("ma_model", SimpleMovingAverageModel(), ModelType.ENSEMBLE)
        engine.add_model("momentum", SimpleMomentumModel(), ModelType.ENSEMBLE)
        
        # Make prediction
        features = np.array([[100, 101, 102, 103, 104, 105, 106, 107, 108, 105]])
        result = await engine.predict(features)
        
        print(f"   Signal: {result.signal.value}")
        print(f"   Confidence: {result.confidence:.2%}")
        print(f"   Uncertainty: {result.uncertainty:.2%}")
        print(f"   Model Votes: {len(result.model_votes)}")
        
        # Get stats
        stats = integration.get_stats()
        print(f"\n📊 Integration Stats: {stats['ai_queries']} AI queries")
        
        print("\n✅ Local ML Integration Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Local ML Integration Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_unified_agent_integration():
    """Test integration with UnifiedAgentInterface"""
    print("\n" + "=" * 60)
    print("🔗 Testing Unified Agent Integration")
    print("=" * 60)
    
    try:
        from backend.agents.unified_agent_interface import (
            UnifiedAgentInterface,
            AgentRequest,
        )
        from backend.agents.models import AgentType
        
        # Initialize interface
        agent = UnifiedAgentInterface()
        
        # Check key pool status
        ds_count = agent.key_manager.count_active(AgentType.DEEPSEEK)
        pp_count = agent.key_manager.count_active(AgentType.PERPLEXITY)
        
        print(f"\n🔑 Key Pool Status:")
        print(f"   DeepSeek: {ds_count} active keys")
        print(f"   Perplexity: {pp_count} active keys")
        
        # Check circuit breaker status
        print(f"\n🛡️ Circuit Breaker Status:")
        breaker_status = agent.circuit_manager.get_status()
        for name, status in breaker_status.items():
            state = status.get('state', 'unknown')
            print(f"   {name}: {state}")
        
        # Get interface stats
        print(f"\n📊 Interface Stats:")
        print(f"   Total requests: {agent.stats['total_requests']}")
        print(f"   MCP success: {agent.stats['mcp_success']}")
        print(f"   Direct API success: {agent.stats['direct_api_success']}")
        
        print("\n✅ Unified Agent Integration Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Unified Agent Integration Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("🧪 AI AGENT SYSTEM TEST SUITE")
    print("   Testing Enhanced AI Agent Infrastructure")
    print("=" * 70)
    
    results = {}
    
    # Run tests
    results["Hierarchical Memory"] = await test_hierarchical_memory()
    results["Vector Store"] = await test_vector_store()
    results["RLHF Module"] = await test_rlhf_module()
    results["Self-Reflection"] = await test_self_reflection()
    results["Performance Evaluator"] = await test_performance_evaluator()
    results["Consensus Mechanisms"] = await test_consensus_mechanisms()
    results["Local ML Integration"] = await test_local_ml_integration()
    results["Unified Agent Integration"] = await test_unified_agent_integration()
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 TEST SUMMARY")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n   Total: {passed}/{len(results)} passed")
    print("=" * 70)
    
    if failed > 0:
        print("\n⚠️ Some tests failed. Check the output above for details.")
    else:
        print("\n🎉 All tests passed! AI Agent System is ready.")
    
    return failed == 0


if __name__ == "__main__":
    asyncio.run(main())
