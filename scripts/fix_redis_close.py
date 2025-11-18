"""
Fix all redis.close() deprecation warnings in the project
==========================================================

This script automatically replaces all deprecated redis.close() calls
with redis.aclose() across the entire backend codebase.

Why this is needed:
- redis.close() is deprecated in redis-py 5.0.1+
- Should use async aclose() method
- Prevents future compatibility issues

Changes made:
1. Replace await redis.close() with await redis.aclose()
2. Replace await self.redis.close() with await self.redis.aclose()

Author: GitHub Copilot
Date: November 5, 2025
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"


def find_files_with_redis_close() -> List[Path]:
    """Find all Python files with redis.close()"""
    files = []
    
    for root, dirs, filenames in os.walk(BACKEND_DIR):
        # Skip __pycache__ and other non-source directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        
        for filename in filenames:
            if filename.endswith('.py'):
                filepath = Path(root) / filename
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'redis.close()' in content:
                            files.append(filepath)
                except Exception as e:
                    print(f"⚠️  Error reading {filepath}: {e}")
    
    return files


def fix_redis_close_calls(content: str) -> Tuple[str, int]:
    """Replace all redis.close() with redis.aclose()"""
    
    count = 0
    
    # Pattern 1: await redis.close()
    pattern1 = r'await\s+redis\.close\(\)'
    replacement1 = r'await redis.aclose()'
    content, n1 = re.subn(pattern1, replacement1, content)
    count += n1
    
    # Pattern 2: await self.redis.close()
    pattern2 = r'await\s+self\.redis\.close\(\)'
    replacement2 = r'await self.redis.aclose()'
    content, n2 = re.subn(pattern2, replacement2, content)
    count += n2
    
    # Pattern 3: redis.close() without await (edge case)
    pattern3 = r'(?<!await\s)(?<!await\s\s)redis\.close\(\)'
    replacement3 = r'await redis.aclose()'
    content, n3 = re.subn(pattern3, replacement3, content)
    count += n3
    
    return content, count


def fix_file(filepath: Path) -> Tuple[bool, int]:
    """Fix a single file"""
    
    try:
        # Read file
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Apply fixes
        content, replacements = fix_redis_close_calls(original_content)
        
        if replacements > 0:
            # Write back
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True, replacements
        
        return False, 0
    
    except Exception as e:
        print(f"❌ Error fixing {filepath}: {e}")
        return False, 0


def main():
    """Main function"""
    print("="*80)
    print("Fixing redis.close() deprecation warnings")
    print("="*80)
    print()
    
    # Find files
    print("🔍 Scanning for files with redis.close()...")
    files = find_files_with_redis_close()
    print(f"   Found {len(files)} files")
    print()
    
    if not files:
        print("✅ No files need fixing!")
        return
    
    # Fix files
    print("🔧 Fixing files...")
    print()
    
    total_replacements = 0
    fixed_files = 0
    
    for filepath in files:
        rel_path = filepath.relative_to(PROJECT_ROOT)
        success, replacements = fix_file(filepath)
        
        if success:
            fixed_files += 1
            total_replacements += replacements
            print(f"   ✅ {rel_path} ({replacements} replacements)")
        else:
            print(f"   ⚠️  {rel_path} (no changes)")
    
    print()
    print("="*80)
    print(f"✅ Fixed {fixed_files} files ({total_replacements} total replacements)")
    print("="*80)
    print()
    print("Note: Please run tests to verify all changes work correctly:")
    print("  pytest tests/integration/test_task_queue.py -v")
    print()


if __name__ == "__main__":
    main()
