import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import type { Tool, Shape, Point, Theme } from './types';
import type { SimpleChartHandle } from '../SimpleChart';

export type DrawingLayerHandle = {
  undo: () => void;
  clear: () => void;
  deleteSelected: () => void;
};

type Props = {
  chartRef: React.RefObject<SimpleChartHandle>;
  activeTool: Tool;
  theme?: Theme;
  storageKey?: string; // to persist drawings per symbol/interval
  onSelectionChange?: (hasSelection: boolean) => void;
  interval?: string; // for magnet snapping buckets
  magnet?: boolean; // snap to bucket/time and minor price rounding
  ohlc?: Array<{
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  }>; // normalized OHLC
};

const defaultTheme: Theme = {
  stroke: 'rgba(255,255,255,0.8)',
  strokeActive: 'rgba(59,130,246,0.95)',
};

const distance2 = (a: { x: number; y: number }, b: { x: number; y: number }) => {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return dx * dx + dy * dy;
};

const DrawingLayer = forwardRef<DrawingLayerHandle, Props>(
  (
    {
      chartRef,
      activeTool,
      theme,
      storageKey,
      onSelectionChange,
      interval = '1',
      magnet = false,
      ohlc = [],
    },
    ref
  ) => {
    const th = { ...defaultTheme, ...(theme || {}) };
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const [shapes, setShapes] = useState<Shape[]>([]);
    const [draft, setDraft] = useState<Shape | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [hoverHit, setHoverHit] = useState<boolean>(false);
    const draggingRef = useRef<null | {
      index: number;
      part:
        | 'line'
        | 'p1'
        | 'p2'
        | 'start' // for hray
        | 'vline'
        | 'hline'
        | 'width'; // for channel width adjustment
      startMouse: { x: number; y: number; point: Point };
      original: Shape;
    }>(null);
    const undoStack = useRef<Shape[][]>([]);

    // Load persisted drawings for this storageKey
    useEffect(() => {
      if (!storageKey) return;
      try {
        const raw = localStorage.getItem(storageKey);
        if (raw) {
          const parsed = JSON.parse(raw) as Shape[];
          if (Array.isArray(parsed)) setShapes(parsed);
        } else {
          setShapes([]);
        }
      } catch {
        // ignore parse errors
      }
    }, [storageKey]);

    // Resize observer is set up after renderAll is defined (see later)

    useImperativeHandle(ref, () => ({
      undo() {
        const prev = undoStack.current.pop();
        if (prev) setShapes(prev);
      },
      clear() {
        undoStack.current.push(shapes);
        setShapes([]);
        setDraft(null);
      },
      deleteSelected() {
        if (!selectedId) return;
        undoStack.current.push(shapes);
        setShapes((prev) => prev.filter((s) => s.id !== selectedId));
        setSelectedId(null);
      },
    }));

    const ctx = () => canvasRef.current?.getContext('2d') || null;

    const toPx = useCallback(
      (p: Point) => {
        const x = chartRef.current?.timeToCoordinate(p.time);
        const y = chartRef.current?.priceToCoordinate(p.price);
        if (x == null || y == null) return null;
        return { x: Number(x), y: Number(y) };
      },
      [chartRef]
    );

    const fromPx = useCallback(
      (xy: { x: number; y: number }): Point | null => {
        const t = chartRef.current?.coordinateToTime(xy.x);
        const price = chartRef.current?.coordinateToPrice(xy.y);
        if (t == null || price == null) return null;
        let time = Number(t);
        let pr = Number(price);
        if (magnet) {
          const iv = String(interval).toUpperCase();
          const bucketSec =
            iv === 'D'
              ? 86400
              : iv === 'W'
                ? 7 * 86400
                : isFinite(parseInt(iv, 10))
                  ? Math.max(1, parseInt(iv, 10)) * 60
                  : 60;
          time = Math.round(time / bucketSec) * bucketSec;
          // rudimentary price rounding (2 decimals)
          pr = Math.round(pr * 100) / 100;
        }
        return { time, price: pr };
      },
      [chartRef, magnet, interval]
    );

    const renderShape = useCallback(
      (g: CanvasRenderingContext2D, s: Shape, active = false) => {
        g.save();
        g.lineWidth = 1;
        g.strokeStyle = active ? th.strokeActive : th.stroke;
        if (s.type === 'trendline') {
          const p1 = toPx(s.p1);
          const p2 = toPx(s.p2);
          if (!p1 || !p2) {
            g.restore();
            return;
          }
          g.beginPath();
          g.moveTo(p1.x, p1.y);
          g.lineTo(p2.x, p2.y);
          g.stroke();
          // handles when active
          if (active) {
            g.fillStyle = th.strokeActive;
            g.beginPath();
            g.arc(p1.x, p1.y, 3, 0, Math.PI * 2);
            g.fill();
            g.beginPath();
            g.arc(p2.x, p2.y, 3, 0, Math.PI * 2);
            g.fill();
          }
        } else if (s.type === 'ray') {
          const p1 = toPx(s.p1);
          const p2 = toPx(s.p2);
          if (!p1 || !p2 || !canvasRef.current) {
            g.restore();
            return;
          }
          // extend line from p1 through p2 towards right side
          const dx = p2.x - p1.x;
          const dy = p2.y - p1.y;
          const W = canvasRef.current.width;
          const t = dx !== 0 ? (W - p1.x) / dx : 0; // factor to reach right edge
          const x2 = p1.x + dx * Math.max(0, t);
          const y2 = p1.y + dy * Math.max(0, t);
          g.beginPath();
          g.moveTo(p1.x, p1.y);
          g.lineTo(x2, y2);
          g.stroke();
          if (active) {
            g.fillStyle = th.strokeActive;
            g.beginPath();
            g.arc(p1.x, p1.y, 3, 0, Math.PI * 2);
            g.fill();
            g.beginPath();
            g.arc(p2.x, p2.y, 3, 0, Math.PI * 2);
            g.fill();
          }
        } else if (s.type === 'hline') {
          const y = chartRef.current?.priceToCoordinate(s.price);
          if (y == null) {
            g.restore();
            return;
          }
          g.beginPath();
          g.moveTo(0, y);
          g.lineTo(canvasRef.current!.width, y);
          g.stroke();
        } else if (s.type === 'hray') {
          const y = chartRef.current?.priceToCoordinate(s.p.price);
          const x1 = chartRef.current?.timeToCoordinate(s.p.time);
          if (y == null || x1 == null || !canvasRef.current) {
            g.restore();
            return;
          }
          g.beginPath();
          g.moveTo(x1, y);
          g.lineTo(canvasRef.current.width, y);
          g.stroke();
          if (active) {
            g.fillStyle = th.strokeActive;
            g.beginPath();
            g.arc(x1, y, 3, 0, Math.PI * 2);
            g.fill();
          }
        } else if (s.type === 'vline') {
          const x = chartRef.current?.timeToCoordinate(s.time);
          if (x == null) {
            g.restore();
            return;
          }
          g.beginPath();
          g.moveTo(x, 0);
          g.lineTo(x, canvasRef.current!.height);
          g.stroke();
        } else if (s.type === 'fib') {
          const levels = s.levels && s.levels.length ? s.levels : [0, 0.236, 0.382, 0.5, 0.618, 1];
          const a = toPx(s.p1);
          const b = toPx(s.p2);
          if (!a || !b) {
            g.restore();
            return;
          }
          const x1 = a.x;
          const x2 = b.x;
          for (const lv of levels) {
            const y = a.y + (b.y - a.y) * lv;
            g.beginPath();
            g.moveTo(x1, y);
            g.lineTo(x2, y);
            g.stroke();
          }
          if (active) {
            g.fillStyle = th.strokeActive;
            g.beginPath();
            g.arc(a.x, a.y, 3, 0, Math.PI * 2);
            g.fill();
            g.beginPath();
            g.arc(b.x, b.y, 3, 0, Math.PI * 2);
            g.fill();
          }
        } else if (s.type === 'rect') {
          const a = toPx(s.p1);
          const b = toPx(s.p2);
          if (!a || !b) {
            g.restore();
            return;
          }
          const x = Math.min(a.x, b.x);
          const y = Math.min(a.y, b.y);
          const w = Math.abs(b.x - a.x);
          const h = Math.abs(b.y - a.y);
          g.strokeRect(x, y, w, h);
          if (active) {
            g.fillStyle = th.strokeActive;
            const corners = [a, { x: a.x, y: b.y }, b, { x: b.x, y: a.y }];
            for (const c of corners) {
              g.beginPath();
              g.arc(c.x, c.y, 3, 0, Math.PI * 2);
              g.fill();
            }
          }
        } else if (s.type === 'ruler') {
          const a = toPx(s.p1);
          const b = toPx(s.p2);
          if (!a || !b || !canvasRef.current) {
            g.restore();
            return;
          }
          const left = Math.min(a.x, b.x);
          const right = Math.max(a.x, b.x);
          const top = Math.min(a.y, b.y);
          const bottom = Math.max(a.y, b.y);

          // Compute metrics
          const t0 = Math.min(s.p1.time, s.p2.time);
          const t1 = Math.max(s.p1.time, s.p2.time);
          const delta = s.p2.price - s.p1.price;
          const percent = s.p1.price !== 0 ? (delta / s.p1.price) * 100 : 0;
          const bars = ohlc.filter((d) => d.time >= t0 && d.time <= t1);
          const volSum = bars.reduce((acc, d) => acc + (d.volume || 0), 0);
          const spanSec = Math.max(0, t1 - t0);

          const fmtNum = (n: number) => {
            const sign = n < 0 ? '-' : '';
            const v = Math.abs(n);
            if (v >= 1e9) return sign + (v / 1e9).toFixed(2) + 'B';
            if (v >= 1e6) return sign + (v / 1e6).toFixed(2) + 'M';
            if (v >= 1e3) return sign + (v / 1e3).toFixed(2) + 'K';
            return sign + v.toFixed(2);
          };
          const fmtDur = (s: number) => {
            const d = Math.floor(s / 86400);
            s %= 86400;
            const h = Math.floor(s / 3600);
            s %= 3600;
            const m = Math.floor(s / 60);
            if (d > 0) return `${d}д ${h}ч ${m}м`;
            if (h > 0) return `${h}ч ${m}м`;
            return `${m}м`;
          };

          const up = delta >= 0;
          const fill = up ? 'rgba(59,130,246,0.18)' : 'rgba(239,68,68,0.18)';
          const stroke = up ? 'rgba(59,130,246,0.45)' : 'rgba(239,68,68,0.45)';
          const labelBg = up ? 'rgba(59,130,246,0.95)' : 'rgba(239,68,68,0.95)';

          // Rect
          g.fillStyle = fill;
          g.fillRect(left, top, right - left, bottom - top);
          g.strokeStyle = stroke;
          g.setLineDash([6, 4]);
          g.strokeRect(left, top, right - left, bottom - top);
          g.setLineDash([]);

          // Label (rounded)
          const lines = [
            `${delta >= 0 ? '+' : ''}${fmtNum(delta)} (${(percent >= 0 ? '+' : '') + percent.toFixed(2)}%)`,
            `Бары: ${bars.length}, ${fmtDur(spanSec)}`,
            `Объём: ${fmtNum(volSum)}`,
          ];
          g.font = '12px sans-serif';
          const padX = 8;
          const padY = 6;
          const textW = Math.max(...lines.map((t) => g.measureText(t).width));
          const textH = 14 * lines.length; // rough line height
          const boxW = Math.ceil(textW) + padX * 2;
          const boxH = Math.ceil(textH) + padY * 2;
          const boxX = Math.round((left + right) / 2 - boxW / 2);
          const boxY = Math.round(top - boxH - 6);
          g.fillStyle = labelBg;
          const r = 6;
          const drawRounded = (x: number, y: number, w: number, h: number, rad: number) => {
            g.beginPath();
            g.moveTo(x + rad, y);
            g.lineTo(x + w - rad, y);
            g.quadraticCurveTo(x + w, y, x + w, y + rad);
            g.lineTo(x + w, y + h - rad);
            g.quadraticCurveTo(x + w, y + h, x + w - rad, y + h);
            g.lineTo(x + rad, y + h);
            g.quadraticCurveTo(x, y + h, x, y + h - rad);
            g.lineTo(x, y + rad);
            g.quadraticCurveTo(x, y, x + rad, y);
            g.closePath();
            g.fill();
          };
          drawRounded(boxX, boxY, boxW, boxH, r);
          g.fillStyle = '#ffffff';
          let ty = boxY + padY + 12;
          for (const ln of lines) {
            g.fillText(ln, boxX + padX, ty);
            ty += 14;
          }
          // Handles when active
          if (active) {
            g.fillStyle = th.strokeActive;
            g.beginPath();
            g.arc(a.x, a.y, 3, 0, Math.PI * 2);
            g.fill();
            g.beginPath();
            g.arc(b.x, b.y, 3, 0, Math.PI * 2);
            g.fill();
          }
        } else if (s.type === 'channel') {
          const a = toPx(s.p1);
          const b = toPx(s.p2);
          if (!a || !b) {
            g.restore();
            return;
          }
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const len = Math.hypot(dx, dy) || 1;
          // unit normal to the line (perpendicular)
          const nx = -dy / len;
          const ny = dx / len;
          const off = s.widthPx ?? 20;
          const a2 = { x: a.x + nx * off, y: a.y + ny * off };
          const b2 = { x: b.x + nx * off, y: b.y + ny * off };
          g.beginPath();
          g.moveTo(a.x, a.y);
          g.lineTo(b.x, b.y);
          g.stroke();
          g.beginPath();
          g.moveTo(a2.x, a2.y);
          g.lineTo(b2.x, b2.y);
          g.stroke();
          if (active) {
            g.fillStyle = th.strokeActive;
            g.beginPath();
            g.arc(a.x, a.y, 3, 0, Math.PI * 2);
            g.fill();
            g.beginPath();
            g.arc(b.x, b.y, 3, 0, Math.PI * 2);
            g.fill();
          }
        }
        g.restore();
      },
      [th.stroke, th.strokeActive, toPx, chartRef, ohlc]
    );

    const renderAll = useCallback(() => {
      const g = ctx();
      if (!g || !canvasRef.current) return;
      g.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
      for (const s of shapes) renderShape(g, s, selectedId === s.id);
      if (draft) renderShape(g, draft, true);
    }, [shapes, draft, renderShape, selectedId]);

    // Resize canvas to chart container; start with parent if needed and upgrade to chart container when ready
    useEffect(() => {
      const c = canvasRef.current;
      if (!c) return;

      let ro: ResizeObserver | null = null;
      let rafId: number | null = null;
      let disposed = false;
      let currentHost: Element | null = null;

      const chartHost = () => (chartRef.current?.container as HTMLDivElement | null) || null;
      const parentHost = () => c.parentElement as Element | null;

      const resize = (host: Element) => {
        const rect = (host as HTMLElement).getBoundingClientRect();
        c.width = Math.max(1, Math.floor(rect.width));
        c.height = Math.max(1, Math.floor(rect.height));
        c.style.width = rect.width + 'px';
        c.style.height = rect.height + 'px';
        renderAll();
      };

      const observe = (host: Element) => {
        if (ro) {
          try {
            ro.disconnect();
          } catch {}
        }
        currentHost = host;
        resize(host);
        ro = new ResizeObserver(() => resize(host));
        try {
          ro.observe(host);
        } catch {}
      };

      const bootstrap = () => {
        const host = chartHost() || parentHost();
        if (!host) return false;
        observe(host);
        return true;
      };

      if (!bootstrap()) {
        const tick = () => {
          if (disposed) return;
          if (!bootstrap()) rafId = requestAnimationFrame(tick);
        };
        rafId = requestAnimationFrame(tick);
      }

      const upgradeTick = () => {
        if (disposed) return;
        const ch = chartHost();
        if (ch && currentHost !== ch) observe(ch);
        rafId = requestAnimationFrame(upgradeTick);
      };
      rafId = requestAnimationFrame(upgradeTick);

      return () => {
        disposed = true;
        try {
          ro?.disconnect();
        } catch {}
        if (rafId != null) cancelAnimationFrame(rafId);
      };
    }, [renderAll, chartRef]);

    useEffect(() => {
      renderAll();
      if (storageKey) {
        try {
          localStorage.setItem(storageKey, JSON.stringify(shapes));
        } catch {}
      }
    }, [shapes, draft, renderAll, storageKey]);

    // Interactions
    // Hit-testing helpers
    const hitTest = useCallback(
      (pos: { x: number; y: number }) => {
        const tol2 = 8 * 8;
        const c = canvasRef.current;
        if (!c)
          return null as null | {
            index: number;
            part: 'line' | 'p1' | 'p2' | 'start' | 'vline' | 'hline' | 'width';
          };

        const pointToSegDist2 = (
          p: { x: number; y: number },
          a: { x: number; y: number },
          b: { x: number; y: number }
        ) => {
          const vx = b.x - a.x;
          const vy = b.y - a.y;
          const wx = p.x - a.x;
          const wy = p.y - a.y;
          const c1 = vx * wx + vy * wy;
          const c2 = vx * vx + vy * vy;
          let t = 0;
          if (c2 > 0) t = Math.max(0, Math.min(1, c1 / c2));
          const px = a.x + t * vx;
          const py = a.y + t * vy;
          return distance2(p, { x: px, y: py });
        };

        for (let i = shapes.length - 1; i >= 0; i--) {
          const s = shapes[i];
          if (s.type === 'trendline') {
            const p1 = toPx(s.p1);
            const p2 = toPx(s.p2);
            if (!p1 || !p2) continue;
            // endpoints priority
            if (distance2(pos, p1) <= tol2) return { index: i, part: 'p1' } as const;
            if (distance2(pos, p2) <= tol2) return { index: i, part: 'p2' } as const;
            if (pointToSegDist2(pos, p1, p2) <= tol2) return { index: i, part: 'line' } as const;
          } else if (s.type === 'ray') {
            const p1 = toPx(s.p1);
            const p2 = toPx(s.p2);
            if (!p1 || !p2 || !c) continue;
            const dx = p2.x - p1.x;
            const dy = p2.y - p1.y;
            const W = c.width;
            const t = dx !== 0 ? (W - p1.x) / dx : 0;
            const end = { x: p1.x + dx * Math.max(0, t), y: p1.y + dy * Math.max(0, t) };
            if (distance2(pos, p1) <= tol2) return { index: i, part: 'p1' } as const;
            if (distance2(pos, p2) <= tol2) return { index: i, part: 'p2' } as const;
            if (pointToSegDist2(pos, p1, end) <= tol2) return { index: i, part: 'line' } as const;
          } else if (s.type === 'hline') {
            const y = chartRef.current?.priceToCoordinate(s.price);
            if (y == null) continue;
            if (Math.abs(pos.y - Number(y)) <= 8) return { index: i, part: 'hline' } as const;
          } else if (s.type === 'hray') {
            const y = chartRef.current?.priceToCoordinate(s.p.price);
            const x1 = chartRef.current?.timeToCoordinate(s.p.time);
            if (y == null || x1 == null || !c) continue;
            // start handle
            if (distance2(pos, { x: Number(x1), y: Number(y) }) <= tol2)
              return { index: i, part: 'start' } as const;
            if (pos.y >= Number(y) - 8 && pos.y <= Number(y) + 8 && pos.x >= Number(x1))
              return { index: i, part: 'line' } as const;
          } else if (s.type === 'vline') {
            const x = chartRef.current?.timeToCoordinate(s.time);
            if (x == null) continue;
            if (Math.abs(pos.x - Number(x)) <= 8) return { index: i, part: 'vline' } as const;
          } else if (s.type === 'fib') {
            const a = toPx(s.p1);
            const b = toPx(s.p2);
            if (!a || !b) continue;
            const levels =
              s.levels && s.levels.length ? s.levels : [0, 0.236, 0.382, 0.5, 0.618, 1];
            const x1 = Math.min(a.x, b.x);
            const x2 = Math.max(a.x, b.x);
            if (distance2(pos, a) <= tol2) return { index: i, part: 'p1' } as const;
            if (distance2(pos, b) <= tol2) return { index: i, part: 'p2' } as const;
            for (const lv of levels) {
              const y = a.y + (b.y - a.y) * lv;
              if (pos.x >= x1 && pos.x <= x2 && Math.abs(pos.y - y) <= 8)
                return { index: i, part: 'line' } as const;
            }
          } else if (s.type === 'rect') {
            const a = toPx(s.p1);
            const b = toPx(s.p2);
            if (!a || !b) continue;
            const x1 = Math.min(a.x, b.x);
            const y1 = Math.min(a.y, b.y);
            const x2 = Math.max(a.x, b.x);
            const y2 = Math.max(a.y, b.y);
            const onEdge =
              (Math.abs(pos.x - x1) <= 6 && pos.y >= y1 && pos.y <= y2) ||
              (Math.abs(pos.x - x2) <= 6 && pos.y >= y1 && pos.y <= y2) ||
              (Math.abs(pos.y - y1) <= 6 && pos.x >= x1 && pos.x <= x2) ||
              (Math.abs(pos.y - y2) <= 6 && pos.x >= x1 && pos.x <= x2);
            if (onEdge) return { index: i, part: 'line' } as const;
            if (distance2(pos, a) <= tol2) return { index: i, part: 'p1' } as const;
            if (distance2(pos, b) <= tol2) return { index: i, part: 'p2' } as const;
          } else if (s.type === 'ruler') {
            const a = toPx(s.p1);
            const b = toPx(s.p2);
            if (!a || !b) continue;
            // endpoints and line body
            const pointToSegDist2 = (
              p: { x: number; y: number },
              a: { x: number; y: number },
              b: { x: number; y: number }
            ) => {
              const vx = b.x - a.x;
              const vy = b.y - a.y;
              const wx = p.x - a.x;
              const wy = p.y - a.y;
              const c1 = vx * wx + vy * wy;
              const c2 = vx * vx + vy * vy;
              let t = 0;
              if (c2 > 0) t = Math.max(0, Math.min(1, c1 / c2));
              const px = a.x + t * vx;
              const py = a.y + t * vy;
              return distance2(p, { x: px, y: py });
            };
            if (distance2(pos, a) <= tol2) return { index: i, part: 'p1' } as const;
            if (distance2(pos, b) <= tol2) return { index: i, part: 'p2' } as const;
            if (pointToSegDist2(pos, a, b) <= tol2) return { index: i, part: 'line' } as const;
          } else if (s.type === 'channel') {
            const a = toPx(s.p1);
            const b = toPx(s.p2);
            if (!a || !b) continue;
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const len = Math.hypot(dx, dy) || 1;
            const nx = -dy / len;
            const ny = dx / len;
            const off = s.widthPx ?? 20;
            const a2 = { x: a.x + nx * off, y: a.y + ny * off };
            const b2 = { x: b.x + nx * off, y: b.y + ny * off };
            const pointToSegDist2 = (
              p: { x: number; y: number },
              a: { x: number; y: number },
              b: { x: number; y: number }
            ) => {
              const vx = b.x - a.x;
              const vy = b.y - a.y;
              const wx = p.x - a.x;
              const wy = p.y - a.y;
              const c1 = vx * wx + vy * wy;
              const c2 = vx * vx + vy * vy;
              let t = 0;
              if (c2 > 0) t = Math.max(0, Math.min(1, c1 / c2));
              const px = a.x + t * vx;
              const py = a.y + t * vy;
              return distance2(p, { x: px, y: py });
            };
            if (distance2(pos, a) <= tol2) return { index: i, part: 'p1' } as const;
            if (distance2(pos, b) <= tol2) return { index: i, part: 'p2' } as const;
            if (pointToSegDist2(pos, a2, b2) <= tol2) return { index: i, part: 'width' } as const;
            if (pointToSegDist2(pos, a, b) <= tol2) return { index: i, part: 'line' } as const;
          }
        }
        return null;
      },
      [shapes, toPx, chartRef]
    );

    useEffect(() => {
      const c = canvasRef.current;
      if (!c) return;

      const onDown = (e: MouseEvent) => {
        if (e.button !== 0) return; // left only
        const rect = c.getBoundingClientRect();
        const pos = { x: e.clientX - rect.left, y: e.clientY - rect.top };
        const point = fromPx(pos);
        if (!point) return;

        if (activeTool === 'select') {
          const hit = hitTest(pos);
          if (hit) {
            setSelectedId(shapes[hit.index].id);
            draggingRef.current = {
              index: hit.index,
              part: hit.part,
              startMouse: { x: pos.x, y: pos.y, point },
              original: shapes[hit.index],
            };
          } else {
            setSelectedId(null);
            draggingRef.current = null;
          }
          return;
        }

        // drawing modes
        if (activeTool === 'trendline') {
          setDraft({ id: 'draft', type: 'trendline', p1: point, p2: point });
        } else if (activeTool === 'ray') {
          setDraft({ id: 'draft', type: 'ray', p1: point, p2: point } as Shape);
        } else if (activeTool === 'hline') {
          setDraft({ id: 'draft', type: 'hline', price: point.price });
        } else if (activeTool === 'hray') {
          setDraft({ id: 'draft', type: 'hray', p: point } as Shape);
        } else if (activeTool === 'vline') {
          setDraft({ id: 'draft', type: 'vline', time: point.time });
        } else if (activeTool === 'fib') {
          setDraft({ id: 'draft', type: 'fib', p1: point, p2: point } as Shape);
        } else if (activeTool === 'rect') {
          setDraft({ id: 'draft', type: 'rect', p1: point, p2: point } as Shape);
        } else if (activeTool === 'ruler') {
          setDraft({ id: 'draft', type: 'ruler', p1: point, p2: point } as Shape);
        } else if (activeTool === 'channel') {
          setDraft({ id: 'draft', type: 'channel', p1: point, p2: point, widthPx: 20 } as any);
        }
      };

      const onMove = (e: MouseEvent) => {
        const rect = c.getBoundingClientRect();
        const pos = { x: e.clientX - rect.left, y: e.clientY - rect.top };
        const point = fromPx(pos);
        if (!point) return;

        // dragging existing shape
        if (draggingRef.current) {
          const { index, part, startMouse, original } = draggingRef.current;
          const startPoint = startMouse.point;
          setShapes((prev) => {
            const next = [...prev];
            const s = next[index];
            if (!s) return prev;
            if (s.type === 'trendline') {
              if (part === 'p1') {
                next[index] = { ...s, p1: point } as Shape;
              } else if (part === 'p2') {
                next[index] = { ...s, p2: point } as Shape;
              } else {
                // translate both points by delta in domain
                const dt = point.time - startPoint.time;
                const dp = point.price - startPoint.price;
                const orig = original as Extract<Shape, { type: 'trendline' }>;
                next[index] = {
                  ...s,
                  p1: { time: orig.p1.time + dt, price: orig.p1.price + dp },
                  p2: { time: orig.p2.time + dt, price: orig.p2.price + dp },
                } as Shape;
              }
            } else if (s.type === 'ray') {
              if (part === 'p1') {
                next[index] = { ...s, p1: point } as Shape;
              } else if (part === 'p2') {
                next[index] = { ...s, p2: point } as Shape;
              } else {
                const dt = point.time - startPoint.time;
                const dp = point.price - startPoint.price;
                const orig = original as Extract<Shape, { type: 'ray' }>;
                next[index] = {
                  ...s,
                  p1: { time: orig.p1.time + dt, price: orig.p1.price + dp },
                  p2: { time: orig.p2.time + dt, price: orig.p2.price + dp },
                } as Shape;
              }
            } else if (s.type === 'hline') {
              next[index] = { ...s, price: point.price } as Shape;
            } else if (s.type === 'hray') {
              if (part === 'start') {
                next[index] = { ...s, p: { time: point.time, price: (s as any).p.price } } as Shape;
              } else {
                next[index] = { ...s, p: { time: (s as any).p.time, price: point.price } } as Shape;
              }
            } else if (s.type === 'vline') {
              next[index] = { ...s, time: point.time } as Shape;
            } else if (s.type === 'fib') {
              if (part === 'p1') {
                const fib = s as Extract<Shape, { type: 'fib' }>;
                next[index] = { ...fib, p1: point } as Shape;
              } else if (part === 'p2') {
                const fib = s as Extract<Shape, { type: 'fib' }>;
                next[index] = { ...fib, p2: point } as Shape;
              } else {
                const dt = point.time - startPoint.time;
                const dp = point.price - startPoint.price;
                const orig = original as Extract<Shape, { type: 'fib' }>;
                next[index] = {
                  ...s,
                  p1: { time: orig.p1.time + dt, price: orig.p1.price + dp },
                  p2: { time: orig.p2.time + dt, price: orig.p2.price + dp },
                } as Shape;
              }
            } else if (s.type === 'rect') {
              if (part === 'p1') {
                const r = s as Extract<Shape, { type: 'rect' }>;
                next[index] = { ...r, p1: point } as Shape;
              } else if (part === 'p2') {
                const r = s as Extract<Shape, { type: 'rect' }>;
                next[index] = { ...r, p2: point } as Shape;
              } else {
                const dt = point.time - startPoint.time;
                const dp = point.price - startPoint.price;
                const orig = original as Extract<Shape, { type: 'rect' }>;
                next[index] = {
                  ...s,
                  p1: { time: orig.p1.time + dt, price: orig.p1.price + dp },
                  p2: { time: orig.p2.time + dt, price: orig.p2.price + dp },
                } as Shape;
              }
            } else if (s.type === 'ruler') {
              if (part === 'p1') {
                const r = s as Extract<Shape, { type: 'ruler' }>;
                next[index] = { ...r, p1: point } as Shape;
              } else if (part === 'p2') {
                const r = s as Extract<Shape, { type: 'ruler' }>;
                next[index] = { ...r, p2: point } as Shape;
              } else {
                const dt = point.time - startPoint.time;
                const dp = point.price - startPoint.price;
                const orig = original as Extract<Shape, { type: 'ruler' }>;
                next[index] = {
                  ...s,
                  p1: { time: orig.p1.time + dt, price: orig.p1.price + dp },
                  p2: { time: orig.p2.time + dt, price: orig.p2.price + dp },
                } as Shape;
              }
            } else if (s.type === 'channel') {
              if (part === 'p1') {
                const ch = s as Extract<Shape, { type: 'channel' }>;
                next[index] = { ...ch, p1: point } as any;
              } else if (part === 'p2') {
                const ch = s as Extract<Shape, { type: 'channel' }>;
                next[index] = { ...ch, p2: point } as any;
              } else if (part === 'width') {
                // adjust width in pixels based on cursor distance to base line along normal
                const ch = s as Extract<Shape, { type: 'channel' }>;
                const a = toPx(ch.p1);
                const b = toPx(ch.p2);
                if (a && b) {
                  const dx = b.x - a.x;
                  const dy = b.y - a.y;
                  const len = Math.hypot(dx, dy) || 1;
                  const nx = -dy / len;
                  const ny = dx / len;
                  const proj = (pos.x - a.x) * nx + (pos.y - a.y) * ny; // signed distance
                  next[index] = { ...ch, widthPx: Math.max(1, Math.abs(proj)) } as any;
                }
              } else {
                const dt = point.time - startPoint.time;
                const dp = point.price - startPoint.price;
                const orig = original as Extract<Shape, { type: 'channel' }>;
                next[index] = {
                  ...s,
                  p1: { time: orig.p1.time + dt, price: orig.p1.price + dp },
                  p2: { time: orig.p2.time + dt, price: orig.p2.price + dp },
                } as any;
              }
            }
            return next;
          });
          return;
        }

        // draw draft update
        if (!draft) return;
        if (draft.type === 'trendline') {
          setDraft({ ...draft, p2: point });
        } else if (draft.type === 'ray') {
          setDraft({ ...draft, p2: point } as Shape);
        } else if (draft.type === 'hline') {
          setDraft({ ...draft, price: point.price });
        } else if (draft.type === 'hray') {
          setDraft({ ...draft, p: { time: point.time, price: draft.p.price } } as Shape);
        } else if (draft.type === 'vline') {
          setDraft({ ...draft, time: point.time });
        } else if (draft.type === 'fib') {
          setDraft({ ...draft, p2: point } as Shape);
        } else if (draft.type === 'rect') {
          setDraft({ ...draft, p2: point } as Shape);
        } else if (draft.type === 'ruler') {
          setDraft({ ...draft, p2: point } as Shape);
        } else if (draft.type === 'channel') {
          setDraft({ ...draft, p2: point } as any);
        }
      };

      const onUp = (_e: MouseEvent) => {
        // end dragging existing
        if (draggingRef.current) {
          undoStack.current.push(shapes);
          draggingRef.current = null;
          return;
        }

        if (!draft) return;
        if (draft.type === 'trendline') {
          // avoid zero-length lines
          const p1 = toPx(draft.p1);
          const p2 = toPx(draft.p2);
          if (p1 && p2 && distance2(p1, p2) > 4) {
            undoStack.current.push(shapes);
            setShapes([...shapes, { ...draft, id: crypto.randomUUID() } as Shape]);
          }
        } else if (draft.type === 'ray') {
          const p1 = toPx(draft.p1);
          const p2 = toPx(draft.p2);
          if (p1 && p2 && distance2(p1, p2) > 4) {
            undoStack.current.push(shapes);
            setShapes([...shapes, { ...draft, id: crypto.randomUUID() } as Shape]);
          }
        } else if (draft.type === 'fib') {
          const p1 = toPx(draft.p1);
          const p2 = toPx(draft.p2);
          if (p1 && p2 && distance2(p1, p2) > 4) {
            undoStack.current.push(shapes);
            setShapes([...shapes, { ...draft, id: crypto.randomUUID() } as Shape]);
          }
        } else {
          undoStack.current.push(shapes);
          setShapes([...shapes, { ...draft, id: crypto.randomUUID() } as Shape]);
        }
        setDraft(null);
      };

      c.addEventListener('mousedown', onDown);
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
      return () => {
        c.removeEventListener('mousedown', onDown);
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
      };
    }, [activeTool, draft, shapes, fromPx, toPx, hitTest]);

    // Keyboard delete in select mode
    useEffect(() => {
      const onKey = (e: KeyboardEvent) => {
        if (activeTool !== 'select') return;
        if (!selectedId) return;
        if (e.key === 'Delete' || e.key === 'Backspace') {
          undoStack.current.push(shapes);
          setShapes((prev) => prev.filter((s) => s.id !== selectedId));
          setSelectedId(null);
        }
      };
      window.addEventListener('keydown', onKey);
      return () => window.removeEventListener('keydown', onKey);
    }, [activeTool, selectedId, shapes]);

    // Global ESC to clear all drawings (and cancel draft)
    useEffect(() => {
      const onEsc = (e: KeyboardEvent) => {
        if (e.key !== 'Escape') return;
        // save previous for undo
        undoStack.current.push(shapes);
        setDraft(null);
        setSelectedId(null);
        setShapes([]);
        // also clear persisted storage immediately if available
        try {
          if (storageKey) localStorage.setItem(storageKey, JSON.stringify([]));
        } catch {}
      };
      window.addEventListener('keydown', onEsc);
      return () => window.removeEventListener('keydown', onEsc);
    }, [shapes, storageKey]);

    // Notify parent about selection changes
    useEffect(() => {
      onSelectionChange?.(!!selectedId);
    }, [selectedId, onSelectionChange]);

    // Hover-aware pointer events in select mode
    useEffect(() => {
      const c = canvasRef.current;
      if (!c) return;
      const onMove = (e: MouseEvent) => {
        if (activeTool !== 'select') return;
        const rect = c.getBoundingClientRect();
        const pos = { x: e.clientX - rect.left, y: e.clientY - rect.top };
        const hit = hitTest(pos);
        setHoverHit(!!hit);
      };
      window.addEventListener('mousemove', onMove);
      return () => window.removeEventListener('mousemove', onMove);
    }, [activeTool, hitTest]);

    return (
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          inset: 0,
          zIndex: 20,
          pointerEvents: activeTool === 'select' ? (hoverHit ? 'auto' : 'none') : 'auto',
          cursor:
            activeTool === 'select'
              ? hoverHit
                ? 'pointer'
                : 'default'
              : activeTool
                ? 'crosshair'
                : 'default',
        }}
      />
    );
  }
);

DrawingLayer.displayName = 'DrawingLayer';

export default DrawingLayer;
export type { Tool, Shape, Point, Theme };
