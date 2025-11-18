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
  Divider,
} from '@mui/material';
import { OptimizationsApi } from '../services/api';
import type { Optimization, OptimizationResult } from '../types/api';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ScatterChart,
  Scatter,
  ZAxis,
} from 'recharts';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useNotify } from '../components/NotificationsProvider';
import WFORunButton from '../components/WFORunButton';

const OptimizationDetailPage: React.FC = () => {
  const { id } = useParams();
  const optimizationId = Number(id || 0);
  const [opt, setOpt] = useState<Optimization | null>(null);
  const [best, setBest] = useState<OptimizationResult | null>(null);
  const [results, setResults] = useState<OptimizationResult[]>([]);
  const [topN, setTopN] = useState<number>(20);
  const [sortBy, setSortBy] = useState<'score' | 'sharpe_ratio' | 'max_drawdown' | 'total_trades'>(
    'score'
  );
  const notify = useNotify();

  useEffect(() => {
    (async () => {
      try {
        const [o, b, r] = await Promise.all([
          OptimizationsApi.get(optimizationId),
          OptimizationsApi.best(optimizationId).catch(() => null),
          OptimizationsApi.results(optimizationId),
        ]);
        setOpt(o);
        if (b) setBest(b as any);
        setResults(r);
      } catch (e: any) {
        notify({ message: `Failed to load optimization: ${e?.message || e}`, severity: 'error' });
      }
    })();
  }, [optimizationId, notify]);

  const topResults = useMemo(() => {
    const sorted = [...results].sort((a, b) => {
      const av = (a as any)[sortBy] ?? -Infinity;
      const bv = (b as any)[sortBy] ?? -Infinity;
      return (typeof bv === 'number' ? bv : -Infinity) - (typeof av === 'number' ? av : -Infinity);
    });
    return sorted.slice(0, Math.max(1, Math.min(200, topN)));
  }, [results, sortBy, topN]);

  const exportCsv = () => {
    const headers = [
      'id',
      'optimization_id',
      'score',
      'total_return',
      'sharpe_ratio',
      'max_drawdown',
      'win_rate',
      'total_trades',
      'params',
    ];
    const lines = [headers.join(',')].concat(
      results.map((r) =>
        [
          r.id,
          r.optimization_id,
          r.score,
          r.total_return ?? '',
          r.sharpe_ratio ?? '',
          r.max_drawdown ?? '',
          r.win_rate ?? '',
          r.total_trades ?? '',
          JSON.stringify(r.params),
        ].join(',')
      )
    );
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `optimization_${optimizationId}_results.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const scoreHistogram = useMemo(() => {
    if (!results.length) return [] as Array<{ bin: string; count: number }>;
    const vals = results
      .map((r) => r.score)
      .filter((v) => typeof v === 'number' && isFinite(v)) as number[];
    if (!vals.length) return [];
    const min = Math.min(...vals),
      max = Math.max(...vals);
    const bins = 20;
    const step = (max - min) / bins || 1;
    const counts = new Array(bins).fill(0);
    vals.forEach((v) => {
      const idx = Math.min(bins - 1, Math.max(0, Math.floor((v - min) / step)));
      counts[idx]++;
    });
    return counts.map((c, i) => ({ bin: (min + i * step).toFixed(2), count: c }));
  }, [results]);

  const sharpeHistogram = useMemo(() => {
    const vals = results
      .map((r) => r.sharpe_ratio)
      .filter((v) => typeof v === 'number' && isFinite(v as number)) as number[];
    if (!vals.length) return [] as Array<{ bin: string; count: number }>;
    const min = Math.min(...vals),
      max = Math.max(...vals);
    const bins = 20;
    const step = (max - min) / bins || 1;
    const counts = new Array(bins).fill(0);
    vals.forEach((v) => {
      const idx = Math.min(bins - 1, Math.max(0, Math.floor((v - min) / step)));
      counts[idx]++;
    });
    return counts.map((c, i) => ({ bin: (min + i * step).toFixed(2), count: c }));
  }, [results]);

  const cols: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 80 },
    { field: 'score', headerName: 'Score', width: 120, type: 'number' },
    { field: 'sharpe_ratio', headerName: 'Sharpe', width: 120, type: 'number' },
    { field: 'max_drawdown', headerName: 'Max DD', width: 120, type: 'number' },
    { field: 'total_trades', headerName: 'Trades', width: 120, type: 'number' },
  ];

  return (
    <Container>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h4">Optimization #{optimizationId}</Typography>
        {opt && opt.status === 'completed' && <WFORunButton optimizationId={optimizationId} />}
      </Stack>
      {opt && (
        <Paper sx={{ mt: 2, p: 2 }}>
          <Stack direction="row" spacing={4}>
            <div>
              <Typography variant="h6">Overview</Typography>
              <div>Type: {opt.optimization_type}</div>
              <div>Symbol: {opt.symbol}</div>
              <div>Timeframe: {opt.timeframe}</div>
              <div>Status: {opt.status}</div>
              <div>Metric: {opt.metric}</div>
              {opt.best_score != null && <div>Best Score: {opt.best_score}</div>}
            </div>
            <div style={{ flex: 1 }}>
              <Typography variant="h6">Best Params</Typography>
              {best ? (
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(best, null, 2)}
                </pre>
              ) : (
                <em>No best result yet.</em>
              )}
            </div>
          </Stack>
        </Paper>
      )}

      <Paper sx={{ mt: 2, p: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
          <Typography variant="h6">Top Results</Typography>
          <Stack direction="row" spacing={2}>
            <TextField
              label="Top N"
              size="small"
              type="number"
              value={topN}
              onChange={(e) => setTopN(Math.max(5, Math.min(200, Number(e.target.value) || 20)))}
              sx={{ width: 120 }}
            />
            <TextField
              label="Sort by"
              size="small"
              select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              sx={{ width: 180 }}
            >
              {['score', 'sharpe_ratio', 'max_drawdown', 'total_trades'].map((v) => (
                <MenuItem key={v} value={v}>
                  {v}
                </MenuItem>
              ))}
            </TextField>
            <Button variant="outlined" onClick={exportCsv}>
              Export CSV
            </Button>
          </Stack>
        </Stack>
        <Divider sx={{ my: 2 }} />
        <div style={{ width: '100%', height: 260 }}>
          <ResponsiveContainer>
            <BarChart data={topResults.map((r, i) => ({ i, score: r.score }))}>
              <CartesianGrid stroke="#ccc" />
              <XAxis dataKey="i" tick={false} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="score" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Paper>

      <Paper sx={{ mt: 2, p: 2 }}>
        <Typography variant="h6">Score vs Total Trades</Typography>
        <div style={{ width: '100%', height: 260 }}>
          <ResponsiveContainer>
            <ScatterChart>
              <CartesianGrid stroke="#ccc" />
              <XAxis dataKey="x" name="Trades" />
              <YAxis dataKey="y" name="Score" />
              <ZAxis range={[60]} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} />
              <Scatter
                data={results.map((r) => ({ x: r.total_trades ?? 0, y: r.score }))}
                fill="#82ca9d"
              />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </Paper>

      <Paper sx={{ mt: 2, p: 2 }}>
        <Typography variant="h6">Distributions</Typography>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
          <div style={{ flex: 1, height: 220 }}>
            <ResponsiveContainer>
              <BarChart data={scoreHistogram}>
                <CartesianGrid stroke="#ccc" />
                <XAxis dataKey="bin" tick={{ fontSize: 10 }} interval={3} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#8884d8" />
              </BarChart>
            </ResponsiveContainer>
            <div style={{ textAlign: 'center', marginTop: 4 }}>Score histogram</div>
          </div>
          <div style={{ flex: 1, height: 220 }}>
            <ResponsiveContainer>
              <BarChart data={sharpeHistogram}>
                <CartesianGrid stroke="#ccc" />
                <XAxis dataKey="bin" tick={{ fontSize: 10 }} interval={3} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#82ca9d" />
              </BarChart>
            </ResponsiveContainer>
            <div style={{ textAlign: 'center', marginTop: 4 }}>Sharpe histogram</div>
          </div>
        </Stack>
      </Paper>

      <Paper sx={{ mt: 2, p: 2 }}>
        <Typography variant="h6">Results Table</Typography>
        <div style={{ width: '100%', height: 420 }}>
          <DataGrid rows={results} columns={cols} getRowId={(r: any) => r.id} />
        </div>
      </Paper>
    </Container>
  );
};

export default OptimizationDetailPage;
