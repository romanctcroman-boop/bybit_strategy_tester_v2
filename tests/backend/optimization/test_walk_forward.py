"""Tests for backend.optimization.walk_forward."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import pytest

from backend.optimization.walk_forward import (
    FoldSpec,
    build_folds,
    wrap_walk_forward,
)


def _ohlcv(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "open": rng.uniform(100, 200, n),
            "high": rng.uniform(100, 200, n),
            "low": rng.uniform(100, 200, n),
            "close": rng.uniform(100, 200, n),
            "volume": rng.uniform(1, 100, n),
        }
    )


class TestBuildFolds:
    def test_invalid_k_folds_raises(self) -> None:
        with pytest.raises(ValueError):
            build_folds(_ohlcv(10_000), FoldSpec(k_folds=0))

    def test_invalid_train_ratio_raises(self) -> None:
        with pytest.raises(ValueError):
            build_folds(_ohlcv(10_000), FoldSpec(train_ratio=1.0))
        with pytest.raises(ValueError):
            build_folds(_ohlcv(10_000), FoldSpec(train_ratio=0.0))

    def test_anchored_folds_train_starts_at_zero(self) -> None:
        df = _ohlcv(20_000)
        folds = build_folds(df, FoldSpec(k_folds=4, mode="anchored", min_fold_bars=500))
        assert len(folds) >= 1
        for f in folds:
            # Anchored: every train slice begins at index 0
            assert f.train.index[0] == df.index[0]

    def test_rolling_folds_advance_window(self) -> None:
        df = _ohlcv(20_000)
        folds = build_folds(df, FoldSpec(k_folds=4, mode="rolling", min_fold_bars=500))
        assert len(folds) >= 2
        # train start of fold i+1 > train start of fold i
        starts = [f.train.index[0] for f in folds]
        assert starts == sorted(starts)
        assert starts[1] > starts[0]

    def test_short_history_returns_single_fold(self) -> None:
        df = _ohlcv(800)  # < 2 × 500 default min_fold_bars
        folds = build_folds(df, FoldSpec(k_folds=6, min_fold_bars=500))
        assert len(folds) == 1
        # train + test should cover the whole df
        assert len(folds[0].train) + len(folds[0].test) == 800

    def test_min_fold_bars_drops_small_folds(self) -> None:
        df = _ohlcv(10_000)
        # min=4000 → with 6 folds each ≈1666 bars → all dropped
        folds = build_folds(df, FoldSpec(k_folds=6, min_fold_bars=4000))
        assert all(len(f.train) >= 4000 and len(f.test) >= 4000 for f in folds)


class TestWrapWalkForward:
    def test_objective_called_per_fold(self) -> None:
        df = _ohlcv(20_000)
        spec = FoldSpec(k_folds=3, min_fold_bars=500)
        call_log: list[int] = []

        def per_fold(_params: dict[str, Any], slice_: pd.DataFrame) -> float:
            call_log.append(len(slice_))
            return 1.0

        wf = wrap_walk_forward(per_fold, df, spec=spec, aggregator="mean")
        score = wf({"x": 1})
        assert score == 1.0
        assert len(call_log) == len(build_folds(df, spec))

    def test_median_robust_to_outlier(self) -> None:
        df = _ohlcv(20_000)
        spec = FoldSpec(k_folds=5, min_fold_bars=500)
        scores_iter = iter([1.0, 1.0, 100.0, 1.0, 1.0])

        def per_fold(_p: dict[str, Any], _s: pd.DataFrame) -> float:
            return next(scores_iter)

        wf = wrap_walk_forward(per_fold, df, spec=spec, aggregator="median")
        # Median of [1, 1, 100, 1, 1] = 1, mean would be 20.8
        assert wf({}) == 1.0

    def test_min_aggregator_takes_worst_fold(self) -> None:
        df = _ohlcv(20_000)
        spec = FoldSpec(k_folds=4, min_fold_bars=500)
        scores_iter = iter([2.0, 3.0, 0.5, 4.0])

        def per_fold(_p: dict[str, Any], _s: pd.DataFrame) -> float:
            return next(scores_iter)

        wf = wrap_walk_forward(per_fold, df, spec=spec, aggregator="min")
        assert wf({}) == 0.5

    def test_trimmed_mean_drops_extremes(self) -> None:
        df = _ohlcv(20_000)
        spec = FoldSpec(k_folds=5, min_fold_bars=500)
        scores_iter = iter([0.0, 1.0, 1.0, 1.0, 100.0])

        def per_fold(_p: dict[str, Any], _s: pd.DataFrame) -> float:
            return next(scores_iter)

        wf = wrap_walk_forward(per_fold, df, spec=spec, aggregator="trimmed_mean")
        # Drop 0 and 100, mean of [1,1,1] = 1
        assert wf({}) == 1.0

    def test_all_nan_returns_neg_inf(self) -> None:
        df = _ohlcv(10_000)
        spec = FoldSpec(k_folds=3, min_fold_bars=500)

        def per_fold(_p: dict[str, Any], _s: pd.DataFrame) -> float:
            return float("nan")

        wf = wrap_walk_forward(per_fold, df, spec=spec)
        assert wf({}) == float("-inf")

    def test_objective_exception_does_not_crash(self) -> None:
        df = _ohlcv(10_000)
        spec = FoldSpec(k_folds=3, min_fold_bars=500)
        calls = {"n": 0}

        def per_fold(_p: dict[str, Any], _s: pd.DataFrame) -> float:
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("boom")
            return 1.0

        wf = wrap_walk_forward(per_fold, df, spec=spec, aggregator="mean")
        # 2 of 3 folds return 1.0; the failing one becomes -inf and is dropped
        # by _aggregate (only finite values are used). Mean of [1.0, 1.0] = 1.0
        result = wf({})
        assert math.isfinite(result)
        assert result == 1.0

    def test_use_test_slice_default(self) -> None:
        df = _ohlcv(20_000)
        spec = FoldSpec(k_folds=3, mode="anchored", train_ratio=0.8, min_fold_bars=500)
        captured: list[int] = []

        def per_fold(_p: dict[str, Any], slice_: pd.DataFrame) -> float:
            captured.append(len(slice_))
            return 1.0

        wf = wrap_walk_forward(per_fold, df, spec=spec, use_test_slice=True)
        wf({})
        # Test slices should be smaller than full dataset
        assert all(c < 20_000 for c in captured)

    def test_no_valid_folds_raises(self) -> None:
        # Data large enough to bypass the short-history fallback (n ≥ 2×min)
        # but min_fold_bars per-window is so high that EVERY constructed fold
        # is filtered out → build_folds returns [] → wrap_walk_forward raises.
        df = _ohlcv(25_000)
        with pytest.raises(ValueError):
            wrap_walk_forward(
                lambda _p, _s: 1.0,
                df,
                # 6 folds × ~4166 bars each, but require 10_000 → all dropped
                FoldSpec(k_folds=6, min_fold_bars=10_000),
            )
