/**
 * 🚀 Lazy Loader - Bybit Strategy Tester v2
 *
 * Dynamic module loading and code splitting utilities.
 * Implements lazy loading patterns for improved performance.
 *
 * Part of Phase 3: Performance Optimization
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

/**
 * Module loading states
 */
export const LoadState = {
    IDLE: 'idle',
    LOADING: 'loading',
    LOADED: 'loaded',
    ERROR: 'error'
};

/**
 * Lazy Loader class for dynamic imports
 */
export class LazyLoader {
    constructor() {
        this._cache = new Map();
        this._pending = new Map();
        this._retryCount = 3;
        this._retryDelay = 1000;
        this._timeout = 30000;
        this._observers = new Map();
    }

    /**
     * Load a module dynamically
     * @param {string} modulePath - Path to the module
     * @param {Object} options - Loading options
     * @returns {Promise<*>}
     */
    async load(modulePath, options = {}) {
        const {
            retry = this._retryCount,
            timeout = this._timeout,
            fallback = null
        } = options;

        // Return cached module
        if (this._cache.has(modulePath)) {
            return this._cache.get(modulePath);
        }

        // Return pending promise if already loading
        if (this._pending.has(modulePath)) {
            return this._pending.get(modulePath);
        }

        // Create loading promise
        const loadPromise = this._loadWithRetry(modulePath, retry, timeout)
            .then(module => {
                this._cache.set(modulePath, module);
                this._pending.delete(modulePath);
                return module;
            })
            .catch(error => {
                this._pending.delete(modulePath);
                if (fallback) {
                    console.warn(`Failed to load ${modulePath}, using fallback`, error);
                    return fallback;
                }
                throw error;
            });

        this._pending.set(modulePath, loadPromise);
        return loadPromise;
    }

    /**
     * Load with retry logic
     * @private
     */
    async _loadWithRetry(modulePath, retries, timeout) {
        let lastError;

        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                return await this._loadWithTimeout(modulePath, timeout);
            } catch (error) {
                lastError = error;
                if (attempt < retries) {
                    await this._delay(this._retryDelay * (attempt + 1));
                }
            }
        }

        throw lastError;
    }

    /**
     * Load with timeout
     * @private
     */
    async _loadWithTimeout(modulePath, timeout) {
        return Promise.race([
            import(/* @vite-ignore */ modulePath),
            new Promise((_, reject) =>
                setTimeout(() => reject(new Error(`Timeout loading ${modulePath}`)), timeout)
            )
        ]);
    }

    /**
     * Delay helper
     * @private
     */
    _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Preload a module (hint to browser)
     * @param {string} modulePath - Path to preload
     */
    preload(modulePath) {
        if (this._cache.has(modulePath)) return;

        const link = document.createElement('link');
        link.rel = 'modulepreload';
        link.href = modulePath;
        document.head.appendChild(link);
    }

    /**
     * Preload multiple modules
     * @param {string[]} modulePaths - Paths to preload
     */
    preloadAll(modulePaths) {
        modulePaths.forEach(path => this.preload(path));
    }

    /**
     * Check if module is cached
     * @param {string} modulePath - Path to check
     * @returns {boolean}
     */
    isCached(modulePath) {
        return this._cache.has(modulePath);
    }

    /**
     * Check if module is loading
     * @param {string} modulePath - Path to check
     * @returns {boolean}
     */
    isLoading(modulePath) {
        return this._pending.has(modulePath);
    }

    /**
     * Get loading state
     * @param {string} modulePath - Path to check
     * @returns {string}
     */
    getState(modulePath) {
        if (this._cache.has(modulePath)) return LoadState.LOADED;
        if (this._pending.has(modulePath)) return LoadState.LOADING;
        return LoadState.IDLE;
    }

    /**
     * Clear cache
     * @param {string} modulePath - Specific path or null for all
     */
    clearCache(modulePath = null) {
        if (modulePath) {
            this._cache.delete(modulePath);
        } else {
            this._cache.clear();
        }
    }
}

/**
 * Intersection Observer based lazy loading for components
 */
export class IntersectionLoader {
    constructor(options = {}) {
        this._options = {
            root: null,
            rootMargin: '100px',
            threshold: 0.1,
            ...options
        };
        this._observer = null;
        this._targets = new Map();
        this._init();
    }

    /**
     * Initialize observer
     * @private
     */
    _init() {
        if (typeof IntersectionObserver === 'undefined') {
            console.warn('IntersectionObserver not supported');
            return;
        }

        this._observer = new IntersectionObserver(
            entries => this._handleIntersection(entries),
            this._options
        );
    }

    /**
     * Handle intersection
     * @private
     */
    _handleIntersection(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const target = entry.target;
                const config = this._targets.get(target);

                if (config) {
                    this._loadTarget(target, config);
                }
            }
        });
    }

    /**
     * Load target content
     * @private
     */
    async _loadTarget(target, config) {
        const { loader, onLoad, onError, placeholder } = config;

        try {
            // Show placeholder
            if (placeholder) {
                target.innerHTML = placeholder;
            }

            // Load content
            const content = await loader();

            // Render content
            if (typeof content === 'string') {
                target.innerHTML = content;
            } else if (content instanceof HTMLElement) {
                target.innerHTML = '';
                target.appendChild(content);
            } else if (content && typeof content.render === 'function') {
                target.innerHTML = '';
                content.render(target);
            }

            // Callback
            if (onLoad) onLoad(target, content);

            // Stop observing
            this.unobserve(target);

        } catch (error) {
            console.error('Lazy load error:', error);
            if (onError) onError(target, error);
        }
    }

    /**
     * Observe an element for lazy loading
     * @param {HTMLElement} target - Element to observe
     * @param {Object} config - Loading configuration
     */
    observe(target, config) {
        if (!this._observer) {
            // Fallback: load immediately
            this._loadTarget(target, config);
            return;
        }

        this._targets.set(target, config);
        this._observer.observe(target);
    }

    /**
     * Stop observing an element
     * @param {HTMLElement} target - Element to unobserve
     */
    unobserve(target) {
        if (this._observer) {
            this._observer.unobserve(target);
        }
        this._targets.delete(target);
    }

    /**
     * Disconnect observer
     */
    disconnect() {
        if (this._observer) {
            this._observer.disconnect();
        }
        this._targets.clear();
    }
}

/**
 * Route-based code splitting helper
 */
export class RouteChunkLoader {
    constructor(lazyLoader) {
        this._loader = lazyLoader || new LazyLoader();
        this._routeMap = new Map();
        this._preloadQueue = [];
    }

    /**
     * Register a route with its chunk
     * @param {string} route - Route path
     * @param {string} chunkPath - Path to chunk module
     * @param {Object} options - Options
     */
    register(route, chunkPath, options = {}) {
        this._routeMap.set(route, {
            path: chunkPath,
            preload: options.preload || false,
            priority: options.priority || 0
        });

        if (options.preload) {
            this._preloadQueue.push({ route, priority: options.priority || 0 });
        }
    }

    /**
     * Load chunk for a route
     * @param {string} route - Route to load
     * @returns {Promise<*>}
     */
    async loadRoute(route) {
        const config = this._routeMap.get(route);
        if (!config) {
            throw new Error(`No chunk registered for route: ${route}`);
        }

        return this._loader.load(config.path);
    }

    /**
     * Preload all registered preload chunks
     */
    preloadAll() {
        // Sort by priority
        this._preloadQueue.sort((a, b) => b.priority - a.priority);

        // Preload in order
        this._preloadQueue.forEach(({ route }) => {
            const config = this._routeMap.get(route);
            if (config) {
                this._loader.preload(config.path);
            }
        });
    }

    /**
     * Preload on idle
     */
    preloadOnIdle() {
        if ('requestIdleCallback' in window) {
            requestIdleCallback(() => this.preloadAll(), { timeout: 2000 });
        } else {
            setTimeout(() => this.preloadAll(), 1000);
        }
    }
}

/**
 * Image lazy loader
 */
export class ImageLoader {
    constructor(options = {}) {
        this._options = {
            placeholder: 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"%3E%3C/svg%3E',
            errorImage: null,
            fadeIn: true,
            fadeInDuration: 300,
            ...options
        };
        this._observer = null;
        this._init();
    }

    /**
     * Initialize
     * @private
     */
    _init() {
        if (typeof IntersectionObserver === 'undefined') return;

        this._observer = new IntersectionObserver(
            entries => this._handleIntersection(entries),
            { rootMargin: '50px', threshold: 0.01 }
        );
    }

    /**
     * Handle intersection
     * @private
     */
    _handleIntersection(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                this._loadImage(entry.target);
                this._observer.unobserve(entry.target);
            }
        });
    }

    /**
     * Load image
     * @private
     */
    _loadImage(img) {
        const src = img.dataset.src;
        const srcset = img.dataset.srcset;

        if (!src) return;

        // Create temp image
        const tempImg = new Image();

        tempImg.onload = () => {
            if (srcset) img.srcset = srcset;
            img.src = src;

            if (this._options.fadeIn) {
                img.style.opacity = '0';
                img.style.transition = `opacity ${this._options.fadeInDuration}ms`;
                requestAnimationFrame(() => {
                    img.style.opacity = '1';
                });
            }

            img.classList.add('lazy-loaded');
            img.classList.remove('lazy-loading');
        };

        tempImg.onerror = () => {
            if (this._options.errorImage) {
                img.src = this._options.errorImage;
            }
            img.classList.add('lazy-error');
            img.classList.remove('lazy-loading');
        };

        img.classList.add('lazy-loading');
        tempImg.src = src;
    }

    /**
     * Observe images for lazy loading
     * @param {string} selector - CSS selector for images
     * @param {HTMLElement} container - Container element
     */
    observe(selector = 'img[data-src]', container = document) {
        const images = container.querySelectorAll(selector);

        images.forEach(img => {
            // Set placeholder
            if (!img.src) {
                img.src = this._options.placeholder;
            }

            if (this._observer) {
                this._observer.observe(img);
            } else {
                // Fallback: load all immediately
                this._loadImage(img);
            }
        });
    }

    /**
     * Disconnect observer
     */
    disconnect() {
        if (this._observer) {
            this._observer.disconnect();
        }
    }
}

// Singleton instances
let lazyLoader = null;
let imageLoader = null;

/**
 * Get lazy loader instance
 * @returns {LazyLoader}
 */
export function getLazyLoader() {
    if (!lazyLoader) {
        lazyLoader = new LazyLoader();
    }
    return lazyLoader;
}

/**
 * Get image loader instance
 * @returns {ImageLoader}
 */
export function getImageLoader() {
    if (!imageLoader) {
        imageLoader = new ImageLoader();
    }
    return imageLoader;
}

/**
 * Lazy load a component
 * @param {Function} importFn - Dynamic import function
 * @param {Object} _options - Options
 * @returns {Function}
 */
export function lazy(importFn, _options = {}) {
    let Component = null;
    let loadPromise = null;

    return {
        load() {
            if (Component) return Promise.resolve(Component);
            if (loadPromise) return loadPromise;

            loadPromise = importFn()
                .then(module => {
                    Component = module.default || module;
                    return Component;
                })
                .catch(error => {
                    loadPromise = null;
                    throw error;
                });

            return loadPromise;
        },

        async render(container, props = {}) {
            const Comp = await this.load();

            if (typeof Comp === 'function') {
                const instance = new Comp(props);
                if (typeof instance.render === 'function') {
                    return instance.render(container);
                }
            }

            return Comp;
        },

        isLoaded() {
            return Component !== null;
        }
    };
}

export default {
    LazyLoader,
    IntersectionLoader,
    RouteChunkLoader,
    ImageLoader,
    LoadState,
    getLazyLoader,
    getImageLoader,
    lazy
};
