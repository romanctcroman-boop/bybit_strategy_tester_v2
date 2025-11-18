import sys
from pathlib import Path

# Add mcp-server to path
mcp_server_path = Path(__file__).parent / "mcp-server"
sys.path.insert(0, str(mcp_server_path))

from backend.api import orchestrator

print(f"Router object: {orchestrator.router}")
print(f"Router prefix: {orchestrator.router.prefix}")
print(f"Router tags: {orchestrator.router.tags}")
print(f"Number of routes: {len(orchestrator.router.routes)}")
print("\nRoutes:")
for i, route in enumerate(orchestrator.router.routes, 1):
    if hasattr(route, 'path'):
        methods = route.methods if hasattr(route, 'methods') else 'N/A'
        print(f"  {i}. {route.path} - {methods}")
