"""MCP FastAPI Bridge

Lightweight in-process bridge providing a stable abstraction over FastMCP.
Goals:
- Decouple UnifiedAgentInterface from raw HTTP loopback (/mcp/tools/call)
- Offer programmatic tool listing & invocation (no network hop)
- Provide uniform response schema (success, content/error, metadata)
- Prepare for future correlation ID + auth enforcement

NOTE: This does NOT replace FastMCP. It wraps the existing `mcp` instance
from `backend.api.app` and exposes a safer surface. Task 8 will patch
`UnifiedAgentInterface._try_mcp` to use this bridge directly.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

try:
    from backend.agents.circuit_breaker_manager import (
        get_circuit_manager,
        CircuitBreakerError,
    )
except Exception:  # pragma: no cover - fallback when running outside backend
    get_circuit_manager = None  # type: ignore
    CircuitBreakerError = Exception  # type: ignore

# Lazy import to avoid circular load during app startup
# Import mcp only when needed (inside initialize method)
_mcp_instance = None


# =============================
# Structured Error Model
# =============================
@dataclass
class StructuredError:
    """Standardized error response for MCP bridge failures"""
    error_type: str  # e.g., "ValidationError", "InvocationError", "TimeoutError"
    message: str
    stage: str  # e.g., "validation", "invocation", "normalization"
    retryable: bool
    tool: str
    correlation_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": False,
            "error_type": self.error_type,
            "message": self.message,
            "stage": self.stage,
            "retryable": self.retryable,
            "tool": self.tool,
        }
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.details:
            result["details"] = self.details
        return result


# =============================
# Tool Argument Schema Registry
# =============================
TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "mcp_agent_to_agent_send_to_deepseek": {
        "required": ["content"],
        "optional": ["conversation_id", "context"],
        "types": {
            "content": str,
            "conversation_id": (str, type(None)),
            "context": (dict, type(None)),
        }
    },
    "mcp_agent_to_agent_send_to_perplexity": {
        "required": ["content"],
        "optional": ["conversation_id", "context"],
        "types": {
            "content": str,
            "conversation_id": (str, type(None)),
            "context": (dict, type(None)),
        }
    },
    "mcp_agent_to_agent_get_consensus": {
        "required": ["question"],
        "optional": ["agents"],
        "types": {
            "question": str,
            "agents": (list, type(None)),
        }
    },
    "mcp_read_project_file": {
        "required": ["file_path"],
        "optional": ["max_size_kb"],
        "types": {
            "file_path": str,
            "max_size_kb": int,
        }
    },
    "mcp_list_project_structure": {
        "required": [],
        "optional": ["directory", "max_depth", "include_hidden"],
        "types": {
            "directory": str,
            "max_depth": int,
            "include_hidden": bool,
        }
    },
    "mcp_analyze_code_quality": {
        "required": ["file_path"],
        "optional": ["tools"],
        "types": {
            "file_path": str,
            "tools": (list, type(None)),
        }
    },
}


def validate_tool_arguments(
    tool_name: str, 
    arguments: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> Optional[StructuredError]:
    """
    Validate tool arguments against schema registry.
    
    Returns:
        StructuredError if validation fails, None if validation passes
    """
    schema = TOOL_SCHEMAS.get(tool_name)
    if not schema:
        # No schema registered - allow invocation (permissive for unregistered tools)
        return None
    
    # Check required arguments
    required = schema.get("required", [])
    missing = [arg for arg in required if arg not in arguments]
    if missing:
        return StructuredError(
            error_type="ValidationError",
            message=f"Missing required arguments: {', '.join(missing)}",
            stage="validation",
            retryable=False,
            tool=tool_name,
            correlation_id=correlation_id,
            details={"missing_args": missing, "required": required}
        )
    
    # Check for unknown arguments
    allowed = set(required) | set(schema.get("optional", []))
    unknown = [arg for arg in arguments.keys() if arg not in allowed]
    if unknown:
        return StructuredError(
            error_type="ValidationError",
            message=f"Unknown arguments: {', '.join(unknown)}",
            stage="validation",
            retryable=False,
            tool=tool_name,
            correlation_id=correlation_id,
            details={"unknown_args": unknown, "allowed": list(allowed)}
        )
    
    # Check argument types
    types = schema.get("types", {})
    type_errors = []
    for arg_name, arg_value in arguments.items():
        expected_type = types.get(arg_name)
        if expected_type and not isinstance(arg_value, expected_type):
            type_errors.append({
                "arg": arg_name,
                "expected": str(expected_type),
                "got": type(arg_value).__name__
            })
    
    if type_errors:
        return StructuredError(
            error_type="ValidationError",
            message=f"Type mismatch for arguments: {', '.join(e['arg'] for e in type_errors)}",
            stage="validation",
            retryable=False,
            tool=tool_name,
            correlation_id=correlation_id,
            details={"type_errors": type_errors}
        )
    
    return None  # Validation passed


def _get_mcp_instance():
    """Lazy getter for mcp instance to avoid circular import"""
    global _mcp_instance
    if _mcp_instance is None:
        try:
            from backend.api.app import mcp
            _mcp_instance = mcp
        except Exception as e:
            logger.error(f"Failed to import MCP instance: {e}")
            return None
    return _mcp_instance


@dataclass
class McpToolInfo:
    name: str
    description: str | None
    callable: Callable[..., Any]


class MCPFastAPIBridge:
    """Singleton bridge for MCP tool introspection & invocation."""
    def __init__(self) -> None:
        self._initialized = False
        self._tools: Dict[str, McpToolInfo] = {}
        self._lock = asyncio.Lock()
        self.breaker_name = "mcp_server"
        self.circuit_manager = None
        if get_circuit_manager is not None:
            try:
                self.circuit_manager = get_circuit_manager()
                if self.breaker_name not in self.circuit_manager.get_all_breakers():
                    self.circuit_manager.register_breaker(
                        name=self.breaker_name,
                        fail_max=3,
                        timeout_duration=30,
                        expected_exception=Exception,
                    )
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning(
                    "MCP bridge could not initialize circuit breaker manager: %s",
                    exc,
                )
                self.circuit_manager = None

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            mcp = _get_mcp_instance()
            if mcp is None:
                logger.error("❌ FastMCP instance unavailable; bridge inactive")
                return
            try:
                tools_dict = await mcp.get_tools()  # returns name->FunctionTool
                for name, fn_tool in tools_dict.items():
                    desc = getattr(fn_tool, "description", None)
                    # FunctionTool exposes .call / is awaitable; keep original object
                    self._tools[name] = McpToolInfo(
                        name=name,
                        description=desc,
                        callable=fn_tool,  # call later via await fn_tool(**kwargs)
                    )
                self._initialized = True
                logger.info(f"✅ MCP bridge initialized with {len(self._tools)} tools")
            except Exception as e:
                logger.error(f"❌ Failed to initialize MCP bridge: {e}")

    async def list_tools(self) -> List[dict]:
        if not self._initialized:
            await self.initialize()
        return [
            {"name": t.name, "description": t.description} for t in self._tools.values()
        ]

    async def _execute_with_breaker(self, func: Callable[[], Any]):
        """Execute coroutine factory through the shared circuit breaker if available."""
        if not self.circuit_manager:
            result = func()
            return await result if asyncio.iscoroutine(result) else result
        return await self.circuit_manager.call_with_breaker(self.breaker_name, func)

    async def call_tool(self, name: str, arguments: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Call MCP tool with progressive retry strategy on timeout.
        
        ✅ FIX: Implements progressive timeouts (30→60→120→300→600s)
        instead of single fixed timeout.
        """
        if not self._initialized:
            await self.initialize()
        arguments = arguments or {}
        
        # ✅ FIX: Progressive timeout configuration
        PROGRESSIVE_TIMEOUTS = [60, 120, 300, 600]  # 1m, 2m, 5m, 10m
        last_exception = None
        
        for attempt, timeout in enumerate(PROGRESSIVE_TIMEOUTS, 1):
            try:
                logger.info(f"🔄 MCP tool '{name}' attempt {attempt}/{len(PROGRESSIVE_TIMEOUTS)} (timeout: {timeout}s)")
                
                async def _attempt_call():
                    return await asyncio.wait_for(
                        self._execute_tool_call(name, arguments),
                        timeout=timeout,
                    )

                return await self._execute_with_breaker(_attempt_call)
                
            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(
                    f"⚠️ MCP tool '{name}' timeout after {timeout}s (attempt {attempt}/{len(PROGRESSIVE_TIMEOUTS)})"
                )
                if attempt < len(PROGRESSIVE_TIMEOUTS):
                    await asyncio.sleep(2)  # Small delay between retries
                    continue
                else:
                    # All attempts exhausted
                    break
            except CircuitBreakerError as e:
                last_exception = e
                logger.warning(
                    "⚠️ MCP circuit breaker open; tool '%s' execution skipped", name
                )
                break
            
            except Exception as e:
                # Non-timeout error: don't retry, return immediately
                last_exception = e
                logger.error(f"❌ MCP tool '{name}' failed with {type(e).__name__}: {e}")
                break
        
        # All retries exhausted or non-timeout error
        if isinstance(last_exception, CircuitBreakerError):
            error = StructuredError(
                error_type="CircuitBreakerOpen",
                message="Circuit breaker open for MCP server",
                stage="circuit_breaker",
                retryable=True,
                tool=name,
                correlation_id=None,
                details={},
            )
        else:
            error = StructuredError(
                error_type="TimeoutError" if isinstance(last_exception, asyncio.TimeoutError) else type(last_exception).__name__,
                message=f"All {len(PROGRESSIVE_TIMEOUTS)} timeout attempts exhausted" if isinstance(last_exception, asyncio.TimeoutError) else str(last_exception),
                stage="invocation",
                retryable=isinstance(last_exception, asyncio.TimeoutError),
                tool=name,
                correlation_id=None,
                details={"timeouts_tried": PROGRESSIVE_TIMEOUTS}
            )
        return error.to_dict()
    
    async def _execute_tool_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internal method: actual tool execution logic (extracted for timeout wrapping).
        Original call_tool logic moved here.
        """
        if not self._initialized:
            await self.initialize()
        arguments = arguments or {}
        
        # Unified timing & correlation ID (start before invocation attempt)
        import time
        start_time = time.perf_counter()
        
        # Fetch correlation ID once (avoid duplicate middleware/contextvar lookups)
        try:
            from backend.middleware.correlation_id import get_correlation_id
            corr_id = get_correlation_id()
        except Exception:
            corr_id = None
        
        # Tool existence check
        if name not in self._tools:
            logger.warning(f"MCP bridge: unknown tool '{name}'")
            
            # Task 13: Track bridge metrics
            try:
                from backend.api.app import MCP_BRIDGE_CALLS
                MCP_BRIDGE_CALLS.labels(tool=name, success="false").inc()
            except Exception:
                pass
            
            error = StructuredError(
                error_type="ToolNotFoundError",
                message=f"Tool '{name}' not found in registry",
                stage="lookup",
                retryable=False,
                tool=name,
                correlation_id=corr_id,
                details={"available_tools": list(self._tools.keys())}
            )
            return error.to_dict()
        
        # Argument validation
        validation_error = validate_tool_arguments(name, arguments, corr_id)
        if validation_error:
            logger.warning(f"MCP bridge: validation failed for tool '{name}': {validation_error.message}")
            try:
                from backend.api.app import MCP_BRIDGE_CALLS
                MCP_BRIDGE_CALLS.labels(tool=name, success="false").inc()
            except Exception:
                pass
            return validation_error.to_dict()
        
        tool_info = self._tools[name]
        tool_obj = tool_info.callable
        
        try:
            # Attempt several invocation patterns for FastMCP tool wrappers:
            # Priority: .call() -> .run() -> direct await/call
            result: Any = None
            invoked = False

            import inspect
            # Helper to invoke with adaptive parameter passing
            def _invoke(callable_obj, prefer_kwargs=True):
                sig = None
                try:
                    sig = inspect.signature(callable_obj)
                except Exception:
                    pass
                if sig:
                    params = list(sig.parameters.values())
                    # Remove self if bound method
                    if params and params[0].name == 'self':
                        params = params[1:]
                    # If single param that looks like container (args/arguments/data), pass dict as positional
                    if len(params) == 1 and params[0].kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY):
                        pname = params[0].name.lower()
                        if pname in {'args','arguments','data','payload','input'}:
                            return callable_obj(arguments)
                    # Else pass kwargs
                    if prefer_kwargs:
                        return callable_obj(**arguments)
                # Fallback heuristic
                if prefer_kwargs:
                    try:
                        return callable_obj(**arguments)
                    except TypeError:
                        return callable_obj(arguments)
                return callable_obj(arguments)

            # 1. .call method
            if hasattr(tool_obj, "call") and callable(getattr(tool_obj, "call")):
                maybe = _invoke(getattr(tool_obj, "call"))
                result = await maybe if asyncio.iscoroutine(maybe) else maybe
                invoked = True
            # 2. .run method (fallback)
            elif hasattr(tool_obj, "run") and callable(getattr(tool_obj, "run")):
                maybe = _invoke(getattr(tool_obj, "run"))
                result = await maybe if asyncio.iscoroutine(maybe) else maybe
                invoked = True
            # 3. Awaitable object directly (e.g., async def wrapper(*args))
            elif callable(tool_obj):
                maybe = _invoke(tool_obj)
                result = await maybe if asyncio.iscoroutine(maybe) else maybe
                invoked = True

            if not invoked:
                raise TypeError(f"Tool '{name}' is not invokable (no call/run and not callable)")
            
            # Task 13: Track successful bridge calls
            try:
                from backend.api.app import MCP_BRIDGE_CALLS
                MCP_BRIDGE_CALLS.labels(tool=name, success="true").inc()
            except Exception:
                pass
            # Observe duration success path
            try:
                from backend.api.app import MCP_BRIDGE_DURATION
                duration = time.perf_counter() - start_time
                MCP_BRIDGE_DURATION.labels(tool=name, success="true").observe(duration)
            except Exception:
                pass
            
            # Normalize result (unwrap ToolResult or other wrappers)
            try:
                from fastmcp.tools.tool import ToolResult  # type: ignore
            except Exception:
                class ToolResult:  # fallback stub
                    pass

            if isinstance(result, ToolResult):
                # Prefer .data or .content attribute if present
                data = getattr(result, "data", None) or getattr(result, "content", None) or result
                result = data

            # Flatten FastMCP TextContent sequences (list of objects with .text)
            try:
                # Import lazily; if unavailable just skip
                from fastmcp.schemas import TextContent  # type: ignore
                TextContentType = TextContent
            except Exception:  # pragma: no cover - optional import
                TextContentType = None

            if isinstance(result, list):
                # If list of TextContent or objects/dicts exposing 'text', join their text payloads
                texts: List[str] = []
                all_text_like = True
                for item in result:
                    text_val = None
                    if TextContentType and isinstance(item, TextContentType):  # proper TextContent
                        text_val = getattr(item, "text", None)
                    elif hasattr(item, "text"):
                        text_val = getattr(item, "text", None)
                    elif isinstance(item, dict) and "text" in item:
                        text_val = item["text"]
                    if text_val is not None and isinstance(text_val, str):
                        texts.append(text_val)
                    else:
                        all_text_like = False
                        break
                if all_text_like and texts:
                    result = "\n".join(texts)

            base: Dict[str, Any]
            if isinstance(result, dict):
                if "success" in result:
                    base = {"tool": name, **result}
                else:
                    base = {"success": True, "tool": name, "content": result}
            elif isinstance(result, (str, bytes)):
                base = {"success": True, "tool": name, "content": result if isinstance(result, str) else result.decode("utf-8", "ignore")}
            else:
                base = {"success": True, "tool": name, "content": str(result)}
            if corr_id:
                base["correlation_id"] = corr_id
            return base
        except Exception as e:  # pragma: no cover - defensive error path
            logger.error(f"❌ MCP tool '{name}' execution failed: {e}")
            
            # Task 13: Track bridge failures
            try:
                from backend.api.app import MCP_BRIDGE_CALLS
                MCP_BRIDGE_CALLS.labels(tool=name, success="false").inc()
            except Exception:
                pass
            # Observe duration failure path (accurate even on early exceptions)
            try:
                from backend.api.app import MCP_BRIDGE_DURATION
                duration = time.perf_counter() - start_time
                MCP_BRIDGE_DURATION.labels(tool=name, success="false").observe(duration)
            except Exception:
                pass
            
            # Structured error response
            error_type = type(e).__name__
            retryable = error_type in ("TimeoutError", "ConnectionError", "HTTPError")
            
            error = StructuredError(
                error_type=error_type,
                message=str(e),
                stage="invocation",
                retryable=retryable,
                tool=name,
                correlation_id=corr_id,
                details={"exception_type": error_type}
            )
            return error.to_dict()


_bridge_instance: MCPFastAPIBridge | None = None


def get_mcp_bridge() -> MCPFastAPIBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = MCPFastAPIBridge()
    return _bridge_instance


async def ensure_mcp_bridge_initialized() -> None:
    bridge = get_mcp_bridge()
    await bridge.initialize()

__all__ = ["get_mcp_bridge", "ensure_mcp_bridge_initialized", "MCPFastAPIBridge"]
