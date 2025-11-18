import React from 'react';
import {
  Box,
  Container,
  Divider,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
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
  const attachLive = useActiveBots((s) => s.attachLive);
  const detachLive = useActiveBots((s) => s.detachLive);

  React.useEffect(() => {
    load();
    const t = setTimeout(() => attachLive('1'), 100); // slight delay to ensure items loaded
    return () => {
      clearTimeout(t);
      detachLive();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Stats panel calculations
  const stats = React.useMemo(() => {
    const count = items.length;
    const countLong = items.filter((x) => x.side === 'LONG').length;
    const countShort = items.filter((x) => x.side === 'SHORT').length;
    const allocated = items.reduce((s, it) => s + (it.qty ?? 0) * (it.current ?? it.entry), 0);
    const pnlUsd = items.reduce((s, it) => s + (it.pnlUsd || 0), 0);
    const totalQty = items.reduce((s, it) => s + (it.qty ?? 0), 0);
    const avgEntry =
      totalQty > 0 ? items.reduce((s, it) => s + it.entry * (it.qty ?? 0), 0) / totalQty : 0;
    const pnlPct = allocated > 0 ? (pnlUsd / allocated) * 100 : 0;
    return { count, countLong, countShort, allocated, pnlUsd, pnlPct, avgEntry };
  }, [items]);

  return (
    <Container maxWidth="lg" sx={{ py: 2 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1.5}
        alignItems={{ xs: 'stretch', sm: 'center' }}
        justifyContent="space-between"
        mb={2}
      >
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          Активные сделки ({items.length})
        </Typography>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <TextField
            size="small"
            placeholder="Поиск"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
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

      {/* Stats panel */}
      <Box
        sx={{
          mb: 2,
          p: 2,
          bgcolor: '#fff',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
        }}
      >
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={3}
          divider={<Divider orientation="vertical" flexItem />}
        >
          <Stack>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              ВСЕГО СДЕЛОК
            </Typography>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {stats.count}{' '}
              <Typography
                component="span"
                variant="body2"
                sx={{ color: 'text.secondary', ml: 0.5 }}
              >
                ({stats.countLong} L / {stats.countShort} S)
              </Typography>
            </Typography>
          </Stack>
          <Stack>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              ALLOCIROVANO
            </Typography>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {stats.allocated.toFixed(2)} USDT
            </Typography>
          </Stack>
          <Stack>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              AVG ENTRY (w)
            </Typography>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {stats.avgEntry.toFixed(4)}
            </Typography>
          </Stack>
          <Stack>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              TOTAL P&L
            </Typography>
            <Typography
              variant="subtitle1"
              sx={{ fontWeight: 700, color: stats.pnlUsd >= 0 ? 'success.main' : 'error.main' }}
            >
              {stats.pnlUsd >= 0 ? '+' : '−'}
              {Math.abs(stats.pnlUsd).toFixed(2)} USDT{' '}
              <Typography
                component="span"
                variant="body2"
                sx={{ ml: 0.5, color: 'text.secondary' }}
              >
                ({(stats.pnlPct >= 0 ? '+' : '−') + Math.abs(stats.pnlPct).toFixed(2)}%)
              </Typography>
            </Typography>
          </Stack>
        </Stack>
      </Box>

      <Stack spacing={1.25}>
        {items.map((x) => (
          <ActiveBotRow key={x.id} item={x} />
        ))}
        {items.length === 0 && (
          <Box sx={{ textAlign: 'center', color: 'text.secondary', py: 8 }}>
            Нет активных сделок
          </Box>
        )}
      </Stack>
    </Container>
  );
};

export default ActiveBotsPage;
