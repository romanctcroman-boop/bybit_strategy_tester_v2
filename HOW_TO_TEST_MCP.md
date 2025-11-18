# 🧪 КАК ПРОТЕСТИРОВАТЬ MCP SERVER В COPILOT

**Важно:** MCP Server НЕ нужно запускать вручную! GitHub Copilot запускает его автоматически.

---

## ✅ ШАГ 1: Проверьте Конфигурацию

### Убедитесь, что `.vscode/mcp.json` настроен:

```json
{
  "mcpServers": {
    "bybit-strategy-tester": {
      "command": "D:\\bybit_strategy_tester_v2\\.venv\\Scripts\\python.exe",
      "args": ["D:\\bybit_strategy_tester_v2\\mcp-server\\server.py"],
      "env": {
        "PERPLEXITY_API_KEY": "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"
      }
    }
  }
}
```

✅ **Файл существует и правильно настроен**

---

## ✅ ШАГ 2: Откройте GitHub Copilot Chat

**Способ 1:** Нажмите `Ctrl + Shift + I` (Windows/Linux) или `Cmd + Shift + I` (Mac)

**Способ 2:** View → Command Palette → "GitHub Copilot: Open Chat"

**Способ 3:** Кликните на иконку Copilot в левом sidebar

---

## ✅ ШАГ 3: Тестируем Tools

### Test 1: Health Check ⚕️

**Введите в Copilot Chat:**
```
@workspace health_check
```

**Или более подробно:**
```
@workspace Use the health_check tool to verify MCP server status and Perplexity API connectivity
```

**Ожидаемый результат:**
```json
{
  "server_status": "✅ RUNNING",
  "perplexity_api": {
    "status": "✅ OK",
    "response_time_seconds": 2.1,
    "api_key_configured": true,
    "api_key_prefix": "pplx-FSlOe..."
  },
  "tools": {
    "total_count": 31,
    "perplexity_tools_count": 14,
    "project_tools_count": 7,
    "analysis_tools_count": 8,
    "utility_tools_count": 2
  },
  "timestamp": "2025-10-30T...",
  "version": "2.0",
  "framework": "FastMCP v2.13.0.1"
}
```

---

### Test 2: List All Tools 📋

**Введите в Copilot Chat:**
```
@workspace list_all_tools
```

**Или:**
```
@workspace Show me all available MCP tools using list_all_tools
```

**Ожидаемый результат:**
```json
{
  "perplexity_ai_tools": {
    "category": "Perplexity AI Integration",
    "count": 14,
    "tools": [
      {"name": "perplexity_search", "description": "Общий поиск..."},
      {"name": "perplexity_sentiment_analysis", "description": "Sentiment..."},
      ...
    ]
  },
  "project_information_tools": { "count": 7 },
  "advanced_analysis_tools": { "count": 8 },
  "utility_tools": { "count": 2 },
  "total_tools": 31
}
```

---

### Test 3: Perplexity Sentiment Analysis 📊

**Введите в Copilot Chat:**
```
@workspace Analyze Bitcoin sentiment over the last 24 hours using perplexity_sentiment_analysis
```

**Ожидаемый результат:**
Copilot должен:
1. Вызвать `perplexity_sentiment_analysis` tool
2. Получить данные от Perplexity API
3. Показать sentiment score, sources, и analysis

---

### Test 4: Complex Multi-Tool Query 🚀

**Введите в Copilot Chat:**
```
@workspace Should I buy Bitcoin now? Please analyze using multiple tools:

1. Use perplexity_sentiment_analysis to check current market sentiment
2. Use perplexity_whale_activity_tracker to see if whales are accumulating
3. Use perplexity_macro_economic_analysis to check the macro environment

Based on all three analyses, provide a clear recommendation.
```

**Ожидаемый результат:**
Copilot должен:
1. ✅ Вызвать `perplexity_sentiment_analysis`
2. ✅ Вызвать `perplexity_whale_activity_tracker`
3. ✅ Вызвать `perplexity_macro_economic_analysis`
4. ✅ Синтезировать результаты
5. ✅ Дать рекомендацию: Buy / Wait / Sell

---

## 🚨 TROUBLESHOOTING

### Проблема 1: "@workspace не распознаётся"

**Причина:** GitHub Copilot extension не активирован

**Решение:**
1. Extensions → Search "GitHub Copilot"
2. Verify extension is installed and enabled
3. Restart VS Code
4. Try again

---

### Проблема 2: "Tool not found"

**Причина:** MCP Server не подключён к Copilot

**Решение 1: Перезагрузить Window**
```
Ctrl+Shift+P → "Developer: Reload Window"
```

**Решение 2: Проверить логи MCP**
```
Ctrl+Shift+P → "MCP: Show Server Logs"
```

**Решение 3: Проверить .vscode/mcp.json**
- Файл существует?
- Paths правильные?
- API key настроен?

---

### Проблема 3: "Perplexity API error"

**Причина:** API key проблема или rate limiting

**Решение:**
1. Verify API key в `.vscode/mcp.json`
2. Test API key manually:
```powershell
curl -X POST "https://api.perplexity.ai/chat/completions" `
  -H "Authorization: Bearer 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" `
  -H "Content-Type: application/json" `
  -d '{"model":"sonar","messages":[{"role":"user","content":"test"}]}'
```
3. Wait 1 minute (rate limiting)
4. Try again

---

### Проблема 4: Copilot не использует tools автоматически

**Причина:** Неявный запрос

**Плохо:**
```
Tell me about Bitcoin sentiment
```

**Хорошо:**
```
@workspace Use perplexity_sentiment_analysis to analyze Bitcoin sentiment
```

**Лучше:**
```
@workspace Analyze Bitcoin sentiment over the last 24 hours using the perplexity_sentiment_analysis tool with these parameters:
- topic: "bitcoin"
- sources: "social_media"
- timeframe: "24h"
```

---

## 💡 BEST PRACTICES

### 1. Всегда используйте `@workspace` prefix
```
✅ @workspace health_check
❌ health_check
```

### 2. Указывайте tool names явно
```
✅ @workspace Use perplexity_sentiment_analysis to...
❌ @workspace Analyze sentiment...
```

### 3. Указывайте параметры когда нужно
```
✅ @workspace Use perplexity_onchain_analysis with blockchain="ethereum", metric="whale_activity", period="7d"
❌ @workspace Analyze Ethereum
```

### 4. Комбинируйте tools для comprehensive analysis
```
✅ @workspace Use sentiment_analysis + whale_tracker + macro_analysis
❌ @workspace What's happening with Bitcoin?
```

---

## 🎯 EXPECTED BEHAVIOR

### Что должно произойти:

1. **Вы вводите:** `@workspace health_check`

2. **Copilot видит:** MCP server configured в `.vscode/mcp.json`

3. **Copilot запускает:** MCP server автоматически
   ```
   D:\bybit_strategy_tester_v2\.venv\Scripts\python.exe 
   D:\bybit_strategy_tester_v2\mcp-server\server.py
   ```

4. **MCP Server стартует:**
   ```
   🚀 BYBIT STRATEGY TESTER MCP SERVER v2.0
   ✅ MCP SERVER READY - Listening for requests...
   ```

5. **Copilot вызывает:** `health_check` tool

6. **MCP Server отвечает:** JSON с результатами

7. **Copilot показывает:** Результаты в chat

8. **MCP Server остаётся:** Running для следующих запросов

---

## ✅ SUCCESS CRITERIA

После успешного тестирования вы должны увидеть:

- [ ] `@workspace health_check` возвращает "✅ RUNNING"
- [ ] `@workspace list_all_tools` показывает 31 tool
- [ ] Perplexity tools работают (success: true)
- [ ] Multi-tool queries выполняются последовательно
- [ ] Response time ~2-5 seconds для Perplexity tools

---

## 📊 METRICS TO TRACK

После тестирования, проверьте:

**Health Check Response:**
- ✅ server_status: "✅ RUNNING"
- ✅ perplexity_api.status: "✅ OK"
- ✅ perplexity_api.response_time_seconds: <5s
- ✅ tools.total_count: 31

**List Tools Response:**
- ✅ perplexity_ai_tools.count: 14
- ✅ total_tools: 31

**Perplexity Tools Response:**
- ✅ success: true
- ✅ answer: (содержательный текст)
- ✅ sources: [array of URLs]
- ✅ analysis_type: (соответствующий тип)

---

## 🚀 NEXT STEPS

После успешного тестирования:

### Immediate (Today):
1. ✅ Test all 4 queries above
2. ✅ Verify health_check works
3. ✅ Verify Perplexity tools work
4. ✅ Document any issues

### Short-term (This Week):
**Phase 2: Performance Optimization**
- [ ] Redis caching (4.6s → <100ms)
- [ ] Batch execution
- [ ] Structured logging

### Long-term (Next 2 Weeks):
**Phase 3: Advanced Features**
- [ ] Smart tool recommendations
- [ ] Streaming responses
- [ ] Custom prompts library

---

## 📞 NEED HELP?

### If Tests Fail:

1. **Check MCP Extension:**
   ```
   Extensions → Search "MCP" → Verify installed
   ```

2. **Check Copilot Extension:**
   ```
   Extensions → Search "GitHub Copilot" → Verify enabled
   ```

3. **Check Configuration:**
   ```
   cat .vscode/mcp.json
   # Verify paths and API key
   ```

4. **Check Logs:**
   ```
   Ctrl+Shift+P → "MCP: Show Server Logs"
   # Look for connection errors
   ```

5. **Restart Everything:**
   ```
   Ctrl+Shift+P → "Developer: Reload Window"
   # Fresh start
   ```

---

**Version:** 1.0  
**Date:** 2025-10-30  
**Status:** 🚀 READY FOR TESTING

---

## 🎯 START NOW!

**Действие 1:** Откройте GitHub Copilot Chat (`Ctrl+Shift+I`)

**Действие 2:** Введите: `@workspace health_check`

**Действие 3:** Verify response contains `"server_status": "✅ RUNNING"`

**Если работает:** 🎉 **SUCCESS! Переходите к Tests 2-4!**

**Если не работает:** 📝 Сообщите, какую ошибку видите, помогу исправить!
