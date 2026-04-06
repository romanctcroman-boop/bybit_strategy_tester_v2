# Session Infrastructure — Memory Bank & Hooks

## Memory Bank (`memory-bank/`)

After completing a significant task:
- Update `memory-bank/activeContext.md` — what was done + next steps
- Update `memory-bank/progress.md` — when a bug is fixed or feature is added

Rarely updated: `projectBrief.md`, `productContext.md`, `systemPatterns.md`, `techContext.md`

## Hooks (`.claude/hooks/`, configured in `.claude/settings.json`)

| Hook | Event | Purpose |
|------|-------|---------|
| `protect_files.py` | PreToolUse Edit\|Write | Blocks .env, alembic/versions/, .git/, *.lock |
| `commission_guard.py` | PreToolUse Edit\|Write | Blocks commission≠0.0007 in Python files |
| `ruff_format.py` | PostToolUse Edit\|Write | Auto-format Python files on save |
| `post_edit_tests.py` | PostToolUse Edit\|Write | Auto-run targeted pytest after backend edits |
| `session_start_context.py` | SessionStart | Load Memory Bank into context |
| `post_compact_context.py` | PostCompact | Re-inject critical constants after compaction |
| `stop_reminder.py` | Stop | Remind to update activeContext.md |
| `post_tool_failure.py` | PostToolUseFailure | Context-aware hints when tools fail |

**Hook test mapping:** editing a backend file triggers targeted test suite, e.g. edit `backend/backtesting/engine.py` → runs `tests/backend/backtesting/test_engine.py`.

## Custom Agents (`.claude/agents/`)

| Agent | Use When |
|-------|----------|
| `backtesting-expert` | Deep engine/adapter analysis, parity investigation, signal routing bugs |
| `optimizer-expert` | Optimization pipeline issues, scoring/ranking, Optuna config |
| `agent-system-expert` | LangGraph pipeline bugs, memory/consensus/debate issues, self-improvement loop |
| `implementer` | Implementing features, fixing bugs, code changes across the project |

## Path-Scoped Rules (`.claude/rules/` — load automatically when working in those paths)

| File | Loaded when editing |
|------|---------------------|
| `backtesting.md` | `backend/backtesting/**`, `backend/core/metrics_calculator.py`, `tests/backend/backtesting/**` |
| `api.md` | `backend/api/**`, `tests/backend/api/**` |
| `agents.md` | `backend/agents/**`, `tests/backend/agents/**`, `tests/ai_agents/**` |
| `frontend.md` | `frontend/**` |
| `optimization.md` | `backend/optimization/**`, `tests/backend/optimization/**` |
