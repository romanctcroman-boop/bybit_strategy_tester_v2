/**
 * 📊 TradingView Lightweight Charts — Equity Chart Component
 *
 * Built on the official TradingView Lightweight Charts library (v4, MIT).
 * Replicates TradingView Strategy Tester chart appearance:
 *   - Baseline series: teal above initial capital, red below (TV-style color change)
 *   - Stepped line (lineType:2) with trade-exit circle markers
 *   - Buy & Hold line series
 *   - MFE/MAE bars via canvas overlay in bottom zone (TV histogram style)
 *   - Regime overlay via TV histogram series (background bands)
 *   - Crosshair, zoom/pan, price scale — all native TV behaviour
 *
 * Public API (unchanged so backtest_results.js needs no edits):
 *   render(data)
 *   setDisplayMode('absolute'|'percent')
 *   toggleBuyHold(bool)
 *   toggleTradeExcursions(bool)
 *   destroy()
 *   .chart          ← shim object with .resize() and regime annotation compat
 *   .data           ← last rendered data object
 *
 * @version 3.1.0 — 2026-02-25
 */

// LightweightCharts is loaded via CDN script tag (window.LightweightCharts)

class TradingViewEquityChart {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.container = document.getElementById(containerId);
    this.data = null;
    this.trades = [];
    this.initialCapital = 10000;

    // .chart shim — exposed so backtest_results.js .chart.resize() etc. works
    this.chart = null;

    this.options = {
      showBuyHold: true,
      showTradeExcursions: false,
      displayMode: 'absolute',   // 'absolute' | 'percent'
      height: null,              // null → fills CSS container
      ...options
    };

    // Internal state
    this._lwChart = null;   // LightweightCharts IChartApi
    this._equitySeries = null;
    this._bhSeries = null;
    this._mfeSeries = null;
    this._maeSeries = null;
    this._excursionCanvas = null;
    this._excursionRAF = null;
    this._resizeObserver = null;
    this._regimeRects = new Map();
    this._regimeAnnotations = {};  // Chart.js compat shim
    this._barScale = 0.65;         // default 65%; buttons: 1.0 / 0.65 / 0.35
  }

  // ─── PUBLIC API ────────────────────────────────────────────────────────────

  render(data) {
    if (!this.container) {
      console.warn('[TVEquityChart] Container not found:', this.containerId);
      return;
    }
    this.data = data;
    // Normalise mfe/mae fields.
    // Use absolute USD values (mfe / mae) for bar scaling so bars are in the
    // same units as the equity P&L axis.  Fallback to pct-derived values only
    // when absolute fields are absent (old result format).
    this.trades = (data.trades || []).map((t) => ({
      ...t,
      mfe: Math.abs(Number(t.mfe ?? t.mfe_pct ?? t.mfe_percent ?? 0)),
      mae: Math.abs(Number(t.mae ?? t.mae_pct ?? t.mae_percent ?? 0))
    }));
    this.initialCapital = data.initial_capital || 10000;
    this._dbgLogged = false;  // reset per render

    this._destroyInternal();
    this._createChart();
    this._buildSeries(data);
    this._setupResizeObserver();
    this._setupLegendInteractivity();
  }

  setDisplayMode(mode) {
    this.options.displayMode = mode;
    if (this.data) this.render(this.data);
  }

  toggleBuyHold(show) {
    this.options.showBuyHold = show;
    if (this._bhSeries) {
      // Series already exists — just show/hide it without full re-render
      this._bhSeries.applyOptions({ visible: show });
    } else if (show && this.data && this._lwChart) {
      // Series doesn't exist yet — build it now (e.g. first time enabling)
      const isPercent = this.options.displayMode === 'percent';
      this._buildBHSeries(this.data, isPercent);
    }
    // If no _lwChart yet, the flag is stored in options and will be respected at next render()
  }

  toggleTradeExcursions(show) {
    this.options.showTradeExcursions = show;
    if (show) {
      requestAnimationFrame(() => requestAnimationFrame(() => this._buildExcursionSeries()));
    } else {
      this._removeExcursionSeries();
    }
  }

  update(data) { this.render(data); }

  destroy() { this._destroyInternal(); }

  // ─── CHART CREATION ────────────────────────────────────────────────────────

  _createChart() {
    if (typeof LightweightCharts === 'undefined') {
      console.error('[TVEquityChart] LightweightCharts library not loaded!');
      return;
    }

    const w = this.container.clientWidth || this.container.offsetWidth || 900;
    const h = this.options.height || this.container.clientHeight || this.container.offsetHeight || 400;

    // Ensure container is measurable — set explicit size if DOM reports 0
    if (this.container.clientHeight === 0 && !this.options.height) {
      this.container.style.height = '400px';
    }

    this._lwChart = LightweightCharts.createChart(this.container, {
      width: w,
      height: h,
      layout: {
        background: { color: '#0d1117' },
        textColor: '#787b86'
      },
      grid: {
        vertLines: { color: 'rgba(48,54,61,0.5)' },
        horzLines: { color: 'rgba(48,54,61,0.8)' }
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: {
          color: '#758696', width: 1,
          style: LightweightCharts.LineStyle.Dashed,
          labelBackgroundColor: '#21262d'
        },
        horzLine: {
          color: '#758696', width: 1,
          style: LightweightCharts.LineStyle.Dashed,
          labelBackgroundColor: '#21262d'
        }
      },
      rightPriceScale: {
        borderColor: 'rgba(48,54,61,0.8)',
        autoScale: true
      },
      timeScale: {
        borderColor: 'rgba(48,54,61,0.8)',
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: true,      // cannot scroll left beyond first bar
        fixRightEdge: true,     // cannot scroll right beyond last bar
        lockVisibleTimeRangeOnResize: true,
        rightBarStaysOnScroll: false,
        minBarSpacing: 2,       // minimum zoom-out bar spacing (px)
        maxBarSpacing: 80       // maximum zoom-in bar spacing (px)
      },
      localization: {
        timeFormatter: (unixSeconds) => {
          // Timestamps are pre-shifted by +10800 (UTC+3), so format as UTC
          const d = new Date(unixSeconds * 1000);
          const pad = (n) => String(n).padStart(2, '0');
          return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
        },
        dateFormatter: (unixSeconds) => {
          const d = new Date(unixSeconds * 1000);
          const pad = (n) => String(n).padStart(2, '0');
          return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
        }
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
      autoSize: true   // LWC watches the container via ResizeObserver — fills available space
    });

    // ── Current time indicator (bottom-right, like TradingView "00:56:53 UTC+3") ──
    this._clockEl = document.createElement('div');
    this._clockEl.style.cssText = [
      'position:absolute', 'bottom:6px', 'right:10px',
      'font-size:13px', 'font-family:monospace',
      'color:#c9d1d9', 'pointer-events:none',
      'z-index:10', 'user-select:none',
      'background:rgba(13,17,23,0.85)', 'padding:2px 7px', 'border-radius:3px'
    ].join(';');
    // Container must be position:relative for absolute child to work
    if (getComputedStyle(this.container).position === 'static') {
      this.container.style.position = 'relative';
    }
    this.container.appendChild(this._clockEl);

    const updateClock = () => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString('en-GB', {
        timeZone: 'Europe/Moscow',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
      if (this._clockEl) this._clockEl.textContent = `${timeStr} UTC+3`;
    };
    updateClock();
    this._clockInterval = setInterval(updateClock, 1000);

    // Build .chart shim expected by backtest_results.js
    const self = this;
    this.chart = {
      resize: () => {
        if (self._lwChart && self.container) {
          const newW = self.container.clientWidth;
          const newH = self.container.clientHeight || 400;
          self._lwChart.resize(newW, newH);
        }
      },
      // Regime overlay compat: backtest_results.js does
      //   innerChart.options.plugins.annotation.annotations[key] = box
      //   innerChart.update('none')
      options: {
        plugins: {
          annotation: {
            get annotations() { return self._regimeAnnotations; }
          }
        }
      },
      update: () => { self._applyRegimeAnnotations(); }
    };
  }

  // ─── SERIES ────────────────────────────────────────────────────────────────

  _buildSeries(data) {
    if (!this._lwChart) return;

    const isPercent = this.options.displayMode === 'percent';
    const timestamps = data.timestamps || [];
    const equity = data.equity || [];

    if (timestamps.length === 0) return;

    // ── 0. MFE/MAE — canvas overlay, added AFTER chart is ready ──
    // Wide trade-duration rectangles drawn on a canvas overlay (TV style).
    // No histogram series needed here — _buildExcursionSeries handles everything.
    // ── 1. Equity as BASELINE series — added AFTER bars so it draws ON TOP ──
    // We ALWAYS display P&L (equity − initialCapital), so baseValue = 0.
    this._equitySeries = this._lwChart.addSeries(LightweightCharts.BaselineSeries, {
      baseValue: { type: 'price', price: 0 },
      // Above zero: teal (profit) — fill is 15% more transparent than before
      topLineColor: '#26a69a',
      topFillColor1: 'rgba(38,166,154,0.13)',
      topFillColor2: 'rgba(38,166,154,0.00)',
      // Below zero: red (loss) — fill is 15% more transparent than before
      bottomLineColor: '#ef5350',
      bottomFillColor1: 'rgba(239,83,80,0.00)',
      bottomFillColor2: 'rgba(239,83,80,0.07)',
      lineWidth: 2,
      lineType: 2,           // Stepped line — matches TV Strategy Tester
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 5,
      crosshairMarkerBorderColor: '#fff',
      crosshairMarkerBackgroundColor: '#26a69a',
      title: 'Equity'
    });

    const equityPoints = this._buildEquityPoints(timestamps, equity, isPercent);
    if (equityPoints.length > 0) {
      this._equitySeries.setData(equityPoints);
    }
    this._equityPoints = equityPoints;

    // autoscaleInfoProvider — locks the visible Y range to the equity P&L.
    // Always includes 0 (break-even line) with 3% breathing room at the edges.
    // MFE/MAE bars are drawn via canvas overlay with normalized pixel heights
    // so they don't need to influence the Y-axis scale.
    this._equitySeries.applyOptions({
      autoscaleInfoProvider: () => {
        const vals = equityPoints.map(p => p.value);
        if (!vals.length) return null;
        const maxV = Math.max(...vals, 0);   // always ≥ 0
        const minV = Math.min(...vals, 0);   // always ≤ 0
        const range = Math.max(maxV - minV, 1);
        const pad = range * 0.03;            // 3% breathing room
        return {
          priceRange: {
            minValue: minV - pad,
            maxValue: maxV + pad
          },
          margins: { above: 2, below: 2 }
        };
      }
    });
    // scaleMargins: leave some room at the top for the last-value label,
    // and at the bottom so the zero-line sits visually above the time axis.
    // Bars grow from the zero-line (price=0) downward/upward via canvas — no
    // extra bottom margin needed; priceToCoordinate(0) gives the exact pixel.
    this._equitySeries.priceScale().applyOptions({
      scaleMargins: { top: 0.08, bottom: 0.12 }
    });

    // ── Zero line — dashed separator ───────────────────────────────────────
    this._equitySeries.createPriceLine({
      price: 0,
      color: 'rgba(120,123,134,0.6)',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: true,
      axisLabelColor: 'rgba(120,123,134,0.85)',
      axisLabelTextColor: '#d1d4dc',
      title: ''
    });

    // ── 2. Trade-exit circle markers ────────────────────────────────────────
    // Shown only when trades < 200.
    // Each marker is placed at a unique timestamp so LWC doesn't discard duplicates.
    // When two trades exit on the same bar, the later one gets +1 sec nudge.
    // _tradeMarkerTimes[i] stores the final (possibly nudged) time for trade[i].
    this._tradeExitSecs = [];
    this._tradeMarkerTimes = [];
    {
      const n = this.trades.length;
      // Build _tradeMarkerTimes: prefer exact equityPoints time (1:1 case), else exitSec
      const useIndex = (n === equityPoints.length);
      this.trades.forEach((trade, i) => {
        this._tradeExitSecs[i] = this._toUnixSec(trade.exit_time) || null;
        this._tradeMarkerTimes[i] = useIndex
          ? (equityPoints[i]?.time || null)
          : (this._tradeExitSecs[i] || null);
      });

      // Nudge duplicate times so every marker has a unique timestamp
      const usedTimes = new Map();
      this.trades.forEach((trade, i) => {
        let t = this._tradeMarkerTimes[i];
        if (!t) return;
        while (usedTimes.has(t)) { t += 1; }
        usedTimes.set(t, 1);
        this._tradeMarkerTimes[i] = t;
      });

      if (n > 0 && n < 200) {
        const markers = this.trades
          .map((trade, i) => {
            const t = this._tradeMarkerTimes[i];
            if (!t) return null;
            return {
              time: t,
              position: 'inBar',
              color: (trade.pnl || 0) >= 0 ? '#26a69a' : '#ef5350',
              shape: 'circle',
              size: 0
            };
          })
          .filter(Boolean)
          .sort((a, b) => a.time - b.time);
        if (markers.length) {
          this._equityMarkersPrimitive = LightweightCharts.createSeriesMarkers(this._equitySeries, markers);
        }
      }
    }

    // ── 3. Buy & Hold ───────────────────────────────────────────────────────
    if (this.options.showBuyHold) {
      this._buildBHSeries(data, isPercent);
    }

    // ── 4. Fit view, then fill bar data ─────────────────────────────────────
    this._lwChart.timeScale().fitContent();

    // ── Clamp vertical scroll so equity line can't go fully off-screen ──────
    // Subscribe to price-scale changes and enforce a max pan range:
    // never let the visible price range drift more than 2× the data range
    // away from the data, so bars and equity line always stay visible.
    {
      const ps = this._equitySeries.priceScale();
      const clampPriceScale = () => {
        if (!this._equitySeries || !this._equityPoints?.length) return;
        const vals = this._equityPoints.map(p => p.value);
        const dataMax = Math.max(...vals, 0);
        const dataMin = Math.min(...vals, 0);
        const dataRange = Math.max(dataMax - dataMin, 1);
        const maxPad = dataRange * 2.5; // allow panning 2.5× range beyond data edges
        try {
          const visRange = ps.getVisiblePriceRange?.();
          if (!visRange) return;
          const { minValue, maxValue } = visRange;
          const clampedMin = Math.max(minValue, dataMin - maxPad);
          const clampedMax = Math.min(maxValue, dataMax + maxPad);
          if (clampedMin !== minValue || clampedMax !== maxValue) {
            ps.applyOptions({ autoScale: false });
            // LWC v4: use setVisiblePriceRange if available
            if (typeof ps.setVisiblePriceRange === 'function') {
              ps.setVisiblePriceRange({ minValue: clampedMin, maxValue: clampedMax });
            }
          }
        } catch (_e) { /* ignore */ }
      };
      this._lwChart.subscribeCrosshairMove(clampPriceScale);
      this._priceClampUnsub = () => {
        try { this._lwChart.unsubscribeCrosshairMove(clampPriceScale); } catch (_e) { /* gone */ }
      };
    }

    if (this.options.showTradeExcursions) {
      requestAnimationFrame(() => requestAnimationFrame(() => this._buildExcursionSeries()));
    }

    // ── 5. HTML tooltip ─────────────────────────────────────────────────────
    this._buildTooltip(data, isPercent);
  }

  _buildEquityPoints(timestamps, equity, isPercent) {
    // Always display P&L (equity - initialCapital).
    // In percent mode: ((equity - base) / base) * 100
    // In absolute mode: equity - base   (so zero = break-even)
    // base = initialCapital so that the zero line truly means "no profit/loss".
    const base = this.initialCapital;
    const raw = [];

    for (let i = 0; i < timestamps.length; i++) {
      const v = equity[i];
      if (v === null || v === undefined) continue;
      const time = this._toUnixSec(timestamps[i]);
      if (!time) continue;
      const pnl = v - base;
      raw.push({ time, value: isPercent ? (pnl / base) * 100 : pnl });
    }

    raw.sort((a, b) => a.time - b.time);
    return this._dedup(raw);
  }

  _buildBHSeries(data, isPercent) {
    const bh = data.bh_equity || [];
    const ts = data.timestamps || [];
    if (!bh.length || !ts.length) return;

    // P&L from initial_capital so that BH zero line = equity zero line = break-even.
    // Using this.initialCapital (same base as equity series) so both graphs are
    // directly comparable on the same axis.
    const base = this.initialCapital;
    const raw = [];

    for (let i = 0; i < Math.min(ts.length, bh.length); i++) {
      const v = bh[i];
      if (v == null) continue;
      const time = this._toUnixSec(ts[i]);
      if (!time) continue;
      const pnl = v - base;
      raw.push({ time, value: isPercent ? (pnl / base) * 100 : pnl });
    }

    raw.sort((a, b) => a.time - b.time);
    const points = this._dedup(raw);
    if (!points.length) return;

    this._bhSeries = this._lwChart.addSeries(LightweightCharts.LineSeries, {
      color: '#2962ff',              // TV-style: bright blue — matches legend badge colour
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerRadius: 4,
      title: 'B&H'
    });
    this._bhSeries.setData(points);

    // Same autoscale logic as equity: always include 0 with 3% padding.
    this._bhSeries.applyOptions({
      autoscaleInfoProvider: () => {
        const pvals = points.map(p => p.value);
        if (!pvals.length) return null;
        const maxV = Math.max(...pvals, 0);
        const minV = Math.min(...pvals, 0);
        const range = Math.max(maxV - minV, 1);
        const pad = range * 0.03;
        return {
          priceRange: {
            minValue: minV - pad,
            maxValue: maxV + pad
          },
          margins: { above: 2, below: 2 }
        };
      }
    });
  }

  // ─── MFE/MAE HISTOGRAM SERIES ─────────────────────────────────────────────
  //
  // KEY DESIGN: bars are on the SAME 'right' scale as equity, and are added
  // to the chart BEFORE the equity series so they render BEHIND it (TV z-order
  // = add order: first added = bottom layer).
  //
  // When showTradeExcursions=true at render time, empty bar series are created
  // in _buildSeries() BEFORE equity is added.  _buildExcursionSeries() then
  // fills them with data (or creates them if called from toggleTradeExcursions).
  //
  // Bar values are expressed in equity P&L units (USDT/%) so the zero of the
  // bars IS the zero of the equity axis — they track together automatically.
  // The equity autoscaleInfoProvider reserves ±budget space so bars stay
  // visible even when the equity line is far below zero.

  _buildExcursionSeries() {
    if (!this._lwChart || !this.trades.length || !this._equityPoints?.length) return;
    // Prevent double-build: if already building, cancel and restart
    if (this._excursionBuildPending) return;
    this._excursionBuildPending = true;
    // Tear down everything from any previous build before creating new canvas
    this._removeExcursionSeries();
    if (this.container) {
      this.container.querySelectorAll('canvas[data-excursion]').forEach(c => c.remove());
    }
    // Use mfe_pct / mae_pct so bars are proportional regardless of position size
    // and robust against zero/negative absolute values in old cached backtests.
    // Fallback: derive pct from absolute USD ÷ initial_capital if pct absent.
    const ic = this.initialCapital || 10000;
    const getMfePct = (t) => {
      const pct = Math.abs(Number(t.mfe_pct ?? 0));
      if (pct > 0) return pct;
      const abs = Math.abs(Number(t.mfe ?? 0));
      return abs > 0 ? (abs / ic * 100) : 0;
    };
    const getMaePct = (t) => {
      const pct = Math.abs(Number(t.mae_pct ?? 0));
      if (pct > 0) return pct;
      const abs = Math.abs(Number(t.mae ?? 0));
      return abs > 0 ? (abs / ic * 100) : 0;
    };

    const allMfePct = this.trades.map(getMfePct);
    const allMaePct = this.trades.map(getMaePct);
    const maxMfePct = allMfePct.length ? Math.max(...allMfePct.filter(v => v > 0), 0) : 0;
    const maxMaePct = allMaePct.length ? Math.max(...allMaePct.filter(v => v > 0), 0) : 0;

    // ── Do NOT extend the equity Y-axis for bars ──
    // The old approach expanded the axis to fit MAE in USD which compressed
    // the equity scale and made bars look tiny. Instead we use a normalized
    // pixel zone anchored at the zero line — matching TradingView's appearance.

    // ── Canvas overlay ──
    const canvas = document.createElement('canvas');
    canvas.dataset.excursion = '1';
    canvas.style.cssText = [
      'position:absolute', 'top:0', 'left:0',
      'width:100%', 'height:100%',
      'pointer-events:none', 'z-index:2'
    ].join(';');
    this.container.appendChild(canvas);
    this._excursionCanvas = canvas;
    this._excursionBuildPending = false; // allow future rebuilds

    // ── Percentage-based bar heights (TV-parity) ──
    const chart = this._lwChart;
    const trades = this.trades;
    const self = this;

    const draw = () => {
      if (!self._excursionCanvas || !chart) return;

      const W = self.container.clientWidth;
      const H = self.container.clientHeight;
      if (W === 0 || H === 0) return;
      const tsWidth = chart.timeScale().width() || W;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      const ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, W, H);

      // ── Zero Y: use actual price-axis coordinate of price=0 from equity series ──
      // This aligns the bar zero-line exactly with the equity chart's break-even line.
      // Fallback to a fixed bottom band if the price scale isn't ready yet.
      const equitySeries = self._equitySeries;
      let zeroY = null;
      if (equitySeries) {
        try { zeroY = equitySeries.priceToCoordinate(0); } catch (_e) { zeroY = null; }
      }
      // If price=0 is off-screen (above chart top or below time-axis), clamp to
      // a reasonable default so bars are still visible.
      if (zeroY == null || zeroY < 0 || zeroY > H) {
        zeroY = H * 0.925; // fallback: near the bottom
      }
      // halfBand: fixed pixel height calculated from the "ideal" zero position
      // (zeroY ≈ 72% of chart height — where bars look tallest and symmetric).
      // Using H * 0.72 as the reference so the band size never changes when
      // the user pans up/down; only zeroY (the anchor point) moves.
      // _barScale (1.0 / 0.65 / 0.35) is set by the size toggle buttons.
      const idealZeroY = H * 0.72;
      const halfBand = Math.max(Math.min(H - idealZeroY, idealZeroY * 0.4), 8) * 0.50 * (self._barScale ?? 1.0);

      // Centre-line separator across the time-scale pane only
      ctx.strokeStyle = 'rgba(120,123,134,0.5)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, zeroY);
      ctx.lineTo(tsWidth, zeroY);
      ctx.stroke();

      // ── Growth / Drawdown strips (TV-style segments below time axis) ──────
      // Drawn as thin coloured rectangles just below the time scale bar.
      // Green = growth segment, Red = drawdown segment.
      // Position: bottom 6px of the canvas (below LWC time axis ~34px tall).
      const tsApi = chart.timeScale();
      const ecPts = self._equityPoints || []; // [{time, value}] sorted asc

      const timeAxisH = 34;         // LWC time-scale row height (px)
      const stripH = 5;             // height of colour strip (sits INSIDE the time-axis zone)
      const ddHistH = 36;           // height of drawdown histogram zone (px) — +50%
      // Growth/drawdown colour strips go BELOW the time axis (last stripH px of canvas)
      const stripY = H - stripH;
      // DD histogram sits ABOVE the time axis
      const ddHistBottom = H - timeAxisH;

      {
        const segs = self._gdSegments || [];
        if (segs.length > 0) {
          segs.forEach(seg => {
            const tStart = self._toUnixSec(seg.startTime);
            const tEnd = self._toUnixSec(seg.endTime);
            if (!tStart || !tEnd) return;
            const xStart = tsApi.timeToCoordinate(tStart);
            const xEnd = tsApi.timeToCoordinate(tEnd);
            if (xStart == null || xEnd == null) return;
            const x1 = Math.min(xStart, xEnd);
            const x2 = Math.max(xStart, xEnd);
            if (x2 < 0 || x1 > tsWidth) return;
            const clampedX1 = Math.max(x1, 0);
            const clampedX2 = Math.min(x2, tsWidth);
            ctx.fillStyle = seg.kind === 'growth'
              ? 'rgba(38,166,154,0.90)'
              : 'rgba(239,83,80,0.90)';
            ctx.fillRect(clampedX1, stripY, clampedX2 - clampedX1, stripH);
          });
        }
      }

      // ── Drawdown histogram (TV-style column plot below equity zero-line) ───
      // Shows the per-bar drawdown from the equity peak as a column chart.
      // Rendered in a dedicated band (ddHistH px tall) just above the colour strip.
      // Each column: red (darker) proportional to drawdown depth (0–maxDD %).
      // Right-side label: "0%" at top, "-maxDD%" at bottom (drawn as small text).
      {
        const ddPts = self._ddPoints;  // [{time, ddPct}] precomputed, 0 ≤ ddPct
        if (ddPts && ddPts.length > 1) {
          const maxDDPct = self._ddMaxPct || 1;  // avoid /0

          // Thin separator line above the histogram zone
          ctx.strokeStyle = 'rgba(120,123,134,0.25)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(0, ddHistBottom - ddHistH);
          ctx.lineTo(tsWidth, ddHistBottom - ddHistH);
          ctx.stroke();

          // Right-side scale labels
          ctx.font = '9px -apple-system,BlinkMacSystemFont,sans-serif';
          ctx.fillStyle = 'rgba(120,123,134,0.75)';
          ctx.textAlign = 'right';
          ctx.textBaseline = 'top';
          ctx.fillText('0%', tsWidth - 2, ddHistBottom - ddHistH + 1);
          ctx.textBaseline = 'bottom';
          ctx.fillText(`-${maxDDPct.toFixed(1)}%`, tsWidth - 2, ddHistBottom - 1);

          // Draw each column
          for (let di = 0; di < ddPts.length; di++) {
            const pt = ddPts[di];
            const x = tsApi.timeToCoordinate(pt.time);
            if (x == null || x < 0 || x > tsWidth) continue;

            const ratio = Math.min(pt.ddPct / maxDDPct, 1);
            if (ratio < 0.001) continue;

            const colH = Math.max(ratio * ddHistH, 1);
            const colY = ddHistBottom - colH;

            // Width: match MFE/MAE bar width logic (at least 1px, max 4px)
            const colW = Math.max(
              di + 1 < ddPts.length
                ? (() => {
                  const xNext = tsApi.timeToCoordinate(ddPts[di + 1].time);
                  return xNext != null ? Math.max(Math.round(Math.abs(xNext - x) - 1), 1) : 2;
                })()
                : 2,
              1
            );

            // Colour intensity: deeper drawdown = more opaque red
            const alpha = 0.35 + ratio * 0.50;
            ctx.fillStyle = `rgba(239,83,80,${alpha.toFixed(2)})`;
            ctx.fillRect(x - colW / 2, colY, colW, colH);
          }
        }
      }

      const n = trades.length;
      if (n === 0) return;

      // interpolateX: get pixel X for any unix-sec timestamp.
      // timeToCoordinate works only for exact series timestamps.
      // For trade exit times (not in series) we interpolate between the two
      // surrounding EC points that DO have valid pixel coords.
      const interpolateX = (targetSec) => {
        if (!targetSec) return null;
        // Try direct first (works if exitSec happens to be an EC timestamp)
        const direct = tsApi.timeToCoordinate(targetSec);
        if (direct != null) return direct;
        // Binary search for surrounding EC points
        let lo = 0, hi = ecPts.length - 1;
        while (lo < hi) {
          const mid = (lo + hi) >> 1;
          if (ecPts[mid].time < targetSec) lo = mid + 1; else hi = mid;
        }
        // lo = first EC point >= targetSec
        const iR = lo, iL = lo - 1;
        const xR = iR < ecPts.length ? tsApi.timeToCoordinate(ecPts[iR].time) : null;
        const xL = iL >= 0 ? tsApi.timeToCoordinate(ecPts[iL].time) : null;
        if (xL != null && xR != null) {
          const tL = ecPts[iL].time, tR = ecPts[iR].time;
          const frac = tR === tL ? 0 : (targetSec - tL) / (tR - tL);
          return xL + frac * (xR - xL);
        }
        return xL ?? xR ?? null;
      };

      // ── Step 1: get X for each trade ────────────────────────────────────
      // _tradeMarkerTimes[i] = equityPoints[i].time (exact EC series timestamp)
      // when trades.length === equityPoints.length (1:1 case).
      // timeToCoordinate knows these times → returns exact pixel X.
      // interpolateX is the fallback for the rare case they differ.
      const markerTimes = self._tradeMarkerTimes || [];
      const allXs = trades.map((_, idx) => interpolateX(markerTimes[idx]));

      // ── Step 2: compute bar width based on trade count + gap table ──────
      // Gap between bars (px):  ≤50→4, ≤100→3, ≤150→3, ≤200→2, >250→1
      // barWidth = pixelGapBetweenBars − gapPx  (fills available slot minus gap)
      const onScreenXs = allXs
        .filter(x => x != null && x >= 0 && x <= tsWidth)
        .sort((a, b) => a - b);
      const uniqueXs = onScreenXs.filter((x, i) => i === 0 || Math.abs(x - onScreenXs[i - 1]) > 0.5);

      // Gap px by trade count
      const gapPx = n <= 50 ? 4
        : n <= 100 ? 3
          : n <= 200 ? 2
            : 1;

      // Pixel distance between neighbouring bars (median of visible gaps)
      let slotPx = 0;
      if (uniqueXs.length >= 2) {
        const gaps = [];
        for (let i = 1; i < uniqueXs.length; i++) gaps.push(uniqueXs[i] - uniqueXs[i - 1]);
        gaps.sort((a, b) => a - b);
        slotPx = gaps[Math.floor(gaps.length * 0.50)] ?? gaps[0]; // median
      } else if (uniqueXs.length === 1 && n > 0) {
        slotPx = tsWidth / n; // single bar visible — estimate
      }

      // barW = slot minus gap, clamped to [2, 40]
      const globalBarW = slotPx > 0
        ? Math.min(Math.max(Math.round(slotPx - gapPx), 2), 40)
        : Math.max(Math.round(tsWidth / Math.max(n, 1) * 0.6), 2);

      // ── Step 3: draw each trade bar centred on its marker X ───────────────
      trades.forEach((trade, idx) => {
        const cx = allXs[idx];
        if (cx == null) return;
        if (cx < -(globalBarW * 2) || cx > tsWidth + globalBarW * 2) return;

        const left = cx - globalBarW / 2;
        const barW = globalBarW;

        const mfePct = getMfePct(trade);
        const maePct = getMaePct(trade);

        if (mfePct > 0 && maxMfePct > 0) {
          const bh = Math.max((mfePct / maxMfePct) * halfBand, 1);
          ctx.fillStyle = 'rgba(38,166,154,0.70)';
          ctx.fillRect(left, zeroY - bh, barW, bh);
        }
        if (maePct > 0 && maxMaePct > 0) {
          const bh = Math.max((maePct / maxMaePct) * halfBand, 1);
          ctx.fillStyle = 'rgba(239,83,80,0.70)';
          ctx.fillRect(left, zeroY, barW, bh);
        }
      });

      if (!self._excursionLogged) {
        self._excursionLogged = true;
        const vis = allXs.filter(x => x != null && x >= 0 && x <= tsWidth).length;
        console.log(`[EX] tsWidth=${tsWidth} uniqueXs=${uniqueXs.length} globalBarW=${globalBarW} visible=${vis}/${n}`);
      }
    };

    // Redraw on every scroll/scale change
    const scheduleRedraw = () => {
      if (self._excursionRAF) cancelAnimationFrame(self._excursionRAF);
      self._excursionRAF = requestAnimationFrame(draw);
    };

    chart.timeScale().subscribeVisibleLogicalRangeChange(scheduleRedraw);
    chart.subscribeCrosshairMove(scheduleRedraw);
    this._excursionRedraw = scheduleRedraw;
    this._excursionUnsubscribe = () => {
      try { chart.timeScale().unsubscribeVisibleLogicalRangeChange(scheduleRedraw); } catch (_e) { /* gone */ }
      try { chart.unsubscribeCrosshairMove(scheduleRedraw); } catch (_e) { /* gone */ }
    };

    // Also redraw on container resize
    if (this._resizeObserver) {
      this._resizeObserver.observe(this.container);
    }

    // Initial draw
    requestAnimationFrame(() => requestAnimationFrame(draw));
  }

  _removeExcursionSeries() {
    if (this._excursionUnsubscribe) {
      this._excursionUnsubscribe();
      this._excursionUnsubscribe = null;
    }
    if (this._excursionRAF) {
      cancelAnimationFrame(this._excursionRAF);
      this._excursionRAF = null;
    }
    if (this._excursionCanvas) {
      this._excursionCanvas.remove();
      this._excursionCanvas = null;
    }
    if (this._mfeSeries) {
      try { this._lwChart.removeSeries(this._mfeSeries); } catch (e) { /* gone */ }
      this._mfeSeries = null;
    }
    if (this._maeSeries) {
      try { this._lwChart.removeSeries(this._maeSeries); } catch (e) { /* gone */ }
      this._maeSeries = null;
    }
    this._budgetMfe = 0;
    this._budgetMae = 0;
    if (this._equitySeries) {
      this._equitySeries.applyOptions({});  // recompute — no budget reserved
    }
  }

  // ─── HTML TOOLTIP ──────────────────────────────────────────────────────────

  _buildTooltip(data, isPercent) {
    if (!this._lwChart) return;
    const self = this;  // capture for callbacks below

    let tt = this.container.querySelector('.lwc-tt');
    if (!tt) {
      tt = document.createElement('div');
      tt.className = 'lwc-tt';
      // TV-style tooltip: dark semi-transparent, subtle border, no shadow
      tt.style.cssText = [
        'position:absolute',
        'min-width:210px',
        'padding:10px 12px 8px',
        'background:rgba(19,23,34,0.93)',
        'border:1px solid rgba(255,255,255,0.08)',
        'border-radius:4px',
        'color:#d1d4dc',
        'font-size:12px',
        'font-family:-apple-system,BlinkMacSystemFont,"Trebuchet MS",Roboto,Ubuntu,sans-serif',
        'line-height:1.5',
        'pointer-events:none',
        'display:none',
        'z-index:20',
        'white-space:nowrap'
      ].join(';');
      this.container.appendChild(tt);
    }

    const equity = data.equity || [];
    const timestamps = data.timestamps || [];
    const base = equity[0] || this.initialCapital;

    // Pre-compute growth/drawdown segments (TV-like "Рост средств / Просадка средств")
    const gdSegments = (() => {
      const n = Math.min(timestamps.length, equity.length);
      if (n < 2) return [];

      const num = (v) => {
        const x = Number(v);
        return Number.isFinite(x) ? x : 0;
      };

      const segments = [];
      let regime = 'growth';
      let segStart = 0;
      let hwm = num(equity[0]);
      let ddMin = hwm;
      let ddMinIdx = 0;

      for (let i = 1; i < n; i += 1) {
        const v = num(equity[i]);
        if (regime === 'growth') {
          if (v >= hwm) {
            hwm = v;
          } else {
            const start = segStart;
            const end = i - 1;
            if (end > start) {
              const startV = num(equity[start]);
              const endV = num(equity[end]);
              const absChange = endV - startV;
              const pctChange = startV !== 0 ? absChange / startV : 0;
              segments.push({
                kind: 'growth',
                startIndex: start,
                endIndex: end,
                startTime: timestamps[start],
                endTime: timestamps[end],
                absChange,
                pctChange
              });
            }
            regime = 'drawdown';
            segStart = end;
            ddMin = v;
            ddMinIdx = i;
          }
        } else {
          if (v <= ddMin) {
            ddMin = v;
            ddMinIdx = i;
          }
          if (v >= hwm) {
            const start = segStart;
            const end = ddMinIdx;
            if (end > start) {
              const startV = num(equity[start]);
              const endV = num(equity[end]);
              const absChange = startV - endV;
              const pctChange = startV !== 0 ? absChange / startV : 0;
              segments.push({
                kind: 'drawdown',
                startIndex: start,
                endIndex: end,
                startTime: timestamps[start],
                endTime: timestamps[end],
                absChange,
                pctChange
              });
            }
            regime = 'growth';
            segStart = end;
            hwm = v;
          }
        }
      }

      const lastIdx = n - 1;
      if (segStart < lastIdx) {
        const start = segStart;
        const end = lastIdx;
        const startV = num(equity[start]);
        const endV = num(equity[end]);
        if (end > start) {
          if (regime === 'growth') {
            const absChange = endV - startV;
            const pctChange = startV !== 0 ? absChange / startV : 0;
            segments.push({
              kind: 'growth',
              startIndex: start,
              endIndex: end,
              startTime: timestamps[start],
              endTime: timestamps[end],
              absChange,
              pctChange
            });
          } else {
            // Drawdown segment: find the deepest point for absChange/pctChange,
            // but extend the visual strip all the way to the last data point
            // so the colour doesn't cut off mid-chart.
            let minV = startV;
            for (let j = start; j <= end; j += 1) {
              const vj = num(equity[j]);
              if (vj < minV) minV = vj;
            }
            const absChange = startV - minV;
            const pctChange = startV !== 0 ? absChange / startV : 0;
            segments.push({
              kind: 'drawdown',
              startIndex: start,
              endIndex: end,          // extend to last point, not just the minimum
              startTime: timestamps[start],
              endTime: timestamps[end],
              absChange,
              pctChange
            });
          }
        }
      }

      return segments;
    })();

    // Save segments so the canvas overlay can draw growth/drawdown strips
    this._gdSegments = gdSegments;
    this._gdTimestamps = timestamps;

    // ── Pre-compute per-point drawdown series for the histogram ──────────────
    // ddPct[i] = (peak_equity - equity[i]) / peak_equity * 100  (always ≥ 0)
    // Stored as [{time (unix sec), ddPct}] aligned with _equityPoints.
    {
      const n = Math.min(timestamps.length, equity.length);
      const ddPts = [];
      let peak = Number(equity[0]) || 0;
      let maxDDPct = 0;
      const num = (v) => { const x = Number(v); return Number.isFinite(x) ? x : 0; };
      for (let i = 0; i < n; i++) {
        const v = num(equity[i]);
        if (v > peak) peak = v;
        const t = this._toUnixSec(timestamps[i]);
        if (!t) continue;
        const ddPct = peak > 0 ? Math.max((peak - v) / peak * 100, 0) : 0;
        ddPts.push({ time: t, ddPct });
        if (ddPct > maxDDPct) maxDDPct = ddPct;
      }
      this._ddPoints = ddPts;
      this._ddMaxPct = maxDDPct > 0 ? maxDDPct : 1;
    }

    // Map each equity point index to its growth/drawdown segment
    const gdIndexToSeg = new Array(timestamps.length).fill(null);
    gdSegments.forEach((seg) => {
      for (let i = seg.startIndex; i <= seg.endIndex && i < gdIndexToSeg.length; i += 1) {
        gdIndexToSeg[i] = seg;
      }
    });

    // Pre-compute: marker time → { trade, tradeNum, cumPnl, segIdx }
    // _tradeMarkerTimes[i] is already nudged (unique). We use it as the key.
    // cumPnl and segIdx are derived from the original equity[]/timestamps[] arrays.
    //
    // When trades.length === timestamps.length (1:1), trade[i] ↔ equity[i] by index.
    // Otherwise we find the closest timestamp to the trade's exit_time.
    const timeToTrade = new Map(); // nudgedMarkerTime → { trade, tradeNum, cumPnl, segIdx }

    if (this._tradeMarkerTimes && this._tradeMarkerTimes.length === this.trades.length) {
      const oneToOne = (this.trades.length === timestamps.length);
      this.trades.forEach((trade, i) => {
        const mt = this._tradeMarkerTimes[i];
        if (!mt) return;

        let cumPnl = 0;
        let segIdx = 0;

        if (oneToOne) {
          // Direct index alignment: trade[i] ↔ timestamps[i] ↔ equity[i]
          cumPnl = (equity[i] != null ? equity[i] : 0) - base;
          segIdx = i;
        } else {
          // Find the timestamps index closest to this trade's exit_time
          const exitMs = trade.exit_time ? this._toEpochMs(trade.exit_time) : null;
          if (exitMs != null) {
            let bestIdx = 0, bestDiff = Infinity;
            for (let j = 0; j < timestamps.length; j++) {
              const diff = Math.abs(new Date(timestamps[j]).getTime() - exitMs);
              if (diff < bestDiff) { bestDiff = diff; bestIdx = j; }
            }
            cumPnl = (equity[bestIdx] != null ? equity[bestIdx] : 0) - base;
            segIdx = bestIdx;
          }
        }

        timeToTrade.set(mt, { trade, tradeNum: i + 1, cumPnl, segIdx });
      });
    }

    // Helper: one TV-style row — coloured dot + label + right-aligned value
    const tvRow = (dotColor, label, value, valueColor) => {
      const dot = dotColor
        ? `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${dotColor};margin-right:6px;flex-shrink:0"></span>`
        : '<span style="display:inline-block;width:8px;margin-right:6px;flex-shrink:0"></span>';
      const vc = valueColor || '#d1d4dc';
      return '<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;padding:1px 0">'
        + `<span style="display:flex;align-items:center;color:#787b86;font-size:11px">${dot}${label}</span>`
        + `<span style="color:${vc};font-size:12px;font-weight:500">${value}</span>`
        + '</div>';
    };

    this._lwChart.subscribeCrosshairMove((param) => {
      if (!param.point || !param.time || param.point.x < 0) {
        tt.style.display = 'none';
        return;
      }

      // param.time is in seconds (LWC internal time).
      // Find the trade marker whose time is closest to the crosshair.
      // No threshold — always show tooltip for the nearest marker, same as TV.
      const cursorSec = param.time;
      const mts = self._tradeMarkerTimes || [];
      let bestIdx = -1, minD = Infinity;
      for (let i = 0; i < mts.length; i++) {
        if (!mts[i]) continue;
        const d = Math.abs(mts[i] - cursorSec);
        if (d < minD) { minD = d; bestIdx = i; }
      }
      if (bestIdx === -1) { tt.style.display = 'none'; return; }

      const bestMarkerTime = mts[bestIdx];
      const entry = timeToTrade.get(bestMarkerTime);
      if (!entry) { tt.style.display = 'none'; return; }

      const { trade, tradeNum, cumPnl, segIdx } = entry;
      const rawPnl = cumPnl;
      const side = (trade.direction || trade.side || 'long');
      const sideLabel = side === 'long' ? 'Long' : 'Short';

      // Exit datetime in TV format: "Mon, Mar 10, 2025, 21:30"
      const exitDate = trade.exit_time ? new Date(this._toEpochMs(trade.exit_time)) : null;
      const exitDateStr = exitDate
        ? exitDate.toLocaleString('en-US', {
          weekday: 'short', month: 'short', day: 'numeric',
          year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
          timeZone: 'Europe/Moscow'
        })
        : '';

      // Cumulative P&L colour
      const pnlCol = rawPnl >= 0 ? '#26a69a' : '#ef5350';
      const pnlSign = rawPnl >= 0 ? '+' : '';
      const pnlStr = isPercent
        ? `${pnlSign}${((rawPnl / base) * 100).toFixed(2)}%`
        : `${pnlSign}${this._fmtUsdt(rawPnl)}`;

      // MFE / MAE
      const mfeUsdt = Math.abs(trade.mfe ?? 0);
      const maeUsdt = Math.abs(trade.mae ?? 0);
      const mfePct = Math.abs(trade.mfe_pct ?? trade.mfe_percent ?? 0);
      const maePct = Math.abs(trade.mae_pct ?? trade.mae_percent ?? 0);

      const mfeStr = isPercent
        ? `+${mfePct.toFixed(2)}%`
        : `${mfeUsdt > 0 ? '+' : ''}${this._fmtUsdt(mfeUsdt)}`;
      const maeStr = isPercent
        ? `-${maePct.toFixed(2)}%`
        : (maeUsdt > 0 ? `-${this._fmtUsdt(maeUsdt)}` : '0.00 USDT');

      const seg = gdIndexToSeg[segIdx];

      let html = '';
      // Header
      html += `<div style="text-align:center;color:#d1d4dc;font-size:12px;font-weight:600;margin-bottom:7px">Trade #${tradeNum} ${sideLabel}</div>`;
      // Divider
      html += '<div style="border-top:1px solid rgba(255,255,255,0.07);margin-bottom:6px"></div>';
      // Rows
      html += tvRow('#26a69a', 'Cumulative P&L', pnlStr, pnlCol);
      html += tvRow('#26a69a', 'Favorable excursion', mfeStr, '#26a69a');
      html += tvRow('#ef5350', 'Adverse excursion', maeStr, '#ef5350');

      if (seg) {
        const isGrowth = seg.kind === 'growth';
        const label = isGrowth ? 'Рост средств' : 'Просадка средств';
        const amountAbs = Math.abs(seg.absChange);
        const pctAbs = Math.abs(seg.pctChange * 100);
        const sign = isGrowth ? '+' : '-';

        const amountStr = `${sign}${amountAbs.toLocaleString('en-US', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2
        })} USDT`;
        const pctStr = `${pctAbs.toFixed(2)}%`;

        const startDate = seg.startTime ? new Date(seg.startTime) : null;
        const endDate = seg.endTime ? new Date(seg.endTime) : null;
        const rangeStr = startDate && endDate
          ? `${startDate.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Europe/Moscow' })} — ${endDate.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Europe/Moscow' })}`
          : '';

        html += '<div style="border-top:1px solid rgba(255,255,255,0.07);margin:6px 0 4px"></div>';
        html += tvRow(
          isGrowth ? '#22c55e' : '#f97373',
          label,
          `${amountStr} (${pctStr})`,
          isGrowth ? '#22c55e' : '#f97373'
        );
        if (rangeStr) {
          html += `<div style="text-align:left;color:#787b86;font-size:11px;margin-top:2px">${rangeStr}</div>`;
        }
      }
      // Footer: exit datetime
      if (exitDateStr) {
        html += '<div style="border-top:1px solid rgba(255,255,255,0.07);margin-top:6px;padding-top:5px">';
        html += `<div style="text-align:center;color:#787b86;font-size:11px">${exitDateStr}</div>`;
        html += '</div>';
      }

      tt.innerHTML = html;
      tt.style.display = 'block';

      // Position tooltip — prefer right of cursor, flip left if near edge
      const tw = tt.offsetWidth, th = tt.offsetHeight;
      const cx = param.point.x, cy = param.point.y;
      const cw = this.container.clientWidth, ch = this.container.clientHeight;
      const leftX = cx + tw + 20 < cw ? cx + 14 : cx - tw - 14;
      const topY = Math.min(Math.max(cy - th / 2, 4), ch - th - 4);
      tt.style.left = `${leftX}px`;
      tt.style.top = `${topY}px`;
    });

    // ── Click on chart → highlight trade row in list + cursor flash ──────────
    // LWC v4 exposes subscribeClick(handler) on the chart instance.
    // On click we find the nearest trade marker and dispatch a custom DOM event
    // so backtest_results.js can scroll the trades list to the matching row.
    if (typeof this._lwChart.subscribeClick === 'function') {
      this._lwChart.subscribeClick((param) => {
        if (!param.time) return;
        const cursorSec = param.time;
        const mts = self._tradeMarkerTimes || [];
        let bestIdx = -1, minD = Infinity;
        for (let i = 0; i < mts.length; i++) {
          if (!mts[i]) continue;
          const d = Math.abs(mts[i] - cursorSec);
          if (d < minD) { minD = d; bestIdx = i; }
        }
        if (bestIdx === -1) return;

        const bestTime = mts[bestIdx];
        const entry = timeToTrade.get(bestTime);
        if (!entry) return;

        // Dispatch custom event — backtest_results.js listens on document
        self.container.dispatchEvent(new CustomEvent('equityChartTradeClick', {
          bubbles: true,
          detail: {
            tradeIndex: bestIdx,          // 0-based index in trades array
            tradeNum: entry.tradeNum,     // 1-based display number
            trade: entry.trade,
            exitTime: entry.trade.exit_time || null
          }
        }));

        // Flash the clicked marker: brief highlight via CSS class on container
        self.container.classList.add('equity-click-flash');
        setTimeout(() => self.container.classList.remove('equity-click-flash'), 300);
      });
    }
  }

  // ─── REGIME OVERLAY COMPAT ─────────────────────────────────────────────────
  // backtest_results.js mutates this._regimeAnnotations then calls .chart.update()
  // We translate Chart.js box annotation {xMin,xMax,backgroundColor} → TV histogram bands

  _applyRegimeAnnotations() {
    if (!this._lwChart || !this._equitySeries) return;

    // Remove previous regime series
    this._regimeRects.forEach((s) => {
      try { this._lwChart.removeSeries(s); } catch (e) { /* already removed */ }
    });
    this._regimeRects.clear();

    const data = this.data;
    if (!data?.timestamps?.length) return;

    Object.entries(this._regimeAnnotations).forEach(([key, box]) => {
      if (!key.startsWith('regime_')) return;

      const si = Math.max(0, Math.round((box.xMin || 0) + 0.5));
      const ei = Math.min(data.timestamps.length - 1, Math.round((box.xMax || 0) - 0.5));
      if (si > ei) return;

      const t1 = this._toUnixSec(data.timestamps[si]);
      const t2 = this._toUnixSec(data.timestamps[ei]);
      if (!t1 || !t2) return;

      const col = box.backgroundColor || 'rgba(158,158,158,0.08)';
      const eq = (data.equity || []).filter(v => v != null);
      const top = eq.length ? Math.max(...eq) * 1.10 : 12000;

      const series = this._lwChart.addSeries(LightweightCharts.HistogramSeries, {
        color: col,
        priceScaleId: '',
        lastValueVisible: false,
        priceLineVisible: false,
        autoscaleInfoProvider: () => ({
          priceRange: { minValue: 0, maxValue: top }
        })
      });

      const pts = [];
      for (let i = si; i <= ei; i++) {
        const t = this._toUnixSec(data.timestamps[i]);
        if (t) pts.push({ time: t, value: top });
      }
      pts.sort((a, b) => a.time - b.time);
      const deduped = this._dedup(pts);
      if (deduped.length) {
        series.setData(deduped);
        this._regimeRects.set(key, series);
      }
    });
  }

  // ─── RESIZE OBSERVER ───────────────────────────────────────────────────────

  _setupResizeObserver() {
    if (this._resizeObserver) this._resizeObserver.disconnect();
    if (!window.ResizeObserver || !this._lwChart) return;

    // Observe the wrapper (parent of container) so panel collapse/expand triggers resize
    const watchTarget = this.container.parentElement || this.container;

    this._resizeObserver = new ResizeObserver(() => {
      if (!this._lwChart || !this.container) return;
      const newW = this.container.clientWidth;
      const newH = this.container.clientHeight || 400;
      if (newW > 0 && newH > 0) {
        this._lwChart.resize(newW, newH);
      }
    });
    this._resizeObserver.observe(watchTarget);
    // Also observe the container itself for height changes
    if (watchTarget !== this.container) {
      this._resizeObserver.observe(this.container);
    }
  }

  // ─── LEGEND CHECKBOXES ─────────────────────────────────────────────────────

  _setupLegendInteractivity() {
    const bhCb = document.getElementById('legendBuyHold');
    if (bhCb) {
      bhCb.onchange = () => {
        this.options.showBuyHold = bhCb.checked;
        if (this.data) this.render(this.data);
      };
    }

    const exCb = document.getElementById('legendTradesRunupDrawdown')
      || document.getElementById('legendTradesExcursions');
    if (exCb) {
      exCb.onchange = () => {
        this.toggleTradeExcursions(exCb.checked);
      };
    }

    // ── Bar size toggle buttons (100% / 65% / 35%) ──────────────────────────
    const barSizeBtns = document.querySelectorAll('.tv-bar-size-btn');
    barSizeBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const scale = parseFloat(btn.dataset.barScale ?? '1');
        this._barScale = scale;
        // Update active state
        barSizeBtns.forEach(b => b.classList.toggle('active', b === btn));
        // Redraw bars immediately
        if (this._excursionRedraw) this._excursionRedraw();
      });
    });
  }

  // ─── CLEANUP ───────────────────────────────────────────────────────────────

  _destroyInternal() {
    if (this._resizeObserver) { this._resizeObserver.disconnect(); this._resizeObserver = null; }
    if (this._clockInterval) { clearInterval(this._clockInterval); this._clockInterval = null; }
    if (this._clockEl && this._clockEl.parentNode) { this._clockEl.parentNode.removeChild(this._clockEl); this._clockEl = null; }
    if (this._priceClampUnsub) { this._priceClampUnsub(); this._priceClampUnsub = null; }
    // Properly remove ALL excursion canvases from the DOM (not just null the ref).
    // Without this, re-render() leaves orphaned canvases that produce duplicate bars.
    this._removeExcursionSeries();
    // Also nuke any stray canvas elements left by previous renders
    if (this.container) {
      this.container.querySelectorAll('canvas[data-excursion]').forEach(c => c.remove());
    }
    this._mfeSeries = null;
    this._maeSeries = null;
    this._budgetMfe = 0;
    this._budgetMae = 0;
    if (this._lwChart) { this._lwChart.remove(); this._lwChart = null; }
    this._equitySeries = null;
    this._bhSeries = null;
    this._equityPoints = null;
    this._dbgLogged = false;
    this._regimeRects.clear();
    this._regimeAnnotations = {};
    this.chart = null;
  }

  // ─── HELPERS ───────────────────────────────────────────────────────────────

  _toEpochMs(ts) {
    /** Convert timestamp to epoch milliseconds for reliable matching. */
    if (!ts) return null;
    if (typeof ts === 'number') {
      const val = ts > 1e12 ? ts : ts * 1000;
      return isNaN(val) ? null : Math.round(val);
    }
    // For ISO strings: if no timezone suffix, treat as UTC (add Z)
    const str = String(ts).trim();
    const hasTimezone = str.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(str);
    const normalized = hasTimezone ? str : str + 'Z';
    const ms = new Date(normalized).getTime();
    return isNaN(ms) ? null : Math.round(ms);
  }

  _toUnixSec(ts) {
    if (!ts) return null;
    const TZ = 10800; // UTC+3 shift: X-axis displays Moscow time labels
    if (typeof ts === 'number') {
      const ms = ts > 1e12 ? ts : ts * 1000;
      return isNaN(ms) ? null : Math.floor(ms / 1000) + TZ;
    }
    // For ISO strings: if no timezone suffix, treat as UTC (add Z)
    // This matches how the backend stores datetimes (all UTC)
    const str = String(ts).trim();
    const hasTimezone = str.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(str);
    const normalized = hasTimezone ? str : str + 'Z';
    const ms = new Date(normalized).getTime();
    return isNaN(ms) ? null : Math.floor(ms / 1000) + TZ;
  }

  _findEquityTimeForExit(exitEpochMs, maxWindowSec = Infinity) {
    /**
     * Find the closest equity point time (unix sec) for a given exit timestamp.
     * Uses binary search for efficiency on large equity curves.
     *
     * @param {number} exitEpochMs   - Exit time in epoch milliseconds
     * @param {number} maxWindowSec  - Max allowed distance in seconds (default: unlimited)
     * @returns {number|null}        - Closest equity point time in unix seconds, or null
     */
    if (!this._equityPoints || this._equityPoints.length === 0) return null;

    const targetTime = Math.floor(exitEpochMs / 1000);

    // Binary search for closest time
    let left = 0;
    let right = this._equityPoints.length - 1;

    while (left < right) {
      const mid = Math.floor((left + right) / 2);
      if (this._equityPoints[mid].time < targetTime) {
        left = mid + 1;
      } else {
        right = mid;
      }
    }

    // Check both neighbours to find the truly closest point
    const idx = left;
    let bestIdx = idx;
    if (idx > 0) {
      const diffPrev = Math.abs(this._equityPoints[idx - 1].time - targetTime);
      const diffCurr = Math.abs(this._equityPoints[idx].time - targetTime);
      bestIdx = diffPrev <= diffCurr ? idx - 1 : idx;
    }

    const bestDiff = Math.abs(this._equityPoints[bestIdx].time - targetTime);
    if (bestDiff > maxWindowSec) return null;   // outside allowed window

    return this._equityPoints[bestIdx].time;
  }

  _dedup(points) {
    const out = [];
    for (let i = 0; i < points.length; i++) {
      if (i === 0 || points[i].time !== points[i - 1].time) {
        out.push(points[i]);
      } else {
        out[out.length - 1] = points[i]; // keep last for same second
      }
    }
    return out;
  }

  _findTradeAtTime(timestamp) {
    if (!timestamp || !this.trades) return null;
    const ms = typeof timestamp === 'number'
      ? (timestamp > 1e12 ? timestamp : timestamp * 1000)
      : new Date(timestamp).getTime();
    return this.trades.find((t) => {
      const entry = this._toEpochMs(t.entry_time);
      const exit = t.exit_time ? this._toEpochMs(t.exit_time) : entry;
      return ms >= entry && ms <= exit;
    }) || null;
  }

  _fmt(value) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency', currency: 'USD',
      minimumFractionDigits: 2, maximumFractionDigits: 2
    }).format(value);
  }

  /** Format a USDT value in TradingView style: "133.31 USDT" (no $ sign) */
  _fmtUsdt(value) {
    const abs = Math.abs(value);
    const formatted = new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(abs);
    return `${formatted} USDT`;
  }
}

// ── Module exports ────────────────────────────────────────────────────────────
/* eslint-disable no-undef */
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TradingViewEquityChart;
}
/* eslint-enable no-undef */

window.TradingViewEquityChart = TradingViewEquityChart;
