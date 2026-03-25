/**
 * 🧪 Test Runner - Bybit Strategy Tester v2
 *
 * Main entry point for running all frontend tests.
 *
 * Part of Phase 4: Testing & Documentation
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

import { runTests } from './TestUtils.js';
import { allComponentTests } from './ComponentTests.js';
import { allCoreTests } from './CoreTests.js';

/**
 * Run all tests
 */
export async function runAllTests(options = {}) {
    console.log('🧪 Running Frontend Tests...\n');
    console.log('='.repeat(50));

    const allSuites = [
        ...allCoreTests,
        ...allComponentTests
    ];

    const { allPassed, results, total } = await runTests(allSuites, options);

    console.log('\n' + '='.repeat(50));

    if (allPassed) {
        console.log('🎉 All tests passed!');
    } else {
        console.log('💥 Some tests failed.');
    }

    return { allPassed, results, total };
}

/**
 * Run specific test suite by name
 */
export async function runTestSuite(name, options = {}) {
    const allSuites = [...allCoreTests, ...allComponentTests];
    const suite = allSuites.find(s => s.name === name);

    if (!suite) {
        console.error(`Test suite "${name}" not found`);
        console.log('Available suites:', allSuites.map(s => s.name).join(', '));
        return null;
    }

    return runTests([suite], options);
}

/**
 * Run core module tests only
 */
export async function runCoreTests(options = {}) {
    console.log('🧪 Running Core Module Tests...\n');
    return runTests(allCoreTests, options);
}

/**
 * Run component tests only
 */
export async function runComponentTests(options = {}) {
    console.log('🧪 Running Component Tests...\n');
    return runTests(allComponentTests, options);
}

// Auto-run if loaded directly in browser
if (typeof window !== 'undefined') {
    window.TestRunner = {
        runAllTests,
        runTestSuite,
        runCoreTests,
        runComponentTests,
        allSuites: [...allCoreTests, ...allComponentTests]
    };

    // Check for auto-run flag
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('autorun') === 'true') {
        runAllTests({ verbose: urlParams.get('verbose') !== 'false' });
    }
}

export default {
    runAllTests,
    runTestSuite,
    runCoreTests,
    runComponentTests
};
