# Backtest Results UI - Улучшения и Новые Компоненты

## Обзор

Реализован набор компонентов для улучшения визуализации и анализа результатов бэктестинга.

## Новые Компоненты

### 1. AIAnalysisPanel

**Файл:** `frontend/src/components/AIAnalysisPanel.tsx`

**Описание:** AI-powered анализ результатов бэктеста с использованием Perplexity AI через MCP Bridge.

**Props:**
```typescript
interface AIAnalysisPanelProps {
  backtest: Backtest | null;
  results: BacktestResults;
}
```

**Функции:**
- Автоматическая генерация базовых инсайтов
- Запрос детального анализа от Perplexity AI
- Структурированные рекомендации (success/warning/info)
- Fallback логика при недоступности API

**Использование:**
```tsx
import AIAnalysisPanel from '../components/AIAnalysisPanel';

<AIAnalysisPanel backtest={backtest} results={results} />
```

**Интеграция:**
- Добавлен в `BacktestDetailPage` в Overview Tab
- Backend endpoint: `POST /api/v1/ai/analyze-backtest`

---

### 2. AdvancedTradeFilters

**Файл:** `frontend/src/components/AdvancedTradeFilters.tsx`

**Описание:** Расширенные фильтры для списка сделок.

**Props:**
```typescript
interface AdvancedTradeFiltersProps {
  filters: TradeFilters;
  onFiltersChange: (filters: TradeFilters) => void;
  availableSignals?: string[];
}

interface TradeFilters {
  side: '' | 'buy' | 'sell';
  pnlMin?: number;
  pnlMax?: number;
  dateFrom?: Date | null;
  dateTo?: Date | null;
  signal?: string;
  sortBy: 'entry_time' | 'exit_time' | 'pnl' | 'pnl_pct' | 'duration';
  sortOrder: 'asc' | 'desc';
}
```

**Возможности фильтрации:**
1. **По направлению:** All / Long / Short
2. **По PnL:** Минимум и максимум (USDT)
3. **По периоду:** От даты / До даты
4. **По сигналу:** Выбор из доступных сигналов
5. **Сортировка:** 5 критериев × 2 порядка

**Использование:**
```tsx
import AdvancedTradeFilters, { TradeFilters } from '../components/AdvancedTradeFilters';

const [filters, setFilters] = useState<TradeFilters>({
  side: '',
  sortBy: 'entry_time',
  sortOrder: 'desc',
});

<AdvancedTradeFilters
  filters={filters}
  onFiltersChange={setFilters}
  availableSignals={['EMA_CROSS', 'RSI_OVERSOLD', 'MACD_SIGNAL']}
/>
```

**UI Features:**
- Accordion с индикатором активных фильтров
- Кнопка "Очистить все фильтры"
- Адаптивный layout (mobile-friendly)

---

### 3. EnhancedMetricsTable

**Файл:** `frontend/src/components/EnhancedMetricsTable.tsx`

**Описание:** Улучшенная таблица метрик с визуальными индикаторами.

**Props:**
```typescript
interface EnhancedMetricsTableProps {
  groups: MetricGroup[];
}

interface MetricGroup {
  title: string;
  metrics: MetricRow[];
}

interface MetricRow {
  label: string;
  value: number | null;
  format: 'usd' | 'percent' | 'plain' | 'ratio';
  benchmark?: number;
  tooltip?: string;
  showTrend?: boolean;
}
```

**Визуальные элементы:**
1. **Цветовая кодировка:**
   - Зеленый: положительные значения
   - Красный: отрицательные значения
   - Серый: нейтральные/отсутствующие

2. **Progress Bars:**
   - Для процентных значений
   - Автоматическая нормализация до 100%

3. **Индикаторы трендов:**
   - ↑ Лучше бенчмарка
   - ↓ Хуже бенчмарка
   - − Равно бенчмарку

4. **Tooltips:**
   - Дополнительная информация о метрике
   - Иконка "?" с hover эффектом

**Использование:**
```tsx
import EnhancedMetricsTable from '../components/EnhancedMetricsTable';

const metricsGroups = [
  {
    title: 'Основные показатели',
    metrics: [
      {
        label: 'Чистый PnL',
        value: 1234.56,
        format: 'usd',
        benchmark: 1000,
        showTrend: true,
        tooltip: 'Общая прибыль за период'
      },
      {
        label: 'Win Rate',
        value: 65.5,
        format: 'percent',
        benchmark: 50,
        showTrend: true
      }
    ]
  }
];

<EnhancedMetricsTable groups={metricsGroups} />
```

---

### 4. PlotlyEquityCurve

**Файл:** `frontend/src/components/PlotlyEquityCurve.tsx`

**Описание:** Интерактивный график equity curve с использованием Plotly.js.

**Props:**
```typescript
interface PlotlyEquityCurveProps {
  data: DataPoint[];
  height?: number;
  showDrawdown?: boolean;
  showBuyHold?: boolean;
  title?: string;
}

interface DataPoint {
  timestamp: number;
  equity?: number;
  drawdown?: number;
  buyHold?: number;
}
```

**Возможности:**
1. **Интерактивность:**
   - Zoom (box select)
   - Pan (drag)
   - Reset axes
   - Hover tooltips

2. **Множественные серии:**
   - Equity curve (синяя линия)
   - Drawdown area (красная заливка, правая ось)
   - Buy & Hold comparison (желтая пунктирная)

3. **Экспорт:**
   - PNG (1600×1000px, 2x scale)
   - Автоматическое имя файла

4. **Темная/светлая тема:**
   - Автоматическая адаптация к MUI theme
   - Настройка цветов, фона, сетки

**Использование:**
```tsx
import PlotlyEquityCurve from '../components/PlotlyEquityCurve';

const equityData = chartData.map(d => ({
  timestamp: d.timestamp,
  equity: d.equityAbs,
  drawdown: calculateDrawdown(d.equityAbs),
  buyHold: d.buyHoldAbs,
}));

<PlotlyEquityCurve
  data={equityData}
  height={500}
  showDrawdown={true}
  showBuyHold={true}
  title="Динамика капитала"
/>
```

---

## Backend API

### AI Analysis Endpoint

**URL:** `POST /api/v1/ai/analyze-backtest`

**Request:**
```json
{
  "context": {
    "backtest_id": 123,
    "strategy": "EMA_CROSS",
    "symbol": "BTCUSDT",
    "timeframe": "15m",
    "period": "2025-01-01 → 2025-10-31",
    "metrics": {
      "net_pnl": 1234.56,
      "win_rate": 65.5,
      "profit_factor": 2.1,
      "sharpe_ratio": 1.8
    }
  },
  "query": "Проанализируй результаты бэктеста..."
}
```

**Response:**
```json
{
  "analysis": "Стратегия показывает отличные результаты...",
  "model": "sonar",
  "tokens": 450
}
```

**Errors:**
- `503`: Perplexity API key not configured
- `500`: Internal error or invalid API response

---

## Установка зависимостей

### Frontend:
```bash
npm install @mui/x-date-pickers date-fns
```

Уже установлены:
- `react-plotly.js` (v2.6.0)
- `plotly.js` (v2.30.0)

### Backend:
```bash
pip install httpx  # Already in requirements.txt
```

---

## Интеграция в BacktestDetailPage

### 1. Добавить импорты:
```tsx
import AIAnalysisPanel from '../components/AIAnalysisPanel';
import AdvancedTradeFilters, { TradeFilters } from '../components/AdvancedTradeFilters';
import EnhancedMetricsTable from '../components/EnhancedMetricsTable';
import PlotlyEquityCurve from '../components/PlotlyEquityCurve';
```

### 2. Добавить state для фильтров:
```tsx
const [tradeFilters, setTradeFilters] = useState<TradeFilters>({
  side: '',
  sortBy: 'entry_time',
  sortOrder: 'desc',
});
```

### 3. Использовать компоненты:

**AI Analysis (в Overview Tab):**
```tsx
<AIAnalysisPanel backtest={backtest} results={results} />
```

**Enhanced Metrics (заменить существующую таблицу):**
```tsx
<EnhancedMetricsTable groups={metricsGroups} />
```

**Plotly Chart (заменить BacktestEquityChart):**
```tsx
<PlotlyEquityCurve
  data={equityChartData}
  height={400}
  showDrawdown={showDrawdown}
  showBuyHold={showBuyHold}
/>
```

**Advanced Filters (в Trades Tab):**
```tsx
<AdvancedTradeFilters
  filters={tradeFilters}
  onFiltersChange={setTradeFilters}
  availableSignals={extractUniqueSignals(trades)}
/>
```

---

## Roadmap

### Следующие улучшения:

1. **Trade List Enhancements:**
   - [ ] Применить фильтры к запросу сделок
   - [ ] Добавить пагинацию с URL параметрами
   - [ ] Export filtered trades to CSV

2. **Metrics Improvements:**
   - [ ] Sparkline charts в таблице метрик
   - [ ] Comparison mode (multiple backtests)
   - [ ] Custom metric formulas

3. **Chart Enhancements:**
   - [ ] Multiple equity curves comparison
   - [ ] Annotation support (mark important events)
   - [ ] Custom indicators overlay

4. **AI Analysis:**
   - [ ] Streaming responses для больших анализов
   - [ ] Save analysis history
   - [ ] Custom analysis templates

---

## Тестирование

### Юнит-тесты (TODO):
```tsx
// AIAnalysisPanel.test.tsx
describe('AIAnalysisPanel', () => {
  it('generates fallback insights when API unavailable', () => {});
  it('calls backend API with correct context', () => {});
  it('parses AI response into structured insights', () => {});
});

// AdvancedTradeFilters.test.tsx
describe('AdvancedTradeFilters', () => {
  it('updates filters on user input', () => {});
  it('clears all filters', () => {});
  it('shows correct active filters count', () => {});
});
```

### E2E тесты (TODO):
```typescript
// backtest-results.spec.ts
test('AI analysis generates insights', async ({ page }) => {
  await page.goto('/backtests/123');
  await page.click('text=Запустить AI-анализ');
  await expect(page.locator('.MuiChip-label')).toContainText('активных');
});

test('trade filters work correctly', async ({ page }) => {
  await page.goto('/backtests/123');
  await page.click('text=Сделки');
  await page.selectOption('select[name="side"]', 'buy');
  // Assert filtered results
});
```

---

## Производительность

### Оптимизации:
1. **React.memo** для всех компонентов
2. **useMemo** для тяжелых вычислений (Plotly data)
3. **Lazy loading** для Plotly (динамический import)
4. **Debounce** для фильтров (избежать частых запросов)

### Bundle размер:
- Plotly.js: ~3MB (gzipped ~800KB)
- MUI date-pickers: ~100KB
- date-fns: ~70KB (tree-shakeable)

**Рекомендация:** Включить code splitting для Plotly.

---

## Контрибьюторы

- AI Analysis: Perplexity AI Integration
- UI Components: Material-UI v5
- Charts: Plotly.js
- Date handling: date-fns
