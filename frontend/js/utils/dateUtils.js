/**
 * dateUtils.js — Centralized date/time helpers for the frontend.
 *
 * ROOT CAUSE OF DESYNC:
 *   `new Date().toISOString()` always returns UTC time.
 *   For users in UTC+N timezones (e.g. UTC+3 Moscow), between 00:00 and N:00
 *   local time, this returns yesterday's date — causing off-by-one errors in
 *   backtest date ranges, filters, and UI defaults.
 *
 * RULE: Never use `.toISOString().slice(0, 10)` for date INPUT fields or
 *       API date parameters. Always use `localDateStr()` instead.
 *
 * EXCEPTIONS (UTC is correct):
 *   - `Date.now()` for timestamps, latency, cache-busting, unique IDs — OK
 *   - `new Date(ts).toISOString()` for logging/debug output — OK
 *   - `new Date().toLocaleTimeString()` for display only — OK
 */

/**
 * Returns today's LOCAL date as "YYYY-MM-DD".
 * Safe for use as default value in date input fields and API parameters.
 *
 * @param {Date} [date] - Optional date object. Defaults to now.
 * @returns {string} e.g. "2026-02-28"
 */
export function localDateStr(date) {
    const d = date || new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

/**
 * Returns a local datetime as "YYYY-MM-DDTHH:MM:SS" (no UTC offset).
 * Use when you need a full ISO-like string but in local time.
 *
 * @param {Date} [date] - Optional date object. Defaults to now.
 * @returns {string} e.g. "2026-02-28T22:54:36"
 */
export function localISOString(date) {
    const d = date || new Date();
    return `${localDateStr(d)}T${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
}

/**
 * Returns a Date object N months ago from today (local time).
 *
 * @param {number} months
 * @returns {Date}
 */
export function monthsAgo(months) {
    const d = new Date();
    d.setMonth(d.getMonth() - months);
    return d;
}

/**
 * Returns a Date object N days ago from today (local time).
 *
 * @param {number} days
 * @returns {Date}
 */
export function daysAgo(days) {
    const d = new Date();
    d.setDate(d.getDate() - days);
    return d;
}
