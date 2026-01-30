/**
 * 🚀 Production Initialization - Bybit Strategy Tester v2
 *
 * Configures frontend for production mode:
 * - Disables debug logging
 * - Enables security features
 * - Patches console methods
 *
 * Include this script BEFORE other scripts in production HTML.
 *
 * @version 1.0.0
 * @date 2026-01-28
 */

(function () {
  "use strict";

  // ============================================
  // ENVIRONMENT DETECTION
  // ============================================

  const isProduction =
    window.location.hostname !== "localhost" &&
    window.location.hostname !== "127.0.0.1" &&
    !window.location.hostname.includes(".local");

  const isDevelopment = !isProduction;

  // Export for use in other scripts
  window.__ENV__ = {
    production: isProduction,
    development: isDevelopment,
    debug: isDevelopment,
  };

  // ============================================
  // CONSOLE CONFIGURATION
  // ============================================

  if (isProduction) {
    // Store original console methods
    const originalConsole = {
      log: console.log,
      debug: console.debug,
      info: console.info,
      warn: console.warn,
      error: console.error,
    };

    // Replace with filtered versions
    console.log = function () {
      // Suppress in production
    };

    console.debug = function () {
      // Suppress in production
    };

    console.info = function () {
      // Suppress in production
    };

    // Keep warn and error for important messages
    console.warn = function (...args) {
      // Only show if first arg is marked as important
      if (
        args[0] &&
        typeof args[0] === "string" &&
        args[0].startsWith("[IMPORTANT]")
      ) {
        originalConsole.warn.apply(console, args);
      }
    };

    console.error = function (...args) {
      // Always show errors
      originalConsole.error.apply(console, args);
    };

    // Provide escape hatch for debugging in production
    window.__debug__ = {
      restore: function () {
        console.log = originalConsole.log;
        console.debug = originalConsole.debug;
        console.info = originalConsole.info;
        console.warn = originalConsole.warn;
        console.error = originalConsole.error;
        console.log("[DEBUG] Console restored for debugging");
      },
      log: originalConsole.log,
    };
  }

  // ============================================
  // GLOBAL ERROR HANDLING
  // ============================================

  window.onerror = function (message, source, lineno, colno, error) {
    // Log errors for debugging
    if (isProduction) {
      // In production, send to error tracking service
      // TODO: Integrate with Sentry/LogRocket
      console.error("[ERROR]", {
        message: message,
        source: source,
        line: lineno,
        column: colno,
        stack: error ? error.stack : null,
      });
    }

    // Return false to let default error handling continue
    return false;
  };

  window.onunhandledrejection = function (event) {
    console.error("[UNHANDLED PROMISE]", event.reason);
  };

  // ============================================
  // SECURITY HARDENING
  // ============================================

  if (isProduction) {
    // Disable right-click context menu (optional)
    // document.addEventListener('contextmenu', e => e.preventDefault());
    // Warn about DevTools (optional, can be annoying)
    // let devtools = false;
    // const threshold = 160;
    // setInterval(() => {
    //     if (window.outerHeight - window.innerHeight > threshold ||
    //         window.outerWidth - window.innerWidth > threshold) {
    //         if (!devtools) {
    //             devtools = true;
    //             console.warn('[IMPORTANT] Developer tools detected');
    //         }
    //     } else {
    //         devtools = false;
    //     }
    // }, 1000);
  }

  // ============================================
  // PERFORMANCE HINTS
  // ============================================

  // Request idle callback polyfill
  window.requestIdleCallback =
    window.requestIdleCallback ||
    function (cb) {
      const start = Date.now();
      return setTimeout(function () {
        cb({
          didTimeout: false,
          timeRemaining: function () {
            return Math.max(0, 50 - (Date.now() - start));
          },
        });
      }, 1);
    };

  window.cancelIdleCallback =
    window.cancelIdleCallback ||
    function (id) {
      clearTimeout(id);
    };

  // ============================================
  // INITIALIZATION COMPLETE
  // ============================================

  if (isDevelopment) {
    console.log("[INIT] Development mode enabled");
    console.log("[INIT] Console logging: ENABLED");
  }
})();
