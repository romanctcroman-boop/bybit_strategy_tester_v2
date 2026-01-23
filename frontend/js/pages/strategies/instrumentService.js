/**
 * 📄 Strategies Page - Instrument Service
 *
 * Handles fetching instrument info, prices, and volatility data
 * with caching to minimize API calls
 *
 * @version 1.0.0
 * @date 2025-12-23
 */

const API_BASE = '/api/v1';

// Cache for instrument info (5 min TTL)
const instrumentInfoCache = {};
const INSTRUMENT_CACHE_TTL = 300000; // 5 minutes

// Cache for current prices (10 sec TTL)
const priceCache = {};
const PRICE_CACHE_TTL = 10000; // 10 seconds

// Cache for volatility data (1 min TTL)
const volatilityCache = {};
const VOLATILITY_CACHE_TTL = 60000; // 1 minute

/**
 * Normalize symbol to XXXUSDT format
 * @param {string} symbol - Raw symbol
 * @returns {string} Normalized symbol
 */
function normalizeSymbol(symbol) {
    if (!symbol) return '';
    return symbol.toUpperCase().replace('USDT', '') + 'USDT';
}

/**
 * Fetch instrument info for a symbol (leverage limits, min order size, etc.)
 * @param {string} symbol - Trading symbol
 * @returns {Promise<Object|null>} Instrument info or null
 */
export async function fetchInstrumentInfo(symbol) {
    if (!symbol) return null;

    const sym = normalizeSymbol(symbol);

    // Check cache first
    const cached = instrumentInfoCache[sym];
    if (cached && cached.timestamp && Date.now() - cached.timestamp < INSTRUMENT_CACHE_TTL) {
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
 * @param {string} symbol - Trading symbol
 * @returns {Promise<number|null>} Current price or null
 */
export async function fetchCurrentPrice(symbol) {
    if (!symbol) return null;

    const sym = normalizeSymbol(symbol);

    // Check cache
    const cached = priceCache[sym];
    if (cached && cached.timestamp && Date.now() - cached.timestamp < PRICE_CACHE_TTL) {
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
 * Fetch volatility data for a symbol (90-day analysis)
 * @param {string} symbol - Trading symbol
 * @returns {Promise<Object|null>} Volatility data or null
 */
export async function fetchVolatility(symbol) {
    if (!symbol) return null;

    // Check cache
    const cached = volatilityCache[symbol];
    if (cached && (Date.now() - cached.timestamp < VOLATILITY_CACHE_TTL)) {
        return cached.data;
    }

    try {
        const response = await fetch(`${API_BASE}/marketdata/bybit/volatility?symbol=${symbol}&days=90`);
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
 * Clear all caches (useful for force refresh)
 */
export function clearCaches() {
    Object.keys(instrumentInfoCache).forEach(key => delete instrumentInfoCache[key]);
    Object.keys(priceCache).forEach(key => delete priceCache[key]);
    Object.keys(volatilityCache).forEach(key => delete volatilityCache[key]);
}

/**
 * Get cached instrument info without fetching
 * @param {string} symbol - Trading symbol
 * @returns {Object|null} Cached data or null
 */
export function getCachedInstrumentInfo(symbol) {
    const sym = normalizeSymbol(symbol);
    const cached = instrumentInfoCache[sym];
    if (cached && cached.timestamp && Date.now() - cached.timestamp < INSTRUMENT_CACHE_TTL) {
        return cached.data;
    }
    return null;
}
