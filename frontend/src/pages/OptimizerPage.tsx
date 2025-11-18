/**
 * OptimizerPage Component - ML-Based Parameter Optimization
 *
 * Features:
 * - Parameter Grid UI (visual parameter space)
 * - ML Engine Selector (CatBoost, XGBoost, LightGBM, Hybrid)
 * - Real-time Progress Indicator
 * - Optimization Results Visualization
 * - Best Parameters Display
 * - Integration with backend optimizer service
 */

import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  LinearProgress,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Alert,
  Slider,
} from '@mui/material';
import { PlayArrow, Stop, Settings, Assessment, TrendingUp, Speed } from '@mui/icons-material';
import axios from 'axios';
import Plot from 'react-plotly.js';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface ParameterRange {
  name: string;
  min: number;
  max: number;
  step: number;
  current: number;
}

interface OptimizationResult {
  id: string;
  parameters: Record<string, number>;
  sharpe_ratio: number;
  total_return: number;
  max_drawdown: number;
  win_rate: number;
}

interface OptimizerState {
  status: 'idle' | 'running' | 'completed' | 'error';
  progress: number;
  currentIteration: number;
  totalIterations: number;
  bestResult?: OptimizationResult;
  allResults: OptimizationResult[];
}

const OptimizerPage: React.FC = () => {
  const [strategy, setStrategy] = useState<string>('sr_mean_reversion');
  const [mlEngine, setMlEngine] = useState<string>('catboost');
  const [parameterRanges, setParameterRanges] = useState<ParameterRange[]>([
    { name: 'lookback_period', min: 10, max: 100, step: 5, current: 20 },
    { name: 'entry_threshold', min: 0.5, max: 3.0, step: 0.1, current: 1.5 },
    { name: 'stop_loss', min: 0.5, max: 5.0, step: 0.5, current: 2.0 },
    { name: 'take_profit', min: 1.0, max: 10.0, step: 0.5, current: 4.0 },
  ]);
  const [optimizerState, setOptimizerState] = useState<OptimizerState>({
    status: 'idle',
    progress: 0,
    currentIteration: 0,
    totalIterations: 0,
    allResults: [],
  });
  const [error, setError] = useState<string | null>(null);

  // Update parameter value
  const handleParameterChange = (index: number, value: number) => {
    const updated = [...parameterRanges];
    updated[index].current = value;
    setParameterRanges(updated);
  };

  // Start optimization
  const handleStartOptimization = async () => {
    setError(null);
    setOptimizerState({
      status: 'running',
      progress: 0,
      currentIteration: 0,
      totalIterations: 100,
      allResults: [],
    });

    try {
      const payload = {
        strategy_name: strategy,
        optimizer_type: mlEngine,
        parameters: parameterRanges.reduce(
          (acc, param) => {
            acc[param.name] = {
              min: param.min,
              max: param.max,
              step: param.step,
            };
            return acc;
          },
          {} as Record<string, any>
        ),
        objective: 'sharpe_ratio',
        n_iterations: 100,
      };

      const response = await axios.post(`${API_BASE_URL}/api/optimize`, payload);

      // Poll for results
      const taskId = response.data.task_id;
      const pollInterval = setInterval(async () => {
        try {
          const statusResponse = await axios.get(`${API_BASE_URL}/api/optimize/${taskId}`);
          const data = statusResponse.data;

          setOptimizerState({
            status: data.status === 'completed' ? 'completed' : 'running',
            progress: data.progress || 0,
            currentIteration: data.current_iteration || 0,
            totalIterations: data.total_iterations || 100,
            bestResult: data.best_result,
            allResults: data.all_results || [],
          });

          if (data.status === 'completed') {
            clearInterval(pollInterval);
          }
        } catch (pollError) {
          console.error('Polling error:', pollError);
          clearInterval(pollInterval);
        }
      }, 2000);
    } catch (err) {
      console.error('Optimization failed:', err);
      setError('Optimization failed. Using mock data for development.');

      // Mock optimization results
      const mockResults: OptimizationResult[] = Array.from({ length: 50 }, (_, i) => ({
        id: `result-${i}`,
        parameters: {
          lookback_period: 10 + Math.random() * 90,
          entry_threshold: 0.5 + Math.random() * 2.5,
          stop_loss: 0.5 + Math.random() * 4.5,
          take_profit: 1.0 + Math.random() * 9.0,
        },
        sharpe_ratio: 0.5 + Math.random() * 2.5,
        total_return: 5 + Math.random() * 45,
        max_drawdown: -(5 + Math.random() * 15),
        win_rate: 40 + Math.random() * 40,
      }));

      mockResults.sort((a, b) => b.sharpe_ratio - a.sharpe_ratio);

      setOptimizerState({
        status: 'completed',
        progress: 100,
        currentIteration: 50,
        totalIterations: 50,
        bestResult: mockResults[0],
        allResults: mockResults,
      });
    }
  };

  // Stop optimization
  const handleStopOptimization = () => {
    setOptimizerState((prev) => ({
      ...prev,
      status: 'idle',
    }));
  };

  // Prepare scatter plot data
  const getScatterPlotData = (): any[] => {
    if (optimizerState.allResults.length === 0) return [];

    return [
      {
        x: optimizerState.allResults.map((r) => r.total_return),
        y: optimizerState.allResults.map((r) => r.sharpe_ratio),
        mode: 'markers',
        type: 'scatter',
        marker: {
          size: 8,
          color: optimizerState.allResults.map((r) => r.max_drawdown),
          colorscale: 'Viridis',
          showscale: true,
          colorbar: {
            title: { text: 'Max DD (%)' },
          },
        },
        text: optimizerState.allResults.map(
          (r) => `Return: ${r.total_return.toFixed(2)}%<br>Sharpe: ${r.sharpe_ratio.toFixed(2)}`
        ),
        hovertemplate: '%{text}<extra></extra>',
      },
    ];
  };

  return (
    <Box sx={{ p: 3, backgroundColor: '#f5f5f5', minHeight: '100vh' }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom sx={{ fontWeight: 600 }}>
          ⚙️ ML-Based Optimizer
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Optimize strategy parameters using advanced ML algorithms
        </Typography>
      </Box>

      {error && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Configuration Panel */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                <Settings sx={{ mr: 1 }} />
                Configuration
              </Typography>

              {/* Strategy Selection */}
              <FormControl fullWidth sx={{ mt: 2 }}>
                <InputLabel>Strategy</InputLabel>
                <Select
                  value={strategy}
                  label="Strategy"
                  onChange={(e) => setStrategy(e.target.value)}
                  disabled={optimizerState.status === 'running'}
                >
                  <MenuItem value="sr_mean_reversion">SR Mean Reversion</MenuItem>
                  <MenuItem value="bb_mean_reversion">Bollinger Bands</MenuItem>
                  <MenuItem value="ema_crossover">EMA Crossover</MenuItem>
                  <MenuItem value="sr_rsi_enhanced">SR + RSI Enhanced</MenuItem>
                </Select>
              </FormControl>

              {/* ML Engine Selection */}
              <FormControl fullWidth sx={{ mt: 2 }}>
                <InputLabel>ML Engine</InputLabel>
                <Select
                  value={mlEngine}
                  label="ML Engine"
                  onChange={(e) => setMlEngine(e.target.value)}
                  disabled={optimizerState.status === 'running'}
                >
                  <MenuItem value="catboost">
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <TrendingUp sx={{ mr: 1, fontSize: 18 }} />
                      CatBoost (Temporal)
                    </Box>
                  </MenuItem>
                  <MenuItem value="xgboost">
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Assessment sx={{ mr: 1, fontSize: 18 }} />
                      XGBoost (Grid)
                    </Box>
                  </MenuItem>
                  <MenuItem value="lightgbm">
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Speed sx={{ mr: 1, fontSize: 18 }} />
                      LightGBM (Fast)
                    </Box>
                  </MenuItem>
                  <MenuItem value="hybrid">Hybrid (Best)</MenuItem>
                </Select>
              </FormControl>

              {/* Parameter Ranges */}
              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Parameter Ranges
                </Typography>
                {parameterRanges.map((param, index) => (
                  <Box key={param.name} sx={{ mt: 2 }}>
                    <Typography variant="caption" gutterBottom>
                      {param.name}: {param.current.toFixed(2)}
                    </Typography>
                    <Slider
                      value={param.current}
                      min={param.min}
                      max={param.max}
                      step={param.step}
                      onChange={(_, value) => handleParameterChange(index, value as number)}
                      disabled={optimizerState.status === 'running'}
                      valueLabelDisplay="auto"
                    />
                  </Box>
                ))}
              </Box>

              {/* Action Buttons */}
              <Box sx={{ mt: 3, display: 'flex', gap: 1 }}>
                {optimizerState.status !== 'running' ? (
                  <Button
                    fullWidth
                    variant="contained"
                    startIcon={<PlayArrow />}
                    onClick={handleStartOptimization}
                  >
                    Start Optimization
                  </Button>
                ) : (
                  <Button
                    fullWidth
                    variant="outlined"
                    color="error"
                    startIcon={<Stop />}
                    onClick={handleStopOptimization}
                  >
                    Stop
                  </Button>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Results Panel */}
        <Grid item xs={12} md={8}>
          {/* Progress */}
          {optimizerState.status === 'running' && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Optimization in Progress...
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={optimizerState.progress}
                  sx={{ height: 10, borderRadius: 5 }}
                />
                <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
                  Iteration {optimizerState.currentIteration} / {optimizerState.totalIterations}
                </Typography>
              </CardContent>
            </Card>
          )}

          {/* Best Result */}
          {optimizerState.bestResult && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  🏆 Best Result
                </Typography>
                <Grid container spacing={2} sx={{ mt: 1 }}>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="caption" color="text.secondary">
                      Sharpe Ratio
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {optimizerState.bestResult.sharpe_ratio.toFixed(2)}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="caption" color="text.secondary">
                      Total Return
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 600, color: '#4caf50' }}>
                      {optimizerState.bestResult.total_return.toFixed(2)}%
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="caption" color="text.secondary">
                      Max Drawdown
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 600, color: '#f44336' }}>
                      {optimizerState.bestResult.max_drawdown.toFixed(2)}%
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="caption" color="text.secondary">
                      Win Rate
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {optimizerState.bestResult.win_rate.toFixed(2)}%
                    </Typography>
                  </Grid>
                </Grid>

                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Best Parameters:
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {Object.entries(optimizerState.bestResult.parameters).map(([key, value]) => (
                      <Chip
                        key={key}
                        label={`${key}: ${typeof value === 'number' ? value.toFixed(2) : value}`}
                        color="primary"
                        variant="outlined"
                      />
                    ))}
                  </Box>
                </Box>
              </CardContent>
            </Card>
          )}

          {/* Scatter Plot */}
          {optimizerState.allResults.length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  📊 Optimization Results
                </Typography>
                <Plot
                  data={getScatterPlotData() as any}
                  layout={
                    {
                      title: { text: 'Return vs Sharpe Ratio (colored by Max Drawdown)' },
                      xaxis: { title: { text: 'Total Return (%)' } },
                      yaxis: { title: { text: 'Sharpe Ratio' } },
                      hovermode: 'closest',
                      width: undefined,
                      height: 400,
                      autosize: true,
                    } as any
                  }
                  config={{ responsive: true }}
                  style={{ width: '100%' }}
                />
              </CardContent>
            </Card>
          )}

          {/* Results Table */}
          {optimizerState.allResults.length > 0 && (
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  All Results (Top 10)
                </Typography>
                <TableContainer component={Paper}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Rank</TableCell>
                        <TableCell align="right">Sharpe</TableCell>
                        <TableCell align="right">Return (%)</TableCell>
                        <TableCell align="right">Max DD (%)</TableCell>
                        <TableCell align="right">Win Rate (%)</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {optimizerState.allResults.slice(0, 10).map((result, index) => (
                        <TableRow key={result.id}>
                          <TableCell>{index + 1}</TableCell>
                          <TableCell align="right">{result.sharpe_ratio.toFixed(2)}</TableCell>
                          <TableCell align="right">{result.total_return.toFixed(2)}</TableCell>
                          <TableCell align="right">{result.max_drawdown.toFixed(2)}</TableCell>
                          <TableCell align="right">{result.win_rate.toFixed(2)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default OptimizerPage;
