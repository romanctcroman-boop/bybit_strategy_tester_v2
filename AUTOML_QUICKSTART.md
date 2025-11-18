# 🤖 AutoML Quick Start Guide

**Quick reference for using AutoML Strategy Optimization**

---

## 🚀 Quick Start (5 minutes)

### Step 1: Create a Study

```bash
curl -X POST http://localhost:8000/api/v1/automl/studies \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": 1,
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-12-31T23:59:59Z",
    "n_trials": 50,
    "n_jobs": 4,
    "objectives": ["sharpe_ratio"],
    "param_space": {
      "ema_short": {"type": "int", "low": 5, "high": 50},
      "ema_long": {"type": "int", "low": 20, "high": 200}
    },
    "sampler": "tpe",
    "pruner": "median"
  }'
```

**Response**:
```json
{
  "study_name": "strategy_1_BTCUSDT_20250127_143022",
  "status": "created",
  "n_trials": 0,
  "n_completed": 0
}
```

### Step 2: Start Optimization

```bash
curl -X POST http://localhost:8000/api/v1/automl/studies/strategy_1_BTCUSDT_20250127_143022/start
```

### Step 3: Monitor Progress

```bash
# Check study status
curl http://localhost:8000/api/v1/automl/studies/strategy_1_BTCUSDT_20250127_143022

# List trials
curl http://localhost:8000/api/v1/automl/studies/strategy_1_BTCUSDT_20250127_143022/trials

# Get best trial
curl http://localhost:8000/api/v1/automl/studies/strategy_1_BTCUSDT_20250127_143022/best
```

### Step 4: Get Results

```bash
# Export results
curl http://localhost:8000/api/v1/automl/studies/strategy_1_BTCUSDT_20250127_143022/export > results.json

# View best parameters
cat results.json | jq '.best_trial.params'
```

---

## 🎨 Frontend Access

**URL**: `http://localhost:3000/automl`

**Actions**:
1. Click **"➕ Create Study"**
2. Fill in parameters
3. Click **"▶ Start"** on study card
4. Wait for completion (auto-refreshes every 10s)
5. View results in **"Trials"** and **"Best Params"** tabs
6. Click **"📥 Export"** to download JSON

---

## 📊 Parameter Space Examples

### Example 1: EMA Crossover Strategy

```json
{
  "param_space": {
    "ema_short": {"type": "int", "low": 5, "high": 50},
    "ema_long": {"type": "int", "low": 20, "high": 200},
    "stop_loss_pct": {"type": "float", "low": 0.5, "high": 5.0},
    "take_profit_pct": {"type": "float", "low": 1.0, "high": 10.0}
  }
}
```

### Example 2: RSI Mean Reversion

```json
{
  "param_space": {
    "rsi_period": {"type": "int", "low": 7, "high": 28},
    "rsi_oversold": {"type": "float", "low": 20, "high": 40},
    "rsi_overbought": {"type": "float", "low": 60, "high": 80},
    "holding_period": {"type": "int", "low": 5, "high": 50}
  }
}
```

### Example 3: Bollinger Bands Breakout

```json
{
  "param_space": {
    "bb_period": {"type": "int", "low": 10, "high": 50},
    "bb_std": {"type": "float", "low": 1.5, "high": 3.0},
    "breakout_threshold": {"type": "float", "low": 0.5, "high": 2.0},
    "atr_multiplier": {"type": "float", "low": 1.0, "high": 4.0}
  }
}
```

### Example 4: Multi-Indicator Combo

```json
{
  "param_space": {
    "ema_period": {"type": "int", "low": 10, "high": 100},
    "rsi_period": {"type": "int", "low": 7, "high": 28},
    "macd_fast": {"type": "int", "low": 8, "high": 20},
    "macd_slow": {"type": "int", "low": 20, "high": 50},
    "macd_signal": {"type": "int", "low": 5, "high": 15},
    "signal_mode": {"type": "categorical", "choices": ["all", "any", "majority"]}
  }
}
```

---

## 🎯 Objective Functions

### Single-Objective

**Maximize Sharpe Ratio**:
```json
{
  "objectives": ["sharpe_ratio"]
}
```

### Multi-Objective

**Sharpe + Drawdown**:
```json
{
  "objectives": ["sharpe_ratio", "max_drawdown"]
}
```

**Sharpe + Drawdown + Win Rate**:
```json
{
  "objectives": ["sharpe_ratio", "max_drawdown", "win_rate"]
}
```

### Available Objectives

| Objective        | Direction | Description                           |
|------------------|-----------|---------------------------------------|
| `sharpe_ratio`   | Maximize  | Risk-adjusted returns                 |
| `max_drawdown`   | Minimize  | Maximum equity drop (negative value)  |
| `win_rate`       | Maximize  | Percentage of winning trades          |
| `profit_factor`  | Maximize  | Gross profit / Gross loss             |
| `total_pnl`      | Maximize  | Total profit/loss                     |

---

## ⚙️ Sampler Options

### TPE (Recommended)

**Tree-structured Parzen Estimator** - Bayesian optimization

```json
{
  "sampler": "tpe"
}
```

**When to use**:
- Default choice
- Works well for most problems
- Smart parameter search

### Random

**Random search** - Baseline

```json
{
  "sampler": "random"
}
```

**When to use**:
- Baseline comparison
- Very high-dimensional spaces (>20 params)

### CMA-ES

**Covariance Matrix Adaptation Evolution Strategy**

```json
{
  "sampler": "cmaes"
}
```

**When to use**:
- Continuous parameters only (no integers/categorical)
- Known to work well for your problem class

---

## 🛑 Pruner Options

### Median (Recommended)

**Stop if worse than median of past trials**

```json
{
  "pruner": "median"
}
```

**Savings**: 30-40% computation time

### Hyperband

**Adaptive resource allocation**

```json
{
  "pruner": "hyperband"
}
```

**Savings**: 40-60% computation time (more aggressive)

### None

**No pruning** (run all trials to completion)

```json
{
  "pruner": "none"
}
```

**When to use**: When trials are fast (<5 seconds)

---

## 🔬 Advanced Usage

### Parallel Execution

```json
{
  "n_trials": 100,
  "n_jobs": 8  // Use 8 CPU cores
}
```

**Recommendation**: Set `n_jobs = min(n_cpus, 16)`

### Study Timeout

```json
{
  "timeout": 3600  // Stop after 1 hour (regardless of n_trials)
}
```

### Custom Study Name

```python
from backend.services.automl_service import OptimizationConfig

config = OptimizationConfig(
    ...
    study_name="my_custom_study_v1"
)
```

### Load Existing Study

```python
from backend.services.automl_service import AutoMLService

service = AutoMLService(storage="sqlite:///optuna.db")
study = service.load_study("strategy_1_BTCUSDT_20250127_143022")
summary = service.get_study_summary(study)
print(summary)
```

---

## 📈 Interpretation Guide

### Best Trial

**Example**:
```json
{
  "trial_number": 42,
  "params": {
    "ema_short": 12,
    "ema_long": 50,
    "stop_loss_pct": 2.5
  },
  "values": {
    "sharpe_ratio": 2.15
  }
}
```

**Interpretation**:
- Trial #42 had best Sharpe Ratio (2.15)
- Use these parameters in your strategy
- Re-run backtest to verify results

### Pareto Front

**Example** (2 objectives: Sharpe + Drawdown):
```json
{
  "pareto_trials": [
    {
      "trial_number": 42,
      "params": {"ema_short": 12, "ema_long": 50},
      "values": {"sharpe_ratio": 2.15, "max_drawdown": -8.5}
    },
    {
      "trial_number": 87,
      "params": {"ema_short": 20, "ema_long": 100},
      "values": {"sharpe_ratio": 1.85, "max_drawdown": -5.2}
    }
  ]
}
```

**Interpretation**:
- Trial #42: Higher Sharpe (2.15), Higher Drawdown (-8.5%)
- Trial #87: Lower Sharpe (1.85), Lower Drawdown (-5.2%)
- Choose based on risk tolerance:
  - Risk-tolerant: Use Trial #42 (higher returns, higher risk)
  - Risk-averse: Use Trial #87 (lower returns, lower risk)

### Trial States

| State      | Meaning                                      |
|------------|----------------------------------------------|
| `COMPLETE` | Trial finished successfully                  |
| `PRUNED`   | Trial stopped early (MedianPruner)           |
| `FAIL`     | Trial encountered error                      |
| `RUNNING`  | Trial currently executing                    |

**Pruned Trials**: Not a failure! Pruning saves time by stopping unpromising trials.

---

## ⚡ Performance Tips

### 1. Start Small

```json
{
  "n_trials": 20,  // Quick test run
  "n_jobs": 2
}
```

**Then scale up**:
```json
{
  "n_trials": 200,  // Production run
  "n_jobs": 8
}
```

### 2. Narrow Search Space

**Before** (wide search):
```json
{
  "ema_short": {"type": "int", "low": 5, "high": 100}
}
```

**After** (focused search):
```json
{
  "ema_short": {"type": "int", "low": 10, "high": 30}
}
```

### 3. Use Pruning

```json
{
  "pruner": "median"  // Saves 30-40% time
}
```

### 4. Multi-Stage Optimization

**Stage 1**: Coarse search (100 trials, wide range)  
**Stage 2**: Fine-tuning (50 trials, narrow range around best)

```python
# Stage 1
config1 = OptimizationConfig(
    n_trials=100,
    param_space={
        "ema_short": {"low": 5, "high": 50},
        "ema_long": {"low": 20, "high": 200}
    }
)
result1 = service.optimize_strategy(config1, param_space1)

# Stage 2: Focus on best region
best_ema_short = result1.best_params["ema_short"]
config2 = OptimizationConfig(
    n_trials=50,
    param_space={
        "ema_short": {"low": best_ema_short - 5, "high": best_ema_short + 5},
        "ema_long": ...
    }
)
```

---

## 🐛 Troubleshooting

### Problem: All trials fail

**Solution**:
1. Check param space (ensure `low < high`)
2. Run single backtest manually
3. Check backend logs

### Problem: No improvement over random

**Solution**:
1. Increase `n_trials` (100 → 200)
2. Widen search space
3. Try different sampler (`tpe` → `cmaes`)

### Problem: Optimization too slow

**Solution**:
1. Increase `n_jobs` (use more CPU cores)
2. Enable pruning (`pruner="median"`)
3. Reduce backtest period (1 year → 6 months)

### Problem: Pareto front empty

**Solution**:
1. Verify `objectives` has 2+ items
2. Check if any trials completed successfully
3. Ensure objective values are valid (not NaN)

---

## 📚 Further Reading

**Optuna Documentation**:
- [Official Docs](https://optuna.readthedocs.io/)
- [Tutorial](https://optuna.readthedocs.io/en/stable/tutorial/index.html)
- [Best Practices](https://optuna.readthedocs.io/en/stable/faq.html)

**Academic Papers**:
- [TPE: Bergstra et al. (2011)](https://papers.nips.cc/paper/4443-algorithms-for-hyper-parameter-optimization)
- [Optuna: Akiba et al. (2019)](https://arxiv.org/abs/1907.10902)

**Our Documentation**:
- [PHASE4_AUTOML_COMPLETE.md](./PHASE4_AUTOML_COMPLETE.md) - Full documentation
- [backend/services/automl_service.py](./backend/services/automl_service.py) - Source code

---

**Need help?** Check full documentation in `PHASE4_AUTOML_COMPLETE.md`
