#!/usr/bin/env python3
"""
Quick script to add @provider_ready to remaining DeepSeek tools
"""

import re
from pathlib import Path

server_path = Path(__file__).parent / "mcp-server" / "server.py"

# Read file
with open(server_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Tools to update (excluding already done)
tools_to_update = [
    "deepseek_optimize_parameters",
    "deepseek_backtest_analysis",
    "deepseek_risk_analysis",
    "deepseek_compare_strategies",
    "deepseek_generate_tests",
    "deepseek_refactor_code"
]

updates = 0
for tool_name in tools_to_update:
    # Pattern: @mcp.tool()\nasync def tool_name
    pattern = rf'(@mcp\.tool\(\))\n(async def {tool_name})'
    replacement = r'\1\n@provider_ready\n\2'
    
    new_content, count = re.subn(pattern, replacement, content)
    if count > 0:
        content = new_content
        updates += count
        print(f"✅ Added @provider_ready to {tool_name}")
    else:
        print(f"⚠️  Pattern not found for {tool_name}")

# Write back
with open(server_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n✅ Total updates: {updates}")
print(f"✅ File updated: {server_path.name}")
