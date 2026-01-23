"""
Model Context Protocol (MCP) Integration

Implements Anthropic's MCP standard for AI agent tool integration:
- Tool discovery and registration
- Universal interoperability
- Context propagation
- Resource management
"""

from .protocol import (
    MCPServer,
    MCPClient,
    MCPMessage,
    MCPTool,
    MCPResource,
    MCPPrompt,
)
from .tool_registry import (
    ToolRegistry,
    Tool,
    ToolParameter,
    ToolResult,
)
from .resource_manager import (
    ResourceManager,
    Resource,
    ResourceType,
)
from .context_manager import (
    ContextManager,
    Context,
    ContextScope,
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
