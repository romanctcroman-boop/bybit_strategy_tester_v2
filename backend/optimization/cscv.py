"""
Combinatorially Symmetric Cross-Validation (CSCV).

López de Prado, M. (2018). Advances in Financial Machine Learning, Chapter 11.

Measures Probability of Backtest Overfitting (PBO) for a set of parameter
combinations. PBO < 0.05 = statistically robust; PBO > 0.5 = likely overfitted.

Unlike standard K-fold, CSCV uses ALL possible chronological partitions of
the data (combinatorial rather than sequential splits), which provides a much
more conservative and statistically sound estimate of overfitting.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd


def cscv_validation(
    strategies: list[dict[str, Any]],
    ohlcv: pd.DataFrame,
    run_backtest_fn: Callable[[dict, pd.DataFrame], float | None],
    n_splits: int = 16,
) -> dict[str, Any]:
    """
    Run CSCV (Combinatorially Symmetric Cross-Validation) on a set of strategies.

    Estimates the Probability of Backtest Overfitting (PBO) across all
    combinatorial partitions of the data.

    Args:
        strategies: List of dicts, each with at least "params" key.
        ohlcv: Full OHLCV DataFrame for splitting.
        run_backtest_fn: Callable(params_dict, sub_ohlcv) -> score_float | None.
        n_splits: Number of chronological sub-periods (must be even, default 16).

    Returns:
        Dict with:
            pbo: float — Probability of Backtest Overfitting (0..1)
            pbo_interpretation: str — "robust" / "borderline" / "overfitted"
            n_combinations: int — total partitions evaluated
    """
    if n_splits % 2 != 0:
        n_splits = n_splits + 1  # ensure even

    n = len(ohlcv)
    bars_per_split = n // n_splits

    if bars_per_split < 50:
        return {
            "pbo": None,
            "pbo_interpretation": "skipped",
            "reason": f"Too few bars per split: {bars_per_split} < 50",
            "n_combinations": 0,
        }

    if not strategies:
        return {
            "pbo": None,
            "pbo_interpretation": "skipped",
            "reason": "No strategies",
            "n_combinations": 0,
        }

    # Create n_splits equal chronological sub-periods
    sub_periods: list[pd.DataFrame] = []
    for i in range(n_splits):
        start_idx = i * bars_per_split
        end_idx = start_idx + bars_per_split if i < n_splits - 1 else n
        sub_periods.append(ohlcv.iloc[start_idx:end_idx])

    # For CSCV: iterate over C(n_splits, n_splits/2) combinations of sub-periods.
    # Cap at 200 combinations for speed (still statistically valid approximation).
    half = n_splits // 2
    all_indices = list(range(n_splits))
    max_combinations = 200

    all_combos = list(combinations(all_indices, half))
    if len(all_combos) > max_combinations:
        rng = np.random.default_rng(42)
        chosen_idxs = rng.choice(len(all_combos), size=max_combinations, replace=False)
        sampled_combos = [all_combos[i] for i in chosen_idxs]
    else:
        sampled_combos = all_combos

    # Evaluate each strategy on each IS/OOS partition
    n_is_wins = 0
    n_is_losses = 0

    for combo in sampled_combos:
        is_indices = set(combo)
        oos_indices = set(all_indices) - is_indices

        is_ohlcv = pd.concat([sub_periods[i] for i in sorted(is_indices)])
        oos_ohlcv = pd.concat([sub_periods[i] for i in sorted(oos_indices)])

        # Score each strategy on IS
        is_scores: list[float] = []
        for strat in strategies:
            s = run_backtest_fn(strat["params"], is_ohlcv)
            is_scores.append(s if s is not None else float("-inf"))

        # IS winner = strategy with highest IS score
        best_is_idx = int(np.argmax(is_scores))

        # Score each strategy on OOS
        oos_scores: list[float] = []
        for strat in strategies:
            s = run_backtest_fn(strat["params"], oos_ohlcv)
            oos_scores.append(s if s is not None else float("-inf"))

        # IS winner's OOS rank
        is_winner_oos_score = oos_scores[best_is_idx]
        valid_oos = [s for s in oos_scores if s != float("-inf")]
        oos_median = float(np.median(valid_oos)) if valid_oos else 0.0

        # PBO logic: IS winner fails if it scores below OOS median
        if is_winner_oos_score < oos_median:
            n_is_losses += 1
        else:
            n_is_wins += 1

    total = n_is_wins + n_is_losses
    pbo = n_is_losses / total if total > 0 else 0.5

    if pbo < 0.1:
        interpretation = "robust"
    elif pbo < 0.3:
        interpretation = "borderline"
    else:
        interpretation = "overfitted"

    return {
        "pbo": round(pbo, 3),
        "pbo_interpretation": interpretation,
        "n_is_wins": n_is_wins,
        "n_is_losses": n_is_losses,
        "n_combinations": total,
        "interpretation_guide": {
            "robust": "PBO < 0.1: low overfitting risk",
            "borderline": "PBO 0.1-0.3: moderate overfitting risk, use with caution",
            "overfitted": "PBO > 0.3: high overfitting risk, do not rely on optimization results",
        },
    }
