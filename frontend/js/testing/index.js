/**
 * 🧪 Testing Module Exports - Bybit Strategy Tester v2
 *
 * Central export point for testing utilities.
 *
 * Part of Phase 4: Testing & Documentation
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// Test utilities
export {
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
} from './TestUtils.js';

// Test runner
export {
    runAllTests,
    runTestSuite,
    runCoreTests,
    runComponentTests
} from './TestRunner.js';

// Test suites
export { allComponentTests } from './ComponentTests.js';
export { allCoreTests } from './CoreTests.js';

export default {
    // Re-export main runner functions
    runAllTests: async (options) => {
        const { runAllTests } = await import('./TestRunner.js');
        return runAllTests(options);
    }
};
