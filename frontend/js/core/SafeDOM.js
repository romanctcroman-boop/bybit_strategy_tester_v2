/**
 * 🛡️ Safe DOM Operations - Bybit Strategy Tester v2
 *
 * Global patches for safe DOM manipulation.
 * Automatically sanitizes content to prevent XSS.
 *
 * Fixes P0-3: innerHTML XSS vulnerability
 *
 * @version 1.0.0
 * @date 2026-01-28
 */

import {
  sanitize,
  escapeHtml,
  setInnerHTML,
  createElementFromHTML,
} from "./Sanitizer.js";

// ============================================
// SAFE DOM UTILITIES
// ============================================

/**
 * Safely set text content (no HTML interpretation)
 * @param {HTMLElement} element - Target element
 * @param {string} text - Text content
 */
export function safeText(element, text) {
  if (element) {
    element.textContent = String(text ?? "");
  }
}

/**
 * Safely set HTML content (sanitized)
 * @param {HTMLElement} element - Target element
 * @param {string} html - HTML content (will be sanitized)
 */
export function safeHTML(element, html) {
  setInnerHTML(element, html);
}

/**
 * Create element with safe content
 * @param {string} tag - HTML tag name
 * @param {Object} attrs - Attributes
 * @param {string|HTMLElement|Array} children - Children (text, element, or array)
 * @returns {HTMLElement}
 */
export function createElement(tag, attrs = {}, children = null) {
  const element = document.createElement(tag);

  // Set attributes safely
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "className") {
      element.className = escapeHtml(String(value));
    } else if (key === "style" && typeof value === "object") {
      Object.assign(element.style, value);
    } else if (key.startsWith("on") && typeof value === "function") {
      // Event handlers - attach safely
      const eventName = key.slice(2).toLowerCase();
      element.addEventListener(eventName, value);
    } else if (key === "data" && typeof value === "object") {
      // Data attributes
      for (const [dataKey, dataValue] of Object.entries(value)) {
        element.dataset[dataKey] = escapeHtml(String(dataValue));
      }
    } else if (typeof value === "string") {
      element.setAttribute(key, escapeHtml(value));
    } else if (typeof value === "boolean" && value) {
      element.setAttribute(key, "");
    }
  }

  // Add children
  if (children !== null) {
    appendChildren(element, children);
  }

  return element;
}

/**
 * Append children safely
 * @param {HTMLElement} parent - Parent element
 * @param {string|HTMLElement|Array} children - Children to append
 */
export function appendChildren(parent, children) {
  if (!parent) return;

  if (Array.isArray(children)) {
    children.forEach((child) => appendChildren(parent, child));
  } else if (
    children instanceof HTMLElement ||
    children instanceof DocumentFragment
  ) {
    parent.appendChild(children);
  } else if (typeof children === "string") {
    // Text content - escape HTML
    parent.appendChild(document.createTextNode(children));
  } else if (children != null) {
    parent.appendChild(document.createTextNode(String(children)));
  }
}

/**
 * Build HTML from template literals safely
 * @param {TemplateStringsArray} strings - Template strings
 * @param {...any} values - Interpolated values
 * @returns {string} Sanitized HTML string
 */
export function html(strings, ...values) {
  let result = "";
  for (let i = 0; i < strings.length; i++) {
    result += strings[i];
    if (i < values.length) {
      const value = values[i];
      if (value instanceof TrustedHTML) {
        // Already trusted - use as is
        result += value.toString();
      } else if (typeof value === "string") {
        // Escape user content
        result += escapeHtml(value);
      } else if (value != null) {
        result += escapeHtml(String(value));
      }
    }
  }
  return result;
}

/**
 * Mark HTML as trusted (use with caution!)
 * Only use for static HTML that doesn't contain user input.
 */
export class TrustedHTML {
  constructor(html) {
    this._html = html;
  }

  toString() {
    return this._html;
  }
}

/**
 * Create trusted HTML (for static content only)
 * @param {string} html - Static HTML string
 * @returns {TrustedHTML}
 */
export function trusted(html) {
  return new TrustedHTML(html);
}

// ============================================
// TABLE BUILDER
// ============================================

/**
 * Build table row safely
 * @param {Array} cells - Cell contents
 * @param {string} cellTag - 'td' or 'th'
 * @returns {HTMLElement}
 */
export function tableRow(cells, cellTag = "td") {
  const tr = document.createElement("tr");
  cells.forEach((content) => {
    const cell = document.createElement(cellTag);
    if (content instanceof HTMLElement) {
      cell.appendChild(content);
    } else {
      cell.textContent = String(content ?? "");
    }
    tr.appendChild(cell);
  });
  return tr;
}

/**
 * Build table safely
 * @param {Array<Array>} rows - Array of row data
 * @param {Array} headers - Optional header row
 * @returns {HTMLElement}
 */
export function buildTable(rows, headers = null) {
  const table = document.createElement("table");

  if (headers) {
    const thead = document.createElement("thead");
    thead.appendChild(tableRow(headers, "th"));
    table.appendChild(thead);
  }

  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    tbody.appendChild(tableRow(row, "td"));
  });
  table.appendChild(tbody);

  return table;
}

// ============================================
// GLOBAL HELPERS
// ============================================

/**
 * Query selector with null safety
 * @param {string} selector - CSS selector
 * @param {HTMLElement} parent - Parent element (default: document)
 * @returns {HTMLElement|null}
 */
export function $(selector, parent = document) {
  return parent.querySelector(selector);
}

/**
 * Query selector all with array return
 * @param {string} selector - CSS selector
 * @param {HTMLElement} parent - Parent element (default: document)
 * @returns {Array<HTMLElement>}
 */
export function $$(selector, parent = document) {
  return Array.from(parent.querySelectorAll(selector));
}

// ============================================
// EXPORTS TO WINDOW
// ============================================

if (typeof window !== "undefined") {
  window.SafeDOM = {
    safeText,
    safeHTML,
    createElement,
    appendChildren,
    html,
    trusted,
    TrustedHTML,
    tableRow,
    buildTable,
    $,
    $$,
    // Re-export from Sanitizer
    sanitize,
    escapeHtml,
    setInnerHTML,
    createElementFromHTML,
  };

  // Shorthand aliases
  window.$safe = $;
  window.$$safe = $$;
}

export default {
  safeText,
  safeHTML,
  createElement,
  appendChildren,
  html,
  trusted,
  TrustedHTML,
  tableRow,
  buildTable,
  $,
  $$,
};
