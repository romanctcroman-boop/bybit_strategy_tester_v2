import React, { Suspense, lazy } from 'react';
import { HashRouter, Routes, Route, Link } from 'react-router-dom';

// Chart Pages
const TestChartPage = lazy(() => import('./pages/TestChartPage'));
const TradingViewDemo = lazy(() => import('./pages/TradingViewDemo'));

import NotificationsProvider from './components/NotificationsProvider';
import ApiHealthIndicator from './components/ApiHealthIndicator';
import TopProgressBar from './components/TopProgressBar';

const App: React.FC = () => {
  return (
    <NotificationsProvider>
      <TopProgressBar />
      <HashRouter>
        <nav
          style={{
            padding: '12px 20px',
            display: 'flex',
            gap: 16,
            alignItems: 'center',
            background: '#f5f5f5',
            borderBottom: '1px solid #ddd',
          }}
        >
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <Link to="/test-chart" style={{ textDecoration: 'none', color: 'inherit' }}>
              <strong>Test Chart</strong>
            </Link>
            <Link to="/tv-demo" style={{ textDecoration: 'none', color: '#666' }}>
              TradingView Demo
            </Link>
          </div>
          <div style={{ marginLeft: 'auto' }}>
            <ApiHealthIndicator />
          </div>
        </nav>
        <Suspense fallback={<div style={{ padding: 20 }}>Loading...</div>}>
          <Routes>
            {/* Test Chart - Main Page */}
            <Route path="/" element={<TestChartPage />} />
            <Route path="/test-chart" element={<TestChartPage />} />

            {/* TradingView Demo */}
            <Route path="/tv-demo" element={<TradingViewDemo />} />
          </Routes>
        </Suspense>
      </HashRouter>
    </NotificationsProvider>
  );
};

export default App;
