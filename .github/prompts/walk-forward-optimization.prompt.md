# Run Walk-Forward Optimization

Complete workflow for running walk-forward optimization on a strategy.

---

## Input Required

- **Strategy:** [Name or ID]
- **Symbol:** [e.g., BTCUSDT]
- **Timeframe:** [e.g., 15m, 1h]
- **Date Range:** [Start and end dates]
- **Parameters to Optimize:** [List with ranges]
- **Optimization Metric:** [Sharpe, Sortino, PnL, etc.]

---

## Phase 1: Configuration

### 1.1 Define Optimization Parameters

```python
optimization_config = {
    'strategy': 'rsi',
    'symbol': 'BTCUSDT',
    'timeframe': '15m',
    'start_date': '2024-01-01',
    'end_date': '2025-01-01',

    # Walk-forward settings
    'train_days': 180,      # Training window
    'test_days': 30,        # Out-of-sample test
    'step_days': 30,        # Roll forward step

    # Parameter ranges to optimize
    'param_ranges': {
        'rsi_period': {'min': 7, 'max': 21, 'step': 2},
        'rsi_overbought': {'min': 65, 'max': 80, 'step': 5},
        'rsi_oversold': {'min': 20, 'max': 35, 'step': 5},
    },

    # Optimization target
    'optimize_for': 'sharpe_ratio',  # or 'sortino', 'total_pnl', 'profit_factor'
    'minimize': False,  # True for drawdown, False for returns
}
```

### 1.2 Verify Data Availability

```python
from backend.services.data_service import DataService

service = DataService()
data = await service.load_ohlcv(
    symbol='BTCUSDT',
    interval='15m',
    start_date='2024-01-01',
    end_date='2025-01-01'
)

print(f"Data points: {len(data)}")
print(f"Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")

# Verify enough data for walk-forward
total_days = (data['timestamp'].max() - data['timestamp'].min()).days
required_days = optimization_config['train_days'] + optimization_config['test_days']
assert total_days >= required_days, f"Need at least {required_days} days, have {total_days}"
```

---

## Phase 2: Run Optimization

### 2.1 Via API

```bash
curl -X POST "http://localhost:8000/api/v1/optimize/walk-forward" \
     -H "Content-Type: application/json" \
     -d '{
       "strategy_type": "rsi",
       "symbol": "BTCUSDT",
       "interval": "15m",
       "start_date": "2024-01-01",
       "end_date": "2025-01-01",
       "train_days": 180,
       "test_days": 30,
       "param_ranges": {
         "rsi_period": [7, 21, 2],
         "rsi_overbought": [65, 80, 5],
         "rsi_oversold": [20, 35, 5]
       },
       "optimize_for": "sharpe_ratio"
     }'
```

### 2.2 Via Python

```python
from backend.backtesting.walk_forward import WalkForwardOptimizer
from backend.backtesting.strategies.rsi_strategy import RSIStrategy

optimizer = WalkForwardOptimizer(
    strategy_class=RSIStrategy,
    param_ranges={
        'rsi_period': range(7, 22, 2),
        'rsi_overbought': range(65, 81, 5),
        'rsi_oversold': range(20, 36, 5),
    },
    train_days=180,
    test_days=30,
    step_days=30,
    optimize_for='sharpe_ratio',
    n_jobs=-1  # Use all CPU cores
)

results = await optimizer.run(data)
```

---

## Phase 3: Analyze Results

### 3.1 Key Metrics to Check

```python
import pandas as pd

results_df = pd.DataFrame(results['windows'])

# Check for overfitting
print("=== Overfitting Analysis ===")
print(f"Average Train Sharpe: {results_df['train_sharpe'].mean():.2f}")
print(f"Average Test Sharpe:  {results_df['test_sharpe'].mean():.2f}")
print(f"Average Degradation:  {results_df['degradation_pct'].mean():.1f}%")

# Warning if degradation > 30%
if results_df['degradation_pct'].mean() > 30:
    print("⚠️ WARNING: High degradation suggests overfitting!")

# Check parameter stability
print("\n=== Parameter Stability ===")
for param in ['rsi_period', 'rsi_overbought', 'rsi_oversold']:
    values = [w['best_params'][param] for w in results['windows']]
    print(f"{param}: mean={np.mean(values):.1f}, std={np.std(values):.1f}")

# Best overall parameters (most common across windows)
from collections import Counter
best_params = Counter([tuple(sorted(w['best_params'].items())) for w in results['windows']])
print(f"\nMost frequent params: {dict(best_params.most_common(1)[0][0])}")
```

### 3.2 Visualization

```python
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 1. Train vs Test Sharpe
ax1 = axes[0, 0]
ax1.bar(range(len(results_df)), results_df['train_sharpe'], alpha=0.7, label='Train')
ax1.bar(range(len(results_df)), results_df['test_sharpe'], alpha=0.7, label='Test')
ax1.set_title('Train vs Test Sharpe by Window')
ax1.legend()

# 2. Degradation over time
ax2 = axes[0, 1]
ax2.plot(results_df['degradation_pct'], marker='o')
ax2.axhline(y=30, color='r', linestyle='--', label='30% threshold')
ax2.set_title('Performance Degradation %')
ax2.legend()

# 3. Parameter evolution
ax3 = axes[1, 0]
param_values = [w['best_params']['rsi_period'] for w in results['windows']]
ax3.plot(param_values, marker='s')
ax3.set_title('RSI Period Evolution')

# 4. Cumulative out-of-sample returns
ax4 = axes[1, 1]
cumulative_returns = np.cumprod(1 + np.array([w['test_return'] for w in results['windows']])) - 1
ax4.plot(cumulative_returns * 100)
ax4.set_title('Cumulative Out-of-Sample Returns %')

plt.tight_layout()
plt.savefig('walk_forward_results.png')
plt.show()
```

---

## Phase 4: Validation

### 4.1 Robustness Checks

```python
# 1. Check for data leakage
print("=== Data Leakage Check ===")
for i, window in enumerate(results['windows']):
    if window['train_end'] >= window['test_start']:
        print(f"⚠️ Window {i}: Training period overlaps test period!")

# 2. Check for sufficient trades per window
print("\n=== Trade Count Check ===")
min_trades = 10
for i, window in enumerate(results['windows']):
    if window['test_trades'] < min_trades:
        print(f"⚠️ Window {i}: Only {window['test_trades']} trades (min: {min_trades})")

# 3. Statistical significance
from scipy import stats
train_sharpes = results_df['train_sharpe'].values
test_sharpes = results_df['test_sharpe'].values
t_stat, p_value = stats.ttest_rel(train_sharpes, test_sharpes)
print(f"\n=== Statistical Test ===")
print(f"Paired t-test: t={t_stat:.2f}, p={p_value:.4f}")
if p_value < 0.05:
    print("⚠️ Significant difference between train/test (possible overfitting)")
```

### 4.2 Forward Test

```python
# Run forward test on most recent unseen data
forward_start = optimization_config['end_date']
forward_end = 'today'

# Use the most stable parameters
best_params = get_robust_params(results)

forward_result = await backtest(
    data=forward_data,
    strategy_params=best_params,
    commission=0.0007
)

print(f"\n=== Forward Test Results ===")
print(f"Parameters: {best_params}")
print(f"Sharpe: {forward_result['sharpe']:.2f}")
print(f"Return: {forward_result['total_return']*100:.1f}%")
print(f"Max DD: {forward_result['max_drawdown']*100:.1f}%")
```

---

## Phase 5: Report

```markdown
## Walk-Forward Optimization Results

### Configuration

- Strategy: [name]
- Symbol: [symbol] | Timeframe: [tf]
- Period: [start] to [end]
- Train: [X] days | Test: [Y] days | Step: [Z] days
- Windows: [N] total

### Results Summary

| Metric           | Value |
| ---------------- | ----- |
| Avg Train Sharpe | X.XX  |
| Avg Test Sharpe  | X.XX  |
| Degradation      | XX%   |
| Best Window      | #X    |
| Worst Window     | #X    |

### Optimal Parameters

| Parameter | Value | Stability (std) |
| --------- | ----- | --------------- |
| param1    | XX    | ±Y              |
| param2    | XX    | ±Y              |

### Overfitting Assessment

- [ ] Degradation < 30%: [PASS/FAIL]
- [ ] Parameters stable: [PASS/FAIL]
- [ ] Forward test positive: [PASS/FAIL]

### Recommendation

[Use these parameters / Continue testing / Strategy not robust]

### Files Generated

- walk_forward_results.png
- optimization_log.csv
- best_params.json
```

---

## Quick Commands

```powershell
# Run optimization via CLI
python -m backend.backtesting.walk_forward \
    --strategy rsi \
    --symbol BTCUSDT \
    --start 2024-01-01 \
    --end 2025-01-01 \
    --train-days 180 \
    --test-days 30

# View results
python -c "import json; print(json.dumps(json.load(open('results/optimization_latest.json')), indent=2))"
```
