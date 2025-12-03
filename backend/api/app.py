import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add mcp-server to Python path BEFORE imports (fixes orchestrator.api.metrics import in metrics_router)
_project_root = Path(__file__).resolve().parent.parent.parent
_mcp_server_path = _project_root / "mcp-server"
if _mcp_server_path.exists() and str(_mcp_server_path) not in sys.path:
    sys.path.insert(0, str(_mcp_server_path))

from backend.api import (
    agent_to_agent_api,  # ✅ Week 5 Day 5: AI Agent Communication (DeepSeek + Perplexity)
    orchestrator,  # ✅ Week 6: Orchestrator Dashboard (MOVED BEFORE metrics to avoid circular import)
)
from backend.api.routers import active_deals as active_deals_router
from backend.api.routers import admin, backtests, inference, marketdata, optimizations, strategies
from backend.api.routers import ai as ai_router  # NEW: AI Analysis router (Perplexity)
from backend.api.routers import bots as bots_router
from backend.api.routers import (
    cache as cache_router,  # ✅ Week 2 Day 2: Cache Statistics & Management
)
from backend.api.routers import (
    csv_export as csv_export_router,  # ✅ Quick Win #4: CSV Export Functionality
)
from backend.api.routers import dashboard as dashboard_router  # ✅ Dashboard KPI endpoints
from backend.api.routers import (
    dashboard_metrics as dashboard_metrics_router,  # ✅ Quick Win #1: Performance Metrics Dashboard
)
from backend.api.routers import (
    executions as executions_router,  # ✅ Week 5 Day 6: Execution orchestration endpoints
)
from backend.api.routers import health as health_router  # NEW: Health check router
from backend.api.routers import (
    health_monitoring as health_monitoring_router,  # ✅ Quick Win #3: Enhanced Health Monitoring
)
from backend.api.routers import live as live_router
from backend.api.routers import metrics as metrics_router  # P0-5: Prometheus metrics router
from backend.api.routers import context as context_router  # Phase A: MCP replacement context API
from backend.api.routers import file_ops as file_ops_router  # Phase A: File access API
from backend.api.routers import test_runner as test_runner_router  # Phase 3: autonomous test execution
from backend.api.routers import perplexity as perplexity_router  # Phase A: Perplexity direct endpoints
from backend.api.routers import queue as queue_router  # ✅ Redis Queue Manager endpoints
from backend.api.routers import security as security_router  # ✅ Phase 1: JWT Auth & Security
from backend.api.routers import (
    strategy_templates as strategy_templates_router,  # ✅ Quick Win #2: Strategy Template Library
)
from backend.api.routers import (
    test as test_router,  # ✅ E2E Test endpoints (reset, cleanup, health/db)
)
from backend.api.routers import wizard as wizard_router
from backend.config import CONFIG

# Optional: start BybitWsManager on app startup when feature flag is enabled
try:
    from redis.asyncio import Redis

    from backend.services.bybit_ws_manager import BybitWsManager
except Exception:
    Redis = None  # type: ignore
    BybitWsManager = None  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log Alembic DB version vs code head(s) on startup
    try:
        from alembic.config import Config as _AlConfig  # type: ignore
        from alembic.script import ScriptDirectory  # type: ignore

        from backend.database import engine  # lazy to avoid import cycles

        db_rev = None
        with engine.connect() as conn:
            try:
                db_rev = conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
            except Exception:
                db_rev = None

        code_heads = None
        try:
            alembic_cfg = _AlConfig("alembic.ini")
            script = ScriptDirectory.from_config(alembic_cfg)
            code_heads = script.get_heads()
        except Exception:
            code_heads = None

        logging.getLogger("uvicorn.error").info(
            "Alembic versions: db=%s code_heads=%s match=%s",
            db_rev,
            code_heads,
            (db_rev in (code_heads or [])),
        )
    except Exception as _e:  # best-effort only
        logging.getLogger("uvicorn.error").warning("Alembic status check failed: %s", _e)

    # Create database tables on startup if they don't exist
    try:
        from backend.database import Base as _Base
        from backend.database import engine as _eng
        _Base.metadata.create_all(bind=_eng)
        logging.getLogger("uvicorn.error").info("✅ Database tables created/verified")
    except Exception as _e:
        logging.getLogger("uvicorn.error").warning("⚠️ Database table creation failed: %s", _e)

    # Initialize Redis Queue Manager
    try:
        from backend.queue import queue_adapter
        await queue_adapter._ensure_connected()
        logging.getLogger("uvicorn.error").info("✅ Redis Queue Manager connected")
    except Exception as _e:
        logging.getLogger("uvicorn.error").warning("⚠️ Redis Queue Manager initialization failed: %s", _e)

    # =========================================================================
    # PHASE 2: Circuit Breaker Persistence (Production Deployment)
    # =========================================================================
    try:
        from backend.agents.circuit_breaker_manager import get_circuit_manager
        from backend.config import CONFIG
        
        circuit_mgr = get_circuit_manager()
        persistence_enabled = await circuit_mgr.enable_persistence(
            redis_url=CONFIG.redis.url,
            autosave_interval=60
        )
        
        if persistence_enabled:
            logging.getLogger("uvicorn.error").info(
                "✅ Phase 2: Circuit Breaker Persistence enabled (Redis autosave: 60s)"
            )
        else:
            logging.getLogger("uvicorn.error").warning(
                "⚠️ Phase 2: Circuit Breaker Persistence unavailable (Redis connection failed)"
            )
    except Exception as _e:
        logging.getLogger("uvicorn.error").warning(
            "⚠️ Phase 2: Circuit Breaker Persistence initialization failed: %s", _e
        )

    # Start config file watcher for hot-reload (Priority 1)
    config_watcher = None
    try:
        from backend.agents.agent_config import start_config_watcher, register_reload_callback
        from backend.agents.circuit_breaker_manager import on_config_change
        
        register_reload_callback(on_config_change)
        config_watcher = start_config_watcher()
        
        logging.getLogger("uvicorn.error").info(
            "✅ Config hot-reload enabled: watching agents.yaml"
        )
        app.state.config_watcher = config_watcher
    except Exception as _e:
        logging.getLogger("uvicorn.error").warning(
            "⚠️ Config hot-reload initialization failed: %s", _e
        )
        app.state.config_watcher = None

    # Initialize Plugin Manager (from MCP Server)
    try:
        import sys
        from pathlib import Path
        
        # Add mcp-server to path if not already there
        mcp_server_path = Path(__file__).parent.parent.parent / "mcp-server"
        if str(mcp_server_path) not in sys.path:
            sys.path.insert(0, str(mcp_server_path))
        
        from orchestrator.plugin_system import PluginManager
        
        plugin_manager = PluginManager(
            plugins_dir=mcp_server_path / "orchestrator" / "plugins",
            orchestrator=None,
            auto_reload=True,
            reload_interval=60
        )
        
        await plugin_manager.initialize()
        await plugin_manager.load_all_plugins()
        
        plugins = plugin_manager.list_plugins()
        logging.getLogger("uvicorn.error").info(
            f"✅ Plugin Manager initialized: {len(plugins)} plugins loaded"
        )
        
        # Set dependencies for orchestrator API
        orchestrator.set_dependencies(plugin_manager, queue_adapter)
        app.state.plugin_manager = plugin_manager
        
    except Exception as _e:
        logging.getLogger("uvicorn.error").warning("⚠️ Plugin Manager initialization failed: %s", _e)
        app.state.plugin_manager = None

    # Initialize MCP Bridge (Task 9: MCP integration)
    try:
        from backend.mcp.mcp_integration import ensure_mcp_bridge_initialized
        await ensure_mcp_bridge_initialized()
        logging.getLogger("uvicorn.error").info("✅ MCP Bridge initialized")
        
        # Capture MCP tool registry after bridge initialization
        asyncio.create_task(capture_tool_registry())
    except Exception as _e:
        logging.getLogger("uvicorn.error").warning("⚠️ MCP Bridge initialization failed: %s", _e)

    # Startup
    if CONFIG.ws_enabled and Redis is not None and BybitWsManager is not None:
        try:
            r = Redis.from_url(CONFIG.redis.url, encoding="utf-8", decode_responses=True)
            mgr = BybitWsManager(r, CONFIG.redis.channel_ticks, CONFIG.redis.channel_klines)
            await mgr.start(symbols=CONFIG.ws_symbols, intervals=CONFIG.ws_intervals)
            app.state.ws_resources = (mgr, r)
        except Exception:
            app.state.ws_resources = None
    else:
        app.state.ws_resources = None

    # Initialize FastMCP HTTP app lifespan (ensures MCP session manager starts)
    # This nests the MCP lifespan inside the main app lifespan so MCP initializes after
    # app startup and tears down before app shutdown (per FastMCP docs).
    try:
        async with mcp_app.lifespan(app):  # type: ignore[name-defined]
            yield
    except NameError:
        yield

    # Shutdown
    # Stop config watcher
    cw = getattr(app.state, "config_watcher", None)
    if cw:
        try:
            cw.stop()
            cw.join(timeout=2)
            logging.getLogger("uvicorn.error").info("🛑 Config watcher stopped")
        except Exception as _e:
            logging.getLogger("uvicorn.error").warning("⚠️ Config watcher shutdown error: %s", _e)
    
    pm = getattr(app.state, "plugin_manager", None)
    if pm:
        try:
            logging.getLogger("uvicorn.error").info("🔌 Shutting down Plugin Manager...")
            await pm.unload_all_plugins()
        except Exception as _e:
            logging.getLogger("uvicorn.error").warning("⚠️ Plugin Manager shutdown error: %s", _e)
    
    ws = getattr(app.state, "ws_resources", None)
    if ws:
        mgr, r = ws
        try:
            await mgr.stop()
        finally:
            try:
                await r.close()
            except Exception:
                pass


app = FastAPI(
    title="bybit_strategy_tester_v2 API", 
    version="2.0.0",  # Phase 1: Security features integrated!
    description="Bybit Strategy Tester with JWT Auth, Rate Limiting & Sandbox",
    lifespan=lifespan
)

import asyncio
import uuid

from fastmcp import FastMCP

# Import MCP error handling and middleware
from backend.api.mcp_errors import (
    AgentUnavailableError,
    exception_to_mcp_error,
)

# =============================
# MCP Hardening Environment Config (Removed - now in middleware factory)
# =============================

# Recommended: Create MCP server from FastAPI app (industry standard)
mcp = FastMCP.from_fastapi(
    app=app,
    name="Bybit Strategy Tester",
    version="2.0.0"
)

# =============================
# MCP Circuit Breaker & Concurrency Control
# =============================
import os as _cb_os
import time as _time


class CircuitBreaker:
    def __init__(self, threshold: int = 5, timeout_seconds: int = 60):
        self.threshold = threshold
        self.timeout_seconds = timeout_seconds
        self.failures = 0
        self.open_until = 0.0

    def is_open(self) -> bool:
        return _time.time() < self.open_until

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = _time.time() + self.timeout_seconds

    def reset(self):
        self.failures = 0
        self.open_until = 0.0

# Configurable via env vars
_CB_THRESHOLD = int(_cb_os.getenv("MCP_CB_FAILURE_THRESHOLD", "5"))
_CB_TIMEOUT = int(_cb_os.getenv("MCP_CB_TIMEOUT_SECONDS", "60"))
_MAX_CONCURRENCY = int(_cb_os.getenv("MCP_MAX_CONCURRENT", "10"))

# Per-tool breakers and global semaphore
_CB = {
    "send_to_deepseek": CircuitBreaker(_CB_THRESHOLD, _CB_TIMEOUT),
    "send_to_perplexity": CircuitBreaker(_CB_THRESHOLD, _CB_TIMEOUT),
    "get_consensus": CircuitBreaker(_CB_THRESHOLD, _CB_TIMEOUT),
}
_MCP_SEMAPHORE = asyncio.Semaphore(_MAX_CONCURRENCY)

# Import agent communication dependencies
from backend.agents.agent_to_agent_communicator import (
    AgentMessage,
    AgentType,
    MessageType,
    get_communicator,
)


@mcp.tool()
async def mcp_agent_to_agent_send_to_deepseek(
    content: str,
    conversation_id: str = None,
    context: dict = None
) -> dict:
    """Send message to DeepSeek agent via MCP"""
    import time
    start_time = time.perf_counter()
    
    # Circuit breaker guard (fail-fast if threshold breached)
    if _CB["send_to_deepseek"].is_open():
        mcp_error = AgentUnavailableError("Circuit breaker open for send_to_deepseek")
        try:
            MCP_TOOL_CALLS.labels(tool="send_to_deepseek", success="false").inc()
            MCP_TOOL_ERRORS.labels(tool="send_to_deepseek", error_type="CircuitOpen").inc()
        except Exception:
            pass
        return mcp_error.to_dict()

    try:
        communicator = get_communicator()
        
        # ВАЖНО: Помечаем context как вызов из MCP tool для предотвращения рекурсии
        # Без этого: MCP tool → route_message → MCP tool → route_message → ...
        if context is None:
            context = {}
        context["from_mcp_tool"] = True
        
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=AgentType.COPILOT,
            to_agent=AgentType.DEEPSEEK,
            message_type=MessageType.QUERY,
            content=content,
            context=context,
            conversation_id=conversation_id or str(uuid.uuid4())
        )
        # DeepSeek feedback: Semaphore + timeout layering to prevent deadlock
        # 1) Semaphore: limits concurrent executions (default 10)
        # 2) Timeout: per-request time budget (120s for AI workloads)
        # No nested locks; semaphore released on timeout or success
        async with _MCP_SEMAPHORE:
            try:
                async with asyncio.timeout(120):
                    response = await communicator.route_message(message)
            except Exception as _inner_exc:
                raise _inner_exc
        result = {
            "success": True,
            "message_id": response.message_id,
            "content": response.content,
            "conversation_id": response.conversation_id,
            "iteration": response.iteration
        }
        
        # Metrics
        duration = time.perf_counter() - start_time
        try:
            MCP_TOOL_CALLS.labels(tool="send_to_deepseek", success="true").inc()
            MCP_TOOL_DURATION.labels(tool="send_to_deepseek").observe(duration)
        except Exception:
            pass
        
        # Reset breaker on success
        _CB["send_to_deepseek"].reset()
        return result
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        logging.getLogger("uvicorn.error").error(f"MCP DeepSeek tool error: {e}")
        
        # Convert to MCP error
        mcp_error = exception_to_mcp_error(e)
        _CB["send_to_deepseek"].record_failure()
        
        # Metrics
        try:
            MCP_TOOL_CALLS.labels(tool="send_to_deepseek", success="false").inc()
            MCP_TOOL_ERRORS.labels(tool="send_to_deepseek", error_type=mcp_error.error_type).inc()
            MCP_TOOL_DURATION.labels(tool="send_to_deepseek").observe(duration)
        except Exception:
            pass
        
        return mcp_error.to_dict()

@mcp.tool()
async def mcp_agent_to_agent_send_to_perplexity(
    content: str,
    conversation_id: str = None,
    context: dict = None
) -> dict:
    """Send message to Perplexity agent via MCP"""
    import time
    start_time = time.perf_counter()
    
    # Circuit breaker guard (fail-fast if threshold breached)
    if _CB["send_to_perplexity"].is_open():
        mcp_error = AgentUnavailableError("Circuit breaker open for send_to_perplexity")
        try:
            MCP_TOOL_CALLS.labels(tool="send_to_perplexity", success="false").inc()
            MCP_TOOL_ERRORS.labels(tool="send_to_perplexity", error_type="CircuitOpen").inc()
        except Exception:
            pass
        return mcp_error.to_dict()

    try:
        communicator = get_communicator()
        
        # ВАЖНО: Помечаем context как вызов из MCP tool для предотвращения рекурсии
        if context is None:
            context = {}
        context["from_mcp_tool"] = True
        
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=AgentType.COPILOT,
            to_agent=AgentType.PERPLEXITY,
            message_type=MessageType.QUERY,
            content=content,
            context=context,
            conversation_id=conversation_id or str(uuid.uuid4())
        )
        # DeepSeek feedback: Semaphore + timeout layering to prevent deadlock
        # 1) Semaphore: limits concurrent executions (default 10)
        # 2) Timeout: per-request time budget (120s for AI workloads)
        # No nested locks; semaphore released on timeout or success
        async with _MCP_SEMAPHORE:
            try:
                async with asyncio.timeout(120):
                    response = await communicator.route_message(message)
            except Exception as _inner_exc:
                raise _inner_exc
        result = {
            "success": True,
            "message_id": response.message_id,
            "content": response.content,
            "conversation_id": response.conversation_id,
            "iteration": response.iteration
        }
        
        # Metrics
        duration = time.perf_counter() - start_time
        try:
            MCP_TOOL_CALLS.labels(tool="send_to_perplexity", success="true").inc()
            MCP_TOOL_DURATION.labels(tool="send_to_perplexity").observe(duration)
        except Exception:
            pass
        
        # Reset breaker on success
        _CB["send_to_perplexity"].reset()
        return result
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        logging.getLogger("uvicorn.error").error(f"MCP Perplexity tool error: {e}")
        
        # Convert to MCP error
        mcp_error = exception_to_mcp_error(e)
        _CB["send_to_perplexity"].record_failure()
        
        # Metrics
        try:
            MCP_TOOL_CALLS.labels(tool="send_to_perplexity", success="false").inc()
            MCP_TOOL_ERRORS.labels(tool="send_to_perplexity", error_type=mcp_error.error_type).inc()
            MCP_TOOL_DURATION.labels(tool="send_to_perplexity").observe(duration)
        except Exception:
            pass
        
        return mcp_error.to_dict()

@mcp.tool()
async def mcp_agent_to_agent_get_consensus(
    question: str,
    agents: list = None
) -> dict:
    """Get consensus from multiple agents"""
    import time
    start_time = time.perf_counter()
    
    # Circuit breaker guard (fail-fast if threshold breached)
    if _CB["get_consensus"].is_open():
        mcp_error = AgentUnavailableError("Circuit breaker open for get_consensus")
        try:
            MCP_TOOL_CALLS.labels(tool="get_consensus", success="false").inc()
            MCP_TOOL_ERRORS.labels(tool="get_consensus", error_type="CircuitOpen").inc()
        except Exception:
            pass
        return mcp_error.to_dict()

    try:
        if agents is None:
            agents = ["deepseek", "perplexity"]
        communicator = get_communicator()
        agent_types = [AgentType(a) for a in agents]
        # DeepSeek feedback: Semaphore + timeout layering to prevent deadlock
        # 1) Semaphore: limits concurrent executions (default 10)
        # 2) Timeout: extended budget (180s) for multi-agent consensus
        # No nested locks; semaphore released on timeout or success
        async with _MCP_SEMAPHORE:
            try:
                async with asyncio.timeout(180):
                    result = await communicator.parallel_consensus(
                        question=question,
                        agents=agent_types
                    )
            except Exception as _inner_exc:
                raise _inner_exc
        response = {
            "success": True,
            "consensus": result["consensus"],
            "confidence_score": result["confidence_score"],
            "conversation_id": result["conversation_id"],
            "individual_responses": result["individual_responses"]
        }
        
        # Metrics
        duration = time.perf_counter() - start_time
        try:
            MCP_TOOL_CALLS.labels(tool="get_consensus", success="true").inc()
            MCP_TOOL_DURATION.labels(tool="get_consensus").observe(duration)
        except Exception:
            pass
        
        # Reset breaker on success
        _CB["get_consensus"].reset()
        return response
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        logging.getLogger("uvicorn.error").error(f"MCP Consensus tool error: {e}")
        
        # Convert to MCP error
        mcp_error = exception_to_mcp_error(e)
        _CB["get_consensus"].record_failure()
        
        # Metrics
        try:
            MCP_TOOL_CALLS.labels(tool="get_consensus", success="false").inc()
            MCP_TOOL_ERRORS.labels(tool="get_consensus", error_type=mcp_error.error_type).inc()
            MCP_TOOL_DURATION.labels(tool="get_consensus").observe(duration)
        except Exception:
            pass
        
        return mcp_error.to_dict()


# ============================================================================
# FILE ACCESS MCP TOOLS (Enhanced Agent Capabilities)
# ============================================================================

@mcp.tool()
async def mcp_read_project_file(
    file_path: str,
    max_size_kb: int = 100
) -> dict:
    """
    Securely read project files (read-only, sandboxed)
    
    Args:
        file_path: Relative path from project root (e.g., "backend/api/app.py")
        max_size_kb: Maximum file size to read (default 100KB for safety)
    
    Returns:
        dict with success, content, metadata
    
    Security:
        - Only allows reading files within project root
        - Blocks access to .env, .git, secrets
        - Enforces file size limits
    """
    import time
    start_time = time.perf_counter()
    
    try:
        # Validate and normalize path
        project_root = Path(__file__).resolve().parent.parent.parent
        target_path = (project_root / file_path).resolve()
        
        # Security: ensure target is within project root
        if not str(target_path).startswith(str(project_root)):
            return {
                "success": False,
                "error": "Path traversal detected: file must be within project root",
                "file_path": file_path
            }
        
        # Security: block sensitive files
        blocked_patterns = ['.env', '.git', 'secrets', 'credentials', '.key', '.pem']
        if any(pattern in str(target_path).lower() for pattern in blocked_patterns):
            return {
                "success": False,
                "error": "Access denied: sensitive file pattern detected",
                "file_path": file_path
            }
        
        # Check file exists
        if not target_path.exists():
            return {
                "success": False,
                "error": "File not found",
                "file_path": file_path
            }
        
        # Check file size
        file_size = target_path.stat().st_size
        max_size_bytes = max_size_kb * 1024
        if file_size > max_size_bytes:
            return {
                "success": False,
                "error": f"File too large: {file_size} bytes (max {max_size_bytes})",
                "file_path": file_path,
                "file_size_kb": file_size // 1024
            }
        
        # Read file content
        with open(target_path, encoding='utf-8') as f:
            content = f.read()
        
        # Metrics
        duration = time.perf_counter() - start_time
        try:
            MCP_TOOL_CALLS.labels(tool="read_project_file", success="true").inc()
            MCP_TOOL_DURATION.labels(tool="read_project_file").observe(duration)
        except Exception:
            pass
        
        return {
            "success": True,
            "content": content,
            "file_path": file_path,
            "absolute_path": str(target_path),
            "file_size_kb": file_size // 1024,
            "lines": len(content.splitlines()),
            "encoding": "utf-8"
        }
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        logging.getLogger("uvicorn.error").error(f"MCP read_project_file error: {e}")
        
        try:
            MCP_TOOL_CALLS.labels(tool="read_project_file", success="false").inc()
            MCP_TOOL_ERRORS.labels(tool="read_project_file", error_type=type(e).__name__).inc()
            MCP_TOOL_DURATION.labels(tool="read_project_file").observe(duration)
        except Exception:
            pass
        
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "file_path": file_path
        }


@mcp.tool()
async def mcp_list_project_structure(
    directory: str = ".",
    max_depth: int = 3,
    include_hidden: bool = False
) -> dict:
    """
    List project directory structure (read-only navigation)
    
    Args:
        directory: Relative path from project root (default "." for root)
        max_depth: Maximum recursion depth (default 3 for safety)
        include_hidden: Include hidden files/folders (default False)
    
    Returns:
        dict with success, structure (tree), file_count, dir_count
    
    Security:
        - Read-only access within project root
        - Depth limit to prevent resource exhaustion
        - Blocks .git, .env, node_modules by default
    """
    import time
    start_time = time.perf_counter()
    
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        target_dir = (project_root / directory).resolve()
        
        # Security: ensure within project root
        if not str(target_dir).startswith(str(project_root)):
            return {
                "success": False,
                "error": "Path traversal detected",
                "directory": directory
            }
        
        if not target_dir.exists() or not target_dir.is_dir():
            return {
                "success": False,
                "error": "Directory not found or not a directory",
                "directory": directory
            }
        
        # Build directory tree
        def build_tree(path: Path, depth: int = 0) -> dict:
            if depth > max_depth:
                return {"name": path.name, "type": "directory", "truncated": True}
            
            result = {
                "name": path.name,
                "type": "directory" if path.is_dir() else "file",
                "relative_path": str(path.relative_to(project_root))
            }
            
            if path.is_file():
                result["size_kb"] = path.stat().st_size // 1024
                return result
            
            # List directory contents
            children = []
            blocked_dirs = {'.git', '__pycache__', 'node_modules', '.pytest_cache', 'htmlcov', '.venv'}
            
            try:
                for item in sorted(path.iterdir()):
                    # Skip hidden files unless requested
                    if not include_hidden and item.name.startswith('.'):
                        continue
                    # Skip blocked directories
                    if item.name in blocked_dirs:
                        continue
                    
                    children.append(build_tree(item, depth + 1))
            except PermissionError:
                result["error"] = "Permission denied"
            
            result["children"] = children
            return result
        
        structure = build_tree(target_dir)
        
        # Count files and directories
        def count_items(node: dict) -> tuple:
            if node.get("type") == "file":
                return (1, 0)
            file_count = 0
            dir_count = 1 if node.get("type") == "directory" else 0
            for child in node.get("children", []):
                f, d = count_items(child)
                file_count += f
                dir_count += d
            return (file_count, dir_count)
        
        file_count, dir_count = count_items(structure)
        
        # Metrics
        duration = time.perf_counter() - start_time
        try:
            MCP_TOOL_CALLS.labels(tool="list_project_structure", success="true").inc()
            MCP_TOOL_DURATION.labels(tool="list_project_structure").observe(duration)
        except Exception:
            pass
        
        return {
            "success": True,
            "structure": structure,
            "file_count": file_count,
            "dir_count": dir_count,
            "max_depth": max_depth,
            "directory": directory
        }
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        logging.getLogger("uvicorn.error").error(f"MCP list_project_structure error: {e}")
        
        try:
            MCP_TOOL_CALLS.labels(tool="list_project_structure", success="false").inc()
            MCP_TOOL_ERRORS.labels(tool="list_project_structure", error_type=type(e).__name__).inc()
            MCP_TOOL_DURATION.labels(tool="list_project_structure").observe(duration)
        except Exception:
            pass
        
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "directory": directory
        }


@mcp.tool()
async def mcp_analyze_code_quality(
    file_path: str,
    tools: list = None
) -> dict:
    """
    Analyze code quality using Ruff, Black, Bandit
    
    Args:
        file_path: Relative path to Python file (e.g., "backend/api/app.py")
        tools: List of tools to run (default: ["ruff", "black", "bandit"])
    
    Returns:
        dict with success, results per tool, summary statistics
    
    Note:
        Requires ruff, black, bandit installed in environment
    """
    import subprocess
    import time
    start_time = time.perf_counter()
    
    if tools is None:
        tools = ["ruff", "black", "bandit"]
    
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        target_file = (project_root / file_path).resolve()
        
        # Security checks
        if not str(target_file).startswith(str(project_root)):
            return {
                "success": False,
                "error": "Path traversal detected",
                "file_path": file_path
            }
        
        if not target_file.exists() or not target_file.is_file():
            return {
                "success": False,
                "error": "File not found or not a file",
                "file_path": file_path
            }
        
        if not file_path.endswith('.py'):
            return {
                "success": False,
                "error": "Only Python files (.py) are supported",
                "file_path": file_path
            }
        
        results = {}
        
        # Run Ruff (linter)
        if "ruff" in tools:
            try:
                proc = subprocess.run(
                    ["ruff", "check", str(target_file), "--output-format=json"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                import json
                ruff_output = json.loads(proc.stdout) if proc.stdout else []
                results["ruff"] = {
                    "issues_count": len(ruff_output),
                    "issues": ruff_output[:10],  # Limit to first 10 for output size
                    "status": "passed" if len(ruff_output) == 0 else "failed"
                }
            except Exception as e:
                results["ruff"] = {"error": str(e), "status": "error"}
        
        # Run Black (formatter check)
        if "black" in tools:
            try:
                proc = subprocess.run(
                    ["black", "--check", "--line-length=100", str(target_file)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                results["black"] = {
                    "status": "passed" if proc.returncode == 0 else "failed",
                    "message": "Formatting OK" if proc.returncode == 0 else "Needs formatting",
                    "output": proc.stdout + proc.stderr
                }
            except Exception as e:
                results["black"] = {"error": str(e), "status": "error"}
        
        # Run Bandit (security scanner)
        if "bandit" in tools:
            try:
                proc = subprocess.run(
                    ["bandit", "-r", str(target_file), "-f", "json", "-ll"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                import json
                bandit_output = json.loads(proc.stdout) if proc.stdout else {}
                results["bandit"] = {
                    "issues_count": len(bandit_output.get("results", [])),
                    "issues": bandit_output.get("results", [])[:5],  # Limit to first 5
                    "status": "passed" if len(bandit_output.get("results", [])) == 0 else "failed"
                }
            except Exception as e:
                results["bandit"] = {"error": str(e), "status": "error"}
        
        # Summary
        all_passed = all(r.get("status") == "passed" for r in results.values())
        total_issues = sum(r.get("issues_count", 0) for r in results.values())
        
        # Metrics
        duration = time.perf_counter() - start_time
        try:
            MCP_TOOL_CALLS.labels(tool="analyze_code_quality", success="true").inc()
            MCP_TOOL_DURATION.labels(tool="analyze_code_quality").observe(duration)
        except Exception:
            pass
        
        return {
            "success": True,
            "file_path": file_path,
            "results": results,
            "summary": {
                "all_passed": all_passed,
                "total_issues": total_issues,
                "tools_run": list(results.keys())
            }
        }
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        logging.getLogger("uvicorn.error").error(f"MCP analyze_code_quality error: {e}")
        
        try:
            MCP_TOOL_CALLS.labels(tool="analyze_code_quality", success="false").inc()
            MCP_TOOL_ERRORS.labels(tool="analyze_code_quality", error_type=type(e).__name__).inc()
            MCP_TOOL_DURATION.labels(tool="analyze_code_quality").observe(duration)
        except Exception:
            pass
        
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "file_path": file_path
        }


# MCP ASGI routes will be registered after custom routes are defined (see below)

# =============================
# Unified MCP Middleware (replaces McpHardeningMiddleware)
# =============================
# Middleware will be registered after CORS setup (see below)

# =============================
# MCP-native health endpoint using app.get on /mcp/health
# =============================
@app.get("/mcp/health")
async def mcp_health_native():
    """
    Enhanced health check via direct FastAPI route (avoids MCP-internal routing)
    Returns detailed status with per-check granularity
    """
    import os as _os
    from datetime import datetime as _dt

    checks = {}

    # Tools from MCP registry (access via get_tools async method)
    tool_count = 0
    tools_registered = []
    try:
        tools_dict = await mcp.get_tools()
        tools_registered = list(tools_dict.keys())
        tool_count = len(tools_registered)
        checks["mcp_tools_available"] = tool_count > 0
    except Exception:
        checks["mcp_tools_available"] = False

    # Auth configured (if required)
    auth_required = _os.getenv("MCP_REQUIRE_AUTH", "0") in ("1", "true", "yes", "True")
    auth_token = _os.getenv("MCP_AUTH_TOKEN", "")
    checks["auth_configured"] = (not auth_required) or bool(auth_token)

    # Database connected
    try:
        from backend.database import engine as _engine
        with _engine.connect() as _conn:
            _conn.exec_driver_sql("SELECT 1")
        checks["database_connected"] = True
    except Exception:
        checks["database_connected"] = False

    # Session manager (if available)
    sessions_active = 0
    _sm = getattr(mcp, "session_manager", None)
    if _sm and hasattr(_sm, "sessions"):
        try:
            sessions_active = len(_sm.sessions)
        except Exception:
            sessions_active = 0

    status = "healthy" if all(checks.values()) else "degraded"

    allowed_origins_str = _os.getenv("MCP_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    allowed_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]
    version = _os.getenv("APP_VERSION", "2.0.0")

    return {
        "status": status,
        "timestamp": _dt.utcnow().isoformat(),
        "version": version,
        "tool_count": tool_count,
        "tools_registered": tools_registered,
        "sessions_active": sessions_active,
        "auth_required": auth_required,
        "allowed_origins": allowed_origins,
        "checks": checks
    }

# ============================================================================
# PHASE 1 SECURITY: Rate Limiting Middleware (MUST BE FIRST!)
# ============================================================================
from backend.middleware.rate_limiter import RateLimitMiddleware, get_rate_limiter

rate_limiter = get_rate_limiter()
app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)

# ============================================================================
# Task 10: Correlation ID Middleware (for distributed tracing)
# ============================================================================
from backend.middleware.correlation_id import CorrelationIdMiddleware, configure_correlation_logging

app.add_middleware(CorrelationIdMiddleware, header_name="X-Request-ID")
# Note: configure_correlation_logging() called in lifespan if needed (optional)

# ============================================================================
# WEEK 2 DAY 2: HTTP Cache Headers Middleware
# ============================================================================
from backend.middleware.cache_headers import CacheHeadersMiddleware

app.add_middleware(
    CacheHeadersMiddleware,
    max_age=60,
    enable_etag=True,
    enable_last_modified=True,
)

# ============================================================================
# CORS Middleware (global, permissive – refined per /mcp via UnifiedMcpMiddleware)
# ============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# MCP Unified Middleware (AFTER CORS for proper override)
# ============================================================================
import os as _env_os

from backend.api.mcp_middleware import UnifiedMcpMiddleware

mcp_require_auth = _env_os.getenv("MCP_REQUIRE_AUTH", "false").lower() in ("true", "1", "yes")
mcp_auth_token = _env_os.getenv("MCP_API_KEY", "")  # Changed from MCP_AUTH_TOKEN to MCP_API_KEY
mcp_allowed_origins_str = _env_os.getenv("MCP_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
mcp_allowed_origins = [o.strip() for o in mcp_allowed_origins_str.split(",") if o.strip()]

# Perplexity recommendation: Enable auth in staging by default
# Override via env: MCP_REQUIRE_AUTH=false to disable
staging_or_prod = _env_os.getenv("ENVIRONMENT", "development") in ("staging", "production")
if staging_or_prod and not mcp_require_auth:
    logging.getLogger("uvicorn.error").warning(
        "⚠️ MCP auth disabled in staging/production! Set MCP_REQUIRE_AUTH=true and MCP_API_KEY."
    )

app.add_middleware(
    UnifiedMcpMiddleware,
    require_auth=mcp_require_auth,
    auth_token=mcp_auth_token,
    allowed_origins=mcp_allowed_origins
)

import os as _os

app.include_router(security_router.router, prefix="/api/v1", tags=["security"])
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["strategies"])
if (_os.environ.get("USE_MOCK_BACKTESTS", "0").lower() in ("1", "true", "yes")):
    try:
        from backend.api.routers import mock_backtests as _mock_bt
        app.include_router(_mock_bt.router, prefix="/api/v1/backtests", tags=["backtests-mock"])
    except Exception as _e:
        logging.getLogger("uvicorn.error").warning("Failed to enable mock backtests: %s", _e)
        app.include_router(backtests.router, prefix="/api/v1/backtests", tags=["backtests"])
else:
    app.include_router(backtests.router, prefix="/api/v1/backtests", tags=["backtests"])
app.include_router(marketdata.router, prefix="/api/v1/marketdata", tags=["marketdata"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(optimizations.router, prefix="/api/v1/optimizations", tags=["optimizations"])
app.include_router(live_router.router, prefix="/api/v1", tags=["live"])
app.include_router(live_router.router, prefix="/ws", tags=["live-ws"])
app.include_router(wizard_router.router, prefix="/api/v1/wizard", tags=["wizard"])
app.include_router(bots_router.router, prefix="/api/v1/bots", tags=["bots"])
app.include_router(active_deals_router.router, prefix="/api/v1/active-deals", tags=["active-deals"])
app.include_router(health_router.router, prefix="/api/v1", tags=["health"])
app.include_router(health_monitoring_router.router, prefix="/api/v1", tags=["health-monitoring"])
app.include_router(csv_export_router.router, prefix="/api/v1", tags=["csv-export"])
app.include_router(context_router.router, prefix="/api/v1", tags=["context"])
app.include_router(file_ops_router.router, prefix="/api/v1", tags=["file-ops"])
app.include_router(test_runner_router.router, prefix="/api/v1", tags=["tests"])
app.include_router(perplexity_router.router, prefix="/api/v1", tags=["perplexity"])
app.include_router(ai_router.router, prefix="/api/v1", tags=["ai"])
app.include_router(inference.router, prefix="/api/v1", tags=["inference"])
app.include_router(metrics_router.router, prefix="/api/v1", tags=["metrics"])
app.include_router(dashboard_router.router, tags=["dashboard"])
app.include_router(dashboard_metrics_router.router, prefix="/api/v1", tags=["dashboard-metrics"])
app.include_router(strategy_templates_router.router, prefix="/api/v1", tags=["strategy-templates"])
app.include_router(test_router.router, prefix="/api/v1", tags=["testing"])
app.include_router(cache_router.router, prefix="/api/v1", tags=["cache"])
app.include_router(queue_router.router, prefix="/api/v1", tags=["queue"])
app.include_router(executions_router.router, prefix="/api/v1", tags=["executions"])
app.include_router(agent_to_agent_api.router, tags=["agents"])
app.include_router(orchestrator.router, prefix="/api/v1/orchestrator", tags=["orchestrator"])

# Task 9: Include MCP bridge routes
try:
    from backend.api.mcp_routes import router as mcp_bridge_router
    app.include_router(mcp_bridge_router, tags=["mcp-bridge"])
    logging.getLogger("uvicorn.error").info("✅ MCP bridge routes included at /mcp/bridge")
except Exception as _e:
    logging.getLogger("uvicorn.error").warning("⚠️ Failed to include MCP bridge routes: %s", _e)

try:
    _logger = logging.getLogger("uvicorn.error")
    _routes_info = []
    for r in app.router.routes:
        try:
            methods = sorted(getattr(r, 'methods', []) or [])
            path = getattr(r, 'path', '')
            name = getattr(r, 'name', '')
            _routes_info.append(f"{methods}:{path}:{name}")
        except Exception:
            continue
    _logger.info("ROUTE_REGISTRY_START (%d routes)", len(_routes_info))
    for _ri in _routes_info:
        _logger.info("ROUTE %s", _ri)
    _logger.info("ROUTE_REGISTRY_END")
except Exception as _e:
    logging.getLogger("uvicorn.error").warning("Route registry logging failed: %s", _e)

@app.get("/api/test-simple")
async def test_simple_endpoint():
    return {"message": "Simple test works!", "status": "ok"}

from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry()
BACKFILL_UPSERTS = Counter(
    "backfill_upserts_total",
    "Total number of upserts performed by backfill",
    labelnames=("symbol", "interval"),
    registry=REGISTRY,
)
BACKFILL_PAGES = Counter(
    "backfill_pages_total",
    "Total number of pages processed by backfill",
    labelnames=("symbol", "interval"),
    registry=REGISTRY,
)
BACKFILL_DURATION = Histogram(
    "backfill_duration_seconds",
    "Backfill duration in seconds",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1200, float("inf")),
    registry=REGISTRY,
)
RUNS_BY_STATUS = Counter(
    "backfill_runs_total",
    "Backfill runs by terminal status",
    labelnames=("status",),
    registry=REGISTRY,
)
# MCP metrics (registered in same custom registry)
MCP_TOOL_CALLS = Counter(
    "mcp_tool_calls_total",
    "Total MCP tool invocations",
    labelnames=("tool", "success"),
    registry=REGISTRY,
)
MCP_TOOL_ERRORS = Counter(
    "mcp_tool_errors_total",
    "Total MCP tool errors",
    labelnames=("tool", "error_type"),
    registry=REGISTRY,
)
MCP_TOOL_DURATION = Histogram(
    "mcp_tool_duration_seconds",
    "MCP tool execution latency",
    labelnames=("tool",),
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0, float("inf")),  # Extended buckets for AI workloads (P95/P99)
    registry=REGISTRY,
)

# Task 13: Enhanced metrics for multi-agent system
CONSENSUS_LOOP_PREVENTED = Counter(
    "consensus_loop_prevented_total",
    "Total consensus loops prevented by guard",
    labelnames=("reason",),  # iteration_cap, duplicate, frequency, depth
    registry=REGISTRY,
)
DLQ_MESSAGES = Counter(
    "dlq_messages_total",
    "Total messages enqueued to DLQ",
    labelnames=("priority", "agent_type"),
    registry=REGISTRY,
)
DLQ_RETRIES = Counter(
    "dlq_retries_total",
    "Total DLQ retry attempts",
    labelnames=("status",),  # success, failed, expired
    registry=REGISTRY,
)
CORRELATION_ID_REQUESTS = Counter(
    "correlation_id_requests_total",
    "Requests with correlation IDs",
    labelnames=("has_correlation_id",),  # true, false
    registry=REGISTRY,
)
MCP_BRIDGE_CALLS = Counter(
    "mcp_bridge_calls_total",
    "MCP bridge direct calls (no HTTP)",
    labelnames=("tool", "success"),
    registry=REGISTRY,
)
MCP_BRIDGE_DURATION = Histogram(
    "mcp_bridge_tool_duration_seconds",
    "Duration of MCP bridge tool calls",
    labelnames=("tool", "success"),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, float("inf")),  # Fine-grained latency buckets
    registry=REGISTRY,
)

def metrics_inc_upserts(symbol: str, interval: str, n: int = 1):
    try:
        BACKFILL_UPSERTS.labels(symbol=symbol, interval=interval).inc(n)
    except Exception:
        pass

def metrics_inc_pages(symbol: str, interval: str, n: int = 1):
    try:
        BACKFILL_PAGES.labels(symbol=symbol, interval=interval).inc(n)
    except Exception:
        pass

def metrics_observe_duration(seconds: float):
    try:
        BACKFILL_DURATION.observe(seconds)
    except Exception:
        pass

def metrics_inc_run_status(status: str):
    try:
        RUNS_BY_STATUS.labels(status=status).inc(1)
    except Exception:
        pass

@app.get("/metrics")
async def metrics():
    legacy_metrics = generate_latest(REGISTRY).decode('utf-8')
    orchestrator_metrics = ""
    try:
        from orchestrator.api.metrics import get_metrics
        metrics_collector = get_metrics()
        orchestrator_metrics = await metrics_collector.export_prometheus()
    except Exception as e:
        orchestrator_metrics = f"# MCP Orchestrator metrics unavailable: {str(e)}\n"
    combined = legacy_metrics + "\n" + orchestrator_metrics
    return Response(combined, media_type=CONTENT_TYPE_LATEST)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz():
    return {"status": "ready"}

@app.get("/livez")
def livez():
    return {"status": "alive"}

@app.get("/api/v1/healthz")
def healthz_v1():
    return healthz()

@app.get("/api/v1/readyz")
def readyz_v1():
    return readyz()

@app.get("/api/v1/livez")
def livez_v1():
    return livez()

@app.get("/api/v1/exchangez")
def exchangez():
    import time
    from typing import Any

    import requests
    t0 = time.perf_counter()
    url = "https://api.bybit.com/v5/market/kline"
    params = {"category": "linear", "symbol": "BTCUSDT", "interval": "1", "limit": 1}
    try:
        r = requests.get(url, params=params, timeout=2.0)
        latency = time.perf_counter() - t0
        status = r.status_code
        ok = r.ok
        payload: Any = None
        try:
            payload = r.json()
        except Exception:
            payload = None
        ret_code = None
        if isinstance(payload, dict):
            ret_code = payload.get("retCode") or payload.get("code")
        if ok and (ret_code in (0, None)):
            return {"status": "ok", "latency_ms": round(latency * 1000, 1), "http": status}
        return Response(
            content={
                "status": "down",
                "latency_ms": round(latency * 1000, 1),
                "http": status,
                "retCode": ret_code,
            }.__str__(),
            media_type="application/json",
            status_code=503,
        )
    except Exception as e:
        latency = time.perf_counter() - t0
        return Response(
            content={
                "status": "down",
                "error": str(e),
                "latency_ms": round(latency * 1000, 1),
            }.__str__(),
            media_type="application/json",
            status_code=503,
        )

# Background Bybit WS manager is handled via the app lifespan above.

# =============================
# NOW register MCP HTTP routes (after custom health route is defined)
# =============================
mcp_app = mcp.http_app(path="/mcp")
app.router.routes.extend(mcp_app.routes)

# Capture tool registry snapshot with delay for proper registration
async def capture_tool_registry():
    await asyncio.sleep(1)  # Wait for tools to fully register
    try:
        tools_dict = await mcp.get_tools()
        tools = list(tools_dict.keys())
        app.state.mcp_tools = tools
        logging.getLogger("uvicorn.error").info(f"✅ MCP Server routes added at /mcp ({len(tools)} agent tools registered: {tools})")
    except Exception as e:
        logging.getLogger("uvicorn.error").warning(f"⚠️ Could not access MCP tool registry: {e}")

# Removed: asyncio.create_task() at module level causes "no running event loop" error
# This will be called via lifespan startup instead
