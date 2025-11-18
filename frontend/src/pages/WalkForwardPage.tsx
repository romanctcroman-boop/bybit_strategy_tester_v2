/**
 * Walk-Forward Optimization Page (ТЗ 3.5.2, Task #10)
 *
 * Визуализация результатов Walk-Forward Optimization:
 * - Timeline с периодами IS/OOS
 * - Efficiency metrics (OOS/IS ratios)
 * - Parameter stability charts
 * - Aggregated performance metrics
 */
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Grid,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useTheme,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Timeline as TimelineIcon,
  TrendingUp as TrendingUpIcon,
  Analytics as AnalyticsIcon,
} from '@mui/icons-material';
import { useNotify } from '../components/NotificationsProvider';
import { OptimizationsApi } from '../services/api';

// ✅ Импорт централизованных утилит форматирования (Quick Win #3)
import { formatDate } from '../utils/formatting';

interface WFOPeriod {
  period_num: number;
  in_sample_start: string;
  in_sample_end: string;
  out_sample_start: string;
  out_sample_end: string;
  best_params: Record<string, any>;
  is_sharpe: number;
  is_net_profit: number;
  is_total_trades: number;
  oos_sharpe: number;
  oos_net_profit: number;
  oos_total_trades: number;
  oos_max_drawdown: number;
  oos_win_rate: number;
  efficiency: number;
}

interface WFOResults {
  walk_results: WFOPeriod[];
  aggregated_metrics: {
    avg_oos_sharpe: number;
    avg_efficiency: number;
    total_periods: number;
    profitable_periods: number;
    avg_oos_net_profit: number;
    avg_oos_max_drawdown: number;
    avg_oos_win_rate: number;
  };
  parameter_stability: Record<
    string,
    {
      values: any[];
      std_dev: number;
      coefficient_of_variation: number;
    }
  >;
}

const WalkForwardPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const optimizationId = parseInt(id || '0', 10);
  const notify = useNotify();
  const theme = useTheme();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [wfoResults, setWfoResults] = useState<WFOResults | null>(null);
  const [viewMode, setViewMode] = useState<'timeline' | 'metrics' | 'stability'>('timeline');

  // Fetch WFO results
  useEffect(() => {
    const fetchResults = async () => {
      setLoading(true);
      setError('');

      try {
        // Get optimization data with WFO results
        const optimization = await OptimizationsApi.get(optimizationId);

        if (!optimization.results || !optimization.results.walk_results) {
          throw new Error('No Walk-Forward results found for this optimization');
        }

        const wfoData: WFOResults = {
          walk_results: optimization.results.walk_results || [],
          aggregated_metrics: optimization.results.aggregated_metrics || {},
          parameter_stability: optimization.results.parameter_stability || {},
        };

        setWfoResults(wfoData);
      } catch (err: any) {
        const message = err?.message || 'Failed to load Walk-Forward results';
        setError(message);
        notify({ message, severity: 'error' });
      } finally {
        setLoading(false);
      }
    };

    if (optimizationId) {
      fetchResults();
    }
  }, [optimizationId, notify]);

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ mt: 4 }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error || !wfoResults) {
    return (
      <Container maxWidth="xl" sx={{ mt: 4 }}>
        <Alert severity="error">{error || 'No Walk-Forward results found'}</Alert>
      </Container>
    );
  }

  const { walk_results, aggregated_metrics, parameter_stability } = wfoResults;

  // Helper to get efficiency color
  const getEfficiencyColor = (efficiency: number) => {
    if (efficiency >= 0.8) return theme.palette.success.main;
    if (efficiency >= 0.6) return theme.palette.warning.main;
    return theme.palette.error.main;
  };

  // ✅ formatDate теперь импортирована из ../utils/formatting

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Typography variant="h4">
          <TimelineIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          Walk-Forward Optimization
        </Typography>

        <ToggleButtonGroup
          size="small"
          value={viewMode}
          exclusive
          onChange={(_, newMode) => newMode && setViewMode(newMode)}
        >
          <ToggleButton value="timeline">
            <TimelineIcon sx={{ mr: 0.5 }} />
            Timeline
          </ToggleButton>
          <ToggleButton value="metrics">
            <TrendingUpIcon sx={{ mr: 0.5 }} />
            Metrics
          </ToggleButton>
          <ToggleButton value="stability">
            <AnalyticsIcon sx={{ mr: 0.5 }} />
            Stability
          </ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      {/* Aggregated Metrics Summary */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom variant="body2">
                Avg OOS Sharpe
              </Typography>
              <Typography variant="h5">{aggregated_metrics.avg_oos_sharpe.toFixed(2)}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom variant="body2">
                Avg Efficiency
              </Typography>
              <Typography
                variant="h5"
                sx={{ color: getEfficiencyColor(aggregated_metrics.avg_efficiency) }}
              >
                {(aggregated_metrics.avg_efficiency * 100).toFixed(1)}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom variant="body2">
                Profitable Periods
              </Typography>
              <Typography variant="h5">
                {aggregated_metrics.profitable_periods} / {aggregated_metrics.total_periods}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom variant="body2">
                Avg Win Rate
              </Typography>
              <Typography variant="h5">
                {(aggregated_metrics.avg_oos_win_rate * 100).toFixed(1)}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Timeline View */}
      {viewMode === 'timeline' && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Walk-Forward Timeline
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Каждый период: оптимизация на In-Sample → тест на Out-of-Sample
          </Typography>

          <Stack spacing={3} sx={{ mt: 3 }}>
            {walk_results.map((period) => (
              <Box key={period.period_num}>
                <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1 }}>
                  <Typography variant="subtitle1" fontWeight="bold">
                    Period {period.period_num}
                  </Typography>
                  <Chip
                    label={`Efficiency: ${(period.efficiency * 100).toFixed(1)}%`}
                    size="small"
                    sx={{
                      bgcolor: getEfficiencyColor(period.efficiency),
                      color: 'white',
                    }}
                  />
                  {period.efficiency >= 0.8 ? (
                    <CheckCircleIcon color="success" />
                  ) : (
                    <WarningIcon color="warning" />
                  )}
                </Stack>

                <Grid container spacing={2}>
                  {/* In-Sample */}
                  <Grid item xs={12} md={6}>
                    <Paper variant="outlined" sx={{ p: 2, bgcolor: 'action.hover' }}>
                      <Typography variant="subtitle2" color="primary" gutterBottom>
                        📊 In-Sample (Training)
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(period.in_sample_start)} - {formatDate(period.in_sample_end)}
                      </Typography>

                      <Stack spacing={0.5} sx={{ mt: 1.5 }}>
                        <Typography variant="body2">
                          <strong>Sharpe:</strong> {period.is_sharpe.toFixed(2)}
                        </Typography>
                        <Typography variant="body2">
                          <strong>Net Profit:</strong> ${period.is_net_profit.toFixed(0)}
                        </Typography>
                        <Typography variant="body2">
                          <strong>Trades:</strong> {period.is_total_trades}
                        </Typography>
                        <Divider sx={{ my: 1 }} />
                        <Typography variant="caption" color="text.secondary">
                          <strong>Best Params:</strong>
                        </Typography>
                        {Object.entries(period.best_params).map(([key, value]) => (
                          <Typography key={key} variant="caption" sx={{ ml: 1 }}>
                            {key}: {JSON.stringify(value)}
                          </Typography>
                        ))}
                      </Stack>
                    </Paper>
                  </Grid>

                  {/* Out-of-Sample */}
                  <Grid item xs={12} md={6}>
                    <Paper
                      variant="outlined"
                      sx={{
                        p: 2,
                        bgcolor: period.efficiency >= 0.8 ? 'success.50' : 'warning.50',
                        border: `2px solid ${getEfficiencyColor(period.efficiency)}`,
                      }}
                    >
                      <Typography variant="subtitle2" color="secondary" gutterBottom>
                        🎯 Out-of-Sample (Testing)
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(period.out_sample_start)} - {formatDate(period.out_sample_end)}
                      </Typography>

                      <Stack spacing={0.5} sx={{ mt: 1.5 }}>
                        <Typography variant="body2">
                          <strong>Sharpe:</strong> {period.oos_sharpe.toFixed(2)}
                        </Typography>
                        <Typography variant="body2">
                          <strong>Net Profit:</strong> ${period.oos_net_profit.toFixed(0)}
                        </Typography>
                        <Typography variant="body2">
                          <strong>Trades:</strong> {period.oos_total_trades}
                        </Typography>
                        <Typography variant="body2">
                          <strong>Max DD:</strong> {(period.oos_max_drawdown * 100).toFixed(1)}%
                        </Typography>
                        <Typography variant="body2">
                          <strong>Win Rate:</strong> {(period.oos_win_rate * 100).toFixed(1)}%
                        </Typography>
                      </Stack>
                    </Paper>
                  </Grid>
                </Grid>
              </Box>
            ))}
          </Stack>
        </Paper>
      )}

      {/* Metrics Comparison View */}
      {viewMode === 'metrics' && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Metrics Comparison (IS vs OOS)
          </Typography>

          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Period</TableCell>
                  <TableCell align="right">IS Sharpe</TableCell>
                  <TableCell align="right">OOS Sharpe</TableCell>
                  <TableCell align="right">Efficiency</TableCell>
                  <TableCell align="right">IS Profit</TableCell>
                  <TableCell align="right">OOS Profit</TableCell>
                  <TableCell align="right">OOS Win Rate</TableCell>
                  <TableCell align="right">OOS Max DD</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {walk_results.map((period) => (
                  <TableRow key={period.period_num} hover>
                    <TableCell>Period {period.period_num}</TableCell>
                    <TableCell align="right">{period.is_sharpe.toFixed(2)}</TableCell>
                    <TableCell align="right">{period.oos_sharpe.toFixed(2)}</TableCell>
                    <TableCell align="right">
                      <Chip
                        label={`${(period.efficiency * 100).toFixed(1)}%`}
                        size="small"
                        sx={{
                          bgcolor: getEfficiencyColor(period.efficiency),
                          color: 'white',
                        }}
                      />
                    </TableCell>
                    <TableCell align="right">${period.is_net_profit.toFixed(0)}</TableCell>
                    <TableCell align="right">${period.oos_net_profit.toFixed(0)}</TableCell>
                    <TableCell align="right">{(period.oos_win_rate * 100).toFixed(1)}%</TableCell>
                    <TableCell align="right">
                      {(period.oos_max_drawdown * 100).toFixed(1)}%
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Parameter Stability View */}
      {viewMode === 'stability' && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Parameter Stability Analysis
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Низкая вариация параметров = стабильность стратегии. CV &lt; 0.2 = хорошо.
          </Typography>

          <Grid container spacing={3}>
            {Object.entries(parameter_stability).map(([paramName, stats]) => (
              <Grid item xs={12} md={6} key={paramName}>
                <Card>
                  <CardContent>
                    <Typography variant="subtitle1" gutterBottom>
                      {paramName}
                    </Typography>

                    <Stack spacing={1}>
                      <Typography variant="body2">
                        <strong>Values:</strong> {stats.values.join(', ')}
                      </Typography>
                      <Typography variant="body2">
                        <strong>Std Dev:</strong> {stats.std_dev.toFixed(3)}
                      </Typography>
                      <Typography variant="body2">
                        <strong>Coefficient of Variation:</strong>{' '}
                        <Chip
                          label={stats.coefficient_of_variation.toFixed(3)}
                          size="small"
                          color={stats.coefficient_of_variation < 0.2 ? 'success' : 'warning'}
                        />
                      </Typography>
                    </Stack>

                    {stats.coefficient_of_variation < 0.2 && (
                      <Alert severity="success" sx={{ mt: 2 }}>
                        ✅ Stable parameter
                      </Alert>
                    )}
                    {stats.coefficient_of_variation >= 0.2 && (
                      <Alert severity="warning" sx={{ mt: 2 }}>
                        ⚠️ Parameter varies significantly across periods
                      </Alert>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Paper>
      )}

      {/* Interpretation Guide */}
      <Paper sx={{ mt: 3, p: 2, bgcolor: 'action.hover' }}>
        <Typography variant="subtitle2" gutterBottom>
          💡 Interpretation Guide
        </Typography>
        <Typography variant="body2" color="text.secondary">
          <strong>Efficiency (OOS/IS):</strong> 80%+ = good, 60-80% = acceptable, &lt;60% =
          overfitting risk
          <br />
          <strong>Parameter Stability:</strong> Low CV (&lt;0.2) indicates robust parameters
          <br />
          <strong>Profitable Periods:</strong> Higher ratio = more consistent strategy
        </Typography>
      </Paper>
    </Container>
  );
};

export default WalkForwardPage;
