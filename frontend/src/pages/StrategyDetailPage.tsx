import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Container, Typography, Paper, Stack, Button, TextField, MenuItem } from '@mui/material';
import { StrategiesApi, BacktestsApi } from '../services/api';
import type { Strategy } from '../types/api';
import { useNotify } from '../components/NotificationsProvider';
import { applyFieldErrors, validateIsoUtc, validateSymbol } from '../utils/forms';

const StrategyDetailPage: React.FC = () => {
  const { id } = useParams();
  const strategyId = Number(id || 0);
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const notify = useNotify();
  // quick backtest form
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState('15');
  const [startDate, setStartDate] = useState('2025-07-01T00:00:00Z');
  const [endDate, setEndDate] = useState('2025-10-22T00:00:00Z');
  const [initialCap, setInitialCap] = useState<number>(1000);
  const [queueing, setQueueing] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const errs: Record<string, string> = {};
    const symErr = validateSymbol(symbol);
    if (symErr) errs.symbol = symErr;
    if (!timeframe) errs.timeframe = 'Select timeframe';
    const sErr = validateIsoUtc(startDate);
    if (sErr) errs.startDate = sErr;
    const eErr = validateIsoUtc(endDate);
    if (eErr) errs.endDate = eErr;
    if (startDate && endDate && Date.parse(startDate) >= Date.parse(endDate))
      errs.endDate = 'End must be after Start';
    if (!initialCap || initialCap <= 0) errs.initialCap = 'Must be > 0';
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(undefined);
      try {
        const s = await StrategiesApi.get(strategyId);
        setStrategy(s);
      } catch (e: any) {
        const msg = e?.message || String(e);
        setError(msg);
        notify({ message: `Failed to load strategy: ${msg}`, severity: 'error' });
      } finally {
        setLoading(false);
      }
    })();
  }, [strategyId, notify]);

  return (
    <Container>
      <Typography variant="h4">Strategy #{strategyId}</Typography>
      {loading && <div>Loading...</div>}
      {error && <div style={{ color: 'red' }}>{error}</div>}
      {strategy && (
        <Paper sx={{ mt: 2, p: 2 }}>
          <Stack spacing={2}>
            <div>
              <Typography variant="h6">Overview</Typography>
              <div>Name: {strategy.name}</div>
              <div>Type: {strategy.strategy_type}</div>
              <div>Active: {strategy.is_active ? 'Yes' : 'No'}</div>
              {strategy.description && <div>Description: {strategy.description}</div>}
            </div>
            <div>
              <Typography variant="h6">Config</Typography>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(strategy.config, null, 2)}
              </pre>
            </div>
            <div>
              <Button href={`#/optimizations`} variant="outlined">
                Go to Optimizations
              </Button>
              <Button href={`#/`} sx={{ ml: 1 }}>
                Back to Strategies
              </Button>
            </div>
          </Stack>
        </Paper>
      )}

      {strategy && (
        <Paper sx={{ mt: 2, p: 2 }}>
          <Typography variant="h6">Run Quick Backtest</Typography>
          <Stack direction="row" spacing={2} sx={{ mt: 1, flexWrap: 'wrap' }}>
            <TextField
              label="Symbol"
              size="small"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              sx={{ width: 160 }}
              error={!!formErrors.symbol}
              helperText={formErrors.symbol}
            />
            <TextField
              label="Timeframe"
              size="small"
              select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              sx={{ width: 160 }}
              error={!!formErrors.timeframe}
              helperText={formErrors.timeframe}
            >
              {['1', '3', '5', '15', '60', '240', 'D', 'W'].map((v) => (
                <MenuItem key={v} value={v}>
                  {v}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Start (ISO UTC)"
              size="small"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              sx={{ width: 260 }}
              error={!!formErrors.startDate}
              helperText={formErrors.startDate}
            />
            <TextField
              label="End (ISO UTC)"
              size="small"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              sx={{ width: 260 }}
              error={!!formErrors.endDate}
              helperText={formErrors.endDate}
            />
            <TextField
              label="Initial Capital"
              size="small"
              type="number"
              value={initialCap}
              onChange={(e) => setInitialCap(Number(e.target.value) || 0)}
              sx={{ width: 180 }}
              error={!!formErrors.initialCap}
              helperText={formErrors.initialCap}
            />
            <Button
              variant="contained"
              disabled={queueing}
              onClick={async () => {
                try {
                  if (!validate()) return;
                  setQueueing(true);
                  const bt = await BacktestsApi.run({
                    strategy_id: strategyId,
                    symbol,
                    timeframe,
                    start_date: startDate,
                    end_date: endDate,
                    initial_capital: initialCap,
                  } as any);
                  if (bt) {
                    notify({ message: `Backtest #${(bt as any).id} created`, severity: 'success' });
                    window.location.hash = `#/backtest/${(bt as any).id}`;
                  }
                } catch (e: any) {
                  const msg = e?.friendlyMessage || e?.message || String(e);
                  applyFieldErrors(setFormErrors, e);
                  notify({ message: `Failed to start backtest: ${msg}`, severity: 'error' });
                } finally {
                  setQueueing(false);
                }
              }}
            >
              Run
            </Button>
            <Button href={`#/optimizations?strategy_id=${strategyId}`} variant="outlined">
              Open Optimizations
            </Button>
          </Stack>
        </Paper>
      )}
    </Container>
  );
};

export default StrategyDetailPage;
