"""
Script to remove orphaned inline MCP tools from app.py
These tools have been migrated to backend/api/mcp/tools/
"""
import os

app_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', 'api', 'app.py')

with open(app_py, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Original file: {len(lines)} lines")

# Find markers
start_marker = None
end_marker = None

for i, line in enumerate(lines):
    # Line 620: "        return mcp_error.to_dict()" - orphaned code starts here
    if start_marker is None and line.strip() == "return mcp_error.to_dict()" and i > 600:
        start_marker = i
        print(f"Found orphan start at line {i+1}: {line.strip()[:50]}")
    
    # Line ~1286: "# MCP ASGI routes will be registered" - where we want to keep
    if "MCP ASGI routes will be registered" in line:
        end_marker = i
        print(f"Found end marker at line {i+1}: {line.strip()[:50]}")
        break

if start_marker and end_marker:
    # Keep everything before start_marker, and from end_marker onwards
    new_lines = lines[:start_marker] + lines[end_marker:]
    
    with open(app_py, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    deleted = end_marker - start_marker
    print(f"Deleted {deleted} lines (from {start_marker+1} to {end_marker})")
    print(f"New file: {len(new_lines)} lines")
    print("Done!")
else:
    print(f"Markers not found. start={start_marker}, end={end_marker}")
    print("Trying alternative approach...")
    
    # Alternative: find the patterns more specifically
    for i, line in enumerate(lines[600:700], start=600):
        if "return mcp_error.to_dict()" in line:
            print(f"  Line {i+1}: {line.strip()[:60]}")
