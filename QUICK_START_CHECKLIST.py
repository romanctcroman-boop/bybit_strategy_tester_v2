#!/usr/bin/env python3
"""
Quick Action Checklist - What to do next
"""

print("=" * 80)
print("  🎯 QUICK ACTION CHECKLIST")
print("=" * 80)

print("\n📋 STATUS: All core components are ready!")
print("   ✅ Phase 1 (Redis Queue) - COMPLETE + TESTED")
print("   ✅ Agent-to-Agent System - COMPLETE + TESTED") 
print("   ⚠️  MCP Server - FIXED (needs VS Code reload)")

print("\n" + "=" * 80)
print("  🚀 IMMEDIATE ACTIONS (Do this NOW)")
print("=" * 80)

print("\n1️⃣  RELOAD VS CODE (Fix MCP Server)")
print("   ├─ Press: Ctrl+Shift+P")
print("   ├─ Type: 'Developer: Reload Window'")
print("   └─ Wait: ~10 seconds for reload")

print("\n2️⃣  CHECK MCP OUTPUT")
print("   ├─ Menu: View → Output")
print("   ├─ Dropdown: Select 'MCP Servers'")
print("   └─ Look for: 'Starting server agent-to-agent-bridge' (no errors)")

print("\n3️⃣  TEST MCP IN COPILOT")
print("   ├─ Open: Copilot Chat (Ctrl+Shift+I)")
print("   ├─ Type: '@workspace What is Phase 1?'")
print("   └─ Expected: Should use MCP tools and return info about Redis Queue")

print("\n" + "=" * 80)
print("  ⚡ OPTIONAL ACTIONS (If you want to test more)")
print("=" * 80)

print("\n4️⃣  START REDIS QUEUE WORKERS (Optional)")
print("   ├─ Command: .\\start_workers.ps1")
print("   ├─ Or: py -m backend.queue.worker_cli --workers 4")
print("   └─ You'll see: '🚀 Worker worker-XXXXX started'")

print("\n5️⃣  TEST AGENT-TO-AGENT CLI (Optional)")
print("   ├─ Command: py cli_send_to_deepseek.py")
print("   ├─ Type: 'What is 2+2?'")
print("   └─ Expected: DeepSeek responds in 2-5 seconds")

print("\n6️⃣  CHECK QUEUE METRICS (Optional)")
print("   ├─ Command: curl http://localhost:8000/api/v1/queue/metrics")
print("   └─ Expected: JSON with tasks_submitted, tasks_completed, etc.")

print("\n" + "=" * 80)
print("  📊 VERIFICATION COMMANDS")
print("=" * 80)

print("\n✅ Check Redis:")
print("   redis-cli ping  # Should return: PONG")

print("\n✅ Check Backend:")
print("   curl http://localhost:8000/api/v1/health  # Should return: OK")

print("\n✅ Check Phase 1:")
print("   py check_phase1_status.py  # Should show: ✅ Phase 1 FULLY IMPLEMENTED")

print("\n✅ Run Tests:")
print("   py test_redis_queue.py  # Should exit with: Exit Code 0")

print("\n" + "=" * 80)
print("  🎯 WHAT TO EXPECT")
print("=" * 80)

print("\n🟢 IF MCP WORKS:")
print("   - Copilot Chat will respond with detailed info")
print("   - Output panel shows 'MCP: agent-to-agent-bridge connected'")
print("   - You can ask complex questions to DeepSeek via Copilot")

print("\n🔴 IF MCP FAILS:")
print("   - Check Output panel for errors")
print("   - Verify backend is running on port 8000")
print("   - Check Python path in .vscode/mcp.json")

print("\n🟡 IF WORKERS NEEDED:")
print("   - Backend shows: 'No workers available'")
print("   - Queue metrics show: active_tasks > 0 but not decreasing")
print("   - Solution: Run .\\start_workers.ps1")

print("\n" + "=" * 80)
print("  📝 CURRENT STATUS")
print("=" * 80)

import subprocess
import sys

def check_status():
    """Quick status check"""
    
    print("\n🔍 Redis:")
    try:
        result = subprocess.run(
            ["redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if "PONG" in result.stdout:
            print("   ✅ RUNNING")
        else:
            print("   ❌ NOT RESPONDING")
    except:
        print("   ⚠️  CAN'T CHECK (redis-cli not found)")
    
    print("\n🔍 Backend:")
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Quiet"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if "True" in result.stdout:
            print("   ✅ LISTENING ON PORT 8000")
        else:
            print("   ⚠️  PORT 8000 NOT RESPONDING")
    except:
        print("   ⚠️  CAN'T CHECK")
    
    print("\n🔍 Queue Files:")
    from pathlib import Path
    queue_path = Path(__file__).parent / "backend" / "queue"
    if queue_path.exists():
        files = list(queue_path.glob("*.py"))
        print(f"   ✅ {len(files)} files found")
    else:
        print("   ❌ backend/queue NOT FOUND")

check_status()

print("\n" + "=" * 80)
print("  🎉 READY TO GO!")
print("=" * 80)

print("\n👉 START HERE:")
print("   1. Reload VS Code (Ctrl+Shift+P → Reload Window)")
print("   2. Check Output panel (View → Output → MCP Servers)")
print("   3. Test in Copilot: '@workspace What is Phase 1?'")

print("\n📚 DOCUMENTATION:")
print("   - SYSTEM_STATUS_COMPLETE.md - Full status report")
print("   - PHASE1_COMPLETE_REPORT.md - Phase 1 details")
print("   - backend/queue/README.md - Queue documentation")

print("\n" + "=" * 80)
