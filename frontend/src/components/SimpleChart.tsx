import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createChart, CandlestickSeries } from 'lightweight-charts';

// Initial visible window in bars. Can be overridden via VITE_INITIAL_VISIBLE_BARS
const INITIAL_VISIBLE_BARS: number = Number((import.meta as any).env?.VITE_INITIAL_VISIBLE_BARS ?? 70);
const RIGHT_OFFSET_BARS: number = Number((import.meta as any).env?.VITE_RIGHT_OFFSET_BARS ?? 3);

type Props = { candles: any[]; datasetKey?: string; interval?: string };

function intervalToSeconds(interval?: string): number {
  if (!interval) return 60; // default 1m
  const iv = String(interval).toUpperCase();
  if (iv === 'D') return 86400;
  if (iv === 'W') return 7 * 86400;
  const n = parseInt(iv, 10);
  if (!isNaN(n)) return n * 60;
  return 60;
}

const SimpleChart: React.FC<Props> = ({ candles, datasetKey = 'default', interval = '1' }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<any>(null);
  const candleSeriesRef = useRef<any>(null);
  const lastCandleCountRef = useRef<number>(0);
  const lastBarTimeRef = useRef<number | null>(null); // UTCTimestamp seconds
  const lastDatasetKeyRef = useRef<string>('');
  const [isInitialized, setIsInitialized] = useState(false);

  const barSeconds = useMemo(() => intervalToSeconds(interval), [interval]);

  // Initialize chart ONCE
  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 800;

    const chart = createChart(container, {
      width,
      height,
      layout: { textColor: '#D1D5DB', background: { color: '#111827' } },
      timeScale: { timeVisible: true, secondsVisible: false, rightOffset: RIGHT_OFFSET_BARS },
      rightPriceScale: { visible: true },
    });
    chartRef.current = chart;
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10B981',
      downColor: '#EF4444',
      wickUpColor: '#10B981',
      wickDownColor: '#EF4444',
    });
    candleSeriesRef.current = candleSeries;

    const handleResize = () => {
      if (!containerRef.current || !chartRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      if (w > 0 && h > 0) chartRef.current.applyOptions({ width: w, height: h });
    };
    window.addEventListener('resize', handleResize);
    setIsInitialized(true);
    return () => {
      window.removeEventListener('resize', handleResize);
      try { chartRef.current?.remove(); } catch {}
      chartRef.current = null;
      candleSeriesRef.current = null;
    };
  }, []);

  // Incremental updates: setData once, then update/append bars
  useEffect(() => {
    if (!isInitialized || !candleSeriesRef.current) return;
    const series = candleSeriesRef.current;
    if (!candles || candles.length === 0) return;

    const isNewDataset = lastDatasetKeyRef.current !== datasetKey;

    // Normalize and sort
    const sorted = [...candles].sort((a, b) => {
      const aTime = (a.open_time ?? 0) || a.time;
      const bTime = (b.open_time ?? 0) || b.time;
      return aTime - bTime;
    });
    const dataRaw = sorted.map((c) => {
      // Convert to UTCTimestamp seconds accepted by lightweight-charts
      if (typeof c.time === 'number') {
        // If seconds already
        const t = c.time < 1e11 ? c.time : Math.floor(c.time / 1000);
        return {
          time: t,
          open: Number(c.open),
          high: Number(c.high),
          low: Number(c.low),
          close: Number(c.close),
        };
      }
      const ms = c.open_time ? Number(c.open_time) : 0;
      const t = Math.floor(ms / 1000);
      return {
        time: t,
        open: Number(c.open),
        high: Number(c.high),
        low: Number(c.low),
        close: Number(c.close),
      };
    });
    // Deduplicate equal timestamps (keep the last seen bar)
    const data: Array<{ time: number; open: number; high: number; low: number; close: number }> = [];
    let prevT: number | null = null;
    for (const d of dataRaw) {
      const t = Number(d.time);
      if (prevT === null || t > prevT) {
        data.push(d);
        prevT = t;
      } else if (t === prevT) {
        data[data.length - 1] = d;
      }
    }

    const prevCount = isNewDataset ? 0 : lastCandleCountRef.current;
    const currCount = data.length;

    if (prevCount === 0) {
      // Initial set
      series.setData(data as any);
      lastCandleCountRef.current = currCount;
      const last = data[data.length - 1];
      const first = data[0];
      lastBarTimeRef.current = last?.time ?? null;
      // Show last N minutes on init (match desired initial zoom)
      if (last && first && chartRef.current) {
        const to = Number(last.time);
        const fromDesired = to - INITIAL_VISIBLE_BARS * barSeconds;
        const from = Math.max(fromDesired, Number(first.time));
        try { chartRef.current.timeScale().setVisibleRange({ from, to }); } catch {}
        // Ensure right padding is applied after setting visible range
        try { chartRef.current.timeScale().applyOptions({ rightOffset: RIGHT_OFFSET_BARS }); } catch {}
      }
      lastDatasetKeyRef.current = datasetKey;
      return;
    }

    const lastIncoming = data[data.length - 1];
    if (!lastIncoming) return;

    if (currCount > prevCount) {
      // One or more new bars appended; append those with time > lastBarTimeRef
      for (let i = prevCount; i < currCount; i++) {
        const bar = data[i];
        if (!bar) continue;
        if (lastBarTimeRef.current == null || bar.time > lastBarTimeRef.current) {
          series.update(bar as any);
          lastBarTimeRef.current = bar.time as number;
        }
      }
      lastCandleCountRef.current = currCount;
      return;
    }

    // Same count: just update last bar (forming candle)
    series.update(lastIncoming as any);
    lastBarTimeRef.current = lastIncoming.time as number;
    lastDatasetKeyRef.current = datasetKey;
  }, [candles, isInitialized, datasetKey, barSeconds]);

  return <div 
    ref={containerRef} 
    style={{ 
      width: '100%', 
      height: '100%',
      minHeight: '800px',
      backgroundColor: '#111827',
      display: 'block',
      overflow: 'visible',
    }} 
  />;
};

export default SimpleChart;
