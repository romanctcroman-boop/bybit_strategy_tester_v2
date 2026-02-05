"""
Gymnasium-Compatible Trading Environment for RL Agent.

Standardized RL environment for trading strategy development.
Supports Gymnasium API (obs, info = reset(); obs, reward, term, trunc, info = step(action)).

Reward functions: pnl, log_return, sharpe, sortino, calmar, drawdown_penalty.
Register: gymnasium.make("TradingEnv-v1") after register_trading_env().
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Try to import gymnasium (modern fork) or gym
try:
    import gymnasium as gym
    from gymnasium import spaces

    GYM_AVAILABLE = True
    GYM_VERSION = "gymnasium"
except ImportError:
    try:
        import gym
        from gym import spaces

        GYM_AVAILABLE = True
        GYM_VERSION = "gym"
    except ImportError:
        GYM_AVAILABLE = False
        gym = None  # type: ignore
        spaces = None  # type: ignore
        GYM_VERSION = None


class TradingAction(IntEnum):
    """Trading actions for the agent."""

    HOLD = 0
    BUY = 1
    SELL = 2
    CLOSE = 3


@dataclass
class TradingConfig:
    """Configuration for the trading environment."""

    initial_balance: float = 10000.0
    max_position_size: float = 1.0
    commission_rate: float = 0.0007  # 0.07% Bybit
    slippage: float = 0.0001  # 0.01%
    leverage: float = 1.0
    max_leverage: float = 10.0
    risk_per_trade: float = 0.02  # 2% risk per trade
    lookback_window: int = 50  # Bars for observation
    reward_scaling: float = 1.0
    use_normalized_observations: bool = True
    include_position_info: bool = True
    include_pnl_info: bool = True


@dataclass
class TradingState:
    """Internal state of the trading environment."""

    balance: float = 10000.0
    position: float = 0.0  # Positive = long, negative = short
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    max_drawdown: float = 0.0
    peak_balance: float = 10000.0
    history: list[dict[str, Any]] = field(default_factory=list)


class TradingEnv(gym.Env if GYM_AVAILABLE else object):
    """
    OpenAI Gym/Gymnasium-compatible trading environment.

    This environment simulates trading on OHLCV data with realistic
    commission, slippage, and position management.

    Features:
    - Supports long/short positions
    - Realistic commission and slippage
    - Configurable observation space (OHLCV + indicators)
    - Multiple reward functions
    - Position sizing based on risk

    Usage:
        import numpy as np

        # Create environment
        env = TradingEnv(df, config=TradingConfig())

        # Reset and run episode
        obs, info = env.reset()
        done = False

        while not done:
            action = agent.predict(obs)
            obs, reward, done, truncated, info = env.step(action)

        print(f"Final PnL: {info['realized_pnl']}")
    """

    metadata = {"render_modes": ["human", "ansi"]}

    def __init__(
        self,
        df: Any,  # pandas DataFrame with OHLCV data
        config: TradingConfig | None = None,
        indicators: list[str] | None = None,
        reward_function: str = "pnl",
        render_mode: str | None = None,
    ):
        """
        Initialize trading environment.

        Args:
            df: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
            config: Trading configuration
            indicators: Additional indicator columns to include in observations
            reward_function: 'pnl', 'log_return', 'sharpe', 'sortino', 'calmar', 'drawdown_penalty'
            render_mode: Rendering mode
        """
        if not GYM_AVAILABLE:
            raise ImportError("gymnasium or gym library not installed. Install with: pip install gymnasium")

        self.df = df.copy()
        self.config = config or TradingConfig()
        self.indicators = indicators or []
        if reward_function not in REWARD_FUNCTIONS:
            logger.warning(f"Unknown reward_function '{reward_function}', using 'pnl'")
            reward_function = "pnl"
        self.reward_function = reward_function
        self.render_mode = render_mode

        # Validate data
        required_cols = ["open", "high", "low", "close", "volume"]
        missing = [c for c in required_cols if c not in self.df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Convert to numpy for speed
        self.prices = self.df[["open", "high", "low", "close", "volume"]].values
        self.n_steps = len(self.prices)

        # Include indicators if available
        self.indicator_data = None
        if self.indicators:
            available = [c for c in self.indicators if c in self.df.columns]
            if available:
                self.indicator_data = self.df[available].values

        # Define action and observation spaces
        self.action_space = spaces.Discrete(4)  # HOLD, BUY, SELL, CLOSE

        # Calculate observation dimension
        obs_dim = self._calculate_obs_dim()
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32)

        # Initialize state
        self.state = TradingState(balance=self.config.initial_balance)
        self.current_step = 0
        self._rewards_history: list[float] = []

    def _calculate_obs_dim(self) -> int:
        """Calculate observation space dimension."""
        # Base OHLCV features
        dim = 5 * self.config.lookback_window

        # Indicator features
        if self.indicator_data is not None:
            dim += self.indicator_data.shape[1] * self.config.lookback_window

        # Position info
        if self.config.include_position_info:
            dim += 3  # position_size, entry_price_normalized, bars_in_position

        # PnL info
        if self.config.include_pnl_info:
            dim += 3  # unrealized_pnl, realized_pnl, drawdown

        return dim

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """
        Reset the environment to initial state.

        Args:
            seed: Random seed
            options: Additional options

        Returns:
            Initial observation and info dict
        """
        if seed is not None:
            np.random.seed(seed)

        # Reset state
        self.state = TradingState(
            balance=self.config.initial_balance,
            peak_balance=self.config.initial_balance,
        )
        self.current_step = self.config.lookback_window
        self._rewards_history = []

        obs = self._get_observation()
        info = self._get_info()

        return obs, info

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """
        Execute one step in the environment.

        Args:
            action: Trading action (0=HOLD, 1=BUY, 2=SELL, 3=CLOSE)

        Returns:
            observation, reward, terminated, truncated, info
        """
        # Store previous state for reward calculation
        prev_equity = self._get_equity()

        # Execute action
        self._execute_action(TradingAction(action))

        # Move to next step
        self.current_step += 1

        # Update unrealized PnL
        self._update_unrealized_pnl()

        # Calculate reward
        current_equity = self._get_equity()
        reward = self._calculate_reward(prev_equity, current_equity)
        self._rewards_history.append(reward)

        # Check if done
        terminated = self._is_terminated()
        truncated = self.current_step >= self.n_steps - 1

        # Get observation and info
        obs = self._get_observation()
        info = self._get_info()

        return obs, reward, terminated, truncated, info

    def _execute_action(self, action: TradingAction) -> None:
        """Execute a trading action."""
        current_price = self.prices[self.current_step, 3]  # Close price

        if action == TradingAction.HOLD:
            pass

        elif action == TradingAction.BUY:
            if self.state.position <= 0:  # Not already long
                # Close short if exists
                if self.state.position < 0:
                    self._close_position(current_price)

                # Open long
                self._open_position(current_price, is_long=True)

        elif action == TradingAction.SELL:
            if self.state.position >= 0:  # Not already short
                # Close long if exists
                if self.state.position > 0:
                    self._close_position(current_price)

                # Open short
                self._open_position(current_price, is_long=False)

        elif action == TradingAction.CLOSE:
            if self.state.position != 0:
                self._close_position(current_price)

    def _open_position(self, price: float, is_long: bool) -> None:
        """Open a new position."""
        # Apply slippage
        slippage = price * self.config.slippage
        entry_price = price + slippage if is_long else price - slippage

        # Calculate position size based on risk
        position_size = self._calculate_position_size(entry_price)

        # Apply commission
        commission = position_size * entry_price * self.config.commission_rate
        self.state.balance -= commission

        # Update state
        self.state.position = position_size if is_long else -position_size
        self.state.entry_price = entry_price
        self.state.total_trades += 1

        # Record history
        self.state.history.append(
            {
                "step": self.current_step,
                "action": "open_long" if is_long else "open_short",
                "price": entry_price,
                "size": self.state.position,
                "balance": self.state.balance,
            }
        )

    def _close_position(self, price: float) -> None:
        """Close the current position."""
        if self.state.position == 0:
            return

        is_long = self.state.position > 0

        # Apply slippage
        slippage = price * self.config.slippage
        exit_price = price - slippage if is_long else price + slippage

        # Calculate PnL
        if is_long:
            pnl = (exit_price - self.state.entry_price) * abs(self.state.position)
        else:
            pnl = (self.state.entry_price - exit_price) * abs(self.state.position)

        # Apply leverage
        pnl *= self.config.leverage

        # Apply commission
        commission = abs(self.state.position) * exit_price * self.config.commission_rate
        pnl -= commission

        # Update state
        self.state.balance += pnl
        self.state.realized_pnl += pnl

        if pnl > 0:
            self.state.winning_trades += 1
        else:
            self.state.losing_trades += 1

        # Update peak and drawdown
        equity = self._get_equity()
        self.state.peak_balance = max(self.state.peak_balance, equity)
        drawdown = (self.state.peak_balance - equity) / self.state.peak_balance
        self.state.max_drawdown = max(self.state.max_drawdown, drawdown)

        # Record history
        self.state.history.append(
            {
                "step": self.current_step,
                "action": "close",
                "price": exit_price,
                "pnl": pnl,
                "balance": self.state.balance,
            }
        )

        # Reset position
        self.state.position = 0
        self.state.entry_price = 0
        self.state.unrealized_pnl = 0

    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size based on risk management."""
        # Simple position sizing: risk_per_trade of balance
        risk_amount = self.state.balance * self.config.risk_per_trade
        position_value = min(
            risk_amount / self.config.commission_rate,
            self.state.balance * self.config.max_position_size,
        )
        return position_value / price

    def _update_unrealized_pnl(self) -> None:
        """Update unrealized PnL based on current price."""
        if self.state.position == 0:
            self.state.unrealized_pnl = 0
            return

        current_price = self.prices[self.current_step, 3]
        is_long = self.state.position > 0

        if is_long:
            self.state.unrealized_pnl = (
                (current_price - self.state.entry_price) * abs(self.state.position) * self.config.leverage
            )
        else:
            self.state.unrealized_pnl = (
                (self.state.entry_price - current_price) * abs(self.state.position) * self.config.leverage
            )

    def _get_equity(self) -> float:
        """Get current equity (balance + unrealized PnL)."""
        return self.state.balance + self.state.unrealized_pnl

    def _calculate_reward(self, prev_equity: float, current_equity: float) -> float:
        """Calculate reward based on selected reward function."""
        if self.reward_function == "pnl":
            # Simple PnL change
            reward = (current_equity - prev_equity) / self.config.initial_balance

        elif self.reward_function == "log_return":
            # Log return
            if prev_equity > 0:
                reward = np.log(current_equity / prev_equity)
            else:
                reward = -1.0

        elif self.reward_function == "sharpe":
            # Approximate Sharpe ratio
            if len(self._rewards_history) > 1:
                returns = np.array(self._rewards_history[-100:])
                std = np.std(returns)
                if std > 0:
                    reward = np.mean(returns) / std
                else:
                    reward = 0.0
            else:
                reward = (current_equity - prev_equity) / self.config.initial_balance

        elif self.reward_function == "sortino":
            # Approximate Sortino ratio (only penalize downside)
            if len(self._rewards_history) > 1:
                returns = np.array(self._rewards_history[-100:])
                downside = returns[returns < 0]
                if len(downside) > 0:
                    downside_std = np.std(downside)
                    if downside_std > 0:
                        reward = np.mean(returns) / downside_std
                    else:
                        reward = np.mean(returns)
                else:
                    reward = np.mean(returns)
            else:
                reward = (current_equity - prev_equity) / self.config.initial_balance

        elif self.reward_function == "calmar":
            # Calmar-like: return / drawdown
            ret = (current_equity - prev_equity) / max(prev_equity, 1e-8)
            dd = max(self.state.max_drawdown, 0.01)
            reward = ret / dd

        elif self.reward_function == "drawdown_penalty":
            # PnL minus drawdown penalty
            ret = (current_equity - prev_equity) / self.config.initial_balance
            penalty = self.state.max_drawdown * 2.0  # Penalize drawdown
            reward = ret - penalty

        else:
            reward = (current_equity - prev_equity) / self.config.initial_balance

        return reward * self.config.reward_scaling

    def _get_observation(self) -> np.ndarray:
        """Get current observation."""
        obs_parts = []

        # OHLCV window
        start_idx = max(0, self.current_step - self.config.lookback_window)
        end_idx = self.current_step
        ohlcv = self.prices[start_idx:end_idx]

        # Normalize OHLCV
        if self.config.use_normalized_observations and len(ohlcv) > 0:
            # Normalize by last close price
            last_close = ohlcv[-1, 3] if len(ohlcv) > 0 else 1.0
            if last_close > 0:
                ohlcv = ohlcv / last_close

        # Pad if needed
        if len(ohlcv) < self.config.lookback_window:
            padding = np.zeros((self.config.lookback_window - len(ohlcv), 5))
            ohlcv = np.vstack([padding, ohlcv])

        obs_parts.append(ohlcv.flatten())

        # Indicators
        if self.indicator_data is not None:
            ind = self.indicator_data[start_idx:end_idx]
            if len(ind) < self.config.lookback_window:
                padding = np.zeros((self.config.lookback_window - len(ind), ind.shape[1]))
                ind = np.vstack([padding, ind])
            obs_parts.append(ind.flatten())

        # Position info
        if self.config.include_position_info:
            current_price = self.prices[self.current_step, 3]
            obs_parts.append(
                np.array(
                    [
                        self.state.position / self.config.max_position_size,
                        (self.state.entry_price / current_price - 1) if current_price > 0 else 0,
                        min(self.current_step, 100) / 100,  # Normalized time in position
                    ]
                )
            )

        # PnL info
        if self.config.include_pnl_info:
            obs_parts.append(
                np.array(
                    [
                        self.state.unrealized_pnl / self.config.initial_balance,
                        self.state.realized_pnl / self.config.initial_balance,
                        self.state.max_drawdown,
                    ]
                )
            )

        return np.concatenate(obs_parts).astype(np.float32)

    def _get_info(self) -> dict[str, Any]:
        """Get current info dict."""
        return {
            "balance": self.state.balance,
            "position": self.state.position,
            "entry_price": self.state.entry_price,
            "unrealized_pnl": self.state.unrealized_pnl,
            "realized_pnl": self.state.realized_pnl,
            "equity": self._get_equity(),
            "total_trades": self.state.total_trades,
            "winning_trades": self.state.winning_trades,
            "losing_trades": self.state.losing_trades,
            "win_rate": (self.state.winning_trades / self.state.total_trades if self.state.total_trades > 0 else 0),
            "max_drawdown": self.state.max_drawdown,
            "current_step": self.current_step,
            "current_price": self.prices[self.current_step, 3],
        }

    def _is_terminated(self) -> bool:
        """Check if episode should terminate."""
        # Terminate if bankrupt
        if self._get_equity() <= 0:
            return True

        # Terminate if max drawdown exceeded
        if self.state.max_drawdown > 0.5:  # 50% drawdown
            return True

        return False

    def render(self) -> str | None:
        """Render the environment."""
        if self.render_mode == "human":
            info = self._get_info()
            print(f"Step: {self.current_step}")
            print(f"  Price: {info['current_price']:.2f}")
            print(f"  Position: {info['position']:.4f}")
            print(f"  Equity: {info['equity']:.2f}")
            print(f"  PnL: {info['realized_pnl']:.2f}")
            print(f"  Win Rate: {info['win_rate']:.1%}")
            print()
            return None

        elif self.render_mode == "ansi":
            info = self._get_info()
            return (
                f"Step {self.current_step}: "
                f"Price={info['current_price']:.2f}, "
                f"Pos={info['position']:.4f}, "
                f"Equity={info['equity']:.2f}, "
                f"PnL={info['realized_pnl']:.2f}"
            )

        return None

    def close(self) -> None:
        """Clean up environment resources."""
        pass


# Typed reward function names for Gymnasium
REWARD_FUNCTIONS = ("pnl", "log_return", "sharpe", "sortino", "calmar", "drawdown_penalty")


def register_trading_env() -> None:
    """Register the trading environment with Gym."""
    if not GYM_AVAILABLE:
        logger.warning("Cannot register environment: gym not available")
        return

    try:
        if GYM_VERSION == "gymnasium":
            import gymnasium

            gymnasium.register(
                id="TradingEnv-v1",
                entry_point="backend.ml.rl.trading_env:TradingEnv",
            )
        else:
            import gym

            gym.envs.registration.register(
                id="TradingEnv-v1",
                entry_point="backend.ml.rl.trading_env:TradingEnv",
            )
        logger.info("Registered TradingEnv-v1")
    except Exception as e:
        logger.warning(f"Failed to register environment: {e}")
