/**
 * 🔥 Optimization Heatmap Component
 *
 * Visualization for parameter optimization results:
 * - 2D heatmap for parameter sensitivity analysis
 * - Interactive hover with detailed metrics
 * - Color gradient for performance metric
 * - Best parameter highlighting
 *
 * @version 1.0.0
 * @date 2026-01-24
 */

export class OptimizationHeatmap {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.container = document.getElementById(containerId);
    this.chart = null;

    this.options = {
      height: 450,
      metric: "sharpe_ratio",
      colorScale: "performance", // 'performance', 'diverging', 'sequential'
      colors: {
        // Performance scale (red -> yellow -> green)
        performance: [
          { value: 0, color: "rgba(239, 83, 80, 0.9)" }, // Red (worst)
          { value: 0.25, color: "rgba(255, 152, 0, 0.9)" }, // Orange
          { value: 0.5, color: "rgba(255, 235, 59, 0.9)" }, // Yellow
          { value: 0.75, color: "rgba(139, 195, 74, 0.9)" }, // Light green
          { value: 1, color: "rgba(38, 166, 154, 0.9)" }, // Green (best)
        ],
        // Diverging scale (for returns around 0)
        diverging: [
          { value: 0, color: "rgba(239, 83, 80, 0.9)" }, // Red (negative)
          { value: 0.5, color: "rgba(255, 255, 255, 0.5)" }, // White (neutral)
          { value: 1, color: "rgba(38, 166, 154, 0.9)" }, // Green (positive)
        ],
        best: "#ffd700", // Gold for best cell
        text: "#787b86",
        grid: "rgba(42, 46, 57, 0.8)",
        background: "#131722",
      },
      showBestMarker: true,
      showValues: true,
      valueFormat: ".2f",
      ...options,
    };
  }

  /**
   * Render optimization heatmap
   * @param {Object} data - Optimization results
   * @param {Array} data.param1_values - Values for X-axis parameter
   * @param {Array} data.param2_values - Values for Y-axis parameter
   * @param {Array<Array>} data.results - 2D array of metric values [y][x]
   * @param {string} data.param1_name - Name of X-axis parameter
   * @param {string} data.param2_name - Name of Y-axis parameter
   * @param {Object} data.best - Best parameters { x, y, value }
   */
  render(data) {
    if (!this.container || !data?.results) {
      console.warn("OptimizationHeatmap: Container or data not found");
      return;
    }

    // Destroy existing chart
    if (this.chart) {
      this.chart.destroy();
    }

    // Store data for reference
    this.data = data;

    // Calculate value range for normalization
    const allValues = data.results.flat();
    this.minValue = Math.min(...allValues);
    this.maxValue = Math.max(...allValues);

    // Create the heatmap using Canvas 2D
    this._renderCanvasHeatmap(data);

    // Render legend
    this._renderLegend();

    return this;
  }

  /**
   * Render heatmap using Canvas 2D
   * @private
   */
  _renderCanvasHeatmap(data) {
    const {
      param1_values,
      param2_values,
      results,
      param1_name,
      param2_name,
      best,
    } = data;

    // Setup container
    this.container.innerHTML = "";
    this.container.style.position = "relative";

    // Calculate dimensions
    const margin = { top: 60, right: 120, bottom: 70, left: 80 };
    const width = this.container.clientWidth || 800;
    const height = this.options.height;
    const chartWidth = width - margin.left - margin.right;
    const chartHeight = height - margin.top - margin.bottom;

    const cellWidth = chartWidth / param1_values.length;
    const cellHeight = chartHeight / param2_values.length;

    // Create canvas
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    canvas.style.width = "100%";
    canvas.style.height = `${height}px`;
    this.container.appendChild(canvas);

    const ctx = canvas.getContext("2d");

    // Draw background
    ctx.fillStyle = this.options.colors.background;
    ctx.fillRect(0, 0, width, height);

    // Draw title
    ctx.fillStyle = this.options.colors.text;
    ctx.font = "bold 14px Arial";
    ctx.textAlign = "center";
    ctx.fillText(
      `Parameter Optimization: ${this._formatMetricName(this.options.metric)}`,
      width / 2,
      25,
    );

    // Draw heatmap cells
    for (let y = 0; y < param2_values.length; y++) {
      for (let x = 0; x < param1_values.length; x++) {
        const value = results[y][x];
        const normalizedValue = this._normalizeValue(value);
        const color = this._getColor(normalizedValue);

        const cellX = margin.left + x * cellWidth;
        const cellY = margin.top + y * cellHeight;

        // Draw cell
        ctx.fillStyle = color;
        ctx.fillRect(cellX, cellY, cellWidth - 1, cellHeight - 1);

        // Draw value text if cells are large enough
        if (this.options.showValues && cellWidth > 30 && cellHeight > 20) {
          ctx.fillStyle = normalizedValue > 0.5 ? "#000000" : "#ffffff";
          ctx.font = "10px Arial";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(
            this._formatValue(value),
            cellX + cellWidth / 2,
            cellY + cellHeight / 2,
          );
        }

        // Highlight best cell
        if (
          this.options.showBestMarker &&
          best &&
          x === best.x_index &&
          y === best.y_index
        ) {
          ctx.strokeStyle = this.options.colors.best;
          ctx.lineWidth = 3;
          ctx.strokeRect(cellX, cellY, cellWidth - 1, cellHeight - 1);
        }
      }
    }

    // Draw X-axis labels (param1)
    ctx.fillStyle = this.options.colors.text;
    ctx.font = "11px Arial";
    ctx.textAlign = "center";

    for (let x = 0; x < param1_values.length; x++) {
      const labelX = margin.left + x * cellWidth + cellWidth / 2;
      ctx.fillText(
        this._formatAxisValue(param1_values[x]),
        labelX,
        margin.top + chartHeight + 15,
      );
    }

    // X-axis title
    ctx.font = "bold 12px Arial";
    ctx.fillText(
      param1_name || "Parameter 1",
      margin.left + chartWidth / 2,
      height - 15,
    );

    // Draw Y-axis labels (param2)
    ctx.font = "11px Arial";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";

    for (let y = 0; y < param2_values.length; y++) {
      const labelY = margin.top + y * cellHeight + cellHeight / 2;
      ctx.fillText(
        this._formatAxisValue(param2_values[y]),
        margin.left - 8,
        labelY,
      );
    }

    // Y-axis title
    ctx.save();
    ctx.translate(15, margin.top + chartHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.font = "bold 12px Arial";
    ctx.textAlign = "center";
    ctx.fillText(param2_name || "Parameter 2", 0, 0);
    ctx.restore();

    // Setup tooltip
    this._setupTooltip(canvas, margin, cellWidth, cellHeight, data);
  }

  /**
   * Render color legend
   * @private
   */
  _renderLegend() {
    const legendId = `${this.containerId}-legend`;
    let legend = document.getElementById(legendId);

    if (!legend) {
      legend = document.createElement("div");
      legend.id = legendId;
      legend.className = "heatmap-legend";
      legend.style.cssText = `
                position: absolute;
                right: 10px;
                top: 70px;
                width: 80px;
                text-align: center;
            `;
      this.container.appendChild(legend);
    }

    const gradientStops = this.options.colors[this.options.colorScale]
      .map((s) => s.color)
      .join(", ");

    legend.innerHTML = `
            <div style="font-size: 11px; color: ${this.options.colors.text}; margin-bottom: 5px;">
                ${this._formatMetricName(this.options.metric)}
            </div>
            <div style="
                height: 150px;
                width: 15px;
                margin: 0 auto;
                background: linear-gradient(to bottom, ${gradientStops});
                border-radius: 2px;
            "></div>
            <div style="display: flex; justify-content: space-between; margin-top: 5px;">
                <span style="font-size: 10px; color: ${this.options.colors.text};">
                    ${this._formatValue(this.minValue)}
                </span>
            </div>
            <div style="margin-top: -25px;">
                <span style="font-size: 10px; color: ${this.options.colors.text};">
                    ${this._formatValue(this.maxValue)}
                </span>
            </div>
        `;
  }

  /**
   * Setup hover tooltip
   * @private
   */
  _setupTooltip(canvas, margin, cellWidth, cellHeight, data) {
    const tooltip = document.createElement("div");
    tooltip.className = "heatmap-tooltip";
    tooltip.style.cssText = `
            position: fixed;
            padding: 8px 12px;
            background: rgba(30, 34, 45, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            color: #d1d4dc;
            font-size: 12px;
            pointer-events: none;
            display: none;
            z-index: 1000;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        `;
    document.body.appendChild(tooltip);

    canvas.addEventListener("mousemove", (e) => {
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;

      const mouseX = (e.clientX - rect.left) * scaleX;
      const mouseY = (e.clientY - rect.top) * scaleY;

      const x = Math.floor((mouseX - margin.left) / cellWidth);
      const y = Math.floor((mouseY - margin.top) / cellHeight);

      if (
        x >= 0 &&
        x < data.param1_values.length &&
        y >= 0 &&
        y < data.param2_values.length
      ) {
        const value = data.results[y][x];

        tooltip.innerHTML = `
                    <div style="font-weight: bold; margin-bottom: 4px;">
                        ${this._formatMetricName(this.options.metric)}: ${this._formatValue(value)}
                    </div>
                    <div>${data.param1_name}: ${data.param1_values[x]}</div>
                    <div>${data.param2_name}: ${data.param2_values[y]}</div>
                `;

        tooltip.style.display = "block";
        tooltip.style.left = `${e.clientX + 10}px`;
        tooltip.style.top = `${e.clientY + 10}px`;
      } else {
        tooltip.style.display = "none";
      }
    });

    canvas.addEventListener("mouseleave", () => {
      tooltip.style.display = "none";
    });

    // Store tooltip reference for cleanup
    this._tooltip = tooltip;
  }

  /**
   * Normalize value to 0-1 range
   * @private
   */
  _normalizeValue(value) {
    if (this.maxValue === this.minValue) return 0.5;
    return (value - this.minValue) / (this.maxValue - this.minValue);
  }

  /**
   * Get color for normalized value
   * @private
   */
  _getColor(normalizedValue) {
    const scale = this.options.colors[this.options.colorScale];

    // Find the two colors to interpolate between
    let lower = scale[0];
    let upper = scale[scale.length - 1];

    for (let i = 0; i < scale.length - 1; i++) {
      if (
        normalizedValue >= scale[i].value &&
        normalizedValue <= scale[i + 1].value
      ) {
        lower = scale[i];
        upper = scale[i + 1];
        break;
      }
    }

    // Interpolate
    const range = upper.value - lower.value;
    const ratio = range === 0 ? 0 : (normalizedValue - lower.value) / range;

    return this._interpolateColor(lower.color, upper.color, ratio);
  }

  /**
   * Interpolate between two rgba colors
   * @private
   */
  _interpolateColor(color1, color2, ratio) {
    const parse = (c) => {
      const match = c.match(
        /rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/,
      );
      return match
        ? {
            r: parseInt(match[1]),
            g: parseInt(match[2]),
            b: parseInt(match[3]),
            a: parseFloat(match[4] ?? 1),
          }
        : { r: 0, g: 0, b: 0, a: 1 };
    };

    const c1 = parse(color1);
    const c2 = parse(color2);

    const r = Math.round(c1.r + (c2.r - c1.r) * ratio);
    const g = Math.round(c1.g + (c2.g - c1.g) * ratio);
    const b = Math.round(c1.b + (c2.b - c1.b) * ratio);
    const a = c1.a + (c2.a - c1.a) * ratio;

    return `rgba(${r}, ${g}, ${b}, ${a})`;
  }

  /**
   * Format metric name for display
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
   * Format value for display
   * @private
   */
  _formatValue(value) {
    if (Math.abs(value) >= 100) return value.toFixed(0);
    if (Math.abs(value) >= 10) return value.toFixed(1);
    return value.toFixed(2);
  }

  /**
   * Format axis value
   * @private
   */
  _formatAxisValue(value) {
    if (typeof value === "number") {
      if (Math.abs(value) >= 1000) return (value / 1000).toFixed(1) + "k";
      if (Number.isInteger(value)) return value.toString();
      return value.toFixed(2);
    }
    return String(value);
  }

  /**
   * Export as image
   */
  exportImage(filename = "optimization-heatmap.png") {
    const canvas = this.container.querySelector("canvas");
    if (!canvas) return;

    const link = document.createElement("a");
    link.download = filename;
    link.href = canvas.toDataURL("image/png");
    link.click();
  }

  /**
   * Destroy the component
   */
  destroy() {
    if (this._tooltip) {
      this._tooltip.remove();
    }
    if (this.container) {
      this.container.innerHTML = "";
    }
  }
}

// Export for ES modules
export default OptimizationHeatmap;

// Attach to window for non-module scripts
if (typeof window !== "undefined") {
  window.OptimizationHeatmap = OptimizationHeatmap;
}
