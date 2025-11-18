"""
Unit tests for AST-based code validator.

Tests Security Layer 2 - code validation before Docker execution.
"""

import pytest
from backend.security.ast_validator import (
    ASTValidator,
    SecurityError,
    ValidationResult,
    validate_code
)


class TestASTValidatorBasics:
    """Test basic validation functionality."""
    
    def test_empty_code(self):
        """Empty code should be valid."""
        validator = ASTValidator()
        result = validator.validate("")
        assert result.is_valid
        assert result.error is None
    
    def test_simple_math(self):
        """Simple math operations should be valid."""
        code = """
x = 1 + 2
y = x * 3
result = y / 2
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_syntax_error(self):
        """Syntax errors should be caught."""
        code = "if True"  # Missing colon
        validator = ASTValidator()
        result = validator.validate(code)
        assert not result.is_valid
        assert "Syntax error" in result.error
    
    def test_validation_result_bool(self):
        """ValidationResult should work in boolean context."""
        result_valid = ValidationResult(is_valid=True)
        result_invalid = ValidationResult(is_valid=False, error="test")
        
        assert result_valid
        assert not result_invalid


class TestImportValidation:
    """Test import statement validation."""
    
    def test_allowed_imports(self):
        """Whitelisted imports should be allowed."""
        allowed_imports = [
            "import numpy",
            "import pandas",
            "import math",
            "import datetime",
            "import json",
            "from numpy import array",
            "from pandas import DataFrame",
            "import numpy as np",
            "import pandas as pd",
        ]
        
        validator = ASTValidator()
        for code in allowed_imports:
            result = validator.validate(code)
            assert result.is_valid, f"Failed for: {code}"
    
    def test_forbidden_imports(self):
        """Forbidden imports should be blocked."""
        forbidden_imports = [
            "import os",
            "import sys",
            "import subprocess",
            "import socket",
            "import requests",
            "import urllib",
            "from os import system",
            "from subprocess import call",
        ]
        
        validator = ASTValidator()
        for code in forbidden_imports:
            result = validator.validate(code)
            assert not result.is_valid, f"Should block: {code}"
            assert "Forbidden module" in result.error
    
    def test_import_tracking(self):
        """Validator should track imports used."""
        code = """
import numpy as np
import pandas as pd
from math import sqrt
"""
        validator = ASTValidator()
        result = validator.validate(code)
        
        assert result.is_valid
        assert "numpy" in result.imports_used
        assert "pandas" in result.imports_used
        assert "math" in result.imports_used


class TestFunctionValidation:
    """Test function call validation."""
    
    def test_allowed_builtins(self):
        """Allowed builtin functions should work."""
        allowed_functions = [
            "print('hello')",
            "len([1, 2, 3])",
            "sum([1, 2, 3])",
            "max(1, 2, 3)",
            "min(1, 2, 3)",
            "range(10)",
            "enumerate([1, 2])",
            "zip([1], [2])",
            "isinstance(1, int)",
            "type(1)",
        ]
        
        validator = ASTValidator()
        for code in allowed_functions:
            result = validator.validate(code)
            assert result.is_valid, f"Failed for: {code}"
    
    def test_forbidden_functions(self):
        """Dangerous functions should be blocked."""
        forbidden_functions = [
            "eval('1+1')",
            "exec('x=1')",
            "compile('x=1', '', 'exec')",
            "__import__('os')",
            "open('file.txt')",
            "input('prompt')",
            "getattr(obj, 'attr')",
            "setattr(obj, 'attr', 1)",
            "globals()",
            "locals()",
        ]
        
        validator = ASTValidator()
        for code in forbidden_functions:
            result = validator.validate(code)
            assert not result.is_valid, f"Should block: {code}"
            assert "Forbidden" in result.error
    
    def test_function_tracking(self):
        """Validator should track function calls."""
        code = """
x = sum([1, 2, 3])
y = max(x, 10)
print(y)
"""
        validator = ASTValidator()
        result = validator.validate(code)
        
        assert result.is_valid
        assert "sum" in result.functions_called
        assert "max" in result.functions_called
        assert "print" in result.functions_called


class TestAttributeValidation:
    """Test attribute access validation."""
    
    def test_normal_attributes(self):
        """Normal attribute access should be allowed."""
        code = """
import numpy as np
arr = np.array([1, 2, 3])
shape = arr.shape
dtype = arr.dtype
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_forbidden_attributes(self):
        """Magic attributes should be blocked."""
        forbidden_attributes = [
            "obj.__class__",
            "obj.__bases__",
            "obj.__subclasses__()",
            "obj.__dict__",
            "obj.__code__",
            "obj.__globals__",
            "obj.__builtins__",
        ]
        
        validator = ASTValidator()
        for code in forbidden_attributes:
            result = validator.validate(code)
            assert not result.is_valid, f"Should block: {code}"
            assert "Forbidden attribute" in result.error
    
    def test_private_attribute_warning(self):
        """Private attributes should generate warnings."""
        code = "obj._private_method()"
        validator = ASTValidator(strict=True)
        result = validator.validate(code)
        
        # Should be valid but have warning
        assert result.is_valid
        assert any("private" in w.lower() for w in result.warnings)


class TestComplexScenarios:
    """Test complex real-world scenarios."""
    
    def test_simple_strategy(self):
        """Simple trading strategy should be valid."""
        code = """
import numpy as np
import pandas as pd
import json

# Calculate indicators
prices = data['close']
ma_short = pd.Series(prices).rolling(window=10).mean()
ma_long = pd.Series(prices).rolling(window=50).mean()

# Generate signal
if ma_short.iloc[-1] > ma_long.iloc[-1]:
    signal = "BUY"
else:
    signal = "SELL"

# Output
print(json.dumps({"signal": signal, "confidence": 0.75}))
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_numpy_pandas_operations(self):
        """Complex numpy/pandas operations should work."""
        code = """
import numpy as np
import pandas as pd

# Numpy operations
arr = np.array([1, 2, 3, 4, 5])
mean = np.mean(arr)
std = np.std(arr)
normalized = (arr - mean) / std

# Pandas operations
df = pd.DataFrame({'price': [100, 101, 102]})
df['returns'] = df['price'].pct_change()
df['ma'] = df['price'].rolling(window=2).mean()
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_malicious_code_attempt_1(self):
        """Attempt to import os and execute commands."""
        code = """
import os
os.system('rm -rf /')
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert not result.is_valid
        assert "os" in result.error.lower()
    
    def test_malicious_code_attempt_2(self):
        """Attempt to use eval for code injection."""
        code = """
user_input = "print('hacked')"
eval(user_input)
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert not result.is_valid
        assert "eval" in result.error.lower()
    
    def test_malicious_code_attempt_3(self):
        """Attempt to access __builtins__ for bypass."""
        code = """
builtins = {}.__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['__builtins__']
builtins['eval']('1+1')
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert not result.is_valid
    
    def test_malicious_code_attempt_4(self):
        """Attempt to open files."""
        code = """
with open('/etc/passwd', 'r') as f:
    secrets = f.read()
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert not result.is_valid
        assert "open" in result.error.lower()
    
    def test_malicious_code_attempt_5(self):
        """Attempt to use __import__ for bypass."""
        code = """
os = __import__('os')
os.system('whoami')
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert not result.is_valid
        assert "__import__" in result.error.lower()


class TestConvenienceFunction:
    """Test the validate_code convenience function."""
    
    def test_validate_code_valid(self):
        """Valid code through convenience function."""
        code = "import numpy as np"
        result = validate_code(code)
        assert result.is_valid
    
    def test_validate_code_invalid(self):
        """Invalid code through convenience function."""
        code = "import os"
        result = validate_code(code)
        assert not result.is_valid
    
    def test_validate_code_strict(self):
        """Test strict mode."""
        code = "x = 1"
        result_strict = validate_code(code, strict=True)
        result_relaxed = validate_code(code, strict=False)
        
        assert result_strict.is_valid
        assert result_relaxed.is_valid


class TestEdgeCases:
    """Test edge cases and corner scenarios."""
    
    def test_multiline_imports(self):
        """Multiple imports in one line."""
        code = "import numpy, pandas, math"
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_nested_function_calls(self):
        """Nested function calls."""
        code = "result = sum(map(int, ['1', '2', '3']))"
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_lambda_functions(self):
        """Lambda functions."""
        code = "f = lambda x: x * 2"
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_list_comprehensions(self):
        """List comprehensions."""
        code = "squares = [x**2 for x in range(10)]"
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_dict_comprehensions(self):
        """Dictionary comprehensions."""
        code = "squares_dict = {x: x**2 for x in range(10)}"
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_generator_expressions(self):
        """Generator expressions."""
        code = "gen = (x**2 for x in range(10))"
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_try_except_blocks(self):
        """Try/except error handling."""
        code = """
try:
    result = 1 / 0
except ZeroDivisionError:
    result = 0
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_with_statements(self):
        """Context managers (without file operations)."""
        code = """
import json
data = {'key': 'value'}
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_class_definitions(self):
        """Class definitions."""
        code = """
class MyClass:
    def __init__(self, value):
        self.value = value
    
    def get_value(self):
        return self.value
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid
    
    def test_function_definitions(self):
        """Function definitions."""
        code = """
def calculate_ma(prices, window):
    import numpy as np
    return np.mean(prices[-window:])
"""
        validator = ASTValidator()
        result = validator.validate(code)
        assert result.is_valid


class TestStrictMode:
    """Test strict vs relaxed validation modes."""
    
    def test_global_statement_strict(self):
        """Global statement in strict mode generates warning."""
        code = """
global x
x = 1
"""
        validator = ASTValidator(strict=True)
        result = validator.validate(code)
        assert result.is_valid  # Valid but has warning
        assert len(result.warnings) > 0
    
    def test_global_statement_relaxed(self):
        """Global statement in relaxed mode."""
        code = """
global x
x = 1
"""
        validator = ASTValidator(strict=False)
        result = validator.validate(code)
        assert result.is_valid
        # Relaxed mode might have fewer warnings


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
