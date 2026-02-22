"""Fix f-strings without placeholders in script files."""

import pathlib
import re

files = [
    "scripts/analyze_strategy.py",
    "scripts/test_generate_signals.py",
    "scripts/test_pipeline_logic.py",
]

# Pattern: f"..." or f'...' where content has NO { or }
PATTERN = re.compile(r'\bf("[^"{}\\]*"|\'[^\'{}\\]*\')')

for fp in files:
    path = pathlib.Path(fp)
    text = path.read_text(encoding="utf-8")
    new_text, count = PATTERN.subn(lambda m: m.group(1), text)
    if count:
        path.write_text(new_text, encoding="utf-8")
        print(f"{fp}: fixed {count} f-strings")
    else:
        print(f"{fp}: no changes needed")

print("Done.")
