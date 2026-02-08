"""
Model Context Protocol Implementation

Based on Anthropic's MCP specification for universal AI agent interoperability.
https://modelcontextprotocol.io/

Key features:
- JSON-RPC 2.0 based communication
- Tool discovery and invocation
- Resource access and management
- Prompt template sharing
- Context propagation across agents
"""

from __future__ import annotations

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from loguru import logger


class MCPMessageType(Enum):
    """MCP message types"""

    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"


class MCPMethod(Enum):
    """Standard MCP methods"""

    # Initialization
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    SHUTDOWN = "shutdown"

    # Tools
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"

    # Resources
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_SUBSCRIBE = "resources/subscribe"
    RESOURCES_UNSUBSCRIBE = "resources/unsubscribe"

    # Prompts
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"

    # Sampling
    SAMPLING_CREATE = "sampling/createMessage"

    # Logging
    LOGGING_SET_LEVEL = "logging/setLevel"


@dataclass
class MCPMessage:
    """MCP protocol message"""

    jsonrpc: str = "2.0"
    id: str | None = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        data = {"jsonrpc": self.jsonrpc}
        if self.id:
            data["id"] = self.id
        if self.method:
            data["method"] = self.method
        if self.params:
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        if self.error:
            data["error"] = self.error
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPMessage:
        """Create from dictionary"""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error"),
        )

    @classmethod
    def request(cls, method: str, params: dict[str, Any] | None = None) -> MCPMessage:
        """Create request message"""
        return cls(
            id=str(uuid.uuid4()),
            method=method,
            params=params or {},
        )

    @classmethod
    def response(cls, id: str, result: Any) -> MCPMessage:
        """Create response message"""
        return cls(id=id, result=result)

    @classmethod
    def error_response(cls, id: str, code: int, message: str, data: Any = None) -> MCPMessage:
        """Create error response"""
        error = {"code": code, "message": message}
        if data:
            error["data"] = data
        return cls(id=id, error=error)


@dataclass
class MCPTool:
    """MCP Tool definition"""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to MCP format"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class MCPResource:
    """MCP Resource definition"""

    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to MCP format"""
        data = {
            "uri": self.uri,
            "name": self.name,
        }
        if self.description:
            data["description"] = self.description
        if self.mime_type:
            data["mimeType"] = self.mime_type
        return data


@dataclass
class MCPPrompt:
    """MCP Prompt template"""

    name: str
    description: str | None = None
    arguments: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to MCP format"""
        data = {"name": self.name}
        if self.description:
            data["description"] = self.description
        if self.arguments:
            data["arguments"] = self.arguments
        return data


@dataclass
class MCPCapabilities:
    """Server/Client capabilities"""

    tools: bool = True
    resources: bool = True
    prompts: bool = True
    sampling: bool = False
    logging: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        caps = {}
        if self.tools:
            caps["tools"] = {}
        if self.resources:
            caps["resources"] = {"subscribe": True}
        if self.prompts:
            caps["prompts"] = {}
        if self.sampling:
            caps["sampling"] = {}
        if self.logging:
            caps["logging"] = {}
        return caps


class MCPTransport(ABC):
    """Abstract transport layer for MCP"""

    @abstractmethod
    async def send(self, message: MCPMessage) -> None:
        """Send message"""
        pass

    @abstractmethod
    async def receive(self) -> MCPMessage:
        """Receive message"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection"""
        pass


class InMemoryTransport(MCPTransport):
    """In-memory transport for testing and local communication"""

    def __init__(self):
        self.incoming: asyncio.Queue[MCPMessage] = asyncio.Queue()
        self.outgoing: asyncio.Queue[MCPMessage] = asyncio.Queue()
        self.peer: InMemoryTransport | None = None

    def connect(self, peer: InMemoryTransport) -> None:
        """Connect to peer transport"""
        self.peer = peer
        peer.peer = self

    async def send(self, message: MCPMessage) -> None:
        """Send to peer's incoming queue"""
        if self.peer:
            await self.peer.incoming.put(message)
        else:
            await self.outgoing.put(message)

    async def receive(self) -> MCPMessage:
        """Receive from incoming queue"""
        return await self.incoming.get()

    async def close(self) -> None:
        """Close connection"""
        self.peer = None


class MCPServer:
    """
    MCP Server Implementation

    Exposes tools, resources, and prompts to MCP clients.

    Example:
        server = MCPServer(name="trading-agent")

        @server.tool("calculate_rsi")
        async def calculate_rsi(prices: list, period: int = 14):
            '''Calculate RSI indicator'''
            return {"rsi": 50.0}

        await server.start()
    """

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        capabilities: MCPCapabilities | None = None,
    ):
        self.name = name
        self.version = version
        self.capabilities = capabilities or MCPCapabilities()

        self.tools: dict[str, MCPTool] = {}
        self.resources: dict[str, MCPResource] = {}
        self.prompts: dict[str, MCPPrompt] = {}

        self.transport: MCPTransport | None = None
        self._running = False
        self._handlers: dict[str, Callable] = {}

        # Register standard handlers
        self._register_standard_handlers()

        logger.info(f"🔌 MCPServer '{name}' initialized")

    def _register_standard_handlers(self) -> None:
        """Register standard MCP method handlers"""
        self._handlers = {
            MCPMethod.INITIALIZE.value: self._handle_initialize,
            MCPMethod.TOOLS_LIST.value: self._handle_tools_list,
            MCPMethod.TOOLS_CALL.value: self._handle_tools_call,
            MCPMethod.RESOURCES_LIST.value: self._handle_resources_list,
            MCPMethod.RESOURCES_READ.value: self._handle_resources_read,
            MCPMethod.PROMPTS_LIST.value: self._handle_prompts_list,
            MCPMethod.PROMPTS_GET.value: self._handle_prompts_get,
        }

    def tool(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> Callable:
        """Decorator to register a tool"""

        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            tool_desc = description or func.__doc__ or f"Tool: {tool_name}"

            # Build input schema from function signature
            import inspect

            sig = inspect.signature(func)
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue

                param_type = "string"
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation is int:
                        param_type = "integer"
                    elif param.annotation is float:
                        param_type = "number"
                    elif param.annotation is bool:
                        param_type = "boolean"
                    elif param.annotation is list:
                        param_type = "array"
                    elif param.annotation is dict:
                        param_type = "object"

                properties[param_name] = {"type": param_type}

                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            input_schema = {
                "type": "object",
                "properties": properties,
            }
            if required:
                input_schema["required"] = required

            tool = MCPTool(
                name=tool_name,
                description=tool_desc,
                input_schema=input_schema,
                handler=func,
            )
            self.tools[tool_name] = tool

            logger.debug(f"🔧 Registered tool: {tool_name}")
            return func

        return decorator

    def add_resource(self, resource: MCPResource) -> None:
        """Add a resource"""
        self.resources[resource.uri] = resource
        logger.debug(f"📁 Added resource: {resource.uri}")

    def add_prompt(self, prompt: MCPPrompt) -> None:
        """Add a prompt template"""
        self.prompts[prompt.name] = prompt
        logger.debug(f"📝 Added prompt: {prompt.name}")

    async def start(self, transport: MCPTransport | None = None) -> None:
        """Start the server"""
        self.transport = transport or InMemoryTransport()
        self._running = True

        logger.info(f"🚀 MCPServer '{self.name}' started")

        # Start message handler loop
        asyncio.create_task(self._message_loop())

    async def stop(self) -> None:
        """Stop the server"""
        self._running = False
        if self.transport:
            await self.transport.close()
        logger.info(f"⏹️ MCPServer '{self.name}' stopped")

    async def _message_loop(self) -> None:
        """Main message processing loop"""
        while self._running:
            try:
                message = await asyncio.wait_for(self.transport.receive(), timeout=1.0)
                await self._handle_message(message)
            except TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Message handling error: {e}")

    async def _handle_message(self, message: MCPMessage) -> None:
        """Handle incoming message"""
        if not message.method:
            return

        handler = self._handlers.get(message.method)
        if handler:
            try:
                result = await handler(message.params or {})
                response = MCPMessage.response(message.id, result)
            except Exception as e:
                response = MCPMessage.error_response(
                    message.id,
                    -32603,
                    str(e),
                )
        else:
            response = MCPMessage.error_response(
                message.id,
                -32601,
                f"Method not found: {message.method}",
            )

        await self.transport.send(response)

    async def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize request"""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": self.capabilities.to_dict(),
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
        }

    async def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/list request"""
        return {"tools": [tool.to_dict() for tool in self.tools.values()]}

    async def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/call request"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool = self.tools[tool_name]
        if not tool.handler:
            raise ValueError(f"Tool has no handler: {tool_name}")

        # Call the handler
        if asyncio.iscoroutinefunction(tool.handler):
            result = await tool.handler(**arguments)
        else:
            result = tool.handler(**arguments)

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result) if not isinstance(result, str) else result,
                }
            ]
        }

    async def _handle_resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle resources/list request"""
        return {"resources": [res.to_dict() for res in self.resources.values()]}

    async def _handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle resources/read request"""
        uri = params.get("uri")

        if uri not in self.resources:
            raise ValueError(f"Unknown resource: {uri}")

        # For now, return placeholder content
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": self.resources[uri].mime_type or "text/plain",
                    "text": f"Content of {uri}",
                }
            ]
        }

    async def _handle_prompts_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle prompts/list request"""
        return {"prompts": [prompt.to_dict() for prompt in self.prompts.values()]}

    async def _handle_prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle prompts/get request"""
        name = params.get("name")

        if name not in self.prompts:
            raise ValueError(f"Unknown prompt: {name}")

        prompt = self.prompts[name]
        return {
            "description": prompt.description,
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": f"Template for {name}",
                    },
                }
            ],
        }


class MCPClient:
    """
    MCP Client Implementation

    Connects to MCP servers and invokes tools/resources.

    Example:
        client = MCPClient()
        await client.connect(server_transport)

        tools = await client.list_tools()
        result = await client.call_tool("calculate_rsi", {"prices": [100, 101, 102]})
    """

    def __init__(self):
        self.transport: MCPTransport | None = None
        self.server_info: dict[str, Any] | None = None
        self.capabilities: dict[str, Any] | None = None
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._running = False

        logger.info("🔌 MCPClient initialized")

    async def connect(self, transport: MCPTransport) -> dict[str, Any]:
        """Connect to server and initialize"""
        self.transport = transport
        self._running = True

        # Start response handler
        asyncio.create_task(self._response_loop())

        # Send initialize request
        result = await self._send_request(
            MCPMethod.INITIALIZE.value,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "mcp-client",
                    "version": "1.0.0",
                },
            },
        )

        self.server_info = result.get("serverInfo")
        self.capabilities = result.get("capabilities")

        logger.info(f"✅ Connected to server: {self.server_info}")
        return result

    async def disconnect(self) -> None:
        """Disconnect from server"""
        self._running = False
        if self.transport:
            await self.transport.close()
        logger.info("🔌 Disconnected from server")

    async def _response_loop(self) -> None:
        """Handle incoming responses"""
        while self._running:
            try:
                message = await asyncio.wait_for(self.transport.receive(), timeout=1.0)

                if message.id and message.id in self._pending_requests:
                    future = self._pending_requests.pop(message.id)
                    if message.error:
                        future.set_exception(Exception(message.error.get("message", "Unknown error")))
                    else:
                        future.set_result(message.result)

            except TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Response handling error: {e}")

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Send request and wait for response"""
        message = MCPMessage.request(method, params)

        future = asyncio.get_event_loop().create_future()
        self._pending_requests[message.id] = future

        await self.transport.send(message)

        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except TimeoutError:
            self._pending_requests.pop(message.id, None)
            raise TimeoutError(f"Request timed out: {method}")

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools"""
        result = await self._send_request(MCPMethod.TOOLS_LIST.value)
        return result.get("tools", [])

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Call a tool"""
        result = await self._send_request(
            MCPMethod.TOOLS_CALL.value,
            {"name": name, "arguments": arguments or {}},
        )

        # Extract text content
        contents = result.get("content", [])
        if contents and contents[0].get("type") == "text":
            text = contents[0].get("text", "")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return result

    async def list_resources(self) -> list[dict[str, Any]]:
        """List available resources"""
        result = await self._send_request(MCPMethod.RESOURCES_LIST.value)
        return result.get("resources", [])

    async def read_resource(self, uri: str) -> Any:
        """Read a resource"""
        result = await self._send_request(
            MCPMethod.RESOURCES_READ.value,
            {"uri": uri},
        )
        return result

    async def list_prompts(self) -> list[dict[str, Any]]:
        """List available prompts"""
        result = await self._send_request(MCPMethod.PROMPTS_LIST.value)
        return result.get("prompts", [])

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Get a prompt"""
        result = await self._send_request(
            MCPMethod.PROMPTS_GET.value,
            {"name": name, "arguments": arguments or {}},
        )
        return result


# Pre-built trading tools for MCP
def create_trading_mcp_server() -> MCPServer:
    """Create MCP server with trading tools"""
    server = MCPServer(
        name="trading-agent-mcp",
        version="1.0.0",
    )

    @server.tool("calculate_rsi")
    async def calculate_rsi(prices: list, period: int = 14) -> dict[str, Any]:
        """Calculate RSI (Relative Strength Index)"""
        import numpy as np

        if len(prices) < period + 1:
            return {"error": "Not enough data"}

        prices = np.array(prices)
        deltas = np.diff(prices)

        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return {"rsi": 100.0}

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return {"rsi": float(rsi), "period": period}

    @server.tool("calculate_macd")
    async def calculate_macd(
        prices: list,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> dict[str, Any]:
        """Calculate MACD indicator"""
        import numpy as np

        if len(prices) < slow_period:
            return {"error": "Not enough data"}

        prices = np.array(prices)

        def ema(data, period):
            alpha = 2 / (period + 1)
            result = np.zeros_like(data)
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
            return result

        ema_fast = ema(prices, fast_period)
        ema_slow = ema(prices, slow_period)
        macd_line = ema_fast - ema_slow
        signal_line = ema(macd_line, signal_period)
        histogram = macd_line - signal_line

        return {
            "macd": float(macd_line[-1]),
            "signal": float(signal_line[-1]),
            "histogram": float(histogram[-1]),
        }

    @server.tool("analyze_market")
    async def analyze_market(
        symbol: str,
        timeframe: str = "4h",
    ) -> dict[str, Any]:
        """Analyze market conditions for a symbol"""
        # Mock analysis
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "trend": "bullish",
            "volatility": "medium",
            "support": 95000,
            "resistance": 100000,
            "recommendation": "cautious_long",
        }

    # Add resources
    server.add_resource(
        MCPResource(
            uri="trading://strategies",
            name="Trading Strategies",
            description="List of available trading strategies",
            mime_type="application/json",
        )
    )

    server.add_resource(
        MCPResource(
            uri="trading://performance",
            name="Performance Metrics",
            description="Current trading performance",
            mime_type="application/json",
        )
    )

    # Add prompts
    server.add_prompt(
        MCPPrompt(
            name="strategy_analysis",
            description="Analyze a trading strategy",
            arguments=[
                {
                    "name": "strategy_name",
                    "description": "Name of strategy",
                    "required": True,
                },
                {
                    "name": "timeframe",
                    "description": "Timeframe for analysis",
                    "required": False,
                },
            ],
        )
    )

    return server


__all__ = [
    "InMemoryTransport",
    "MCPCapabilities",
    "MCPClient",
    "MCPMessage",
    "MCPMessageType",
    "MCPMethod",
    "MCPPrompt",
    "MCPResource",
    "MCPServer",
    "MCPTool",
    "MCPTransport",
    "create_trading_mcp_server",
]
