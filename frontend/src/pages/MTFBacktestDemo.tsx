/**
 * MTF Backtest Demo Page
 * 
 * Demonstrates Multi-Timeframe backtest functionality (ТЗ 3.4.2)
 */
import React, { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Container,
  Divider,
  Grid,
  Paper,
  Stack,
  TextField,
  Typography,
  Alert,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import MTFSelector from '../components/MTFSelector';
import { useNotify } from '../components/NotificationsProvider';

interface MTFBacktestConfig {
  symbol: string;
  centralTimeframe: string;
  additionalTimeframes: string[];
  htfFilters: any[];
  initialCapital: number;
  strategyType: string;
  fastEma: number;
  slowEma: number;
}

const MTFBacktestDemo: React.FC = () => {
  const notify = useNotify();
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  
  const [config, setConfig] = useState<MTFBacktestConfig>({
    symbol: 'BTCUSDT',
    centralTimeframe: '15',
    additionalTimeframes: ['60', 'D'],
    htfFilters: [
      {
        id: '1',
        timeframe: '60',
        type: 'trend_ma',
        params: { period: 200, condition: 'price_above' },
      },
    ],
    initialCapital: 10000,
    strategyType: 'ema_crossover',
    fastEma: 50,
    slowEma: 200,
  });

  const handleRunMTFBacktest = async () => {
    setLoading(true);
    setResults(null);

    try {
      const payload = {
        strategy_id: 1, // Mock strategy ID
        symbol: config.symbol,
        timeframe: config.centralTimeframe,
        start_date: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(), // 90 days ago
        end_date: new Date().toISOString(),
        initial_capital: config.initialCapital,
        leverage: 1,
        commission: 0.0006,
        config: {
          type: config.strategyType,
          fast_ema: config.fastEma,
          slow_ema: config.slowEma,
        },
        additional_timeframes: config.additionalTimeframes,
        htf_filters: config.htfFilters,
      };

      const response = await fetch('http://localhost:8000/api/backtests/mtf', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'MTF Backtest failed');
      }

      const data = await response.json();
      setResults(data);
      
      notify({
        message: `MTF Backtest completed: ${data.results?.total_trades || 0} trades`,
        severity: 'success',
      });
    } catch (error: any) {
      console.error('MTF Backtest error:', error);
      notify({
        message: error.message || 'MTF Backtest failed',
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        Multi-Timeframe Backtest Demo
      </Typography>
      
      <Typography variant="body2" color="text.secondary" paragraph>
        Test strategies with higher timeframe filters for better trend alignment (ТЗ 3.4.2)
      </Typography>

      <Divider sx={{ mb: 3 }} />

      <Grid container spacing={3}>
        {/* Configuration Panel */}
        <Grid item xs={12} md={6}>
          <Stack spacing={3}>
            {/* Basic Config */}
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Basic Configuration
                </Typography>
                
                <Stack spacing={2}>
                  <TextField
                    label="Symbol"
                    value={config.symbol}
                    onChange={(e) => setConfig({ ...config, symbol: e.target.value })}
                    fullWidth
                    size="small"
                  />
                  
                  <TextField
                    label="Central Timeframe"
                    value={config.centralTimeframe}
                    onChange={(e) => setConfig({ ...config, centralTimeframe: e.target.value })}
                    fullWidth
                    size="small"
                    helperText="Main trading timeframe"
                  />
                  
                  <TextField
                    label="Initial Capital (USDT)"
                    type="number"
                    value={config.initialCapital}
                    onChange={(e) =>
                      setConfig({ ...config, initialCapital: parseFloat(e.target.value) })
                    }
                    fullWidth
                    size="small"
                  />
                  
                  <Divider />
                  
                  <Typography variant="subtitle2">Strategy Parameters</Typography>
                  
                  <TextField
                    label="Fast EMA Period"
                    type="number"
                    value={config.fastEma}
                    onChange={(e) =>
                      setConfig({ ...config, fastEma: parseInt(e.target.value) })
                    }
                    fullWidth
                    size="small"
                  />
                  
                  <TextField
                    label="Slow EMA Period"
                    type="number"
                    value={config.slowEma}
                    onChange={(e) =>
                      setConfig({ ...config, slowEma: parseInt(e.target.value) })
                    }
                    fullWidth
                    size="small"
                  />
                </Stack>
              </CardContent>
            </Card>

            {/* MTF Selector */}
            <MTFSelector
              centralTimeframe={config.centralTimeframe}
              additionalTimeframes={config.additionalTimeframes}
              htfFilters={config.htfFilters}
              onAdditionalTimeframesChange={(tfs) =>
                setConfig({ ...config, additionalTimeframes: tfs })
              }
              onHTFFiltersChange={(filters) =>
                setConfig({ ...config, htfFilters: filters })
              }
              disabled={loading}
            />

            {/* Run Button */}
            <Button
              variant="contained"
              color="primary"
              size="large"
              startIcon={loading ? <CircularProgress size={20} /> : <PlayArrowIcon />}
              onClick={handleRunMTFBacktest}
              disabled={loading}
              fullWidth
            >
              {loading ? 'Running MTF Backtest...' : 'Run MTF Backtest'}
            </Button>
          </Stack>
        </Grid>

        {/* Results Panel */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Results
              </Typography>

              {!results && !loading && (
                <Alert severity="info">
                  Configure MTF parameters and click "Run MTF Backtest" to see results
                </Alert>
              )}

              {loading && (
                <Box display="flex" justifyContent="center" p={4}>
                  <CircularProgress />
                </Box>
              )}

              {results && (
                <Stack spacing={2}>
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Performance
                    </Typography>
                    <Typography variant="h5">
                      {results.results?.metrics?.net_profit?.toFixed(2) || 'N/A'} USDT
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      ({results.results?.metrics?.net_profit_pct?.toFixed(2) || 'N/A'}%)
                    </Typography>
                  </Paper>

                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                          Total Trades
                        </Typography>
                        <Typography variant="h6">
                          {results.results?.total_trades || 0}
                        </Typography>
                      </Paper>
                    </Grid>
                    
                    <Grid item xs={6}>
                      <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                          Win Rate
                        </Typography>
                        <Typography variant="h6">
                          {((results.results?.win_rate || 0) * 100).toFixed(1)}%
                        </Typography>
                      </Paper>
                    </Grid>
                    
                    <Grid item xs={6}>
                      <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                          Sharpe Ratio
                        </Typography>
                        <Typography variant="h6">
                          {results.results?.sharpe_ratio?.toFixed(2) || 'N/A'}
                        </Typography>
                      </Paper>
                    </Grid>
                    
                    <Grid item xs={6}>
                      <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                          Max Drawdown
                        </Typography>
                        <Typography variant="h6" color="error">
                          {(results.results?.metrics?.max_drawdown_pct?.toFixed(2) || 'N/A')}%
                        </Typography>
                      </Paper>
                    </Grid>
                    
                    <Grid item xs={6}>
                      <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                          Profit Factor
                        </Typography>
                        <Typography variant="h6">
                          {results.results?.profit_factor?.toFixed(2) || 'N/A'}
                        </Typography>
                      </Paper>
                    </Grid>
                    
                    <Grid item xs={6}>
                      <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                          Sortino Ratio
                        </Typography>
                        <Typography variant="h6">
                          {results.results?.sortino_ratio?.toFixed(2) || 'N/A'}
                        </Typography>
                      </Paper>
                    </Grid>
                  </Grid>

                  {/* MTF Config Info */}
                  <Divider />
                  
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      MTF Configuration
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Central: {results.central_timeframe}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Additional: {results.additional_timeframes?.join(', ') || 'None'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      HTF Filters: {results.mtf_config?.htf_filters?.length || 0}
                    </Typography>
                  </Box>

                  {/* HTF Indicators Preview */}
                  {results.htf_indicators && Object.keys(results.htf_indicators).length > 0 && (
                    <Box>
                      <Typography variant="subtitle2" gutterBottom>
                        HTF Indicators Available
                      </Typography>
                      {Object.entries(results.htf_indicators).map(([tf, data]: [string, any]) => (
                        <Typography key={tf} variant="body2" color="text.secondary">
                          {tf}: {Object.keys(data).filter((k) => k !== 'timestamps').join(', ')}
                        </Typography>
                      ))}
                    </Box>
                  )}
                </Stack>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Container>
  );
};

export default MTFBacktestDemo;
