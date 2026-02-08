"""
Model Context Protocol (MCP) Integration

Implements Anthropic's MCP standard for AI agent tool integration:
- Tool discovery and registration
- Universal interoperability
- Context propagation
- Resource management
"""

from .context_manager import (
    Context,
    ContextManager,
    ContextScope,
)
from .protocol import (
    MCPClient,
    MCPMessage,
    MCPPrompt,
    MCPResource,
    MCPServer,
    MCPTool,
)
from .resource_manager import (
    Resource,
    ResourceManager,
    ResourceType,
)
from .tool_registry import (
    Tool,
    ToolParameter,
    ToolRegistry,
    ToolResult,
)

__all__ = [
    # Protocol
    "MCPServer",
    "MCPClient",
    "MCPMessage",
    "MCPTool",
    "MCPResource",
    "MCPPrompt",
    # Tools
    "ToolRegistry",
    "Tool",
    "ToolParameter",
    "ToolResult",
    # Resources
    "ResourceManager",
    "Resource",
    "ResourceType",
    # Context
    "ContextManager",
    "Context",
    "ContextScope",
]
