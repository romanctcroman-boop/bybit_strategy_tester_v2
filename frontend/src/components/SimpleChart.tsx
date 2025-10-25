import React, {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  BarSeries,
  AreaSeries,
  BaselineSeries,
  LineType,
  HistogramSeries,
} from 'lightweight-charts';

// Initial visible window in bars. Can be overridden via VITE_INITIAL_VISIBLE_BARS
const INITIAL_VISIBLE_BARS: number = Number(
  (import.meta as any).env?.VITE_INITIAL_VISIBLE_BARS ?? 70
);
const RIGHT_OFFSET_BARS: number = Number((import.meta as any).env?.VITE_RIGHT_OFFSET_BARS ?? 3);

type Props = {
  candles: any[];
  datasetKey?: string;
  interval?: string;
  showSMA20?: boolean;
  showEMA50?: boolean;
  showBB?: boolean; // Bollinger Bands (20, 2)
  showVWAP?: boolean; // VWAP overlay (daily reset)
  showRSI?: boolean; // RSI panel
  showMACD?: boolean; // MACD panel
  showSuperTrend?: boolean; // SuperTrend overlay
  showDonchian?: boolean; // Donchian Channels overlay
  showKeltner?: boolean; // Keltner Channels overlay
  chartType?:
    | 'bars'
    | 'candles'
    | 'hollow_candles'
    | 'line'
    | 'line_dots'
    | 'stepline'
    | 'area'
    | 'area_hlc'
    | 'baseline';
};

export type SimpleChartHandle = {
  container: HTMLDivElement | null;
  priceToCoordinate: (price: number) => number | null;
  coordinateToPrice: (y: number) => number | null;
  timeToCoordinate: (timeSec: number) => number | null | undefined;
  coordinateToTime: (x: number) => number | undefined;
};

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
  (
    {
      candles,
      datasetKey = 'default',
      interval = '1',
      showSMA20 = true,
      showEMA50 = false,
      showBB = false,
      showVWAP = false,
      showRSI = false,
      showMACD = false,
      showSuperTrend = false,
      showDonchian = false,
      showKeltner = false,
      chartType = 'hollow_candles',
    },
    ref
  ) => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const chartRef = useRef<any>(null);
    const mainSeriesRef = useRef<any>(null);
    const sma20Ref = useRef<any>(null);
    const ema50Ref = useRef<any>(null);
    const bbURef = useRef<any>(null);
    const bbMRef = useRef<any>(null);
    const bbLRef = useRef<any>(null);
    const wrapperRef = useRef<HTMLDivElement | null>(null);
    const rsiContainerRef = useRef<HTMLDivElement | null>(null);
    const macdContainerRef = useRef<HTMLDivElement | null>(null);
    const vwapRef = useRef<any>(null);
    const rsiChartRef = useRef<any>(null);
    const rsiSeriesRef = useRef<any>(null);
    const macdChartRef = useRef<any>(null);
    const macdLineRef = useRef<any>(null);
    const macdSignalRef = useRef<any>(null);
    const macdHistRef = useRef<any>(null);
    // Extra overlays
    const stUpRef = useRef<any>(null);
    const stDnRef = useRef<any>(null);
    const donchURef = useRef<any>(null);
    const donchMRef = useRef<any>(null);
    const donchLRef = useRef<any>(null);
    const keltURef = useRef<any>(null);
    const keltMRef = useRef<any>(null);
    const keltLRef = useRef<any>(null);
    const syncingRef = useRef<boolean>(false);
    const lastDatasetKeyRef = useRef<string>('');
    const lastChartTypeRef = useRef<Props['chartType'] | null>(null);
    const [isInitialized, setIsInitialized] = useState(false);
    // Crosshair sync overlay (vertical line across panes)
    const crosshairLineRef = useRef<HTMLDivElement | null>(null);

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
        timeScale: { timeVisible: true, secondsVisible: false, rightOffset: RIGHT_OFFSET_BARS },
        rightPriceScale: { visible: true },
      });
      chartRef.current = chart;
      // Default series - will be reconfigured by chartType effect
      const initialSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#10B981',
        downColor: '#EF4444',
        wickUpColor: '#10B981',
        wickDownColor: '#EF4444',
      });
      mainSeriesRef.current = initialSeries;

      // Precreate overlays (hidden by default)
      sma20Ref.current = chart.addSeries(LineSeries, { color: '#0288d1', lineWidth: 1 });
      ema50Ref.current = chart.addSeries(LineSeries, { color: '#7b1fa2', lineWidth: 1 });
      bbURef.current = chart.addSeries(LineSeries, {
        color: 'rgba(144,202,249,0.9)',
        lineWidth: 1,
      });
      bbMRef.current = chart.addSeries(LineSeries, {
        color: 'rgba(144,202,249,0.6)',
        lineWidth: 1,
      });
      bbLRef.current = chart.addSeries(LineSeries, {
        color: 'rgba(144,202,249,0.9)',
        lineWidth: 1,
      });
      vwapRef.current = chart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 2 });
      // Extra overlays create upfront
      stUpRef.current = chart.addSeries(LineSeries, {
        color: '#10b981',
        lineWidth: 2,
        lineType: LineType.WithSteps,
      });
      stDnRef.current = chart.addSeries(LineSeries, {
        color: '#ef4444',
        lineWidth: 2,
        lineType: LineType.WithSteps,
      });
      donchURef.current = chart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 1 });
      donchMRef.current = chart.addSeries(LineSeries, { color: '#9ca3af', lineWidth: 1 });
      donchLRef.current = chart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 1 });
      keltURef.current = chart.addSeries(LineSeries, { color: '#22c55e', lineWidth: 1 });
      keltMRef.current = chart.addSeries(LineSeries, { color: '#60a5fa', lineWidth: 1 });
      keltLRef.current = chart.addSeries(LineSeries, { color: '#22c55e', lineWidth: 1 });

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
        sma20Ref.current = null;
        ema50Ref.current = null;
        bbURef.current = null;
        bbMRef.current = null;
        bbLRef.current = null;
        vwapRef.current = null;
        stUpRef.current = null;
        stDnRef.current = null;
        donchURef.current = null;
        donchMRef.current = null;
        donchLRef.current = null;
        keltURef.current = null;
        keltMRef.current = null;
        keltLRef.current = null;
      };
    }, []);

    // Expose a minimal handle for drawing layer
    useImperativeHandle(
      ref,
      () => ({
        container: containerRef.current,
        priceToCoordinate: (price: number) =>
          mainSeriesRef.current?.priceToCoordinate(price) ?? null,
        coordinateToPrice: (y: number) => mainSeriesRef.current?.coordinateToPrice(y) ?? null,
        timeToCoordinate: (timeSec: number) =>
          chartRef.current?.timeScale()?.timeToCoordinate?.(timeSec as any),
        coordinateToTime: (x: number) => {
          const t = chartRef.current?.timeScale()?.coordinateToTime?.(x) as any;
          if (typeof t === 'number') return t; // UTCTimestamp seconds
          // if BusinessDay object, we can't reliably convert without a date lib; return undefined
          return undefined;
        },
      }),
      []
    );

    // Create/destroy RSI and MACD sub-charts when toggles change
    useEffect(() => {
      const ensureChart = (
        hostRef: React.RefObject<HTMLDivElement>,
        setChart: (c: any) => void
      ) => {
        const host = hostRef.current;
        if (!host) return null;
        const rect = host.getBoundingClientRect();
        const ch = createChart(host, {
          width: Math.max(1, Math.floor(rect.width || 800)),
          height: Math.max(100, Math.floor(rect.height || 140)),
          layout: { textColor: '#D1D5DB', background: { color: '#111827' } },
          timeScale: { timeVisible: true, secondsVisible: false },
          rightPriceScale: { visible: true },
        });
        setChart(ch);
        return ch;
      };

      const destroy = (ch: any) => {
        try {
          ch?.remove?.();
        } catch {}
      };

      if (showRSI && !rsiChartRef.current && rsiContainerRef.current) {
        const ch = ensureChart(rsiContainerRef, (c) => (rsiChartRef.current = c));
        if (ch) {
          rsiSeriesRef.current = ch.addSeries(LineSeries, { color: '#f97316', lineWidth: 1 });
        }
      } else if (!showRSI && rsiChartRef.current) {
        destroy(rsiChartRef.current);
        rsiChartRef.current = null;
        rsiSeriesRef.current = null;
      }

      if (showMACD && !macdChartRef.current && macdContainerRef.current) {
        const ch = ensureChart(macdContainerRef, (c) => (macdChartRef.current = c));
        if (ch) {
          macdLineRef.current = ch.addSeries(LineSeries, { color: '#60a5fa', lineWidth: 1 });
          macdSignalRef.current = ch.addSeries(LineSeries, { color: '#f43f5e', lineWidth: 1 });
          macdHistRef.current = ch.addSeries(HistogramSeries, { base: 0 } as any);
        }
      } else if (!showMACD && macdChartRef.current) {
        destroy(macdChartRef.current);
        macdChartRef.current = null;
        macdLineRef.current = null;
        macdSignalRef.current = null;
        macdHistRef.current = null;
      }
    }, [showRSI, showMACD]);

    // Sync time scales between panes
    useEffect(() => {
      if (!chartRef.current) return;
      const mainTS = chartRef.current.timeScale();
      const handlers: Array<() => void> = [];
      const syncTo = (range: any) => {
        if (!range) return;
        if (syncingRef.current) return;
        syncingRef.current = true;
        try {
          rsiChartRef.current?.timeScale().setVisibleRange(range);
          macdChartRef.current?.timeScale().setVisibleRange(range);
        } catch {}
        syncingRef.current = false;
      };
      const syncFrom = (srcChart: any) => (range: any) => {
        if (!range) return;
        if (syncingRef.current) return;
        syncingRef.current = true;
        try {
          const ts = range;
          if (srcChart !== chartRef.current) mainTS.setVisibleRange(ts);
          if (srcChart !== rsiChartRef.current && rsiChartRef.current)
            rsiChartRef.current.timeScale().setVisibleRange(ts);
          if (srcChart !== macdChartRef.current && macdChartRef.current)
            macdChartRef.current.timeScale().setVisibleRange(ts);
        } catch {}
        syncingRef.current = false;
      };
      // seed current range
      try {
        const r = mainTS.getVisibleRange?.();
        if (r) syncTo(r);
      } catch {}
      const hMain = (r: any) => syncFrom(chartRef.current)(r);
      mainTS.subscribeVisibleTimeRangeChange(hMain);
      handlers.push(() => mainTS.unsubscribeVisibleTimeRangeChange(hMain));
      if (rsiChartRef.current) {
        const ts = rsiChartRef.current.timeScale();
        const h = (r: any) => syncFrom(rsiChartRef.current)(r);
        ts.subscribeVisibleTimeRangeChange(h);
        handlers.push(() => ts.unsubscribeVisibleTimeRangeChange(h));
      }
      if (macdChartRef.current) {
        const ts = macdChartRef.current.timeScale();
        const h = (r: any) => syncFrom(macdChartRef.current)(r);
        ts.subscribeVisibleTimeRangeChange(h);
        handlers.push(() => ts.unsubscribeVisibleTimeRangeChange(h));
      }
      return () => {
        for (const u of handlers) {
          try {
            u();
          } catch {}
        }
      };
    }, [showRSI, showMACD, isInitialized]);

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
      const dataLine = dataOHLC.map((d) => ({ time: d.time as any, value: d.close }));

      const needRecreate = !mainSeriesRef.current || lastChartTypeRef.current !== chartType;
      if (needRecreate) {
        try {
          if (mainSeriesRef.current) chart.removeSeries(mainSeriesRef.current);
        } catch {}
        let s: any;
        switch (chartType) {
          case 'bars':
            s = chart.addSeries(BarSeries, {
              upColor: '#10B981',
              downColor: '#EF4444',
              thinBars: false,
            });
            break;
          case 'candles':
            s = chart.addSeries(CandlestickSeries, {
              upColor: '#10B981',
              downColor: '#EF4444',
              wickUpColor: '#10B981',
              wickDownColor: '#EF4444',
            });
            break;
          case 'hollow_candles':
            s = chart.addSeries(CandlestickSeries, {
              upColor: 'rgba(0,0,0,0)',
              downColor: 'rgba(0,0,0,0)',
              borderUpColor: '#10B981',
              borderDownColor: '#EF4444',
              wickUpColor: '#10B981',
              wickDownColor: '#EF4444',
            } as any);
            break;
          case 'line':
            s = chart.addSeries(LineSeries, { color: '#60A5FA', lineWidth: 2 });
            break;
          case 'line_dots':
            s = chart.addSeries(LineSeries, { color: '#60A5FA', lineWidth: 2 });
            break;
          case 'stepline':
            s = chart.addSeries(LineSeries, {
              color: '#60A5FA',
              lineWidth: 2,
              lineType: LineType.WithSteps,
            });
            break;
          case 'area':
          case 'area_hlc':
            s = chart.addSeries(AreaSeries, {
              lineColor: '#60A5FA',
              topColor: 'rgba(96,165,250,0.3)',
              bottomColor: 'rgba(96,165,250,0.05)',
              lineWidth: 2,
            });
            break;
          case 'baseline':
            s = chart.addSeries(BaselineSeries, {
              baseValue: { type: 'price', price: dataLine.length ? dataLine[0].value : 0 },
              topLineColor: '#10B981',
              topFillColor1: 'rgba(16,185,129,0.25)',
              topFillColor2: 'rgba(16,185,129,0.05)',
              bottomLineColor: '#EF4444',
              bottomFillColor1: 'rgba(239,68,68,0.25)',
              bottomFillColor2: 'rgba(239,68,68,0.05)',
              lineWidth: 2,
            } as any);
            break;
          default:
            s = chart.addSeries(CandlestickSeries, {
              upColor: '#10B981',
              downColor: '#EF4444',
              wickUpColor: '#10B981',
              wickDownColor: '#EF4444',
            });
        }
        mainSeriesRef.current = s;
        lastChartTypeRef.current = chartType;
      }

      // Set data according to type
      if (chartType === 'bars' || chartType === 'candles' || chartType === 'hollow_candles') {
        mainSeriesRef.current.setData(dataOHLC as any);
      } else {
        mainSeriesRef.current.setData(dataLine as any);
        if (chartType === 'line_dots') {
          try {
            const markers = dataLine.map((p) => ({
              time: p.time as any,
              position: 'inBar',
              color: '#93C5FD',
              shape: 'circle' as any,
              size: 1,
            }));
            mainSeriesRef.current.setMarkers(markers);
          } catch {}
        } else {
          try {
            mainSeriesRef.current.setMarkers?.([]);
          } catch {}
        }
      }

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
    }, [isInitialized, candles, datasetKey, barSeconds, chartType]);

    // Calculate and paint overlays and indicator panels
    useEffect(() => {
      if (!isInitialized || !chartRef.current || !mainSeriesRef.current) return;
      if (!candles || candles.length === 0) return;

      // Map candles
      const sorted = [...candles]
        .sort((a, b) => (a.open_time ?? a.time) - (b.open_time ?? b.time))
        .map((c) => ({
          time:
            typeof c.time === 'number'
              ? c.time < 1e11
                ? c.time
                : Math.floor(c.time / 1000)
              : Math.floor(Number(c.open_time || 0) / 1000),
          open: Number(c.open),
          high: Number(c.high),
          low: Number(c.low),
          close: Number(c.close),
          volume: c.volume != null ? Number(c.volume) : 0,
        }))
        .filter((d) => isFinite(d.time) && isFinite(d.close));

      const data = sorted.map((d) => ({ time: d.time, close: d.close }));

      const lineData = (arr: Array<{ time: number; value: number }>) =>
        arr.filter((p) => Number.isFinite(p.time) && Number.isFinite(p.value)) as any;

      // EMA with SMA seed (closer to TV/TA-Lib behavior)
      const emaWithSMASeed = (values: number[], period: number): number[] => {
        const out = new Array(values.length).fill(NaN);
        if (values.length === 0) return out;
        const k = 2 / (period + 1);
        if (values.length >= period) {
          let sum = 0;
          for (let i = 0; i < period; i++) sum += values[i];
          let ema = sum / period;
          out[period - 1] = ema;
          for (let i = period; i < values.length; i++) {
            const v = values[i];
            ema = v * k + ema * (1 - k);
            out[i] = ema;
          }
        } else {
          // Fallback if insufficient data: simple seed
          let ema = values[0];
          out[0] = ema;
          for (let i = 1; i < values.length; i++) {
            const v = values[i];
            ema = v * k + ema * (1 - k);
            out[i] = ema;
          }
        }
        return out;
      };

      const computeATR = (len = 14) => {
        const trArr: number[] = [];
        let prevClose: number | null = null;
        for (const d of sorted) {
          const hl = d.high - d.low;
          const hc = prevClose == null ? hl : Math.abs(d.high - prevClose);
          const lc = prevClose == null ? hl : Math.abs(d.low - prevClose);
          const tr = Math.max(hl, hc, lc);
          trArr.push(tr);
          prevClose = d.close;
        }
        // Wilder's smoothing (RMA)
        const out: number[] = [];
        let rma: number | null = null;
        for (let i = 0; i < trArr.length; i++) {
          const v = trArr[i];
          if (rma == null) {
            if (i < len) {
              // seed with SMA for first len
              // accumulate until i === len-1
              if (i === len - 1) {
                const sma = trArr.slice(0, len).reduce((a, b) => a + b, 0) / len;
                rma = sma;
                out.push(rma);
              } else {
                out.push(NaN);
              }
            }
          } else {
            rma = (rma * (len - 1) + v) / len;
            out.push(rma);
          }
        }
        return out;
      };

      // SMA20
      if (sma20Ref.current) {
        if (showSMA20) {
          const len = 20;
          const out: Array<{ time: number; value: number }> = [];
          let sum = 0;
          const buf: number[] = [];
          for (const d of data) {
            buf.push(d.close);
            sum += d.close;
            if (buf.length > len) sum -= buf.shift()!;
            if (buf.length === len) out.push({ time: d.time, value: +(sum / len) });
          }
          sma20Ref.current.setData(lineData(out));
        } else {
          sma20Ref.current.setData([]);
        }
      }

      // EMA50
      if (ema50Ref.current) {
        if (showEMA50) {
          const len = 50;
          const k = 2 / (len + 1);
          const out: Array<{ time: number; value: number }> = [];
          let ema: number | null = null;
          for (const d of data) {
            if (ema == null) {
              ema = d.close; // seed with first value
            } else {
              ema = d.close * k + ema * (1 - k);
            }
            out.push({ time: d.time, value: +ema });
          }
          ema50Ref.current.setData(lineData(out.slice(len - 1)));
        } else {
          ema50Ref.current.setData([]);
        }
      }

      // Bollinger Bands (20, 2)
      if (bbURef.current && bbMRef.current && bbLRef.current) {
        if (showBB) {
          const len = 20;
          const mult = 2;
          const upper: Array<{ time: number; value: number }> = [];
          const middle: Array<{ time: number; value: number }> = [];
          const lower: Array<{ time: number; value: number }> = [];
          const buf: number[] = [];
          for (const d of data) {
            buf.push(d.close);
            if (buf.length > len) buf.shift();
            if (buf.length === len) {
              const mean = buf.reduce((a, b) => a + b, 0) / len;
              const variance = buf.reduce((a, b) => a + (b - mean) * (b - mean), 0) / len;
              const stdev = Math.sqrt(variance);
              middle.push({ time: d.time, value: +mean });
              upper.push({ time: d.time, value: +(mean + mult * stdev) });
              lower.push({ time: d.time, value: +(mean - mult * stdev) });
            }
          }
          bbURef.current.setData(lineData(upper));
          bbMRef.current.setData(lineData(middle));
          bbLRef.current.setData(lineData(lower));
        } else {
          bbURef.current.setData([]);
          bbMRef.current.setData([]);
          bbLRef.current.setData([]);
        }
      }

      // VWAP (daily reset)
      if (vwapRef.current) {
        if (showVWAP) {
          const out: Array<{ time: number; value: number }> = [];
          let curDay: number | null = null;
          let cumPV = 0;
          let cumVol = 0;
          for (const d of sorted) {
            const day = Math.floor(d.time / 86400);
            if (curDay === null || day !== curDay) {
              curDay = day;
              cumPV = 0;
              cumVol = 0;
            }
            const typical = (d.high + d.low + d.close) / 3;
            const vol = d.volume || 0;
            cumPV += typical * vol;
            cumVol += vol;
            if (cumVol > 0) out.push({ time: d.time, value: +(cumPV / cumVol) });
          }
          vwapRef.current.setData(lineData(out));
        } else {
          vwapRef.current.setData([]);
        }
      }

      // RSI (14)
      if (rsiSeriesRef.current) {
        if (showRSI) {
          const len = 14;
          const out: Array<{ time: number; value: number }> = [];
          let avgGain = 0;
          let avgLoss = 0;
          for (let i = 1; i < data.length; i++) {
            const change = data[i].close - data[i - 1].close;
            const gain = change > 0 ? change : 0;
            const loss = change < 0 ? -change : 0;
            if (i <= len) {
              avgGain += gain;
              avgLoss += loss;
              if (i === len) {
                avgGain /= len;
                avgLoss /= len;
                const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
                const rsi = 100 - 100 / (1 + rs);
                out.push({ time: data[i].time, value: +rsi });
              }
            } else {
              avgGain = (avgGain * (len - 1) + gain) / len;
              avgLoss = (avgLoss * (len - 1) + loss) / len;
              const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
              const rsi = 100 - 100 / (1 + rs);
              out.push({ time: data[i].time, value: +rsi });
            }
          }
          rsiSeriesRef.current.setData(lineData(out));
        } else {
          rsiSeriesRef.current.setData([]);
        }
      }

      // MACD (12, 26, 9) with histogram — EMAs seeded by SMA for closer TV match
      if (macdLineRef.current && macdSignalRef.current) {
        if (showMACD) {
          const closes = data.map((d) => d.close);
          const ema12 = emaWithSMASeed(closes, 12);
          const ema26 = emaWithSMASeed(closes, 26);
          const macdVals: number[] = closes.map((_, i) => ema12[i] - ema26[i]);
          const macdArr: Array<{ time: number; value: number }> = data.map((d, i) => ({
            time: d.time,
            value: macdVals[i],
          }));
          // Signal EMA with SMA seed on MACD values
          const sigPeriod = 9;
          const kSig = 2 / (sigPeriod + 1);
          const signalVals = new Array(macdVals.length).fill(NaN);
          const buf: number[] = [];
          let emaSig: number | null = null;
          for (let i = 0; i < macdVals.length; i++) {
            const v = macdVals[i];
            if (!isFinite(v)) continue;
            buf.push(v);
            if (buf.length < sigPeriod) {
              // wait
            } else if (buf.length === sigPeriod && emaSig == null) {
              const sma = buf.reduce((a, b) => a + b, 0) / sigPeriod;
              emaSig = sma;
              signalVals[i] = emaSig;
            } else if (emaSig != null) {
              emaSig = v * kSig + emaSig * (1 - kSig);
              signalVals[i] = emaSig;
            }
            if (buf.length > sigPeriod) buf.shift();
          }
          const signalArr: Array<{ time: number; value: number }> = data.map((d, i) => ({
            time: d.time,
            value: signalVals[i],
          }));
          macdLineRef.current.setData(lineData(macdArr));
          macdSignalRef.current.setData(lineData(signalArr));
          if (macdHistRef.current) {
            const hist = macdArr.map((m, i) => {
              const sig = signalVals[i];
              const v = m.value - sig;
              return { time: m.time, value: v, color: v >= 0 ? '#10B981' : '#EF4444' };
            });
            const histFiltered = hist.filter((h) => Number.isFinite(h.value));
            macdHistRef.current.setData(histFiltered as any);
          }
        } else {
          macdLineRef.current.setData([]);
          macdSignalRef.current.setData([]);
          if (macdHistRef.current) macdHistRef.current.setData([]);
        }
      }

      // SuperTrend (10, 3) — classic final band logic using previous close
      if (stUpRef.current && stDnRef.current) {
        if (showSuperTrend) {
          const len = 10;
          const mult = 3;
          const atr = computeATR(len);
          const up: Array<{ time: number; value: number }> = [];
          const dn: Array<{ time: number; value: number }> = [];
          let prevFinalUp: number | null = null;
          let prevFinalDn: number | null = null;
          let prevClose: number | null = null;
          let trendUp = false;
          for (let i = 0; i < sorted.length; i++) {
            const d = sorted[i];
            const hl2 = (d.high + d.low) / 2;
            const atrv = atr[i] ?? NaN;
            if (!isFinite(atrv)) {
              prevClose = d.close;
              continue;
            }
            const basicUp = hl2 + mult * atrv;
            const basicDn = hl2 - mult * atrv;
            // Final bands
            let finalUp = basicUp;
            if (prevFinalUp != null) {
              if (basicUp < prevFinalUp || (prevClose != null && prevClose > prevFinalUp)) {
                finalUp = basicUp;
              } else {
                finalUp = prevFinalUp;
              }
            }
            let finalDn = basicDn;
            if (prevFinalDn != null) {
              if (basicDn > prevFinalDn || (prevClose != null && prevClose < prevFinalDn)) {
                finalDn = basicDn;
              } else {
                finalDn = prevFinalDn;
              }
            }
            // Trend switch
            if (!trendUp && d.close > (prevFinalUp ?? finalUp)) trendUp = true;
            else if (trendUp && d.close < (prevFinalDn ?? finalDn)) trendUp = false;

            if (trendUp) up.push({ time: d.time, value: finalDn });
            else dn.push({ time: d.time, value: finalUp });

            prevFinalUp = finalUp;
            prevFinalDn = finalDn;
            prevClose = d.close;
          }
          stUpRef.current.setData(lineData(up as any));
          stDnRef.current.setData(lineData(dn as any));
        } else {
          stUpRef.current.setData([]);
          stDnRef.current.setData([]);
        }
      }

      // Donchian Channels (20)
      if (donchURef.current && donchMRef.current && donchLRef.current) {
        if (showDonchian) {
          const len = 20;
          const upper: Array<{ time: number; value: number }> = [];
          const lower: Array<{ time: number; value: number }> = [];
          const middle: Array<{ time: number; value: number }> = [];
          const hiBuf: number[] = [];
          const loBuf: number[] = [];
          for (const d of sorted) {
            hiBuf.push(d.high);
            loBuf.push(d.low);
            if (hiBuf.length > len) hiBuf.shift();
            if (loBuf.length > len) loBuf.shift();
            if (hiBuf.length === len && loBuf.length === len) {
              const hi = Math.max(...hiBuf);
              const lo = Math.min(...loBuf);
              upper.push({ time: d.time, value: hi });
              lower.push({ time: d.time, value: lo });
              middle.push({ time: d.time, value: (hi + lo) / 2 });
            }
          }
          donchURef.current.setData(lineData(upper));
          donchMRef.current.setData(lineData(middle));
          donchLRef.current.setData(lineData(lower));
        } else {
          donchURef.current.setData([]);
          donchMRef.current.setData([]);
          donchLRef.current.setData([]);
        }
      }

      // Keltner Channels (EMA20 of HLC3, ATR10 * 2) — common TV default
      if (keltURef.current && keltMRef.current && keltLRef.current) {
        if (showKeltner) {
          const len = 20; // EMA period for middle
          const atrLen = 10; // ATR period
          const mult = 2; // band multiplier
          const hlc3 = sorted.map((d) => (d.high + d.low + d.close) / 3);
          const emaMid = emaWithSMASeed(hlc3, len);
          const atr = computeATR(atrLen);
          const upper: Array<{ time: number; value: number }> = [];
          const mid: Array<{ time: number; value: number }> = [];
          const lower: Array<{ time: number; value: number }> = [];
          for (let i = 0; i < sorted.length; i++) {
            const a = atr[i];
            const m = emaMid[i];
            if (!isFinite(a) || !isFinite(m)) continue;
            upper.push({ time: sorted[i].time, value: m + mult * a });
            mid.push({ time: sorted[i].time, value: m });
            lower.push({ time: sorted[i].time, value: m - mult * a });
          }
          keltURef.current.setData(lineData(upper));
          keltMRef.current.setData(lineData(mid));
          keltLRef.current.setData(lineData(lower));
        } else {
          keltURef.current.setData([]);
          keltMRef.current.setData([]);
          keltLRef.current.setData([]);
        }
      }
    }, [
      candles,
      isInitialized,
      showSMA20,
      showEMA50,
      showBB,
      showVWAP,
      showRSI,
      showMACD,
      showSuperTrend,
      showDonchian,
      showKeltner,
    ]);

    // Panel heights
    const calcHeights = () => {
      const hasRSI = !!showRSI;
      const hasMACD = !!showMACD;
      if (hasRSI && hasMACD) return { main: 0.6, rsi: 0.2, macd: 0.2 };
      if (hasRSI && !hasMACD) return { main: 0.75, rsi: 0.25, macd: 0 };
      if (!hasRSI && hasMACD) return { main: 0.75, rsi: 0, macd: 0.25 };
      return { main: 1, rsi: 0, macd: 0 };
    };

    useEffect(() => {
      const wrap = wrapperRef.current;
      if (!wrap) return;
      const ro = new ResizeObserver(() => {
        const rect = wrap.getBoundingClientRect();
        const { main, rsi, macd } = calcHeights();
        const w = Math.max(1, Math.floor(rect.width));
        const h = Math.max(320, Math.floor(rect.height));
        if (containerRef.current) {
          containerRef.current.style.width = `${w}px`;
          containerRef.current.style.height = `${Math.floor(h * main)}px`;
          chartRef.current?.applyOptions({ width: w, height: Math.floor(h * main) });
        }
        if (rsiContainerRef.current && rsiChartRef.current) {
          rsiContainerRef.current.style.width = `${w}px`;
          rsiContainerRef.current.style.height = `${Math.floor(h * rsi)}px`;
          rsiChartRef.current.applyOptions({ width: w, height: Math.floor(h * rsi) });
        }
        if (macdContainerRef.current && macdChartRef.current) {
          macdContainerRef.current.style.width = `${w}px`;
          macdContainerRef.current.style.height = `${Math.floor(h * macd)}px`;
          macdChartRef.current.applyOptions({ width: w, height: Math.floor(h * macd) });
        }
      });
      ro.observe(wrap);
      return () => ro.disconnect();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [showRSI, showMACD]);

    // Sync crosshair between panes via a DOM vertical line overlay
    useEffect(() => {
      const root = wrapperRef.current;
      const mainEl = containerRef.current;
      if (!root || !mainEl || !chartRef.current) return;

      const ensureLine = () => {
        if (!crosshairLineRef.current) {
          const div = document.createElement('div');
          div.style.position = 'absolute';
          div.style.top = '0';
          div.style.bottom = '0';
          div.style.width = '1px';
          div.style.background = 'rgba(255,255,255,0.35)';
          div.style.pointerEvents = 'none';
          div.style.transform = 'translateX(-0.5px)';
          div.style.display = 'none';
          div.style.zIndex = '5';
          root.appendChild(div);
          crosshairLineRef.current = div;
        }
      };

      const showAt = (hostEl: HTMLDivElement, x: number) => {
        const line = crosshairLineRef.current;
        if (!root || !line) return;
        const rootRect = root.getBoundingClientRect();
        const hostRect = hostEl.getBoundingClientRect();
        const absX = hostRect.left - rootRect.left + x;
        line.style.left = `${Math.round(absX)}px`;
        line.style.display = 'block';
      };

      const hide = () => {
        const line = crosshairLineRef.current;
        if (line) line.style.display = 'none';
      };

      ensureLine();

      const sub = (chart: any, hostEl: HTMLDivElement) => {
        const handler = (param: any) => {
          // If pointer leaves the chart or no time is available, hide
          if (!param?.point || param.time === undefined || param.point.x == null) {
            hide();
            return;
          }
          showAt(hostEl, Math.floor(param.point.x));
        };
        chart.subscribeCrosshairMove(handler);
        return () => chart.unsubscribeCrosshairMove(handler);
      };

      const unsubs: Array<() => void> = [];
      unsubs.push(sub(chartRef.current, mainEl));
      if (showRSI && rsiChartRef.current && rsiContainerRef.current) {
        unsubs.push(sub(rsiChartRef.current, rsiContainerRef.current));
      }
      if (showMACD && macdChartRef.current && macdContainerRef.current) {
        unsubs.push(sub(macdChartRef.current, macdContainerRef.current));
      }

      // Hide on root mouse leave for safety
      const onLeave = (e: MouseEvent) => {
        if (!root) return;
        const rect = root.getBoundingClientRect();
        const x = e.clientX,
          y = e.clientY;
        if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) hide();
      };
      window.addEventListener('mousemove', onLeave);

      return () => {
        unsubs.forEach((u) => {
          try {
            u();
          } catch {}
        });
        window.removeEventListener('mousemove', onLeave);
      };
    }, [isInitialized, showRSI, showMACD]);

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
        {showRSI ? <div ref={rsiContainerRef} style={{ width: '100%', height: 0 }} /> : null}
        {showMACD ? <div ref={macdContainerRef} style={{ width: '100%', height: 0 }} /> : null}
      </div>
    );
  }
);

SimpleChart.displayName = 'SimpleChart';

export default SimpleChart;
