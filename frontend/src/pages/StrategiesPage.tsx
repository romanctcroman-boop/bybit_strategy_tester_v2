import React, { useEffect, useMemo, useState } from 'react';
import {
  Container,
  Typography,
  Button,
  ListItem,
  ListItemText,
  TextField,
  MenuItem,
  Stack,
} from '@mui/material';
import PaginatedList from '../components/PaginatedList';
import { useStrategiesStore } from '../store/strategies';
import { useNotify } from '../components/NotificationsProvider';
import StrategyDialog from '../components/StrategyDialog';
import { IconButton } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

const StrategiesPage: React.FC = () => {
  const {
    items,
    total,
    limit,
    offset,
    fetchAll,
    setPage,
    loading,
    error,
    isActive,
    strategyType,
    setFilters,
    select,
    add,
    update,
    remove,
  } = useStrategiesStore();
  const notify = useNotify();
  const [localActive, setLocalActive] = useState<string>(
    isActive === undefined ? 'all' : isActive ? 'active' : 'inactive'
  );
  const [localType, setLocalType] = useState<string>(strategyType || '');
  const [sortBy, setSortBy] = useState<'created_at' | 'name'>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [dlgOpen, setDlgOpen] = useState(false);
  const [editing, setEditing] = useState<any | null>(null);

  useEffect(() => {
    fetchAll().catch((_e) => notify({ message: 'Failed to load strategies', severity: 'error' }));
  }, [fetchAll, notify]);

  const sortedItems = useMemo(() => {
    const arr = [...items];
    arr.sort((a, b) => {
      let av: any = (a as any)[sortBy];
      let bv: any = (b as any)[sortBy];
      if (sortBy === 'created_at') {
        av = av ? Date.parse(av) : 0;
        bv = bv ? Date.parse(bv) : 0;
      } else {
        av = (av || '').toString().toLowerCase();
        bv = (bv || '').toString().toLowerCase();
      }
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return arr;
  }, [items, sortBy, sortDir]);

  return (
    <Container>
      <Typography variant="h4">Strategies</Typography>
      <Button
        variant="contained"
        sx={{ mt: 2, mb: 2 }}
        onClick={() => {
          setEditing(null);
          setDlgOpen(true);
        }}
      >
        New Strategy
      </Button>
      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <TextField
          label="Status"
          size="small"
          select
          value={localActive}
          onChange={(_e) => setLocalActive(_e.target.value)}
          sx={{ width: 160 }}
        >
          <MenuItem value="all">All</MenuItem>
          <MenuItem value="active">Active</MenuItem>
          <MenuItem value="inactive">Inactive</MenuItem>
        </TextField>
        <TextField
          label="Strategy Type"
          size="small"
          value={localType}
          onChange={(_e) => setLocalType(_e.target.value)}
          placeholder="e.g. rsi_ema"
          sx={{ width: 220 }}
        />
        <TextField
          label="Sort by"
          size="small"
          select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as any)}
          sx={{ width: 160 }}
        >
          <MenuItem value="created_at">Created</MenuItem>
          <MenuItem value="name">Name</MenuItem>
        </TextField>
        <TextField
          label="Order"
          size="small"
          select
          value={sortDir}
          onChange={(e) => setSortDir(e.target.value as any)}
          sx={{ width: 140 }}
        >
          <MenuItem value="asc">Asc</MenuItem>
          <MenuItem value="desc">Desc</MenuItem>
        </TextField>
        <Button
          variant="outlined"
          disabled={loading}
          onClick={() => {
            const a = localActive === 'all' ? undefined : localActive === 'active';
            setFilters({ isActive: a, strategyType: localType || undefined });
            fetchAll({ limit, offset, isActive: a, strategyType: localType || undefined }).catch(
              () => notify({ message: 'Failed to apply filters', severity: 'error' })
            );
          }}
        >
          {loading ? 'Applying…' : 'Apply'}
        </Button>
      </Stack>
      {loading && <div>Loading...</div>}
      {error && <div>{error}</div>}
      <PaginatedList
        items={sortedItems}
        total={total}
        limit={limit}
        offset={offset}
        onPageChange={(p) => setPage(p)}
        renderItem={(s) => (
          <ListItem
            key={s.id}
            secondaryAction={
              <Stack direction="row" spacing={1}>
                <IconButton
                  edge="end"
                  aria-label="edit"
                  onClick={(e) => {
                    e.preventDefault();
                    setEditing(s as any);
                    setDlgOpen(true);
                  }}
                >
                  <EditIcon />
                </IconButton>
                <IconButton
                  edge="end"
                  aria-label="delete"
                  onClick={async (e) => {
                    e.preventDefault();
                    try {
                      await remove((s as any).id);
                      notify({ message: 'Deleted', severity: 'success' });
                    } catch (err: any) {
                      notify({
                        message: err?.friendlyMessage || err?.message || 'Delete failed',
                        severity: 'error',
                      });
                    }
                  }}
                >
                  <DeleteIcon />
                </IconButton>
              </Stack>
            }
            button
            component="a"
            href={`#/strategy/${(s as any).id}`}
            onClick={() => select((s as any).id)}
          >
            <ListItemText
              primary={`${(s as any).name} (${(s as any).strategy_type})`}
              secondary={(s as any).description}
            />
          </ListItem>
        )}
      />

      <StrategyDialog
        open={dlgOpen}
        initial={editing}
        onClose={() => setDlgOpen(false)}
        onSubmit={async (payload) => {
          try {
            if (editing?.id) {
              await update(editing.id, payload);
              notify({ message: 'Updated', severity: 'success' });
            } else {
              await add(payload);
              notify({ message: 'Created', severity: 'success' });
            }
          } catch (e: any) {
            notify({
              message: e?.friendlyMessage || e?.message || 'Save failed',
              severity: 'error',
            });
            throw e;
          }
        }}
      />
    </Container>
  );
};

export default StrategiesPage;
