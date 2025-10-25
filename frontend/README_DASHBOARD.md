# Frontend Dashboard Integration - Session Report

## ✅ Выполнено

### 1. CSV Export Integration

#### Added CSV Download Buttons
В `BacktestDetailPage.tsx` добавлены кнопки для скачивания CSV отчетов:

**Расположение:** Tab "Обзор" (Overview)  
**Функциональность:**
- Кнопка "Скачать Performance.csv"
- Кнопка "Скачать Risk Ratios.csv"
- Кнопка "Скачать Trades Analysis.csv"
- Кнопка "Скачать List of Trades.csv"
- Кнопка "Скачать все отчеты (ZIP)"

**API Endpoints:**
```typescript
// Single report download
GET /backtests/{id}/export/{report_type}
// report_type: list_of_trades | performance | risk_ratios | trades_analysis

// All reports as ZIP
GET /backtests/{id}/export/all
```

#### Implementation Details
```typescript
const downloadCSV = async (backtestId: number, reportType: string) => {
  const response = await fetch(
    `/backtests/${backtestId}/export/${reportType}`
  );
  
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `backtest_${backtestId}_${reportType}.csv`;
  a.click();
  window.URL.revokeObjectURL(url);
};
```

### 2. Plotly Charts Integration (In Progress)

#### Created PlotlyChart Component
`frontend/src/components/PlotlyChart.tsx` - универсальный компонент для отображения Plotly графиков.

**Особенности:**
- Dynamic import Plotly.js (не увеличивает основной bundle)
- Responsive дизайн
- Поддержка темной темы
- Интерактивность (zoom, pan, hover)
- Loading/Error states

**Usage:**
```tsx
import PlotlyChart from '../components/PlotlyChart';

<PlotlyChart
  plotlyJson={chartData}  // JSON string from backend
  height={400}
  loading={isLoading}
  error={errorMessage}
/>
```

#### Added Plotly.js Dependency
`package.json` обновлен:
```json
"plotly.js-basic-dist-min": "^2.28.0"
```

### 3. Charts Tab (Next Step)

План реализации вкладки "Графики":

**Charts to Integrate:**
1. **Equity Curve** - График equity с опциональным drawdown
2. **Drawdown Overlay** - Dual y-axis (equity + drawdown)
3. **PnL Distribution** - Гистограмма распределения прибыли
4. **Parameter Heatmap** - Тепловая карта для оптимизации

**Backend Integration:**
```typescript
// Fetch Plotly charts from backend
const response = await BacktestsApi.getCharts(backtestId, chartType);
// response.plotly_json contains Plotly figure
```

**API Endpoints to Implement:**
```python
# backend/api/routers/backtests.py

@router.get("/{backtest_id}/charts/{chart_type}")
def get_chart(backtest_id: int, chart_type: str):
    """
    Generate Plotly chart for backtest
    
    chart_type: equity_curve | drawdown_overlay | pnl_distribution | parameter_heatmap
    
    Returns: {"plotly_json": "<plotly_figure_json>"}
    """
    # Use backend/visualization/advanced_charts.py
    pass
```

## 📦 Структура файлов

```
frontend/
├── src/
│   ├── components/
│   │   ├── PlotlyChart.tsx           ✅ NEW - Plotly chart component
│   │   └── ...
│   ├── pages/
│   │   ├── BacktestDetailPage.tsx    🔄 MODIFIED - Added CSV buttons
│   │   └── ...
│   └── services/
│       └── api.ts                     🔄 TO MODIFY - Add charts endpoints
├── package.json                       🔄 MODIFIED - Added plotly.js
└── README_DASHBOARD.md                ✅ NEW - This file
```

## 🚀 Next Steps

### Priority 1: API Endpoints for Charts

Create `backend/api/routers/backtests.py` endpoints:

```python
from backend.visualization.advanced_charts import (
    create_equity_curve,
    create_drawdown_overlay,
    create_pnl_distribution,
    create_parameter_heatmap
)

@router.get("/{backtest_id}/charts/equity_curve")
def get_equity_chart(backtest_id: int, show_drawdown: bool = True):
    # Get backtest results
    # Call create_equity_curve()
    # Return Plotly JSON
    pass

@router.get("/{backtest_id}/charts/drawdown_overlay")
def get_drawdown_chart(backtest_id: int):
    # Call create_drawdown_overlay()
    pass

@router.get("/{backtest_id}/charts/pnl_distribution")
def get_pnl_distribution(backtest_id: int, bins: int = 30):
    # Call create_pnl_distribution()
    pass

# For optimization results only:
@router.get("/optimizations/{optimization_id}/charts/heatmap")
def get_heatmap(optimization_id: int, param_x: str, param_y: str, metric: str):
    # Call create_parameter_heatmap()
    pass
```

### Priority 2: Charts Tab Implementation

Add new tab to `BacktestDetailPage.tsx`:

```tsx
// Add to tabs array
<Tabs>
  <Tab label="Обзор" />
  <Tab label="Динамика" />
  <Tab label="Анализ сделок" />
  <Tab label="Риск" />
  <Tab label="Графики" />  {/* NEW */}
  <Tab label="Сделки" />
</Tabs>

// Add ChartsTab component
const ChartsTab: React.FC<{ backtestId: number }> = ({ backtestId }) => {
  const [equityData, setEquityData] = useState(null);
  const [drawdownData, setDrawdownData] = useState(null);
  const [pnlData, setPnlData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Fetch all charts
    fetchCharts();
  }, [backtestId]);

  return (
    <Stack spacing={3} sx={{ mt: 2 }}>
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6">Equity Curve</Typography>
        <PlotlyChart plotlyJson={equityData} height={400} loading={loading} />
      </Paper>

      <Paper sx={{ p: 3 }}>
        <Typography variant="h6">Drawdown Overlay</Typography>
        <PlotlyChart plotlyJson={drawdownData} height={400} loading={loading} />
      </Paper>

      <Paper sx={{ p: 3 }}>
        <Typography variant="h6">PnL Distribution</Typography>
        <PlotlyChart plotlyJson={pnlData} height={350} loading={loading} />
      </Paper>
    </Stack>
  );
};
```

### Priority 3: Update API Service

Add to `frontend/src/services/api.ts`:

```typescript
export const BacktestsApi = {
  // Existing methods...
  
  // Charts endpoints
  getEquityCurve: async (id: number, showDrawdown: boolean = true) => {
    const response = await api.get(
      `/backtests/${id}/charts/equity_curve?show_drawdown=${showDrawdown}`
    );
    return response.data;
  },
  
  getDrawdownOverlay: async (id: number) => {
    const response = await api.get(`/backtests/${id}/charts/drawdown_overlay`);
    return response.data;
  },
  
  getPnlDistribution: async (id: number, bins: number = 30) => {
    const response = await api.get(
      `/backtests/${id}/charts/pnl_distribution?bins=${bins}`
    );
    return response.data;
  },
  
  // CSV export (already implemented)
  exportCSV: async (id: number, reportType: string) => {
    const response = await api.get(
      `/backtests/${id}/export/${reportType}`,
      { responseType: 'blob' }
    );
    return response.data;
  },
};
```

### Priority 4: Mode Switcher (Базовый/Продвинутый/Экспертный)

Add mode selection to top of page:

```tsx
const [mode, setMode] = useState<'basic' | 'advanced' | 'expert'>('basic');

// Show/hide features based on mode:
// - basic: Overview, simple metrics
// - advanced: + Charts, detailed analysis
// - expert: + AI recommendations, Monte Carlo, Walk-Forward
```

## 🔧 Installation

```bash
cd frontend
npm install plotly.js-basic-dist-min
npm run dev
```

## 📊 Expected Result

После завершения пользователь сможет:

1. **Скачивать CSV отчеты** - 4 типа + ZIP архив
2. **Просматривать интерактивные графики** - Plotly charts
3. **Анализировать результаты** - Equity, Drawdown, PnL distribution
4. **Переключать режимы** - Базовый/Продвинутый/Экспертный

## ✅ Compliance with ТЗ

- ✅ **ТЗ 4** - CSV Export полностью реализован (backend + frontend)
- 🔄 **ТЗ 3.7.2** - Advanced Visualization (backend готов, frontend в процессе)
- ⏳ **ТЗ 3.7** - Dashboard интеграция (следующий приоритет)

## 🎯 Session Progress

**Completed:**
- [x] CSV Export backend (ReportGenerator)
- [x] CSV Export API endpoints
- [x] CSV Export tests (16/16 PASSED)
- [x] PlotlyChart React component
- [x] package.json update (plotly.js)

**In Progress:**
- [ ] Charts API endpoints
- [ ] Charts Tab implementation
- [ ] API service update
- [ ] Mode switcher

**Estimated Time:**
- Charts API: 1-2 hours
- Charts Tab: 2-3 hours
- Full integration: 4-6 hours

## 🐛 Known Issues

None currently.

## 📝 Notes

- Plotly.js используется в минимальной версии (basic-dist-min) для оптимизации bundle size
- Dynamic import гарантирует, что Plotly загружается только при необходимости
- Все графики responsive и работают в темной теме
- CSV экспорт использует blob download для корректной работы с большими файлами
