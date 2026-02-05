"""
Unit tests for TradingEnv - Gymnasium-compatible RL trading environment.

Requires gymnasium: pip install gymnasium or pip install .[dev-full]
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("gymnasium")


def create_sample_df(n_bars=500):
    """Helper to create sample OHLCV DataFrame."""
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(n_bars) * 0.5)
    prices = np.maximum(prices, 10)
    return pd.DataFrame({
        "open": prices * 0.99,
        "high": prices * 1.01,
        "low": prices * 0.98,
        "close": prices,
        "volume": np.random.rand(n_bars) * 1000000,
    })


class TestTradingEnvImport:
    def test_import_trading_env(self):
        from backend.ml.rl.trading_env import TradingEnv
        assert TradingEnv is not None


class TestTradingEnvCreation:
    def test_create_env(self):
        from backend.ml.rl.trading_env import TradingConfig, TradingEnv
        df = create_sample_df()
        config = TradingConfig(initial_balance=10000.0)
        env = TradingEnv(df=df, config=config)
        assert env is not None


class TestTradingEnvReset:
    def test_reset_returns_observation(self):
        from backend.ml.rl.trading_env import TradingConfig, TradingEnv
        df = create_sample_df()
        env = TradingEnv(df=df, config=TradingConfig())
        obs, info = env.reset()
        assert isinstance(obs, np.ndarray)


class TestTradingEnvStep:
    def test_step_returns_tuple(self):
        from backend.ml.rl.trading_env import TradingConfig, TradingEnv
        df = create_sample_df()
        env = TradingEnv(df=df, config=TradingConfig())
        env.reset()
        result = env.step(0)
        assert len(result) == 5


class TestTradingEnvActionSpace:
    def test_action_space_size(self):
        from backend.ml.rl.trading_env import TradingConfig, TradingEnv
        df = create_sample_df()
        env = TradingEnv(df=df, config=TradingConfig())
        assert env.action_space.n == 4


class TestTradingEnvRewardFunctions:
    """Проверка всех reward-функций."""

    def test_reward_pnl(self):
        from backend.ml.rl.trading_env import TradingConfig, TradingEnv
        df = create_sample_df(100)
        env = TradingEnv(df=df, config=TradingConfig(), reward_function="pnl")
        obs, _ = env.reset()
        obs, reward, term, trunc, info = env.step(0)
        assert isinstance(reward, float)

    def test_reward_sharpe(self):
        from backend.ml.rl.trading_env import TradingConfig, TradingEnv
        df = create_sample_df(100)
        env = TradingEnv(df=df, config=TradingConfig(), reward_function="sharpe")
        obs, _ = env.reset()
        for _ in range(5):
            obs, reward, term, trunc, info = env.step(0)
            if term or trunc:
                break
        assert isinstance(reward, float)

    def test_reward_drawdown_penalty(self):
        from backend.ml.rl.trading_env import TradingConfig, TradingEnv
        df = create_sample_df(100)
        env = TradingEnv(df=df, config=TradingConfig(), reward_function="drawdown_penalty")
        obs, _ = env.reset()
        obs, reward, term, trunc, info = env.step(0)
        assert isinstance(reward, float)


class TestTradingEnvGymnasiumRegister:
    """Проверка регистрации gymnasium.make()."""

    def test_register_and_make(self):
        import pytest
        gym = pytest.importorskip("gymnasium")
        from backend.ml.rl.trading_env import register_trading_env

        register_trading_env()
        df = create_sample_df(100)
        env = gym.make("TradingEnv-v1", df=df)
        obs, info = env.reset(seed=42)
        assert obs is not None
        assert isinstance(obs, np.ndarray)
        env.close()
