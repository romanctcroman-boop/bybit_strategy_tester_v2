import React from 'react';
import { Box, Button, Container, Stack, TextField, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import BotCard from '../components/BotCard';
import { selectFilteredBots, useBotsStore } from '../store/bots';

const BotsPage: React.FC = () => {
  const filter = useBotsStore((s) => s.filter);
  const setFilter = useBotsStore((s) => s.setFilter);
  const items = useBotsStore((s) => selectFilteredBots(s));
  const createBot = useBotsStore((s) => s.createBot);
  const load = useBotsStore((s) => s.load);

  React.useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCreate = () => {
    createBot({ name: 'Draft Bot', label: 'DRAFT', status: 'awaiting_signal' });
  };

  return (
    <Container maxWidth="lg" sx={{ py: 2 }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ xs: 'stretch', sm: 'center' }} spacing={1.5} mb={2}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          Боты
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
          <TextField
            size="small"
            placeholder="Поиск по названию/меткам"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <Button variant="contained" startIcon={<AddIcon />} onClick={onCreate}>
            Создать бота
          </Button>
        </Stack>
      </Stack>

      <Stack spacing={1.5}>
        {items.map((b) => (
          <BotCard key={b.id} bot={b} />
        ))}
        {items.length === 0 && (
          <Box sx={{ textAlign: 'center', color: 'text.secondary', py: 8 }}>
            <Typography variant="body1">Нет ботов. Нажмите «Создать бота», чтобы начать.</Typography>
          </Box>
        )}
      </Stack>
    </Container>
  );
};

export default BotsPage;
