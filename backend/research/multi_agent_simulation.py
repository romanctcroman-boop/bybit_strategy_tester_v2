"""
🤖 Multi-Agent Market Simulation

Market simulation with multiple trading agents.

@version: 1.0.0
@date: 2026-02-26
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    """Agent types"""

    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    MARKET_MAKER = "market_maker"
    RANDOM = "random"
    RL_AGENT = "rl_agent"


@dataclass
class Agent:
    """Trading agent"""

    id: str
    agent_type: AgentType
    capital: float
    position: float = 0.0
    pnl: float = 0.0
    trades: int = 0
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.agent_type.value,
            "capital": self.capital,
            "position": self.position,
            "pnl": self.pnl,
            "trades": self.trades,
        }


class MarketSimulator:
    """
    Multi-agent market simulator.

    Simulates market dynamics with heterogeneous agents.
    """

    def __init__(
        self,
        initial_price: float = 50000.0,
        volatility: float = 0.02,
    ):
        """
        Args:
            initial_price: Initial asset price
            volatility: Price volatility
        """
        self.price = initial_price
        self.volatility = volatility
        self.price_history: list[float] = [initial_price]

        # Agents
        self.agents: dict[str, Agent] = {}

        # Order book
        self.bids: list[dict[str, float]] = []
        self.asks: list[dict[str, float]] = []

        # Time
        self.current_step = 0

    def add_agent(self, agent: Agent):
        """Add agent to simulation"""
        self.agents[agent.id] = agent
        logger.info(f"Added agent {agent.id} ({agent.agent_type.value})")

    def remove_agent(self, agent_id: str):
        """Remove agent from simulation"""
        if agent_id in self.agents:
            del self.agents[agent_id]

    def _get_agent_decision(self, agent: Agent) -> float:
        """
        Get agent's trading decision.

        Returns:
            Order size (positive = buy, negative = sell)
        """
        if agent.agent_type == AgentType.MOMENTUM:
            # Momentum: buy if price went up
            if len(self.price_history) > 2:
                trend = (self.price - self.price_history[-3]) / self.price_history[-3]
                return trend * agent.capital * 0.1
            return 0.0

        elif agent.agent_type == AgentType.MEAN_REVERSION:
            # Mean reversion: buy if price below average
            if len(self.price_history) > 10:
                mean_price = np.mean(self.price_history[-10:])
                deviation = (self.price - mean_price) / mean_price
                return -deviation * agent.capital * 0.1
            return 0.0

        elif agent.agent_type == AgentType.MARKET_MAKER:
            # Market maker: provide liquidity
            return np.random.randn() * agent.capital * 0.01

        elif agent.agent_type == AgentType.RANDOM:
            # Random trading
            return np.random.randn() * agent.capital * 0.05

        elif agent.agent_type == AgentType.RL_AGENT:
            # RL agent (placeholder)
            return np.random.randn() * agent.capital * 0.02

        return 0.0

    def _update_price(self, net_order: float):
        """Update price based on net order flow"""
        # Price impact
        impact = net_order / (self.price * 1000)  # Simplified impact model

        # Update price
        self.price = self.price * (1 + impact + np.random.randn() * self.volatility)
        self.price = max(self.price, 1.0)  # Floor

        self.price_history.append(self.price)

    def step(self) -> dict[str, Any]:
        """
        Run one simulation step.

        Returns:
            Step results
        """
        self.current_step += 1

        # Collect orders from all agents
        orders = {}
        net_order = 0.0

        for agent_id, agent in self.agents.items():
            order_size = self._get_agent_decision(agent)
            orders[agent_id] = order_size
            net_order += order_size

            # Update agent position
            agent.position += order_size
            agent.trades += 1 if order_size != 0 else 0

        # Update price
        self._update_price(net_order)

        # Update PnL
        for agent in self.agents.values():
            agent.pnl = agent.position * (self.price - self.price_history[0])

        return {
            "step": self.current_step,
            "price": self.price,
            "net_order": net_order,
            "orders": orders,
        }

    def run(self, n_steps: int) -> list[dict[str, Any]]:
        """
        Run simulation for n steps.

        Args:
            n_steps: Number of steps

        Returns:
            List of step results
        """
        results = []

        for _ in range(n_steps):
            result = self.step()
            results.append(result)

        return results

    def get_agent_performance(self) -> dict[str, dict[str, Any]]:
        """Get performance metrics for all agents"""
        performance = {}

        for agent_id, agent in self.agents.items():
            performance[agent_id] = {
                "pnl": agent.pnl,
                "position": agent.position,
                "trades": agent.trades,
                "return": agent.pnl / agent.capital if agent.capital > 0 else 0,
            }

        return performance

    def get_market_metrics(self) -> dict[str, Any]:
        """Get market metrics"""
        if len(self.price_history) < 2:
            return {}

        returns = np.diff(self.price_history) / self.price_history[:-1]

        return {
            "current_price": self.price,
            "total_return": (self.price - self.price_history[0]) / self.price_history[0],
            "volatility": np.std(returns) * np.sqrt(252),
            "sharpe": np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0,
            "max_drawdown": self._calculate_max_drawdown(),
            "n_agents": len(self.agents),
        }

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if len(self.price_history) < 2:
            return 0.0

        peak = self.price_history[0]
        max_dd = 0.0

        for price in self.price_history:
            if price > peak:
                peak = price

            dd = (peak - price) / peak
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "current_step": self.current_step,
            "price": self.price,
            "price_history": self.price_history[-100:],  # Last 100 prices
            "agents": {aid: a.to_dict() for aid, a in self.agents.items()},
            "market_metrics": self.get_market_metrics(),
            "agent_performance": self.get_agent_performance(),
        }
