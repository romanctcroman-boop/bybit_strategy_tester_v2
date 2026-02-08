"""
MCP Tool Registry

Centralized registry for AI agent tools with:
- Automatic schema generation
- Validation
- Usage tracking
- Permission management
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, get_type_hints

from loguru import logger


class ParameterType(Enum):
    """Tool parameter types"""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """Tool parameter definition"""

    name: str
    type: ParameterType
    description: str = ""
    required: bool = True
    default: Any = None
    enum: list[Any] | None = None
    items_type: ParameterType | None = None  # For array types

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema format"""
        schema = {"type": self.type.value}

        if self.description:
            schema["description"] = self.description

        if self.default is not None:
            schema["default"] = self.default

        if self.enum:
            schema["enum"] = self.enum

        if self.type == ParameterType.ARRAY and self.items_type:
            schema["items"] = {"type": self.items_type.value}

        return schema


@dataclass
class ToolResult:
    """Result of tool execution"""

    success: bool
    data: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


@dataclass
class ToolUsageStats:
    """Tool usage statistics"""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_execution_time_ms: float = 0.0
    last_called: datetime | None = None

    @property
    def average_execution_time_ms(self) -> float:
        """Average execution time"""
        if self.total_calls == 0:
            return 0.0
        return self.total_execution_time_ms / self.total_calls

    @property
    def success_rate(self) -> float:
        """Success rate as percentage"""
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100


class ToolPermission(Enum):
    """Tool permission levels"""

    PUBLIC = "public"  # Anyone can use
    AUTHENTICATED = "authenticated"  # Requires auth
    ADMIN = "admin"  # Admin only
    INTERNAL = "internal"  # System only


@dataclass
class Tool:
    """
    Tool definition for AI agents

    Example:
        @Tool.from_function
        async def calculate_rsi(prices: list, period: int = 14):
            '''Calculate RSI indicator'''
            return {"rsi": 50.0}
    """

    name: str
    description: str
    handler: Callable
    parameters: list[ToolParameter] = field(default_factory=list)
    permission: ToolPermission = ToolPermission.PUBLIC
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    version: str = "1.0.0"
    deprecated: bool = False
    stats: ToolUsageStats = field(default_factory=ToolUsageStats)

    def get_input_schema(self) -> dict[str, Any]:
        """Get JSON Schema for tool input"""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        schema = {
            "type": "object",
            "properties": properties,
        }

        if required:
            schema["required"] = required

        return schema

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.get_input_schema(),
            "permission": self.permission.value,
            "category": self.category,
            "tags": self.tags,
            "version": self.version,
            "deprecated": self.deprecated,
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool"""
        import time

        start_time = time.time()

        try:
            # Validate parameters
            for param in self.parameters:
                if param.required and param.name not in kwargs:
                    if param.default is None:
                        raise ValueError(f"Missing required parameter: {param.name}")
                    kwargs[param.name] = param.default

            # Execute handler
            if asyncio.iscoroutinefunction(self.handler):
                result = await self.handler(**kwargs)
            else:
                result = self.handler(**kwargs)

            execution_time = (time.time() - start_time) * 1000

            # Update stats
            self.stats.total_calls += 1
            self.stats.successful_calls += 1
            self.stats.total_execution_time_ms += execution_time
            self.stats.last_called = datetime.now(UTC)

            return ToolResult(
                success=True,
                data=result,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000

            # Update stats
            self.stats.total_calls += 1
            self.stats.failed_calls += 1
            self.stats.total_execution_time_ms += execution_time
            self.stats.last_called = datetime.now(UTC)

            logger.error(f"Tool execution failed: {self.name} - {e}")

            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
            )

    @classmethod
    def from_function(
        cls,
        func: Callable | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        permission: ToolPermission = ToolPermission.PUBLIC,
        category: str = "general",
        tags: list[str] | None = None,
    ):
        """Create Tool from function with automatic schema generation"""

        def decorator(fn: Callable) -> Tool:
            tool_name = name or fn.__name__
            tool_desc = description or fn.__doc__ or f"Tool: {tool_name}"

            # Extract parameters from signature
            sig = inspect.signature(fn)
            type_hints = get_type_hints(fn) if hasattr(fn, "__annotations__") else {}

            parameters = []
            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue

                # Determine type
                param_type = ParameterType.STRING
                hint = type_hints.get(param_name)

                if hint:
                    if hint is int:
                        param_type = ParameterType.INTEGER
                    elif hint is float:
                        param_type = ParameterType.NUMBER
                    elif hint is bool:
                        param_type = ParameterType.BOOLEAN
                    elif hint is list or (hasattr(hint, "__origin__") and hint.__origin__ is list):
                        param_type = ParameterType.ARRAY
                    elif hint is dict or (hasattr(hint, "__origin__") and hint.__origin__ is dict):
                        param_type = ParameterType.OBJECT

                parameters.append(
                    ToolParameter(
                        name=param_name,
                        type=param_type,
                        required=param.default == inspect.Parameter.empty,
                        default=None if param.default == inspect.Parameter.empty else param.default,
                    )
                )

            return cls(
                name=tool_name,
                description=tool_desc.strip(),
                handler=fn,
                parameters=parameters,
                permission=permission,
                category=category,
                tags=tags or [],
            )

        if func is not None:
            return decorator(func)
        return decorator


class ToolRegistry:
    """
    Centralized tool registry for AI agents

    Features:
    - Tool registration and discovery
    - Category-based organization
    - Usage tracking
    - Permission management

    Example:
        registry = ToolRegistry()

        @registry.register(category="trading")
        async def calculate_rsi(prices: list, period: int = 14):
            '''Calculate RSI indicator'''
            return {"rsi": 50.0}

        tools = registry.list_tools(category="trading")
        result = await registry.execute("calculate_rsi", prices=[100, 101, 102])
    """

    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self._categories: dict[str, list[str]] = {}  # category -> tool names

        logger.info("🔧 ToolRegistry initialized")

    def register(
        self,
        func: Callable | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        permission: ToolPermission = ToolPermission.PUBLIC,
        category: str = "general",
        tags: list[str] | None = None,
    ) -> Callable:
        """Register a tool"""

        def decorator(fn: Callable) -> Callable:
            tool = Tool.from_function(
                fn,
                name=name,
                description=description,
                permission=permission,
                category=category,
                tags=tags,
            )

            self.add_tool(tool)
            return fn

        if func is not None:
            return decorator(func)
        return decorator

    def add_tool(self, tool: Tool) -> None:
        """Add a tool to registry"""
        if tool.name in self.tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")

        self.tools[tool.name] = tool

        # Update category index
        if tool.category not in self._categories:
            self._categories[tool.category] = []
        if tool.name not in self._categories[tool.category]:
            self._categories[tool.category].append(tool.name)

        logger.debug(f"🔧 Registered tool: {tool.name} [{tool.category}]")

    def get_tool(self, name: str) -> Tool | None:
        """Get tool by name"""
        return self.tools.get(name)

    def list_tools(
        self,
        category: str | None = None,
        permission: ToolPermission | None = None,
        include_deprecated: bool = False,
    ) -> list[Tool]:
        """List tools with optional filters"""
        tools = list(self.tools.values())

        if category:
            tools = [t for t in tools if t.category == category]

        if permission:
            tools = [t for t in tools if t.permission == permission]

        if not include_deprecated:
            tools = [t for t in tools if not t.deprecated]

        return tools

    def list_categories(self) -> list[str]:
        """List all categories"""
        return list(self._categories.keys())

    async def execute(
        self,
        tool_name: str,
        **kwargs,
    ) -> ToolResult:
        """Execute a tool by name"""
        tool = self.get_tool(tool_name)

        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}",
            )

        if tool.deprecated:
            logger.warning(f"Using deprecated tool: {tool_name}")

        return await tool.execute(**kwargs)

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics"""
        total_calls = sum(t.stats.total_calls for t in self.tools.values())
        successful_calls = sum(t.stats.successful_calls for t in self.tools.values())

        return {
            "total_tools": len(self.tools),
            "categories": len(self._categories),
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "success_rate": (successful_calls / total_calls * 100) if total_calls > 0 else 0.0,
            "by_category": {cat: len(tools) for cat, tools in self._categories.items()},
        }

    def export_schema(self) -> dict[str, Any]:
        """Export all tools as OpenAPI schema"""
        return {
            "tools": [tool.to_dict() for tool in self.tools.values()],
            "categories": self._categories,
            "stats": self.get_stats(),
        }


# Global registry instance
_global_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get global tool registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


# Convenience decorators
def tool(
    name: str | None = None,
    description: str | None = None,
    category: str = "general",
    tags: list[str] | None = None,
) -> Callable:
    """Decorator to register tool in global registry"""
    registry = get_tool_registry()
    return registry.register(
        name=name,
        description=description,
        category=category,
        tags=tags,
    )


__all__ = [
    "ParameterType",
    "Tool",
    "ToolParameter",
    "ToolPermission",
    "ToolRegistry",
    "ToolResult",
    "ToolUsageStats",
    "get_tool_registry",
    "tool",
]
