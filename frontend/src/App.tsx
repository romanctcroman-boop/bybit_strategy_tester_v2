import React from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { StrategiesPage, OptimizationsPage, DataUploadPage, BacktestDetailPage } from './pages';
import NotificationsProvider from './components/NotificationsProvider';

const App: React.FC = () => {
  return (
    <NotificationsProvider>
      <BrowserRouter>
        <nav style={{ padding: 12 }}>
          <Link to="/">Strategies</Link> | <Link to="/optimizations">Optimizations</Link> | <Link to="/upload">Uploads</Link>
        </nav>
        <Routes>
          <Route path="/" element={<StrategiesPage />} />
          <Route path="/optimizations" element={<OptimizationsPage />} />
          <Route path="/upload" element={<DataUploadPage />} />
          <Route path="/backtest/:id" element={<BacktestDetailPage />} />
        </Routes>
      </BrowserRouter>
    </NotificationsProvider>
  );
};

export default App;
