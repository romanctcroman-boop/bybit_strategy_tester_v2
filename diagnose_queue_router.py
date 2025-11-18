"""
Simple diagnostic: check if queue router is registered at runtime
"""

import sys
sys.path.insert(0, "D:\\bybit_strategy_tester_v2")

from backend.api.app import app

print("=" * 60)
print(" Diagnostic: Queue Router Registration")
print("=" * 60)

# Check import
try:
    from backend.api.routers import queue as queue_router
    print("\n✅ queue_router import OK")
    print(f"   Router object: {queue_router.router}")
    print(f"   Router routes: {[r.path for r in queue_router.router.routes if hasattr(r, 'path')]}")
except Exception as e:
    print(f"\n❌ Failed to import queue_router: {e}")
    sys.exit(1)

# Check if registered in app
print("\n📝 All app routes:")
all_routes = [r.path for r in app.routes if hasattr(r, 'path')]
queue_routes = [r for r in all_routes if 'queue' in r.lower()]

if queue_routes:
    print(f"\n✅ Found {len(queue_routes)} queue routes in app:")
    for route in sorted(queue_routes):
        print(f"   - {route}")
else:
    print("\n❌ NO queue routes found in app!")
    print("\nAll routes:")
    for route in sorted(all_routes)[:20]:
        print(f"   - {route}")

print("\n" + "=" * 60)
