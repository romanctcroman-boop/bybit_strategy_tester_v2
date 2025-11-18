# 🧪 How to Test VS Code Extension

## ✅ Prerequisites
- ✅ Backend running on `http://localhost:8000` (separate terminal)
- ✅ Extension compiled (`vscode-extension/out/extension.js` exists)
- ✅ WebSocket endpoint: `ws://localhost:8000/api/v1/agent/ws`

## 📋 Testing Steps

### 1. Open Extension Workspace
```powershell
# Navigate to extension folder
cd D:\bybit_strategy_tester_v2\vscode-extension

# Open in VS Code (or use File > Open Folder)
code .
```

### 2. Launch Extension Development Host
- Press **F5** (or Run > Start Debugging)
- New VS Code window will open with extension loaded
- Check Output panel for "Agent Bridge: Connected to ws://localhost:8000/..."

### 3. Test Commands

#### Test 1: Send to DeepSeek Agent
1. Open any file (e.g., create `test.txt`)
2. Type: "What is Agent-to-Agent communication?"
3. Select the text
4. Press **Ctrl+Shift+P** → Type "Send to DeepSeek Agent"
5. Wait for response (should appear in notification or output panel)

#### Test 2: Get Multi-Agent Consensus
1. Select text: "Which is better for trading: EMA or SMA?"
2. Press **Ctrl+Shift+P** → Type "Get Multi-Agent Consensus"
3. Wait for responses from both DeepSeek and Perplexity
4. Check consensus result

#### Test 3: Context Menu Integration
1. Select any code/text
2. Right-click → Should see "Agent Bridge" submenu with:
   - Send to DeepSeek Agent
   - Send to Perplexity Agent
   - Get Multi-Agent Consensus

### 4. Verify WebSocket Connection
- Check VS Code Output panel (View > Output)
- Select "Agent Bridge" from dropdown
- Should see:
  ```
  [Agent Bridge] Connecting to ws://localhost:8000/api/v1/agent/ws/vscode-copilot
  [Agent Bridge] Connected! Client ID: vscode-copilot
  [Agent Bridge] Pong received: {"type":"pong"}
  ```

## 🔍 Expected Behavior

### Successful Test Indicators:
- ✅ Extension activates on startup (check status bar)
- ✅ WebSocket connection established (green indicator)
- ✅ Commands appear in Command Palette (Ctrl+Shift+P)
- ✅ Context menu shows Agent Bridge options
- ✅ Agent responses appear within 5-10 seconds
- ✅ Notifications show agent responses

### Troubleshooting:
❌ **"Connection refused"** → Backend not running
   - Solution: Start backend in separate terminal: `py run_backend.py`

❌ **"Extension not found"** → Not compiled
   - Solution: `cd vscode-extension; npm run compile`

❌ **"Commands not visible"** → Extension not activated
   - Solution: Reload window (Ctrl+Shift+P → "Reload Window")

## 📊 Extension Configuration

Settings (File > Preferences > Settings > Extensions > Agent-to-Agent Bridge):
- `agentBridge.serverUrl`: WebSocket URL (default: ws://localhost:8000/api/v1/agent/ws)
- `agentBridge.autoConnect`: Auto-connect on startup (default: true)
- `agentBridge.defaultAgent`: Default agent (deepseek/perplexity/auto)
- `agentBridge.showNotifications`: Show response notifications (default: true)
- `agentBridge.maxResponseLength`: Max response length (default: 5000)

## 🎯 Full Test Scenario

### Scenario: Multi-Agent Collaboration
1. Open new file: `test-collaboration.md`
2. Write: "Analyze the pros and cons of microservices architecture for a trading platform"
3. Select text
4. Run: "Get Multi-Agent Consensus"
5. Expected:
   - DeepSeek provides technical analysis
   - Perplexity provides industry research
   - Consensus combines both perspectives
   - Response time: 10-30 seconds

### Scenario: Iterative Conversation
1. Send: "What is machine learning?" → DeepSeek
2. Wait for response
3. Send: "Now explain neural networks" → DeepSeek (same conversation)
4. Expected:
   - Conversation context preserved
   - Second response builds on first

## 📈 Performance Metrics

**Target Performance:**
- Initial connection: <1s
- Simple query (DeepSeek): 3-8s
- Consensus (2 agents): 10-30s
- WebSocket ping/pong: <100ms

**Current Performance (from test results):**
- Basic routing: 5.5s ✅
- Collaborative: 41s (3 messages)
- Consensus: 34.6s
- Multi-turn: 24.7s

## 🎉 Success Criteria

Extension test is **PASSED** if:
- ✅ Extension loads without errors
- ✅ WebSocket connection established
- ✅ At least 1 successful message to DeepSeek
- ✅ Response displayed in UI
- ✅ Commands visible in Command Palette
- ✅ Context menu integration works

## 📝 Next Steps After Testing

1. Package extension: `vsce package`
2. Install locally: `code --install-extension agent-to-agent-bridge-1.0.0.vsix`
3. Production deployment (optional)

---

**Status**: Ready for testing ✅
**Backend**: Running on port 8000 ✅
**Test Suite**: 5/5 passed (100%) ✅
