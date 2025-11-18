"""
Auto-fix auth_middleware tests:
Move middleware creation INSIDE patch context
"""

import re

test_file = "tests/backend/security/test_auth_middleware.py"

with open(test_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern: middleware created OUTSIDE patch, then patch → add_middleware
pattern = r'(    def test_\w+\([^)]+\):.*?""".*?""")\n        middleware = AuthenticationMiddleware\((.*?)\)\n        \n        with patch\('
replacement = r'\1\n        \n        with patch('

content_fixed = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Pattern 2: Move middleware INSIDE all nested patch blocks
# Find: with patch(...): \n with patch(...): \n with patch(...): \n app.add_middleware
# Replace: Insert middleware creation before app.add_middleware

# Complex regex for nested patches - find and fix manually is safer
# Let's count how many need fixing

matches = re.findall(r'middleware = AuthenticationMiddleware.*?\n.*?with patch\(', content, re.DOTALL)
print(f"Found {len(matches)} tests with wrong pattern")

# Strategy: find all test methods with this pattern
test_pattern = r'(    def (test_\w+)\([^)]+\):.*?""".*?""")\s+(middleware = AuthenticationMiddleware\([^)]+\))\s+(with patch.*?app\.add_middleware\(BaseHTTPMiddleware.*?client = TestClient\(app.*?\))'

def fix_test(match):
    """Rewrite test to move middleware inside patches"""
    intro = match.group(1)
    test_name = match.group(2) 
    middleware_line = match.group(3)
    patch_block = match.group(4)
    
    # Move middleware line after last 'with patch' and before app.add_middleware
    # Find position of app.add_middleware
    patch_lines = patch_block.split('\n')
    fixed_lines = []
    middleware_inserted = False
    
    for line in patch_lines:
        if 'app.add_middleware' in line and not middleware_inserted:
            # Insert middleware creation before this line
            indent = len(line) - len(line.lstrip())
            fixed_lines.append(' ' * indent + middleware_line.strip())
            middleware_inserted = True
        fixed_lines.append(line)
    
    return intro + '\n        \n        ' + '\n'.join(fixed_lines)

# This is too complex for regex, do manual edits
# Instead, create a simple search-replace script

# List all tests that need fixing
tests_to_fix = [
    "test_protected_path_requires_auth",
    "test_missing_token_returns_401",
    "test_invalid_signature_returns_401", 
    "test_malformed_token_returns_401",
    "test_api_key_token_accepted",
    "test_refresh_token_rejected",
    "test_rate_limit_allowed",
    "test_rate_limit_exceeded_returns_429",
    "test_rate_limit_cost_calculation_post",
    "test_rate_limit_cost_calculation_batch",
    "test_security_headers_added",
    "test_user_info_attached_to_request",
    "test_internal_error_returns_500"
]

print(f"\nTests needing manual fix: {len(tests_to_fix)}")
print('\n'.join(tests_to_fix))
