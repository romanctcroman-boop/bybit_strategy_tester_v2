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
      showBuyHold: false,
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
    if (this.data) this.render(this.data);
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

    const h = this.options.height || this.container.clientHeight || 400;

    this._lwChart = LightweightCharts.createChart(this.container, {
      width: this.container.clientWidth,
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
        borderColor: 'rgba(48,54,61,0.8)'
      },
      timeScale: {
        borderColor: 'rgba(48,54,61,0.8)',
        timeVisible: true,
        secondsVisible: false
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true }
    });

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

    // ── 0. MFE/MAE histogram series — added FIRST so they render BEHIND equity ──
    // Bars share the same 'right' scale as equity so their zero IS the equity
    // zero line (TradingView-style anchoring).  The equity autoscaleInfoProvider
    // reserves ±budget space so bars stay visible even when equity is deeply
    // negative.
    if (this.options.showTradeExcursions) {
      this._mfeSeries = this._lwChart.addHistogramSeries({
        priceScaleId: 'right',
        lastValueVisible: false,
        priceLineVisible: false
      });
      this._maeSeries = this._lwChart.addHistogramSeries({
        priceScaleId: 'right',
        lastValueVisible: false,
        priceLineVisible: false
      });
    }

    // ── 1. Equity as BASELINE series — added AFTER bars so it draws ON TOP ──
    // We ALWAYS display P&L (equity − initialCapital), so baseValue = 0.
    this._equitySeries = this._lwChart.addBaselineSeries({
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
    // The MFE/MAE bars are on the same 'right' scale and grow from zero, so
    // we extend the price range to always include ±budgetMfe/Mae (set after
    // _buildExcursionSeries runs).  Before bars are built _budgetMfe = 0 so
    // the range is just the equity range — this is fine.
    this._equitySeries.applyOptions({
      autoscaleInfoProvider: () => {
        const vals = equityPoints.map(p => p.value);
        if (!vals.length) return null;
        const maxV = Math.max(...vals, 0);   // always ≥ 0
        const minV = Math.min(...vals, 0);   // always ≤ 0
        const range = Math.max(maxV - minV, 1);
        const pad = range * 0.03;            // 3% breathing room
        const budgetMfe = this._budgetMfe || 0;
        const budgetMae = this._budgetMae || 0;
        return {
          priceRange: {
            minValue: Math.min(minV - pad, -budgetMae),
            maxValue: Math.max(maxV + pad, budgetMfe)
          },
          margins: { above: 2, below: 2 }
        };
      }
    });
    // scaleMargins: reserve top 18% for MFE bars, bottom 18% for MAE bars.
    // Equity curve lives in the middle 64%, zero line stays near the top of
    // that zone when equity is deeply negative (typical losing strategy view).
    this._equitySeries.priceScale().applyOptions({
      scaleMargins: { top: 0.18, bottom: 0.18 }
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
    // Shown only when trades < 200 (strictly: 199 shown, 200 hidden).
    // size:0 is the smallest marker TV supports — roughly half of size:1.
    if (this.trades.length > 0 && this.trades.length < 200) {
      const markers = [];
      // Build a sorted array of EC times for binary search
      const ecTimesForMarkers = equityPoints.map(p => p.time);

      this.trades.forEach((trade) => {
        const exitSec = this._toUnixSec(trade.exit_time);
        if (!exitSec) return;

        // Binary search: find closest EC timestamp to trade exit_time
        let lo = 0, hi = ecTimesForMarkers.length - 1;
        while (lo < hi) {
          const mid = (lo + hi) >> 1;
          if (ecTimesForMarkers[mid] < exitSec) lo = mid + 1; else hi = mid;
        }
        if (lo > 0 && Math.abs(ecTimesForMarkers[lo - 1] - exitSec) < Math.abs(ecTimesForMarkers[lo] - exitSec)) lo--;
        const markerTime = ecTimesForMarkers[lo];
        if (!markerTime) return;

        const pnl = trade.pnl || 0;
        markers.push({
          time: markerTime,
          position: 'inBar',
          color: pnl >= 0 ? '#26a69a' : '#ef5350',
          shape: 'circle',
          size: 0
        });
      });
      if (markers.length > 0) {
        markers.sort((a, b) => a.time - b.time);
        this._equitySeries.setMarkers(markers);
      }
    }

    // ── 3. Buy & Hold ───────────────────────────────────────────────────────
    if (this.options.showBuyHold) {
      this._buildBHSeries(data, isPercent);
    }

    // ── 4. Fit view, then fill bar data ─────────────────────────────────────
    this._lwChart.timeScale().fitContent();

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
    const base = equity[0] || this.initialCapital;
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

    // Same convention as equity: show P&L from initial value (base)
    const base = bh[0] || this.initialCapital;
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

    this._bhSeries = this._lwChart.addLineSeries({
      color: 'rgba(120,123,134,0.85)',   // TV-style: muted grey, equity line stays dominant
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerRadius: 4,
      title: 'B&H'
    });
    this._bhSeries.setData(points);

    // Same autoscale logic as equity: always include 0 with 3% padding.
    // Also includes ±budget to match equity's reserved bar space.
    this._bhSeries.applyOptions({
      autoscaleInfoProvider: () => {
        const pvals = points.map(p => p.value);
        if (!pvals.length) return null;
        const maxV = Math.max(...pvals, 0);
        const minV = Math.min(...pvals, 0);
        const range = Math.max(maxV - minV, 1);
        const pad = range * 0.03;
        const budgetMfe = this._budgetMfe || 0;
        const budgetMae = this._budgetMae || 0;
        return {
          priceRange: {
            minValue: Math.min(minV - pad, -budgetMae),
            maxValue: Math.max(maxV + pad, budgetMfe)
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

    // In percent mode the equity axis shows % P&L, so use mfe_pct/mae_pct.
    // In absolute mode use mfe/mae (USDT) — same units as equity axis.
    const isPercent = this.options.displayMode === 'percent';

    // CRITICAL: Always use the correct field for the mode — never mix units!
    // In absolute mode: use mfe/mae (USD values from backend)
    // In percent mode: use mfe_pct/mae_pct (percentage values from backend)
    const getMfe = (t) => Math.abs(Number(isPercent
      ? (t.mfe_pct ?? t.mfe_percent ?? 0)  // Percent mode: use percentage fields only
      : (t.mfe ?? 0)));                     // Absolute mode: use USD fields only
    const getMae = (t) => Math.abs(Number(isPercent
      ? (t.mae_pct ?? t.mae_percent ?? 0)  // Percent mode: use percentage fields only
      : (t.mae ?? 0)));                     // Absolute mode: use USD fields only

    // Fixed chart-height budget for MFE/MAE bars (in price-axis units = equity P&L units).
    // We use the FULL equity axis range so bars always occupy the same visual fraction
    // of the chart regardless of which half of trades they belong to.
    const equityValues = this._equityPoints.map(p => p.value);
    const equityMax = Math.max(...equityValues, 0);
    const equityMin = Math.min(...equityValues, 0);
    const equityRange = Math.max(equityMax - equityMin, 1);

    // Each bar occupies up to 20% of the full equity axis height.
    const maxBarHeight = equityRange * 0.20;

    // ── Normalization: TV-style LINEAR scaling ──
    // Largest MFE/MAE bar = maxBarHeight (20% of equity range).
    // All others are proportional: a trade with half the max MFE gets half the bar.
    // This matches TradingView Strategy Tester which uses linear proportional bars
    // (large losses/wins → tall bars, small → short, visually intuitive).
    // Minimum visible floor: 4% of maxBarHeight so very small values are still seen.
    const allMfeRaw = this.trades.map(getMfe);
    const allMaeRaw = this.trades.map(getMae);
    const maxMfe = Math.max(...allMfeRaw, 1e-9);
    const maxMae = Math.max(...allMaeRaw, 1e-9);
    const minFloor = 0.04; // 4% of maxBarHeight = minimum visible bar height

    // Linear-scale a raw value to [minFloor..1] × maxBarHeight
    const linearScale = (val, maxVal) => {
      if (val <= 0) return 0;
      const ratio = val / maxVal;          // 0..1, linear
      return Math.max(ratio, minFloor);    // never below 4% floor
    };

    // Store for equity/BH autoscaleInfoProvider so they reserve the right gap.
    this._budgetMfe = maxBarHeight;
    this._budgetMae = maxBarHeight;

    // LWC histogram bars must use timestamps that exist in the chart's timeScale.
    // The timeScale is defined by the equity series (EC timestamps = bar open times).
    // Using arbitrary exit_time values causes bars to disappear because LWC can't
    // place them on unknown time positions.
    //
    // Strategy: map each trade to its closest EC timestamp (binary search).
    // Collision handling: if two trades map to the same EC slot, assign the second
    // trade to the nearest FREE adjacent EC slot (walk forward/backward).
    // This ensures every trade gets a visible bar with no overwrites.

    // Build sorted array of EC unix-sec times for fast lookup
    const ecTimes = this._equityPoints.map(p => p.time).sort((a, b) => a - b);

    // Binary search: index of closest EC time to targetSec
    const closestEcIdx = (targetSec) => {
      let lo = 0, hi = ecTimes.length - 1;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (ecTimes[mid] < targetSec) lo = mid + 1; else hi = mid;
      }
      if (lo > 0 && Math.abs(ecTimes[lo - 1] - targetSec) <= Math.abs(ecTimes[lo] - targetSec)) lo--;
      return lo;
    };

    // Find next free EC slot starting from idx, searching outward
    const usedSlots = new Set();
    const claimSlot = (startIdx) => {
      // Search forward then backward for a free EC slot
      for (let delta = 0; delta < ecTimes.length; delta++) {
        const fwd = startIdx + delta;
        if (fwd < ecTimes.length && !usedSlots.has(ecTimes[fwd])) {
          usedSlots.add(ecTimes[fwd]);
          return ecTimes[fwd];
        }
        const bwd = startIdx - delta;
        if (delta > 0 && bwd >= 0 && !usedSlots.has(ecTimes[bwd])) {
          usedSlots.add(ecTimes[bwd]);
          return ecTimes[bwd];
        }
      }
      return null; // shouldn't happen (more trades than EC points is impossible)
    };

    const mfeData = [];
    const maeData = [];

    this.trades.forEach((trade) => {
      const exitSec = this._toUnixSec(trade.exit_time);
      if (!exitSec) return;

      const idx = closestEcIdx(exitSec);
      const slot = claimSlot(idx);
      if (!slot) return;

      const mfe = getMfe(trade);
      const mae = getMae(trade);

      const scaledMfe = mfe > 0 ? linearScale(mfe, maxMfe) * maxBarHeight : 0;
      const scaledMae = mae > 0 ? linearScale(mae, maxMae) * maxBarHeight : 0;

      // TV uses a single uniform color for all MFE bars and a single color for
      // all MAE bars — no realized/unrealized tonal split.
      if (scaledMfe > 0) {
        mfeData.push({
          time: slot,
          value: scaledMfe,
          color: 'rgba(38,166,154,0.75)'   // teal — all MFE bars same color
        });
      }
      if (scaledMae > 0) {
        maeData.push({
          time: slot,
          value: -scaledMae,
          color: 'rgba(239,83,80,0.75)'    // red — all MAE bars same color
        });
      }
    });

    mfeData.sort((a, b) => a.time - b.time);
    maeData.sort((a, b) => a.time - b.time);

    // Both series on 'right' scale — same axis as equity.
    // autoscaleInfoProvider locks the data range to ±maxBarHeight so LWC
    // doesn't auto-zoom based on bar values (bars stay consistent height).
    const barOpts = {
      priceScaleId: 'right',
      lastValueVisible: false,
      priceLineVisible: false,
      autoscaleInfoProvider: () => ({
        priceRange: { minValue: -maxBarHeight, maxValue: maxBarHeight }
      })
    };

    if (this._mfeSeries) {
      this._mfeSeries.applyOptions(barOpts);
      this._mfeSeries.setData(mfeData);
    } else {
      this._mfeSeries = this._lwChart.addHistogramSeries(barOpts);
      this._mfeSeries.setData(mfeData);
    }

    if (this._maeSeries) {
      this._maeSeries.applyOptions({ ...barOpts });
      this._maeSeries.setData(maeData);
    } else {
      this._maeSeries = this._lwChart.addHistogramSeries({ ...barOpts });
      this._maeSeries.setData(maeData);
    }

    if (this._equitySeries) {
      this._equitySeries.applyOptions({});
    }
  }

  _removeExcursionSeries() {
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

    // Pre-compute: for each equity point index, which trade is it?
    // EC timestamps are bar open times (not exact exit times), so we use
    // closest-exit-time matching (within one timeframe bar = 4h window) rather
    // than the range check that misses points between trades.
    const ecIndexToTrade = new Array(timestamps.length).fill(null);
    if (this.trades && this.trades.length) {
      timestamps.forEach((ts, i) => {
        const ecMs = new Date(ts).getTime();
        let bestTrade = null;
        let bestDiff = Infinity;
        this.trades.forEach((t) => {
          if (!t.exit_time) return;
          const diff = Math.abs(new Date(t.exit_time).getTime() - ecMs);
          // Max window: 6 hours (covers ±1 bar on any supported timeframe up to 4h)
          if (diff < bestDiff && diff <= 6 * 3600 * 1000) {
            bestDiff = diff;
            bestTrade = t;
          }
        });
        ecIndexToTrade[i] = bestTrade;
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

      // Find closest equity index
      const ms = param.time * 1000;
      let ci = 0, minD = Infinity;
      for (let i = 0; i < timestamps.length; i++) {
        const d = Math.abs(new Date(timestamps[i]).getTime() - ms);
        if (d < minD) { minD = d; ci = i; }
      }

      const trade = ecIndexToTrade[ci];
      if (!trade) { tt.style.display = 'none'; return; }

      // ── TV-style header: "Trade #N Long/Short" centred ──
      const ev = equity[ci];
      const rawPnl = ev - base;   // cumulative P&L from start
      const side = (trade.direction || trade.side || 'long');
      const sideLabel = side === 'long' ? 'Long' : 'Short';

      // Find trade index for numbering
      const tradeIdx = this.trades.indexOf(trade);
      const tradeNum = tradeIdx >= 0 ? tradeIdx + 1 : '?';

      // Exit datetime in TV format: "Mon, Mar 10, 2025, 21:30"
      const exitDate = trade.exit_time ? new Date(trade.exit_time) : null;
      const exitDateStr = exitDate
        ? exitDate.toLocaleString('en-US', {
          weekday: 'short', month: 'short', day: 'numeric',
          year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false
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

      let html = '';
      // Header
      html += `<div style="text-align:center;color:#d1d4dc;font-size:12px;font-weight:600;margin-bottom:7px">Trade #${tradeNum} ${sideLabel}</div>`;
      // Divider
      html += '<div style="border-top:1px solid rgba(255,255,255,0.07);margin-bottom:6px"></div>';
      // Rows
      html += tvRow('#26a69a', 'Cumulative P&L', pnlStr, pnlCol);
      html += tvRow('#26a69a', 'Favorable excursion', mfeStr, '#26a69a');
      html += tvRow('#ef5350', 'Adverse excursion', maeStr, '#ef5350');
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

      const series = this._lwChart.addHistogramSeries({
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
  }

  // ─── CLEANUP ───────────────────────────────────────────────────────────────

  _destroyInternal() {
    if (this._resizeObserver) { this._resizeObserver.disconnect(); this._resizeObserver = null; }
    this._excursionCanvas = null;  // canvas no longer used
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
    if (typeof ts === 'number') {
      const ms = ts > 1e12 ? ts : ts * 1000;
      return isNaN(ms) ? null : Math.floor(ms / 1000);
    }
    // For ISO strings: if no timezone suffix, treat as UTC (add Z)
    // This matches how the backend stores datetimes (all UTC)
    const str = String(ts).trim();
    // If no timezone info present, append Z so Date() treats it as UTC
    // (matches backend's all-UTC storage)
    const hasTimezone = str.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(str);
    const normalized = hasTimezone ? str : str + 'Z';
    const ms = new Date(normalized).getTime();
    return isNaN(ms) ? null : Math.floor(ms / 1000);
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
      const entry = new Date(t.entry_time).getTime();
      const exit = t.exit_time ? new Date(t.exit_time).getTime() : entry;
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
