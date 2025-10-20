import React, { useEffect } from 'react';
import { Container, Typography, Button, List, ListItem, ListItemText } from '@mui/material';
import { useBacktestsStore } from '../store/backtests';
import { useNotify } from '../components/NotificationsProvider';

const OptimizationsPage: React.FC = () => {
  const { items, fetchAll, loading, error } = useBacktestsStore();
  const notify = useNotify();

  useEffect(() => {
    fetchAll().catch(() => notify({ message: 'Failed to load optimizations', severity: 'error' }));
  }, []);

  return (
    <Container>
      <Typography variant="h4">Optimizations / Backtests</Typography>
      <Button variant="contained" sx={{ mt: 2, mb: 2 }}>
        Run Optimization
      </Button>
      {loading && <div>Loading...</div>}
      {error && <div>{error}</div>}
      <List>
        {items.map((s) => (
          <ListItem key={s.id} button component="a" href={`#/backtests/${s.id}`}>
            <ListItemText primary={`${s.symbol} ${s.timeframe}`} secondary={`Status: ${s.status}`} />
          </ListItem>
        ))}
      </List>
    </Container>
  );
};

export default OptimizationsPage;
