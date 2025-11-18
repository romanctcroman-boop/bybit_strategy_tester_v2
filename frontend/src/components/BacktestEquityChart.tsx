import React, { useEffect, useMemo, useRef } from 'react';
import { Box, useTheme } from '@mui/material';
import {
  AreaSeries,
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  PriceScaleMode,
  type IChartApi,
} from 'lightweight-charts';

type ChartMode = 'abs' | 'pct';

type ChartDatum = {
  timestamp: number;
  equityAbs?: number;
  equityPct?: number;
  pnlAbs?: number;
  pnlPct?: number;
  buyHoldAbs?: number;
  buyHoldPct?: number;
};

interface BacktestEquityChartProps {
  data: ChartDatum[];
  mode: ChartMode;
  showPnlBars: boolean;
  showBuyHold: boolean;
  height?: number;
}

const toFiniteNumber = (value: unknown): number | null => {
  if (value == null) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string') {
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

const BacktestEquityChart: React.FC<BacktestEquityChartProps> = ({
  data,
  mode,
  showPnlBars,
  showBuyHold,
  height = 360,
}) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const equitySeriesRef = useRef<any>(null);
  const pnlSeriesRef = useRef<any>(null);
  const buyHoldSeriesRef = useRef<any>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const initialFitRef = useRef(false);
  const lastRangeRef = useRef<string | null>(null);
  const initialShowPnlBarsRef = useRef(showPnlBars);
  const initialShowBuyHoldRef = useRef(showBuyHold);

  const colors = useMemo(() => {
    return {
      background: isDark ? '#081125' : '#ffffff',
      text: isDark ? 'rgba(226,232,240,0.88)' : 'rgba(15, 23, 42, 0.82)',
      grid: isDark ? 'rgba(148, 163, 184, 0.16)' : 'rgba(148, 163, 184, 0.25)',
      axisBorder: isDark ? 'rgba(148, 163, 184, 0.24)' : 'rgba(148, 163, 184, 0.35)',
      equityLine: '#20edb7',
      equityAreaTop: 'rgba(32, 237, 183, 0.32)',
      equityAreaBottom: 'rgba(32, 237, 183, 0.04)',
      buyHold: '#facc15',
      pnlPositive: 'rgba(32, 237, 183, 0.85)',
      pnlNegative: 'rgba(248, 113, 113, 0.85)',
      crosshair: isDark ? 'rgba(148, 163, 184, 0.4)' : 'rgba(30, 41, 59, 0.35)',
    };
  }, [isDark]);

  useEffect(() => {
    initialShowPnlBarsRef.current = showPnlBars;
    initialShowBuyHoldRef.current = showBuyHold;
  }, [showPnlBars, showBuyHold]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Clean up any existing chart before re-creating (theme change)
    if (chartRef.current) {
      try {
        chartRef.current.remove();
      } catch {
        // ignore
      }
      chartRef.current = null;
      equitySeriesRef.current = null;
      pnlSeriesRef.current = null;
      buyHoldSeriesRef.current = null;
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      initialFitRef.current = false;
    }

    const chart = createChart(container, {
      width: container.clientWidth || 800,
      height,
      layout: {
        background: { type: ColorType.Solid, color: colors.background },
        textColor: colors.text,
      },
      grid: {
        horzLines: { color: colors.grid },
        vertLines: { color: colors.grid },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: colors.crosshair, labelBackgroundColor: colors.crosshair },
        horzLine: { color: colors.crosshair, labelBackgroundColor: colors.crosshair },
      },
      timeScale: {
        borderColor: colors.axisBorder,
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: colors.axisBorder,
        mode: PriceScaleMode.Normal,
      },
      leftPriceScale: {
        visible: initialShowPnlBarsRef.current,
        borderColor: colors.axisBorder,
        mode: PriceScaleMode.Normal,
      },
    });

    const equitySeries = chart.addSeries(AreaSeries, {
      lineColor: colors.equityLine,
      topColor: colors.equityAreaTop,
      bottomColor: colors.equityAreaBottom,
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });

    const pnlSeries = chart.addSeries(HistogramSeries, {
      priceScaleId: 'left',
      priceLineVisible: false,
      base: 0,
      lastValueVisible: false,
      color: colors.pnlPositive,
    });
    pnlSeries.applyOptions({ visible: initialShowPnlBarsRef.current });

    const buyHoldSeries = chart.addSeries(LineSeries, {
      color: colors.buyHold,
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });
    buyHoldSeries.applyOptions({ visible: initialShowBuyHoldRef.current });

    chartRef.current = chart;
    equitySeriesRef.current = equitySeries;
    pnlSeriesRef.current = pnlSeries;
    buyHoldSeriesRef.current = buyHoldSeries;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height: h } = entry.contentRect;
        if (width > 0 && h > 0) {
          chart.applyOptions({ width: Math.floor(width), height: Math.floor(h) });
        }
      }
    });
    resizeObserver.observe(container);
    resizeObserverRef.current = resizeObserver;

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      equitySeriesRef.current = null;
      pnlSeriesRef.current = null;
      buyHoldSeriesRef.current = null;
      resizeObserverRef.current = null;
      initialFitRef.current = false;
    };
  }, [colors, height]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.applyOptions({
      leftPriceScale: {
        visible: showPnlBars,
        borderColor: colors.axisBorder,
        mode: PriceScaleMode.Normal,
      },
    });
    if (pnlSeriesRef.current) {
      pnlSeriesRef.current.applyOptions({ visible: showPnlBars });
    }
    if (buyHoldSeriesRef.current) {
      buyHoldSeriesRef.current.applyOptions({ visible: showBuyHold });
    }
  }, [showPnlBars, showBuyHold, colors.axisBorder]);

  useEffect(() => {
    if (!chartRef.current || !equitySeriesRef.current) return;

    const toSeconds = (timestamp: number) => Math.floor(timestamp / 1000);

    const equityValues = data
      .map((row) => {
        const value =
          mode === 'pct' ? toFiniteNumber(row.equityPct) : toFiniteNumber(row.equityAbs);
        if (value == null) return null;
        return { time: toSeconds(row.timestamp), value };
      })
      .filter(Boolean) as Array<{ time: number; value: number }>;

    equitySeriesRef.current.setData(equityValues);
    equitySeriesRef.current.applyOptions({
      priceFormat:
        mode === 'pct'
          ? { type: 'price', precision: 2, minMove: 0.01 }
          : { type: 'price', precision: 2, minMove: 0.01 },
    });

    if (showPnlBars && pnlSeriesRef.current) {
      const histogram = data
        .map((row) => {
          const value = mode === 'pct' ? toFiniteNumber(row.pnlPct) : toFiniteNumber(row.pnlAbs);
          if (value == null) return null;
          const color = value >= 0 ? colors.pnlPositive : colors.pnlNegative;
          return { time: toSeconds(row.timestamp), value, color };
        })
        .filter(Boolean) as Array<{ time: number; value: number; color: string }>;
      pnlSeriesRef.current.setData(histogram);
      pnlSeriesRef.current.applyOptions({
        priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
      });
    } else if (pnlSeriesRef.current) {
      pnlSeriesRef.current.setData([]);
    }

    if (buyHoldSeriesRef.current) {
      if (showBuyHold) {
        const lineValues = data
          .map((row) => {
            const value =
              mode === 'pct' ? toFiniteNumber(row.buyHoldPct) : toFiniteNumber(row.buyHoldAbs);
            if (value == null) return null;
            return { time: toSeconds(row.timestamp), value };
          })
          .filter(Boolean) as Array<{ time: number; value: number }>;
        buyHoldSeriesRef.current.setData(lineValues);
      } else {
        buyHoldSeriesRef.current.setData([]);
      }
    }

    const signature = equityValues.length
      ? `${equityValues[0].time}-${equityValues[equityValues.length - 1].time}`
      : 'empty';
    if (signature !== lastRangeRef.current) {
      initialFitRef.current = false;
      lastRangeRef.current = signature;
    }

    if (equityValues.length && chartRef.current && !initialFitRef.current) {
      chartRef.current.timeScale().fitContent();
      initialFitRef.current = true;
    }
  }, [data, mode, showPnlBars, showBuyHold, colors.pnlNegative, colors.pnlPositive]);

  return <Box ref={containerRef} sx={{ width: '100%', height }} />;
};

export default BacktestEquityChart;
