/**
 * 📝 Logger - Bybit Strategy Tester v2
 *
 * Production-safe logging with conditional output.
 * Replaces direct console.log usage.
 *
 * Fixes P1-10: console.log in production
 *
 * @version 1.0.0
 * @date 2026-01-28
 */

// ============================================
// LOG LEVELS
// ============================================

export const LogLevel = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,
  NONE: 4,
};

// ============================================
// LOGGER CLASS
// ============================================

/**
 * Production-safe logger
 *
 * @example
 * const logger = new Logger('MyModule');
 * logger.debug('Detailed info');
 * logger.info('General info');
 * logger.warn('Warning message');
 * logger.error('Error occurred', error);
 */
export class Logger {
  /**
   * @param {string} module - Module name for prefixing
   * @param {Object} options - Configuration
   */
  constructor(module, options = {}) {
    this.module = module;
    this.level = options.level ?? Logger.globalLevel;
    this.enabled = options.enabled ?? Logger.globalEnabled;
    this.styles = {
      debug: "color: #888",
      info: "color: #2196F3",
      warn: "color: #FF9800",
      error: "color: #F44336; font-weight: bold",
    };
  }

  // ============================================
  // STATIC CONFIGURATION
  // ============================================

  static globalLevel = LogLevel.DEBUG;
  static globalEnabled = true;

  /**
   * Configure global logging
   * @param {Object} options
   */
  static configure(options = {}) {
    if (options.level !== undefined) {
      Logger.globalLevel = options.level;
    }
    if (options.enabled !== undefined) {
      Logger.globalEnabled = options.enabled;
    }
  }

  /**
   * Set production mode (minimal logging)
   */
  static setProductionMode() {
    Logger.globalLevel = LogLevel.ERROR;
  }

  /**
   * Set development mode (full logging)
   */
  static setDevelopmentMode() {
    Logger.globalLevel = LogLevel.DEBUG;
  }

  // ============================================
  // LOGGING METHODS
  // ============================================

  /**
   * Debug level log
   * @param {...any} args
   */
  debug(...args) {
    this._log(LogLevel.DEBUG, "debug", ...args);
  }

  /**
   * Info level log
   * @param {...any} args
   */
  info(...args) {
    this._log(LogLevel.INFO, "info", ...args);
  }

  /**
   * Warning level log
   * @param {...any} args
   */
  warn(...args) {
    this._log(LogLevel.WARN, "warn", ...args);
  }

  /**
   * Error level log
   * @param {...any} args
   */
  error(...args) {
    this._log(LogLevel.ERROR, "error", ...args);
  }

  /**
   * Log with timing
   * @param {string} label
   * @returns {Function} End function
   */
  time(label) {
    if (!this._shouldLog(LogLevel.DEBUG)) {
      return () => {};
    }

    const start = performance.now();
    return () => {
      const duration = performance.now() - start;
      this.debug(`${label}: ${duration.toFixed(2)}ms`);
    };
  }

  /**
   * Group logs together
   * @param {string} label
   * @param {Function} fn
   */
  group(label, fn) {
    if (!this._shouldLog(LogLevel.DEBUG)) {
      fn();
      return;
    }

    console.group(`[${this.module}] ${label}`);
    try {
      fn();
    } finally {
      console.groupEnd();
    }
  }

  /**
   * Log table data
   * @param {Array|Object} data
   */
  table(data) {
    if (!this._shouldLog(LogLevel.DEBUG)) return;
    console.table(data);
  }

  // ============================================
  // INTERNAL METHODS
  // ============================================

  /**
   * Check if should log at level
   * @private
   */
  _shouldLog(level) {
    return (
      this.enabled &&
      Logger.globalEnabled &&
      level >= this.level &&
      level >= Logger.globalLevel
    );
  }

  /**
   * Internal log method
   * @private
   */
  _log(level, method, ...args) {
    if (!this._shouldLog(level)) return;

    const prefix = `[${this.module}]`;
    const style = this.styles[method];

    // Check if console method exists
    const consoleFn = console[method] || console.log;

    // Use styled output in browsers
    if (typeof window !== "undefined" && style) {
      consoleFn(`%c${prefix}`, style, ...args);
    } else {
      consoleFn(prefix, ...args);
    }
  }
}

// ============================================
// CONVENIENCE FACTORY
// ============================================

const loggers = new Map();

/**
 * Get or create logger for module
 * @param {string} module - Module name
 * @returns {Logger}
 */
export function getLogger(module) {
  if (!loggers.has(module)) {
    loggers.set(module, new Logger(module));
  }
  return loggers.get(module);
}

/**
 * Create new logger instance
 * @param {string} module - Module name
 * @param {Object} options - Logger options
 * @returns {Logger}
 */
export function createLogger(module, options = {}) {
  return new Logger(module, options);
}

// ============================================
// AUTO-CONFIGURE FOR ENVIRONMENT
// ============================================

// Detect production environment
const isProduction = () => {
  if (typeof window !== "undefined") {
    // Check if URL contains production indicators
    const hostname = window.location?.hostname || "";
    return (
      !hostname.includes("localhost") &&
      !hostname.includes("127.0.0.1") &&
      !hostname.includes(".local")
    );
  }
  return false;
};

// Auto-configure on load
if (isProduction()) {
  Logger.setProductionMode();
}

// ============================================
// EXPORTS
// ============================================

export default Logger;

// Attach to window for non-module scripts
if (typeof window !== "undefined") {
  window.Logger = Logger;
  window.LogLevel = LogLevel;
  window.getLogger = getLogger;
  window.createLogger = createLogger;
}
