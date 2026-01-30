# GitHub Copilot Instructions - Usage Guide

**Last Updated:** 2026-01-30
**Version:** 1.0

---

## File Structure Overview

```
.github/
├── copilot-instructions.md           # Main rules file (loaded automatically)
├── instructions/                     # Path-specific rules
│   ├── strategies.instructions.md    # Rules for strategy files
│   ├── api-connectors.instructions.md # Rules for API integrations
│   ├── backtester.instructions.md    # Rules for backtesting engine
│   ├── api-endpoints.instructions.md # Rules for FastAPI endpoints
│   └── tests.instructions.md         # Rules for test files
└── prompts/                          # Reusable prompts
    ├── analyze-task.prompt.md        # Task analysis workflow
    ├── safe-refactor.prompt.md       # Safe refactoring protocol
    ├── add-strategy.prompt.md        # Add new strategy workflow
    ├── add-api-endpoint.prompt.md    # Add new API endpoint workflow
    └── debug-session.prompt.md       # Debug session protocol

.copilot/
├── session-template.md               # Template for session tracking
└── variable-tracker.md               # Variable tracking (manual)

docs/
└── ai-context.md                     # Project context (manual updates)
```

---

## How It Works

### 1. Automatic Rules (copilot-instructions.md)

The main instructions file is automatically loaded by GitHub Copilot for every conversation. It contains:

- Core workflow rules
- Critical project rules
- Code patterns
- Testing standards

### 2. Path-Specific Rules (instructions/\*.instructions.md)

These files apply rules based on file paths:

- When editing `**/strategies/**/*.py` → `strategies.instructions.md` applies
- When editing `**/adapters/**/*.py` → `api-connectors.instructions.md` applies
- etc.

### 3. Reusable Prompts (prompts/\*.prompt.md)

Use these for specific workflows. Reference them in chat:

```
Use @analyze-task to analyze this task:
[Your task description]
```

Or copy-paste the prompt content when starting a complex task.

---

## How to Use

### Starting a Session

1. **Read context:**

    ```
    Please read docs/ai-context.md to understand the current project state.
    ```

2. **Check variables:**

    ```
    Check .copilot/variable-tracker.md for critical variables.
    ```

3. **Use session template:**
   Copy `.copilot/session-template.md` and fill in your session goals.

### For Complex Tasks

1. **Analyze first:**

    ```
    Use the analyze-task prompt to analyze this task:
    [Task description]
    ```

2. **Wait for approval** before implementation.

3. **Validate after** each step.

### For Refactoring

1. **Use safe-refactor prompt:**

    ```
    Use the safe-refactor prompt for this refactoring:
    [What you want to refactor]
    ```

2. **Create checkpoints** after each step.

3. **Verify no variables lost.**

### For Adding Features

**New Strategy:**

```
Use the add-strategy prompt:
Strategy Name: EMA Crossover
Indicators: EMA 12, EMA 26
Entry: Fast EMA crosses above slow EMA (long)
Parameters: fast_period, slow_period
```

**New API Endpoint:**

```
Use the add-api-endpoint prompt:
Path: /api/v1/optimize
Method: POST
Purpose: Run strategy optimization
```

### Ending a Session

1. **Update docs/ai-context.md** with session summary
2. **Update .copilot/variable-tracker.md** if variables changed
3. **Commit changes** with descriptive message

---

## Quick Reference

### Run Commands

```powershell
# Start server
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=backend --cov-report=term-missing

# Lint check
ruff check .

# Format code
ruff format .
```

### Critical Rules Reminder

1. **Commission rate = 0.0007 (0.07%)** - Never change without approval
2. **Use FallbackEngineV2** as gold standard for backtesting
3. **Never hardcode API keys** - Use environment variables
4. **Track all variables** before refactoring
5. **Run tests** after every change

### File Location Shortcuts

| What            | Where                                               |
| --------------- | --------------------------------------------------- |
| Main API        | `backend/api/app.py`                                |
| Backtest engine | `backend/backtesting/engines/fallback_engine_v2.py` |
| Strategies      | `backend/backtesting/strategies/`                   |
| API routers     | `backend/api/routers/`                              |
| Tests           | `tests/`                                            |
| Frontend        | `frontend/`                                         |

---

## Customization

### Adding New Path-Specific Rules

Create a new file in `.github/instructions/`:

```markdown
---
applyTo: "**/your/path/**/*.py"
---

# Your Rules Title

[Your rules content]
```

### Adding New Prompts

Create a new file in `.github/prompts/`:

```markdown
# Prompt Title

[Your prompt workflow]
```

### Updating Main Rules

Edit `.github/copilot-instructions.md` to add/modify global rules.

---

## Comparison: Copilot vs Cursor

| Feature             | Cursor  | Copilot (This System)           |
| ------------------- | ------- | ------------------------------- |
| Modular rules       | ✅ Auto | ⚠️ Single main file             |
| Path-specific       | ✅      | ✅ (identical)                  |
| Prompt files        | ✅      | ✅ (identical)                  |
| Context persistence | ✅ Auto | ⚠️ Manual (ai-context.md)       |
| Variable tracking   | ✅ Auto | ⚠️ Manual (variable-tracker.md) |
| Agent mode          | ✅      | ❌ Not available                |
| MCP servers         | ✅      | ❌ Not available                |

**Key difference:** In Copilot, you need to **manually** maintain `ai-context.md` and `variable-tracker.md`.

---

## Troubleshooting

### Rules Not Applying?

1. Check file path matches `applyTo` pattern
2. Verify file is saved
3. Restart VS Code if needed

### Prompts Not Working?

1. Copy-paste prompt content directly
2. Or reference: "Follow the workflow in .github/prompts/[name].prompt.md"

### Context Lost Between Sessions?

1. Always update `docs/ai-context.md` at session end
2. Read it at session start
3. Use session template for tracking
