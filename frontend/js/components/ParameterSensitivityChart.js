/**
 * 📈 Parameter Sensitivity Chart Component
 *
 * Line chart visualization showing how each parameter affects performance:
 * - Multiple metrics on single chart
 * - Interactive parameter selection
 * - Confidence intervals
 * - Optimal range highlighting
 *
 * @version 1.0.0
 * @date 2026-01-24
 */

export class ParameterSensitivityChart {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.container = document.getElementById(containerId);
    this.chart = null;

    this.options = {
      height: 350,
      metrics: ["sharpe_ratio", "total_return", "win_rate"],
      colors: {
        sharpe_ratio: "#26a69a",
        sortino_ratio: "#42a5f5",
        total_return: "#66bb6a",
        win_rate: "#ffca28",
        profit_factor: "#ab47bc",
        max_drawdown: "#ef5350",
        calmar_ratio: "#29b6f6",
        text: "#787b86",
        grid: "rgba(42, 46, 57, 0.8)",
        optimal: "rgba(38, 166, 154, 0.2)",
      },
      showOptimalRange: true,
      ...options,
    };
  }

  /**
   * Render parameter sensitivity chart
   * @param {Object} data - Sensitivity analysis data
   * @param {string} data.parameter_name - Name of the parameter
   * @param {Array} data.parameter_values - Values tested
   * @param {Object} data.metrics - Object with metric name -> values array
   * @param {Object} data.optimal_range - { min, max } optimal range
   */
  render(data) {
    if (!this.container || !data?.parameter_values) {
      console.warn("ParameterSensitivityChart: Container or data not found");
      return;
    }

    // Destroy existing chart
    if (this.chart) {
      this.chart.destroy();
    }

    const ctx = this._getOrCreateCanvas();
    const datasets = this._buildDatasets(data);

    this.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: data.parameter_values.map((v) => this._formatValue(v)),
        datasets: datasets,
      },
      options: this._getChartOptions(data),
      plugins: this.options.showOptimalRange
        ? [this._optimalRangePlugin(data)]
        : [],
    });

    return this.chart;
  }

  /**
   * Build datasets from data
   * @private
   */
  _buildDatasets(data) {
    const datasets = [];
    const metricsToShow = Object.keys(data.metrics).filter((m) =>
      this.options.metrics.includes(m),
    );

    metricsToShow.forEach((metric, index) => {
      const values = data.metrics[metric];
      const color = this.options.colors[metric] || this._getDefaultColor(index);

      datasets.push({
        label: this._formatMetricName(metric),
        data: values,
        borderColor: color,
        backgroundColor: `${color}20`,
        borderWidth: 2,
        fill: false,
        tension: 0.3,
        pointRadius: 3,
        pointHoverRadius: 6,
        yAxisID: this._getAxisId(metric),
      });
    });

    return datasets;
  }

  /**
   * Get Chart.js options
   * @private
   */
  _getChartOptions(data) {
    const hasReturnMetric = data.metrics.total_return !== undefined;
    const hasRatioMetric =
      data.metrics.sharpe_ratio !== undefined ||
      data.metrics.sortino_ratio !== undefined;

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
          labels: { color: this.options.colors.text },
        },
        title: {
          display: true,
          text: `Parameter Sensitivity: ${data.parameter_name}`,
          color: this.options.colors.text,
          font: { size: 14, weight: "bold" },
        },
        tooltip: {
          callbacks: {
            title: (context) => {
              return `${data.parameter_name}: ${context[0].label}`;
            },
            label: (context) => {
              const metric = context.dataset.label;
              const value = context.parsed.y;
              return `${metric}: ${this._formatMetricValue(context.dataset.yAxisID, value)}`;
            },
          },
        },
      },
      scales: {
        x: {
          title: {
            display: true,
            text: data.parameter_name,
            color: this.options.colors.text,
          },
          grid: { color: this.options.colors.grid },
          ticks: { color: this.options.colors.text },
        },
        y: {
          type: "linear",
          display: hasRatioMetric,
          position: "left",
          title: {
            display: true,
            text: "Ratio",
            color: this.options.colors.text,
          },
          grid: { color: this.options.colors.grid },
          ticks: { color: this.options.colors.text },
        },
        y1: {
          type: "linear",
          display: hasReturnMetric,
          position: "right",
          title: {
            display: true,
            text: "Return %",
            color: this.options.colors.text,
          },
          grid: { drawOnChartArea: false },
          ticks: {
            color: this.options.colors.text,
            callback: (value) => `${value.toFixed(1)}%`,
          },
        },
      },
    };
  }

  /**
   * Plugin to highlight optimal parameter range
   * @private
   */
  _optimalRangePlugin(data) {
    return {
      id: "optimalRange",
      beforeDraw: (chart) => {
        if (!data.optimal_range) return;

        const { ctx, chartArea, scales } = chart;
        const { min, max } = data.optimal_range;

        // Find x positions for min and max
        const labels = data.parameter_values;
        let minIndex = labels.findIndex((v) => v >= min);
        let maxIndex = labels.findIndex((v) => v >= max);

        if (minIndex === -1) minIndex = 0;
        if (maxIndex === -1) maxIndex = labels.length - 1;

        const x1 = scales.x.getPixelForValue(minIndex);
        const x2 = scales.x.getPixelForValue(maxIndex);

        ctx.save();
        ctx.fillStyle = this.options.colors.optimal;
        ctx.fillRect(
          x1,
          chartArea.top,
          x2 - x1,
          chartArea.bottom - chartArea.top,
        );
        ctx.restore();
      },
    };
  }

  /**
   * Determine Y-axis for metric
   * @private
   */
  _getAxisId(metric) {
    const returnMetrics = ["total_return", "win_rate", "max_drawdown"];
    return returnMetrics.includes(metric) ? "y1" : "y";
  }

  /**
   * Format metric value for tooltip
   * @private
   */
  _formatMetricValue(axisId, value) {
    if (axisId === "y1") {
      return `${value.toFixed(2)}%`;
    }
    return value.toFixed(3);
  }

  /**
   * Get default color for index
   * @private
   */
  _getDefaultColor(index) {
    const palette = [
      "#26a69a",
      "#42a5f5",
      "#66bb6a",
      "#ffca28",
      "#ab47bc",
      "#ef5350",
      "#29b6f6",
      "#ff7043",
    ];
    return palette[index % palette.length];
  }

  /**
   * Format metric name
   * @private
   */
  _formatMetricName(metric) {
    const names = {
      sharpe_ratio: "Sharpe Ratio",
      sortino_ratio: "Sortino Ratio",
      total_return: "Total Return",
      win_rate: "Win Rate",
      profit_factor: "Profit Factor",
      max_drawdown: "Max Drawdown",
      calmar_ratio: "Calmar Ratio",
    };
    return (
      names[metric] ||
      metric.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())
    );
  }

  /**
   * Format parameter value
   * @private
   */
  _formatValue(value) {
    if (typeof value !== "number") return value;
    if (Number.isInteger(value)) return value.toString();
    return value.toFixed(2);
  }

  /**
   * Create or get canvas
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
   * Destroy chart
   */
  destroy() {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }
}

// Export for ES modules
export default ParameterSensitivityChart;

// Attach to window for non-module scripts
if (typeof window !== "undefined") {
  window.ParameterSensitivityChart = ParameterSensitivityChart;
}
