/**
 * 📄 Trading Page JavaScript
 *
 * Page-specific scripts for trading.html
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
import liveTrading from '../services/liveTrading.js';

// State
let currentSymbol = 'BTCUSDT';
let currentTimeframe = '60';
let currentSide = 'buy';
let currentLeverage = 5;
let chart = null;
let volumeChart = null;
let candleSeries = null;
let volumeSeries = null;
let volumeSmaSeries = null;
let priceLine = null;
let candleData = [];
let volumeData = [];

const API_BASE = 'http://localhost:8000/api/v1';

// Sample Data
const watchlistData = [
    { symbol: 'BTCUSDT', name: 'Bitcoin', price: 97234.50, change: 2.34 },
    { symbol: 'ETHUSDT', name: 'Ethereum', price: 3456.78, change: -1.23 },
    { symbol: 'SOLUSDT', name: 'Solana', price: 198.45, change: 5.67 },
    { symbol: 'BNBUSDT', name: 'BNB', price: 612.34, change: 0.89 },
    { symbol: 'XRPUSDT', name: 'Ripple', price: 2.34, change: -2.45 },
    { symbol: 'ADAUSDT', name: 'Cardano', price: 0.89, change: 3.21 },
    { symbol: 'DOGEUSDT', name: 'Dogecoin', price: 0.32, change: 8.76 },
    { symbol: 'AVAXUSDT', name: 'Avalanche', price: 42.56, change: -0.54 }
];

const positionsData = [
    {
        symbol: 'BTCUSDT',
        side: 'buy',
        size: 0.15,
        entryPrice: 95000,
        markPrice: 97234.50,
        liqPrice: 76000,
        margin: 2850,
        pnl: 335.18,
        pnlPercent: 11.76
    },
    {
        symbol: 'ETHUSDT',
        side: 'sell',
        size: 2.5,
        entryPrice: 3500,
        markPrice: 3456.78,
        liqPrice: 4200,
        margin: 1750,
        pnl: 108.05,
        pnlPercent: 6.17
    }
];

// eslint-disable-next-line no-unused-vars
const openOrdersData = [
    { symbol: 'SOLUSDT', side: 'buy', type: 'Limit', price: 185.00, amount: 10, filled: 0, status: 'Open' },
    { symbol: 'BTCUSDT', side: 'sell', type: 'Stop', price: 100000, amount: 0.1, filled: 0, status: 'Open' },
    { symbol: 'ETHUSDT', side: 'buy', type: 'Limit', price: 3300, amount: 1.5, filled: 0.5, status: 'Partial' }
];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    loadCandleData();
    renderWatchlist();
    renderPositions();
    setupEventListeners();
    startPriceUpdates();
});

function initCharts() {
    // Main candlestick chart
    const container = document.getElementById('tradingChart');
    chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: container.clientHeight,
        layout: {
            background: { type: 'solid', color: '#0d1117' },
            textColor: '#8b949e',
            fontSize: 12
        },
        grid: {
            vertLines: { color: '#1c2128', style: 1 },
            horzLines: { color: '#1c2128', style: 1 }
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                color: '#58a6ff',
                width: 1,
                style: LightweightCharts.LineStyle.Dashed,
                labelBackgroundColor: '#58a6ff'
            },
            horzLine: {
                color: '#58a6ff',
                width: 1,
                style: LightweightCharts.LineStyle.Dashed,
                labelBackgroundColor: '#58a6ff'
            }
        },
        rightPriceScale: {
            borderColor: '#30363d',
            scaleMargins: { top: 0.1, bottom: 0.2 }
        },
        timeScale: {
            borderColor: '#30363d',
            timeVisible: true,
            secondsVisible: false,
            rightOffset: 5,
            barSpacing: 8
        },
        handleScroll: { vertTouchDrag: false }
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#00c853',
        downColor: '#ff1744',
        borderDownColor: '#ff1744',
        borderUpColor: '#00c853',
        wickDownColor: '#ff1744',
        wickUpColor: '#00c853',
        priceFormat: { type: 'price', precision: 2, minMove: 0.01 }
    });

    // Volume chart
    const volumeContainer = document.getElementById('volumeChart');
    volumeChart = LightweightCharts.createChart(volumeContainer, {
        width: volumeContainer.clientWidth,
        height: volumeContainer.clientHeight,
        layout: {
            background: { type: 'solid', color: '#0d1117' },
            textColor: '#8b949e',
            fontSize: 10
        },
        grid: {
            vertLines: { visible: false },
            horzLines: { color: '#1c2128', style: 1 }
        },
        rightPriceScale: {
            borderColor: '#30363d',
            scaleMargins: { top: 0.1, bottom: 0 }
        },
        timeScale: {
            visible: false
        },
        crosshair: {
            horzLine: { visible: false },
            vertLine: { visible: false }
        }
    });

    volumeSeries = volumeChart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: ''
    });

    // SMA line on volume
    volumeSmaSeries = volumeChart.addLineSeries({
        color: '#58a6ff',
        lineWidth: 1,
        priceScaleId: '',
        lastValueVisible: false,
        priceLineVisible: false
    });

    // Sync time scales
    chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) volumeChart.timeScale().setVisibleLogicalRange(range);
    });

    // Crosshair sync and OHLC display
    chart.subscribeCrosshairMove((param) => {
        if (param.time) {
            const data = param.seriesData.get(candleSeries);
            if (data) {
                updateOhlcDisplay(data);
            }
        }
    });

    // Resize handler
    const resizeObserver = new ResizeObserver(() => {
        chart.resize(container.clientWidth, container.clientHeight);
        volumeChart.resize(volumeContainer.clientWidth, volumeContainer.clientHeight);
    });
    resizeObserver.observe(container);
    resizeObserver.observe(volumeContainer);
}

function updateOhlcDisplay(data) {
    const isUp = data.close >= data.open;
    const cls = isUp ? 'up' : 'down';

    document.getElementById('ohlcOpen').textContent = formatPrice(data.open);
    document.getElementById('ohlcOpen').className = `ohlc-value ${cls}`;

    document.getElementById('ohlcHigh').textContent = formatPrice(data.high);
    document.getElementById('ohlcHigh').className = `ohlc-value ${cls}`;

    document.getElementById('ohlcLow').textContent = formatPrice(data.low);
    document.getElementById('ohlcLow').className = `ohlc-value ${cls}`;

    document.getElementById('ohlcClose').textContent = formatPrice(data.close);
    document.getElementById('ohlcClose').className = `ohlc-value ${cls}`;
}

function formatPrice(price) {
    if (price >= 1000) return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (price >= 1) return price.toFixed(4);
    return price.toFixed(6);
}

async function loadCandleData() {
    try {
        // Fetch from API
        const response = await fetch(
            `${API_BASE}/marketdata/bybit/klines?symbol=${currentSymbol}&interval=${currentTimeframe}&limit=500`
        );

        if (response.ok) {
            const data = await response.json();
            if (data && data.length > 0) {
                candleData = data.map(k => ({
                    time: k.time || Math.floor(k.open_time / 1000),
                    open: parseFloat(k.open),
                    high: parseFloat(k.high),
                    low: parseFloat(k.low),
                    close: parseFloat(k.close)
                }));

                volumeData = data.map(k => ({
                    time: k.time || Math.floor(k.open_time / 1000),
                    value: parseFloat(k.volume || 0),
                    color: parseFloat(k.close) >= parseFloat(k.open)
                        ? 'rgba(0, 200, 83, 0.5)'
                        : 'rgba(255, 23, 68, 0.5)'
                }));

                candleSeries.setData(candleData);
                volumeSeries.setData(volumeData);

                // Calculate and set volume SMA
                const smaData = calculateSMA(volumeData, 9);
                volumeSmaSeries.setData(smaData);

                // Update last SMA value
                if (smaData.length > 0) {
                    const lastSma = smaData[smaData.length - 1].value;
                    document.getElementById('volumeSma').textContent = formatVolume(lastSma);
                }

                // Add price line
                updatePriceLine();
                return;
            }
        }
    } catch (err) {
        console.error('API fetch failed:', err);
        showError('Не удалось загрузить данные с сервера. Проверьте подключение.');
    }
}

function calculateSMA(data, period) {
    const result = [];
    for (let i = period - 1; i < data.length; i++) {
        let sum = 0;
        for (let j = 0; j < period; j++) {
            sum += data[i - j].value;
        }
        result.push({ time: data[i].time, value: sum / period });
    }
    return result;
}

function formatVolume(vol) {
    if (vol >= 1e9) return (vol / 1e9).toFixed(2) + 'B';
    if (vol >= 1e6) return (vol / 1e6).toFixed(2) + 'M';
    if (vol >= 1e3) return (vol / 1e3).toFixed(2) + 'K';
    return vol.toFixed(2);
}

function updatePriceLine() {
    if (candleData.length === 0) return;

    const lastCandle = candleData[candleData.length - 1];
    const isUp = lastCandle.close >= lastCandle.open;

    if (priceLine) {
        candleSeries.removePriceLine(priceLine);
    }

    priceLine = candleSeries.createPriceLine({
        price: lastCandle.close,
        color: isUp ? '#00c853' : '#ff1744',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: ''
    });
}

// Показать ошибку на графике
function showError(message) {
    const container = document.getElementById('tv_chart_container');
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#ff4444;font-size:14px;text-align:center;background:#1e222d;padding:20px;border-radius:8px;border:1px solid #363a45;';
    overlay.textContent = message;
    container.style.position = 'relative';
    container.appendChild(overlay);
}

function renderWatchlist() {
    const container = document.getElementById('watchlist');
    container.innerHTML = watchlistData.map(item => `
                <div class="watchlist-item ${item.symbol === currentSymbol ? 'active' : ''}" 
                     onclick="selectSymbol('${item.symbol}')">
                    <div>
                        <div class="watchlist-symbol">${item.symbol}</div>
                        <div class="watchlist-name">${item.name}</div>
                    </div>
                    <div class="watchlist-price">
                        <div class="watchlist-price-value">$${item.price.toLocaleString()}</div>
                        <div class="watchlist-change ${item.change >= 0 ? 'positive' : 'negative'}">
                            ${item.change >= 0 ? '+' : ''}${item.change.toFixed(2)}%
                        </div>
                    </div>
                </div>
            `).join('');
}

function renderPositions() {
    const tbody = document.getElementById('positionsTableBody');
    tbody.innerHTML = positionsData.map(pos => `
                <tr>
                    <td>
                        <strong>${pos.symbol}</strong>
                        <span class="side-tag ${pos.side}">${pos.side.toUpperCase()}</span>
                    </td>
                    <td>${pos.size} ${pos.symbol.replace('USDT', '')}</td>
                    <td>$${pos.entryPrice.toLocaleString()}</td>
                    <td>$${pos.markPrice.toLocaleString()}</td>
                    <td>$${pos.liqPrice.toLocaleString()}</td>
                    <td>$${pos.margin.toLocaleString()}</td>
                    <td>
                        <span class="pnl-value ${pos.pnl >= 0 ? 'positive' : 'negative'}">
                            ${pos.pnl >= 0 ? '+' : ''}$${pos.pnl.toFixed(2)} (${pos.pnlPercent.toFixed(2)}%)
                        </span>
                    </td>
                    <td>
                        <button class="action-btn" onclick="editPosition('${pos.symbol}')">TP/SL</button>
                        <button class="action-btn danger" onclick="closePosition('${pos.symbol}')">Close</button>
                    </td>
                </tr>
            `).join('');
}

function setupEventListeners() {
    // Timeframe buttons
    document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTimeframe = btn.dataset.tf;
            loadCandleData();
        });
    });

    // Trading tabs
    document.querySelectorAll('.trading-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.trading-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            const panel = tab.dataset.panel;
            document.getElementById('orderPanel').style.display = panel === 'order' ? 'block' : 'none';
            document.getElementById('positionsPanel').style.display = panel === 'positions' ? 'block' : 'none';
            document.getElementById('orderbookPanel').style.display = panel === 'orderbook' ? 'block' : 'none';
        });
    });

    // Order type buttons
    document.querySelectorAll('.order-type-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.order-type-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });

    // Bottom tabs
    document.querySelectorAll('.bottom-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.bottom-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            // Would switch bottom panel content
        });
    });

    // Slider
    document.getElementById('amountSlider').addEventListener('input', (e) => {
        const percent = e.target.value / 100;
        const maxAmount = 0.542; // Example max
        document.getElementById('orderAmount').value = (maxAmount * percent).toFixed(3);
        updateOrderSummary();
    });

    // Price and amount inputs
    ['orderPrice', 'orderAmount'].forEach(id => {
        document.getElementById(id).addEventListener('input', updateOrderSummary);
    });

    // Search
    document.getElementById('watchlistSearch').addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        document.querySelectorAll('.watchlist-item').forEach(item => {
            const symbol = item.querySelector('.watchlist-symbol').textContent.toLowerCase();
            item.style.display = symbol.includes(query) ? 'flex' : 'none';
        });
    });
}

// eslint-disable-next-line no-unused-vars
function selectSymbol(symbol) {
    currentSymbol = symbol;
    document.getElementById('currentSymbol').textContent = symbol;
    document.getElementById('submitOrderBtn').textContent =
        `${currentSide === 'buy' ? 'Buy/Long' : 'Sell/Short'} ${symbol}`;
    renderWatchlist();

    // Update price
    const symbolData = watchlistData.find(s => s.symbol === symbol);
    if (symbolData) {
        document.getElementById('currentPrice').textContent = `$${symbolData.price.toLocaleString()}`;
        document.getElementById('orderPrice').value = symbolData.price;
        updateOrderSummary();
    }
}

function selectSide(side) {
    currentSide = side;
    document.querySelectorAll('.side-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.side-btn.${side}`).classList.add('active');

    const submitBtn = document.getElementById('submitOrderBtn');
    submitBtn.className = `submit-btn ${side}`;
    submitBtn.textContent = `${side === 'buy' ? 'Buy/Long' : 'Sell/Short'} ${currentSymbol}`;
}

function setLeverage(lev) {
    currentLeverage = lev;
    document.getElementById('leverageValue').textContent = `${lev}x`;
    document.querySelectorAll('.leverage-btn').forEach(btn => {
        btn.classList.toggle('active', parseInt(btn.textContent) === lev);
    });
    updateOrderSummary();
}

function updateOrderSummary() {
    const price = parseFloat(document.getElementById('orderPrice').value) || 0;
    const amount = parseFloat(document.getElementById('orderAmount').value) || 0;

    const orderValue = price * amount;
    const margin = orderValue / currentLeverage;
    const fee = orderValue * 0.0006; // 0.06% taker fee

    document.getElementById('orderValue').textContent = `$${orderValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('requiredMargin').textContent = `$${margin.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('estFee').textContent = `$${fee.toFixed(2)}`;
}

function submitOrder() {
    const price = document.getElementById('orderPrice').value;
    const amount = document.getElementById('orderAmount').value;
    const tp = document.getElementById('takeProfit').value;
    const sl = document.getElementById('stopLoss').value;
    const orderType = document.querySelector('.order-type-btn.active')?.dataset.type || 'market';

    const submitBtn = document.getElementById('submitOrderBtn');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Placing order...';

    liveTrading.placeOrder({
        symbol: currentSymbol,
        side: currentSide,
        qty: parseFloat(amount),
        orderType: orderType,
        price: orderType === 'limit' ? parseFloat(price) : null,
        stopLoss: sl ? parseFloat(sl) : null,
        takeProfit: tp ? parseFloat(tp) : null
    })
        .then(result => {
            console.log('Order placed:', result);
            showNotification(`✅ Order placed: ${currentSide.toUpperCase()} ${amount} ${currentSymbol}`, 'success');
            // Refresh positions
            loadPositionsFromAPI();
        })
        .catch(error => {
            console.error('Order failed:', error);
            showNotification(`❌ Order failed: ${error.message}`, 'error');
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        });
}

function startPriceUpdates() {
    // Получение реальных цен из API
    async function fetchRealPrices() {
        try {
            // Use dashboard tickers endpoint which is confirmed working
            const response = await fetch(`${API_BASE}/dashboard/market/tickers?top=20`);
            if (response.ok) {
                const data = await response.json();
                // Handle both array response and {tickers: [...]} response
                const tickers = Array.isArray(data) ? data : (data.tickers || []);
                if (tickers.length > 0) {
                    tickers.forEach(ticker => {
                        const item = watchlistData.find(w => w.symbol === ticker.symbol);
                        if (item) {
                            item.price = parseFloat(ticker.lastPrice || ticker.last_price || ticker.price);
                            item.change = parseFloat(ticker.price24hPcnt || ticker.price_24h_pcnt || ticker.change_24h || 0) * 100;
                        }
                    });
                    renderWatchlist();

                    // Update current price
                    const current = watchlistData.find(s => s.symbol === currentSymbol);
                    if (current) {
                        const priceEl = document.getElementById('currentPrice');
                        priceEl.textContent = `$${current.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                        priceEl.className = `price-value ${current.change >= 0 ? 'up' : 'down'}`;

                        const changeEl = document.getElementById('priceChange');
                        changeEl.textContent = `${current.change >= 0 ? '+' : ''}${current.change.toFixed(2)}%`;
                        changeEl.className = `price-change ${current.change >= 0 ? 'positive' : 'negative'}`;
                    }
                }
            }
        } catch (e) {
            console.warn('Price update failed:', e);
        }
    }

    fetchRealPrices();
    setInterval(fetchRealPrices, 5000); // Обновление каждые 5 секунд
}

// eslint-disable-next-line no-unused-vars
function editPosition(symbol) {
    alert(`Edit TP/SL for ${symbol}`);
}

// eslint-disable-next-line no-unused-vars
function closePosition(symbol) {
    if (confirm(`Close ${symbol} position?`)) {
        const index = positionsData.findIndex(p => p.symbol === symbol);
        if (index !== -1) {
            positionsData.splice(index, 1);
            renderPositions();
        }
    }
}

function openSymbolSearch() {
    alert('Symbol search would open here');
}

function toggleIndicators() {
    alert('Indicators panel would toggle here');
}

function toggleDrawingTools() {
    alert('Drawing tools would toggle here');
}

// ============================================
// NOTIFICATIONS & API INTEGRATION
// ============================================

/**
 * Show notification toast
 * @param {string} message - Notification message
 * @param {string} type - Type: 'success', 'error', 'info'
 */
function showNotification(message, type = 'info') {
    // Remove existing notification
    const existing = document.querySelector('.trading-notification');
    if (existing) existing.remove();

    const notification = document.createElement('div');
    notification.className = `trading-notification trading-notification-${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()" class="notification-close">&times;</button>
    `;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        display: flex;
        align-items: center;
        gap: 12px;
        animation: slideIn 0.3s ease;
        background: ${type === 'success' ? '#00c853' : type === 'error' ? '#ff1744' : '#58a6ff'};
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;

    document.body.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => notification.remove(), 5000);
}

/**
 * Load positions from API
 */
async function loadPositionsFromAPI() {
    try {
        const positions = await liveTrading.getPositions();
        if (positions && positions.length > 0) {
            // Update positionsData with API data
            positionsData.length = 0;
            positions.forEach(pos => {
                positionsData.push({
                    symbol: pos.symbol,
                    side: pos.side.toLowerCase(),
                    size: parseFloat(pos.size || pos.qty || 0),
                    entryPrice: parseFloat(pos.entry_price || pos.entryPrice || 0),
                    markPrice: parseFloat(pos.mark_price || pos.markPrice || 0),
                    liqPrice: parseFloat(pos.liq_price || pos.liqPrice || 0),
                    margin: parseFloat(pos.margin || 0),
                    pnl: parseFloat(pos.unrealized_pnl || pos.pnl || 0),
                    pnlPercent: parseFloat(pos.roe_percent || pos.pnlPercent || 0)
                });
            });
            renderPositions();
        }
    } catch (error) {
        console.error('Failed to load positions:', error);
    }
}

/**
 * Load balance from API
 */
async function loadBalanceFromAPI() {
    try {
        const balance = await liveTrading.getBalance();
        if (balance) {
            const available = balance.available_balance || balance.availableBalance || 0;
            const equity = balance.equity || balance.total_balance || 0;
            const margin = balance.used_margin || balance.usedMargin || 0;

            document.querySelector('.balance-item:nth-child(1) .balance-value').textContent =
                `$${parseFloat(available).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
            document.querySelector('.balance-item:nth-child(2) .balance-value').textContent =
                `$${parseFloat(equity).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
            document.querySelector('.balance-item:nth-child(3) .balance-value').textContent =
                `$${parseFloat(margin).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
        }
    } catch (error) {
        console.error('Failed to load balance:', error);
    }
}

/**
 * Initialize Live Trading connection
 */
async function initLiveTrading() {
    try {
        // Connect WebSocket for real-time updates
        await liveTrading.connectWebSocket();

        // Register callbacks for real-time updates
        liveTrading.onUpdate('position', (data) => {
            console.log('Position update:', data);
            loadPositionsFromAPI();
        });

        liveTrading.onUpdate('wallet', (data) => {
            console.log('Wallet update:', data);
            loadBalanceFromAPI();
        });

        liveTrading.onUpdate('order', (data) => {
            console.log('Order update:', data);
            showNotification(`Order ${data.status}: ${data.symbol}`, 'info');
        });

        liveTrading.onUpdate('error', (data) => {
            console.error('Trading error:', data);
            showNotification(`Error: ${data.error || data.message}`, 'error');
        });

        // Load initial data
        await loadPositionsFromAPI();
        await loadBalanceFromAPI();

        showNotification('Connected to Live Trading', 'success');
    } catch (error) {
        console.warn('Live trading connection failed:', error);
        // Continue without live trading - use mock data
    }
}

// Initialize live trading on page load
document.addEventListener('DOMContentLoaded', () => {
    // Existing initialization is already called
    // Add live trading initialization
    setTimeout(initLiveTrading, 1000); // Delay to ensure other init is complete
});

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: initCharts, updateOhlcDisplay, formatPrice, loadCandleData, calculateSMA

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {
    window.tradingPage = {
        // Add public methods here
    };

    // onclick handler exports (required for auto-event-binding.js with type="module")
    window.openSymbolSearch = openSymbolSearch;
    window.toggleIndicators = toggleIndicators;
    window.toggleDrawingTools = toggleDrawingTools;
    window.selectSide = selectSide;
    window.setLeverage = setLeverage;
    window.submitOrder = submitOrder;
    window.selectSymbol = selectSymbol;
    window.editPosition = editPosition;
    window.closePosition = closePosition;
}
