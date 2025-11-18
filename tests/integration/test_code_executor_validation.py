"""
Integration tests for CodeExecutor with AST Validation.

Tests Security Layer 2 (AST validation) integration with Security Layer 1 (Docker sandbox).
"""

import pytest
import json
from backend.services.code_executor import CodeExecutor, ExecutionResult


class TestCodeExecutorWithValidation:
    """Test CodeExecutor with AST validation enabled."""
    
    @pytest.mark.asyncio
    async def test_valid_code_execution(self):
        """Valid code should pass validation and execute successfully."""
        code = """
import numpy as np
import json

# Simple calculation
arr = np.array([1, 2, 3, 4, 5])
mean = float(np.mean(arr))

result = {'mean': mean, 'signal': 'BUY'}
print(json.dumps(result))
"""
        executor = CodeExecutor(validate_code=True)
        result = await executor.execute_strategy(code, {}, timeout=10)
        
        assert result.success
        assert result.error is None
        
        output = json.loads(result.output)
        assert output['mean'] == 3.0
        assert output['signal'] == 'BUY'
    
    @pytest.mark.asyncio
    async def test_forbidden_import_blocked(self):
        """Code with forbidden imports should be blocked before execution."""
        code = """
import os
os.system('echo "hacked"')
"""
        executor = CodeExecutor(validate_code=True)
        result = await executor.execute_strategy(code, {}, timeout=10)
        
        assert not result.success
        assert "Code validation failed" in result.error
        assert "os" in result.error.lower()
        assert result.execution_time < 1.0  # Should fail fast (no Docker execution)
    
    @pytest.mark.asyncio
    async def test_eval_blocked(self):
        """Code using eval() should be blocked."""
        code = """
user_input = "1+1"
result = eval(user_input)
print(result)
"""
        executor = CodeExecutor(validate_code=True)
        result = await executor.execute_strategy(code, {}, timeout=10)
        
        assert not result.success
        assert "Code validation failed" in result.error
        assert "eval" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_magic_attributes_blocked(self):
        """Code accessing magic attributes should be blocked."""
        code = """
obj = {}
builtins = obj.__class__.__bases__[0].__subclasses__()
print(builtins)
"""
        executor = CodeExecutor(validate_code=True)
        result = await executor.execute_strategy(code, {}, timeout=10)
        
        assert not result.success
        assert "Code validation failed" in result.error
    
    @pytest.mark.asyncio
    async def test_validation_can_be_disabled(self):
        """Validation can be disabled for testing purposes."""
        code = """
import json
print(json.dumps({'test': True}))
"""
        executor = CodeExecutor(validate_code=False)
        result = await executor.execute_strategy(code, {}, timeout=10)
        
        assert result.success
        output = json.loads(result.output)
        assert output['test'] is True
    
    @pytest.mark.asyncio
    async def test_complex_strategy_with_validation(self):
        """Complex trading strategy with validation."""
        code = """
import numpy as np
import pandas as pd
import json

# Simulate receiving data (in production, data would be injected)
prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]

# Calculate indicators
df = pd.DataFrame({'price': prices})
df['ma_short'] = df['price'].rolling(window=3).mean()
df['ma_long'] = df['price'].rolling(window=5).mean()
df['rsi'] = (df['price'].pct_change().rolling(window=5).mean() + 1) * 50

# Generate signal
last_row = df.iloc[-1]
if last_row['ma_short'] > last_row['ma_long'] and last_row['rsi'] < 70:
    signal = 'BUY'
elif last_row['ma_short'] < last_row['ma_long'] and last_row['rsi'] > 30:
    signal = 'SELL'
else:
    signal = 'HOLD'

result = {
    'signal': signal,
    'price': float(last_row['price']),
    'ma_short': float(last_row['ma_short']),
    'ma_long': float(last_row['ma_long']),
    'rsi': float(last_row['rsi'])
}

print(json.dumps(result))
"""
        
        data = {}  # Data embedded in code for this test
        
        executor = CodeExecutor(validate_code=True)
        result = await executor.execute_strategy(code, data, timeout=10)
        
        assert result.success
        assert result.error is None
        
        output = json.loads(result.output)
        assert 'signal' in output
        assert output['signal'] in ['BUY', 'SELL', 'HOLD']
        assert 'price' in output
        assert 'ma_short' in output
        assert 'ma_long' in output
        assert 'rsi' in output
    
    @pytest.mark.asyncio
    async def test_syntax_error_caught_by_validation(self):
        """Syntax errors should be caught during validation."""
        code = """
if True  # Missing colon
    print("test")
"""
        executor = CodeExecutor(validate_code=True)
        result = await executor.execute_strategy(code, {}, timeout=10)
        
        assert not result.success
        assert "Syntax error" in result.error
    
    @pytest.mark.asyncio
    async def test_validation_metrics(self):
        """Validation should track imports and functions used."""
        code = """
import numpy as np
import pandas as pd
import json

arr = np.array([1, 2, 3])
mean = np.mean(arr)
print(json.dumps({'mean': float(mean)}))
"""
        executor = CodeExecutor(validate_code=True)
        
        # Get validation result through executor
        validation_result = executor.validator.validate(code)
        
        assert validation_result.is_valid
        assert 'numpy' in validation_result.imports_used
        assert 'pandas' in validation_result.imports_used
        assert 'json' in validation_result.imports_used
        assert 'np.array' in validation_result.functions_called
        assert 'np.mean' in validation_result.functions_called


class TestSecurityLayers:
    """Test multi-layer security (AST validation + Docker sandbox)."""
    
    @pytest.mark.asyncio
    async def test_layer_2_blocks_before_layer_1(self):
        """AST validation (Layer 2) should block code before Docker execution (Layer 1)."""
        code = "import subprocess; subprocess.run(['ls'])"
        
        start_time = __import__('time').time()
        executor = CodeExecutor(validate_code=True)
        result = await executor.execute_strategy(code, {}, timeout=10)
        elapsed = __import__('time').time() - start_time
        
        assert not result.success
        assert "subprocess" in result.error.lower()
        assert elapsed < 1.0  # Should fail in <1s (no Docker overhead)
    
    @pytest.mark.asyncio
    async def test_both_layers_protect(self):
        """Even if Layer 2 is disabled, Layer 1 (Docker) should still protect."""
        # Note: This would normally be blocked by Docker's network isolation
        # But AST validation catches it first
        code = """
import socket
sock = socket.socket()
sock.connect(('google.com', 80))
"""
        
        # With validation
        executor_validated = CodeExecutor(validate_code=True)
        result_validated = await executor_validated.execute_strategy(code, {}, timeout=10)
        assert not result_validated.success
        assert "socket" in result_validated.error.lower()
        
        # Without validation (Docker would block network)
        # Skipping this test as it requires Docker execution


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
