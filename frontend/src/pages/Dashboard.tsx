import React, { useEffect } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  CircularProgress,
  Alert,
} from '@mui/material';
import { TrendingUp, Assessment, CheckCircle } from '@mui/icons-material';
import { useAppStore } from '../store';
import { api } from '../services/api';

const Dashboard: React.FC = () => {
  const {
    backtests,
    optimizations,
    loading,
    error,
    setBacktests,
    setOptimizations,
    setLoading,
    setError,
  } = useAppStore();

  useEffect(() => {
    const loadDashboardData = async () => {
      setLoading(true);
      try {
        // Load recent backtests and optimizations
        const [backtestData, optimizationData] = await Promise.all([
          api.backtest.list({ limit: 5 }),
          api.optimization.list({ limit: 5 }),
        ]);

        setBacktests(backtestData);
        setOptimizations(optimizationData);
        setError(null);
      } catch (err) {
        setError({
          id: 'dashboard-error',
          message: 'Failed to load dashboard data',
          severity: 'error',
          timestamp: new Date(),
        });
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, [setBacktests, setOptimizations, setLoading, setError]);

  const stats = {
    totalBacktests: backtests.length,
    totalOptimizations: optimizations.length,
    completedBacktests: backtests.filter((b) => b.status === 'completed').length,
    completedOptimizations: optimizations.filter((o) => o.status === 'SUCCESS').length,
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight="bold">
        📊 Dashboard
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error.message}
        </Alert>
      )}

      {loading ? (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={60} />
        </Box>
      ) : (
        <>
          {/* Stats Cards */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Card sx={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
                <CardContent>
                  <Box display="flex" alignItems="center" justifyContent="space-between">
                    <Box>
                      <Typography variant="h4" color="white" fontWeight="bold">
                        {stats.totalBacktests}
                      </Typography>
                      <Typography variant="body2" color="white" sx={{ opacity: 0.9 }}>
                        Total Backtests
                      </Typography>
                    </Box>
                    <Assessment sx={{ fontSize: 48, color: 'white', opacity: 0.7 }} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card sx={{ background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' }}>
                <CardContent>
                  <Box display="flex" alignItems="center" justifyContent="space-between">
                    <Box>
                      <Typography variant="h4" color="white" fontWeight="bold">
                        {stats.totalOptimizations}
                      </Typography>
                      <Typography variant="body2" color="white" sx={{ opacity: 0.9 }}>
                        Total Optimizations
                      </Typography>
                    </Box>
                    <TrendingUp sx={{ fontSize: 48, color: 'white', opacity: 0.7 }} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card sx={{ background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' }}>
                <CardContent>
                  <Box display="flex" alignItems="center" justifyContent="space-between">
                    <Box>
                      <Typography variant="h4" color="white" fontWeight="bold">
                        {stats.completedBacktests}
                      </Typography>
                      <Typography variant="body2" color="white" sx={{ opacity: 0.9 }}>
                        Completed Backtests
                      </Typography>
                    </Box>
                    <CheckCircle sx={{ fontSize: 48, color: 'white', opacity: 0.7 }} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card sx={{ background: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)' }}>
                <CardContent>
                  <Box display="flex" alignItems="center" justifyContent="space-between">
                    <Box>
                      <Typography variant="h4" color="white" fontWeight="bold">
                        {stats.completedOptimizations}
                      </Typography>
                      <Typography variant="body2" color="white" sx={{ opacity: 0.9 }}>
                        Completed Optimizations
                      </Typography>
                    </Box>
                    <CheckCircle sx={{ fontSize: 48, color: 'white', opacity: 0.7 }} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Recent Activity */}
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom fontWeight="bold">
                  Recent Backtests
                </Typography>
                {backtests.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No backtests found. Run your first backtest!
                  </Typography>
                ) : (
                  <Box>
                    {backtests.slice(0, 5).map((backtest) => (
                      <Box
                        key={backtest.id}
                        sx={{
                          py: 1.5,
                          borderBottom: '1px solid',
                          borderColor: 'divider',
                          '&:last-child': { borderBottom: 'none' },
                        }}
                      >
                        <Typography variant="body2" fontWeight="medium">
                          {backtest.strategy_name || 'Unnamed Strategy'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {backtest.symbol} • {backtest.timeframe} • {backtest.status}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                )}
              </Paper>
            </Grid>

            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom fontWeight="bold">
                  Recent Optimizations
                </Typography>
                {optimizations.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No optimizations found. Start optimizing!
                  </Typography>
                ) : (
                  <Box>
                    {optimizations.slice(0, 5).map((optimization) => (
                      <Box
                        key={optimization.task_id}
                        sx={{
                          py: 1.5,
                          borderBottom: '1px solid',
                          borderColor: 'divider',
                          '&:last-child': { borderBottom: 'none' },
                        }}
                      >
                        <Typography variant="body2" fontWeight="medium">
                          {optimization.method?.toUpperCase() || 'Unknown Method'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Status: {optimization.status}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                )}
              </Paper>
            </Grid>
          </Grid>
        </>
      )}
    </Box>
  );
};

export default Dashboard;
