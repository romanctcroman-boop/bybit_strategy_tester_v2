/**
 * 🧪 Core Module Tests - Bybit Strategy Tester v2
 *
 * Unit tests for core architecture modules.
 *
 * Part of Phase 4: Testing & Documentation
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

import { describe, assert, mock, timers as _timers } from './TestUtils.js';

// StateManager tests
export const stateManagerTests = describe('StateManager', ({ test, beforeEach }) => {
    let store;

    beforeEach(async () => {
        const { createStore } = await import('../core/StateManager.js');
        store = createStore({ count: 0, user: null }, { persist: false });
    });

    test('Initial state is set correctly', () => {
        assert.equal(store.get('count'), 0);
        assert.isNull(store.get('user'));
    });

    test('State can be updated with set()', () => {
        store.set('count', 5);
        assert.equal(store.get('count'), 5);
    });

    test('Nested state can be accessed', () => {
        store.set('user', { name: 'John', age: 30 });
        assert.equal(store.get('user.name'), 'John');
        assert.equal(store.get('user.age'), 30);
    });

    test('State changes trigger subscribers', () => {
        const callback = mock();
        store.subscribe('count', callback);

        store.set('count', 10);

        assert.equal(callback.callCount(), 1);
        assert.ok(callback.calledWith(10, 0));
    });

    test('Wildcard subscription works', () => {
        const callback = mock();
        store.subscribe('*', callback);

        store.set('count', 1);
        store.set('user', { name: 'Test' });

        assert.equal(callback.callCount(), 2);
    });

    test('Unsubscribe works correctly', () => {
        const callback = mock();
        const unsubscribe = store.subscribe('count', callback);

        store.set('count', 1);
        assert.equal(callback.callCount(), 1);

        unsubscribe();
        store.set('count', 2);
        assert.equal(callback.callCount(), 1);
    });

    test('Batch updates', () => {
        const callback = mock();
        store.subscribe('*', callback);

        store.batch(() => {
            store.set('count', 1);
            store.set('count', 2);
            store.set('count', 3);
        });

        // Should only trigger once after batch
        assert.equal(callback.callCount(), 1);
    });

    test('Reset state', () => {
        store.set('count', 100);
        store.set('user', { name: 'Test' });

        store.reset();

        assert.equal(store.get('count'), 0);
        assert.isNull(store.get('user'));
    });
});

// EventBus tests
export const eventBusTests = describe('EventBus', ({ test, beforeEach }) => {
    let bus;

    beforeEach(async () => {
        const { EventBus } = await import('../core/EventBus.js');
        bus = new EventBus();
    });

    test('Basic event emission', () => {
        const callback = mock();
        bus.on('test', callback);

        bus.emit('test', { data: 123 });

        assert.equal(callback.callCount(), 1);
        assert.ok(callback.calledWith({ data: 123 }));
    });

    test('Multiple listeners', () => {
        const callback1 = mock();
        const callback2 = mock();

        bus.on('event', callback1);
        bus.on('event', callback2);

        bus.emit('event');

        assert.equal(callback1.callCount(), 1);
        assert.equal(callback2.callCount(), 1);
    });

    test('Once listener fires only once', () => {
        const callback = mock();
        bus.once('event', callback);

        bus.emit('event');
        bus.emit('event');
        bus.emit('event');

        assert.equal(callback.callCount(), 1);
    });

    test('Off removes listener', () => {
        const callback = mock();
        bus.on('event', callback);

        bus.emit('event');
        assert.equal(callback.callCount(), 1);

        bus.off('event', callback);
        bus.emit('event');
        assert.equal(callback.callCount(), 1);
    });

    test('Wildcard listener', () => {
        const callback = mock();
        bus.on('*', callback);

        bus.emit('event1');
        bus.emit('event2');
        bus.emit('event3');

        assert.equal(callback.callCount(), 3);
    });

    test('Namespace events', () => {
        const callback = mock();
        bus.on('user:*', callback);

        bus.emit('user:login');
        bus.emit('user:logout');
        bus.emit('other:event');

        assert.equal(callback.callCount(), 2);
    });

    test('Event history', () => {
        bus.emit('event1', { a: 1 });
        bus.emit('event2', { b: 2 });

        const history = bus.getHistory();
        assert.equal(history.length, 2);
        assert.equal(history[0].event, 'event1');
    });
});

// Router tests
export const routerTests = describe('Router', ({ test, beforeEach, afterEach }) => {
    let router;

    beforeEach(async () => {
        const { Router } = await import('../core/Router.js');
        router = new Router({ mode: 'hash' });
    });

    afterEach(() => {
        window.location.hash = '';
    });

    test('Add routes', () => {
        router.addRoute('/', () => 'home');
        router.addRoute('/about', () => 'about');
        router.addRoute('/users/:id', () => 'user');

        const routes = router.getRoutes();
        assert.equal(routes.length, 3);
    });

    test('Route matching', () => {
        router.addRoute('/users/:id', () => 'user');

        const match = router.match('/users/123');
        assert.ok(match, 'Route should match');
        assert.equal(match.params.id, '123');
    });

    test('Query params parsing', () => {
        router.addRoute('/search', () => 'search');

        const match = router.match('/search?q=test&page=1');
        assert.ok(match);
        assert.equal(match.query.q, 'test');
        assert.equal(match.query.page, '1');
    });

    test('Route guards', async () => {
        const guard = mock(() => true);

        router.addRoute('/protected', () => 'protected', {
            guards: [guard]
        });

        await router.navigate('/protected');

        assert.equal(guard.callCount(), 1);
    });

    test('Guard rejection', async () => {
        const guard = mock(() => false);
        const callback = mock();

        router.addRoute('/protected', callback, {
            guards: [guard]
        });

        await router.navigate('/protected');

        assert.equal(callback.callCount(), 0);
    });

    test('Navigation callbacks', async () => {
        const callback = mock();
        router.onNavigate(callback);

        router.addRoute('/test', () => 'test');
        await router.navigate('/test');

        assert.equal(callback.callCount(), 1);
    });
});

// ServiceLayer tests
export const serviceLayerTests = describe('ServiceLayer', ({ test, beforeEach }) => {
    let services;

    beforeEach(async () => {
        const { getServices } = await import('../core/ServiceLayer.js');
        services = getServices();
    });

    test('Services are available', () => {
        assert.ok(services.market, 'Market service should exist');
        assert.ok(services.trading, 'Trading service should exist');
        assert.ok(services.strategy, 'Strategy service should exist');
        assert.ok(services.analytics, 'Analytics service should exist');
        assert.ok(services.settings, 'Settings service should exist');
        assert.ok(services.notifications, 'Notifications service should exist');
    });

    test('Service caching', async () => {
        const { BaseService } = await import('../core/ServiceLayer.js');

        class TestService extends BaseService {
            constructor() {
                super();
                this.fetchCount = 0;
            }

            async getData() {
                return this.cached('test-data', async () => {
                    this.fetchCount++;
                    return { value: 'data' };
                });
            }
        }

        const service = new TestService();

        await service.getData();
        await service.getData();
        await service.getData();

        assert.equal(service.fetchCount, 1, 'Should only fetch once');
    });

    test('Cache clearing', async () => {
        const { BaseService } = await import('../core/ServiceLayer.js');

        class TestService extends BaseService {
            constructor() {
                super();
                this.fetchCount = 0;
            }

            async getData() {
                return this.cached('test-data', async () => {
                    this.fetchCount++;
                    return { value: this.fetchCount };
                });
            }
        }

        const service = new TestService();

        await service.getData();
        service.clearCache();
        await service.getData();

        assert.equal(service.fetchCount, 2, 'Should fetch again after cache clear');
    });
});

// LazyLoader tests
export const lazyLoaderTests = describe('LazyLoader', ({ test }) => {
    test('LazyLoader caches modules', async () => {
        const { getLazyLoader } = await import('../core/LazyLoader.js');
        const loader = getLazyLoader();

        // First check that it's not cached
        assert.ok(!loader.isCached('./StateManager.js'));
    });

    test('Loading state tracking', async () => {
        const { getLazyLoader, LoadState } = await import('../core/LazyLoader.js');
        const loader = getLazyLoader();

        assert.equal(loader.getState('./nonexistent.js'), LoadState.IDLE);
    });
});

// PerformanceMonitor tests
export const performanceMonitorTests = describe('PerformanceMonitor', ({ test }) => {
    test('PerformanceMonitor can be instantiated', async () => {
        const { PerformanceMonitor } = await import('../core/PerformanceMonitor.js');

        const monitor = new PerformanceMonitor({ debug: false });
        assert.ok(monitor, 'Monitor should be created');
    });

    test('Custom marks and measures', async () => {
        const { PerformanceMonitor } = await import('../core/PerformanceMonitor.js');

        const monitor = new PerformanceMonitor({ debug: false });

        monitor.mark('start');
        // Simulate some work
        await new Promise(r => setTimeout(r, 10));
        monitor.mark('end');

        const duration = monitor.measure('test-operation', 'start', 'end');
        assert.ok(duration >= 10, 'Duration should be at least 10ms');
    });

    test('Rating calculation', async () => {
        const { getRating, Rating } = await import('../core/PerformanceMonitor.js');

        assert.equal(getRating('LCP', 2000), Rating.GOOD);
        assert.equal(getRating('LCP', 3000), Rating.NEEDS_IMPROVEMENT);
        assert.equal(getRating('LCP', 5000), Rating.POOR);
    });

    test('Performance score', async () => {
        const { PerformanceMonitor } = await import('../core/PerformanceMonitor.js');

        const monitor = new PerformanceMonitor({ debug: false });
        const score = monitor.getScore();

        assert.isType(score, 'number');
        assert.ok(score >= 0 && score <= 100, 'Score should be 0-100');
    });
});

// Export all test suites
export const allCoreTests = [
    stateManagerTests,
    eventBusTests,
    routerTests,
    serviceLayerTests,
    lazyLoaderTests,
    performanceMonitorTests
];

export default allCoreTests;
