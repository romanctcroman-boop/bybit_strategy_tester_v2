"""
Tests for portfolio allocation methods (MIN_VARIANCE, MAX_SHARPE, etc.)
and multi-symbol equity aggregation.
"""

import numpy as np

from backend.services.advanced_backtesting.portfolio import (
    AllocationMethod,
    AssetAllocation,
    PortfolioBacktester,
    aggregate_multi_symbol_equity,
    run_portfolio_backtest,
)


def _make_candles(n: int, base: float, drift: float, vol: float) -> list[dict]:
    """Generate candle list with returns."""
    np.random.seed(42)
    closes = [base]
    for _ in range(n - 1):
        ret = drift + np.random.normal(0, vol)
        closes.append(closes[-1] * (1 + ret))
    return [{"close": c} for c in closes]


def test_equal_weight_allocation():
    """Equal weight allocation."""
    data = {
        "A": _make_candles(100, 100, 0.001, 0.02),
        "B": _make_candles(100, 50, 0.0005, 0.03),
        "C": _make_candles(100, 20, -0.0002, 0.015),
    }
    r = run_portfolio_backtest(data, "equal_weight", "monthly", 10000)
    assert r["status"] == "completed"
    assert "performance" in r
    weights = r["allocation"]["final"]
    assert len(weights) == 3
    for w in weights.values():
        assert 0.2 <= w <= 0.5  # ~1/3 each, allow rebalance drift


def test_risk_parity_allocation():
    """Risk parity weights by inverse volatility."""
    data = {
        "low_vol": _make_candles(100, 100, 0.001, 0.01),
        "high_vol": _make_candles(100, 100, 0.001, 0.05),
    }
    r = run_portfolio_backtest(data, "risk_parity", "monthly", 10000)
    assert r["status"] == "completed"
    # low_vol should get higher weight (inverse vol)
    weights = r["allocation"]["final"]
    assert weights.get("low_vol", 0) > weights.get("high_vol", 0)


def test_min_variance_allocation():
    """Min-variance portfolio (requires scipy)."""
    data = {
        "A": _make_candles(100, 100, 0.001, 0.02),
        "B": _make_candles(100, 50, 0.0005, 0.03),
    }
    r = run_portfolio_backtest(data, "min_variance", "monthly", 10000)
    assert r["status"] == "completed"
    weights = r["allocation"]["final"]
    assert abs(sum(weights.values()) - 1.0) < 0.01
    assert all(0 <= w <= 1 for w in weights.values())


def test_max_sharpe_allocation():
    """Max-Sharpe portfolio (requires scipy)."""
    data = {
        "A": _make_candles(100, 100, 0.002, 0.02),
        "B": _make_candles(100, 50, 0.0005, 0.03),
    }
    r = run_portfolio_backtest(data, "max_sharpe", "monthly", 10000)
    assert r["status"] == "completed"
    weights = r["allocation"]["final"]
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_cvxportfolio_allocation():
    """Cvxportfolio allocation (cvxpy or scipy fallback)."""
    data = {
        "A": _make_candles(100, 100, 0.002, 0.02),
        "B": _make_candles(100, 50, 0.0005, 0.03),
    }
    r = run_portfolio_backtest(data, "cvxportfolio", "monthly", 10000)
    assert r["status"] == "completed"
    weights = r["allocation"]["final"]
    assert abs(sum(weights.values()) - 1.0) < 0.01
    assert all(0 <= w <= 1 for w in weights.values())


def test_correlation_analysis():
    """Correlation matrix and rolling correlations."""
    data = {
        "A": _make_candles(100, 100, 0.001, 0.02),
        "B": _make_candles(100, 50, 0.001, 0.02),  # correlated
    }
    bt = PortfolioBacktester(["A", "B"], 10000)
    alloc = AssetAllocation(method=AllocationMethod.EQUAL_WEIGHT)
    r = bt.run(data, alloc)
    assert r["status"] == "completed"
    corr = r["correlation"]
    assert "correlation_matrix" in corr
    assert "A" in corr["correlation_matrix"]
    assert corr["correlation_matrix"]["A"]["B"] == corr["correlation_matrix"]["B"]["A"]


def test_aggregate_multi_symbol_equity():
    """Aggregate equity curves with different lengths."""
    curves = {
        "A": [1000.0, 1010.0, 1020.0],
        "B": [500.0, 505.0],
        "C": [200.0],
    }
    agg = aggregate_multi_symbol_equity(curves)
    assert len(agg) == 3
    assert agg[0] == 1700.0  # 1000 + 500 + 200
    assert agg[1] == 1715.0  # 1010 + 505 + 200 (C uses last known)
    assert agg[2] == 1725.0  # 1020 + 505(B last) + 200(C last)


def test_aggregate_empty():
    """Empty equity curves."""
    assert aggregate_multi_symbol_equity({}) == []


def test_diversification_ratio_present():
    """Diversification ratio is computed for multi-asset."""
    data = {
        "A": _make_candles(100, 100, 0.001, 0.02),
        "B": _make_candles(100, 50, 0.0005, 0.03),
    }
    r = run_portfolio_backtest(data, "equal_weight", "monthly", 10000)
    assert "portfolio" in r["performance"]
    assert "diversification_ratio" in r["performance"]["portfolio"]


def test_portfolio_api_endpoint():
    """API /api/v1/advanced-backtest/portfolio accepts all allocation methods."""
    from fastapi.testclient import TestClient

    from backend.api.app import app

    client = TestClient(app)
    asset_data = {
        "BTCUSDT": _make_candles(50, 50000, 0.001, 0.02),
        "ETHUSDT": _make_candles(50, 3000, 0.0005, 0.03),
    }
    payload = {
        "asset_data": asset_data,
        "allocation_method": "min_variance",
        "rebalance_frequency": "monthly",
        "initial_capital": 10000,
        "commission": 0.0007,
    }
    resp = client.post("/api/v1/advanced-backtest/portfolio", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert "performance" in data
    assert "correlation" in data
    assert "equity_curve" in data
