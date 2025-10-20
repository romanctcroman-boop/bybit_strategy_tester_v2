import React, { useEffect } from 'react';
import { Container, Typography, Button, List, ListItem, ListItemText } from '@mui/material';
import { useStrategiesStore } from '../store/strategies';
import { useNotify } from '../components/NotificationsProvider';

const StrategiesPage: React.FC = () => {
  const { items, fetchAll, loading, error } = useStrategiesStore();
  const notify = useNotify();

  useEffect(() => {
    fetchAll().catch((e) => notify({ message: 'Failed to load strategies', severity: 'error' }));
  }, []);

  return (
    <Container>
      <Typography variant="h4">Strategies</Typography>
      <Button variant="contained" sx={{ mt: 2, mb: 2 }}>
        New Strategy
      </Button>
      {loading && <div>Loading...</div>}
      {error && <div>{error}</div>}
      <List>
        {items.map((s) => (
          <ListItem key={s.id} button component="a" href={`#/strategies/${s.id}`}>
            <ListItemText primary={s.name} secondary={s.description} />
          </ListItem>
        ))}
      </List>
    </Container>
  );
};

export default StrategiesPage;
