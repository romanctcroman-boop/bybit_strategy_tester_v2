"""
Add get_next_key mocks to all remaining tests
"""
import re

TEST_FILE = r"tests\test_deepseek_client.py"

with open(TEST_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Find all test methods without get_next_key mock
# Pattern: test method that creates client but doesn't mock get_next_key
test_pattern = r'(async def test_\w+\(self\):.*?client = DeepSeekReliableClient\([^)]+\))'

def add_mock_after_client_creation(match):
    original = match.group(1)
    if 'get_next_key' in original or '_process_single_request' in original:
        # Already has mock
        return original
    
    # Add mock after client creation
    lines = original.split('\n')
    client_line_idx = next(i for i, line in enumerate(lines) if 'DeepSeekReliableClient(' in line)
    
    # Find end of client creation (closing parenthesis)
    bracket_count = 0
    end_idx = client_line_idx
    for i in range(client_line_idx, len(lines)):
        bracket_count += lines[i].count('(') - lines[i].count(')')
        if bracket_count == 0:
            end_idx = i
            break
    
    # Insert mock after client creation
    indent = '        '  # Assuming 8 spaces indent
    mock_code = [
        '',
        f'{indent}# Mock get_next_key to avoid timeout',
        f'{indent}async def mock_get_key(timeout=30.0):',
        f'{indent}    from reliability import KeyConfig',
        f'{indent}    return KeyConfig(id="key1", api_key="sk-test", secret="", weight=1.0, max_failures=10)',
        f'{indent}client.key_rotation.get_next_key = mock_get_key',
    ]
    
    lines = lines[:end_idx+1] + mock_code + lines[end_idx+1:]
    return '\n'.join(lines)

# Apply to all test methods
new_content = re.sub(test_pattern, add_mock_after_client_creation, content, flags=re.DOTALL)

with open(TEST_FILE, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ Added get_next_key mocks to all remaining tests")
