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
    // Normalise mfe/mae fields — accept mfe_pct, mfe_percent, or mfe (all %)
    this.trades = (data.trades || []).map((t) => ({
      ...t,
      mfe: Math.abs(Number(t.mfe_pct ?? t.mfe_percent ?? t.mfe ?? 0)),
      mae: Math.abs(Number(t.mae_pct ?? t.mae_percent ?? t.mae ?? 0))
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
    // In TV LW Charts z-order = add order: first added = bottom layer.
    // We create them empty now; data is filled in _buildExcursionSeries().
    // This guarantees equity line always draws on top of the bars.
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

    // autoscaleInfoProvider — locks the visible Y range to the UNION of:
    //   • equity P&L range  [minV … maxV]   (always includes 0)
    //   • bar zone          [-budgetMae … +budgetMfe]  (when excursions on)
    // A small pad (3%) is added above the equity max and below equity min
    // so the line never touches the chart edge.
    // The bar budget is NOT added on top of equity max — bars share the same
    // zero, so their zone is already accounted for by including [-budget, 0].
    const self = this;
    this._equitySeries.applyOptions({
      autoscaleInfoProvider: () => {
        const vals = equityPoints.map(p => p.value);
        if (!vals.length) return null;
        const maxV = Math.max(...vals, 0);   // always ≥ 0
        const minV = Math.min(...vals, 0);   // always ≤ 0
        const range = Math.max(maxV - minV, 1);
        const pad = range * 0.03;           // 3% breathing room
        const budgetMfe = self.options.showTradeExcursions
          ? (self._budgetMfe || 200) : 0;
        const budgetMae = self.options.showTradeExcursions
          ? (self._budgetMae || 200) : 0;
        // Union: equity zone ∪ bar zone, both anchored at zero
        return {
          priceRange: {
            minValue: Math.min(minV - pad, -budgetMae),
            maxValue: Math.max(maxV + pad, budgetMfe)
          },
          margins: { above: 2, below: 2 }
        };
      }
    });
    this._equitySeries.priceScale().applyOptions({
      scaleMargins: { top: 0.05, bottom: 0.02 }
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
      this.trades.forEach((trade, i) => {
        if (i >= equityPoints.length) return;
        const pt = equityPoints[i];
        const pnl = trade.pnl || 0;
        markers.push({
          time: pt.time,
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
      color: '#2962ff',
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerRadius: 4,
      title: 'B&H'
    });
    this._bhSeries.setData(points);

    // Same autoscale logic as equity: show actual B&H range + bar budgets,
    // always include 0, never stretch beyond what the data requires.
    const self = this;
    this._bhSeries.applyOptions({
      autoscaleInfoProvider: () => {
        const pvals = points.map(p => p.value);
        if (!pvals.length) return null;
        const maxV = Math.max(...pvals, 0);
        const minV = Math.min(...pvals, 0);
        const range = Math.max(maxV - minV, 1);
        const pad = range * 0.03;
        const budgetMfe = self.options.showTradeExcursions
          ? (self._budgetMfe || 200) : 0;
        const budgetMae = self.options.showTradeExcursions
          ? (self._budgetMae || 200) : 0;
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

  _buildExcursionSeries() {
    if (!this._lwChart || !this.trades.length || !this._equityPoints?.length) return;

    const maxMfe = Math.max(...this.trades.map(t => t.mfe || 0), 0.001);
    const maxMae = Math.max(...this.trades.map(t => t.mae || 0), 0.001);

    // ── Bar zone height in equity P&L units (USDT / %) ────────────────────
    // Step 1: raw zone height = 35% of the visible equity range.
    // Step 2: snap UP to nearest multiple of 50 (in equity units) for a
    //         clean scale — e.g. 1800 range → raw=630 → snap=650.
    // Step 3: clamp to [200, 600] so tiny or huge ranges stay reasonable.
    //   tiny equity (range=300): raw=105 → snap=150 → clamp → 200
    //   normal (range=1800):     raw=630 → snap=650 → clamp → 600
    //   large (range=5000):      raw=1750 → snap=1800 → clamp → 600
    const vals = this._equityPoints.map(p => p.value);
    const eqMax = Math.max(...vals, 0);
    const eqMin = Math.min(...vals, 0);
    const eqRange = Math.max(eqMax - eqMin, 1);

    const snapBudget = (raw) => {
      const snapped = Math.ceil(raw / 50) * 50;
      return Math.min(Math.max(snapped, 200), 600);
    };

    const budgetMfe = snapBudget(eqRange * 0.35);
    const budgetMae = snapBudget(eqRange * 0.35);
    this._budgetMfe = budgetMfe;
    this._budgetMae = budgetMae;

    const mfeData = [];
    const maeData = [];

    this.trades.forEach((trade, i) => {
      if (i >= this._equityPoints.length) return;
      const time = this._equityPoints[i].time;
      const pnl = trade.pnl || 0;
      const mfe = trade.mfe || 0;
      const mae = trade.mae || 0;

      // MFE: POSITIVE value → bar grows UP from zero
      mfeData.push({
        time,
        value: mfe > 0 ? (mfe / maxMfe) * budgetMfe : 0,
        color: mfe > 0
          ? (pnl >= 0 ? 'rgba(38,166,154,0.75)' : 'rgba(38,166,154,0.30)')
          : 'rgba(0,0,0,0)'
      });

      // MAE: NEGATIVE value → bar grows DOWN from zero
      maeData.push({
        time,
        value: mae > 0 ? -((mae / maxMae) * budgetMae) : 0,
        color: mae > 0
          ? (pnl < 0 ? 'rgba(239,83,80,0.75)' : 'rgba(239,83,80,0.30)')
          : 'rgba(0,0,0,0)'
      });
    });

    // Scale locked to the snapped budget: MFE above zero, MAE below zero
    const barOpts = {
      priceScaleId: 'right',
      lastValueVisible: false,
      priceLineVisible: false,
      autoscaleInfoProvider: () => ({
        priceRange: {
          minValue: -budgetMae,
          maxValue: budgetMfe
        }
      })
    };

    if (this._mfeSeries) {
      this._mfeSeries.applyOptions(barOpts);
      this._mfeSeries.setData(mfeData.sort((a, b) => a.time - b.time));
    } else {
      this._mfeSeries = this._lwChart.addHistogramSeries(barOpts);
      this._mfeSeries.setData(mfeData.sort((a, b) => a.time - b.time));
    }

    if (this._maeSeries) {
      this._maeSeries.applyOptions({ ...barOpts });
      this._maeSeries.setData(maeData.sort((a, b) => a.time - b.time));
    } else {
      this._maeSeries = this._lwChart.addHistogramSeries({ ...barOpts });
      this._maeSeries.setData(maeData.sort((a, b) => a.time - b.time));
    }

    // Nudge equity autoscaleInfoProvider to include bar budgets in its range
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
      tt.style.cssText = [
        'position:absolute', 'padding:8px 12px',
        'background:#161b22', 'border:1px solid rgba(48,54,61,0.9)',
        'border-radius:4px', 'color:#d1d4dc',
        'font-size:11px', 'font-family:system-ui,sans-serif',
        'line-height:1.65', 'pointer-events:none',
        'display:none', 'z-index:20', 'white-space:nowrap'
      ].join(';');
      this.container.appendChild(tt);
    }

    const equity = data.equity || [];
    const timestamps = data.timestamps || [];
    const base = equity[0] || this.initialCapital;

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

      const ev = equity[ci];
      const dateStr = new Date(param.time * 1000).toLocaleDateString('ru-RU', {
        day: 'numeric', month: 'short', year: 'numeric'
      });

      let html = `<div style="color:#787b86;margin-bottom:4px">${dateStr}</div>`;

      if (ev != null) {
        const pnl = ev - base;
        const pnlPct = (pnl / base) * 100;
        const col = pnl >= 0 ? '#26a69a' : '#ef5350';
        const sign = pnl >= 0 ? '+' : '';
        if (isPercent) {
          html += `<div>P&amp;L: <span style="color:${col}">${sign}${pnlPct.toFixed(2)}%</span></div>`;
        } else {
          html += `<div>P&amp;L: <span style="color:${col}">${sign}${this._fmt(pnl)}</span></div>`;
          html += `<div style="color:#787b86;font-size:10px">Капитал: ${this._fmt(ev)}</div>`;
        }
      }

      const trade = this._findTradeAtTime(timestamps[ci]);
      if (trade) {
        const side = (trade.direction || trade.side || 'long').toUpperCase();
        const tc = (trade.pnl || 0) >= 0 ? '#26a69a' : '#ef5350';
        html += '<div style="margin-top:4px;border-top:1px solid rgba(42,46,57,0.8);padding-top:4px">';
        html += `<div>📊 ${side} Trade</div>`;
        if (trade.entry_price) html += `<div style="color:#787b86">Entry: ${this._fmt(trade.entry_price)}</div>`;
        if (trade.exit_price) html += `<div style="color:#787b86">Exit: ${this._fmt(trade.exit_price)}</div>`;
        html += `<div>P&amp;L: <span style="color:${tc}">${(trade.pnl || 0) >= 0 ? '+' : ''}${this._fmt(trade.pnl || 0)}</span></div>`;
        if (trade.mfe) html += `<div style="color:#26a69a">MFE: +${Number(trade.mfe).toFixed(2)}%</div>`;
        if (trade.mae) html += `<div style="color:#ef5350">MAE: -${Math.abs(Number(trade.mae)).toFixed(2)}%</div>`;
        html += '</div>';
      }

      tt.innerHTML = html;
      tt.style.display = 'block';

      // Position tooltip (avoid clipping at edges)
      const tw = tt.offsetWidth, th = tt.offsetHeight;
      const cx = param.point.x, cy = param.point.y;
      const cw = this.container.clientWidth, ch = this.container.clientHeight;
      tt.style.left = (cx + tw + 20 < cw ? cx + 12 : cx - tw - 12) + 'px';
      tt.style.top = (cy + th + 20 < ch ? cy + 8 : cy - th - 8) + 'px';
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
}

// ── Module exports ────────────────────────────────────────────────────────────
/* eslint-disable no-undef */
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TradingViewEquityChart;
}
/* eslint-enable no-undef */

window.TradingViewEquityChart = TradingViewEquityChart;
