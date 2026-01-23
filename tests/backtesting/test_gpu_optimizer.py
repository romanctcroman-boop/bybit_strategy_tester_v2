import numpy as np
import pandas as pd
import pytest

from backend.backtesting.gpu_optimizer import GPUGridOptimizer


def _sample_candles(n: int = 30) -> pd.DataFrame:
    base = np.linspace(100, 110, n)
    data = {
        "close": base,
        "high": base + 1,
        "low": base - 1,
    }
    return pd.DataFrame(data)


def test_validation_empty_ranges():
    optimizer = GPUGridOptimizer(force_cpu=True)
    candles = _sample_candles()

    with pytest.raises(ValueError):
        optimizer.optimize(
            candles=candles,
            rsi_period_range=[],
            rsi_overbought_range=[70],
            rsi_oversold_range=[30],
            stop_loss_range=[1.0],
            take_profit_range=[2.0],
        )


def test_validation_nan_values():
    optimizer = GPUGridOptimizer(force_cpu=True)
    candles = _sample_candles()
    candles.loc[5, "close"] = np.nan

    with pytest.raises(ValueError):
        optimizer.optimize(
            candles=candles,
            rsi_period_range=[14],
            rsi_overbought_range=[70],
            rsi_oversold_range=[30],
            stop_loss_range=[1.0],
            take_profit_range=[2.0],
        )


def test_force_cpu_execution_mode():
    optimizer = GPUGridOptimizer(force_cpu=True)
    candles = _sample_candles()

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14],
        rsi_overbought_range=[70],
        rsi_oversold_range=[30],
        stop_loss_range=[1.0],
        take_profit_range=[2.0],
    )

    assert result.execution_mode.startswith("cpu")
    assert result.fallback_reason is None
    assert result.performance_stats.get("execution_mode") == result.execution_mode


def test_top_k_limit_and_order():
    optimizer = GPUGridOptimizer(force_cpu=True)
    # Колеблющийся ряд, чтобы генерировать трейды
    x = np.linspace(0, 20, 200)
    close = 100 + 5 * np.sin(x)
    candles = pd.DataFrame(
        {
            "close": close,
            "high": close + 0.5,
            "low": close - 0.5,
        }
    )

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[6, 8, 10],
        rsi_overbought_range=[55, 60, 65],
        rsi_oversold_range=[35, 40, 45],
        stop_loss_range=[0.5, 1.0],
        take_profit_range=[0.5, 1.0],
        top_k=2,
    )

    # Возвращаем не больше top_k результатов
    assert len(result.top_results) <= 2
    # Результаты отсортированы по score
    if len(result.top_results) == 2:
        assert result.top_results[0]["score"] >= result.top_results[1]["score"]


def test_top_k_validation():
    optimizer = GPUGridOptimizer(force_cpu=True)
    candles = _sample_candles()

    with pytest.raises(ValueError):
        optimizer.optimize(
            candles=candles,
            rsi_period_range=[14],
            rsi_overbought_range=[70],
            rsi_oversold_range=[30],
            stop_loss_range=[1.0],
            take_profit_range=[2.0],
            top_k=0,
        )
