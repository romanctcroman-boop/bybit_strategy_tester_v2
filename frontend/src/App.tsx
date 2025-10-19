import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard';
import OptimizationPage from './pages/OptimizationPage';
import BacktestPage from './pages/BacktestPage';
import DataPage from './pages/DataPage';
import SettingsPage from './pages/SettingsPage';
import { useAppStore } from './store';
import { wsService } from './services/websocket';
import './App.css';

const App: React.FC = () => {
  const { settings, setWsConnected } = useAppStore();

  // Create theme based on settings
  const theme = React.useMemo(
    () =>
      createTheme({
        palette: {
          mode: settings.theme,
          primary: {
            main: '#1976d2',
          },
          secondary: {
            main: '#dc004e',
          },
        },
      }),
    [settings.theme]
  );

  // WebSocket connection management
  useEffect(() => {
    if (settings.autoConnect) {
      wsService.connect();

      const unsubscribeConnect = wsService.onConnect(() => {
        console.log('[App] WebSocket connected');
        setWsConnected(true);
      });

      const unsubscribeDisconnect = wsService.onDisconnect(() => {
        console.log('[App] WebSocket disconnected');
        setWsConnected(false);
      });

      return () => {
        unsubscribeConnect();
        unsubscribeDisconnect();
        wsService.disconnect();
      };
    }
  }, [settings.autoConnect, setWsConnected]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/optimization" element={<OptimizationPage />} />
            <Route path="/backtest" element={<BacktestPage />} />
            <Route path="/data" element={<DataPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default App;
