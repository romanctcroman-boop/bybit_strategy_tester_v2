"""
Test Kelly Criterion and Monte Carlo API endpoints.

Tests the new position sizing API integration.
"""

import requests

BASE_URL = "http://localhost:8000/api/v1/monte-carlo"


def test_quick_kelly():
    """Test quick Kelly calculation from stats."""
    print("=" * 70)
    print("Test 1: Quick Kelly from Stats")
    print("=" * 70)

    response = requests.get(
        f"{BASE_URL}/quick-kelly",
        params={
            "win_rate": 0.55,
            "avg_win": 150,
            "avg_loss": 100,
            "kelly_fraction": 0.5,
        },
    )

    if response.status_code == 200:
        data = response.json()
        print(f"  Win Rate: {data['win_rate']:.1%}")
        print(f"  Win/Loss Ratio: {data['win_loss_ratio']:.2f}")
        print(f"  Full Kelly: {data['full_kelly']:.2%}")
        print(f"  Half Kelly: {data['half_kelly']:.2%}")
        print(f"  Adjusted Kelly: {data['adjusted_kelly']:.2%}")
        print(f"  Edge: {data['edge']:.4f}")
        print(f"  Recommendation: {data['recommendation']}")
        print("\n✅ Quick Kelly test PASSED")
        return True
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")
        return False


def test_kelly_with_trades():
    """Test Kelly calculation with trade data."""
    print("\n" + "=" * 70)
    print("Test 2: Kelly with Trade Data")
    print("=" * 70)

    # Generate sample trades
    trades = []
    import random

    random.seed(42)
    for i in range(100):
        if random.random() < 0.55:  # 55% win rate
            pnl = random.uniform(100, 200)
        else:
            pnl = random.uniform(-150, -50)

        trades.append(
            {
                "pnl": pnl,
                "entry_price": 50000,
                "exit_price": 50000 + (pnl / 0.1),
                "size": 0.1,
            }
        )

    response = requests.post(
        f"{BASE_URL}/kelly",
        json={
            "trades": trades,
            "taker_fee": 0.0007,
            "min_trades": 50,
            "lookback_trades": 100,
            "use_exponential_weights": True,
            "decay_factor": 0.95,
            "kelly_fraction": 0.5,
        },
    )

    if response.status_code == 200:
        data = response.json()
        print(f"  Trades Analyzed: {data['trades_analyzed']}")
        print(f"  Sufficient Data: {data['sufficient_data']}")
        print(f"  Win Rate: {data.get('win_rate', 0):.1%}")
        print(f"  Win/Loss Ratio: {data.get('win_loss_ratio', 0):.2f}")
        print(f"  Full Kelly: {data.get('full_kelly', 0):.2%}")
        print(f"  Half Kelly: {data.get('half_kelly', 0):.2%}")
        print(f"  Kelly Fraction: {data.get('kelly_fraction', 0):.2%}")
        print(f"  Recommendation: {data['recommendation']}")
        print("\n✅ Kelly with trades test PASSED")
        return True
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")
        return False


def test_enhanced_monte_carlo():
    """Test enhanced Monte Carlo simulation."""
    print("\n" + "=" * 70)
    print("Test 3: Enhanced Monte Carlo Simulation")
    print("=" * 70)

    # Generate sample trades
    trades = []
    import random

    random.seed(42)
    for i in range(50):
        if random.random() < 0.55:
            pnl = random.uniform(100, 200)
        else:
            pnl = random.uniform(-150, -50)

        trades.append(
            {
                "pnl": pnl,
                "entry_price": 50000,
                "exit_price": 50000 + (pnl / 0.1),
                "size": 0.1,
            }
        )

    response = requests.post(
        f"{BASE_URL}/enhanced-analysis",
        json={
            "trades": trades,
            "initial_capital": 10000,
            "n_simulations": 1000,
            "target_return": 0.5,
            "max_drawdown_limit": 0.3,
            "confidence_level": 0.95,
        },
    )

    if response.status_code == 200:
        data = response.json()
        print(f"  Simulations: {data['n_simulations']}")
        print(f"  Trades: {data['trades_count']}")
        print()
        print("  Return Statistics:")
        print(f"    Mean: {data['return_mean']:.1%}")
        print(f"    Median: {data['return_median']:.1%}")
        print(
            f"    95% CI: [{data['return_ci_lower']:.1%}, {data['return_ci_upper']:.1%}]"
        )
        print()
        print("  Drawdown Statistics:")
        print(f"    Mean Max DD: {data['max_drawdown_mean']:.1%}")
        print(f"    Worst DD: {data['max_drawdown_worst']:.1%}")
        print()
        print("  Sharpe Statistics:")
        print(f"    Mean Sharpe: {data['sharpe_mean']:.2f}")
        print(
            f"    95% CI: [{data['sharpe_ci_lower']:.2f}, {data['sharpe_ci_upper']:.2f}]"
        )
        print()
        print("  Probabilities:")
        print(f"    P(Profit): {data['probability_of_profit']:.1%}")
        print(f"    P(Target 50%): {data['probability_of_target']:.1%}")
        print(f"    Risk of Ruin (30% DD): {data['risk_of_ruin']:.1%}")
        print()
        print("  Risk Metrics:")
        print(f"    VaR (95%): {data['var_95']:.1%}")
        print(f"    CVaR (95%): {data['cvar_95']:.1%}")
        print("\n✅ Enhanced Monte Carlo test PASSED")
        return True
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("  KELLY CRITERION & MONTE CARLO API TESTS")
    print("=" * 70)

    results = []
    results.append(("Quick Kelly", test_quick_kelly()))
    results.append(("Kelly with Trades", test_kelly_with_trades()))
    results.append(("Enhanced Monte Carlo", test_enhanced_monte_carlo()))

    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n" + "=" * 70)
        print("  ALL TESTS PASSED!")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("  SOME TESTS FAILED")
        print("=" * 70)


if __name__ == "__main__":
    main()
