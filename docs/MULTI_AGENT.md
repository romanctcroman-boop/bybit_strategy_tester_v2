# Multi-Agent AI Architecture для VS Code

## 🎯 Обзор

Мультиагентная AI-платформа для VS Code, интегрирующая:
- **GitHub Copilot** - IDE-ассистент, автодополнение
- **DeepSeek API** - кодогенерация, рефакторинг, глубокий reasoning
- **Perplexity Sonar Pro** - логический анализ, research, аудит

Все агенты объединены через **MCP Router** - центральный оркестратор с автоматической маршрутизацией и fallback механизмом.

## 📐 Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        VS Code                              │
│  (Hotkeys, Tasks, Commands, Selection, Terminal)           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Router                               │
│  • Анализ задачи                                            │
│  • Автоматическая маршрутизация                            │
│  • Fallback между агентами                                 │
│  • Pipeline execution                                       │
│  • Request logging (request_id)                            │
└────┬──────────────┬──────────────┬─────────────────────────┘
     │              │              │
     ▼              ▼              ▼
┌─────────┐   ┌──────────┐   ┌────────────┐
│ Copilot │   │ DeepSeek │   │ Sonar Pro  │
│         │   │   API    │   │    API     │
│ (VS Ext)│   │          │   │            │
└─────────┘   └──────────┘   └────────────┘
```

## 🚀 Быстрый старт

### 1. Настройка API ключей

```bash
# .env файл
PERPLEXITY_API_KEY=pplx-xxxxx
DEEPSEEK_API_KEY=sk-xxxxx
```

### 2. Запуск MCP сервера

```bash
cd mcp-server
python server.py
```

### 3. Использование из VS Code

#### Через Tasks (Ctrl+Shift+P → "Tasks: Run Task")
- **AI: Generate Code (DeepSeek)** - Генерация кода
- **AI: Refactor Code (DeepSeek)** - Рефакторинг текущего файла
- **AI: Analyze Logic (Sonar Pro)** - Анализ логики кода
- **AI: Code Review Workflow** - Полный code review pipeline
- **AI: Strategy Development Workflow** - Разработка торговой стратегии

#### Через Hotkeys
- `Ctrl+Shift+G` - Generate Code
- `Ctrl+Shift+R` - Refactor Code
- `Ctrl+Shift+A` - Analyze Logic
- `Ctrl+Shift+E` - Explain Code (на выделенном тексте)
- `Ctrl+Shift+D` - Generate Documentation
- `Ctrl+Shift+W Ctrl+Shift+C` - Code Review Workflow
- `Ctrl+Shift+W Ctrl+Shift+S` - Strategy Development Workflow
- `Ctrl+Shift+W Ctrl+Shift+R` - Refactor with Audit Workflow

#### Через CLI

```bash
# Генерация кода
python mcp-server/vscode_integration.py \
  --task code-generation \
  --prompt "Create a FastAPI endpoint for user authentication"

# Рефакторинг файла
python mcp-server/vscode_integration.py \
  --task refactoring \
  --file backend/api/app.py

# Анализ логики
python mcp-server/vscode_integration.py \
  --task logic-analysis \
  --file backend/services/data_service.py

# Workflow: Code Review
python mcp-server/vscode_integration.py \
  --workflow code-review \
  --file backend/core/backtest.py
```

## 🎯 Типы задач и маршрутизация

### Copilot Tasks
| Task Type | Description | Primary Agent | Fallback |
|-----------|-------------|---------------|----------|
| `context-completion` | Автодополнение кода | Copilot | - |
| `ide-integration` | Работа с IDE/терминалом | Copilot | - |
| `quick-fix` | Быстрые исправления | Copilot | DeepSeek |

### DeepSeek Tasks
| Task Type | Description | Primary Agent | Fallback |
|-----------|-------------|---------------|----------|
| `code-generation` | Генерация кода | DeepSeek | Copilot |
| `refactoring` | Рефакторинг | DeepSeek | - |
| `deep-reasoning` | Глубокий анализ | DeepSeek | Sonar Pro |
| `batch-operations` | Массовые операции | DeepSeek | - |
| `documentation` | Генерация документации | DeepSeek | Sonar Pro |

### Sonar Pro Tasks
| Task Type | Description | Primary Agent | Fallback |
|-----------|-------------|---------------|----------|
| `logic-analysis` | Анализ логики | Sonar Pro | DeepSeek |
| `audit` | Аудит кода/решений | Sonar Pro | - |
| `research` | Исследование и поиск | Sonar Pro | - |
| `explain` | Объяснения | Sonar Pro | - |
| `strategy-review` | Ревью торговых стратегий | Sonar Pro | DeepSeek |

## 🔄 Pipeline Workflows

### 1. Code Review Workflow

```json
{
  "steps": [
    {
      "name": "analyze_logic",
      "task_type": "logic-analysis",
      "agent": "sonar-pro",
      "data": {"query": "Analyze code logic and potential issues"}
    },
    {
      "name": "generate_improvements",
      "task_type": "code-generation",
      "agent": "deepseek",
      "data": {"prompt": "Generate improved version based on analysis"}
    },
    {
      "name": "create_summary",
      "task_type": "explain",
      "agent": "sonar-pro",
      "data": {"query": "Summarize improvements"}
    }
  ]
}
```

**Использование:**
```bash
python mcp-server/vscode_integration.py \
  --workflow code-review \
  --file backend/core/backtest.py
```

### 2. Strategy Development Workflow

```json
{
  "steps": [
    {
      "name": "research_approach",
      "task_type": "research",
      "agent": "sonar-pro",
      "data": {"query": "Research RSI mean reversion strategies"}
    },
    {
      "name": "generate_code",
      "task_type": "code-generation",
      "agent": "deepseek",
      "data": {"prompt": "Generate Python strategy class"}
    },
    {
      "name": "create_documentation",
      "task_type": "documentation",
      "agent": "deepseek",
      "data": {"prompt": "Create comprehensive documentation"}
    }
  ]
}
```

### 3. Refactor with Audit Workflow

```json
{
  "steps": [
    {
      "name": "refactor",
      "task_type": "refactoring",
      "agent": "deepseek"
    },
    {
      "name": "audit",
      "task_type": "audit",
      "agent": "sonar-pro"
    },
    {
      "name": "final_improvements",
      "task_type": "code-generation",
      "agent": "deepseek"
    }
  ]
}
```

## 🔌 MCP Tools

### 1. multi_agent_route

Базовая маршрутизация задач.

```python
await multi_agent_route(
    task_type="code-generation",
    prompt="Create a FastAPI endpoint",
    context={"framework": "FastAPI", "auth": "JWT"}
)
```

**Response:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": "code-generation",
  "agent": "deepseek",
  "status": "success",
  "result": "# Generated code here...",
  "metadata": {
    "execution_time": 2.34,
    "model": "deepseek-coder",
    "usage": {"tokens": 450}
  }
}
```

### 2. multi_agent_pipeline

Выполнение цепочки задач.

```python
await multi_agent_pipeline(
    steps=[
        {"name": "analyze", "task_type": "logic-analysis", ...},
        {"name": "improve", "task_type": "code-generation", ...}
    ]
)
```

### 3. list_available_agents

Список всех агентов и их возможностей.

```python
await list_available_agents()
```

### 4. get_routing_info

Информация о маршрутизации для задачи.

```python
await get_routing_info(task_type="code-generation")
```

**Response:**
```json
{
  "task_type": "code-generation",
  "primary_agent": "deepseek",
  "fallback_agents": ["copilot"],
  "total_agents": 2,
  "auto_fallback": true
}
```

## 🛠️ Advanced Features

### Context Preprocessing

MCP Router автоматически обрабатывает контекст:
- AST анализ (будущее расширение)
- Структура проекта
- История git (будущее расширение)
- Зависимости

### Fallback Mechanism

Если primary agent недоступен или ошибается:
1. Автоматический fallback на следующий agent
2. Логирование попыток
3. Возврат результата от успешного агента

```python
# Пример: code-generation
# Primary: DeepSeek → Fallback: Copilot

# Если DeepSeek недоступен
{
  "primary_agent": "deepseek",
  "status": "error",
  "fallback_to": "copilot"
}
```

### Request Logging

Каждый запрос получает уникальный `request_id`:

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-10-31T14:30:00",
  "task_type": "code-generation",
  "agent": "deepseek",
  "status": "success",
  "execution_time": 2.34
}
```

Логи сохраняются для диагностики и воспроизводимости.

## 📝 Примеры использования

### 1. Генерация кода с контекстом

```python
result = await multi_agent_route(
    task_type="code-generation",
    prompt="Create a FastAPI endpoint for user registration",
    context={
        "framework": "FastAPI",
        "database": "PostgreSQL",
        "auth": "JWT",
        "validation": "Pydantic"
    }
)
```

### 2. Анализ торговой стратегии

```python
result = await multi_agent_route(
    task_type="strategy-review",
    query="Review this RSI mean reversion strategy for edge cases",
    context={"code": open("strategy.py").read()}
)
```

### 3. Полный workflow разработки

```bash
# 1. Research
python vscode_integration.py \
  --task research \
  --prompt "Best practices for async FastAPI endpoints"

# 2. Generate
python vscode_integration.py \
  --task code-generation \
  --prompt "Create async endpoint based on research"

# 3. Review
python vscode_integration.py \
  --workflow code-review \
  --file api/endpoints/users.py
```

## 🔒 Security \& Rate Limiting

### API Keys Management
- Храним в `.env` файле
- **НЕ коммитим** в git
- Используем secure storage

### Rate Limiting
- Автоматический retry с backoff
- Fallback на другие агенты
- Логирование rate limit errors

## 🧪 Testing

### Unit Tests

```bash
pytest mcp-server/tests/test_router.py
```

### Integration Tests

```bash
# Test с реальными API
pytest mcp-server/tests/test_integration.py --api-keys

# Test с моками
pytest mcp-server/tests/test_integration.py
```

## 📊 Monitoring \& Analytics

### Request Stats

```python
# Получение статистики
router = get_router()
stats = router.request_logs

# Анализ успешности агентов
success_rate = {
    "deepseek": count_success("deepseek") / total,
    "sonar-pro": count_success("sonar-pro") / total
}
```

## 🔮 Future Enhancements

### Planned Features
1. **AST Preprocessing** - Глубокий анализ структуры кода
2. **Git Integration** - Анализ истории изменений
3. **Project Graph** - Граф зависимостей проекта
4. **Custom Agents** - Плагинная архитектура для новых AI API
5. **Web Dashboard** - UI для мониторинга и управления
6. **Streaming Responses** - Real-time вывод результатов
7. **Collaborative Pipelines** - Совместные workflows

## 📚 API Reference

### TaskType Enum

```python
class TaskType(str, Enum):
    # Copilot
    CONTEXT_COMPLETION = "context-completion"
    IDE_INTEGRATION = "ide-integration"
    QUICK_FIX = "quick-fix"
    
    # DeepSeek
    CODE_GENERATION = "code-generation"
    REFACTORING = "refactoring"
    DEEP_REASONING = "deep-reasoning"
    BATCH_OPERATIONS = "batch-operations"
    DOCUMENTATION = "documentation"
    
    # Sonar Pro
    LOGIC_ANALYSIS = "logic-analysis"
    AUDIT = "audit"
    RESEARCH = "research"
    EXPLAIN = "explain"
    STRATEGY_REVIEW = "strategy-review"
    
    # Pipeline
    PIPELINE = "pipeline"
    MULTI_AGENT = "multi-agent"
```

### AgentType Enum

```python
class AgentType(str, Enum):
    COPILOT = "copilot"
    DEEPSEEK = "deepseek"
    SONAR_PRO = "sonar-pro"
```

## 🤝 Contributing

### Adding New Agents

1. Create client class:
```python
class NewAgentClient(BaseAgentClient):
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Implementation
        pass
```

2. Register in router:
```python
self.new_agent_client = NewAgentClient()
```

3. Add to routing table:
```python
self.task_routing[TaskType.NEW_TASK] = [AgentType.NEW_AGENT]
```

## 📄 License

MIT License - см. LICENSE файл

## 📞 Support

- GitHub Issues: [bybit_strategy_tester_v2/issues](https://github.com/RomanCTC/bybit_strategy_tester_v2/issues)
- Документация: `docs/MULTI_AGENT.md`
- MCP Server Logs: `logs/mcp-server-startup.log`

---

**Version:** 1.0.0  
**Last Updated:** October 31, 2025  
**Status:** ✅ Production Ready
