/**
 * 🔒 Security Configuration - Bybit Strategy Tester v2
 *
 * Content Security Policy and Subresource Integrity configuration.
 * Part of Phase 1: Critical Security & Performance
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// ============================================
// SUBRESOURCE INTEGRITY HASHES
// ============================================
// These hashes ensure CDN resources haven't been tampered with.
// Regenerate using: https://www.srihash.org/ or openssl dgst -sha384 -binary FILE | base64

const SRI_HASHES = {
    // Chart.js
    'chart.js': {
        version: '4.4.1',
        url: 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js',
        integrity: 'sha384-9nhczxUqK87bcKHh20fSQcTGD4qq5GhayNYSYWqwBkINBhOfQLg/P5HG5lF1urn4'
    },

    // Chart.js Date Adapter
    'chartjs-adapter-date-fns': {
        version: '3.0.0',
        url: 'https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js',
        integrity: 'sha384-cVMg8E3QFwTvGCDuK+ET4PD341jF3W8nO1auiXfuZNQkzbUUiBGLsIQUE+b1mxws'
    },

    // Bootstrap Icons
    'bootstrap-icons': {
        version: '1.11.1',
        url: 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css',
        integrity: 'sha384-4LISF5TTJX/fLmGSxO53rV4miRxdg84mZsxmO8Rx5jGtp/LbrixFETvWa5a6sESd'
    },

    // Bootstrap CSS
    'bootstrap-css': {
        version: '5.3.2',
        url: 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
        integrity: 'sha384-T3c6CoIi6uLrA9TneNEoa7RxnatzjcDSCmG1MXxSR1GAsXEV/Dwwykc2MPK8M2HN'
    },

    // Bootstrap JS Bundle
    'bootstrap-js': {
        version: '5.3.2',
        url: 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js',
        integrity: 'sha384-C6RzsynM9kWDrMNeT87bh95OGNyZPhcTNXj1NW7RuBCsyN/o0jlpcV8Qyq46cDfL'
    },

    // Lightweight Charts (TradingView)
    'lightweight-charts': {
        version: '4.1.0',
        url: 'https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js',
        integrity: 'sha384-rcCMiCptH4kTlEbg0euOTUKWe72TESbrjElatnG+9BfbmUIV268UK/Pro5biJdGm'
    }
};

// ============================================
// CONTENT SECURITY POLICY
// ============================================

/**
 * Generate CSP meta tag content
 * @param {Object} options - CSP options
 * @returns {string} CSP policy string
 */
function generateCSP(options = {}) {
    const defaults = {
        // Default sources
        defaultSrc: ['\'self\''],

        // Scripts - local + specific CDNs
        scriptSrc: [
            '\'self\'',
            'https://cdn.jsdelivr.net',
            'https://unpkg.com'
            // For inline event handlers (temporary - should be removed)
            // "'unsafe-inline'"
        ],

        // Styles - local + CDNs + inline (needed for dynamic styles)
        styleSrc: [
            '\'self\'',
            'https://cdn.jsdelivr.net',
            'https://fonts.googleapis.com',
            '\'unsafe-inline\'' // Required for inline styles, try to remove later
        ],

        // Images
        imgSrc: [
            '\'self\'',
            'data:',
            'https:'
        ],

        // Fonts
        fontSrc: [
            '\'self\'',
            'https://cdn.jsdelivr.net',
            'https://fonts.gstatic.com'
        ],

        // API connections
        connectSrc: [
            '\'self\'',
            'https://api.bybit.com',
            'wss://stream.bybit.com',
            'ws://localhost:*',
            'http://localhost:*'
        ],

        // Frames (none by default)
        frameSrc: ['\'none\''],

        // Objects (none)
        objectSrc: ['\'none\''],

        // Base URI
        baseUri: ['\'self\''],

        // Form actions
        formAction: ['\'self\''],

        // Frame ancestors (clickjacking protection)
        frameAncestors: ['\'none\''],

        // Upgrade insecure requests in production
        upgradeInsecureRequests: options.production || false
    };

    const policy = { ...defaults, ...options };

    const directives = [
        `default-src ${policy.defaultSrc.join(' ')}`,
        `script-src ${policy.scriptSrc.join(' ')}`,
        `style-src ${policy.styleSrc.join(' ')}`,
        `img-src ${policy.imgSrc.join(' ')}`,
        `font-src ${policy.fontSrc.join(' ')}`,
        `connect-src ${policy.connectSrc.join(' ')}`,
        `frame-src ${policy.frameSrc.join(' ')}`,
        `object-src ${policy.objectSrc.join(' ')}`,
        `base-uri ${policy.baseUri.join(' ')}`,
        `form-action ${policy.formAction.join(' ')}`,
        `frame-ancestors ${policy.frameAncestors.join(' ')}`
    ];

    if (policy.upgradeInsecureRequests) {
        directives.push('upgrade-insecure-requests');
    }

    return directives.join('; ');
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
    // CSP
    'Content-Security-Policy': generateCSP(),

    // Prevent MIME sniffing
    'X-Content-Type-Options': 'nosniff',

    // XSS Protection (legacy, but still useful)
    'X-XSS-Protection': '1; mode=block',

    // Clickjacking protection
    'X-Frame-Options': 'DENY',

    // Referrer policy
    'Referrer-Policy': 'strict-origin-when-cross-origin',

    // Permissions policy
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'

    // HSTS (only for production with HTTPS)
    // 'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
};

// ============================================
// HELPER FUNCTIONS
// ============================================

/**
 * Generate script tag with SRI
 * @param {string} name - Library name from SRI_HASHES
 * @param {Object} options - Additional attributes
 * @returns {string} Script tag HTML
 */
function getScriptTag(name, options = {}) {
    const lib = SRI_HASHES[name];
    if (!lib) {
        console.warn(`Unknown library: ${name}`);
        return '';
    }

    const attrs = [
        `src="${lib.url}"`,
        `integrity="${lib.integrity}"`,
        'crossorigin="anonymous"'
    ];

    if (options.async) attrs.push('async');
    if (options.defer) attrs.push('defer');

    return `<script ${attrs.join(' ')}></script>`;
}

/**
 * Generate link tag with SRI
 * @param {string} name - Library name from SRI_HASHES
 * @returns {string} Link tag HTML
 */
function getLinkTag(name) {
    const lib = SRI_HASHES[name];
    if (!lib) {
        console.warn(`Unknown library: ${name}`);
        return '';
    }

    return `<link rel="stylesheet" href="${lib.url}" integrity="${lib.integrity}" crossorigin="anonymous">`;
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
    getLinkTag
};

// Attach to window
if (typeof window !== 'undefined') {
    window.Security = {
        SRI_HASHES,
        generateCSP,
        getCSPMetaTag,
        SECURITY_HEADERS
    };
}
