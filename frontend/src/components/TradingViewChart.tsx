import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

interface Candle { time: string | number; open: number; high: number; low: number; close: number }

const TradingViewChart: React.FC<{ candles: Candle[] }> = ({ candles }) => {
  const ref = useRef<HTMLDivElement | null>(null);
  const seriesRef = useRef<any>(null);

  useEffect(() => {
    if (!ref.current) return;
    // use any types to avoid heavyweight generic conflicts with the lib types
    const chart: any = createChart(ref.current, { width: ref.current.clientWidth, height: 300 });
    const candleSeries: any = chart.addCandlestickSeries();
    seriesRef.current = candleSeries;
    const mapped = candles.map((c) => ({ time: typeof c.time === 'number' ? Math.floor(c.time) : Math.floor(new Date(c.time).getTime() / 1000), open: c.open, high: c.high, low: c.low, close: c.close }));
    seriesRef.current.setData(mapped as any);

    const onResize = () => chart.applyOptions({ width: ref.current!.clientWidth });
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (seriesRef.current) {
      const mapped = candles.map((c) => ({ time: typeof c.time === 'number' ? Math.floor(c.time) : Math.floor(new Date(c.time).getTime() / 1000), open: c.open, high: c.high, low: c.low, close: c.close }));
      seriesRef.current.setData(mapped as any);
    }
  }, [candles]);

  return <div ref={ref} style={{ width: '100%' }} />;
};

export default TradingViewChart;
