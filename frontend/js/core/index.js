/**
 * 🧠 Core Module Exports - Bybit Strategy Tester v2
 *
 * Central export point for all core architecture modules.
 *
 * Part of Phase 2-3: Architecture & Performance
 *
 * @version 2.0.0
 * @date 2025-12-21
 */

// State Management
import {
    StateManager,
    createStore,
    getStore,
    StateMiddleware
} from './StateManager.js';

// Event System
import {
    EventBus,
    getEventBus,
    Events
} from './EventBus.js';

// Router
import {
    Router,
    getRouter
} from './Router.js';

// Service Layer
import {
    BaseService,
    MarketService,
    TradingService,
    StrategyService,
    AnalyticsService,
    SettingsService,
    NotificationService,
    getServices,
    getService
} from './ServiceLayer.js';

// Lazy Loading (Phase 3)
import {
    LazyLoader,
    IntersectionLoader,
    RouteChunkLoader,
    ImageLoader,
    LoadState,
    getLazyLoader,
    getImageLoader,
    lazy
} from './LazyLoader.js';

// Resource Hints (Phase 3)
import {
    ResourceHints,
    FetchPriority,
    HintType,
    ResourceType,
    getResourceHints,
    initResourceHints
} from './ResourceHints.js';

// Performance Monitoring (Phase 3)
import {
    PerformanceMonitor,
    MemoryMonitor,
    Thresholds,
    Rating,
    getRating,
    getPerformanceMonitor,
    initPerformanceMonitoring
} from './PerformanceMonitor.js';

// Re-export all
export {
    // State Management
    StateManager,
    createStore,
    getStore,
    StateMiddleware,
    // Event System
    EventBus,
    getEventBus,
    Events,
    // Router
    Router,
    getRouter,
    // Service Layer
    BaseService,
    MarketService,
    TradingService,
    StrategyService,
    AnalyticsService,
    SettingsService,
    NotificationService,
    getServices,
    getService,
    // Lazy Loading (Phase 3)
    LazyLoader,
    IntersectionLoader,
    RouteChunkLoader,
    ImageLoader,
    LoadState,
    getLazyLoader,
    getImageLoader,
    lazy,
    // Resource Hints (Phase 3)
    ResourceHints,
    FetchPriority,
    HintType,
    ResourceType,
    getResourceHints,
    initResourceHints,
    // Performance Monitoring (Phase 3)
    PerformanceMonitor,
    MemoryMonitor,
    Thresholds,
    Rating,
    getRating,
    getPerformanceMonitor,
    initPerformanceMonitoring
};

// Convenience function to initialize all core systems
let initialized = false;

/**
 * Initialize core systems
 * @param {Object} options - Configuration options
 * @returns {Object} Initialized core systems
 */
export function initCore(options = {}) {
    if (initialized) {
        console.warn('Core systems already initialized');
        return getCoreInstances();
    }

    const {
        routes = [],
        initialState = {},
        middleware = [],
        debug = false
    } = options;

    // Create store
    const store = createStore(initialState, {
        devTools: debug,
        persist: true,
        persistKey: 'bybit-strategy-tester'
    });

    // Add middleware
    if (debug) {
        store.use(StateMiddleware.logger());
    }
    middleware.forEach(m => store.use(m));

    // Initialize router
    const router = getRouter();
    routes.forEach(route => router.addRoute(route.path, route.component, route.options));

    // Get event bus
    const bus = getEventBus();

    // Get services
    const services = getServices();

    // Connect systems
    router.onNavigate((path, route) => {
        store.set('router.currentPath', path);
        store.set('router.currentRoute', route?.path || null);
        bus.emit(Events.ROUTE_CHANGED, { path, route });
    });

    initialized = true;

    return { store, router, bus, services };
}

/**
 * Get all initialized core instances
 * @returns {Object}
 */
export function getCoreInstances() {
    return {
        store: getStore(),
        bus: getEventBus(),
        router: getRouter(),
        services: getServices()
    };
}

export default {
    initCore,
    getCoreInstances
};
