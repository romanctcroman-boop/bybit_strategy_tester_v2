import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

interface Candle {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
}
interface TradeMarker {
  time: number;
  side: 'buy' | 'sell';
  price: number;
}
interface Props {
  candles: Candle[];
  markers?: TradeMarker[];
  showSMA20?: boolean;
  showSMA50?: boolean;
}

const TradingViewChart: React.FC<Props> = ({
  candles,
  markers = [],
  showSMA20 = true,
  showSMA50 = false,
}) => {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);
  const sma20Ref = useRef<any>(null);
  const sma50Ref = useRef<any>(null);

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

  useEffect(() => {
    if (!ref.current) return;
    try {
      const chart: any = createChart(ref.current, { width: ref.current.clientWidth, height: 480 });
      chartRef.current = chart;
      const candleSeries: any = addCandlesCompat(chart);
      seriesRef.current = candleSeries;
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
      candleSeries.setData(mapped as any);
      if (markers.length) {
        candleSeries.setMarkers(
          markers.map((m) => ({
            time: Math.floor(m.time),
            position: m.side === 'buy' ? 'belowBar' : 'aboveBar',
            color: m.side === 'buy' ? '#2e7d32' : '#c62828',
            shape: m.side === 'buy' ? 'arrowUp' : 'arrowDown',
            text: `${m.side.toUpperCase()} ${m.price}`,
          })) as any
        );
      }
      chart.timeScale().fitContent();

      const onResize = () => chart.applyOptions({ width: ref.current!.clientWidth });
      window.addEventListener('resize', onResize);
      return () => {
        window.removeEventListener('resize', onResize);
        chart.remove();
      };
    } catch {
      console.error('Failed to initialize TradingViewChart');
      return undefined;
    }
  }, [candles, markers]);

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
      seriesRef.current.setData(mapped as any);

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
    } catch {
      console.error('Failed to update chart data');
    }
  }, [candles, showSMA20, showSMA50]);

  useEffect(() => {
    if (!seriesRef.current) return;
    try {
      if (markers.length) {
        seriesRef.current.setMarkers(
          markers.map((m: any) => ({
            time: Math.floor(m.time),
            position: m.side === 'buy' ? 'belowBar' : 'aboveBar',
            color: m.side === 'buy' ? '#2e7d32' : '#c62828',
            shape: m.side === 'buy' ? 'arrowUp' : 'arrowDown',
            text: `${m.side.toUpperCase()} ${m.price}`,
          })) as any
        );
      } else {
        seriesRef.current.setMarkers([]);
      }
    } catch {
      console.error('Failed to update markers');
    }
  }, [markers]);

  return <div ref={ref} style={{ width: '100%', height: 480 }} />;
};

export default TradingViewChart;
