"""Extract and save all mojibake patterns to a file."""

import re

with open('frontend/js/pages/backtest_results.js', 'r', encoding='utf-8') as f:
    text = f.read()

# Find all string literals containing potential mojibake
patterns = []
for match in re.finditer(r"'([^']{2,})'", text):
    content = match.group(1)
    # Check if it contains mojibake characters
    if '\u0420' in content or '\u0421' in content or ('\u0440' in content and '\u045f' in content):
        if len(content) > 5:  # Skip short patterns
            patterns.append(content)

# Remove duplicates while preserving order
seen = set()
unique = []
for p in patterns:
    if p not in seen:
        seen.add(p)
        unique.append(p)

with open('scripts/patterns.txt', 'w', encoding='utf-8') as f:
    for p in unique:
        # Print as hex escape
        escaped = ''.join(f'\\u{ord(c):04x}' if ord(c) > 127 else c for c in p)
        f.write(f"# {repr(p)[:60]}...\n")
        f.write(f"('{escaped}', 'REPLACE_ME'),\n\n")

print(f"Saved {len(unique)} patterns to scripts/patterns.txt")
