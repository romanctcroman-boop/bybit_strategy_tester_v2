import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Container,
  Typography,
  Paper,
  Stack,
  TextField,
  MenuItem,
  Button,
  ButtonGroup,
} from '@mui/material';
import { Tabs, Tab, Grid, Chip } from '@mui/material';
import TradingViewWidget from '../components/TradingViewWidget';
import { FormControlLabel, Checkbox } from '@mui/material';
import { useBacktestsStore } from '../store/backtests';
import { Backtest, Trade } from '../types/api';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import {
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts';
import { DataApi, BacktestsApi } from '../services/api';
import { useNotify } from '../components/NotificationsProvider';

// Lazy load TradingViewChart outside of component to avoid re-initialization on every render
const TradingViewChart = React.lazy(() => import('../components/TradingViewChart'));

const TradesTable: React.FC<{ trades: Trade[] }> = ({ trades }) => {
  const cols: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 80 },
    {
      field: 'entry_time',
      headerName: 'Entry',
      width: 170,
      valueGetter: (p: any) => new Date(p.row.entry_time).toLocaleString(),
    },
    {
      field: 'exit_time',
      headerName: 'Exit',
      width: 180,
      valueGetter: (p: any) => (p.row.exit_time ? new Date(p.row.exit_time).toLocaleString() : ''),
    },
    { field: 'side', headerName: 'Side', width: 100 },
    { field: 'price', headerName: 'Price', width: 120 },
    { field: 'qty', headerName: 'Qty', width: 100 },
    { field: 'pnl', headerName: 'PnL', width: 120 },
    // Optional analytics columns if present in the data
    { field: 'mfe', headerName: 'MFE', width: 100, valueGetter: (p: any) => p.row.mfe ?? '' },
    { field: 'mae', headerName: 'MAE', width: 100, valueGetter: (p: any) => p.row.mae ?? '' },
    { field: 'peak', headerName: 'Peak', width: 100, valueGetter: (p: any) => p.row.peak ?? '' },
    {
      field: 'drawdown',
      headerName: 'DD',
      width: 100,
      valueGetter: (p: any) => p.row.drawdown ?? '',
    },
    {
      field: 'bars_held',
      headerName: 'Bars',
      width: 90,
      valueGetter: (p: any) => p.row.bars_held ?? '',
    },
  ];

  return (
    <div style={{ height: 420, width: '100%' }}>
      <DataGrid rows={trades} columns={cols} getRowId={(r: any) => r.id} />
    </div>
  );
};

const BacktestDetailPage: React.FC = () => {
  const { id } = useParams();
  const backtestId = Number(id || 0);
  const {
    fetchTrades,
    setTradesPage,
    setTradeFilters,
    trades,
    tradesLimit,
    tradesOffset,
    tradesTotal,
    tradeSide,
  } = useBacktestsStore();
  const [pageSize, setPageSize] = useState<number>(tradesLimit);
  const page = useMemo(() => Math.floor(tradesOffset / pageSize) + 1, [tradesOffset, pageSize]);
  const [series, setSeries] = useState<any[]>([]); // equity series
  const [ddSeries, setDdSeries] = useState<any[]>([]); // drawdown series
  const [rollWinSeries, setRollWinSeries] = useState<any[]>([]); // rolling win rate
  const [candles, setCandles] = useState<any[]>([]);
  const [useTradingView, setUseTradingView] = useState(false);
  const [tvSymbol, setTvSymbol] = useState('BTCUSDT');
  const [tvTheme, setTvTheme] = useState<'light' | 'dark'>('light');
  const [tvInterval, setTvInterval] = useState('60');
  const [useMACD, setUseMACD] = useState(true);
  const [useRSI, setUseRSI] = useState(false);
  const [showSMA20, setShowSMA20] = useState(true);
  const [showSMA50, setShowSMA50] = useState(false);
  const notify = useNotify();
  const [backtest, setBacktest] = useState<Backtest | null>(null);
  const [tab, setTab] = useState<number>(0);

  useEffect(() => {
    (async () => {
      try {
        const bt = await BacktestsApi.get(backtestId);
        setBacktest(bt);
        const t = await fetchTrades(backtestId, { limit: pageSize, offset: 0 });
        if (t) {
          // compute equity and drawdown series from trades slice
          const sorted = [...t].sort(
            (a, b) => new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime()
          );
          let cum = bt?.initial_capital ?? 0;
          let peak = cum;
          const eq: any[] = [];
          const dd: any[] = [];
          let wins: number[] = []; // 1 for win, 0 for loss
          const roll: any[] = [];
          for (const tr of sorted) {
            const pnl = tr.pnl ?? 0;
            cum += pnl;
            peak = Math.max(peak, cum);
            const ts = new Date(tr.entry_time).toISOString();
            eq.push({ time: ts, equity: cum });
            const drawdown = peak > 0 ? (cum - peak) / peak : 0;
            dd.push({ time: ts, drawdown });
            wins.push((pnl ?? 0) > 0 ? 1 : 0);
            if (wins.length > 20) wins = wins.slice(wins.length - 20);
            const winRate = wins.reduce((a, b) => a + b, 0) / wins.length;
            roll.push({ time: ts, win: Math.round(winRate * 100) });
          }
          setSeries(eq);
          setDdSeries(dd);
          setRollWinSeries(roll);
        }
      } catch (e: any) {
        notify({ message: `Failed to load trades: ${e?.message || e}`, severity: 'error' });
      }
    })();
  }, [backtestId, pageSize, fetchTrades, notify]);

  const applyTradeFilter = async (side: 'buy' | 'sell' | '') => {
    setTradeFilters({ side: side || undefined });
    const t = await fetchTrades(backtestId, {
      side: side || undefined,
      limit: pageSize,
      offset: 0,
    });
    if (t) {
      const sorted = [...t].sort(
        (a, b) => new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime()
      );
      let cum = backtest?.initial_capital ?? 0;
      let peak = cum;
      const eq: any[] = [];
      const dd: any[] = [];
      let wins: number[] = [];
      const roll: any[] = [];
      for (const tr of sorted) {
        const pnl = tr.pnl ?? 0;
        cum += pnl;
        peak = Math.max(peak, cum);
        const ts = new Date(tr.entry_time).toISOString();
        eq.push({ time: ts, equity: cum });
        const drawdown = peak > 0 ? (cum - peak) / peak : 0;
        dd.push({ time: ts, drawdown });
        wins.push((pnl ?? 0) > 0 ? 1 : 0);
        if (wins.length > 20) wins = wins.slice(wins.length - 20);
        const winRate = wins.reduce((a, b) => a + b, 0) / wins.length;
        roll.push({ time: ts, win: Math.round(winRate * 100) });
      }
      setSeries(eq);
      setDdSeries(dd);
      setRollWinSeries(roll);
    }
  };

  const changePage = async (nextPage: number) => {
    await setTradesPage(backtestId, nextPage, pageSize);
    const t = await fetchTrades(backtestId, { limit: pageSize, offset: (nextPage - 1) * pageSize });
    if (t) {
      const sorted = [...t].sort(
        (a, b) => new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime()
      );
      let cum = backtest?.initial_capital ?? 0;
      let peak = cum;
      const eq: any[] = [];
      const dd: any[] = [];
      let wins: number[] = [];
      const roll: any[] = [];
      for (const tr of sorted) {
        const pnl = tr.pnl ?? 0;
        cum += pnl;
        peak = Math.max(peak, cum);
        const ts = new Date(tr.entry_time).toISOString();
        eq.push({ time: ts, equity: cum });
        const drawdown = peak > 0 ? (cum - peak) / peak : 0;
        dd.push({ time: ts, drawdown });
        wins.push((pnl ?? 0) > 0 ? 1 : 0);
        if (wins.length > 20) wins = wins.slice(wins.length - 20);
        const winRate = wins.reduce((a, b) => a + b, 0) / wins.length;
        roll.push({ time: ts, win: Math.round(winRate * 100) });
      }
      setSeries(eq);
      setDdSeries(dd);
      setRollWinSeries(roll);
    }
  };

  const exportCsv = () => {
    const rows = trades;
    const headers = ['id', 'backtest_id', 'entry_time', 'exit_time', 'side', 'price', 'qty', 'pnl'];
    const lines = [headers.join(',')].concat(
      rows.map((r) =>
        [
          r.id,
          r.backtest_id,
          new Date(r.entry_time).toISOString(),
          r.exit_time ? new Date(r.exit_time).toISOString() : '',
          r.side,
          r.price,
          r.qty,
          r.pnl ?? '',
        ].join(',')
      )
    );
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backtest_${backtestId}_trades.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Load real candles from backend for selected symbol/interval when lightweight chart is active
  useEffect(() => {
    if (useTradingView) return; // TradingView widget fetches its own data
    (async () => {
      try {
        // Map TradingView-like intervals to Bybit adapter's expected strings
        const interval = tvInterval; // BybitAdapter accepts '1','3','60','D','W'
        const data = await DataApi.bybitKlines(tvSymbol, interval, 500, 0);
        setCandles(data);
      } catch (e: any) {
        notify({ message: `Failed to load candles: ${e?.message || e}`, severity: 'error' });
      }
    })();
  }, [tvSymbol, tvInterval, useTradingView, notify]);

  return (
    <Container>
      <Typography variant="h4">Backtest #{id}</Typography>

      {/* Tabs Navigation */}
      <Paper sx={{ mt: 2 }}>
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          variant="scrollable"
          scrollButtons
          allowScrollButtonsMobile
        >
          <Tab label="Overview" />
          <Tab label="Dynamics" />
          <Tab label="Trade Analysis" />
          <Tab label="Risk & Efficiency" />
          <Tab label="Trades" />
        </Tabs>
      </Paper>

      {/* Overview Tab */}
      {tab === 0 && backtest && (
        <Paper sx={{ mt: 2, p: 2 }}>
          <Typography variant="h6">Overview</Typography>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} md={6} lg={4}>
              <Chip label={`Strategy: ${backtest.strategy_id}`} />
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
              <Chip label={`Symbol: ${backtest.symbol}`} />
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
              <Chip label={`Timeframe: ${backtest.timeframe}`} />
            </Grid>
            <Grid item xs={12} md={6} lg={6}>
              <Chip label={`Period: ${backtest.start_date} → ${backtest.end_date}`} />
            </Grid>
            <Grid item xs={12} md={6} lg={3}>
              <Chip label={`Status: ${backtest.status}`} />
            </Grid>
            {backtest.final_capital != null && (
              <Grid item xs={12} md={6} lg={3}>
                <Chip color="primary" label={`Final Capital: ${backtest.final_capital}`} />
              </Grid>
            )}
          </Grid>
          {backtest.metrics && (
            <div style={{ marginTop: 12 }}>
              <Typography variant="subtitle1">Metrics (raw)</Typography>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(backtest.metrics, null, 2)}
              </pre>
            </div>
          )}
        </Paper>
      )}

      {/* Dynamics Tab */}
      {tab === 1 && (
        <>
          <Paper sx={{ mt: 2, p: 2 }}>
            <Typography variant="h6">Equity curve</Typography>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={series}>
                <CartesianGrid stroke="#333" />
                <XAxis
                  dataKey="time"
                  tickFormatter={(v: any) => new Date(v).toLocaleDateString()}
                />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="equity" stroke="#4fc3f7" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Paper>

          <Paper sx={{ mt: 2, p: 2 }}>
            <Typography variant="h6">Drawdown (%)</Typography>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={ddSeries}>
                <CartesianGrid stroke="#333" />
                <XAxis
                  dataKey="time"
                  tickFormatter={(v: any) => new Date(v).toLocaleDateString()}
                />
                <YAxis tickFormatter={(v: any) => (v * 100).toFixed(0) + '%'} />
                <Tooltip formatter={(v: any) => [(v * 100).toFixed(2) + '%', 'DD']} />
                <Area
                  type="monotone"
                  dataKey="drawdown"
                  stroke="#ef5350"
                  fill="#ef5350"
                  fillOpacity={0.3}
                />
              </AreaChart>
            </ResponsiveContainer>
          </Paper>

          <Paper sx={{ mt: 2, p: 2 }}>
            <Typography variant="h6">Rolling Win Rate (last 20 trades)</Typography>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={rollWinSeries}>
                <CartesianGrid stroke="#333" />
                <XAxis
                  dataKey="time"
                  tickFormatter={(v: any) => new Date(v).toLocaleDateString()}
                />
                <YAxis domain={[0, 100]} tickFormatter={(v: any) => v + '%'} />
                <Tooltip formatter={(v: any) => [v + '%', 'Win %']} />
                <Line type="monotone" dataKey="win" stroke="#66bb6a" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Paper>

          <Paper sx={{ mt: 2, p: 2 }}>
            <Typography variant="h6">Price Chart</Typography>
            <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
              <ButtonGroup variant="outlined">
                <Button onClick={() => setUseTradingView(false)} disabled={!useTradingView}>
                  Lightweight
                </Button>
                <Button onClick={() => setUseTradingView(true)} disabled={useTradingView}>
                  TradingView
                </Button>
              </ButtonGroup>
              {!useTradingView && (
                <>
                  <FormControlLabel
                    control={<Checkbox checked={showSMA20} onChange={(_, v) => setShowSMA20(v)} />}
                    label="SMA 20"
                  />
                  <FormControlLabel
                    control={<Checkbox checked={showSMA50} onChange={(_, v) => setShowSMA50(v)} />}
                    label="SMA 50"
                  />
                </>
              )}
            </Stack>
            {useTradingView ? (
              <>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
                  <TextField
                    label="Symbol"
                    size="small"
                    value={tvSymbol}
                    onChange={(e) => setTvSymbol(e.target.value)}
                  />
                  <TextField
                    label="Interval"
                    size="small"
                    select
                    value={tvInterval}
                    onChange={(e) => setTvInterval(e.target.value)}
                  >
                    {['1', '5', '15', '60', '240', 'D', 'W'].map((v) => (
                      <MenuItem key={v} value={v}>
                        {v}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    label="Theme"
                    size="small"
                    select
                    value={tvTheme}
                    onChange={(e) => setTvTheme(e.target.value as any)}
                  >
                    {['light', 'dark'].map((v) => (
                      <MenuItem key={v} value={v}>
                        {v}
                      </MenuItem>
                    ))}
                  </TextField>
                  <FormControlLabel
                    control={<Checkbox checked={useMACD} onChange={(_, v) => setUseMACD(v)} />}
                    label="MACD"
                  />
                  <FormControlLabel
                    control={<Checkbox checked={useRSI} onChange={(_, v) => setUseRSI(v)} />}
                    label="RSI"
                  />
                </div>
                <TradingViewWidget
                  symbol={`BYBIT:${tvSymbol}`}
                  interval={tvInterval}
                  theme={tvTheme}
                  studies={[
                    ...(useMACD ? ['MACD@tv-basicstudies'] : []),
                    ...(useRSI ? ['RSI@tv-basicstudies'] : []),
                  ]}
                />
              </>
            ) : (
              <React.Suspense
                fallback={
                  <div
                    style={{
                      height: 480,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    Loading chart...
                  </div>
                }
              >
                <TradingViewChart
                  candles={candles}
                  markers={trades.map((t) => ({
                    time: Math.floor(new Date(t.entry_time).getTime() / 1000),
                    side: t.side as any,
                    price: t.price,
                  }))}
                  showSMA20={showSMA20}
                  showSMA50={showSMA50}
                />
              </React.Suspense>
            )}
          </Paper>
        </>
      )}

      {/* Trade Analysis Tab - placeholder */}
      {tab === 2 && (
        <Paper sx={{ mt: 2, p: 2 }}>
          <Typography variant="h6">Trade Analysis</Typography>
          <Typography variant="body2" color="text.secondary">
            More analytics coming soon.
          </Typography>
        </Paper>
      )}

      {/* Risk & Efficiency Tab */}
      {tab === 3 && backtest?.metrics && (
        <Paper sx={{ mt: 2, p: 2 }}>
          <Typography variant="h6">Risk & Efficiency</Typography>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(backtest.metrics, null, 2)}
          </pre>
        </Paper>
      )}

      {/* Trades Tab */}
      {tab === 4 && (
        <Paper sx={{ mt: 2, p: 2 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Trades</Typography>
            <Stack direction="row" spacing={2} alignItems="center">
              <TextField
                label="Side"
                size="small"
                select
                value={tradeSide || ''}
                onChange={(e) => applyTradeFilter((e.target.value as any) || '')}
                sx={{ width: 140 }}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="buy">Buy</MenuItem>
                <MenuItem value="sell">Sell</MenuItem>
              </TextField>
              <TextField
                label="Page size"
                size="small"
                type="number"
                value={pageSize}
                onChange={(e) =>
                  setPageSize(Math.max(10, Math.min(1000, Number(e.target.value) || 50)))
                }
                sx={{ width: 120 }}
              />
              <Button variant="outlined" onClick={() => changePage(1)}>
                Apply
              </Button>
              <Button variant="outlined" onClick={exportCsv}>
                Export CSV
              </Button>
            </Stack>
          </Stack>
          <div style={{ marginTop: 12 }}>
            <TradesTable trades={trades} />
          </div>
          <Stack
            direction="row"
            spacing={2}
            alignItems="center"
            justifyContent="flex-end"
            sx={{ mt: 2 }}
          >
            <Button disabled={page <= 1} onClick={() => changePage(page - 1)}>
              Prev
            </Button>
            <div>
              Page {page} / {Math.max(1, Math.ceil((tradesTotal || 0) / pageSize))}
            </div>
            <Button
              disabled={page >= Math.ceil((tradesTotal || 0) / pageSize)}
              onClick={() => changePage(page + 1)}
            >
              Next
            </Button>
          </Stack>
        </Paper>
      )}
    </Container>
  );
};

export default BacktestDetailPage;
