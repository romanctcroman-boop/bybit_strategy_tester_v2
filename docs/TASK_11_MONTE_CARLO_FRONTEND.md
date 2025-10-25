# Task #11: Monte Carlo Frontend Integration

**Status**: ✅ COMPLETED  
**Date**: 2025-10-25

## Overview
Реализован фронтенд для Monte Carlo симуляции с визуализацией распределения результатов, cone of uncertainty и оценкой рисков стратегии.

## Implemented Features

### 1. MonteCarloTab Component
**File**: `frontend/src/components/MonteCarloTab.tsx` (465 lines)

Полнофункциональная вкладка Monte Carlo с:

#### **Statistics Cards** (4 карточки)
1. **Mean Return** - средняя доходность всех симуляций
   - Comparison с original strategy
   - Icon: TrendingUpIcon

2. **Std Deviation** - стандартное отклонение (мера волатильности)
   - Показывает разброс результатов
   - Icon: ShowChartIcon

3. **Probability of Profit** - вероятность прибыли
   - Color-coded:
     * Green: ≥70% (high confidence)
     * Yellow/Orange: <70% (moderate)
   - Percentage display

4. **Probability of Ruin** - вероятность разорения
   - Color-coded:
     * Green: ≤10% (low risk)
     * Red: >10% (high risk)
   - Critical risk metric

#### **Distribution Histogram** (Recharts)
- X-axis: Return (%)
- Y-axis: Frequency
- Features:
  * Bar chart с 20 bins
  * Reference lines:
    - Red dashed: Original strategy
    - Green dashed: Mean of simulations
  * Tooltips для каждого бара
  * Responsive container

#### **Percentiles Table**
Детальная таблица доверительных интервалов:
- **5th Percentile** (Pessimistic) - красный chip
- **25th Percentile** - оранжевый chip
- **50th Percentile** (Median) - синий chip, выделен
- **75th Percentile** - зелёный chip
- **95th Percentile** (Optimistic) - зелёный chip
- **Original Strategy** - цвет зависит от percentile rank
  * Green: ≥75th
  * Yellow: 50-75th
  * Red: <50th

#### **Cone of Uncertainty** (Recharts)
Проекция роста капитала с доверительными интервалами:
- LineChart с 6 линиями:
  * **p95** (95th percentile) - зелёная пунктирная
  * **p75** (75th percentile) - светло-зелёная пунктирная
  * **p50** (Median) - синяя сплошная (толстая)
  * **p25** (25th percentile) - оранжевая пунктирная
  * **p5** (5th percentile) - красная пунктирная
  * **Original** - красная сплошная (толстая)
- X-axis: Time Period (0-100)
- Y-axis: Cumulative Return (%)
- Legend для всех линий

#### **Run Buttons**
Три кнопки для запуска симуляций:
- **500 simulations** - быстрый тест (outlined button)
- **1000 simulations** - рекомендуемый (contained button)
- **5000 simulations** - подробный анализ (outlined button)

#### **Interpretation Guide**
Alert с интерпретацией результатов:
- Probability of Profit ≥ 70%: Стратегия робастна
- Probability of Ruin ≤ 10%: Низкий риск разорения
- Original Percentile ≥ 50th: Выше среднего
- Узкий конус (малый Std Dev): Предсказуемые результаты

### 2. Integration with BacktestDetailPage
**File**: `frontend/src/pages/BacktestDetailPage.tsx`

**Changes**:
- Импорт `MonteCarloTab`
- Добавлена 7-я вкладка "Monte Carlo"
- Tabs переиндексированы:
  * 0: Обзор
  * 1: Динамика
  * 2: Анализ сделок
  * 3: Риск
  * 4: Графики
  * 5: TradingView
  * **6: Monte Carlo** ← NEW
  * 7: Сделки

**Code**:
```tsx
import MonteCarloTab from '../components/MonteCarloTab';

// In Tabs:
<Tab label="Monte Carlo" />

// In tab content:
{tab === 6 && backtestId && <MonteCarloTab backtestId={backtestId} />}
```

## Data Structures

### MonteCarloResult Interface
```typescript
interface MonteCarloResult {
  n_simulations: number;           // 1000
  original_return: number;          // 42.5%
  mean_return: number;              // 38.2%
  std_return: number;               // 15.8%
  percentile_5: number;             // 8.5%
  percentile_25: number;            // 26.3%
  percentile_50: number;            // 37.9%
  percentile_75: number;            // 49.8%
  percentile_95: number;            // 68.4%
  prob_profit: number;              // 0.87 (87%)
  prob_ruin: number;                // 0.03 (3%)
  original_percentile: number;      // 62.5th
  distribution: {
    returns: number[];              // Array of all simulation returns
    max_drawdowns: number[];        // Array of max DDs
    sharpe_ratios: number[];        // Array of Sharpe ratios
  };
}
```

## Backend Integration Points

### Required API Endpoint (TODO)
**Endpoint**: `POST /backtests/{id}/monte-carlo`

**Request**:
```json
{
  "n_simulations": 1000,
  "random_seed": 42
}
```

**Response**:
```json
{
  "n_simulations": 1000,
  "original_return": 42.5,
  "mean_return": 38.2,
  "std_return": 15.8,
  "percentile_5": 8.5,
  "percentile_25": 26.3,
  "percentile_50": 37.9,
  "percentile_75": 49.8,
  "percentile_95": 68.4,
  "prob_profit": 0.87,
  "prob_ruin": 0.03,
  "original_percentile": 62.5,
  "distribution": {
    "returns": [...],
    "max_drawdowns": [...],
    "sharpe_ratios": [...]
  }
}
```

### Backend Monte Carlo Simulator
**Location**: `backend/optimization/monte_carlo.py`

**Class**: `MonteCarloSimulator`

**Method**: `run(trades_list, initial_capital, n_simulations, ruin_threshold)`

**Flow**:
1. Bootstrap permutation сделок с возвратом
2. Расчёт метрик для каждой перестановки
3. Построение распределения
4. Расчёт percentiles и вероятностей
5. Return `MonteCarloResult` dataclass

## User Flow

1. **Navigate to backtest**:
   - User opens BacktestDetailPage
   - Clicks "Monte Carlo" tab

2. **Initial state**:
   - Info alert с описанием
   - "Run Monte Carlo (1000 simulations)" button
   - Interpretation guide

3. **Run simulation**:
   - User clicks button
   - Loading indicator (2 seconds mock)
   - Success notification

4. **View results**:
   - 4 statistics cards at top
   - Distribution histogram (center-left)
   - Percentiles table (right)
   - Cone of uncertainty (full width)
   - Interpretation guide (bottom)

5. **Re-run options**:
   - 500 simulations (fast)
   - 1000 simulations (recommended)
   - 5000 simulations (detailed)

## Visual Design

### Color Coding

**Probability of Profit**:
- Green background: ≥70%
- Yellow/Warning background: <70%

**Probability of Ruin**:
- Green background: ≤10%
- Red/Error background: >10%

**Percentile Chips**:
- Red: 5th (pessimistic)
- Orange: 25th
- Blue: 50th (median)
- Green: 75th, 95th (optimistic)

**Original Strategy Badge**:
- Success (green): ≥75th percentile
- Warning (yellow): 50-75th percentile
- Error (red): <50th percentile

### Chart Styling

**Histogram**:
- Bar color: #8884d8 (blue)
- Grid: dashed (#ccc)
- Reference lines: dashed

**Cone of Uncertainty**:
- 95th: #82ca9d (green), dashed
- 75th: #a4de6c (light green), dashed
- 50th: #8884d8 (blue), solid, thick
- 25th: #ffc658 (orange), dashed
- 5th: #ff7c7c (red), dashed
- Original: #ff0000 (red), solid, thick

## Mock Data

Current implementation uses **mock data** for demonstration:
- n_simulations: 1000
- original_return: 42.5%
- mean_return: 38.2%
- std_return: 15.8%
- prob_profit: 87%
- prob_ruin: 3%

**Distribution**:
- Normal distribution centered at 38.2%
- Range: 5th (8.5%) to 95th (68.4%) percentile

## Testing Checklist

- [x] MonteCarloTab renders without errors
- [x] Statistics cards display correctly
- [x] Distribution histogram shows data
- [x] Percentiles table formatted properly
- [x] Cone of uncertainty displays all lines
- [x] Run buttons trigger loading state
- [x] Color coding works correctly
- [x] Responsive layout on mobile/desktop
- [ ] API integration (TODO)
- [ ] Real data from backend (TODO)
- [ ] Error handling for API failures
- [ ] Loading states during long simulations

## Known Limitations

1. **Mock Data**: Currently uses hardcoded mock data
   - TODO: Connect to real API endpoint
   - TODO: Implement BacktestsApi.runMonteCarlo()

2. **No Persistence**: Results not saved
   - TODO: Store MC results in backtest.results
   - TODO: Auto-load if already run

3. **No Advanced Options**:
   - TODO: Configurable random seed
   - TODO: Configurable ruin threshold
   - TODO: Export MC results to CSV

4. **Limited Visualizations**:
   - TODO: Drawdown distribution histogram
   - TODO: Sharpe ratio distribution
   - TODO: Trade sequence permutations view

## Future Enhancements

### Priority 1: API Integration
- [ ] Create `/backtests/{id}/monte-carlo` endpoint
- [ ] Connect MonteCarloTab to real backend
- [ ] Handle loading/error states
- [ ] Store results in database

### Priority 2: Advanced Features
- [ ] Custom n_simulations input
- [ ] Random seed selector
- [ ] Ruin threshold configuration
- [ ] Export MC results to CSV/JSON

### Priority 3: Additional Visualizations
- [ ] Drawdown distribution chart
- [ ] Sharpe ratio distribution
- [ ] Win rate distribution
- [ ] Correlation matrix of metrics

### Priority 4: Statistical Analysis
- [ ] Confidence intervals for all metrics
- [ ] Kolmogorov-Smirnov test for normality
- [ ] Skewness and kurtosis
- [ ] Value at Risk (VaR) metrics

## Files Modified

### Created
- `frontend/src/components/MonteCarloTab.tsx` (465 lines)

### Modified
- `frontend/src/pages/BacktestDetailPage.tsx` (+3 lines)
  * Import MonteCarloTab
  * Add "Monte Carlo" tab
  * Render MonteCarloTab when tab === 6

## Dependencies
- Material-UI (Card, Chip, Table, Alert, CircularProgress)
- Recharts (BarChart, LineChart, ReferenceLine)
- React Router (useParams)
- `../components/NotificationsProvider` (useNotify)

## Documentation References
- Backend Monte Carlo: `backend/optimization/monte_carlo.py`
- ТЗ Section 3.5.3: Monte Carlo Simulation
- Backend tests: `tests/test_monte_carlo.py` (19 tests passing)

---

**Task #11 Status**: ✅ **COMPLETED**

All core features implemented:
- ✅ MonteCarloTab component (465 lines)
- ✅ Distribution histogram (Recharts)
- ✅ Cone of uncertainty visualization
- ✅ Percentiles table with color coding
- ✅ Statistics cards (4 metrics)
- ✅ Run buttons (500/1000/5000)
- ✅ Interpretation guide
- ✅ Integration in BacktestDetailPage

**Next Step**: Connect to real API endpoint (Task #12)

**Estimated Time to API Integration**: 1-2 hours
