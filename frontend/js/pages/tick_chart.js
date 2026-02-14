/**
 * 📄 Tick Chart Page JavaScript
 *
 * Page-specific scripts for tick_chart.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
// eslint-disable-next-line no-unused-vars
import { apiClient, API_CONFIG } from '../api.js';
// eslint-disable-next-line no-unused-vars
import { formatNumber, formatCurrency, formatDate, debounce } from '../utils.js';

const API_BASE = '/api/v1/marketdata/ticks';

let chart = null;
let candleSeries = null;
let volumeSeries = null;
let ws = null;
// eslint-disable-next-line no-unused-vars
let isConnected = false;
let currentSymbol = 'BTCUSDT';
let currentTicks = 100;
let tradeCount = 0;
// eslint-disable-next-line no-unused-vars
const lastTradeTime = Date.now();

// Performance optimization: throttling and batching
let pendingCandleUpdate = null;
let pendingCurrentUpdate = null;
const pendingTradeUpdates = [];
let renderFrameRequested = false;
const CANDLE_THROTTLE_MS = 50;  // Max 20 candle updates/sec
const TRADE_BATCH_SIZE = 10;     // Batch trades for DOM updates
let lastCandleRender = 0;

// Auto-scroll settings
const autoScrollEnabled = true;
let userScrolledAway = false;

// Tick chart uses index-based time (not real timestamps) because multiple candles
// can be created per second. LightweightCharts requires unique ascending times.
let candleIndex = 0;
const indexToTimeMap = new Map(); // Map index -> real timestamp for tooltip
const MAX_INDEX_MAP_SIZE = 10000;  // Prevent memory leak
const CLEANUP_BATCH_SIZE = 1000;   // Remove this many old entries when limit reached

// Helper function to add to indexToTimeMap with automatic cleanup
function addToIndexMap(index, timestamp) {
    indexToTimeMap.set(index, timestamp);

    // Memory leak prevention: cleanup old entries
    if (indexToTimeMap.size > MAX_INDEX_MAP_SIZE) {
        console.log(`[Memory] Cleaning up indexToTimeMap: ${indexToTimeMap.size} entries`);

        const toDelete = Array.from(indexToTimeMap.keys())
            .sort((a, b) => a - b)  // Oldest indices first
            .slice(0, CLEANUP_BATCH_SIZE);

        toDelete.forEach(k => indexToTimeMap.delete(k));

        console.log(`[Memory] After cleanup: ${indexToTimeMap.size} entries (removed ${CLEANUP_BATCH_SIZE})`);
    }
}

// ETA calculation
const recentTradesPerSecond = [];  // Rolling window of trades/sec
const ETA_WINDOW_SIZE = 10;      // Average over 10 seconds
// eslint-disable-next-line no-unused-vars
const candlesCreatedInLastMinute = 0;
let lastCandleCountCheck = 0;
let lastMinuteCheckTime = Date.now();
let lastTickCount = 0;  // For calculating trades/sec from current updates
let ticksThisSecond = 0;  // Accumulated ticks in current second

// Initialize chart
function initChart() {
    const container = document.getElementById('tickChart');

    chart = LightweightCharts.createChart(container, {
        layout: {
            background: { type: 'solid', color: '#0a0e17' },
            textColor: '#d1d4dc'
        },
        grid: {
            vertLines: { color: '#1e222d' },
            horzLines: { color: '#1e222d' }
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal
        },
        rightPriceScale: {
            borderColor: '#2a2e39'
        },
        timeScale: {
            borderColor: '#2a2e39',
            timeVisible: false,  // Hide default time labels (we use index)
            secondsVisible: false,
            rightOffset: 5,  // Space for new candles
            shiftVisibleRangeOnNewBar: true,  // Auto-scroll on new bars
            tickMarkFormatter: (time) => `#${time}`  // Show bar number
        },
        localization: {
            timeFormatter: (time) => `Bar #${time}`  // Tooltip format
        }
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#00c853',
        downColor: '#ff1744',
        borderDownColor: '#ff1744',
        borderUpColor: '#00c853',
        wickDownColor: '#ff1744',
        wickUpColor: '#00c853'
    });

    volumeSeries = chart.addHistogramSeries({
        color: '#2962ff',
        priceFormat: { type: 'volume' },
        priceScaleId: '',
        scaleMargins: {
            top: 0.8,
            bottom: 0
        }
    });

    // Track user scroll to disable auto-scroll when user navigates
    chart.timeScale().subscribeVisibleTimeRangeChange(() => {
        // If user scrolled away from latest candle
        const visibleRange = chart.timeScale().getVisibleRange();
        if (visibleRange && candleIndex > 0) {
            // If right edge is more than 10 candles from current, user scrolled away
            userScrolledAway = (candleIndex - visibleRange.to) > 10;

            // Show/hide "Scroll to Now" button
            const scrollBtn = document.getElementById('scrollToNowBtn');
            if (userScrolledAway) {
                scrollBtn.classList.remove('hidden');
            } else {
                scrollBtn.classList.add('hidden');
            }
        }
    });

    // Resize handler
    new ResizeObserver(() => {
        chart.applyOptions({
            width: container.clientWidth,
            height: container.clientHeight
        });
    }).observe(container);

    // Crosshair tooltip
    chart.subscribeCrosshairMove(param => {
        const tooltip = document.getElementById('chartTooltip');
        if (!param.point || param.time === undefined) {
            tooltip.classList.add('hidden');
            return;
        }

        const data = param.seriesData.get(candleSeries);
        if (data) {
            tooltip.classList.remove('hidden');
            // param.time is index, get real timestamp from map
            const realTime = indexToTimeMap.get(param.time);
            if (realTime) {
                document.getElementById('tooltipTime').textContent = new Date(realTime * 1000).toLocaleTimeString();
            } else {
                document.getElementById('tooltipTime').textContent = `Bar #${param.time}`;
            }
            document.getElementById('tooltipOpen').textContent = data.open.toFixed(2);
            document.getElementById('tooltipHigh').textContent = data.high.toFixed(2);
            document.getElementById('tooltipLow').textContent = data.low.toFixed(2);
            document.getElementById('tooltipClose').textContent = data.close.toFixed(2);
        }
    });
}

// Start tick service
async function startTickService() {
    currentSymbol = document.getElementById('symbolSelect').value;
    currentTicks = parseInt(document.getElementById('ticksSelect').value);

    document.getElementById('tickTotal').textContent = currentTicks;

    try {
        // Reset reconnection state
        shouldReconnect = true;
        wsReconnectAttempts = 0;

        // Start backend service with selected ticks parameter
        await fetch(`${API_BASE}/start?symbols=${currentSymbol}&ticks=${currentTicks}`, { method: 'POST' });

        // Connect WebSocket
        connectWebSocket();

        document.getElementById('startBtn').classList.add('hidden');
        document.getElementById('stopBtn').classList.remove('hidden');
    } catch (e) {
        console.error('Failed to start tick service:', e);
    }
}

// Stop tick service
async function stopTickService() {
    shouldReconnect = false;  // Disable auto-reconnect

    // Clear any pending reconnect timeout
    if (wsReconnectTimeout) {
        clearTimeout(wsReconnectTimeout);
        wsReconnectTimeout = null;
    }

    if (ws) {
        ws.close();
        ws = null;
    }

    try {
        await fetch(`${API_BASE}/stop`, { method: 'POST' });
    } catch (e) {
        console.error('Failed to stop tick service:', e);
    }

    updateConnectionStatus(false);
    document.getElementById('startBtn').classList.remove('hidden');
    document.getElementById('stopBtn').classList.add('hidden');
}

// WebSocket reconnection logic
let wsReconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
const RECONNECT_DELAY_MS = 2000;
let wsReconnectTimeout = null;
let shouldReconnect = true;

// WebSocket connection
function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        console.log('WebSocket already connected');
        return;
    }

    const wsUrl = `ws://${window.location.host}${API_BASE}/ws/${currentSymbol}?ticks=${currentTicks}`;
    console.log('Connecting to:', wsUrl);

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
        updateConnectionStatus(true);
        wsReconnectAttempts = 0;  // Reset counter on success
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);

        // Auto-reconnect if enabled and not manually stopped
        if (shouldReconnect && wsReconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            wsReconnectAttempts++;
            console.log(`Reconnecting in ${RECONNECT_DELAY_MS}ms (attempt ${wsReconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);

            wsReconnectTimeout = setTimeout(() => {
                connectWebSocket();
            }, RECONNECT_DELAY_MS);
        } else if (wsReconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            console.error('Max reconnection attempts reached. Please restart manually.');
            document.getElementById('statusText').textContent = 'Disconnected - Click Start to reconnect';
        }
    };

    ws.onerror = (e) => {
        console.error('WebSocket error:', e);
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };
}

// Schedule render frame for batched updates
function scheduleRenderFrame() {
    if (!renderFrameRequested) {
        renderFrameRequested = true;
        requestAnimationFrame(processUpdates);
    }
}

let lastFrameTime = Date.now();
let frameCount = 0;
let lastFpsUpdate = Date.now();

// Process all pending updates in single frame (GPU-optimized)
function processUpdates() {
    renderFrameRequested = false;
    const now = Date.now();

    // FPS / Freeze detection
    frameCount++;
    if (now - lastFpsUpdate >= 1000) {
        const fps = Math.round((frameCount * 1000) / (now - lastFpsUpdate));
        document.getElementById('fpsStat').textContent = `${fps} FPS`;
        if (fps < 10) {
            document.getElementById('fpsStat').style.color = 'red';
        } else {
            document.getElementById('fpsStat').style.color = '#888';
        }
        frameCount = 0;
        lastFpsUpdate = now;
    }

    // Detect main thread freeze
    const frameDelta = now - lastFrameTime;
    if (frameDelta > 200) {
        console.warn(`Main thread freeze detected: ${frameDelta}ms`);
    }
    lastFrameTime = now;

    // Process pending candle update (completed candle)
    if (pendingCandleUpdate && (now - lastCandleRender >= CANDLE_THROTTLE_MS)) {
        const { candle, volume, isNew } = pendingCandleUpdate;
        candleSeries.update(candle);
        volumeSeries.update(volume);

        if (isNew) {
            const countEl = document.getElementById('candleCount');
            countEl.textContent = parseInt(countEl.textContent) + 1;
        }

        // Auto-scroll only on new completed candle
        if (autoScrollEnabled && !userScrolledAway) {
            chart.timeScale().scrollToRealTime();
        }

        pendingCandleUpdate = null;
        lastCandleRender = now;
    }

    // Process pending current candle update (throttled DOM updates)
    if (pendingCurrentUpdate) {
        const data = pendingCurrentUpdate;

        // Update progress bar using CSS transform (GPU-accelerated)
        const progress = data.progress_pct || 0;
        document.getElementById('progressFill').style.transform = `scaleX(${progress / 100})`;
        document.getElementById('tickProgress').textContent = data.current_ticks || 0;

        // Update buy/sell volume (less frequent - only if changed significantly)
        document.getElementById('buyVolume').textContent = (data.buy_volume || 0).toFixed(4);
        document.getElementById('sellVolume').textContent = (data.sell_volume || 0).toFixed(4);

        // Update current (incomplete) candle on chart
        if (data.open) {
            candleSeries.update({
                time: candleIndex,
                open: data.open,
                high: data.high,
                low: data.low,
                close: data.close
            });
            // NO scrollToRealTime here - too expensive, only on completed candle
        }

        pendingCurrentUpdate = null;
    }

    // Process batched trade updates
    if (pendingTradeUpdates.length > 0) {
        const trades = pendingTradeUpdates.splice(0, TRADE_BATCH_SIZE);
        const tradesList = document.getElementById('tradesList');

        // Use DocumentFragment for batch DOM insertion (much faster)
        const fragment = document.createDocumentFragment();

        trades.forEach(trade => {
            tradeCount++;

            const tradeEl = document.createElement('div');
            tradeEl.className = 'trade-item ' + trade.side.toLowerCase();
            tradeEl.innerHTML = `
                        <span class="trade-price">${trade.price.toFixed(2)}</span>
                        <span class="trade-qty">${trade.qty.toFixed(4)}</span>
                    `;
            fragment.insertBefore(tradeEl, fragment.firstChild);
        });

        tradesList.insertBefore(fragment, tradesList.firstChild);

        // Keep only last 50 trades
        while (tradesList.children.length > 50) {
            tradesList.removeChild(tradesList.lastChild);
        }

        // Update last trade display
        const lastTrade = trades[trades.length - 1];
        if (lastTrade) {
            document.getElementById('totalTrades').textContent = tradeCount;
            document.getElementById('lastPrice').textContent = lastTrade.price.toFixed(2);
            document.getElementById('lastPrice').className = 'stat-value ' + (lastTrade.side === 'Buy' ? 'green' : 'red');
        }

        // If more trades pending, schedule another frame
        if (pendingTradeUpdates.length > 0) {
            scheduleRenderFrame();
        }
    }
}

// Handle WebSocket messages
function handleMessage(msg) {
    switch (msg.type) {
        case 'history': {
            // Load historical candles with index-based time
            candleIndex = 0;
            indexToTimeMap.clear();

            const candles = msg.data.map((c, i) => {
                addToIndexMap(i, c.time);  // Use helper function
                return {
                    time: i,  // Use index, not timestamp
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close
                };
            });
            const volumes = msg.data.map((c, i) => ({
                time: i,  // Use index
                value: c.volume,
                color: c.close >= c.open ? 'rgba(0,200,83,0.5)' : 'rgba(255,23,68,0.5)'
            }));

            candleIndex = msg.data.length;
            candleSeries.setData(candles);
            volumeSeries.setData(volumes);
            document.getElementById('candleCount').textContent = candles.length;

            // Scroll to latest after loading history
            chart.timeScale().scrollToRealTime();
            break;
        }

        case 'candle': {
            // Queue new completed candle for next render frame
            // Use current candleIndex (this is the index where "current" candle was being shown)
            const completedIndex = candleIndex;
            addToIndexMap(completedIndex, msg.data.time);  // Use helper function

            const candle = {
                time: completedIndex,  // Use current index (replaces the "current" preview)
                open: msg.data.open,
                high: msg.data.high,
                low: msg.data.low,
                close: msg.data.close
            };
            pendingCandleUpdate = {
                candle,
                volume: {
                    time: completedIndex,  // Use same index
                    value: msg.data.volume,
                    color: candle.close >= candle.open ? 'rgba(0,200,83,0.5)' : 'rgba(255,23,68,0.5)'
                },
                isNew: true
            };

            // NOW increment for next candle
            candleIndex++;

            scheduleRenderFrame();
            break;
        }

        case 'current': {
            // Queue current candle update
            pendingCurrentUpdate = msg.data;

            // Update latency if server time is available
            if (msg.data.server_time) {
                // Note: This assumes clocks are roughly synced, or at least consistent.
                // We care about *changes* in this value (jitter).
                // A better metric is "time since last message" but this helps see transport delay.
                const latency = Date.now() - msg.data.server_time;
                // Simple moving average
                const latEl = document.getElementById('latencyStat');
                latEl.textContent = `${latency} ms (diff)`;
                if (latency > 1000) latEl.style.color = 'red';
                else latEl.style.color = '#00ff88';
            }

            // Count ticks from current updates for accurate ETA
            const currentTicks = msg.data.current_ticks || 0;
            if (lastTickCount > 0 && currentTicks >= lastTickCount) {
                // Normal increment
                ticksThisSecond += (currentTicks - lastTickCount);
            } else if (lastTickCount > 0 && currentTicks < lastTickCount) {
                // New candle started (ticks reset from high value to low)
                ticksThisSecond += currentTicks;
            }
            lastTickCount = currentTicks;

            scheduleRenderFrame();
            break;
        }

        case 'trade':
            // Queue trade for batched processing
            pendingTradeUpdates.push(msg.data);
            scheduleRenderFrame();
            break;

        case 'trades':
            // Backend sends a micro-batch to reduce message overhead.
            if (Array.isArray(msg.data) && msg.data.length > 0) {
                pendingTradeUpdates.push(...msg.data);
                scheduleRenderFrame();
            }
            break;

        case 'ping':
            // Keep-alive, ignore
            break;
    }
}

// Reset auto-scroll when user clicks "Scroll to Now" button or double-clicks chart
function scrollToNow() {
    userScrolledAway = false;
    chart.timeScale().scrollToRealTime();
}

// Update connection status
function updateConnectionStatus(connected) {
    isConnected = connected;
    const dot = document.getElementById('statusDot');
    const text = document.getElementById('statusText');

    if (connected) {
        dot.classList.add('connected');
        text.textContent = 'Connected - Live';
    } else {
        dot.classList.remove('connected');
        text.textContent = 'Disconnected';
    }
}

// Calculate ETA to next candle
function updateETA() {
    // Store ticks/sec history for averaging (from actual tick count, not trade messages)
    recentTradesPerSecond.push(ticksThisSecond);
    if (recentTradesPerSecond.length > ETA_WINDOW_SIZE) {
        recentTradesPerSecond.shift();
    }

    // Calculate average trades per second
    const avgTradesPerSec = recentTradesPerSecond.reduce((a, b) => a + b, 0) / recentTradesPerSecond.length;

    // Get current progress
    const currentProgress = parseInt(document.getElementById('tickProgress').textContent) || 0;
    const ticksNeeded = currentTicks - currentProgress;

    // Calculate ETA
    const etaEl = document.getElementById('etaText');
    if (avgTradesPerSec > 0 && ticksNeeded > 0) {
        const etaSeconds = ticksNeeded / avgTradesPerSec;
        if (etaSeconds < 60) {
            etaEl.textContent = `ETA: ~${Math.round(etaSeconds)}s`;
        } else {
            const mins = Math.floor(etaSeconds / 60);
            const secs = Math.round(etaSeconds % 60);
            etaEl.textContent = `ETA: ~${mins}m ${secs}s`;
        }
    } else if (currentProgress === 0) {
        etaEl.textContent = 'ETA: waiting for trades...';
    } else {
        etaEl.textContent = 'ETA: calculating...';
    }

    // Update trades/sec display (show actual ticks this second)
    document.getElementById('tradesPerSec').textContent = ticksThisSecond;
    ticksThisSecond = 0;  // Reset for next second
}

// Calculate candle rate (candles per minute)
function updateCandleRate() {
    const now = Date.now();
    const elapsedMs = now - lastMinuteCheckTime;

    if (elapsedMs >= 60000) {
        // One minute passed - calculate rate
        const currentCandleCount = parseInt(document.getElementById('candleCount').textContent) || 0;
        const candlesInLastMinute = currentCandleCount - lastCandleCountCheck;

        document.getElementById('candleRate').textContent = `${candlesInLastMinute} candles/min`;

        lastCandleCountCheck = currentCandleCount;
        lastMinuteCheckTime = now;
    }
}

// Update stats every second
setInterval(() => {
    updateETA();
    updateCandleRate();
}, 1000);

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initChart();
});

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: to, addToIndexMap, initChart, startTickService, stopTickService

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {
    window.tickchartPage = {
        // Add public methods here
    };

    // onclick handler exports (required for auto-event-binding.js with type="module")
    window.startTickService = startTickService;
    window.stopTickService = stopTickService;
    window.scrollToNow = scrollToNow;
}
