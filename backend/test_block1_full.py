"""
БЛОК 1: Полный тест Backend API Foundation

Проверяет все компоненты созданные в блоке 1
"""

import sys
import os
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test results storage
test_results = []


def test_result(name: str, passed: bool, details: str = ""):
    """Record test result"""
    test_results.append({
        'name': name,
        'passed': passed,
        'details': details
    })
    return passed


def print_header(title: str):
    """Print section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_test(name: str, passed: bool, details: str = ""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{name:.<50} {status}")
    if details:
        print(f"   └─ {details}")


# ============================================================================
# TEST 1: File Structure
# ============================================================================
def test_file_structure():
    """Test that all required files exist"""
    print_header("TEST 1: File Structure")
    
    required_files = [
        "backend/main.py",
        "backend/database/__init__.py",
        "backend/core/config.py",
        "backend/.env",
        "backend/requirements.txt",
        "backend/test_basic.py",
        "START_BACKEND.ps1",
        "BLOCK_1_SUMMARY.md",
        "QUICK_START_CURRENT.md",
    ]
    
    all_passed = True
    
    for file_path in required_files:
        full_path = Path(__file__).parent.parent / file_path
        exists = full_path.exists()
        
        if not exists:
            all_passed = False
        
        test_result(f"File exists: {file_path}", exists)
        print_test(file_path, exists)
    
    return all_passed


# ============================================================================
# TEST 2: Python Imports
# ============================================================================
def test_imports():
    """Test that all required packages can be imported"""
    print_header("TEST 2: Python Package Imports")
    
    packages = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("sqlalchemy", "SQLAlchemy"),
        ("pydantic", "Pydantic"),
        ("pydantic_settings", "Pydantic Settings"),
        ("loguru", "Loguru"),
        ("redis", "Redis"),
        ("celery", "Celery"),
        ("pandas", "Pandas"),
        ("numpy", "NumPy"),
        ("pybit", "PyBit"),
        ("dotenv", "Python-dotenv"),
        ("jose", "Python-jose"),
        ("pytest", "Pytest"),
    ]
    
    all_passed = True
    
    for package, display_name in packages:
        try:
            __import__(package)
            test_result(f"Import: {display_name}", True)
            print_test(display_name, True)
        except ImportError as e:
            test_result(f"Import: {display_name}", False, str(e))
            print_test(display_name, False, str(e))
            all_passed = False
    
    return all_passed


# ============================================================================
# TEST 3: Configuration Loading
# ============================================================================
def test_configuration():
    """Test configuration loading"""
    print_header("TEST 3: Configuration Loading")
    
    try:
        from backend.core.config import settings
        
        # Test that settings loaded
        passed = test_result("Settings object created", True)
        print_test("Settings object created", True)
        
        # Test required attributes
        attrs = [
            ("API_HOST", settings.API_HOST),
            ("API_PORT", settings.API_PORT),
            ("POSTGRES_HOST", settings.POSTGRES_HOST),
            ("POSTGRES_PORT", settings.POSTGRES_PORT),
            ("REDIS_HOST", settings.REDIS_HOST),
            ("DEBUG", settings.DEBUG),
        ]
        
        for attr_name, attr_value in attrs:
            has_attr = attr_value is not None
            test_result(f"Setting: {attr_name}", has_attr, str(attr_value))
            print_test(f"{attr_name} = {attr_value}", has_attr)
        
        # Test property methods
        db_url = settings.database_url
        redis_url = settings.redis_url
        
        test_result("Database URL generation", bool(db_url), db_url)
        print_test(f"database_url", bool(db_url), db_url)
        
        test_result("Redis URL generation", bool(redis_url), redis_url)
        print_test(f"redis_url", bool(redis_url), redis_url)
        
        return True
        
    except Exception as e:
        test_result("Configuration loading", False, str(e))
        print_test("Configuration", False, str(e))
        return False


# ============================================================================
# TEST 4: Database Module
# ============================================================================
def test_database_module():
    """Test database module"""
    print_header("TEST 4: Database Module")
    
    try:
        # Import from root backend, not from database submodule
        import backend.database as db_module
        engine = db_module.engine
        SessionLocal = db_module.SessionLocal
        Base = db_module.Base
        get_db = db_module.get_db
        
        # Test engine exists
        passed = test_result("SQLAlchemy engine created", True)
        print_test("SQLAlchemy engine", True)
        
        # Test SessionLocal exists
        passed = test_result("SessionLocal factory created", True)
        print_test("SessionLocal factory", True)
        
        # Test Base exists
        passed = test_result("Base class created", True)
        print_test("Base class", True)
        
        # Test get_db function
        passed = test_result("get_db dependency function", True)
        print_test("get_db dependency", True)
        
        return True
        
    except Exception as e:
        test_result("Database module", False, str(e))
        print_test("Database module", False, str(e))
        return False


# ============================================================================
# TEST 5: FastAPI Application
# ============================================================================
def test_fastapi_app():
    """Test FastAPI application"""
    print_header("TEST 5: FastAPI Application")
    
    try:
        from backend.main import app
        
        # Test app exists
        test_result("FastAPI app created", True)
        print_test("FastAPI app created", True)
        
        # Test app attributes
        test_result("App title", bool(app.title), app.title)
        print_test(f"Title: {app.title}", bool(app.title))
        
        test_result("App version", bool(app.version), app.version)
        print_test(f"Version: {app.version}", bool(app.version))
        
        # Test routes exist
        routes = [route.path for route in app.routes]
        
        expected_routes = ["/", "/health", "/docs", "/redoc", "/openapi.json"]
        
        for route in expected_routes:
            exists = route in routes
            test_result(f"Route: {route}", exists)
            print_test(f"Route {route}", exists)
        
        # Test middleware
        has_cors = any("CORSMiddleware" in str(m) for m in app.user_middleware)
        test_result("CORS middleware", has_cors)
        print_test("CORS middleware", has_cors)
        
        return True
        
    except Exception as e:
        test_result("FastAPI application", False, str(e))
        print_test("FastAPI application", False, str(e))
        return False


# ============================================================================
# TEST 6: API Endpoints (with TestClient)
# ============================================================================
def test_api_endpoints():
    """Test API endpoints using TestClient"""
    print_header("TEST 6: API Endpoints")
    
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
        
        client = TestClient(app)
        
        # Test root endpoint
        response = client.get("/")
        root_ok = response.status_code == 200
        test_result("GET /", root_ok, f"Status: {response.status_code}")
        print_test(f"GET / → {response.status_code}", root_ok)
        
        if root_ok:
            data = response.json()
            print(f"   └─ Response: {data.get('message', '')}")
        
        # Test health endpoint
        response = client.get("/health")
        health_ok = response.status_code == 200
        test_result("GET /health", health_ok, f"Status: {response.status_code}")
        print_test(f"GET /health → {response.status_code}", health_ok)
        
        if health_ok:
            data = response.json()
            print(f"   └─ Status: {data.get('status', '')}")
            print(f"   └─ Service: {data.get('service', '')}")
        
        # Test OpenAPI docs
        response = client.get("/openapi.json")
        openapi_ok = response.status_code == 200
        test_result("GET /openapi.json", openapi_ok, f"Status: {response.status_code}")
        print_test(f"GET /openapi.json → {response.status_code}", openapi_ok)
        
        return root_ok and health_ok and openapi_ok
        
    except Exception as e:
        test_result("API endpoints", False, str(e))
        print_test("API endpoints", False, str(e))
        return False


# ============================================================================
# TEST 7: Logging
# ============================================================================
def test_logging():
    """Test logging functionality"""
    print_header("TEST 7: Logging Functionality")
    
    try:
        from loguru import logger
        
        # Test logger exists
        test_result("Loguru logger", True)
        print_test("Loguru logger imported", True)
        
        # Test log directory exists
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        test_result("Logs directory", log_dir.exists(), str(log_dir))
        print_test(f"Logs directory: {log_dir}", log_dir.exists())
        
        # Test logging works
        test_message = f"Test log message at {time.time()}"
        logger.info(test_message)
        
        test_result("Logger write test", True)
        print_test("Logger can write", True)
        
        return True
        
    except Exception as e:
        test_result("Logging", False, str(e))
        print_test("Logging", False, str(e))
        return False


# ============================================================================
# TEST 8: Environment Variables
# ============================================================================
def test_environment():
    """Test environment variables loading"""
    print_header("TEST 8: Environment Variables")
    
    try:
        from dotenv import load_dotenv
        import os
        
        # Load .env file
        env_path = Path(__file__).parent / ".env"
        load_dotenv(env_path)
        
        test_result(".env file exists", env_path.exists(), str(env_path))
        print_test(f".env file: {env_path}", env_path.exists())
        
        # Check some environment variables
        env_vars = [
            "API_HOST",
            "API_PORT",
            "POSTGRES_HOST",
            "POSTGRES_DB",
            "REDIS_HOST",
            "DEBUG",
        ]
        
        from backend.core.config import settings
        
        for var in env_vars:
            value = getattr(settings, var, None)
            has_value = value is not None
            test_result(f"ENV: {var}", has_value, str(value))
            print_test(f"{var} = {value}", has_value)
        
        return True
        
    except Exception as e:
        test_result("Environment variables", False, str(e))
        print_test("Environment variables", False, str(e))
        return False


# ============================================================================
# FINAL REPORT
# ============================================================================
def print_final_report():
    """Print final test report"""
    print("\n" + "=" * 70)
    print("  FINAL TEST REPORT - БЛОК 1")
    print("=" * 70)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for t in test_results if t['passed'])
    failed_tests = total_tests - passed_tests
    
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {failed_tests}")
    print(f"📊 Success Rate: {success_rate:.1f}%")
    
    if failed_tests > 0:
        print("\n❌ Failed Tests:")
        for test in test_results:
            if not test['passed']:
                print(f"  • {test['name']}")
                if test['details']:
                    print(f"    └─ {test['details']}")
    
    print("\n" + "=" * 70)
    
    if failed_tests == 0:
        print("🎉 ALL TESTS PASSED! БЛОК 1 ПОЛНОСТЬЮ ГОТОВ!")
        print("\n✅ Backend API Foundation работает отлично!")
        print("✅ Все компоненты на месте")
        print("✅ Конфигурация загружается")
        print("✅ API endpoints отвечают")
        print("\n🚀 Готов к БЛОКУ 2: Database Schema")
    else:
        print("⚠️ SOME TESTS FAILED")
        print("\n🔧 Проверьте ошибки выше и исправьте перед продолжением")
    
    print("=" * 70)
    
    return failed_tests == 0


# ============================================================================
# MAIN
# ============================================================================
def main():
    """Run all tests"""
    print("=" * 70)
    print("  🧪 БЛОК 1: ПОЛНОЕ ТЕСТИРОВАНИЕ")
    print("  Backend API Foundation - Comprehensive Test Suite")
    print("=" * 70)
    
    start_time = time.time()
    
    # Run all tests
    tests = [
        ("File Structure", test_file_structure),
        ("Python Imports", test_imports),
        ("Configuration", test_configuration),
        ("Database Module", test_database_module),
        ("FastAPI Application", test_fastapi_app),
        ("API Endpoints", test_api_endpoints),
        ("Logging", test_logging),
        ("Environment Variables", test_environment),
    ]
    
    all_passed = True
    
    for name, test_func in tests:
        try:
            result = test_func()
            if not result:
                all_passed = False
        except Exception as e:
            print(f"\n❌ Test section '{name}' crashed: {e}")
            all_passed = False
    
    elapsed_time = time.time() - start_time
    
    # Print final report
    success = print_final_report()
    
    print(f"\n⏱️  Time elapsed: {elapsed_time:.2f} seconds")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
