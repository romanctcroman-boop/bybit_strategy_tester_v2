# Subsystem Index — Bybit Strategy Tester v2

Sub-directory CLAUDE.md files load automatically when you read files from that directory.

| Subsystem | Key entry point | Sub-dir CLAUDE.md | Critical trap |
|-----------|----------------|-------------------|---------------|
| **Backtesting engine** | `backend/backtesting/engine.py` | `backend/backtesting/CLAUDE.md` | Entry on NEXT bar open; commission on margin |
| **Strategy Builder** | `backend/backtesting/strategy_builder/adapter.py` | `backend/backtesting/CLAUDE.md` | Port aliases silent drop; `"Chart"` TF resolution |
| **API / Routers** | `backend/api/app.py` | `backend/api/CLAUDE.md` | Direction default: API=`"long"`, engine=`"both"` |
| **Live Trading** | `backend/services/live_trading/strategy_runner.py` | `backend/services/CLAUDE.md` | `paper_trading.py` ≠ real orders; pos_size units differ |
| **Risk Management** | `backend/services/risk_management/risk_engine.py` | `backend/services/CLAUDE.md` | 6 sizing methods, 7 SL types, 18 rejection reasons |
| **Data / Cache** | `backend/services/kline_manager.py` | `backend/services/CLAUDE.md` | 4-tier cache; `kline_db_service.py` FROZEN |
| **AI Pipeline** | `backend/agents/trading_strategy_graph.py` | `backend/agents/CLAUDE.md` | WF after optimizer; sig counts ≠ trade counts |
| **Agent Memory** | `backend/agents/memory/hierarchical_memory.py` | `backend/agents/CLAUDE.md` | Timestamp format `"%Y-%m-%d %H:%M:%S"` (space, not T) |
| **Consensus/Debate** | `backend/agents/consensus/consensus_engine.py` | `backend/agents/CLAUDE.md` | `.decision` field (NOT `.consensus_answer`) |
| **Optimization** | `backend/optimization/optuna_optimizer.py` | `backend/optimization/CLAUDE.md` | `max_drawdown_limit` fraction vs result percentage |
| **Frontend** | `frontend/js/pages/strategy_builder.js` | `frontend/CLAUDE.md` | No build step; commission UI% → backend decimal |
| **ML / RL** | `backend/ml/regime_detection.py` | `backend/ml/CLAUDE.md` | All dependencies optional; `commission_rate=0.0007` in TradingConfig |

## Cross-Cutting Parameters (grep before any refactor)

| Parameter | Default | Risk | Key files |
|-----------|---------|------|-----------|
| `commission_value` | **0.0007** | HIGHEST | engine.py, models.py, 12+ files |
| `initial_capital` | 10000.0 | HIGH | engine.py, metrics_calculator.py, optimization/ |
| `position_size` | 1.0 (fraction) | HIGH | engine.py, live trading uses percent — unit mismatch! |
| `leverage` | 1.0 (engine) / 10 (optimizer) | MODERATE | inconsistency documented in ADR-006 |
| `pyramiding` | 1 | MODERATE | reads from request_params (fixed commit d5d0eb2) |
| `direction` | `"both"` (engine) / `"long"` (API) | MODERATE | API default trap! |

**Commission parity check:** `grep -rn commission backend/ | grep -v 0.0007 | grep -v .pyc | grep -v __pycache__`

**Full refactor checklist:** `docs/REFACTOR_CHECKLIST.md`
