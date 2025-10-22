import React from 'react';
import { Box, Button, Container, IconButton, Stack, TextField, Tooltip, Typography } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import ActiveBotRow from '../components/ActiveBotRow';
import { selectFilteredActive, useActiveBots } from '../store/activeBots';

const ActiveBotsPage: React.FC = () => {
  const filter = useActiveBots((s) => s.filter);
  const setFilter = useActiveBots((s) => s.setFilter);
  const items = useActiveBots((s) => selectFilteredActive(s));
  const refresh = useActiveBots((s) => s.refresh);
  const load = useActiveBots((s) => s.load);

  React.useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Container maxWidth="lg" sx={{ py: 2 }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ xs: 'stretch', sm: 'center' }} justifyContent="space-between" mb={2}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>Активные сделки ({items.length})</Typography>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <TextField size="small" placeholder="Поиск" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <Tooltip title="Обновить">
            <span>
              <IconButton color="primary" onClick={refresh}>
                <RefreshIcon />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Фильтры (макет)">
            <span>
              <IconButton>
                <FilterAltIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      </Stack>

      <Stack spacing={1.25}>
        {items.map((x) => (
          <ActiveBotRow key={x.id} item={x} />
        ))}
        {items.length === 0 && (
          <Box sx={{ textAlign: 'center', color: 'text.secondary', py: 8 }}>Нет активных сделок</Box>
        )}
      </Stack>
    </Container>
  );
};

export default ActiveBotsPage;
