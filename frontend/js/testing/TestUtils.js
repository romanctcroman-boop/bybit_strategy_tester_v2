/**
 * 🧪 Test Utilities - Bybit Strategy Tester v2
 *
 * Lightweight testing utilities for frontend components.
 * Provides assertion helpers, mocking, and test runners.
 *
 * Part of Phase 4: Testing & Documentation
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

/**
 * Test result status
 */
export const TestStatus = {
    PASS: 'pass',
    FAIL: 'fail',
    SKIP: 'skip',
    PENDING: 'pending'
};

/**
 * Assertion Error class
 */
export class AssertionError extends Error {
    constructor(message, expected, actual) {
        super(message);
        this.name = 'AssertionError';
        this.expected = expected;
        this.actual = actual;
    }
}

/**
 * Assertion helpers
 */
export const assert = {
    /**
     * Assert value is truthy
     */
    ok(value, message = 'Expected value to be truthy') {
        if (!value) {
            throw new AssertionError(message, true, value);
        }
    },

    /**
     * Assert strict equality
     */
    equal(actual, expected, message) {
        if (actual !== expected) {
            throw new AssertionError(
                message || `Expected ${expected}, got ${actual}`,
                expected,
                actual
            );
        }
    },

    /**
     * Assert deep equality
     */
    deepEqual(actual, expected, message) {
        const actualStr = JSON.stringify(actual);
        const expectedStr = JSON.stringify(expected);
        if (actualStr !== expectedStr) {
            throw new AssertionError(
                message || 'Objects not deeply equal',
                expected,
                actual
            );
        }
    },

    /**
     * Assert value is null or undefined
     */
    isNull(value, message = 'Expected null or undefined') {
        if (value != null) {
            throw new AssertionError(message, null, value);
        }
    },

    /**
     * Assert value is not null or undefined
     */
    isNotNull(value, message = 'Expected non-null value') {
        if (value == null) {
            throw new AssertionError(message, 'non-null', value);
        }
    },

    /**
     * Assert value is of type
     */
    isType(value, type, message) {
        const actualType = typeof value;
        if (actualType !== type) {
            throw new AssertionError(
                message || `Expected type ${type}, got ${actualType}`,
                type,
                actualType
            );
        }
    },

    /**
     * Assert value is instance of class
     */
    isInstance(value, constructor, message) {
        if (!(value instanceof constructor)) {
            throw new AssertionError(
                message || `Expected instance of ${constructor.name}`,
                constructor.name,
                value?.constructor?.name || typeof value
            );
        }
    },

    /**
     * Assert array contains value
     */
    contains(array, value, message) {
        if (!array.includes(value)) {
            throw new AssertionError(
                message || `Array does not contain ${value}`,
                value,
                array
            );
        }
    },

    /**
     * Assert array length
     */
    hasLength(array, length, message) {
        if (array.length !== length) {
            throw new AssertionError(
                message || `Expected length ${length}, got ${array.length}`,
                length,
                array.length
            );
        }
    },

    /**
     * Assert throws error
     */
    throws(fn, errorType, message) {
        let threw = false;
        let error = null;

        try {
            fn();
        } catch (e) {
            threw = true;
            error = e;
        }

        if (!threw) {
            throw new AssertionError(
                message || 'Expected function to throw',
                'Error',
                'No error'
            );
        }

        if (errorType && !(error instanceof errorType)) {
            throw new AssertionError(
                message || `Expected ${errorType.name}, got ${error.constructor.name}`,
                errorType.name,
                error.constructor.name
            );
        }
    },

    /**
     * Assert async function throws
     */
    async throwsAsync(fn, errorType, message) {
        let threw = false;
        let error = null;

        try {
            await fn();
        } catch (e) {
            threw = true;
            error = e;
        }

        if (!threw) {
            throw new AssertionError(
                message || 'Expected async function to throw',
                'Error',
                'No error'
            );
        }

        if (errorType && !(error instanceof errorType)) {
            throw new AssertionError(
                message || `Expected ${errorType.name}`,
                errorType.name,
                error?.constructor?.name
            );
        }
    },

    /**
     * Assert element exists in DOM
     */
    elementExists(selector, message) {
        const el = document.querySelector(selector);
        if (!el) {
            throw new AssertionError(
                message || `Element ${selector} not found`,
                'Element',
                null
            );
        }
        return el;
    },

    /**
     * Assert element has text
     */
    elementHasText(selector, text, message) {
        const el = document.querySelector(selector);
        if (!el || !el.textContent.includes(text)) {
            throw new AssertionError(
                message || `Element ${selector} does not contain "${text}"`,
                text,
                el?.textContent
            );
        }
    }
};

/**
 * Test Suite class
 */
export class TestSuite {
    constructor(name) {
        this.name = name;
        this.tests = [];
        this.beforeEachFn = null;
        this.afterEachFn = null;
        this.beforeAllFn = null;
        this.afterAllFn = null;
    }

    /**
     * Add a test
     */
    test(name, fn, options = {}) {
        this.tests.push({
            name,
            fn,
            skip: options.skip || false,
            only: options.only || false,
            timeout: options.timeout || 5000
        });
        return this;
    }

    /**
     * Add a skipped test
     */
    skip(name, fn) {
        return this.test(name, fn, { skip: true });
    }

    /**
     * Add an only test (run only this)
     */
    only(name, fn) {
        return this.test(name, fn, { only: true });
    }

    /**
     * Set before each hook
     */
    beforeEach(fn) {
        this.beforeEachFn = fn;
        return this;
    }

    /**
     * Set after each hook
     */
    afterEach(fn) {
        this.afterEachFn = fn;
        return this;
    }

    /**
     * Set before all hook
     */
    beforeAll(fn) {
        this.beforeAllFn = fn;
        return this;
    }

    /**
     * Set after all hook
     */
    afterAll(fn) {
        this.afterAllFn = fn;
        return this;
    }

    /**
     * Run all tests
     */
    async run() {
        const results = {
            suite: this.name,
            passed: 0,
            failed: 0,
            skipped: 0,
            tests: [],
            duration: 0
        };

        const startTime = performance.now();

        // Check for only tests
        const hasOnly = this.tests.some(t => t.only);
        const testsToRun = hasOnly
            ? this.tests.filter(t => t.only)
            : this.tests;

        // Run beforeAll
        if (this.beforeAllFn) {
            try {
                await this.beforeAllFn();
            } catch (error) {
                console.error(`beforeAll failed: ${error.message}`);
            }
        }

        // Run tests
        for (const test of testsToRun) {
            const testResult = {
                name: test.name,
                status: TestStatus.PENDING,
                duration: 0,
                error: null
            };

            if (test.skip) {
                testResult.status = TestStatus.SKIP;
                results.skipped++;
            } else {
                const testStart = performance.now();

                try {
                    // Run beforeEach
                    if (this.beforeEachFn) {
                        await this.beforeEachFn();
                    }

                    // Run test with timeout
                    await Promise.race([
                        test.fn(),
                        new Promise((_, reject) =>
                            setTimeout(() => reject(new Error('Test timeout')), test.timeout)
                        )
                    ]);

                    testResult.status = TestStatus.PASS;
                    results.passed++;

                    // Run afterEach
                    if (this.afterEachFn) {
                        await this.afterEachFn();
                    }
                } catch (error) {
                    testResult.status = TestStatus.FAIL;
                    testResult.error = {
                        message: error.message,
                        expected: error.expected,
                        actual: error.actual,
                        stack: error.stack
                    };
                    results.failed++;
                }

                testResult.duration = performance.now() - testStart;
            }

            results.tests.push(testResult);
        }

        // Run afterAll
        if (this.afterAllFn) {
            try {
                await this.afterAllFn();
            } catch (error) {
                console.error(`afterAll failed: ${error.message}`);
            }
        }

        results.duration = performance.now() - startTime;
        return results;
    }
}

/**
 * Mock function creator
 */
export function mock(implementation = () => {}) {
    const calls = [];

    const mockFn = function (...args) {
        const call = {
            args,
            timestamp: Date.now(),
            result: undefined,
            error: undefined
        };

        try {
            call.result = implementation.apply(this, args);
            calls.push(call);
            return call.result;
        } catch (error) {
            call.error = error;
            calls.push(call);
            throw error;
        }
    };

    mockFn.calls = calls;
    mockFn.callCount = () => calls.length;
    mockFn.calledWith = (...args) => calls.some(c =>
        JSON.stringify(c.args) === JSON.stringify(args)
    );
    mockFn.lastCall = () => calls[calls.length - 1];
    mockFn.reset = () => { calls.length = 0; };
    mockFn.mockImplementation = (fn) => {
        implementation = fn;
        return mockFn;
    };
    mockFn.mockReturnValue = (value) => {
        implementation = () => value;
        return mockFn;
    };
    mockFn.mockResolvedValue = (value) => {
        implementation = () => Promise.resolve(value);
        return mockFn;
    };
    mockFn.mockRejectedValue = (error) => {
        implementation = () => Promise.reject(error);
        return mockFn;
    };

    return mockFn;
}

/**
 * Spy on object method
 */
export function spy(object, method) {
    const original = object[method];
    const mockFn = mock(function (...args) {
        return original.apply(this, args);
    });

    object[method] = mockFn;
    mockFn.restore = () => {
        object[method] = original;
    };

    return mockFn;
}

/**
 * Timer mocks
 */
export const timers = {
    _original: {},
    _timers: [],
    _now: 0,

    install() {
        this._original = {
            setTimeout: window.setTimeout.bind(window),
            clearTimeout: window.clearTimeout.bind(window),
            setInterval: window.setInterval.bind(window),
            clearInterval: window.clearInterval.bind(window),
            Date: window.Date
        };

        window.setTimeout = (fn, delay) => {
            const id = this._timers.length;
            this._timers.push({ fn, time: this._now + delay, type: 'timeout', id });
            return id;
        };

        window.clearTimeout = (id) => {
            this._timers = this._timers.filter(t => t.id !== id);
        };

        window.setInterval = (fn, delay) => {
            const id = this._timers.length;
            this._timers.push({ fn, time: this._now + delay, delay, type: 'interval', id });
            return id;
        };

        window.clearInterval = (id) => {
            this._timers = this._timers.filter(t => t.id !== id);
        };

        const self = this;
        window.Date = class extends Date {
            constructor(...args) {
                if (args.length === 0) {
                    super(self._now);
                } else {
                    super(...args);
                }
            }
            static now() {
                return self._now;
            }
        };
    },

    uninstall() {
        Object.assign(window, this._original);
        this._timers = [];
        this._now = 0;
    },

    tick(ms) {
        this._now += ms;

        const ready = this._timers
            .filter(t => t.time <= this._now)
            .sort((a, b) => a.time - b.time);

        for (const timer of ready) {
            timer.fn();
            if (timer.type === 'interval') {
                timer.time += timer.delay;
            } else {
                this._timers = this._timers.filter(t => t.id !== timer.id);
            }
        }
    },

    runAll() {
        while (this._timers.length > 0) {
            const next = Math.min(...this._timers.map(t => t.time));
            this.tick(next - this._now);
        }
    }
};

/**
 * DOM test helpers
 */
export const dom = {
    /**
     * Create test container
     */
    createContainer(id = 'test-container') {
        let container = document.getElementById(id);
        if (!container) {
            container = document.createElement('div');
            container.id = id;
            document.body.appendChild(container);
        }
        return container;
    },

    /**
     * Clear test container
     */
    clearContainer(id = 'test-container') {
        const container = document.getElementById(id);
        if (container) {
            container.innerHTML = '';
        }
    },

    /**
     * Remove test container
     */
    removeContainer(id = 'test-container') {
        const container = document.getElementById(id);
        if (container) {
            container.remove();
        }
    },

    /**
     * Simulate click event
     */
    click(element) {
        element.dispatchEvent(new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
            view: window
        }));
    },

    /**
     * Simulate input event
     */
    input(element, value) {
        element.value = value;
        element.dispatchEvent(new Event('input', { bubbles: true }));
    },

    /**
     * Simulate keyboard event
     */
    keydown(element, key, options = {}) {
        element.dispatchEvent(new KeyboardEvent('keydown', {
            key,
            bubbles: true,
            ...options
        }));
    },

    /**
     * Wait for element
     */
    async waitFor(selector, timeout = 3000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            const el = document.querySelector(selector);
            if (el) return el;
            await new Promise(r => setTimeout(r, 50));
        }
        throw new Error(`Element ${selector} not found after ${timeout}ms`);
    },

    /**
     * Wait for condition
     */
    async waitUntil(condition, timeout = 3000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            if (await condition()) return true;
            await new Promise(r => setTimeout(r, 50));
        }
        throw new Error(`Condition not met after ${timeout}ms`);
    }
};

/**
 * Test Reporter
 */
export class TestReporter {
    constructor(options = {}) {
        this.options = {
            verbose: true,
            colors: true,
            ...options
        };
    }

    /**
     * Report test results
     */
    report(results) {
        console.group(`📋 ${results.suite}`);

        results.tests.forEach(test => {
            const icon = this._getStatusIcon(test.status);
            const duration = test.duration.toFixed(2);

            if (test.status === TestStatus.FAIL) {
                console.error(`${icon} ${test.name} (${duration}ms)`);
                if (test.error) {
                    console.error(`   └─ ${test.error.message}`);
                    if (this.options.verbose && test.error.expected !== undefined) {
                        console.error(`      Expected: ${JSON.stringify(test.error.expected)}`);
                        console.error(`      Actual: ${JSON.stringify(test.error.actual)}`);
                    }
                }
            } else if (test.status === TestStatus.SKIP) {
                console.warn(`${icon} ${test.name} (skipped)`);
            } else {
                console.log(`${icon} ${test.name} (${duration}ms)`);
            }
        });

        console.log('');
        console.log(`✅ Passed: ${results.passed}`);
        console.log(`❌ Failed: ${results.failed}`);
        console.log(`⏭️ Skipped: ${results.skipped}`);
        console.log(`⏱️ Duration: ${results.duration.toFixed(2)}ms`);

        console.groupEnd();

        return results.failed === 0;
    }

    _getStatusIcon(status) {
        switch (status) {
        case TestStatus.PASS: return '✅';
        case TestStatus.FAIL: return '❌';
        case TestStatus.SKIP: return '⏭️';
        default: return '⏳';
        }
    }
}

/**
 * Create and run test suite
 */
export function describe(name, setupFn) {
    const suite = new TestSuite(name);
    setupFn({
        test: suite.test.bind(suite),
        it: suite.test.bind(suite),
        skip: suite.skip.bind(suite),
        only: suite.only.bind(suite),
        beforeEach: suite.beforeEach.bind(suite),
        afterEach: suite.afterEach.bind(suite),
        beforeAll: suite.beforeAll.bind(suite),
        afterAll: suite.afterAll.bind(suite)
    });
    return suite;
}

/**
 * Run multiple test suites
 */
export async function runTests(suites, options = {}) {
    const reporter = new TestReporter(options);
    const allResults = [];
    let allPassed = true;

    for (const suite of suites) {
        const results = await suite.run();
        allResults.push(results);
        if (!reporter.report(results)) {
            allPassed = false;
        }
    }

    // Summary
    console.log('\n📊 Test Summary:');
    const total = {
        passed: allResults.reduce((sum, r) => sum + r.passed, 0),
        failed: allResults.reduce((sum, r) => sum + r.failed, 0),
        skipped: allResults.reduce((sum, r) => sum + r.skipped, 0),
        duration: allResults.reduce((sum, r) => sum + r.duration, 0)
    };

    console.log(`   Total: ${total.passed + total.failed + total.skipped} tests`);
    console.log(`   Passed: ${total.passed}`);
    console.log(`   Failed: ${total.failed}`);
    console.log(`   Duration: ${total.duration.toFixed(2)}ms`);

    return { allPassed, results: allResults, total };
}

export default {
    TestSuite,
    TestStatus,
    AssertionError,
    assert,
    mock,
    spy,
    timers,
    dom,
    describe,
    runTests,
    TestReporter
};
