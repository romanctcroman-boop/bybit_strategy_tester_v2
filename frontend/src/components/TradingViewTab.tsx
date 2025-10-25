/**
 * TradingViewTab Component (ТЗ 9.2 Step 4)
 *
 * Interactive TradingView Lightweight Charts for backtest analysis
 * with TP/SL price lines and enhanced trade markers
 */
import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  ButtonGroup,
  Card,
  CardContent,
  Checkbox,
  CircularProgress,
  FormControlLabel,
  Grid,
  Paper,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import CandlestickChartIcon from '@mui/icons-material/CandlestickChart';
import TimelineIcon from '@mui/icons-material/Timeline';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import FitScreenIcon from '@mui/icons-material/FitScreen';
import TradingViewChart from './TradingViewChart';
import { BacktestsApi } from '../services/api';
import { useNotify } from './NotificationsProvider';

interface TradingViewTabProps {
  backtestId: number;
}

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface Trade {
  id: number;
  entry_time: number;
  entry_price: number;
  exit_time?: number;
  exit_price?: number;
  side: 'buy' | 'sell';
  tp_price?: number;
  sl_price?: number;
  pnl?: number;
  pnl_percent?: number;
  size?: number;
}

const TradingViewTab: React.FC<TradingViewTabProps> = ({ backtestId }) => {
  const notify = useNotify();

  // Data states
  const [candles, setCandles] = useState<Candle[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

  // Chart controls
  const [chartType, setChartType] = useState<'candlestick' | 'line' | 'area' | 'baseline'>(
    'candlestick'
  );
  const [scaleMode, setScaleMode] = useState<'normal' | 'log' | 'percent' | 'index100'>('normal');

  // Display options
  const [showSMA20, setShowSMA20] = useState(true);
  const [showSMA50, setShowSMA50] = useState(false);
  const [showVolume, setShowVolume] = useState(true);
  const [showTPSL, setShowTPSL] = useState(true);
  const [showMarkerTooltips, setShowMarkerTooltips] = useState(true);
  const [scaleMarkersBySize, setScaleMarkersBySize] = useState(false);
  const [showExitMarkers, setShowExitMarkers] = useState(true);

  // Chart API ref
  const [chartApi, setChartApi] = useState<any>(null);

  // Fetch candles and trades
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError('');

      try {
        // Fetch backtest details to get candles
        const backtest = await BacktestsApi.get(backtestId);

        // TODO: API should return candles, for now use mock data
        // In production, add endpoint: GET /api/backtests/{id}/candles
        if ((backtest as any).candles && Array.isArray((backtest as any).candles)) {
          setCandles((backtest as any).candles);
        } else {
          setCandles([]);
          notify({
            message: 'Candles data not available for this backtest',
            severity: 'warning',
          });
        }

        // Fetch trades
        const tradesResponse = await BacktestsApi.trades(backtestId, {
          limit: 1000, // Get all trades for chart
          offset: 0,
        });

        // Convert trades to internal format (timestamps to unix)
        const convertedTrades: Trade[] = (tradesResponse.items || []).map((t) => ({
          id: t.id,
          entry_time:
            typeof t.entry_time === 'number'
              ? t.entry_time
              : new Date(t.entry_time).getTime() / 1000,
          entry_price: t.entry_price,
          exit_time: t.exit_time
            ? typeof t.exit_time === 'number'
              ? t.exit_time
              : new Date(t.exit_time).getTime() / 1000
            : undefined,
          exit_price: t.exit_price,
          side: t.side,
          tp_price: undefined, // Not available in API
          sl_price: undefined, // Not available in API
          pnl: t.pnl,
          pnl_percent: t.pnl_pct, // Use pnl_pct from API
          size: t.quantity, // Use quantity from API
        }));

        setTrades(convertedTrades);
      } catch (err: any) {
        const message = err?.friendlyMessage || 'Failed to load chart data';
        setError(message);
        notify({ message, severity: 'error' });
      } finally {
        setLoading(false);
      }
    };

    if (backtestId) {
      fetchData();
    }
  }, [backtestId, notify]);

  // Convert trades to markers
  const markers = trades.flatMap((trade) => {
    const markersList: any[] = [];

    // Entry marker
    markersList.push({
      time: trade.entry_time,
      side: trade.side,
      price: trade.entry_price,
      tp_price: trade.tp_price,
      sl_price: trade.sl_price,
      exit_price: trade.exit_price,
      exit_time: trade.exit_time,
      is_entry: true,
      pnl: trade.pnl,
      pnl_percent: trade.pnl_percent,
      size: trade.size || 1.0,
    });

    // Exit marker (if trade is closed)
    if (trade.exit_time && trade.exit_price) {
      markersList.push({
        time: trade.exit_time,
        side: trade.side === 'buy' ? ('sell' as const) : ('buy' as const),
        price: trade.exit_price,
        is_entry: false,
        pnl: trade.pnl,
        pnl_percent: trade.pnl_percent,
        size: trade.size || 1.0,
      });
    }

    return markersList;
  });

  // Chart controls
  const handleFitContent = () => {
    if (chartApi?.fitContent) {
      chartApi.fitContent();
    }
  };

  const handleZoomToTrade = (tradeId: number) => {
    const trade = trades.find((t) => t.id === tradeId);
    if (!trade || !chartApi?.setVisibleRange) return;

    const startTime = trade.entry_time;
    const endTime = trade.exit_time || trade.entry_time + 3600 * 24; // +24h if still open

    chartApi.setVisibleRange(startTime - 3600, endTime + 3600); // Add 1h padding
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  if (candles.length === 0) {
    return (
      <Alert severity="info" sx={{ mt: 2 }}>
        No candle data available for this backtest. TradingView chart requires OHLCV data.
      </Alert>
    );
  }

  return (
    <Grid container spacing={3} sx={{ mt: 1 }}>
      {/* Left Controls Panel */}
      <Grid item xs={12} md={3}>
        <Stack spacing={2}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Chart Type
              </Typography>

              <ToggleButtonGroup
                value={chartType}
                exclusive
                onChange={(_, value) => value && setChartType(value)}
                orientation="vertical"
                fullWidth
                size="small"
              >
                <ToggleButton value="candlestick">
                  <CandlestickChartIcon sx={{ mr: 1 }} />
                  Candlestick
                </ToggleButton>
                <ToggleButton value="line">
                  <ShowChartIcon sx={{ mr: 1 }} />
                  Line
                </ToggleButton>
                <ToggleButton value="area">
                  <TimelineIcon sx={{ mr: 1 }} />
                  Area
                </ToggleButton>
                <ToggleButton value="baseline">Baseline</ToggleButton>
              </ToggleButtonGroup>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Scale Mode
              </Typography>

              <ButtonGroup orientation="vertical" fullWidth size="small">
                <Button
                  variant={scaleMode === 'normal' ? 'contained' : 'outlined'}
                  onClick={() => setScaleMode('normal')}
                >
                  Normal
                </Button>
                <Button
                  variant={scaleMode === 'log' ? 'contained' : 'outlined'}
                  onClick={() => setScaleMode('log')}
                >
                  Logarithmic
                </Button>
                <Button
                  variant={scaleMode === 'percent' ? 'contained' : 'outlined'}
                  onClick={() => setScaleMode('percent')}
                >
                  Percentage
                </Button>
                <Button
                  variant={scaleMode === 'index100' ? 'contained' : 'outlined'}
                  onClick={() => setScaleMode('index100')}
                >
                  Indexed to 100
                </Button>
              </ButtonGroup>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Indicators
              </Typography>

              <Stack spacing={1}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={showSMA20}
                      onChange={(e) => setShowSMA20(e.target.checked)}
                    />
                  }
                  label="SMA 20"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={showSMA50}
                      onChange={(e) => setShowSMA50(e.target.checked)}
                    />
                  }
                  label="SMA 50"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={showVolume}
                      onChange={(e) => setShowVolume(e.target.checked)}
                    />
                  }
                  label="Volume"
                />
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Trade Markers
              </Typography>

              <Stack spacing={1}>
                <FormControlLabel
                  control={
                    <Checkbox checked={showTPSL} onChange={(e) => setShowTPSL(e.target.checked)} />
                  }
                  label="TP/SL Lines"
                  sx={{ fontWeight: 'bold', color: 'primary.main' }}
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={showMarkerTooltips}
                      onChange={(e) => setShowMarkerTooltips(e.target.checked)}
                    />
                  }
                  label="P&L Tooltips"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={scaleMarkersBySize}
                      onChange={(e) => setScaleMarkersBySize(e.target.checked)}
                    />
                  }
                  label="Scale by Size"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={showExitMarkers}
                      onChange={(e) => setShowExitMarkers(e.target.checked)}
                    />
                  }
                  label="Exit Circles"
                />
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Chart Controls
              </Typography>

              <Stack spacing={1}>
                <Button
                  startIcon={<FitScreenIcon />}
                  onClick={handleFitContent}
                  fullWidth
                  size="small"
                >
                  Fit Content
                </Button>
                <Button
                  startIcon={<ZoomInIcon />}
                  onClick={() => trades.length > 0 && handleZoomToTrade(trades[0].id)}
                  fullWidth
                  size="small"
                  disabled={trades.length === 0}
                >
                  Zoom to First Trade
                </Button>
              </Stack>
            </CardContent>
          </Card>

          <Paper sx={{ p: 2, backgroundColor: 'action.hover' }}>
            <Typography variant="caption" color="text.secondary">
              <strong>Stats:</strong>
              <br />
              Candles: {candles.length}
              <br />
              Trades: {trades.length}
              <br />
              Markers: {markers.length}
            </Typography>
          </Paper>
        </Stack>
      </Grid>

      {/* Right Chart Panel */}
      <Grid item xs={12} md={9}>
        <Paper elevation={3} sx={{ p: 2, height: 700 }}>
          <Box height="100%">
            <TradingViewChart
              candles={candles}
              markers={markers}
              chartType={chartType}
              scaleMode={scaleMode}
              showSMA20={showSMA20}
              showSMA50={showSMA50}
              showVolume={showVolume}
              showTPSL={showTPSL}
              showMarkerTooltips={showMarkerTooltips}
              scaleMarkersBySize={scaleMarkersBySize}
              showExitMarkers={showExitMarkers}
              onApi={setChartApi}
            />
          </Box>
        </Paper>

        {/* TP/SL Legend */}
        {showTPSL && (
          <Paper elevation={1} sx={{ mt: 2, p: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              TP/SL Price Lines Legend
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={4}>
                <Box display="flex" alignItems="center" gap={1}>
                  <Box
                    sx={{
                      width: 40,
                      height: 3,
                      bgcolor: '#4caf50',
                      borderStyle: 'dashed',
                      borderWidth: 2,
                      borderColor: '#4caf50',
                    }}
                  />
                  <Typography variant="body2">Take Profit (TP)</Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box display="flex" alignItems="center" gap={1}>
                  <Box
                    sx={{
                      width: 40,
                      height: 3,
                      bgcolor: '#f44336',
                      borderStyle: 'dashed',
                      borderWidth: 2,
                      borderColor: '#f44336',
                    }}
                  />
                  <Typography variant="body2">Stop Loss (SL)</Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box display="flex" alignItems="center" gap={1}>
                  <Box
                    sx={{
                      width: 40,
                      height: 3,
                      bgcolor: '#2196f3',
                      borderStyle: 'dotted',
                      borderWidth: 2,
                      borderColor: '#2196f3',
                    }}
                  />
                  <Typography variant="body2">Actual Exit</Typography>
                </Box>
              </Grid>
            </Grid>
          </Paper>
        )}

        {/* Marker Legend */}
        <Paper elevation={1} sx={{ mt: 2, p: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Trade Markers Legend
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            Entry markers: <strong>Arrows</strong> (Green ▲ = Long, Red ▼ = Short)
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            Exit markers: {showExitMarkers ? <strong>Circles</strong> : <strong>Arrows</strong>}{' '}
            (Blue = Profit, Red = Loss)
          </Typography>
          {showMarkerTooltips && (
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
              Hover over markers to see P&L information
            </Typography>
          )}
        </Paper>

        {/* Help */}
        <Paper elevation={1} sx={{ mt: 2, p: 2, backgroundColor: 'action.hover' }}>
          <Typography variant="body2" color="text.secondary">
            💡 <strong>Tip:</strong> Use mouse wheel to zoom, drag to pan. Click &quot;Fit
            Content&quot; to see all data. Toggle TP/SL lines to see target levels for each trade.
          </Typography>
        </Paper>
      </Grid>
    </Grid>
  );
};

export default TradingViewTab;
