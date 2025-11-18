# Sprint 1 Backlog - Week 1 (Oct 30 - Nov 5, 2025)

**Sprint Goal:** Fix critical issues + Start Frontend MVP

---

## 🔴 CRITICAL FIXES (Backend Team, 1-2 days)

### Task 1.1: Fix Monte Carlo Std Dev Bug ⚡ ✅ COMPLETE

**Status:** ✅ DONE (45 minutes, commit b31f622c)  
**Problem:** Standard deviation returns 0.00% (indicates randomization bug)

**File:** `backend/core/monte_carlo.py` or similar

**Expected fix:**
```python
# Check shuffle algorithm
import numpy as np

def run_simulation(self, trades_list, iterations=1000):
    results = []
    for i in range(iterations):
        # CRITICAL: Ensure proper shuffling
        shuffled_trades = trades_list.copy()
        np.random.shuffle(shuffled_trades)  # Use numpy shuffle
        
        # CRITICAL: Use compounding returns, not arithmetic mean
        equity = initial_capital
        for trade in shuffled_trades:
            equity = equity * (1 + trade.return_pct)
        
        results.append(equity - initial_capital)
    
    # Should now have non-zero std dev
    return {
        'mean': np.mean(results),
        'std': np.std(results),  # Should be > 0
        'percentile_5': np.percentile(results, 5),
        'percentile_95': np.percentile(results, 95)
    }
```

**Acceptance Criteria:**
- ✅ Std Dev > 0.00% in test run (DONE: 0.44%)
- ✅ Unit test with known trade sequence validates variance (DONE: tests/test_monte_carlo_fix.py)
- ✅ Re-run extended testing suite (Test 5: Monte Carlo) (DONE: PASS)

**Result:**
- Std Dev: 0.00% → 0.44% ✅
- Range: [0%, 0%] → [-1.50%, 1.58%] ✅
- 95% CI: [-1.08%, 0.66%] ✅
- See: MONTE_CARLO_FIX_REPORT.md

**Actual Time:** 45 minutes (estimate: 3 hours)

---

### Task 1.2: Expand Walk-Forward to 10-15 Cycles ⚡ ✅ COMPLETE

**Status:** ✅ DONE (14.5 minutes execution, commit pending)  
**Problem:** Only 2 profitable periods tested (insufficient sample)

**File:** `run_wfo_full.py`, `tests/integration/test_wfo_expansion.py`

**Final Configuration:**
```python
# Perplexity Recommendation (SELECTED)
in_sample_size = 8000   # ~27.8 days
out_sample_size = 2000  # ~6.9 days
step_size = 2000        # ~6.9 days
# Result: 22 cycles (target 10-15+) ✅
```

**Results:**
- **Periods:** 22 (PASS - target 10+)
- **Efficiency:** 0.0% (FAIL - target 120-160%)
- **Param Stability:** 0.559 (FAIL - target 0.60-0.95)
- **Consistency CV:** 0.474 (FAIL - target 0.15-0.45)
- **Perplexity Benchmarks:** 1/4 PASS ❌

**Critical Finding:**
- **Avg OOS Return:** -8.88% (strategy loses money!)
- **Profitable Periods:** 1/22 (4.5%)
- **Win Rate:** ~20-25% (target 40-50%)
- **Verdict:** EMA Crossover NOT viable for BTCUSDT 5min

**See:** WFO_22_CYCLES_REPORT.md

**Actual Time:** 14.5 minutes (estimate: 4 hours, 21x faster!)

---

### Task 1.3: Out-of-Sample Validation Test ⚠️ SKIPPED

**Status:** ⚠️ SKIPPED  
**Rationale:** WFO already provided 22 independent OOS tests. All failed catastrophically → strategy invalid. No need for additional validation testing.

**Perplexity Recommendation:** Pivot to mean-reversion strategies instead of tuning failed trend-following approach.

**Estimate:** 3 hours (saved)

---

### Task 1.4: Parameter Sensitivity Analysis ⚠️ SKIPPED

**Status:** ⚠️ SKIPPED  
**Rationale:** Sensitivity analysis is for tuning viable strategies. Current EMA Crossover strategy is fundamentally flawed (negative returns, low win rate). No amount of parameter adjustment will fix structural issues.

**Perplexity Recommendation:** Don't optimize a broken strategy. Pivot to Support/Resistance (Priority #1) or Bollinger Bands (Priority #2).

**Estimate:** 4 hours (saved)

---

### Task 1.3: Out-of-Sample Validation Test ⚡ HIGH PRIORITY

**Problem:** Need to measure IS vs OOS carry-through to detect overfitting

**Create:** `tests/integration/test_oos_validation.py`

**Implementation:**
```python
class TestOutOfSampleValidation:
    def test_is_vs_oos_carrythrough(self):
        """
        Test IS efficiency vs OOS efficiency
        
        Healthy: OOS = 70-85% of IS efficiency
        Warning: OOS < 50% of IS = severe overfitting
        """
        # Use final 20% of data as holdout (never touched in optimization)
        holdout_start = int(len(data) * 0.8)
        training_data = data[:holdout_start]
        holdout_data = data[holdout_start:]
        
        # Run WFO on training data
        wfo_results = wfo.run(training_data, param_space, strategy_config)
        is_efficiency = wfo_results['aggregated_metrics']['efficiency']
        optimal_params = wfo_results['optimal_parameters']
        
        # Test optimal params on holdout
        oos_results = backtest_engine.run(holdout_data, optimal_params)
        oos_efficiency = calculate_efficiency(oos_results)
        
        carrythrough = (oos_efficiency / is_efficiency) * 100
        
        # Assertions
        assert carrythrough > 50, f"Severe overfitting: {carrythrough:.1f}%"
        assert carrythrough > 70, f"Target 70-85%, got {carrythrough:.1f}%"
        
        logger.info(f"IS Efficiency: {is_efficiency:.2f}%")
        logger.info(f"OOS Efficiency: {oos_efficiency:.2f}%")
        logger.info(f"Carry-through: {carrythrough:.1f}% {'✅ HEALTHY' if carrythrough > 70 else '⚠️ WARNING'}")
```

**Acceptance Criteria:**
- ✅ Test creates holdout set (final 20% of data)
- ✅ Measures carry-through percentage
- ✅ Logs clear diagnostic information
- ✅ Fails if carry-through < 50% (overfitting detection)

**Estimate:** 3 hours

---

### Task 1.4: Parameter Sensitivity Analysis ⚡ MEDIUM PRIORITY

**Problem:** Validate robustness around EMA 15/40 optimal parameters

**Create:** `tests/integration/test_parameter_sensitivity.py`

**Implementation:**
```python
def test_parameter_sensitivity_ema():
    """
    Test performance with parameter variations around optimal EMA 15/40
    
    Robust strategy: 85%+ performance in adjacent parameter space
    Overfitted: Cliff-edge degradation outside exact parameters
    """
    optimal_fast = 15
    optimal_slow = 40
    
    # Test grid around optimal
    variations = [
        (13, 38), (13, 39), (13, 40), (13, 41), (13, 42),
        (14, 38), (14, 39), (14, 40), (14, 41), (14, 42),
        (15, 38), (15, 39), (15, 40), (15, 41), (15, 42),  # <-- Optimal
        (16, 38), (16, 39), (16, 40), (16, 41), (16, 42),
        (17, 38), (17, 39), (17, 40), (17, 41), (17, 42),
    ]
    
    baseline_result = run_backtest(optimal_fast, optimal_slow)
    baseline_sharpe = baseline_result['sharpe_ratio']
    
    degradation_count = 0
    for fast, slow in variations:
        if (fast, slow) == (optimal_fast, optimal_slow):
            continue
            
        result = run_backtest(fast, slow)
        performance_ratio = result['sharpe_ratio'] / baseline_sharpe
        
        if performance_ratio < 0.85:  # >15% degradation
            degradation_count += 1
        
        logger.info(f"EMA {fast}/{slow}: {performance_ratio*100:.1f}% of optimal")
    
    # Robust if most variations maintain 85%+ performance
    robustness_score = 1 - (degradation_count / len(variations))
    
    assert robustness_score > 0.7, f"Low robustness: {robustness_score*100:.1f}%"
    logger.info(f"Parameter Robustness: {robustness_score*100:.1f}% ✅")
```

**Acceptance Criteria:**
- ✅ Tests 25 parameter combinations around optimal
- ✅ Measures performance degradation
- ✅ Calculates robustness score (target >70%)
- ✅ Visual heatmap of parameter space (optional)

**Estimate:** 4 hours

---

## 🟡 FRONTEND MVP START (Frontend Team, 5 days)

### Task 2.1: Project Setup & Scaffolding (Day 1-2)

**Tool:** electron-react-boilerplate

```bash
# Initialize project
git clone --depth 1 --branch main https://github.com/electron-react-boilerplate/electron-react-boilerplate.git frontend_v2
cd frontend_v2
npm install

# Clean boilerplate
npm run clean

# Configure TypeScript strict mode
# Update tsconfig.json
```

**Acceptance Criteria:**
- ✅ Electron app launches with React + TypeScript
- ✅ Hot reload working in development
- ✅ Production build succeeds
- ✅ ESLint + Prettier configured

**Estimate:** 1 day

---

### Task 2.2: Backend API Connection (Day 2)

**File:** `frontend_v2/src/services/api.ts`

```typescript
import axios from 'axios';

const API_BASE_URL = process.env.API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Test connection
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

// Strategy endpoints
export const getStrategies = async () => {
  const response = await api.get('/api/strategies');
  return response.data;
};

export const runBacktest = async (strategyId: string, params: any) => {
  const response = await api.post('/api/backtests', {
    strategy_id: strategyId,
    ...params,
  });
  return response.data;
};
```

**Acceptance Criteria:**
- ✅ API client configured with axios
- ✅ Health check endpoint tested
- ✅ Error handling implemented
- ✅ TypeScript types for API responses

**Estimate:** 0.5 day

---

### Task 2.3: Dashboard Layout (Day 3)

**File:** `frontend_v2/src/pages/Dashboard.tsx`

```typescript
import React from 'react';
import { Layout, Menu } from 'antd'; // Or your UI library

const { Header, Sider, Content } = Layout;

export const Dashboard: React.FC = () => {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider>
        <Menu theme="dark" mode="inline">
          <Menu.Item key="strategies">Strategies</Menu.Item>
          <Menu.Item key="backtests">Backtests</Menu.Item>
          <Menu.Item key="optimization">Optimization</Menu.Item>
        </Menu>
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: 0 }}>
          <h1>Bybit Strategy Tester</h1>
        </Header>
        <Content style={{ margin: '16px' }}>
          {/* Content will go here */}
        </Content>
      </Layout>
    </Layout>
  );
};
```

**Acceptance Criteria:**
- ✅ Responsive layout with sidebar navigation
- ✅ Header with app title
- ✅ Content area for pages
- ✅ Basic routing setup (React Router)

**Estimate:** 1 day

---

### Task 2.4: Strategy Selection Form (Day 4)

**File:** `frontend_v2/src/components/StrategyForm.tsx`

```typescript
import React, { useState } from 'react';
import { Form, Select, InputNumber, Button } from 'antd';

export const StrategyForm: React.FC = () => {
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      const result = await runBacktest(values.strategy, values);
      console.log('Backtest result:', result);
      // Navigate to results page
    } catch (error) {
      console.error('Backtest failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form onFinish={onFinish} layout="vertical">
      <Form.Item label="Strategy" name="strategy">
        <Select>
          <Select.Option value="ema_crossover">EMA Crossover</Select.Option>
          <Select.Option value="support_resistance">Support/Resistance</Select.Option>
        </Select>
      </Form.Item>
      
      <Form.Item label="Symbol" name="symbol" initialValue="BTCUSDT">
        <Input />
      </Form.Item>
      
      <Form.Item label="Timeframe" name="timeframe" initialValue="5">
        <Select>
          <Select.Option value="1">1m</Select.Option>
          <Select.Option value="5">5m</Select.Option>
          <Select.Option value="15">15m</Select.Option>
        </Select>
      </Form.Item>
      
      <Button type="primary" htmlType="submit" loading={loading}>
        Run Backtest
      </Button>
    </Form>
  );
};
```

**Acceptance Criteria:**
- ✅ Form with strategy selection
- ✅ Symbol and timeframe inputs
- ✅ Parameter inputs (dynamic based on strategy)
- ✅ Submit button with loading state
- ✅ Form validation

**Estimate:** 1 day

---

### Task 2.5: First Integration Test (Day 5)

**Goal:** Run one complete backtest from UI to backend and display results

**Acceptance Criteria:**
- ✅ User selects EMA Crossover strategy
- ✅ Fills in parameters (symbol, timeframe, EMA periods)
- ✅ Clicks "Run Backtest"
- ✅ Frontend sends request to backend
- ✅ Backend executes backtest
- ✅ Results displayed in UI (at minimum: Net Profit, Win Rate, Max DD)
- ✅ Success/error messages shown

**Estimate:** 1 day

---

## 📊 SPRINT 1 SUMMARY

**Total Duration:** 1 week (5 working days)

**Team Split:**
- Backend: 1-2 developers (critical fixes)
- Frontend: 1-2 developers (MVP scaffolding)

**Deliverables:**
1. ✅ Monte Carlo bug fixed (Std Dev > 0%)
2. ✅ Walk-Forward expanded (10-15 cycles)
3. ✅ Out-of-sample validation test
4. ✅ Parameter sensitivity analysis
5. ✅ Electron app running with React + TypeScript
6. ✅ Backend API connected
7. ✅ Basic dashboard layout
8. ✅ Strategy form implemented
9. ✅ **First end-to-end backtest from UI working**

**Success Metrics:**
- All critical tests passing (17/17 → 21/21 with new tests)
- Frontend app launches without errors
- One complete backtest flow working (UI → Backend → UI)

---

## 🚀 NEXT SPRINT (Week 2)

**Backend:**
- Support/Resistance strategy
- Bollinger Bands strategy
- RSI confirmation
- HTF filter optimization

**Frontend:**
- Results display (tables)
- TradingView charts integration
- Parameter validation
- Error handling improvements

---

**Sprint Start Date:** October 30, 2025  
**Sprint End Date:** November 5, 2025  
**Sprint Retrospective:** November 5, 2025, 5 PM
