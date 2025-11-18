# 🚀 QUICK ACTION GUIDE - Start Here!

## Current Status (verified by `verify_system.py`)

```
✅ Redis: RUNNING
❌ Backend: NOT RUNNING
✅ Queue Files: COMPLETE (61,632 bytes)
❌ MCP Config: Parse error (minor - will fix)
✅ Agent System: Tests passed (5/5)
```

---

## 🎯 IMMEDIATE ACTION NEEDED

### 1. Start Backend (КРИТИЧНО)

Backend API НЕ запущен! Без него MCP Server не сможет подключиться.

**В новом PowerShell терминале:**

```powershell
# Активировать venv
& D:/bybit_strategy_tester_v2/.venv/Scripts/Activate.ps1

# Запустить Backend
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

**Ожидаемый вывод:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Проверка:**
```powershell
# В другом терминале
curl http://localhost:8000/api/v1/health
# Должно вернуть: {"status":"ok"}
```

---

### 2. Reload VS Code (после запуска Backend)

После того как Backend запустился:

```
1. Ctrl+Shift+P
2. Type: "Developer: Reload Window"
3. Wait: ~10 seconds
```

---

### 3. Check MCP Output

После reload:

```
1. Menu: View → Output
2. Dropdown: Select "MCP Servers"
3. Look for: "Starting server agent-to-agent-bridge"
```

**✅ Good output:**
```
[agent-to-agent-bridge] Starting...
[agent-to-agent-bridge] Connected to http://localhost:8000
[agent-to-agent-bridge] Registered 4 tools
```

**❌ Bad output:**
```
Error: spawn python ENOENT
```
→ If this happens, Python path in mcp.json is wrong.

---

## 📝 Why Backend Wasn't Running

Your system currently has running:
- ✅ `agent_background_service.py` (Process 3708)
- ✅ `background_diagnostic_service.py` (Process 35012)
- ✅ MCP Server (`server.py`) - 2 instances (12100, 28836)

But **missing**:
- ❌ `uvicorn backend.app:app` (main FastAPI backend)

The FastAPI backend is REQUIRED for:
- Agent-to-Agent endpoints (`/api/v1/agent/send-to-deepseek`, etc.)
- Queue endpoints (`/api/v1/queue/backtest/run`, etc.)
- MCP Server connection (`mcp_server_wrapper.py` connects to it)

---

## 🔧 Alternative: Use Task

VS Code has a task configured to start backend:

```
1. Ctrl+Shift+P
2. Type: "Tasks: Run Task"
3. Select: "Start backend (uvicorn)"
```

---

## ✅ After Backend Starts

Once backend is running on port 8000:

1. **Verify Backend:**
   ```powershell
   curl http://localhost:8000/api/v1/health
   curl http://localhost:8000/api/v1/agent/health
   ```

2. **Reload VS Code:**
   ```
   Ctrl+Shift+P → "Developer: Reload Window"
   ```

3. **Check MCP:**
   ```
   View → Output → "MCP Servers"
   ```

4. **Test in Copilot:**
   ```
   Copilot Chat → "@workspace What is Phase 1?"
   ```

5. **Start Workers (optional):**
   ```powershell
   .\start_workers.ps1
   ```

---

## 🎯 Expected Final State

When everything is running correctly:

```
✅ Redis: localhost:6379
✅ Backend API: localhost:8000
✅ MCP Server: Connected to backend
✅ Agent-to-Agent: Accessible via MCP tools
✅ Queue System: Ready (workers optional)
```

---

## 🚨 Quick Troubleshooting

### Backend won't start?

```powershell
# Check if port 8000 is occupied
netstat -ano | findstr :8000

# Kill process if needed (replace PID)
Stop-Process -Id <PID> -Force
```

### MCP still showing "spawn python ENOENT"?

Edit `.vscode/mcp.json`:
```json
"agent-to-agent-bridge": {
  "command": "D:\\bybit_strategy_tester_v2\\.venv\\Scripts\\python.exe",
  // ...
}
```

### Agent tests failing?

```powershell
# Re-run tests
py test_agent_to_agent.py
```

---

**ACTION**: Start backend NOW, then reload VS Code!

```powershell
# Copy-paste this:
& D:/bybit_strategy_tester_v2/.venv/Scripts/Activate.ps1 ; uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```
