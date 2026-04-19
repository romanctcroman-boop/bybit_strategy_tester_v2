"""Tests for backend.optimization.overfit_guards."""

from __future__ import annotations

from backend.optimization.overfit_guards import (
    GuardThresholds,
    evaluate_overfit_guards,
    thresholds_from_config,
)


class TestEvaluateOverfitGuards:
    def test_none_result_fails(self) -> None:
        out = evaluate_overfit_guards(None)
        assert not out.passed
        assert "backtest_failed" in out.failed_guards

    def test_passes_clean_result(self) -> None:
        result = {
            "total_trades": 120,
            "max_drawdown": 12.5,
            "profit_factor": 1.8,
            "sharpe_ratio": 1.6,
            "buy_hold_sharpe": 1.0,
            "max_consecutive_losses": 4,
            "net_profit": 5000.0,
            "largest_win": 800.0,
        }
        out = evaluate_overfit_guards(result, n_bars=20_000)
        assert out.passed, out.failed_guards
        assert out.reason == "ok"

    def test_min_trades_violation(self) -> None:
        result = {"total_trades": 5, "max_drawdown": 5, "profit_factor": 2.0}
        out = evaluate_overfit_guards(result)
        assert not out.passed
        assert any("min_trades" in g for g in out.failed_guards)

    def test_drawdown_violation(self) -> None:
        result = {
            "total_trades": 100,
            "max_drawdown": 75.0,
            "profit_factor": 1.5,
        }
        out = evaluate_overfit_guards(result)
        assert not out.passed
        assert any("max_dd" in g for g in out.failed_guards)

    def test_drawdown_negative_value_treated_as_absolute(self) -> None:
        result = {"total_trades": 100, "max_drawdown": -75.0, "profit_factor": 1.5}
        out = evaluate_overfit_guards(result)
        assert any("max_dd" in g for g in out.failed_guards)

    def test_profit_factor_violation(self) -> None:
        result = {"total_trades": 50, "max_drawdown": 10, "profit_factor": 0.7}
        out = evaluate_overfit_guards(result)
        assert any("profit_factor" in g for g in out.failed_guards)

    def test_pf_zero_with_zero_trades_not_flagged(self) -> None:
        # No trades at all → only min_trades should fire, not PF
        result = {"total_trades": 0, "max_drawdown": 0, "profit_factor": 0}
        out = evaluate_overfit_guards(result)
        assert any("min_trades" in g for g in out.failed_guards)
        assert not any("profit_factor" in g for g in out.failed_guards)

    def test_sharpe_vs_buyhold_violation(self) -> None:
        result = {
            "total_trades": 100,
            "max_drawdown": 10,
            "profit_factor": 1.4,
            "sharpe_ratio": 0.5,
            "buy_hold_sharpe": 1.0,
            "max_consecutive_losses": 3,
        }
        out = evaluate_overfit_guards(result)
        assert any("sharpe_vs_buyhold" in g for g in out.failed_guards)

    def test_sharpe_check_skipped_when_buyhold_negative(self) -> None:
        result = {
            "total_trades": 100,
            "max_drawdown": 10,
            "profit_factor": 1.4,
            "sharpe_ratio": 0.05,  # tiny but positive
            "buy_hold_sharpe": -0.5,  # negative → check disabled
            "max_consecutive_losses": 3,
        }
        out = evaluate_overfit_guards(result)
        assert not any("sharpe_vs_buyhold" in g for g in out.failed_guards)

    def test_consecutive_losses_violation(self) -> None:
        result = {
            "total_trades": 100,
            "max_drawdown": 10,
            "profit_factor": 1.4,
            "max_consecutive_losses": 15,
        }
        out = evaluate_overfit_guards(result)
        assert any("loss_streak" in g for g in out.failed_guards)

    def test_single_trade_dominance_violation(self) -> None:
        result = {
            "total_trades": 50,
            "max_drawdown": 10,
            "profit_factor": 1.4,
            "max_consecutive_losses": 3,
            "net_profit": 1000.0,
            "largest_win": 950.0,  # 95% of total → curve-fit signature
        }
        out = evaluate_overfit_guards(result)
        assert any("single_trade_dominates" in g for g in out.failed_guards)

    def test_trade_density_violation(self) -> None:
        # 50 trades over 100k bars → density 0.5/1k → below default 2.0
        result = {
            "total_trades": 50,
            "max_drawdown": 10,
            "profit_factor": 1.5,
            "max_consecutive_losses": 3,
        }
        out = evaluate_overfit_guards(result, n_bars=100_000)
        assert any("trade_density" in g for g in out.failed_guards)

    def test_nan_values_handled(self) -> None:
        result = {
            "total_trades": 100,
            "max_drawdown": float("nan"),
            "profit_factor": float("inf"),
            "sharpe_ratio": float("nan"),
            "buy_hold_sharpe": 1.0,
            "max_consecutive_losses": 3,
        }
        # Should not raise; NaN coerced to 0 → no false-positive on dd
        out = evaluate_overfit_guards(result)
        assert isinstance(out.passed, bool)


class TestThresholdsFromConfig:
    def test_empty_config_returns_defaults(self) -> None:
        t = thresholds_from_config({})
        assert t == GuardThresholds()

    def test_picks_up_existing_keys(self) -> None:
        t = thresholds_from_config(
            {
                "min_trades": 50,
                "max_drawdown_limit": 0.30,  # 30 % as fraction
                "min_profit_factor": 1.5,
            }
        )
        assert t.min_trades == 50
        assert t.max_drawdown_pct == 30.0  # converted from 0.30
        assert t.min_profit_factor == 1.5

    def test_drawdown_passed_as_percent(self) -> None:
        # Value > 1 → already percent
        t = thresholds_from_config({"max_drawdown_limit": 25})
        assert t.max_drawdown_pct == 25.0

    def test_extra_keys_via_explicit_names(self) -> None:
        t = thresholds_from_config(
            {
                "min_trades_per_1000_bars": 5.0,
                "max_consecutive_losses": 6,
                "min_sharpe_vs_buyhold": 1.5,
                "reject_single_trade_winner": False,
            }
        )
        assert t.min_trades_per_1000_bars == 5.0
        assert t.max_consecutive_losses == 6
        assert t.min_sharpe_vs_buyhold == 1.5
        assert t.reject_single_trade_winner is False
