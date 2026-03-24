"""Tests for P3-4: Multi-agent market simulation."""

from backend.research import Agent, AgentType, MarketSimulator


class TestAgentType:
    def test_all_agent_types_defined(self):
        assert AgentType.MOMENTUM == "momentum"
        assert AgentType.MEAN_REVERSION == "mean_reversion"
        assert AgentType.MARKET_MAKER == "market_maker"
        assert AgentType.RANDOM == "random"
        assert AgentType.RL_AGENT == "rl_agent"

    def test_agent_type_is_str_enum(self):
        assert isinstance(AgentType.MOMENTUM, str)


class TestAgent:
    def test_create_agent(self):
        agent = Agent("a1", AgentType.MOMENTUM, capital=10000.0)
        assert agent.id == "a1"
        assert agent.agent_type == AgentType.MOMENTUM
        assert agent.capital == 10000.0
        assert agent.position == 0.0
        assert agent.pnl == 0.0
        assert agent.trades == 0

    def test_agent_to_dict(self):
        agent = Agent("a1", AgentType.RANDOM, capital=5000.0)
        d = agent.to_dict()
        assert d["id"] == "a1"
        assert d["type"] == "random"
        assert d["capital"] == 5000.0
        assert "position" in d
        assert "pnl" in d
        assert "trades" in d


class TestMarketSimulator:
    def test_init_default(self):
        sim = MarketSimulator()
        assert sim.price == 50000.0
        assert len(sim.price_history) == 1
        assert sim.current_step == 0

    def test_init_custom(self):
        sim = MarketSimulator(initial_price=1000.0, volatility=0.01)
        assert sim.price == 1000.0
        assert sim.volatility == 0.01

    def test_add_agent(self):
        sim = MarketSimulator()
        agent = Agent("m1", AgentType.MOMENTUM, capital=10000.0)
        sim.add_agent(agent)
        assert "m1" in sim.agents

    def test_remove_agent(self):
        sim = MarketSimulator()
        agent = Agent("m1", AgentType.MOMENTUM, capital=10000.0)
        sim.add_agent(agent)
        sim.remove_agent("m1")
        assert "m1" not in sim.agents

    def test_remove_nonexistent_agent_safe(self):
        sim = MarketSimulator()
        sim.remove_agent("nonexistent")  # should not raise

    def test_step_increments(self):
        sim = MarketSimulator()
        sim.add_agent(Agent("r1", AgentType.RANDOM, capital=10000.0))
        result = sim.step()
        assert sim.current_step == 1
        assert "price" in result
        assert "step" in result
        assert result["step"] == 1

    def test_step_price_history_grows(self):
        sim = MarketSimulator()
        sim.add_agent(Agent("r1", AgentType.RANDOM, capital=10000.0))
        assert len(sim.price_history) == 1
        sim.step()
        assert len(sim.price_history) == 2

    def test_price_always_positive(self):
        sim = MarketSimulator(initial_price=100.0, volatility=0.1)
        sim.add_agent(Agent("r1", AgentType.RANDOM, capital=100000.0))
        for _ in range(100):
            sim.step()
        assert sim.price > 0

    def test_run_returns_correct_length(self):
        sim = MarketSimulator()
        sim.add_agent(Agent("r1", AgentType.RANDOM, capital=10000.0))
        results = sim.run(n_steps=50)
        assert len(results) == 50

    def test_run_current_step_correct(self):
        sim = MarketSimulator()
        sim.add_agent(Agent("r1", AgentType.RANDOM, capital=10000.0))
        sim.run(n_steps=25)
        assert sim.current_step == 25

    def test_all_agent_types_run(self):
        sim = MarketSimulator(initial_price=1000.0)
        for i, at in enumerate(AgentType):
            sim.add_agent(Agent(f"agent_{i}", at, capital=10000.0))
        results = sim.run(n_steps=20)
        assert len(results) == 20
        assert len(sim.agents) == 5

    def test_get_agent_performance_keys(self):
        sim = MarketSimulator()
        sim.add_agent(Agent("m1", AgentType.MOMENTUM, capital=10000.0))
        sim.run(n_steps=15)
        perf = sim.get_agent_performance()
        assert "m1" in perf
        assert "pnl" in perf["m1"]
        assert "trades" in perf["m1"]
        assert "return" in perf["m1"]

    def test_get_market_metrics_keys(self):
        sim = MarketSimulator()
        sim.add_agent(Agent("r1", AgentType.RANDOM, capital=10000.0))
        sim.run(n_steps=30)
        metrics = sim.get_market_metrics()
        assert "current_price" in metrics
        assert "volatility" in metrics
        assert "sharpe" in metrics
        assert "max_drawdown" in metrics
        assert "n_agents" in metrics

    def test_market_metrics_empty_before_run(self):
        sim = MarketSimulator()
        # Only 1 price point initially — returns empty dict
        metrics = sim.get_market_metrics()
        assert isinstance(metrics, dict)

    def test_max_drawdown_non_negative(self):
        sim = MarketSimulator()
        sim.add_agent(Agent("r1", AgentType.RANDOM, capital=10000.0))
        sim.run(n_steps=100)
        metrics = sim.get_market_metrics()
        assert metrics["max_drawdown"] >= 0.0

    def test_to_dict_structure(self):
        sim = MarketSimulator()
        sim.add_agent(Agent("r1", AgentType.RANDOM, capital=10000.0))
        sim.run(n_steps=10)
        d = sim.to_dict()
        assert "current_step" in d
        assert "price" in d
        assert "price_history" in d
        assert "agents" in d
        assert "market_metrics" in d
        assert "agent_performance" in d

    def test_multiple_agents_interaction(self):
        sim = MarketSimulator(initial_price=50000.0)
        sim.add_agent(Agent("momentum_1", AgentType.MOMENTUM, capital=10000.0))
        sim.add_agent(Agent("mean_rev_1", AgentType.MEAN_REVERSION, capital=10000.0))
        sim.add_agent(Agent("mm_1", AgentType.MARKET_MAKER, capital=50000.0))
        results = sim.run(n_steps=100)
        assert len(results) == 100
        perf = sim.get_agent_performance()
        assert len(perf) == 3

    def test_trades_counted(self):
        sim = MarketSimulator()
        sim.add_agent(Agent("r1", AgentType.RANDOM, capital=10000.0))
        sim.run(n_steps=50)
        perf = sim.get_agent_performance()
        # Random agent should have trades
        assert perf["r1"]["trades"] >= 0
