"""
Walk-forward objective wrapper.

Single-shot backtests on the full history are the #1 source of overfitting in
parameter optimisation. Walk-forward analysis splits the data into ``k_folds``
non-overlapping (or overlapping with stride) train/test windows, evaluates
the candidate parameters on each fold, and aggregates the per-fold scores
with a robust statistic (median by default — resistant to outlier folds).

This wrapper is **objective-agnostic**: callers pass any function
``ohlcv_slice -> score`` and get back a single scalar suitable for Optuna's
``objective`` callback.

Example
-------
::

    from backend.optimization.walk_forward import wrap_walk_forward, FoldSpec

    def single_fold_objective(params, ohlcv):
        result = backtest(params, ohlcv)
        return calculate_composite_score(result, "sharpe_ratio")

    wf_objective = wrap_walk_forward(
        single_fold_objective,
        ohlcv=full_history_df,
        spec=FoldSpec(k_folds=6, train_ratio=0.8, mode="anchored"),
        aggregator="median",
    )

    # Pass to Optuna:
    study.optimize(lambda trial: wf_objective(suggest_params(trial)), n_trials=1500)
"""

from __future__ import annotations

import logging
import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

logger = logging.getLogger(__name__)

AggregatorName = Literal["median", "mean", "min", "trimmed_mean"]
FoldMode = Literal["anchored", "rolling"]


@dataclass(frozen=True)
class FoldSpec:
    """Configuration for the walk-forward split.

    Attributes:
        k_folds: Number of train/test pairs to generate.
        train_ratio: Fraction of each window dedicated to training.
            ``train_ratio=0.8`` means 80 % train / 20 % test.
        mode: ``"anchored"`` keeps the train start fixed (expanding window);
            ``"rolling"`` advances both train start and end by ``stride``.
        min_fold_bars: Reject any fold whose train OR test slice is shorter
            than this. Avoids degenerate folds at the start of history.
    """

    k_folds: int = 6
    train_ratio: float = 0.8
    mode: FoldMode = "anchored"
    min_fold_bars: int = 500


@dataclass(frozen=True)
class _Fold:
    train: pd.DataFrame
    test: pd.DataFrame


def _aggregate(scores: list[float], how: AggregatorName) -> float:
    """Combine per-fold scores into a single objective value.

    NaN-/Inf-safe; if every score is non-finite the result is ``-inf`` so
    Optuna treats the trial as the worst possible.
    """
    finite = [s for s in scores if math.isfinite(s)]
    if not finite:
        return float("-inf")
    if how == "mean":
        return float(statistics.fmean(finite))
    if how == "min":
        return float(min(finite))
    if how == "trimmed_mean":
        # Drop one best + one worst when n ≥ 4 (Tukey-style robustness).
        if len(finite) >= 4:
            trimmed = sorted(finite)[1:-1]
            return float(statistics.fmean(trimmed))
        return float(statistics.fmean(finite))
    # default: median (robust to outlier folds, recommended)
    return float(statistics.median(finite))


def build_folds(ohlcv: pd.DataFrame, spec: FoldSpec) -> list[_Fold]:
    """Slice *ohlcv* into ``k_folds`` train/test pairs per the *spec*.

    Returns:
        List of :class:`_Fold` objects. May contain fewer than ``k_folds``
        entries if the history is too short — folds shorter than
        ``min_fold_bars`` are silently dropped with a warning.

    Raises:
        ValueError: If *spec* is logically inconsistent (e.g. k_folds < 1).
    """
    if spec.k_folds < 1:
        raise ValueError(f"k_folds must be ≥ 1, got {spec.k_folds}")
    if not 0.0 < spec.train_ratio < 1.0:
        raise ValueError(f"train_ratio must be in (0, 1), got {spec.train_ratio}")

    n = len(ohlcv)
    if n < spec.min_fold_bars * 2:
        logger.warning(
            "OHLCV too short for walk-forward (%d bars < 2×min_fold_bars=%d) — returning a single fold.",
            n,
            spec.min_fold_bars,
        )
        split = int(n * spec.train_ratio)
        return [_Fold(train=ohlcv.iloc[:split], test=ohlcv.iloc[split:])]

    folds: list[_Fold] = []
    if spec.mode == "anchored":
        # Expanding-window: each fold tests on the next chunk after the train end.
        # Test chunk size grows so all folds end at the data tail; train always
        # starts at index 0.
        # Layout:  [-------- train --------][test_1]
        #          [---------- train ----------][test_2]
        #                                        ...
        test_per_fold = max(1, n // (spec.k_folds + 1))
        for i in range(spec.k_folds):
            test_start = (i + 1) * test_per_fold
            test_end = min(n, test_start + test_per_fold)
            if test_start >= n:
                break
            folds.append(
                _Fold(
                    train=ohlcv.iloc[:test_start],
                    test=ohlcv.iloc[test_start:test_end],
                )
            )
    else:
        # Rolling: window slides by stride; both train_size and test_size constant.
        # Total span used = window × k_folds  → window = n / (k + train_ratio·(k-1))
        # Simpler heuristic: window = n // k_folds, train = window·train_ratio.
        window = n // spec.k_folds
        train_size = max(1, int(window * spec.train_ratio))
        test_size = max(1, window - train_size)
        for i in range(spec.k_folds):
            start = i * window
            train_end = start + train_size
            test_end = train_end + test_size
            if test_end > n:
                break
            folds.append(
                _Fold(
                    train=ohlcv.iloc[start:train_end],
                    test=ohlcv.iloc[train_end:test_end],
                )
            )

    # Drop folds that are too small to be meaningful.
    folds = [f for f in folds if len(f.train) >= spec.min_fold_bars and len(f.test) >= spec.min_fold_bars]
    return folds


def wrap_walk_forward(
    single_fold_objective: Callable[[dict[str, Any], pd.DataFrame], float],
    ohlcv: pd.DataFrame,
    spec: FoldSpec | None = None,
    *,
    aggregator: AggregatorName = "median",
    use_test_slice: bool = True,
) -> Callable[[dict[str, Any]], float]:
    """Decorate a per-fold objective into a walk-forward objective.

    Args:
        single_fold_objective: Callable ``(params, ohlcv_slice) -> score``.
            MUST be deterministic given the inputs and MUST NOT raise.
        ohlcv: Full history dataframe (chronologically ordered).
        spec: Fold configuration (defaults to 6 anchored folds, 80 % train).
        aggregator: How to combine per-fold scores.
        use_test_slice: If True (default), score is computed on the **test**
            slice of each fold (out-of-sample, the honest measurement). If
            False, score is computed on the train slice (in-sample, mostly
            useful for sanity checks).

    Returns:
        Function ``params -> aggregated_score`` ready to plug into Optuna.
    """
    spec = spec or FoldSpec()
    folds = build_folds(ohlcv, spec)
    if not folds:
        raise ValueError(
            f"No valid folds constructed (n={len(ohlcv)}, spec={spec}). Reduce min_fold_bars or supply more history."
        )
    logger.info(
        "Walk-forward: %d folds × ~%d test bars each (mode=%s, agg=%s)",
        len(folds),
        sum(len(f.test) for f in folds) // len(folds),
        spec.mode,
        aggregator,
    )

    def _wrapped(params: dict[str, Any]) -> float:
        scores: list[float] = []
        for f in folds:
            slice_ = f.test if use_test_slice else f.train
            try:
                s = float(single_fold_objective(params, slice_))
            except Exception as exc:
                logger.warning("walk-forward fold raised: %s", exc)
                s = float("-inf")
            scores.append(s)
        return _aggregate(scores, aggregator)

    return _wrapped
