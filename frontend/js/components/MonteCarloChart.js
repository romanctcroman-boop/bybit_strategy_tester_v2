/**
 * 🎲 Monte Carlo Simulation Chart Component
 *
 * Visualization for Monte Carlo analysis results:
 * - Confidence bands (5th, 25th, 50th, 75th, 95th percentiles)
 * - Distribution histogram for final equity
 * - Probability cone visualization
 * - VaR/CVaR indicators
 *
 * @version 1.0.0
 * @date 2026-01-24
 */

export class MonteCarloChart {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.container = document.getElementById(containerId);
    this.chart = null;

    this.options = {
      height: 400,
      confidenceLevels: [0.05, 0.25, 0.5, 0.75, 0.95],
      colors: {
        median: "#26a69a",
        bands: [
          "rgba(38, 166, 154, 0.1)", // 5-95%
          "rgba(38, 166, 154, 0.2)", // 25-75%
        ],
        baseline: "#ef5350",
        var: "#ff9800",
        grid: "rgba(42, 46, 57, 0.8)",
        text: "#787b86",
        background: "#131722",
      },
      showVaR: true,
      varLevel: 0.05, // 5% VaR
      initialCapital: 10000,
      ...options,
    };
  }

  /**
   * Render Monte Carlo simulation results
   * @param {Object} data - Simulation data
   * @param {Array} data.simulations - Array of equity curves [n_sims x n_periods]
   * @param {Array} data.timestamps - Time labels
   * @param {Object} data.statistics - Calculated statistics
   */
  render(data) {
    if (!this.container || !data?.simulations) {
      console.warn("MonteCarloChart: Container or data not found");
      return;
    }

    // Destroy existing chart
    if (this.chart) {
      this.chart.destroy();
    }

    // Calculate percentiles for each time step
    const percentiles = this._calculatePercentiles(data.simulations);
    const timestamps =
      data.timestamps || this._generateTimeLabels(data.simulations[0].length);

    // Create canvas
    const ctx = this._getOrCreateCanvas();

    // Build datasets
    const datasets = this._buildDatasets(percentiles, timestamps);

    // Create chart
    this.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: timestamps,
        datasets: datasets,
      },
      options: this._getChartOptions(data),
    });

    // Add distribution panel if container exists
    if (data.statistics) {
      this._renderStatisticsPanel(data.statistics);
    }

    return this.chart;
  }

  /**
   * Render final equity distribution histogram
   * @param {string} histogramContainerId - Container for histogram
   * @param {Array} finalEquities - Array of final equity values
   */
  renderDistribution(histogramContainerId, finalEquities) {
    const container = document.getElementById(histogramContainerId);
    if (!container || !finalEquities?.length) return;

    // Calculate histogram bins
    const bins = this._calculateHistogramBins(finalEquities, 30);

    const ctx = this._createCanvas(container, "distribution-canvas");

    // Calculate colors based on profit/loss
    const colors = bins.centers.map(
      (v) =>
        v >= this.options.initialCapital
          ? "rgba(38, 166, 154, 0.7)" // Profit - green
          : "rgba(239, 83, 80, 0.7)", // Loss - red
    );

    new Chart(ctx, {
      type: "bar",
      data: {
        labels: bins.centers.map((v) => this._formatCurrency(v)),
        datasets: [
          {
            label: "Frequency",
            data: bins.counts,
            backgroundColor: colors,
            borderRadius: 2,
            barPercentage: 0.95,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          title: {
            display: true,
            text: "Final Equity Distribution",
            color: this.options.colors.text,
          },
          annotation: this._getDistributionAnnotations(finalEquities),
        },
        scales: {
          x: {
            title: {
              display: true,
              text: "Final Equity ($)",
              color: this.options.colors.text,
            },
            grid: { display: false },
            ticks: { color: this.options.colors.text },
          },
          y: {
            title: {
              display: true,
              text: "Frequency",
              color: this.options.colors.text,
            },
            grid: { color: this.options.colors.grid },
            ticks: { color: this.options.colors.text },
          },
        },
      },
    });
  }

  /**
   * Calculate percentiles for each time step
   * @private
   */
  _calculatePercentiles(simulations) {
    const n_periods = simulations[0].length;
    const result = {
      p5: [],
      p25: [],
      p50: [],
      p75: [],
      p95: [],
    };

    for (let t = 0; t < n_periods; t++) {
      const values = simulations.map((sim) => sim[t]).sort((a, b) => a - b);
      const n = values.length;

      result.p5.push(values[Math.floor(n * 0.05)]);
      result.p25.push(values[Math.floor(n * 0.25)]);
      result.p50.push(values[Math.floor(n * 0.5)]);
      result.p75.push(values[Math.floor(n * 0.75)]);
      result.p95.push(values[Math.floor(n * 0.95)]);
    }

    return result;
  }

  /**
   * Build Chart.js datasets
   * @private
   */
  _buildDatasets(percentiles, timestamps) {
    const datasets = [];

    // 5-95% confidence band (background)
    datasets.push({
      label: "90% Confidence",
      data: percentiles.p95,
      borderColor: "transparent",
      backgroundColor: this.options.colors.bands[0],
      fill: "+1",
      pointRadius: 0,
      order: 4,
    });
    datasets.push({
      label: "_p5",
      data: percentiles.p5,
      borderColor: "transparent",
      backgroundColor: "transparent",
      fill: false,
      pointRadius: 0,
      order: 5,
    });

    // 25-75% confidence band
    datasets.push({
      label: "50% Confidence",
      data: percentiles.p75,
      borderColor: "transparent",
      backgroundColor: this.options.colors.bands[1],
      fill: "+1",
      pointRadius: 0,
      order: 2,
    });
    datasets.push({
      label: "_p25",
      data: percentiles.p25,
      borderColor: "transparent",
      backgroundColor: "transparent",
      fill: false,
      pointRadius: 0,
      order: 3,
    });

    // Median line
    datasets.push({
      label: "Median (50th Percentile)",
      data: percentiles.p50,
      borderColor: this.options.colors.median,
      backgroundColor: "transparent",
      borderWidth: 2,
      fill: false,
      pointRadius: 0,
      tension: 0.1,
      order: 1,
    });

    // Initial capital baseline
    datasets.push({
      label: "Initial Capital",
      data: new Array(timestamps.length).fill(this.options.initialCapital),
      borderColor: this.options.colors.baseline,
      borderDash: [5, 5],
      borderWidth: 1,
      fill: false,
      pointRadius: 0,
      order: 6,
    });

    return datasets;
  }

  /**
   * Get Chart.js options
   * @private
   */
  _getChartOptions(data) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: "index",
      },
      plugins: {
        legend: {
          position: "top",
          labels: {
            color: this.options.colors.text,
            filter: (item) => !item.text.startsWith("_"),
          },
        },
        title: {
          display: true,
          text: `Monte Carlo Simulation (${data.simulations?.length || 0} runs)`,
          color: this.options.colors.text,
          font: { size: 14 },
        },
        tooltip: {
          callbacks: {
            label: (context) => {
              const value = context.parsed.y;
              return `${context.dataset.label}: ${this._formatCurrency(value)}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: this.options.colors.grid },
          ticks: {
            color: this.options.colors.text,
            maxTicksLimit: 10,
          },
        },
        y: {
          title: {
            display: true,
            text: "Portfolio Value ($)",
            color: this.options.colors.text,
          },
          grid: { color: this.options.colors.grid },
          ticks: {
            color: this.options.colors.text,
            callback: (value) => this._formatCurrency(value),
          },
        },
      },
    };
  }

  /**
   * Calculate histogram bins
   * @private
   */
  _calculateHistogramBins(values, numBins) {
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min;
    const binWidth = range / numBins;

    const counts = new Array(numBins).fill(0);
    const centers = [];

    for (let i = 0; i < numBins; i++) {
      centers.push(min + binWidth * (i + 0.5));
    }

    for (const value of values) {
      const binIndex = Math.min(
        Math.floor((value - min) / binWidth),
        numBins - 1,
      );
      counts[binIndex]++;
    }

    return { counts, centers };
  }

  /**
   * Get annotations for distribution chart (VaR, mean, etc.)
   * @private
   */
  _getDistributionAnnotations(finalEquities) {
    if (!this.options.showVaR) return {};

    const sorted = [...finalEquities].sort((a, b) => a - b);
    const varValue = sorted[Math.floor(sorted.length * this.options.varLevel)];
    const meanValue =
      finalEquities.reduce((a, b) => a + b, 0) / finalEquities.length;

    return {
      annotations: {
        varLine: {
          type: "line",
          xMin: this._formatCurrency(varValue),
          xMax: this._formatCurrency(varValue),
          borderColor: this.options.colors.var,
          borderWidth: 2,
          borderDash: [5, 5],
          label: {
            display: true,
            content: `VaR ${(this.options.varLevel * 100).toFixed(0)}%`,
            position: "start",
          },
        },
        meanLine: {
          type: "line",
          xMin: this._formatCurrency(meanValue),
          xMax: this._formatCurrency(meanValue),
          borderColor: this.options.colors.median,
          borderWidth: 2,
          label: {
            display: true,
            content: "Mean",
            position: "end",
          },
        },
      },
    };
  }

  /**
   * Render statistics panel
   * @private
   */
  _renderStatisticsPanel(statistics) {
    const panelId = `${this.containerId}-stats`;
    let panel = document.getElementById(panelId);

    if (!panel) {
      panel = document.createElement("div");
      panel.id = panelId;
      panel.className = "monte-carlo-stats mt-3";
      this.container.parentNode.appendChild(panel);
    }

    const {
      mean_return,
      median_return,
      std_return,
      prob_profit,
      prob_loss,
      var_5,
      cvar_5,
      max_drawdown_mean,
    } = statistics;

    panel.innerHTML = `
            <div class="row g-2">
                <div class="col-md-3">
                    <div class="stat-card bg-dark p-2 rounded">
                        <div class="text-muted small">Expected Return</div>
                        <div class="h5 mb-0 ${mean_return >= 0 ? "text-success" : "text-danger"}">
                            ${(mean_return * 100).toFixed(2)}%
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card bg-dark p-2 rounded">
                        <div class="text-muted small">Probability of Profit</div>
                        <div class="h5 mb-0 text-success">${(prob_profit * 100).toFixed(1)}%</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card bg-dark p-2 rounded">
                        <div class="text-muted small">VaR (5%)</div>
                        <div class="h5 mb-0 text-warning">${this._formatCurrency(var_5)}</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card bg-dark p-2 rounded">
                        <div class="text-muted small">Avg Max Drawdown</div>
                        <div class="h5 mb-0 text-danger">${(max_drawdown_mean * 100).toFixed(2)}%</div>
                    </div>
                </div>
            </div>
        `;
  }

  /**
   * Create or get canvas element
   * @private
   */
  _getOrCreateCanvas() {
    let canvas = this.container.querySelector("canvas");
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvas.style.height = `${this.options.height}px`;
      this.container.innerHTML = "";
      this.container.appendChild(canvas);
    }
    return canvas.getContext("2d");
  }

  /**
   * Create canvas in container
   * @private
   */
  _createCanvas(container, id) {
    container.innerHTML = "";
    const canvas = document.createElement("canvas");
    canvas.id = id;
    canvas.style.height = `${this.options.height / 2}px`;
    container.appendChild(canvas);
    return canvas.getContext("2d");
  }

  /**
   * Generate time labels
   * @private
   */
  _generateTimeLabels(length) {
    return Array.from({ length }, (_, i) => `T${i}`);
  }

  /**
   * Format currency
   * @private
   */
  _formatCurrency(value) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  }

  /**
   * Destroy the chart
   */
  destroy() {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }
}

// Export for ES modules
export default MonteCarloChart;

// Attach to window for non-module scripts
if (typeof window !== "undefined") {
  window.MonteCarloChart = MonteCarloChart;
}
