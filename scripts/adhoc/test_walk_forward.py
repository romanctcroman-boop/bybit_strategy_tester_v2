"""Test Walk-Forward Optimization."""

import numpy as np
import pandas as pd

from backend.backtesting.walk_forward import WalkForwardOptimizer


def create_sample_data(n_bars: int = 2000) -> pd.DataFrame:
    """Create sample OHLCV data."""
    np.random.seed(42)

    timestamps = pd.date_range(start="2025-01-01", periods=n_bars, freq="1h")

    # Generate price data with trend and noise
    returns = np.random.randn(n_bars) * 0.002
    # Add some trend periods
    returns[200:400] += 0.001  # Uptrend
    returns[600:800] -= 0.001  # Downtrend
    returns[1000:1200] += 0.0015  # Strong uptrend

    close = 100 * np.exp(np.cumsum(returns))
    high = close * (1 + np.abs(np.random.randn(n_bars)) * 0.005)
    low = close * (1 - np.abs(np.random.randn(n_bars)) * 0.005)
    open_p = close + np.random.randn(n_bars) * 0.5
    volume = np.random.randint(1000, 10000, n_bars).astype(float)

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_p,
            "high": np.maximum.reduce([open_p, high, close]),
            "low": np.minimum.reduce([open_p, low, close]),
            "close": close,
            "volume": volume,
        }
    )


def simple_backtest(data: pd.DataFrame, params: dict) -> dict:
    """
    Simple moving average crossover backtest for testing.

    Args:
        data: OHLCV DataFrame
        params: {"fast_period": int, "slow_period": int}

    Returns:
        dict with sharpe_ratio, total_return, total_trades
    """
    fast_period = params.get("fast_period", 10)
    slow_period = params.get("slow_period", 20)

    close = data["close"].values
    n = len(close)

    # Calculate SMAs
    fast_sma = pd.Series(close).rolling(fast_period).mean().values
    slow_sma = pd.Series(close).rolling(slow_period).mean().values

    # Generate signals
    position = 0
    equity = [10000.0]
    trades = 0
    entry_price = 0

    for i in range(slow_period, n):
        if np.isnan(fast_sma[i]) or np.isnan(slow_sma[i]):
            equity.append(equity[-1])
            continue

        # Long signal
        if fast_sma[i] > slow_sma[i] and position == 0:
            position = 1
            entry_price = close[i]
            trades += 1
        # Exit signal
        elif fast_sma[i] < slow_sma[i] and position == 1:
            pnl = (close[i] - entry_price) / entry_price * equity[-1]
            equity.append(equity[-1] + pnl)
            position = 0
            continue

        # Mark-to-market
        if position == 1:
            unrealized = (close[i] - entry_price) / entry_price * equity[-1]
            equity.append(
                equity[-1] + unrealized - (equity[-1] - 10000)
                if len(equity) > 1
                else 10000 + unrealized
            )
        else:
            equity.append(equity[-1])

    # Calculate metrics
    equity = np.array(equity)
    returns = np.diff(equity) / equity[:-1]
    returns = returns[~np.isnan(returns)]

    if len(returns) < 2 or np.std(returns) == 0:
        sharpe = 0
    else:
        sharpe = (
            np.mean(returns) / np.std(returns) * np.sqrt(252 * 24)
        )  # Hourly to annual

    total_return = (equity[-1] - equity[0]) / equity[0]

    return {
        "sharpe_ratio": sharpe,
        "total_return": total_return,
        "total_trades": trades,
    }


def test_walk_forward_rolling():
    """Test rolling walk-forward optimization."""
    print("\n" + "=" * 70)
    print("Test 1: Rolling Walk-Forward Optimization")
    print("=" * 70)

    # Create sample data
    data = create_sample_data(2000)
    print(
        f"Data: {len(data)} bars, {data['timestamp'].iloc[0]} to {data['timestamp'].iloc[-1]}"
    )

    # Define parameter grid
    param_grid = {
        "fast_period": [5, 10, 15, 20],
        "slow_period": [20, 30, 40, 50],
    }

    # Create optimizer
    wfo = WalkForwardOptimizer(
        in_sample_ratio=0.7,
        n_windows=4,
        mode="rolling",
        min_trades_per_window=3,
    )

    # Run optimization
    result = wfo.optimize(
        data=data,
        param_grid=param_grid,
        backtest_func=simple_backtest,
        optimize_metric="sharpe_ratio",
        strategy_name="SMA Crossover",
    )

    # Print report
    report = wfo.print_report(result)
    print(report)

    # Assertions
    assert result.total_windows > 0, "Should have at least one window"
    print(f"\n✅ Rolling WFO test PASSED ({result.total_windows} windows)")

    return result


def test_walk_forward_anchored():
    """Test anchored walk-forward optimization."""
    print("\n" + "=" * 70)
    print("Test 2: Anchored Walk-Forward Optimization")
    print("=" * 70)

    data = create_sample_data(2000)

    param_grid = {
        "fast_period": [10, 15],
        "slow_period": [30, 40],
    }

    wfo = WalkForwardOptimizer(
        in_sample_ratio=0.7,
        n_windows=3,
        mode="anchored",
        min_trades_per_window=3,
    )

    result = wfo.optimize(
        data=data,
        param_grid=param_grid,
        backtest_func=simple_backtest,
        optimize_metric="sharpe_ratio",
        strategy_name="SMA Crossover (Anchored)",
    )

    report = wfo.print_report(result)
    print(report)

    assert result.total_windows > 0, "Should have at least one window"
    print(f"\n✅ Anchored WFO test PASSED ({result.total_windows} windows)")

    return result


def test_robustness_metrics():
    """Test robustness metrics calculation."""
    print("\n" + "=" * 70)
    print("Test 3: Robustness Metrics")
    print("=" * 70)

    data = create_sample_data(3000)

    param_grid = {
        "fast_period": [5, 10, 15, 20, 25],
        "slow_period": [25, 30, 35, 40, 50],
    }

    wfo = WalkForwardOptimizer(
        in_sample_ratio=0.7,
        n_windows=5,
        mode="rolling",
        min_trades_per_window=2,
    )

    result = wfo.optimize(
        data=data,
        param_grid=param_grid,
        backtest_func=simple_backtest,
        optimize_metric="sharpe_ratio",
        strategy_name="Robustness Test",
    )

    print(f"  Avg IS Sharpe: {result.avg_is_sharpe:.2f}")
    print(f"  Avg OOS Sharpe: {result.avg_oos_sharpe:.2f}")
    print(f"  Sharpe Degradation: {result.avg_sharpe_degradation:+.1f}%")
    print(f"  OOS Win Rate: {result.oos_win_rate:.1f}%")
    print(f"  Parameter Stability: {result.parameter_stability:.1f}%")

    # Check that metrics are calculated
    assert result.avg_is_sharpe != 0 or result.avg_oos_sharpe != 0, (
        "Metrics should be non-zero"
    )

    print("\n✅ Robustness metrics test PASSED")


def main():
    """Run all tests."""
    print("=" * 70)
    print("  WALK-FORWARD OPTIMIZATION TESTS")
    print("=" * 70)

    test_walk_forward_rolling()
    test_walk_forward_anchored()
    test_robustness_metrics()

    print("\n" + "=" * 70)
    print("  ALL TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    main()
