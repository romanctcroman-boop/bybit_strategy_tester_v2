import React, { useEffect, useRef, useState } from 'react';
import { createChart, PriceScaleMode } from 'lightweight-charts';

interface Candle {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}
interface TradeMarker {
  time: number;
  side: 'buy' | 'sell';
  price: number;
  tp_price?: number;
  sl_price?: number;
  exit_price?: number;
  exit_time?: number;
  // Enhanced marker display (ТЗ 9.2 Step 3)
  pnl?: number; // Profit/Loss amount
  pnl_percent?: number; // P&L percentage
  size?: number; // Trade size (for marker scaling)
  label?: string; // Custom marker label
  color?: string; // Override marker color
  is_entry?: boolean; // True for entry, false for exit
}

interface PriceLine {
  price: number;
  color: string;
  lineWidth?: number;
  lineStyle?: 'solid' | 'dotted' | 'dashed';
  axisLabelVisible?: boolean;
  title?: string;
}
interface Props {
  candles: Candle[];
  markers?: TradeMarker[];
  showSMA20?: boolean;
  showSMA50?: boolean;
  // Interactive controls
  chartType?: 'candlestick' | 'line' | 'area' | 'baseline';
  scaleMode?: 'normal' | 'log' | 'percent' | 'index100';
  wheelZoom?: boolean;
  dragScroll?: boolean;
  // Price format controls
  pricePrecision?: number; // number of fraction digits
  minMove?: number; // minimal price step (e.g., 0.01 for 2 decimals)
  // Expose a small API to parent for view controls
  onApi?: (api: {
    fitContent: () => void;
    setVisibleRange: (fromSec: number, toSec: number) => void;
    getVisibleRange: () => { from: number; to: number } | null;
  }) => void;
  // Optional custom legend
  showLegend?: boolean;
  // Volume histogram
  showVolume?: boolean;
  volumeScale?: 'left' | 'right';
  // Request more data when user scrolls to edges
  onNeedMore?: (dir: 'left' | 'right', fromTimeSec: number) => void | Promise<void>;
  // TP/SL price lines (ТЗ 9.2)
  showTPSL?: boolean;
  priceLines?: PriceLine[];
  // Enhanced markers (ТЗ 9.2 Step 3)
  showMarkerTooltips?: boolean; // Show P&L in tooltips
  scaleMarkersBySize?: boolean; // Scale marker size by trade size
  showExitMarkers?: boolean; // Show separate exit markers
}

const TradingViewChart: React.FC<Props> = ({
  candles,
  markers = [],
  showSMA20 = true,
  showSMA50 = false,
  chartType = 'candlestick',
  scaleMode = 'normal',
  wheelZoom = true,
  dragScroll = true,
  pricePrecision,
  minMove,
  onApi,
  showLegend = false,
  showVolume = false,
  volumeScale = 'left',
  onNeedMore,
  showTPSL = false,
  priceLines = [],
  showMarkerTooltips = true,
  scaleMarkersBySize = false,
  showExitMarkers = true,
}) => {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);
  const sma20Ref = useRef<any>(null);
  const sma50Ref = useRef<any>(null);
  const roRef = useRef<ResizeObserver | null>(null);
  const volumeRef = useRef<any>(null);
  const priceLinesRef = useRef<any[]>([]);
  const [legend, setLegend] = useState<{
    time: string;
    price: number | { open: number; high: number; low: number; close: number };
  } | null>(null);
  const loadingMoreRef = useRef<boolean>(false);
  const lastRequestedRef = useRef<number | null>(null);

  // Compatibility helpers for different lightweight-charts major versions
  const addCandlesCompat = (chart: any, options?: any) => {
    try {
      if (typeof chart?.addCandlestickSeries === 'function')
        return chart.addCandlestickSeries(options);
    } catch {}
    try {
      if (typeof chart?.addSeries === 'function')
        return chart.addSeries({ type: 'Candlestick', ...(options || {}) });
    } catch {}
    throw new Error('Candlestick series API not found on chart object');
  };
  const addLineCompat = (chart: any, options?: any) => {
    try {
      if (typeof chart?.addLineSeries === 'function') return chart.addLineSeries(options);
    } catch {}
    try {
      if (typeof chart?.addSeries === 'function')
        return chart.addSeries({ type: 'Line', ...(options || {}) });
    } catch {}
    throw new Error('Line series API not found on chart object');
  };
  const addAreaCompat = (chart: any, options?: any) => {
    try {
      if (typeof chart?.addAreaSeries === 'function') return chart.addAreaSeries(options);
    } catch {}
    try {
      if (typeof chart?.addSeries === 'function')
        return chart.addSeries({ type: 'Area', ...(options || {}) });
    } catch {}
    throw new Error('Area series API not found on chart object');
  };
  const addHistogramCompat = (chart: any, options?: any) => {
    try {
      if (typeof chart?.addHistogramSeries === 'function') return chart.addHistogramSeries(options);
    } catch {}
    try {
      if (typeof chart?.addSeries === 'function')
        return chart.addSeries({ type: 'Histogram', ...(options || {}) });
    } catch {}
    throw new Error('Histogram series API not found on chart object');
  };
  const addBaselineCompat = (chart: any, options?: any) => {
    try {
      if (typeof chart?.addBaselineSeries === 'function') return chart.addBaselineSeries(options);
    } catch {}
    try {
      if (typeof chart?.addSeries === 'function')
        return chart.addSeries({ type: 'Baseline', ...(options || {}) });
    } catch {}
    throw new Error('Baseline series API not found on chart object');
  };

  const createSeriesByType = (c: any, t: 'candlestick' | 'line' | 'area' | 'baseline') => {
    if (t === 'line') return addLineCompat(c, { color: '#90caf9' });
    if (t === 'area')
      return addAreaCompat(c, {
        lineColor: '#90caf9',
        topColor: 'rgba(144,202,249,0.2)',
        bottomColor: 'rgba(144,202,249,0.0)',
      });
    if (t === 'baseline')
      return addBaselineCompat(c, {
        baseValue: { type: 'price', price: 0 },
        topFillColor1: 'rgba(76,175,80,0.2)',
        bottomFillColor1: 'rgba(244,67,54,0.2)',
      });
    return addCandlesCompat(c);
  };

  const priceScaleModeFrom = (m: 'normal' | 'log' | 'percent' | 'index100') => {
    switch (m) {
      case 'log':
        return PriceScaleMode.Logarithmic;
      case 'percent':
        return PriceScaleMode.Percentage;
      case 'index100':
        return PriceScaleMode.IndexedTo100;
      default:
        return PriceScaleMode.Normal;
    }
  };

  useEffect(() => {
    if (!ref.current) return;
    try {
      const initWidth = ref.current.clientWidth || 800;
      const initHeight = ref.current.clientHeight || 480;
      const chart: any = createChart(ref.current, {
        width: initWidth,
        height: initHeight,
        rightPriceScale: { mode: priceScaleModeFrom(scaleMode) },
        handleScroll: {
          mouseWheel: dragScroll,
          pressedMouseMove: dragScroll,
          horzTouchDrag: true,
          vertTouchDrag: true,
        },
        handleScale: { mouseWheel: wheelZoom, pinch: true, axisPressedMouseMove: true },
      });
      chartRef.current = chart;
      const series: any = createSeriesByType(chart, chartType);
      seriesRef.current = series;
      // Apply price format if provided
      if (typeof (pricePrecision as any) === 'number' || typeof (minMove as any) === 'number') {
        try {
          series.applyOptions({
            priceFormat: {
              type: 'price',
              precision: typeof pricePrecision === 'number' ? pricePrecision : undefined,
              minMove: typeof minMove === 'number' ? minMove : undefined,
            },
          });
        } catch {}
      }

      // Provide tiny API to parent
      if (typeof onApi === 'function') {
        onApi({
          fitContent: () => {
            try {
              chart.timeScale().fitContent();
            } catch {}
          },
          setVisibleRange: (fromSec: number, toSec: number) => {
            try {
              chart
                .timeScale()
                .setVisibleRange({ from: Math.floor(fromSec), to: Math.floor(toSec) });
            } catch {}
          },
          getVisibleRange: () => {
            try {
              const r = chart.timeScale().getVisibleRange();
              if (r && typeof r.from === 'number' && typeof r.to === 'number') {
                return { from: Math.floor(r.from), to: Math.floor(r.to) };
              }
            } catch {}
            return null;
          },
        });
      }
      const mapped = candles.map((c) => ({
        time:
          typeof c.time === 'number'
            ? Math.floor(c.time)
            : Math.floor(new Date(c.time).getTime() / 1000),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));
      // Data format depends on series type; for non-candles use close as value
      if (chartType === 'candlestick') {
        series.setData(mapped as any);
      } else {
        series.setData(mapped.map((d) => ({ time: d.time as number, value: d.close })) as any);
      }
      // Volume histogram (optional)
      if (showVolume) {
        try {
          volumeRef.current = addHistogramCompat(chart, {
            priceScaleId: volumeScale === 'left' ? 'left' : 'right',
            color: 'rgba(124,179,66,0.7)',
            base: 0,
            lineWidth: 1,
            priceFormat: { type: 'volume' },
            scaleMargins: { top: 0.8, bottom: 0 },
          });
          const vdata = mapped.map((d) => ({
            time: d.time as number,
            value: d.close != null ? ((d as any).volume ?? 0) : 0,
          }));
          volumeRef.current.setData(vdata as any);
        } catch {}
      }

      // Enhanced Trade Markers (ТЗ 9.2 Step 3)
      if (markers.length) {
        const enhancedMarkers = markers.map((m) => {
          // Determine if this is entry or exit marker
          const isEntry = m.is_entry !== undefined ? m.is_entry : !m.exit_time;

          // Base marker configuration
          let markerConfig: any = {
            time: Math.floor(m.time),
            position: m.side === 'buy' ? 'belowBar' : 'aboveBar',
          };

          // Color logic
          if (m.color) {
            markerConfig.color = m.color;
          } else if (isEntry) {
            // Entry markers: green for buy, red for sell
            markerConfig.color = m.side === 'buy' ? '#2e7d32' : '#c62828';
          } else {
            // Exit markers: different shades based on P&L
            if (m.pnl !== undefined) {
              markerConfig.color = m.pnl >= 0 ? '#1976d2' : '#d32f2f';
            } else {
              markerConfig.color = m.side === 'buy' ? '#1976d2' : '#ff6f00';
            }
          }

          // Shape logic
          if (isEntry) {
            markerConfig.shape = m.side === 'buy' ? 'arrowUp' : 'arrowDown';
          } else {
            // Exit markers: circles for exits
            markerConfig.shape = showExitMarkers
              ? 'circle'
              : m.side === 'buy'
                ? 'arrowDown'
                : 'arrowUp';
          }

          // Size scaling
          if (scaleMarkersBySize && m.size !== undefined) {
            // Normalize size: 0.5 to 2.0 scale
            const normalizedSize = Math.max(0.5, Math.min(2.0, m.size / 1.0));
            markerConfig.size = normalizedSize;
          }

          // Text/Tooltip
          if (m.label) {
            markerConfig.text = m.label;
          } else if (showMarkerTooltips) {
            if (isEntry) {
              markerConfig.text = `${m.side.toUpperCase()} ${m.price.toFixed(2)}`;
            } else if (m.pnl !== undefined && m.pnl_percent !== undefined) {
              const pnlSign = m.pnl >= 0 ? '+' : '';
              markerConfig.text = `EXIT ${m.price.toFixed(2)} (${pnlSign}${m.pnl_percent.toFixed(2)}%)`;
            } else {
              markerConfig.text = `EXIT ${m.price.toFixed(2)}`;
            }
          } else {
            markerConfig.text = `${m.side.toUpperCase()} ${m.price.toFixed(2)}`;
          }

          return markerConfig;
        });

        series.setMarkers(enhancedMarkers as any);
      }

      // TP/SL Price Lines (ТЗ 9.2)
      if (showTPSL && markers.length) {
        // Clear existing price lines
        priceLinesRef.current.forEach((line) => {
          try {
            series.removePriceLine(line);
          } catch {}
        });
        priceLinesRef.current = [];

        // Add TP/SL lines for each trade marker
        markers.forEach((marker) => {
          // Take Profit line
          if (marker.tp_price) {
            try {
              const tpLine = series.createPriceLine({
                price: marker.tp_price,
                color: '#4caf50',
                lineWidth: 2,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: `TP: ${marker.tp_price.toFixed(2)}`,
              });
              priceLinesRef.current.push(tpLine);
            } catch {}
          }

          // Stop Loss line
          if (marker.sl_price) {
            try {
              const slLine = series.createPriceLine({
                price: marker.sl_price,
                color: '#f44336',
                lineWidth: 2,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: `SL: ${marker.sl_price.toFixed(2)}`,
              });
              priceLinesRef.current.push(slLine);
            } catch {}
          }

          // Exit line (if different from TP/SL)
          if (
            marker.exit_price &&
            marker.exit_price !== marker.tp_price &&
            marker.exit_price !== marker.sl_price
          ) {
            try {
              const exitLine = series.createPriceLine({
                price: marker.exit_price,
                color: '#2196f3',
                lineWidth: 2,
                lineStyle: 1, // Dotted
                axisLabelVisible: true,
                title: `Exit: ${marker.exit_price.toFixed(2)}`,
              });
              priceLinesRef.current.push(exitLine);
            } catch {}
          }
        });
      }

      // Custom price lines
      if (priceLines.length) {
        priceLines.forEach((pl) => {
          try {
            const lineStyle = pl.lineStyle === 'dotted' ? 1 : pl.lineStyle === 'dashed' ? 2 : 0;
            const line = series.createPriceLine({
              price: pl.price,
              color: pl.color,
              lineWidth: pl.lineWidth || 2,
              lineStyle: lineStyle,
              axisLabelVisible: pl.axisLabelVisible !== false,
              title: pl.title || '',
            });
            priceLinesRef.current.push(line);
          } catch {}
        });
      }

      chart.timeScale().fitContent();

      // Track container size changes, including user-resize of wrapper
      const ro = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const cr = entry.contentRect;
          if (cr.width > 0 && cr.height > 0) {
            try {
              chart.applyOptions({ width: Math.floor(cr.width), height: Math.floor(cr.height) });
            } catch {}
          }
        }
      });
      ro.observe(ref.current!);
      roRef.current = ro;

      const onResize = () => {
        if (!ref.current) return;
        try {
          chart.applyOptions({ width: ref.current.clientWidth, height: ref.current.clientHeight });
        } catch {}
      };
      // Crosshair legend
      const crosshairHandler = (param: any) => {
        if (!param || !param.time || !seriesRef.current) {
          setLegend(null);
          return;
        }
        try {
          const t = param.time; // seconds or BusinessDay
          const p = param.seriesPrices?.get(seriesRef.current);
          if (p != null) {
            const ts =
              typeof t === 'number' ? new Date(t * 1000).toLocaleString() : JSON.stringify(t);
            setLegend({ time: ts, price: p });
          }
        } catch {
          // ignore
        }
      };
      chart.subscribeCrosshairMove(crosshairHandler);
      // Infinite history trigger on left edge
      const rangeHandler = (logicalRange: any) => {
        try {
          if (!logicalRange || typeof logicalRange.from !== 'number') return;
          // if user scrolls close to the first bar, ask for more data
          const leftGap = logicalRange.from;
          if (leftGap < 5 && typeof onNeedMore === 'function' && !loadingMoreRef.current) {
            const times = (candles || [])
              .map((c) =>
                typeof c.time === 'number'
                  ? Math.floor(c.time)
                  : Math.floor(new Date(c.time).getTime() / 1000)
              )
              .filter((t) => isFinite(t));
            if (!times.length) return;
            const minT = Math.min(...times);
            if (lastRequestedRef.current != null && lastRequestedRef.current === minT) return;
            lastRequestedRef.current = minT;
            loadingMoreRef.current = true;
            Promise.resolve(onNeedMore('left', minT))
              .catch(() => {})
              .finally(() => {
                loadingMoreRef.current = false;
              });
          }
        } catch {}
      };
      try {
        chart.timeScale().subscribeVisibleLogicalRangeChange(rangeHandler);
      } catch {}
      window.addEventListener('resize', onResize);
      return () => {
        window.removeEventListener('resize', onResize);
        try {
          roRef.current?.disconnect();
        } catch {}
        try {
          chart.unsubscribeCrosshairMove(crosshairHandler);
        } catch {}
        try {
          chart.timeScale().unsubscribeVisibleLogicalRangeChange(rangeHandler);
        } catch {}
        try {
          volumeRef.current = null;
        } catch {}
        chart.remove();
      };
    } catch {
      console.error('Failed to initialize TradingViewChart');
      return undefined;
    }
    // Intentionally re-create chart only on type change; other options are applied via separate effects
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartType]);

  useEffect(() => {
    if (!seriesRef.current || !chartRef.current) return;
    try {
      const mapped = candles.map((c) => ({
        time:
          typeof c.time === 'number'
            ? Math.floor(c.time)
            : Math.floor(new Date(c.time).getTime() / 1000),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));
      if (chartType === 'candlestick') {
        seriesRef.current.setData(mapped as any);
      } else {
        seriesRef.current.setData(
          mapped.map((d) => ({ time: d.time as number, value: d.close })) as any
        );
      }

      // Overlays
      const toSMA = (len: number) => {
        const out: Array<{ time: number; value: number }> = [];
        let sum = 0;
        const buf: number[] = [];
        for (const c of mapped) {
          buf.push(c.close);
          sum += c.close;
          if (buf.length > len) sum -= buf.shift()!;
          if (buf.length === len) out.push({ time: c.time as number, value: +(sum / len) });
        }
        return out;
      };

      if (showSMA20) {
        if (!sma20Ref.current)
          sma20Ref.current = addLineCompat(chartRef.current, { color: '#0288d1', lineWidth: 1 });
        sma20Ref.current.setData(toSMA(20) as any);
      } else if (sma20Ref.current) {
        sma20Ref.current.setData([]);
      }
      if (showSMA50) {
        if (!sma50Ref.current)
          sma50Ref.current = addLineCompat(chartRef.current, { color: '#7b1fa2', lineWidth: 1 });
        sma50Ref.current.setData(toSMA(50) as any);
      } else if (sma50Ref.current) {
        sma50Ref.current.setData([]);
      }
      // Update volume data if enabled and series exists
      if (showVolume && volumeRef.current) {
        const vdata = mapped.map((d) => ({
          time: d.time as number,
          value: (d as any).volume ?? 0,
        }));
        volumeRef.current.setData(vdata as any);
      }
    } catch {
      console.error('Failed to update chart data');
    }
  }, [candles, showSMA20, showSMA50, chartType, showVolume]);

  // Enhanced markers update (ТЗ 9.2 Step 3)
  useEffect(() => {
    if (!seriesRef.current) return;
    try {
      if (markers.length) {
        const enhancedMarkers = markers.map((m) => {
          // Determine if this is entry or exit marker
          const isEntry = m.is_entry !== undefined ? m.is_entry : !m.exit_time;

          // Base marker configuration
          let markerConfig: any = {
            time: Math.floor(m.time),
            position: m.side === 'buy' ? 'belowBar' : 'aboveBar',
          };

          // Color logic
          if (m.color) {
            markerConfig.color = m.color;
          } else if (isEntry) {
            // Entry markers: green for buy, red for sell
            markerConfig.color = m.side === 'buy' ? '#2e7d32' : '#c62828';
          } else {
            // Exit markers: different shades based on P&L
            if (m.pnl !== undefined) {
              markerConfig.color = m.pnl >= 0 ? '#1976d2' : '#d32f2f';
            } else {
              markerConfig.color = m.side === 'buy' ? '#1976d2' : '#ff6f00';
            }
          }

          // Shape logic
          if (isEntry) {
            markerConfig.shape = m.side === 'buy' ? 'arrowUp' : 'arrowDown';
          } else {
            // Exit markers: circles for exits
            markerConfig.shape = showExitMarkers
              ? 'circle'
              : m.side === 'buy'
                ? 'arrowDown'
                : 'arrowUp';
          }

          // Size scaling
          if (scaleMarkersBySize && m.size !== undefined) {
            // Normalize size: 0.5 to 2.0 scale
            const normalizedSize = Math.max(0.5, Math.min(2.0, m.size / 1.0));
            markerConfig.size = normalizedSize;
          }

          // Text/Tooltip
          if (m.label) {
            markerConfig.text = m.label;
          } else if (showMarkerTooltips) {
            if (isEntry) {
              markerConfig.text = `${m.side.toUpperCase()} ${m.price.toFixed(2)}`;
            } else if (m.pnl !== undefined && m.pnl_percent !== undefined) {
              const pnlSign = m.pnl >= 0 ? '+' : '';
              markerConfig.text = `EXIT ${m.price.toFixed(2)} (${pnlSign}${m.pnl_percent.toFixed(2)}%)`;
            } else {
              markerConfig.text = `EXIT ${m.price.toFixed(2)}`;
            }
          } else {
            markerConfig.text = `${m.side.toUpperCase()} ${m.price.toFixed(2)}`;
          }

          return markerConfig;
        });

        seriesRef.current.setMarkers(enhancedMarkers as any);
      } else {
        seriesRef.current.setMarkers([]);
      }
    } catch {
      console.error('Failed to update markers');
    }
  }, [markers, showMarkerTooltips, scaleMarkersBySize, showExitMarkers]);

  // Update TP/SL price lines when markers or priceLines change (ТЗ 9.2)
  useEffect(() => {
    if (!seriesRef.current) return;

    try {
      // Clear existing price lines
      priceLinesRef.current.forEach((line) => {
        try {
          seriesRef.current.removePriceLine(line);
        } catch {}
      });
      priceLinesRef.current = [];

      // Add TP/SL lines for each trade marker
      if (showTPSL && markers.length) {
        markers.forEach((marker) => {
          // Take Profit line
          if (marker.tp_price) {
            try {
              const tpLine = seriesRef.current.createPriceLine({
                price: marker.tp_price,
                color: '#4caf50',
                lineWidth: 2,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: `TP: ${marker.tp_price.toFixed(2)}`,
              });
              priceLinesRef.current.push(tpLine);
            } catch (e) {
              console.debug('Failed to create TP line:', e);
            }
          }

          // Stop Loss line
          if (marker.sl_price) {
            try {
              const slLine = seriesRef.current.createPriceLine({
                price: marker.sl_price,
                color: '#f44336',
                lineWidth: 2,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: `SL: ${marker.sl_price.toFixed(2)}`,
              });
              priceLinesRef.current.push(slLine);
            } catch (e) {
              console.debug('Failed to create SL line:', e);
            }
          }

          // Exit line (if different from TP/SL)
          if (
            marker.exit_price &&
            marker.exit_price !== marker.tp_price &&
            marker.exit_price !== marker.sl_price
          ) {
            try {
              const exitLine = seriesRef.current.createPriceLine({
                price: marker.exit_price,
                color: '#2196f3',
                lineWidth: 2,
                lineStyle: 1, // Dotted
                axisLabelVisible: true,
                title: `Exit: ${marker.exit_price.toFixed(2)}`,
              });
              priceLinesRef.current.push(exitLine);
            } catch (e) {
              console.debug('Failed to create Exit line:', e);
            }
          }
        });
      }

      // Custom price lines
      if (priceLines.length) {
        priceLines.forEach((pl) => {
          try {
            const lineStyle = pl.lineStyle === 'dotted' ? 1 : pl.lineStyle === 'dashed' ? 2 : 0;
            const line = seriesRef.current.createPriceLine({
              price: pl.price,
              color: pl.color,
              lineWidth: pl.lineWidth || 2,
              lineStyle: lineStyle,
              axisLabelVisible: pl.axisLabelVisible !== false,
              title: pl.title || '',
            });
            priceLinesRef.current.push(line);
          } catch (e) {
            console.debug('Failed to create custom price line:', e);
          }
        });
      }
    } catch (e) {
      console.error('Failed to update price lines:', e);
    }
  }, [markers, priceLines, showTPSL]);

  // React to scale mode and interactivity toggles on the fly
  useEffect(() => {
    if (!chartRef.current) return;
    try {
      chartRef.current.applyOptions({
        rightPriceScale: { mode: priceScaleModeFrom(scaleMode) },
        handleScroll: {
          mouseWheel: dragScroll,
          pressedMouseMove: dragScroll,
          horzTouchDrag: true,
          vertTouchDrag: true,
        },
        handleScale: { mouseWheel: wheelZoom, pinch: true, axisPressedMouseMove: true },
      });
      // Recreate or move volume scale as needed
      if (volumeRef.current) {
        volumeRef.current.applyOptions({ priceScaleId: volumeScale === 'left' ? 'left' : 'right' });
      } else if (showVolume && chartRef.current) {
        try {
          volumeRef.current = addHistogramCompat(chartRef.current, {
            priceScaleId: volumeScale === 'left' ? 'left' : 'right',
            color: 'rgba(124,179,66,0.7)',
            base: 0,
            lineWidth: 1,
            priceFormat: { type: 'volume' },
            scaleMargins: { top: 0.8, bottom: 0 },
          });
        } catch {}
      }
    } catch {}
  }, [scaleMode, wheelZoom, dragScroll, showVolume, volumeScale]);

  return (
    <div ref={ref} style={{ width: '100%', height: '100%', minHeight: 320, position: 'relative' }}>
      {showLegend && legend && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            left: 8,
            background: 'rgba(0,0,0,0.6)',
            color: '#fff',
            fontSize: 12,
            padding: '6px 8px',
            borderRadius: 4,
            pointerEvents: 'none',
          }}
        >
          <div>{legend.time}</div>
          <div>
            {typeof legend.price === 'number'
              ? `Price: ${legend.price}`
              : `O:${legend.price.open} H:${legend.price.high} L:${legend.price.low} C:${legend.price.close}`}
          </div>
        </div>
      )}
    </div>
  );
};

export default TradingViewChart;
