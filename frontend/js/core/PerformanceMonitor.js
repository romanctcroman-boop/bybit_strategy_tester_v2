/**
 * 📊 Performance Monitor - Bybit Strategy Tester v2
 *
 * Core Web Vitals tracking, performance metrics,
 * and reporting utilities.
 *
 * Part of Phase 3: Performance Optimization
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

/**
 * Core Web Vitals thresholds
 */
export const Thresholds = {
    LCP: { good: 2500, needsImprovement: 4000 },
    FID: { good: 100, needsImprovement: 300 },
    CLS: { good: 0.1, needsImprovement: 0.25 },
    FCP: { good: 1800, needsImprovement: 3000 },
    TTFB: { good: 800, needsImprovement: 1800 },
    INP: { good: 200, needsImprovement: 500 }
};

/**
 * Metric rating
 */
export const Rating = {
    GOOD: 'good',
    NEEDS_IMPROVEMENT: 'needs-improvement',
    POOR: 'poor'
};

/**
 * Get rating for a metric
 * @param {string} metric - Metric name
 * @param {number} value - Metric value
 * @returns {string}
 */
export function getRating(metric, value) {
    const threshold = Thresholds[metric];
    if (!threshold) return Rating.GOOD;

    if (value <= threshold.good) return Rating.GOOD;
    if (value <= threshold.needsImprovement) return Rating.NEEDS_IMPROVEMENT;
    return Rating.POOR;
}

/**
 * Performance Monitor class
 */
export class PerformanceMonitor {
    constructor(options = {}) {
        this._options = {
            reportEndpoint: null,
            sampleRate: 1.0,
            debug: false,
            ...options
        };

        this._metrics = {};
        this._marks = new Map();
        this._observers = [];
        this._callbacks = new Set();

        this._shouldSample = Math.random() < this._options.sampleRate;
    }

    /**
     * Initialize monitoring
     */
    init() {
        if (!this._shouldSample) return;

        this._observeLCP();
        this._observeFID();
        this._observeCLS();
        this._observeFCP();
        this._observeTTFB();
        this._observeINP();
        this._observeLongTasks();
        this._observeResources();
    }

    /**
     * Observe Largest Contentful Paint
     * @private
     */
    _observeLCP() {
        try {
            const observer = new PerformanceObserver(list => {
                const entries = list.getEntries();
                const lastEntry = entries[entries.length - 1];

                this._recordMetric('LCP', lastEntry.startTime, {
                    element: lastEntry.element?.tagName,
                    size: lastEntry.size,
                    url: lastEntry.url
                });
            });

            observer.observe({ type: 'largest-contentful-paint', buffered: true });
            this._observers.push(observer);
        } catch (e) {
            this._debug('LCP not supported');
        }
    }

    /**
     * Observe First Input Delay
     * @private
     */
    _observeFID() {
        try {
            const observer = new PerformanceObserver(list => {
                const entries = list.getEntries();
                const firstEntry = entries[0];

                this._recordMetric('FID', firstEntry.processingStart - firstEntry.startTime, {
                    eventType: firstEntry.name
                });
            });

            observer.observe({ type: 'first-input', buffered: true });
            this._observers.push(observer);
        } catch (e) {
            this._debug('FID not supported');
        }
    }

    /**
     * Observe Cumulative Layout Shift
     * @private
     */
    _observeCLS() {
        try {
            let clsValue = 0;
            let sessionValue = 0;
            let sessionEntries = [];

            const observer = new PerformanceObserver(list => {
                for (const entry of list.getEntries()) {
                    if (!entry.hadRecentInput) {
                        const firstSessionEntry = sessionEntries[0];
                        const lastSessionEntry = sessionEntries[sessionEntries.length - 1];

                        // Start new session if gap > 1s or session > 5s
                        if (sessionValue &&
                            (entry.startTime - lastSessionEntry.startTime > 1000 ||
                            entry.startTime - firstSessionEntry.startTime > 5000)) {
                            clsValue = Math.max(clsValue, sessionValue);
                            sessionValue = 0;
                            sessionEntries = [];
                        }

                        sessionValue += entry.value;
                        sessionEntries.push(entry);
                    }
                }

                const totalCLS = Math.max(clsValue, sessionValue);
                this._recordMetric('CLS', totalCLS);
            });

            observer.observe({ type: 'layout-shift', buffered: true });
            this._observers.push(observer);
        } catch (e) {
            this._debug('CLS not supported');
        }
    }

    /**
     * Observe First Contentful Paint
     * @private
     */
    _observeFCP() {
        try {
            const observer = new PerformanceObserver(list => {
                const entries = list.getEntries();
                const fcpEntry = entries.find(e => e.name === 'first-contentful-paint');

                if (fcpEntry) {
                    this._recordMetric('FCP', fcpEntry.startTime);
                }
            });

            observer.observe({ type: 'paint', buffered: true });
            this._observers.push(observer);
        } catch (e) {
            this._debug('FCP not supported');
        }
    }

    /**
     * Observe Time to First Byte
     * @private
     */
    _observeTTFB() {
        try {
            const navEntry = performance.getEntriesByType('navigation')[0];
            if (navEntry) {
                this._recordMetric('TTFB', navEntry.responseStart - navEntry.requestStart, {
                    domainLookup: navEntry.domainLookupEnd - navEntry.domainLookupStart,
                    connect: navEntry.connectEnd - navEntry.connectStart,
                    ssl: navEntry.secureConnectionStart > 0
                        ? navEntry.connectEnd - navEntry.secureConnectionStart
                        : 0
                });
            }
        } catch (e) {
            this._debug('TTFB not supported');
        }
    }

    /**
     * Observe Interaction to Next Paint
     * @private
     */
    _observeINP() {
        try {
            let maxINP = 0;

            const observer = new PerformanceObserver(list => {
                for (const entry of list.getEntries()) {
                    const duration = entry.duration;
                    if (duration > maxINP) {
                        maxINP = duration;
                        this._recordMetric('INP', duration, {
                            eventType: entry.name
                        });
                    }
                }
            });

            observer.observe({ type: 'event', buffered: true, durationThreshold: 16 });
            this._observers.push(observer);
        } catch (e) {
            this._debug('INP not supported');
        }
    }

    /**
     * Observe long tasks
     * @private
     */
    _observeLongTasks() {
        try {
            const observer = new PerformanceObserver(list => {
                for (const entry of list.getEntries()) {
                    this._debug('Long task detected:', entry.duration, 'ms');

                    if (!this._metrics.longTasks) {
                        this._metrics.longTasks = [];
                    }

                    this._metrics.longTasks.push({
                        duration: entry.duration,
                        startTime: entry.startTime,
                        attribution: entry.attribution?.[0]?.name
                    });
                }
            });

            observer.observe({ type: 'longtask', buffered: true });
            this._observers.push(observer);
        } catch (e) {
            this._debug('Long tasks not supported');
        }
    }

    /**
     * Observe resource timing
     * @private
     */
    _observeResources() {
        try {
            const observer = new PerformanceObserver(list => {
                for (const entry of list.getEntries()) {
                    if (entry.initiatorType === 'fetch' || entry.initiatorType === 'xmlhttprequest') {
                        if (!this._metrics.apiCalls) {
                            this._metrics.apiCalls = [];
                        }

                        this._metrics.apiCalls.push({
                            url: entry.name,
                            duration: entry.duration,
                            transferSize: entry.transferSize,
                            startTime: entry.startTime
                        });
                    }
                }
            });

            observer.observe({ type: 'resource', buffered: true });
            this._observers.push(observer);
        } catch (e) {
            this._debug('Resource timing not supported');
        }
    }

    /**
     * Record a metric
     * @private
     */
    _recordMetric(name, value, details = {}) {
        const rating = getRating(name, value);

        this._metrics[name] = {
            value,
            rating,
            details,
            timestamp: Date.now()
        };

        this._debug(`${name}: ${value} (${rating})`);
        this._notifyCallbacks(name, this._metrics[name]);
    }

    /**
     * Notify callbacks
     * @private
     */
    _notifyCallbacks(name, metric) {
        this._callbacks.forEach(cb => {
            try {
                cb(name, metric);
            } catch (e) {
                console.error('Metric callback error:', e);
            }
        });
    }

    /**
     * Debug log
     * @private
     */
    _debug(...args) {
        if (this._options.debug) {
            console.log('[Perf]', ...args);
        }
    }

    /**
     * Mark a point in time
     * @param {string} name - Mark name
     */
    mark(name) {
        performance.mark(name);
        this._marks.set(name, performance.now());
    }

    /**
     * Measure between two marks
     * @param {string} name - Measure name
     * @param {string} startMark - Start mark
     * @param {string} endMark - End mark
     * @returns {number}
     */
    measure(name, startMark, endMark) {
        try {
            performance.measure(name, startMark, endMark);
            const entries = performance.getEntriesByName(name, 'measure');
            const duration = entries[entries.length - 1]?.duration || 0;

            this._metrics[`custom:${name}`] = {
                value: duration,
                timestamp: Date.now()
            };

            return duration;
        } catch (e) {
            this._debug('Measure error:', e);
            return 0;
        }
    }

    /**
     * Subscribe to metric updates
     * @param {Function} callback - Callback function
     * @returns {Function} Unsubscribe function
     */
    subscribe(callback) {
        this._callbacks.add(callback);
        return () => this._callbacks.delete(callback);
    }

    /**
     * Get all metrics
     * @returns {Object}
     */
    getMetrics() {
        return { ...this._metrics };
    }

    /**
     * Get a specific metric
     * @param {string} name - Metric name
     * @returns {Object|null}
     */
    getMetric(name) {
        return this._metrics[name] || null;
    }

    /**
     * Get Core Web Vitals summary
     * @returns {Object}
     */
    getWebVitals() {
        return {
            LCP: this._metrics.LCP || null,
            FID: this._metrics.FID || null,
            CLS: this._metrics.CLS || null,
            FCP: this._metrics.FCP || null,
            TTFB: this._metrics.TTFB || null,
            INP: this._metrics.INP || null
        };
    }

    /**
     * Get performance score (0-100)
     * @returns {number}
     */
    getScore() {
        const vitals = this.getWebVitals();
        let score = 100;
        let count = 0;

        Object.entries(vitals).forEach(([_name, metric]) => {
            if (metric) {
                count++;
                if (metric.rating === Rating.NEEDS_IMPROVEMENT) {
                    score -= 15;
                } else if (metric.rating === Rating.POOR) {
                    score -= 30;
                }
            }
        });

        return count > 0 ? Math.max(0, score) : 0;
    }

    /**
     * Report metrics to endpoint
     * @param {string} endpoint - Report endpoint
     * @returns {Promise<void>}
     */
    async report(endpoint = null) {
        const url = endpoint || this._options.reportEndpoint;
        if (!url) return;

        try {
            const data = {
                url: window.location.href,
                userAgent: navigator.userAgent,
                connection: navigator.connection?.effectiveType,
                metrics: this.getMetrics(),
                timestamp: Date.now()
            };

            if (navigator.sendBeacon) {
                navigator.sendBeacon(url, JSON.stringify(data));
            } else {
                await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                    keepalive: true
                });
            }
        } catch (e) {
            this._debug('Report error:', e);
        }
    }

    /**
     * Stop all observers
     */
    disconnect() {
        this._observers.forEach(observer => observer.disconnect());
        this._observers = [];
    }
}

/**
 * Memory Monitor
 */
export class MemoryMonitor {
    constructor() {
        this._samples = [];
        this._maxSamples = 100;
        this._interval = null;
    }

    /**
     * Start monitoring
     * @param {number} intervalMs - Sampling interval
     */
    start(intervalMs = 5000) {
        if (!performance.memory) {
            console.warn('Memory API not available');
            return;
        }

        this._interval = setInterval(() => {
            this._sample();
        }, intervalMs);

        this._sample();
    }

    /**
     * Stop monitoring
     */
    stop() {
        if (this._interval) {
            clearInterval(this._interval);
            this._interval = null;
        }
    }

    /**
     * Take a sample
     * @private
     */
    _sample() {
        if (!performance.memory) return;

        const sample = {
            usedJSHeapSize: performance.memory.usedJSHeapSize,
            totalJSHeapSize: performance.memory.totalJSHeapSize,
            jsHeapSizeLimit: performance.memory.jsHeapSizeLimit,
            timestamp: Date.now()
        };

        this._samples.push(sample);

        if (this._samples.length > this._maxSamples) {
            this._samples.shift();
        }
    }

    /**
     * Get current memory usage
     * @returns {Object|null}
     */
    getCurrent() {
        if (!performance.memory) return null;

        return {
            used: performance.memory.usedJSHeapSize,
            total: performance.memory.totalJSHeapSize,
            limit: performance.memory.jsHeapSizeLimit,
            percentage: (performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit) * 100
        };
    }

    /**
     * Get memory trend
     * @returns {string} 'increasing', 'decreasing', 'stable'
     */
    getTrend() {
        if (this._samples.length < 10) return 'unknown';

        const recent = this._samples.slice(-10);
        const first = recent[0].usedJSHeapSize;
        const last = recent[recent.length - 1].usedJSHeapSize;
        const diff = ((last - first) / first) * 100;

        if (diff > 10) return 'increasing';
        if (diff < -10) return 'decreasing';
        return 'stable';
    }

    /**
     * Get all samples
     * @returns {Object[]}
     */
    getSamples() {
        return [...this._samples];
    }
}

// Singleton instance
let monitor = null;

/**
 * Get performance monitor instance
 * @param {Object} options - Options
 * @returns {PerformanceMonitor}
 */
export function getPerformanceMonitor(options = {}) {
    if (!monitor) {
        monitor = new PerformanceMonitor(options);
    }
    return monitor;
}

/**
 * Initialize performance monitoring
 * @param {Object} options - Options
 * @returns {PerformanceMonitor}
 */
export function initPerformanceMonitoring(options = {}) {
    const perf = getPerformanceMonitor(options);
    perf.init();

    // Report on page unload
    window.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
            perf.report();
        }
    });

    return perf;
}

export default {
    PerformanceMonitor,
    MemoryMonitor,
    Thresholds,
    Rating,
    getRating,
    getPerformanceMonitor,
    initPerformanceMonitoring
};
