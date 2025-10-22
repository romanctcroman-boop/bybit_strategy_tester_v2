import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Box, CircularProgress, Container, FormControl, InputLabel, MenuItem, Paper, Select, Typography } from '@mui/material';
import SimpleChart from '../components/SimpleChart';
import { useMarketDataStore } from '../store/marketData';

const TestChartPage: React.FC = () => {
  const [updateTime, setUpdateTime] = useState<string>('');
  const { currentInterval, loading, error, initialize, switchInterval, mergedCandles } = useMarketDataStore((s) => ({
    currentInterval: s.currentInterval,
    loading: s.loading,
    error: s.error,
    initialize: s.initialize,
    switchInterval: s.switchInterval,
    mergedCandles: s.getMergedCandles(),
  }));
  const candles = mergedCandles;

  const INTERVALS = useMemo(() => ['1','5','15','30','60','240','D','W'], []);

  // Initial load: 249-250 closed 1-minute candles from Bybit
  useEffect(() => {
    (async () => {
      await initialize('BTCUSDT', '15'); // default 15m, 500 bars loaded inside store
      setUpdateTime(new Date().toLocaleTimeString());
    })();
  }, []);

  // WS-driven; no polling effect needed now

  return (
    <Container maxWidth="lg">
      <Typography variant="h4" sx={{ mt: 3, mb: 2 }}>
        📊 Live BTCUSDT Chart
      </Typography>
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
        <FormControl size="small">
          <InputLabel id="tf-label">Таймфрейм</InputLabel>
          <Select
            labelId="tf-label"
            value={currentInterval}
            label="Таймфрейм"
            onChange={async (e) => {
              const itv = String(e.target.value);
              await switchInterval(itv, 500);
              setUpdateTime(new Date().toLocaleTimeString());
            }}
            sx={{ minWidth: 140 }}
          >
            {INTERVALS.map((itv: string) => (
              <MenuItem key={itv} value={itv}>{itv === 'D' ? '1D' : itv === 'W' ? '1W' : `${itv}m`}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <Typography variant="body2" color="textSecondary">Свечей: <strong>{candles.length}</strong></Typography>
        <Typography variant="body2" color="textSecondary">Последнее обновление: {updateTime}</Typography>
      </Box>
      
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 600 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Paper sx={{ mt: 2, p: 3 }}>
          
          {candles.length > 0 ? (
            <Box sx={{ 
              width: '100%', 
              height: 800,  // Увеличил высоту
              display: 'block',
              overflow: 'visible',
            }}>
              <SimpleChart candles={candles} datasetKey={`BTCUSDT:${currentInterval}`} interval={currentInterval} />
            </Box>
          ) : (
            <Alert severity="info">No candles available</Alert>
          )}
        </Paper>
      )}
    </Container>
  );
};

export default TestChartPage;
