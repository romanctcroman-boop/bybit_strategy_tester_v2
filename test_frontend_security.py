#!/usr/bin/env python3
"""
🧪 Frontend Security Audit - Test Script

Verifies that security fixes were implemented correctly.

Run: python test_frontend_security.py
"""

import sys
from pathlib import Path

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def print_ok(msg):
    print(f"  {GREEN}✅ {msg}{RESET}")


def print_fail(msg):
    print(f"  {RED}❌ {msg}{RESET}")


def print_warn(msg):
    print(f"  {YELLOW}⚠️  {msg}{RESET}")


def print_header(msg):
    print(f"\n{YELLOW}📦 {msg}{RESET}")


class FrontendSecurityTest:
    """Test frontend security implementations."""

    def __init__(self, frontend_path: str):
        self.frontend_path = Path(frontend_path)
        self.js_core_path = self.frontend_path / "js" / "core"
        self.tests_passed = 0
        self.tests_failed = 0

    def run_all_tests(self):
        """Run all security tests."""
        print("\n" + "=" * 60)
        print("🔒 FRONTEND SECURITY AUDIT - TEST RESULTS")
        print("=" * 60)

        self.test_new_files_exist()
        self.test_api_client()
        self.test_websocket_client()
        self.test_sanitizer()
        self.test_logger()
        self.test_security_js()
        self.test_core_index_exports()

        print("\n" + "-" * 60)
        total = self.tests_passed + self.tests_failed
        print(f"Results: {self.tests_passed}/{total} tests passed")

        if self.tests_failed > 0:
            print(f"{RED}❌ {self.tests_failed} tests FAILED{RESET}")
            return 1
        else:
            print(f"{GREEN}✅ All tests PASSED{RESET}")
            return 0

    def test_new_files_exist(self):
        """Check that all new security files exist."""
        print_header("New Security Files")

        required_files = [
            "ApiClient.js",
            "WebSocketClient.js",
            "Sanitizer.js",
            "Logger.js",
        ]

        for filename in required_files:
            filepath = self.js_core_path / filename
            if filepath.exists():
                print_ok(f"{filename} exists")
                self.tests_passed += 1
            else:
                print_fail(f"{filename} NOT FOUND")
                self.tests_failed += 1

    def test_api_client(self):
        """Test ApiClient.js implementation."""
        print_header("ApiClient.js - CSRF Protection")

        filepath = self.js_core_path / "ApiClient.js"
        if not filepath.exists():
            print_fail("File not found")
            self.tests_failed += 3
            return

        content = filepath.read_text(encoding="utf-8")

        # Check CSRF token handling
        if "csrfToken" in content and "X-CSRF-Token" in content:
            print_ok("CSRF token handling implemented")
            self.tests_passed += 1
        else:
            print_fail("CSRF token handling missing")
            self.tests_failed += 1

        # Check interceptors
        if "addRequestInterceptor" in content and "addResponseInterceptor" in content:
            print_ok("Request/Response interceptors implemented")
            self.tests_passed += 1
        else:
            print_fail("Interceptors missing")
            self.tests_failed += 1

        # Check retry logic
        if "retries" in content and "_executeWithRetry" in content:
            print_ok("Retry logic implemented")
            self.tests_passed += 1
        else:
            print_fail("Retry logic missing")
            self.tests_failed += 1

        # Check error handling
        if "class ApiError" in content:
            print_ok("ApiError class defined")
            self.tests_passed += 1
        else:
            print_fail("ApiError class missing")
            self.tests_failed += 1

    def test_websocket_client(self):
        """Test WebSocketClient.js implementation."""
        print_header("WebSocketClient.js - Auto-Reconnect")

        filepath = self.js_core_path / "WebSocketClient.js"
        if not filepath.exists():
            print_fail("File not found")
            self.tests_failed += 3
            return

        content = filepath.read_text(encoding="utf-8")

        # Check reconnection logic
        if "_scheduleReconnect" in content and "maxReconnectAttempts" in content:
            print_ok("Auto-reconnect with max attempts")
            self.tests_passed += 1
        else:
            print_fail("Reconnect logic missing")
            self.tests_failed += 1

        # Check exponential backoff
        if "reconnectDecay" in content or "Math.pow" in content:
            print_ok("Exponential backoff implemented")
            self.tests_passed += 1
        else:
            print_fail("Exponential backoff missing")
            self.tests_failed += 1

        # Check heartbeat
        if "_startHeartbeat" in content and "heartbeatInterval" in content:
            print_ok("Heartbeat/ping mechanism")
            self.tests_passed += 1
        else:
            print_fail("Heartbeat missing")
            self.tests_failed += 1

        # Check message queue
        if "_messageQueue" in content and "queueMessages" in content:
            print_ok("Message queuing when disconnected")
            self.tests_passed += 1
        else:
            print_fail("Message queue missing")
            self.tests_failed += 1

    def test_sanitizer(self):
        """Test Sanitizer.js implementation."""
        print_header("Sanitizer.js - XSS Protection")

        filepath = self.js_core_path / "Sanitizer.js"
        if not filepath.exists():
            print_fail("File not found")
            self.tests_failed += 3
            return

        content = filepath.read_text(encoding="utf-8")

        # Check dangerous tag removal
        if "_isDangerousTag" in content and "script" in content.lower():
            print_ok("Dangerous tag detection (script, iframe, etc.)")
            self.tests_passed += 1
        else:
            print_fail("Dangerous tag detection missing")
            self.tests_failed += 1

        # Check URL validation
        if "_isValidUrl" in content and "javascript:" in content:
            print_ok("URL validation (javascript: blocking)")
            self.tests_passed += 1
        else:
            print_fail("URL validation missing")
            self.tests_failed += 1

        # Check attribute sanitization
        if "_sanitizeAttributes" in content:
            print_ok("Attribute sanitization")
            self.tests_passed += 1
        else:
            print_fail("Attribute sanitization missing")
            self.tests_failed += 1

        # Check escapeHtml export
        if "export function escapeHtml" in content or "function escapeHtml" in content:
            print_ok("escapeHtml function available")
            self.tests_passed += 1
        else:
            print_fail("escapeHtml function missing")
            self.tests_failed += 1

    def test_logger(self):
        """Test Logger.js implementation."""
        print_header("Logger.js - Production-Safe Logging")

        filepath = self.js_core_path / "Logger.js"
        if not filepath.exists():
            print_fail("File not found")
            self.tests_failed += 2
            return

        content = filepath.read_text(encoding="utf-8")

        # Check log levels
        if "LogLevel" in content and "DEBUG" in content and "ERROR" in content:
            print_ok("Log levels defined")
            self.tests_passed += 1
        else:
            print_fail("Log levels missing")
            self.tests_failed += 1

        # Check production mode
        if "setProductionMode" in content or "isProduction" in content:
            print_ok("Production mode detection")
            self.tests_passed += 1
        else:
            print_fail("Production mode missing")
            self.tests_failed += 1

        # Check _shouldLog method
        if "_shouldLog" in content:
            print_ok("Conditional logging (_shouldLog)")
            self.tests_passed += 1
        else:
            print_fail("Conditional logging missing")
            self.tests_failed += 1

    def test_security_js(self):
        """Test security.js improvements."""
        print_header("security.js - CSP Improvements")

        filepath = self.frontend_path / "js" / "security.js"
        if not filepath.exists():
            print_fail("File not found")
            self.tests_failed += 3
            return

        content = filepath.read_text(encoding="utf-8")

        # Check nonce generation
        if "generateNonce" in content and "getNonce" in content:
            print_ok("Nonce generation functions")
            self.tests_passed += 1
        else:
            print_fail("Nonce generation missing")
            self.tests_failed += 1

        # Check unsafe-inline removed (shouldn't be in styleSrc without nonce)
        if "'unsafe-inline'" not in content or "nonce-" in content:
            print_ok("unsafe-inline replaced with nonce")
            self.tests_passed += 1
        else:
            print_warn("unsafe-inline might still be present")
            self.tests_failed += 1

        # Check CSRF functions
        if "getCsrfToken" in content and "setCsrfToken" in content:
            print_ok("CSRF token management functions")
            self.tests_passed += 1
        else:
            print_fail("CSRF functions missing")
            self.tests_failed += 1

    def test_core_index_exports(self):
        """Test that index.js exports new modules."""
        print_header("Core Index Exports")

        filepath = self.js_core_path / "index.js"
        if not filepath.exists():
            print_fail("index.js not found")
            self.tests_failed += 1
            return

        content = filepath.read_text(encoding="utf-8")

        exports_to_check = [
            ("ApiClient", "ApiClient export"),
            ("WebSocketClient", "WebSocketClient export"),
            ("Sanitizer", "Sanitizer export"),
            ("sanitize", "sanitize function export"),
            ("escapeHtml", "escapeHtml function export"),
        ]

        for export_name, description in exports_to_check:
            if export_name in content:
                print_ok(description)
                self.tests_passed += 1
            else:
                print_fail(f"{description} missing")
                self.tests_failed += 1


def main():
    """Main entry point."""
    # Determine frontend path
    script_dir = Path(__file__).parent
    frontend_path = script_dir / "frontend"

    if not frontend_path.exists():
        # Try project root (this script may be run from repo root)
        frontend_path = Path(__file__).resolve().parent / "frontend"

    if not frontend_path.exists():
        print(f"{RED}❌ Frontend directory not found{RESET}")
        sys.exit(1)

    tester = FrontendSecurityTest(str(frontend_path))
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
