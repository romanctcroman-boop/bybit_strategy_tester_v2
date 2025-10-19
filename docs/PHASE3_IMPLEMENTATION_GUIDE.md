# Phase 3: Frontend Development - Implementation Guide

## 🎉 Статус: В ПРОЦЕССЕ (30%)

Дата начала: 17 октября 2025  
Текущий прогресс: Базовая структура готова

---

## ✅ Что уже создано

### 1. Configuration Files ✅

- ✅ `vite.config.ts` - Vite bundler config с proxy для API
- ✅ `tsconfig.json` - TypeScript config с path mapping
- ✅ `tsconfig.node.json` - TypeScript config для Vite

### 2. Type Definitions ✅

- ✅ `src/types/index.ts` (200+ lines)
  - Candle, Strategy, BacktestResult
  - OptimizationRequest, OptimizationResult
  - WalkForwardWindow, WebSocketMessage
  - AppSettings, AppError

### 3. Services ✅

- ✅ `src/services/api.ts` (200 lines) - HTTP client с axios
  - Health check, candles, symbols
  - Strategies CRUD
  - Backtest run/get/list
  - Optimization start/get/cancel/list
- ✅ `src/services/websocket.ts` (200 lines) - WebSocket client
  - Auto-reconnect logic
  - Heartbeat (ping/pong)
  - Subscribe/unsubscribe to tasks
  - Event handlers (onMessage, onError, onConnect, onDisconnect)

### 4. State Management ✅

- ✅ `src/store/index.ts` (160 lines) - Zustand store
  - Settings, errors, loading
  - Strategies, market data
  - Backtests, optimizations
  - WebSocket connection state
  - Progress tracking per task

### 5. Main App Structure ✅

- ✅ `src/main.tsx` - React entry point
- ✅ `src/App.tsx` - Main app with routing & theme

---

## ⏳ Что нужно создать

### Приоритет 1: Core Components (Required)

#### `src/components/Layout/Layout.tsx`

```tsx
import React from 'react';
import { Box, AppBar, Toolbar, Typography, Drawer } from '@mui/material';
import Sidebar from './Sidebar';

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar position="fixed">
        <Toolbar>
          <Typography variant="h6">Bybit Strategy Tester</Typography>
        </Toolbar>
      </AppBar>
      <Drawer variant="permanent">
        <Toolbar /> {/* Spacer */}
        <Sidebar />
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar /> {/* Spacer */}
        {children}
      </Box>
    </Box>
  );
};

export default Layout;
```

#### `src/components/Layout/Sidebar.tsx`

```tsx
import React from 'react';
import { List, ListItem, ListItemIcon, ListItemText } from '@mui/material';
import { Link } from 'react-router-dom';
import { Dashboard, TrendingUp, Assessment, Settings } from '@mui/icons-material';

const menuItems = [
  { text: 'Dashboard', icon: <Dashboard />, path: '/' },
  { text: 'Optimization', icon: <TrendingUp />, path: '/optimization' },
  { text: 'Backtest', icon: <Assessment />, path: '/backtest' },
  { text: 'Settings', icon: <Settings />, path: '/settings' },
];

export const Sidebar: React.FC = () => {
  return (
    <List>
      {menuItems.map((item) => (
        <ListItem button component={Link} to={item.path} key={item.text}>
          <ListItemIcon>{item.icon}</ListItemIcon>
          <ListItemText primary={item.text} />
        </ListItem>
      ))}
    </List>
  );
};

export default Sidebar;
```

### Приоритет 2: Pages (Required)

#### `src/pages/Dashboard.tsx`

```tsx
import React, { useEffect } from 'react';
import { Box, Grid, Card, CardContent, Typography } from '@mui/material';
import { useAppStore } from '../store';
import { apiService } from '../services/api';

export const Dashboard: React.FC = () => {
  const { backtests, optimizations } = useAppStore();

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6">Recent Backtests</Typography>
              <Typography variant="h2">{backtests.length}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6">Optimizations</Typography>
              <Typography variant="h2">{optimizations.length}</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
```

#### `src/pages/OptimizationPage.tsx`

```tsx
import React, { useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import { useAppStore } from '../store';
import { apiService } from '../services/api';
import type { OptimizationRequest, OptimizationMethod } from '../types';

export const OptimizationPage: React.FC = () => {
  const { addOptimization, addError } = useAppStore();
  const [method, setMethod] = useState<OptimizationMethod>('bayesian');
  const [loading, setLoading] = useState(false);

  const handleStartOptimization = async () => {
    setLoading(true);
    try {
      const request: OptimizationRequest = {
        method,
        strategy_class: 'MA_Crossover',
        symbol: 'BTCUSDT',
        timeframe: '15',
        start_date: '2024-01-01T00:00:00',
        end_date: '2024-12-31T23:59:59',
        initial_capital: 10000,
        commission: 0.001,
        parameters: {
          fast_period: { min: 5, max: 50, step: 5 },
          slow_period: { min: 20, max: 200, step: 10 },
        },
        n_trials: 50, // for Bayesian
      };

      const result = await apiService.startOptimization(request);
      addOptimization(result);
      console.log('Optimization started:', result.task_id);
    } catch (error: any) {
      addError({
        message: 'Failed to start optimization',
        details: error.message,
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Strategy Optimization
      </Typography>
      <Card>
        <CardContent>
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Method</InputLabel>
            <Select
              value={method}
              onChange={(e) => setMethod(e.target.value as OptimizationMethod)}
            >
              <MenuItem value="grid_search">Grid Search</MenuItem>
              <MenuItem value="walk_forward">Walk-Forward</MenuItem>
              <MenuItem value="bayesian">Bayesian</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant="contained"
            onClick={handleStartOptimization}
            disabled={loading}
            fullWidth
          >
            {loading ? 'Starting...' : 'Start Optimization'}
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
};

export default OptimizationPage;
```

#### `src/pages/BacktestPage.tsx`

```tsx
import React from 'react';
import { Box, Typography } from '@mui/material';

export const BacktestPage: React.FC = () => {
  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Backtest
      </Typography>
      <Typography variant="body1">Backtest functionality coming soon...</Typography>
    </Box>
  );
};

export default BacktestPage;
```

#### `src/pages/SettingsPage.tsx`

```tsx
import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Switch,
  FormControlLabel,
} from '@mui/material';
import { useAppStore } from '../store';

export const SettingsPage: React.FC = () => {
  const { settings, updateSettings } = useAppStore();

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>
      <Card>
        <CardContent>
          <TextField
            fullWidth
            label="API Base URL"
            value={settings.apiBaseUrl}
            onChange={(e) => updateSettings({ apiBaseUrl: e.target.value })}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="WebSocket URL"
            value={settings.wsBaseUrl}
            onChange={(e) => updateSettings({ wsBaseUrl: e.target.value })}
            sx={{ mb: 2 }}
          />
          <FormControlLabel
            control={
              <Switch
                checked={settings.autoConnect}
                onChange={(e) => updateSettings({ autoConnect: e.target.checked })}
              />
            }
            label="Auto-connect WebSocket"
          />
        </CardContent>
      </Card>
    </Box>
  );
};

export default SettingsPage;
```

### Приоритет 3: Chart Components (Recommended)

#### `src/components/Charts/CandleChart.tsx`

```tsx
import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi } from 'lightweight-charts';
import type { Candle } from '../../types';

interface Props {
  data: Candle[];
  height?: number;
}

export const CandleChart: React.FC<Props> = ({ data, height = 400 }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { color: '#1e1e1e' },
        textColor: '#ffffff',
      },
      grid: {
        vertLines: { color: '#2e2e2e' },
        horzLines: { color: '#2e2e2e' },
      },
    });

    const candleSeries = chart.addCandlestickSeries();

    const formattedData = data.map((candle) => ({
      time: new Date(candle.timestamp).getTime() / 1000,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    }));

    candleSeries.setData(formattedData);
    chartRef.current = chart;

    return () => chart.remove();
  }, [data, height]);

  return <div ref={chartContainerRef} />;
};

export default CandleChart;
```

### Приоритет 4: Additional Files

#### `index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Bybit Strategy Tester</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

#### `src/App.css`

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Roboto', sans-serif;
}

#root {
  width: 100%;
  height: 100vh;
}
```

---

## 🚀 Запуск приложения

### 1. Установить зависимости (если не установлены)

```powershell
cd frontend
npm install
```

### 2. Создать недостающие компоненты

Скопировать код выше в соответствующие файлы:

- `src/components/Layout/Layout.tsx`
- `src/components/Layout/Sidebar.tsx`
- `src/pages/Dashboard.tsx`
- `src/pages/OptimizationPage.tsx`
- `src/pages/BacktestPage.tsx`
- `src/pages/SettingsPage.tsx`
- `src/components/Charts/CandleChart.tsx`
- `index.html` (в корне frontend/)
- `src/App.css`

### 3. Запустить dev server

```powershell
npm run dev
```

### 4. Запустить Electron (опционально)

```powershell
npm run electron:dev
```

---

## 📋 Следующие шаги

### Phase 3.1: Завершить базовый UI ✅

1. ✅ Создать Layout и Sidebar
2. ✅ Создать все Pages (Dashboard, Optimization, Backtest, Settings)
3. ✅ Добавить базовую навигацию

### Phase 3.2: Chart Integration 🔄

1. ⏳ Интегрировать TradingView Lightweight Charts
2. ⏳ Создать CandleChart component
3. ⏳ Создать EquityCurveChart component
4. ⏳ Добавить indicators overlay

### Phase 3.3: Real-time Updates 🔄

1. ⏳ WebSocket integration для progress updates
2. ⏳ Progress bars для optimization tasks
3. ⏳ Live chart updates
4. ⏳ Notifications system

### Phase 3.4: Polish & Testing 🔄

1. ⏳ Responsive design
2. ⏳ Error handling & loading states
3. ⏳ Form validation
4. ⏳ E2E testing

---

## 🐛 Известные проблемы

### 1. Line Endings (CRLF vs LF)

**Проблема:** ESLint ошибки "Delete `␍`"  
**Решение:** Настроить Git для автоконвертации:

```powershell
git config core.autocrlf true
```

### 2. Missing @types/react-dom

**Проблема:** TypeScript не может найти типы для react-dom/client  
**Решение:**

```powershell
npm install --save-dev @types/react-dom
```

### 3. Module Resolution

**Проблема:** Cannot find module '@types/index'  
**Решение:** Уже исправлено - используем относительные пути `../types`

---

## 💡 Полезные команды

```powershell
# Development
npm run dev                 # Start Vite dev server
npm run electron:dev        # Start Electron + Vite

# Build
npm run build              # Build for production
npm run electron:build     # Build Electron app

# Linting
npm run lint               # Run ESLint
npm run lint:fix           # Auto-fix ESLint errors

# Testing
npm test                   # Run tests (если настроены)
```

---

## 📊 Текущий прогресс

| Компонент         | Статус     | Прогресс |
| ----------------- | ---------- | -------- |
| Configuration     | ✅ Done    | 100%     |
| Type Definitions  | ✅ Done    | 100%     |
| API Service       | ✅ Done    | 100%     |
| WebSocket Service | ✅ Done    | 100%     |
| Zustand Store     | ✅ Done    | 100%     |
| Main App          | ✅ Done    | 100%     |
| Layout Components | ⏳ Pending | 0%       |
| Pages             | ⏳ Pending | 0%       |
| Chart Components  | ⏳ Pending | 0%       |
| Real-time Updates | ⏳ Pending | 0%       |
| UI Polish         | ⏳ Pending | 0%       |

**Overall Progress: 30%**

---

## 🎯 Следующая сессия

Приоритеты для продолжения:

1. ✅ Создать все компоненты из секции "Что нужно создать"
2. ✅ Запустить `npm run dev` и проверить что приложение загружается
3. ✅ Протестировать навигацию между страницами
4. ✅ Протестировать запуск optimization через UI
5. ✅ Добавить chart components с TradingView

**Estimated time to complete Phase 3:** 4-6 hours

---

Готовы продолжить? Следующий шаг — создать все недостающие компоненты! 🚀
