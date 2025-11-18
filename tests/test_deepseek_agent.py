"""
Tests for DeepSeek Code Generation Agent
=========================================

Test Coverage:
- ✅ Agent initialization and configuration
- ✅ API connection and disconnection
- ✅ Rate limiting
- ✅ Code generation
- ✅ Code cleaning (markdown removal)
- ✅ Code testing (syntax, imports)
- ✅ Auto-fix mechanism
- ✅ Complete strategy generation workflow
- ✅ Error handling and retries
- ✅ Token counting

Week 3 Day 4
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from backend.agents import (
    DeepSeekAgent,
    DeepSeekConfig,
    CodeGenerationStatus,
    GenerationResult,
    DeepSeekModel
)


@pytest.fixture
def config(monkeypatch):
    """Test configuration"""
    # Prevent reading .env file in tests
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-123")
    return DeepSeekConfig(
        max_tokens=1000,
        max_retries=2,
        retry_delay=0.1,
        max_fix_iterations=2,
        requests_per_minute=100
    )


@pytest.fixture
async def agent(config):
    """Create DeepSeekAgent for testing"""
    agent = DeepSeekAgent(config)
    yield agent
    if agent._session:
        await agent.disconnect()


@pytest.mark.asyncio
async def test_agent_initialization(config):
    """Test 1: Agent initialization"""
    agent = DeepSeekAgent(config)
    
    assert agent.config.api_key == "test-key-123"
    assert agent.config.max_tokens == 1000
    assert agent.config.model == DeepSeekModel.CODER
    assert agent._session is None


@pytest.mark.asyncio
async def test_agent_connect_disconnect(agent):
    """Test 2: Connect and disconnect"""
    # Connect
    await agent.connect()
    assert agent._session is not None
    
    # Disconnect
    await agent.disconnect()
    assert agent._session is None


@pytest.mark.asyncio
async def test_context_manager(config):
    """Test 3: Async context manager"""
    async with DeepSeekAgent(config) as agent:
        assert agent._session is not None
    
    # Should auto-disconnect
    assert agent._session is None


@pytest.mark.asyncio
async def test_rate_limiting(agent):
    """Test 4: Rate limiting enforcement"""
    import time
    
    # Add many requests
    now = time.time()
    agent._request_times = [now - i for i in range(90)]  # 90 requests in last minute
    agent.config.requests_per_minute = 50
    
    # Should trigger rate limit
    start = time.time()
    await agent._rate_limit()
    elapsed = time.time() - start
    
    # Should have waited (mocked sleep in real test)
    assert len(agent._request_times) <= agent.config.requests_per_minute


@pytest.mark.asyncio
async def test_clean_code():
    """Test 5: Code cleaning (remove markdown)"""
    agent = DeepSeekAgent()
    
    # Test with markdown code block
    code_with_markdown = """```python
def hello():
    print("world")
```"""
    
    cleaned = agent._clean_code(code_with_markdown)
    assert "```" not in cleaned
    assert "def hello():" in cleaned
    
    # Test without markdown
    plain_code = """def hello():
    print("world")"""
    
    cleaned = agent._clean_code(plain_code)
    assert cleaned == plain_code.strip()


@pytest.mark.asyncio
async def test_test_code_valid():
    """Test 6: Testing valid code"""
    agent = DeepSeekAgent()
    
    valid_code = """
import pandas as pd

def calculate_ema(data, period):
    return data.ewm(span=period).mean()
"""
    
    result = await agent.test_code(valid_code)
    
    assert result["syntax_valid"] is True
    assert result["imports_valid"] is True
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_test_code_syntax_error():
    """Test 7: Testing code with syntax error"""
    agent = DeepSeekAgent()
    
    invalid_code = """
def broken_function(
    # Missing closing parenthesis
    print("hello")
"""
    
    result = await agent.test_code(invalid_code)
    
    assert result["syntax_valid"] is False
    assert len(result["errors"]) > 0
    assert "syntax" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_test_code_import_error():
    """Test 8: Testing code with import error"""
    agent = DeepSeekAgent()
    
    code_with_bad_import = """
import nonexistent_module_xyz

def test():
    pass
"""
    
    result = await agent.test_code(code_with_bad_import)
    
    assert result["syntax_valid"] is True
    assert result["imports_valid"] is False
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_generate_code_mocked(agent):
    """Test 9: Code generation with mocked API"""
    mock_response = {
        "choices": [{"message": {"content": "def strategy(): pass"}}],
        "usage": {"total_tokens": 100}
    }
    
    with patch.object(agent, '_call_api', return_value=mock_response):
        code, tokens = await agent.generate_code("Create a simple strategy")
        
        assert "def strategy():" in code
        assert tokens == 100


@pytest.mark.asyncio
async def test_fix_code_mocked(agent):
    """Test 10: Code fixing with mocked API"""
    original_code = "def broken("
    error = "Syntax error"
    
    mock_response = {
        "choices": [{"message": {"content": "def fixed(): pass"}}],
        "usage": {"total_tokens": 150}
    }
    
    with patch.object(agent, '_call_api', return_value=mock_response):
        fixed_code, tokens = await agent.fix_code(
            original_code, error, "test prompt"
        )
        
        assert "def fixed():" in fixed_code
        assert tokens == 150


@pytest.mark.asyncio
async def test_generate_strategy_success(agent):
    """Test 11: Complete strategy generation (success path)"""
    mock_code = """
import pandas as pd

def ema_crossover_strategy(data):
    data['ema20'] = data['close'].ewm(span=20).mean()
    data['ema50'] = data['close'].ewm(span=50).mean()
    return data
"""
    
    mock_api_response = {
        "choices": [{"message": {"content": mock_code}}],
        "usage": {"total_tokens": 200}
    }
    
    with patch.object(agent, '_call_api', return_value=mock_api_response):
        result = await agent.generate_strategy(
            prompt="Create EMA crossover strategy",
            context={"symbol": "BTCUSDT"}
        )
        
        assert result.status == CodeGenerationStatus.COMPLETED
        assert result.code is not None
        assert "ema_crossover" in result.code
        assert result.tokens_used == 200
        assert result.iterations == 1
        assert result.error is None


@pytest.mark.asyncio
async def test_generate_strategy_with_auto_fix(agent):
    """Test 12: Strategy generation with auto-fix"""
    # First generation has syntax error
    broken_code = "def strategy(:"
    
    # Fixed code
    fixed_code = """
def strategy(data):
    return data
"""
    
    call_count = [0]
    
    async def mock_call_api(messages, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: generate broken code
            return {
                "choices": [{"message": {"content": broken_code}}],
                "usage": {"total_tokens": 50}
            }
        else:
            # Second call: fix code
            return {
                "choices": [{"message": {"content": fixed_code}}],
                "usage": {"total_tokens": 75}
            }
    
    with patch.object(agent, '_call_api', side_effect=mock_call_api):
        result = await agent.generate_strategy(
            prompt="Create strategy",
            enable_auto_fix=True
        )
        
        # Should succeed after auto-fix
        assert result.status == CodeGenerationStatus.COMPLETED
        assert result.iterations == 2  # Generate + fix
        assert result.tokens_used == 125  # 50 + 75
        assert "def strategy(data):" in result.code


@pytest.mark.asyncio
async def test_generate_strategy_max_iterations(agent):
    """Test 13: Auto-fix max iterations"""
    broken_code = "def broken(:"
    
    async def mock_call_api_always_broken(messages, **kwargs):
        return {
            "choices": [{"message": {"content": broken_code}}],
            "usage": {"total_tokens": 50}
        }
    
    with patch.object(agent, '_call_api', side_effect=mock_call_api_always_broken):
        result = await agent.generate_strategy(
            prompt="Create strategy",
            enable_auto_fix=True
        )
        
        # Should fail after max iterations
        assert result.status == CodeGenerationStatus.FAILED
        # iterations = 1 (initial generate) + (max_fix_iterations - 1) fix attempts
        assert result.iterations == agent.config.max_fix_iterations
        assert result.error is not None
        assert "Failed to fix" in result.error


@pytest.mark.asyncio
async def test_api_retry_logic(agent):
    """Test 14: API retry on failure - properly mocking session.post as context manager"""
    await agent.connect()  # Create session first
    
    # Create mock response for successful API call
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "choices": [{"message": {"content": "success after retry"}}],
        "usage": {"total_tokens": 150}
    })
    
    # Create mock context manager for success case
    mock_post_success = AsyncMock()
    mock_post_success.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_success.__aexit__ = AsyncMock(return_value=None)
    
    # Configure side_effect: fail first time, succeed second time
    # This tests that the retry loop inside _call_api works correctly
    call_count = [0]
    
    def mock_post_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: raise exception to trigger retry
            raise Exception("Temporary network failure")
        else:
            # Second call: return successful response
            return mock_post_success
    
    agent._session.post = MagicMock(side_effect=mock_post_side_effect)
    
    # Generate code - should retry and succeed
    code, tokens = await agent.generate_code("test prompt")
    
    # Verify the result
    assert code == "success after retry"
    assert tokens == 150
    
    # Verify session.post was called twice (1 failure + 1 success)
    assert agent._session.post.call_count == 2
    assert call_count[0] == 2
    
    # Verify both calls had correct URL
    for call in agent._session.post.call_args_list:
        assert call[0][0] == agent.config.api_url  # URL is first positional arg


@pytest.mark.asyncio
async def test_generate_strategy_without_auto_fix(agent):
    """Test 15: Generation without auto-fix"""
    broken_code = "def broken(:"
    
    mock_response = {
        "choices": [{"message": {"content": broken_code}}],
        "usage": {"total_tokens": 50}
    }
    
    with patch.object(agent, '_call_api', return_value=mock_response):
        result = await agent.generate_strategy(
            prompt="Create strategy",
            enable_auto_fix=False
        )
        
        # Should complete even with broken code (no testing)
        assert result.status == CodeGenerationStatus.COMPLETED
        assert result.code == broken_code
        assert result.iterations == 1


# Integration test (requires real API key, skip by default)
@pytest.mark.skip(reason="Requires real DeepSeek API key")
@pytest.mark.asyncio
async def test_real_api_integration():
    """Test 16: Real API integration (manual test)"""
    config = DeepSeekConfig()  # Loads from .env
    
    async with DeepSeekAgent(config) as agent:
        result = await agent.generate_strategy(
            prompt="Create a simple moving average crossover strategy",
            context={"symbol": "BTCUSDT", "timeframe": "1h"}
        )
        
        assert result.status == CodeGenerationStatus.COMPLETED
        assert result.code is not None
        assert len(result.code) > 100
        print(f"\n{'='*60}")
        print(f"Generated code ({result.tokens_used} tokens):")
        print(f"{'='*60}")
        print(result.code)
        print(f"{'='*60}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
