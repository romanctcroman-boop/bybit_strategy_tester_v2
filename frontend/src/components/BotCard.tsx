import React from 'react';
import {
  Box,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import EditIcon from '@mui/icons-material/Edit';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import ShareIcon from '@mui/icons-material/Share';
import AssessmentIcon from '@mui/icons-material/Assessment';
import { Bot, botStatusLabel, exchangeLabel } from '../types/bots';
import { useBotsStore } from '../store/bots';
import { emitNotification } from '../services/notifications';

export interface BotCardProps {
  bot: Bot;
}

const statusColor: Record<Bot['status'], 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  awaiting_start: 'info',
  awaiting_signal: 'info',
  running: 'success',
  awaiting_stop: 'warning',
  stopped: 'warning',
  error: 'error',
};

const sideColor: Record<Bot['direction'], string> = {
  LONG: '#1db954', // green
  SHORT: '#ff6d00', // orange
};

const BotCard: React.FC<BotCardProps> = ({ bot }) => {
  const startBot = useBotsStore((s) => s.startBot);
  const stopBot = useBotsStore((s) => s.stopBot);
  const cloneBot = useBotsStore((s) => s.cloneBot);

  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const handleMenu = (e: React.MouseEvent<HTMLButtonElement>) => setAnchorEl(e.currentTarget);
  const handleClose = () => setAnchorEl(null);

  const onStart = () => {
    startBot(bot.id);
    emitNotification({ message: `Бот «${bot.name}» запущен`, severity: 'success' });
    handleClose();
  };
  const onStop = () => {
    stopBot(bot.id);
    emitNotification({ message: `Бот «${bot.name}» остановлен`, severity: 'info' });
    handleClose();
  };
  const onClone = () => {
    const c = cloneBot(bot.id);
    if (c) emitNotification({ message: `Скопирован как «${c.name}»`, severity: 'success' });
    handleClose();
  };

  const labelBg = bot.direction === 'LONG' ? 'rgba(29,185,84,0.1)' : 'rgba(255,109,0,0.1)';
  const labelColor = bot.direction === 'LONG' ? '#1db954' : '#ff6d00';

  return (
    <Card variant="outlined" sx={{ overflow: 'hidden' }}>
      <Box sx={{ display: 'flex' }}>
        {/* Side accent */}
        <Box sx={{ width: 6, backgroundColor: sideColor[bot.direction] }} />
        <Box sx={{ flex: 1 }}>
          <CardContent sx={{ py: 1.5 }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                  {bot.name}
                </Typography>
                <Chip label={bot.direction} size="small" sx={{ bgcolor: labelBg, color: labelColor }} />
                {bot.label && (
                  <Chip label={bot.label} size="small" variant="outlined" sx={{ borderStyle: 'dashed' }} />
                )}
              </Stack>
              <Stack direction="row" alignItems="center" spacing={0.5}>
                <Tooltip title="Меню">
                  <IconButton size="small" onClick={handleMenu}>
                    <MoreVertIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Menu anchorEl={anchorEl} open={open} onClose={handleClose} elevation={2}>
                  {/* Action set inspired by Veles: availability can depend on status */}
                  <MenuItem onClick={onStop}>
                    <StopIcon fontSize="small" style={{ marginRight: 8 }} /> Остановить
                  </MenuItem>
                  <MenuItem onClick={onStart}>
                    <PlayArrowIcon fontSize="small" style={{ marginRight: 8 }} /> Запустить сделку
                  </MenuItem>
                  <MenuItem onClick={handleClose}>
                    <EditIcon fontSize="small" style={{ marginRight: 8 }} /> Редактировать
                  </MenuItem>
                  <MenuItem onClick={onClone}>
                    <ContentCopyIcon fontSize="small" style={{ marginRight: 8 }} /> Клонировать
                  </MenuItem>
                  <MenuItem onClick={handleClose}>
                    <ShareIcon fontSize="small" style={{ marginRight: 8 }} /> Поделиться
                  </MenuItem>
                  <MenuItem onClick={handleClose}>
                    <AssessmentIcon fontSize="small" style={{ marginRight: 8 }} /> Бэктест
                  </MenuItem>
                </Menu>
              </Stack>
            </Stack>

            {/* Stats row */}
            <Stack direction="row" spacing={4} mt={1.25} alignItems="center" sx={{ color: 'text.secondary' }}>
              <Stack spacing={0.3}>
                <Typography variant="caption">СТАТУС</Typography>
                <Chip
                  size="small"
                  color={statusColor[bot.status]}
                  label={botStatusLabel[bot.status]}
                  variant="outlined"
                />
              </Stack>
              <Stack spacing={0.3}>
                <Typography variant="caption">БИРЖА</Typography>
                <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box
                    component="span"
                    sx={{
                      width: 18,
                      height: 18,
                      bgcolor: '#000',
                      color: '#fff',
                      borderRadius: '50%',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 10,
                    }}
                  >
                    B
                  </Box>
                  {exchangeLabel(bot.exchange)}
                </Typography>
              </Stack>
              <Stack spacing={0.3}>
                <Typography variant="caption">ДЕПОЗИТ</Typography>
                <Typography variant="body2">{bot.depositUsd} USDT</Typography>
              </Stack>
              <Stack spacing={0.3}>
                <Typography variant="caption">ПЛЕЧО</Typography>
                <Typography variant="body2">x{bot.leverage}</Typography>
              </Stack>
            </Stack>
          </CardContent>
        </Box>
      </Box>
    </Card>
  );
};

export default BotCard;
