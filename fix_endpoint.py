"""Fix endpoint URL in test file."""

path = r"D:\bybit_strategy_tester_v2\test_evaluation_logic.py"
content = open(path, encoding="utf-8").read()
old = 'optimizations/sync"'
new = 'optimizations/sync/grid-search"'
content = content.replace(old, new)
open(path, "w", encoding="utf-8").write(content)
print(f"Fixed! Found {content.count('grid-search')} occurrences")
