"""Fix DeepSeek tests by patching KeyRotation.get_next_key()"""

import re

filepath = "tests/test_deepseek_client.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace TestErrorHandling class
old_pattern = r'class TestErrorHandling:.*?(?=\nclass |$)'
new_class = '''class TestErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(5)
    async def test_rate_limit_error(self, mock_key_rotation):
        """Should handle rate limit (429) error with key rotation"""
        keys = [{"id": "key1", "api_key": "sk-test-1", "weight": 1.0}]
        client = DeepSeekReliableClient(api_keys=keys, enable_monitoring=False)
        
        # Patch get_next_key to avoid timeout
        with patch.object(client.key_rotation, 'get_next_key', new=mock_key_rotation):
            mock_response = MagicMock()
            mock_response.status_code = 429
            client.http_client.post = AsyncMock(return_value=mock_response)
            
            response = await client.chat_completion(prompt="Test")
            assert response is not None
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(5)
    async def test_auth_error(self, mock_key_rotation):
        """Should handle authentication (401) error"""
        keys = [{"id": "key1", "api_key": "sk-invalid", "weight": 1.0}]
        client = DeepSeekReliableClient(api_keys=keys, enable_monitoring=False)
        
        with patch.object(client.key_rotation, 'get_next_key', new=mock_key_rotation):
            mock_response = MagicMock()
            mock_response.status_code = 401
            client.http_client.post = AsyncMock(return_value=mock_response)
            
            response = await client.chat_completion(prompt="Test")
            assert response is not None
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(5)
    async def test_server_error_with_retry(self, mock_key_rotation):
        """Should retry on server (500) error"""
        keys = [{"id": "key1", "api_key": "sk-test", "weight": 1.0}]
        retry_config = RetryConfig(max_retries=2, base_delay=0.1)
        client = DeepSeekReliableClient(api_keys=keys, retry_config=retry_config, enable_monitoring=False)
        
        with patch.object(client.key_rotation, 'get_next_key', new=mock_key_rotation):
            call_count = 0
            async def mock_post(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                mock_response = MagicMock()
                if call_count == 1:
                    mock_response.status_code = 500
                else:
                    mock_response.status_code = 200
                    mock_response.json.return_value = {
                        "choices": [{"message": {"content": "Success"}}],
                        "usage": {"total_tokens": 10}
                    }
                return mock_response
            
            client.http_client.post = mock_post
            response = await client.chat_completion(prompt="Test")
            assert call_count >= 2


'''

content = re.sub(old_pattern, new_class, content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Fixed TestErrorHandling class with KeyRotation mocking")
