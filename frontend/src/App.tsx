import React, { Suspense, lazy, useMemo } from 'react';
import { HashRouter, Routes, Route, Link } from 'react-router-dom';
import {
  Box,
  CircularProgress,
  Container,
  ThemeProvider as MuiThemeProvider,
  CssBaseline,
} from '@mui/material';

// Lazy load pages
const TestChartPage = lazy(() => import('./pages/TestChartPage'));
const HomePage = lazy(() => import('./pages/HomePage'));
const AIStudioPage = lazy(() => import('./pages/AIStudioPage'));
const OptimizerPage = lazy(() => import('./pages/OptimizerPage'));
const BacktestsPage = lazy(() => import('./pages/BacktestsPage'));
const StrategiesPage = lazy(() => import('./pages/StrategiesPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));

import GlobalProviders from './components/GlobalProviders';
import ApiHealthIndicator from './components/ApiHealthIndicator';
import TopProgressBar from './components/TopProgressBar';
import ProtectedRoute from './components/ProtectedRoute';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeToggle } from './components/ThemeToggle';
import { lightTheme } from './theme/light';
import { darkTheme } from './theme/dark';

// Suspense fallback component
const PageLoader: React.FC = () => (
  <Container>
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '60vh',
        flexDirection: 'column',
        gap: 2,
      }}
    >
      <CircularProgress size={48} />
      <Box sx={{ color: 'text.secondary' }}>Загрузка...</Box>
    </Box>
  </Container>
);

// User info display component
const UserInfoDisplay: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();

  if (!isAuthenticated || !user) {
    return null;
  }

  return (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
      <Box sx={{ fontSize: '0.875rem', color: '#fff', opacity: 0.9 }}>
        👤 {user.user_id || user.user || 'User'}
      </Box>
      <button
        onClick={logout}
        style={{
          background: 'rgba(255, 255, 255, 0.1)',
          border: '1px solid rgba(255, 255, 255, 0.2)',
          color: '#fff',
          padding: '4px 12px',
          borderRadius: 4,
          cursor: 'pointer',
          fontSize: '0.875rem',
        }}
      >
        Logout
      </button>
    </Box>
  );
};

// Inner component that uses theme
const AppContent: React.FC = () => {
  const { mode } = useTheme();
  const theme = useMemo(() => (mode === 'light' ? lightTheme : darkTheme), [mode]);

  return (
    <MuiThemeProvider theme={theme}>
      <CssBaseline />
      <TopProgressBar />
      <HashRouter>
        <nav
          style={{
            padding: '12px 20px',
            display: 'flex',
            gap: 16,
            alignItems: 'center',
            background: mode === 'light' ? '#1976d2' : '#1e1e1e',
            borderBottom: mode === 'light' ? '1px solid #115293' : '1px solid #333',
            color: '#fff',
          }}
        >
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <Link to="/" style={{ textDecoration: 'none', color: '#fff', fontWeight: 600 }}>
              🏠 Home
            </Link>
            <Link to="/ai-studio" style={{ textDecoration: 'none', color: '#fff' }}>
              🤖 AI Studio
            </Link>
            <Link to="/backtests" style={{ textDecoration: 'none', color: '#fff' }}>
              📊 Backtests
            </Link>
            <Link to="/optimizations" style={{ textDecoration: 'none', color: '#fff' }}>
              ⚙️ Optimizer
            </Link>
            <Link to="/strategies" style={{ textDecoration: 'none', color: '#fff' }}>
              📈 Strategies
            </Link>
            <Link to="/test-chart" style={{ textDecoration: 'none', color: '#fff' }}>
              📉 Charts
            </Link>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, alignItems: 'center' }}>
            <UserInfoDisplay />
            <ThemeToggle />
            <ApiHealthIndicator />
          </div>
        </nav>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public: Login & Register */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Protected: Home Dashboard */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <HomePage />
                </ProtectedRoute>
              }
            />

            {/* Protected: AI Studio */}
            <Route
              path="/ai-studio"
              element={
                <ProtectedRoute>
                  <AIStudioPage />
                </ProtectedRoute>
              }
            />

            {/* Protected: Backtests */}
            <Route
              path="/backtests"
              element={
                <ProtectedRoute>
                  <BacktestsPage />
                </ProtectedRoute>
              }
            />

            {/* Protected: Optimizer */}
            <Route
              path="/optimizations"
              element={
                <ProtectedRoute>
                  <OptimizerPage />
                </ProtectedRoute>
              }
            />

            {/* Protected: Strategies */}
            <Route
              path="/strategies"
              element={
                <ProtectedRoute>
                  <StrategiesPage />
                </ProtectedRoute>
              }
            />

            {/* Protected: Test Chart */}
            <Route
              path="/test-chart"
              element={
                <ProtectedRoute>
                  <TestChartPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Suspense>
      </HashRouter>
    </MuiThemeProvider>
  );
};

const App: React.FC = () => {
  return (
    <GlobalProviders>
      <ThemeProvider>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </ThemeProvider>
    </GlobalProviders>
  );
};

export default App;
