import React, { useEffect, useState } from 'react';
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
  } = useStrategiesStore();
  const notify = useNotify();
  const [localActive, setLocalActive] = useState<string>(
    isActive === undefined ? 'all' : isActive ? 'active' : 'inactive'
  );
  const [localType, setLocalType] = useState<string>(strategyType || '');

  useEffect(() => {
    fetchAll().catch((_e) => notify({ message: 'Failed to load strategies', severity: 'error' }));
  }, [fetchAll, notify]);

  return (
    <Container>
      <Typography variant="h4">Strategies</Typography>
      <Button variant="contained" sx={{ mt: 2, mb: 2 }}>
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
        items={items}
        total={total}
        limit={limit}
        offset={offset}
        onPageChange={(p) => setPage(p)}
        renderItem={(s) => (
          <ListItem
            key={s.id}
            button
            component="a"
            href={`#/strategy/${s.id}`}
            onClick={() => select(s.id)}
          >
            <ListItemText primary={`${s.name} (${s.strategy_type})`} secondary={s.description} />
          </ListItem>
        )}
      />
    </Container>
  );
};

export default StrategiesPage;
