"""
Anti-overfit guard rails for backtest results.

Catches common Optuna "phantom optima" — configurations that score high in
sample but are statistically meaningless or pathological. These are checked
**after** :func:`scoring.calculate_composite_score` and BEFORE the score is
returned to Optuna, so the surrogate model never sees fantasy peaks.

The guards are configurable via ``config_params``; a missing key disables
that specific guard. All thresholds default to lenient values so the module
is safe to enable globally without changing existing behaviour.

Returned value semantics
------------------------
:func:`evaluate_overfit_guards` returns a :class:`GuardResult`:

* ``passed=True`` → safe to use original score.
* ``passed=False`` → caller should substitute a worst-case score (typically
  ``-1e6`` for maximisation) so Optuna marks the trial as unattractive
  without raising :class:`optuna.TrialPruned` (which would prevent the
  surrogate model from learning the *boundary* of feasibility).

The module deliberately has **no Optuna dependency** — it operates on plain
backtest result dicts and can be unit-tested without a study.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GuardThresholds:
    """Configuration for :func:`evaluate_overfit_guards`.

    All thresholds are inclusive — e.g. ``min_trades=30`` rejects 29 trades.
    """

    #: Minimum number of trades required for statistical significance.
    #: Floor of 30 follows the central-limit-theorem rule of thumb.
    min_trades: int = 30

    #: Minimum trades per 1000 bars (alternative to absolute floor).
    #: 2.0 means at least 2 trades per 1000 candles. Set to 0 to disable.
    min_trades_per_1000_bars: float = 2.0

    #: Reject if drawdown exceeds this percentage (0–100).
    #: 50% is generous; production strategies usually demand ≤ 25-30%.
    max_drawdown_pct: float = 50.0

    #: Sharpe-ratio improvement multiplier vs a buy-and-hold reference.
    #: 1.2 means strategy must outperform B&H Sharpe by at least 20%.
    #: Set to 0 to disable (no B&H comparison).
    min_sharpe_vs_buyhold: float = 1.2

    #: Reject if longest losing streak exceeds this. 0 disables.
    max_consecutive_losses: int = 10

    #: Reject if profit factor is below this. 1.0 = breakeven.
    min_profit_factor: float = 1.0

    #: If True, reject results where ALL profit comes from a single trade
    #: (>80% of net profit from one trade — classic curve-fit signature).
    reject_single_trade_winner: bool = True


@dataclass(frozen=True)
class GuardResult:
    """Outcome of running anti-overfit guards on a single backtest result."""

    passed: bool
    failed_guards: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def reason(self) -> str:
        """Human-readable summary suitable for logging."""
        if self.passed:
            return "ok"
        return ", ".join(self.failed_guards) or "rejected"


def _safe_float(v: Any, default: float = 0.0) -> float:
    """NaN/None-safe float coercion (mirrors scoring._safe)."""
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def thresholds_from_config(config_params: dict[str, Any]) -> GuardThresholds:
    """Build :class:`GuardThresholds` from a free-form ``config_params`` dict.

    Reuses keys that already exist in the optimizer config (``min_trades``,
    ``max_drawdown_limit``, ``min_profit_factor``) so existing UI controls
    automatically drive the guards. Unknown keys fall back to the defaults
    in :class:`GuardThresholds`.
    """
    defaults = GuardThresholds()

    # max_drawdown_limit may arrive as a fraction (0.5) or percentage (50);
    # auto-detect: values ≤ 1.0 are treated as fractions.
    raw_dd = config_params.get("max_drawdown_limit")
    if raw_dd is None:
        max_dd_pct = defaults.max_drawdown_pct
    else:
        try:
            raw_dd_f = float(raw_dd)
            max_dd_pct = raw_dd_f * 100.0 if raw_dd_f <= 1.0 else raw_dd_f
        except (TypeError, ValueError):
            max_dd_pct = defaults.max_drawdown_pct

    return GuardThresholds(
        min_trades=int(config_params.get("min_trades") or defaults.min_trades),
        min_trades_per_1000_bars=float(
            config_params.get("min_trades_per_1000_bars", defaults.min_trades_per_1000_bars)
        ),
        max_drawdown_pct=max_dd_pct,
        min_sharpe_vs_buyhold=float(config_params.get("min_sharpe_vs_buyhold", defaults.min_sharpe_vs_buyhold)),
        max_consecutive_losses=int(config_params.get("max_consecutive_losses", defaults.max_consecutive_losses)),
        min_profit_factor=float(config_params.get("min_profit_factor") or defaults.min_profit_factor),
        reject_single_trade_winner=bool(
            config_params.get("reject_single_trade_winner", defaults.reject_single_trade_winner)
        ),
    )


def evaluate_overfit_guards(
    result: dict[str, Any] | None,
    thresholds: GuardThresholds | None = None,
    *,
    n_bars: int | None = None,
) -> GuardResult:
    """Run all configured guards against a backtest result.

    Args:
        result: Backtest output dict (the same dict consumed by
            :func:`scoring.calculate_composite_score`). ``None`` means the
            backtest itself failed and the trial is automatically rejected.
        thresholds: Guard thresholds (defaults if not given).
        n_bars: Total bar count of the backtest, used by the
            ``min_trades_per_1000_bars`` rule. If omitted, that rule is
            skipped.

    Returns:
        :class:`GuardResult` describing pass/fail and the offending guards.
    """
    if result is None:
        return GuardResult(passed=False, failed_guards=("backtest_failed",))

    th = thresholds or GuardThresholds()
    failed: list[str] = []
    notes: list[str] = []

    total_trades = int(_safe_float(result.get("total_trades")))
    if th.min_trades > 0 and total_trades < th.min_trades:
        failed.append(f"min_trades({total_trades}<{th.min_trades})")

    if th.min_trades_per_1000_bars > 0 and n_bars and n_bars > 0:
        density = total_trades * 1000.0 / n_bars
        if density < th.min_trades_per_1000_bars:
            failed.append(f"trade_density({density:.2f}<{th.min_trades_per_1000_bars:.2f}/1k)")

    if th.max_drawdown_pct > 0:
        dd = abs(_safe_float(result.get("max_drawdown")))
        if dd > th.max_drawdown_pct:
            failed.append(f"max_dd({dd:.1f}>{th.max_drawdown_pct:.1f}%)")

    if th.min_profit_factor > 0:
        pf = _safe_float(result.get("profit_factor"))
        # PF == 0 means no losses *or* no trades — only flag if we have trades.
        if total_trades > 0 and pf < th.min_profit_factor:
            failed.append(f"profit_factor({pf:.2f}<{th.min_profit_factor:.2f})")

    if th.min_sharpe_vs_buyhold > 0:
        strat_sh = _safe_float(result.get("sharpe_ratio"))
        bh_sh = _safe_float(result.get("buy_hold_sharpe"))
        # Only check if both numbers are present and B&H Sharpe is positive
        # (negative B&H Sharpe means any positive strategy wins trivially).
        if bh_sh > 0.1 and strat_sh < bh_sh * th.min_sharpe_vs_buyhold:
            failed.append(f"sharpe_vs_buyhold({strat_sh:.2f}<{bh_sh:.2f}×{th.min_sharpe_vs_buyhold})")

    if th.max_consecutive_losses > 0:
        streak = int(_safe_float(result.get("max_consecutive_losses")))
        if streak > th.max_consecutive_losses:
            failed.append(f"loss_streak({streak}>{th.max_consecutive_losses})")

    if th.reject_single_trade_winner and total_trades >= 2:
        # Heuristic: classic curve-fit signature — ≥80% of net profit comes
        # from one outsized trade. Use largest_win / net_profit if present.
        net = _safe_float(result.get("net_profit"))
        biggest = _safe_float(result.get("largest_win"))
        if net > 0 and biggest > 0 and biggest / net > 0.80:
            failed.append(f"single_trade_dominates({biggest / net:.0%}>80%)")

    notes.append(f"trades={total_trades}")
    return GuardResult(
        passed=not failed,
        failed_guards=tuple(failed),
        notes=tuple(notes),
    )
