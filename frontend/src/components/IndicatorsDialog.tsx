import React, { useMemo, useState } from 'react';
import {
  Box,
  Checkbox,
  Dialog,
  DialogTitle,
  IconButton,
  InputAdornment,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import SearchIcon from '@mui/icons-material/Search';

export type IndicatorsDialogProps = {
  open: boolean;
  onClose: () => void;
  // Supported toggles today
  showSMA20: boolean;
  setShowSMA20: (v: boolean) => void;
  showEMA50: boolean;
  setShowEMA50: (v: boolean) => void;
  showBB: boolean;
  setShowBB: (v: boolean) => void;
  showRSI: boolean;
  setShowRSI: (v: boolean) => void;
  showMACD: boolean;
  setShowMACD: (v: boolean) => void;
  showVWAP: boolean;
  setShowVWAP: (v: boolean) => void;
  showSuperTrend: boolean;
  setShowSuperTrend: (v: boolean) => void;
  showDonchian: boolean;
  setShowDonchian: (v: boolean) => void;
  showKeltner: boolean;
  setShowKeltner: (v: boolean) => void;
};

// Catalog of indicators (RU labels similar to TradingView), mark which are already supported
type IndicatorItem = {
  id: string;
  label: string;
  supported?: boolean;
  bind?: 'SMA20' | 'EMA50' | 'BB20_2' | 'RSI' | 'MACD' | 'VWAP' | 'SUPER' | 'DONCHIAN' | 'KELTNER';
  type: 'overlay' | 'oscillator' | 'volume' | 'other';
};

const ALL_INDICATORS: IndicatorItem[] = [
  // Supported
  {
    id: 'sma20',
    label: 'Скользящее среднее (SMA20)',
    supported: true,
    bind: 'SMA20',
    type: 'overlay',
  },
  {
    id: 'ema50',
    label: 'Экспоненциальное скользящее (EMA50)',
    supported: true,
    bind: 'EMA50',
    type: 'overlay',
  },
  {
    id: 'bb',
    label: 'Полосы Боллинджера (20, 2)',
    supported: true,
    bind: 'BB20_2',
    type: 'overlay',
  },
  // Newly supported
  { id: 'vwap', label: 'VWAP', supported: true, bind: 'VWAP', type: 'overlay' },
  {
    id: 'rsi',
    label: 'Индекс относительной силы (RSI)',
    supported: true,
    bind: 'RSI',
    type: 'oscillator',
  },
  { id: 'macd', label: 'MACD', supported: true, bind: 'MACD', type: 'oscillator' },
  { id: 'atr', label: 'Средний истинный диапазон (ATR)', type: 'other' },
  { id: 'supertrend', label: 'SuperTrend', supported: true, bind: 'SUPER', type: 'overlay' },
  { id: 'keltner', label: 'Канал Кельтнера', supported: true, bind: 'KELTNER', type: 'overlay' },
  { id: 'donchian', label: 'Канал Дончиана', supported: true, bind: 'DONCHIAN', type: 'overlay' },
  { id: 'ichimoku', label: 'Облако Ишимоку', type: 'overlay' },
  { id: 'stoch', label: 'Стохастический осциллятор', type: 'oscillator' },
  { id: 'cci', label: 'Индекс товарного канала (CCI)', type: 'oscillator' },
  { id: 'aroon', label: 'Арун (Aroon)', type: 'oscillator' },
  { id: 'adx', label: 'Индекс среднего направленного движения (ADX)', type: 'oscillator' },
  { id: 'vortex', label: 'Индикатор Vortex', type: 'oscillator' },
  { id: 'mfi', label: 'Индекс денежного потока (MFI)', type: 'oscillator' },
  { id: 'williamsr', label: 'Процентный диапазон Вильямса (%R)', type: 'oscillator' },
  { id: 'roc', label: 'Скорость изменения цены (ROC)', type: 'oscillator' },
  { id: 'trix', label: 'TRIX', type: 'oscillator' },
  { id: 'obv', label: 'Объём по балансу (OBV)', type: 'volume' },
  { id: 'chaikin_money_flow', label: 'Денежный поток Чайкина', type: 'volume' },
  { id: 'chaikin_osc', label: 'Осциллятор Чайкина', type: 'volume' },
  { id: 'vwap_visible', label: 'Volume Profile Visible Range', type: 'other' },
  { id: 'vwap_fixed', label: 'Volume Profile Fixed Range', type: 'other' },
  { id: 'stddev', label: 'Стандартное отклонение', type: 'other' },
  { id: 'zigzag', label: 'ЗигЗаг', type: 'other' },
  { id: 'linreg', label: 'Кривая линейной регрессии', type: 'overlay' },
  { id: 'envelopes', label: 'Конверты', type: 'overlay' },
  { id: 'dema', label: 'Скользящее среднее (двойное эксп.)', type: 'overlay' },
  { id: 'tema', label: 'Скользящее среднее (тройное эксп.)', type: 'overlay' },
  { id: 'hma', label: 'Скользящее среднее Халла (HMA)', type: 'overlay' },
  { id: 'wma', label: 'Скользящее среднее взвешенное (WMA)', type: 'overlay' },
  { id: 'ema', label: 'Скользящее среднее экспоненциальное (EMA)', type: 'overlay' },
  { id: 'sma', label: 'Скользящее среднее (SMA)', type: 'overlay' },
];

export default function IndicatorsDialog(props: IndicatorsDialogProps) {
  const {
    open,
    onClose,
    showSMA20,
    setShowSMA20,
    showEMA50,
    setShowEMA50,
    showBB,
    setShowBB,
    showRSI,
    setShowRSI,
    showMACD,
    setShowMACD,
    showVWAP,
    setShowVWAP,
    showSuperTrend,
    setShowSuperTrend,
    showDonchian,
    setShowDonchian,
    showKeltner,
    setShowKeltner,
  } = props;
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ALL_INDICATORS;
    return ALL_INDICATORS.filter((i) => i.label.toLowerCase().includes(q));
  }, [query]);

  const handleToggle = (item: IndicatorItem) => {
    if (!item.supported) return;
    if (item.bind === 'SMA20') setShowSMA20(!showSMA20);
    else if (item.bind === 'EMA50') setShowEMA50(!showEMA50);
    else if (item.bind === 'BB20_2') setShowBB(!showBB);
    else if (item.bind === 'RSI') setShowRSI(!showRSI);
    else if (item.bind === 'MACD') setShowMACD(!showMACD);
    else if (item.bind === 'VWAP') setShowVWAP(!showVWAP);
    else if (item.bind === 'SUPER') setShowSuperTrend(!showSuperTrend);
    else if (item.bind === 'DONCHIAN') setShowDonchian(!showDonchian);
    else if (item.bind === 'KELTNER') setShowKeltner(!showKeltner);
  };

  const isChecked = (item: IndicatorItem) => {
    if (!item.supported) return false;
    if (item.bind === 'SMA20') return showSMA20;
    if (item.bind === 'EMA50') return showEMA50;
    if (item.bind === 'BB20_2') return showBB;
    if (item.bind === 'RSI') return showRSI;
    if (item.bind === 'MACD') return showMACD;
    if (item.bind === 'VWAP') return showVWAP;
    if (item.bind === 'SUPER') return showSuperTrend;
    if (item.bind === 'DONCHIAN') return showDonchian;
    if (item.bind === 'KELTNER') return showKeltner;
    return false;
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h6">Индикаторы</Typography>
        <IconButton size="small" onClick={onClose} aria-label="close">
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <Box sx={{ px: 2, pb: 2 }}>
        <TextField
          fullWidth
          size="small"
          placeholder="Поиск"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
          sx={{ mb: 1.5 }}
        />
        <List dense sx={{ maxHeight: 420, overflowY: 'auto' }}>
          {filtered.map((item) => (
            <ListItem key={item.id} disablePadding secondaryAction={null}>
              <Tooltip
                title={item.supported ? '' : 'Пока недоступно в этой версии (можно добавить позже)'}
              >
                <span style={{ width: '100%' }}>
                  <ListItemButton onClick={() => handleToggle(item)} disabled={!item.supported}>
                    <ListItemIcon>
                      <Checkbox
                        edge="start"
                        checked={isChecked(item)}
                        tabIndex={-1}
                        disableRipple
                        color="primary"
                      />
                    </ListItemIcon>
                    <ListItemText
                      primary={item.label}
                      secondary={
                        item.supported ? undefined : (
                          <Typography variant="caption" color="text.secondary">
                            Недоступно
                          </Typography>
                        )
                      }
                    />
                  </ListItemButton>
                </span>
              </Tooltip>
            </ListItem>
          ))}
        </List>
      </Box>
    </Dialog>
  );
}
