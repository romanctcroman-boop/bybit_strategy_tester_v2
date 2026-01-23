"""Extract mojibake patterns from the JS file."""

import re

with open('frontend/js/pages/backtest_results.js', 'r', encoding='utf-8') as f:
    text = f.read()

# Find all string literals containing potential mojibake
patterns = set()
for match in re.finditer(r"'([^']*)'", text):
    content = match.group(1)
    # Check if it contains mojibake characters
    if '\u0420' in content or '\u0421' in content or '\u0440' in content:
        patterns.add(content)

print(f"Found {len(patterns)} unique mojibake patterns:\n")
for p in sorted(patterns):
    # Print as Python string literal
    escaped = ''.join(f'\\u{ord(c):04x}' if ord(c) > 127 else c for c in p)
    print(f"'{escaped}',")
