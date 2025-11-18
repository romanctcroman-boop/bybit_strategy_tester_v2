# Dashboard UI - Trading Strategy Tester

## Структура компонентов

```
Dashboard/
├── Dashboard.tsx          # Main container (4-panel layout)
├── Dashboard.css          # Layout styles (grid, colors)
├── index.ts               # Barrel exports
├── Header/
│   ├── DashboardHeader.tsx  # Status, strategy selector, timeframe
│   └── Header.css
├── LeftPanel/             # Charts & Metrics (70% width, blue theme)
│   ├── LeftPanel.tsx
│   ├── LeftPanel.css
│   ├── EquityCurveChart   # Placeholder - будет TradingView/Recharts
│   ├── MetricsCards       # Return, Sharpe, Win Rate, Max DD, PF, Trades
│   ├── WFOPeriodTable     # 22 cycles breakdown
│   └── StrategyComparisonChart  # 4 strategies overlay
├── RightPanel/            # Controls & Filters (30% width, teal theme)
│   ├── RightPanel.tsx
│   ├── RightPanel.css
│   ├── StrategyParamsForm       # Lookback, tolerance, stop-loss
│   ├── SignalFiltersForm        # RSI, BB, volume toggles
│   ├── PatternSettingsForm      # S/R, BB, EMA parameters
│   └── EntryExitConditionsForm  # Entry/exit rule toggles
└── Footer/
    ├── DashboardFooter.tsx  # Status updates, data range
    └── Footer.css
```

## Цветовая схема (из макета)

- **Header:** `#2d5016` → `#3d6b1f` (green gradient)
- **Left Panel:** `#0a0a3f` → `#000033` (dark blue gradient)
- **Right Panel:** `#0d4d4d` → `#085858` (teal gradient)
- **Footer:** `#4a0e4e` → `#6a1b6d` (purple gradient)

## Использование

```tsx
import { Dashboard } from '@/components/Dashboard';

function App() {
  return <Dashboard strategyName="S/R Mean-Reversion" timeframe="5m" />;
}
```

## Следующие шаги

### 1. Выбор библиотеки для графиков (ожидаем ответ от Perplexity AI)

**Опции:**

- **TradingView Lightweight Charts** - лучший выбор для финансовых данных
- **Recharts** - проще в интеграции с React
- **Chart.js** - максимальная производительность для больших данных (44K точек)

### 2. Интеграция с WFO JSON данными

```typescript
// hooks/useWFOResults.ts
const useWFOResults = (strategy: string) => {
  const [data, setData] = useState<WFOResults | null>(null);

  useEffect(() => {
    // Load from /results/wfo_{strategy}_22_cycles_*.json
    fetch(`/results/wfo_${strategy}_22_cycles_latest.json`)
      .then((res) => res.json())
      .then(setData);
  }, [strategy]);

  return { data, loading };
};
```

### 3. Real-time обновления

**Варианты (ожидаем рекомендацию от Perplexity):**

- File watcher (chokidar) - для Electron desktop app
- WebSocket - для live backend updates
- HTTP polling - простой fallback

### 4. Performance оптимизации

- React.memo() для дорогих компонентов (charts)
- useMemo() для data transformations
- Debounce для слайдеров параметров (300ms)
- Canvas rendering для >10K точек

## Текущий статус

✅ **Completed:**

- Dashboard layout structure (4 panels)
- Header with strategy selector and timeframe controls
- Left Panel with placeholder charts and metrics cards
- WFO Period Table (22 rows) with sortable columns
- Right Panel with 4 form sections:
  - Strategy Parameters (lookback, tolerance, stop-loss)
  - Signal Filters (RSI, BB, volume toggles)
  - Pattern Settings (S/R, BB, EMA periods)
  - Entry/Exit Conditions (entry/exit rule checkboxes)
- Footer with data range and status
- CSS styling matching mockup colors
- Responsive layout (grid → flex on mobile)

🔄 **In Progress:**

- Awaiting Perplexity AI recommendations for charting library
- Awaiting Perplexity AI recommendations for real-time updates

⏳ **Pending:**

- Implement EquityCurveChart with chosen library
- Implement StrategyComparisonChart (4 lines)
- Load real WFO JSON data from `/results/`
- Calculate aggregate metrics from WFO results
- Add WebSocket/file watcher for live updates
- Add export functionality (CSV, JSON, PNG)
- Add preset saving/loading for strategy parameters

## Данные для визуализации

**Источники:**

- `results/wfo_sr_22_cycles_20251029_184838.json` - S/R strategy (22 periods)
- `results/wfo_bb_22_cycles_20251029_190227.json` - Bollinger Bands (22 periods)
- Sprint 1 EMA results (need to locate file)
- Sprint 2 S/R+RSI results (need to locate file)

**Формат WFO JSON:**

```json
{
  "metadata": {
    "strategy": "SR Mean-Reversion",
    "symbol": "BTCUSDT",
    "timeframe": "5m",
    "total_periods": 22
  },
  "periods": [
    {
      "period_id": 1,
      "is_start": 1704067200000,
      "is_end": 1706745599000,
      "oos_start": 1706745600000,
      "oos_end": 1709423999000,
      "oos_metrics": {
        "return_pct": -2.34,
        "sharpe": -0.45,
        "win_rate": 0.58,
        "total_trades": 42
      }
    }
  ]
}
```

## Интеграция в приложение

```tsx
// src/App.tsx
import { Dashboard } from '@/components/Dashboard';

function App() {
  return (
    <div className="app">
      <Dashboard />
    </div>
  );
}
```

## Техническая спецификация

- **Framework:** React 18 + TypeScript
- **Build Tool:** Vite
- **Desktop:** Electron
- **State Management:** useState (можно добавить Zustand для глобального состояния)
- **Charts:** TBD (ожидаем Perplexity)
- **Styling:** CSS Modules (можно мигрировать на Tailwind)

## Perplexity AI Query

Comprehensive query prepared in `perplexity_ui_design_query.md`:

1. Charting library comparison (TradingView vs Recharts vs Chart.js)
2. Layout architecture (CSS Grid vs Flexbox)
3. Real-time data updates (WebSocket vs polling vs file watching)
4. Multi-strategy comparison UI patterns
5. Performance optimization for 44K data points
6. React + TypeScript code examples
7. Component hierarchy recommendations
