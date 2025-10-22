import React from 'react';
import { Box, Chip, IconButton, Menu, MenuItem, Stack, Typography } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import CloseIcon from '@mui/icons-material/Close';
import AddIcon from '@mui/icons-material/Add';
import CancelIcon from '@mui/icons-material/Cancel';
import PriceProgressBar from './PriceProgressBar';
import { ActiveBot, useActiveBots } from '../store/activeBots';
import { emitNotification } from '../services/notifications';

const sideColor: Record<ActiveBot['side'], string> = {
  LONG: '#1db954',
  SHORT: '#ff6d00',
};

const ActiveBotRow: React.FC<{ item: ActiveBot }> = ({ item }) => {
  const [anchor, setAnchor] = React.useState<null | HTMLElement>(null);
  const closeDeal = useActiveBots((s) => s.closeDeal);
  const averageDeal = useActiveBots((s) => s.averageDeal);
  const cancelDeal = useActiveBots((s) => s.cancelDeal);

  const loss = item.pnlUsd < 0;

  const closeMenu = () => setAnchor(null);
  const onOpenDeal = () => {
    emitNotification({ message: 'Открыта страница сделки (макет)', severity: 'info' });
    closeMenu();
  };
  const onOpenBot = () => {
    emitNotification({ message: 'Открыт редактор бота (макет)', severity: 'info' });
    closeMenu();
  };
  const onCloseMarket = async () => {
    await closeDeal(item.id);
    emitNotification({ message: 'Сделка закрыта (mock API)', severity: 'warning' });
    closeMenu();
  };
  const onManualAverage = async () => {
    await averageDeal(item.id);
    emitNotification({ message: 'Усреднение выполнено (mock API)', severity: 'info' });
    closeMenu();
  };
  const onCancelDeal = async () => {
    await cancelDeal(item.id);
    emitNotification({ message: 'Сделка отменена (mock API)', severity: 'error' });
    closeMenu();
  };

  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: '6px 1fr 520px 220px 48px', alignItems: 'center', bgcolor: '#fff', borderRadius: 1, border: '1px solid', borderColor: 'divider', overflow: 'hidden' }}>
      <Box sx={{ width: '6px', height: '100%', bgcolor: sideColor[item.side] }} />

      {/* Left: name + chips */}
      <Box sx={{ px: 2, py: 1 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            {item.name}
          </Typography>
          <Chip size="small" label={item.side} sx={{ bgcolor: 'rgba(0,0,0,0.04)' }} />
          {item.orderProgress && (
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              ОРДЕРА {item.orderProgress}
            </Typography>
          )}
        </Stack>
      </Box>

      {/* Middle: bar */}
      <Box sx={{ px: 2 }}>
        <PriceProgressBar
          min={item.min}
          entry={item.entry}
          nextOpen={item.nextOpen}
          target={item.target}
          current={item.current}
          side={item.side}
        />
      </Box>

      {/* Right: P&L */}
      <Box sx={{ px: 2 }}>
        <Typography variant="subtitle2" sx={{ color: loss ? 'error.main' : 'success.main', fontWeight: 600 }}>
          {item.pnlUsd > 0 ? '+' : '−'}{Math.abs(item.pnlUsd)} USDT
        </Typography>
        <Typography variant="caption" sx={{ color: loss ? 'error.main' : 'success.main' }}>
          ({item.pnlPct > 0 ? '+' : '−'}{Math.abs(item.pnlPct)}%)
        </Typography>
      </Box>

      {/* Actions */}
      <Box>
        <IconButton size="small" onClick={(e) => setAnchor(e.currentTarget)}>
          <MoreVertIcon fontSize="small" />
        </IconButton>
        <Menu anchorEl={anchor} open={!!anchor} onClose={closeMenu}>
          <MenuItem onClick={onOpenDeal}>
            <ShowChartIcon fontSize="small" style={{ marginRight: 8 }} /> К сделке
          </MenuItem>
          <MenuItem onClick={onOpenBot}>
            <ShowChartIcon fontSize="small" style={{ marginRight: 8 }} /> К боту
          </MenuItem>
          <MenuItem onClick={onCloseMarket}>
            <CloseIcon fontSize="small" style={{ marginRight: 8 }} /> Закрыть по рынку
          </MenuItem>
          <MenuItem onClick={onManualAverage}>
            <AddIcon fontSize="small" style={{ marginRight: 8 }} /> Усреднить
          </MenuItem>
          <MenuItem onClick={onCancelDeal}>
            <CancelIcon fontSize="small" style={{ marginRight: 8 }} /> Отменить
          </MenuItem>
        </Menu>
      </Box>
    </Box>
  );
};

export default ActiveBotRow;
