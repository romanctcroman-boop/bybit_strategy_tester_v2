# Fix the specific mojibake line in backtest_results.js
# Line 1712: Replace the garbled text with correct Russian

import re

file_path = r'd:\bybit_strategy_tester_v2\frontend\js\pages\backtest_results.js'

# Read file
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find and print the character codes around "Unknown'}"
search_str = "Unknown'}"
idx = content.find(search_str)
if idx > 0:
    # Extract the garbled part after "Unknown'} "
    after = content[idx + len(search_str):idx + len(search_str) + 20]
    print(f"After 'Unknown}}': {repr(after)}")
    print(f"Char codes: {[ord(c) for c in after]}")

# Simple line-based replacement
lines = content.split('\n')
for i, line in enumerate(lines):
    if "strategyName.textContent" in line and "Unknown" in line:
        print(f"Found line {i+1}: {repr(line[:80])}")
        # Replace everything after Unknown'} with correct text
        new_line = re.sub(r"Unknown'\}\s*[^`]+`", "Unknown'} Отчёт`", line)
        if new_line != line:
            lines[i] = new_line
            print(f"Replaced with: {repr(new_line[:80])}")

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print("\nDone!")
