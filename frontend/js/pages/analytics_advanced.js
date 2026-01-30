/**
 * 📄 Analytics Advanced Page JavaScript
 *
 * Page-specific scripts for analytics_advanced.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
import { apiClient, API_CONFIG } from "../api.js";
import {
  formatNumber,
  formatCurrency,
  formatDate,
  debounce,
} from "../utils.js";

// Chart.js defaults
Chart.defaults.color = "#8b949e";
Chart.defaults.borderColor = "#30363d";

// Equity Curve Chart
const equityCtx = document.getElementById("equityCurveChart").getContext("2d");
const equityData = {
  labels: Array.from({ length: 30 }, (_, i) => `Day ${i + 1}`),
  datasets: [
    {
      label: "Portfolio Value",
      data: [
        10000, 10250, 10180, 10420, 10650, 10580, 10820, 11050, 10980, 11200,
        11450, 11380, 11620, 11850, 11780, 12020, 12250, 12180, 12420, 12650,
        12580, 12820, 13050, 12980, 13200, 13450, 13380, 13620, 13850, 14782,
      ],
      borderColor: "#58a6ff",
      backgroundColor: "rgba(88, 166, 255, 0.1)",
      fill: true,
      tension: 0.4,
      pointRadius: 0,
      pointHoverRadius: 6,
    },
    {
      label: "Benchmark (Buy & Hold)",
      data: [
        10000, 10100, 10050, 10200, 10350, 10300, 10450, 10600, 10550, 10700,
        10850, 10800, 10950, 11100, 11050, 11200, 11350, 11300, 11450, 11600,
        11550, 11700, 11850, 11800, 11950, 12100, 12050, 12200, 12350, 12500,
      ],
      borderColor: "#8b949e",
      borderDash: [5, 5],
      fill: false,
      tension: 0.4,
      pointRadius: 0,
    },
  ],
};
new Chart(equityCtx, {
  type: "line",
  data: equityData,
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      intersect: false,
      mode: "index",
    },
    plugins: {
      legend: {
        position: "top",
        align: "end",
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        grid: {
          color: "rgba(48, 54, 61, 0.5)",
        },
      },
      x: {
        grid: {
          display: false,
        },
      },
    },
  },
});

// Returns Distribution Chart
const returnsCtx = document.getElementById("returnsDistChart").getContext("2d");
new Chart(returnsCtx, {
  type: "bar",
  data: {
    labels: [
      "<-5%",
      "-5% to -3%",
      "-3% to -1%",
      "-1% to 0%",
      "0% to 1%",
      "1% to 3%",
      "3% to 5%",
      ">5%",
    ],
    datasets: [
      {
        label: "Trade Count",
        data: [12, 45, 128, 234, 312, 287, 156, 42],
        backgroundColor: [
          "rgba(248, 81, 73, 0.8)",
          "rgba(248, 81, 73, 0.6)",
          "rgba(248, 81, 73, 0.4)",
          "rgba(248, 81, 73, 0.2)",
          "rgba(63, 185, 80, 0.2)",
          "rgba(63, 185, 80, 0.4)",
          "rgba(63, 185, 80, 0.6)",
          "rgba(63, 185, 80, 0.8)",
        ],
        borderRadius: 4,
      },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: {
          color: "rgba(48, 54, 61, 0.5)",
        },
      },
      x: {
        grid: {
          display: false,
        },
      },
    },
  },
});

// Drawdown Chart
const ddCtx = document.getElementById("drawdownChart").getContext("2d");
const drawdownData = [
  0, -0.5, -1.2, -0.8, -0.3, -1.5, -2.1, -1.8, -0.9, -0.4, -2.5, -3.2, -4.1,
  -5.2, -6.8, -8.4, -7.2, -5.8, -4.2, -3.1, -2.4, -1.8, -1.2, -0.6, -1.4, -2.1,
  -1.5, -0.8, -0.3, -2.1,
];
new Chart(ddCtx, {
  type: "line",
  data: {
    labels: Array.from({ length: 30 }, (_, i) => `Day ${i + 1}`),
    datasets: [
      {
        label: "Drawdown %",
        data: drawdownData,
        borderColor: "#f85149",
        backgroundColor: "rgba(248, 81, 73, 0.2)",
        fill: true,
        tension: 0.4,
        pointRadius: 0,
      },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
    },
    scales: {
      y: {
        max: 0,
        grid: {
          color: "rgba(48, 54, 61, 0.5)",
        },
        ticks: {
          callback: function (value) {
            return value + "%";
          },
        },
      },
      x: {
        grid: {
          display: false,
        },
      },
    },
  },
});

// Hourly Distribution Chart
const hourlyCtx = document.getElementById("hourlyChart").getContext("2d");
new Chart(hourlyCtx, {
  type: "bar",
  data: {
    labels: ["0", "2", "4", "6", "8", "10", "12", "14", "16", "18", "20", "22"],
    datasets: [
      {
        label: "Trades",
        data: [45, 32, 28, 52, 78, 125, 156, 142, 168, 134, 89, 56],
        backgroundColor: "rgba(88, 166, 255, 0.6)",
        borderRadius: 4,
      },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      y: { display: false },
      x: { grid: { display: false } },
    },
  },
});

// Daily Distribution Chart
const dailyCtx = document.getElementById("dailyChart").getContext("2d");
new Chart(dailyCtx, {
  type: "bar",
  data: {
    labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    datasets: [
      {
        label: "P&L",
        data: [2450, 1820, 3120, -580, 1950, 890, 1240],
        backgroundColor: function (context) {
          return context.raw >= 0
            ? "rgba(63, 185, 80, 0.6)"
            : "rgba(248, 81, 73, 0.6)";
        },
        borderRadius: 4,
      },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      y: { display: false },
      x: { grid: { display: false } },
    },
  },
});

// Symbol Distribution Chart
const symbolCtx = document.getElementById("symbolChart").getContext("2d");
new Chart(symbolCtx, {
  type: "doughnut",
  data: {
    labels: ["BTC", "ETH", "SOL", "XRP", "Others"],
    datasets: [
      {
        data: [35, 28, 18, 12, 7],
        backgroundColor: [
          "#f7931a",
          "#627eea",
          "#00ffa3",
          "#23292f",
          "#8b949e",
        ],
        borderWidth: 0,
      },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "right",
        labels: {
          boxWidth: 12,
          padding: 8,
        },
      },
    },
    cutout: "60%",
  },
});

// Mini Charts for Strategy Comparison
function createMiniChart(canvasId, data, color) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: "line",
    data: {
      labels: data,
      datasets: [
        {
          data: data,
          borderColor: color,
          borderWidth: 2,
          fill: false,
          tension: 0.4,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { display: false },
      },
    },
  });
}

createMiniChart(
  "miniChart1",
  [10, 12, 11, 14, 13, 16, 18, 17, 20, 22, 24],
  "#58a6ff",
);
createMiniChart(
  "miniChart2",
  [10, 11, 10, 12, 11, 13, 12, 14, 15, 17, 18],
  "#a371f7",
);
createMiniChart(
  "miniChart3",
  [10, 13, 12, 15, 18, 17, 20, 19, 22, 28, 31],
  "#3fb950",
);
createMiniChart(
  "miniChart4",
  [10, 10, 11, 11, 11, 12, 12, 11, 12, 12, 12],
  "#f0883e",
);

// Generate Heatmap
function generateHeatmap() {
  const grid = document.getElementById("heatmapGrid");
  const months = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  const years = ["2024", "2025"];

  const performanceData = {
    2024: [4.2, -1.5, 2.8, 5.1, -2.3, 3.7, 6.2, -0.8, 4.5, 7.1, 3.2, 5.8],
    2025: [6.4, 4.8, -1.2, 3.5, 2.9, 5.2, 0, 0, 0, 0, 0, 0],
  };

  // Header row
  months.forEach((month) => {
    const cell = document.createElement("div");
    cell.className = "heatmap-label";
    cell.textContent = month;
    cell.style.justifyContent = month ? "center" : "flex-end";
    cell.style.paddingRight = month ? "0" : "8px";
    grid.appendChild(cell);
  });

  // Data rows
  years.forEach((year) => {
    const yearLabel = document.createElement("div");
    yearLabel.className = "heatmap-label";
    yearLabel.textContent = year;
    yearLabel.style.justifyContent = "flex-end";
    yearLabel.style.paddingRight = "8px";
    grid.appendChild(yearLabel);

    performanceData[year].forEach((value, idx) => {
      const cell = document.createElement("div");
      cell.className = "heatmap-cell";

      if (value === 0) {
        cell.classList.add("neutral");
      } else if (value > 5) {
        cell.classList.add("profit-high");
        cell.textContent = `+${value}%`;
      } else if (value > 2) {
        cell.classList.add("profit-medium");
        cell.textContent = `+${value}%`;
      } else if (value > 0) {
        cell.classList.add("profit-low");
        cell.textContent = `+${value}%`;
      } else if (value > -2) {
        cell.classList.add("loss-low");
        cell.textContent = `${value}%`;
      } else if (value > -5) {
        cell.classList.add("loss-medium");
        cell.textContent = `${value}%`;
      } else {
        cell.classList.add("loss-high");
        cell.textContent = `${value}%`;
      }

      cell.title = `${months[idx + 1]} ${year}: ${value > 0 ? "+" : ""}${value}%`;
      grid.appendChild(cell);
    });
  });
}

generateHeatmap();

// Tab switching
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", function () {
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.remove("active");
      t.setAttribute("aria-selected", "false");
    });
    this.classList.add("active");
    this.setAttribute("aria-selected", "true");
  });
});

// Chart period buttons
document.querySelectorAll(".chart-controls").forEach((controls) => {
  controls.querySelectorAll(".chart-btn").forEach((btn) => {
    btn.addEventListener("click", function () {
      controls
        .querySelectorAll(".chart-btn")
        .forEach((b) => b.classList.remove("active"));
      this.classList.add("active");
    });
  });
});

// Keyboard shortcuts
document.addEventListener("keydown", function (e) {
  if (e.key === "r" && !e.ctrlKey && !e.metaKey) {
    // Refresh data
    console.log("Refreshing data...");
  }
  if (e.key === "Escape") {
    // Close any open modals
  }
});

// ============================================
// MONTE CARLO SIMULATION
// ============================================

let mcEquityCurvesChart = null;
let mcDistributionChart = null;

// Load backtests for Monte Carlo dropdown
async function loadBacktestsForMonteCarlo() {
  try {
    const response = await fetch("/api/v1/backtests/?limit=20");
    const data = await response.json();
    const select = document.getElementById("mcBacktestSelect");

    if (!select) return;

    select.innerHTML = '<option value="">Select Backtest...</option>';

    const backtests = data.backtests || data || [];
    backtests.forEach((bt) => {
      const option = document.createElement("option");
      option.value = bt.id;
      option.textContent = `${bt.symbol || "Unknown"} - ${bt.strategy_type || "Strategy"} (${bt.created_at?.split("T")[0] || ""})`;
      select.appendChild(option);
    });
  } catch (error) {
    console.error("Failed to load backtests:", error);
  }
}

// Run Monte Carlo Simulation
async function runMonteCarloSimulation() {
  const backtestId = document.getElementById("mcBacktestSelect")?.value;
  const simulations =
    parseInt(document.getElementById("mcSimulations")?.value) || 1000;
  const capital =
    parseFloat(document.getElementById("mcCapital")?.value) || 10000;
  const method = document.getElementById("mcMethod")?.value || "bootstrap";
  const confidence =
    parseFloat(document.getElementById("mcConfidence")?.value) || 0.95;

  if (!backtestId) {
    alert("Please select a backtest first");
    return;
  }

  // Show loading
  document.getElementById("mcLoading").style.display = "block";
  document.getElementById("mcResults").style.display = "none";
  document.getElementById("mcEmpty").style.display = "none";

  try {
    // Get backtest data first
    const btResponse = await fetch(`/api/v1/backtests/${backtestId}`);
    const backtest = await btResponse.json();

    // Run Monte Carlo analysis
    const mcResponse = await fetch("/api/v1/monte-carlo/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        backtest_results: backtest,
        n_simulations: simulations,
        initial_capital: capital,
        method: method,
        confidence_level: confidence,
      }),
    });

    if (!mcResponse.ok) {
      throw new Error("Monte Carlo analysis failed");
    }

    const results = await mcResponse.json();

    // Display results
    displayMonteCarloResults(results, confidence);
  } catch (error) {
    console.error("Monte Carlo simulation failed:", error);
    document.getElementById("mcEmpty").style.display = "block";
    document.getElementById("mcEmpty").innerHTML = `
            <i class="fas fa-exclamation-triangle fa-3x text-danger mb-3"></i>
            <p class="text-danger">Simulation failed: ${error.message}</p>
        `;
  } finally {
    document.getElementById("mcLoading").style.display = "none";
  }
}

function displayMonteCarloResults(results, confidence) {
  // Update stats
  document.getElementById("mcProbProfit").textContent =
    `${((results.probability_of_profit || 0) * 100).toFixed(1)}%`;
  document.getElementById("mcMedianReturn").textContent =
    `${((results.median_return || 0) * 100).toFixed(1)}%`;
  document.getElementById("mcVaR").textContent =
    `${((results.var || results.value_at_risk || 0) * 100).toFixed(1)}%`;
  document.getElementById("mcCVaR").textContent =
    `${((results.cvar || results.expected_shortfall || 0) * 100).toFixed(1)}%`;
  document.getElementById("mcMaxDD").textContent =
    `${((results.expected_max_drawdown || results.max_drawdown?.mean || 0) * 100).toFixed(1)}%`;
  document.getElementById("mcKelly").textContent =
    `${((results.kelly_fraction || results.kelly || 0) * 100).toFixed(1)}%`;

  // Show results section
  document.getElementById("mcResults").style.display = "block";

  // Draw equity curves chart
  drawMonteCarloEquityCurves(results);

  // Draw distribution chart
  drawMonteCarloDistribution(results);
}

function drawMonteCarloEquityCurves(results) {
  const ctx = document.getElementById("mcEquityCurves")?.getContext("2d");
  if (!ctx) return;

  if (mcEquityCurvesChart) {
    mcEquityCurvesChart.destroy();
  }

  const bands = results.confidence_bands || results.equity_bands || {};
  const length = bands.median?.length || 100;
  const labels = Array.from({ length }, (_, i) => i + 1);

  const datasets = [];

  // 95th percentile band
  if (bands.p95 && bands.p5) {
    datasets.push({
      label: "95% Confidence",
      data: bands.p95,
      borderColor: "rgba(63, 185, 80, 0.3)",
      backgroundColor: "rgba(63, 185, 80, 0.1)",
      fill: "+1",
      pointRadius: 0,
      tension: 0.4,
    });
    datasets.push({
      label: "5th Percentile",
      data: bands.p5,
      borderColor: "rgba(248, 81, 73, 0.3)",
      backgroundColor: "transparent",
      fill: false,
      pointRadius: 0,
      tension: 0.4,
    });
  }

  // Median line
  if (bands.median) {
    datasets.push({
      label: "Median",
      data: bands.median,
      borderColor: "#58a6ff",
      backgroundColor: "transparent",
      fill: false,
      pointRadius: 0,
      borderWidth: 2,
      tension: 0.4,
    });
  }

  mcEquityCurvesChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { position: "top", align: "end" },
        title: { display: true, text: "Monte Carlo Equity Curves" },
      },
      scales: {
        y: { beginAtZero: false },
        x: { display: false },
      },
    },
  });
}

function drawMonteCarloDistribution(results) {
  const ctx = document.getElementById("mcDistribution")?.getContext("2d");
  if (!ctx) return;

  if (mcDistributionChart) {
    mcDistributionChart.destroy();
  }

  const dist =
    results.final_equity_distribution || results.return_distribution || {};
  const bins = dist.bins || [];
  const counts = dist.counts || [];

  // If no distribution data, create dummy
  if (bins.length === 0) {
    const returns = results.final_returns || [];
    // Create histogram manually
    const minVal = Math.min(...returns) || -0.5;
    const maxVal = Math.max(...returns) || 0.5;
    const binCount = 20;
    const binWidth = (maxVal - minVal) / binCount;

    for (let i = 0; i < binCount; i++) {
      bins.push(((minVal + i * binWidth) * 100).toFixed(0) + "%");
      counts.push(
        returns.filter(
          (r) => r >= minVal + i * binWidth && r < minVal + (i + 1) * binWidth,
        ).length,
      );
    }
  }

  mcDistributionChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: bins.map((b) =>
        typeof b === "number" ? `${(b * 100).toFixed(0)}%` : b,
      ),
      datasets: [
        {
          label: "Frequency",
          data: counts,
          backgroundColor: counts.map((_, i) =>
            i < counts.length / 2
              ? "rgba(248, 81, 73, 0.6)"
              : "rgba(63, 185, 80, 0.6)",
          ),
          borderRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: true, text: "Return Distribution" },
      },
      scales: {
        y: { beginAtZero: true },
        x: { display: true },
      },
    },
  });
}

// Initialize Monte Carlo on page load
document.addEventListener("DOMContentLoaded", () => {
  loadBacktestsForMonteCarlo();
});

// ============================================
// MARKET REGIME DETECTION
// ============================================

let regimeHistoryChart = null;

/**
 * Detect market regime for selected symbol
 */
async function detectMarketRegime() {
  const symbol = document.getElementById("regimeSymbol")?.value || "BTCUSDT";
  const interval = document.getElementById("regimeInterval")?.value || "1h";

  // Show loading, hide others
  document.getElementById("regimeLoading").style.display = "block";
  document.getElementById("regimeResults").style.display = "none";
  document.getElementById("regimeEmpty").style.display = "none";

  try {
    const response = await fetch("/api/v1/market-regime/detect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: symbol,
        interval: interval,
        lookback_bars: 200,
      }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();
    displayRegimeResults(data);

    // Also fetch history for chart
    await loadRegimeHistory(symbol, interval);
  } catch (error) {
    console.error("Regime detection failed:", error);
    alert("Failed to detect market regime: " + error.message);
    document.getElementById("regimeEmpty").style.display = "block";
  } finally {
    document.getElementById("regimeLoading").style.display = "none";
  }
}

/**
 * Display regime detection results
 */
function displayRegimeResults(data) {
  document.getElementById("regimeResults").style.display = "block";

  // Regime type with color
  const regimeColors = {
    trending_up: "#26a69a",
    trending_down: "#ef5350",
    ranging: "#78909c",
    volatile: "#ffa726",
    breakout_up: "#66bb6a",
    breakout_down: "#f44336",
    unknown: "#9e9e9e",
  };

  const regimeEl = document.getElementById("regimeType");
  regimeEl.textContent = data.regime.replace("_", " ").toUpperCase();
  regimeEl.style.color = regimeColors[data.regime] || "#fff";

  // Indicators
  document.getElementById("regimeConfidence").textContent =
    (data.confidence * 100).toFixed(1) + "%";
  document.getElementById("regimeADX").textContent =
    data.indicators.adx.toFixed(1);
  document.getElementById("regimePlusDI").textContent =
    data.indicators.plus_di.toFixed(1);
  document.getElementById("regimeMinusDI").textContent =
    data.indicators.minus_di.toFixed(1);
  document.getElementById("regimeBandwidth").textContent =
    data.indicators.bandwidth.toFixed(1);

  // Trading signals
  const signals = data.trading_signals;
  const longEl = document.getElementById("regimeAllowLong");
  const shortEl = document.getElementById("regimeAllowShort");

  longEl.textContent = "LONG: " + (signals.allow_long ? "✓" : "✗");
  longEl.className =
    "badge " + (signals.allow_long ? "bg-success" : "bg-danger");

  shortEl.textContent = "SHORT: " + (signals.allow_short ? "✓" : "✗");
  shortEl.className =
    "badge " + (signals.allow_short ? "bg-success" : "bg-danger");

  document.getElementById("regimePositionSize").textContent =
    (signals.recommended_position_size * 100).toFixed(0) + "%";
  document.getElementById("regimeDescription").textContent =
    signals.regime_description || data.reason;
}

/**
 * Load regime history for chart
 */
async function loadRegimeHistory(symbol, interval) {
  try {
    const response = await fetch(
      `/api/v1/market-regime/history/${symbol}?interval=${interval}&days=14`,
    );
    if (!response.ok) return;

    const data = await response.json();
    drawRegimeHistoryChart(data);
  } catch (error) {
    console.error("Failed to load regime history:", error);
  }
}

/**
 * Draw regime history chart
 */
function drawRegimeHistoryChart(data) {
  const ctx = document.getElementById("regimeHistoryChart");
  if (!ctx) return;

  if (regimeHistoryChart) {
    regimeHistoryChart.destroy();
  }

  const regimeColors = {
    trending_up: "#26a69a",
    trending_down: "#ef5350",
    ranging: "#78909c",
    volatile: "#ffa726",
    breakout_up: "#66bb6a",
    breakout_down: "#f44336",
    unknown: "#9e9e9e",
  };

  const labels = data.history.map((h) => h.timestamp.split("T")[0]);
  const adxValues = data.history.map((h) => h.adx);
  const bgColors = data.history.map((h) => regimeColors[h.regime] || "#9e9e9e");

  regimeHistoryChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "ADX (colored by regime)",
          data: adxValues,
          backgroundColor: bgColors,
          borderRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: true, text: "Regime History (ADX)" },
      },
      scales: {
        y: { beginAtZero: true, max: 60 },
        x: { display: true },
      },
    },
  });
}

// ============================================
// PORTFOLIO BACKTESTING
// ============================================

let portfolioEquityChart = null;
let portfolioAllocationChart = null;

/**
 * Run portfolio backtest
 */
async function runPortfolioBacktest() {
  const assetsSelect = document.getElementById("portfolioAssets");
  const selectedAssets = Array.from(assetsSelect.selectedOptions).map(
    (o) => o.value,
  );

  if (selectedAssets.length < 2) {
    alert("Please select at least 2 assets for portfolio backtest");
    return;
  }

  const allocation =
    document.getElementById("portfolioAllocation")?.value || "equal_weight";
  const rebalance =
    document.getElementById("portfolioRebalance")?.value || "weekly";
  const capital =
    parseFloat(document.getElementById("portfolioCapital")?.value) || 100000;
  const days =
    parseInt(document.getElementById("portfolioPeriod")?.value) || 90;

  // Show loading
  document.getElementById("portfolioLoading").style.display = "block";
  document.getElementById("portfolioResults").style.display = "none";
  document.getElementById("portfolioEmpty").style.display = "none";

  try {
    // Calculate dates
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - days);

    const formatDateStr = (d) => d.toISOString().split("T")[0];

    // Build asset_data - this is required by the API
    // For now, we'll use a simplified approach
    const response = await fetch("/api/v1/advanced-backtest/portfolio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        asset_data: selectedAssets.reduce((acc, symbol) => {
          acc[symbol] = {
            symbol: symbol,
            weight: 1 / selectedAssets.length,
          };
          return acc;
        }, {}),
        allocation_method: allocation,
        rebalance_frequency: rebalance,
        initial_capital: capital,
        start_date: formatDateStr(startDate),
        end_date: formatDateStr(endDate),
        interval: "1h",
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `API error: ${response.status}`);
    }

    const data = await response.json();
    displayPortfolioResults(data, selectedAssets);
  } catch (error) {
    console.error("Portfolio backtest failed:", error);
    alert("Portfolio backtest failed: " + error.message);
    document.getElementById("portfolioEmpty").style.display = "block";
  } finally {
    document.getElementById("portfolioLoading").style.display = "none";
  }
}

/**
 * Display portfolio backtest results
 */
function displayPortfolioResults(data, assets) {
  document.getElementById("portfolioResults").style.display = "block";

  // Metrics
  const totalReturn = data.total_return || 0;
  document.getElementById("portfolioReturn").textContent =
    (totalReturn >= 0 ? "+" : "") + (totalReturn * 100).toFixed(2) + "%";
  document.getElementById("portfolioReturn").className =
    "stat-value " + (totalReturn >= 0 ? "text-success" : "text-danger");

  document.getElementById("portfolioSharpe").textContent = (
    data.sharpe_ratio || 0
  ).toFixed(2);
  document.getElementById("portfolioMaxDD").textContent =
    ((data.max_drawdown || 0) * 100).toFixed(2) + "%";
  document.getElementById("portfolioVolatility").textContent =
    ((data.volatility || 0) * 100).toFixed(2) + "%";
  document.getElementById("portfolioSortino").textContent = (
    data.sortino_ratio || 0
  ).toFixed(2);
  document.getElementById("portfolioTrades").textContent =
    data.total_trades || 0;

  // Equity Chart
  drawPortfolioEquityChart(data.equity_curve || []);

  // Allocation Chart
  drawPortfolioAllocationChart(data.allocations || {}, assets);
}

/**
 * Draw portfolio equity chart
 */
function drawPortfolioEquityChart(equityCurve) {
  const ctx = document.getElementById("portfolioEquityChart");
  if (!ctx) return;

  if (portfolioEquityChart) {
    portfolioEquityChart.destroy();
  }

  const labels = equityCurve.map((_, i) => `Day ${i + 1}`);

  portfolioEquityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Portfolio Value",
          data: equityCurve,
          borderColor: "#58a6ff",
          backgroundColor: "rgba(88, 166, 255, 0.1)",
          fill: true,
          tension: 0.4,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: true, text: "Portfolio Equity Curve" },
      },
      scales: {
        y: { beginAtZero: false },
        x: { display: false },
      },
    },
  });
}

/**
 * Draw portfolio allocation pie chart
 */
function drawPortfolioAllocationChart(allocations, assets) {
  const ctx = document.getElementById("portfolioAllocationChart");
  if (!ctx) return;

  if (portfolioAllocationChart) {
    portfolioAllocationChart.destroy();
  }

  const colors = [
    "#58a6ff",
    "#3fb950",
    "#f0883e",
    "#a371f7",
    "#f85149",
    "#8b949e",
    "#79c0ff",
    "#56d364",
  ];

  // Use allocations if available, otherwise equal weight
  const labels =
    Object.keys(allocations).length > 0 ? Object.keys(allocations) : assets;
  const weights =
    Object.keys(allocations).length > 0
      ? Object.values(allocations)
      : assets.map(() => 1 / assets.length);

  portfolioAllocationChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [
        {
          data: weights.map((w) => (w * 100).toFixed(1)),
          backgroundColor: colors.slice(0, labels.length),
          borderWidth: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "right", labels: { boxWidth: 12 } },
        title: { display: true, text: "Asset Allocation" },
      },
    },
  });
}

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: createMiniChart, generateHeatmap, runMonteCarloSimulation

// Attach to window for backwards compatibility
if (typeof window !== "undefined") {
  window.analyticsadvancedPage = {
    runMonteCarloSimulation,
    loadBacktestsForMonteCarlo,
    detectMarketRegime,
    runPortfolioBacktest,
  };
  // Also expose globally for onclick handlers
  window.runMonteCarloSimulation = runMonteCarloSimulation;
  window.detectMarketRegime = detectMarketRegime;
  window.runPortfolioBacktest = runPortfolioBacktest;
}
