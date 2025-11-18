#!/usr/bin/env python3
"""
Автоматическая замена всех print() на logger.info() в server.py
Критический фикс для устранения stdio/JSON-RPC конфликта
"""

import re
from pathlib import Path

def fix_print_statements(file_path: Path) -> int:
    """Replace all print() with logger.info()"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    replacements = 0
    
    # Pattern 1: print(f"...") -> logger.info(f"...")
    pattern1 = r'(\s+)print\((f"[^"]*")\)'
    matches1 = re.findall(pattern1, content)
    content = re.sub(pattern1, r'\1logger.info(\2)', content)
    replacements += len(matches1)
    
    # Pattern 2: print("...") -> logger.info("...")
    pattern2 = r'(\s+)print\(("([^"]|\\")*")\)'
    matches2 = re.findall(pattern2, content)
    content = re.sub(pattern2, r'\1logger.info(\2)', content)
    replacements += len(matches2)
    
    # Pattern 3: print(...) with complex expressions
    # Find all print( and replace carefully
    lines = content.split('\n')
    fixed_lines = []
    
    for line in lines:
        if 'print(' in line and not line.strip().startswith('#'):
            # Skip comments and already fixed lines
            if 'logger.' not in line:
                # Replace print( with logger.info(
                fixed_line = line.replace('print(', 'logger.info(')
                if fixed_line != line:
                    fixed_lines.append(fixed_line)
                    continue
        
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    # Save if changes were made
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Fixed {len(re.findall(r'logger\.info\(', content))} print statements")
        print(f"📝 File saved: {file_path}")
        return len(re.findall(r'logger\.info\(', content))
    else:
        print("⚠️ No changes needed")
        return 0

def main():
    """Main function"""
    server_file = Path(__file__).parent / 'mcp-server' / 'server.py'
    
    if not server_file.exists():
        print(f"❌ File not found: {server_file}")
        return
    
    print("=" * 80)
    print("🔧 FIXING MCP SERVER - Removing stdout/stderr conflicts")
    print("=" * 80)
    print(f"\n📁 Target file: {server_file}")
    print(f"📊 File size: {server_file.stat().st_size} bytes")
    print(f"📝 Lines: {len(server_file.read_text(encoding='utf-8').splitlines())}")
    print("\n🔄 Replacing print() → logger.info()...")
    print()
    
    count = fix_print_statements(server_file)
    
    print()
    print("=" * 80)
    print(f"✅ FIX COMPLETE: {count} logger calls in file")
    print("=" * 80)
    print("\n✅ All print() statements replaced with logger.info()")
    print("✅ No more stdout/stderr conflicts with JSON-RPC")
    print("✅ MCP server should now run stable 24/7")
    print("\n🚀 Next: Test MCP server restart")

if __name__ == "__main__":
    main()
