/**
 * 🧪 Security Tests - Bybit Strategy Tester v2
 *
 * Tests for security modules:
 * - Sanitizer (XSS protection)
 * - ApiClient (CSRF)
 * - WebSocketClient (reconnection)
 * - CSP generation
 *
 * @version 1.0.0
 * @date 2026-01-28
 */

import { Sanitizer, escapeHtml } from "../core/Sanitizer.js";
import { ApiClient, ApiError } from "../core/ApiClient.js";
import {
  WebSocketClient,
  WS_STATE,
  WS_EVENTS,
} from "../core/WebSocketClient.js";
import { generateCSP, getNonce } from "../security.js";

// ============================================
// TEST UTILITIES
// ============================================

let testResults = {
  passed: 0,
  failed: 0,
  errors: [],
};

function assert(condition, message) {
  if (condition) {
    testResults.passed++;
    console.log(`  ✅ ${message}`);
  } else {
    testResults.failed++;
    testResults.errors.push(message);
    console.error(`  ❌ ${message}`);
  }
}

function assertEqual(actual, expected, message) {
  const passed = actual === expected;
  if (!passed) {
    console.error(`    Expected: ${expected}`);
    console.error(`    Actual: ${actual}`);
  }
  assert(passed, message);
}

function assertContains(str, substring, message) {
  assert(str.includes(substring), message);
}

function assertNotContains(str, substring, message) {
  assert(!str.includes(substring), message);
}

function describe(name, fn) {
  console.log(`\n📦 ${name}`);
  fn();
}

function it(name, fn) {
  try {
    fn();
  } catch (error) {
    testResults.failed++;
    testResults.errors.push(`${name}: ${error.message}`);
    console.error(`  ❌ ${name}: ${error.message}`);
  }
}

// ============================================
// SANITIZER TESTS
// ============================================

describe("Sanitizer", () => {
  const sanitizer = new Sanitizer();

  it("should remove script tags", () => {
    const input = '<p>Hello</p><script>alert("xss")</script><p>World</p>';
    const output = sanitizer.sanitize(input);
    assertNotContains(output, "script", "Script tag removed");
    assertContains(output, "<p>Hello</p>", "Safe content preserved");
  });

  it("should remove onclick handlers", () => {
    const input = '<button onclick="alert(1)">Click</button>';
    const output = sanitizer.sanitize(input);
    assertNotContains(output, "onclick", "onclick removed");
  });

  it("should remove javascript: URLs", () => {
    const input = '<a href="javascript:alert(1)">Link</a>';
    const output = sanitizer.sanitize(input);
    assertNotContains(output, "javascript:", "javascript: URL removed");
  });

  it("should allow safe HTML", () => {
    const input = "<p><strong>Bold</strong> and <em>italic</em></p>";
    const output = sanitizer.sanitize(input);
    assertContains(output, "<strong>Bold</strong>", "Strong tag preserved");
    assertContains(output, "<em>italic</em>", "Em tag preserved");
  });

  it('should add rel="noopener noreferrer" to external links', () => {
    const input = '<a href="https://example.com">External</a>';
    const output = sanitizer.sanitize(input);
    assertContains(
      output,
      'rel="noopener noreferrer"',
      "Security attributes added",
    );
  });

  it("should handle empty input", () => {
    assertEqual(sanitizer.sanitize(""), "", "Empty string handled");
    assertEqual(sanitizer.sanitize(null), "", "Null handled");
    assertEqual(sanitizer.sanitize(undefined), "", "Undefined handled");
  });

  it("should escape HTML entities with escapeHtml", () => {
    const input = '<script>alert("xss")</script>';
    const output = escapeHtml(input);
    assertNotContains(output, "<script>", "Script tag escaped");
    assertContains(output, "&lt;script&gt;", "Properly escaped");
  });

  it("should remove data: URLs from images", () => {
    // data: URLs in src should be blocked (potential XSS vector)
    const input = '<img src="data:text/html,<script>alert(1)</script>">';
    const output = sanitizer.sanitize(input);
    assertNotContains(output, "data:", "data: URL removed from src");
  });

  it("should remove style injection attempts", () => {
    const input =
      '<div style="background: url(javascript:alert(1))">Test</div>';
    const output = sanitizer.sanitize(input);
    assertNotContains(output, "javascript:", "JavaScript in style removed");
  });

  it("should handle nested dangerous content", () => {
    const input = "<div><iframe><script>alert(1)</script></iframe></div>";
    const output = sanitizer.sanitize(input);
    assertNotContains(output, "iframe", "Nested iframe removed");
    assertNotContains(output, "script", "Nested script removed");
  });
});

// ============================================
// CSP TESTS
// ============================================

describe("Content Security Policy", () => {
  it("should generate nonce", () => {
    const nonce = getNonce();
    assert(nonce && nonce.length > 0, "Nonce generated");
    assert(typeof nonce === "string", "Nonce is string");
  });

  it("should include nonce in CSP", () => {
    const csp = generateCSP();
    assertContains(csp, "'nonce-", "Nonce included in CSP");
  });

  it("should not include unsafe-inline", () => {
    const csp = generateCSP();
    assertNotContains(csp, "'unsafe-inline'", "No unsafe-inline in CSP");
  });

  it("should include frame-ancestors none", () => {
    const csp = generateCSP();
    assertContains(
      csp,
      "frame-ancestors 'none'",
      "Clickjacking protection present",
    );
  });

  it("should include object-src none", () => {
    const csp = generateCSP();
    assertContains(csp, "object-src 'none'", "Object-src restricted");
  });
});

// ============================================
// API CLIENT TESTS
// ============================================

describe("ApiClient", () => {
  it("should create instance with defaults", () => {
    const client = new ApiClient();
    assert(client.baseUrl === "/api", "Default baseUrl set");
    assert(client.timeout === 30000, "Default timeout set");
  });

  it("should accept custom configuration", () => {
    const client = new ApiClient("/api/v2", {
      timeout: 10000,
      retries: 5,
    });
    assertEqual(client.baseUrl, "/api/v2", "Custom baseUrl");
    assertEqual(client.timeout, 10000, "Custom timeout");
    assertEqual(client.retries, 5, "Custom retries");
  });

  it("should add request interceptors", () => {
    const client = new ApiClient();

    const remove = client.addRequestInterceptor((config) => {
      return config;
    });

    assert(typeof remove === "function", "Returns remove function");
    assert(client._requestInterceptors.length === 1, "Interceptor added");

    remove();
    assert(client._requestInterceptors.length === 0, "Interceptor removed");
  });

  it("should add error handlers", () => {
    const client = new ApiClient();

    const remove = client.addErrorHandler(() => {
      // Handler callback
    });

    assert(typeof remove === "function", "Returns remove function");
    assert(client._errorHandlers.length === 1, "Handler added");
  });

  it("ApiError should have correct properties", () => {
    const error = new ApiError(404, "Not found", { detail: "Item not found" });

    assertEqual(error.status, 404, "Status code set");
    assertEqual(error.message, "Not found", "Message set");
    assert(error.data.detail === "Item not found", "Data set");
    assert(error.isClientError(), "isClientError() correct");
    assert(!error.isServerError(), "isServerError() correct");
  });

  it("should identify auth errors", () => {
    const error401 = new ApiError(401, "Unauthorized");
    const error403 = new ApiError(403, "Forbidden");
    const error404 = new ApiError(404, "Not found");

    assert(error401.isAuthError(), "401 is auth error");
    assert(error403.isAuthError(), "403 is auth error");
    assert(!error404.isAuthError(), "404 is not auth error");
  });
});

// ============================================
// WEBSOCKET CLIENT TESTS
// ============================================

describe("WebSocketClient", () => {
  it("should create instance with defaults", () => {
    const ws = new WebSocketClient("wss://example.com");
    assert(ws.url === "wss://example.com", "URL set");
    assert(ws.options.reconnect === true, "Reconnect enabled by default");
    assert(
      ws.options.maxReconnectAttempts === 20,
      "Default max reconnect attempts",
    );
  });

  it("should accept custom options", () => {
    const ws = new WebSocketClient("wss://example.com", {
      reconnect: false,
      maxReconnectAttempts: 5,
      heartbeatInterval: 10000,
    });

    assert(ws.options.reconnect === false, "Custom reconnect");
    assertEqual(ws.options.maxReconnectAttempts, 5, "Custom max attempts");
    assertEqual(ws.options.heartbeatInterval, 10000, "Custom heartbeat");
  });

  it("should have correct initial state", () => {
    const ws = new WebSocketClient("wss://example.com");
    assertEqual(ws.getState(), WS_STATE.CLOSED, "Initial state is CLOSED");
    assert(!ws.isConnected(), "Not connected initially");
  });

  it("should track subscriptions", () => {
    const ws = new WebSocketClient("wss://example.com");

    // Manually add subscriptions (since we can't connect)
    ws._subscriptions.add("orderbook.50.BTCUSDT");
    ws._subscriptions.add("trade.BTCUSDT");

    const subs = ws.getSubscriptions();
    assert(subs.includes("orderbook.50.BTCUSDT"), "Subscription tracked");
    assert(subs.includes("trade.BTCUSDT"), "Multiple subscriptions");
    assertEqual(subs.length, 2, "Correct count");
  });

  it("should add and remove event listeners", () => {
    const ws = new WebSocketClient("wss://example.com");

    const remove = ws.on(WS_EVENTS.CONNECT, () => {
      // Listener callback
    });

    assert(typeof remove === "function", "Returns remove function");
    assert(ws._listeners.get(WS_EVENTS.CONNECT).size === 1, "Listener added");

    remove();
    assert(ws._listeners.get(WS_EVENTS.CONNECT).size === 0, "Listener removed");
  });

  it("should queue messages when not connected", () => {
    const ws = new WebSocketClient("wss://example.com", {
      queueMessages: true,
    });

    const sent = ws.send({ test: "message" });
    assert(!sent, "Message not sent immediately");
    assertEqual(ws._messageQueue.length, 1, "Message queued");
  });

  it("should respect max queue size", () => {
    const ws = new WebSocketClient("wss://example.com", {
      queueMessages: true,
      maxQueueSize: 2,
    });

    ws.send({ msg: 1 });
    ws.send({ msg: 2 });
    ws.send({ msg: 3 }); // Should be dropped

    assertEqual(ws._messageQueue.length, 2, "Queue size respected");
  });
});

// ============================================
// RUN TESTS
// ============================================

export function runSecurityTests() {
  console.log("\n🔒 SECURITY MODULE TESTS");
  console.log("========================\n");

  // Reset results
  testResults = { passed: 0, failed: 0, errors: [] };

  // Note: Tests are run by the describe/it calls above

  console.log("\n------------------------");
  console.log(
    `Results: ${testResults.passed} passed, ${testResults.failed} failed`,
  );

  if (testResults.errors.length > 0) {
    console.log("\n❌ Failed tests:");
    testResults.errors.forEach((e) => console.log(`  - ${e}`));
  }

  return testResults;
}

// Auto-run if loaded directly
if (typeof window !== "undefined") {
  window.runSecurityTests = runSecurityTests;
}

// Run tests
runSecurityTests();
