"""
Basic Backend Test

Tests basic functionality without database dependency
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all basic imports work"""
    print("🧪 Testing imports...")
    
    try:
        import fastapi
        print("  ✅ FastAPI imported")
    except ImportError as e:
        print(f"  ❌ FastAPI import failed: {e}")
        return False
    
    try:
        import uvicorn
        print("  ✅ Uvicorn imported")
    except ImportError as e:
        print(f"  ❌ Uvicorn import failed: {e}")
        return False
    
    try:
        import sqlalchemy
        print("  ✅ SQLAlchemy imported")
    except ImportError as e:
        print(f"  ❌ SQLAlchemy import failed: {e}")
        return False
    
    try:
        import pydantic
        print("  ✅ Pydantic imported")
    except ImportError as e:
        print(f"  ❌ Pydantic import failed: {e}")
        return False
    
    try:
        from loguru import logger
        print("  ✅ Loguru imported")
    except ImportError as e:
        print(f"  ❌ Loguru import failed: {e}")
        return False
    
    return True


def test_config():
    """Test configuration loading"""
    print("\n🧪 Testing configuration...")
    
    try:
        from backend.core.config import settings
        print(f"  ✅ Settings loaded")
        print(f"  📍 API Host: {settings.API_HOST}")
        print(f"  📍 API Port: {settings.API_PORT}")
        print(f"  📍 Database URL: {settings.database_url}")
        return True
    except Exception as e:
        print(f"  ❌ Config loading failed: {e}")
        return False


def test_main_app():
    """Test FastAPI app creation"""
    print("\n🧪 Testing FastAPI app...")
    
    try:
        from backend.main import app
        print(f"  ✅ FastAPI app created")
        print(f"  📍 Title: {app.title}")
        print(f"  📍 Version: {app.version}")
        return True
    except Exception as e:
        print(f"  ❌ App creation failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("🎯 BYBIT STRATEGY TESTER - BACKEND BASIC TESTS")
    print("=" * 60)
    print()
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("FastAPI App", test_main_app),
    ]
    
    results = []
    
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name:.<40} {status}")
    
    all_passed = all(result for _, result in results)
    
    print("=" * 60)
    
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("\n✅ Backend is ready to start!")
        print("Run: python -m uvicorn backend.main:app --reload")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("\n🔧 Please fix the issues above before starting the backend")
        return 1


if __name__ == "__main__":
    exit(main())
