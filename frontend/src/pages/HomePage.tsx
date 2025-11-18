/**
 * HomePage Component - Enhanced Dashboard
 * AI-First Trading Dashboard with KPI Cards, Real-time Charts, Strategy Explorer
 *
 * Features:
 * - KPI Cards: Total P&L, Win Rate, Active Bots, Sharpe Ratio
 * - Real-time Chart Integration (TradingView)
 * - Strategy Explorer with Quick Actions
 * - AI Assistant Quick Access
 * - Recent Activity Feed
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Card,
  CardContent,
  Typography,
  Grid,
  Box,
  Button,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  SmartToy,
  ShowChart,
  Settings,
  PlayArrow,
  Psychology,
} from '@mui/icons-material';
import axios from 'axios';

// ✅ Импорт централизованных утилит форматирования (Quick Win #3)
import { formatCurrency, formatPercentage, formatRelativeTime } from '../utils/formatting';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface KPIData {
  totalPnL: number;
  winRate: number;
  activeBots: number;
  sharpeRatio: number;
  totalTrades: number;
  avgTradeReturn: number;
}

interface RecentActivity {
  id: string;
  type: 'backtest' | 'optimization' | 'bot_started' | 'bot_stopped';
  message: string;
  timestamp: string;
  status: 'success' | 'error' | 'running';
}

const HomePage: React.FC = () => {
  const [kpiData, setKpiData] = useState<KPIData>({
    totalPnL: 0,
    winRate: 0,
    activeBots: 0,
    sharpeRatio: 0,
    totalTrades: 0,
    avgTradeReturn: 0,
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>([]);

  // Fetch KPI data from backend
  useEffect(() => {
    const fetchKPIData = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_BASE_URL}/api/dashboard/kpi`);
        setKpiData(response.data);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch KPI data:', err);
        // Use mock data for development
        setKpiData({
          totalPnL: 12450.75,
          winRate: 62.5,
          activeBots: 3,
          sharpeRatio: 1.85,
          totalTrades: 247,
          avgTradeReturn: 2.3,
        });
        setError('Using mock data - API unavailable');
      } finally {
        setLoading(false);
      }
    };

    const fetchRecentActivity = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/dashboard/activity`);
        setRecentActivity(response.data);
      } catch {
        // Mock data
        setRecentActivity([
          {
            id: '1',
            type: 'backtest',
            message: 'Backtest completed: SR Mean Reversion (5m)',
            timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
            status: 'success',
          },
          {
            id: '2',
            type: 'optimization',
            message: 'Optimization running: CatBoost optimizer',
            timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
            status: 'running',
          },
          {
            id: '3',
            type: 'bot_started',
            message: 'Bot started: EMA Crossover',
            timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
            status: 'success',
          },
        ]);
      }
    };

    fetchKPIData();
    fetchRecentActivity();

    // Refresh KPI every 30 seconds
    const interval = setInterval(fetchKPIData, 30000);
    return () => clearInterval(interval);
  }, []);

  // ✅ Функции форматирования теперь импортированы из ../utils/formatting

  return (
    <Box sx={{ p: 3, backgroundColor: '#f5f5f5', minHeight: '100vh' }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom sx={{ fontWeight: 600 }}>
          📊 Trading Dashboard
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Real-time overview of your trading strategies and performance
        </Typography>
      </Box>

      {/* Alert for API errors */}
      {error && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* KPI Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Total P&L */}
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                {kpiData.totalPnL >= 0 ? (
                  <TrendingUp sx={{ color: '#4caf50', mr: 1 }} />
                ) : (
                  <TrendingDown sx={{ color: '#f44336', mr: 1 }} />
                )}
                <Typography variant="body2" color="text.secondary">
                  Total P&L
                </Typography>
              </Box>
              <Typography
                variant="h4"
                sx={{ fontWeight: 600, color: kpiData.totalPnL >= 0 ? '#4caf50' : '#f44336' }}
              >
                {loading ? '...' : formatCurrency(kpiData.totalPnL)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {kpiData.totalTrades} trades
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Win Rate */}
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <ShowChart sx={{ color: '#2196f3', mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  Win Rate
                </Typography>
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {loading ? '...' : formatPercentage(kpiData.winRate)}
              </Typography>
              <LinearProgress
                variant="determinate"
                value={kpiData.winRate}
                sx={{ mt: 1, height: 6, borderRadius: 3 }}
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Active Bots */}
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <SmartToy sx={{ color: '#ff9800', mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  Active Bots
                </Typography>
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {loading ? '...' : kpiData.activeBots}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Running strategies
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Sharpe Ratio */}
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Psychology sx={{ color: '#9c27b0', mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  Sharpe Ratio
                </Typography>
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {loading ? '...' : kpiData.sharpeRatio.toFixed(2)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Risk-adjusted return
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Quick Actions & AI Assistant */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Quick Actions */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                🚀 Quick Actions
              </Typography>
              <Grid container spacing={2} sx={{ mt: 1 }}>
                <Grid item xs={12} sm={6} md={3}>
                  <Button
                    component={Link}
                    to="/ai-studio"
                    fullWidth
                    variant="contained"
                    startIcon={<Psychology />}
                    sx={{ py: 1.5 }}
                  >
                    AI Studio
                  </Button>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Button
                    component={Link}
                    to="/backtests"
                    fullWidth
                    variant="outlined"
                    startIcon={<PlayArrow />}
                    sx={{ py: 1.5 }}
                  >
                    Run Backtest
                  </Button>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Button
                    component={Link}
                    to="/optimizations"
                    fullWidth
                    variant="outlined"
                    startIcon={<Settings />}
                    sx={{ py: 1.5 }}
                  >
                    Optimize
                  </Button>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Button
                    component={Link}
                    to="/strategies"
                    fullWidth
                    variant="outlined"
                    startIcon={<ShowChart />}
                    sx={{ py: 1.5 }}
                  >
                    Strategies
                  </Button>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* AI Assistant */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                🤖 AI Assistant
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Get AI-powered insights and strategy recommendations
              </Typography>
              <Button
                component={Link}
                to="/ai-studio"
                fullWidth
                variant="contained"
                color="secondary"
                startIcon={<Psychology />}
              >
                Open AI Studio
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Activity */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
            📋 Recent Activity
          </Typography>
          <Box sx={{ mt: 2 }}>
            {recentActivity.map((activity) => (
              <Box
                key={activity.id}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  py: 1.5,
                  borderBottom: '1px solid #e0e0e0',
                  '&:last-child': { borderBottom: 'none' },
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      backgroundColor:
                        activity.status === 'success'
                          ? '#4caf50'
                          : activity.status === 'running'
                            ? '#ff9800'
                            : '#f44336',
                      mr: 2,
                    }}
                  />
                  <Typography variant="body2">{activity.message}</Typography>
                </Box>
                <Typography variant="caption" color="text.secondary">
                  {formatRelativeTime(activity.timestamp)}
                </Typography>
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default HomePage;
