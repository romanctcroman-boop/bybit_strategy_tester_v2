/**
 * Monte Carlo Tab Component (Task #11)
 *
 * Визуализация Monte Carlo симуляции для оценки робастности стратегии
 */
import React, { useState, useEffect } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Grid,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Chip,
} from '@mui/material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
  ReferenceLine,
} from 'recharts';
import CasinoIcon from '@mui/icons-material/Casino';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import WarningIcon from '@mui/icons-material/Warning';
import { useNotify } from './NotificationsProvider';

interface MonteCarloTabProps {
  backtestId: number;
}

interface MonteCarloResult {
  n_simulations: number;
  original_return: number;
  mean_return: number;
  std_return: number;
  percentile_5: number;
  percentile_25: number;
  percentile_50: number;
  percentile_75: number;
  percentile_95: number;
  prob_profit: number;
  prob_ruin: number;
  original_percentile: number;
  distribution: {
    returns: number[];
    max_drawdowns: number[];
    sharpe_ratios: number[];
  };
}

const MonteCarloTab: React.FC<MonteCarloTabProps> = ({ backtestId }) => {
  const notify = useNotify();
  const [loading, setLoading] = useState(false);
  const [mcResults, setMcResults] = useState<MonteCarloResult | null>(null);
  const [error, setError] = useState<string>('');

  // Run Monte Carlo simulation
  const handleRunMC = async (nSimulations: number = 1000) => {
    setLoading(true);
    setError('');

    try {
      // TODO: Replace with actual API call
      // const response = await BacktestsApi.runMonteCarlo(backtestId, { n_simulations: nSimulations });

      // Mock data for demonstration
      await new Promise((resolve) => setTimeout(resolve, 2000));

      const mockResults: MonteCarloResult = {
        n_simulations: nSimulations,
        original_return: 42.5,
        mean_return: 38.2,
        std_return: 15.8,
        percentile_5: 8.5,
        percentile_25: 26.3,
        percentile_50: 37.9,
        percentile_75: 49.8,
        percentile_95: 68.4,
        prob_profit: 0.87,
        prob_ruin: 0.03,
        original_percentile: 62.5,
        distribution: {
          returns: Array.from({ length: 50 }, (_, i) => {
            const x = (i - 25) * 3;
            const mean = 38.2;
            const std = 15.8;
            return Math.exp(-0.5 * Math.pow((x - mean) / std, 2)) * 100;
          }),
          max_drawdowns: Array.from({ length: 50 }, () => Math.random() * 25 + 5),
          sharpe_ratios: Array.from({ length: 50 }, () => Math.random() * 2 + 0.5),
        },
      };

      setMcResults(mockResults);
      notify({
        message: `Monte Carlo completed: ${nSimulations} simulations`,
        severity: 'success',
      });
    } catch (err: any) {
      const message = err?.message || 'Failed to run Monte Carlo simulation';
      setError(message);
      notify({ message, severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // Auto-load if results exist
  useEffect(() => {
    // Could check if MC results already exist for this backtest
    // For now, require manual trigger
  }, [backtestId]);

  // Prepare histogram data
  const histogramData = mcResults
    ? Array.from({ length: 20 }, (_, i) => {
        const binStart =
          mcResults.percentile_5 + (i * (mcResults.percentile_95 - mcResults.percentile_5)) / 20;
        const binEnd =
          mcResults.percentile_5 +
          ((i + 1) * (mcResults.percentile_95 - mcResults.percentile_5)) / 20;
        const count = mcResults.distribution.returns.filter(
          (r) => r >= binStart && r < binEnd
        ).length;
        return {
          bin: `${binStart.toFixed(1)}`,
          count,
          binCenter: (binStart + binEnd) / 2,
        };
      })
    : [];

  if (!mcResults && !loading) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Monte Carlo Simulation
          </Typography>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Оцените робастность стратегии через случайные перестановки сделок (bootstrap). Симуляция
            покажет распределение возможных результатов и риски.
          </Typography>
          <Button
            variant="contained"
            startIcon={<CasinoIcon />}
            onClick={() => handleRunMC(1000)}
            disabled={loading}
          >
            Run Monte Carlo (1000 simulations)
          </Button>
        </Alert>

        <Paper sx={{ p: 2, backgroundColor: 'action.hover' }}>
          <Typography variant="body2" color="text.secondary">
            <strong>Что покажет симуляция:</strong>
            <ul>
              <li>📊 Распределение возможных доходностей</li>
              <li>📉 Конус неопределённости (Cone of Uncertainty)</li>
              <li>🎯 Доверительные интервалы (5%, 25%, 50%, 75%, 95%)</li>
              <li>✅ Вероятность прибыли (Probability of Profit)</li>
              <li>⚠️ Вероятность разорения (Probability of Ruin)</li>
            </ul>
          </Typography>
        </Paper>
      </Box>
    );
  }

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Running {1000} simulations...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 3 }}>
        {error}
      </Alert>
    );
  }

  if (!mcResults) return null;

  // Get confidence color
  const getConfidenceColor = (percentile: number) => {
    if (percentile >= 75) return 'success';
    if (percentile >= 50) return 'warning';
    return 'error';
  };

  return (
    <Grid container spacing={3} sx={{ mt: 1, p: 2 }}>
      {/* Statistics Cards */}
      <Grid item xs={12} md={3}>
        <Card>
          <CardContent>
            <Typography color="text.secondary" gutterBottom>
              <TrendingUpIcon fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
              Mean Return
            </Typography>
            <Typography variant="h4">{mcResults.mean_return.toFixed(2)}%</Typography>
            <Typography variant="body2" color="text.secondary">
              Original: {mcResults.original_return.toFixed(2)}%
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={3}>
        <Card>
          <CardContent>
            <Typography color="text.secondary" gutterBottom>
              <ShowChartIcon fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
              Std Deviation
            </Typography>
            <Typography variant="h4">{mcResults.std_return.toFixed(2)}%</Typography>
            <Typography variant="body2" color="text.secondary">
              Volatility measure
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={3}>
        <Card
          sx={{ backgroundColor: mcResults.prob_profit >= 0.7 ? 'success.light' : 'warning.light' }}
        >
          <CardContent>
            <Typography color="text.secondary" gutterBottom>
              ✅ Probability of Profit
            </Typography>
            <Typography variant="h4">{(mcResults.prob_profit * 100).toFixed(1)}%</Typography>
            <Typography variant="body2" color="text.secondary">
              {mcResults.prob_profit >= 0.7 ? 'High confidence' : 'Moderate'}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={3}>
        <Card
          sx={{ backgroundColor: mcResults.prob_ruin <= 0.1 ? 'success.light' : 'error.light' }}
        >
          <CardContent>
            <Typography color="text.secondary" gutterBottom>
              <WarningIcon fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
              Probability of Ruin
            </Typography>
            <Typography variant="h4">{(mcResults.prob_ruin * 100).toFixed(1)}%</Typography>
            <Typography variant="body2" color="text.secondary">
              {mcResults.prob_ruin <= 0.1 ? 'Low risk' : 'High risk'}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Distribution Histogram */}
      <Grid item xs={12} md={8}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Return Distribution ({mcResults.n_simulations} simulations)
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={histogramData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="bin"
                label={{ value: 'Return (%)', position: 'insideBottom', offset: -5 }}
                tick={{ fontSize: 10 }}
                interval={2}
              />
              <YAxis label={{ value: 'Frequency', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <ReferenceLine
                x={mcResults.original_return.toFixed(1)}
                stroke="red"
                strokeDasharray="3 3"
                label={{ value: 'Original', position: 'top' }}
              />
              <ReferenceLine
                x={mcResults.mean_return.toFixed(1)}
                stroke="green"
                strokeDasharray="3 3"
                label={{ value: 'Mean', position: 'top' }}
              />
              <Bar dataKey="count" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            Red line: Original strategy | Green line: Average of simulations
          </Typography>
        </Paper>
      </Grid>

      {/* Percentiles Table */}
      <Grid item xs={12} md={4}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Percentiles
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Percentile</TableCell>
                  <TableCell align="right">Return (%)</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell>5th (Pessimistic)</TableCell>
                  <TableCell align="right">
                    <Chip
                      label={`${mcResults.percentile_5.toFixed(2)}%`}
                      size="small"
                      color="error"
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>25th</TableCell>
                  <TableCell align="right">
                    <Chip
                      label={`${mcResults.percentile_25.toFixed(2)}%`}
                      size="small"
                      color="warning"
                    />
                  </TableCell>
                </TableRow>
                <TableRow sx={{ backgroundColor: 'action.hover' }}>
                  <TableCell>
                    <strong>50th (Median)</strong>
                  </TableCell>
                  <TableCell align="right">
                    <Chip
                      label={`${mcResults.percentile_50.toFixed(2)}%`}
                      size="small"
                      color="info"
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>75th</TableCell>
                  <TableCell align="right">
                    <Chip
                      label={`${mcResults.percentile_75.toFixed(2)}%`}
                      size="small"
                      color="success"
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>95th (Optimistic)</TableCell>
                  <TableCell align="right">
                    <Chip
                      label={`${mcResults.percentile_95.toFixed(2)}%`}
                      size="small"
                      color="success"
                    />
                  </TableCell>
                </TableRow>
                <TableRow sx={{ borderTop: 2, borderColor: 'divider' }}>
                  <TableCell>
                    <strong>Original Strategy</strong>
                  </TableCell>
                  <TableCell align="right">
                    <Chip
                      label={`${mcResults.original_return.toFixed(2)}%`}
                      size="small"
                      color={getConfidenceColor(mcResults.original_percentile)}
                    />
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            Original at {mcResults.original_percentile.toFixed(1)}th percentile
          </Typography>
        </Paper>
      </Grid>

      {/* Cone of Uncertainty */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Cone of Uncertainty (Equity Growth Projection)
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart
              data={Array.from({ length: 100 }, (_, i) => ({
                period: i,
                p5: mcResults.percentile_5 * (1 + i / 100),
                p25: mcResults.percentile_25 * (1 + i / 100),
                p50: mcResults.percentile_50 * (1 + i / 100),
                p75: mcResults.percentile_75 * (1 + i / 100),
                p95: mcResults.percentile_95 * (1 + i / 100),
                original: mcResults.original_return * (1 + i / 100),
              }))}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="period"
                label={{ value: 'Time Period', position: 'insideBottom', offset: -5 }}
              />
              <YAxis
                label={{ value: 'Cumulative Return (%)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="p95"
                stroke="#82ca9d"
                strokeDasharray="5 5"
                name="95th percentile"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="p75"
                stroke="#a4de6c"
                strokeDasharray="3 3"
                name="75th percentile"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="p50"
                stroke="#8884d8"
                strokeWidth={2}
                name="Median"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="p25"
                stroke="#ffc658"
                strokeDasharray="3 3"
                name="25th percentile"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="p5"
                stroke="#ff7c7c"
                strokeDasharray="5 5"
                name="5th percentile"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="original"
                stroke="#ff0000"
                strokeWidth={2}
                name="Original"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            Shows possible equity trajectories based on Monte Carlo simulations
          </Typography>
        </Paper>
      </Grid>

      {/* Interpretation Guide */}
      <Grid item xs={12}>
        <Alert severity="info">
          <Typography variant="body2">
            <strong>Интерпретация результатов:</strong>
            <ul style={{ marginTop: 8, marginBottom: 0 }}>
              <li>
                <strong>Probability of Profit ≥ 70%:</strong> Стратегия робастна, высокая
                вероятность прибыли
              </li>
              <li>
                <strong>Probability of Ruin ≤ 10%:</strong> Низкий риск разорения, стратегия
                безопасна
              </li>
              <li>
                <strong>Original Percentile ≥ 50th:</strong> Исходная стратегия выше среднего по
                симуляциям
              </li>
              <li>
                <strong>Узкий конус (малый Std Dev):</strong> Предсказуемые результаты, низкая
                неопределённость
              </li>
            </ul>
          </Typography>
        </Alert>
      </Grid>

      {/* Re-run Button */}
      <Grid item xs={12}>
        <Box display="flex" justifyContent="center" gap={2}>
          <Button
            variant="outlined"
            startIcon={<CasinoIcon />}
            onClick={() => handleRunMC(500)}
            disabled={loading}
          >
            Re-run (500 simulations)
          </Button>
          <Button
            variant="contained"
            startIcon={<CasinoIcon />}
            onClick={() => handleRunMC(1000)}
            disabled={loading}
          >
            Re-run (1000 simulations)
          </Button>
          <Button
            variant="outlined"
            startIcon={<CasinoIcon />}
            onClick={() => handleRunMC(5000)}
            disabled={loading}
          >
            Re-run (5000 simulations)
          </Button>
        </Box>
      </Grid>
    </Grid>
  );
};

export default MonteCarloTab;
