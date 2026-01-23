# 📚 Frontend Developer Guide

## Bybit Strategy Tester v2 - Frontend Architecture

**Version:** 2.0.0
**Date:** December 2025

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Core Modules](#core-modules)
4. [Component System](#component-system)
5. [State Management](#state-management)
6. [Event System](#event-system)
7. [Routing](#routing)
8. [Service Layer](#service-layer)
9. [Performance Optimization](#performance-optimization)
10. [Testing](#testing)
11. [Build Process](#build-process)
12. [Best Practices](#best-practices)

---

## Architecture Overview

The frontend follows a modular architecture with clear separation of concerns:

```text
┌─────────────────────────────────────────────────────────────┐
│                        HTML Pages                            │
├─────────────────────────────────────────────────────────────┤
│                     Component Layer                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │
│  │  Modal  │ │  Toast  │ │DataTable│ │  Form   │ ...        │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘            │
├─────────────────────────────────────────────────────────────┤
│                       Core Layer                             │
│  ┌────────────┐ ┌──────────┐ ┌────────┐ ┌─────────────────┐ │
│  │StateManager│ │ EventBus │ │ Router │ │  ServiceLayer   │ │
│  └────────────┘ └──────────┘ └────────┘ └─────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                   Performance Layer                          │
│  ┌────────────┐ ┌─────────────┐ ┌───────────────────────┐   │
│  │ LazyLoader │ │ResourceHints│ │ PerformanceMonitor    │   │
│  └────────────┘ └─────────────┘ └───────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                        API Layer                             │
│                      (api.js)                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```text
frontend/
├── css/                    # Extracted CSS files
│   ├── variables.css       # CSS custom properties
│   ├── common.css          # Shared styles
│   ├── components.css      # Component styles
│   └── [page].css          # Page-specific styles
│
├── js/
│   ├── api.js              # API client
│   ├── navigation.js       # Navigation utilities
│   ├── security.js         # Security helpers
│   ├── utils.js            # Utility functions
│   │
│   ├── components/         # UI Components
│   │   ├── Component.js    # Base component class
│   │   ├── Modal.js        # Modal dialogs
│   │   ├── Toast.js        # Toast notifications
│   │   ├── DataTable.js    # Data tables
│   │   ├── Form.js         # Form handling
│   │   ├── Card.js         # Card containers
│   │   ├── Loader.js       # Loading indicators
│   │   └── index.js        # Component exports
│   │
│   ├── core/               # Core architecture
│   │   ├── StateManager.js # State management
│   │   ├── EventBus.js     # Event system
│   │   ├── Router.js       # Client-side routing
│   │   ├── ServiceLayer.js # API services
│   │   ├── LazyLoader.js   # Dynamic loading
│   │   ├── ResourceHints.js# Resource hints
│   │   ├── PerformanceMonitor.js # Metrics
│   │   └── index.js        # Core exports
│   │
│   ├── pages/              # Page-specific JS
│   │   ├── dashboard.js
│   │   ├── trading.js
│   │   └── ...
│   │
│   └── testing/            # Testing utilities
│       ├── TestUtils.js
│       ├── ComponentTests.js
│       ├── CoreTests.js
│       └── TestRunner.js
│
├── libs/                   # Third-party libraries
├── assets/                 # Static assets
├── dist/                   # Build output
├── vite.config.js          # Vite configuration
└── package.json
```

---

## Core Modules

### Importing Core Modules

```javascript
import {
    // State Management
    createStore, getStore, StateMiddleware,
    // Event System
    getEventBus, Events,
    // Router
    getRouter,
    // Services
    getServices, getService,
    // Performance
    getLazyLoader, initPerformanceMonitoring
} from './core/index.js';
```

### Quick Start

```javascript
import { initCore } from './core/index.js';

// Initialize all core systems
const { store, router, bus, services } = initCore({
    debug: true,
    routes: [
        { path: '/', component: HomeComponent },
        { path: '/dashboard', component: DashboardComponent }
    ],
    initialState: {
        user: null,
        theme: 'dark'
    }
});
```

---

## Component System

### Base Component

All components extend the base `Component` class:

```javascript
import { Component } from './components/Component.js';

class MyComponent extends Component {
    constructor(props) {
        super(props);
        this.state = { count: 0 };
    }

    // Lifecycle methods
    onMount() {
        console.log('Component mounted');
    }

    onUnmount() {
        console.log('Component will unmount');
    }

    onUpdate(prevState) {
        console.log('State updated', prevState, this.state);
    }

    // Render the component
    render(container) {
        this.element.innerHTML = `
            <div class="my-component">
                <h2>${this.props.title}</h2>
                <p>Count: ${this.state.count}</p>
                <button class="increment-btn">Increment</button>
            </div>
        `;

        // Bind events
        this.$('.increment-btn').addEventListener('click', () => {
            this.setState({ count: this.state.count + 1 });
        });

        if (container) {
            container.appendChild(this.element);
        }

        return this.element;
    }
}
```

### Available Components

#### Modal

```javascript
import { Modal } from './components/Modal.js';

// Create modal
const modal = new Modal({
    title: 'Confirm Action',
    content: '<p>Are you sure?</p>',
    size: 'md', // sm, md, lg, xl
    buttons: [
        { text: 'Cancel', variant: 'secondary', onClick: () => modal.close() },
        { text: 'Confirm', variant: 'primary', onClick: handleConfirm }
    ]
});

modal.open();

// Static helpers
const result = await Modal.confirm('Delete item?', 'This cannot be undone.');
await Modal.alert('Success', 'Operation completed.');
```

#### Toast

```javascript
import { Toast } from './components/Toast.js';

Toast.show('Item saved successfully', 'success');
Toast.show('Error occurred', 'error');
Toast.show('Please wait...', 'info', { duration: 0 }); // No auto-dismiss

// Shorthand methods
Toast.success('Saved!');
Toast.error('Failed!');
Toast.warning('Check input');
Toast.info('Loading...');
```

#### DataTable

```javascript
import { DataTable } from './components/DataTable.js';

const table = new DataTable({
    data: [...],
    columns: [
        { key: 'id', label: 'ID', sortable: true },
        { key: 'name', label: 'Name', sortable: true, searchable: true },
        { key: 'price', label: 'Price', format: (v) => `$${v.toFixed(2)}` },
        { key: 'actions', label: '', render: (row) => `<button>Edit</button>` }
    ],
    pagination: true,
    pageSize: 20,
    searchable: true,
    selectable: true,
    onRowClick: (row) => console.log('Clicked', row),
    onSelectionChange: (selected) => console.log('Selected', selected)
});

table.render(container);

// Methods
table.setData(newData);
table.sort('name', 'asc');
table.search('query');
table.goToPage(2);
```

#### Form

```javascript
import { Form } from './components/Form.js';

const form = new Form({
    fields: [
        { name: 'email', type: 'email', label: 'Email', required: true },
        { name: 'password', type: 'password', label: 'Password', required: true },
        { 
            name: 'role', 
            type: 'select', 
            label: 'Role',
            options: [
                { value: 'user', label: 'User' },
                { value: 'admin', label: 'Admin' }
            ]
        }
    ],
    onSubmit: (data) => {
        console.log('Form data:', data);
    },
    validation: {
        email: { pattern: /^[^\s@]+@[^\s@]+$/, message: 'Invalid email' }
    }
});

form.render(container);

// Methods
form.setValue('email', 'test@example.com');
form.getValue('email');
form.getValues();
form.validate();
form.reset();
```

---

## State Management

### Creating a Store

```javascript
import { createStore, StateMiddleware } from './core/StateManager.js';

const store = createStore({
    user: null,
    theme: 'dark',
    trading: {
        positions: [],
        balance: 0
    }
}, {
    persist: true,
    persistKey: 'app-state',
    devTools: true
});

// Add middleware
store.use(StateMiddleware.logger());
store.use(StateMiddleware.validator(validateState));
```

### Using the Store

```javascript
// Get state
const user = store.get('user');
const positions = store.get('trading.positions');

// Set state
store.set('user', { name: 'John' });
store.set('trading.balance', 1000);

// Subscribe to changes
const unsubscribe = store.subscribe('trading.positions', (newValue, oldValue) => {
    console.log('Positions changed:', newValue);
    updateUI(newValue);
});

// Batch updates
store.batch(() => {
    store.set('trading.positions', [...]);
    store.set('trading.balance', 5000);
}); // Triggers only one notification

// Reset to initial state
store.reset();
```

---

## Event System

### Using EventBus

```javascript
import { getEventBus, Events } from './core/EventBus.js';

const bus = getEventBus();

// Subscribe to events
bus.on('order:placed', (data) => {
    console.log('Order placed:', data);
});

// One-time subscription
bus.once('user:login', (user) => {
    console.log('User logged in:', user);
});

// Wildcard subscriptions
bus.on('order:*', (data) => {
    // Matches order:placed, order:cancelled, etc.
});

bus.on('*', (data) => {
    // All events
});

// Emit events
bus.emit('order:placed', { orderId: 123, symbol: 'BTCUSDT' });

// Unsubscribe
bus.off('order:placed', handler);

// Get event history
const history = bus.getHistory();
```

### Predefined Events

```javascript
import { Events } from './core/EventBus.js';

// Available events
Events.ORDER_PLACED
Events.ORDER_CANCELLED
Events.POSITION_OPEN
Events.POSITION_CLOSE
Events.BALANCE_UPDATE
Events.PRICE_UPDATE
Events.ROUTE_CHANGED
Events.STATE_CHANGED
Events.ERROR
Events.NOTIFICATION
```

---

## Routing

### Setting Up Routes

```javascript
import { getRouter } from './core/Router.js';

const router = getRouter();

// Add routes
router.addRoute('/', HomeComponent);
router.addRoute('/dashboard', DashboardComponent);
router.addRoute('/trading/:symbol', TradingComponent);
router.addRoute('/users/:id/orders', UserOrdersComponent);

// With options
router.addRoute('/admin', AdminComponent, {
    guards: [authGuard, adminGuard],
    meta: { requiresAuth: true }
});

// Navigation
router.navigate('/trading/BTCUSDT');
router.navigate('/dashboard', { query: { tab: 'overview' } });

// Get current route info
const current = router.current();
console.log(current.path, current.params, current.query);

// Listen to navigation
router.onNavigate((path, route) => {
    console.log('Navigated to:', path);
});
```

### Route Guards

```javascript
// Authentication guard
async function authGuard(to, from) {
    const user = store.get('user');
    if (!user) {
        router.navigate('/login');
        return false;
    }
    return true;
}

// Role-based guard
async function adminGuard(to, from) {
    const user = store.get('user');
    return user?.role === 'admin';
}
```

---

## Service Layer

### Using Services

```javascript
import { getServices, getService } from './core/ServiceLayer.js';

const services = getServices();
// or
const tradingService = getService('trading');

// Market data
const symbols = await services.market.getSymbols();
const price = await services.market.getPrice('BTCUSDT');
const klines = await services.market.getKlines('BTCUSDT', '1h', 100);

// Trading
const balance = await services.trading.getBalance();
const positions = await services.trading.getPositions();
await services.trading.placeOrder({ symbol: 'BTCUSDT', side: 'Buy', qty: 0.01 });

// Strategies
const strategies = await services.strategy.getStrategies();
const backtestResult = await services.strategy.runBacktest(strategyId, params);

// Analytics
const stats = await services.analytics.getDashboardStats();
const performance = await services.analytics.getPerformance('30d');
```

### Creating Custom Services

```javascript
import { BaseService } from './core/ServiceLayer.js';

class CustomService extends BaseService {
    async getCustomData() {
        return this.cached('custom-data', async () => {
            const response = await api.get('/custom/data');
            this.store?.set('customData', response);
            return response;
        }, 60000); // Cache for 1 minute
    }
}
```

---

## Performance Optimization

### Lazy Loading

```javascript
import { getLazyLoader, lazy } from './core/LazyLoader.js';

// Module lazy loading
const loader = getLazyLoader();
const module = await loader.load('./heavy-module.js');

// Component lazy loading
const HeavyComponent = lazy(() => import('./HeavyComponent.js'));
await HeavyComponent.load();
HeavyComponent.render(container);

// Image lazy loading
import { getImageLoader } from './core/LazyLoader.js';
const imageLoader = getImageLoader();
imageLoader.observe('img[data-src]');
```

### Resource Hints

```javascript
import { getResourceHints } from './core/ResourceHints.js';

const hints = getResourceHints();

// Preload critical resources
hints.preload('/js/critical.js', 'script');
hints.preload('/css/above-fold.css', 'style');

// Prefetch next page resources
hints.prefetch('/js/next-page.js', 'script');

// Preconnect to API
hints.preconnect('https://api.bybit.com', true);

// Module preload
hints.modulePreload('/js/feature.js');
```

### Performance Monitoring

```javascript
import { initPerformanceMonitoring } from './core/PerformanceMonitor.js';

const monitor = initPerformanceMonitoring({
    debug: true,
    reportEndpoint: '/api/metrics'
});

// Get Core Web Vitals
const vitals = monitor.getWebVitals();
console.log('LCP:', vitals.LCP);
console.log('FID:', vitals.FID);
console.log('CLS:', vitals.CLS);

// Custom marks
monitor.mark('feature-start');
// ... do work ...
monitor.mark('feature-end');
const duration = monitor.measure('feature', 'feature-start', 'feature-end');

// Get performance score
const score = monitor.getScore(); // 0-100
```

---

## Testing

### Running Tests

Open `test-runner.html` in browser or:

```javascript
import { runAllTests } from './testing/TestRunner.js';

const { allPassed, total } = await runAllTests({ verbose: true });
console.log(`${total.passed}/${total.passed + total.failed} tests passed`);
```

### Writing Tests

```javascript
import { describe, assert, mock, dom } from './testing/TestUtils.js';

export const myTests = describe('My Feature', ({ test, beforeEach, afterEach }) => {
    beforeEach(() => {
        dom.createContainer();
    });

    afterEach(() => {
        dom.clearContainer();
    });

    test('should do something', async () => {
        const result = myFunction();
        assert.equal(result, expected);
    });

    test('should handle async', async () => {
        const data = await fetchData();
        assert.ok(data.length > 0);
    });
});
```

### Assertions

```javascript
assert.ok(value);                    // Truthy
assert.equal(actual, expected);      // Strict equality
assert.deepEqual(obj1, obj2);        // Deep equality
assert.isNull(value);                // null/undefined
assert.isNotNull(value);             // Not null/undefined
assert.isType(value, 'string');      // Type check
assert.isInstance(obj, Class);       // Instance check
assert.contains(array, value);       // Array contains
assert.hasLength(array, 5);          // Array length
assert.throws(() => fn(), Error);    // Throws error
assert.elementExists('.selector');   // DOM element exists
```

### Mocking

```javascript
import { mock, spy, timers } from './testing/TestUtils.js';

// Mock function
const mockFn = mock(() => 'mocked');
mockFn();
assert.equal(mockFn.callCount(), 1);

// Spy on method
const fetchSpy = spy(api, 'get');
await api.get('/endpoint');
assert.ok(fetchSpy.calledWith('/endpoint'));
fetchSpy.restore();

// Mock timers
timers.install();
setTimeout(() => console.log('later'), 1000);
timers.tick(1000); // Fast-forward
timers.uninstall();
```

---

## Build Process

### Development

```bash
cd frontend
npm run dev      # Start dev server at localhost:3000
```

### Production Build

```bash
npm run build    # Build to dist/
npm run preview  # Preview production build
```

### Build Output

```text
dist/
├── *.html              # HTML pages
├── css/                # CSS files with SRI hashes
├── js/                 # JavaScript bundles
│   ├── pages/          # Page-specific JS
│   └── chunks/         # Code-split chunks
├── assets/             # Static assets
└── sri-manifest.json   # SRI hashes for CSP
```

---

## Best Practices

### Component Guidelines

1. **Single Responsibility**: One component, one purpose
2. **Props for Configuration**: Pass data via props
3. **State for Internal Data**: Use state for component-internal data
4. **Clean Up**: Always implement `onUnmount()` for cleanup
5. **Event Delegation**: Use `this.$()` for event binding

### State Management

1. **Normalize Data**: Keep state flat when possible
2. **Derive Data**: Compute derived data in components
3. **Batch Updates**: Use `store.batch()` for multiple updates
4. **Subscribe Selectively**: Subscribe to specific paths, not `*`

### Performance

1. **Lazy Load**: Use lazy loading for non-critical modules
2. **Preload Critical**: Preload critical resources
3. **Monitor**: Track Core Web Vitals
4. **Optimize Images**: Use `data-src` for lazy images

### Security

1. **CSP**: All scripts have SRI hashes
2. **Escape HTML**: Use `textContent` not `innerHTML` for user data
3. **Validate Input**: Validate all form inputs
4. **Secure API**: Use HTTPS, validate responses

---

## Quick Reference

### Import Map

```javascript
// Components
import { Modal, Toast, DataTable, Form, Card, Loader } from './components/index.js';

// Core
import { 
    createStore, getStore, 
    getEventBus, Events,
    getRouter,
    getServices
} from './core/index.js';

// Testing
import { describe, assert, mock } from './testing/TestUtils.js';
```

### Common Patterns

```javascript
// Initialize page
document.addEventListener('DOMContentLoaded', async () => {
    const { store, services } = initCore({ debug: true });
    
    // Load initial data
    const data = await services.analytics.getDashboardStats();
    store.set('dashboard', data);
    
    // Render UI
    const dashboard = new DashboardComponent();
    dashboard.render(document.getElementById('app'));
});

// Clean up on page leave
window.addEventListener('beforeunload', () => {
    store.persist();
    monitor.report();
});
```

---

**Questions?** See inline code documentation or check test files for usage examples.
