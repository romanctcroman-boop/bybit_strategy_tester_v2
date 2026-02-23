"""Test Kelly Calculator and Monte Carlo Analyzer."""

import numpy as np

from backend.backtesting.position_sizing import (
    IndicatorCache,
    KellyCalculator,
    MonteCarloAnalyzer,
    TradeResult,
)


def create_sample_trades(n_trades: int = 100, win_rate: float = 0.55) -> list:
    """Create sample trades for testing."""
    np.random.seed(42)
    trades = []

    for _i in range(n_trades):
        is_win = np.random.random() < win_rate
        entry_price = 100.0

        if is_win:
            # Winning trade: +1% to +5%
            exit_price = entry_price * (1 + np.random.uniform(0.01, 0.05))
        else:
            # Losing trade: -1% to -3%
            exit_price = entry_price * (1 - np.random.uniform(0.01, 0.03))

        size = 1.0
        pnl = size * (exit_price - entry_price)

        trades.append(
            TradeResult(
                pnl=pnl,
                entry_price=entry_price,
                exit_price=exit_price,
                size=size,
            )
        )

    return trades


def test_kelly_calculator():
    """Test Kelly Calculator."""
    print("\n" + "=" * 60)
    print("Testing Kelly Calculator")
    print("=" * 60)

    kelly = KellyCalculator(
        min_trades=30,
        lookback_trades=100,
        use_exponential_weights=True,
        kelly_fraction=0.5,  # Half-Kelly
    )

    # Test with insufficient trades
    small_trades = create_sample_trades(10)
    size = kelly.calculate(small_trades, default_size=0.1)
    print("\n1. Insufficient trades (10):")
    print(f"   Position size: {size:.1%} (should be default 10%)")
    assert abs(size - 0.1) < 0.001, "Should return default size"

    # Test with sufficient trades
    trades = create_sample_trades(100, win_rate=0.55)
    size = kelly.calculate(trades)
    print("\n2. Sufficient trades (100, 55% win rate):")
    print(f"   Calculated position size: {size:.1%}")

    # Get detailed stats
    stats = kelly.get_kelly_stats(trades)
    print("\n3. Kelly Statistics:")
    print(f"   Win Rate: {stats['win_rate']:.1%}")
    print(f"   Win/Loss Ratio: {stats['win_loss_ratio']:.2f}")
    print(f"   Full Kelly: {stats['full_kelly']:.1%}")
    print(f"   Half Kelly: {stats['half_kelly']:.1%}")
    print(f"   Recommended Position: {stats['kelly_fraction']:.1%}")

    # Test with high win rate
    high_wr_trades = create_sample_trades(100, win_rate=0.70)
    high_stats = kelly.get_kelly_stats(high_wr_trades)
    print("\n4. High win rate (70%):")
    print(f"   Full Kelly: {high_stats['full_kelly']:.1%}")
    print(f"   Recommended: {high_stats['kelly_fraction']:.1%}")

    # Test with low win rate
    low_wr_trades = create_sample_trades(100, win_rate=0.40)
    low_stats = kelly.get_kelly_stats(low_wr_trades)
    print("\n5. Low win rate (40%):")
    print(f"   Full Kelly: {low_stats['full_kelly']:.1%}")
    print(f"   Recommended: {low_stats['kelly_fraction']:.1%}")

    print("\n✅ Kelly Calculator test PASSED!")


def test_monte_carlo():
    """Test Monte Carlo Analyzer."""
    print("\n" + "=" * 60)
    print("Testing Monte Carlo Analyzer")
    print("=" * 60)

    mc = MonteCarloAnalyzer(
        n_simulations=1000,
        confidence_level=0.95,
        random_seed=42,
    )

    # Test with sample trades
    trades = create_sample_trades(100, win_rate=0.55)

    print("\n1. Running Monte Carlo simulation...")
    results = mc.run_simulation(
        trades,
        initial_capital=10000,
        target_return=0.50,  # 50% target
        max_drawdown_limit=0.20,  # 20% max DD limit
    )

    print(f"\n2. Simulation Results ({results['n_simulations']} simulations):")
    print(f"   Expected Return: {results['return_mean']:.1%}")
    print(f"   Return Std Dev: {results['return_std']:.1%}")
    print(
        f"   95% CI: [{results['return_ci_lower']:.1%}, {results['return_ci_upper']:.1%}]"
    )

    print("\n3. Risk Metrics:")
    print(f"   Mean Max Drawdown: {results['max_drawdown_mean']:.1%}")
    print(f"   Worst Max Drawdown: {results['max_drawdown_worst']:.1%}")
    print(f"   VaR (95%): {results['var_95']:.1%}")
    print(f"   CVaR (95%): {results['cvar_95']:.1%}")

    print("\n4. Sharpe Ratio:")
    print(f"   Mean: {results['sharpe_mean']:.2f}")
    print(
        f"   95% CI: [{results['sharpe_ci_lower']:.2f}, {results['sharpe_ci_upper']:.2f}]"
    )

    print("\n5. Probability Metrics:")
    print(f"   P(Profit): {results['probability_of_profit']:.1%}")
    print(f"   P(50% Return): {results['probability_of_target']:.1%}")
    print(f"   Risk of Ruin (>20% DD): {results['risk_of_ruin']:.1%}")

    # Test path simulation
    print("\n6. Running path simulation...")
    paths = mc.run_path_simulation(trades, initial_capital=10000, n_paths=100)
    print(
        f"   Final equity range: ${paths['final_equity_range'][0]:.0f} - ${paths['final_equity_range'][1]:.0f}"
    )

    print("\n✅ Monte Carlo Analyzer test PASSED!")


def test_indicator_cache():
    """Test Indicator Cache."""
    print("\n" + "=" * 60)
    print("Testing Indicator Cache")
    print("=" * 60)

    cache = IndicatorCache(max_size=10)

    # Sample data
    data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

    # Sample compute function
    compute_calls = [0]

    def compute_sma(data, period=3):
        compute_calls[0] += 1
        return np.convolve(data, np.ones(period) / period, mode="valid")

    # First call - should compute
    result1 = cache.get("sma", data, compute_sma, period=3)
    print(f"\n1. First call: computed (calls={compute_calls[0]})")

    # Second call - should use cache
    result2 = cache.get("sma", data, compute_sma, period=3)
    print(f"2. Second call: cached (calls={compute_calls[0]})")

    # Different parameters - should compute
    result3 = cache.get("sma", data, compute_sma, period=2)
    print(f"3. Different params: computed (calls={compute_calls[0]})")

    # Verify results match
    assert np.allclose(result1, result2), "Cached result should match"
    assert compute_calls[0] == 2, "Should only compute twice"

    print(f"\n4. Cache stats: {cache.stats()}")

    print("\n✅ Indicator Cache test PASSED!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("  POSITION SIZING & MONTE CARLO TESTS")
    print("=" * 60)

    test_kelly_calculator()
    test_monte_carlo()
    test_indicator_cache()

    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
