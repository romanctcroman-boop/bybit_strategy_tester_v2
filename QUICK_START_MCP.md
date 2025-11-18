# 🚀 БЫСТРЫЙ СТАРТ MCP СЕРВЕРА

## Запуск сервера (3 способа):

### 1️⃣ Простой запуск (рекомендуется):
```powershell
.\scripts\start_mcp_simple.ps1
```

### 2️⃣ Production запуск (с логами):
```powershell
.\scripts\start_mcp_server.ps1
```

### 3️⃣ Прямой запуск (для отладки):
```powershell
.\.venv\Scripts\python.exe .\mcp-server\server.py
```

---

## ✅ Проверка работы:

После запуска должно появиться:
```
🔧 Available Tools: 🎉 49 total (PREMIUM + CHAIN-OF-THOUGHT + CACHING)
   ├─ 🚀 Perplexity AI Tools: 27
   ├─ 🧠 Chain-of-Thought Tools: 2 (NEW!)
   ├─ 📁 Project Info Tools: 7
   ├─ 📊 Analysis Tools: 8
   └─ 🛠️ Utility Tools: 5

✅ MCP SERVER READY - Listening for requests...
```

---

## 🔧 Новые возможности:

### Chain-of-Thought Analysis:
```
tool: chain_of_thought_analysis
query: "Analyze BTCUSDT and suggest strategy"
```

### Quick Reasoning:
```
tool: quick_reasoning_analysis
query: "What's current BTC trend?"
```

### Market Analysis:
```
tool: market_analysis_reasoning
symbol: "BTCUSDT"
timeframe: "4h"
```

---

## 📁 Документация:

- **MCP_SERVER_STATUS.md** - полный статус и документация
- **PHASE_1_QUICK_START_COMPLETE.md** - отчёт о выполненной работе
- **DEEPSEEK_FINAL_EXECUTIVE_REPORT.md** - коды от DeepSeek API

---

**Статус**: ✅ Сервер работает идеально  
**MCP Score**: 6/10 (+2 после Phase 1)  
**Tools**: 49 (включая 2 новых Chain-of-Thought)
