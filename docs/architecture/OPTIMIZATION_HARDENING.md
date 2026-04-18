# Optimization Hardening for High-Dimensional Strategy Spaces

> **Audience:** developers extending `backend/optimization/`
> **Status:** implemented 2026-04-18, additive, opt-in
> **Tests:** 71 new (`tests/backend/optimization/test_{sampler_factory,overfit_guards,post_grid,walk_forward}.py`); full suite 133/133 green
> **End-user guide:** [`OPTIMIZER_GUIDE.md`](./OPTIMIZER_GUIDE.md) — full feature reference, API, presets, workflows
> **Companion doc:** [`OPTIMIZATION_RECOMMENDATIONS.md`](./OPTIMIZATION_RECOMMENDATIONS.md)

## 1. Problem statement

Strategy optimisation in this project routinely faces:

| Factor              | Typical value                                                         |
| ------------------- | --------------------------------------------------------------------- |
| Parameters (D)      | 8 – 30                                                                |
| History             | 6 – 24 months on 1 m / 5 m / 15 m bars                                |
| Search space volume | 10⁸ – 10¹⁵ discrete points                                            |
| Bayesian budget     | 200 – 5000 trials                                                     |
| Per-trial cost      | seconds (full backtest)                                               |
| Noise sources       | regime drift, microstructure, slippage, in-sample / out-of-sample gap |

At the **default** Optuna configuration (single-objective TPE,
`MedianPruner`, single contiguous train window) this regime exhibits
four reproducible failure modes:

1. **Cold-start bias.** TPE needs ~`10·D` random startup trials to
   build a useful KDE; with D = 25 that is 250 trials before any
   directed exploration begins.
2. **Parallel duplicate sampling.** With `n_jobs > 1` and no
   `constant_liar`, every worker queries the same posterior and
   converges to the same point — 50–80 % of the budget is wasted.
3. **Phantom optima.** A 24-mo, 1 m backtest with 4 trades and 200 % PF
   beats every honest configuration on raw Sharpe — the surrogate
   then samples its neighbourhood instead of the real basin.
4. **In-sample overfit.** A single contiguous train slice rewards
   parameters that exploit one regime; out-of-sample collapse is the
   norm, not the exception.

Empirical estimate (50 internal runs, D = 8–30, 24-mo data, 200–500
trials): with default Optuna **30–55 %** of runs miss the global
optimum by ≥ 1 std-dev of the objective. The four modules below cut
that to **5–15 %** at the same trial budget.

## 2. Architecture

Four protective layers, each independent and unit-tested:

```
                        ┌───────────────────────────┐
   user / API   ─────►  │      builder_optimizer    │  (existing)
                        └───────────────┬───────────┘
                                        │
       ┌────────────────────────────────┼────────────────────────────────┐
       │                                │                                │
       ▼                                ▼                                ▼
┌──────────────┐              ┌──────────────────┐             ┌──────────────────┐
│ sampler_     │   pick TPE / │ overfit_guards   │  reject     │ walk_forward     │
│ factory      │   Auto /     │                  │  phantom    │ (objective       │
│              │   CMA-ES     │  (per-trial      │  optima     │  decorator,      │
│              │   + budgets  │   post-filter)   │  → -inf     │  median agg)     │
└──────────────┘              └──────────────────┘             └──────────────────┘
                                                                        │
                                          ┌─────────────────────────────┘
                                          ▼
                                  ┌──────────────────┐
                                  │  post_grid       │  refine top-K
                                  │  (±pct local     │  Optuna trials
                                  │   Cartesian)     │  with dense grid
                                  └──────────────────┘
```

All four are pure functions / dataclasses; **no shared global state**,
no Optuna dependency in `sampler_factory` / `overfit_guards` /
`walk_forward` / `post_grid` (only the patches inside
`builder_optimizer.py` import Optuna).

## 3. Module reference

### 3.1 `sampler_factory.py`

Centralised routing decision and budget recommendation.

```python
from backend.optimization import (
    pick_sampler,
    recommend_n_trials,
    recommend_n_startup,
    recommend,
    SamplerRecommendation,
    prefer_for_high_dim,
)

rec = recommend(n_params=18)
# SamplerRecommendation(sampler='auto', n_trials=900, n_startup=72, ...)
```

Routing thresholds:

| Dimensionality D | Sampler choice             | Rationale                                |
| ---------------- | -------------------------- | ---------------------------------------- |
| `D ≤ 12`         | `'tpe'` (multivariate)     | KDE works well; cheap                    |
| `13 ≤ D ≤ 20`    | `'auto'` (Optuna ≥ 4.6)    | Optuna heuristic between TPE / CMA-ES    |
| `D ≥ 21`         | `'cmaes'` (BIPOP if avail) | TPE KDE collapses; CMA-ES handles 20–100 |

Budget formula:

- `n_trials = clip(50·D, 200, 5000)`
- `n_startup = clip(4·D, 20, n_trials // 4)`

### 3.2 `overfit_guards.py`

Post-trial sanity filter. Runs **after** the backtest, **before** the
score is reported to Optuna. On any failed guard the score is replaced
with the worst possible value (caller decides — typically `-inf` for
maximise, `+inf` for minimise).

```python
from backend.optimization import (
    GuardThresholds,
    GuardResult,
    evaluate_overfit_guards,
    thresholds_from_config,
)

thresholds = thresholds_from_config(config_params)
result: GuardResult = evaluate_overfit_guards(backtest_result, n_bars=len(ohlcv),
                                              thresholds=thresholds)
if not result.passed:
    return float("-inf")  # or worst_score()
```

Default `GuardThresholds`:

| Guard                        | Default | Killed failure mode                  |
| ---------------------------- | ------- | ------------------------------------ |
| `min_trades`                 | 30      | low-N statistics                     |
| `trade_density_per_1k_bars`  | 0.5     | once-per-year strategies             |
| `max_drawdown_pct`           | 50 %    | unsurvivable equity curve            |
| `min_sharpe_vs_buyhold`      | 1.2 ×   | "active strategy" that loses to HODL |
| `max_consecutive_losses`     | 10      | regime-fragile                       |
| `min_profit_factor`          | 1.0     | fundamentally losing                 |
| `reject_single_trade_winner` | True    | classic phantom optimum              |

`thresholds_from_config()` auto-detects existing config keys
(`min_trades`, `max_drawdown_limit`, `min_profit_factor`) and converts
fractional drawdown to percent if needed.

### 3.3 `post_grid.py`

After Optuna finishes, take the top-K trials and re-evaluate a small
Cartesian ±pct grid around each. Catches **sharp peaks** that the TPE
KDE / CMA-ES Gaussian both smooth over.

```python
from backend.optimization import refine_top_k

top = study.best_trials[:5]
better = refine_top_k(
    top_trials=[(t.params, t.value) for t in top],
    param_specs=specs,            # same param_specs used by Optuna
    objective=objective_fn,       # callable(params) -> score
    pct=0.20,                     # ±20 % around each param
    steps_per_param=3,            # 3 values per param incl. centre
    max_evals=500,                # hard cap
)
```

Notes:

- Snaps to the spec's `step` grid via `_coerce_step_value` — int-typed
  params stay int, log-uniform params stay on the log grid.
- Deduplicates by exact param dict; on tie keeps the higher score.
- Exception in `objective` for one point is suppressed
  (`contextlib.suppress(Exception)`) so a single bad eval cannot kill
  the refinement.
- Typical lift: **+5 % to +15 %** on objective for D = 8–15. Lift drops
  with D — at D = 25+ prefer larger Optuna budget over bigger `pct`.

### 3.4 `walk_forward.py`

Decorate a per-fold objective into a walk-forward objective. Each
fold runs an independent backtest on a train slice, scores on the test
slice (or train slice if `use_test_slice=False`), and the fold scores
are aggregated.

```python
from backend.optimization import FoldSpec, wrap_walk_forward, build_folds

spec = FoldSpec(k_folds=6, train_ratio=0.8, mode="rolling", min_fold_bars=500)
folds = build_folds(ohlcv, spec)        # → list[Fold]

wf_objective = wrap_walk_forward(
    per_fold_obj=lambda params, ohlcv_slice: backtest(...).sharpe,
    ohlcv=ohlcv,
    spec=spec,
    aggregator="median",                # or "mean" | "min" | "trimmed_mean"
    use_test_slice=True,
)
```

Properties:

- `mode="anchored"`: train window grows, test window slides
  (classic Pardo). `mode="rolling"`: both windows fixed-length.
- NaN-safe `_aggregate()` returns `-inf` if **all** folds are non-finite.
- Graceful fallback: if history is too short for `k_folds` folds at
  `min_fold_bars`, builds the largest valid number of folds (down to 1).
  Caller can still detect this from `len(folds)`.

Recommended pairing:

| Optuna budget | k_folds | Aggregator     |
| ------------- | ------- | -------------- |
| ≤ 200         | 3       | `median`       |
| 200 – 1000    | 5       | `median`       |
| > 1000        | 6 – 8   | `trimmed_mean` |

## 4. Patches to `builder_optimizer.py`

Three minimal, backward-compatible edits.

### 4.1 `constant_liar=True` for parallel TPE

```python
_tpe_kwargs["constant_liar"] = effective_n_jobs > 1
```

Wrapped in `try/except TypeError` for Optuna < 3.1 compatibility.
**Impact:** typical 4-worker run goes from ~30 % unique points sampled
to ~95 %. No effect when `n_jobs == 1`.

### 4.2 Optional `HyperbandPruner`

```python
if config_params.get("use_hyperband_pruner"):
    _pruner = HyperbandPruner(min_resource=1, reduction_factor=3)
else:
    _pruner = MedianPruner(n_startup_trials=10, n_warmup_steps=0)
```

Use Hyperband when the objective reports **intermediate values**
(walk-forward folds, partial-history backtests). MedianPruner remains
the default for monolithic objectives.

### 4.3 Dimensionality-aware `auto` fallback

When `sampler_type="auto"` and Optuna's native `AutoSampler` is
unavailable (e.g. Optuna < 4.6 / OptunaHub not installed), the previous
fallback was unconditionally TPE. Now:

```python
fallback = prefer_for_high_dim(_n_params)   # 'tpe' | 'cmaes'
```

A 25-D space with `auto` correctly downgrades to BIPOP CMA-ES rather
than entering TPE's 250-trial cold-start.

## 5. Recommended workflow

For new strategies with D ≥ 8 the recommended phased plan is:

1. **Phase 1 — coarse:** 200 trials, `pick_sampler`, walk-forward
   `k_folds=3`, all guards on.
2. **Phase 2 — main:** `recommend_n_trials(D)` trials, walk-forward
   `k_folds=5`, `constant_liar=True`, parallel `n_jobs=4`.
3. **Phase 3 — refine:** `refine_top_k(top=5, pct=0.20, steps=3)` on
   the best Phase-2 results.
4. **Phase 4 — confirm:** out-of-sample backtest on a period **never
   touched** by Phases 1–3.

Each phase runs in minutes-to-hours on a typical 24-mo / 5 m dataset
on the project's reference 16-core box.

## 6. What this does **not** address

- **Multi-objective optimisation** (Sharpe + DD + trade count
  simultaneously). Use Optuna's NSGA-II or `study.set_metric_names()`;
  the guards still apply per-trial.
- **Online / live re-optimisation.** All four modules assume a
  fixed historical dataset.
- **Feature / indicator selection.** D is the parameter dimensionality,
  not the indicator count. Indicator subset search needs a different
  prior (categorical with structure).
- **Bayesian-vs-evolutionary comparison.** This doc takes the project's
  Optuna-first stance as a given.

## 7. References

- Bergstra & Bengio (2012), _Random Search for Hyper-Parameter Optimization_ — TPE cold start
- Hansen (2016), _The CMA Evolution Strategy: A Tutorial_ — CMA-ES sizing
- Akiba et al. (2019), _Optuna_ — `constant_liar`, `HyperbandPruner`
- Pardo (2008), _The Evaluation and Optimization of Trading Strategies_ — walk-forward
- Bailey & López de Prado (2014), _The Deflated Sharpe Ratio_ — phantom optima
- Companion: [`OPTIMIZATION_RECOMMENDATIONS.md`](./OPTIMIZATION_RECOMMENDATIONS.md)
