/**
 * 🔒 Security Configuration - Bybit Strategy Tester v2
 *
 * Content Security Policy and Subresource Integrity configuration.
 * Part of Phase 1: Critical Security & Performance
 *
 * @version 2.0.0
 * @date 2026-01-28
 *
 * Security Improvements:
 * - Nonce-based CSP for inline styles (P0-1 fix)
 * - CSRF token management
 * - Enhanced security headers
 */

// ============================================
// SUBRESOURCE INTEGRITY HASHES
// ============================================
// These hashes ensure CDN resources haven't been tampered with.
// Regenerate using: https://www.srihash.org/ or openssl dgst -sha384 -binary FILE | base64

const SRI_HASHES = {
  // Chart.js
  "chart.js": {
    version: "4.4.1",
    url: "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
    integrity:
      "sha384-9nhczxUqK87bcKHh20fSQcTGD4qq5GhayNYSYWqwBkINBhOfQLg/P5HG5lF1urn4",
  },

  // Chart.js Date Adapter
  "chartjs-adapter-date-fns": {
    version: "3.0.0",
    url: "https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js",
    integrity:
      "sha384-cVMg8E3QFwTvGCDuK+ET4PD341jF3W8nO1auiXfuZNQkzbUUiBGLsIQUE+b1mxws",
  },

  // Bootstrap Icons
  "bootstrap-icons": {
    version: "1.11.1",
    url: "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css",
    integrity:
      "sha384-4LISF5TTJX/fLmGSxO53rV4miRxdg84mZsxmO8Rx5jGtp/LbrixFETvWa5a6sESd",
  },

  // Bootstrap CSS
  "bootstrap-css": {
    version: "5.3.2",
    url: "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css",
    integrity:
      "sha384-T3c6CoIi6uLrA9TneNEoa7RxnatzjcDSCmG1MXxSR1GAsXEV/Dwwykc2MPK8M2HN",
  },

  // Bootstrap JS Bundle
  "bootstrap-js": {
    version: "5.3.2",
    url: "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js",
    integrity:
      "sha384-C6RzsynM9kWDrMNeT87bh95OGNyZPhcTNXj1NW7RuBCsyN/o0jlpcV8Qyq46cDfL",
  },

  // Lightweight Charts (TradingView)
  "lightweight-charts": {
    version: "4.1.0",
    url: "https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js",
    integrity:
      "sha384-rcCMiCptH4kTlEbg0euOTUKWe72TESbrjElatnG+9BfbmUIV268UK/Pro5biJdGm",
  },
};

// ============================================
// CONTENT SECURITY POLICY
// ============================================

/**
 * Generate a cryptographically secure nonce
 * @returns {string} Base64 encoded nonce
 */
function generateNonce() {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return btoa(String.fromCharCode.apply(null, array));
}

// Store current nonce (regenerated per page load)
let currentNonce = null;

/**
 * Get or generate the current page nonce
 * @returns {string}
 */
function getNonce() {
  if (!currentNonce) {
    currentNonce = generateNonce();
  }
  return currentNonce;
}

/**
 * Generate CSP meta tag content
 * @param {Object} options - CSP options
 * @returns {string} CSP policy string
 */
function generateCSP(options = {}) {
  const nonce = options.nonce || getNonce();

  const defaults = {
    // Default sources
    defaultSrc: ["'self'"],

    // Scripts - local + specific CDNs + nonce for inline
    scriptSrc: [
      "'self'",
      "https://cdn.jsdelivr.net",
      "https://unpkg.com",
      `'nonce-${nonce}'`,
    ],

    // Styles - local + CDNs + nonce (NO unsafe-inline!)
    styleSrc: [
      "'self'",
      "https://cdn.jsdelivr.net",
      "https://fonts.googleapis.com",
      `'nonce-${nonce}'`,
      // REMOVED: '\'unsafe-inline\'' - Security vulnerability!
    ],

    // Images
    imgSrc: ["'self'", "data:", "https:"],

    // Fonts
    fontSrc: [
      "'self'",
      "https://cdn.jsdelivr.net",
      "https://fonts.gstatic.com",
    ],

    // API connections
    connectSrc: [
      "'self'",
      "https://api.bybit.com",
      "wss://stream.bybit.com",
      "ws://localhost:*",
      "http://localhost:*",
    ],

    // Frames (none by default)
    frameSrc: ["'none'"],

    // Objects (none)
    objectSrc: ["'none'"],

    // Base URI
    baseUri: ["'self'"],

    // Form actions
    formAction: ["'self'"],

    // Frame ancestors (clickjacking protection)
    frameAncestors: ["'none'"],

    // Upgrade insecure requests in production
    upgradeInsecureRequests: options.production || false,
  };

  const policy = { ...defaults, ...options };

  const directives = [
    `default-src ${policy.defaultSrc.join(" ")}`,
    `script-src ${policy.scriptSrc.join(" ")}`,
    `style-src ${policy.styleSrc.join(" ")}`,
    `img-src ${policy.imgSrc.join(" ")}`,
    `font-src ${policy.fontSrc.join(" ")}`,
    `connect-src ${policy.connectSrc.join(" ")}`,
    `frame-src ${policy.frameSrc.join(" ")}`,
    `object-src ${policy.objectSrc.join(" ")}`,
    `base-uri ${policy.baseUri.join(" ")}`,
    `form-action ${policy.formAction.join(" ")}`,
    `frame-ancestors ${policy.frameAncestors.join(" ")}`,
  ];

  if (policy.upgradeInsecureRequests) {
    directives.push("upgrade-insecure-requests");
  }

  return directives.join("; ");
}

/**
 * Generate CSP meta tag HTML
 * @returns {string} Meta tag HTML
 */
function getCSPMetaTag() {
  return `<meta http-equiv="Content-Security-Policy" content="${generateCSP()}">`;
}

// ============================================
// SECURITY HEADERS (for server-side use)
// ============================================

const SECURITY_HEADERS = {
  // CSP (will need nonce from server)
  "Content-Security-Policy": generateCSP(),

  // Prevent MIME sniffing
  "X-Content-Type-Options": "nosniff",

  // XSS Protection (legacy, but still useful)
  "X-XSS-Protection": "1; mode=block",

  // Clickjacking protection
  "X-Frame-Options": "DENY",

  // Referrer policy
  "Referrer-Policy": "strict-origin-when-cross-origin",

  // Permissions policy
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",

  // Cross-Origin policies
  "Cross-Origin-Embedder-Policy": "require-corp",
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Resource-Policy": "same-origin",

  // HSTS (only for production with HTTPS)
  // 'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
};

// ============================================
// CSRF PROTECTION
// ============================================

let csrfToken = null;

/**
 * Initialize CSRF token from meta tag
 */
function initCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) {
    csrfToken = meta.getAttribute("content");
  }
  return csrfToken;
}

/**
 * Get current CSRF token
 * @returns {string|null}
 */
function getCsrfToken() {
  if (!csrfToken) {
    initCsrfToken();
  }
  return csrfToken;
}

/**
 * Set CSRF token (e.g., from API response)
 * @param {string} token
 */
function setCsrfToken(token) {
  csrfToken = token;

  // Update meta tag if exists
  let meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta) {
    meta = document.createElement("meta");
    meta.setAttribute("name", "csrf-token");
    document.head.appendChild(meta);
  }
  meta.setAttribute("content", token);
}

/**
 * Add CSRF token to headers
 * @param {Object} headers - Request headers
 * @returns {Object} Headers with CSRF token
 */
function withCsrfToken(headers = {}) {
  const token = getCsrfToken();
  if (token) {
    return {
      ...headers,
      "X-CSRF-Token": token,
    };
  }
  return headers;
}

// ============================================
// HELPER FUNCTIONS
// ============================================

/**
 * Generate script tag with SRI and nonce
 * @param {string} name - Library name from SRI_HASHES
 * @param {Object} options - Additional attributes
 * @returns {string} Script tag HTML
 */
function getScriptTag(name, options = {}) {
  const lib = SRI_HASHES[name];
  if (!lib) {
    console.warn(`Unknown library: ${name}`);
    return "";
  }

  const nonce = options.nonce || getNonce();
  const attrs = [
    `src="${lib.url}"`,
    `integrity="${lib.integrity}"`,
    'crossorigin="anonymous"',
    `nonce="${nonce}"`,
  ];

  if (options.async) attrs.push("async");
  if (options.defer) attrs.push("defer");

  return `<script ${attrs.join(" ")}></script>`;
}

/**
 * Generate link tag with SRI and nonce
 * @param {string} name - Library name from SRI_HASHES
 * @param {Object} options - Additional attributes
 * @returns {string} Link tag HTML
 */
function getLinkTag(name, options = {}) {
  const lib = SRI_HASHES[name];
  if (!lib) {
    console.warn(`Unknown library: ${name}`);
    return "";
  }

  const nonce = options.nonce || getNonce();
  return `<link rel="stylesheet" href="${lib.url}" integrity="${lib.integrity}" crossorigin="anonymous" nonce="${nonce}">`;
}

/**
 * Generate inline style tag with nonce
 * @param {string} css - CSS content
 * @param {Object} options - Additional attributes
 * @returns {string} Style tag HTML
 */
function getStyleTag(css, options = {}) {
  const nonce = options.nonce || getNonce();
  return `<style nonce="${nonce}">${css}</style>`;
}

/**
 * Generate inline script tag with nonce
 * @param {string} js - JavaScript content
 * @param {Object} options - Additional attributes
 * @returns {string} Script tag HTML
 */
function getInlineScriptTag(js, options = {}) {
  const nonce = options.nonce || getNonce();
  return `<script nonce="${nonce}">${js}</script>`;
}

// ============================================
// EXPORTS
// ============================================

export {
  SRI_HASHES,
  generateCSP,
  getCSPMetaTag,
  SECURITY_HEADERS,
  getScriptTag,
  getLinkTag,
  getStyleTag,
  getInlineScriptTag,
  getNonce,
  generateNonce,
  getCsrfToken,
  setCsrfToken,
  withCsrfToken,
  initCsrfToken,
};

// Attach to window
if (typeof window !== "undefined") {
  window.Security = {
    SRI_HASHES,
    generateCSP,
    getCSPMetaTag,
    SECURITY_HEADERS,
    getNonce,
    getCsrfToken,
    setCsrfToken,
    withCsrfToken,
  };

  // Auto-initialize CSRF token
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCsrfToken);
  } else {
    initCsrfToken();
  }
}
