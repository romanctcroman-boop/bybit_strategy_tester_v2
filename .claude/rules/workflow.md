# Workflow — How to Work with Claude Code

## Directories to prioritize first

```
backend/backtesting/            # Engine, adapter, strategies, models — core
backend/core/metrics_calculator.py  # 166 metrics — read before any metrics change
backend/config/database_policy.py   # Date/retention constants
backend/api/routers/backtests.py    # Main backtest API
backend/api/routers/strategy_builder.py
frontend/js/pages/strategy_builder.js
frontend/js/pages/backtest_results.js
CLAUDE.md                           # Project overview + critical constants
```

## Directories to read when needed

```
backend/backtesting/engines/fallback_engine_v4.py  # When changing engine (~3200 lines)
backend/backtesting/indicators/                    # When adding indicator (split package)
backend/backtesting/strategy_builder/adapter.py    # When changing Builder (1399 lines)
backend/services/adapters/bybit.py                 # When changing Bybit API (1710 lines)
frontend/js/pages/strategy_builder.js              # When changing UI (13378 lines)
backend/services/live_trading/strategy_runner.py   # When changing live trading (821 lines)
backend/services/risk_management/risk_engine.py    # When changing risk management
backend/agents/memory/hierarchical_memory.py       # When changing agent memory
backend/agents/consensus/consensus_engine.py       # When changing agent consensus
backend/optimization/optuna_optimizer.py           # When changing optimization pipeline
backend/ml/regime_detection.py                     # When changing ML/regime detection
frontend/js/core/StateManager.js                   # When changing frontend state
```

## Directories to usually ignore

```
mcp-server/                     # MCP disabled, not active in prod
frontend/dist/                  # Build artifacts
data/archive/                   # Logs and result dumps
backend/backtesting/universal_engine/  # Experimental, not in main flow
backend/ml/                     # ML optional, not core to backtest
deployment/                     # DevOps, not code
backend/research/               # Research stubs (XAI, federated, blockchain) — not integrated
backend/social/                 # Copy trading PoC — in-memory, not production
backend/experimental/           # L2 LOB — experimental WebSocket collector
```

## Commands

```bash
# Start server
python main.py server

# Run migrations
python main.py migrate

# Generate AI strategy
python main.py generate-strategy --prompt "RSI momentum for BTCUSDT"

# Health check
python main.py health --detailed

# Run tests (use pytest directly, not via main.py)
pytest tests/ -x -q
pytest tests/backend/backtesting/test_engine.py -v
pytest tests/backend/backtesting/test_strategy_builder_parity.py -v
pytest tests/ai_agents/test_divergence_block_ai_agents.py -v
pytest tests/e2e/test_strategy_builder_full_flow.py -v
```

## Sub-directory CLAUDE.md files (load on-demand when reading files in that directory)

- `backend/backtesting/CLAUDE.md` — engine, adapter, SignalResult, BacktestConfig table, Builder params
- `backend/api/CLAUDE.md` — direction trap, warning codes, cross-cutting params, known inconsistencies
- `backend/optimization/CLAUDE.md` — optimizer, scoring, metrics, filter unit mismatch
- `frontend/CLAUDE.md` — no-build rule, commission UI%→decimal, direction mismatch CSS
- `backend/agents/CLAUDE.md` — LangGraph pipeline, memory, consensus, self-improvement, security
- `backend/services/CLAUDE.md` — live trading, risk management, kline cache, pitfalls
- `backend/ml/CLAUDE.md` — regime detection, RL agents, Gymnasium env
- `tests/CLAUDE.md` — test infrastructure, fixtures, directories, pytest commands
- `docs/REFACTOR_CHECKLIST.md` — full refactor checklist for AI agents
