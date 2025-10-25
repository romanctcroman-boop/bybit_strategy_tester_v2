import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Box,
  Button,
  Checkbox,
  Chip,
  Container,
  Divider,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useTheme,
} from "@mui/material";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  Cell,
} from "recharts";
import { BacktestsApi } from "../services/api";
import type { Backtest, Trade } from "../types/api";
import { useNotify } from "../components/NotificationsProvider";

type TradeSide = "" | "buy" | "sell";
type ChartMode = "abs" | "pct";
type ValueUnit = "usd" | "percent" | "plain";

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
    "all" | "long" | "short",
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
    "all" | "long" | "short",
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

type SideKey = "all" | "long" | "short";
type SideStats = NonNullable<BacktestResults["by_side"]>[SideKey];
type DynamicsStats = NonNullable<BacktestResults["dynamics"]>[SideKey];

type EnrichedTrade = Trade & {
  cumulative?: number;
};

const TRADE_PAGE_SIZE = 100;

const defaultDigits: Record<ValueUnit, number> = {
  usd: 2,
  percent: 2,
  plain: 0,
};

const toFiniteNumber = (value: unknown): number | null => {
  if (value == null) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string") {
    if (!value.trim()) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  if (value instanceof Date) {
    const parsed = value.getTime();
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const toTimestamp = (value: unknown): number | null => {
  if (value == null) return null;
  if (value instanceof Date) {
    const ts = value.getTime();
    return Number.isFinite(ts) ? ts : null;
  }
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string") {
    if (!value.trim()) return null;
    const ts = Date.parse(value);
    return Number.isFinite(ts) ? ts : null;
  }
  return null;
};

const formatNumber = (value: number, digits = 2): string =>
  new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);

const formatValueWithUnit = (value: unknown, unit: ValueUnit, digits?: number): string => {
  const numeric = toFiniteNumber(value);
  if (numeric == null) return "";
  const resolvedDigits = digits ?? defaultDigits[unit];
  if (unit === "percent") {
    const scaled = Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
    return `${formatNumber(scaled, resolvedDigits)}%`;
  }
  if (unit === "usd") {
    return `${formatNumber(numeric, resolvedDigits)} USDT`;
  }
  return formatNumber(numeric, resolvedDigits);
};

const formatSignedValueWithUnit = (value: unknown, unit: ValueUnit, digits?: number): string => {
  const numeric = toFiniteNumber(value);
  if (numeric == null) return "";
  if (numeric === 0) return formatValueWithUnit(0, unit, digits);
  const prefix = numeric > 0 ? "+" : "-";
  return `${prefix}${formatValueWithUnit(Math.abs(numeric), unit, digits)}`;
};

const formatDateTime = (value: unknown): string => {
  const ts = toTimestamp(value);
  if (ts == null) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(ts));
};

const formatQuantity = (value: unknown, digits = 4): string => {
  const numeric = toFiniteNumber(value);
  if (numeric == null) return "";
  const absValue = Math.abs(numeric);
  const hasFraction = Math.abs(absValue - Math.trunc(absValue)) > 1e-8;
  const minDigits = hasFraction ? Math.min(2, digits) : 0;
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: minDigits,
    maximumFractionDigits: digits,
  }).format(numeric);
};

const formatDuration = (minutes: unknown): string => {
  const numeric = toFiniteNumber(minutes);
  if (numeric == null) return "";
  const total = Math.max(0, Math.round(numeric));
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  const parts: string[] = [];
  if (hours) parts.push(`${hours} ч`);
  if (mins) parts.push(`${mins} мин`);
  return parts.length ? parts.join(" ") : "0 мин";
};

const DualValue: React.FC<{
  absolute?: unknown;
  percent?: unknown;
  absDigits?: number;
  pctDigits?: number;
}> = ({ absolute, percent, absDigits = 2, pctDigits = 2 }) => {
  const hasPercent = percent != null && toFiniteNumber(percent) != null;
  return (
    <Stack spacing={0.25} sx={{ fontSize: 14 }}>
      <span>{formatValueWithUnit(absolute, "usd", absDigits)}</span>
      {hasPercent ? (
        <Typography component="span" variant="caption" color="text.secondary">
          {formatValueWithUnit(percent, "percent", pctDigits)}
        </Typography>
      ) : null}
    </Stack>
  );
};

const SummaryMetric: React.FC<{ title: string; primary: string; secondary?: string }> = ({
  title,
  primary,
  secondary,
}) => (
  <Paper
    sx={{
      p: 2,
      borderRadius: 2,
      minWidth: 220,
      background: (theme) =>
        theme.palette.mode === "dark"
          ? "linear-gradient(160deg, rgba(8,15,23,0.92) 0%, rgba(12,22,32,0.92) 100%)"
          : "#101921",
      color: (theme) => (theme.palette.mode === "dark" ? theme.palette.text.primary : "#e8f1ff"),
      border: (theme) =>
        theme.palette.mode === "dark"
          ? "1px solid rgba(148, 163, 184, 0.18)"
          : "1px solid rgba(15, 23, 42, 0.18)",
      boxShadow: (theme) =>
        theme.palette.mode === "dark"
          ? "0 18px 48px rgba(8, 15, 23, 0.45)"
          : "0 18px 36px rgba(15, 23, 42, 0.28)",
    }}
  >
    <Typography variant="subtitle2" sx={{ opacity: 0.7 }}>
      {title}
    </Typography>
    <Typography variant="h5" sx={{ mt: 0.5, fontWeight: 600 }}>
      {primary}
    </Typography>
    {secondary ? (
      <Typography variant="body2" sx={{ mt: 0.5, opacity: 0.7 }}>
        {secondary}
      </Typography>
    ) : null}
  </Paper>
);

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
  const isDark = theme.palette.mode === "dark";
  const equityKey = mode === "pct" ? "equityPct" : "equityAbs";
  const pnlKey = mode === "pct" ? "pnlPct" : "pnlAbs";
  const buyHoldKey = mode === "pct" ? "buyHoldPct" : "buyHoldAbs";

  const axisColor = isDark ? "rgba(226, 232, 240, 0.72)" : "rgba(30, 41, 59, 0.72)";
  const gridColor = isDark ? "rgba(148, 163, 184, 0.18)" : "rgba(148, 163, 184, 0.28)";
  const tooltipBg = isDark ? "#07131b" : "#f8fafc";
  const tooltipColor = isDark ? "#f8fafc" : "#0f172a";
  const containerBg = isDark ? "rgba(4, 13, 18, 0.92)" : "#f8fafc";
  const positiveBar = "#20edb7";
  const negativeBar = "#f87171";

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
          ? "linear-gradient(160deg, rgba(2,8,23,0.92) 0%, rgba(8,15,23,0.92) 100%)"
          : "#ffffff",
        border: isDark ? "1px solid rgba(148, 163, 184, 0.18)" : "1px solid rgba(15, 23, 42, 0.08)",
        boxShadow: isDark ? "0 18px 60px rgba(8, 15, 23, 0.45)" : "0 20px 45px rgba(15, 23, 42, 0.12)",
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
              width: "100%",
              height: 380,
              mt: 2,
              borderRadius: 3,
              background: containerBg,
              px: 1,
              pb: 1,
            }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data} margin={{ top: 24, right: 28, bottom: 16, left: 0 }}>
                <defs>
                  <linearGradient id={`equity-gradient-${mode}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#20edb7" stopOpacity={0.32} />
                    <stop offset="100%" stopColor="#20edb7" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis
                  dataKey="timestamp"
                  type="number"
                  scale="time"
                  domain={['auto', 'auto']}
                  tickFormatter={(ts) =>
                    new Intl.DateTimeFormat("ru-RU", { month: "short", day: "2-digit" }).format(
                      new Date(ts as number)
                    )
                  }
                  tick={{ fill: axisColor, fontSize: 12, dy: 4 }}
                  axisLine={{ stroke: gridColor }}
                  tickLine={{ stroke: gridColor }}
                />
                <YAxis
                  yAxisId="left"
                  tickFormatter={(val: number) =>
                    mode === "pct" ? `${formatNumber(val, 1)}%` : formatNumber(val, 0)
                  }
                  tick={{ fill: axisColor, fontSize: 12 }}
                  axisLine={{ stroke: gridColor }}
                  tickLine={{ stroke: gridColor }}
                  width={80}
                />
                <RechartsTooltip
                  cursor={{ stroke: "rgba(148, 163, 184, 0.24)" }}
                  contentStyle={{
                    background: tooltipBg,
                    borderRadius: 12,
                    borderColor: "rgba(148, 163, 184, 0.22)",
                    color: tooltipColor,
                    boxShadow: "0 18px 48px rgba(8, 15, 23, 0.55)",
                  }}
                  labelFormatter={(ts) => formatDateTime(Number(ts))}
                  formatter={(rawValue: unknown, name?: string, payload?: any) => {
                    if (!name) return null;
                    const numeric = toFiniteNumber(rawValue);
                    if (numeric == null) return ["", name];
                    const key = String(payload?.dataKey ?? "").toLowerCase();
                    const isPercent = key.includes("pct") || name.includes("%");
                    const scaled = isPercent && Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
                    const suffix = isPercent ? "%" : " USDT";
                    return [`${formatNumber(scaled, 2)}${suffix}`, name];
                  }}
                />
                {showPnlBars ? (
                  <Bar
                    yAxisId="left"
                    dataKey={pnlKey}
                    name={mode === "pct" ? "PnL (%)" : "PnL"}
                    barSize={10}
                    radius={[6, 6, 6, 6]}
                  >
                    {data.map((entry) => {
                      const val = toFiniteNumber((entry as any)[pnlKey]);
                      const fill = val != null && val < 0 ? negativeBar : positiveBar;
                      return <Cell key={`pnl-${entry.timestamp}`} fill={fill} />;
                    })}
                  </Bar>
                ) : null}
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey={equityKey}
                  stroke="none"
                  fill={`url(#equity-gradient-${mode})`}
                  isAnimationActive={false}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey={equityKey}
                  name={mode === "pct" ? "Капитал (%)" : "Капитал"}
                  stroke="#20edb7"
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 4, stroke: "#0f172a", strokeWidth: 2, fill: "#20edb7" }}
                />
                {showBuyHold ? (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey={buyHoldKey}
                    name="Покупка и удержание"
                    stroke="#facc15"
                    strokeWidth={1.5}
                    strokeDasharray="6 4"
                    dot={false}
                    isAnimationActive={false}
                  />
                ) : null}
              </ComposedChart>
            </ResponsiveContainer>
          </Box>

          <Divider sx={{ my: 2, borderColor: isDark ? "rgba(148, 163, 184, 0.2)" : undefined }} />

          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={2}
            alignItems={{ xs: "flex-start", sm: "center" }}
            justifyContent="space-between"
          >
            <Stack direction="row" spacing={2} flexWrap="wrap" rowGap={1}>
              <FormControlLabel
                sx={{ color: axisColor, "& .MuiFormControlLabel-label": { color: axisColor } }}
                control={
                  <Checkbox
                    size="small"
                    checked={showBuyHold}
                    onChange={(event) => onToggleBuyHold(event.target.checked)}
                    sx={{
                      color: axisColor,
                      "&.Mui-checked": {
                        color: "#facc15",
                      },
                    }}
                  />
                }
                label="Покупка и удержание"
              />
              <FormControlLabel
                sx={{ color: axisColor, "& .MuiFormControlLabel-label": { color: axisColor } }}
                control={
                  <Checkbox
                    size="small"
                    checked={showPnlBars}
                    onChange={(event) => onTogglePnlBars(event.target.checked)}
                    sx={{
                      color: axisColor,
                      "&.Mui-checked": {
                        color: negativeBar,
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
                background: isDark ? "#07131b" : "#e2e8f0",
                borderRadius: 999,
                p: 0.5,
                "& .MuiToggleButton-root": {
                  border: "0 !important",
                  borderRadius: 999,
                  color: axisColor,
                  px: 2,
                  textTransform: "none",
                  fontWeight: 600,
                },
                "& .Mui-selected": {
                  background: "#2563eb !important",
                  color: "#f8fafc !important",
                  boxShadow: "0 10px 28px rgba(37, 99, 235, 0.35)",
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
}) => {
  const overview = results.overview ?? {};
  const statsAll = (results.by_side?.all ?? {}) as Partial<SideStats>;
  const wins = statsAll.wins ?? null;
  const losses = statsAll.losses ?? null;
  const totalTrades = overview.total_trades ?? statsAll.total_trades ?? null;

  const summary = [
    {
      title: "Общие ПР/УБ",
      primary: formatSignedValueWithUnit(overview.net_pnl, "usd"),
      secondary: formatSignedValueWithUnit(overview.net_pct, "percent", 2),
    },
    {
      title: "Макс. просадка средств",
      primary: formatSignedValueWithUnit(overview.max_drawdown_abs, "usd"),
      secondary: formatSignedValueWithUnit(overview.max_drawdown_pct, "percent", 2),
    },
    {
      title: "Всего сделок",
      primary: formatValueWithUnit(totalTrades, "plain", 0),
      secondary:
        wins != null && losses != null
          ? `${formatValueWithUnit(wins, "plain", 0)} побед / ${formatValueWithUnit(losses, "plain", 0)} убытков`
          : undefined,
    },
    {
      title: "Прибыльные сделки",
      primary: formatValueWithUnit(statsAll.win_rate, "percent", 2),
      secondary:
        wins != null && totalTrades != null
          ? `${formatValueWithUnit(wins, "plain", 0)} / ${formatValueWithUnit(totalTrades, "plain", 0)}`
          : undefined,
    },
    {
      title: "Фактор прибыли",
      primary: formatValueWithUnit(overview.profit_factor, "plain", 3),
      secondary: undefined,
    },
  ];

  return (
    <Stack spacing={3} sx={{ mt: 2 }}>
      <Paper sx={{ p: 3, borderRadius: 2 }}>
        <Stack direction="row" spacing={4} flexWrap="wrap" rowGap={2}>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Инструмент
            </Typography>
            <Typography variant="h6">{backtest?.symbol ?? ""}</Typography>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Таймфрейм
            </Typography>
            <Typography variant="h6">
              {backtest?.timeframe ? `${backtest.timeframe}m` : ""}
            </Typography>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Период
            </Typography>
            <Typography variant="h6">
              {`${formatDateTime(backtest?.start_date)}  ${formatDateTime(backtest?.end_date)}`}
            </Typography>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Капитал
            </Typography>
            <Typography variant="h6">{formatValueWithUnit(backtest?.initial_capital, "usd")}</Typography>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Плечо
            </Typography>
            <Typography variant="h6">
              {toFiniteNumber(backtest?.leverage) != null
                ? `x${formatNumber(toFiniteNumber(backtest?.leverage) ?? 0, 1)}`
                : ""}
            </Typography>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Статус
            </Typography>
            <Chip
              label={backtest?.status ? backtest.status.toUpperCase() : ""}
              color={backtest?.status === "completed" ? "success" : "default"}
            />
          </Box>
        </Stack>
      </Paper>

      <Stack direction="row" spacing={2} flexWrap="wrap" rowGap={2}>
        {summary.map((item) => (
          <SummaryMetric
            key={item.title}
            title={item.title}
            primary={item.primary}
            secondary={item.secondary}
          />
        ))}
      </Stack>

      <OverviewChart
        data={chartData}
        mode={chartMode}
        onModeChange={onChartModeChange}
        showPnlBars={showPnlBars}
        onTogglePnlBars={onTogglePnlBars}
        showBuyHold={showBuyHold}
        onToggleBuyHold={onToggleBuyHold}
      />
    </Stack>
  );
};

const DynamicsTab: React.FC<{ results: BacktestResults }> = ({ results }) => {
  const sides: SideKey[] = ["all", "long", "short"];
  const sideLabels: Record<SideKey, string> = {
    all: "Все сделки",
    long: "Длинные",
    short: "Короткие",
  };

  const rows: Array<{ label: string; abs: keyof DynamicsStats; pct: keyof DynamicsStats | null }> = [
    { label: "Нереализованная прибыль", abs: "unrealized_abs", pct: "unrealized_pct" },
    { label: "Чистая прибыль", abs: "net_abs", pct: "net_pct" },
    { label: "Валовая прибыль", abs: "gross_profit_abs", pct: "gross_profit_pct" },
    { label: "Валовый убыток", abs: "gross_loss_abs", pct: "gross_loss_pct" },
    { label: "Комиссии", abs: "fees_abs", pct: "fees_pct" },
    { label: "Макс. рост капитала", abs: "max_runup_abs", pct: "max_runup_pct" },
    { label: "Макс. просадка", abs: "max_drawdown_abs", pct: "max_drawdown_pct" },
    { label: "Buy & Hold", abs: "buyhold_abs", pct: "buyhold_pct" },
    { label: "Макс. контракты", abs: "max_contracts", pct: null },
  ];

  const getStats = (side: SideKey): Partial<DynamicsStats> =>
    (results.dynamics?.[side] ?? {}) as Partial<DynamicsStats>;

  return (
    <Paper sx={{ p: 3, mt: 2 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Денежная динамика
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Показатель</TableCell>
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
                if (row.abs === "max_contracts") {
                  return (
                    <TableCell key={side} align="center">
                      {formatValueWithUnit((data as DynamicsStats).max_contracts, "plain", 0)}
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
  const sides: SideKey[] = ["all", "long", "short"];
  const sideLabels: Record<SideKey, string> = {
    all: "Все сделки",
    long: "Длинные",
    short: "Короткие",
  };

  const fields: Array<{ key: keyof SideStats; label: string; unit: ValueUnit; digits?: number }> = [
    { key: "total_trades", label: "Всего сделок", unit: "plain" },
    { key: "open_trades", label: "Открыто сейчас", unit: "plain" },
    { key: "wins", label: "Побед", unit: "plain" },
    { key: "losses", label: "Убытков", unit: "plain" },
    { key: "win_rate", label: "Win Rate", unit: "percent", digits: 2 },
    { key: "avg_pl", label: "Средний PnL", unit: "usd" },
    { key: "avg_pl_pct", label: "Средний PnL %", unit: "percent", digits: 2 },
    { key: "avg_win", label: "Средняя прибыль", unit: "usd" },
    { key: "avg_win_pct", label: "Средняя прибыль %", unit: "percent", digits: 2 },
    { key: "avg_loss", label: "Средний убыток", unit: "usd" },
    { key: "avg_loss_pct", label: "Средний убыток %", unit: "percent", digits: 2 },
    { key: "max_win", label: "Макс. прибыль", unit: "usd" },
    { key: "max_win_pct", label: "Макс. прибыль %", unit: "percent", digits: 2 },
    { key: "max_loss", label: "Макс. убыток", unit: "usd" },
    { key: "max_loss_pct", label: "Макс. убыток %", unit: "percent", digits: 2 },
    { key: "profit_factor", label: "Profit Factor", unit: "plain", digits: 3 },
    { key: "avg_bars", label: "Среднее баров", unit: "plain" },
    { key: "avg_bars_win", label: "Баров в профите", unit: "plain" },
    { key: "avg_bars_loss", label: "Баров в убытке", unit: "plain" },
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
            <TableCell>Показатель</TableCell>
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
    { title: "Sharpe Ratio", value: risk.sharpe },
    { title: "Sortino Ratio", value: risk.sortino },
    { title: "Profit Factor", value: risk.profit_factor },
  ];

  return (
    <Stack spacing={2} sx={{ mt: 2 }}>
      <Stack direction="row" spacing={3} flexWrap="wrap" rowGap={2}>
        {cards.map((card) => (
          <Paper key={card.title} sx={{ p: 2, minWidth: 200 }}>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
              {card.title}
            </Typography>
            <Typography variant="h5">{formatValueWithUnit(card.value, "plain", 3)}</Typography>
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
  side: TradeSide;
  onSideChange: (value: TradeSide) => void;
  onExport: () => void;
}> = ({ trades, total, onLoadMore, canLoadMore, loading, side, onSideChange, onExport }) => (
  <Stack spacing={2} sx={{ mt: 2 }}>
    <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" rowGap={1.5}>
      <TextField
        select
        label="Сторона"
        size="small"
        value={side}
        onChange={(event) => onSideChange(event.target.value as TradeSide)}
        sx={{ width: 200 }}
      >
        <MenuItem value="">Все</MenuItem>
        <MenuItem value="buy">Long</MenuItem>
        <MenuItem value="sell">Short</MenuItem>
      </TextField>
      <Chip label={`Загружено: ${trades.length}${total != null ? ` из ${total}` : ""}`} />
      <Box flexGrow={1} />
      <Button variant="outlined" onClick={onExport} disabled={loading || trades.length === 0}>
        Экспорт CSV
      </Button>
      <Button variant="contained" onClick={onLoadMore} disabled={loading || !canLoadMore}>
        {loading ? "Загрузка" : "Загрузить ещё"}
      </Button>
    </Stack>

    <Paper sx={{ p: 2 }}>
      {trades.length === 0 ? (
        <Typography color="text.secondary">Нет сделок для отображения.</Typography>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell></TableCell>
              <TableCell>Этап</TableCell>
              <TableCell>Время</TableCell>
              <TableCell>Финансы</TableCell>
              <TableCell>Накопительно</TableCell>
              <TableCell>Дополнительно</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {trades.map((trade, index) => (
              <React.Fragment key={trade.id ?? `${index}-${trade.entry_time}`}>
                <TableRow hover>
                  <TableCell rowSpan={2}>{index + 1}</TableCell>
                  <TableCell>Вход</TableCell>
                  <TableCell>{formatDateTime(trade.entry_time)}</TableCell>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <span>Цена: {formatValueWithUnit(trade.price, "usd")}</span>
                      <span>Объём: {formatQuantity(trade.qty)}</span>
                      <span>PnL: {formatValueWithUnit(trade.pnl, "usd")}</span>
                      <span>PnL%: {formatValueWithUnit(trade.pnl_pct, "percent")}</span>
                    </Stack>
                  </TableCell>
                  <TableCell>{formatValueWithUnit(trade.cumulative, "usd")}</TableCell>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <span>Сторона: {trade.side === "buy" ? "Long" : "Short"}</span>
                      <span>Сигнал: {trade.signal || ""}</span>
                    </Stack>
                  </TableCell>
                </TableRow>
                <TableRow hover sx={{ backgroundColor: "action.hover" }}>
                  <TableCell>Выход</TableCell>
                  <TableCell>{formatDateTime(trade.exit_time)}</TableCell>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <span>Комиссия: {formatValueWithUnit((trade as any).fee, "usd")}</span>
                      <span>MFE: {formatValueWithUnit((trade as any).mfe, "usd")}</span>
                      <span>MAE: {formatValueWithUnit((trade as any).mae, "usd")}</span>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <span>Длительность: {formatDuration((trade as any).duration_min)}</span>
                      <span>Бары: {formatQuantity((trade as any).bars_held, 0)}</span>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <span>Макс. прибыль: {formatValueWithUnit((trade as any).peak, "usd")}</span>
                      <span>Макс. просадка: {formatValueWithUnit((trade as any).drawdown, "usd")}</span>
                      <span>Позиция: {formatQuantity(trade.position_size ?? trade.qty)}</span>
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
  const [tradeSide, setTradeSide] = useState<TradeSide>("");
  const [trades, setTrades] = useState<EnrichedTrade[]>([]);
  const [tradesTotal, setTradesTotal] = useState<number | undefined>(undefined);
  const [chartMode, setChartMode] = useState<ChartMode>("abs");
  const [showPnlBars, setShowPnlBars] = useState(true);
  const [showBuyHold, setShowBuyHold] = useState(true);

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
      notify({ message: error?.friendlyMessage || "Не удалось загрузить тест", severity: "error" });
    } finally {
      setLoading(false);
    }
  }, [backtestId, notify]);

  useEffect(() => {
    loadBacktest();
  }, [loadBacktest]);

  const chartData = useMemo<ChartDatum[]>(() => {
    const map = new Map<number, ChartDatum>();
    const equityRows = Array.isArray(results?.equity) ? results.equity : [];
    equityRows.forEach((row) => {
      const ts = toTimestamp((row as any)?.time);
      if (ts == null) return;
      const entry = map.get(ts) ?? { timestamp: ts, label: "" };
      const equityAbs = toFiniteNumber((row as any)?.equity);
      if (equityAbs != null) entry.equityAbs = equityAbs;
      map.set(ts, entry);
    });

    const pnlRows = Array.isArray(results?.pnl_bars) ? results.pnl_bars : [];
    pnlRows.forEach((row) => {
      const ts = toTimestamp((row as any)?.time);
      if (ts == null) return;
      const entry = map.get(ts) ?? { timestamp: ts, label: "" };
      const pnlAbs = toFiniteNumber((row as any)?.pnl);
      if (pnlAbs != null) entry.pnlAbs = pnlAbs;
      map.set(ts, entry);
    });

    const initial = toFiniteNumber(backtest?.initial_capital);
    const buyHoldDiffAbs = toFiniteNumber(results?.dynamics?.all?.buyhold_abs);
    const buyHoldAbs = initial != null && buyHoldDiffAbs != null ? initial + buyHoldDiffAbs : null;
    const buyHoldPctRaw = toFiniteNumber(results?.dynamics?.all?.buyhold_pct);

    return Array.from(map.values())
      .sort((a, b) => a.timestamp - b.timestamp)
      .map((entry) => {
        const datum: ChartDatum = {
          timestamp: entry.timestamp,
          label: formatDateTime(entry.timestamp),
        };
        const equityAbs = entry.equityAbs;
        if (equityAbs != null) {
          datum.equityAbs = equityAbs;
          if (initial != null && initial !== 0) {
            datum.equityPct = ((equityAbs - initial) / initial) * 100;
          }
        }
        const pnlAbs = entry.pnlAbs;
        if (pnlAbs != null) {
          datum.pnlAbs = pnlAbs;
          if (initial != null && initial !== 0) {
            datum.pnlPct = (pnlAbs / initial) * 100;
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

  const canLoadMore = tradesTotal == null || enhancedTrades.length < tradesTotal;

  const fetchTrades = useCallback(
    async (reset: boolean) => {
      if (backtestId == null || tradesLoadingRef.current) return;
      try {
        tradesLoadingRef.current = true;
        setTradeLoading(true);
        const offset = reset ? 0 : tradesRef.current.length;
        const { items, total } = await BacktestsApi.trades(backtestId, {
          limit: TRADE_PAGE_SIZE,
          offset,
          side: tradeSide || undefined,
        });
        const normalized = items.map((item) => ({ ...item })) as EnrichedTrade[];
        setTrades((prev) => (reset ? normalized : [...prev, ...normalized]));
        if (typeof total === "number") {
          setTradesTotal(total);
        } else if (reset) {
          setTradesTotal(normalized.length < TRADE_PAGE_SIZE ? normalized.length : undefined);
        }
      } catch (error: any) {
        notify({
          message: error?.friendlyMessage || "Не удалось загрузить сделки",
          severity: "error",
        });
      } finally {
        tradesLoadingRef.current = false;
        setTradeLoading(false);
      }
    },
    [backtestId, tradeSide, notify]
  );

  useEffect(() => {
    if (backtestId == null) return;
    setTrades([]);
    tradesRef.current = [];
    setTradesTotal(undefined);
    fetchTrades(true);
  }, [backtestId, tradeSide, fetchTrades]);

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
        const { items } = await BacktestsApi.trades(backtestId, {
          limit: TRADE_PAGE_SIZE,
          offset,
          side: tradeSide || undefined,
        });
        all.push(...(items as EnrichedTrade[]));
        if (items.length < TRADE_PAGE_SIZE) break;
        offset += items.length;
      }
      if (all.length === 0) {
        notify({ message: "Нет данных для экспорта", severity: "info" });
        return;
      }
      const header = [
        "id",
        "entry_time",
        "exit_time",
        "side",
        "price",
        "qty",
        "pnl",
        "pnl_pct",
        "fee",
        "signal",
        "duration_min",
        "bars_held",
      ];
      const rows = all.map((trade) =>
        header
          .map((key) => {
            const val = (trade as any)[key];
            if (val == null) return "";
            if (val instanceof Date) return val.toISOString();
            return String(val);
          })
          .join(";")
      );
      const csv = [header.join(";"), ...rows].join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `backtest-${backtestId}-trades.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error: any) {
      notify({ message: error?.friendlyMessage || "Ошибка экспорта", severity: "error" });
    } finally {
      tradesLoadingRef.current = false;
      setTradeLoading(false);
    }
  }, [backtestId, tradeSide, notify]);

  const resultsSafe = results ?? {};

  if (backtestId == null) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Typography variant="h4">Детали теста</Typography>
        <Typography color="error" sx={{ mt: 2 }}>
          Некорректный идентификатор теста.
        </Typography>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4">Детали теста</Typography>
      {loading && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Загрузка данных
        </Typography>
      )}
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
        <Tab label="Коэффициенты риска/эффективности" sx={{ whiteSpace: "nowrap" }} />
        <Tab label="Список сделок" />
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
        />
      )}
      {tab === 1 && <DynamicsTab results={resultsSafe} />}
      {tab === 2 && <AnalysisTab results={resultsSafe} />}
      {tab === 3 && <RiskTab results={resultsSafe} />}
      {tab === 4 && (
        <TradesTab
          trades={enhancedTrades}
          total={tradesTotal}
          onLoadMore={handleLoadMore}
          canLoadMore={canLoadMore}
          loading={tradeLoading}
          side={tradeSide}
          onSideChange={setTradeSide}
          onExport={handleExport}
        />
      )}
    </Container>
  );
};

export default BacktestDetailPage;
