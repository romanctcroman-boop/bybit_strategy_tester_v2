"""
Pytest configuration and shared fixtures for MCP server testing.
Provides mock configurations, test utilities, and common fixtures.
"""

import asyncio
import json
import os
from typing import AsyncGenerator, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from prometheus_client import CollectorRegistry

# from mcp.server import MCPServer
# from mcp.types import JSONRPCRequest, Tool
# from deepseek_tools import DeepSeekClient


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_registry() -> CollectorRegistry:
    """Provide a clean Prometheus registry for each test."""
    return CollectorRegistry()


@pytest.fixture
def mock_deepseek_client() -> AsyncMock:
    """Mock DeepSeek API client to avoid external calls."""
    mock_client = AsyncMock(spec=DeepSeekClient)
    
    # Mock successful responses
    mock_client.chat_completion.return_value = {
        "choices": [{"message": {"content": "Mocked response"}}]
    }
    mock_client.embeddings.return_value = {
        "data": [{"embedding": [0.1, 0.2, 0.3]}]
    }
    mock_client.image_analysis.return_value = {
        "analysis": "Mocked image analysis"
    }
    mock_client.file_processing.return_value = {
        "content": "Mocked file content"
    }
    mock_client.web_search.return_value = {
        "results": ["Mocked search result 1", "Mocked search result 2"]
    }
    mock_client.code_generation.return_value = {
        "code": "def mocked_function(): pass"
    }
    
    # Mock error responses
    mock_client.chat_completion.side_effect = None  # Clear side effect for normal use
    
    return mock_client


@pytest.fixture
def mock_perplexity_client() -> AsyncMock:
    """Mock Perplexity API client."""
    mock_client = AsyncMock()
    mock_client.search.return_value = {
        "results": [{"title": "Mocked result", "snippet": "Mocked content"}]
    }
    return mock_client


# @pytest.fixture
# def sample_mcp_request() -> JSONRPCRequest:
#     """Provide a sample valid MCP request."""
#     return JSONRPCRequest(
#         jsonrpc="2.0",
#         id="test-123",
#         method="tools/call",
#         params={
#             "name": "test_tool",
#             "arguments": {"query": "test query"}
#         }
#     )


# @pytest.fixture
# def invalid_mcp_request() -> Dict[str, Any]:
#     """Provide an invalid MCP request for error testing."""
#     return {
#         "jsonrpc": "1.0",  # Invalid version
#         "id": 123,  # Invalid ID type
#         "method": "invalid_method"
#     }


# @pytest.fixture
# def deepseek_tools() -> Dict[str, Tool]:
#     """Define all DeepSeek MCP tools for testing."""
#     pass
#     # return {
#     #     "deepseek_chat": Tool(
#     #         name="deepseek_chat",
#     #         description="Chat completion with DeepSeek",
#     #         inputSchema={
#     #             "type": "object",
#     #             "properties": {
#     #                 "message": {"type": "string"},
#                     "temperature": {"type": "number", "minimum": 0, "maximum": 1}
#                 },
#                 "required": ["message"]
#             }
#         ),
#         "deepseek_embeddings": Tool(
#             name="deepseek_embeddings",
#             description="Generate embeddings with DeepSeek",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "text": {"type": "string"}
#                 },
#                 "required": ["text"]
#             }
#         ),
#         "deepseek_image_analysis": Tool(
#             name="deepseek_image_analysis",
#             description="Analyze images with DeepSeek",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "image_url": {"type": "string"},
#                     "analysis_type": {"type": "string", "enum": ["objects", "text", "all"]}
#                 },
#                 "required": ["image_url"]
#             }
#         ),
#         "deepseek_file_process": Tool(
#             name="deepseek_file_process",
#             description="Process files with DeepSeek",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "file_path": {"type": "string"},
#                     "operation": {"type": "string", "enum": ["summarize", "extract", "analyze"]}
#                 },
#                 "required": ["file_path"]
#             }
#         ),
#         "deepseek_web_search": Tool(
#             name="deepseek_web_search",
#             description="Web search with DeepSeek",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "query": {"type": "string"},
#                     "max_results": {"type": "integer", "minimum": 1, "maximum": 10}
#                 },
#                 "required": ["query"]
#             }
#         ),
#         "deepseek_code_generation": Tool(
#             name="deepseek_code_generation",
#             description="Code generation with DeepSeek",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "prompt": {"type": "string"},
#                     "language": {"type": "string"},
#                     "complexity": {"type": "string", "enum": ["simple", "medium", "complex"]}
#                 },
#                 "required": ["prompt"]
#             }
#         )
#     }


# @pytest.fixture
# @patch('deepseek_tools.DeepSeekClient')
# def mcp_server(mock_client_class, mock_deepseek_client) -> MCPServer:
#     """Create MCP server instance with mocked dependencies."""
#     mock_client_class.return_value = mock_deepseek_client
#     server = MCPServer("test-server")
#     return server


class TestHelpers:
    """Utility functions for testing."""
    
    @staticmethod
    def assert_metrics_exist(registry: CollectorRegistry, metric_names: list[str]) -> None:
        """Verify that expected metrics exist in the registry."""
        for metric_name in metric_names:
            assert metric_name in [m.name for m in registry.collect()], f"Metric {metric_name} not found"
    
    @staticmethod
    def create_error_response(error_code: int, message: str) -> Dict[str, Any]:
        """Create standardized error response."""
        return {
            "jsonrpc": "2.0",
            "id": "test",
            "error": {
                "code": error_code,
                "message": message
            }
        }


@pytest.fixture
def test_helpers() -> TestHelpers:
    """Provide test helper utilities."""
    return TestHelpers()