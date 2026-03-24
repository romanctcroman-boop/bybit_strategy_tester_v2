"""
🔧 Gymnasium Wrapper for TradingEnv

Thin adapter that adds Gymnasium-style interface helpers and reward-function
injection on top of the core TradingEnv.
"""

import logging
from typing import Any

import numpy as np

from .rewards import PnLReward, RewardFunction
from .trading_env import TradingEnv

logger = logging.getLogger(__name__)


class TradingEnvWrapper:
    """
    Wrapper around TradingEnv that:

    * Accepts a pluggable :class:`RewardFunction` instead of hard-coded PnL.
    * Exposes the standard Gymnasium ``reset / step / render / close`` API.
    * Proxies any attribute not found on the wrapper to the underlying env.

    Args:
        env: A :class:`TradingEnv` instance to wrap.
        reward_fn: Optional reward function. Defaults to :class:`PnLReward`.
    """

    def __init__(
        self,
        env: TradingEnv,
        reward_fn: RewardFunction | None = None,
    ) -> None:
        self.env = env
        self.reward_fn: RewardFunction = reward_fn if reward_fn is not None else PnLReward()

        # Expose spaces directly
        self.action_space = env.action_space
        self.observation_space = env.observation_space
        self.metadata = getattr(env, "metadata", {})

    # ------------------------------------------------------------------
    # Gymnasium-style API
    # ------------------------------------------------------------------

    def reset(self, *, seed: int | None = None, options: dict | None = None) -> tuple[np.ndarray, dict]:
        """
        Reset the environment.

        Returns:
            (observation, info) tuple for Gymnasium compatibility.
        """
        if hasattr(self.reward_fn, "reset"):
            self.reward_fn.reset()  # type: ignore[union-attr]

        obs = self.env.reset()
        return obs, {}

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """
        Take one step.

        Returns:
            (obs, reward, terminated, truncated, info) — Gymnasium v0.26+ style.
        """
        prev_obs = self.env._get_observation()
        obs, _raw_reward, done, info = self.env.step(action)

        # Inject net_worths for Sharpe/Sortino rewards
        info["net_worths"] = list(self.env.net_worths)

        reward = self.reward_fn.calculate(prev_obs, action, obs, info)

        # Gymnasium v0.26 uses terminated + truncated instead of a single done
        terminated = done
        truncated = False

        return obs, reward, terminated, truncated, info

    def render(self) -> Any:
        return self.env.render()

    def close(self) -> None:
        if hasattr(self.env, "close"):
            self.env.close()  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Delegation
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to the wrapped environment."""
        return getattr(self.env, name)

    def __repr__(self) -> str:
        return f"TradingEnvWrapper(env={self.env!r}, reward_fn={self.reward_fn!r})"
