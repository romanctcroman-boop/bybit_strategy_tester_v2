# Optimizer Guide — Full Pipeline & Features

> **Last updated:** 2026-04-18
> **Audience:** end-users of Strategy Builder + developers integrating the optimization API
> **Scope:** complete reference covering all optimizer features, presets, flags, and how they interact
> **Companion docs:**
> - [`OPTIMIZATION_HARDENING.md`](./OPTIMIZATION_HARDENING.md) — implementation details
> - [`OPTIMIZATION_RECOMMENDATIONS.md`](./OPTIMIZATION_RECOMMENDATIONS.md) — theoretical background
> - [`STRATEGY_BUILDER_ARCHITECTURE.md`](./STRATEGY_BUILDER_ARCHITECTURE.md) — builder/graph pipeline

---

## Table of contents

1. [TL;DR](#1-tldr)
2. [End-to-end pipeline](#2-end-to-end-pipeline)
3. [Features catalogue](#3-features-catalogue)
4. [Hardening presets (UI buttons)](#4-hardening-presets-ui-buttons)
5. [API reference](#5-api-reference)
6. [Feature interaction matrix](#6-feature-interaction-matrix)
7. [Recommended workflows](#7-recommended-workflows)
8. [Output schema](#8-output-schema)
9. [Troubleshooting](#9-troubleshooting)
10. [Glossary](#10-glossary)

---

## 1. TL;DR

The optimizer runs **three distinct search algorithms** in series, each
protected by **four hardening layers** (all opt-in). Everything except the
core Bayesian search is **off by default** — if you don't flip flags,
behavior is identical to the pre-2026-04-18 baseline.

```

┌────────────┐   ┌───────────┐   ┌────────────┐   ┌──────────┐
│  Grid /    │ → │ Bayesian  │ → │ Post-grid  │ → │ Overfit  │
│  Random    │   │ (Optuna)  │   │ refine     │   │ guards   │
│  search    │   │ ± WF      │   │ (±pct top) │   │ (filter) │
└────────────┘   └───────────┘   └────────────┘   └──────────┘
   coarse          main            local peak        sanity
                                                     check

```

**Three-run recipe (recommended for production strategies):**

| Run # | Preset     | Goal                                             |
| ----- | ---------- | ------------------------------------------------ |
| 1     | **Coarse** | Scout the full space (QMC sampler, wide ranges)  |
| 2     | **Main**   | Focus with Bayesian + parallel (constant_liar)   |
| 3     | **Confirm**| Walk-forward + overfit_guards + post-grid refine |

---

## 2. End-to-end pipeline

### 2.1 Request lifecycle

```

  UI / API
     │
     ▼
  POST /api/v1/strategy-builder/strategies/{id}/optimize
  body: BuilderOptimizationRequest (47 fields)
     │
     ▼
  ┌────────────────────────────────────────────────────────────┐
  │  router.py::start_optimization                             │
  │  • validate request (Pydantic)                             │
  │  • create Optimization DB row (status=PENDING)             │
  │  • schedule _execute_optimization_bg as BackgroundTask     │
  │  • return 202 + optimization_id                            │
  └────────────────────────────────────────────────────────────┘
     │
     ▼  (async, in background)
  ┌────────────────────────────────────────────────────────────┐
  │  _execute_optimization_bg                                  │
  │  ┌──────────────────────────────────────────────────────┐  │
  │  │ 1. Load OHLCV (smart_kline_service)                  │  │
  │  │ 2. extract_optimizable_params(strategy.graph)        │  │
  │  │ 3. build config_params {n_trials, sampler, flags...} │  │
  │  │ 4. Route by method:                                  │  │
  │  │    - grid    → run_builder_grid_search               │  │
  │  │    - random  → run_builder_random_search             │  │
  │  │    - bayes   → run_builder_optuna_search             │  │
  │  │ 5. If run_post_grid_refine:                          │  │
  │  │    run_builder_grid_search on build_refinement_grid  │  │
  │  │ 6. If apply_overfit_guards:                          │  │
  │  │    annotate each top_result with guard_passed        │  │
  │  │ 7. If run_cscv: compute PBO                          │  │
  │  │ 8. Update Optimization row (status=COMPLETED)        │  │
  │  └──────────────────────────────────────────────────────┘  │
  └────────────────────────────────────────────────────────────┘
     │
     ▼
  GET /api/v1/strategy-builder/strategies/{id}/optimizations/{opt_id}
  → full results (top_results, convergence, guards, refine annotations)

```

### 2.2 Inside `run_builder_optuna_search` (Bayesian path)

```

  ┌────────────────────────────────────────────────────────────┐
  │ 1. create_study                                            │
  │    • sampler = pick_sampler(D, n_trials, prefer_cmaes)     │
  │      - D ≤ 10 + n ≥ 50  → TPE                              │
  │      - D ≥ 20           → CMA-ES (if ≥50 startup trials)  │
  │      - "high-dim low-n" → QMC (quasi-random Sobol)        │
  │    • if use_constant_liar: TPESampler(constant_liar=True) │
  │    • if use_hyperband_pruner: HyperbandPruner()            │
  │    • else: MedianPruner()                                  │
  │                                                            │
  │ 2. if warm_start_trials:                                   │
  │    study.enqueue_trial(...) × N  (reuse prior best params) │
  │                                                            │
  │ 3. objective(trial):                                       │
  │    ┌─────────────────────────────────────────────────────┐ │
  │    │ a) suggest params (trial.suggest_*)                 │ │
  │    │ b) apply_cross_block_constraints                    │ │
  │    │    (e.g. TP ≥ SL·1.5, MACD fast < slow)             │ │
  │    │ c) clone_graph_with_params                          │ │
  │    │ d) passes_filters + passes_dynamic_constraints      │ │
  │    │ e) if wf_validation enabled:                        │ │
  │    │       folds = build_folds(ohlcv, n_folds)           │ │
  │    │       scores = [backtest(fold) for fold in folds]   │ │
  │    │       return aggregate(scores, method=median)       │ │
  │    │    else:                                            │ │
  │    │       return backtest(full_ohlcv).sharpe_ratio      │ │
  │    └─────────────────────────────────────────────────────┘ │
  │                                                            │
  │ 4. study.optimize(objective, n_trials, timeout, n_jobs)    │
  │                                                            │
  │ 5. collect top_n by calculate_composite_score              │
  │    (multi-criteria: sharpe/winrate/drawdown weighted)      │
  │                                                            │
  │ 6. return {top_results, all_trials, study_stats}           │
  └────────────────────────────────────────────────────────────┘

```

### 2.3 Post-grid refinement (new 2026-04-18)

Runs **after** the Bayesian search when `run_post_grid_refine=True`:

```

  top_results from Bayesian → take top-K (default K=5)
         │
         ▼
  For each of the K results:
    • For each dimension, build a ±pct local box around best value
      (default pct=0.20, steps=3)
    • Generate Cartesian grid within param_specs bounds
  Merge grids, deduplicate, cap at post_grid_max_evals (default 500)
         │
         ▼
  run_builder_grid_search on the merged grid
         │
         ▼
  Merge new results into top_results, re-rank by composite score
  Each refined trial carries `refined_from_trial: <original_rank>`

```

**Why this matters:** Bayesian sampler can "smooth over" sharp peaks.
Cartesian grid around the top-K catches optima the surrogate missed.

### 2.4 Overfit guards (new 2026-04-18)

Post-filter **applied to top results**, does not change search:

```

  For each result in top_results:
    violations = []
    if metrics.trade_count < guard_min_trades (default 30):
        violations.append("min_trades:<30")
    if metrics.max_drawdown_pct > guard_max_drawdown_pct (default 50):
        violations.append("max_drawdown:>50")
    if metrics.profit_factor < guard_min_profit_factor (default 1.0):
        violations.append("min_profit_factor:<1.0")

    result.guard_passed = (len(violations) == 0)
    result.guard_violations = violations

```

Results that fail guards are **still returned** (ranked last), so you
can inspect them. Guards are signals, not hard rejects.

### 2.5 Walk-forward validation (existing + reinforced)

```

  Split OHLCV chronologically into N folds (default 6):
  [─train─|─test─] [──train──|─test─] [───train───|─test─] ...
  │       │       │         │        │           │
  Optimize only on train, score on held-out test.
  Aggregate scores (median / mean / min) → robust single objective.

  Benefits:
  • Rejects regime-overfit parameters automatically
  • Single "sharpe" metric you see is already cross-validated
  • HyperbandPruner (new) accelerates this: prunes dud trials after
    fold 1 or 2, saving 60-80% of per-trial cost.

```

---

## 3. Features catalogue

### 3.1 Search algorithms (`method` parameter)

| Method | When to use | Cost | Deterministic |
|--------|-------------|------|---------------|
| `grid` | D ≤ 4, dense verification, post-grid refine | 5ᴰ–10ᴰ backtests | ✅ |
| `random` | D 4–10, quick scout, no priors | ~200 trials | ❌ (seeded) |
| `bayesian` (default) | D 8–30, expensive objective, main workhorse | 200–2000 trials | ❌ (seeded) |
| `genetic` | D 15–50 with strong constraints (experimental) | 500–5000 evals | ❌ |

### 3.2 Samplers (inside Bayesian mode)

| Sampler | Auto-picked when | Strength | Weakness |
|---------|------------------|----------|----------|
| **TPE** (Tree-structured Parzen) | D ≤ 10, n_trials ≥ 50 | Good with mixed discrete/continuous | Needs ~10·D startup trials |
| **CMA-ES** | D ≥ 20, n_trials ≥ 100 | Fast convergence in smooth continuous spaces | Wasteful on discrete, slow startup |
| **QMC** (Quasi-Monte Carlo / Sobol) | D ≥ 15 + n_trials < 10·D | Space-filling, no cold start | No learning, pure exploration |
| **Auto** | (default) `pick_sampler()` chooses | Best of the above based on D and budget | — |

Override via `sampler_type: "tpe" | "cmaes" | "qmc" | "auto"`.

### 3.3 Pruners (inside Bayesian mode)

| Pruner | When to use | How it works |
|--------|-------------|--------------|
| **MedianPruner** (default) | Single-window objective | Prune trial if its intermediate value < median at same step |
| **HyperbandPruner** (opt-in) | Walk-forward objective with ≥ 3 folds | Bandit-style: run many trials for 1 fold, promote top 1/3 to 2 folds, etc. |
| None | Quick sanity runs | — |

Enable HyperbandPruner: `use_hyperband_pruner=True`.

### 3.4 Parallelisation

| Flag | Effect |
|------|--------|
| `n_jobs=1` | Serial (deterministic with seed) |
| `n_jobs=-1` | Use all CPU cores |
| `use_constant_liar=True` | **Required** for n_jobs > 1 + Bayesian — prevents duplicate sampling |

### 3.5 Warm-start

| Flag | Effect |
|------|--------|
| `warm_start_from_prev=True` | Reuse best N params from previous optimization of same strategy |
| `warm_start_top_n=5` | How many top params to enqueue as seed trials |

### 3.6 Cross-block constraints

Automatically applied to every trial (can't disable; they protect against
obviously invalid configurations):

| Constraint | Rationale |
|------------|-----------|
| MACD `fast_period < slow_period` | Mathematical requirement |
| SL/TP `TP ≥ SL × 1.5` (unless close_by_time present) | Positive risk/reward |
| Breakeven `activation < TP` (clamped to 70% of TP) | Logical ordering |

### 3.7 Multi-criteria scoring

Default objective is a **weighted composite**, not raw Sharpe:

```python
composite = (
    weights.sharpe * normalized(sharpe_ratio) +
    weights.winrate * normalized(win_rate) +
    weights.drawdown * normalized(1 - max_drawdown_pct / 100) +
    weights.profit_factor * normalized(profit_factor) +
    weights.trades * log(trade_count) / log(100)
)

```

Override via `optimize_metric` + `weights` dict.

### 3.8 CSCV (Combinatorially Symmetric Cross-Validation)

Post-hoc **overfitting probability** (PBO):

```

run_cscv=True, cscv_n_splits=16
  → split data into 16 chronological blocks
  → for each combination of 8 blocks train / 8 test:
      - find best params on train
      - check rank on test
  → PBO = P(best-on-train ranks in bottom-half on test)

```

Interpret:
- **PBO < 0.3** → genuine alpha likely
- **PBO > 0.7** → overfit; optimization is memorising history

### 3.9 Guided-Transfer Score (GT-Score)

Post-hoc robustness metric (neighbourhood stability):

```

gt_score_top_n=5, gt_score_neighbors=20, gt_score_epsilon=0.05
  → for each of top N results:
      perturb each param by ±epsilon fraction of range
      run 20 perturbed backtests
      compute mean(sharpe) and std(sharpe)
  → robust_score = mean − λ·std

```

High GT-Score = flat, stable optimum. Low GT-Score = sharp, fragile peak.

---

## 4. Hardening presets (UI buttons)

Strategy Builder has **4 one-click preset buttons** that set multiple
flags atomically. Use them instead of wiring checkboxes manually.

### 🔍 Coarse (scout)

```json
{
  "method": "random",
  "n_trials": 200,
  "sampler_type": "qmc",
  "use_constant_liar": false,
  "use_hyperband_pruner": false,
  "apply_overfit_guards": false,
  "run_post_grid_refine": false,
  "run_cscv": false
}

```

**Goal:** evenly sample the full space; identify promising regions.
**Runtime:** 10–30 min on 6-mo 15m data.

### 🎯 Main (primary Bayesian)

```json
{
  "method": "bayesian",
  "n_trials": 500,
  "sampler_type": "auto",
  "use_constant_liar": true,
  "use_hyperband_pruner": true,
  "apply_overfit_guards": false,
  "run_post_grid_refine": false,
  "run_cscv": false,
  "n_jobs": -1
}

```

**Goal:** focused Bayesian search, parallel, with WF-aware pruning.
**Runtime:** 30–90 min.

### 🔥 Refine (polish top-5)

```json
{
  "method": "bayesian",
  "n_trials": 300,
  "sampler_type": "tpe",
  "use_constant_liar": true,
  "use_hyperband_pruner": true,
  "apply_overfit_guards": false,
  "run_post_grid_refine": true,
  "post_grid_top_k": 5,
  "post_grid_pct": 0.20,
  "post_grid_steps": 3,
  "post_grid_max_evals": 500
}

```

**Goal:** Bayesian + dense local grid around top 5 — catches sharp peaks.
**Runtime:** 20–60 min (Bayesian) + 5–15 min (refine).
**When you'll see the biggest Sharpe lift over pre-2026-04-18 baseline.**

### ✅ Confirm (final validation)

```json
{
  "method": "bayesian",
  "n_trials": 300,
  "sampler_type": "tpe",
  "use_constant_liar": true,
  "use_hyperband_pruner": true,
  "apply_overfit_guards": true,
  "overfit_guard_min_trades": 30,
  "overfit_guard_max_drawdown_pct": 50,
  "overfit_guard_min_profit_factor": 1.0,
  "run_post_grid_refine": true,
  "run_cscv": true,
  "cscv_n_splits": 16,
  "gt_score_top_n": 5
}

```

**Goal:** every statistical check on; promote survivors to live testing.
**Runtime:** 60–180 min (CSCV is the expensive part).

---

## 5. API reference

### 5.1 Start optimization

```

POST /api/v1/strategy-builder/strategies/{strategy_id}/optimize
Content-Type: application/json

```

**Core fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `symbol` | `str` | — | e.g. `"BTCUSDT"` |
| `interval` | `str` | — | `"1"` `"5"` `"15"` `"30"` `"60"` `"240"` `"D"` `"W"` `"M"` |
| `start_date` | `str` (ISO) | — | e.g. `"2025-01-01"` |
| `end_date` | `str` (ISO) | — | e.g. `"2025-06-01"` |
| `method` | `str` | `"bayesian"` | `grid` \| `random` \| `bayesian` \| `genetic` |
| `n_trials` | `int` | `200` | Bayesian/random budget |
| `n_jobs` | `int` | `1` | Parallel workers (-1 = all cores) |
| `timeout_seconds` | `int` | `3600` | Hard stop |
| `initial_capital` | `float` | `10000.0` | Starting capital |
| `commission_value` | `float` | `0.0007` | **DO NOT CHANGE** (TradingView parity) |

**Hardening fields (all opt-in):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sampler_type` | `str` | `"auto"` | `auto` \| `tpe` \| `cmaes` \| `qmc` |
| `use_constant_liar` | `bool` | `false` | **Must be true** when `n_jobs > 1` + Bayesian |
| `use_hyperband_pruner` | `bool` | `false` | Better pruning when using walk-forward |
| `apply_overfit_guards` | `bool` | `false` | Post-filter annotation |
| `overfit_guard_min_trades` | `int \| null` | `null` (→30) | Min trade count threshold |
| `overfit_guard_max_drawdown_pct` | `float \| null` | `null` (→50) | Max acceptable drawdown |
| `overfit_guard_min_profit_factor` | `float \| null` | `null` (→1.0) | Min PF threshold |
| `run_post_grid_refine` | `bool` | `false` | Run local grid around top-K |
| `post_grid_top_k` | `int` | `5` | How many top results to refine |
| `post_grid_pct` | `float` | `0.20` | Half-width of local box |
| `post_grid_steps` | `int` | `3` | Grid resolution per dim |
| `post_grid_max_evals` | `int` | `500` | Hard cap on refinement budget |
| `run_cscv` | `bool` | `false` | Post-hoc overfit probability (PBO) |
| `cscv_n_splits` | `int` | `16` | CSCV chronological splits |
| `gt_score_top_n` | `int` | `5` | GT-Score analyzer budget |
| `gt_score_neighbors` | `int` | `20` | Perturbations per result |
| `gt_score_epsilon` | `float` | `0.05` | Perturbation fraction |

**Response (202):**

```json
{
  "optimization_id": 42,
  "status": "PENDING",
  "strategy_id": 1,
  "estimated_runtime_seconds": 1800
}

```

### 5.2 Poll progress

```

GET /api/v1/strategy-builder/strategies/{strategy_id}/optimizations/{opt_id}

```

```json
{
  "id": 42,
  "status": "RUNNING",                // PENDING | RUNNING | COMPLETED | FAILED
  "progress": {
    "completed_trials": 120,
    "total_trials": 500,
    "current_best_sharpe": 1.87,
    "stage": "bayesian"               // bayesian | post_grid_refine | overfit_guards | cscv
  },
  "started_at": "2026-04-18T18:00:00Z"
}

```

### 5.3 Cancel

```

POST /api/v1/strategy-builder/strategies/{strategy_id}/optimizations/{opt_id}/cancel

```

### 5.4 Get results (COMPLETED)

```

GET /api/v1/strategy-builder/strategies/{strategy_id}/optimizations/{opt_id}

```

```json
{
  "id": 42,
  "status": "COMPLETED",
  "results": {
    "top_results": [
      {
        "rank": 1,
        "params": {"rsi_1.period": 14, "sltp_1.stop_loss_percent": 2.5, ...},
        "metrics": {"sharpe_ratio": 2.13, "max_drawdown_pct": 12.4, ...},
        "composite_score": 0.87,
        "guard_passed": true,              // if apply_overfit_guards=true
        "guard_violations": [],
        "refined_from_trial": null,        // or original rank if this came from post-grid
        "gt_score": 0.72                   // if GT-Score ran
      },
      ...
    ],
    "all_trials": [...],                   // full history
    "cscv_pbo": 0.23,                      // if run_cscv=true
    "study_stats": {
      "total_trials": 520,                 // 500 bayesian + 20 refine
      "pruned_trials": 87,                 // HyperbandPruner activity
      "refine_trials": 20
    }
  }
}

```

### 5.5 Apply best params

```

POST /api/v1/optimizations/{opt_id}/apply
{"rank": 1, "target_strategy_id": 5}

```

Clones the strategy with the chosen param set. Target strategy must
already exist; optimizer does not create new strategy rows.

---

## 6. Feature interaction matrix

| If enabling... | You should also enable... | You cannot combine with... |
|----------------|---------------------------|----------------------------|
| `n_jobs > 1` | `use_constant_liar=true` | — |
| `wf_validation=true` | `use_hyperband_pruner=true` (for 3× speed-up) | `pruner=None` |
| `run_post_grid_refine` | `method=bayesian` (grid-only refine wastes calls) | — |
| `apply_overfit_guards` | `wf_validation` (guards are noisy without it) | — |
| `run_cscv` | `n_trials ≥ 300` (CSCV needs population) | Very slow; use only for final confirm |
| `method=genetic` | `population_size ≥ 50` | `warm_start_from_prev` (incompatible) |

---

## 7. Recommended workflows

### 7.1 New strategy (no priors)

```

1. Coarse preset (200 trials, QMC)
   → identify top-10 param regions
2. Main preset (500 trials, Bayesian, warm-start from step 1)
   → converge to best 10
3. Confirm preset (300 trials + CSCV + guards)
   → filter survivors; deploy those with guard_passed && PBO<0.3

```

### 7.2 Iterating on existing strategy

```

1. Main preset, warm_start_from_prev=true
   → builds on last known good params
2. If best Sharpe doesn't improve by > 10 %:
     switch to Refine preset
     (post-grid around previous best)
3. Confirm preset if you're about to deploy

```

### 7.3 Large space (D ≥ 25)

```

1. Coarse preset, n_trials=500, sampler=qmc
   → full coverage
2. Main preset, sampler=cmaes, n_trials=2000, n_jobs=-1
   → CMA-ES loves large continuous spaces
3. Confirm with post-grid refine only (skip CSCV if budget-constrained)

```

### 7.4 Noisy / shoft history (< 3 months)

```

method=random (not Bayesian — not enough data for priors)
n_trials=300
wf_validation=false (not enough data for folds)
apply_overfit_guards=true (critical!)
run_cscv=true, cscv_n_splits=8

```

Treat results with caution; live-test before capital allocation.

---

## 8. Output schema

`Optimization.results` JSON structure:

```jsonc
{
  "top_results": [
    {
      "rank": 1,
      "trial_number": 123,
      "params": { /* flattened block_id.param_key → value */ },
      "metrics": {
        "sharpe_ratio": 2.13,
        "sortino_ratio": 3.01,
        "calmar_ratio": 1.72,
        "max_drawdown_pct": 12.4,
        "win_rate": 0.58,
        "profit_factor": 1.83,
        "trade_count": 147,
        "total_return_pct": 28.6,
        /* ... 166 metrics total */
      },
      "composite_score": 0.87,

      // --- Hardening annotations (present only if flag enabled) ---
      "guard_passed": true,
      "guard_violations": [],            // or ["min_trades:<30", ...]
      "refined_from_trial": null,        // or original_rank: int
      "gt_score": 0.72,
      "gt_score_std": 0.15
    }
  ],

  "all_trials": [ /* every trial with params + metrics */ ],

  "study_stats": {
    "total_trials": 520,
    "completed_trials": 433,
    "pruned_trials": 87,
    "failed_trials": 0,
    "bayesian_trials": 500,
    "refine_trials": 20,
    "best_trial_number": 412,
    "elapsed_seconds": 2143
  },

  // --- Only present if run_cscv=true ---
  "cscv": {
    "pbo": 0.23,
    "performance_degradation_pct": -8.4,
    "stochastic_dominance": true
  },

  // --- Only present if GT-Score ran ---
  "gt_score_analysis": {
    "top_results_analyzed": 5,
    "most_robust_rank": 3,               // rank with highest gt_score
    "fragility_warnings": ["rank_1:std>0.30"]
  }
}

```

---

## 9. Troubleshooting

### "Optimization returned same result as before enabling hardening"

All hardening flags are **opt-in, default false**. Verify your request
actually set them:

```powershell

# Inspect a completed optimization

Invoke-RestMethod "http://localhost:8000/api/v1/strategy-builder/strategies/1/optimizations/42" `
  | Select-Object -ExpandProperty request_params `
  | Select-Object use_hyperband_pruner, apply_overfit_guards, run_post_grid_refine

```

If all three are `False` — the UI didn't send the flags. Click a preset
button in the UI, or add them explicitly in the API call.

### "n_jobs > 1 gives same results every time / duplicates"

Set `use_constant_liar=true`. Without it, parallel workers all query the
same posterior and converge to the same point.

### "Bayesian stuck on 1 region; missing obvious better params elsewhere"

Run **Coarse → Main → Refine** sequence (not just Main). Bayesian is a
local improver; it needs a good starting distribution.

### "Sharpe is great but live deployment underperforms"

Enable `apply_overfit_guards` + `run_cscv`. If `guard_passed=false` or
`cscv_pbo>0.5`, the strategy is almost certainly overfit.

### "HyperbandPruner makes results non-reproducible"

Normal — it prunes aggressively and is more noisy than MedianPruner.
For reproducibility studies, set `use_hyperband_pruner=false`.

### "CSCV is too slow"

CSCV with 16 splits runs ~100 extra backtests. Reduce to `cscv_n_splits=8`,
or only enable for final Confirm runs.

---

## 10. Glossary

| Term | Definition |
|------|-----------|
| **D** | Number of optimizable parameters (dimension of search space) |
| **TPE** | Tree-structured Parzen Estimator; Optuna's default Bayesian sampler |
| **CMA-ES** | Covariance Matrix Adaptation Evolution Strategy; continuous-space optimizer |
| **QMC / Sobol** | Quasi-Monte Carlo; low-discrepancy space-filling sequence |
| **HyperbandPruner** | Bandit-style multi-fidelity pruner; aggressive early stopping |
| **constant_liar** | Parallel Bayesian trick: feed pending trials into posterior with pessimistic imputed score |
| **Walk-forward** | Time-series cross-validation with chronological train/test splits |
| **CSCV / PBO** | Combinatorially Symmetric CV; measures Probability of Backtest Overfitting |
| **GT-Score** | Guided-Transfer Score; neighbourhood robustness metric |
| **Composite score** | Multi-criteria weighted aggregation used for ranking (not the Bayesian objective) |
| **Post-grid refine** | Local Cartesian grid around top-K Bayesian results |
| **Overfit guard** | Hard threshold check (min_trades, max_drawdown, min_pf) flagging suspicious results |
| **Warm-start** | Seeding the sampler with prior best params via `enqueue_trial` |
| **Refinement trial** | A trial added during post-grid refine stage (carries `refined_from_trial`) |

---

## Appendix A — Quick API snippets

### Minimal request (all hardening off — baseline pre-2026-04-18)

```json
{
  "symbol": "BTCUSDT",
  "interval": "15",
  "start_date": "2025-01-01",
  "end_date": "2025-06-01",
  "method": "bayesian",
  "n_trials": 200
}

```

### Full hardening on (Confirm preset equivalent)

```json
{
  "symbol": "BTCUSDT",
  "interval": "15",
  "start_date": "2025-01-01",
  "end_date": "2025-06-01",
  "method": "bayesian",
  "n_trials": 500,
  "n_jobs": -1,
  "sampler_type": "auto",
  "use_constant_liar": true,
  "use_hyperband_pruner": true,
  "apply_overfit_guards": true,
  "overfit_guard_min_trades": 30,
  "overfit_guard_max_drawdown_pct": 50,
  "overfit_guard_min_profit_factor": 1.0,
  "run_post_grid_refine": true,
  "post_grid_top_k": 5,
  "post_grid_pct": 0.20,
  "post_grid_steps": 3,
  "post_grid_max_evals": 500,
  "run_cscv": true,
  "cscv_n_splits": 16,
  "gt_score_top_n": 5,
  "gt_score_neighbors": 20,
  "gt_score_epsilon": 0.05,
  "wf_validation": true,
  "wf_n_folds": 6
}

```

### Reuse prior best (warm-start)

```json
{
  "method": "bayesian",
  "n_trials": 200,
  "warm_start_from_prev": true,
  "warm_start_top_n": 5,
  "use_hyperband_pruner": true,
  "run_post_grid_refine": true
}

```

---

## Appendix B — File map

| Feature | Primary source file | Tests |
|---------|---------------------|-------|
| Request/response models | `backend/api/routers/strategy_builder/router.py` | `tests/backend/api/routers/test_strategy_builder*.py` |
| Bayesian search | `backend/optimization/builder_optimizer.py::run_builder_optuna_search` | `tests/test_builder_optimizer.py` |
| Grid/random | `backend/optimization/builder_optimizer.py::run_builder_grid_search` | `tests/test_optimizer_performance.py` |
| Sampler routing | `backend/optimization/sampler_factory.py` | `tests/backend/optimization/test_sampler_factory.py` |
| Overfit guards | `backend/optimization/overfit_guards.py` | `tests/backend/optimization/test_overfit_guards.py` |
| Post-grid refine | `backend/optimization/post_grid.py` | `tests/backend/optimization/test_post_grid.py` |
| Walk-forward | `backend/optimization/walk_forward.py` | `tests/backend/optimization/test_walk_forward.py` |
| CSCV / PBO | `backend/optimization/cscv.py` | `tests/backend/optimization/test_cscv*.py` |
| GT-Score | `backend/optimization/scoring.py` | `tests/test_optimization_quality.py` |
| Composite ranking | `backend/optimization/scoring.py::calculate_composite_score` | ditto |
| UI presets | `frontend/js/pages/optimization_panels.js::applyHardeningPreset` | `frontend/tests/...` |

---

**End of document.**
