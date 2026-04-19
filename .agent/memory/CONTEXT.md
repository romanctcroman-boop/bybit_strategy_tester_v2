# Project Context Summary

## Bybit Strategy Tester v2

> Auto-generated context for agent sessions.
> Last updated: 2026-02-14

---

## Quick Reference

### Project Type

- **Type**: Trading/Finance Platform
- **Language**: Python 3.14 + JavaScript
- **Framework**: FastAPI + SQLAlchemy
- **Database**: SQLite
- **Agent Models**: Claude Sonnet 4 / Opus 4, Gemini 3 Pro

### Key Commands

```powershell
# Start all services (VS Code task or script)
.\start_all.ps1

# Run tests
pytest tests/ -v

# Lint code
ruff check . --fix
ruff format .

# Run backtest
py -3.14 scripts/calibrate_166_metrics.py
```

### Critical Files

- `backend/core/metrics_calculator.py` — 166 TradingView-parity metrics
- `backend/backtesting/engines/fallback_engine_v4.py` — Gold standard engine (V4)
- `backend/services/adapters/bybit.py` — Bybit API v5 integration
- `backend/config/database_policy.py` — Data retention constants

### TradingView Parity

- Commission: 0.07% (0.0007) — MUST match
- 100% parity achieved on core metrics
- Bar Magnifier supported

---

## Agent Configuration (v3.1)

### Files Structure

```
.agent/
├── Claude.md               — Claude Sonnet 4 / Opus 4 rules (v3.1)
├── Gemini.md               — Gemini 3 Pro rules (v1.1)
├── mcp.json                — MCP server config (gitignored, uses env vars)
├── memory/
│   ├── CONTEXT.md          — This file (session state)
│   └── TODO.md             — Pending work items
├── docs/                   — Architecture docs (16 files)
├── rules/                  — Autonomy & operation rules (5 files)
│   ├── autonomy-guidelines.md
│   ├── enhanced-autonomy.md
│   ├── innovation-mode.md
│   ├── session-handoff.md
│   └── memory-first.md
└── workflows/
    ├── start_app.md        — Service startup (VS Code tasks)
    └── multi_agent.md      — Multi-agent orchestration

.github/
├── copilot-instructions.md — Main rules (auto-loaded by VS Code)
├── instructions/           — Path-specific rules (8 files)
│   ├── api-connectors.instructions.md
│   ├── api-endpoints.instructions.md
│   ├── backtester.instructions.md
│   ├── database.instructions.md
│   ├── frontend.instructions.md
│   ├── services.instructions.md
│   ├── strategies.instructions.md
│   └── tests.instructions.md
├── skills/                 — Project-specific agent skills (7 skills)
│   ├── api-endpoint/SKILL.md
│   ├── backtest-execution/SKILL.md
│   ├── bybit-api-integration/SKILL.md
│   ├── database-operations/SKILL.md
│   ├── metrics-calculator/SKILL.md
│   ├── safe-refactoring/SKILL.md
│   └── strategy-development/SKILL.md
├── agents/                 — Custom agents (5 agents)
│   ├── planner.agent.md
│   ├── implementer.agent.md
│   ├── reviewer.agent.md
│   ├── backtester.agent.md
│   └── tdd.agent.md
└── prompts/                — Reusable prompts (13 files)
    ├── add-api-endpoint.prompt.md
    ├── add-strategy.prompt.md
    ├── analyze-task.prompt.md
    ├── architecture-review.prompt.md
    ├── code-review.prompt.md
    ├── debug-session.prompt.md
    ├── full-stack-debug.prompt.md
    ├── implement-feature.prompt.md
    ├── performance-audit.prompt.md
    ├── safe-refactor.prompt.md
    ├── tdd-workflow.prompt.md
    ├── tradingview-parity-check.prompt.md
    └── walk-forward-optimization.prompt.md
```

### VS Code Settings

- `chat.agent.maxRequests`: 30
- `chat.agent.runTasks`: true
- `chat.agentSkillsLocations`: `[".github/skills"]`
- `chat.agentFilesLocations`: `[".github/agents", ".agent"]`
- Code generation instructions → Claude.md
- Test generation instructions → tests.instructions.md
- Code review instructions → code-review.prompt.md

---

## Agent Capabilities Summary

| Feature    | Location                | Count |
| ---------- | ----------------------- | ----- |
| Agents     | `.github/agents/`       | 5     |
| Skills     | `.github/skills/`       | 7     |
| Prompts    | `.github/prompts/`      | 13    |
| Path Rules | `.github/instructions/` | 8     |
| Rules      | `.agent/rules/`         | 5     |
| Workflows  | `.agent/workflows/`     | 2     |

---

## Recent Work

### Session 2026-02-14 — Agent Config Audit & Cleanup

- Removed 19.5 MB of irrelevant generic skills (232 dirs in `.agent/skills/`)
- Fixed `.agent/Claude.md` v2.0 → v3.1 for Claude Sonnet 4 / Opus 4
- Fixed workflows (replaced Claude Code `// turbo` syntax with VS Code tasks)
- Created 3 new project-specific skills (database-operations, metrics-calculator, bybit-api-integration)
- Security: replaced hardcoded API keys with `${env:...}` in MCP config
- Security: gitignored `.agent/mcp.json`, cleaned git history
- Updated Gemini.md to v1.1
- Cleaned up backup files and empty directories

### Session 2026-02-08 — Advanced Agent Features

- Created 5 custom agents in `.github/agents/`
- Created 4 skills in `.github/skills/`
- Created 13 reusable prompts
- Enhanced VS Code settings for Copilot Agent Mode

---

_This file is auto-updated by the agent after each session._
_Last updated: 2026-02-14_
