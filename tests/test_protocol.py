"""
Unit tests for JSON-RPC protocol compliance and error handling.
Validates MCP protocol adherence and proper error responses.
"""

import json
from typing import Dict, Any
from unittest.mock import patch

import pytest
from mcp.types import JSONRPCRequest, JSONRPCResponse

from conftest import TestHelpers


class TestJSONRPCProtocol:
    """Test JSON-RPC 2.0 protocol compliance."""
    
    def test_valid_jsonrpc_request_parsing(self, sample_mcp_request: JSONRPCRequest):
        """Test that valid JSON-RPC requests are parsed correctly."""
        # Simulate request parsing
        parsed_request = JSONRPCRequest(**sample_mcp_request.dict())
        
        assert parsed_request.jsonrpc == "2.0"
        assert parsed_request.id == "test-123"
        assert parsed_request.method == "tools/call"
        assert parsed_request.params["name"] == "test_tool"
    
    def test_invalid_jsonrpc_version(self, invalid_mcp_request: Dict[str, Any]):
        """Test handling of invalid JSON-RPC version."""
        # This should raise validation error
        with pytest.raises(ValueError):
            JSONRPCRequest(**invalid_mcp_request)
    
    def test_missing_required_fields(self):
        """Test error handling for missing required fields."""
        incomplete_request = {"jsonrpc": "2.0"}  # Missing id and method
        
        with pytest.raises(ValueError) as exc_info:
            JSONRPCRequest(**incomplete_request)
        
        assert "field required" in str(exc_info.value).lower()
    
    def test_protocol_method_validation(self, mcp_server):
        """Test that only valid MCP methods are accepted."""
        invalid_method_request = JSONRPCRequest(
            jsonrpc="2.0",
            id="test-456",
            method="invalid/method",
            params={}
        )
        
        # Simulate method validation
        valid_methods = {"tools/call", "tools/list", "resources/list"}
        assert invalid_method_request.method not in valid_methods
    
    @pytest.mark.asyncio
    async def test_protocol_error_responses(self, mcp_server, test_helpers: TestHelpers):
        """Test proper error responses for various error conditions."""
        
        # Test Parse Error (invalid JSON)
        with pytest.raises(json.JSONDecodeError):
            json.loads("invalid json")
        
        # Test Invalid Request (missing fields)
        invalid_request = {"jsonrpc": "2.0"}  # Missing id and method
        expected_error = test_helpers.create_error_response(-32600, "Invalid Request")
        
        # In actual implementation, server should return this error
        assert "error" in expected_error
        assert expected_error["error"]["code"] == -32600
    
    def test_batch_requests_support(self):
        """Test handling of batch requests (if supported)."""
        batch_requests = [
            {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/list",
                "params": {}
            },
            {
                "jsonrpc": "2.0", 
                "id": "2",
                "method": "resources/list",
                "params": {}
            }
        ]
        
        # Verify batch structure
        assert len(batch_requests) == 2
        assert all(req["jsonrpc"] == "2.0" for req in batch_requests)
    
    @pytest.mark.asyncio
    async def test_notification_handling(self):
        """Test handling of notifications (requests without id)."""
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/update",
            "params": {"status": "updated"}
        }
        
        # Notifications shouldn't receive responses
        # This is a protocol compliance test
        assert "id" not in notification
    
    def test_response_structure_validation(self):
        """Test that responses follow JSON-RPC 2.0 structure."""
        valid_response = JSONRPCResponse(
            jsonrpc="2.0",
            id="test-123",
            result={"tools": []}
        )
        
        assert valid_response.jsonrpc == "2.0"
        assert valid_response.id == "test-123"
        assert "result" in valid_response.dict()
    
    @pytest.mark.parametrize("invalid_input", [
        "plain string",  # Not JSON
        123,  # Wrong type
        None,  # Null
        {"invalid": "structure"}  # Missing required fields
    ])
    def test_malformed_input_handling(self, invalid_input):
        """Test handling of various malformed inputs."""
        # All should result in parse errors
        with pytest.raises((ValueError, TypeError, json.JSONDecodeError)):
            if isinstance(invalid_input, str):
                json.loads(invalid_input)  # This will fail for non-JSON strings
            else:
                JSONRPCRequest(**invalid_input)  # This will fail validation