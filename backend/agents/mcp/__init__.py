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
    "Context",
    # Context
    "ContextManager",
    "ContextScope",
    "MCPClient",
    "MCPMessage",
    "MCPPrompt",
    "MCPResource",
    # Protocol
    "MCPServer",
    "MCPTool",
    "Resource",
    # Resources
    "ResourceManager",
    "ResourceType",
    "Tool",
    "ToolParameter",
    # Tools
    "ToolRegistry",
    "ToolResult",
]
