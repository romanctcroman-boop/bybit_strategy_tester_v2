"""Quick fix: Add enable_monitoring=False to all DeepSeekReliableClient calls"""
import re

filepath = "tests/test_deepseek_client.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern: DeepSeekReliableClient(...) without enable_monitoring
def add_monitoring_flag(match):
    args = match.group(1).strip()
    if 'enable_monitoring' in args:
        return match.group(0)  # Already has flag
    
    # Add enable_monitoring=False
    if args.endswith(','):
        return f"DeepSeekReliableClient({args}\n            enable_monitoring=False\n        )"
    else:
        return f"DeepSeekReliableClient(\n{args},\n            enable_monitoring=False\n        )"

# Replace all occurrences
content = re.sub(
    r'DeepSeekReliableClient\(([^)]+)\)',
    add_monitoring_flag,
    content,
    flags=re.DOTALL
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Fixed: Added enable_monitoring=False to all DeepSeekReliableClient calls")
