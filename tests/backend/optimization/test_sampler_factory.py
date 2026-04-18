"""Tests for backend.optimization.sampler_factory."""

from __future__ import annotations

import pytest

from backend.optimization.sampler_factory import (
    DIM_AUTO_TO_CMAES,
    DIM_TPE_TO_AUTO,
    MAX_RECOMMENDED_TRIALS,
    MIN_RECOMMENDED_TRIALS,
    pick_sampler,
    prefer_for_high_dim,
    recommend,
    recommend_n_startup,
    recommend_n_trials,
)


class TestPickSampler:
    """Sampler routing rules."""

    @pytest.mark.parametrize("d", [1, 5, 8, 10, DIM_TPE_TO_AUTO])
    def test_low_dim_uses_tpe(self, d: int) -> None:
        assert pick_sampler(d) == "tpe"

    @pytest.mark.parametrize("d", [DIM_TPE_TO_AUTO + 1, 15, DIM_AUTO_TO_CMAES])
    def test_mid_dim_uses_auto(self, d: int) -> None:
        assert pick_sampler(d) == "auto"

    @pytest.mark.parametrize("d", [DIM_AUTO_TO_CMAES + 1, 25, 30, 50])
    def test_high_dim_uses_cmaes(self, d: int) -> None:
        assert pick_sampler(d) == "cmaes"

    def test_zero_or_negative_falls_back_to_tpe(self) -> None:
        assert pick_sampler(0) == "tpe"
        assert pick_sampler(-1) == "tpe"


class TestPreferForHighDim:
    """Fallback used when AutoSampler is unavailable."""

    @pytest.mark.parametrize("d", [1, 12, 20])
    def test_keeps_tpe_up_to_20(self, d: int) -> None:
        assert prefer_for_high_dim(d) == "tpe"

    @pytest.mark.parametrize("d", [21, 25, 30])
    def test_switches_to_cmaes_above_20(self, d: int) -> None:
        assert prefer_for_high_dim(d) == "cmaes"


class TestRecommendNTrials:
    """Budget formula: max(MIN, 50×D), capped at MAX."""

    def test_floor_applied_for_small_d(self) -> None:
        # 50 × 1 = 50, but floor is 200
        assert recommend_n_trials(1) == MIN_RECOMMENDED_TRIALS

    def test_linear_above_floor(self) -> None:
        assert recommend_n_trials(8) == 400
        assert recommend_n_trials(15) == 750
        assert recommend_n_trials(30) == 1500

    def test_capped_at_max(self) -> None:
        assert recommend_n_trials(1000) == MAX_RECOMMENDED_TRIALS

    def test_multiplier_scales_result(self) -> None:
        base = recommend_n_trials(10)
        assert recommend_n_trials(10, multiplier=2.0) == 2 * base

    def test_multiplier_zero_returns_one(self) -> None:
        # Floor is 1 — multiplier=0 collapses to that
        assert recommend_n_trials(10, multiplier=0.0) == 1

    def test_returns_int(self) -> None:
        assert isinstance(recommend_n_trials(8), int)


class TestRecommendNStartup:
    """Startup is bounded by 4×D and ≤ n_trials/4."""

    def test_startup_cap_at_quarter_of_budget(self) -> None:
        # 100 trials / 4 = 25, while 4×D=80 → 25 wins
        assert recommend_n_startup(20, 100) == 25

    def test_startup_floor_4d_or_20(self) -> None:
        # 1000 trials / 4 = 250 cap, 4×3=12 floor → max(20, 12)=20 (then min with 250)
        assert recommend_n_startup(3, 1000) == 20

    def test_startup_never_exceeds_n_trials(self) -> None:
        assert recommend_n_startup(50, 40) <= 40


class TestRecommend:
    """End-to-end recommend() bundle."""

    def test_returns_consistent_recommendation(self) -> None:
        rec = recommend(8)
        assert rec.sampler == "tpe"
        assert rec.n_trials == recommend_n_trials(8)
        assert rec.n_startup == recommend_n_startup(8, rec.n_trials)
        assert rec.rationale  # non-empty

    def test_rationale_mentions_dimensionality(self) -> None:
        for d in (5, 15, 25):
            rec = recommend(d)
            assert str(d) in rec.rationale

    def test_high_dim_recommends_cmaes(self) -> None:
        rec = recommend(30)
        assert rec.sampler == "cmaes"
        assert "CMA-ES" in rec.rationale
