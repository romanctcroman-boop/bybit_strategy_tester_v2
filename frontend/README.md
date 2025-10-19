# Bybit Strategy Tester v2.0 - Frontend

React + TypeScript + Electron desktop application for backtesting and optimizing trading strategies.

## ✅ Phase 3 Frontend Development - COMPLETED

### Components Created

#### Layout Components

- **Layout.tsx** - Main application layout with AppBar + Drawer
- **Sidebar.tsx** - Navigation sidebar with 5 menu items (Dashboard, Optimization, Backtest, Market Data, Settings)

#### Pages

- **Dashboard.tsx** - Overview page with stats cards and recent activity
- **OptimizationPage.tsx** - Placeholder for optimization features
- **BacktestPage.tsx** - Placeholder for backtest execution
- **DataPage.tsx** - Placeholder for market data management
- **SettingsPage.tsx** - Placeholder for application settings

### Running the Application

#### Web Browser (Development)

```powershell
cd d:\bybit_strategy_tester_v2\frontend
npm run dev
```

Then open http://localhost:5173

#### Electron Desktop App

```powershell
cd d:\bybit_strategy_tester_v2\frontend
npm run electron:dev
```

### Tech Stack

- **React 18.2.0** - UI library
- **TypeScript 5.3.3** - Type safety
- **Material-UI 5.15.3** - Component library
- **React Router 6.21.1** - Client-side routing
- **Zustand 4.4.7** - State management
- **Vite 5.0.10** - Build tool
- **Electron 28.1.3** - Desktop wrapper

### Features Implemented

✅ Navigation sidebar with active route highlighting  
✅ Dashboard with stats cards (4 gradient cards)  
✅ Recent backtests and optimizations display  
✅ Layout with fixed AppBar and permanent Drawer  
✅ Routing for all 5 pages  
✅ Light/dark theme support  
✅ WebSocket connection setup  
✅ API client with organized endpoints  
✅ Zustand store with error handling

### Next Steps (Future Phases)

- Implement full Optimization page with parameter configuration
- Implement full Backtest page with strategy selection and results visualization
- Add CandleChart component with lightweight-charts
- Add real-time data updates via WebSocket
- Add optimization progress tracking
- Add backtest result analysis charts

### API Integration

The frontend connects to the FastAPI backend at `http://localhost:8000/api/v1`

Backend must be running for full functionality:

```powershell
cd d:\bybit_strategy_tester_v2
python -m uvicorn backend.api.main:app --reload
```

### Known Issues

- CRLF line ending warnings (cosmetic only, doesn't affect functionality)
- Placeholder pages need full implementation
- Chart components not yet created

### Lint

```powershell
npm run lint        # Check for errors
npm run lint:fix    # Auto-fix formatting
```
