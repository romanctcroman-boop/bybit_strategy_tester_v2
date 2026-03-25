/**
 * 🧩 Base Component Class - Bybit Strategy Tester v2
 *
 * Foundation for all reusable UI components.
 * Provides lifecycle management, event handling, and DOM utilities.
 *
 * Part of Phase 2: Architecture Modernization
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

/**
 * Base class for all UI components
 * Provides common functionality: lifecycle, events, DOM management
 */
export class Component {
    /**
     * Create a new component
     * @param {Object} options - Component options
     * @param {HTMLElement|string} options.container - Container element or selector
     * @param {Object} options.props - Component properties
     * @param {Object} options.state - Initial state
     */
    constructor(options = {}) {
        this.container = this._resolveContainer(options.container);
        this.props = { ...this.defaultProps(), ...options.props };
        this.state = { ...this.defaultState(), ...options.state };
        this.element = null;
        this._eventListeners = [];
        this._children = [];
        this._mounted = false;

        // Auto-mount if container is provided
        if (this.container && options.autoMount !== false) {
            this.mount();
        }
    }

    /**
     * Default props - override in subclasses
     * @returns {Object} Default properties
     */
    defaultProps() {
        return {};
    }

    /**
     * Default state - override in subclasses
     * @returns {Object} Default state
     */
    defaultState() {
        return {};
    }

    /**
     * Resolve container from selector or element
     * @private
     */
    _resolveContainer(container) {
        if (!container) return null;
        if (typeof container === 'string') {
            return document.querySelector(container);
        }
        return container;
    }

    /**
     * Create the component's DOM element - override in subclasses
     * @returns {HTMLElement} The component element
     */
    render() {
        const el = document.createElement('div');
        el.className = 'component';
        return el;
    }

    /**
     * Mount the component to the DOM
     * @returns {Component} This component for chaining
     */
    mount() {
        if (this._mounted) return this;

        this.beforeMount();
        this.element = this.render();

        if (this.container) {
            this.container.appendChild(this.element);
        }

        this._mounted = true;
        this.afterMount();

        return this;
    }

    /**
     * Unmount the component from the DOM
     * @returns {Component} This component for chaining
     */
    unmount() {
        if (!this._mounted) return this;

        this.beforeUnmount();

        // Remove all event listeners
        this._eventListeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });
        this._eventListeners = [];

        // Unmount children
        this._children.forEach(child => child.unmount());
        this._children = [];

        // Remove from DOM
        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }

        this._mounted = false;
        this.afterUnmount();

        return this;
    }

    /**
     * Update component state and re-render if needed
     * @param {Object} newState - Partial state to merge
     * @param {boolean} shouldRender - Whether to re-render
     */
    setState(newState, shouldRender = true) {
        const prevState = { ...this.state };
        this.state = { ...this.state, ...newState };

        if (shouldRender && this._mounted) {
            this.update(prevState);
        }
    }

    /**
     * Update the component - called after state changes
     * @param {Object} _prevState - Previous state before update
     */
    update(_prevState) {
        // Default: full re-render
        const newElement = this.render();
        if (this.element && this.element.parentNode) {
            this.element.parentNode.replaceChild(newElement, this.element);
            this.element = newElement;
        }
    }

    /**
     * Add an event listener with automatic cleanup
     * @param {HTMLElement|string} element - Element or selector
     * @param {string} event - Event name
     * @param {Function} handler - Event handler
     * @param {Object} options - Event listener options
     */
    on(element, event, handler, options = {}) {
        const el = typeof element === 'string'
            ? this.element?.querySelector(element) || document.querySelector(element)
            : element;

        if (!el) return this;

        const boundHandler = handler.bind(this);
        el.addEventListener(event, boundHandler, options);
        this._eventListeners.push({ element: el, event, handler: boundHandler });

        return this;
    }

    /**
     * Emit a custom event
     * @param {string} eventName - Event name
     * @param {*} detail - Event detail data
     */
    emit(eventName, detail = null) {
        const event = new CustomEvent(eventName, {
            bubbles: true,
            cancelable: true,
            detail
        });

        if (this.element) {
            this.element.dispatchEvent(event);
        }

        return this;
    }

    /**
     * Find an element within this component
     * @param {string} selector - CSS selector
     * @returns {HTMLElement|null}
     */
    find(selector) {
        return this.element?.querySelector(selector) || null;
    }

    /**
     * Find all elements within this component
     * @param {string} selector - CSS selector
     * @returns {NodeList}
     */
    findAll(selector) {
        return this.element?.querySelectorAll(selector) || [];
    }

    /**
     * Add a child component
     * @param {Component} child - Child component
     * @returns {Component} The child component
     */
    addChild(child) {
        this._children.push(child);
        return child;
    }

    // Lifecycle hooks - override in subclasses
    beforeMount() {}
    afterMount() {}
    beforeUnmount() {}
    afterUnmount() {}

    /**
     * Create an HTML element with attributes and children
     * @param {string} tag - HTML tag name
     * @param {Object} attrs - Attributes
     * @param  {...(HTMLElement|string)} children - Child elements or text
     * @returns {HTMLElement}
     */
    createElement(tag, attrs = {}, ...children) {
        const el = document.createElement(tag);

        for (const [key, value] of Object.entries(attrs)) {
            if (key === 'className') {
                el.className = value;
            } else if (key === 'style' && typeof value === 'object') {
                Object.assign(el.style, value);
            } else if (key.startsWith('on') && typeof value === 'function') {
                const event = key.slice(2).toLowerCase();
                el.addEventListener(event, value.bind(this));
            } else if (key === 'data' && typeof value === 'object') {
                for (const [dataKey, dataValue] of Object.entries(value)) {
                    el.dataset[dataKey] = dataValue;
                }
            } else if (value !== null && value !== undefined && value !== false) {
                el.setAttribute(key, value === true ? '' : value);
            }
        }

        for (const child of children) {
            if (child instanceof HTMLElement) {
                el.appendChild(child);
            } else if (child !== null && child !== undefined) {
                el.appendChild(document.createTextNode(String(child)));
            }
        }

        return el;
    }

    /**
     * Shorthand for createElement
     */
    h(tag, attrs = {}, ...children) {
        return this.createElement(tag, attrs, ...children);
    }
}

// Export for use
export default Component;
