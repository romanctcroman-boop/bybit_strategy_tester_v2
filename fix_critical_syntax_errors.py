"""
Автоматическое исправление критических синтаксических ошибок
BLOCKER P0: 4 файла с unterminated string literals

Дата: 2025-10-30
GitHub Copilot + Perplexity AI Integration
"""

import re
from pathlib import Path

# Файлы с ошибками
BROKEN_FILES = [
    "test_real_ai_workflow.py",
    "test_real_ai_workflow_mtf.py",
    "analyze_project_with_mcp.py",
    "query_mcp_tools.py"
]

def fix_unterminated_string(file_path: Path) -> bool:
    """
    Исправляет незакрытые строковые литералы в raise ValueError()
    
    Проблема:
        raise ValueError(
            "⚠️ SECURITY: PERPLEXITY_API_KEY not configured.
        "
            "Please add PERPLEXITY_API_KEY to .env file"
        )
    
    Решение:
        raise ValueError(
            "⚠️ SECURITY: PERPLEXITY_API_KEY not configured. "
            "Please add PERPLEXITY_API_KEY to .env file"
        )
    """
    
    print(f"\n{'='*80}")
    print(f"📝 Processing: {file_path.name}")
    print(f"{'='*80}")
    
    try:
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Pattern 1: Unterminated string в raise ValueError
        # Ищем строки вида: "text.\n"
        pattern1 = r'("⚠️ SECURITY: PERPLEXITY_API_KEY not configured\.)\n(")'
        replacement1 = r'\1 "\n\2'
        content, count1 = re.subn(pattern1, replacement1, content)
        
        # Pattern 2: Более общий случай - любая незакрытая строка в raise
        pattern2 = r'(raise \w+\(\s*"[^"]*)\n(\s*")'
        replacement2 = r'\1 "\n\2'
        content, count2 = re.subn(pattern2, replacement2, content)
        
        total_fixes = count1 + count2
        
        if total_fixes > 0:
            # Backup original
            backup_path = file_path.with_suffix(file_path.suffix + '.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            print(f"  ✅ Backup created: {backup_path.name}")
            
            # Write fixed content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"  ✅ Fixed {total_fixes} unterminated strings")
            print(f"  ✅ File updated: {file_path.name}")
            return True
        else:
            print(f"  ⚠️  No unterminated strings found (file may be already fixed)")
            return False
    
    except Exception as e:
        print(f"  ❌ Error processing {file_path.name}: {e}")
        return False


def verify_syntax(file_path: Path) -> bool:
    """
    Проверка синтаксиса Python файла
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Compile to check syntax
        compile(code, str(file_path), 'exec')
        print(f"  ✅ Syntax valid: {file_path.name}")
        return True
    
    except SyntaxError as e:
        print(f"  ❌ Syntax error in {file_path.name}:")
        print(f"     Line {e.lineno}: {e.msg}")
        print(f"     {e.text}")
        return False
    
    except Exception as e:
        print(f"  ❌ Error verifying {file_path.name}: {e}")
        return False


def main():
    """Main execution"""
    
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║                   CRITICAL SYNTAX ERRORS FIXER                           ║
║                   BLOCKER P0: 4 files with issues                        ║
╚══════════════════════════════════════════════════════════════════════════╝
    """)
    
    project_root = Path(__file__).parent
    results = {
        "fixed": [],
        "already_ok": [],
        "failed": []
    }
    
    # Step 1: Fix files
    print("\n🔧 STEP 1: Fixing Syntax Errors")
    print("─" * 80)
    
    for filename in BROKEN_FILES:
        file_path = project_root / filename
        
        if not file_path.exists():
            print(f"\n⚠️  File not found: {filename}")
            results["failed"].append(filename)
            continue
        
        success = fix_unterminated_string(file_path)
        
        if success:
            results["fixed"].append(filename)
        else:
            results["already_ok"].append(filename)
    
    # Step 2: Verify syntax
    print(f"\n\n🔍 STEP 2: Verifying Syntax")
    print("─" * 80)
    
    all_valid = True
    for filename in BROKEN_FILES:
        file_path = project_root / filename
        
        if file_path.exists():
            print(f"\nVerifying: {filename}")
            valid = verify_syntax(file_path)
            if not valid:
                all_valid = False
    
    # Step 3: Summary
    print(f"\n\n{'='*80}")
    print("📊 SUMMARY")
    print(f"{'='*80}")
    
    print(f"\n✅ Fixed: {len(results['fixed'])} files")
    for f in results['fixed']:
        print(f"   • {f}")
    
    if results['already_ok']:
        print(f"\n⚠️  Already OK: {len(results['already_ok'])} files")
        for f in results['already_ok']:
            print(f"   • {f}")
    
    if results['failed']:
        print(f"\n❌ Failed: {len(results['failed'])} files")
        for f in results['failed']:
            print(f"   • {f}")
    
    print(f"\n{'='*80}")
    if all_valid:
        print("✅ ALL FILES HAVE VALID SYNTAX!")
        print("✅ Project can now be imported without syntax errors")
        print("\n🚀 Next Steps:")
        print("   1. Run tests: pytest tests/")
        print("   2. Check MCP server: python mcp-server/server.py")
        print("   3. Test MCP bridge: python mcp_bridge.py")
    else:
        print("❌ SOME FILES STILL HAVE SYNTAX ERRORS")
        print("⚠️  Manual review required")
        print("\n🔍 Troubleshooting:")
        print("   1. Check backup files (*.backup)")
        print("   2. Review error messages above")
        print("   3. Manually fix remaining issues")
    print(f"{'='*80}\n")
    
    return 0 if all_valid else 1


if __name__ == "__main__":
    exit(main())
