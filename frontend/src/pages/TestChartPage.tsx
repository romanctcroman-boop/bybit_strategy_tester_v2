import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  Container,
  Menu,
  MenuItem,
  Typography,
  Button,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import StarBorderIcon from '@mui/icons-material/StarBorder';
import StarIcon from '@mui/icons-material/Star';
import SearchIcon from '@mui/icons-material/Search';
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import PhotoCameraOutlinedIcon from '@mui/icons-material/PhotoCameraOutlined';
import SimpleChart, { type SimpleChartHandle } from '../components/SimpleChart';
import DrawToolbar from '../components/draw/DrawToolbar';
import DrawingLayer, { type DrawingLayerHandle } from '../components/draw/DrawingLayer';
import type { Tool } from '../components/draw/types';
import { useMarketDataStore } from '../store/marketData';
import { BYBIT_TOP_TICKERS, fetchTopBybitTickersByVolume } from '../services/topBybitTickers';

const TOP_BAR_HEIGHT = 44; // px

// Helpers and options
function formatIntervalLabel(iv: string): string {
  const u = String(iv).toUpperCase();
  if (u === 'D') return '1d';
  if (u === 'W') return '1w';
  const n = parseInt(u, 10);
  if (isNaN(n)) return u;
  if (n % 60 === 0) return `${n / 60}h`;
  if (n >= 1440) return `${Math.round(n / 1440)}d`;
  return `${n}m`;
}

const timeframeOptions: Array<{ value: string; label: string }> = [
  { value: '1', label: '1m' },
  { value: '5', label: '5m' },
  { value: '15', label: '15m' },
  { value: '30', label: '30m' },
  { value: '60', label: '1h' },
  { value: '240', label: '4h' },
  { value: 'D', label: '1d' },
];

const FAVORITES_LS_KEY = 'bybit:favorites';

const TestChartPage: React.FC = () => {
  const [updateTime, setUpdateTime] = useState<string>('');
  const [tfAnchor, setTfAnchor] = useState<HTMLElement | null>(null);
  const [tool, setTool] = useState<Tool>('select');
  const [hasSelection, setHasSelection] = useState<boolean>(false);
  const [magnet, setMagnet] = useState<boolean>(false);
  const chartRef = React.useRef<SimpleChartHandle>(null);
  const drawRef = React.useRef<DrawingLayerHandle>(null);
  const {
    currentSymbol,
    currentInterval,
    currentCategory,
    loading,
    error,
    initialize,
    switchInterval,
    mergedCandles,
    setCategory,
  } = useMarketDataStore((s) => ({
    currentSymbol: s.currentSymbol,
    currentInterval: s.currentInterval,
    currentCategory: s.currentCategory,
    loading: s.loading,
    error: s.error,
    initialize: s.initialize,
    switchInterval: s.switchInterval,
    mergedCandles: s.getMergedCandles(),
    setCategory: s.setCategory,
  }));
  const candles = mergedCandles;
  // Normalized OHLC for tools/overlays (seconds-based time)
  const normOHLC = useMemo(() => {
    return candles
      .map((c) => ({
        time:
          typeof (c as any).time === 'number'
            ? (c as any).time < 1e11
              ? (c as any).time
              : Math.floor((c as any).time / 1000)
            : Math.floor(Number((c as any).open_time || 0) / 1000),
        open: Number((c as any).open),
        high: Number((c as any).high),
        low: Number((c as any).low),
        close: Number((c as any).close),
        volume: (c as any).volume != null ? Number((c as any).volume) : 0,
      }))
      .filter((d) => Number.isFinite(d.time) && Number.isFinite(d.close))
      .sort((a, b) => a.time - b.time);
  }, [candles]);
  const [favorites, setFavorites] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(FAVORITES_LS_KEY);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      return Array.isArray(arr) ? (arr as string[]) : [];
    } catch {
      return [];
    }
  });

  // Market category is managed in the store: 'linear' (Futures) | 'spot' (Spot)

  const setFavorite = (sym: string, on: boolean) => {
    const up = sym.toUpperCase();
    setFavorites((prev) => {
      const next = on ? Array.from(new Set([up, ...prev])) : prev.filter((s) => s !== up);
      try {
        localStorage.setItem(FAVORITES_LS_KEY, JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  const isFavorite = (sym: string) => favorites.includes(sym.toUpperCase());

  type TickerOption = { symbol: string; label: string; group: 'Избранное' | 'Топ Bybit' };
  const [allTickers, setAllTickers] = useState<string[]>(() => BYBIT_TOP_TICKERS);
  // Load dynamic Top 100 by volume per selected category with fallback
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const top = await fetchTopBybitTickersByVolume({
          category: currentCategory,
          limit: 100,
          quote: 'USDT',
        });
        if (active && Array.isArray(top) && top.length) setAllTickers(top);
      } catch {}
    })();
    return () => {
      active = false;
    };
  }, [currentCategory]);
  const options: TickerOption[] = useMemo(() => {
    const favSet = new Set(favorites.map((s) => s.toUpperCase()));
    const list = allTickers.map<TickerOption>((s) => ({
      symbol: s.toUpperCase(),
      label: currentCategory === 'linear' ? `${s.toUpperCase()}.P` : s.toUpperCase(),
      group: favSet.has(s.toUpperCase()) ? 'Избранное' : 'Топ Bybit',
    }));
    // Ensure currentSymbol is present even if not in top list
    const cur = currentSymbol.toUpperCase();
    if (!list.some((o) => o.symbol === cur)) {
      list.unshift({
        symbol: cur,
        label: currentCategory === 'linear' ? `${cur}.P` : cur,
        group: favSet.has(cur) ? 'Избранное' : 'Топ Bybit',
      });
    }
    // Sort: Favorites first (by trading volume from API), then Top Bybit (preserve API volume order)
    const favs = list.filter((o) => o.group === 'Избранное');
    const top = list.filter((o) => o.group === 'Топ Bybit');
    return [...favs, ...top];
  }, [allTickers, favorites, currentSymbol, currentCategory]);

  const changeSymbol = async (symRaw: string) => {
    const sym = symRaw.trim().toUpperCase();
    if (!sym) return;
    await initialize(sym, currentInterval);
    setUpdateTime(new Date().toLocaleTimeString());
  };

  // Initial load: 15m BTCUSDT
  useEffect(() => {
    (async () => {
      await initialize('BTCUSDT', '15');
      setUpdateTime(new Date().toLocaleTimeString());
    })();
  }, [initialize]);

  // Keyboard shortcuts for tools and delete
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const tag = (target?.tagName || '').toLowerCase();
      const isEditable =
        tag === 'input' || tag === 'textarea' || (target as any)?.isContentEditable;
      if (isEditable) return;
      const key = e.key.toLowerCase();
      if (key === 'escape' || key === 's') return setTool('select');
      if (key === 't') return setTool('trendline');
      if (key === 'r') return setTool('ray');
      if (key === 'h') return setTool('hline');
      if (key === 'y') return setTool('hray');
      if (key === 'v') return setTool('vline');
      if (key === 'f') return setTool('fib');
      if ((e.key === 'Delete' || e.key === 'Backspace') && hasSelection) {
        drawRef.current?.deleteSelected();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [hasSelection]);

  return (
    <Container maxWidth="lg">
      <Typography variant="h4" sx={{ mt: 3, mb: 2 }}>
        📊 Live {currentSymbol} Chart
      </Typography>
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
        <Typography variant="body2" color="textSecondary">
          Свечей: <strong>{candles.length}</strong>
        </Typography>
        <Typography variant="body2" color="textSecondary">
          Последнее обновление: {updateTime}
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 600 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Paper sx={{ mt: 2, p: 0 }}>
          {candles.length > 0 ? (
            <Box sx={{ width: '100%', height: '70vh', minHeight: 360 }}>
              {/* Top bar full width of chart window */}
              <Box
                sx={{
                  height: TOP_BAR_HEIGHT,
                  px: 1.5,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1,
                  color: '#fff',
                  bgcolor: 'rgba(17,24,39,0.95)',
                  borderBottom: '1px solid rgba(255,255,255,0.08)',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {/* Favorite star toggle */}
                  <Box
                    sx={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      color: '#fff',
                      cursor: 'pointer',
                    }}
                    onClick={() => setFavorite(currentSymbol, !isFavorite(currentSymbol))}
                    title={
                      isFavorite(currentSymbol) ? 'Убрать из избранного' : 'Добавить в избранное'
                    }
                  >
                    {isFavorite(currentSymbol) ? (
                      <StarIcon fontSize="small" />
                    ) : (
                      <StarBorderIcon fontSize="small" />
                    )}
                  </Box>

                  {/* Ticker selector with free input and favorites grouping */}
                  <Autocomplete
                    disableClearable
                    freeSolo
                    options={options}
                    groupBy={(o) => o.group}
                    getOptionLabel={(o) => (typeof o === 'string' ? o : o.label)}
                    renderOption={(props, option) => (
                      <li {...props} key={option.symbol}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {favorites.includes(option.symbol) ? (
                            <StarIcon fontSize="small" sx={{ color: '#fbbf24' }} />
                          ) : (
                            <StarBorderIcon fontSize="small" sx={{ opacity: 0.6 }} />
                          )}
                          <Typography variant="body2">{option.label}</Typography>
                        </Box>
                      </li>
                    )}
                    value={currentSymbol}
                    onChange={(_, value) => {
                      const sym =
                        typeof value === 'string' ? value : (value as TickerOption).symbol;
                      changeSymbol(sym);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        const input = (e.target as HTMLInputElement)?.value || '';
                        if (input) changeSymbol(input);
                      }
                    }}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        size="small"
                        variant="outlined"
                        placeholder="Введите тикер (например BTCUSDT или BTCUSDT.P)"
                        InputProps={{
                          ...params.InputProps,
                          startAdornment: <SearchIcon fontSize="small" sx={{ mr: 0.5 }} />,
                          sx: {
                            color: '#fff',
                            '.MuiOutlinedInput-notchedOutline': {
                              borderColor: 'rgba(255,255,255,0.2)',
                            },
                            '&:hover .MuiOutlinedInput-notchedOutline': {
                              borderColor: 'rgba(255,255,255,0.3)',
                            },
                          },
                        }}
                        sx={{ minWidth: 260 }}
                      />
                    )}
                    sx={{
                      minWidth: 260,
                      '& .MuiInputBase-input': { color: '#fff' },
                      '& .MuiSvgIcon-root': { color: '#fff' },
                    }}
                  />

                  <Typography variant="body2" sx={{ color: '#fff', opacity: 0.8 }}>
                    • Bybit {currentCategory === 'linear' ? 'Futures' : 'Spot'}
                  </Typography>
                  {/* Category switcher */}
                  <ToggleButtonGroup
                    size="small"
                    exclusive
                    value={currentCategory}
                    onChange={(_, val) => {
                      if (val) setCategory(val);
                    }}
                    sx={{
                      ml: 1,
                      '& .MuiToggleButton-root': {
                        color: '#fff',
                        borderColor: 'rgba(255,255,255,0.2)',
                      },
                    }}
                  >
                    <ToggleButton value="linear">Futures</ToggleButton>
                    <ToggleButton value="spot">Spot</ToggleButton>
                  </ToggleButtonGroup>
                  <Box sx={{ ml: 1 }} />
                  {/* Timeframe current value with dropdown */}
                  <Button
                    size="small"
                    onClick={(e) => setTfAnchor(e.currentTarget)}
                    sx={{ color: '#fff', borderColor: 'rgba(255,255,255,0.2)' }}
                    variant="outlined"
                  >
                    {formatIntervalLabel(currentInterval)}
                  </Button>
                  <Menu
                    anchorEl={tfAnchor}
                    open={Boolean(tfAnchor)}
                    onClose={() => setTfAnchor(null)}
                  >
                    {timeframeOptions.map((opt) => (
                      <MenuItem
                        key={opt.value}
                        selected={opt.value === currentInterval}
                        onClick={async () => {
                          setTfAnchor(null);
                          await switchInterval(opt.value, 1000);
                          setUpdateTime(new Date().toLocaleTimeString());
                        }}
                      >
                        {opt.label}
                      </MenuItem>
                    ))}
                  </Menu>

                  <PhotoCameraOutlinedIcon fontSize="small" />
                </Box>
              </Box>

              {/* Main area: left tools rail + chart */}
              <Box
                sx={{ display: 'flex', height: `calc(70vh - ${TOP_BAR_HEIGHT}px)`, minHeight: 316 }}
              >
                <DrawToolbar
                  variant="sidebar"
                  tool={tool}
                  onChange={setTool}
                  onUndo={() => drawRef.current?.undo()}
                  onClear={() => drawRef.current?.clear()}
                  onDelete={() => drawRef.current?.deleteSelected()}
                  selected={hasSelection}
                  magnetEnabled={magnet}
                  onToggleMagnet={() => setMagnet((v) => !v)}
                />
                <Box sx={{ position: 'relative', flex: 1 }}>
                  <DrawingLayer
                    chartRef={chartRef}
                    activeTool={tool}
                    ref={drawRef}
                    storageKey={`draw:${currentSymbol}:${currentInterval}:${currentCategory}`}
                    onSelectionChange={setHasSelection}
                    interval={currentInterval}
                    magnet={magnet}
                    ohlc={normOHLC}
                  />
                  <SimpleChart
                    ref={chartRef}
                    candles={candles}
                    datasetKey={`${currentSymbol}:${currentInterval}`}
                    interval={currentInterval}
                  />
                </Box>
              </Box>
            </Box>
          ) : (
            <Alert severity="info">No candles available</Alert>
          )}
        </Paper>
      )}
    </Container>
  );
};

export default TestChartPage;
