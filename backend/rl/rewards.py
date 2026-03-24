"""
🏆 Reward Functions for RL Trading Environment

Modular reward functions that can be plugged into TradingEnv.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class RewardFunction(ABC):
    """Abstract base class for RL reward functions."""

    @abstractmethod
    def calculate(
        self,
        state: np.ndarray,
        action: int,
        next_state: np.ndarray,
        info: dict[str, Any],
    ) -> float:
        """
        Calculate reward for a transition.

        Args:
            state: Observation before action
            action: Action taken (0=hold, 1=buy, 2=sell)
            next_state: Observation after action
            info: Additional info dict from env.step()

        Returns:
            Scalar reward value
        """


class PnLReward(RewardFunction):
    """
    Simple Profit-and-Loss reward.

    Returns the realized PnL of the step, normalised by initial capital.
    """

    def calculate(
        self,
        state: np.ndarray,
        action: int,
        next_state: np.ndarray,
        info: dict[str, Any],
    ) -> float:
        return float(info.get("pnl", 0.0))


class SharpeReward(RewardFunction):
    """
    Rolling Sharpe-ratio reward.

    Accumulates per-step returns and returns the annualised Sharpe ratio
    computed over the full history so far.  A short-window version is used
    during the episode; the full window is used for terminal reward.

    Args:
        window: Number of recent returns to consider (default 252).
        annualise_factor: sqrt(periods per year), e.g. sqrt(252) for daily.
    """

    def __init__(self, window: int = 252, annualise_factor: float = 15.87) -> None:
        self.window = window
        self.annualise_factor = annualise_factor
        self._returns: list[float] = []

    def reset(self) -> None:
        """Clear accumulated returns.  Call at env.reset()."""
        self._returns = []

    def calculate(
        self,
        state: np.ndarray,
        action: int,
        next_state: np.ndarray,
        info: dict[str, Any],
    ) -> float:
        """Return rolling Sharpe ratio using net-worth history."""
        net_worths: list[float] = info.get("net_worths", [])

        if len(net_worths) >= 2:
            r = (net_worths[-1] - net_worths[-2]) / (net_worths[-2] + 1e-8)
            self._returns.append(r)

        recent = self._returns[-self.window :]
        if len(recent) < 2:
            return 0.0

        r_arr = np.array(recent, dtype=np.float64)
        std = r_arr.std()
        if std < 1e-10:
            return 0.0

        return float(r_arr.mean() / std * self.annualise_factor)


class SortinoReward(RewardFunction):
    """
    Sortino-ratio reward (penalises only downside volatility).

    Args:
        window: Number of recent returns to consider.
        annualise_factor: sqrt(periods per year).
    """

    def __init__(self, window: int = 252, annualise_factor: float = 15.87) -> None:
        self.window = window
        self.annualise_factor = annualise_factor
        self._returns: list[float] = []

    def reset(self) -> None:
        self._returns = []

    def calculate(
        self,
        state: np.ndarray,
        action: int,
        next_state: np.ndarray,
        info: dict[str, Any],
    ) -> float:
        net_worths: list[float] = info.get("net_worths", [])

        if len(net_worths) >= 2:
            r = (net_worths[-1] - net_worths[-2]) / (net_worths[-2] + 1e-8)
            self._returns.append(r)

        recent = np.array(self._returns[-self.window :], dtype=np.float64)
        if len(recent) < 2:
            return 0.0

        mean_r = recent.mean()
        downside = recent[recent < 0]
        if len(downside) == 0:
            return float(mean_r * self.annualise_factor)

        downside_std = downside.std()
        if downside_std < 1e-10:
            return float(mean_r * self.annualise_factor)

        return float(mean_r / downside_std * self.annualise_factor)
