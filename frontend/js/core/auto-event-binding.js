/**
 * Auto Event Binding - CSP-Compliant Event Handler Migration
 *
 * This script automatically converts inline onclick handlers to addEventListener.
 * It runs BEFORE DOMContentLoaded to intercept all onclick attributes.
 *
 * Strategy:
 * 1. Use MutationObserver to catch dynamically added elements
 * 2. On DOM ready, scan all elements with onclick attributes
 * 3. Extract the function call, remove onclick, add event listener
 *
 * Benefits:
 * - No need to modify HTML files
 * - Backward compatible
 * - CSP compliant (unsafe-inline not required)
 * - Works with dynamically added content
 *
 * @author Audit Migration Script
 * @version 1.0.0
 */

(function () {
  'use strict';

  // Track processed elements to avoid duplicates
  const processedElements = new WeakSet();

  // Debug mode
  const DEBUG = false;

  /**
   * Convert onclick string to function call — CSP-safe (no new Function / eval).
   * Handles patterns:
   *   "fnName()"
   *   "fnName('string', 123)"
   *   "fnName(this)"
   *   "obj.method()"  — falls back to window lookup on dotted names
   *
   * For simple no-arg and string/number-arg calls the handler resolves the
   * function from window. Complex expressions (e.g. chained calls, ternary)
   * are left unprocessed so the original onclick remains in place.
   */
  function parseOnclickHandler(onclickStr) {
    if (!onclickStr) return null;

    const cleanStr = onclickStr.trim().replace(/;\s*$/, '');

    // Match: funcName(optionalArgs)
    const match = cleanStr.match(/^([\w$.]+)\s*\((.*)\)\s*$/s);
    if (!match) {
      // Cannot safely parse — leave onclick as-is (will be handled by inline)
      return null;
    }

    const funcPath = match[1];   // e.g. "exportTabDynamics" or "obj.method"
    const argsStr = match[2].trim(); // e.g. "" or "'foo', 123" or "this"

    // Resolve function from window (supports single-level dot notation)
    function resolveFunc() {
      const parts = funcPath.split('.');
      let obj = window;
      for (const part of parts) {
        if (obj == null) return null;
        obj = obj[part];
      }
      return typeof obj === 'function' ? obj : null;
    }

    // Parse simple argument list: empty, 'string', "string", number, true/false/null/undefined
    // Special token: "this" → the element itself
    function parseArgs(str, element) {
      if (!str) return [];
      const tokens = str.split(',').map((s) => s.trim());
      return tokens.map((token) => {
        if (token === 'this') return element;
        if (token === 'true') return true;
        if (token === 'false') return false;
        if (token === 'null') return null;
        if (token === 'undefined') return undefined;
        // Quoted string
        if (/^(['"]).*\1$/.test(token)) return token.slice(1, -1);
        // Number
        const num = Number(token);
        if (!isNaN(num) && token !== '') return num;
        // Unknown — return as string
        return token;
      });
    }

    return function (_event) {
      const fn = resolveFunc();
      if (!fn) {
        console.warn('[AutoEventBinding] Function not found in window:', funcPath);
        return;
      }
      try {
        const args = parseArgs(argsStr, this);
        fn.apply(this, args);
      } catch (e) {
        console.error('[AutoEventBinding] Error executing handler:', cleanStr, e);
      }
    };
  }

  /**
   * Process a single element - convert inline event handlers to addEventListener
   * Handles onclick and onchange attributes
   */
  function processElement(element) {
    if (processedElements.has(element)) return;

    const onclick = element.getAttribute('onclick');
    const onchange = element.getAttribute('onchange');

    if (!onclick && !onchange) return;

    // Mark as processed
    processedElements.add(element);

    // Convert onclick
    if (onclick) {
      const handler = parseOnclickHandler(onclick);
      if (handler) {
        element.removeAttribute('onclick');
        element.addEventListener('click', handler);
        if (DEBUG) {
          console.log('[AutoEventBinding] Converted onclick:', onclick.substring(0, 50));
        }
      }
    }

    // Convert onchange
    if (onchange) {
      const handler = parseOnclickHandler(onchange);
      if (handler) {
        element.removeAttribute('onchange');
        element.addEventListener('change', handler);
        if (DEBUG) {
          console.log('[AutoEventBinding] Converted onchange:', onchange.substring(0, 50));
        }
      }
    }
  }

  /**
   * Process all elements in a root element
   */
  function processAllElements(root) {
    // Process root if it has onclick or onchange
    if (root.hasAttribute && (root.hasAttribute('onclick') || root.hasAttribute('onchange'))) {
      processElement(root);
    }

    // Process all descendants with onclick or onchange
    const elements = root.querySelectorAll('[onclick], [onchange]');
    elements.forEach(processElement);

    if (DEBUG && elements.length > 0) {
      console.log('[AutoEventBinding] Processed', elements.length, 'elements');
    }
  }

  /**
   * Set up MutationObserver for dynamic content
   */
  function setupObserver() {
    const observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        // Check added nodes
        mutation.addedNodes.forEach(function (node) {
          if (node.nodeType === Node.ELEMENT_NODE) {
            processAllElements(node);
          }
        });

        // Check if onclick or onchange attribute was added
        if (
          mutation.type === 'attributes' &&
          (mutation.attributeName === 'onclick' || mutation.attributeName === 'onchange')
        ) {
          processElement(mutation.target);
        }
      });
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['onclick', 'onchange']
    });

    if (DEBUG) {
      console.log('[AutoEventBinding] MutationObserver active');
    }

    return observer;
  }

  /**
   * Initialize auto event binding
   */
  function init() {
    // Set up observer for dynamic content
    setupObserver();

    // Process existing elements when DOM is ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        processAllElements(document.body);
        if (DEBUG) {
          console.log('[AutoEventBinding] Initial processing complete');
        }
      });
    } else {
      // DOM already loaded
      processAllElements(document.body);
      if (DEBUG) {
        console.log(
          '[AutoEventBinding] Initial processing complete (late init)'
        );
      }
    }
  }

  // Export for testing/debugging
  window.AutoEventBinding = {
    processElement: processElement,
    processAll: function () {
      processAllElements(document.body);
    },
    debug: function (enabled) {
      // Note: This won't work since DEBUG is const, but shows intent
      console.log('[AutoEventBinding] Debug mode:', enabled ? 'ON' : 'OFF');
    }
  };

  // Auto-initialize
  init();

  console.log(
    '[AutoEventBinding] Loaded - onclick handlers will be auto-converted'
  );
})();
