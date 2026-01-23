/**
 * 📄 Strategies Page JavaScript
 *
 * Page-specific scripts for strategies.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 1.1.0
 * @date 2025-12-22
 */

// Import shared utilities
import { debounce } from '../utils.js';

const API_BASE = '/api/v1';
let strategies = [];
let strategyTypes = [];
const topSymbols = []; // Cache for top symbols (modified via push)
// eslint-disable-next-line no-unused-vars
let editingStrategyId = null;

// Note: updatePositionSizeInput is defined at the bottom of the file
// and exposed via window.updatePositionSizeInput

/**
 * Update leverage display and slider background
 */
function updateLeverageDisplay(value) {
    const leverageValue = document.getElementById('leverageValue');
    const leverageSlider = document.getElementById('strategyLeverage');
    const maxLeverage = leverageSlider ? parseInt(leverageSlider.max) || 100 : 100;

    if (leverageValue) {
        leverageValue.textContent = value + 'x';
        // Change color for high leverage warning (relative to max)
        const leveragePercent = value / maxLeverage;
        if (leveragePercent >= 0.5) {
            leverageValue.style.color = '#ff6b6b';
        } else if (leveragePercent >= 0.2) {
            leverageValue.style.color = '#ffd93d';
        } else {
            leverageValue.style.color = 'var(--accent-color)';
        }
    }

    // Update slider track gradient via CSS variable
    if (leverageSlider) {
        const percent = ((value - 1) / (maxLeverage - 1)) * 100;
        leverageSlider.style.setProperty('--leverage-percent', `${percent}%`);
    }
}
// Expose to global scope for inline event handlers
window.updateLeverageDisplay = updateLeverageDisplay;

/**
 * Initialize leverage slider scroll support
 */
function initLeverageSliderScroll() {
    const leverageSlider = document.getElementById('strategyLeverage');
    if (!leverageSlider) return;

    // Scroll wheel support
    leverageSlider.addEventListener('wheel', function (e) {
        e.preventDefault();

        const currentValue = parseInt(this.value);
        const maxLeverage = parseInt(this.max) || 100;
        const step = e.deltaY < 0 ? 1 : -1; // Scroll up = increase, scroll down = decrease

        let newValue = currentValue + step;
        newValue = Math.max(1, Math.min(maxLeverage, newValue)); // Clamp between 1 and max

        this.value = newValue;
        updateLeverageDisplay(newValue);
        // Update warning when leverage changes
        updateLeverageLimits().catch(() => {});
    }, { passive: false });

    // Update warning dynamically when slider moves
    leverageSlider.addEventListener('input', function () {
        updateLeverageDisplay(parseInt(this.value));
        updateLeverageLimits().catch(() => {});
    });
}

// Cache for instrument info
const instrumentInfoCache = {};
// Cache for current prices
const priceCache = {};

/**
 * Fetch instrument info for a symbol (leverage limits, min order size, etc.)
 */
async function fetchInstrumentInfo(symbol) {
    if (!symbol) return null;

    const sym = symbol.toUpperCase().replace('USDT', '') + 'USDT';

    // Check cache first (with 5 min TTL for instrument info)
    const cached = instrumentInfoCache[sym];
    if (cached && cached.timestamp && Date.now() - cached.timestamp < 300000) {
        return cached.data;
    }

    try {
        const response = await fetch(`${API_BASE}/marketdata/symbols/${sym}/instrument-info`);
        if (!response.ok) {
            console.warn(`Failed to fetch instrument info for ${sym}`);
            return null;
        }
        const info = await response.json();
        instrumentInfoCache[sym] = { data: info, timestamp: Date.now() };
        return info;
    } catch (error) {
        console.error('Error fetching instrument info:', error);
        return null;
    }
}

/**
 * Fetch current price for a symbol
 */
async function fetchCurrentPrice(symbol) {
    if (!symbol) return null;

    const sym = symbol.toUpperCase().replace('USDT', '') + 'USDT';

    // Check cache (with 10 sec TTL for price)
    const cached = priceCache[sym];
    if (cached && cached.timestamp && Date.now() - cached.timestamp < 10000) {
        return cached.price;
    }

    try {
        // Use klines endpoint to get latest price
        const response = await fetch(`${API_BASE}/marketdata/bybit/klines/fetch?symbol=${sym}&interval=1&limit=1`);
        if (!response.ok) {
            console.warn(`Failed to fetch price for ${sym}`);
            return null;
        }
        const data = await response.json();
        if (data && data.length > 0) {
            const price = parseFloat(data[0].close || data[0][4]); // close price
            priceCache[sym] = { price, timestamp: Date.now() };
            return price;
        }
        return null;
    } catch (error) {
        console.error('Error fetching price:', error);
        return null;
    }
}

/**
 * Round quantity according to Bybit qtyStep
 */
function roundToStep(value, step) {
    if (!step || step <= 0) return value;
    const precision = Math.max(0, Math.ceil(-Math.log10(step)));
    return Math.floor(value / step) * step;
}

// Cache for volatility data (avoid repeated API calls)
const volatilityCache = {};
const VOLATILITY_CACHE_TTL = 60000; // 1 minute cache

/**
 * Fetch volatility data for a symbol (90-day analysis)
 */
async function fetchVolatility(symbol) {
    // Check cache
    const cached = volatilityCache[symbol];
    if (cached && (Date.now() - cached.timestamp < VOLATILITY_CACHE_TTL)) {
        return cached.data;
    }

    try {
        const response = await fetch(`/api/v1/marketdata/bybit/volatility?symbol=${symbol}&days=90`);
        if (response.ok) {
            const data = await response.json();
            volatilityCache[symbol] = { data, timestamp: Date.now() };
            return data;
        }
        return null;
    } catch (error) {
        console.error('Error fetching volatility:', error);
        return null;
    }
}

/**
 * Calculate and apply maximum leverage based on order size and instrument limits
 *
 * Logic:
 * 1. Get current price, minNotionalValue ($5), qtyStep, minOrderQty
 * 2. Calculate: minQty = max(minOrderQty, ceil(minNotionalValue / price / qtyStep) * qtyStep)
 * 3. minPositionValue = minQty * price
 * 4. With margin = orderAmount, maxLeverage = floor(orderAmount / (minPositionValue / leverage))
 *    But minPositionValue must be met, so: leverage * margin >= minPositionValue
 *    => maxLeverage = floor(margin / (minNotionalValue / maxLeverage_exchange))
 *
 * Simplified: To open minimum position of $5, with margin M:
 *    If M < $5, we can't trade at all
 *    If M >= $5, maxLeverage = min(exchangeMax, floor(M / minNotionalValue * exchangeMax))
 *    But practically: maxLeverage = min(exchangeMax, floor(capital / minNotionalValue))
 */
async function updateLeverageLimits() {
    try {
        const symbolEl = document.getElementById('strategySymbol');
        const capitalEl = document.getElementById('strategyCapital');
        const positionSizeTypeEl = document.getElementById('strategyPositionSizeType');
        const positionSizeEl = document.getElementById('strategyPositionSize');
        const leverageSlider = document.getElementById('strategyLeverage');
        const leverageScale = document.querySelector('.leverage-scale');
        const leverageWarning = document.getElementById('leverageWarning');
        const leverageRiskIndicator = document.getElementById('leverageRiskIndicator');

        if (!leverageSlider) return;

        const symbol = symbolEl?.value || 'BTCUSDT';
        const capital = parseFloat(capitalEl?.value) || 10000;
        const positionSizeType = positionSizeTypeEl?.value || 'percent';
        const positionSize = parseFloat(positionSizeEl?.value) || 100;

        // Fetch instrument info, current price, and volatility in parallel
        const [info, currentPrice, volatility] = await Promise.all([
            fetchInstrumentInfo(symbol),
            fetchCurrentPrice(symbol),
            fetchVolatility(symbol)
        ]);

        // Default limits
        let exchangeMaxLeverage = 100;
        let minNotionalValue = 5; // Default $5 minimum
        let minOrderQty = 0.001;
        let qtyStep = 0.001;

        if (info) {
            exchangeMaxLeverage = info.maxLeverage || 100;
            minNotionalValue = info.minNotionalValue || 5;
            minOrderQty = info.minOrderQty || 0.001;
            qtyStep = info.qtyStep || 0.001;
        }

        // Calculate margin and position based on order type
        //
        // Bybit formula: Initial Margin = Position Value / Leverage
        // Therefore: Position Value = Margin × Leverage
        //
        // Types:
        // - percent: margin = % of capital, position = margin × leverage
        // - fixed_amount: margin = specified $ amount, position = margin × leverage
        // - contracts: position = contracts × price (fixed), margin = position / leverage
        //
        // Validation:
        // - margin ≤ capital (can't risk more than you have)
        // - position ≥ minNotionalValue (Bybit minimum ~$5)

        let margin = capital;        // Margin (collateral) for the trade
        let isPositionFixed = false; // Whether position size is fixed (contracts mode)
        let fixedPositionValue = 0;  // Fixed position value for contracts mode

        if (positionSizeType === 'percent') {
            // Margin = % of capital
            margin = capital * (positionSize / 100);
        } else if (positionSizeType === 'fixed_amount') {
            // Margin = fixed $ amount
            margin = positionSize;
        } else if (positionSizeType === 'contracts' && currentPrice) {
            // Position is fixed (contracts × price), margin = position / leverage
            isPositionFixed = true;
            fixedPositionValue = positionSize * currentPrice;
        }

        // Calculate minimum position requirements
        let minPositionValue = minNotionalValue;
        if (currentPrice && currentPrice > 0) {
            // Calculate minimum quantity that satisfies both minOrderQty and minNotionalValue
            const minQtyFromNotional = Math.ceil(minNotionalValue / currentPrice / qtyStep) * qtyStep;
            const effectiveMinQty = Math.max(minOrderQty, minQtyFromNotional);
            minPositionValue = effectiveMinQty * currentPrice;
        }

        // Calculate leverage constraints
        // For percent/fixed_amount: margin is set by user, position = margin × leverage
        // For contracts: position is fixed, margin = position / leverage
        //
        // Bybit requires: position value >= minNotionalValue (typically $5)
        // User requires: required margin <= capital

        const effectiveMaxLeverage = exchangeMaxLeverage;
        const currentLeverage = parseInt(leverageSlider.value) || 1;

        let positionValue, requiredMargin;

        if (isPositionFixed) {
            // Contracts mode: position is fixed, margin = position / leverage
            positionValue = fixedPositionValue;
            requiredMargin = positionValue / currentLeverage;
        } else {
            // Percent/Fixed amount: margin is set, position = margin × leverage
            positionValue = margin * currentLeverage;
            requiredMargin = margin;
        }

        let warningMessage = '';
        let isError = false;

        if (margin <= 0 && !isPositionFixed) {
            // No margin set - no warning
        } else if (requiredMargin > capital) {
            // Required margin exceeds available capital
            if (isPositionFixed) {
                const minLeverageForCapital = Math.ceil(fixedPositionValue / capital);
                if (minLeverageForCapital <= effectiveMaxLeverage) {
                    warningMessage = `Требуемая маржа $${requiredMargin.toFixed(2)} превышает капитал $${capital}. Увеличьте плечо до ${minLeverageForCapital}x`;
                } else {
                    warningMessage = `Позиция $${fixedPositionValue.toFixed(2)} слишком большая. Даже с плечом ${effectiveMaxLeverage}x маржа ($${(fixedPositionValue / effectiveMaxLeverage).toFixed(2)}) превышает капитал $${capital}`;
                    isError = true;
                }
            } else {
                warningMessage = `Маржа $${margin.toFixed(2)} превышает капитал $${capital}`;
                isError = true;
            }
        } else if (positionValue < minPositionValue) {
            // Position too small
            warningMessage = `Размер позиции $${positionValue.toFixed(2)} меньше минимума $${minPositionValue.toFixed(2)}`;
        }

        // Update slider limits - always 1x to max
        leverageSlider.min = 1;
        leverageSlider.max = effectiveMaxLeverage;
        updateLeverageDisplay(currentLeverage);

        // Update scale labels - always show full range
        if (leverageScale) {
            const max = effectiveMaxLeverage;
            leverageScale.innerHTML = `
                <span>1x</span>
                <span>${Math.round(max * 0.25)}x</span>
                <span>${Math.round(max * 0.5)}x</span>
                <span>${Math.round(max * 0.75)}x</span>
                <span>${max}x</span>
            `;
        }

        // Show/hide warning
        if (leverageWarning) {
            if (warningMessage) {
                leverageWarning.textContent = warningMessage;
                leverageWarning.classList.add('visible');
                if (isError) {
                    leverageWarning.classList.add('error');
                } else {
                    leverageWarning.classList.remove('error');
                }
            } else {
                leverageWarning.classList.remove('visible', 'error');
                leverageWarning.textContent = '';
            }
        }

        // Update risk indicator
        // Formula: Liquidation at price move = 100% / Leverage
        // Compare with actual volatility to assess real risk
        if (leverageRiskIndicator) {
            const liquidationPercent = (100 / currentLeverage);
            let riskClass, riskText;

            // If we have volatility data, use it for smarter risk assessment
            if (volatility && volatility.avg_daily_range) {
                const maxMove = volatility.max_daily_move || 0;
                const avgRange = volatility.avg_daily_range;

                // Use AVERAGE daily volatility for risk assessment (not max!)
                // riskRatio = how many average daily moves fit into liquidation threshold
                // < 2: very risky - could be liquidated in 1-2 bad days
                // 2-4: moderate risk
                // 4-8: acceptable risk
                // > 8: low risk
                const riskRatio = liquidationPercent / avgRange;

                // Also check if max historical move could liquidate (warning)
                const maxMoveWarning = maxMove > 0 && liquidationPercent < maxMove;

                if (riskRatio < 2) {
                    riskClass = 'risk-extreme';
                    riskText = `🔴 ОПАСНО! Ликвидация: ${liquidationPercent.toFixed(1)}% | Ср. волатильность: ${avgRange.toFixed(1)}%/день`;
                } else if (riskRatio < 4 || maxMoveWarning) {
                    riskClass = 'risk-high';
                    const extra = maxMoveWarning ? ` (макс. ${maxMove.toFixed(0)}%)` : '';
                    riskText = `🟠 Высокий риск: ликвидация ${liquidationPercent.toFixed(1)}% | Волатильность: ${avgRange.toFixed(1)}%${extra}`;
                } else if (riskRatio < 8) {
                    riskClass = 'risk-medium';
                    riskText = `🟡 Средний риск: ликвидация ${liquidationPercent.toFixed(1)}% | Волатильность: ${avgRange.toFixed(1)}%/день`;
                } else {
                    riskClass = 'risk-low';
                    riskText = `🟢 Низкий риск: ликвидация ${liquidationPercent.toFixed(1)}% | Волатильность: ${avgRange.toFixed(1)}%/день`;
                }
            } else {
                // Fallback to simple leverage-based assessment
                if (currentLeverage <= 5) {
                    riskClass = 'risk-low';
                    riskText = `🟢 Низкий риск: ликвидация при движении ${liquidationPercent.toFixed(2)}%`;
                } else if (currentLeverage <= 20) {
                    riskClass = 'risk-medium';
                    riskText = `🟡 Средний риск: ликвидация при движении ${liquidationPercent.toFixed(2)}%`;
                } else if (currentLeverage <= 50) {
                    riskClass = 'risk-high';
                    riskText = `🟠 Высокий риск: ликвидация при движении ${liquidationPercent.toFixed(2)}%`;
                } else {
                    riskClass = 'risk-extreme';
                    riskText = `🔴 Экстремальный риск: ликвидация при движении ${liquidationPercent.toFixed(2)}%`;
                }
            }

            leverageRiskIndicator.textContent = riskText;
            leverageRiskIndicator.className = `leverage-risk-indicator ${riskClass}`;
        }

        // Log for debugging
        if (currentPrice) {
            console.log(`${symbol}: type=${positionSizeType}, margin=$${requiredMargin.toFixed(2)}, leverage=${currentLeverage}x, position=$${positionValue.toFixed(2)}, capital=$${capital}`);
        }

    } catch (error) {
        console.warn('Error updating leverage limits:', error);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadStrategies();
    loadStrategyTypes();
    loadTopSymbols(); // Load top 20 symbols
    setupFilters();
    setDefaultDates();
    setupEventListeners();
    initLeverageSliderScroll(); // Enable scroll on leverage slider
});

/**
 * Setup all event listeners (CSP-compliant, no inline handlers)
 */
function setupEventListeners() {
    // Main toolbar buttons
    const btnNewStrategy = document.getElementById('btnNewStrategy');
    if (btnNewStrategy) {
        btnNewStrategy.addEventListener('click', openCreateModal);
    }

    // Strategy modal buttons
    const btnCloseModal = document.getElementById('btnCloseModal');
    if (btnCloseModal) {
        btnCloseModal.addEventListener('click', closeModal);
    }

    const btnCancelModal = document.getElementById('btnCancelModal');
    if (btnCancelModal) {
        btnCancelModal.addEventListener('click', closeModal);
    }

    const btnSaveStrategy = document.getElementById('btnSaveStrategy');
    if (btnSaveStrategy) {
        btnSaveStrategy.addEventListener('click', saveStrategy);
    }

    // Backtest modal buttons
    const btnCloseBacktestModal = document.getElementById('btnCloseBacktestModal');
    if (btnCloseBacktestModal) {
        btnCloseBacktestModal.addEventListener('click', closeBacktestModal);
    }

    const btnCancelBacktest = document.getElementById('btnCancelBacktest');
    if (btnCancelBacktest) {
        btnCancelBacktest.addEventListener('click', closeBacktestModal);
    }

    const btnRunBacktest = document.getElementById('btnRunBacktest');
    if (btnRunBacktest) {
        btnRunBacktest.addEventListener('click', runBacktest);
    }

    // Initialize period quick-select buttons
    initPeriodButtons();

    // Strategy type change
    const strategyType = document.getElementById('strategyType');
    if (strategyType) {
        strategyType.addEventListener('change', () => updateParametersUI());
    }

    // Symbol and Timeframe change - trigger data check
    const strategySymbol = document.getElementById('strategySymbol');
    if (strategySymbol) {
        strategySymbol.addEventListener('input', checkSymbolData);
        strategySymbol.addEventListener('change', () => {
            checkSymbolData();
            updateLeverageLimits().catch(err => console.warn('Leverage update error:', err));
        });
    }

    const strategyTimeframe = document.getElementById('strategyTimeframe');
    if (strategyTimeframe) {
        strategyTimeframe.addEventListener('change', checkSymbolData);
    }

    // Capital and position size changes - update leverage limits
    const strategyCapital = document.getElementById('strategyCapital');
    if (strategyCapital) {
        strategyCapital.addEventListener('change', () => updateLeverageLimits().catch(() => {}));
        strategyCapital.addEventListener('input', debounce(() => updateLeverageLimits().catch(() => {}), 300));
    }

    const strategyPositionSize = document.getElementById('strategyPositionSize');
    if (strategyPositionSize) {
        strategyPositionSize.addEventListener('change', () => updateLeverageLimits().catch(() => {}));
        strategyPositionSize.addEventListener('input', debounce(() => updateLeverageLimits().catch(() => {}), 300));
    }

    const strategyPositionSizeType = document.getElementById('strategyPositionSizeType');
    if (strategyPositionSizeType) {
        strategyPositionSizeType.addEventListener('change', () => updateLeverageLimits().catch(() => {}));
    }

    // Delegate click events for dynamically created strategy cards
    const container = document.getElementById('strategiesContainer');
    if (container) {
        container.addEventListener('click', handleStrategyCardClick);
    }
}

/**
 * Handle clicks on strategy cards (event delegation)
 */
function handleStrategyCardClick(e) {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;

    const action = btn.dataset.action;
    const strategyId = btn.dataset.id;

    switch (action) {
    case 'backtest':
        openBacktestModal(strategyId);
        break;
    case 'edit':
        editStrategy(strategyId);
        break;
    case 'duplicate':
        duplicateStrategy(strategyId);
        break;
    case 'pause':
        pauseStrategy(strategyId);
        break;
    case 'activate':
        activateStrategy(strategyId);
        break;
    case 'delete':
        deleteStrategy(strategyId);
        break;
    }
}

function setDefaultDates() {
    const today = new Date();
    const sixMonthsAgo = new Date();
    sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);

    document.getElementById('backtestStartDate').value = sixMonthsAgo.toISOString().split('T')[0];
    document.getElementById('backtestEndDate').value = today.toISOString().split('T')[0];
}

// =============================================================================
// TOP SYMBOLS & DATA CHECK
// =============================================================================

/**
 * Load top 20 trading pairs by volume from Bybit
 */
async function loadTopSymbols() {
    try {
        const response = await fetch(`${API_BASE}/marketdata/symbols/top?limit=20`);
        if (!response.ok) throw new Error('Failed to load symbols');

        const data = await response.json();
        const symbols = data.symbols || [];

        // Populate datalist
        const datalist = document.getElementById('symbolsList');
        if (datalist) {
            datalist.innerHTML = symbols.map(s =>
                `<option value="${s.symbol}" label="${s.symbol} - $${formatNumber(s.turnover_24h)}">`
            ).join('');
        }

        // Store for later use
        topSymbols.length = 0;
        topSymbols.push(...symbols);

    } catch (error) {
        console.error('Failed to load top symbols:', error);
        // Fallback to default popular pairs
        const fallbackSymbols = [
            'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
            'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT',
            'MATICUSDT', 'LTCUSDT', 'UNIUSDT', 'ATOMUSDT', 'XLMUSDT',
            'FILUSDT', 'APTUSDT', 'ARBUSDT', 'OPUSDT', 'NEARUSDT'
        ];
        const datalist = document.getElementById('symbolsList');
        if (datalist) {
            datalist.innerHTML = fallbackSymbols.map(s =>
                `<option value="${s}">`
            ).join('');
        }
    }
}

/**
 * Check if data exists for selected symbol/timeframe and trigger loading if needed
 */
const checkSymbolData = debounce(async function () {
    const symbol = document.getElementById('strategySymbol').value?.trim().toUpperCase();
    const timeframe = document.getElementById('strategyTimeframe').value;

    const statusRow = document.getElementById('dataStatusRow');
    const statusIndicator = document.getElementById('dataStatusIndicator');

    // Hide if either is not selected
    if (!symbol || !timeframe) {
        statusRow?.classList.add('hidden');
        return;
    }

    // Show checking status
    statusRow?.classList.remove('hidden');
    statusIndicator.className = 'data-status checking';
    statusIndicator.innerHTML = `
        <span class="status-icon">⏳</span>
        <span class="status-text">Проверка данных для ${symbol} / ${timeframe}...</span>
    `;

    try {
        const response = await fetch(
            `${API_BASE}/marketdata/symbols/check-data?symbol=${symbol}&interval=${timeframe}`
        );

        if (!response.ok) throw new Error('Check failed');

        const data = await response.json();

        if (data.has_data) {
            // Data available - show freshness info
            const freshIcon = getFreshnessIcon(data.freshness);
            const freshText = getFreshnessText(data.freshness, data.hours_old);
            const lastDate = data.latest_datetime
                ? new Date(data.latest_datetime).toLocaleString('ru-RU')
                : '';

            // Auto-refresh if data is stale or outdated
            if (data.freshness === 'stale' || data.freshness === 'outdated') {
                statusIndicator.className = 'data-status loading';
                statusIndicator.innerHTML = `
                    <span class="status-icon">🔄</span>
                    <span class="status-text">
                        Обновление данных...
                        <br><small>${freshText}</small>
                    </span>
                `;

                // Trigger auto-refresh
                await refreshSymbolData(symbol, timeframe, statusIndicator);
            } else {
                // Data is fresh - still do a quick update for latest candles
                // Show status first
                const firstDate = data.earliest_datetime
                    ? new Date(data.earliest_datetime).toLocaleDateString('ru-RU')
                    : '';
                const periodText = firstDate && lastDate
                    ? `${firstDate} — ${new Date(data.latest_datetime).toLocaleDateString('ru-RU')}`
                    : '';

                statusIndicator.className = 'data-status available';
                statusIndicator.innerHTML = `
                    <span class="status-icon">${freshIcon}</span>
                    <span class="status-text">
                        Данные доступны: ${formatNumber(data.candle_count)} свечей
                        <br><small>${periodText ? 'Период: ' + periodText + ' • ' : ''}${freshText}</small>
                    </span>
                    <button type="button" class="btn-refresh-data" onclick="window.forceRefreshData()" title="Обновить данные">🔄</button>
                `;

                // Store current selection for force refresh
                window._currentSymbol = symbol;
                window._currentTimeframe = timeframe;
                window._currentStatusIndicator = statusIndicator;
            }
        } else {
            // No data - trigger loading
            statusIndicator.className = 'data-status loading';
            statusIndicator.innerHTML = `
                <span class="status-icon">📥</span>
                <span class="status-text">Загрузка данных...</span>
            `;

            // Trigger data loading
            await refreshSymbolData(symbol, timeframe, statusIndicator);
        }

    } catch (error) {
        console.error('Data check failed:', error);
        statusIndicator.className = 'data-status error';
        statusIndicator.innerHTML = `
            <span class="status-icon">⚠️</span>
            <span class="status-text">Ошибка проверки данных</span>
        `;
    }
}, 500);

/**
 * Format large numbers for display
 */
function formatNumber(num) {
    if (!num) return '0';
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
    return num.toFixed(0);
}

/**
 * Get icon for data freshness status
 */
function getFreshnessIcon(freshness) {
    switch (freshness) {
    case 'fresh':
        return '✅';
    case 'stale':
        return '⚠️';
    case 'outdated':
        return '🔄';
    default:
        return '❓';
    }
}

/**
 * Get text description for data freshness
 */
function getFreshnessText(freshness, hoursOld) {
    const hoursText = hoursOld !== null ? ` (${formatHoursAgo(hoursOld)})` : '';

    switch (freshness) {
    case 'fresh':
        return `Данные актуальны${hoursText}`;
    case 'stale':
        return `Требуется обновление${hoursText}`;
    case 'outdated':
        return `Данные устарели${hoursText}`;
    default:
        return 'Статус неизвестен';
    }
}

/**
 * Force refresh data (called from refresh button)
 */
window.forceRefreshData = async function () {
    const symbol = window._currentSymbol;
    const timeframe = window._currentTimeframe;
    const statusIndicator = window._currentStatusIndicator;

    if (symbol && timeframe && statusIndicator) {
        statusIndicator.className = 'data-status loading';
        statusIndicator.innerHTML = `
            <span class="status-icon">🔄</span>
            <span class="status-text">Обновление данных...</span>
        `;
        await refreshSymbolData(symbol, timeframe, statusIndicator);
    }
};

/**
 * Refresh symbol data from Bybit API with SSE progress streaming
 */
async function refreshSymbolData(symbol, timeframe, statusIndicator) {
    // Get progress bar elements
    const progressContainer = document.getElementById('candleLoadingProgress');
    const progressBar = document.getElementById('candleLoadingBar');
    const progressStatus = document.getElementById('candleLoadingStatus');
    const progressPercent = document.getElementById('candleLoadingPercent');
    const progressDetails = document.getElementById('candleLoadingDetails');

    // Show progress bar
    if (progressContainer) {
        progressContainer.classList.remove('hidden');
        progressBar.style.width = '0%';
        progressStatus.textContent = 'Подключение к серверу...';
        progressPercent.textContent = '0%';
        progressDetails.textContent = 'Инициализация...';
    }

    try {
        // Use SSE for progress streaming
        const eventSource = new EventSource(
            `${API_BASE}/marketdata/symbols/refresh-data-stream?symbol=${symbol}&interval=${timeframe}`
        );

        return new Promise((resolve, reject) => {
            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.event === 'progress') {
                        // Update progress bar
                        if (progressContainer) {
                            progressBar.style.width = `${data.percent}%`;
                            progressPercent.textContent = `${data.percent}%`;
                            progressStatus.textContent = data.message || 'Загрузка...';
                            if (data.loaded !== undefined && data.total !== undefined) {
                                progressDetails.textContent = `${formatNumber(data.loaded)} / ${formatNumber(data.total)} свечей`;
                            }
                        }
                    } else if (data.event === 'complete') {
                        // Complete - update UI
                        if (progressContainer) {
                            progressBar.style.width = '100%';
                            progressPercent.textContent = '100%';
                            progressStatus.textContent = 'Готово!';
                            progressDetails.textContent = data.message || `${formatNumber(data.total_count)} свечей загружено`;
                        }

                        // Update status indicator
                        statusIndicator.className = 'data-status available';
                        statusIndicator.innerHTML = `
                            <span class="status-icon">✅</span>
                            <span class="status-text">
                                ${data.new_candles > 0 ? `Добавлено ${formatNumber(data.new_candles)} свечей` : 'Данные актуальны'}
                                <br><small>Всего: ${formatNumber(data.total_count)} свечей в базе</small>
                            </span>
                        `;

                        // Hide progress bar after short delay
                        setTimeout(() => {
                            progressContainer?.classList.add('hidden');
                        }, 2000);

                        eventSource.close();
                        resolve(data);
                    } else if (data.event === 'error') {
                        throw new Error(data.message);
                    }
                } catch (parseError) {
                    console.error('SSE parse error:', parseError);
                }
            };

            eventSource.onerror = (error) => {
                console.error('SSE connection error:', error);
                eventSource.close();

                // Fallback to regular POST request
                fallbackRefresh(symbol, timeframe, statusIndicator, progressContainer)
                    .then(resolve)
                    .catch(reject);
            };

            // Timeout after 60 seconds
            setTimeout(() => {
                if (eventSource.readyState !== EventSource.CLOSED) {
                    eventSource.close();
                    fallbackRefresh(symbol, timeframe, statusIndicator, progressContainer)
                        .then(resolve)
                        .catch(reject);
                }
            }, 60000);
        });

    } catch (error) {
        console.error('Data refresh failed:', error);
        progressContainer?.classList.add('hidden');
        statusIndicator.className = 'data-status error';
        statusIndicator.innerHTML = `
            <span class="status-icon">❌</span>
            <span class="status-text">Ошибка обновления данных</span>
        `;
    }
}

/**
 * Fallback refresh using regular POST request
 */
async function fallbackRefresh(symbol, timeframe, statusIndicator, progressContainer) {
    try {
        const response = await fetch(
            `${API_BASE}/marketdata/symbols/refresh-data?symbol=${symbol}&interval=${timeframe}`,
            { method: 'POST' }
        );

        if (!response.ok) throw new Error('Refresh failed');

        const data = await response.json();

        // Format date range
        const dateRange = formatDateRange(data.earliest_datetime, data.latest_datetime);

        // Hide progress bar
        progressContainer?.classList.add('hidden');

        // Show success with period info
        statusIndicator.className = 'data-status available';
        statusIndicator.innerHTML = `
            <span class="status-icon">✅</span>
            <span class="status-text">
                ${data.message}
                <br><small>Всего: ${formatNumber(data.total_count)} свечей • ${dateRange}</small>
            </span>
        `;

        return data;

    } catch (error) {
        console.error('Fallback refresh failed:', error);
        progressContainer?.classList.add('hidden');
        statusIndicator.className = 'data-status error';
        statusIndicator.innerHTML = `
            <span class="status-icon">❌</span>
            <span class="status-text">Ошибка обновления данных</span>
        `;
        throw error;
    }
}

/**
 * Format date range for display
 */
function formatDateRange(earliestIso, latestIso) {
    if (!earliestIso || !latestIso) return '';

    const earliest = new Date(earliestIso);
    const latest = new Date(latestIso);

    const formatDate = (d) => d.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });

    return `${formatDate(earliest)} — ${formatDate(latest)}`;
}

/**
 * Format hours ago into human-readable Russian text
 */
function formatHoursAgo(hours) {
    if (hours < 1) {
        const mins = Math.round(hours * 60);
        return `${mins} мин. назад`;
    } else if (hours < 24) {
        return `${Math.round(hours)} ч. назад`;
    } else {
        const days = Math.round(hours / 24);
        return `${days} дн. назад`;
    }
}

async function loadStrategies() {
    try {
        const params = new URLSearchParams();
        const search = document.getElementById('searchInput').value;
        const status = document.getElementById('statusFilter').value;
        const type = document.getElementById('typeFilter').value;

        if (search) params.append('search', search);
        if (status) params.append('status', status);
        if (type) params.append('strategy_type', type);

        const response = await fetch(`${API_BASE}/strategies/?${params}`);
        const data = await response.json();
        strategies = data.items || [];
        renderStrategies();
    } catch (error) {
        showToast('Failed to load strategies: ' + error.message, 'error');
        document.getElementById('strategiesContainer').innerHTML = `
            <div class="empty-state">
                <h3>Error loading strategies</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

async function loadStrategyTypes() {
    try {
        const response = await fetch(`${API_BASE}/strategies/types`);
        strategyTypes = await response.json();
    } catch (error) {
        console.error('Failed to load strategy types:', error);
    }
}

function setupFilters() {
    document.getElementById('searchInput').addEventListener('input', debounce(loadStrategies, 300));
    document.getElementById('statusFilter').addEventListener('change', loadStrategies);
    document.getElementById('typeFilter').addEventListener('change', loadStrategies);
}

function renderStrategies() {
    const container = document.getElementById('strategiesContainer');

    if (strategies.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No strategies found</h3>
                <p>Create your first trading strategy using the "+ New Strategy" button above.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = strategies.map(strategy => `
        <div class="strategy-card">
            <div class="strategy-header">
                <div>
                    <div class="strategy-title">${escapeHtml(strategy.name)}</div>
                    <span class="strategy-type">${strategy.strategy_type}</span>
                </div>
                <span class="strategy-status status-${strategy.status}">${strategy.status}</span>
            </div>

            <div class="strategy-meta">
                <span>📈 ${strategy.symbol || 'BTCUSDT'}</span>
                <span>⏱ ${strategy.timeframe || '1h'}</span>
                <span>💰 $${(strategy.initial_capital || 10000).toLocaleString()}</span>
            </div>

            <div class="strategy-metrics">
                <div class="metric">
                    <div class="metric-value ${getReturnClass(strategy.total_return)}">
                        ${formatPercent(strategy.total_return)}
                    </div>
                    <div class="metric-label">Return</div>
                </div>
                <div class="metric">
                    <div class="metric-value">
                        ${strategy.sharpe_ratio?.toFixed(2) || '-'}
                    </div>
                    <div class="metric-label">Sharpe</div>
                </div>
                <div class="metric">
                    <div class="metric-value">
                        ${formatPercent(strategy.win_rate, false)}
                    </div>
                    <div class="metric-label">Win Rate</div>
                </div>
            </div>

            <div class="strategy-actions">
                <button class="btn btn-sm btn-primary" data-action="backtest" data-id="${strategy.id}">
                    ▶ Backtest
                </button>
                <button class="btn btn-sm btn-secondary" data-action="edit" data-id="${strategy.id}">
                    ✏️ Edit
                </button>
                <button class="btn btn-sm btn-secondary" data-action="duplicate" data-id="${strategy.id}">
                    📋 Copy
                </button>
                ${strategy.status === 'active'
        ? `<button class="btn btn-sm btn-secondary" data-action="pause" data-id="${strategy.id}">⏸ Pause</button>`
        : `<button class="btn btn-sm btn-secondary" data-action="activate" data-id="${strategy.id}">▶ Activate</button>`}
                <button class="btn btn-sm btn-danger" data-action="delete" data-id="${strategy.id}">
                    🗑
                </button>
            </div>
        </div>
    `).join('');
}

// Modal functions
function openCreateModal() {
    editingStrategyId = null;
    document.getElementById('modalTitle').textContent = 'Создание стратегии';
    document.getElementById('strategyForm').reset();
    document.getElementById('strategyId').value = '';
    updateLeverageDisplay(1); // Reset leverage slider
    // Calculate leverage limits based on default values (async, don't await)
    updateLeverageLimits().catch(err => console.warn('Leverage limits init error:', err));
    updateParametersUI();
    document.getElementById('strategyModal').classList.add('active');
}

function closeModal() {
    document.getElementById('strategyModal').classList.remove('active');
}

async function editStrategy(id) {
    try {
        const response = await fetch(`${API_BASE}/strategies/${id}`);
        const strategy = await response.json();

        editingStrategyId = id;
        document.getElementById('modalTitle').textContent = 'Редактирование стратегии';
        document.getElementById('strategyId').value = id;
        document.getElementById('strategyName').value = strategy.name;
        document.getElementById('strategyType').value = strategy.strategy_type;
        document.getElementById('strategyStatus').value = strategy.status;
        document.getElementById('strategySymbol').value = strategy.symbol || 'BTCUSDT';
        document.getElementById('strategyTimeframe').value = strategy.timeframe || '1h';
        document.getElementById('strategyCapital').value = strategy.initial_capital || 10000;
        document.getElementById('strategyStopLoss').value = strategy.stop_loss_pct || '';
        document.getElementById('strategyTakeProfit').value = strategy.take_profit_pct || '';

        // Read trading settings from parameters (where they are stored)
        const params = strategy.parameters || {};
        const positionSizeType = params._position_size_type || 'percent';
        document.getElementById('strategyDirection').value = params._direction || 'both';
        document.getElementById('strategyPositionSizeType').value = positionSizeType;

        // Set position size value based on type
        if (positionSizeType === 'percent') {
            document.getElementById('strategyPositionSize').value = (strategy.position_size || 1) * 100;
        } else {
            // For fixed_amount or contracts, use stored _order_amount
            document.getElementById('strategyPositionSize').value = params._order_amount || 100;
        }

        // Update position size input label/limits
        updatePositionSizeInput();

        // Update leverage limits first, then set value
        await updateLeverageLimits();

        // Advanced parameters from stored settings
        const leverageVal = params._leverage || 1;
        document.getElementById('strategyLeverage').value = leverageVal;
        updateLeverageDisplay(leverageVal);
        document.getElementById('strategyPyramiding').value = params._pyramiding || 1;
        document.getElementById('strategyCommission').value = (params._commission || 0.001) * 100;
        document.getElementById('strategySlippage').value = (params._slippage || 0.0005) * 100;

        // Update strategy-specific parameters (RSI period, etc.) - filter out _prefixed
        const strategyParams = {};
        for (const [key, value] of Object.entries(params)) {
            if (!key.startsWith('_')) {
                strategyParams[key] = value;
            }
        }
        updateParametersUI(strategyParams);

        document.getElementById('strategyModal').classList.add('active');
    } catch (error) {
        showToast('Ошибка загрузки стратегии: ' + error.message, 'error');
    }
}

async function saveStrategy() {
    const id = document.getElementById('strategyId').value;

    // Get strategy-specific parameters (RSI period, overbought, etc.)
    const strategyParams = getParametersFromUI();

    // Get position size type and value
    const positionSizeType = document.getElementById('strategyPositionSizeType').value;
    const positionSizeValue = parseFloat(document.getElementById('strategyPositionSize').value);

    // Calculate position_size for DB (always as fraction 0-1)
    // and store actual order amount in parameters
    let positionSizeForDB = 1.0;  // Default 100%
    let orderAmount = null;

    if (positionSizeType === 'percent') {
        positionSizeForDB = positionSizeValue / 100;  // Convert % to fraction
    } else if (positionSizeType === 'fixed_amount') {
        orderAmount = positionSizeValue;  // Store fixed $ amount
        positionSizeForDB = 1.0;  // Will be calculated in backend based on orderAmount
    } else if (positionSizeType === 'contracts') {
        orderAmount = positionSizeValue;  // Store contracts count
        positionSizeForDB = 1.0;
    }

    // Add trading settings to parameters for storage
    const allParameters = {
        ...strategyParams,
        // Trading settings stored in parameters since DB doesn't have separate columns
        _direction: document.getElementById('strategyDirection').value,
        _leverage: parseInt(document.getElementById('strategyLeverage').value) || 1,
        _pyramiding: parseInt(document.getElementById('strategyPyramiding').value) || 1,
        _commission: parseFloat(document.getElementById('strategyCommission').value) / 100 || 0.001,
        _slippage: parseFloat(document.getElementById('strategySlippage').value) / 100 || 0.0005,
        _position_size_type: positionSizeType,
        _order_amount: orderAmount  // Fixed amount in $ or contracts
    };

    const data = {
        name: document.getElementById('strategyName').value,
        strategy_type: document.getElementById('strategyType').value,
        status: document.getElementById('strategyStatus').value,
        symbol: document.getElementById('strategySymbol').value,
        timeframe: document.getElementById('strategyTimeframe').value,
        initial_capital: parseFloat(document.getElementById('strategyCapital').value),
        position_size: positionSizeForDB,
        stop_loss_pct: parseFloat(document.getElementById('strategyStopLoss').value) || null,
        take_profit_pct: parseFloat(document.getElementById('strategyTakeProfit').value) || null,
        parameters: allParameters
    };

    try {
        const url = id ? `${API_BASE}/strategies/${id}` : `${API_BASE}/strategies/`;
        const method = id ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка сохранения стратегии');
        }

        closeModal();
        loadStrategies();
        showToast(id ? 'Стратегия обновлена!' : 'Стратегия создана!', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function deleteStrategy(id) {
    if (!confirm('Вы уверены, что хотите удалить эту стратегию?')) return;

    try {
        // Use permanent=true to actually delete from database
        const response = await fetch(`${API_BASE}/strategies/${id}?permanent=true`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Ошибка удаления');

        loadStrategies();
        showToast('Стратегия удалена', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function duplicateStrategy(id) {
    try {
        const response = await fetch(`${API_BASE}/strategies/${id}/duplicate`, { method: 'POST' });
        if (!response.ok) throw new Error('Ошибка дублирования');

        loadStrategies();
        showToast('Стратегия скопирована!', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function activateStrategy(id) {
    try {
        const response = await fetch(`${API_BASE}/strategies/${id}/activate`, { method: 'POST' });
        if (!response.ok) throw new Error('Ошибка активации');

        loadStrategies();
        showToast('Стратегия активирована!', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function pauseStrategy(id) {
    try {
        const response = await fetch(`${API_BASE}/strategies/${id}/pause`, { method: 'POST' });
        if (!response.ok) throw new Error('Ошибка паузы');

        loadStrategies();
        showToast('Стратегия приостановлена', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Backtest Modal
async function openBacktestModal(strategyId) {
    document.getElementById('backtestStrategyId').value = strategyId;
    // Reset progress UI when opening modal
    resetBacktestProgress();
    // Hide previous results
    document.getElementById('backtestResults').classList.add('hidden');
    // Set default dates (last month)
    setBacktestPeriod('1m');

    // Load and display strategy info
    await loadBacktestStrategyInfo(strategyId);

    document.getElementById('backtestModal').classList.add('active');
}

/**
 * Load strategy info and display in backtest modal
 */
async function loadBacktestStrategyInfo(strategyId) {
    const infoContainer = document.getElementById('backtestStrategyInfo');
    if (!infoContainer) return;

    try {
        const response = await fetch(`${API_BASE}/strategies/${strategyId}`);
        if (!response.ok) throw new Error('Failed to load strategy');

        const strategy = await response.json();
        console.log('[loadBacktestStrategyInfo] Strategy loaded:', strategy);
        console.log('[loadBacktestStrategyInfo] initial_capital:', strategy.initial_capital);

        // Format strategy type display name
        const typeNames = {
            'rsi': 'RSI',
            'macd': 'MACD',
            'bollinger': 'Bollinger Bands',
            'sma_cross': 'SMA Cross',
            'ema_cross': 'EMA Cross',
            'custom': 'Custom'
        };
        const typeName = typeNames[strategy.strategy_type] || strategy.strategy_type;

        // Format parameters - filter out internal _prefixed ones
        const params = strategy.parameters || {};
        const displayParams = Object.entries(params)
            .filter(([key]) => !key.startsWith('_'))
            .map(([key, val]) => `<span class="param-tag">${key}: ${val}</span>`)
            .join(' ');

        // Get trading settings from parameters
        const leverage = params._leverage || 1;
        const direction = params._direction || 'both';
        const directionNames = { 'long': 'Long', 'short': 'Short', 'both': 'Long/Short' };

        // Calculate position size based on type
        const positionSizeType = params._position_size_type || 'percent';
        const orderAmount = params._order_amount || 0;
        const initialCapital = strategy.initial_capital || 10000;

        let positionSizeDisplay;
        if (positionSizeType === 'fixed_amount' && orderAmount > 0) {
            const effectiveSize = orderAmount * leverage;
            positionSizeDisplay = `$${orderAmount.toLocaleString()} × ${leverage}x = <strong>$${effectiveSize.toLocaleString()}</strong>`;
        } else {
            const positionPct = (strategy.position_size || 1) * 100;
            const effectiveSize = initialCapital * (strategy.position_size || 1) * leverage;
            positionSizeDisplay = `${positionPct}% × ${leverage}x = <strong>$${effectiveSize.toLocaleString()}</strong>`;
        }

        infoContainer.innerHTML = `
            <div class="strategy-info-card">
                <div class="strategy-info-header">
                    <span class="strategy-name">${escapeHtml(strategy.name)}</span>
                    <span class="strategy-type-badge">${escapeHtml(typeName)}</span>
                </div>
                <div class="strategy-info-details">
                    <div class="info-row">
                        <span class="info-label">Символ:</span>
                        <span class="info-value">${escapeHtml(strategy.symbol)}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Таймфрейм:</span>
                        <span class="info-value">${escapeHtml(strategy.timeframe)}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Капитал:</span>
                        <span class="info-value">$${initialCapital.toLocaleString()}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Размер позиции:</span>
                        <span class="info-value">${positionSizeDisplay}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Направление:</span>
                        <span class="info-value">${directionNames[direction]}</span>
                    </div>
                    <div class="info-row full-width">
                        <span class="info-label">Параметры стратегии:</span>
                        <span class="info-value params">${displayParams || 'По умолчанию'}</span>
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading strategy info:', error);
        infoContainer.innerHTML = '<div class="error-text">Не удалось загрузить информацию о стратегии</div>';
    }
}

function closeBacktestModal() {
    document.getElementById('backtestModal').classList.remove('active');
    resetBacktestProgress();
}

/**
 * Set backtest period from quick buttons
 * @param {string} period - '1d', '1w', '1m', '3m'
 */
function setBacktestPeriod(period) {
    const endDate = new Date();
    const startDate = new Date();

    switch (period) {
    case '1d':
        startDate.setDate(startDate.getDate() - 1);
        break;
    case '1w':
        startDate.setDate(startDate.getDate() - 7);
        break;
    case '1m':
        startDate.setMonth(startDate.getMonth() - 1);
        break;
    case '3m':
        startDate.setMonth(startDate.getMonth() - 3);
        break;
    default:
        startDate.setMonth(startDate.getMonth() - 1);
    }

    // Format dates as YYYY-MM-DD for input[type="date"]
    document.getElementById('backtestStartDate').value = startDate.toISOString().split('T')[0];
    document.getElementById('backtestEndDate').value = endDate.toISOString().split('T')[0];

    // Update active button state
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.period === period) {
            btn.classList.add('active');
        }
    });
}

// Initialize period buttons
function initPeriodButtons() {
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            setBacktestPeriod(btn.dataset.period);
        });
    });
}

/**
 * Reset backtest progress UI to initial state
 */
function resetBacktestProgress() {
    const progressEl = document.getElementById('backtestProgress');
    const progressBar = document.getElementById('backtestProgressBar');
    const statusText = document.getElementById('backtestStatusText');
    const percentText = document.getElementById('backtestPercentText');
    const detailsText = document.getElementById('backtestProgressDetails');
    const btnText = document.getElementById('btnRunBacktestText');
    const btnSpinner = document.getElementById('btnRunBacktestSpinner');
    const btnRun = document.getElementById('btnRunBacktest');

    progressEl.classList.add('hidden');
    progressBar.style.width = '0%';
    progressBar.classList.remove('indeterminate');
    statusText.textContent = 'Инициализация...';
    percentText.textContent = '0%';
    detailsText.textContent = 'Подготовка исторических данных...';
    btnText.textContent = 'Запустить';
    btnSpinner.classList.add('hidden');
    btnRun.disabled = false;
}

/**
 * Update backtest progress UI
 * @param {string} status - Status text
 * @param {number} percent - Progress percentage (0-100)
 * @param {string} details - Detailed progress message
 */
function updateBacktestProgress(status, percent, details) {
    const progressEl = document.getElementById('backtestProgress');
    const progressBar = document.getElementById('backtestProgressBar');
    const statusText = document.getElementById('backtestStatusText');
    const percentText = document.getElementById('backtestPercentText');
    const detailsText = document.getElementById('backtestProgressDetails');

    progressEl.classList.remove('hidden');

    if (percent === -1) {
        // Indeterminate progress
        progressBar.classList.add('indeterminate');
        percentText.textContent = '...';
    } else {
        progressBar.classList.remove('indeterminate');
        progressBar.style.width = `${percent}%`;
        percentText.textContent = `${Math.round(percent)}%`;
    }

    statusText.textContent = status;
    detailsText.textContent = details;
}

async function runBacktest() {
    const strategyId = document.getElementById('backtestStrategyId').value;
    const startDateStr = document.getElementById('backtestStartDate').value;
    const endDateStr = document.getElementById('backtestEndDate').value;

    // ========== DATE VALIDATION ==========
    if (!startDateStr || !endDateStr) {
        showToast('Выберите даты начала и окончания', 'error');
        return;
    }

    const startDate = new Date(startDateStr);
    const endDate = new Date(endDateStr);
    const now = new Date();

    // Check: start < end
    if (startDate >= endDate) {
        showToast('Дата начала должна быть раньше даты окончания', 'error');
        return;
    }

    // Check: end date not in future
    if (endDate > now) {
        showToast('Дата окончания не может быть в будущем', 'error');
        return;
    }

    // Check: max 5 years period
    const daysDiff = (endDate - startDate) / (1000 * 60 * 60 * 24);
    if (daysDiff > 365 * 5) {
        showToast('Период бэктеста не может превышать 5 лет', 'error');
        return;
    }

    // Check: min 1 day period
    if (daysDiff < 1) {
        showToast('Период бэктеста должен быть минимум 1 день', 'error');
        return;
    }

    const data = {
        start_date: startDateStr + 'T00:00:00Z',
        end_date: endDateStr + 'T23:59:59Z',
        save_result: document.getElementById('backtestSaveResult').checked
    };

    // Symbol and capital now come from strategy settings, no override needed

    // Get UI elements
    const btnRun = document.getElementById('btnRunBacktest');
    const btnText = document.getElementById('btnRunBacktestText');
    const btnSpinner = document.getElementById('btnRunBacktestSpinner');
    const resultsSection = document.getElementById('backtestResults');

    try {
        // Hide previous results
        resultsSection.classList.add('hidden');

        // Show progress UI
        btnRun.disabled = true;
        btnText.textContent = 'Выполняется...';
        btnSpinner.classList.remove('hidden');

        // Phase 1: Initializing
        updateBacktestProgress('Инициализация...', 5, 'Подключение к серверу...');
        await sleep(200);

        // Phase 2: Fetching data
        updateBacktestProgress('Загрузка данных', 15, 'Скачивание исторических свечей с Bybit...');
        await sleep(300);

        // Phase 3: Running - use indeterminate progress during actual API call
        updateBacktestProgress('Выполнение бэктеста', -1, 'Анализ эффективности стратегии...');

        const response = await fetch(`${API_BASE}/backtests/from-strategy/${strategyId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.status === 'failed') {
            throw new Error(result.error_message || 'Ошибка бэктеста');
        }

        // Phase 4: Complete
        updateBacktestProgress('Готово!', 100, 'Бэктест успешно завершён');
        await sleep(300);

        // Display results in modal
        displayBacktestResults(result, startDate, endDate);

        // Reset button state
        btnRun.disabled = false;
        btnText.textContent = 'Запустить ещё';
        btnSpinner.classList.add('hidden');

        // Refresh strategies list in background
        loadStrategies();

        const metrics = result.metrics;
        showToast(
            `Бэктест завершён! Доходность: ${formatPercent(metrics?.total_return)}, ` +
            `Sharpe: ${metrics?.sharpe_ratio?.toFixed(2) || 'N/A'}`,
            'success'
        );
    } catch (error) {
        // Error state
        updateBacktestProgress('Ошибка', 0, error.message);
        showToast('Ошибка бэктеста: ' + error.message, 'error');

        // Reset button but keep progress visible
        btnRun.disabled = false;
        btnText.textContent = 'Повторить';
        btnSpinner.classList.add('hidden');
    }
}

/**
 * Display backtest results in the modal
 */
function displayBacktestResults(result, startDate, endDate) {
    const resultsSection = document.getElementById('backtestResults');
    const metrics = result.metrics || {};

    // Total return
    const returnEl = document.getElementById('resultReturn');
    const totalReturn = metrics.total_return;
    returnEl.textContent = formatPercent(totalReturn);
    returnEl.className = 'result-value ' + (totalReturn >= 0 ? 'positive' : 'negative');

    // Sharpe ratio
    const sharpeEl = document.getElementById('resultSharpe');
    sharpeEl.textContent = metrics.sharpe_ratio?.toFixed(2) || '-';
    sharpeEl.className = 'result-value ' + (metrics.sharpe_ratio >= 1 ? 'positive' : '');

    // Win rate
    const winRateEl = document.getElementById('resultWinRate');
    const winRate = metrics.win_rate;
    winRateEl.textContent = winRate != null ? winRate.toFixed(1) + '%' : '-';
    winRateEl.className = 'result-value ' + (winRate >= 50 ? 'positive' : 'negative');

    // Max drawdown
    const drawdownEl = document.getElementById('resultDrawdown');
    const maxDD = metrics.max_drawdown;
    drawdownEl.textContent = maxDD != null ? (-Math.abs(maxDD)).toFixed(2) + '%' : '-';
    drawdownEl.className = 'result-value negative';

    // Total trades
    const tradesEl = document.getElementById('resultTrades');
    tradesEl.textContent = metrics.total_trades || '0';

    // Profit factor
    const pfEl = document.getElementById('resultProfitFactor');
    const pf = metrics.profit_factor;
    pfEl.textContent = pf != null ? pf.toFixed(2) : '-';
    pfEl.className = 'result-value ' + (pf >= 1.5 ? 'positive' : (pf < 1 ? 'negative' : ''));

    // Period info
    document.getElementById('resultPeriod').textContent =
        `Период: ${startDate} — ${endDate}`;

    // Show results section
    resultsSection.classList.remove('hidden');
}

/**
 * Helper sleep function for progress animations
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Parameters UI
function updateParametersUI(existingParams = {}) {
    const type = document.getElementById('strategyType').value;
    const typeInfo = strategyTypes.find(t => t.strategy_type === type);
    const defaultParams = typeInfo?.parameters || {};
    const container = document.getElementById('parametersContainer');

    container.innerHTML = Object.entries(defaultParams).map(([key, value]) => `
        <div class="form-row" style="margin-bottom: 10px;">
            <div class="form-group" style="margin-bottom: 0;">
                <label>${key.replace(/_/g, ' ')}</label>
                <input type="number" 
                       class="param-input" 
                       data-param="${key}" 
                       value="${existingParams[key] ?? value}"
                       step="any">
            </div>
        </div>
    `).join('');
}

function getParametersFromUI() {
    const params = {};
    document.querySelectorAll('.param-input').forEach(input => {
        const value = parseFloat(input.value);
        if (!isNaN(value)) {
            params[input.dataset.param] = value;
        }
    });
    return params;
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatPercent(value, isRatio = false) {
    if (value === null || value === undefined) return '-';
    const pct = isRatio ? value * 100 : value;
    const sign = pct >= 0 ? '+' : '';
    return `${sign}${pct.toFixed(2)}%`;
}

function getReturnClass(value) {
    if (value === null || value === undefined) return '';
    return value >= 0 ? 'positive' : 'negative';
}

/**
 * Update position size input based on selected type
 */
function updatePositionSizeInput() {
    const typeSelect = document.getElementById('strategyPositionSizeType');
    const sizeInput = document.getElementById('strategyPositionSize');
    const sizeLabel = document.getElementById('positionSizeLabel');

    if (!typeSelect || !sizeInput || !sizeLabel) return;

    const type = typeSelect.value;

    switch (type) {
    case 'percent':
        sizeLabel.textContent = 'Размер позиции (%)';
        sizeInput.min = 1;
        sizeInput.max = 100;
        sizeInput.step = 1;
        sizeInput.placeholder = '100';
        break;
    case 'fixed_amount':
        sizeLabel.textContent = 'Сумма на ордер ($)';
        sizeInput.min = 1;
        sizeInput.max = 1000000;
        sizeInput.step = 1;
        sizeInput.placeholder = '100';
        break;
    case 'contracts':
        sizeLabel.textContent = 'Количество контрактов';
        sizeInput.min = 0.001;
        sizeInput.max = 10000;
        sizeInput.step = 0.001;
        sizeInput.placeholder = '1';
        break;
    }
}

// Make function globally available for HTML onchange
window.updatePositionSizeInput = updatePositionSizeInput;

// debounce - using imported version from utils.js

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => toast.remove(), 5000);
}

// ============================================
// EXPORTS (for testing and external access)
// ============================================

if (typeof window !== 'undefined') {
    window.strategiesPage = {
        loadStrategies,
        loadStrategyTypes,
        openCreateModal,
        closeModal,
        renderStrategies
    };
}
