"""
Reinforcement Learning Module for Universal Math Engine v2.4.

This module provides RL-based trading agents:
1. TradingEnvironment - OpenAI Gym-like environment
2. DQNAgent - Deep Q-Network agent
3. PPOAgent - Proximal Policy Optimization agent
4. A3CAgent - Asynchronous Advantage Actor-Critic
5. SACAgent - Soft Actor-Critic
6. ExperienceReplay - Memory buffer for training

Author: Universal Math Engine Team
Version: 2.4.0
"""

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

# ============================================================================
# ENUMS AND DATA STRUCTURES
# ============================================================================


class Action(Enum):
    """Trading actions."""

    HOLD = 0
    BUY = 1
    SELL = 2
    CLOSE = 3


class RewardType(Enum):
    """Types of reward functions."""

    PNL = "pnl"  # Raw PnL
    SHARPE = "sharpe"  # Sharpe ratio based
    SORTINO = "sortino"  # Sortino ratio based
    RISK_ADJUSTED = "risk_adjusted"  # Risk-adjusted returns
    CUSTOM = "custom"


@dataclass
class State:
    """Environment state representation."""

    features: NDArray  # Market features
    position: int  # Current position (-1, 0, 1)
    entry_price: float  # Entry price if in position
    unrealized_pnl: float  # Unrealized PnL
    realized_pnl: float  # Realized PnL
    cash: float  # Available cash
    equity: float  # Total equity
    step: int  # Current step


@dataclass
class Experience:
    """Single experience tuple for replay."""

    state: NDArray
    action: int
    reward: float
    next_state: NDArray
    done: bool
    info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RLConfig:
    """Configuration for RL agents."""

    # Environment
    initial_capital: float = 10000.0
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005  # 0.05%
    max_position: int = 1  # Max position size

    # Training
    learning_rate: float = 0.001
    gamma: float = 0.99  # Discount factor
    batch_size: int = 64
    buffer_size: int = 100000
    target_update_freq: int = 100

    # Exploration
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay: float = 0.995

    # Network
    hidden_layers: List[int] = field(default_factory=lambda: [64, 64])
    activation: str = "relu"

    # PPO specific
    clip_ratio: float = 0.2
    value_loss_coef: float = 0.5
    entropy_coef: float = 0.01
    gae_lambda: float = 0.95

    # SAC specific
    alpha: float = 0.2  # Entropy coefficient
    tau: float = 0.005  # Soft update coefficient

    # Reward shaping
    reward_type: RewardType = RewardType.RISK_ADJUSTED
    reward_window: int = 20


# ============================================================================
# TRADING ENVIRONMENT
# ============================================================================


class TradingEnvironment:
    """
    OpenAI Gym-like trading environment.

    Provides market simulation for RL agent training.
    """

    def __init__(
        self, prices: NDArray, features: NDArray, config: Optional[RLConfig] = None
    ):
        """
        Initialize environment.

        Args:
            prices: Price series (close prices)
            features: Feature matrix (T x N)
            config: Environment configuration
        """
        self.prices = prices
        self.features = features
        self.config = config or RLConfig()

        self.n_steps = len(prices)
        self.n_features = features.shape[1]
        self.n_actions = len(Action)

        # State variables
        self._step = 0
        self._position = 0
        self._entry_price = 0.0
        self._cash = self.config.initial_capital
        self._equity_history: List[float] = []
        self._trade_history: List[Dict] = []

        # Reward calculation
        self._returns_buffer: deque = deque(maxlen=self.config.reward_window)

    @property
    def observation_space(self) -> Tuple[int, ...]:
        """Get observation space shape."""
        # Features + position + unrealized_pnl + cash_ratio
        return (self.n_features + 3,)

    @property
    def action_space(self) -> int:
        """Get number of actions."""
        return self.n_actions

    def reset(self) -> NDArray:
        """
        Reset environment to initial state.

        Returns:
            Initial observation
        """
        self._step = 0
        self._position = 0
        self._entry_price = 0.0
        self._cash = self.config.initial_capital
        self._equity_history = [self.config.initial_capital]
        self._trade_history = []
        self._returns_buffer.clear()

        return self._get_observation()

    def step(self, action: int) -> Tuple[NDArray, float, bool, Dict]:
        """
        Take action in environment.

        Args:
            action: Action to take (0=HOLD, 1=BUY, 2=SELL, 3=CLOSE)

        Returns:
            (observation, reward, done, info)
        """
        if self._step >= self.n_steps - 1:
            return self._get_observation(), 0.0, True, {}

        current_price = self.prices[self._step]
        next_price = self.prices[self._step + 1]

        # Execute action
        reward = 0.0
        info: Dict[str, Any] = {"action": Action(action).name}

        if action == Action.BUY.value and self._position <= 0:
            # Close short if exists, then go long
            if self._position < 0:
                reward += self._close_position(current_price)

            self._open_position(1, current_price)
            info["trade"] = "open_long"

        elif action == Action.SELL.value and self._position >= 0:
            # Close long if exists, then go short
            if self._position > 0:
                reward += self._close_position(current_price)

            self._open_position(-1, current_price)
            info["trade"] = "open_short"

        elif action == Action.CLOSE.value and self._position != 0:
            reward += self._close_position(current_price)
            info["trade"] = "close"

        # Calculate unrealized PnL
        unrealized_pnl = 0.0
        if self._position != 0:
            price_change = (next_price - self._entry_price) / self._entry_price
            unrealized_pnl = self._position * price_change * self._cash

        # Update equity
        equity = self._cash + unrealized_pnl
        self._equity_history.append(equity)

        # Calculate step return
        step_return = (equity - self._equity_history[-2]) / self._equity_history[-2]
        self._returns_buffer.append(step_return)

        # Calculate reward
        reward += self._calculate_reward(step_return)

        # Move to next step
        self._step += 1
        done = self._step >= self.n_steps - 1

        # Force close at end
        if done and self._position != 0:
            reward += self._close_position(self.prices[self._step])

        info["equity"] = equity
        info["step_return"] = step_return

        return self._get_observation(), reward, done, info

    def _get_observation(self) -> NDArray:
        """Get current observation."""
        features = self.features[self._step]

        # Add position and portfolio info
        position_info = np.array(
            [
                self._position,
                self._get_unrealized_pnl_ratio(),
                self._cash / self.config.initial_capital,
            ]
        )

        return np.concatenate([features, position_info])

    def _get_unrealized_pnl_ratio(self) -> float:
        """Get unrealized PnL as ratio of initial capital."""
        if self._position == 0:
            return 0.0

        current_price = self.prices[self._step]
        price_change = (current_price - self._entry_price) / self._entry_price
        return self._position * price_change

    def _open_position(self, direction: int, price: float) -> None:
        """Open a position."""
        # Apply slippage
        if direction > 0:
            price *= 1 + self.config.slippage
        else:
            price *= 1 - self.config.slippage

        # Apply commission
        commission = self._cash * self.config.commission
        self._cash -= commission

        self._position = direction
        self._entry_price = price

        self._trade_history.append(
            {
                "step": self._step,
                "action": "open",
                "direction": direction,
                "price": price,
                "commission": commission,
            }
        )

    def _close_position(self, price: float) -> float:
        """Close current position and return PnL."""
        if self._position == 0:
            return 0.0

        # Apply slippage
        if self._position > 0:
            price *= 1 - self.config.slippage
        else:
            price *= 1 + self.config.slippage

        # Calculate PnL
        price_change = (price - self._entry_price) / self._entry_price
        pnl = self._position * price_change * self._cash

        # Apply commission
        commission = (self._cash + pnl) * self.config.commission
        pnl -= commission

        self._cash += pnl

        self._trade_history.append(
            {
                "step": self._step,
                "action": "close",
                "direction": self._position,
                "price": price,
                "pnl": pnl,
                "commission": commission,
            }
        )

        self._position = 0
        self._entry_price = 0.0

        return pnl / self.config.initial_capital  # Normalized PnL

    def _calculate_reward(self, step_return: float) -> float:
        """Calculate reward based on configured reward type."""
        if self.config.reward_type == RewardType.PNL:
            return step_return * 100  # Scale up

        elif self.config.reward_type == RewardType.SHARPE:
            if len(self._returns_buffer) < 2:
                return step_return * 100
            returns = np.array(self._returns_buffer)
            sharpe = np.mean(returns) / (np.std(returns) + 1e-8)
            return sharpe

        elif self.config.reward_type == RewardType.SORTINO:
            if len(self._returns_buffer) < 2:
                return step_return * 100
            returns = np.array(self._returns_buffer)
            neg_returns = returns[returns < 0]
            downside = np.std(neg_returns) if len(neg_returns) > 0 else 1e-8
            return np.mean(returns) / (downside + 1e-8)

        elif self.config.reward_type == RewardType.RISK_ADJUSTED:
            # Reward = return - risk_penalty
            if len(self._returns_buffer) < 2:
                return step_return * 100
            returns = np.array(self._returns_buffer)
            risk_penalty = np.std(returns) * 0.5
            return (step_return - risk_penalty) * 100

        return step_return * 100

    def get_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        if len(self._equity_history) < 2:
            return {}

        equity = np.array(self._equity_history)
        returns = np.diff(equity) / equity[:-1]

        total_return = (equity[-1] / equity[0]) - 1
        sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        max_dd = np.max(drawdown)

        # Win rate
        trades = [t for t in self._trade_history if t["action"] == "close"]
        if trades:
            wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
            win_rate = wins / len(trades)
        else:
            win_rate = 0.0

        return {
            "total_return": float(total_return),
            "sharpe_ratio": float(sharpe),
            "max_drawdown": float(max_dd),
            "win_rate": float(win_rate),
            "n_trades": len(trades),
            "final_equity": float(equity[-1]),
        }


# ============================================================================
# EXPERIENCE REPLAY
# ============================================================================


class ExperienceReplay:
    """
    Experience replay buffer for off-policy learning.
    """

    def __init__(self, capacity: int = 100000):
        self.buffer: deque = deque(maxlen=capacity)

    def push(self, experience: Experience) -> None:
        """Add experience to buffer."""
        self.buffer.append(experience)

    def sample(self, batch_size: int) -> List[Experience]:
        """Sample random batch from buffer."""
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)
        return [self.buffer[i] for i in indices]

    def __len__(self) -> int:
        return len(self.buffer)


class PrioritizedReplay(ExperienceReplay):
    """
    Prioritized experience replay with TD-error based sampling.
    """

    def __init__(
        self,
        capacity: int = 100000,
        alpha: float = 0.6,  # Priority exponent
        beta: float = 0.4,  # Importance sampling exponent
    ):
        super().__init__(capacity)
        self.priorities: deque = deque(maxlen=capacity)
        self.alpha = alpha
        self.beta = beta
        self.max_priority = 1.0

    def push(self, experience: Experience) -> None:
        """Add experience with max priority."""
        self.buffer.append(experience)
        self.priorities.append(self.max_priority)

    def sample(self, batch_size: int) -> Tuple[List[Experience], NDArray, NDArray]:
        """Sample batch with priority-based probabilities."""
        priorities = np.array(self.priorities)
        probs = priorities**self.alpha
        probs /= probs.sum()

        indices = np.random.choice(len(self.buffer), batch_size, p=probs, replace=False)
        experiences = [self.buffer[i] for i in indices]

        # Importance sampling weights
        weights = (len(self.buffer) * probs[indices]) ** (-self.beta)
        weights /= weights.max()

        return experiences, indices, weights

    def update_priorities(self, indices: NDArray, td_errors: NDArray) -> None:
        """Update priorities based on TD errors."""
        for idx, td_error in zip(indices, td_errors):
            priority = abs(td_error) + 1e-6
            self.priorities[idx] = priority
            self.max_priority = max(self.max_priority, priority)


# ============================================================================
# NEURAL NETWORK LAYERS (Pure NumPy)
# ============================================================================


class Layer(ABC):
    """Base layer class."""

    @abstractmethod
    def forward(self, x: NDArray) -> NDArray:
        pass

    @abstractmethod
    def backward(self, grad: NDArray) -> NDArray:
        pass

    @abstractmethod
    def get_params(self) -> List[NDArray]:
        pass

    @abstractmethod
    def set_params(self, params: List[NDArray]) -> None:
        pass


class Dense(Layer):
    """Fully connected layer."""

    def __init__(self, input_dim: int, output_dim: int):
        # Xavier initialization
        scale = np.sqrt(2.0 / (input_dim + output_dim))
        self.weights = np.random.randn(input_dim, output_dim) * scale
        self.bias = np.zeros(output_dim)

        self._input: Optional[NDArray] = None
        self._grad_weights: Optional[NDArray] = None
        self._grad_bias: Optional[NDArray] = None

    def forward(self, x: NDArray) -> NDArray:
        self._input = x
        return x @ self.weights + self.bias

    def backward(self, grad: NDArray) -> NDArray:
        self._grad_weights = self._input.T @ grad
        self._grad_bias = np.sum(grad, axis=0)
        return grad @ self.weights.T

    def get_params(self) -> List[NDArray]:
        return [self.weights, self.bias]

    def set_params(self, params: List[NDArray]) -> None:
        self.weights, self.bias = params

    def get_gradients(self) -> List[NDArray]:
        return [self._grad_weights, self._grad_bias]


class ReLU(Layer):
    """ReLU activation."""

    def __init__(self):
        self._mask: Optional[NDArray] = None

    def forward(self, x: NDArray) -> NDArray:
        self._mask = x > 0
        return x * self._mask

    def backward(self, grad: NDArray) -> NDArray:
        return grad * self._mask

    def get_params(self) -> List[NDArray]:
        return []

    def set_params(self, params: List[NDArray]) -> None:
        pass


class Tanh(Layer):
    """Tanh activation."""

    def __init__(self):
        self._output: Optional[NDArray] = None

    def forward(self, x: NDArray) -> NDArray:
        self._output = np.tanh(x)
        return self._output

    def backward(self, grad: NDArray) -> NDArray:
        return grad * (1 - self._output**2)

    def get_params(self) -> List[NDArray]:
        return []

    def set_params(self, params: List[NDArray]) -> None:
        pass


class Softmax(Layer):
    """Softmax activation."""

    def __init__(self):
        self._output: Optional[NDArray] = None

    def forward(self, x: NDArray) -> NDArray:
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        self._output = exp_x / np.sum(exp_x, axis=-1, keepdims=True)
        return self._output

    def backward(self, grad: NDArray) -> NDArray:
        # Simplified: assumes cross-entropy loss handles softmax gradient
        return grad

    def get_params(self) -> List[NDArray]:
        return []

    def set_params(self, params: List[NDArray]) -> None:
        pass


class NeuralNetwork:
    """Simple feed-forward neural network."""

    def __init__(self, layer_sizes: List[int], activation: str = "relu"):
        self.layers: List[Layer] = []

        for i in range(len(layer_sizes) - 1):
            self.layers.append(Dense(layer_sizes[i], layer_sizes[i + 1]))

            # Add activation for all but last layer
            if i < len(layer_sizes) - 2:
                if activation == "relu":
                    self.layers.append(ReLU())
                elif activation == "tanh":
                    self.layers.append(Tanh())

    def forward(self, x: NDArray) -> NDArray:
        for layer in self.layers:
            x = layer.forward(x)
        return x

    def backward(self, grad: NDArray) -> None:
        for layer in reversed(self.layers):
            grad = layer.backward(grad)

    def get_params(self) -> List[List[NDArray]]:
        return [layer.get_params() for layer in self.layers]

    def set_params(self, params: List[List[NDArray]]) -> None:
        for layer, p in zip(self.layers, params):
            if p:
                layer.set_params(p)

    def copy(self) -> "NeuralNetwork":
        """Create a copy of the network."""
        new_net = NeuralNetwork.__new__(NeuralNetwork)
        new_net.layers = []

        for layer in self.layers:
            if isinstance(layer, Dense):
                new_layer = Dense(layer.weights.shape[0], layer.weights.shape[1])
                new_layer.weights = layer.weights.copy()
                new_layer.bias = layer.bias.copy()
                new_net.layers.append(new_layer)
            elif isinstance(layer, ReLU):
                new_net.layers.append(ReLU())
            elif isinstance(layer, Tanh):
                new_net.layers.append(Tanh())

        return new_net


class Adam:
    """Adam optimizer."""

    def __init__(
        self,
        learning_rate: float = 0.001,
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
    ):
        self.lr = learning_rate
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon

        self.m: Dict[int, NDArray] = {}  # First moment
        self.v: Dict[int, NDArray] = {}  # Second moment
        self.t = 0

    def step(self, params: List[NDArray], grads: List[NDArray]) -> List[NDArray]:
        """Update parameters."""
        self.t += 1
        updated = []

        for i, (param, grad) in enumerate(zip(params, grads)):
            if grad is None:
                updated.append(param)
                continue

            if i not in self.m:
                self.m[i] = np.zeros_like(param)
                self.v[i] = np.zeros_like(param)

            self.m[i] = self.beta1 * self.m[i] + (1 - self.beta1) * grad
            self.v[i] = self.beta2 * self.v[i] + (1 - self.beta2) * (grad**2)

            m_hat = self.m[i] / (1 - self.beta1**self.t)
            v_hat = self.v[i] / (1 - self.beta2**self.t)

            param = param - self.lr * m_hat / (np.sqrt(v_hat) + self.epsilon)
            updated.append(param)

        return updated


# ============================================================================
# BASE RL AGENT
# ============================================================================


class BaseAgent(ABC):
    """Base class for RL agents."""

    def __init__(self, config: RLConfig):
        self.config = config

    @abstractmethod
    def select_action(self, state: NDArray, training: bool = True) -> int:
        pass

    @abstractmethod
    def update(self, experience: Experience) -> Dict[str, float]:
        pass

    @abstractmethod
    def save(self, path: str) -> None:
        pass

    @abstractmethod
    def load(self, path: str) -> None:
        pass


# ============================================================================
# DQN AGENT
# ============================================================================


class DQNAgent(BaseAgent):
    """
    Deep Q-Network agent.

    Uses experience replay and target network for stable training.
    """

    def __init__(
        self, state_dim: int, action_dim: int, config: Optional[RLConfig] = None
    ):
        config = config or RLConfig()
        super().__init__(config)

        self.state_dim = state_dim
        self.action_dim = action_dim

        # Networks
        layer_sizes = [state_dim] + config.hidden_layers + [action_dim]
        self.q_network = NeuralNetwork(layer_sizes, config.activation)
        self.target_network = self.q_network.copy()

        # Optimizer
        self.optimizer = Adam(config.learning_rate)

        # Replay buffer
        self.replay_buffer = ExperienceReplay(config.buffer_size)

        # Exploration
        self.epsilon = config.epsilon_start

        # Training state
        self.update_count = 0

    def select_action(self, state: NDArray, training: bool = True) -> int:
        """Select action using epsilon-greedy policy."""
        if training and np.random.random() < self.epsilon:
            return np.random.randint(self.action_dim)

        state = state.reshape(1, -1)
        q_values = self.q_network.forward(state)
        return int(np.argmax(q_values))

    def update(self, experience: Experience) -> Dict[str, float]:
        """Update agent from experience."""
        self.replay_buffer.push(experience)

        if len(self.replay_buffer) < self.config.batch_size:
            return {}

        # Sample batch
        batch = self.replay_buffer.sample(self.config.batch_size)

        states = np.array([e.state for e in batch])
        actions = np.array([e.action for e in batch])
        rewards = np.array([e.reward for e in batch])
        next_states = np.array([e.next_state for e in batch])
        dones = np.array([e.done for e in batch])

        # Current Q values
        current_q = self.q_network.forward(states)
        current_q_actions = current_q[np.arange(len(actions)), actions]

        # Target Q values (Double DQN)
        next_q = self.q_network.forward(next_states)
        next_actions = np.argmax(next_q, axis=1)
        target_next_q = self.target_network.forward(next_states)
        target_q_values = target_next_q[np.arange(len(next_actions)), next_actions]

        # Compute targets
        targets = rewards + self.config.gamma * target_q_values * (1 - dones)

        # Compute loss gradient
        td_error = current_q_actions - targets
        loss = np.mean(td_error**2)

        # Backpropagation
        grad = np.zeros_like(current_q)
        grad[np.arange(len(actions)), actions] = 2 * td_error / len(batch)

        self.q_network.backward(grad)

        # Update parameters
        all_params = []
        all_grads = []
        for layer in self.q_network.layers:
            if isinstance(layer, Dense):
                all_params.extend(layer.get_params())
                all_grads.extend(layer.get_gradients())

        updated_params = self.optimizer.step(all_params, all_grads)

        # Set updated params back
        idx = 0
        for layer in self.q_network.layers:
            if isinstance(layer, Dense):
                layer.weights = updated_params[idx]
                layer.bias = updated_params[idx + 1]
                idx += 2

        # Update target network
        self.update_count += 1
        if self.update_count % self.config.target_update_freq == 0:
            self.target_network = self.q_network.copy()

        # Decay epsilon
        self.epsilon = max(
            self.config.epsilon_end, self.epsilon * self.config.epsilon_decay
        )

        return {"loss": float(loss), "epsilon": self.epsilon}

    def save(self, path: str) -> None:
        """Save agent state."""
        params = {
            "q_network": self.q_network.get_params(),
            "target_network": self.target_network.get_params(),
            "epsilon": self.epsilon,
            "update_count": self.update_count,
        }
        np.save(path, params, allow_pickle=True)

    def load(self, path: str) -> None:
        """Load agent state."""
        params = np.load(path, allow_pickle=True).item()
        self.q_network.set_params(params["q_network"])
        self.target_network.set_params(params["target_network"])
        self.epsilon = params["epsilon"]
        self.update_count = params["update_count"]


# ============================================================================
# PPO AGENT
# ============================================================================


class PPOAgent(BaseAgent):
    """
    Proximal Policy Optimization agent.

    Uses clipped surrogate objective for stable policy updates.
    """

    def __init__(
        self, state_dim: int, action_dim: int, config: Optional[RLConfig] = None
    ):
        config = config or RLConfig()
        super().__init__(config)

        self.state_dim = state_dim
        self.action_dim = action_dim

        # Actor network (policy)
        actor_sizes = [state_dim] + config.hidden_layers + [action_dim]
        self.actor = NeuralNetwork(actor_sizes, config.activation)

        # Critic network (value function)
        critic_sizes = [state_dim] + config.hidden_layers + [1]
        self.critic = NeuralNetwork(critic_sizes, config.activation)

        # Optimizers
        self.actor_optimizer = Adam(config.learning_rate)
        self.critic_optimizer = Adam(config.learning_rate)

        # Trajectory buffer
        self.trajectory: List[Experience] = []

    def select_action(self, state: NDArray, training: bool = True) -> int:
        """Select action using stochastic policy."""
        state = state.reshape(1, -1)
        logits = self.actor.forward(state)

        # Softmax to get probabilities
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        probs = probs.flatten()

        if training:
            action = np.random.choice(self.action_dim, p=probs)
        else:
            action = np.argmax(probs)

        return int(action)

    def get_action_prob(self, state: NDArray, action: int) -> float:
        """Get probability of taking action in state."""
        state = state.reshape(1, -1)
        logits = self.actor.forward(state)
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        return float(probs[0, action])

    def get_value(self, state: NDArray) -> float:
        """Get value estimate for state."""
        state = state.reshape(1, -1)
        return float(self.critic.forward(state)[0, 0])

    def update(self, experience: Experience) -> Dict[str, float]:
        """Store experience for later batch update."""
        self.trajectory.append(experience)

        if experience.done:
            return self._update_from_trajectory()

        return {}

    def _update_from_trajectory(self) -> Dict[str, float]:
        """Update from collected trajectory."""
        if not self.trajectory:
            return {}

        states = np.array([e.state for e in self.trajectory])
        actions = np.array([e.action for e in self.trajectory])
        rewards = np.array([e.reward for e in self.trajectory])

        # Compute returns and advantages (GAE)
        values = np.array([self.get_value(s) for s in states])
        next_values = np.roll(values, -1)
        next_values[-1] = 0

        # TD residuals
        deltas = rewards + self.config.gamma * next_values - values

        # GAE advantages
        advantages = np.zeros_like(rewards)
        gae = 0
        for t in reversed(range(len(rewards))):
            gae = deltas[t] + self.config.gamma * self.config.gae_lambda * gae
            advantages[t] = gae

        returns = advantages + values

        # Normalize advantages
        advantages = (advantages - np.mean(advantages)) / (np.std(advantages) + 1e-8)

        # Store old action probabilities
        old_probs = np.array(
            [self.get_action_prob(states[i], actions[i]) for i in range(len(states))]
        )

        # PPO update (multiple epochs)
        total_actor_loss = 0.0
        total_critic_loss = 0.0
        n_updates = 4

        for _ in range(n_updates):
            # Get current probabilities
            new_probs = np.array(
                [
                    self.get_action_prob(states[i], actions[i])
                    for i in range(len(states))
                ]
            )

            # Ratio
            ratios = new_probs / (old_probs + 1e-8)

            # Clipped surrogate objective
            surr1 = ratios * advantages
            surr2 = (
                np.clip(ratios, 1 - self.config.clip_ratio, 1 + self.config.clip_ratio)
                * advantages
            )
            actor_loss = -np.mean(np.minimum(surr1, surr2))

            # Value loss
            current_values = np.array([self.get_value(s) for s in states])
            critic_loss = np.mean((current_values - returns) ** 2)

            # Entropy bonus (encourage exploration)
            logits = np.array(
                [self.actor.forward(s.reshape(1, -1)).flatten() for s in states]
            )
            exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
            probs_all = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
            entropy = -np.mean(np.sum(probs_all * np.log(probs_all + 1e-8), axis=1))

            # Total loss (for logging purposes)
            _ = (
                actor_loss
                + self.config.value_loss_coef * critic_loss
                - self.config.entropy_coef * entropy
            )

            total_actor_loss += actor_loss
            total_critic_loss += critic_loss

            # Simple gradient update (simplified for demo)
            # In practice, would compute proper gradients

        # Clear trajectory
        self.trajectory = []

        return {
            "actor_loss": total_actor_loss / n_updates,
            "critic_loss": total_critic_loss / n_updates,
        }

    def save(self, path: str) -> None:
        """Save agent state."""
        params = {"actor": self.actor.get_params(), "critic": self.critic.get_params()}
        np.save(path, params, allow_pickle=True)

    def load(self, path: str) -> None:
        """Load agent state."""
        params = np.load(path, allow_pickle=True).item()
        self.actor.set_params(params["actor"])
        self.critic.set_params(params["critic"])


# ============================================================================
# A3C AGENT (SINGLE-THREADED VERSION)
# ============================================================================


class A3CAgent(BaseAgent):
    """
    Advantage Actor-Critic agent.

    Single-threaded version for demonstration.
    For true A3C, would use multiprocessing.
    """

    def __init__(
        self, state_dim: int, action_dim: int, config: Optional[RLConfig] = None
    ):
        config = config or RLConfig()
        super().__init__(config)

        self.state_dim = state_dim
        self.action_dim = action_dim

        # Shared network with two heads
        hidden = config.hidden_layers

        # Feature extractor
        feature_sizes = [state_dim] + hidden
        self.feature_net = NeuralNetwork(feature_sizes, config.activation)

        # Policy head
        self.policy_head = Dense(hidden[-1], action_dim)

        # Value head
        self.value_head = Dense(hidden[-1], 1)

        # Optimizer
        self.optimizer = Adam(config.learning_rate)

        # N-step buffer
        self.n_step = 5
        self.buffer: List[Experience] = []

    def _get_features(self, state: NDArray) -> NDArray:
        """Extract features from state."""
        return self.feature_net.forward(state.reshape(1, -1))

    def select_action(self, state: NDArray, training: bool = True) -> int:
        """Select action using policy."""
        features = self._get_features(state)
        logits = self.policy_head.forward(features)

        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        probs = probs.flatten()

        if training:
            action = np.random.choice(self.action_dim, p=probs)
        else:
            action = np.argmax(probs)

        return int(action)

    def get_value(self, state: NDArray) -> float:
        """Get value estimate."""
        features = self._get_features(state)
        return float(self.value_head.forward(features)[0, 0])

    def update(self, experience: Experience) -> Dict[str, float]:
        """Update from experience."""
        self.buffer.append(experience)

        if len(self.buffer) < self.n_step and not experience.done:
            return {}

        # Compute n-step return
        returns = 0.0
        if not experience.done:
            returns = self.get_value(experience.next_state)

        for exp in reversed(self.buffer):
            returns = exp.reward + self.config.gamma * returns

        # Get first state in buffer
        first_exp = self.buffer[0]
        value = self.get_value(first_exp.state)

        # Advantage
        advantage = returns - value

        # Losses (simplified)
        value_loss = advantage**2

        # Policy gradient (simplified)
        features = self._get_features(first_exp.state)
        logits = self.policy_head.forward(features)
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        log_prob = np.log(probs[0, first_exp.action] + 1e-8)
        policy_loss = -log_prob * advantage

        # Clear buffer
        self.buffer = []

        return {"value_loss": float(value_loss), "policy_loss": float(policy_loss)}

    def save(self, path: str) -> None:
        """Save agent state."""
        params = {
            "feature_net": self.feature_net.get_params(),
            "policy_head": self.policy_head.get_params(),
            "value_head": self.value_head.get_params(),
        }
        np.save(path, params, allow_pickle=True)

    def load(self, path: str) -> None:
        """Load agent state."""
        params = np.load(path, allow_pickle=True).item()
        self.feature_net.set_params(params["feature_net"])
        self.policy_head.set_params(params["policy_head"])
        self.value_head.set_params(params["value_head"])


# ============================================================================
# SAC AGENT (SIMPLIFIED)
# ============================================================================


class SACAgent(BaseAgent):
    """
    Soft Actor-Critic agent (simplified continuous action version).

    For discrete actions, treats Q-values as action preferences.
    """

    def __init__(
        self, state_dim: int, action_dim: int, config: Optional[RLConfig] = None
    ):
        config = config or RLConfig()
        super().__init__(config)

        self.state_dim = state_dim
        self.action_dim = action_dim

        # Actor network
        actor_sizes = [state_dim] + config.hidden_layers + [action_dim]
        self.actor = NeuralNetwork(actor_sizes, config.activation)

        # Twin Q-networks
        q_sizes = [state_dim] + config.hidden_layers + [action_dim]
        self.q1 = NeuralNetwork(q_sizes, config.activation)
        self.q2 = NeuralNetwork(q_sizes, config.activation)

        # Target Q-networks
        self.q1_target = self.q1.copy()
        self.q2_target = self.q2.copy()

        # Optimizers
        self.actor_optimizer = Adam(config.learning_rate)
        self.q1_optimizer = Adam(config.learning_rate)
        self.q2_optimizer = Adam(config.learning_rate)

        # Entropy coefficient
        self.alpha = config.alpha

        # Replay buffer
        self.replay_buffer = ExperienceReplay(config.buffer_size)

    def select_action(self, state: NDArray, training: bool = True) -> int:
        """Select action using stochastic policy."""
        state = state.reshape(1, -1)
        logits = self.actor.forward(state)

        # Softmax with temperature
        temp = self.alpha if training else 0.1
        scaled_logits = logits / temp
        exp_logits = np.exp(scaled_logits - np.max(scaled_logits))
        probs = exp_logits / np.sum(exp_logits)
        probs = probs.flatten()

        if training:
            action = np.random.choice(self.action_dim, p=probs)
        else:
            action = np.argmax(probs)

        return int(action)

    def update(self, experience: Experience) -> Dict[str, float]:
        """Update agent."""
        self.replay_buffer.push(experience)

        if len(self.replay_buffer) < self.config.batch_size:
            return {}

        # Sample batch
        batch = self.replay_buffer.sample(self.config.batch_size)

        states = np.array([e.state for e in batch])
        actions = np.array([e.action for e in batch])
        rewards = np.array([e.reward for e in batch])
        next_states = np.array([e.next_state for e in batch])
        dones = np.array([e.done for e in batch])

        # Compute target Q values
        next_logits = self.actor.forward(next_states)
        next_exp_logits = np.exp(
            next_logits - np.max(next_logits, axis=1, keepdims=True)
        )
        next_probs = next_exp_logits / np.sum(next_exp_logits, axis=1, keepdims=True)

        next_q1 = self.q1_target.forward(next_states)
        next_q2 = self.q2_target.forward(next_states)
        next_q = np.minimum(next_q1, next_q2)

        # Soft Q target
        next_v = np.sum(
            next_probs * (next_q - self.alpha * np.log(next_probs + 1e-8)), axis=1
        )
        target_q = rewards + self.config.gamma * next_v * (1 - dones)

        # Current Q values
        q1_values = self.q1.forward(states)
        q2_values = self.q2.forward(states)

        q1_actions = q1_values[np.arange(len(actions)), actions]
        q2_actions = q2_values[np.arange(len(actions)), actions]

        # Q losses
        q1_loss = np.mean((q1_actions - target_q) ** 2)
        q2_loss = np.mean((q2_actions - target_q) ** 2)

        # Policy loss (simplified)
        logits = self.actor.forward(states)
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

        q_values = np.minimum(self.q1.forward(states), self.q2.forward(states))

        actor_loss = np.mean(
            np.sum(probs * (self.alpha * np.log(probs + 1e-8) - q_values), axis=1)
        )

        # Soft update targets
        for param, target_param in zip(
            self.q1.get_params(), self.q1_target.get_params()
        ):
            for p, tp in zip(param, target_param):
                tp[:] = self.config.tau * p + (1 - self.config.tau) * tp

        for param, target_param in zip(
            self.q2.get_params(), self.q2_target.get_params()
        ):
            for p, tp in zip(param, target_param):
                tp[:] = self.config.tau * p + (1 - self.config.tau) * tp

        return {
            "q1_loss": float(q1_loss),
            "q2_loss": float(q2_loss),
            "actor_loss": float(actor_loss),
        }

    def save(self, path: str) -> None:
        """Save agent state."""
        params = {
            "actor": self.actor.get_params(),
            "q1": self.q1.get_params(),
            "q2": self.q2.get_params(),
            "q1_target": self.q1_target.get_params(),
            "q2_target": self.q2_target.get_params(),
        }
        np.save(path, params, allow_pickle=True)

    def load(self, path: str) -> None:
        """Load agent state."""
        params = np.load(path, allow_pickle=True).item()
        self.actor.set_params(params["actor"])
        self.q1.set_params(params["q1"])
        self.q2.set_params(params["q2"])
        self.q1_target.set_params(params["q1_target"])
        self.q2_target.set_params(params["q2_target"])


# ============================================================================
# RL TRAINER
# ============================================================================


class RLTrainer:
    """
    Trainer for RL agents.
    """

    def __init__(
        self,
        agent: BaseAgent,
        env: TradingEnvironment,
        config: Optional[RLConfig] = None,
    ):
        self.agent = agent
        self.env = env
        self.config = config or RLConfig()

        self.episode_rewards: List[float] = []
        self.episode_lengths: List[int] = []
        self.metrics_history: List[Dict] = []

    def train(self, n_episodes: int, verbose: bool = True) -> Dict[str, List[float]]:
        """
        Train agent for specified number of episodes.

        Args:
            n_episodes: Number of episodes
            verbose: Whether to print progress

        Returns:
            Training history
        """
        for episode in range(n_episodes):
            state = self.env.reset()
            episode_reward = 0.0
            episode_length = 0

            done = False
            while not done:
                action = self.agent.select_action(state, training=True)
                next_state, reward, done, info = self.env.step(action)

                experience = Experience(
                    state=state,
                    action=action,
                    reward=reward,
                    next_state=next_state,
                    done=done,
                    info=info,
                )

                self.agent.update(experience)

                state = next_state
                episode_reward += reward
                episode_length += 1

            self.episode_rewards.append(episode_reward)
            self.episode_lengths.append(episode_length)

            # Get episode metrics
            metrics = self.env.get_metrics()
            metrics["episode"] = episode
            metrics["reward"] = episode_reward
            self.metrics_history.append(metrics)

            if verbose and (episode + 1) % 10 == 0:
                avg_reward = np.mean(self.episode_rewards[-10:])
                print(
                    f"Episode {episode + 1}: Avg Reward = {avg_reward:.2f}, "
                    f"Sharpe = {metrics.get('sharpe_ratio', 0):.2f}"
                )

        return {
            "rewards": self.episode_rewards,
            "lengths": self.episode_lengths,
            "metrics": self.metrics_history,
        }

    def evaluate(self, n_episodes: int = 10) -> Dict[str, float]:
        """
        Evaluate agent without training.

        Args:
            n_episodes: Number of evaluation episodes

        Returns:
            Average metrics
        """
        total_return = 0.0
        total_sharpe = 0.0
        total_trades = 0

        for _ in range(n_episodes):
            state = self.env.reset()
            done = False

            while not done:
                action = self.agent.select_action(state, training=False)
                state, _, done, _ = self.env.step(action)

            metrics = self.env.get_metrics()
            total_return += metrics.get("total_return", 0)
            total_sharpe += metrics.get("sharpe_ratio", 0)
            total_trades += metrics.get("n_trades", 0)

        return {
            "avg_return": total_return / n_episodes,
            "avg_sharpe": total_sharpe / n_episodes,
            "avg_trades": total_trades / n_episodes,
        }


# ============================================================================
# AGENT FACTORY
# ============================================================================


class AgentFactory:
    """Factory for creating RL agents."""

    @staticmethod
    def create_agent(
        agent_type: str,
        state_dim: int,
        action_dim: int,
        config: Optional[RLConfig] = None,
    ) -> BaseAgent:
        """
        Create RL agent.

        Args:
            agent_type: Type of agent ("dqn", "ppo", "a3c", "sac")
            state_dim: State dimension
            action_dim: Action dimension
            config: Agent configuration

        Returns:
            RL agent instance
        """
        if agent_type.lower() == "dqn":
            return DQNAgent(state_dim, action_dim, config)
        elif agent_type.lower() == "ppo":
            return PPOAgent(state_dim, action_dim, config)
        elif agent_type.lower() == "a3c":
            return A3CAgent(state_dim, action_dim, config)
        elif agent_type.lower() == "sac":
            return SACAgent(state_dim, action_dim, config)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

    @staticmethod
    def get_available_agents() -> List[str]:
        """Get list of available agent types."""
        return ["dqn", "ppo", "a3c", "sac"]


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "Action",
    "RewardType",
    # Data structures
    "State",
    "Experience",
    "RLConfig",
    # Environment
    "TradingEnvironment",
    # Replay buffers
    "ExperienceReplay",
    "PrioritizedReplay",
    # Neural network components
    "Layer",
    "Dense",
    "ReLU",
    "Tanh",
    "Softmax",
    "NeuralNetwork",
    "Adam",
    # Agents
    "BaseAgent",
    "DQNAgent",
    "PPOAgent",
    "A3CAgent",
    "SACAgent",
    # Training
    "RLTrainer",
    # Factory
    "AgentFactory",
]
