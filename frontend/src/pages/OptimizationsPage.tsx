import React, { useEffect, useState } from 'react';
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
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PaginatedList from '../components/PaginatedList';
import { useOptimizationsStore } from '../store/optimizations';
import { useNotify } from '../components/NotificationsProvider';
import type { Optimization, OptimizationResult } from '../types/api';
import { useLocation } from 'react-router-dom';

const OptimizationsPage: React.FC = () => {
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
