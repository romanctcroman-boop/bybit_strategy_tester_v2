# ТЗ: Улучшение качества оптимизации стратегий

**Версия:** 1.0  
**Дата:** 2026-04-09  
**Статус:** Готово к реализации  
**Приоритет реализации:** P0 → P1 → P2

---

## Содержание

1. [Контекст и мотивация](#1-контекст-и-мотивация)
2. [P0-1: Фикс BIPOP CMA-ES (баг)](#2-p0-1-фикс-bipop-cma-es-баг)
3. [P0-2: OOS Validation Split](#3-p0-2-oos-validation-split)
4. [P1-1: GT-Score Post-Processing](#4-p1-1-gt-score-post-processing)
5. [P1-2: fANOVA Parameter Importance](#5-p1-2-fanova-parameter-importance)
6. [P1-3: AutoSampler (Optuna 4.6)](#6-p1-3-autosampler-optuna-46)
7. [P2-1: CSCV Validation](#7-p2-1-cscv-validation)
8. [P2-2: Multi-Objective Anti-Overfit](#8-p2-2-multi-objective-anti-overfit)
9. [P2-3: Deflated Sharpe Ratio](#9-p2-3-deflated-sharpe-ratio)
10. [Изменения API/Frontend](#10-изменения-apifrontend)
11. [Тесты](#11-тесты)
12. [Ограничения и допущения](#12-ограничения-и-допущения)

---

## 1. Контекст и мотивация

### 1.1 Текущее состояние

Оптимизатор стратегий (`backend/optimization/builder_optimizer.py`) реализует:
- Grid search / Random search / Bayesian (TPE, CMA-ES, GP) через Optuna
- 200 trials Bayesian ≈ 36.5 минут на RSI+ST стратегию с 10 параметрами
- Progress tracking через `.run/optimizer_progress.json`
- Native constraints через `_constraints_func` + `trial.user_attrs["constraint"]`
- Warm-start через `study.enqueue_trial()`

### 1.2 Выявленные проблемы

| # | Проблема | Тип | Влияние |
|---|---------|-----|---------|
| B1 | `restart_strategy="ipop"` deprecated в Optuna 4.4.0 → silently ignored | Баг | CMA-ES не перезапускается при стагнации |
| B2 | 200 trials за 3 месяца данных = гарантированный overfitting (Bailey-Borwein: N≈15-22) | Методологическая | best_score содержит selection bias |
| G1 | Нет OOS валидации → нельзя отличить параметры от артефактов | Пробел | Ложные сигналы о качестве стратегии |
| G2 | Нет оценки устойчивости параметров (GT-Score) | Пробел | Острые пики ≠ устойчивые стратегии |
| G3 | Нет важности параметров после оптимизации | Пробел | Неизвестно какие параметры ключевые |

### 1.3 Математическое обоснование (Bailey-Borwein 2014)

```
N_indep ≈ (T_years × 252) / avg_trade_holding_days

Данные: 3 месяца (типичный сеанс)  →  N_indep ≈ 11-22
Наши 200 trials  →  overfitting в 9-18× раз

Вывод: OOS split — не улучшение, а математически необходимое условие
       для того, чтобы best_score имел хоть какое-то статистическое значение.
```

---

## 2. P0-1: Фикс BIPOP CMA-ES (баг)

### 2.1 Проблема

**Файл:** `backend/optimization/builder_optimizer.py`  
**Строки:** 3683–3705  
**Симптом:** `restart_strategy="ipop"` передаётся в `CmaEsSampler`, но начиная с Optuna 4.4.0 этот параметр deprecated и **silently ignored** (no warning, no error). IPOP restart не работает.

**Changelog Optuna 4.4.0:**
> "CmaEsSampler's restart_strategy parameter is deprecated. The ipop restart functionality has been moved to OptunaHub as RestartCmaEsSampler."

### 2.2 Решение

Заменить `CmaEsSampler(restart_strategy="ipop", ...)` на `optunahub.RestartCmaEsSampler(restart_strategy="bipop", ...)`.

**Почему BIPOP лучше IPOP:**
- IPOP: при стагнации только удваивает размер популяции (один режим)
- BIPOP: адаптивно выбирает между большой популяцией (глобальный поиск) и малой (локальное уточнение) — Hansen 2009, превосходство на 15/24 функциях BBOB benchmark

### 2.3 Точные изменения

**Файл:** `backend/optimization/builder_optimizer.py`

**Шаг 1.** Добавить импорт в блок `try/except ImportError` (строки ~3618–3630, внутри функции `run_builder_optuna_search`):

```python
# БЫЛО (строки 3618-3630):
try:
    import optuna
    from optuna.samplers import CmaEsSampler, RandomSampler, TPESampler

    try:
        from optuna.samplers import QMCSampler  # Optuna ≥ 3.0
    except ImportError:
        QMCSampler = None

    try:
        from optuna.samplers import GPSampler  # Optuna ≥ 3.6 native GP
    except ImportError:
        GPSampler = None
except ImportError:
    ...

# СТАЛО — добавить блок RestartCmaEsSampler:
try:
    import optuna
    from optuna.samplers import CmaEsSampler, RandomSampler, TPESampler

    try:
        from optuna.samplers import QMCSampler  # Optuna ≥ 3.0
    except ImportError:
        QMCSampler = None

    try:
        from optuna.samplers import GPSampler  # Optuna ≥ 3.6 native GP
    except ImportError:
        GPSampler = None

    try:
        import optunahub as _optunahub
        _restart_cmaes_module = _optunahub.load_module("samplers/restart_cmaes")
        RestartCmaEsSampler = _restart_cmaes_module.RestartCmaEsSampler
    except Exception:
        RestartCmaEsSampler = None  # fallback to standard CmaEsSampler
except ImportError:
    ...
```

**Шаг 2.** Изменить блок создания CMA-ES sampler (строки ~3683–3705):

```python
# БЫЛО:
_cmaes_kwargs: dict[str, Any] = {
    "seed": 42,
    "n_startup_trials": _cmaes_startup,
    "restart_strategy": "ipop",      # ← DEPRECATED, silently ignored
    "constraints_func": _constraints_func,
}
if _cmaes_seed_sampler is not None:
    _cmaes_kwargs["independent_sampler"] = _cmaes_seed_sampler
try:
    sampler = CmaEsSampler(with_margin=True, **_cmaes_kwargs)
except TypeError:
    sampler = CmaEsSampler(**_cmaes_kwargs)

# СТАЛО:
if RestartCmaEsSampler is not None:
    # OptunaHub RestartCmaEsSampler с BIPOP стратегией (лучше IPOP: адаптивный выбор
    # размера популяции между большой/малой в зависимости от бюджета).
    # BIPOP = Hansen 2009, превосходит IPOP на 15/24 функциях BBOB benchmark.
    _restart_cmaes_kwargs: dict[str, Any] = {
        "seed": 42,
        "n_startup_trials": _cmaes_startup,
        "restart_strategy": "bipop",
        "constraints_func": _constraints_func,
    }
    if _cmaes_seed_sampler is not None:
        _restart_cmaes_kwargs["independent_sampler"] = _cmaes_seed_sampler
    try:
        sampler = RestartCmaEsSampler(with_margin=True, **_restart_cmaes_kwargs)
    except TypeError:
        sampler = RestartCmaEsSampler(**_restart_cmaes_kwargs)
    logger.info("CMA-ES sampler: BIPOP restart via OptunaHub RestartCmaEsSampler")
else:
    # Fallback: стандартный CmaEsSampler без restart (deprecation warning уже removed)
    _cmaes_kwargs: dict[str, Any] = {
        "seed": 42,
        "n_startup_trials": _cmaes_startup,
        "constraints_func": _constraints_func,
    }
    if _cmaes_seed_sampler is not None:
        _cmaes_kwargs["independent_sampler"] = _cmaes_seed_sampler
    try:
        sampler = CmaEsSampler(with_margin=True, **_cmaes_kwargs)
    except TypeError:
        sampler = CmaEsSampler(**_cmaes_kwargs)
    logger.warning("OptunaHub not available — CMA-ES without restart (install: pip install optunahub)")
```

**Шаг 3.** Обновить docstring функции `run_builder_optuna_search` (строка ~3606):

```python
# БЫЛО:
sampler_type: "tpe", "random", "cmaes", or "gp"

# СТАЛО:
sampler_type: "tpe", "random", "cmaes" (BIPOP restart via OptunaHub), "gp", or "auto" (Optuna 4.6+)
```

### 2.4 Зависимости

```bash
pip install optunahub
# optunahub подтягивает samplers/restart_cmaes с GitHub при первом вызове load_module()
# Интернет нужен только один раз — модуль кешируется локально
```

Добавить в `requirements.txt` или `pyproject.toml`:
```
optunahub>=0.1.0
```

### 2.5 Fallback-поведение

Если `optunahub` недоступен (offline, нет интернета при первом запуске) → graceful degradation к стандартному `CmaEsSampler` без restart + `logger.warning`. Оптимизация не ломается.

---

## 3. P0-2: OOS Validation Split

### 3.1 Проблема

Все текущие методы оптимизации (Grid, Random, Bayesian) используют **весь** переданный OHLCV для оптимизации. Результат best_score статистически невалиден без независимого out-of-sample теста.

**Математика (Bailey-Borwein):** Для 3 месяцев данных и 200 трайлов вероятность overfitting ≈ 85-95%.

### 3.2 Архитектурное решение

OOS split выполняется **в router** перед передачей ohlcv в оптимизатор. Оптимизатор получает только IS данные. После оптимизации — автоматический rerún топ-N на OOS данных.

**Принцип "sealed OOS":** OOS данные не должны влиять ни на один выбор параметров. Router делает split один раз, OOS не передаётся в optimizer никак.

### 3.3 Параметры OOS split

| Параметр | Тип | Default | Описание |
|---------|-----|---------|---------|
| `oos_ratio` | float | 0.2 | Доля данных для OOS (последние 20%) |
| `oos_min_bars` | int | 200 | Минимальное кол-во баров для OOS (иначе skip) |
| `run_oos_validation` | bool | False | Включить OOS validation (opt-in) |

OOS validation **opt-in** (default=False) чтобы не ломать существующие workflow.

### 3.4 Изменения: `backend/optimization/builder_optimizer.py`

**Добавить новую функцию** после строки ~100 (в секцию утилит):

```python
def split_ohlcv_is_oos(
    ohlcv: pd.DataFrame,
    oos_ratio: float = 0.2,
    oos_min_bars: int = 200,
    warmup_bars: int = 200,
) -> tuple[pd.DataFrame, pd.DataFrame | None, dict]:
    """
    Split OHLCV into In-Sample (IS) and Out-of-Sample (OOS) segments.

    The OOS segment is always the LAST oos_ratio fraction of the data.
    IS segment is everything before OOS.

    The OOS segment gets an additional `warmup_bars` prepended from the IS tail
    so that indicator warm-up (Wilder RSI, Supertrend) is available for OOS
    signal generation. These warm-up bars are sliced off before OOS backtest
    (via warmup_cutoff in config_params), preserving the "sealed OOS" invariant.

    Args:
        ohlcv: Full OHLCV DataFrame with DatetimeIndex.
        oos_ratio: Fraction of bars to reserve for OOS (default 0.2 = 20%).
        oos_min_bars: If OOS segment would have fewer bars, return None for OOS
                      (OOS validation skipped, IS = full dataset).
        warmup_bars: Extra bars prepended to OOS for indicator warm-up.

    Returns:
        Tuple of:
            - is_ohlcv: IS DataFrame (used for optimization)
            - oos_ohlcv: OOS DataFrame with warmup prepended, or None if too short
            - split_info: Dict with split metadata for response/logging
    """
    n = len(ohlcv)
    n_oos = max(int(n * oos_ratio), 1)
    n_is = n - n_oos

    if n_oos < oos_min_bars:
        return ohlcv, None, {
            "oos_skipped": True,
            "reason": f"OOS segment too short: {n_oos} bars < oos_min_bars={oos_min_bars}",
            "n_total": n,
            "n_is": n,
            "n_oos": 0,
        }

    is_ohlcv = ohlcv.iloc[:n_is]

    # OOS with warmup prepended (for indicator convergence)
    warmup_start = max(0, n_is - warmup_bars)
    oos_with_warmup = ohlcv.iloc[warmup_start:]
    oos_cutoff_ts = ohlcv.index[n_is]  # first bar of actual OOS

    split_info = {
        "oos_skipped": False,
        "n_total": n,
        "n_is": n_is,
        "n_oos": n_oos,
        "n_oos_warmup": n_is - warmup_start,
        "is_start": str(ohlcv.index[0]),
        "is_end": str(ohlcv.index[n_is - 1]),
        "oos_start": str(oos_cutoff_ts),
        "oos_end": str(ohlcv.index[-1]),
        "oos_cutoff_ts": str(oos_cutoff_ts),
    }

    return is_ohlcv, oos_with_warmup, split_info
```

**Добавить новую функцию** для OOS re-run (после `split_ohlcv_is_oos`):

```python
def run_oos_validation(
    top_results: list[dict[str, Any]],
    base_graph: dict[str, Any],
    oos_ohlcv: pd.DataFrame,
    config_params: dict[str, Any],
    oos_cutoff_ts: str,
    n_top: int = 5,
) -> list[dict[str, Any]]:
    """
    Re-run top-N IS results on OOS data and attach OOS metrics.

    Mutates top_results in-place: adds "oos_*" keys to each result dict.
    Results that fail OOS backtest get oos_score=None.

    Args:
        top_results: List of result dicts from IS optimization (sorted by IS score).
        base_graph: Base strategy graph.
        oos_ohlcv: OOS DataFrame (with warmup prepended).
        config_params: Backtest config params (IS version — will clone with OOS cutoff).
        oos_cutoff_ts: Timestamp string where actual OOS starts (warmup cutoff).
        n_top: How many top results to validate (default 5).

    Returns:
        top_results with OOS metrics attached.
    """
    oos_config = {**config_params, "warmup_cutoff": oos_cutoff_ts}

    for result in top_results[:n_top]:
        params = result.get("params", {})
        if not params:
            continue

        modified_graph = clone_graph_with_params(base_graph, params)
        oos_result = run_builder_backtest(modified_graph, oos_ohlcv, oos_config)

        if oos_result is None:
            result["oos_score"] = None
            result["oos_sharpe_ratio"] = None
            result["oos_total_return"] = None
            result["oos_max_drawdown"] = None
            result["oos_win_rate"] = None
            result["oos_total_trades"] = None
            result["oos_degradation_pct"] = None
            continue

        oos_score = calculate_composite_score(
            oos_result,
            config_params.get("optimize_metric", "sharpe_ratio"),
        )
        is_score = result.get("score", 0) or 0

        result["oos_score"] = oos_score
        result["oos_sharpe_ratio"] = oos_result.get("sharpe_ratio")
        result["oos_total_return"] = oos_result.get("total_return")
        result["oos_max_drawdown"] = oos_result.get("max_drawdown")
        result["oos_win_rate"] = oos_result.get("win_rate")
        result["oos_total_trades"] = oos_result.get("total_trades")

        # OOS degradation: насколько хуже OOS vs IS (в %)
        # Положительное число = ухудшение, отрицательное = OOS лучше IS
        if abs(is_score) > 1e-9:
            result["oos_degradation_pct"] = round((is_score - oos_score) / abs(is_score) * 100, 1)
        else:
            result["oos_degradation_pct"] = None

    return top_results
```

### 3.5 Изменения: `backend/api/routers/strategy_builder/router.py`

**Строка ~1897 (перед вызовом `run_builder_optuna_search`):**

Добавить OOS split логику в блок `if request.method == "bayesian":`:

```python
if request.method == "bayesian":
    custom_ranges = request.parameter_ranges or None
    from backend.optimization.builder_optimizer import _merge_ranges, split_ohlcv_is_oos

    active_specs = _merge_ranges(all_params, custom_ranges) if custom_ranges else all_params

    # OOS split (opt-in через request.run_oos_validation)
    _oos_ohlcv = None
    _oos_split_info: dict = {}
    if getattr(request, "run_oos_validation", False):
        ohlcv_for_opt, _oos_ohlcv, _oos_split_info = split_ohlcv_is_oos(
            ohlcv,
            oos_ratio=getattr(request, "oos_ratio", 0.2),
            oos_min_bars=200,
        )
        if _oos_split_info.get("oos_skipped"):
            logger.warning(f"OOS skipped: {_oos_split_info['reason']}")
            ohlcv_for_opt = ohlcv
    else:
        ohlcv_for_opt = ohlcv

    result = await asyncio.to_thread(
        run_builder_optuna_search,
        base_graph=strategy_graph,
        ohlcv=ohlcv_for_opt,       # ← IS only (или full если OOS disabled)
        param_specs=active_specs,
        ...
    )

    # OOS validation после оптимизации
    if _oos_ohlcv is not None and isinstance(result, dict) and result.get("top_results"):
        from backend.optimization.builder_optimizer import run_oos_validation
        _oos_config = {**config_params}
        result["top_results"] = run_oos_validation(
            top_results=result["top_results"],
            base_graph=strategy_graph,
            oos_ohlcv=_oos_ohlcv,
            config_params=_oos_config,
            oos_cutoff_ts=_oos_split_info["oos_cutoff_ts"],
            n_top=5,
        )
        result["oos_split_info"] = _oos_split_info
```

### 3.6 Изменения: `backend/api/routers/strategy_builder/router.py` — Request model

Найти класс `OptimizationRequest` (или аналог) и добавить поля:

```python
class BuilderOptimizeRequest(BaseModel):
    # ... existing fields ...
    
    # OOS Validation (opt-in)
    run_oos_validation: bool = False
    oos_ratio: float = Field(default=0.2, ge=0.1, le=0.4,
                              description="OOS fraction (0.1-0.4). Default 0.2 = last 20% of data.")
```

### 3.7 Формат ответа с OOS

Каждый результат в `top_results[]` получает дополнительные поля:

```json
{
  "params": {...},
  "score": 0.0817,
  "sharpe_ratio": 1.23,
  
  "oos_score": 0.0621,
  "oos_sharpe_ratio": 0.89,
  "oos_total_return": 12.4,
  "oos_max_drawdown": 8.1,
  "oos_win_rate": 54.2,
  "oos_total_trades": 23,
  "oos_degradation_pct": 24.0
}
```

Корневой уровень ответа получает:
```json
{
  "oos_split_info": {
    "n_is": 3200,
    "n_oos": 800,
    "is_start": "2025-01-01T00:00:00",
    "is_end": "2025-10-05T00:00:00",
    "oos_start": "2025-10-05T00:00:00",
    "oos_end": "2025-12-31T00:00:00"
  }
}
```

### 3.8 Критические ограничения

1. **"Sealed OOS" правило:** OOS данные никогда не передаются в optimizer. Split делается один раз до запуска, OOS хранится в локальной переменной router'а.
2. **`warmup_cutoff`:** OOS OHLCV содержит 200 warmup баров из конца IS. `warmup_cutoff` в `config_params` указывает реальное начало OOS — движок trim'ит warmup перед backtest.
3. **`oos_ratio` фиксируется до запуска:** Не подбирать oos_ratio экспериментально — это создаст мета-overfitting.

---

## 4. P1-1: GT-Score Post-Processing

### 4.1 Суть

GT-Score (Generalization-Testing Score) измеряет устойчивость стратегии в окрестности найденного оптимума. Высокий GT-Score = параметры лежат на "плато" (устойчиво). Низкий GT-Score = параметры на острой вершине (overfitting).

**Источник:** Arxiv 2024 "GT-Score: A New Metric for Evaluating Strategy Generalization in Algorithmic Trading"  
**Заявленный эффект:** 98% улучшение generalization ratio (OOS/IS).

**Формула:**
```
GT-Score = mean(scores_neighbors) / (std(scores_neighbors) + ε)

где neighbors = N случайных perturbations параметров оптимума (±epsilon%)
```

### 4.2 Изменения: `backend/optimization/scoring.py`

Добавить в конец файла:

```python
def calculate_gt_score(
    base_params: dict,
    param_specs: list[dict],
    run_backtest_fn,
    optimize_metric: str = "sharpe_ratio",
    weights: dict | None = None,
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
                         Should be a partial of run_builder_backtest.
        optimize_metric: Metric name for scoring.
        weights: Optional metric weights.
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
                # Integer perturbation: ±1..max(1, delta) steps
                max_step = max(1, int(delta))
                offset = rng.randint(-max_step, max_step)
                new_val = int(val) + offset
                new_val = max(spec["low"], min(spec["high"], new_val))
                perturbed[path] = int(new_val)
            else:
                # Float perturbation: uniform in ±delta
                offset = rng.uniform(-delta, delta)
                new_val = float(val) + offset
                new_val = max(spec["low"], min(spec["high"], new_val))
                # Round to spec step precision
                step = spec.get("step", 0.01)
                n_decimals = max(0, -int(math.floor(math.log10(step))) if step < 1 else 0)
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
```

### 4.3 Изменения: `backend/optimization/builder_optimizer.py`

**В функции `run_builder_optuna_search`** — после строки ~4042 (после `top_results.sort(...)`), добавить GT-Score расчёт:

```python
# GT-Score post-processing (optional, controlled by config_params flag)
if config_params.get("run_gt_score", False) and top_results:
    from backend.optimization.scoring import calculate_gt_score
    import functools

    gt_n = min(config_params.get("gt_score_top_n", 5), len(top_results))
    gt_neighbors = config_params.get("gt_score_neighbors", 20)
    gt_epsilon = config_params.get("gt_score_epsilon", 0.05)

    logger.info(f"GT-Score: evaluating {gt_n} top results × {gt_neighbors} neighbors each")

    for i, result in enumerate(top_results[:gt_n]):
        def _bt_fn(params, _graph=base_graph, _ohlcv=ohlcv, _cfg=config_params):
            modified = clone_graph_with_params(_graph, params)
            r = run_builder_backtest(modified, _ohlcv, _cfg)
            if r is None:
                return None
            return calculate_composite_score(r, optimize_metric, weights)

        gt_info = calculate_gt_score(
            base_params=result["params"],
            param_specs=param_specs,
            run_backtest_fn=_bt_fn,
            optimize_metric=optimize_metric,
            weights=weights,
            n_neighbors=gt_neighbors,
            epsilon=gt_epsilon,
        )
        result.update(gt_info)
        logger.debug(f"GT-Score result[{i}]: {gt_info}")
```

### 4.4 Изменения: Request model

```python
class BuilderOptimizeRequest(BaseModel):
    # ...
    run_gt_score: bool = False
    gt_score_top_n: int = Field(default=5, ge=1, le=20)
    gt_score_neighbors: int = Field(default=20, ge=5, le=100)
    gt_score_epsilon: float = Field(default=0.05, ge=0.01, le=0.2)
```

Добавить в `config_params` в router.py:
```python
config_params["run_gt_score"] = getattr(request, "run_gt_score", False)
config_params["gt_score_top_n"] = getattr(request, "gt_score_top_n", 5)
config_params["gt_score_neighbors"] = getattr(request, "gt_score_neighbors", 20)
config_params["gt_score_epsilon"] = getattr(request, "gt_score_epsilon", 0.05)
```

### 4.5 Производительность

- GT-Score для 5 результатов × 20 neighbors = 100 дополнительных backtest'ов
- При ~1 сек/backtest → +100 секунд к итоговому времени (приемлемо для 36-минутной оптимизации)
- Можно снизить до n_neighbors=10 для быстрого режима

---

## 5. P1-2: fANOVA Parameter Importance

### 5.1 Суть

После завершения Optuna optimization — автоматически вычислить важность каждого параметра через fANOVA algorithm. Результат: какие параметры реально влияют на метрику, какие можно зафиксировать в следующей оптимизации.

### 5.2 Изменения: `backend/optimization/builder_optimizer.py`

**В функции `run_builder_optuna_search`** — добавить после строки ~4070 (после обновления progress):

```python
# fANOVA parameter importance (post-optimization analytics)
param_importance: dict[str, float] = {}
if len(completed_trials) >= 30:  # fANOVA needs enough trials for reliable estimates
    try:
        try:
            from optuna_fast_fanova import FanovaImportanceEvaluator as _FanovaEval
        except ImportError:
            from optuna.importance import FanovaImportanceEvaluator as _FanovaEval

        importance_result = optuna.importance.get_param_importances(
            study,
            evaluator=_FanovaEval(seed=42),
            # Use only feasible trials for importance (infeasible distort the landscape)
            params=None,
        )
        param_importance = {k: round(float(v), 4) for k, v in importance_result.items()}
        logger.info(f"fANOVA param importance: {param_importance}")

        # Tag low-importance params (<5%) — candidates for fixing in next optimization
        low_importance = [p for p, imp in param_importance.items() if imp < 0.05]
        if low_importance:
            logger.info(f"Low-importance params (consider fixing): {low_importance}")

    except Exception as _fanova_err:
        logger.warning(f"fANOVA importance failed (non-critical): {_fanova_err}")
        param_importance = {}
```

**В `return` dict** (строка ~4086) добавить:
```python
return {
    ...
    "param_importance": param_importance,  # fANOVA importance scores
    "param_importance_low": [p for p, v in param_importance.items() if v < 0.05],
    ...
}
```

### 5.3 Зависимости

```bash
pip install optuna-fast-fanova  # faster version for >1000 trials
# Без него — fallback на стандартный FanovaImportanceEvaluator (работает до ~1000 trials)
```

Добавить в `requirements.txt` как optional:
```
optuna-fast-fanova>=0.0.1  # optional, speeds up fANOVA for large studies
```

---

## 6. P1-3: AutoSampler (Optuna 4.6)

### 6.1 Суть

Optuna 4.6 (ноябрь 2025) добавил `AutoSampler` — автоматически выбирает оптимальный sampler на основе характеристик study:
- GPSampler → если `n_trials < 200` и нет multi-objective
- NSGAIISampler → если multi-objective
- TPESampler → по умолчанию

### 6.2 Изменения: `backend/optimization/builder_optimizer.py`

**В блок импорта** (строки ~3618–3630):

```python
try:
    from optuna.samplers import AutoSampler  # Optuna ≥ 4.6
except ImportError:
    AutoSampler = None
```

**В секцию создания sampler** — добавить ветку `sampler_type == "auto"` перед текущими:

```python
if sampler_type == "auto" and AutoSampler is not None:
    # Optuna 4.6 AutoSampler: автоматически выбирает GPSampler/NSGAIISampler/TPESampler
    # на основе размера study, n_trials, наличия multi-objective.
    sampler = AutoSampler(seed=42)
    logger.info("Using Optuna 4.6 AutoSampler (automatic sampler selection)")
elif sampler_type == "auto":
    # Fallback для Optuna < 4.6 — TPE с multivariate
    logger.warning("AutoSampler not available (requires Optuna ≥ 4.6), falling back to TPE")
    sampler_type = "tpe"  # will fall through to TPE block below
```

**В docstring** `sampler_type`:
```
sampler_type: "tpe", "random", "cmaes", "gp", or "auto" (Optuna 4.6+, automatic selection)
```

---

## 7. P2-1: CSCV Validation

### 7.1 Суть

Combinatorially Symmetric Cross-Validation (López de Prado 2018). Создаёт все возможные хронологические разбиения данных, оценивает вероятность overfitting (PBO).

**Эмпирические результаты:** обычный backtest = 68% false positives, CSCV = 22%.

**Формула PBO:**
```
PBO = P(IS-selected strategy performs worse than median OOS strategy)
PBO < 0.05 → статистически robust
PBO > 0.5  → likely overfitted
```

### 7.2 Архитектура

CSCV — отдельный модуль `backend/optimization/cscv.py`. Вызывается опционально после завершения оптимизации для топ-N результатов.

**Вычислительная стоимость:** CSCV с `n_splits=16` и топ-5 результатами = 16 × 5 = 80 backtest'ов.

### 7.3 Новый файл: `backend/optimization/cscv.py`

```python
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

import math
from typing import Any, Callable

import numpy as np
import pandas as pd


def cscv_validation(
    strategies: list[dict[str, Any]],
    ohlcv: pd.DataFrame,
    run_backtest_fn: Callable[[dict, pd.DataFrame], float | None],
    n_splits: int = 16,
    metric_fn: Callable[[dict], float] | None = None,
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
        metric_fn: Optional function to extract scalar metric from strategy dict.
                   If None, uses "score" key.

    Returns:
        Dict with:
            pbo: float — Probability of Backtest Overfitting (0..1)
            pbo_interpretation: str — "robust" / "borderline" / "overfitted"
            n_combinations: int — total partitions evaluated
            split_scores: list[dict] — per-strategy IS vs OOS scores per partition
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
        return {"pbo": None, "pbo_interpretation": "skipped", "reason": "No strategies", "n_combinations": 0}

    # Create n_splits equal chronological sub-periods
    sub_periods = []
    for i in range(n_splits):
        start_idx = i * bars_per_split
        end_idx = start_idx + bars_per_split if i < n_splits - 1 else n
        sub_periods.append(ohlcv.iloc[start_idx:end_idx])

    # For CSCV: iterate over all C(n_splits, n_splits/2) combinations of sub-periods
    # Each combination uses half the sub-periods as IS, the other half as OOS
    # For n_splits=16: C(16,8) = 12870 combinations — computationally expensive.
    # Practical approximation: sample up to max_combinations randomly.
    from itertools import combinations

    half = n_splits // 2
    all_indices = list(range(n_splits))

    # Cap at 200 combinations for speed (still statistically valid approximation)
    max_combinations = 200
    all_combos = list(combinations(all_indices, half))
    if len(all_combos) > max_combinations:
        rng = np.random.default_rng(42)
        chosen_idxs = rng.choice(len(all_combos), size=max_combinations, replace=False)
        sampled_combos = [all_combos[i] for i in chosen_idxs]
    else:
        sampled_combos = all_combos

    # Evaluate each strategy on each IS/OOS partition
    n_is_wins = 0  # IS-selected strategy also wins OOS
    n_is_losses = 0  # IS-selected loses on OOS
    combination_results = []

    for combo in sampled_combos:
        is_indices = set(combo)
        oos_indices = set(all_indices) - is_indices

        is_ohlcv = pd.concat([sub_periods[i] for i in sorted(is_indices)])
        oos_ohlcv = pd.concat([sub_periods[i] for i in sorted(oos_indices)])

        # Score each strategy on IS
        is_scores = []
        for strat in strategies:
            s = run_backtest_fn(strat["params"], is_ohlcv)
            is_scores.append(s if s is not None else float("-inf"))

        # IS winner = strategy with highest IS score
        best_is_idx = int(np.argmax(is_scores))

        # Score each strategy on OOS
        oos_scores = []
        for strat in strategies:
            s = run_backtest_fn(strat["params"], oos_ohlcv)
            oos_scores.append(s if s is not None else float("-inf"))

        # IS winner's OOS rank
        is_winner_oos_score = oos_scores[best_is_idx]
        oos_median = float(np.median([s for s in oos_scores if s != float("-inf")] or [0.0]))

        # PBO logic: IS winner fails if it scores below OOS median
        if is_winner_oos_score < oos_median:
            n_is_losses += 1
        else:
            n_is_wins += 1

        combination_results.append({
            "is_winner_idx": best_is_idx,
            "is_winner_oos_score": is_winner_oos_score,
            "oos_median": oos_median,
            "is_win": is_winner_oos_score >= oos_median,
        })

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
```

### 7.4 Интеграция в `run_builder_optuna_search`

Добавить опциональный вызов после GT-Score (строка ~4070):

```python
cscv_result: dict = {}
if config_params.get("run_cscv", False) and len(top_results) >= 2:
    from backend.optimization.cscv import cscv_validation

    def _cscv_backtest_fn(params, sub_ohlcv, _graph=base_graph, _cfg=config_params):
        modified = clone_graph_with_params(_graph, params)
        r = run_builder_backtest(modified, sub_ohlcv, _cfg)
        if r is None:
            return None
        return calculate_composite_score(r, optimize_metric, weights)

    cscv_result = cscv_validation(
        strategies=top_results[:10],  # top-10 candidates
        ohlcv=ohlcv,
        run_backtest_fn=_cscv_backtest_fn,
        n_splits=config_params.get("cscv_n_splits", 16),
    )
    logger.info(f"CSCV result: PBO={cscv_result.get('pbo')}, {cscv_result.get('pbo_interpretation')}")
```

---

## 8. P2-2: Multi-Objective Anti-Overfit

### 8.1 Суть

Оптимизировать одновременно две цели:
1. `f1 = oos_score` — производительность на OOS
2. `f2 = -(is_score - oos_score)` — минус gap (maximize = minimize overfitting)

Результат — Pareto-фронт стратегий, одновременно хороших И не overfitted.

**Требует:** реализованного OOS split (P0-2) как prerequisite.

### 8.2 Зависимости

- P0-2 (OOS split) должен быть реализован первым
- Меняет структуру Optuna study (multi-objective)
- Несовместим с `run_builder_walk_forward` в текущей реализации

### 8.3 Изменения: `backend/optimization/builder_optimizer.py`

**Добавить новую функцию** `run_builder_optuna_multi_objective`:

```python
def run_builder_optuna_multi_objective(
    base_graph: dict[str, Any],
    is_ohlcv: pd.DataFrame,
    oos_ohlcv: pd.DataFrame,
    oos_cutoff_ts: str,
    param_specs: list[dict[str, Any]],
    config_params: dict[str, Any],
    optimize_metric: str = "sharpe_ratio",
    weights: dict[str, float] | None = None,
    n_trials: int | None = 200,
    top_n: int = 10,
    timeout_seconds: int = 3600,
    strategy_id: str | None = None,
) -> dict[str, Any]:
    """
    Multi-objective Bayesian optimization: maximize OOS score + minimize IS/OOS gap.

    Uses NSGA-II (Non-dominated Sorting Genetic Algorithm) which is the
    standard for multi-objective optimization. Results form a Pareto front
    of strategies that are simultaneously good AND not overfitted.

    Objectives:
        f1 = oos_score (maximize) — performance on held-out data
        f2 = -(is_score - oos_score) (maximize = minimize gap) — generalization

    Requires OOS split to be performed externally (sealed OOS invariant).

    Args:
        is_ohlcv: In-sample OHLCV (optimization target).
        oos_ohlcv: Out-of-sample OHLCV with warmup prepended.
        oos_cutoff_ts: Timestamp where actual OOS starts (warmup cutoff).
        ... (other params same as run_builder_optuna_search)

    Returns:
        Dict with Pareto-front results sorted by OOS score.
    """
    import optuna
    try:
        from optuna.samplers import NSGAIISampler
    except ImportError:
        from optuna.samplers import TPESampler as NSGAIISampler  # type: ignore

    start_time = time.time()

    # Silent logging during optimization
    import loguru as _loguru_mod
    _loguru_logger = _loguru_mod.logger
    _loguru_logger.disable("backend.backtesting")

    # OOS config: add warmup_cutoff so engine trims warmup bars
    oos_config = {**config_params, "warmup_cutoff": oos_cutoff_ts}

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    n_params = len(param_specs)
    sampler = NSGAIISampler(
        seed=42,
        population_size=max(50, n_params * 5),
        mutation_prob=None,  # auto
        crossover_prob=0.9,
        swapped_ratio=0.5,
    )

    study = optuna.create_study(
        directions=["maximize", "maximize"],  # f1=oos_score, f2=-(is-oos gap)
        sampler=sampler,
    )

    all_trial_results: list[dict[str, Any]] = []

    def objective(trial: optuna.Trial) -> tuple[float, float]:
        params = {}
        for spec in param_specs:
            path = spec["param_path"]
            if spec["type"] == "int":
                params[path] = trial.suggest_int(path, int(spec["low"]), int(spec["high"]),
                                                   step=max(1, int(spec.get("step", 1))))
            else:
                params[path] = trial.suggest_float(path, float(spec["low"]), float(spec["high"]),
                                                     step=float(spec.get("step")) if spec.get("step") else None)

        # IS backtest
        is_graph = clone_graph_with_params(base_graph, params)
        is_result = run_builder_backtest(is_graph, is_ohlcv, config_params)
        if is_result is None:
            return float("-inf"), float("-inf")

        # OOS backtest
        oos_graph = clone_graph_with_params(base_graph, params)
        oos_result = run_builder_backtest(oos_graph, oos_ohlcv, oos_config)
        if oos_result is None:
            return float("-inf"), float("-inf")

        is_score = calculate_composite_score(is_result, optimize_metric, weights)
        oos_score = calculate_composite_score(oos_result, optimize_metric, weights)

        # f2: minimize IS/OOS gap → maximize negative gap
        gap_penalty = -(is_score - oos_score)

        trial.set_user_attr("is_score", is_score)
        trial.set_user_attr("oos_score", oos_score)
        all_trial_results.append({"params": params, "is_score": is_score,
                                   "oos_score": oos_score, "_trial_number": trial.number})

        return oos_score, gap_penalty

    try:
        study.optimize(
            objective,
            n_trials=n_trials,
            timeout=timeout_seconds,
            show_progress_bar=False,
            catch=(Exception,),
        )
    finally:
        _loguru_logger.enable("backend.backtesting")

    # Extract Pareto-front trials
    pareto_trials = study.best_trials  # Optuna returns non-dominated trials
    pareto_results = []
    for trial in pareto_trials:
        if trial.values is None:
            continue
        oos_score_val, gap_penalty_val = trial.values
        result_dict = {
            "params": trial.params,
            "oos_score": oos_score_val,
            "is_score": trial.user_attrs.get("is_score", 0),
            "gap_penalty": gap_penalty_val,
            "score": oos_score_val,  # primary sort key = OOS performance
            "oos_degradation_pct": None,
        }
        is_s = result_dict["is_score"]
        if abs(is_s) > 1e-9:
            result_dict["oos_degradation_pct"] = round((is_s - oos_score_val) / abs(is_s) * 100, 1)
        pareto_results.append(result_dict)

    # Sort Pareto front by OOS score (primary) then gap (secondary)
    pareto_results.sort(key=lambda r: (r["oos_score"], r["gap_penalty"]), reverse=True)
    top_results = pareto_results[:top_n]

    execution_time = time.time() - start_time
    completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]

    return {
        "status": "completed",
        "method": "optuna_multi_objective",
        "sampler": "nsga2",
        "total_combinations": n_trials,
        "tested_combinations": len(completed),
        "pareto_front_size": len(pareto_trials),
        "top_results": top_results,
        "best_params": top_results[0]["params"] if top_results else {},
        "best_score": top_results[0]["oos_score"] if top_results else 0.0,
        "best_metrics": {k: v for k, v in top_results[0].items()
                         if k not in ("params",)} if top_results else {},
        "execution_time_seconds": round(execution_time, 2),
    }
```

### 8.4 Интеграция в router.py

В `POST /optimize` handler добавить поддержку `method == "multi_objective"`:

```python
elif request.method == "multi_objective":
    if not getattr(request, "run_oos_validation", False):
        raise HTTPException(
            status_code=400,
            detail="multi_objective method requires run_oos_validation=True (OOS split needed)"
        )
    from backend.optimization.builder_optimizer import (
        split_ohlcv_is_oos, run_builder_optuna_multi_objective
    )
    is_ohlcv, oos_ohlcv, split_info = split_ohlcv_is_oos(ohlcv, oos_ratio=request.oos_ratio)
    if oos_ohlcv is None:
        raise HTTPException(status_code=400, detail=f"Not enough data for OOS split: {split_info['reason']}")

    result = await asyncio.to_thread(
        run_builder_optuna_multi_objective,
        base_graph=strategy_graph,
        is_ohlcv=is_ohlcv,
        oos_ohlcv=oos_ohlcv,
        oos_cutoff_ts=split_info["oos_cutoff_ts"],
        param_specs=active_specs,
        config_params=config_params,
        optimize_metric=request.optimize_metric,
        weights=request.weights,
        n_trials=request.n_trials,
        top_n=_internal_max_results,
        timeout_seconds=request.timeout_seconds,
        strategy_id=strategy_id,
    )
    result["oos_split_info"] = split_info
```

---

## 9. P2-3: Deflated Sharpe Ratio

### 9.1 Суть

DSR корректирует Sharpe Ratio на selection bias от множественного тестирования. При 200 трайлах лучший Sharpe статистически завышен — DSR показывает "реальный" Sharpe с поправкой.

**Формула (Bailey & López de Prado 2014):**
```
DSR = Φ(SR_hat × √(T-1) / √(1 - skew×SR_hat + (kurtosis-1)/4 × SR_hat²) 
        - E[max_N] × √(T-1))

где E[max_N] ≈ (1 - γ)×z(1-1/N) + γ×z(1-1/(N×e))
    γ = Euler-Mascheroni constant ≈ 0.5772
    N = number of trials
    T = number of observations (bars)
```

### 9.2 Изменения: `backend/optimization/scoring.py`

Добавить функцию:

```python
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
        DSR: float (dimensionless). DSR > 0 → statistically significant edge.
    """
    from scipy import stats as _stats
    import math

    if n_observations < 10 or n_trials < 1:
        return float("nan")

    gamma_em = 0.5772156649  # Euler-Mascheroni constant

    # Expected maximum Sharpe from N independent trials (Extreme Value Theory)
    # Approximation: E[max_N] ≈ μ×(1-γ)×Φ⁻¹(1-1/N) + γ×Φ⁻¹(1-1/(N×e))
    z1 = _stats.norm.ppf(1 - 1.0 / max(n_trials, 2))
    z2 = _stats.norm.ppf(1 - 1.0 / max(n_trials * math.e, 2))
    expected_max = (1 - gamma_em) * z1 + gamma_em * z2

    # Standard deviation of SR estimator
    sr_std = math.sqrt(
        (1 - skewness * sharpe_ratio + (kurtosis - 1) / 4.0 * sharpe_ratio ** 2)
        / max(n_observations - 1, 1)
    )

    if sr_std < 1e-12:
        return float("nan")

    # DSR: probability that SR > expected maximum from random search
    dsr_z = (sharpe_ratio - expected_max) / sr_std
    dsr = float(_stats.norm.cdf(dsr_z))

    return round(dsr, 4)
```

### 9.3 Интеграция в `run_builder_optuna_search`

После строки ~4070 добавить DSR расчёт:

```python
# Deflated Sharpe Ratio (selection bias correction)
dsr_value = None
best_sr = top_results[0].get("sharpe_ratio") if top_results else None
if best_sr is not None and completed_trials:
    try:
        from backend.optimization.scoring import deflated_sharpe_ratio
        dsr_value = deflated_sharpe_ratio(
            sharpe_ratio=float(best_sr),
            n_trials=len(completed_trials),
            n_observations=len(ohlcv),
        )
        if dsr_value is not None and dsr_value < 0.1:
            logger.warning(
                f"⚠️ DSR={dsr_value:.3f}: best Sharpe may not be statistically significant "
                f"(tested {len(completed_trials)} combinations on {len(ohlcv)} bars). "
                f"Consider longer history or fewer trials."
            )
    except Exception as _dsr_err:
        logger.debug(f"DSR calculation failed (non-critical): {_dsr_err}")
```

В `return` dict добавить:
```python
"deflated_sharpe_ratio": dsr_value,
"dsr_warning": dsr_value is not None and dsr_value < 0.1,
```

---

## 10. Изменения API/Frontend

### 10.1 Summary изменений в Request/Response

**Новые поля в `BuilderOptimizeRequest`:**

```python
# P0-2: OOS Validation
run_oos_validation: bool = False
oos_ratio: float = Field(default=0.2, ge=0.1, le=0.4)

# P1-1: GT-Score
run_gt_score: bool = False
gt_score_top_n: int = Field(default=5, ge=1, le=20)
gt_score_neighbors: int = Field(default=20, ge=5, le=100)

# P2-1: CSCV
run_cscv: bool = False
cscv_n_splits: int = Field(default=16, ge=4, le=32)

# P1-3: AutoSampler
# sampler_type уже существует — добавить "auto" в Literal
sampler_type: Literal["tpe", "random", "cmaes", "gp", "auto"] = "tpe"

# P2-2: Multi-objective
# method уже существует — добавить "multi_objective" в Literal
method: Literal["grid", "random_search", "bayesian", "walk_forward", "multi_objective"] = "bayesian"
```

**Новые поля в Response:**

```json
{
  "top_results": [{
    "oos_score": null,
    "oos_sharpe_ratio": null,
    "oos_total_return": null,
    "oos_max_drawdown": null,
    "oos_win_rate": null,
    "oos_total_trades": null,
    "oos_degradation_pct": null,
    "gt_score": null,
    "gt_mean": null,
    "gt_std": null,
    "gt_n_valid": null
  }],
  "param_importance": {},
  "param_importance_low": [],
  "deflated_sharpe_ratio": null,
  "dsr_warning": false,
  "oos_split_info": null,
  "cscv": null
}
```

### 10.2 Frontend — отображение новых метрик

**Файл:** `frontend/js/pages/optimization_panels.js`

Добавить отображение в карточку результата оптимизации:

1. **OOS metrics столбцы** в таблице результатов:
   - `IS Score` / `OOS Score` / `OOS Degradation %`
   - Цветовая кодировка: degradation > 50% → красный, 20-50% → жёлтый, < 20% → зелёный

2. **GT-Score badge** рядом с best result:
   - GT > 5 → "Stable" (зелёный)
   - GT 1-5 → "Moderate" (жёлтый)
   - GT < 1 → "Fragile" (красный)

3. **DSR warning banner** если `dsr_warning=true`:
   ```
   ⚠️ Deflated Sharpe Ratio = 0.08 — результат статистически незначим.
   Рекомендуется увеличить период данных или уменьшить количество трайлов.
   ```

4. **fANOVA bar chart** (опционально) — после завершения оптимизации, если `param_importance` не пустой.

5. **CSCV badge** на результате:
   - PBO < 0.1 → "Robust" (зелёный)
   - PBO 0.1-0.3 → "Borderline" (жёлтый)
   - PBO > 0.3 → "Overfitted" (красный)

---

## 11. Тесты

### 11.1 Тесты для P0-1 (BIPOP CMA-ES)

**Файл:** `tests/test_builder_optimizer.py`

```python
class TestBipopCmaes:
    def test_restart_cmaes_sampler_not_deprecated(self):
        """Verify we no longer use deprecated restart_strategy='ipop'."""
        import ast, inspect
        from backend.optimization.builder_optimizer import run_builder_optuna_search
        src = inspect.getsource(run_builder_optuna_search)
        assert '"ipop"' not in src, "restart_strategy='ipop' is deprecated in Optuna 4.4.0"
        assert "restart_strategy" not in src or "bipop" in src or "RestartCmaEsSampler" in src

    def test_optunahub_import_or_graceful_fallback(self):
        """RestartCmaEsSampler imports or falls back to None (no crash)."""
        try:
            import optunahub
            m = optunahub.load_module("samplers/restart_cmaes")
            assert hasattr(m, "RestartCmaEsSampler")
        except Exception:
            pass  # graceful fallback expected

    @pytest.mark.slow
    def test_cmaes_sampler_runs_with_bipop(self, sample_rsi_graph, sample_ohlcv,
                                             backtest_config_params):
        """CMA-ES optimization runs successfully with BIPOP (or fallback)."""
        result = run_builder_optuna_search(
            base_graph=sample_rsi_graph,
            ohlcv=sample_ohlcv,
            param_specs=[{"param_path": "rsi_1.period", "type": "int",
                          "low": 10, "high": 20, "step": 1}],
            config_params=backtest_config_params,
            n_trials=10,
            sampler_type="cmaes",
        )
        assert result["status"] == "completed"
        assert result["tested_combinations"] > 0
```

### 11.2 Тесты для P0-2 (OOS Split)

```python
class TestOOSSplit:
    def test_split_returns_correct_sizes(self, sample_ohlcv):
        is_df, oos_df, info = split_ohlcv_is_oos(sample_ohlcv, oos_ratio=0.2, oos_min_bars=10)
        n = len(sample_ohlcv)
        expected_oos = int(n * 0.2)
        assert abs(len(oos_df) - expected_oos - 200) <= 5  # warmup included
        assert info["oos_skipped"] is False
        assert info["n_is"] + info["n_oos"] == n

    def test_split_skips_when_too_short(self):
        import pandas as pd, numpy as np
        small_ohlcv = pd.DataFrame({"open": [1]*100, "high": [1]*100,
                                    "low": [1]*100, "close": [1]*100,
                                    "volume": [1]*100},
                                   index=pd.date_range("2025-01-01", periods=100, freq="15min"))
        is_df, oos_df, info = split_ohlcv_is_oos(small_ohlcv, oos_ratio=0.2, oos_min_bars=50)
        assert oos_df is None
        assert info["oos_skipped"] is True

    def test_oos_sealed_invariant(self, sample_ohlcv):
        """IS and OOS must not overlap (sealed OOS invariant)."""
        is_df, oos_warmup_df, info = split_ohlcv_is_oos(sample_ohlcv, oos_ratio=0.2)
        oos_start = pd.Timestamp(info["oos_start"])
        is_end = pd.Timestamp(info["is_end"])
        assert is_end < oos_start, "IS and OOS must not overlap"

    @pytest.mark.slow
    def test_oos_validation_runs_end_to_end(self, sample_rsi_graph, sample_ohlcv,
                                             backtest_config_params):
        """OOS validation adds oos_* keys to top results."""
        is_df, oos_df, info = split_ohlcv_is_oos(sample_ohlcv, oos_ratio=0.2, oos_min_bars=50)
        if oos_df is None:
            pytest.skip("OOS too short for this fixture")
        result = run_builder_optuna_search(
            base_graph=sample_rsi_graph,
            ohlcv=is_df,
            param_specs=[{"param_path": "rsi_1.period", "type": "int",
                          "low": 10, "high": 14, "step": 1}],
            config_params=backtest_config_params,
            n_trials=5,
            sampler_type="tpe",
            top_n=3,
        )
        if not result.get("top_results"):
            pytest.skip("No results from optimization")
        top = run_oos_validation(
            top_results=result["top_results"],
            base_graph=sample_rsi_graph,
            oos_ohlcv=oos_df,
            config_params=backtest_config_params,
            oos_cutoff_ts=info["oos_cutoff_ts"],
        )
        for r in top[:3]:
            assert "oos_score" in r
            assert "oos_degradation_pct" in r
```

### 11.3 Тесты для P1-1 (GT-Score)

```python
class TestGTScore:
    def test_gt_score_stable_params_scores_high(self, ...):
        """Params on a flat plateau get high GT-Score."""
        ...

    def test_gt_score_sharp_peak_scores_low(self, ...):
        """Params on a narrow spike get low GT-Score."""
        ...

    def test_gt_score_respects_param_bounds(self, sample_param_specs):
        """Perturbed params never exceed spec bounds."""
        ...

    def test_gt_score_returns_valid_structure(self, ...):
        result = calculate_gt_score(...)
        assert "gt_score" in result
        assert "gt_mean" in result
        assert result["gt_n_valid"] >= 0
```

### 11.4 Тесты для P1-2 (fANOVA)

```python
class TestFanovaImportance:
    @pytest.mark.slow
    def test_fanova_returns_importance_dict(self, ...):
        """After ≥30 trials, fANOVA importance dict is non-empty."""
        result = run_builder_optuna_search(..., n_trials=40, ...)
        assert "param_importance" in result
        if result["param_importance"]:
            assert all(0 <= v <= 1 for v in result["param_importance"].values())

    def test_fanova_skipped_for_few_trials(self, ...):
        """fANOVA is skipped (empty dict) when < 30 trials."""
        result = run_builder_optuna_search(..., n_trials=10, ...)
        assert result.get("param_importance", {}) == {}
```

### 11.5 Тесты для P2-1 (CSCV)

```python
class TestCSCV:
    def test_cscv_pbo_between_0_and_1(self, ...):
        pbo = cscv_validation(strategies, ohlcv, backtest_fn)
        assert 0.0 <= pbo["pbo"] <= 1.0

    def test_cscv_skips_when_too_few_bars(self, small_ohlcv, ...):
        result = cscv_validation(..., ohlcv=small_ohlcv, n_splits=16)
        assert result["pbo_interpretation"] == "skipped"

    def test_cscv_perfect_strategy_has_low_pbo(self, ...):
        """A strategy consistently best on all splits should have PBO < 0.3."""
        ...
```

### 11.6 Тесты для P2-3 (DSR)

```python
class TestDeflatedSharpeRatio:
    def test_dsr_decreases_with_more_trials(self):
        sr = 1.5
        dsr_10 = deflated_sharpe_ratio(sr, n_trials=10, n_observations=1000)
        dsr_200 = deflated_sharpe_ratio(sr, n_trials=200, n_observations=1000)
        assert dsr_10 > dsr_200, "More trials → more selection bias → lower DSR"

    def test_dsr_increases_with_more_observations(self):
        sr = 1.5
        dsr_100 = deflated_sharpe_ratio(sr, n_trials=50, n_observations=100)
        dsr_1000 = deflated_sharpe_ratio(sr, n_trials=50, n_observations=1000)
        assert dsr_1000 > dsr_100, "More data → more statistical power → higher DSR"

    def test_dsr_negative_sr_returns_low_value(self):
        dsr = deflated_sharpe_ratio(-0.5, n_trials=100, n_observations=500)
        assert dsr < 0.1

    def test_dsr_nan_for_invalid_inputs(self):
        dsr = deflated_sharpe_ratio(1.0, n_trials=0, n_observations=500)
        assert math.isnan(dsr)
```

---

## 12. Ограничения и допущения

### 12.1 Что НЕ входит в данное ТЗ

| Исключение | Причина |
|-----------|---------|
| Pruners (MedianPruner, HyperbandPruner) | Неприменимы к одноточечным backtests |
| Walk-Forward мета-overfitting guard | Требует отдельного ТЗ для WFO |
| Live trading интеграция OOS | Scope creep |
| UI для CSCV в реальном времени | Слишком дорого вычислительно для live updates |

### 12.2 Порядок реализации

```
Sprint 1 (P0, ~2-3 дня):
  - P0-1: Фикс BIPOP CMA-ES + optunahub dependency
  - P0-2: OOS split функции + интеграция в router

Sprint 2 (P1, ~3-4 дня):
  - P1-1: GT-Score в scoring.py + интеграция в optimizer
  - P1-2: fANOVA post-processing
  - P1-3: AutoSampler поддержка

Sprint 3 (P2, ~4-5 дней):
  - P2-1: CSCV модуль + интеграция
  - P2-2: Multi-objective optimizer (требует OOS из Sprint 1)
  - P2-3: DSR calculation

Sprint 4 (Frontend):
  - OOS metrics в таблице результатов
  - GT-Score badges
  - DSR warning banners
  - fANOVA importance chart
```

### 12.3 Зависимости между задачами

```
P0-1 (BIPOP) — независим
P0-2 (OOS)   — независим
P1-1 (GT)    — независим (но лучше после P0-2)
P1-2 (fANOVA)— независим
P1-3 (Auto)  — независим
P2-1 (CSCV)  — независим
P2-2 (Multi) — ТРЕБУЕТ P0-2 (OOS split)
P2-3 (DSR)   — независим
```

### 12.4 Производительность — ожидаемые накладные расходы

| Функция | Условие включения | Накладные расходы |
|---------|-----------------|-------------------|
| OOS validation | `run_oos_validation=True` | +5 backtest'ов (~10-30 сек) |
| GT-Score | `run_gt_score=True` | +100 backtest'ов (~2-5 мин) |
| fANOVA | автоматически при ≥30 trials | +1-5 сек (CPU) |
| CSCV | `run_cscv=True` | +80-200 backtest'ов (~3-10 мин) |
| DSR | автоматически | < 1 сек (pure math) |
| BIPOP restart | при `sampler_type="cmaes"` | 0 (только улучшает качество) |

**Все opt-in функции выключены по умолчанию.** Базовая оптимизация без новых флагов работает идентично текущей.

---

## Приложение А: Краткая справка по математике

### Bailey-Borwein formula (overfitting bound)
```
N_max_safe = (T / holding_period) × (1 / log(N_trials))
где T = количество баров, holding_period = средняя длительность сделки
```

### Deflated Sharpe Ratio
```python
from scipy.stats import norm
import math

def dsr(SR, N, T, skew=0, kurt=3):
    g = 0.5772156649  # Euler-Mascheroni
    E_max = (1-g)*norm.ppf(1-1/N) + g*norm.ppf(1-1/(N*math.e))
    std_SR = math.sqrt((1 - skew*SR + (kurt-1)/4*SR**2) / (T-1))
    return norm.cdf((SR - E_max) / std_SR)
```

### GT-Score intuition
```
Plateau landscape:  neighbors score ~0.8, std ~0.05 → GT = 0.8/0.05 = 16 (excellent)
Sharp peak:         neighbors score ~0.1, std ~0.4  → GT = 0.1/0.4 = 0.25 (poor)
```

### CSCV PBO interpretation
```
PBO = P(IS-selected strategy performs below OOS median)
PBO = 0.05 → random selection would win OOS 5% of the time → robust
PBO = 0.50 → IS selection = random coin flip → completely overfitted
```
