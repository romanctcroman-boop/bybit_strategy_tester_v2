import React, { Suspense, lazy } from 'react';
import { HashRouter, Routes, Route, Link } from 'react-router-dom';
const BotsPage = lazy(() => import('./pages/BotsPage'));
const ActiveBotsPage = lazy(() => import('./pages/ActiveBotsPage'));
const WizardCreateBot = lazy(() => import('./pages/WizardCreateBot'));
const AlgoBuilderPage = lazy(() => import('./pages/AlgoBuilderPage'));
const StrategiesPage = lazy(() => import('./pages/StrategiesPage'));
const StrategyBuilderPage = lazy(() => import('./pages/StrategyBuilderPage'));
const OptimizationsPage = lazy(() => import('./pages/OptimizationsPage'));
const OptimizationDetailPage = lazy(() => import('./pages/OptimizationDetailPage'));
const DataUploadPage = lazy(() => import('./pages/DataUploadPage'));
const BacktestsPage = lazy(() => import('./pages/BacktestsPage'));
const BacktestDetailPage = lazy(() => import('./pages/BacktestDetailPage'));
const StrategyDetailPage = lazy(() => import('./pages/StrategyDetailPage'));
const TestChartPage = lazy(() => import('./pages/TestChartPage'));
const DebugPage = lazy(() => import('./pages/DebugPage'));
const AdminBackfillPage = lazy(() => import('./pages/AdminBackfillPage'));
import NotificationsProvider from './components/NotificationsProvider';
import ApiHealthIndicator from './components/ApiHealthIndicator';
import TopProgressBar from './components/TopProgressBar';

const App: React.FC = () => {
  return (
    <NotificationsProvider>
      <TopProgressBar />
      <HashRouter>
        <nav
          style={{ padding: 12, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}
        >
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Link to="/">Bots</Link> | <Link to="/active">Active</Link> |{' '}
            <Link to="/strategy">Strategy</Link> | <Link to="/bots/create">Create</Link> |{' '}
            <Link to="/algo">Algo</Link> | <Link to="/strategies">Strategies</Link> |{' '}
            <Link to="/optimizations">Optimizations</Link> | <Link to="/upload">Uploads</Link> |{' '}
            <Link to="/backtests">Backtests</Link> | <Link to="/test-chart">Test Chart</Link> |{' '}
            <Link to="/admin/backfill">Admin Backfill</Link> | <Link to="/debug">Debug</Link>
          </div>
          <div style={{ marginLeft: 'auto' }}>
            <ApiHealthIndicator />
          </div>
        </nav>
        <Suspense fallback={null}>
          <Routes>
            <Route path="/" element={<BotsPage />} />
            <Route path="/active" element={<ActiveBotsPage />} />
            <Route path="/strategies" element={<StrategiesPage />} />
            <Route path="/strategy" element={<StrategyBuilderPage />} />
            <Route path="/strategy/:id" element={<StrategyDetailPage />} />
            <Route path="/bots/create" element={<WizardCreateBot />} />
            <Route path="/algo" element={<AlgoBuilderPage />} />
            <Route path="/optimizations" element={<OptimizationsPage />} />
            <Route path="/optimization/:id" element={<OptimizationDetailPage />} />
            <Route path="/upload" element={<DataUploadPage />} />
            <Route path="/backtests" element={<BacktestsPage />} />
            <Route path="/backtest/:id" element={<BacktestDetailPage />} />
            <Route path="/test-chart" element={<TestChartPage />} />
            <Route path="/admin/backfill" element={<AdminBackfillPage />} />
            <Route path="/debug" element={<DebugPage />} />
          </Routes>
        </Suspense>
      </HashRouter>
    </NotificationsProvider>
  );
};

export default App;
