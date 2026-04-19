"""
Optimization Scoring Functions.

Composite score calculation, multi-criteria ranking, GT-Score,
and Deflated Sharpe Ratio.
Extracted from optimizations.py for testability and reuse.
"""

from __future__ import annotations

import math


def _safe(v: object, default: float = 0.0) -> float:
    """Return default if v is None, NaN, or non-finite.

    Replaces the ``x or 0`` pattern which fails for NaN: float('nan') is
    truthy, so ``nan or 0`` returns nan instead of 0.
    """
    if v is None:
        return default
    try:
        f = float(v)  # type: ignore[arg-type]
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def calculate_composite_score(result: dict, metric: str, weights: dict | None = None) -> float:
    """
    Calculate composite score for a backtest result.

    Supports all 20 metrics from EvaluationCriteriaPanel:
    - Performance: total_return, cagr, sharpe_ratio, sortino_ratio, calmar_ratio
    - Risk: max_drawdown, avg_drawdown, volatility, var_95, risk_adjusted_return
    - Trade quality: win_rate, profit_factor, avg_win, avg_loss, expectancy, payoff_ratio
    - Activity: total_trades, trades_per_month, avg_trade_duration, avg_bars_in_trade

    Args:
        result: Dict with backtest metric values.
        metric: Name of the metric to optimize.
        weights: Optional dict of metric weights for composite scoring.

    Returns:
        Score value (higher = better for all metrics).

    Note:
        max_drawdown comes in PERCENT (17.29 = 17.29%).
    """
    total_return = _safe(result.get("total_return"))
    sharpe_ratio = _safe(result.get("sharpe_ratio"))
    net_profit = _safe(result.get("net_profit"))
    max_drawdown_pct = abs(_safe(result.get("max_drawdown")))
    max_drawdown = max_drawdown_pct / 100.0
    win_rate_pct = _safe(result.get("win_rate"))
    profit_factor = _safe(result.get("profit_factor"))  # 0 for losers, not 1
    profit_factor = min(profit_factor, 999.0)  # cap to avoid runaway scores from tiny loss baselines

    # Simple metrics (higher = better)
    if metric == "net_profit":
        return net_profit
    elif metric == "sharpe_ratio":
        return sharpe_ratio
    elif metric == "sortino_ratio":
        return _safe(result.get("sortino_ratio"))
    elif metric == "total_return":
        return total_return
    elif metric == "cagr":
        return _safe(result.get("cagr"))
    elif metric == "win_rate":
        return win_rate_pct
    elif metric == "profit_factor":
        return profit_factor
    elif metric == "expectancy":
        return _safe(result.get("expectancy"))
    elif metric == "recovery_factor":
        rf = _safe(result.get("recovery_factor"))
        return min(rf, 999.0) if rf != float("inf") else 999.0
    elif metric == "avg_win":
        return _safe(result.get("avg_win"))
    elif metric == "payoff_ratio":
        return _safe(result.get("payoff_ratio"))
    elif metric == "total_trades":
        return _safe(result.get("total_trades"))
    elif metric == "trades_per_month":
        return _safe(result.get("trades_per_month"))

    # Inverted metrics (lower = better, return negative for sorting)
    elif metric == "max_drawdown":
        return -max_drawdown_pct
    elif metric == "avg_drawdown":
        return -(abs(_safe(result.get("avg_drawdown"))))
    elif metric == "avg_loss":
        return -(abs(_safe(result.get("avg_loss"))))
    elif metric == "volatility":
        return -(abs(_safe(result.get("volatility"))))
    elif metric == "var_95":
        return -(abs(_safe(result.get("var_95"))))

    # Activity metrics (neutral - return raw value)
    elif metric == "avg_trade_duration":
        return _safe(result.get("avg_trade_duration")) or _safe(result.get("avg_bars_in_trade"))
    elif metric == "avg_bars_in_trade":
        return _safe(result.get("avg_bars_in_trade"))

    # Computed composite metrics
    elif metric == "calmar_ratio":
        if max_drawdown_pct > 1.0:
            return total_return / max_drawdown_pct
        return total_return * 10 if total_return > 0 else total_return
    elif metric == "risk_adjusted_return":
        drawdown_factor = 1 + max_drawdown
        return total_return / drawdown_factor

    # ──────────────────────────────────────────────────────────────────────────
    # pareto_balance: per-result proxy score for the Pareto-optimal NP↑ / DD↓
    # trade-off.  Uses a robust ratio: total_return% / (max_drawdown% + ε)
    # amplified by a log-trade bonus so thin 1-2 trade back-tests don't win.
    #
    # The *true* Pareto normalisation (across all candidates) is performed by
    # apply_pareto_scores() which is called by the optimizer after the full
    # grid is evaluated.  This per-result value is used only for early sorting
    # and streaming progress during the sweep.
    # ──────────────────────────────────────────────────────────────────────────
    elif metric == "pareto_balance":
        trades = int(result.get("total_trades", 0) or 0)
        dd_safe = max(max_drawdown_pct, 0.1)  # floor at 0.1% to avoid /0
        trade_bonus = math.log1p(max(trades, 1))
        raw = (total_return / dd_safe) * trade_bonus
        return min(raw, 1e6)  # cap at 1 M

    # P2-5: composite quality score (AI agent strategy selection)
    elif metric == "composite_quality":
        return composite_quality_score(result)

    # Default — net_profit
    return net_profit


def apply_pareto_scores(results: list[dict]) -> list[dict]:
    """
    Post-processing: assign a normalised Pareto-balance score to every result.

    Separates the Pareto trade-off between **Net Profit** (higher = better)
    and **Max Drawdown** (lower = better) without arbitrary hard thresholds.

    Algorithm
    ---------
    1. Collect ``total_return`` and ``max_drawdown`` across all candidates.
    2. Min–max normalise each to [0, 1].
    3. ``pareto_score = np_norm / (dd_norm + ε)`` — rewards high return
       relative to drawdown across the *entire candidate set*, not in
       absolute terms.
    4. Apply a log-trade bonus ``log(1 + trades)`` to penalise thin samples.
    5. Write the result back to ``result["score"]`` and
       ``result["pareto_score"]`` for display.

    The function mutates the list in-place and returns it.

    Args:
        results: List of result dicts (already contain ``total_return``,
                 ``max_drawdown``, ``total_trades``).

    Returns:
        Same list with ``score`` and ``pareto_score`` updated.
    """

    if not results:
        return results

    # Use actual total_return (not abs) so negative-return strategies always rank below
    # positive-return ones. Clamp negative returns to 0 for normalization purposes.
    raw_returns = [float(r.get("total_return", 0) or 0) for r in results]
    drawdowns = [abs(float(r.get("max_drawdown", 0) or 0)) for r in results]

    # For normalization, floor returns at 0 so losers never compete with winners
    norm_returns = [max(ret, 0.0) for ret in raw_returns]

    min_ret, max_ret = min(norm_returns), max(norm_returns)
    min_dd, max_dd = min(drawdowns), max(drawdowns)

    ret_range = max_ret - min_ret if max_ret > min_ret else 1.0
    dd_range = max_dd - min_dd if max_dd > min_dd else 1.0

    EPS = 1e-6

    for i, r in enumerate(results):
        np_norm = (norm_returns[i] - min_ret) / ret_range  # 0..1, higher=better
        # dd_norm: 0..1, higher means WORSE drawdown → invert
        dd_raw_norm = (drawdowns[i] - min_dd) / dd_range  # 0=best DD, 1=worst DD
        dd_penalty = dd_raw_norm + EPS  # avoid /0

        trades = int(r.get("total_trades", 0) or 0)
        trade_bonus = math.log1p(max(trades, 1))

        pareto = (np_norm / dd_penalty) * trade_bonus
        # Penalise losing strategies: negative total_return → always score 0 or below
        if raw_returns[i] < 0:
            pareto = -abs(pareto) - 1.0
        r["pareto_score"] = round(float(pareto), 6)
        r["score"] = r["pareto_score"]

    # Sort best first (modifies list order)
    results.sort(key=lambda x: x.get("pareto_score", 0), reverse=True)
    return results


def rank_by_multi_criteria(results: list[dict], selection_criteria: list[str]) -> list[dict]:
    """
    Rank results by multiple criteria using average rank method.

    For each criterion, assigns ranks (1=best). The overall score
    is the average rank across all criteria. Lower = better.

    Args:
        results: List of result dicts with metric values.
        selection_criteria: List of metric names to rank by.

    Returns:
        Sorted list (best first) with '_avg_rank' field added.
    """
    if not results or not selection_criteria:
        return results

    # Direction: True = higher is better, False = lower is better
    criteria_direction = {
        # Performance (higher = better)
        "net_profit": True,
        "total_return": True,
        "cagr": True,
        "sharpe_ratio": True,
        "sortino_ratio": True,
        "calmar_ratio": True,
        "risk_adjusted_return": True,
        "pareto_balance": True,  # normalised NP/DD ratio — higher = better
        "pareto_score": True,  # same as pareto_balance after apply_pareto_scores()
        # Risk (lower = better)
        "max_drawdown": False,
        "avg_drawdown": False,
        "volatility": False,
        "var_95": False,
        # Trade quality
        "win_rate": True,
        "profit_factor": True,
        "avg_win": True,
        "avg_loss": False,
        "expectancy": True,
        "payoff_ratio": True,
        "recovery_factor": True,
        # Activity
        "total_trades": True,
        "trades_per_month": True,
        "avg_trade_duration": True,
        "avg_bars_in_trade": True,
    }

    n = len(results)

    # Calculate ranks for each criterion
    for criterion in selection_criteria:
        if criterion not in criteria_direction:
            continue

        higher_is_better = criteria_direction[criterion]

        # For max_drawdown, use absolute value for ranking
        def get_value(r, crit=criterion):
            if crit == "max_drawdown":
                return abs(r.get(crit, 0) or 0)
            return r.get(crit, 0) or 0

        # Sort indices by criterion value
        sorted_indices = sorted(
            range(n),
            key=lambda i: get_value(results[i]),
            reverse=higher_is_better,
        )

        # Assign ranks (1-based)
        for rank, idx in enumerate(sorted_indices, 1):
            if "_ranks" not in results[idx]:
                results[idx]["_ranks"] = {}
            results[idx]["_ranks"][criterion] = rank

    # Calculate average rank
    for i, r in enumerate(results):
        ranks = r.get("_ranks", {})
        if ranks:
            r["_avg_rank"] = sum(ranks.values()) / len(ranks)
        else:
            r["_avg_rank"] = float("inf")
        # Store original index for stable tie-breaking
        r["_orig_idx"] = i

    # Sort by average rank (lower = better), tie-break by total_return desc then original index
    results.sort(
        key=lambda x: (
            x.get("_avg_rank", float("inf")),
            -(x.get("total_return", 0) or 0),
            x.get("_orig_idx", 0),
        )
    )

    # Set score as negative average rank (for compatibility with existing sort)
    for r in results:
        r["score"] = -r.get("_avg_rank", float("inf"))

    # Cleanup temp fields
    for r in results:
        r.pop("_ranks", None)
        r.pop("_avg_rank", None)
        r.pop("_orig_idx", None)

    return results


def composite_quality_score(result: dict) -> float:
    """
    P2-5: Composite quality score for AI agent strategy selection.

    Formula::

        score = Sharpe × Sortino × log(1 + trade_count) / (1 + max_drawdown_fraction)

    This balances risk-adjusted return (Sharpe×Sortino) against trade activity
    (log term prevents rewarding thin back-tests with 1-2 lucky trades) and
    drawdown penalty.

    Rules:
    - Returns 0.0 when Sharpe or Sortino is non-positive (unprofitable strategies score 0)
    - max_drawdown expected as PERCENT (e.g. 17.5 = 17.5%); converted to fraction internally
    - Capped at 1000.0 to prevent extreme outliers skewing comparisons

    Args:
        result: Dict with backtest metric values (same format as MetricsCalculator output).

    Returns:
        Float score ≥ 0.0.  Higher = better.

    Example::

        >>> composite_quality_score({"sharpe_ratio": 1.2, "sortino_ratio": 1.8,
        ...                          "total_trades": 50, "max_drawdown": 15.0})
        # ≈ 1.2 × 1.8 × log(51) / 1.15 ≈ 6.84
    """

    sharpe = result.get("sharpe_ratio", 0.0) or 0.0
    sortino = result.get("sortino_ratio", 0.0) or 0.0
    trades = int(result.get("total_trades", 0) or 0)
    max_dd_pct = abs(result.get("max_drawdown", 0.0) or 0.0)

    # Guard against NaN/inf from upstream calculation errors
    if not math.isfinite(sharpe) or not math.isfinite(sortino) or not math.isfinite(max_dd_pct):
        return 0.0

    if sharpe <= 0 or sortino <= 0:
        return 0.0

    max_dd_frac = max_dd_pct / 100.0
    score = sharpe * sortino * math.log1p(trades) / (1.0 + max_dd_frac)
    return min(float(score), 1000.0)


def apply_custom_sort_order(results: list[dict], sort_order: list[dict]) -> list[dict]:
    """
    Apply custom multi-level sort from frontend EvaluationCriteriaPanel.

    Args:
        results: List of result dicts.
        sort_order: List of {"metric": str, "direction": "asc"|"desc"}.

    Returns:
        Sorted list of results.
    """
    if not results or not sort_order:
        return results

    # Build composite sort key
    def sort_key(item):
        keys = []
        for so in sort_order:
            metric = so.get("metric", "")
            direction = so.get("direction", "desc")
            value = item.get(metric, 0) or 0
            # Negate for descending so sorted() works correctly
            keys.append(-value if direction == "desc" else value)
        return tuple(keys)

    return sorted(results, key=sort_key)


# =============================================================================
# P1-1: GT-Score (Generalization-Testing Score)
# =============================================================================


def calculate_gt_score(
    base_params: dict,
    param_specs: list[dict],
    run_backtest_fn,
    n_neighbors: int = 20,
    epsilon: float = 0.05,
    seed: int = 42,
) -> dict:
    """
    Calculate GT-Score (Generalization-Testing Score) for a parameter set.

    Measures robustness of the found optimum by evaluating N perturbed
    parameter combinations in the ±epsilon neighborhood.

    High GT-Score = strategy sits on a plateau (robust, generalizable).
    Low GT-Score  = strategy is a sharp peak (overfitted, fragile).

    Args:
        base_params: Optimal parameter dict {"param_path": value, ...}.
        param_specs: Parameter specs with type/low/high/step info.
        run_backtest_fn: Callable(params_dict) -> score_float | None.
        n_neighbors: Number of perturbed neighbors to evaluate (default 20).
        epsilon: Perturbation fraction of param range (default 0.05 = ±5%).
        seed: RNG seed for reproducibility.

    Returns:
        Dict with:
            gt_score: float — mean/std ratio (higher = more robust)
            gt_mean: float — mean neighbor score
            gt_std: float — std of neighbor scores
            gt_n_valid: int — number of neighbors with valid results
    """
    import random

    import numpy as np

    rng = random.Random(seed)

    # Build spec lookup by param_path
    spec_map = {s["param_path"]: s for s in param_specs}

    neighbor_scores: list[float] = []

    for _ in range(n_neighbors):
        perturbed = {}
        for path, val in base_params.items():
            spec = spec_map.get(path)
            if spec is None:
                perturbed[path] = val
                continue

            param_range = spec["high"] - spec["low"]
            delta = param_range * epsilon

            if spec["type"] == "int":
                max_step = max(1, int(delta))
                offset = rng.randint(-max_step, max_step)
                new_val = int(val) + offset
                new_val = max(spec["low"], min(spec["high"], new_val))
                perturbed[path] = int(new_val)
            else:
                offset = rng.uniform(-delta, delta)
                new_val = float(val) + offset
                new_val = max(spec["low"], min(spec["high"], new_val))
                step = spec.get("step", 0.01)
                n_decimals = max(0, -math.floor(math.log10(step)) if step < 1 else 0)
                perturbed[path] = round(new_val, n_decimals)

        score = run_backtest_fn(perturbed)
        if score is not None:
            neighbor_scores.append(score)

    if len(neighbor_scores) < 2:
        return {"gt_score": 0.0, "gt_mean": 0.0, "gt_std": 0.0, "gt_n_valid": len(neighbor_scores)}

    gt_mean = float(np.mean(neighbor_scores))
    gt_std = float(np.std(neighbor_scores))
    gt_score = gt_mean / (gt_std + 1e-8)

    return {
        "gt_score": round(gt_score, 4),
        "gt_mean": round(gt_mean, 6),
        "gt_std": round(gt_std, 6),
        "gt_n_valid": len(neighbor_scores),
    }


# =============================================================================
# P2-3: Deflated Sharpe Ratio (DSR) — Bailey & López de Prado (2014)
# =============================================================================


def deflated_sharpe_ratio(
    sharpe_ratio: float,
    n_trials: int,
    n_observations: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """
    Calculate Deflated Sharpe Ratio (DSR) — Bailey & López de Prado (2014).

    Corrects the best observed Sharpe Ratio for selection bias from
    evaluating multiple parameter combinations. DSR < 0 means the
    strategy has no statistical edge after accounting for trial count.

    Args:
        sharpe_ratio: Best observed Sharpe Ratio from optimization.
        n_trials: Number of parameter combinations evaluated (strategies tested).
        n_observations: Number of bars (time periods) in the backtest.
        skewness: Skewness of returns (default 0 = normal).
        kurtosis: Kurtosis of returns (default 3 = normal).

    Returns:
        DSR: float in [0, 1] (probability). DSR > 0.5 → statistically significant edge.
    """
    from scipy import stats as _stats

    if n_observations < 10 or n_trials < 1:
        return float("nan")

    gamma_em = 0.5772156649  # Euler-Mascheroni constant

    # Expected maximum Sharpe from N independent trials (Extreme Value Theory)
    z1 = _stats.norm.ppf(1 - 1.0 / max(n_trials, 2))
    z2 = _stats.norm.ppf(1 - 1.0 / max(n_trials * math.e, 2))
    expected_max = (1 - gamma_em) * z1 + gamma_em * z2

    # Standard deviation of SR estimator
    sr_std = math.sqrt(
        (1 - skewness * sharpe_ratio + (kurtosis - 1) / 4.0 * sharpe_ratio**2) / max(n_observations - 1, 1)
    )

    if sr_std < 1e-12:
        return float("nan")

    # DSR: probability that SR > expected maximum from random search
    dsr_z = (sharpe_ratio - expected_max) / sr_std
    dsr = float(_stats.norm.cdf(dsr_z))

    return round(dsr, 4)
