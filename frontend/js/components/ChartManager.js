/**
 * 📊 ChartManager — Централизованный lifecycle для Chart.js экземпляров
 *
 * Решает проблему утечек памяти в backtest_results.js:
 * 7 Chart.js экземпляров создавались без .destroy() при переинициализации,
 * что приводило к "Canvas is already in use" ошибкам и росту памяти.
 *
 * @module ChartManager
 * @version 1.0.0
 * @date 2026-02-26
 * @migration P0-2: Chart.js memory leak fix
 */

/**
 * Manages Chart.js instance lifecycle: create, destroy, update.
 *
 * Usage:
 *   import { chartManager } from '../components/ChartManager.js';
 *   const chart = chartManager.init('drawdown', canvas, chartConfig);
 *   chartManager.destroyAll();  // call before page unload or re-init
 */
export class ChartManager {
    constructor() {
        /** @type {Map<string, Chart>} name → Chart instance */
        this._charts = new Map();
    }

    /**
     * Create (or recreate) a Chart.js instance.
     * Always destroys any existing chart with the same name first
     * to prevent "Canvas is already in use" errors.
     *
     * @param {string} name   - Unique identifier (e.g. 'drawdown', 'monthly')
     * @param {HTMLCanvasElement} canvas - Target <canvas> element
     * @param {object} config - Chart.js configuration object
     * @returns {Chart} The newly created Chart instance
     */
    init(name, canvas, config) {
        this.destroy(name);
        // Also destroy any existing Chart registered to this canvas by Chart.js internally
        if (typeof Chart !== 'undefined' && Chart.getChart) {
            const existing = Chart.getChart(canvas);
            if (existing) existing.destroy();
        }
        const chart = new Chart(canvas, config);
        this._charts.set(name, chart);
        return chart;
    }

    /**
     * Destroy a specific chart and remove it from the registry.
     *
     * @param {string} name - Chart identifier
     */
    destroy(name) {
        const chart = this._charts.get(name);
        if (chart) {
            try {
                chart.destroy();
            } catch (_err) {
                // Ignore if already destroyed
            }
            this._charts.delete(name);
        }
    }

    /**
     * Destroy ALL managed charts and clear the registry.
     * Call before page navigation or full re-initialization.
     */
    destroyAll() {
        for (const name of [...this._charts.keys()]) {
            this.destroy(name);
        }
    }

    /**
     * Get a Chart instance by name.
     *
     * @param {string} name - Chart identifier
     * @returns {Chart|null}
     */
    get(name) {
        return this._charts.get(name) ?? null;
    }

    /**
     * Check if a chart exists in the registry.
     *
     * @param {string} name - Chart identifier
     * @returns {boolean}
     */
    has(name) {
        return this._charts.has(name);
    }

    /**
     * Returns array of all managed Chart instances.
     *
     * @returns {Chart[]}
     */
    getAll() {
        return [...this._charts.values()];
    }

    /**
     * Update a chart's data without destroying/recreating it.
     * Efficient for live data updates.
     *
     * @param {string} name    - Chart identifier
     * @param {string[]} labels - New labels array
     * @param {Array[]} datasets - Array of data arrays, one per dataset
     * @param {string} [mode='default'] - Chart.js update mode
     */
    update(name, labels, datasets, mode = 'default') {
        const chart = this._charts.get(name);
        if (!chart) return;
        chart.data.labels = labels;
        datasets.forEach((data, i) => {
            if (chart.data.datasets[i]) {
                chart.data.datasets[i].data = data;
            }
        });
        chart.update(mode);
    }

    /**
     * Clear a chart's data (labels + all dataset data arrays) without destroying.
     * More efficient than destroy+recreate for clearing display.
     *
     * @param {string} name  - Chart identifier
     * @param {string} [mode='none'] - Chart.js update mode ('none' = no animation)
     */
    clear(name, mode = 'none') {
        const chart = this._charts.get(name);
        if (!chart) return;
        chart.data.labels = [];
        chart.data.datasets.forEach((ds) => { ds.data = []; });
        chart.update(mode);
    }

    /**
     * Clear ALL charts' data without destroying instances.
     * Use instead of destroyAll() when you plan to refill data shortly.
     *
     * @param {string} [mode='none'] - Chart.js update mode
     */
    clearAll(mode = 'none') {
        for (const name of this._charts.keys()) {
            this.clear(name, mode);
        }
    }

    /**
     * Return registry size (number of managed charts).
     *
     * @returns {number}
     */
    get size() {
        return this._charts.size;
    }
}

/**
 * Singleton instance used across backtest_results.js.
 * Import this instead of `new ChartManager()`.
 */
export const chartManager = new ChartManager();
