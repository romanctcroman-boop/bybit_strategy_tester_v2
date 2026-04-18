"""
Sampler & budget recommendation factory.

Centralises the rule-of-thumb logic for picking an Optuna sampler given the
dimensionality of the search space, and for recommending a sensible trial
budget. Used by Strategy Builder optimisation paths so that callers don't
hard-code ``sampler_type="tpe"`` regardless of whether they have 8 or 30
parameters.

Rationale
---------
* **n_params ≤ 12** → ``tpe``: TPE with ``multivariate=True`` is the most
  sample-efficient sampler in low dimensions and handles correlated params
  well via the ``group=True`` grouping.
* **13 ≤ n_params ≤ 20** → ``auto``: AutoSampler (Optuna ≥ 4.6) selects an
  appropriate algorithm per phase. If unavailable, callers fall back to
  TPE → CMA-ES based on `prefer_for_high_dim()`.
* **n_params ≥ 21** → ``cmaes``: TPE/GP degrade above ~20 dims; CMA-ES
  (covariance matrix adaptation evolutionary strategy) scales much better
  and the BIPOP restart variant escapes local optima.

Recommended budgets follow ``max(200, 50 × D)`` — the floor of 200 keeps
small-D problems from underexploring; the linear scaling matches Optuna's
own published recommendations (100–1000 for TPE, 100–10000 for CMA-ES).

This module has **no Optuna dependency** so it can be imported cheaply at
startup; the actual sampler instantiation is left to ``builder_optimizer``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SamplerName = Literal["tpe", "auto", "cmaes", "gp", "qmc", "random"]


# ─────────────────────────────────────────────────────────────────────────────
# Thresholds — tuned for crypto-strategy parameter spaces (typically 8–30 D)
# ─────────────────────────────────────────────────────────────────────────────

#: Above this dimensionality, switch to AutoSampler if available.
DIM_TPE_TO_AUTO = 12

#: Above this dimensionality, switch to CMA-ES (TPE surrogate becomes unreliable).
DIM_AUTO_TO_CMAES = 20

#: Floor on recommended trials regardless of D.
MIN_RECOMMENDED_TRIALS = 200

#: Trials per parameter (linear scaling above the floor).
TRIALS_PER_PARAM = 50

#: Cap to avoid runaway budgets on D > 40 (the user's spec maxes at 30).
MAX_RECOMMENDED_TRIALS = 5000


@dataclass(frozen=True)
class SamplerRecommendation:
    """Bundle of sampler choice + budget hint for a given parameter space."""

    sampler: SamplerName
    n_trials: int
    n_startup: int
    rationale: str


def pick_sampler(n_params: int) -> SamplerName:
    """Return the recommended sampler name for the given dimensionality.

    Args:
        n_params: Number of optimisable parameters.

    Returns:
        Canonical sampler identifier consumed by ``run_builder_optuna_search``.

    >>> pick_sampler(5)
    'tpe'
    >>> pick_sampler(15)
    'auto'
    >>> pick_sampler(25)
    'cmaes'
    """
    if n_params <= 0:
        # Defensive — empty search space should never reach the sampler at all.
        return "tpe"
    if n_params <= DIM_TPE_TO_AUTO:
        return "tpe"
    if n_params <= DIM_AUTO_TO_CMAES:
        return "auto"
    return "cmaes"


def prefer_for_high_dim(n_params: int) -> SamplerName:
    """Fallback when AutoSampler is unavailable (Optuna < 4.6).

    For mid-dim (13–20) we still want something that handles correlations,
    so we keep TPE; for high-dim (≥21) we fall through to CMA-ES.
    """
    if n_params <= DIM_AUTO_TO_CMAES:
        return "tpe"
    return "cmaes"


def recommend_n_trials(n_params: int, *, multiplier: float = 1.0) -> int:
    """Return a sensible trial budget for a search space of ``n_params`` dims.

    Uses ``max(MIN_RECOMMENDED_TRIALS, TRIALS_PER_PARAM × n_params)``,
    clipped to ``MAX_RECOMMENDED_TRIALS``.

    Args:
        n_params: Number of optimisable parameters.
        multiplier: Multiply the result (e.g. 0.5 for "fast" mode, 2.0 for
            "thorough"). Useful for callers that want to scale the default.

    >>> recommend_n_trials(5)
    250
    >>> recommend_n_trials(8)
    400
    >>> recommend_n_trials(30)
    1500
    """
    base = max(MIN_RECOMMENDED_TRIALS, TRIALS_PER_PARAM * max(n_params, 1))
    scaled = round(base * max(multiplier, 0.0))
    return max(1, min(scaled, MAX_RECOMMENDED_TRIALS))


def recommend_n_startup(n_params: int, n_trials: int) -> int:
    """Recommend the size of the QMC/random exploration phase.

    Keeps ``≥ 4 × D`` startup points so the surrogate model has enough data
    to fit, but never spends more than ¼ of the total budget on startup.
    """
    floor = max(20, 4 * max(n_params, 1))
    cap = max(10, n_trials // 4)
    return min(floor, cap)


def recommend(n_params: int, *, multiplier: float = 1.0) -> SamplerRecommendation:
    """One-shot recommendation: sampler + budget + startup, with rationale.

    Combines :func:`pick_sampler` and :func:`recommend_n_trials`.
    """
    sampler = pick_sampler(n_params)
    n_trials = recommend_n_trials(n_params, multiplier=multiplier)
    n_startup = recommend_n_startup(n_params, n_trials)
    if sampler == "tpe":
        why = (
            f"D={n_params} ≤ {DIM_TPE_TO_AUTO}: TPE multivariate is the most sample-efficient choice in low dimensions."
        )
    elif sampler == "auto":
        why = (
            f"{DIM_TPE_TO_AUTO} < D={n_params} ≤ {DIM_AUTO_TO_CMAES}: "
            "AutoSampler picks per-phase between GP/TPE/CMA-ES."
        )
    else:  # cmaes
        why = (
            f"D={n_params} > {DIM_AUTO_TO_CMAES}: TPE/GP degrade in high dims, "
            "CMA-ES (BIPOP restart) scales much better."
        )
    return SamplerRecommendation(
        sampler=sampler,
        n_trials=n_trials,
        n_startup=n_startup,
        rationale=why,
    )
