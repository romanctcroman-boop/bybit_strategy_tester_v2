/**
 * TradingView Chart Demo - TP/SL Price Lines (ТЗ 9.2)
 *
 * Демонстрация возможностей TradingView Lightweight Charts:
 * - Candlestick/Line/Area графики
 * - Trade markers (Entry/Exit)
 * - TP/SL price lines
 * - Volume histogram
 * - SMA overlays
 * - Chart controls (zoom, scale mode)
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  ButtonGroup,
  Card,
  CardContent,
  Checkbox,
  Container,
  Divider,
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
import TradingViewChart from '../components/TradingViewChart';

// Generate sample candle data
const generateSampleCandles = (count: number = 100) => {
  const now = Math.floor(Date.now() / 1000);
  const candles = [];
  let price = 50000;

  for (let i = 0; i < count; i++) {
    const change = (Math.random() - 0.5) * 200;
    price = price + change;

    const open = price;
    const close = price + (Math.random() - 0.5) * 100;
    const high = Math.max(open, close) + Math.random() * 50;
    const low = Math.min(open, close) - Math.random() * 50;
    const volume = Math.random() * 1000;

    candles.push({
      time: now - (count - i) * 900, // 15 min intervals
      open,
      high,
      low,
      close,
      volume,
    });
  }

  return candles;
};

// Generate sample trade markers with TP/SL and enhanced fields
const generateSampleTrades = (candles: any[]) => {
  if (candles.length < 20) return [];

  const markers = [];

  // Long trade 1 - Hits TP (Profit)
  const entry1 = candles[20];
  const exit1 = candles[35];
  const pnl1 = exit1.close - entry1.close;
  const pnl1_pct = ((exit1.close - entry1.close) / entry1.close) * 100;

  markers.push({
    time: entry1.time,
    side: 'buy' as const,
    price: entry1.close,
    tp_price: entry1.close * 1.03, // TP at +3%
    sl_price: entry1.close * 0.98, // SL at -2%
    exit_price: exit1.close,
    exit_time: exit1.time,
    is_entry: true,
    size: 1.5, // Larger trade
    pnl: pnl1,
    pnl_percent: pnl1_pct,
  });

  markers.push({
    time: exit1.time,
    side: 'sell' as const,
    price: exit1.close,
    is_entry: false,
    pnl: pnl1,
    pnl_percent: pnl1_pct,
    size: 1.5,
  });

  // Long trade 2 - Manual exit (Profit)
  const entry2 = candles[50];
  const exit2 = candles[70];
  const pnl2 = exit2.close - entry2.close;
  const pnl2_pct = ((exit2.close - entry2.close) / entry2.close) * 100;

  markers.push({
    time: entry2.time,
    side: 'buy' as const,
    price: entry2.close,
    tp_price: entry2.close * 1.05, // TP at +5%
    sl_price: entry2.close * 0.97, // SL at -3%
    exit_price: exit2.close,
    exit_time: exit2.time,
    is_entry: true,
    size: 1.0, // Normal trade
    pnl: pnl2,
    pnl_percent: pnl2_pct,
  });

  markers.push({
    time: exit2.time,
    side: 'sell' as const,
    price: exit2.close,
    is_entry: false,
    pnl: pnl2,
    pnl_percent: pnl2_pct,
    size: 1.0,
  });

  // Short trade - Hits SL (Loss)
  const entry3 = candles[80];
  const exit3 = candles[90];
  const pnl3 = entry3.close - exit3.close; // Short P&L inverted
  const pnl3_pct = ((entry3.close - exit3.close) / entry3.close) * 100;

  markers.push({
    time: entry3.time,
    side: 'sell' as const,
    price: entry3.close,
    tp_price: entry3.close * 0.97, // TP at -3% (short)
    sl_price: entry3.close * 1.02, // SL at +2% (short)
    exit_price: exit3.close,
    exit_time: exit3.time,
    is_entry: true,
    size: 0.8, // Smaller trade
    pnl: pnl3,
    pnl_percent: pnl3_pct,
  });

  markers.push({
    time: exit3.time,
    side: 'buy' as const,
    price: exit3.close,
    is_entry: false,
    pnl: pnl3,
    pnl_percent: pnl3_pct,
    size: 0.8,
  });

  return markers;
};

const TradingViewDemo: React.FC = () => {
  const [candles, setCandles] = useState<any[]>([]);
  const [markers, setMarkers] = useState<any[]>([]);

  const [chartType, setChartType] = useState<'candlestick' | 'line' | 'area' | 'baseline'>(
    'candlestick'
  );
  const [scaleMode, setScaleMode] = useState<'normal' | 'log' | 'percent' | 'index100'>('normal');

  const [showSMA20, setShowSMA20] = useState(true);
  const [showSMA50, setShowSMA50] = useState(false);
  const [showVolume, setShowVolume] = useState(true);
  const [showLegend, setShowLegend] = useState(true);
  const [showTPSL, setShowTPSL] = useState(true);
  const [wheelZoom, setWheelZoom] = useState(true);
  const [dragScroll, setDragScroll] = useState(true);

  // Enhanced markers controls (ТЗ 9.2 Step 3)
  const [showMarkerTooltips, setShowMarkerTooltips] = useState(true);
  const [scaleMarkersBySize, setScaleMarkersBySize] = useState(false);
  const [showExitMarkers, setShowExitMarkers] = useState(true);

  useEffect(() => {
    const sampleCandles = generateSampleCandles(100);
    setCandles(sampleCandles);
    setMarkers(generateSampleTrades(sampleCandles));
  }, []);

  const handleRegenerateData = () => {
    const sampleCandles = generateSampleCandles(100);
    setCandles(sampleCandles);
    setMarkers(generateSampleTrades(sampleCandles));
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        TradingView Chart Demo (ТЗ 9.2)
      </Typography>

      <Typography variant="body2" color="text.secondary" paragraph>
        Interactive demonstration of TradingView Lightweight Charts with TP/SL price lines
      </Typography>

      <Divider sx={{ mb: 3 }} />

      <Grid container spacing={3}>
        {/* Chart Controls */}
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
                  Overlays & Indicators
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
                    label="Volume Histogram"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={showLegend}
                        onChange={(e) => setShowLegend(e.target.checked)}
                      />
                    }
                    label="Crosshair Legend"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={showTPSL}
                        onChange={(e) => setShowTPSL(e.target.checked)}
                      />
                    }
                    label="TP/SL Lines"
                    sx={{ fontWeight: 'bold', color: 'primary.main' }}
                  />
                </Stack>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Enhanced Markers
                </Typography>

                <Stack spacing={1}>
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
                    label="Scale by Trade Size"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={showExitMarkers}
                        onChange={(e) => setShowExitMarkers(e.target.checked)}
                      />
                    }
                    label="Exit Markers (Circles)"
                  />
                </Stack>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Interactivity
                </Typography>

                <Stack spacing={1}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={wheelZoom}
                        onChange={(e) => setWheelZoom(e.target.checked)}
                      />
                    }
                    label="Mouse Wheel Zoom"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={dragScroll}
                        onChange={(e) => setDragScroll(e.target.checked)}
                      />
                    }
                    label="Drag to Scroll"
                  />
                </Stack>
              </CardContent>
            </Card>

            <Button variant="outlined" onClick={handleRegenerateData} fullWidth>
              Regenerate Data
            </Button>
          </Stack>
        </Grid>

        {/* Chart Display */}
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
                showLegend={showLegend}
                showTPSL={showTPSL}
                wheelZoom={wheelZoom}
                dragScroll={dragScroll}
                showMarkerTooltips={showMarkerTooltips}
                scaleMarkersBySize={scaleMarkersBySize}
                showExitMarkers={showExitMarkers}
              />
            </Box>
          </Paper>

          {/* Legend for TP/SL lines */}
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

          {/* Trade Info */}
          <Paper elevation={1} sx={{ mt: 2, p: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Sample Trades & Enhanced Markers
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {markers.filter((m) => m.is_entry).length} Entry markers,{' '}
              {markers.filter((m) => !m.is_entry).length} Exit markers
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {markers.filter((m) => m.tp_price).length} trades with TP/SL levels
            </Typography>
            <Typography variant="body2" color="text.secondary">
              P&L Tooltips: {showMarkerTooltips ? 'Enabled' : 'Disabled'} | Size Scaling:{' '}
              {scaleMarkersBySize ? 'Enabled' : 'Disabled'} | Exit Circles:{' '}
              {showExitMarkers ? 'Yes' : 'No'}
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
              Entry markers: Arrows (Green=Long, Red=Short) | Exit markers:{' '}
              {showExitMarkers ? 'Circles' : 'Arrows'} (Blue=Profit, Red=Loss)
            </Typography>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
};

export default TradingViewDemo;
