import React, { useEffect, useState, useMemo } from 'react';
import {
  Container,
  Typography,
  Button,
  ListItemText,
  Stack,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  Divider,
  TextField,
  MenuItem,
  Paper,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
  FormControl,
  InputLabel,
  Select,
  Alert,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AddIcon from '@mui/icons-material/Add';
import TuneIcon from '@mui/icons-material/Tune';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import PaginatedList from '../components/PaginatedList';
import PlotlyChart from '../components/PlotlyChart';
import { useOptimizationsStore } from '../store/optimizations';
import { useNotify } from '../components/NotificationsProvider';
import type { Optimization, OptimizationResult } from '../types/api';
import { useLocation } from 'react-router-dom';

type SortOrder = 'asc' | 'desc';
type SortKey = 'score' | 'sharpe_ratio' | 'max_drawdown' | 'total_trades' | 'win_rate';

interface ParameterRangeInput {
  start: number;
  stop: number;
  step: number;
}

interface NewOptimizationForm {
  strategy_id: string;
  tp_range: ParameterRangeInput;
  sl_range: ParameterRangeInput;
  trailing_activation_range: ParameterRangeInput;
  trailing_distance_range: ParameterRangeInput;
  score_function: 'sharpe' | 'profit_factor' | 'custom';
  min_trades: number;
  max_drawdown: number;
  n_processes: number;
}

export default function OptimizationsPage() {
  const {
    items,
    total,
    limit,
    offset,
    fetchAll,
    setPage,
    loading,
    error,
    runGrid,
    runWalkForward,
    runBayesian,
    results,
    best,
    status,
    strategyId,
    setFilters,
    select,
  } = useOptimizationsStore();
  const notify = useNotify();
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [resultsMap, setResultsMap] = useState<Record<number, OptimizationResult[]>>({});
  const [bestMap, setBestMap] = useState<Record<number, OptimizationResult | undefined>>({});
  const [localStatus, setLocalStatus] = useState<string>(status || '');
  const [localStrategyId, setLocalStrategyId] = useState<string>(
    strategyId ? String(strategyId) : ''
  );
  const location = useLocation();
  
  // New state for sorting and dialog
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [openNewDialog, setOpenNewDialog] = useState(false);
  const [selectedOptId, setSelectedOptId] = useState<string | null>(null);
  
  const [newOptForm, setNewOptForm] = useState<NewOptimizationForm>({
    strategy_id: '',
    tp_range: { start: 1.0, stop: 5.0, step: 0.5 },
    sl_range: { start: 0.5, stop: 3.0, step: 0.5 },
    trailing_activation_range: { start: 0.0, stop: 2.0, step: 0.5 },
    trailing_distance_range: { start: 0.3, stop: 1.5, step: 0.3 },
    score_function: 'sharpe',
    min_trades: 30,
    max_drawdown: 0.20,
    n_processes: 4,
  });

  useEffect(() => {
    // parse query for strategy_id/status to prefill filters
    const params = new URLSearchParams(location.search);
    const sid = params.get('strategy_id');
    const st = params.get('status');
    if (sid || st || items.length === 0) {
      const sidNum = sid ? Number(sid) : undefined;
      setLocalStrategyId(sid || '');
      if (st) setLocalStatus(st);
      setFilters({ strategyId: sidNum, status: st || undefined });
      fetchAll({ limit, offset, strategy_id: sidNum, status: st || undefined }).catch(() =>
        notify({ message: 'Failed to load optimizations', severity: 'error' })
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  // Calculate total combinations for preview
  const calculateTotalCombinations = (form: NewOptimizationForm): number => {
    const tpCount = Math.floor((form.tp_range.stop - form.tp_range.start) / form.tp_range.step) + 1;
    const slCount = Math.floor((form.sl_range.stop - form.sl_range.start) / form.sl_range.step) + 1;
    const trailActCount = Math.floor((form.trailing_activation_range.stop - form.trailing_activation_range.start) / form.trailing_activation_range.step) + 1;
    const trailDistCount = Math.floor((form.trailing_distance_range.stop - form.trailing_distance_range.start) / form.trailing_distance_range.step) + 1;
    return tpCount * slCount * trailActCount * trailDistCount;
  };

  // Handle new optimization submission
  const handleCreateOptimization = async () => {
    try {
      const totalCombos = calculateTotalCombinations(newOptForm);
      if (totalCombos > 10000) {
        notify({ message: `Warning: ${totalCombos} combinations may take a long time!`, severity: 'warning' });
      }
      
      await runGrid({
        strategy_id: parseInt(newOptForm.strategy_id),
        parameter_ranges: {
          tp_pct: [newOptForm.tp_range.start, newOptForm.tp_range.stop, newOptForm.tp_range.step],
          sl_pct: [newOptForm.sl_range.start, newOptForm.sl_range.stop, newOptForm.sl_range.step],
          trailing_activation_pct: [newOptForm.trailing_activation_range.start, newOptForm.trailing_activation_range.stop, newOptForm.trailing_activation_range.step],
          trailing_distance_pct: [newOptForm.trailing_distance_range.start, newOptForm.trailing_distance_range.stop, newOptForm.trailing_distance_range.step],
        },
        score_function: newOptForm.score_function,
        validation_rules: {
          min_trades: newOptForm.min_trades,
          max_drawdown: newOptForm.max_drawdown,
        },
        n_processes: newOptForm.n_processes,
      });
      
      setOpenNewDialog(false);
      notify({ message: 'Grid optimization started!', severity: 'success' });
      fetchAll();
    } catch (err) {
      notify({ message: `Failed to start optimization: ${err}`, severity: 'error' });
    }
  };

  // Sort results
  const sortResults = (results: OptimizationResult[]): OptimizationResult[] => {
    if (!results || results.length === 0) return [];
    
    return [...results].sort((a, b) => {
      let aVal: number, bVal: number;
      
      switch (sortKey) {
        case 'score':
          aVal = a.score ?? -Infinity;
          bVal = b.score ?? -Infinity;
          break;
        case 'sharpe_ratio':
          aVal = a.metrics?.sharpe_ratio ?? -Infinity;
          bVal = b.metrics?.sharpe_ratio ?? -Infinity;
          break;
        case 'max_drawdown':
          aVal = a.metrics?.max_drawdown ?? Infinity;
          bVal = b.metrics?.max_drawdown ?? Infinity;
          break;
        case 'total_trades':
          aVal = a.metrics?.total_trades ?? 0;
          bVal = b.metrics?.total_trades ?? 0;
          break;
        case 'win_rate':
          aVal = a.metrics?.win_rate ?? 0;
          bVal = b.metrics?.win_rate ?? 0;
          break;
        default:
          aVal = a.score ?? -Infinity;
          bVal = b.score ?? -Infinity;
      }
      
      return sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
    });
  };

  // Generate heatmap data
  const generateHeatmapData = (results: OptimizationResult[]) => {
    if (!results || results.length === 0) return null;
    
    const tpValues = [...new Set(results.map(r => r.parameters.tp_pct))].sort((a, b) => a - b);
    const slValues = [...new Set(results.map(r => r.parameters.sl_pct))].sort((a, b) => a - b);
    
    const zData: number[][] = [];
    
    for (const slVal of slValues) {
      const row: number[] = [];
      for (const tpVal of tpValues) {
        const match = results.find(
          r => r.parameters.tp_pct === tpVal && r.parameters.sl_pct === slVal
        );
        row.push(match?.score ?? NaN);
      }
      zData.push(row);
    }
    
    return {
      data: [{
        type: 'heatmap' as const,
        x: tpValues,
        y: slValues,
        z: zData,
        colorscale: 'Viridis',
        hovertemplate: 'TP: %{x}%<br>SL: %{y}%<br>Score: %{z:.3f}<extra></extra>',
      }],
      layout: {
        title: 'Optimization Heatmap (TP vs SL)',
        xaxis: { title: 'Take Profit %' },
        yaxis: { title: 'Stop Loss %' },
        height: 500,
      },
    };
  };
  
  const handleExpand = async (o: Optimization) => {
    const newId = expandedId === o.id ? null : o.id;
    setExpandedId(newId);
    if (newId) {
      try {
        // Fetch best + results if not already cached
        if (!bestMap[o.id]) {
          const b = await best(o.id);
          if (b) setBestMap((m) => ({ ...m, [o.id]: b }));
        }
        if (!resultsMap[o.id]) {
          const r = await results(o.id);
          if (r) setResultsMap((m) => ({ ...m, [o.id]: r }));
        }
      } catch (e: any) {
        notify({ message: `Failed to load results: ${e?.message || e}`, severity: 'error' });
      }
    }
  };

  const [busy, setBusy] = useState<{ id?: number; action?: 'grid' | 'wf' | 'bayes' }>({});
  const onRunGrid = async (o: Optimization) => {
    try {
      setBusy({ id: o.id, action: 'grid' });
      const payload = { param_space: o.param_ranges || {}, metric: o.metric };
      const resp = await runGrid(o.id, payload);
      if (resp)
        notify({ message: `Queued grid: ${resp.task_id} on ${resp.queue}`, severity: 'success' });
    } catch (e: any) {
      const msg = e?.friendlyMessage || e?.message || String(e);
      notify({ message: `Run grid failed: ${msg}`, severity: 'error' });
    } finally {
      setBusy({});
    }
  };
  const onRunWF = async (o: Optimization) => {
    try {
      setBusy({ id: o.id, action: 'wf' });
      const payload = { param_space: o.param_ranges || {}, metric: o.metric };
      const resp = await runWalkForward(o.id, payload);
      if (resp)
        notify({
          message: `Queued walk-forward: ${resp.task_id} on ${resp.queue}`,
          severity: 'success',
        });
    } catch (e: any) {
      const msg = e?.friendlyMessage || e?.message || String(e);
      notify({ message: `Run walk-forward failed: ${msg}`, severity: 'error' });
    } finally {
      setBusy({});
    }
  };
  const onRunBayes = async (o: Optimization) => {
    try {
      setBusy({ id: o.id, action: 'bayes' });
      const payload = { param_space: o.param_ranges || {}, metric: o.metric } as any;
      const resp = await runBayesian(o.id, payload);
      if (resp)
        notify({
          message: `Queued bayesian: ${resp.task_id} on ${resp.queue}`,
          severity: 'success',
        });
    } catch (e: any) {
      const msg = e?.friendlyMessage || e?.message || String(e);
      notify({ message: `Run bayesian failed: ${msg}`, severity: 'error' });
    } finally {
      setBusy({});
    }
  };

  return (
    <Container>
      <Typography variant="h4">Optimizations</Typography>
      <Stack direction="row" spacing={2} sx={{ mt: 2, mb: 2 }}>
        <TextField
          label="Status"
          size="small"
          select
          value={localStatus}
          onChange={(e) => setLocalStatus(e.target.value)}
          sx={{ width: 180 }}
        >
          <MenuItem value="">All</MenuItem>
          {['queued', 'running', 'completed', 'failed'].map((v) => (
            <MenuItem key={v} value={v}>
              {v}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="Strategy ID"
          size="small"
          value={localStrategyId}
          onChange={(e) => setLocalStrategyId(e.target.value.replace(/\D/g, ''))}
          sx={{ width: 160 }}
        />
        <Button
          variant="outlined"
          disabled={loading}
          onClick={() => {
            const sid = localStrategyId ? Number(localStrategyId) : undefined;
            setFilters({ status: localStatus || undefined, strategyId: sid });
            fetchAll({ limit, offset, status: localStatus || undefined, strategy_id: sid }).catch(
              () => notify({ message: 'Failed to apply filters', severity: 'error' })
            );
          }}
        >
          Apply
        </Button>
      </Stack>
      {loading && <div>Loading...</div>}
      {error && <div>{error}</div>}
      <PaginatedList
        items={items}
        total={total}
        limit={limit}
        offset={offset}
        onPageChange={(p) => setPage(p)}
        renderItem={(o) => (
          <Accordion
            expanded={expandedId === o.id}
            onChange={() => {
              select(o.id);
              handleExpand(o as Optimization);
            }}
            key={(o as Optimization).id}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Stack
                direction="row"
                spacing={2}
                alignItems="center"
                sx={{ width: '100%', justifyContent: 'space-between' }}
              >
                <ListItemText
                  primary={`${(o as Optimization).optimization_type.toUpperCase()} — ${(o as Optimization).symbol} / ${(o as Optimization).timeframe}`}
                  secondary={`Status: ${(o as Optimization).status}${(o as Optimization).best_score != null ? `, Best: ${(o as Optimization).best_score}` : ''}`}
                />
                <Stack direction="row" spacing={1}>
                  <Chip label={(o as Optimization).metric} size="small" />
                  <Button size="small" href={`#/optimization/${(o as Optimization).id}`}>
                    Open Details
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={busy.id === (o as Optimization).id && busy.action === 'grid'}
                    onClick={(e) => {
                      e.stopPropagation();
                      onRunGrid(o as Optimization);
                    }}
                  >
                    {busy.id === (o as Optimization).id && busy.action === 'grid'
                      ? 'Queueing…'
                      : 'Run Grid'}
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={busy.id === (o as Optimization).id && busy.action === 'wf'}
                    onClick={(e) => {
                      e.stopPropagation();
                      onRunWF(o as Optimization);
                    }}
                  >
                    {busy.id === (o as Optimization).id && busy.action === 'wf'
                      ? 'Queueing…'
                      : 'Run Walk-Forward'}
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={busy.id === (o as Optimization).id && busy.action === 'bayes'}
                    onClick={(e) => {
                      e.stopPropagation();
                      onRunBayes(o as Optimization);
                    }}
                  >
                    {busy.id === (o as Optimization).id && busy.action === 'bayes'
                      ? 'Queueing…'
                      : 'Run Bayesian'}
                  </Button>
                </Stack>
              </Stack>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={2}>
                <div>
                  <Typography variant="subtitle1">Best</Typography>
                  <Divider sx={{ my: 1 }} />
                  {bestMap[(o as Optimization).id] ? (
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                      {JSON.stringify(bestMap[(o as Optimization).id], null, 2)}
                    </pre>
                  ) : (
                    <em>No best result yet.</em>
                  )}
                </div>
                <div>
                  <Typography variant="subtitle1">Results</Typography>
                  <Divider sx={{ my: 1 }} />
                  {resultsMap[(o as Optimization).id]?.length ? (
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            <th style={{ textAlign: 'left', padding: 6 }}>Score</th>
                            <th style={{ textAlign: 'left', padding: 6 }}>Sharpe</th>
                            <th style={{ textAlign: 'left', padding: 6 }}>Max DD</th>
                            <th style={{ textAlign: 'left', padding: 6 }}>Trades</th>
                            <th style={{ textAlign: 'left', padding: 6 }}>Params</th>
                          </tr>
                        </thead>
                        <tbody>
                          {resultsMap[(o as Optimization).id].map((r) => (
                            <tr key={r.id}>
                              <td style={{ padding: 6 }}>{r.score}</td>
                              <td style={{ padding: 6 }}>{r.sharpe_ratio ?? '-'}</td>
                              <td style={{ padding: 6 }}>{r.max_drawdown ?? '-'}</td>
                              <td style={{ padding: 6 }}>{r.total_trades ?? '-'}</td>
                              <td style={{ padding: 6 }}>
                                <code>{JSON.stringify(r.params)}</code>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <em>No results.</em>
                  )}
                </div>
              </Stack>
            </AccordionDetails>
          </Accordion>
        )}
      />
    </Container>
  );
};

export default OptimizationsPage;
