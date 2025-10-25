import React, { useEffect, useState } from 'react';
import {
  Container,
  Typography,
  Button,
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
  FormControl,
  InputLabel,
  Select,
  Alert,
  Tab,
  Tabs,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AddIcon from '@mui/icons-material/Add';
import TuneIcon from '@mui/icons-material/Tune';
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
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
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
    create,
    runGrid,
    results,
    best,
    status,
    strategyId,
    setFilters,
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
  const [selectedTab, setSelectedTab] = useState<number>(0);

  const [newOptForm, setNewOptForm] = useState<NewOptimizationForm>({
    strategy_id: '',
    symbol: 'BTCUSDT',
    timeframe: '15',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    initial_capital: 10000,
    tp_range: { start: 1.0, stop: 5.0, step: 0.5 },
    sl_range: { start: 0.5, stop: 3.0, step: 0.5 },
    trailing_activation_range: { start: 0.0, stop: 2.0, step: 0.5 },
    trailing_distance_range: { start: 0.3, stop: 1.5, step: 0.3 },
    score_function: 'sharpe',
    min_trades: 30,
    max_drawdown: 0.2,
    n_processes: 4,
  });

  useEffect(() => {
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

  // Calculate total combinations
  const calculateTotalCombinations = (form: NewOptimizationForm): number => {
    const tpCount = Math.floor((form.tp_range.stop - form.tp_range.start) / form.tp_range.step) + 1;
    const slCount = Math.floor((form.sl_range.stop - form.sl_range.start) / form.sl_range.step) + 1;
    const trailActCount =
      Math.floor(
        (form.trailing_activation_range.stop - form.trailing_activation_range.start) /
          form.trailing_activation_range.step
      ) + 1;
    const trailDistCount =
      Math.floor(
        (form.trailing_distance_range.stop - form.trailing_distance_range.start) /
          form.trailing_distance_range.step
      ) + 1;
    return tpCount * slCount * trailActCount * trailDistCount;
  };

  // Handle new optimization
  const handleCreateOptimization = async () => {
    try {
      const totalCombos = calculateTotalCombinations(newOptForm);

      if (totalCombos > 10000) {
        notify({
          message: `Warning: ${totalCombos} combinations may take a long time!`,
          severity: 'warning',
        });
      }

      // Step 1: Create optimization record
      const optimization = await create({
        strategy_id: parseInt(newOptForm.strategy_id),
        optimization_type: 'grid_search',
        symbol: newOptForm.symbol,
        timeframe: newOptForm.timeframe,
        start_date: new Date(newOptForm.start_date).toISOString(),
        end_date: new Date(newOptForm.end_date).toISOString(),
        param_ranges: {
          tp_pct: [newOptForm.tp_range.start, newOptForm.tp_range.stop, newOptForm.tp_range.step],
          sl_pct: [newOptForm.sl_range.start, newOptForm.sl_range.stop, newOptForm.sl_range.step],
          trailing_activation_pct: [
            newOptForm.trailing_activation_range.start,
            newOptForm.trailing_activation_range.stop,
            newOptForm.trailing_activation_range.step,
          ],
          trailing_distance_pct: [
            newOptForm.trailing_distance_range.start,
            newOptForm.trailing_distance_range.stop,
            newOptForm.trailing_distance_range.step,
          ],
        },
        metric: newOptForm.score_function === 'sharpe' ? 'sharpe_ratio' : 'profit_factor',
        initial_capital: newOptForm.initial_capital,
        total_combinations: totalCombos,
        config: {
          validation_rules: {
            min_trades: newOptForm.min_trades,
            max_drawdown: newOptForm.max_drawdown,
          },
          n_processes: newOptForm.n_processes,
        },
      });

      if (!optimization) {
        throw new Error('Failed to create optimization record');
      }

      // Step 2: Start grid search task
      await runGrid(optimization.id, {
        param_space: {
          tp_pct: [newOptForm.tp_range.start, newOptForm.tp_range.stop, newOptForm.tp_range.step],
          sl_pct: [newOptForm.sl_range.start, newOptForm.sl_range.stop, newOptForm.sl_range.step],
        },
        metric: newOptForm.score_function === 'sharpe' ? 'sharpe_ratio' : 'profit_factor',
      });

      setOpenNewDialog(false);
      notify({
        message: `Grid optimization #${optimization.id} started with ${totalCombos} combinations!`,
        severity: 'success',
      });

      // Refresh list
      await fetchAll();
    } catch (err: any) {
      notify({
        message: `Failed to start optimization: ${err?.message || err}`,
        severity: 'error',
      });
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

    const tpValues = [...new Set(results.map((r) => r.params?.tp_pct).filter(Boolean))].sort(
      (a, b) => (a as number) - (b as number)
    );
    const slValues = [...new Set(results.map((r) => r.params?.sl_pct).filter(Boolean))].sort(
      (a, b) => (a as number) - (b as number)
    );

    if (tpValues.length === 0 || slValues.length === 0) return null;

    const zData: number[][] = [];

    for (const slVal of slValues) {
      const row: number[] = [];
      for (const tpVal of tpValues) {
        const match = results.find((r) => r.params?.tp_pct === tpVal && r.params?.sl_pct === slVal);
        row.push(match?.score ?? NaN);
      }
      zData.push(row);
    }

    return {
      data: [
        {
          type: 'heatmap' as const,
          x: tpValues,
          y: slValues,
          z: zData,
          colorscale: 'Viridis',
          hovertemplate: 'TP: %{x}%<br>SL: %{y}%<br>Score: %{z:.3f}<extra></extra>',
        },
      ],
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

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('desc');
    }
  };

  return (
    <Container maxWidth="xl">
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Typography variant="h4">Optimizations</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpenNewDialog(true)}>
          New Optimization
        </Button>
      </Stack>

      {/* Filters */}
      <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
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
      {error && <Alert severity="error">{error}</Alert>}

      {/* Optimizations List */}
      <PaginatedList
        items={items}
        total={total}
        limit={limit}
        offset={offset}
        onPageChange={(p) => setPage(p)}
        renderItem={(o: Optimization) => (
          <Accordion key={o.id} expanded={expandedId === o.id} onChange={() => handleExpand(o)}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Stack direction="row" spacing={2} alignItems="center" sx={{ width: '100%' }}>
                <Typography sx={{ fontWeight: 'bold' }}>#{o.id}</Typography>
                <Chip label={o.status || 'unknown'} size="small" />
                <Typography variant="body2">Strategy #{o.strategy_id}</Typography>
                <Typography variant="body2" sx={{ ml: 'auto' }}>
                  {o.optimization_type || 'grid'}
                </Typography>
              </Stack>
            </AccordionSummary>
            <AccordionDetails>
              <Divider sx={{ mb: 2 }} />

              {/* Tabs for Results/Heatmap */}
              <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
                <Tabs value={selectedTab} onChange={(_, v) => setSelectedTab(v)}>
                  <Tab label="Results Table" />
                  <Tab label="Heatmap" />
                  <Tab label="Best Result" />
                </Tabs>
              </Box>

              {/* Tab 0: Results Table */}
              {selectedTab === 0 && (
                <>
                  {resultsMap[o.id] && resultsMap[o.id].length > 0 ? (
                    <TableContainer component={Paper} sx={{ maxHeight: 600 }}>
                      <Table stickyHeader size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>
                              <TableSortLabel
                                active={sortKey === 'score'}
                                direction={sortKey === 'score' ? sortOrder : 'asc'}
                                onClick={() => handleSort('score')}
                              >
                                Score
                              </TableSortLabel>
                            </TableCell>
                            <TableCell>
                              <TableSortLabel
                                active={sortKey === 'sharpe_ratio'}
                                direction={sortKey === 'sharpe_ratio' ? sortOrder : 'asc'}
                                onClick={() => handleSort('sharpe_ratio')}
                              >
                                Sharpe
                              </TableSortLabel>
                            </TableCell>
                            <TableCell>
                              <TableSortLabel
                                active={sortKey === 'max_drawdown'}
                                direction={sortKey === 'max_drawdown' ? sortOrder : 'asc'}
                                onClick={() => handleSort('max_drawdown')}
                              >
                                Max DD
                              </TableSortLabel>
                            </TableCell>
                            <TableCell>
                              <TableSortLabel
                                active={sortKey === 'total_trades'}
                                direction={sortKey === 'total_trades' ? sortOrder : 'asc'}
                                onClick={() => handleSort('total_trades')}
                              >
                                Trades
                              </TableSortLabel>
                            </TableCell>
                            <TableCell>
                              <TableSortLabel
                                active={sortKey === 'win_rate'}
                                direction={sortKey === 'win_rate' ? sortOrder : 'asc'}
                                onClick={() => handleSort('win_rate')}
                              >
                                Win Rate
                              </TableSortLabel>
                            </TableCell>
                            <TableCell>TP %</TableCell>
                            <TableCell>SL %</TableCell>
                            <TableCell>Trailing Act</TableCell>
                            <TableCell>Trailing Dist</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {sortResults(resultsMap[o.id]).map((r, idx) => (
                            <TableRow key={idx} hover>
                              <TableCell>{r.score?.toFixed(3) ?? 'N/A'}</TableCell>
                              <TableCell>{r.metrics?.sharpe_ratio?.toFixed(2) ?? 'N/A'}</TableCell>
                              <TableCell>
                                {r.metrics?.max_drawdown
                                  ? (r.metrics.max_drawdown * 100).toFixed(2) + '%'
                                  : 'N/A'}
                              </TableCell>
                              <TableCell>{r.metrics?.total_trades ?? 'N/A'}</TableCell>
                              <TableCell>
                                {r.metrics?.win_rate
                                  ? (r.metrics.win_rate * 100).toFixed(1) + '%'
                                  : 'N/A'}
                              </TableCell>
                              <TableCell>{r.params?.tp_pct ?? 'N/A'}</TableCell>
                              <TableCell>{r.params?.sl_pct ?? 'N/A'}</TableCell>
                              <TableCell>{r.params?.trailing_activation_pct ?? 'N/A'}</TableCell>
                              <TableCell>{r.params?.trailing_distance_pct ?? 'N/A'}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      No results available
                    </Typography>
                  )}
                </>
              )}

              {/* Tab 1: Heatmap */}
              {selectedTab === 1 && (
                <>
                  {resultsMap[o.id] && resultsMap[o.id].length > 0 ? (
                    (() => {
                      const heatmapData = generateHeatmapData(resultsMap[o.id]);
                      return heatmapData ? (
                        <PlotlyChart data={heatmapData.data} layout={heatmapData.layout} />
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          Not enough data for heatmap
                        </Typography>
                      );
                    })()
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      No results available
                    </Typography>
                  )}
                </>
              )}

              {/* Tab 2: Best Result */}
              {selectedTab === 2 && (
                <>
                  {bestMap[o.id] ? (
                    <Box>
                      <Typography variant="h6" gutterBottom>
                        Best Result
                      </Typography>
                      <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                        <pre style={{ margin: 0, overflow: 'auto' }}>
                          {JSON.stringify(bestMap[o.id], null, 2)}
                        </pre>
                      </Paper>
                    </Box>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      No best result available
                    </Typography>
                  )}
                </>
              )}
            </AccordionDetails>
          </Accordion>
        )}
      />

      {/* New Optimization Dialog */}
      <Dialog open={openNewDialog} onClose={() => setOpenNewDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <TuneIcon />
            <Typography variant="h6">New Grid Optimization</Typography>
          </Stack>
        </DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={3}>
            {/* Strategy ID */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Strategy ID"
                type="number"
                value={newOptForm.strategy_id}
                onChange={(e) => setNewOptForm({ ...newOptForm, strategy_id: e.target.value })}
                required
              />
            </Grid>

            {/* Symbol */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Symbol"
                value={newOptForm.symbol}
                onChange={(e) => setNewOptForm({ ...newOptForm, symbol: e.target.value })}
                required
                placeholder="BTCUSDT"
              />
            </Grid>

            {/* Timeframe */}
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel>Timeframe</InputLabel>
                <Select
                  value={newOptForm.timeframe}
                  label="Timeframe"
                  onChange={(e) => setNewOptForm({ ...newOptForm, timeframe: e.target.value })}
                >
                  <MenuItem value="1">1m</MenuItem>
                  <MenuItem value="5">5m</MenuItem>
                  <MenuItem value="15">15m</MenuItem>
                  <MenuItem value="30">30m</MenuItem>
                  <MenuItem value="60">1h</MenuItem>
                  <MenuItem value="240">4h</MenuItem>
                  <MenuItem value="D">1D</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {/* Start Date */}
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Start Date"
                type="date"
                value={newOptForm.start_date}
                onChange={(e) => setNewOptForm({ ...newOptForm, start_date: e.target.value })}
                InputLabelProps={{ shrink: true }}
                required
              />
            </Grid>

            {/* End Date */}
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="End Date"
                type="date"
                value={newOptForm.end_date}
                onChange={(e) => setNewOptForm({ ...newOptForm, end_date: e.target.value })}
                InputLabelProps={{ shrink: true }}
                required
              />
            </Grid>

            {/* Initial Capital */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Initial Capital (USDT)"
                type="number"
                value={newOptForm.initial_capital}
                onChange={(e) =>
                  setNewOptForm({ ...newOptForm, initial_capital: parseFloat(e.target.value) })
                }
                required
              />
            </Grid>

            <Grid item xs={12}>
              <Divider />
            </Grid>

            {/* Take Profit Range */}
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Take Profit % Range
              </Typography>
              <Stack direction="row" spacing={2}>
                <TextField
                  label="Start"
                  type="number"
                  size="small"
                  value={newOptForm.tp_range.start}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      tp_range: { ...newOptForm.tp_range, start: parseFloat(e.target.value) },
                    })
                  }
                />
                <TextField
                  label="Stop"
                  type="number"
                  size="small"
                  value={newOptForm.tp_range.stop}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      tp_range: { ...newOptForm.tp_range, stop: parseFloat(e.target.value) },
                    })
                  }
                />
                <TextField
                  label="Step"
                  type="number"
                  size="small"
                  value={newOptForm.tp_range.step}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      tp_range: { ...newOptForm.tp_range, step: parseFloat(e.target.value) },
                    })
                  }
                />
              </Stack>
            </Grid>

            {/* Stop Loss Range */}
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Stop Loss % Range
              </Typography>
              <Stack direction="row" spacing={2}>
                <TextField
                  label="Start"
                  type="number"
                  size="small"
                  value={newOptForm.sl_range.start}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      sl_range: { ...newOptForm.sl_range, start: parseFloat(e.target.value) },
                    })
                  }
                />
                <TextField
                  label="Stop"
                  type="number"
                  size="small"
                  value={newOptForm.sl_range.stop}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      sl_range: { ...newOptForm.sl_range, stop: parseFloat(e.target.value) },
                    })
                  }
                />
                <TextField
                  label="Step"
                  type="number"
                  size="small"
                  value={newOptForm.sl_range.step}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      sl_range: { ...newOptForm.sl_range, step: parseFloat(e.target.value) },
                    })
                  }
                />
              </Stack>
            </Grid>

            {/* Trailing Activation Range */}
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Trailing Activation % Range
              </Typography>
              <Stack direction="row" spacing={2}>
                <TextField
                  label="Start"
                  type="number"
                  size="small"
                  value={newOptForm.trailing_activation_range.start}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      trailing_activation_range: {
                        ...newOptForm.trailing_activation_range,
                        start: parseFloat(e.target.value),
                      },
                    })
                  }
                />
                <TextField
                  label="Stop"
                  type="number"
                  size="small"
                  value={newOptForm.trailing_activation_range.stop}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      trailing_activation_range: {
                        ...newOptForm.trailing_activation_range,
                        stop: parseFloat(e.target.value),
                      },
                    })
                  }
                />
                <TextField
                  label="Step"
                  type="number"
                  size="small"
                  value={newOptForm.trailing_activation_range.step}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      trailing_activation_range: {
                        ...newOptForm.trailing_activation_range,
                        step: parseFloat(e.target.value),
                      },
                    })
                  }
                />
              </Stack>
            </Grid>

            {/* Trailing Distance Range */}
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Trailing Distance % Range
              </Typography>
              <Stack direction="row" spacing={2}>
                <TextField
                  label="Start"
                  type="number"
                  size="small"
                  value={newOptForm.trailing_distance_range.start}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      trailing_distance_range: {
                        ...newOptForm.trailing_distance_range,
                        start: parseFloat(e.target.value),
                      },
                    })
                  }
                />
                <TextField
                  label="Stop"
                  type="number"
                  size="small"
                  value={newOptForm.trailing_distance_range.stop}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      trailing_distance_range: {
                        ...newOptForm.trailing_distance_range,
                        stop: parseFloat(e.target.value),
                      },
                    })
                  }
                />
                <TextField
                  label="Step"
                  type="number"
                  size="small"
                  value={newOptForm.trailing_distance_range.step}
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      trailing_distance_range: {
                        ...newOptForm.trailing_distance_range,
                        step: parseFloat(e.target.value),
                      },
                    })
                  }
                />
              </Stack>
            </Grid>

            <Grid item xs={12}>
              <Divider />
            </Grid>

            {/* Score Function */}
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Score Function</InputLabel>
                <Select
                  value={newOptForm.score_function}
                  label="Score Function"
                  onChange={(e) =>
                    setNewOptForm({
                      ...newOptForm,
                      score_function: e.target.value as 'sharpe' | 'profit_factor' | 'custom',
                    })
                  }
                >
                  <MenuItem value="sharpe">Sharpe Ratio</MenuItem>
                  <MenuItem value="profit_factor">Profit Factor</MenuItem>
                  <MenuItem value="custom">Custom</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {/* Min Trades */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Min Trades"
                type="number"
                value={newOptForm.min_trades}
                onChange={(e) =>
                  setNewOptForm({ ...newOptForm, min_trades: parseInt(e.target.value) })
                }
              />
            </Grid>

            {/* Max Drawdown */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Max Drawdown (0.0-1.0)"
                type="number"
                inputProps={{ step: 0.01, min: 0, max: 1 }}
                value={newOptForm.max_drawdown}
                onChange={(e) =>
                  setNewOptForm({ ...newOptForm, max_drawdown: parseFloat(e.target.value) })
                }
              />
            </Grid>

            {/* N Processes */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Parallel Processes"
                type="number"
                value={newOptForm.n_processes}
                onChange={(e) =>
                  setNewOptForm({ ...newOptForm, n_processes: parseInt(e.target.value) })
                }
              />
            </Grid>

            {/* Total Combinations Preview */}
            <Grid item xs={12}>
              <Alert severity="info">
                <Typography variant="body2">
                  Total combinations:{' '}
                  <strong>{calculateTotalCombinations(newOptForm).toLocaleString()}</strong>
                </Typography>
                <Typography variant="caption">
                  Estimated time: ~{(calculateTotalCombinations(newOptForm) / 10).toFixed(0)}{' '}
                  seconds (assuming 10 backtests/sec)
                </Typography>
              </Alert>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenNewDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreateOptimization}
            disabled={!newOptForm.strategy_id}
          >
            Start Optimization
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
