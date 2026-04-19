"""
Reinforcement Learning Agent for Trading Strategy Optimization.

Implements DQN and PPO agents for learning optimal trading policies.
Features:
- State representation from market data
- Action space: buy/sell/hold with position sizing
- Reward shaping for trading (Sharpe, PnL, drawdown penalties)
- Experience replay and target networks
"""

import logging
import random
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from backend.core.indicators import calculate_rsi

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration and Enums
# ============================================================================


class RLAction(Enum):
    """Trading actions for RL agent."""

    HOLD = 0
    BUY = 1
    SELL = 2
    CLOSE = 3


@dataclass
class RLConfig:
    """Configuration for RL agent."""

    # Network architecture
    state_dim: int = 64
    action_dim: int = 4  # HOLD, BUY, SELL, CLOSE
    hidden_dims: list[int] = field(default_factory=lambda: [256, 128, 64])

    # Training parameters
    learning_rate: float = 1e-4
    gamma: float = 0.99  # Discount factor
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay: float = 0.995
    batch_size: int = 64
    memory_size: int = 100000

    # DQN specific
    target_update_freq: int = 100  # Steps between target network updates
    double_dqn: bool = True  # Use Double DQN

    # PPO specific
    clip_epsilon: float = 0.2
    value_loss_coef: float = 0.5
    entropy_coef: float = 0.01
    ppo_epochs: int = 4
    gae_lambda: float = 0.95

    # Trading specific
    transaction_cost: float = 0.001  # 0.1%
    max_position_size: float = 1.0
    reward_scaling: float = 1.0


# ============================================================================
# Market State Representation
# ============================================================================


@dataclass
class MarketState:
    """Market state for RL agent."""

    # Price data (normalized)
    prices: np.ndarray  # Last N prices
    volumes: np.ndarray  # Last N volumes
    returns: np.ndarray  # Last N returns

    # Technical indicators (normalized)
    rsi: float = 0.0
    macd: float = 0.0
    macd_signal: float = 0.0
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    atr: float = 0.0

    # Position info
    position_size: float = 0.0  # -1 to 1 (short to long)
    unrealized_pnl: float = 0.0
    entry_price: float = 0.0

    # Time features
    hour_sin: float = 0.0
    hour_cos: float = 0.0
    day_of_week: int = 0

    def to_array(self) -> np.ndarray:
        """Convert state to numpy array for network input."""
        # Flatten price data
        features = [
            *self.prices.flatten(),
            *self.volumes.flatten(),
            *self.returns.flatten(),
            self.rsi,
            self.macd,
            self.macd_signal,
            self.bb_upper,
            self.bb_lower,
            self.atr,
            self.position_size,
            self.unrealized_pnl,
            self.entry_price,
            self.hour_sin,
            self.hour_cos,
            float(self.day_of_week) / 7.0,
        ]
        return np.array(features, dtype=np.float32)


@dataclass
class Experience:
    """Experience tuple for replay buffer."""

    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool


# ============================================================================
# Replay Buffer
# ============================================================================


class ReplayBuffer:
    """Experience replay buffer for DQN."""

    def __init__(self, capacity: int = 100000):
        self.buffer: deque[Experience] = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        """Add experience to buffer."""
        exp = Experience(state, action, reward, next_state, done)
        self.buffer.append(exp)

    def sample(self, batch_size: int) -> list[Experience]:
        """Sample random batch of experiences."""
        return random.sample(list(self.buffer), min(batch_size, len(self.buffer)))

    def __len__(self) -> int:
        return len(self.buffer)


class PrioritizedReplayBuffer(ReplayBuffer):
    """Prioritized experience replay buffer."""

    def __init__(self, capacity: int = 100000, alpha: float = 0.6):
        super().__init__(capacity)
        self.priorities: deque[float] = deque(maxlen=capacity)
        self.alpha = alpha

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        priority: float = 1.0,
    ) -> None:
        """Add experience with priority."""
        super().push(state, action, reward, next_state, done)
        self.priorities.append(priority)

    def sample(self, batch_size: int, beta: float = 0.4) -> tuple[list[Experience], np.ndarray, list[int]]:
        """Sample batch weighted by priorities."""
        if len(self.buffer) == 0:
            return [], np.array([]), []

        priorities = np.array(list(self.priorities))
        probs = priorities**self.alpha
        probs /= probs.sum()

        indices = np.random.choice(len(self.buffer), min(batch_size, len(self.buffer)), p=probs, replace=False)
        samples = [self.buffer[i] for i in indices]

        # Importance sampling weights
        weights = (len(self.buffer) * probs[indices]) ** (-beta)
        weights /= weights.max()

        return samples, weights, list(indices)

    def update_priorities(self, indices: list[int], priorities: list[float]) -> None:
        """Update priorities for sampled experiences."""
        for idx, priority in zip(indices, priorities, strict=False):
            if idx < len(self.priorities):
                self.priorities[idx] = priority + 1e-5  # Small epsilon to avoid zero


# ============================================================================
# Neural Network (NumPy Implementation - no PyTorch dependency)
# ============================================================================


class SimpleNeuralNetwork:
    """Simple feedforward neural network using NumPy."""

    def __init__(self, layer_dims: list[int], learning_rate: float = 1e-4):
        self.layer_dims = layer_dims
        self.lr = learning_rate
        self.weights: list[np.ndarray] = []
        self.biases: list[np.ndarray] = []

        # Initialize weights using He initialization
        for i in range(len(layer_dims) - 1):
            w = np.random.randn(layer_dims[i], layer_dims[i + 1]) * np.sqrt(2.0 / layer_dims[i])
            b = np.zeros((1, layer_dims[i + 1]))
            self.weights.append(w)
            self.biases.append(b)

    def relu(self, x: np.ndarray) -> np.ndarray:
        """ReLU activation."""
        return np.maximum(0, x)

    def relu_derivative(self, x: np.ndarray) -> np.ndarray:
        """ReLU derivative."""
        return (x > 0).astype(float)

    def softmax(self, x: np.ndarray) -> np.ndarray:
        """Softmax activation for output layer."""
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=-1, keepdims=True)

    def forward(self, x: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
        """Forward pass, returns output and cached activations."""
        activations = [x]
        current = x

        for i in range(len(self.weights) - 1):
            z = np.dot(current, self.weights[i]) + self.biases[i]
            current = self.relu(z)
            activations.append(current)

        # Output layer (linear for Q-values)
        z = np.dot(current, self.weights[-1]) + self.biases[-1]
        activations.append(z)

        return z, activations

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Get Q-values for state."""
        output, _ = self.forward(x)
        return output

    def train_step(
        self,
        states: np.ndarray,
        targets: np.ndarray,
        actions: np.ndarray,
    ) -> float:
        """Single training step, returns loss."""
        # Forward pass
        predictions, activations = self.forward(states)

        # Compute TD error for the taken actions
        batch_size = states.shape[0]
        action_indices = actions.astype(int)
        predicted_q = predictions[np.arange(batch_size), action_indices]
        loss = np.mean((predicted_q - targets) ** 2)

        # Backward pass (simplified)
        d_output = np.zeros_like(predictions)
        d_output[np.arange(batch_size), action_indices] = 2 * (predicted_q - targets) / batch_size

        # Backprop through layers
        d_current = d_output
        for i in range(len(self.weights) - 1, -1, -1):
            if i < len(self.weights) - 1:
                d_current = d_current * self.relu_derivative(activations[i + 1])

            d_w = np.dot(activations[i].T, d_current)
            d_b = np.sum(d_current, axis=0, keepdims=True)

            # Gradient clipping
            d_w = np.clip(d_w, -1.0, 1.0)
            d_b = np.clip(d_b, -1.0, 1.0)

            self.weights[i] -= self.lr * d_w
            self.biases[i] -= self.lr * d_b

            if i > 0:
                d_current = np.dot(d_current, self.weights[i].T)

        return float(loss)

    def copy_from(self, other: "SimpleNeuralNetwork") -> None:
        """Copy weights from another network."""
        for i in range(len(self.weights)):
            self.weights[i] = other.weights[i].copy()
            self.biases[i] = other.biases[i].copy()

    def save(self, filepath: str) -> None:
        """Save model weights."""
        np.savez(
            filepath,
            *self.weights,
            *self.biases,
            layer_dims=self.layer_dims,
        )

    def load(self, filepath: str) -> None:
        """Load model weights."""
        data = np.load(filepath, allow_pickle=True)
        n_layers = len(self.weights)
        for i in range(n_layers):
            self.weights[i] = data[f"arr_{i}"]
            self.biases[i] = data[f"arr_{n_layers + i}"]


# ============================================================================
# Base RL Agent
# ============================================================================


class BaseRLAgent(ABC):
    """Base class for RL trading agents."""

    def __init__(self, config: RLConfig):
        self.config = config
        self.training_steps = 0
        self.episode_rewards: list[float] = []
        self.episode_lengths: list[int] = []

    @abstractmethod
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """Select action given state."""
        pass

    @abstractmethod
    def update(self, experience: Experience) -> float | None:
        """Update agent with new experience, returns loss if trained."""
        pass

    @abstractmethod
    def save(self, filepath: str) -> None:
        """Save agent to file."""
        pass

    @abstractmethod
    def load(self, filepath: str) -> None:
        """Load agent from file."""
        pass


# ============================================================================
# DQN Agent
# ============================================================================


class DQNAgent(BaseRLAgent):
    """Deep Q-Network agent for trading."""

    def __init__(self, config: RLConfig):
        super().__init__(config)

        # Build networks
        layer_dims = [config.state_dim, *config.hidden_dims, config.action_dim]
        self.q_network = SimpleNeuralNetwork(layer_dims, config.learning_rate)
        self.target_network = SimpleNeuralNetwork(layer_dims, config.learning_rate)
        self.target_network.copy_from(self.q_network)

        # Replay buffer
        self.replay_buffer = ReplayBuffer(config.memory_size)

        # Exploration
        self.epsilon = config.epsilon_start

        logger.info(f"DQN Agent initialized with state_dim={config.state_dim}, action_dim={config.action_dim}")

    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """Select action using epsilon-greedy policy."""
        if training and random.random() < self.epsilon:
            return random.randint(0, self.config.action_dim - 1)

        # Ensure state is 2D
        if state.ndim == 1:
            state = state.reshape(1, -1)

        q_values = self.q_network.predict(state)
        return int(np.argmax(q_values[0]))

    def update(self, experience: Experience) -> float | None:
        """Update agent with experience."""
        # Store experience
        self.replay_buffer.push(
            experience.state,
            experience.action,
            experience.reward,
            experience.next_state,
            experience.done,
        )

        # Check if enough samples for training
        if len(self.replay_buffer) < self.config.batch_size:
            return None

        # Sample batch
        batch = self.replay_buffer.sample(self.config.batch_size)

        # Prepare batch data
        states = np.array([e.state for e in batch])
        actions = np.array([e.action for e in batch])
        rewards = np.array([e.reward for e in batch])
        next_states = np.array([e.next_state for e in batch])
        dones = np.array([e.done for e in batch])

        # Compute targets
        if self.config.double_dqn:
            # Double DQN: use online network to select action, target to evaluate
            next_q_online = self.q_network.predict(next_states)
            best_actions = np.argmax(next_q_online, axis=1)
            next_q_target = self.target_network.predict(next_states)
            next_q = next_q_target[np.arange(len(batch)), best_actions]
        else:
            # Standard DQN
            next_q_target = self.target_network.predict(next_states)
            next_q = np.max(next_q_target, axis=1)

        targets = rewards + self.config.gamma * next_q * (1 - dones)

        # Train Q-network
        loss = self.q_network.train_step(states, targets, actions)

        self.training_steps += 1

        # Update target network
        if self.training_steps % self.config.target_update_freq == 0:
            self.target_network.copy_from(self.q_network)

        # Decay epsilon
        self.epsilon = max(
            self.config.epsilon_end,
            self.epsilon * self.config.epsilon_decay,
        )

        return loss

    def save(self, filepath: str) -> None:
        """Save agent."""
        self.q_network.save(f"{filepath}_q_network.npz")
        self.target_network.save(f"{filepath}_target_network.npz")

    def load(self, filepath: str) -> None:
        """Load agent."""
        self.q_network.load(f"{filepath}_q_network.npz")
        self.target_network.load(f"{filepath}_target_network.npz")


# ============================================================================
# Reward Functions
# ============================================================================


class RewardCalculator:
    """Calculate rewards for trading actions."""

    def __init__(
        self,
        transaction_cost: float = 0.001,
        risk_free_rate: float = 0.0,
        sharpe_window: int = 20,
    ):
        self.transaction_cost = transaction_cost
        self.risk_free_rate = risk_free_rate
        self.sharpe_window = sharpe_window
        self.returns_history: deque[float] = deque(maxlen=sharpe_window)

    def calculate_reward(
        self,
        pnl: float,
        action: RLAction,
        position_changed: bool,
        unrealized_pnl: float = 0.0,
        max_drawdown: float = 0.0,
    ) -> float:
        """
        Calculate reward with multiple components.

        Args:
            pnl: Realized PnL from this step
            action: Action taken
            position_changed: Whether position was opened/closed
            unrealized_pnl: Current unrealized PnL
            max_drawdown: Maximum drawdown so far

        Returns:
            Shaped reward
        """
        reward = 0.0

        # 1. PnL component (main reward)
        reward += pnl

        # 2. Transaction cost penalty
        if position_changed:
            reward -= self.transaction_cost

        # 3. Holding penalty (encourage action)
        if action == RLAction.HOLD:
            reward -= 0.0001

        # 4. Drawdown penalty
        if max_drawdown > 0.1:  # 10% drawdown
            reward -= 0.001 * (max_drawdown - 0.1)

        # 5. Risk-adjusted return (Sharpe-like)
        self.returns_history.append(pnl)
        if len(self.returns_history) >= self.sharpe_window:
            returns_arr = np.array(list(self.returns_history))
            mean_return = np.mean(returns_arr)
            std_return = np.std(returns_arr) + 1e-8
            sharpe = (mean_return - self.risk_free_rate) / std_return
            reward += 0.01 * sharpe  # Small Sharpe bonus

        return reward


# ============================================================================
# Trading Environment Wrapper
# ============================================================================


class TradingEnvironment:
    """
    Trading environment for RL agent.

    Wraps market data and trading logic into gym-like interface.
    """

    def __init__(
        self,
        prices: np.ndarray,
        config: RLConfig,
        lookback: int = 20,
    ):
        self.prices = prices
        self.config = config
        self.lookback = lookback

        self.current_step = 0
        self.position = 0.0  # -1 to 1
        self.entry_price = 0.0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_value = 0.0

        self.reward_calculator = RewardCalculator(config.transaction_cost)

    def reset(self) -> np.ndarray:
        """Reset environment to initial state."""
        self.current_step = self.lookback
        self.position = 0.0
        self.entry_price = 0.0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_value = 0.0

        return self._get_state()

    def _get_state(self) -> np.ndarray:
        """Get current state representation."""
        start_idx = max(0, self.current_step - self.lookback)
        end_idx = self.current_step

        # Price data
        prices = self.prices[start_idx:end_idx]
        if len(prices) < self.lookback:
            prices = np.pad(prices, (self.lookback - len(prices), 0), mode="edge")

        # Normalize prices
        prices_norm = (prices - prices.mean()) / (prices.std() + 1e-8)

        # Returns
        returns = np.diff(prices) / (prices[:-1] + 1e-8)
        returns = np.pad(returns, (1, 0), mode="constant")

        # Volumes (placeholder)
        volumes = np.zeros_like(prices)

        # Simple technical indicators
        rsi = self._calculate_rsi(prices)
        ma_fast = np.mean(prices[-5:]) if len(prices) >= 5 else prices[-1]
        ma_slow = np.mean(prices[-20:]) if len(prices) >= 20 else prices[-1]
        current_price = prices[-1]
        bb_upper = np.mean(prices) + 2 * np.std(prices)
        bb_lower = np.mean(prices) - 2 * np.std(prices)

        # Build state
        state = MarketState(
            prices=prices_norm,
            volumes=volumes,
            returns=returns,
            rsi=rsi / 100.0,  # Normalize to 0-1
            macd=(ma_fast - ma_slow) / (current_price + 1e-8),
            macd_signal=0.0,
            bb_upper=(bb_upper - current_price) / (current_price + 1e-8),
            bb_lower=(current_price - bb_lower) / (current_price + 1e-8),
            atr=np.std(returns) if len(returns) > 1 else 0.0,
            position_size=self.position,
            unrealized_pnl=self._calculate_unrealized_pnl(),
            entry_price=self.entry_price / (current_price + 1e-8) if self.entry_price > 0 else 0.0,
        )

        return state.to_array()

    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI indicator using unified library."""
        if len(prices) < period + 1:
            return 50.0

        rsi_array = calculate_rsi(prices, period)
        # Return last non-NaN value
        valid_rsi = rsi_array[~np.isnan(rsi_array)]
        return float(valid_rsi[-1]) if len(valid_rsi) > 0 else 50.0

    def _calculate_unrealized_pnl(self) -> float:
        """Calculate unrealized PnL."""
        if self.position == 0 or self.entry_price == 0:
            return 0.0

        current_price = self.prices[self.current_step]
        return self.position * (current_price - self.entry_price) / self.entry_price

    def step(self, action: int) -> tuple[np.ndarray, float, bool, dict[str, Any]]:
        """
        Execute action in environment.

        Returns:
            next_state, reward, done, info
        """
        current_price = self.prices[self.current_step]
        pnl = 0.0
        position_changed = False

        rl_action = RLAction(action)

        # Execute action
        if rl_action == RLAction.BUY and self.position <= 0:
            if self.position < 0:
                # Close short first
                pnl = -self.position * (current_price - self.entry_price) / self.entry_price
            self.position = self.config.max_position_size
            self.entry_price = current_price
            position_changed = True

        elif rl_action == RLAction.SELL and self.position >= 0:
            if self.position > 0:
                # Close long first
                pnl = self.position * (current_price - self.entry_price) / self.entry_price
            self.position = -self.config.max_position_size
            self.entry_price = current_price
            position_changed = True

        elif rl_action == RLAction.CLOSE and self.position != 0:
            if self.position > 0:
                pnl = self.position * (current_price - self.entry_price) / self.entry_price
            else:
                pnl = -self.position * (current_price - self.entry_price) / self.entry_price
            self.position = 0.0
            self.entry_price = 0.0
            position_changed = True

        # Update PnL tracking
        self.total_pnl += pnl
        if self.total_pnl > self.peak_value:
            self.peak_value = self.total_pnl
        drawdown = (self.peak_value - self.total_pnl) / (self.peak_value + 1e-8) if self.peak_value > 0 else 0.0
        self.max_drawdown = max(self.max_drawdown, drawdown)

        # Calculate reward
        reward = self.reward_calculator.calculate_reward(
            pnl=pnl,
            action=rl_action,
            position_changed=position_changed,
            unrealized_pnl=self._calculate_unrealized_pnl(),
            max_drawdown=self.max_drawdown,
        )

        # Move to next step
        self.current_step += 1
        done = self.current_step >= len(self.prices) - 1

        # Get next state
        next_state = self._get_state()

        info = {
            "pnl": pnl,
            "total_pnl": self.total_pnl,
            "position": self.position,
            "max_drawdown": self.max_drawdown,
            "price": current_price,
        }

        return next_state, reward * self.config.reward_scaling, done, info


# ============================================================================
# Training Loop
# ============================================================================


async def train_rl_agent(
    agent: BaseRLAgent,
    env: TradingEnvironment,
    num_episodes: int = 1000,
    max_steps_per_episode: int = 1000,
    eval_interval: int = 100,
    save_path: str | None = None,
) -> dict[str, Any]:
    """
    Train RL agent on trading environment.

    Returns training metrics.
    """
    training_metrics = {
        "episode_rewards": [],
        "episode_lengths": [],
        "losses": [],
        "final_pnl": [],
    }

    best_reward = float("-inf")

    for episode in range(num_episodes):
        state = env.reset()
        episode_reward = 0.0
        episode_loss = 0.0
        steps = 0

        for _step in range(max_steps_per_episode):
            # Select action
            action = agent.select_action(state, training=True)

            # Take step
            next_state, reward, done, info = env.step(action)

            # Create experience
            exp = Experience(
                state=state,
                action=action,
                reward=reward,
                next_state=next_state,
                done=done,
            )

            # Update agent
            loss = agent.update(exp)
            if loss is not None:
                episode_loss += loss

            episode_reward += reward
            steps += 1
            state = next_state

            if done:
                break

        # Record metrics
        training_metrics["episode_rewards"].append(episode_reward)
        training_metrics["episode_lengths"].append(steps)
        training_metrics["losses"].append(episode_loss / max(steps, 1))
        training_metrics["final_pnl"].append(info.get("total_pnl", 0.0))

        # Logging
        if (episode + 1) % 10 == 0:
            avg_reward = np.mean(training_metrics["episode_rewards"][-10:])
            avg_pnl = np.mean(training_metrics["final_pnl"][-10:])
            logger.info(f"Episode {episode + 1}/{num_episodes}: Avg Reward: {avg_reward:.4f}, Avg PnL: {avg_pnl:.4%}")

        # Save best model
        if save_path and episode_reward > best_reward:
            best_reward = episode_reward
            agent.save(f"{save_path}/best_model")

    return training_metrics


# ============================================================================
# Global Instance
# ============================================================================

_rl_agent: BaseRLAgent | None = None


def get_rl_agent(config: RLConfig | None = None) -> BaseRLAgent:
    """Get or create global RL agent."""
    global _rl_agent
    if _rl_agent is None:
        _rl_agent = DQNAgent(config or RLConfig())
    return _rl_agent
