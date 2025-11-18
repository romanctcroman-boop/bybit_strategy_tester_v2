import React, {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createChart, CandlestickSeries } from 'lightweight-charts';

// Initial visible window in bars. Can be overridden via VITE_INITIAL_VISIBLE_BARS
const INITIAL_VISIBLE_BARS: number = Number(
  (import.meta as any).env?.VITE_INITIAL_VISIBLE_BARS ?? 70
);
const RIGHT_OFFSET_BARS: number = Number((import.meta as any).env?.VITE_RIGHT_OFFSET_BARS ?? 3);

type Props = {
  candles: any[];
  datasetKey?: string;
  interval?: string;
};

export interface SimpleChartHandle {
  getChart: () => any | null;
  getTimeScale: () => any | null;
  getMainSeries: () => any | null;
  scrollToRealtime: () => void;
  // For DrawingLayer compatibility
  container: HTMLDivElement | null;
  priceToCoordinate: (price: number) => number | null;
  coordinateToPrice: (y: number) => number | null;
  timeToCoordinate: (timeSec: number) => number | null;
  coordinateToTime: (x: number) => number | undefined;
}

function intervalToSeconds(interval?: string): number {
  if (!interval) return 60; // default 1m
  const iv = String(interval).toUpperCase();
  if (iv === 'D') return 86400;
  if (iv === 'W') return 7 * 86400;
  const n = parseInt(iv, 10);
  if (!isNaN(n)) return n * 60;
  return 60;
}

const SimpleChart = forwardRef<SimpleChartHandle, Props>(
  ({ candles, datasetKey = 'default', interval = '1' }, ref) => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const chartRef = useRef<any>(null);
    const mainSeriesRef = useRef<any>(null);
    const wrapperRef = useRef<HTMLDivElement | null>(null);
    const lastDatasetKeyRef = useRef<string>('');
    const [isInitialized, setIsInitialized] = useState(false);

    const barSeconds = useMemo(() => intervalToSeconds(interval), [interval]);

    // Initialize chart ONCE
    useEffect(() => {
      if (!containerRef.current) return;
      const container = containerRef.current;
      const width = container.clientWidth || 800;
      const height = container.clientHeight || 600;

      const chart = createChart(container, {
        width,
        height,
        layout: { textColor: '#D1D5DB', background: { color: '#111827' } },
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
          rightOffset: RIGHT_OFFSET_BARS,
          fixLeftEdge: false, // Разрешить скролл влево
          fixRightEdge: false, // Разрешить скролл вправо
          lockVisibleTimeRangeOnResize: false, // Разрешить изменение видимого диапазона при resize
          rightBarStaysOnScroll: false, // Разрешить движение бара при скролле
          shiftVisibleRangeOnNewBar: false, // НЕ сдвигать автоматически при новых данных
        },
        rightPriceScale: { visible: true },
        crosshair: {
          mode: 1, // CrosshairMode.Normal - магнитное прилипание к данным
        },
        handleScroll: {
          mouseWheel: true, // Скролл колесиком мыши
          pressedMouseMove: true, // Перетаскивание графика зажатой мышкой (НЕ масштабирование!)
          horzTouchDrag: true,
          vertTouchDrag: true,
        },
        handleScale: {
          axisPressedMouseMove: false, // ОТКЛЮЧЕНО - иначе график растягивается вместо скролла
          mouseWheel: true, // Зум колесиком работает
          pinch: true,
        },
        kineticScroll: {
          mouse: false, // Плавная прокрутка мышкой (может мешать точному позиционированию)
          touch: true, // Плавная прокрутка touch-жестами
        },
      });
      chartRef.current = chart;
      // Default series - will be reconfigured by chartType effect
      const initialSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#10B981',
        downColor: '#EF4444',
        wickUpColor: '#10B981',
        wickDownColor: '#EF4444',
        // Price line options (горизонтальная линия текущей цены)
        lastValueVisible: true, // Метка текущей цены на правой оси
        priceLineVisible: true, // Горизонтальная линия
        priceLineStyle: 3, // LineStyle.Dashed
        priceLineWidth: 1,
        // priceLineColor будет автоматически по цвету последней свечи
      });
      mainSeriesRef.current = initialSeries;

      const handleResize = () => {
        if (!containerRef.current || !chartRef.current) return;
        const w = containerRef.current.clientWidth;
        const h = containerRef.current.clientHeight;
        if (w > 0 && h > 0) chartRef.current.applyOptions({ width: w, height: h });
      };
      // Observe container size directly for true responsiveness (not only window)
      let ro: ResizeObserver | null = null;
      try {
        ro = new ResizeObserver(() => handleResize());
        ro.observe(container);
      } catch {}
      window.addEventListener('resize', handleResize);

      setIsInitialized(true);
      return () => {
        window.removeEventListener('resize', handleResize);
        try {
          if (ro) ro.disconnect();
        } catch {}
        try {
          chartRef.current?.remove();
        } catch {}
        chartRef.current = null;
        mainSeriesRef.current = null;
      };
    }, []);

    // Expose handle for external access (DrawingLayer compatibility)
    useImperativeHandle(
      ref,
      () => ({
        getChart: () => chartRef.current,
        getTimeScale: () => chartRef.current?.timeScale() ?? null,
        getMainSeries: () => mainSeriesRef.current,
        scrollToRealtime: () => {
          if (!chartRef.current) return;
          chartRef.current.timeScale().scrollToRealTime();
        },
        // DrawingLayer needs these methods
        container: containerRef.current,
        priceToCoordinate: (price: number) =>
          mainSeriesRef.current?.priceToCoordinate(price) ?? null,
        coordinateToPrice: (y: number) => mainSeriesRef.current?.coordinateToPrice(y) ?? null,
        timeToCoordinate: (timeSec: number) =>
          chartRef.current?.timeScale()?.timeToCoordinate?.(timeSec as any) ?? null,
        coordinateToTime: (x: number) => {
          const t = chartRef.current?.timeScale()?.coordinateToTime?.(x) as any;
          if (typeof t === 'number') return t; // UTCTimestamp seconds
          return undefined;
        },
      }),
      []
    );

    // Track last candle count and time to detect if we need full setData or just update
    const lastCandleCountRef = useRef<number>(0);
    const lastCandleTimeRef = useRef<number>(0);

    // Create/update main series when dataset, interval, or chartType changes
    useEffect(() => {
      if (!isInitialized || !chartRef.current) return;
      if (!candles || candles.length === 0) return;

      const chart = chartRef.current;

      // Normalize and sort OHLC
      const sorted = [...candles].sort((a, b) => {
        const aTime = (a.open_time ?? 0) || a.time;
        const bTime = (b.open_time ?? 0) || b.time;
        return aTime - bTime;
      });
      const raw = sorted.map((c) => {
        const t =
          typeof c.time === 'number'
            ? c.time < 1e11
              ? c.time
              : Math.floor(c.time / 1000)
            : Math.floor(Number(c.open_time || 0) / 1000);
        return {
          time: t,
          open: Number(c.open),
          high: Number(c.high),
          low: Number(c.low),
          close: Number(c.close),
        };
      });
      // Deduplicate equal timestamps
      const dataOHLC: Array<{
        time: number;
        open: number;
        high: number;
        low: number;
        close: number;
      }> = [];
      let prevT: number | null = null;
      for (const d of raw) {
        const t = Number(d.time);
        if (prevT === null || t > prevT) {
          dataOHLC.push(d);
          prevT = t;
        } else if (t === prevT) {
          dataOHLC[dataOHLC.length - 1] = d;
        }
      }

      // Общие опции для price line (применяются ко всем типам графиков)
      const priceLineOptions = {
        lastValueVisible: true, // Метка текущей цены на правой оси
        priceLineVisible: true, // Горизонтальная линия
        priceLineStyle: 3, // LineStyle.Dashed
        priceLineWidth: 1,
      };

      // Create Japanese candlestick series if not exists
      if (!mainSeriesRef.current) {
        const s = chart.addSeries(CandlestickSeries, {
          upColor: '#10B981',
          downColor: '#EF4444',
          wickUpColor: '#10B981',
          wickDownColor: '#EF4444',
          ...priceLineOptions,
        });
        mainSeriesRef.current = s;
        // Force full setData on first create
        lastCandleCountRef.current = 0;
      }

      // Optimize: use update() for forming candle instead of setData() for all data
      const currentCount = dataOHLC.length;
      const lastCandle = dataOHLC[dataOHLC.length - 1];
      const lastTime = lastCandle ? lastCandle.time : 0;
      const datasetChanged = lastDatasetKeyRef.current !== datasetKey;

      // Use incremental update if only last candle changed (forming candle update)
      const useIncrementalUpdate =
        !datasetChanged &&
        currentCount > 0 &&
        currentCount === lastCandleCountRef.current &&
        lastTime === lastCandleTimeRef.current;

      if (useIncrementalUpdate && lastCandle) {
        // Incremental update for forming candle - much faster, no flicker
        try {
          mainSeriesRef.current.update(lastCandle as any);
        } catch {
          // Fallback to setData if update fails
          mainSeriesRef.current.setData(dataOHLC as any);
        }
      } else {
        // Full setData for: initial load, new candle, interval change
        mainSeriesRef.current.setData(dataOHLC as any);
      }

      // Update tracking refs
      lastCandleCountRef.current = currentCount;
      lastCandleTimeRef.current = lastTime;

      // When dataset key changes (e.g., interval), reset visible range to last N bars
      if (lastDatasetKeyRef.current !== datasetKey) {
        const last = dataOHLC[dataOHLC.length - 1];
        const first = dataOHLC[0];
        if (last && first) {
          const to = Number(last.time);
          const fromDesired = to - INITIAL_VISIBLE_BARS * barSeconds;
          const from = Math.max(fromDesired, Number(first.time));
          try {
            chart.timeScale().setVisibleRange({ from, to });
          } catch {}
          try {
            chart.timeScale().applyOptions({ rightOffset: RIGHT_OFFSET_BARS });
          } catch {}
        }
        lastDatasetKeyRef.current = datasetKey;
      }
    }, [isInitialized, candles, datasetKey, barSeconds]);

    // Resize main chart to fill wrapper
    useEffect(() => {
      const wrap = wrapperRef.current;
      if (!wrap) return;
      const ro = new ResizeObserver(() => {
        const rect = wrap.getBoundingClientRect();
        const w = Math.max(1, Math.floor(rect.width));
        const h = Math.max(320, Math.floor(rect.height));
        if (containerRef.current && chartRef.current) {
          containerRef.current.style.width = `${w}px`;
          containerRef.current.style.height = `${h}px`;
          chartRef.current.applyOptions({ width: w, height: h });
        }
      });
      ro.observe(wrap);
      return () => ro.disconnect();
    }, []);

    return (
      <div
        ref={wrapperRef}
        style={{
          width: '100%',
          height: '100%',
          minHeight: '320px',
          backgroundColor: '#111827',
          position: 'relative',
        }}
      >
        <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      </div>
    );
  }
);

SimpleChart.displayName = 'SimpleChart';

export default SimpleChart;
