import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Container,
  FormControlLabel,
  LinearProgress,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useTheme,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import ChartsTab from '../components/ChartsTab';
import TradingViewTab from '../components/TradingViewTab';
import MonteCarloTab from '../components/MonteCarloTab';
import AIAnalysisPanel from '../components/AIAnalysisPanel';

// ✅ Import centralized formatting utilities (Quick Win #3)
import {
  formatValueWithUnit,
  formatSignedValueWithUnit,
  formatDateTime,
  formatDuration,
  formatQuantity,
  toFiniteNumber,
  toTimestamp,
  type ValueUnit,
} from '../utils/formatting';
import AdvancedTradeFilters, { TradeFilters } from '../components/AdvancedTradeFilters';
// TODO: Integrate EnhancedMetricsTable in Analysis/Dynamics tabs
// import EnhancedMetricsTable, { MetricGroup } from '../components/EnhancedMetricsTable';
import PlotlyEquityCurve from '../components/PlotlyEquityCurve';
import { useNotify } from '../components/NotificationsProvider';
import { BacktestsApi } from '../services/api';
import type { Backtest, Trade } from '../types/api';

type ChartMode = 'abs' | 'pct';

type ChartDatum = {
  timestamp: number;
  label: string;
  equityAbs?: number;
  equityPct?: number;
  pnlAbs?: number;
  pnlPct?: number;
  buyHoldAbs?: number;
  buyHoldPct?: number;
};

type BacktestResults = {
  overview?: {
    net_pnl?: number;
    net_pct?: number;
    total_trades?: number;
    wins?: number;
    losses?: number;
    max_drawdown_abs?: number;
    max_drawdown_pct?: number;
    profit_factor?: number;
  };
  by_side?: Record<
    'all' | 'long' | 'short',
    {
      total_trades?: number;
      open_trades?: number;
      wins?: number;
      losses?: number;
      win_rate?: number;
      avg_pl?: number;
      avg_pl_pct?: number;
      avg_win?: number;
      avg_win_pct?: number;
      avg_loss?: number;
      avg_loss_pct?: number;
      max_win?: number;
      max_win_pct?: number;
      max_loss?: number;
      max_loss_pct?: number;
      profit_factor?: number;
      avg_bars?: number;
      avg_bars_win?: number;
      avg_bars_loss?: number;
    }
  >;
  dynamics?: Record<
    'all' | 'long' | 'short',
    {
      unrealized_abs?: number;
      unrealized_pct?: number;
      net_abs?: number;
      net_pct?: number;
      gross_profit_abs?: number;
      gross_profit_pct?: number;
      gross_loss_abs?: number;
      gross_loss_pct?: number;
      fees_abs?: number;
      fees_pct?: number;
      max_runup_abs?: number;
      max_runup_pct?: number;
      max_drawdown_abs?: number;
      max_drawdown_pct?: number;
      buyhold_abs?: number;
      buyhold_pct?: number;
      max_contracts?: number;
    }
  >;
  risk?: {
    sharpe?: number;
    sortino?: number;
    profit_factor?: number;
  };
  equity?: Array<{ time?: string | number | Date; equity?: number }>;
  pnl_bars?: Array<{ time?: string | number | Date; pnl?: number }>;
};

type SideKey = 'all' | 'long' | 'short';
type SideStats = NonNullable<BacktestResults['by_side']>[SideKey];
type DynamicsStats = NonNullable<BacktestResults['dynamics']>[SideKey];

type EnrichedTrade = Trade & {
  cumulative?: number;
};

const TRADE_PAGE_SIZE = 100;

// ✅ All formatting functions now imported from ../utils/formatting

const DualValue: React.FC<{
  absolute?: unknown;
  percent?: unknown;
}> = ({ absolute, percent }) => {
  const absoluteText = formatValueWithUnit(absolute, 'usd');
  const percentText = percent != null ? formatValueWithUnit(percent, 'percent', 2) : null;
  if (!percentText) return <>{absoluteText}</>;
  return (
    <Stack spacing={0.5} alignItems="center">
      <span>{absoluteText}</span>
      <Typography variant="caption" color="text.secondary">
        {percentText}
      </Typography>
    </Stack>
  );
};

const OverviewChart: React.FC<{
  data: ChartDatum[];
  mode: ChartMode;
  onModeChange: (value: ChartMode) => void;
  showPnlBars: boolean;
  onTogglePnlBars: (checked: boolean) => void;
  showBuyHold: boolean;
  onToggleBuyHold: (checked: boolean) => void;
}> = ({ data, mode, onModeChange, showPnlBars, onTogglePnlBars, showBuyHold, onToggleBuyHold }) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const axisColor = isDark ? 'rgba(226, 232, 240, 0.82)' : 'rgba(30, 41, 59, 0.78)';

  const handleModeChange = (_: React.MouseEvent<HTMLElement>, value: ChartMode | null) => {
    if (value) onModeChange(value);
  };

  return (
    <Paper
      sx={{
        p: 3,
        mt: 3,
        borderRadius: 3,
        background: isDark
          ? 'linear-gradient(160deg, rgba(2,8,23,0.9) 0%, rgba(8,15,23,0.92) 100%)'
          : '#ffffff',
        border: isDark ? '1px solid rgba(148, 163, 184, 0.18)' : '1px solid rgba(15, 23, 42, 0.08)',
        boxShadow: isDark
          ? '0 18px 60px rgba(8, 15, 23, 0.45)'
          : '0 20px 45px rgba(15, 23, 42, 0.12)',
      }}
    >
      <Typography variant="h6">Капитал и динамика сделок</Typography>

      {data.length === 0 ? (
        <Box sx={{ py: 6 }}>
          <Typography align="center" color="text.secondary">
            Нет данных для визуализации.
          </Typography>
        </Box>
      ) : (
        <>
          <Box
            sx={{
              mt: 2,
              borderRadius: 3,
              overflow: 'hidden',
              border: '1px solid',
              borderColor: isDark ? 'rgba(148,163,184,0.16)' : 'rgba(15,23,42,0.08)',
            }}
          >
            <PlotlyEquityCurve
              data={data.map((d) => ({
                timestamp: d.timestamp,
                equity: mode === 'abs' ? d.equityAbs : d.equityPct,
                buyHold: mode === 'abs' ? d.buyHoldAbs : d.buyHoldPct,
              }))}
              height={380}
              showBuyHold={showBuyHold}
              title=""
            />
          </Box>

          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={2}
            alignItems={{ xs: 'flex-start', sm: 'center' }}
            justifyContent="space-between"
            sx={{ mt: 2 }}
          >
            <Stack direction="row" spacing={2} flexWrap="wrap" rowGap={1}>
              <FormControlLabel
                sx={{ color: axisColor, '& .MuiFormControlLabel-label': { color: axisColor } }}
                control={
                  <Checkbox
                    size="small"
                    checked={showBuyHold}
                    onChange={(event) => onToggleBuyHold(event.target.checked)}
                    sx={{
                      color: axisColor,
                      '&.Mui-checked': {
                        color: '#facc15',
                      },
                    }}
                  />
                }
                label="Покупка и удержание"
              />
              <FormControlLabel
                sx={{ color: axisColor, '& .MuiFormControlLabel-label': { color: axisColor } }}
                control={
                  <Checkbox
                    size="small"
                    checked={showPnlBars}
                    onChange={(event) => onTogglePnlBars(event.target.checked)}
                    sx={{
                      color: axisColor,
                      '&.Mui-checked': {
                        color: '#f87171',
                      },
                    }}
                  />
                }
                label="Нарастание и просадка сделок"
              />
            </Stack>
            <ToggleButtonGroup
              size="small"
              color="primary"
              exclusive
              value={mode}
              onChange={handleModeChange}
              sx={{
                background: isDark ? '#07131b' : '#e2e8f0',
                borderRadius: 999,
                p: 0.5,
                '& .MuiToggleButton-root': {
                  border: '0 !important',
                  borderRadius: 999,
                  color: axisColor,
                  px: 2,
                  textTransform: 'none',
                  fontWeight: 600,
                },
                '& .Mui-selected': {
                  background: '#2563eb !important',
                  color: '#f8fafc !important',
                  boxShadow: '0 10px 28px rgba(37, 99, 235, 0.35)',
                },
              }}
            >
              <ToggleButton value="abs">Абсолютные значения</ToggleButton>
              <ToggleButton value="pct">Проценты</ToggleButton>
            </ToggleButtonGroup>
          </Stack>
        </>
      )}
    </Paper>
  );
};

const OverviewTab: React.FC<{
  backtest: Backtest | null;
  results: BacktestResults;
  chartData: ChartDatum[];
  chartMode: ChartMode;
  onChartModeChange: (value: ChartMode) => void;
  showPnlBars: boolean;
  onTogglePnlBars: (checked: boolean) => void;
  showBuyHold: boolean;
  onToggleBuyHold: (checked: boolean) => void;
  onDownloadCSV: (
    reportType: 'performance' | 'risk_ratios' | 'trades_analysis' | 'list_of_trades'
  ) => void;
}> = ({
  backtest,
  results,
  chartData,
  chartMode,
  onChartModeChange,
  showPnlBars,
  onTogglePnlBars,
  showBuyHold,
  onToggleBuyHold,
  onDownloadCSV,
}) => {
  const overview = results.overview ?? {};
  const statsAll = (results.by_side?.all ?? {}) as Partial<SideStats>;
  const wins = statsAll.wins ?? null;
  const losses = statsAll.losses ?? null;
  const totalTrades = overview.total_trades ?? statsAll.total_trades ?? null;

  const summary = [
    {
      title: 'Чистый PnL',
      primary: formatSignedValueWithUnit(overview.net_pnl, 'usd'),
      secondary: formatSignedValueWithUnit(overview.net_pct, 'percent', 2),
    },
    {
      title: 'Макс. просадка',
      primary: formatSignedValueWithUnit(overview.max_drawdown_abs, 'usd'),
      secondary: formatSignedValueWithUnit(overview.max_drawdown_pct, 'percent', 2),
    },
    {
      title: 'Всего сделок',
      primary: formatValueWithUnit(totalTrades, 'none', 0),
      secondary:
        wins != null && losses != null
          ? `${formatValueWithUnit(wins, 'none', 0)} побед / ${formatValueWithUnit(losses, 'none', 0)} поражений`
          : undefined,
    },
    {
      title: 'Win Rate',
      primary: formatValueWithUnit(statsAll.win_rate, 'percent', 2),
      secondary:
        wins != null && totalTrades != null
          ? `${formatValueWithUnit(wins, 'none', 0)} / ${formatValueWithUnit(totalTrades, 'none', 0)}`
          : undefined,
    },
    {
      title: 'Profit Factor',
      primary: formatValueWithUnit(overview.profit_factor, 'none', 3),
      secondary: undefined,
    },
  ];

  return (
    <Stack spacing={3} sx={{ mt: 2 }}>
      <Paper sx={{ p: 3, borderRadius: 2 }}>
        <Stack direction="row" spacing={4} flexWrap="wrap" rowGap={2}>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Торговый период
            </Typography>
            <Typography variant="h6" sx={{ mt: 0.5 }}>
              {backtest?.start_date && backtest?.end_date
                ? `${backtest.start_date} → ${backtest.end_date}`
                : '—'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Символ
            </Typography>
            <Typography variant="h6" sx={{ mt: 0.5 }}>
              {backtest?.symbol ?? '—'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Таймфрейм
            </Typography>
            <Typography variant="h6" sx={{ mt: 0.5 }}>
              {backtest?.timeframe ?? '—'}
            </Typography>
          </Box>
        </Stack>
      </Paper>

      {/* AI Analysis Panel - Perplexity AI integration */}
      <AIAnalysisPanel backtest={backtest} results={results} />

      <Paper sx={{ p: 3, borderRadius: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Экспорт отчётов CSV
        </Typography>
        <Stack direction="row" spacing={2} flexWrap="wrap" rowGap={1.5}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<DownloadIcon />}
            onClick={() => onDownloadCSV('performance')}
          >
            Показатели
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<DownloadIcon />}
            onClick={() => onDownloadCSV('risk_ratios')}
          >
            Риск-метрики
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<DownloadIcon />}
            onClick={() => onDownloadCSV('trades_analysis')}
          >
            Анализ сделок
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<DownloadIcon />}
            onClick={() => onDownloadCSV('list_of_trades')}
          >
            Список сделок
          </Button>
        </Stack>
      </Paper>

      <Paper sx={{ p: 3, borderRadius: 2 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={3}>
          <Stack spacing={1.5} flexShrink={0} minWidth={260}>
            {summary.map((item) => (
              <Paper key={item.title} sx={{ p: 2, borderRadius: 2 }}>
                <Typography variant="subtitle2" color="text.secondary">
                  {item.title}
                </Typography>
                <Typography variant="h5" sx={{ mt: 0.5 }}>
                  {item.primary}
                </Typography>
                {item.secondary ? (
                  <Typography variant="body2" color="text.secondary">
                    {item.secondary}
                  </Typography>
                ) : null}
              </Paper>
            ))}
          </Stack>

          <Box flexGrow={1}>
            <OverviewChart
              data={chartData}
              mode={chartMode}
              onModeChange={onChartModeChange}
              showPnlBars={showPnlBars}
              onTogglePnlBars={onTogglePnlBars}
              showBuyHold={showBuyHold}
              onToggleBuyHold={onToggleBuyHold}
            />
          </Box>
        </Stack>
      </Paper>
    </Stack>
  );
};

const DynamicsTab: React.FC<{ results: BacktestResults }> = ({ results }) => {
  const sides: SideKey[] = ['all', 'long', 'short'];
  const sideLabels: Record<SideKey, string> = {
    all: 'Все сделки',
    long: 'Длинные',
    short: 'Короткие',
  };

  const rows: Array<{ label: string; abs: keyof DynamicsStats; pct: keyof DynamicsStats | null }> =
    [
      { label: 'Нереализованный результат', abs: 'unrealized_abs', pct: 'unrealized_pct' },
      { label: 'Чистый результат', abs: 'net_abs', pct: 'net_pct' },
      { label: 'Валовая прибыль', abs: 'gross_profit_abs', pct: 'gross_profit_pct' },
      { label: 'Валовый убыток', abs: 'gross_loss_abs', pct: 'gross_loss_pct' },
      { label: 'Комиссии', abs: 'fees_abs', pct: 'fees_pct' },
      { label: 'Макс. рост капитала', abs: 'max_runup_abs', pct: 'max_runup_pct' },
      { label: 'Макс. просадка', abs: 'max_drawdown_abs', pct: 'max_drawdown_pct' },
      { label: 'Buy & Hold', abs: 'buyhold_abs', pct: 'buyhold_pct' },
      { label: 'Макс. контрактов', abs: 'max_contracts', pct: null },
    ];

  const getStats = (side: SideKey): Partial<DynamicsStats> =>
    (results.dynamics?.[side] ?? {}) as Partial<DynamicsStats>;

  return (
    <Paper sx={{ p: 3, mt: 2 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Таблица динамики
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Метрика</TableCell>
            {sides.map((side) => (
              <TableCell key={side} align="center">
                {sideLabels[side]}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.label} hover>
              <TableCell>{row.label}</TableCell>
              {sides.map((side) => {
                const data = getStats(side);
                if (row.abs === 'max_contracts') {
                  return (
                    <TableCell key={side} align="center">
                      {formatValueWithUnit((data as DynamicsStats).max_contracts, 'none', 0)}
                    </TableCell>
                  );
                }
                return (
                  <TableCell key={side} align="center">
                    <DualValue
                      absolute={data[row.abs]}
                      percent={row.pct ? data[row.pct] : undefined}
                    />
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Paper>
  );
};

const AnalysisTab: React.FC<{ results: BacktestResults }> = ({ results }) => {
  const sides: SideKey[] = ['all', 'long', 'short'];
  const sideLabels: Record<SideKey, string> = {
    all: 'Все сделки',
    long: 'Длинные',
    short: 'Короткие',
  };

  const fields: Array<{ key: keyof SideStats; label: string; unit: ValueUnit; digits?: number }> = [
    { key: 'total_trades', label: 'Всего сделок', unit: 'none' },
    { key: 'open_trades', label: 'Открытые сделки', unit: 'none' },
    { key: 'wins', label: 'Победы', unit: 'none' },
    { key: 'losses', label: 'Поражения', unit: 'none' },
    { key: 'win_rate', label: 'Win Rate', unit: 'percent', digits: 2 },
    { key: 'avg_pl', label: 'Средний PnL', unit: 'usd' },
    { key: 'avg_pl_pct', label: 'Средний PnL %', unit: 'percent', digits: 2 },
    { key: 'avg_win', label: 'Средняя победа', unit: 'usd' },
    { key: 'avg_win_pct', label: 'Средняя победа %', unit: 'percent', digits: 2 },
    { key: 'avg_loss', label: 'Средний проигрыш', unit: 'usd' },
    { key: 'avg_loss_pct', label: 'Средний проигрыш %', unit: 'percent', digits: 2 },
    { key: 'max_win', label: 'Макс. прибыль', unit: 'usd' },
    { key: 'max_win_pct', label: 'Макс. прибыль %', unit: 'percent', digits: 2 },
    { key: 'max_loss', label: 'Макс. убыток', unit: 'usd' },
    { key: 'max_loss_pct', label: 'Макс. убыток %', unit: 'percent', digits: 2 },
    { key: 'profit_factor', label: 'Profit Factor', unit: 'none', digits: 3 },
    { key: 'avg_bars', label: 'Среднее баров', unit: 'none' },
    { key: 'avg_bars_win', label: 'Баров в победе', unit: 'none' },
    { key: 'avg_bars_loss', label: 'Баров в поражении', unit: 'none' },
  ];

  const getSideStats = (side: SideKey): Partial<SideStats> =>
    (results.by_side?.[side] ?? {}) as Partial<SideStats>;

  return (
    <Paper sx={{ p: 3, mt: 2 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Анализ по направлениям
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Метрика</TableCell>
            {sides.map((side) => (
              <TableCell key={side} align="center">
                {sideLabels[side]}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {fields.map((field) => (
            <TableRow key={field.key} hover>
              <TableCell>{field.label}</TableCell>
              {sides.map((side) => (
                <TableCell key={side} align="center">
                  {formatValueWithUnit(getSideStats(side)[field.key], field.unit, field.digits)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Paper>
  );
};

const RiskTab: React.FC<{ results: BacktestResults }> = ({ results }) => {
  const risk = results.risk ?? {};
  const cards = [
    { title: 'Sharpe Ratio', value: risk.sharpe },
    { title: 'Sortino Ratio', value: risk.sortino },
    { title: 'Profit Factor', value: risk.profit_factor },
  ];

  return (
    <Stack spacing={2} sx={{ mt: 2 }}>
      <Stack direction="row" spacing={3} flexWrap="wrap" rowGap={2}>
        {cards.map((card) => (
          <Paper key={card.title} sx={{ p: 2, minWidth: 200 }}>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
              {card.title}
            </Typography>
            <Typography variant="h5">{formatValueWithUnit(card.value, 'none', 3)}</Typography>
          </Paper>
        ))}
      </Stack>
    </Stack>
  );
};

const TradesTab: React.FC<{
  trades: EnrichedTrade[];
  total?: number;
  onLoadMore: () => void;
  canLoadMore: boolean;
  loading: boolean;
  onExport: () => void;
  filters: TradeFilters;
  onFiltersChange: (filters: TradeFilters) => void;
  availableSignals: string[];
}> = ({
  trades,
  total,
  onLoadMore,
  canLoadMore,
  loading,
  onExport,
  filters,
  onFiltersChange,
  availableSignals,
}) => (
  <Stack spacing={2} sx={{ mt: 2 }}>
    {/* Advanced Trade Filters */}
    <AdvancedTradeFilters
      filters={filters}
      onFiltersChange={onFiltersChange}
      availableSignals={availableSignals}
    />

    <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" rowGap={1.5}>
      <Chip label={`Отображено: ${trades.length}${total != null ? ` из ${total}` : ''}`} />
      <Box flexGrow={1} />
      <Button variant="outlined" onClick={onExport} disabled={loading || trades.length === 0}>
        Экспорт CSV
      </Button>
      <Button variant="contained" onClick={onLoadMore} disabled={loading || !canLoadMore}>
        {loading ? <CircularProgress size={18} /> : 'Загрузить ещё'}
      </Button>
    </Stack>

    <Paper sx={{ p: 2 }}>
      {trades.length === 0 ? (
        <Typography color="text.secondary">Нет сделок для отображения.</Typography>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell />
              <TableCell>Этап</TableCell>
              <TableCell>Время</TableCell>
              <TableCell>Параметры</TableCell>
              <TableCell>Накопленный PnL</TableCell>
              <TableCell>Дополнительно</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {trades.map((trade, index) => (
              <React.Fragment key={trade.id ?? `${index}-${trade.entry_time}`}>
                <TableRow hover>
                  <TableCell rowSpan={2}>{trades.length - index}</TableCell>
                  <TableCell>Вход</TableCell>
                  <TableCell>{formatDateTime(trade.entry_time)}</TableCell>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <span>Цена: {formatValueWithUnit(trade.entry_price, 'usd')}</span>
                      <span>Объём: {formatQuantity(trade.quantity)}</span>
                    </Stack>
                  </TableCell>
                  <TableCell>{formatValueWithUnit(trade.cumulative_pnl, 'usd')}</TableCell>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <span>Сторона: {trade.side === 'buy' ? 'Long' : 'Short'}</span>
                      <span>Сигнал: {trade.signal || '—'}</span>
                    </Stack>
                  </TableCell>
                </TableRow>
                <TableRow hover sx={{ backgroundColor: 'action.hover' }}>
                  <TableCell>Выход</TableCell>
                  <TableCell>{formatDateTime(trade.exit_time)}</TableCell>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <span>PnL: {formatValueWithUnit(trade.pnl, 'usd')}</span>
                      <span>PnL%: {formatValueWithUnit(trade.pnl_pct, 'percent')}</span>
                      <span>Комиссия: {formatValueWithUnit((trade as any).fee, 'usd')}</span>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <span>Длительность: {formatDuration((trade as any).duration_min)}</span>
                      <span>Баров: {formatQuantity((trade as any).bars_held, 0)}</span>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <span>Макс. пик: {formatValueWithUnit(trade.run_up, 'usd')}</span>
                      <span>Макс. просадка: {formatValueWithUnit(trade.drawdown, 'usd')}</span>
                      <span>Размер позиции: {formatQuantity(trade.quantity)}</span>
                    </Stack>
                  </TableCell>
                </TableRow>
              </React.Fragment>
            ))}
          </TableBody>
        </Table>
      )}
    </Paper>
  </Stack>
);

const BacktestDetailPage: React.FC = () => {
  const params = useParams<{ id: string }>();
  const notify = useNotify();
  const backtestId = useMemo(() => {
    const raw = params.id;
    if (!raw) return null;
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  }, [params.id]);

  const [backtest, setBacktest] = useState<Backtest | null>(null);
  const [results, setResults] = useState<BacktestResults>({});
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [tradeLoading, setTradeLoading] = useState(false);
  const [trades, setTrades] = useState<EnrichedTrade[]>([]);
  const [tradesTotal, setTradesTotal] = useState<number | undefined>(undefined);
  const [chartMode, setChartMode] = useState<ChartMode>('abs');
  const [showPnlBars, setShowPnlBars] = useState(true);
  const [showBuyHold, setShowBuyHold] = useState(true);

  // Trade filters state (for AdvancedTradeFilters component)
  const [tradeFilters, setTradeFilters] = useState<TradeFilters>({
    side: '',
    sortBy: 'entry_time',
    sortOrder: 'desc',
  });

  const tradesRef = useRef<EnrichedTrade[]>([]);
  const tradesLoadingRef = useRef(false);

  useEffect(() => {
    tradesRef.current = trades;
  }, [trades]);

  const loadBacktest = useCallback(async () => {
    if (backtestId == null) return;
    try {
      setLoading(true);
      const data = await BacktestsApi.get(backtestId);
      setBacktest(data);
      const res = (data.results || {}) as BacktestResults;
      setResults(res ?? {});
    } catch (error: any) {
      notify({
        message: error?.friendlyMessage || 'Не удалось загрузить бэктест',
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  }, [backtestId, notify]);

  useEffect(() => {
    loadBacktest();
  }, [loadBacktest]);

  const handleDownloadCSV = useCallback(
    async (reportType: 'performance' | 'risk_ratios' | 'trades_analysis' | 'list_of_trades') => {
      if (backtestId == null) return;
      try {
        const blob = await BacktestsApi.exportCSV(backtestId, reportType);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `backtest_${backtestId}_${reportType}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        notify({ message: 'CSV файл успешно загружен', severity: 'success' });
      } catch (error: any) {
        notify({
          message: error?.friendlyMessage || 'Не удалось загрузить CSV',
          severity: 'error',
        });
      }
    },
    [backtestId, notify]
  );

  const chartData = useMemo<ChartDatum[]>(() => {
    if (!results) return [];
    const map = new Map<number, ChartDatum>();
    const equityRows = Array.isArray(results.equity) ? results.equity : [];
    equityRows.forEach((row) => {
      const ts = toTimestamp(row?.time);
      if (ts == null) return;
      const entry = map.get(ts) ?? { timestamp: ts, label: '' };
      const equityAbs = toFiniteNumber(row?.equity);
      if (equityAbs != null) entry.equityAbs = equityAbs;
      map.set(ts, entry);
    });

    const pnlRows = Array.isArray(results.pnl_bars) ? results.pnl_bars : [];
    pnlRows.forEach((row) => {
      const ts = toTimestamp(row?.time);
      if (ts == null) return;
      const entry = map.get(ts) ?? { timestamp: ts, label: '' };
      const pnlAbs = toFiniteNumber(row?.pnl);
      if (pnlAbs != null) entry.pnlAbs = pnlAbs;
      map.set(ts, entry);
    });

    const initial = toFiniteNumber(backtest?.initial_capital);
    const buyHoldDiffAbs = toFiniteNumber(results.dynamics?.all?.buyhold_abs);
    const buyHoldAbs = initial != null && buyHoldDiffAbs != null ? initial + buyHoldDiffAbs : null;
    const buyHoldPctRaw = toFiniteNumber(results.dynamics?.all?.buyhold_pct);

    return Array.from(map.values())
      .sort((a, b) => a.timestamp - b.timestamp)
      .map((entry) => {
        const datum: ChartDatum = {
          timestamp: entry.timestamp,
          label: formatDateTime(entry.timestamp),
        };
        if (entry.equityAbs != null) {
          datum.equityAbs = entry.equityAbs;
          if (initial != null && initial !== 0) {
            datum.equityPct = ((entry.equityAbs - initial) / initial) * 100;
          }
        }
        if (entry.pnlAbs != null) {
          datum.pnlAbs = entry.pnlAbs;
          if (initial != null && initial !== 0) {
            datum.pnlPct = (entry.pnlAbs / initial) * 100;
          }
        }
        if (buyHoldAbs != null) datum.buyHoldAbs = buyHoldAbs;
        if (buyHoldPctRaw != null) {
          datum.buyHoldPct = Math.abs(buyHoldPctRaw) <= 1 ? buyHoldPctRaw * 100 : buyHoldPctRaw;
        }
        return datum;
      });
  }, [results, backtest?.initial_capital]);

  const enhancedTrades = useMemo(() => {
    let cumulative = 0;
    return trades.map((trade) => {
      const pnl = toFiniteNumber(trade.pnl) ?? 0;
      cumulative += pnl;
      return { ...trade, cumulative };
    });
  }, [trades]);

  // Extract unique signals for filtering
  const availableSignals = useMemo(() => {
    const signals = new Set<string>();
    trades.forEach((trade) => {
      if (trade.signal) signals.add(trade.signal);
    });
    return Array.from(signals).sort();
  }, [trades]);

  const canLoadMore = tradesTotal == null || enhancedTrades.length < tradesTotal;

  const fetchTrades = useCallback(
    async (reset: boolean) => {
      if (backtestId == null || tradesLoadingRef.current) return;
      try {
        tradesLoadingRef.current = true;
        setTradeLoading(true);
        const offset = reset ? 0 : tradesRef.current.length;
        const response = await BacktestsApi.trades(backtestId, {
          limit: TRADE_PAGE_SIZE,
          offset,
          side: tradeFilters.side || undefined,
        });
        const items = (response?.items ?? []) as Trade[];
        const normalized = items.map((item) => ({ ...item })) as EnrichedTrade[];
        // Reverse order to show newest trades first
        const reversed = [...normalized].reverse();
        setTrades((prev) => (reset ? reversed : [...prev, ...reversed]));
        if (typeof response?.total === 'number') {
          setTradesTotal(response.total);
        } else if (reset) {
          setTradesTotal(normalized.length < TRADE_PAGE_SIZE ? normalized.length : undefined);
        }
      } catch (error: any) {
        notify({
          message: error?.friendlyMessage || 'Не удалось загрузить сделки',
          severity: 'error',
        });
      } finally {
        tradesLoadingRef.current = false;
        setTradeLoading(false);
      }
    },
    [backtestId, tradeFilters.side, notify]
  );

  useEffect(() => {
    if (backtestId == null) return;
    setTrades([]);
    tradesRef.current = [];
    setTradesTotal(undefined);
    fetchTrades(true);
  }, [backtestId, tradeFilters.side, fetchTrades]);

  const handleLoadMore = useCallback(() => {
    if (!canLoadMore || tradesLoadingRef.current) return;
    fetchTrades(false);
  }, [canLoadMore, fetchTrades]);

  const handleExport = useCallback(async () => {
    if (backtestId == null) return;
    try {
      tradesLoadingRef.current = true;
      setTradeLoading(true);
      let offset = 0;
      const all: EnrichedTrade[] = [];
      for (;;) {
        const response = await BacktestsApi.trades(backtestId, {
          limit: TRADE_PAGE_SIZE,
          offset,
          side: tradeFilters.side || undefined,
        });
        const items = (response?.items ?? []) as EnrichedTrade[];
        if (items.length === 0) break;
        all.push(...items);
        if (items.length < TRADE_PAGE_SIZE) break;
        offset += items.length;
      }
      if (all.length === 0) {
        notify({ message: 'Нет сделок для экспорта', severity: 'info' });
        return;
      }
      const header = [
        'id',
        'entry_time',
        'exit_time',
        'side',
        'price',
        'qty',
        'pnl',
        'pnl_pct',
        'fee',
        'signal',
        'duration_min',
        'bars_held',
      ];
      const rows = all.map((trade) =>
        header
          .map((key) => {
            const val = (trade as any)[key];
            if (val == null) return '';
            if (val instanceof Date) return val.toISOString();
            return String(val);
          })
          .join(';')
      );
      const csv = [header.join(';'), ...rows].join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `backtest-${backtestId}-trades.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error: any) {
      notify({ message: error?.friendlyMessage || 'Ошибка экспорта', severity: 'error' });
    } finally {
      tradesLoadingRef.current = false;
      setTradeLoading(false);
    }
  }, [backtestId, tradeFilters.side, notify]);

  if (backtestId == null) {
    return (
      <Container sx={{ py: 4 }}>
        <Alert severity="warning">Некорректный идентификатор бэктеста.</Alert>
      </Container>
    );
  }

  const resultsSafe = results ?? {};

  return (
    <Container sx={{ py: 3 }}>
      <Stack direction="row" alignItems="center" spacing={2}>
        <Typography variant="h4">Backtest #{backtestId}</Typography>
        {loading ? <LinearProgress sx={{ flexGrow: 1, maxWidth: 240 }} /> : null}
      </Stack>
      <Typography variant="subtitle1" color="text.secondary" sx={{ mt: 0.5 }}>
        Стратегия: {backtest?.strategy_id ?? '—'}
      </Typography>

      <Tabs
        value={tab}
        onChange={(_, next) => setTab(next)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mt: 2 }}
      >
        <Tab label="Обзор" />
        <Tab label="Динамика" />
        <Tab label="Анализ сделок" />
        <Tab label="Риск" />
        <Tab label="Графики" />
        <Tab label="TradingView" />
        <Tab label="Monte Carlo" />
        <Tab label="Сделки" />
      </Tabs>

      {tab === 0 && (
        <OverviewTab
          backtest={backtest}
          results={resultsSafe}
          chartData={chartData}
          chartMode={chartMode}
          onChartModeChange={setChartMode}
          showPnlBars={showPnlBars}
          onTogglePnlBars={setShowPnlBars}
          showBuyHold={showBuyHold}
          onToggleBuyHold={setShowBuyHold}
          onDownloadCSV={handleDownloadCSV}
        />
      )}
      {tab === 1 && <DynamicsTab results={resultsSafe} />}
      {tab === 2 && <AnalysisTab results={resultsSafe} />}
      {tab === 3 && <RiskTab results={resultsSafe} />}
      {tab === 4 && backtestId && <ChartsTab backtestId={backtestId} />}
      {tab === 5 && backtestId && <TradingViewTab backtestId={backtestId} />}
      {tab === 6 && backtestId && <MonteCarloTab backtestId={backtestId} />}
      {tab === 7 && (
        <TradesTab
          trades={enhancedTrades}
          total={tradesTotal}
          onLoadMore={handleLoadMore}
          canLoadMore={canLoadMore}
          loading={tradeLoading}
          onExport={handleExport}
          filters={tradeFilters}
          onFiltersChange={setTradeFilters}
          availableSignals={availableSignals}
        />
      )}
    </Container>
  );
};

export default BacktestDetailPage;
