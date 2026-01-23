"""
Unit Tests for MCP Tools.

Tests for the modular MCP tools in backend/api/mcp/tools/.
Covers agent_tools.py and file_tools.py.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def project_root():
    """Get the actual project root for testing."""
    return Path(__file__).parent.parent.parent.parent.parent


@pytest.fixture
def mock_mcp():
    """Create a mock MCP server for testing."""
    class MockMCP:
        def __init__(self):
            self.registered_tools = []
        
        def tool(self):
            def decorator(func):
                self.registered_tools.append(func.__name__)
                return func
            return decorator
    
    return MockMCP()


# ==============================================================================
# File Tools Tests
# ==============================================================================

class TestFileTools:
    """Tests for file_tools.py."""
    
    def test_is_path_safe_valid_path(self, project_root):
        """Test that valid paths are allowed."""
        from backend.api.mcp.tools.file_tools import _is_path_safe
        
        # Valid path within project
        target = project_root / "backend" / "api" / "app.py"
        is_safe, error = _is_path_safe(target, project_root)
        
        assert is_safe is True
        # Error can be None or empty string
        assert error is None or error == ""
    
    def test_is_path_safe_blocked_patterns(self, project_root):
        """Test that blocked patterns (.env, .git, secrets) are rejected."""
        from backend.api.mcp.tools.file_tools import _is_path_safe
        
        blocked_paths = [
            project_root / ".env",
            project_root / ".git" / "config",
            project_root / "secrets" / "api_keys.json",
            project_root / "credentials.json",
            project_root / "private.key",
        ]
        
        for path in blocked_paths:
            is_safe, error = _is_path_safe(path, project_root)
            assert is_safe is False, f"Path {path} should be blocked"
            assert error is not None and error != ""
    
    def test_is_path_safe_path_traversal(self, project_root):
        """Test that path traversal attacks are blocked."""
        from backend.api.mcp.tools.file_tools import _is_path_safe
        
        # Attempt to escape project root
        malicious_path = project_root / ".." / ".." / "etc" / "passwd"
        is_safe, error = _is_path_safe(malicious_path.resolve(), project_root)
        
        assert is_safe is False
        assert error is not None and error != ""
    
    @pytest.mark.asyncio
    async def test_read_project_file_success(self, project_root):
        """Test reading a valid project file."""
        from backend.api.mcp.tools.file_tools import read_project_file
        
        result = await read_project_file("README.md")
        
        assert result["success"] is True
        assert "content" in result
        assert len(result["content"]) > 0
    
    @pytest.mark.asyncio
    async def test_read_project_file_not_found(self):
        """Test reading a non-existent file."""
        from backend.api.mcp.tools.file_tools import read_project_file
        
        result = await read_project_file("nonexistent_file_xyz123.py")
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_read_project_file_blocked(self):
        """Test reading a blocked file (.env)."""
        from backend.api.mcp.tools.file_tools import read_project_file
        
        result = await read_project_file(".env")
        
        assert result["success"] is False
        error_msg = result.get("error", "").lower()
        assert "blocked" in error_msg or "not allowed" in error_msg or "access" in error_msg
    
    @pytest.mark.asyncio
    async def test_list_project_structure_success(self):
        """Test listing project structure."""
        from backend.api.mcp.tools.file_tools import list_project_structure
        
        result = await list_project_structure(directory="backend", max_depth=2)
        
        assert result["success"] is True
        assert "structure" in result
        assert result["structure"]["name"] == "backend"
        assert result["structure"]["type"] == "directory"
    
    @pytest.mark.asyncio
    async def test_list_project_structure_max_depth(self):
        """Test that max_depth is respected."""
        from backend.api.mcp.tools.file_tools import list_project_structure
        
        result = await list_project_structure(directory=".", max_depth=1)
        
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_list_project_structure_hidden_files(self):
        """Test hidden files filtering."""
        from backend.api.mcp.tools.file_tools import list_project_structure
        
        # Without include_hidden
        result_no_hidden = await list_project_structure(directory=".", max_depth=1, include_hidden=False)
        
        # Check that .git is not in the list
        children = result_no_hidden["structure"].get("children", [])
        names = [c["name"] for c in children]
        assert ".git" not in names
    
    def test_register_file_tools(self, mock_mcp):
        """Test that file tools are registered correctly."""
        from backend.api.mcp.tools.file_tools import register_file_tools
        
        register_file_tools(mock_mcp)
        
        assert len(mock_mcp.registered_tools) == 3
        assert "mcp_read_project_file" in mock_mcp.registered_tools
        assert "mcp_list_project_structure" in mock_mcp.registered_tools
        assert "mcp_analyze_code_quality" in mock_mcp.registered_tools


# ==============================================================================
# Agent Tools Tests
# ==============================================================================

class TestAgentTools:
    """Tests for agent_tools.py."""
    
    def test_register_agent_tools(self, mock_mcp):
        """Test that agent tools are registered correctly."""
        from backend.api.mcp.tools.agent_tools import register_agent_tools
        
        register_agent_tools(mock_mcp)
        
        assert len(mock_mcp.registered_tools) == 3
        assert "mcp_agent_to_agent_send_to_deepseek" in mock_mcp.registered_tools
        assert "mcp_agent_to_agent_send_to_perplexity" in mock_mcp.registered_tools
        assert "mcp_agent_to_agent_get_consensus" in mock_mcp.registered_tools
    
    @pytest.mark.asyncio
    async def test_send_to_deepseek_returns_dict(self):
        """Test that send_to_deepseek returns proper dict structure."""
        from backend.api.mcp.tools.agent_tools import send_to_deepseek
        
        # The function should always return a dict, even on failure
        result = await send_to_deepseek("Hello DeepSeek test")
        
        assert isinstance(result, dict)
        assert "success" in result
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Perplexity API key - run manually")
    async def test_send_to_perplexity_returns_dict(self):
        """Test that send_to_perplexity returns proper dict structure."""
        from backend.api.mcp.tools.agent_tools import send_to_perplexity
        
        result = await send_to_perplexity("Hello Perplexity test")
        
        assert isinstance(result, dict)
        assert "success" in result
    
    @pytest.mark.asyncio
    async def test_get_consensus_returns_dict(self):
        """Test get_consensus returns proper structure."""
        from backend.api.mcp.tools.agent_tools import get_consensus
        
        result = await get_consensus("What is 2+2?")
        
        assert isinstance(result, dict)
        assert "success" in result


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestMCPToolsIntegration:
    """Integration tests that verify tools work together."""
    
    def test_all_tools_exported(self):
        """Test that all tools are properly exported."""
        from backend.api.mcp.tools import agent_tools, file_tools
        
        # Check agent_tools exports
        assert hasattr(agent_tools, "send_to_deepseek")
        assert hasattr(agent_tools, "send_to_perplexity")
        assert hasattr(agent_tools, "get_consensus")
        assert hasattr(agent_tools, "register_agent_tools")
        
        # Check file_tools exports
        assert hasattr(file_tools, "read_project_file")
        assert hasattr(file_tools, "list_project_structure")
        assert hasattr(file_tools, "analyze_code_quality")
        assert hasattr(file_tools, "register_file_tools")
    
    def test_blocked_patterns_comprehensive(self):
        """Test that all security-sensitive patterns are blocked."""
        from backend.api.mcp.tools.file_tools import BLOCKED_PATTERNS
        
        # Essential security patterns
        essential_patterns = [".env", ".git", "secrets", "password", ".key"]
        
        for pattern in essential_patterns:
            assert pattern in BLOCKED_PATTERNS, f"'{pattern}' should be in BLOCKED_PATTERNS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
