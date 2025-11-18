# Bybit Strategy Tester v2 - AI Agent Instructions

## Project Overview

Sophisticated cryptocurrency trading strategy backtesting platform with **multi-agent AI architecture** (GitHub Copilot + DeepSeek + Perplexity). Full-stack TypeScript/React frontend, Python FastAPI backend, MCP Server for AI orchestration, and comprehensive testing infrastructure.

**Critical DNS Issue**: If agents fail with `getaddrinfo failed`, check DNS server (see bottom of document).

## Architecture: The Big Picture

### Three-Layer AI System
```
GitHub Copilot (IDE) → MCP Server (Orchestrator) → [DeepSeek API | Perplexity API]
                     ↓
               Unified Agent Interface (auto-fallback)
```

**Key architectural decisions:**
- **MCP Server** (`mcp-server/server.py`): 51 AI tools, runs as separate process, JSON-RPC over stdio
- **Unified Agent Interface** (`backend/agents/unified_agent_interface.py`): Auto-fallback MCP→Direct API, 8 DeepSeek + 4 Perplexity keys with round-robin rotation
- **Agent-to-Agent Communication** (`backend/api/agent_to_agent_api.py`): WebSocket bridge for direct DeepSeek↔Perplexity conversations bypassing Copilot token limits

### Backend Service Boundaries
- **FastAPI** (`backend/api/app.py`): Main API server (port 8000)
- **MCP Server** (`mcp-server/server.py`): AI tool server (stdio JSON-RPC)
- **Celery Workers** (`backend/celery_app.py`): Async backtests/optimizations
- **Redis**: Cache (DB 0), Celery broker (DB 1), results (DB 2), live WebSocket relay
- **PostgreSQL**: Primary data store (strategies, backtests, trades)

### Frontend Structure
- **React + Vite** (`frontend/`): Port 5173, proxies `/api` to backend
- **Lightweight Charts** + **TradingView**: Dual charting engine
- **Material-UI v6**: Component library (NOTE: v6 has breaking changes from v5 - check migration docs)

## Critical Developer Workflows

### Starting the System (Windows PowerShell)
```powershell
# Quick start (all services)
.\start.ps1

# Or manually:
# Terminal 1: Backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000

# Terminal 2: MCP Server (optional, for AI features)
python mcp-server\server.py

# Terminal 3: Frontend
cd frontend
npm run dev

# Terminal 4: Celery worker (optional, for async tasks)
celery -A backend.celery_app:celery_app worker -l info
```

### DNS Troubleshooting (Common Issue)
If agents fail with `[Errno 11001] getaddrinfo failed`:
```powershell
# Check DNS
nslookup api.deepseek.com

# If timeout, change DNS to Google (requires admin):
Set-DnsClientServerAddress -InterfaceAlias "Ethernet" -ServerAddresses ("8.8.8.8","8.8.4.4")
```

### Running Tests
```bash
# Backend unit tests
pytest tests/backend -v --maxfail=1

# E2E tests (Playwright)
cd frontend
npm run test:e2e          # Headless
npm run test:e2e:ui       # Interactive UI
npm run test:e2e:headed   # Visible browser

# Integration tests (requires PostgreSQL)
pytest tests/integration -v

# MCP Server tools
python test_mcp_enhanced_simple.py  # Quick check (1s)
pytest tests/backend/test_mcp_advanced_tools.py -v  # Full suite
```

### Database Migrations
```powershell
$env:DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/postgres'
python -m alembic upgrade head
```

## Project-Specific Conventions

### Multi-Key Agent System
**CRITICAL**: Never use single API keys directly. Always go through `UnifiedAgentInterface`:

```python
from backend.agents.unified_agent_interface import get_agent_interface, AgentRequest, AgentType

agent = get_agent_interface()

request = AgentRequest(
    agent_type=AgentType.DEEPSEEK,  # or AgentType.PERPLEXITY
    task_type="analyze",
    prompt="Analyze this trading strategy...",
    code=strategy_code,
    context={"use_file_access": False}  # Set True for MCP file tools
)

response = await agent.execute(request)
# Automatically tries: MCP Server → Direct API (key 0) → Backup keys (1-7)
```

**Key rotation strategy**: Round-robin per agent, automatic failover on 429/500 errors, health checks every 30s.

### Timezone Consistency (CRITICAL)
**Rule**: All timestamps are UTC, ISO 8601 format, stored as `timestamptz` in PostgreSQL.

```python
# ✅ CORRECT
from datetime import datetime, timezone
now = datetime.now(timezone.utc)  # timezone-aware
timestamp = now.isoformat()  # "2025-11-17T18:45:04.891604+00:00"

# ❌ WRONG
now = datetime.utcnow()  # naive datetime (deprecated)
now = datetime.now()     # local time (ambiguous)
```

**Frontend**: Use `date-fns-tz` for display, always parse from UTC:
```typescript
import { formatInTimeZone } from 'date-fns-tz';
const display = formatInTimeZone(utcTimestamp, 'America/New_York', 'yyyy-MM-dd HH:mm:ss zzz');
```

### MCP Tools: Discovery Pattern
MCP tools are NOT regular Python functions - they're registered with `@mcp.tool()` decorator:

```python
from fastmcp import FastMCP
mcp = FastMCP("server-name")

@mcp.tool()
async def analyze_backtest_results(backtest_id: int) -> dict:
    """AI analysis of backtest results via Perplexity.
    
    Args:
        backtest_id: Database ID of backtest
    
    Returns:
        dict with analysis, recommendations, and metrics explanation
    """
    # Implementation uses Perplexity API with caching
```

**Tool naming convention**: `{agent}_{action}_{subject}` (e.g., `perplexity_analyze_crypto`, `deepseek_generate_strategy`)

**Available tools**: Run `python mcp-server/server.py` and check `MCP_TOOLS_COMPLETE_INVENTORY.md` for full list (51 tools).

### Async Everywhere (FastAPI + Celery)
**Pattern**: All I/O operations must be async to avoid blocking event loop.

```python
# ✅ CORRECT: Async DB query
from sqlalchemy.ext.asyncio import AsyncSession
async with AsyncSession(engine) as session:
    result = await session.execute(select(Strategy))
    strategies = result.scalars().all()

# ✅ CORRECT: Async HTTP
async with httpx.AsyncClient() as client:
    response = await client.get(url)

# ❌ WRONG: Sync in async context
import requests
response = requests.get(url)  # Blocks event loop!
```

**Celery tasks**: Long-running work (backtests, optimizations) goes to Celery:
```python
from backend.celery_app import celery_app

@celery_app.task(bind=True, max_retries=3)
def backfill_symbol_task(self, symbol: str, interval: str, lookback_minutes: int):
    # Runs in separate worker process
    pass

# Trigger from API
task = backfill_symbol_task.delay("BTCUSDT", "1", 1440)
return {"task_id": task.id}
```

### Error Handling: Circuit Breaker Pattern
**Location**: `backend/reliability/circuit_breaker.py`

```python
from backend.reliability.circuit_breaker import CircuitBreakerManager

cb_manager = CircuitBreakerManager()

async def call_external_api():
    async with cb_manager.circuit_breaker("api_name") as cb:
        if cb.is_open:
            raise Exception("Circuit breaker open")
        response = await httpx.get(url)
        return response

# Automatically trips open after 5 failures, half-open after 30s
```

**Used by**: All external API calls (Bybit, DeepSeek, Perplexity), database connections.

### Caching Strategy
**Three-layer cache**:
1. **In-memory** (`mcp-server/perplexity_cache.py`): 100 entries, 1h TTL, 56-61% hit rate
2. **Redis** (`backend/api/routers/cache.py`): Persistent cache, no TTL
3. **Working sets** (`backend/services/market_data_cache.py`): Recent 500 candles per symbol/interval

```python
# MCP Server cache (automatic)
@mcp.tool()
async def perplexity_analyze_crypto(symbol: str):
    # Cache key: hash(function_name + args)
    # Automatically cached for 1 hour
    pass

# Explicit Redis cache
from backend.database.redis_cache import get_cached, set_cached
value = await get_cached(f"backtest:{backtest_id}")
if not value:
    value = await expensive_computation()
    await set_cached(f"backtest:{backtest_id}", value, ttl=3600)
```

## Integration Points & External Dependencies

### Bybit API v5
**Authentication**: API key + secret in `.env` (BYBIT_API_KEY, BYBIT_API_SECRET)
**Adapter**: `backend/services/adapters/bybit.py` wraps `pybit` library
**Rate limits**: 120 req/min public, 600 req/min private (handled by adapter)

```python
from backend.services.adapters.bybit import BybitAdapter
adapter = BybitAdapter()
candles = await adapter.get_klines("BTCUSDT", "15", limit=500)
# Returns: List[dict] with {time, open, high, low, close, volume}
```

### AI Agents: When to Use Which
- **DeepSeek** (8 keys): Code generation, strategy debugging, technical analysis
- **Perplexity** (4 keys): Market research, crypto news, educational content, backtest interpretation
- **Copilot**: IDE integration, code completion (always available)

**Cost**: DeepSeek ~$0.30/1M tokens, Perplexity ~$5/1M tokens → prefer DeepSeek for code.

### WebSocket Live Data
**Endpoint**: `ws://127.0.0.1:8000/api/v1/live?channel=bybit:ticks`
**Backend**: `backend/api/routers/live.py` relays from Redis pub/sub
**Start producer**: Set `BYBIT_WS_ENABLED=1`, `BYBIT_WS_SYMBOLS=BTCUSDT,ETHUSDT`, `BYBIT_WS_INTERVALS=1,5`

## Common Pitfalls & Solutions

### "Import Error: No module named 'backend'"
**Fix**: Add project root to `sys.path` in scripts:
```python
from pathlib import Path
import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
```

### "MCP Server not responding"
**Check**: 
1. Is it running? Look for `mcp_server.log` in `logs/`
2. Firewall blocking stdio? Run as admin
3. Broken tool? Check `MCP_SERVER_STATUS.md` for diagnostics

### "Agent timeout / All channels failed"
**Diagnose**:
```python
# Check health
from backend.agents.unified_agent_interface import get_agent_interface
agent = get_agent_interface()
health = await agent.health_check()
print(health)  # Shows MCP, DeepSeek, Perplexity status
```
**Common causes**: DNS failure (see DNS section), API key quota exhausted, MCP server offline.

### "Celery tasks not running"
**Check**:
```powershell
# Is worker running?
celery -A backend.celery_app:celery_app inspect active

# Is Redis reachable?
redis-cli ping  # Should return PONG

# Check task state
celery -A backend.celery_app:celery_app inspect registered
```

## Key Files to Reference

### Architecture & Patterns
- `backend/agents/unified_agent_interface.py` - Multi-key agent system with auto-fallback
- `mcp-server/server.py` - MCP tool registration, 51 AI tools
- `backend/api/agent_to_agent_api.py` - DeepSeek↔Perplexity WebSocket bridge
- `backend/reliability/circuit_breaker.py` - Failure recovery patterns

### Testing Examples
- `tests/integration/test_mcp_tools_comprehensive.py` - Full MCP integration tests
- `frontend/tests/e2e/auth.spec.ts` - Playwright E2E examples
- `tests/backend/test_backtest_engine.py` - Backtest engine unit tests

### Configuration
- `.env.example` - All environment variables with defaults
- `backend/settings.py` - Pydantic settings models (typed config)
- `alembic/versions/` - Database migration history

### Documentation Hubs
- `MCP_INDEX.md` - MCP Server complete documentation
- `MULTI_AGENT_QUICKSTART.md` - AI system 3-minute start guide
- `E2E_TESTS_QUICK_REFERENCE.md` - Testing workflows
- `00_START_HERE.txt` - Project quick start

## Recent Changes (November 2025)
- ✅ Multi-agent architecture complete (DeepSeek + Perplexity + Copilot)
- ✅ E2E testing 16/16 passing with Playwright
- ✅ MCP Server 51 tools with caching (56-61% hit rate)
- ⚠️ DNS issues affecting agent connectivity (see troubleshooting)
- 🚧 Frontend Material-UI v6 migration in progress

## Questions to Ask
1. "Which AI agent should I use for [task]?" → Check agent capabilities in `АГЕНТЫ_КРАТКИЙ_АНАЛИЗ.md`
2. "How do I add a new MCP tool?" → Follow pattern in `mcp-server/server.py`, use `@mcp.tool()` decorator
3. "Why are my tests hanging?" → Check for DNS issues, ensure async/await properly used
4. "How do I run just one test?" → `pytest tests/path/to/test.py::test_name -v`

---
**Last Updated**: November 17, 2025  
**Project Status**: Production-ready backend, frontend in active development  
**Team**: Solo developer + 3 AI agents (Copilot, DeepSeek, Perplexity)
