# 📖 API Reference

## Bybit Strategy Tester v2 - Frontend Modules

---

## Table of Contents

- [Component](#component)
- [Modal](#modal)
- [Toast](#toast)
- [DataTable](#datatable)
- [Form](#form)
- [StateManager](#statemanager)
- [EventBus](#eventbus)
- [Router](#router)
- [ServiceLayer](#servicelayer)
- [LazyLoader](#lazyloader)
- [PerformanceMonitor](#performancemonitor)
- [TestUtils](#testutils)

---

## Component

Base class for all UI components.

### Constructor

```javascript
new Component(props?: object)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| props | object | {} | Component properties |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| element | HTMLElement | Root DOM element |
| props | object | Component properties |
| state | object | Internal state |
| _mounted | boolean | Whether component is mounted |

### Methods

#### render(container?)

Render the component to the DOM.

```javascript
render(container?: HTMLElement): HTMLElement
```

#### setState(newState)

Update component state and trigger re-render.

```javascript
setState(newState: object): void
```

#### destroy()

Remove component and clean up.

```javascript
destroy(): void
```

#### $(selector)

Query element within component.

```javascript
$(selector: string): Element | null
```

#### $$(selector)

Query all elements within component.

```javascript
$$(selector: string): NodeList
```

### Lifecycle Methods

| Method | When Called |
|--------|-------------|
| onMount() | After render to DOM |
| onUnmount() | Before removal |
| onUpdate(prevState) | After state change |

---

## Modal

Dialog/modal component.

### Constructor

```javascript
new Modal(options: ModalOptions)
```

### ModalOptions

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| title | string | '' | Modal title |
| content | string\|HTMLElement | '' | Modal content |
| size | 'sm'\|'md'\|'lg'\|'xl' | 'md' | Modal size |
| closable | boolean | true | Show close button |
| backdrop | boolean\|'static' | true | Backdrop behavior |
| keyboard | boolean | true | Close on Escape |
| buttons | ModalButton[] | [] | Footer buttons |
| onOpen | function | null | Open callback |
| onClose | function | null | Close callback |

### ModalButton

| Property | Type | Description |
|----------|------|-------------|
| text | string | Button text |
| variant | string | Bootstrap variant (primary, secondary, etc.) |
| onClick | function | Click handler |
| dismiss | boolean | Close modal on click |

### Methods

#### open()

Open the modal.

```javascript
open(): void
```

#### close()

Close the modal.

```javascript
close(): void
```

#### setContent(content)

Update modal content.

```javascript
setContent(content: string | HTMLElement): void
```

### Static Methods

#### Modal.confirm(title, message, options?)

Show confirmation dialog.

```javascript
static confirm(title: string, message: string, options?: object): Promise<boolean>
```

#### Modal.alert(title, message, options?)

Show alert dialog.

```javascript
static alert(title: string, message: string, options?: object): Promise<void>
```

---

## Toast

Toast notification component.

### Static Methods

#### Toast.show(message, type?, options?)

Show a toast notification.

```javascript
static show(message: string, type?: string, options?: ToastOptions): Toast
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| message | string | - | Toast message |
| type | string | 'info' | 'success', 'error', 'warning', 'info' |
| options | object | {} | Additional options |

### ToastOptions

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| duration | number | 5000 | Auto-dismiss time (0 = never) |
| position | string | 'top-right' | Toast position |
| dismissible | boolean | true | Show close button |

### Shorthand Methods

```javascript
static success(message: string, options?: object): Toast
static error(message: string, options?: object): Toast
static warning(message: string, options?: object): Toast
static info(message: string, options?: object): Toast
```

---

## DataTable

Data table with sorting, pagination, and search.

### Constructor

```javascript
new DataTable(options: DataTableOptions)
```

### DataTableOptions

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| data | array | [] | Table data |
| columns | Column[] | [] | Column definitions |
| pagination | boolean | false | Enable pagination |
| pageSize | number | 10 | Rows per page |
| pageSizes | number[] | [10,25,50,100] | Page size options |
| searchable | boolean | false | Enable search |
| selectable | boolean | false | Enable row selection |
| sortable | boolean | false | Enable sorting |
| emptyMessage | string | 'No data' | Empty state message |
| onRowClick | function | null | Row click handler |
| onSelectionChange | function | null | Selection change handler |

### Column

| Property | Type | Description |
|----------|------|-------------|
| key | string | Data property key |
| label | string | Column header |
| sortable | boolean | Enable sorting |
| searchable | boolean | Include in search |
| width | string | Column width |
| align | string | Text alignment |
| format | function | Value formatter |
| render | function | Custom cell render |

### Methods

#### setData(data)

Update table data.

```javascript
setData(data: array): void
```

#### sort(column, direction?)

Sort by column.

```javascript
sort(column: string, direction?: 'asc' | 'desc'): void
```

#### search(query)

Filter by search query.

```javascript
search(query: string): void
```

#### goToPage(page)

Navigate to page.

```javascript
goToPage(page: number): void
```

#### getSelected()

Get selected rows.

```javascript
getSelected(): array
```

---

## Form

Form component with validation.

### Constructor

```javascript
new Form(options: FormOptions)
```

### FormOptions

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| fields | Field[] | [] | Form fields |
| layout | 'vertical'\|'horizontal'\|'inline' | 'vertical' | Form layout |
| submitText | string | 'Submit' | Submit button text |
| resetText | string | null | Reset button text |
| onSubmit | function | null | Submit handler |
| validation | object | {} | Validation rules |

### Field

| Property | Type | Description |
|----------|------|-------------|
| name | string | Field name |
| type | string | Input type |
| label | string | Field label |
| placeholder | string | Placeholder text |
| required | boolean | Is required |
| disabled | boolean | Is disabled |
| value | any | Initial value |
| options | array | Select/radio options |
| validation | object | Field validation |

### Methods

#### setValue(name, value)

Set field value.

```javascript
setValue(name: string, value: any): void
```

#### getValue(name)

Get field value.

```javascript
getValue(name: string): any
```

#### getValues()

Get all values.

```javascript
getValues(): object
```

#### validate()

Validate all fields.

```javascript
validate(): boolean
```

#### reset()

Reset form to initial values.

```javascript
reset(): void
```

#### submit()

Trigger form submission.

```javascript
submit(): void
```

---

## StateManager

Redux-like state management.

### createStore(initialState, options?)

Create a new store.

```javascript
createStore(initialState: object, options?: StoreOptions): Store
```

### StoreOptions

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| persist | boolean | false | Persist to localStorage |
| persistKey | string | 'app-state' | localStorage key |
| devTools | boolean | false | Enable devtools |

### Store Methods

#### get(path)

Get state value by path.

```javascript
get(path: string): any
```

#### set(path, value)

Set state value.

```javascript
set(path: string, value: any): void
```

#### subscribe(path, callback)

Subscribe to state changes.

```javascript
subscribe(path: string, callback: function): function
```

Returns unsubscribe function.

#### batch(fn)

Batch multiple updates.

```javascript
batch(fn: function): void
```

#### reset()

Reset to initial state.

```javascript
reset(): void
```

#### use(middleware)

Add middleware.

```javascript
use(middleware: function): void
```

### StateMiddleware

#### StateMiddleware.logger()

Log state changes.

#### StateMiddleware.validator(fn)

Validate state changes.

---

## EventBus

Publish/subscribe event system.

### Methods

#### on(event, callback)

Subscribe to event.

```javascript
on(event: string, callback: function): function
```

#### once(event, callback)

Subscribe once.

```javascript
once(event: string, callback: function): function
```

#### off(event, callback?)

Unsubscribe from event.

```javascript
off(event: string, callback?: function): void
```

#### emit(event, data?)

Emit event.

```javascript
emit(event: string, data?: any): void
```

#### getHistory()

Get event history.

```javascript
getHistory(): EventRecord[]
```

### Wildcards

- `*` - Match all events
- `namespace:*` - Match all events in namespace

---

## Router

Client-side routing.

### Methods

#### addRoute(path, component, options?)

Add a route.

```javascript
addRoute(path: string, component: any, options?: RouteOptions): void
```

### RouteOptions

| Option | Type | Description |
|--------|------|-------------|
| guards | function[] | Route guards |
| meta | object | Route metadata |
| redirect | string | Redirect to path |

#### navigate(path, options?)

Navigate to path.

```javascript
navigate(path: string, options?: object): Promise<void>
```

#### current()

Get current route.

```javascript
current(): Route
```

#### onNavigate(callback)

Listen to navigation.

```javascript
onNavigate(callback: function): function
```

#### back()

Go back in history.

```javascript
back(): void
```

#### forward()

Go forward in history.

```javascript
forward(): void
```

---

## ServiceLayer

API service abstraction.

### Services

| Service | Description |
|---------|-------------|
| market | Market data (symbols, prices, klines) |
| trading | Trading operations (orders, positions) |
| strategy | Strategy management and backtesting |
| analytics | Performance analytics |
| settings | User settings |
| notifications | Notifications |

### Market Service

```javascript
getSymbols(): Promise<string[]>
getPrice(symbol): Promise<object>
getTicker(symbol): Promise<object>
getKlines(symbol, interval, limit?): Promise<array>
getOrderBook(symbol, limit?): Promise<object>
```

### Trading Service

```javascript
getBalance(): Promise<object>
getPositions(): Promise<array>
getOrders(): Promise<array>
placeOrder(order): Promise<object>
cancelOrder(orderId): Promise<object>
closePosition(symbol): Promise<object>
```

### Strategy Service

```javascript
getStrategies(): Promise<array>
getStrategy(id): Promise<object>
createStrategy(data): Promise<object>
updateStrategy(id, data): Promise<object>
deleteStrategy(id): Promise<void>
runBacktest(strategyId, params): Promise<object>
```

---

## LazyLoader

Dynamic module loading.

### Methods

#### load(modulePath, options?)

Load module dynamically.

```javascript
load(modulePath: string, options?: object): Promise<module>
```

#### preload(modulePath)

Preload module.

```javascript
preload(modulePath: string): void
```

#### isCached(modulePath)

Check if module is cached.

```javascript
isCached(modulePath: string): boolean
```

### lazy(importFn)

Create lazy component.

```javascript
lazy(importFn: function): LazyComponent
```

---

## PerformanceMonitor

Core Web Vitals tracking.

### Methods

#### init()

Initialize monitoring.

```javascript
init(): void
```

#### getWebVitals()

Get Core Web Vitals.

```javascript
getWebVitals(): WebVitals
```

### WebVitals

| Metric | Description | Good | Needs Improvement |
|--------|-------------|------|-------------------|
| LCP | Largest Contentful Paint | ≤2.5s | ≤4s |
| FID | First Input Delay | ≤100ms | ≤300ms |
| CLS | Cumulative Layout Shift | ≤0.1 | ≤0.25 |
| FCP | First Contentful Paint | ≤1.8s | ≤3s |
| TTFB | Time to First Byte | ≤800ms | ≤1.8s |
| INP | Interaction to Next Paint | ≤200ms | ≤500ms |

#### mark(name)

Create performance mark.

```javascript
mark(name: string): void
```

#### measure(name, startMark, endMark)

Measure between marks.

```javascript
measure(name: string, startMark: string, endMark: string): number
```

#### getScore()

Get overall performance score (0-100).

```javascript
getScore(): number
```

---

## TestUtils

Testing utilities.

### assert

Assertion helpers.

```javascript
assert.ok(value)
assert.equal(actual, expected)
assert.deepEqual(actual, expected)
assert.isNull(value)
assert.isNotNull(value)
assert.isType(value, type)
assert.isInstance(value, constructor)
assert.contains(array, value)
assert.hasLength(array, length)
assert.throws(fn, errorType?)
assert.elementExists(selector)
```

### mock(implementation?)

Create mock function.

```javascript
const fn = mock(() => 'result');
fn();
fn.callCount(); // 1
fn.calledWith('arg'); // boolean
fn.lastCall(); // { args, result }
fn.reset();
```

### describe(name, setupFn)

Create test suite.

```javascript
const suite = describe('My Tests', ({ test, beforeEach, afterEach }) => {
    test('should work', () => {
        assert.ok(true);
    });
});
```

### runTests(suites)

Run test suites.

```javascript
const { allPassed, total } = await runTests([suite1, suite2]);
```

---

*Last updated: December 2025*
