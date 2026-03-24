/**
 * utils.js Unit Tests
 *
 * Covers all functions changed during the B-14 bug-fix session:
 *   - isValidSymbol  (B-14: tightened regex)
 *   - formatNumber
 *   - formatCurrency
 *   - formatPercent
 *   - validateNumber
 *   - debounce
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// ─── helpers ──────────────────────────────────────────────────────────────────
// utils.js is not a pure-ESM module — it uses window/document globals and
// attaches to window.Utils.  We import it with a dynamic import inside each
// describe block so happy-dom is fully initialised first.

let isValidSymbol, validateNumber, formatNumber, formatCurrency, formatPercent, debounce;

beforeEach(async () => {
    // Re-import for each test file load — vitest resets modules between suites
    // when using happy-dom, so a static import at top level is fine too, but
    // the dynamic approach avoids top-level await syntax.
    const mod = await import('../../js/utils.js');
    // utils.js exports via named exports (export { ... } at the bottom)
    isValidSymbol = mod.isValidSymbol;
    validateNumber = mod.validateNumber;
    formatNumber = mod.formatNumber;
    formatCurrency = mod.formatCurrency;
    formatPercent = mod.formatPercent;
    debounce = mod.debounce;
});

// ─── isValidSymbol ─────────────────────────────────────────────────────────────
describe('isValidSymbol (B-14)', () => {
    // ── valid symbols ──────────────────────────────────────────────────────────
    it('accepts common USDT pairs', () => {
        expect(isValidSymbol('BTCUSDT')).toBe(true);
        expect(isValidSymbol('ETHUSDT')).toBe(true);
        expect(isValidSymbol('SOLUSDT')).toBe(true);
        expect(isValidSymbol('BNBUSDT')).toBe(true);
        expect(isValidSymbol('XRPUSDT')).toBe(true);
    });

    it('accepts USDC pairs', () => {
        expect(isValidSymbol('BTCUSDC')).toBe(true);
        expect(isValidSymbol('ETHUSDC')).toBe(true);
        expect(isValidSymbol('SOLUSDC')).toBe(true);
    });

    it('accepts numeric-prefix symbols (meme coins)', () => {
        // Bybit lists: 10000PEPUSDT, 1000BONKUSDT
        expect(isValidSymbol('10000PEPUSDT')).toBe(true);
        expect(isValidSymbol('1000BONKUSDT')).toBe(true);
    });

    it('accepts exactly 3-char base pairs', () => {
        expect(isValidSymbol('ADAUSDT')).toBe(true); // 3 base chars
    });

    // ── invalid symbols ────────────────────────────────────────────────────────
    it('rejects lowercase symbols', () => {
        expect(isValidSymbol('btcusdt')).toBe(false);
        expect(isValidSymbol('BtcUSDT')).toBe(false);
    });

    it('rejects USDT without trailing T/C (old regex accepted this)', () => {
        expect(isValidSymbol('BTCUSD')).toBe(false);
    });

    it('rejects empty string', () => {
        expect(isValidSymbol('')).toBe(false);
    });

    it('rejects null / undefined gracefully', () => {
        // regex.test(null) coerces to 'null' — symbol must be a string
        expect(isValidSymbol(null)).toBe(false);
        expect(isValidSymbol(undefined)).toBe(false);
    });

    it('rejects symbols with special characters', () => {
        expect(isValidSymbol('BTC-USDT')).toBe(false);
        expect(isValidSymbol('BTC/USDT')).toBe(false);
        expect(isValidSymbol('BTC USDT')).toBe(false);
    });

    it('rejects symbols that are too long', () => {
        // 13 base chars + USDT = 17 total — over the 12+4=16 ceiling
        expect(isValidSymbol('ABCDEFGHIJKLMNUSDT')).toBe(false);
    });

    it('rejects unsupported quote currencies', () => {
        expect(isValidSymbol('BTCBUSD')).toBe(false);
        expect(isValidSymbol('BTCEUR')).toBe(false);
    });
});

// ─── formatNumber ──────────────────────────────────────────────────────────────
describe('formatNumber', () => {
    it('formats integers with 2 decimal places', () => {
        expect(formatNumber(1000)).toBe('1,000.00');
    });

    it('formats with custom decimal count', () => {
        expect(formatNumber(3.14159, 4)).toBe('3.1416');
    });

    it('returns em-dash for null/undefined/NaN', () => {
        expect(formatNumber(null)).toBe('—');
        expect(formatNumber(undefined)).toBe('—');
        expect(formatNumber(NaN)).toBe('—');
    });
});

// ─── formatCurrency ────────────────────────────────────────────────────────────
describe('formatCurrency', () => {
    it('uses $ symbol for USD and USDT', () => {
        expect(formatCurrency(1000, 'USD')).toContain('$');
        expect(formatCurrency(1000, 'USDT')).toContain('$');
    });

    it('compacts millions', () => {
        expect(formatCurrency(2500000)).toContain('M');
    });

    it('compacts thousands', () => {
        expect(formatCurrency(5000)).toContain('K');
    });

    it('returns em-dash for null/undefined/NaN', () => {
        expect(formatCurrency(null)).toBe('—');
        expect(formatCurrency(NaN)).toBe('—');
    });
});

// ─── formatPercent ─────────────────────────────────────────────────────────────
describe('formatPercent', () => {
    it('converts fractional value to percent string', () => {
        expect(formatPercent(0.05)).toBe('+5.00%');
        expect(formatPercent(-0.03)).toBe('-3.00%');
    });

    it('omits + sign when includeSign=false', () => {
        expect(formatPercent(0.1, false)).toBe('10.00%');
    });

    it('returns em-dash for nullish values', () => {
        expect(formatPercent(null)).toBe('—');
        expect(formatPercent(undefined)).toBe('—');
    });
});

// ─── validateNumber ────────────────────────────────────────────────────────────
describe('validateNumber', () => {
    it('returns valid for a number within range', () => {
        const r = validateNumber(50, { min: 0, max: 100 });
        expect(r.valid).toBe(true);
        expect(r.error).toBeNull();
    });

    it('returns invalid when below min', () => {
        const r = validateNumber(-1, { min: 0 });
        expect(r.valid).toBe(false);
        expect(r.error).toBeTruthy();
    });

    it('returns invalid when above max', () => {
        const r = validateNumber(101, { max: 100 });
        expect(r.valid).toBe(false);
    });

    it('returns invalid for empty string when required=true', () => {
        const r = validateNumber('', { required: true });
        expect(r.valid).toBe(false);
    });

    it('returns valid for empty string when required=false', () => {
        const r = validateNumber('', { required: false });
        expect(r.valid).toBe(true);
    });

    it('returns invalid for non-numeric string', () => {
        const r = validateNumber('abc');
        expect(r.valid).toBe(false);
    });
});

// ─── debounce ──────────────────────────────────────────────────────────────────
describe('debounce', () => {
    it('delays function invocation', async () => {
        vi.useFakeTimers();
        const fn = vi.fn();
        const debounced = debounce(fn, 100);

        debounced();
        debounced();
        debounced();

        expect(fn).not.toHaveBeenCalled();
        vi.advanceTimersByTime(100);
        expect(fn).toHaveBeenCalledTimes(1);

        vi.useRealTimers();
    });

    it('passes the latest arguments', async () => {
        vi.useFakeTimers();
        const fn = vi.fn();
        const debounced = debounce(fn, 50);

        debounced('a');
        debounced('b');
        debounced('c');

        vi.advanceTimersByTime(50);
        expect(fn).toHaveBeenCalledWith('c');

        vi.useRealTimers();
    });
});
