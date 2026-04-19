"""
🤖 Trading Environment for RL

Gymnasium-compatible trading environment.
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TradingAction:
    """Trading action"""

    action: int  # 0=hold, 1=buy, 2=sell
    quantity: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None


class TradingEnv:
    """
    Gymnasium-compatible trading environment.

    Action space:
    - 0: Hold
    - 1: Buy
    - 2: Sell

    Observation space:
    - Price features (OHLCV)
    - Technical indicators
    - Position state
    - Account state

    Reward:
    - Configurable (PnL, Sharpe, Sortino, etc.)
    """

    metadata = {"render_modes": ["human", "ansi"]}

    def __init__(
        self,
        data: pd.DataFrame,
        initial_balance: float = 10000.0,
        commission: float = 0.0007,
        reward_type: str = "pnl",
        window_size: int = 10,
    ):
        """
        Args:
            data: OHLCV data
            initial_balance: Initial balance
            commission: Commission rate
            reward_type: Reward function type
            window_size: Observation window size
        """
        self.data = data
        self.initial_balance = initial_balance
        self.commission = commission
        self.reward_type = reward_type
        self.window_size = window_size

        # Action space: 3 actions (hold, buy, sell)
        self.action_space = 3

        # Observation space: features
        self.n_features = 20  # OHLCV + indicators + state
        self.observation_space = (window_size, self.n_features)

        # State
        self.current_step = 0
        self.balance = initial_balance
        self.position = 0  # 0=no position, 1=long, -1=short
        self.position_size = 0.0
        self.position_price = 0.0
        self.trades: list[dict] = []
        self.done = False

        # History
        self.net_worths: list[float] = []
        self.positions_history: list[dict] = []

    def reset(self) -> np.ndarray:
        """Reset environment"""
        self.current_step = 0
        self.balance = self.initial_balance
        self.position = 0
        self.position_size = 0.0
        self.position_price = 0.0
        self.trades = []
        self.done = False
        self.net_worths = [self.initial_balance]
        self.positions_history = []

        return self._get_observation()

    def step(self, action: int) -> tuple[np.ndarray, float, bool, dict[str, Any]]:
        """
        Take action.

        Args:
            action: 0=hold, 1=buy, 2=sell

        Returns:
            (observation, reward, done, info)
        """
        self.current_step += 1

        # Execute action
        reward = self._execute_action(action)

        # Update net worth
        net_worth = self._calculate_net_worth()
        self.net_worths.append(net_worth)

        # Check if done
        if self.current_step >= len(self.data) - 1 or net_worth <= 0:
            self.done = True

        # Get next observation
        obs = self._get_observation()

        # Info
        info = {
            "net_worth": net_worth,
            "balance": self.balance,
            "position": self.position,
            "step": self.current_step,
        }

        return obs, reward, self.done, info

    def _get_observation(self) -> np.ndarray:
        """Get current observation"""
        start_idx = max(0, self.current_step - self.window_size + 1)
        end_idx = self.current_step + 1

        window = self.data.iloc[start_idx:end_idx]

        # Features
        features = []

        for idx in range(len(window)):
            row = window.iloc[idx]

            feat = [
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
                # Normalized price
                row["close"] / self.data["close"].iloc[0] - 1,
                # Returns
                row["close"] / window.iloc[max(0, idx - 1)]["close"] - 1 if idx > 0 else 0,
                # Position state
                float(self.position),
                self.position_size,
                # Account state
                self.balance / self.initial_balance,
            ]

            # Pad if needed
            while len(feat) < self.n_features:
                feat.append(0.0)

            features.append(feat[: self.n_features])

        # Pad window if needed
        while len(features) < self.window_size:
            features.insert(0, [0.0] * self.n_features)

        return np.array(features)

    def _execute_action(self, action: int) -> float:
        """Execute action and return reward"""
        current_price = self.data["close"].iloc[self.current_step]

        reward = 0.0

        if action == 1:  # Buy
            if self.position == 0:
                # Open long position
                quantity = self.balance * 0.95 / current_price  # Use 95% of balance
                self.position = 1
                self.position_size = quantity
                self.position_price = current_price
                self.balance -= quantity * current_price * (1 + self.commission)

                self.trades.append(
                    {
                        "type": "buy",
                        "price": current_price,
                        "quantity": quantity,
                        "step": self.current_step,
                    }
                )

        elif action == 2 and self.position == 1:  # Sell - Close long position
            pnl = (current_price - self.position_price) * self.position_size
            self.balance += self.position_size * current_price * (1 - self.commission)

            reward = pnl / self.initial_balance  # Reward = PnL

            self.trades.append(
                {
                    "type": "sell",
                    "price": current_price,
                    "quantity": self.position_size,
                    "pnl": pnl,
                    "step": self.current_step,
                }
            )

            self.position = 0
            self.position_size = 0.0
            self.position_price = 0.0

        return reward

    def _calculate_net_worth(self) -> float:
        """Calculate net worth"""
        current_price = self.data["close"].iloc[self.current_step]

        position_value = self.position_size * current_price if self.position == 1 else 0.0

        return self.balance + position_value

    def render(self, mode="human"):
        """Render environment"""
        net_worth = self._calculate_net_worth()
        profit = net_worth - self.initial_balance

        if mode == "human":
            print(f"Step: {self.current_step}, Net Worth: {net_worth:.2f}, Profit: {profit:.2f}")

        return f"Step {self.current_step}, Profit: {profit:.2f}"

    def get_performance(self) -> dict[str, Any]:
        """Get trading performance"""
        if len(self.net_worths) < 2:
            return {}

        net_worths = np.array(self.net_worths)
        returns = np.diff(net_worths) / net_worths[:-1]

        total_return = (net_worths[-1] - net_worths[0]) / net_worths[0]

        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 0 and np.std(returns) > 0 else 0.0

        return {
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "final_net_worth": net_worths[-1],
            "total_trades": len(self.trades),
        }


# Alias for Gymnasium registration
TradingEnvV1 = TradingEnv
