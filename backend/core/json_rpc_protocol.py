"""
JSON-RPC 2.0 Protocol Implementation для MCP Server
====================================================

Полная реализация JSON-RPC 2.0 спецификации с:
- Pydantic models для валидации
- API версионирование (/v1/, /v2/)
- Error handling по стандарту JSON-RPC
- Async/await pattern
- OpenAPI documentation

Спецификация: https://www.jsonrpc.org/specification

Author: DeepSeek Code Agent
Date: 2025-11-02
"""

from typing import Any, Dict, List, Optional, Union, Literal
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# JSON-RPC 2.0 ERROR CODES (Standard + Custom)
# ═══════════════════════════════════════════════════════════════════════════

class JSONRPCErrorCode(int, Enum):
    """
    JSON-RPC 2.0 Standard Error Codes + Custom Extensions
    
    Standard Errors (-32768 to -32000):
        -32700: Parse error (Invalid JSON)
        -32600: Invalid Request (Not a valid Request object)
        -32601: Method not found
        -32602: Invalid params
        -32603: Internal error
        -32000 to -32099: Server errors (reserved for implementation-defined)
    
    Custom MCP Errors (-32000 to -32099):
        -32000: Agent unavailable
        -32001: Task execution failed
        -32002: Validation failed
        -32003: Timeout error
        -32004: Rate limit exceeded
        -32005: Authentication failed
        -32006: Authorization failed
    """
    # Standard errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # Custom MCP errors
    AGENT_UNAVAILABLE = -32000
    TASK_EXECUTION_FAILED = -32001
    VALIDATION_FAILED = -32002
    TIMEOUT_ERROR = -32003
    RATE_LIMIT_EXCEEDED = -32004
    AUTHENTICATION_FAILED = -32005
    AUTHORIZATION_FAILED = -32006


# ═══════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS - JSON-RPC 2.0 Request/Response
# ═══════════════════════════════════════════════════════════════════════════

class JSONRPCRequest(BaseModel):
    """
    JSON-RPC 2.0 Request Object
    
    A rpc call is represented by sending a Request object to a Server.
    
    Fields:
        jsonrpc: "2.0" (exactly)
        method: Name of the method to be invoked
        params: Parameters for the method (optional)
        id: Request identifier (string, number, or null)
    
    Notifications:
        If id is null, it's a notification (no response expected)
    """
    jsonrpc: Literal["2.0"] = Field(
        default="2.0",
        description="JSON-RPC version (must be exactly '2.0')"
    )
    method: str = Field(
        ...,
        description="Name of the method to be invoked",
        min_length=1
    )
    params: Optional[Union[Dict[str, Any], List[Any]]] = Field(
        default=None,
        description="Parameters for the method (structured values)"
    )
    id: Optional[Union[str, int]] = Field(
        default=None,
        description="Request identifier (null for notifications)"
    )
    
    @validator("method")
    def method_must_not_start_with_rpc(cls, v):
        """Method names starting with 'rpc.' are reserved"""
        if v.startswith("rpc."):
            raise ValueError("Method names starting with 'rpc.' are reserved")
        return v
    
    @validator("id")
    def id_must_be_valid(cls, v):
        """ID must be string, number, or null (not fractional numbers)"""
        if v is not None:
            if isinstance(v, float):
                raise ValueError("ID must not be fractional number")
        return v
    
    class Config:
        schema_extra = {
            "examples": [
                {
                    "jsonrpc": "2.0",
                    "method": "run_task",
                    "params": {
                        "tool": "DeepSeek",
                        "prompt": "Generate DCA strategy code",
                        "priority": 10
                    },
                    "id": "req-123"
                },
                {
                    "jsonrpc": "2.0",
                    "method": "get_status",
                    "params": {"include_workers": True},
                    "id": 1
                }
            ]
        }


class JSONRPCError(BaseModel):
    """
    JSON-RPC 2.0 Error Object
    
    When a rpc call encounters an error, the Response Object contains the error member.
    
    Fields:
        code: Number indicating the error type
        message: Short description of the error
        data: Additional information about the error (optional)
    """
    code: int = Field(
        ...,
        description="Error code (integer)"
    )
    message: str = Field(
        ...,
        description="Short description of the error",
        min_length=1
    )
    data: Optional[Any] = Field(
        default=None,
        description="Additional information about the error"
    )
    
    class Config:
        schema_extra = {
            "examples": [
                {
                    "code": -32601,
                    "message": "Method not found",
                    "data": {"method": "unknown_method"}
                },
                {
                    "code": -32000,
                    "message": "Agent unavailable",
                    "data": {"agent": "DeepSeek", "reason": "API key not configured"}
                }
            ]
        }


class JSONRPCResponse(BaseModel):
    """
    JSON-RPC 2.0 Response Object
    
    When a rpc call is made, the Server replies with a Response.
    
    Success Response:
        - jsonrpc: "2.0"
        - result: The result of the method invocation
        - id: The id from the Request
    
    Error Response:
        - jsonrpc: "2.0"
        - error: Error object
        - id: The id from the Request (or null)
    
    NOTE: Either result or error must be present, but not both.
    """
    jsonrpc: Literal["2.0"] = Field(
        default="2.0",
        description="JSON-RPC version"
    )
    result: Optional[Any] = Field(
        default=None,
        description="Result of the method invocation (success)"
    )
    error: Optional[JSONRPCError] = Field(
        default=None,
        description="Error object (failure)"
    )
    id: Optional[Union[str, int]] = Field(
        ...,
        description="Request identifier from the original Request"
    )
    
    @root_validator
    def check_result_or_error(cls, values):
        """Ensure either result or error is present, but not both"""
        result = values.get("result")
        error = values.get("error")
        
        if result is not None and error is not None:
            raise ValueError("Response must contain either result or error, not both")
        
        if result is None and error is None:
            raise ValueError("Response must contain either result or error")
        
        return values
    
    class Config:
        schema_extra = {
            "examples": [
                {
                    "jsonrpc": "2.0",
                    "result": {"status": "success", "data": "..."},
                    "id": "req-123"
                },
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": "Method not found"
                    },
                    "id": "req-456"
                }
            ]
        }


class JSONRPCBatchRequest(BaseModel):
    """
    JSON-RPC 2.0 Batch Request
    
    To send several Request objects at the same time, the Client MAY send an Array.
    """
    __root__: List[JSONRPCRequest] = Field(
        ...,
        min_items=1,
        description="Array of JSON-RPC 2.0 Request objects"
    )
    
    class Config:
        schema_extra = {
            "example": [
                {"jsonrpc": "2.0", "method": "run_task", "params": {}, "id": 1},
                {"jsonrpc": "2.0", "method": "get_status", "id": 2}
            ]
        }


class JSONRPCBatchResponse(BaseModel):
    """
    JSON-RPC 2.0 Batch Response
    
    The Server responds with an Array containing the corresponding Response objects.
    """
    __root__: List[JSONRPCResponse] = Field(
        ...,
        description="Array of JSON-RPC 2.0 Response objects"
    )


# ═══════════════════════════════════════════════════════════════════════════
# MCP-SPECIFIC REQUEST MODELS (Extended Params)
# ═══════════════════════════════════════════════════════════════════════════

class RunTaskParams(BaseModel):
    """
    Parameters for 'run_task' method
    
    Запуск reasoning/coding/ML workflow с приоритизацией
    """
    tool: str = Field(
        ...,
        description="Tool/Agent name (DeepSeek, Perplexity, Copilot)",
        examples=["DeepSeek", "Perplexity", "Copilot"]
    )
    prompt: str = Field(
        ...,
        description="Task prompt/query",
        min_length=1
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Task priority (1=low, 10=high)"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for the task"
    )
    timeout: Optional[int] = Field(
        default=120,
        ge=10,
        le=600,
        description="Task timeout in seconds"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Task tags for categorization"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "tool": "DeepSeek",
                "prompt": "Generate DCA strategy for BTCUSDT",
                "priority": 8,
                "context": {"symbol": "BTCUSDT", "timeframe": "1h"},
                "timeout": 180,
                "tags": ["strategy", "generation"]
            }
        }


class GetStatusParams(BaseModel):
    """
    Parameters for 'get_status' method
    
    Получение состояния очередей, воркеров, агентов
    """
    include_workers: bool = Field(
        default=True,
        description="Include worker status"
    )
    include_queue: bool = Field(
        default=True,
        description="Include queue metrics"
    )
    include_metrics: bool = Field(
        default=False,
        description="Include detailed metrics"
    )


class GetAnalyticsParams(BaseModel):
    """
    Parameters for 'get_analytics' method
    
    Live-данные о latency, throughput, utilization
    """
    time_range: str = Field(
        default="1h",
        description="Time range (1h, 6h, 24h, 7d)",
        pattern="^(1h|6h|24h|7d)$"
    )
    metrics: List[str] = Field(
        default_factory=lambda: ["latency", "throughput"],
        description="Metrics to retrieve"
    )
    agents: Optional[List[str]] = Field(
        default=None,
        description="Filter by specific agents"
    )


class InjectTaskParams(BaseModel):
    """
    Parameters for 'inject' method
    
    Ручной ввод или корректировка задач
    """
    task: Dict[str, Any] = Field(
        ...,
        description="Task payload"
    )
    force: bool = Field(
        default=False,
        description="Force injection even if queue is full"
    )
    position: Literal["front", "back"] = Field(
        default="back",
        description="Queue position"
    )


class ControlScaleParams(BaseModel):
    """
    Parameters for 'control/scale' method
    
    Масштабирование, преемпция, управление ресурсами
    """
    action: Literal["scale_up", "scale_down", "pause", "resume", "preempt"] = Field(
        ...,
        description="Control action"
    )
    target: Optional[str] = Field(
        default=None,
        description="Target worker/queue"
    )
    scale_factor: Optional[int] = Field(
        default=1,
        ge=1,
        le=10,
        description="Scale factor (for scale_up/down)"
    )


# ═══════════════════════════════════════════════════════════════════════════
# JSON-RPC PROTOCOL HANDLER
# ═══════════════════════════════════════════════════════════════════════════

class JSONRPCProtocolHandler:
    """
    JSON-RPC 2.0 Protocol Handler for MCP Server
    
    Features:
        - Request validation via Pydantic
        - Method routing
        - Error handling по стандарту JSON-RPC
        - Batch request support
        - Logging всех запросов/ответов
    """
    
    def __init__(self):
        self.methods: Dict[str, callable] = {}
        self.request_history: List[Dict] = []
        
    def register_method(self, name: str, handler: callable):
        """
        Регистрация метода JSON-RPC
        
        Args:
            name: Имя метода (например, "run_task")
            handler: Async function для обработки метода
        """
        if name.startswith("rpc."):
            raise ValueError("Method names starting with 'rpc.' are reserved")
        
        self.methods[name] = handler
        logger.info(f"[JSON-RPC] Registered method: {name}")
    
    async def handle_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """
        Обработка одиночного JSON-RPC запроса
        
        Args:
            request: Валидированный JSONRPCRequest
        
        Returns:
            JSONRPCResponse (success или error)
        """
        start_time = datetime.now()
        request_id = request.id
        method = request.method
        
        logger.info(f"[JSON-RPC] Request {request_id}: {method}")
        
        try:
            # Проверка существования метода
            if method not in self.methods:
                return JSONRPCResponse(
                    error=JSONRPCError(
                        code=JSONRPCErrorCode.METHOD_NOT_FOUND,
                        message=f"Method '{method}' not found",
                        data={"available_methods": list(self.methods.keys())}
                    ),
                    id=request_id
                )
            
            # Вызов обработчика метода
            handler = self.methods[method]
            result = await handler(request.params)
            
            # Success response
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Логирование
            self._log_request(request_id, method, "success", execution_time)
            
            return JSONRPCResponse(
                result={
                    "data": result,
                    "metadata": {
                        "execution_time": execution_time,
                        "timestamp": datetime.now().isoformat()
                    }
                },
                id=request_id
            )
            
        except ValueError as e:
            # Invalid params
            logger.error(f"[JSON-RPC] Invalid params for {method}: {e}")
            return JSONRPCResponse(
                error=JSONRPCError(
                    code=JSONRPCErrorCode.INVALID_PARAMS,
                    message="Invalid method parameters",
                    data={"error": str(e)}
                ),
                id=request_id
            )
            
        except Exception as e:
            # Internal error
            logger.error(f"[JSON-RPC] Internal error in {method}: {e}", exc_info=True)
            return JSONRPCResponse(
                error=JSONRPCError(
                    code=JSONRPCErrorCode.INTERNAL_ERROR,
                    message="Internal server error",
                    data={"error": str(e)}
                ),
                id=request_id
            )
    
    async def handle_batch_request(self, batch: JSONRPCBatchRequest) -> JSONRPCBatchResponse:
        """
        Обработка batch запроса (массив запросов)
        
        Args:
            batch: Массив JSONRPCRequest
        
        Returns:
            Массив JSONRPCResponse
        """
        logger.info(f"[JSON-RPC] Batch request with {len(batch.__root__)} requests")
        
        responses = []
        for request in batch.__root__:
            response = await self.handle_request(request)
            responses.append(response)
        
        return JSONRPCBatchResponse(__root__=responses)
    
    def _log_request(self, request_id: Optional[Union[str, int]], method: str, status: str, execution_time: float):
        """Логирование запроса для аналитики"""
        self.request_history.append({
            "request_id": request_id,
            "method": method,
            "status": status,
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat()
        })
        
        # Ограничение размера истории
        if len(self.request_history) > 10000:
            self.request_history = self.request_history[-5000:]
    
    def get_request_history(self, limit: int = 100) -> List[Dict]:
        """Получение истории запросов"""
        return self.request_history[-limit:]


# ═══════════════════════════════════════════════════════════════════════════
# FASTAPI INTEGRATION (v1, v2 versioning)
# ═══════════════════════════════════════════════════════════════════════════

def create_jsonrpc_app(handler: JSONRPCProtocolHandler, version: str = "v1") -> FastAPI:
    """
    Создание FastAPI приложения с JSON-RPC endpoints
    
    Args:
        handler: JSONRPCProtocolHandler instance
        version: API version (v1, v2)
    
    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title=f"MCP Server JSON-RPC {version.upper()}",
        version=version,
        description="JSON-RPC 2.0 API for MCP Orchestrator"
    )
    
    @app.post(f"/{version}/jsonrpc", response_model=Union[JSONRPCResponse, JSONRPCBatchResponse])
    async def jsonrpc_endpoint(request: Request):
        """
        Unified JSON-RPC 2.0 endpoint
        
        Handles both single and batch requests
        """
        try:
            # Parse raw body
            body = await request.json()
            
            # Check if batch (array) or single request
            if isinstance(body, list):
                # Batch request
                batch = JSONRPCBatchRequest(__root__=[JSONRPCRequest(**req) for req in body])
                response = await handler.handle_batch_request(batch)
                return JSONResponse(
                    content=[resp.dict(exclude_none=True) for resp in response.__root__]
                )
            else:
                # Single request
                jsonrpc_request = JSONRPCRequest(**body)
                response = await handler.handle_request(jsonrpc_request)
                return JSONResponse(
                    content=response.dict(exclude_none=True)
                )
                
        except Exception as e:
            # Parse error или invalid request
            logger.error(f"[JSON-RPC] Parse error: {e}")
            error_response = JSONRPCResponse(
                error=JSONRPCError(
                    code=JSONRPCErrorCode.PARSE_ERROR if "JSON" in str(e) else JSONRPCErrorCode.INVALID_REQUEST,
                    message="Parse error" if "JSON" in str(e) else "Invalid Request",
                    data={"error": str(e)}
                ),
                id=None
            )
            return JSONResponse(
                content=error_response.dict(exclude_none=True),
                status_code=400
            )
    
    @app.get(f"/{version}/methods")
    async def list_methods():
        """List all available JSON-RPC methods"""
        return {
            "methods": list(handler.methods.keys()),
            "version": version
        }
    
    @app.get(f"/{version}/history")
    async def get_history(limit: int = 100):
        """Get request history"""
        return {
            "history": handler.get_request_history(limit),
            "total": len(handler.request_history)
        }
    
    return app


# ═══════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    
    # Create protocol handler
    handler = JSONRPCProtocolHandler()
    
    # Register methods
    async def run_task_handler(params: Optional[Dict]) -> Dict:
        """Example handler for run_task method"""
        validated_params = RunTaskParams(**params)
        return {
            "status": "success",
            "task_id": str(uuid.uuid4()),
            "tool": validated_params.tool,
            "priority": validated_params.priority
        }
    
    async def get_status_handler(params: Optional[Dict]) -> Dict:
        """Example handler for get_status method"""
        if params:
            validated_params = GetStatusParams(**params)
        else:
            validated_params = GetStatusParams()
        
        return {
            "queue_depth": 42,
            "active_workers": 5,
            "include_workers": validated_params.include_workers
        }
    
    handler.register_method("run_task", run_task_handler)
    handler.register_method("get_status", get_status_handler)
    
    # Create FastAPI app (v1)
    app_v1 = create_jsonrpc_app(handler, version="v1")
    
    # Create FastAPI app (v2) - для будущих расширений
    app_v2 = create_jsonrpc_app(handler, version="v2")
    
    print("✅ JSON-RPC 2.0 Protocol готов!")
    print("📡 Endpoints:")
    print("   - POST /v1/jsonrpc")
    print("   - GET  /v1/methods")
    print("   - GET  /v1/history")
    print("   - POST /v2/jsonrpc (future)")
    
    # Test single request
    async def test():
        test_request = JSONRPCRequest(
            method="run_task",
            params={
                "tool": "DeepSeek",
                "prompt": "Test prompt",
                "priority": 8
            },
            id="test-123"
        )
        
        response = await handler.handle_request(test_request)
        print(f"\n✅ Test response: {response.dict()}")
    
    asyncio.run(test())
