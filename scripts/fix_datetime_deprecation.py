"""
Fix all datetime.utcnow() deprecation warnings in the project
==============================================================

This script automatically replaces all deprecated datetime.utcnow() calls
with datetime.now(timezone.utc) across the entire backend codebase.

Why this is needed:
- datetime.utcnow() is deprecated in Python 3.12+
- Should use timezone-aware datetime objects
- Prevents future compatibility issues

Changes made:
1. Add 'timezone' import where needed
2. Replace datetime.utcnow() with datetime.now(timezone.utc)
3. Replace default=datetime.utcnow with default=lambda: datetime.now(timezone.utc)

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


def find_files_with_datetime_utcnow() -> List[Path]:
    """Find all Python files with datetime.utcnow()"""
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
                        if 'datetime.utcnow' in content:
                            files.append(filepath)
                except Exception as e:
                    print(f"⚠️  Error reading {filepath}: {e}")
    
    return files


def fix_datetime_imports(content: str) -> str:
    """Add timezone import if needed"""
    
    # Check if already has timezone import
    if 'from datetime import' in content and 'timezone' not in content.split('from datetime import')[1].split('\n')[0]:
        # Add timezone to existing import
        content = re.sub(
            r'from datetime import ([^\n]+)',
            lambda m: f'from datetime import {m.group(1).strip()}, timezone' if 'timezone' not in m.group(1) else m.group(0),
            content,
            count=1
        )
    elif 'import datetime' in content and 'from datetime import' not in content:
        # If using 'import datetime', no need to change
        pass
    
    return content


def fix_datetime_utcnow_calls(content: str) -> Tuple[str, int]:
    """Replace all datetime.utcnow() with datetime.now(timezone.utc)"""
    
    count = 0
    
    # Pattern 1: datetime.utcnow() calls
    pattern1 = r'datetime\.utcnow\(\)'
    replacement1 = r'datetime.now(timezone.utc)'
    content, n1 = re.subn(pattern1, replacement1, content)
    count += n1
    
    # Pattern 2: default=datetime.utcnow (in SQLAlchemy models)
    pattern2 = r'default=datetime\.utcnow(?![\(])'
    replacement2 = r'default=lambda: datetime.now(timezone.utc)'
    content, n2 = re.subn(pattern2, replacement2, content)
    count += n2
    
    # Pattern 3: __import__("datetime").datetime.utcnow() (rare case)
    pattern3 = r'__import__\("datetime"\)\.datetime\.utcnow\(\)'
    replacement3 = r'__import__("datetime").datetime.now(__import__("datetime").timezone.utc)'
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
        content = fix_datetime_imports(original_content)
        content, replacements = fix_datetime_utcnow_calls(content)
        
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
    print("Fixing datetime.utcnow() deprecation warnings")
    print("="*80)
    print()
    
    # Find files
    print("🔍 Scanning for files with datetime.utcnow()...")
    files = find_files_with_datetime_utcnow()
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
    print("  pytest tests/integration/test_deepseek_agent.py -v")
    print("  pytest tests/integration/test_task_queue.py -v")
    print()


if __name__ == "__main__":
    main()
