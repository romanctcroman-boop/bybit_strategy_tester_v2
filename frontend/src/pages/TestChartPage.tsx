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
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import StarBorderIcon from '@mui/icons-material/StarBorder';
import StarIcon from '@mui/icons-material/Star';
import SearchIcon from '@mui/icons-material/Search';
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import PhotoCameraOutlinedIcon from '@mui/icons-material/PhotoCameraOutlined';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import CandlestickChartIcon from '@mui/icons-material/CandlestickChart';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import SimpleChart, { type SimpleChartHandle } from '../components/SimpleChart';
import TradingViewChart from '../components/TradingViewChart';
import DrawToolbar from '../components/draw/DrawToolbar';
import DrawingLayer, { type DrawingLayerHandle } from '../components/draw/DrawingLayer';
import PeriodSelector, { type PeriodRange } from '../components/PeriodSelector';
import type { Tool } from '../components/draw/types';
import { useMarketDataStore } from '../store/marketData';
import { BYBIT_TOP_TICKERS, fetchTopBybitTickersByVolume } from '../services/topBybitTickers';
import { TIMEFRAMES, formatIntervalLabel } from '../constants/timeframes';

const TOP_BAR_HEIGHT = 44; // px
const FAVORITES_LS_KEY = 'bybit:favorites';

// Calculate default period (30 days back from today)
function getDefaultPeriod(): PeriodRange {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30); // 30 days ago

  return {
    startDate: start.toISOString().split('T')[0],
    endDate: end.toISOString().split('T')[0],
  };
}

const TestChartPage: React.FC = () => {
  const [updateTime, setUpdateTime] = useState<string>('');
  const [tfAnchor, setTfAnchor] = useState<HTMLElement | null>(null);
  const [tool, setTool] = useState<Tool>('select');
  const [hasSelection, setHasSelection] = useState<boolean>(false);
  const [magnet, setMagnet] = useState<boolean>(false);
  const [chartMode, setChartMode] = useState<'drawing' | 'trading'>('drawing'); // New: chart mode
  const [showTradeMarkers, setShowTradeMarkers] = useState<boolean>(true); // New: trade markers toggle
  const [selectedBacktestId, setSelectedBacktestId] = useState<number | null>(null); // New: backtest selection
  const [backtestTrades, setBacktestTrades] = useState<any[]>([]); // New: loaded trades
  const [loadingTrades, setLoadingTrades] = useState<boolean>(false); // New: loading state
  const [period, setPeriod] = useState<PeriodRange>(getDefaultPeriod()); // New: period filter
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
    clearCandleCache,
    saveCurrentState,
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
    clearCandleCache: s.clearCandleCache,
    saveCurrentState: s.saveCurrentState,
  }));
  const candles = mergedCandles;

  // Normalized OHLC for tools/overlays (seconds-based time)
  const normOHLC = useMemo(() => {
    const normalized = candles
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

    // Filter by period (only in trading mode for backtesting)
    if (chartMode === 'trading' && period) {
      const startTimeSec = new Date(period.startDate).getTime() / 1000;
      const endTimeSec = new Date(period.endDate).getTime() / 1000 + 86400; // +1 day to include end date

      return normalized.filter((d) => d.time >= startTimeSec && d.time <= endTimeSec);
    }

    return normalized;
  }, [candles, chartMode, period]);

  // Demo trade markers for testing (TODO: replace with API data)
  const demoTradeMarkers = useMemo(() => {
    if (!normOHLC.length || !showTradeMarkers) return [];

    // Create sample trades based on chart data
    const markers = [];
    const dataLength = normOHLC.length;

    if (dataLength > 50) {
      // Trade 1: BUY at index 10, EXIT at index 30
      const buyIdx1 = Math.floor(dataLength * 0.1);
      const exitIdx1 = Math.floor(dataLength * 0.3);
      const buyPrice1 = normOHLC[buyIdx1].low * 1.001;
      const exitPrice1 = normOHLC[exitIdx1].high * 0.999;
      const pnl1 = ((exitPrice1 - buyPrice1) / buyPrice1) * 100;

      markers.push({
        time: normOHLC[buyIdx1].time,
        side: 'buy' as const,
        price: buyPrice1,
        tp_price: buyPrice1 * 1.02,
        sl_price: buyPrice1 * 0.99,
        exit_price: exitPrice1,
        exit_time: normOHLC[exitIdx1].time,
        pnl_percent: pnl1,
        is_entry: true,
      });

      // Trade 2: SELL at index 50, EXIT at index 70
      const sellIdx2 = Math.floor(dataLength * 0.5);
      const exitIdx2 = Math.floor(dataLength * 0.7);
      const sellPrice2 = normOHLC[sellIdx2].high * 0.999;
      const exitPrice2 = normOHLC[exitIdx2].low * 1.001;
      const pnl2 = ((sellPrice2 - exitPrice2) / sellPrice2) * 100;

      markers.push({
        time: normOHLC[sellIdx2].time,
        side: 'sell' as const,
        price: sellPrice2,
        tp_price: sellPrice2 * 0.98,
        sl_price: sellPrice2 * 1.01,
        exit_price: exitPrice2,
        exit_time: normOHLC[exitIdx2].time,
        pnl_percent: pnl2,
        is_entry: true,
      });
    }

    return markers;
  }, [normOHLC, showTradeMarkers]);

  // Load trades from API when backtest is selected
  useEffect(() => {
    if (!selectedBacktestId || !showTradeMarkers || chartMode !== 'trading') {
      setBacktestTrades([]);
      return;
    }

    let active = true;
    (async () => {
      try {
        setLoadingTrades(true);
        // Import BacktestsApi
        const { BacktestsApi } = await import('../services/api');
        const { items } = await BacktestsApi.trades(selectedBacktestId, { limit: 1000 });
        if (active) {
          setBacktestTrades(items || []);
        }
      } catch (err) {
        console.error('Failed to load backtest trades:', err);
        if (active) setBacktestTrades([]);
      } finally {
        if (active) setLoadingTrades(false);
      }
    })();

    return () => {
      active = false;
    };
  }, [selectedBacktestId, showTradeMarkers, chartMode]);

  // Transform API trades into chart markers
  const apiTradeMarkers = useMemo(() => {
    if (!backtestTrades.length) return [];

    return backtestTrades.map((trade) => {
      const entryTime =
        trade.entry_time instanceof Date
          ? Math.floor(trade.entry_time.getTime() / 1000)
          : Math.floor(new Date(trade.entry_time).getTime() / 1000);

      const exitTime = trade.exit_time
        ? trade.exit_time instanceof Date
          ? Math.floor(trade.exit_time.getTime() / 1000)
          : Math.floor(new Date(trade.exit_time).getTime() / 1000)
        : undefined;

      const entryPrice = trade.price || trade.entry_price;
      const exitPrice = trade.exit_price;
      const side = trade.side === 'buy' || trade.side === 'LONG' ? 'buy' : 'sell';

      // Calculate TP/SL levels (example: 2% profit, 1% loss)
      const tpPrice = side === 'buy' ? entryPrice * 1.02 : entryPrice * 0.98;
      const slPrice = side === 'buy' ? entryPrice * 0.99 : entryPrice * 1.01;

      return {
        time: entryTime,
        side: side as 'buy' | 'sell',
        price: entryPrice,
        tp_price: tpPrice,
        sl_price: slPrice,
        exit_price: exitPrice,
        exit_time: exitTime,
        pnl_percent: trade.pnl_pct || trade.pnl_percent,
        is_entry: true,
      };
    });
  }, [backtestTrades]);

  // Use API markers if available, otherwise demo markers
  const tradeMarkers =
    selectedBacktestId && apiTradeMarkers.length > 0 ? apiTradeMarkers : demoTradeMarkers;

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
    <Container maxWidth={false} sx={{ pl: 1, pr: 1, maxWidth: '98vw' }}>
      <Typography variant="h4" sx={{ mt: 2, mb: 1 }}>
        📊 Live {currentSymbol} Chart
      </Typography>
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 1, flexWrap: 'wrap' }}>
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
                    {TIMEFRAMES.map((tf) => (
                      <MenuItem
                        key={tf.value}
                        selected={tf.value === currentInterval}
                        onClick={async () => {
                          setTfAnchor(null);
                          await switchInterval(tf.value, 1000);
                          setUpdateTime(new Date().toLocaleTimeString());
                        }}
                      >
                        {tf.label}
                      </MenuItem>
                    ))}
                  </Menu>

                  {/* Chart Mode Switcher */}
                  <Box sx={{ ml: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <ToggleButtonGroup
                      size="small"
                      exclusive
                      value={chartMode}
                      onChange={(_, val) => {
                        if (val) setChartMode(val);
                      }}
                      sx={{
                        '& .MuiToggleButton-root': {
                          color: '#fff',
                          borderColor: 'rgba(255,255,255,0.2)',
                          px: 1.5,
                          py: 0.5,
                        },
                      }}
                    >
                      <ToggleButton value="drawing">
                        <ShowChartIcon fontSize="small" sx={{ mr: 0.5 }} />
                        Drawing
                      </ToggleButton>
                      <ToggleButton value="trading">
                        <CandlestickChartIcon fontSize="small" sx={{ mr: 0.5 }} />
                        Trading
                      </ToggleButton>
                    </ToggleButtonGroup>

                    {/* Show Trade Markers checkbox - only visible in trading mode */}
                    {chartMode === 'trading' && (
                      <>
                        <FormControlLabel
                          control={
                            <Checkbox
                              checked={showTradeMarkers}
                              onChange={(e) => setShowTradeMarkers(e.target.checked)}
                              size="small"
                              sx={{
                                color: 'rgba(255,255,255,0.7)',
                                '&.Mui-checked': { color: '#4caf50' },
                              }}
                            />
                          }
                          label={
                            <Typography variant="body2" sx={{ color: '#fff' }}>
                              Show Trades
                            </Typography>
                          }
                          sx={{ ml: 1 }}
                        />

                        {/* Backtest ID input */}
                        <TextField
                          size="small"
                          type="number"
                          placeholder="Backtest ID"
                          value={selectedBacktestId || ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            setSelectedBacktestId(val ? parseInt(val, 10) : null);
                          }}
                          sx={{
                            ml: 1,
                            width: 120,
                            '& .MuiInputBase-input': {
                              color: '#fff',
                              py: 0.75,
                            },
                            '& .MuiOutlinedInput-notchedOutline': {
                              borderColor: 'rgba(255,255,255,0.2)',
                            },
                            '&:hover .MuiOutlinedInput-notchedOutline': {
                              borderColor: 'rgba(255,255,255,0.3)',
                            },
                          }}
                          InputProps={{
                            endAdornment: loadingTrades && (
                              <CircularProgress size={16} sx={{ color: '#fff' }} />
                            ),
                          }}
                        />

                        {/* Period Selector for Backtest */}
                        <Box sx={{ ml: 2, minWidth: 280 }}>
                          <PeriodSelector
                            value={period}
                            onChange={(newPeriod) => {
                              setPeriod(newPeriod);
                              console.log('📅 Period changed:', newPeriod);
                              // TODO: Reload data with new period
                            }}
                            label=""
                          />
                        </Box>
                      </>
                    )}
                  </Box>

                  {/* Clear Cache Button */}
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => {
                      if (
                        window.confirm(
                          `Очистить кэш для ${currentSymbol} ${formatIntervalLabel(currentInterval)}?`
                        )
                      ) {
                        clearCandleCache();
                        // Reload data
                        initialize(currentSymbol, currentInterval);
                      }
                    }}
                    startIcon={<DeleteSweepIcon fontSize="small" />}
                    sx={{
                      ml: 2,
                      color: '#fff',
                      borderColor: 'rgba(255,255,255,0.2)',
                      '&:hover': {
                        borderColor: 'rgba(255,100,100,0.5)',
                        backgroundColor: 'rgba(255,100,100,0.1)',
                      },
                    }}
                  >
                    Clear Cache
                  </Button>

                  {/* Exit Button - Graceful Shutdown */}
                  <Button
                    size="small"
                    variant="contained"
                    color="error"
                    onClick={async () => {
                      if (window.confirm('Сохранить данные перед закрытием?')) {
                        try {
                          // Save current state
                          await saveCurrentState();

                          // Clear message with instructions
                          const message =
                            '✅ Данные сохранены успешно!\n\n' +
                            '📌 Для выхода из приложения:\n' +
                            '   • Закройте вкладку браузера (Ctrl+W)\n' +
                            '   • Или остановите сервер в PowerShell (Ctrl+C)';

                          alert(message);

                          // Try to close the tab (only works if window was opened by script)
                          window.close();

                          // If close() didn't work, user sees the message and can close manually
                        } catch (err) {
                          console.error('Error during shutdown:', err);
                          alert('❌ Ошибка при сохранении данных');
                        }
                      }
                    }}
                    startIcon={<ExitToAppIcon fontSize="small" />}
                    sx={{
                      ml: 2,
                    }}
                  >
                    Выход
                  </Button>

                  <PhotoCameraOutlinedIcon fontSize="small" />
                </Box>
              </Box>

              {/* Main area: left tools rail + chart */}
              <Box
                sx={{ display: 'flex', height: `calc(90vh - ${TOP_BAR_HEIGHT}px)`, minHeight: 500 }}
              >
                {/* Drawing Toolbar - only visible in drawing mode */}
                {chartMode === 'drawing' && (
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
                )}

                <Box sx={{ position: 'relative', flex: 1 }}>
                  {chartMode === 'drawing' ? (
                    <>
                      {/* Drawing Chart with overlay */}
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
                    </>
                  ) : (
                    /* Trading View Chart with trade markers */
                    <TradingViewChart
                      candles={normOHLC.map((c) => ({
                        time: c.time,
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close,
                        volume: c.volume,
                      }))}
                      markers={tradeMarkers}
                      showVolume={true}
                      showTPSL={showTradeMarkers}
                      chartType="candlestick"
                      wheelZoom={true}
                      dragScroll={true}
                      showMarkerTooltips={true}
                      showExitMarkers={true}
                    />
                  )}
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
