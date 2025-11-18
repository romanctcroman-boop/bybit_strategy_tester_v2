from fastapi import FastAPI
from fastmcp import FastMCP

# Test 1: Standard FastMCP (not from_fastapi)
print("=== Test 1: Standard Fast MCP ===")
mcp1 = FastMCP(name="Test1")

@mcp1.tool()
def test_tool1(message: str) -> str:
    return f"Echo: {message}"

print(f"Tools registered: {len(mcp1._tool_manager._tools)}")
for tool_name in mcp1._tool_manager._tools.keys():
    print(f"  - {tool_name}")

# Test 2: FastMCP.from_fastapi
print("\n=== Test 2: FastMCP.from_fastapi ===")
app = FastAPI()

@app.get("/test")
def test_endpoint():
    return {"status": "ok"}

mcp2 = FastMCP.from_fastapi(app=app, name="Test2")

@mcp2.tool()
def test_tool2(message: str) -> str:
    return f"Echo2: {message}"

print(f"Tools registered: {len(mcp2._tool_manager._tools)}")
for tool_name in mcp2._tool_manager._tools.keys():
    print(f"  - {tool_name}")

# Check http_app routes
http_app1 = mcp1.http_app()
http_app2 = mcp2.http_app()
print(f"\nHTTP App 1 routes: {[r.path for r in http_app1.routes]}")
print(f"HTTP App 2 routes: {[r.path for r in http_app2.routes]}")
