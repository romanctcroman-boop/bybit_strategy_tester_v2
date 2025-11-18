# Task #10: Walk-Forward Optimization Frontend Integration

**Status**: ✅ COMPLETED  
**Date**: 2025-01-XX

## Overview
Реализован фронтенд для визуализации результатов Walk-Forward Optimization с защитой от переобучения через сравнение In-Sample (IS) и Out-of-Sample (OOS) performance.

## Implemented Features

### 1. WalkForwardPage Component
**File**: `frontend/src/pages/WalkForwardPage.tsx` (428 lines)

Компонент с тремя режимами визуализации:

#### **Timeline View** (по умолчанию)
- Side-by-side сравнение IS и OOS для каждого периода
- In-Sample панель (тренировка):
  * Sharpe Ratio, Net Profit, Total Trades
  * Best Parameters (оптимальные параметры)
- Out-of-Sample панель (тестирование):
  * Sharpe Ratio, Net Profit, Total Trades
  * Max Drawdown, Win Rate
- Efficiency chip с цветовой индикацией:
  * 🟢 Green: ≥80% (отличная робастность)
  * 🟡 Yellow: ≥60% (приемлемая)
  * 🔴 Red: <60% (переобучение)

#### **Metrics View**
Таблица с детальным сравнением всех периодов:
- Period Number
- IS Sharpe vs OOS Sharpe
- Efficiency (OOS/IS performance ratio)
- IS Net Profit vs OOS Net Profit
- OOS Win Rate
- OOS Max Drawdown

#### **Stability View**
Анализ стабильности параметров:
- Values across periods (значения по периодам)
- Standard Deviation (стандартное отклонение)
- Coefficient of Variation (CV)
- Visual indicators:
  * 🟢 CV <0.2: Стабильный параметр
  * 🟡 CV 0.2-0.3: Умеренная вариация
  * 🔴 CV >0.3: Нестабильный (потенциальная проблема)

#### **Aggregated Metrics Cards**
Суммарная статистика:
1. **Average OOS Sharpe**: Средний Sharpe Ratio на тестовых данных
2. **Average Efficiency**: Средняя робастность стратегии
3. **Profitable Periods**: Количество прибыльных периодов
4. **Average Win Rate**: Средний процент прибыльных сделок

### 2. WFORunButton Component
**File**: `frontend/src/components/WFORunButton.tsx` (107 lines)

Кнопка запуска Walk-Forward оптимизации:

**Features**:
- Dialog с конфигурацией WFO параметров
- In-Sample Size (bars): Размер окна обучения (default: 252 = 1 год)
- Out-of-Sample Size (bars): Размер окна тестирования (default: 63 = 3 месяца)
- Step Size (bars): Шаг сдвига окна (default: 63)
- Visual example демонстрирующий скользящее окно
- API integration с уведомлениями
- Автоматический переход на страницу результатов

**UI/UX**:
- Disabled state пока optimization не completed
- Loading spinner во время запуска
- Notifications для success/error states
- Helper text с объяснениями параметров

### 3. Integration with OptimizationDetailPage
**File**: `frontend/src/pages/OptimizationDetailPage.tsx`

**Changes**:
- Импорт `WFORunButton`
- Добавлена кнопка в header (появляется только если `status === 'completed'`)
- Layout: Stack с `justifyContent: space-between`

**Before**:
```tsx
<Typography variant="h4">Optimization #{optimizationId}</Typography>
```

**After**:
```tsx
<Stack direction="row" alignItems="center" justifyContent="space-between">
  <Typography variant="h4">Optimization #{optimizationId}</Typography>
  {opt && opt.status === 'completed' && (
    <WFORunButton optimizationId={optimizationId} />
  )}
</Stack>
```

### 4. Routing Configuration
**Files**: `frontend/src/App.tsx`, `frontend/src/pages/index.tsx`

**Route**: `/walk-forward/:id`

**App.tsx**:
```tsx
const WalkForwardPage = lazy(() => import('./pages/WalkForwardPage'));

// ...in routes
<Route path="/walk-forward/:id" element={<WalkForwardPage />} />
```

**index.tsx**:
```tsx
export { default as WalkForwardPage } from './WalkForwardPage';
```

### 5. API Integration
**Backend Endpoint**: `POST /optimizations/{id}/run/walk-forward`

**Request Payload**:
```typescript
{
  train_size: number;      // In-Sample size (bars)
  test_size: number;       // Out-of-Sample size (bars)
  step_size: number;       // Rolling window step (bars)
  strategy_config?: Record<string, any>;
  param_space?: Record<string, any>;
  metric?: string;         // default: 'sharpe_ratio'
  queue?: string;
}
```

**Response**:
```typescript
{
  task_id: string;
  status: "queued";
}
```

**Results Retrieval**:
```typescript
// WFO results stored in optimization.results field
const optimization = await OptimizationsApi.get(optimizationId);
const wfoData: WFOResults = {
  walk_results: optimization.results.walk_results,
  aggregated_metrics: optimization.results.aggregated_metrics,
  parameter_stability: optimization.results.parameter_stability,
};
```

## Data Structures

### WFOPeriod Interface
```typescript
interface WFOPeriod {
  period_num: number;
  in_sample_start: string;
  in_sample_end: string;
  out_sample_start: string;
  out_sample_end: string;
  best_params: Record<string, any>;
  is_sharpe: number;
  is_net_profit: number;
  is_total_trades: number;
  oos_sharpe: number;
  oos_net_profit: number;
  oos_total_trades: number;
  oos_max_drawdown: number;
  oos_win_rate: number;
  efficiency: number;  // OOS/IS performance ratio
}
```

### WFOResults Interface
```typescript
interface WFOResults {
  walk_results: WFOPeriod[];
  aggregated_metrics: {
    avg_oos_sharpe: number;
    avg_efficiency: number;
    total_periods: number;
    profitable_periods: number;
    avg_oos_net_profit: number;
    avg_oos_max_drawdown: number;
    avg_oos_win_rate: number;
  };
  parameter_stability: {
    [paramName: string]: {
      values: number[];
      std_dev: number;
      coefficient_of_variation: number;
    };
  };
}
```

## User Flow

1. **Запуск WFO**:
   - User открывает OptimizationDetailPage
   - Если optimization completed → видит кнопку "Run Walk-Forward"
   - Нажимает кнопку → Dialog с параметрами
   - Настраивает In-Sample/Out-Sample/Step размеры
   - Нажимает "Start Walk-Forward"
   - Task enqueued → notification с task_id
   - Автоматический redirect на /walk-forward/:id

2. **Просмотр результатов**:
   - WalkForwardPage загружает optimization results
   - Показывает aggregated metrics в карточках
   - Default view: Timeline с IS/OOS сравнением
   - Пользователь может переключаться между:
     * Timeline View (визуальное сравнение)
     * Metrics View (табличное сравнение)
     * Stability View (анализ параметров)

3. **Интерпретация**:
   - **Efficiency ≥80%**: Стратегия робастна, низкий риск переобучения
   - **Efficiency 60-80%**: Приемлемая робастность, требует мониторинга
   - **Efficiency <60%**: Высокий риск переобучения, требуется доработка
   - **CV <0.2**: Параметр стабильный
   - **CV >0.3**: Параметр нестабильный (варьируется между периодами)

## Efficiency Color Coding

```typescript
const getEfficiencyColor = (efficiency: number) => {
  if (efficiency >= 0.8) return 'success';  // Green
  if (efficiency >= 0.6) return 'warning';  // Yellow
  return 'error';                           // Red
};
```

- **Green (≥80%)**: Excellent robustness
- **Yellow (60-79%)**: Acceptable, monitor carefully
- **Red (<60%)**: Overfitting risk, strategy needs improvement

## Testing Checklist

- [ ] WalkForwardPage loads without errors
- [ ] API integration retrieves optimization results
- [ ] Timeline view displays IS/OOS comparison correctly
- [ ] Metrics view shows all periods in table
- [ ] Stability view calculates CV correctly
- [ ] Aggregated metrics cards display correct values
- [ ] Efficiency color coding works (green/yellow/red)
- [ ] WFORunButton dialog opens/closes
- [ ] WFO task enqueues successfully
- [ ] Navigation to /walk-forward/:id works
- [ ] Loading/error states handled gracefully
- [ ] Responsive layout on mobile/tablet/desktop

## Backend Integration Points

### Walk-Forward Task
**File**: `backend/tasks/optimize_tasks.py`  
**Task**: `walk_forward_task`

**Flow**:
1. Load market data (symbol, interval, start_date, end_date)
2. Create WalkForwardOptimizer with config
3. Run optimization (sliding window IS→OOS)
4. Calculate efficiency, degradation, robustness_score
5. Save results to optimization.results field
6. Update optimization status to 'completed'

### Results Storage
**Location**: `optimization.results` JSON field

**Structure**:
```json
{
  "method": "walk_forward",
  "metric": "sharpe_ratio",
  "config": {
    "mode": "rolling",
    "train_size": 252,
    "test_size": 63,
    "step_size": 63
  },
  "walk_results": [...],
  "aggregated_metrics": {...},
  "parameter_stability": {...},
  "summary": {
    "robustness_score": 0.789,
    "recommended_params": {...}
  }
}
```

## Known Limitations

1. **No Charts Yet**: Нет Recharts визуализаций для efficiency trends
   - TODO: Add line chart для efficiency по периодам
   - TODO: Add scatter plot OOS vs IS performance
   - TODO: Add parameter value timeline

2. **No Real-time Progress**: WFO task выполняется в Celery, нет real-time updates
   - TODO: Integrate with Redis Streams для live progress

3. **Mock Data Fallback**: Если результаты не найдены, нет fallback UI
   - TODO: Add better error handling и empty state

## Future Enhancements

### Priority 1: Charts & Visualizations
- [ ] Efficiency trend line chart (Recharts)
- [ ] OOS vs IS scatter plot
- [ ] Parameter stability timeline chart
- [ ] Drawdown comparison chart

### Priority 2: Advanced Analytics
- [ ] Robustness Score interpretation guide
- [ ] Degradation metrics visualization
- [ ] Parameter correlation heatmap
- [ ] Walk-Forward path optimizer (find optimal window sizes)

### Priority 3: Export & Reporting
- [ ] Export WFO results to CSV
- [ ] PDF report generation
- [ ] Comparative analysis (multiple WFO runs)
- [ ] Best period selector

## Files Modified

### Created
- `frontend/src/pages/WalkForwardPage.tsx` (428 lines)
- `frontend/src/components/WFORunButton.tsx` (107 lines)

### Modified
- `frontend/src/App.tsx` (+3 lines: lazy import + route)
- `frontend/src/pages/index.tsx` (+1 line: export)
- `frontend/src/pages/OptimizationDetailPage.tsx` (+7 lines: import + button)

## Dependencies
- Material-UI (Grid, Card, Chip, Table, Dialog, ToggleButtonGroup)
- React Router (useParams, useNavigate)
- `../services/api` (OptimizationsApi)
- `../components/NotificationsProvider` (useNotify)

## Documentation References
- Backend WFO: `backend/core/walk_forward_optimizer.py`
- API Endpoints: `backend/api/routers/optimizations.py`
- Task Implementation: `backend/tasks/optimize_tasks.py`

---

**Task #10 Status**: ✅ **COMPLETED**

All core features implemented:
- ✅ WalkForwardPage with 3 view modes
- ✅ WFORunButton with configuration dialog
- ✅ Integration with OptimizationDetailPage
- ✅ Routing configured
- ✅ API connected
- ✅ Efficiency color coding
- ✅ Parameter stability analysis
- ✅ Aggregated metrics

**Next Task**: Task #11 - Monte Carlo Frontend Integration
