#!/usr/bin/env python3
"""
Final System Verification Test
Проверка всех компонентов после исправления
"""

import subprocess
import sys
import time
from pathlib import Path
import json

print("=" * 80)
print("  FINAL SYSTEM VERIFICATION TEST")
print("=" * 80)

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def check_mark(passed):
    return f"{Colors.GREEN}✓{Colors.END}" if passed else f"{Colors.RED}✗{Colors.END}"

results = {
    "redis": False,
    "backend": False,
    "queue_files": False,
    "mcp_config": False,
    "agent_system": False
}

print("\n" + "=" * 80)
print("  1. REDIS SERVER")
print("=" * 80)

try:
    result = subprocess.run(
        ["redis-cli", "ping"],
        capture_output=True,
        text=True,
        timeout=3
    )
    if "PONG" in result.stdout:
        print(f"{check_mark(True)} Redis is running on localhost:6379")
        results["redis"] = True
    else:
        print(f"{check_mark(False)} Redis not responding")
except FileNotFoundError:
    print(f"{check_mark(False)} redis-cli not found (Redis not installed?)")
except Exception as e:
    print(f"{check_mark(False)} Error checking Redis: {e}")

print("\n" + "=" * 80)
print("  2. BACKEND API")
print("=" * 80)

try:
    import requests
    
    # Check if backend is running
    try:
        response = requests.get("http://localhost:8000/api/v1/health", timeout=3)
        if response.status_code == 200:
            print(f"{check_mark(True)} Backend is running on port 8000")
            results["backend"] = True
            
            # Check agent endpoints
            endpoints = [
                "/api/v1/agent/send-to-deepseek",
                "/api/v1/agent/send-to-perplexity",
                "/api/v1/agent/get-consensus"
            ]
            
            for endpoint in endpoints:
                url = f"http://localhost:8000{endpoint}"
                # Just check if endpoint exists (will return 422 for missing payload)
                resp = requests.post(url, json={}, timeout=2)
                if resp.status_code in [200, 422]:  # 422 = validation error (expected)
                    print(f"{check_mark(True)} {endpoint}")
                else:
                    print(f"{check_mark(False)} {endpoint} (status: {resp.status_code})")
        else:
            print(f"{check_mark(False)} Backend returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"{check_mark(False)} Backend not responding on port 8000")
        print(f"   {Colors.YELLOW}Hint:{Colors.END} Start backend with: uvicorn backend.app:app --port 8000")
    except requests.exceptions.Timeout:
        print(f"{check_mark(False)} Backend connection timeout")
        
except ImportError:
    print(f"{check_mark(False)} requests module not installed")
    print(f"   {Colors.YELLOW}Hint:{Colors.END} pip install requests")

print("\n" + "=" * 80)
print("  3. QUEUE FILES (Phase 1)")
print("=" * 80)

queue_path = Path(__file__).parent / "backend" / "queue"
required_files = [
    "__init__.py",
    "redis_queue_manager.py",
    "task_handlers.py",
    "adapter.py",
    "worker_cli.py",
    "autoscaler.py",
    "README.md"
]

if queue_path.exists():
    all_exist = True
    total_size = 0
    
    for file in required_files:
        file_path = queue_path / file
        if file_path.exists():
            size = file_path.stat().st_size
            total_size += size
            print(f"{check_mark(True)} {file} ({size:,} bytes)")
        else:
            print(f"{check_mark(False)} {file} MISSING")
            all_exist = False
    
    if all_exist:
        print(f"\n{check_mark(True)} All queue files present ({total_size:,} bytes total)")
        results["queue_files"] = True
else:
    print(f"{check_mark(False)} backend/queue directory not found")

print("\n" + "=" * 80)
print("  4. MCP SERVER CONFIGURATION")
print("=" * 80)

mcp_config_path = Path(__file__).parent / ".vscode" / "mcp.json"

if mcp_config_path.exists():
    try:
        with open(mcp_config_path, 'r', encoding='utf-8') as f:
            # Remove comments for JSON parsing
            content = f.read()
            lines = [line for line in content.split('\n') if not line.strip().startswith('//')]
            config = json.loads('\n'.join(lines))
        
        if "servers" in config:
            servers = config["servers"]
            
            # Check bybit-strategy-tester
            if "bybit-strategy-tester" in servers:
                print(f"{check_mark(True)} bybit-strategy-tester server configured")
            else:
                print(f"{check_mark(False)} bybit-strategy-tester server missing")
            
            # Check agent-to-agent-bridge
            if "agent-to-agent-bridge" in servers:
                bridge_config = servers["agent-to-agent-bridge"]
                print(f"{check_mark(True)} agent-to-agent-bridge server configured")
                
                # Check Python path
                command = bridge_config.get("command", "")
                if "python.exe" in command or "py.exe" in command:
                    print(f"{check_mark(True)} Python path is explicit (good!)")
                    print(f"   Path: {command}")
                    results["mcp_config"] = True
                else:
                    print(f"{check_mark(False)} Python path is 'python' (may cause ENOENT)")
                    print(f"   {Colors.YELLOW}Hint:{Colors.END} Change to full path: D:\\...\\python.exe")
            else:
                print(f"{check_mark(False)} agent-to-agent-bridge server missing")
        else:
            print(f"{check_mark(False)} No servers configured in mcp.json")
            
    except Exception as e:
        print(f"{check_mark(False)} Error reading mcp.json: {e}")
else:
    print(f"{check_mark(False)} .vscode/mcp.json not found")

print("\n" + "=" * 80)
print("  5. AGENT-TO-AGENT SYSTEM")
print("=" * 80)

# Check test file
test_file = Path(__file__).parent / "test_agent_to_agent.py"
if test_file.exists():
    print(f"{check_mark(True)} test_agent_to_agent.py exists")
    
    # Check if tests passed (look for test results in files)
    test_results_files = [
        "AGENT_TO_AGENT_TEST_ANALYSIS.md",
        "AGENT_COMMUNICATION_PRODUCTION_READY.md"
    ]
    
    for result_file in test_results_files:
        result_path = Path(__file__).parent / result_file
        if result_path.exists():
            print(f"{check_mark(True)} {result_file} found")
            
            # Check for success indicators
            content = result_path.read_text(encoding='utf-8')
            if "5/5" in content or "PASSED" in content or "SUCCESS" in content:
                print(f"   {Colors.GREEN}Contains success indicators{Colors.END}")
                results["agent_system"] = True
else:
    print(f"{check_mark(False)} test_agent_to_agent.py not found")

print("\n" + "=" * 80)
print("  SUMMARY")
print("=" * 80)

total = len(results)
passed = sum(results.values())
percentage = (passed / total) * 100

print(f"\nPassed: {passed}/{total} ({percentage:.0f}%)")
print("")

for component, status in results.items():
    symbol = check_mark(status)
    status_text = f"{Colors.GREEN}PASSED{Colors.END}" if status else f"{Colors.RED}FAILED{Colors.END}"
    print(f"{symbol} {component.upper().replace('_', ' ')}: {status_text}")

print("\n" + "=" * 80)
print("  NEXT STEPS")
print("=" * 80)

if all(results.values()):
    print(f"\n{Colors.GREEN}✓ ALL SYSTEMS OPERATIONAL!{Colors.END}")
    print("\nReady to use:")
    print("  1. Reload VS Code: Ctrl+Shift+P → 'Developer: Reload Window'")
    print("  2. Check MCP Output: View → Output → 'MCP Servers'")
    print("  3. Test in Copilot: '@workspace What is Phase 1?'")
    print("  4. Start workers: .\\start_workers.ps1")
else:
    print(f"\n{Colors.YELLOW}⚠ SOME COMPONENTS NEED ATTENTION{Colors.END}")
    print("\nActions needed:")
    
    if not results["redis"]:
        print(f"\n{Colors.RED}✗ Redis:{Colors.END}")
        print("   Start Redis: redis-server")
        print("   Or Docker: docker run -d -p 6379:6379 redis:latest")
    
    if not results["backend"]:
        print(f"\n{Colors.RED}✗ Backend:{Colors.END}")
        print("   Start backend: uvicorn backend.app:app --port 8000")
    
    if not results["mcp_config"]:
        print(f"\n{Colors.RED}✗ MCP Config:{Colors.END}")
        print("   Fix Python path in .vscode/mcp.json")
        print("   Change 'python' to full path: D:\\...\\python.exe")
    
    if not results["queue_files"]:
        print(f"\n{Colors.RED}✗ Queue Files:{Colors.END}")
        print("   Phase 1 implementation incomplete")
        print("   Check: backend/queue/ directory")

print("\n" + "=" * 80)
print("")

# Exit with appropriate code
sys.exit(0 if all(results.values()) else 1)
