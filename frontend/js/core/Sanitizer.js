/**
 * 🛡️ HTML Sanitizer - Bybit Strategy Tester v2
 *
 * XSS protection through HTML sanitization.
 * DOMPurify-like functionality without external dependencies.
 *
 * Fixes P0-3: innerHTML XSS vulnerability
 *
 * @version 1.0.0
 * @date 2026-01-28
 */

// ============================================
// ALLOWED TAGS AND ATTRIBUTES
// ============================================

const DEFAULT_ALLOWED_TAGS = new Set([
    // Text formatting
    'p',
    'br',
    'hr',
    'span',
    'div',
    'strong',
    'b',
    'em',
    'i',
    'u',
    's',
    'strike',
    'del',
    'ins',
    'sub',
    'sup',
    'small',
    'mark',
    'code',
    'pre',
    'kbd',
    'samp',

    // Headings
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',

    // Lists
    'ul',
    'ol',
    'li',
    'dl',
    'dt',
    'dd',

    // Tables
    'table',
    'thead',
    'tbody',
    'tfoot',
    'tr',
    'th',
    'td',
    'caption',
    'colgroup',
    'col',

    // Links and media (careful with these)
    'a',
    'img',

    // Semantic
    'article',
    'section',
    'header',
    'footer',
    'nav',
    'aside',
    'main',
    'figure',
    'figcaption',
    'blockquote',
    'cite',
    'q',
    'abbr',
    'time',

    // Forms (read-only display)
    'label',

    // Bootstrap icons
    'i'
]);

const DEFAULT_ALLOWED_ATTRS = new Set([
    // Global attributes
    'class',
    'id',
    'title',
    'lang',
    'dir',

    // Data attributes are handled separately

    // Specific attributes
    'href',
    'src',
    'alt',
    'width',
    'height',
    'colspan',
    'rowspan',
    'scope',
    'datetime',
    'cite'
]);

// Attributes allowed on specific tags
const TAG_SPECIFIC_ATTRS = {
    a: ['href', 'target', 'rel'],
    img: ['src', 'alt', 'width', 'height', 'loading'],
    td: ['colspan', 'rowspan'],
    th: ['colspan', 'rowspan', 'scope'],
    time: ['datetime'],
    blockquote: ['cite'],
    q: ['cite']
};

// URL schemes allowed in href/src
const ALLOWED_URI_SCHEMES = new Set([
    'http:',
    'https:',
    'mailto:',
    'tel:',
    '#',
    ''
]);

// ============================================
// SANITIZER CLASS
// ============================================

/**
 * HTML Sanitizer for XSS protection
 *
 * @example
 * const sanitizer = new Sanitizer();
 *
 * // Basic sanitization
 * const safe = sanitizer.sanitize('<script>alert("xss")</script><p>Safe</p>');
 * // Result: '<p>Safe</p>'
 *
 * // With custom config
 * const sanitizer = new Sanitizer({
 *     allowedTags: ['p', 'b', 'i'],
 *     allowedAttrs: ['class']
 * });
 */
export class Sanitizer {
    constructor(options = {}) {
        this.allowedTags = options.allowedTags
            ? new Set(options.allowedTags)
            : new Set(DEFAULT_ALLOWED_TAGS);

        this.allowedAttrs = options.allowedAttrs
            ? new Set(options.allowedAttrs)
            : new Set(DEFAULT_ALLOWED_ATTRS);

        this.allowDataAttrs = options.allowDataAttrs !== false;
        this.allowStyles = options.allowStyles || false;
        this.allowedStyles = new Set(options.allowedStyles || []);
        this.stripComments = options.stripComments !== false;

        // Create parser
        this._parser = new DOMParser();
    }

    /**
   * Sanitize HTML string
   * @param {string} html - Raw HTML
   * @returns {string} Sanitized HTML
   */
    sanitize(html) {
        if (!html || typeof html !== 'string') {
            return '';
        }

        // Quick check for obvious safe strings
        if (!/[<>&"']/.test(html)) {
            return html;
        }

        // Parse HTML
        const doc = this._parser.parseFromString(
            `<div id="sanitize-root">${html}</div>`,
            'text/html'
        );

        const root = doc.getElementById('sanitize-root');
        if (!root) {
            return this._escapeText(html);
        }

        // Process all nodes
        this._processNode(root);

        return root.innerHTML;
    }

    /**
   * Sanitize and return as text (strip all HTML)
   * @param {string} html - Raw HTML
   * @returns {string} Plain text
   */
    sanitizeToText(html) {
        if (!html || typeof html !== 'string') {
            return '';
        }

        const doc = this._parser.parseFromString(html, 'text/html');
        return doc.body.textContent || '';
    }

    /**
   * Process DOM node recursively
   * @private
   */
    _processNode(node) {
        const childrenToRemove = [];

        for (const child of node.childNodes) {
            if (child.nodeType === Node.ELEMENT_NODE) {
                const tagName = child.tagName.toLowerCase();

                // Check if tag is allowed
                if (!this.allowedTags.has(tagName)) {
                    // Remove dangerous tags completely
                    if (this._isDangerousTag(tagName)) {
                        childrenToRemove.push(child);
                    } else {
                        // Replace with children for non-dangerous tags
                        const fragment = document.createDocumentFragment();
                        while (child.firstChild) {
                            fragment.appendChild(child.firstChild);
                        }
                        node.replaceChild(fragment, child);
                        // Re-process this position
                        this._processNode(node);
                        return;
                    }
                } else {
                    // Sanitize attributes
                    this._sanitizeAttributes(child);
                    // Process children
                    this._processNode(child);
                }
            } else if (child.nodeType === Node.COMMENT_NODE && this.stripComments) {
                childrenToRemove.push(child);
            }
        }

        // Remove marked children
        for (const child of childrenToRemove) {
            node.removeChild(child);
        }
    }

    /**
   * Check if tag is dangerous (should be removed entirely)
   * @private
   */
    _isDangerousTag(tagName) {
        const dangerous = new Set([
            'script',
            'style',
            'iframe',
            'frame',
            'frameset',
            'object',
            'embed',
            'applet',
            'base',
            'link',
            'meta',
            'form',
            'input',
            'button',
            'select',
            'textarea',
            'noscript',
            'template',
            'slot',
            'svg',
            'math'
        ]);
        return dangerous.has(tagName);
    }

    /**
   * Sanitize element attributes
   * @private
   */
    _sanitizeAttributes(element) {
        const tagName = element.tagName.toLowerCase();
        const tagSpecific = TAG_SPECIFIC_ATTRS[tagName] || [];
        const attrsToRemove = [];

        for (const attr of element.attributes) {
            const attrName = attr.name.toLowerCase();
            const attrValue = attr.value;

            // Check if attribute is allowed
            const isAllowed =
        this.allowedAttrs.has(attrName) ||
        tagSpecific.includes(attrName) ||
        (this.allowDataAttrs && attrName.startsWith('data-')) ||
        (this.allowStyles && attrName === 'style');

            if (!isAllowed) {
                attrsToRemove.push(attr.name);
                continue;
            }

            // Validate specific attributes
            if (attrName === 'href' || attrName === 'src') {
                if (!this._isValidUrl(attrValue)) {
                    attrsToRemove.push(attr.name);
                    continue;
                }
            }

            // Sanitize style attribute
            if (attrName === 'style' && this.allowStyles) {
                const safeStyle = this._sanitizeStyle(attrValue);
                if (safeStyle) {
                    element.setAttribute('style', safeStyle);
                } else {
                    attrsToRemove.push('style');
                }
            }

            // Check for event handlers (onclick, onload, etc.)
            if (attrName.startsWith('on')) {
                attrsToRemove.push(attr.name);
            }
        }

        // Remove disallowed attributes
        for (const attr of attrsToRemove) {
            element.removeAttribute(attr);
        }

        // Add security attributes to links
        if (tagName === 'a' && element.hasAttribute('href')) {
            const href = element.getAttribute('href');
            // External links - add noopener noreferrer
            if (href && (href.startsWith('http://') || href.startsWith('https://'))) {
                element.setAttribute('rel', 'noopener noreferrer');
                element.setAttribute('target', '_blank');
            }
        }

        // Add lazy loading to images
        if (tagName === 'img' && !element.hasAttribute('loading')) {
            element.setAttribute('loading', 'lazy');
        }
    }

    /**
   * Validate URL is safe
   * @private
   */
    _isValidUrl(url) {
        if (!url) return false;

        // Trim and check for javascript: or data: exploits
        const trimmed = url.trim().toLowerCase();

        // Block javascript: and data: URLs
        if (trimmed.startsWith('javascript:') || trimmed.startsWith('data:')) {
            return false;
        }

        // Block vbscript: (IE)
        if (trimmed.startsWith('vbscript:')) {
            return false;
        }

        // Check for encoded variants
        const decoded = decodeURIComponent(trimmed);
        if (decoded.includes('javascript:') || decoded.includes('data:')) {
            return false;
        }

        // Allow relative URLs and safe schemes
        try {
            if (
                url.startsWith('#') ||
        url.startsWith('/') ||
        url.startsWith('./') ||
        url.startsWith('../')
            ) {
                return true;
            }

            const urlObj = new URL(url, window.location.origin);
            return ALLOWED_URI_SCHEMES.has(urlObj.protocol);
        } catch {
            // If URL parsing fails, be conservative
            return url.startsWith('#') || url.startsWith('/');
        }
    }

    /**
   * Sanitize style attribute
   * @private
   */
    _sanitizeStyle(style) {
        if (!style) return '';

        // Parse style declarations
        const declarations = style.split(';').filter(Boolean);
        const safeDeclarations = [];

        for (const decl of declarations) {
            const [property, value] = decl.split(':').map((s) => s.trim());

            if (!property || !value) continue;

            // Check if property is allowed
            if (this.allowedStyles.size === 0 || this.allowedStyles.has(property)) {
                // Check for dangerous values
                const lowerValue = value.toLowerCase();
                if (
                    lowerValue.includes('javascript:') ||
          lowerValue.includes('expression(') ||
          (lowerValue.includes('url(') &&
            !this._isValidUrl(
                lowerValue.match(/url\(['"]?([^'"]+)['"]?\)/)?.[1]
            ))
                ) {
                    continue;
                }

                safeDeclarations.push(`${property}: ${value}`);
            }
        }

        return safeDeclarations.join('; ');
    }

    /**
   * Escape text for safe display
   * @private
   */
    _escapeText(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// ============================================
// CONVENIENCE FUNCTIONS
// ============================================

// Default sanitizer instance
const defaultSanitizer = new Sanitizer();

/**
 * Sanitize HTML string with default config
 * @param {string} html - Raw HTML
 * @returns {string} Sanitized HTML
 */
export function sanitize(html) {
    return defaultSanitizer.sanitize(html);
}

/**
 * Sanitize to plain text
 * @param {string} html - Raw HTML
 * @returns {string} Plain text
 */
export function sanitizeToText(html) {
    return defaultSanitizer.sanitizeToText(html);
}

/**
 * Escape HTML entities (use for text that should never contain HTML)
 * @param {string} text - Raw text
 * @returns {string} Escaped text
 */
export function escapeHtml(text) {
    if (!text || typeof text !== 'string') return '';

    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Safe innerHTML setter
 * Sanitizes content before setting innerHTML
 * @param {HTMLElement} element - Target element
 * @param {string} html - HTML content
 */
export function setInnerHTML(element, html) {
    if (element && typeof html === 'string') {
        element.innerHTML = defaultSanitizer.sanitize(html);
    }
}

/**
 * Create element from HTML template (sanitized)
 * @param {string} html - HTML template
 * @returns {HTMLElement|null}
 */
export function createElementFromHTML(html) {
    const sanitized = defaultSanitizer.sanitize(html);
    const template = document.createElement('template');
    template.innerHTML = sanitized.trim();
    return template.content.firstChild;
}

// ============================================
// EXPORTS
// ============================================

export default Sanitizer;

// Attach to window for non-module scripts
if (typeof window !== 'undefined') {
    window.Sanitizer = Sanitizer;
    window.sanitize = sanitize;
    window.sanitizeToText = sanitizeToText;
    window.escapeHtml = escapeHtml;
    window.setInnerHTML = setInnerHTML;
    window.createElementFromHTML = createElementFromHTML;
}
