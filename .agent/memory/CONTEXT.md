# Project Context Summary

## Bybit Strategy Tester v2

> Auto-generated context for agent sessions.
> Last updated: 2026-01-24

---

## Quick Reference

### Project Type

- **Type**: Trading/Finance Platform
- **Language**: Python 3.14 + JavaScript
- **Framework**: FastAPI + SQLAlchemy
- **Database**: SQLite

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
- `backend/backtesting/engines/fallback_engine_v2.py` - Gold standard
- `backend/services/adapters/bybit.py` - API integration

### TradingView Parity

- Commission: 0.07% (MUST match)
- 100% parity achieved on core metrics
- Bar Magnifier supported

---

## Recent Work (Last Session)

- **MCP Infrastructure Added (2026-01-24)**:
    - Created `.agent/mcp.json` with Docker + Bybit MCP servers
    - Built custom `bybit_mcp_server.py` with 6 trading tools
    - Added `multi_agent.md` workflow for parallel agents
    - Created `browser-ui-testing` skill
- Configured Claude Opus 4.5 autonomy
- Added 234+ Agent Skills
- Created trading-autonomy skill
- Set up innovation mode
- Bar Magnifier tested successfully

---

## Next Session Hints

Potential tasks:

- Expand 166-metric calibration
- Add more strategy types
- Performance optimization
- Documentation updates

---

_This file is auto-updated by the agent after each session._
