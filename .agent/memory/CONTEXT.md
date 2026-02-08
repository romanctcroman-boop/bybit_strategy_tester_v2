# Project Context Summary

## Bybit Strategy Tester v2

> Auto-generated context for agent sessions.
> Last updated: 2026-02-08

---

## Quick Reference

### Project Type

- **Type**: Trading/Finance Platform
- **Language**: Python 3.14 + JavaScript
- **Framework**: FastAPI + SQLAlchemy
- **Database**: SQLite
- **Agent Model**: Claude Sonnet 4.5 / Opus 4.5

### Key Commands

```powershell
# Start all services
.\start_all.ps1

# Run tests
pytest tests/ -v

# Lint code
ruff check .

# Run backtest
py -3.14 scripts/calibrate_166_metrics.py
```

### Critical Files

- `backend/core/metrics_calculator.py` - 166 metrics
- `backend/backtesting/engines/fallback_engine_v4.py` - Gold standard (V4)
- `backend/services/adapters/bybit.py` - API integration

### TradingView Parity

- Commission: 0.07% (MUST match)
- 100% parity achieved on core metrics
- Bar Magnifier supported

---

## Agent Configuration (v2.0)

### Files Structure

```
.agent/
├── Claude.md               — Claude 4.5 specific rules (v2.0)
├── Gemini.md               — Gemini 3 Pro rules
├── mcp.json                — MCP server configuration
├── memory/
│   ├── CONTEXT.md          — This file (session state)
│   └── TODO.md             — Pending work
├── rules/                  — Autonomy & operation rules
│   ├── autonomy-guidelines.md
│   ├── enhanced-autonomy.md
│   ├── innovation-mode.md
│   ├── session-handoff.md
│   └── memory-first.md
├── skills/                 — Reusable agent skills
│   ├── backtest-execution.md
│   ├── safe-refactoring.md
│   ├── strategy-development.md
│   └── api-endpoint-development.md
└── workflows/
    ├── start_app.md
    └── multi_agent.md

.github/
├── copilot-instructions.md — Main rules (auto-loaded)
├── instructions/           — Path-specific rules (7 files)
│   ├── api-connectors.instructions.md
│   ├── api-endpoints.instructions.md
│   ├── backtester.instructions.md
│   ├── database.instructions.md
│   ├── frontend.instructions.md
│   ├── services.instructions.md
│   ├── strategies.instructions.md
│   └── tests.instructions.md
└── prompts/                — Reusable prompts (12 files)
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
    ├── tradingview-parity-check.prompt.md
    └── walk-forward-optimization.prompt.md
```

### VS Code Settings

- `chat.agent.maxRequests`: 30
- `chat.agent.runTasks`: true
- Code generation instructions linked to Claude.md
- Test generation instructions linked to tests.instructions.md
- Code review instructions linked to code-review.prompt.md

---

## Recent Work

### Session 2026-02-08 (Phase 2 — Advanced Agent Features)

- **Custom Agents** (`.github/agents/`):
    - `planner.agent.md` — Read-only planning/research agent with handoffs
    - `implementer.agent.md` — Full-capability implementation agent
    - `reviewer.agent.md` — Code review with TradingView parity checklist
    - `backtester.agent.md` — Backtest execution and metrics analysis
    - `tdd.agent.md` — Test-Driven Development (Red/Green/Refactor)

- **Official Agent Skills** (`.github/skills/`):
    - `backtest-execution/SKILL.md` — API and engine usage with metrics
    - `strategy-development/SKILL.md` — BaseStrategy template and pandas_ta
    - `api-endpoint/SKILL.md` — FastAPI router patterns and async DB
    - `safe-refactoring/SKILL.md` — Incremental refactoring with test verification

- **VS Code Settings** enhanced:
    - `chat.promptFiles: true` — Enables `.github/prompts/` folder
    - `chat.agentFilesLocations` — Points to `.github/agents` and `.agent`
    - `chat.agentSkillsLocations` — Points to `.github/skills` and `.agent/skills`
    - `github.copilot.chat.organizationCustomAgents.enabled: true`

- **New Prompt**: `tdd-workflow.prompt.md` — Red/Green/Refactor cycle

### Session 2026-02-08 (Phase 1 — Foundation)

- Rewrote `.agent/Claude.md` for Claude 4.5 (v2.0)
- Created 5 reusable prompts (full-stack-debug, performance-audit, etc.)
- Created 4 agent skills in `.agent/skills/`
- Added 3 path-specific instructions (frontend, database, services)
- Updated VS Code settings with Copilot Agent Mode maximization

---

## Agent Capabilities Summary

| Feature         | Location                | Count |
| --------------- | ----------------------- | ----- |
| Custom Agents   | `.github/agents/`       | 5     |
| Official Skills | `.github/skills/`       | 4     |
| Legacy Skills   | `.agent/skills/`        | 4     |
| Prompts         | `.github/prompts/`      | 13    |
| Instructions    | `.github/instructions/` | 8     |
| Rules           | `.agent/rules/`         | 5     |
| Workflows       | `.agent/workflows/`     | 2     |

## Next Session Hints

- Convert `.agent/skills/` to YAML frontmatter format (agentskills.io standard)
- Explore subagent orchestration with `agents:` restriction
- Add community skills from `github/awesome-copilot`
- Performance profiling skill with cProfile integration
- E2E testing skill with Playwright

---

_This file is auto-updated by the agent after each session._
_Last updated: 2026-02-08 (Phase 2)_
