"""
🔐 AUTOMATED SECURITY FIX SCRIPT
Fixes hardcoded API keys across the project

Method: Copilot ↔ Perplexity AI Collaborative Analysis
Priority: P0 - CRITICAL
"""
import os
import re
from pathlib import Path
from datetime import datetime

# Files with hardcoded API keys (Priority P0)
PRIORITY_P0_FILES = [
    "query_mcp_tools.py",
    "analyze_project_with_mcp.py",
    "test_real_ai_workflow.py",
    "test_real_ai_workflow_mtf.py",
    "test_full_90days_mtf_ai_workflow.py",
]

# Files with fallback keys (Priority P1)
PRIORITY_P1_FILES = [
    "mcp-server/server.py",
    "conduct_project_audit.py",
    "test_mcp_conceptual_100.py",
    "mcp-server/test_perplexity.py",
    "tests/integration/test_simplified_real.py",
]

# Test files (Priority P2)
PRIORITY_P2_FILES = [
    "tests/integration/test_mcp_cyclic_dialogue.py",
    "tests/integration/test_real_mcp_copilot_perplexity.py",
    "test_mcp_health.py",
]


def fix_hardcoded_api_key(file_path: Path) -> tuple[bool, str]:
    """
    Fix hardcoded API key in a file.
    
    Returns:
        (success: bool, message: str)
    """
    try:
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Pattern 1: Direct hardcoded key
        pattern1 = r'PERPLEXITY_API_KEY\s*=\s*"pplx-[A-Za-z0-9]+"'
        
        if re.search(pattern1, content):
            # Check if dotenv import already exists
            has_dotenv_import = 'from dotenv import load_dotenv' in content
            has_load_dotenv = 'load_dotenv()' in content
            
            # Add imports if needed
            if not has_dotenv_import:
                # Find import section (after docstring)
                import_match = re.search(r'(""".*?"""|\'\'\'.*?\'\'\')\s*\n', content, re.DOTALL)
                if import_match:
                    insert_pos = import_match.end()
                    content = (
                        content[:insert_pos] +
                        "import os\nfrom dotenv import load_dotenv\n\n" +
                        content[insert_pos:]
                    )
            
            # Add load_dotenv() if needed
            if not has_load_dotenv:
                # Add after imports
                import_section_end = content.find('\n\n', content.find('import'))
                if import_section_end != -1:
                    content = (
                        content[:import_section_end] +
                        "\n\nload_dotenv()  # Load environment variables from .env file\n" +
                        content[import_section_end:]
                    )
            
            # Replace hardcoded key
            replacement = '''PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

if not PERPLEXITY_API_KEY:
    raise ValueError(
        "⚠️ SECURITY: PERPLEXITY_API_KEY not configured.\\n"
        "Please add PERPLEXITY_API_KEY to .env file"
    )'''
            
            content = re.sub(pattern1, replacement, content)
        
        # Pattern 2: Fallback key in os.getenv()
        pattern2 = r'os\.getenv\("PERPLEXITY_API_KEY",\s*"pplx-[A-Za-z0-9]+"\)'
        pattern2_alt = r'os\.environ\.get\([\'"]PERPLEXITY_API_KEY[\'"]\s*,\s*[\'"]pplx-[A-Za-z0-9]+[\'"]\)'
        
        if re.search(pattern2, content) or re.search(pattern2_alt, content):
            content = re.sub(pattern2, 'os.getenv("PERPLEXITY_API_KEY")', content)
            content = re.sub(pattern2_alt, 'os.getenv("PERPLEXITY_API_KEY")', content)
            
            # Add validation if not exists
            if 'if not PERPLEXITY_API_KEY:' not in content:
                # Find the line after key assignment
                key_line_match = re.search(r'(PERPLEXITY_API_KEY\s*=\s*os\.getenv.*?\n)', content)
                if key_line_match:
                    insert_pos = key_line_match.end()
                    validation = '''\nif not PERPLEXITY_API_KEY:
    raise ValueError(
        "⚠️ SECURITY: PERPLEXITY_API_KEY not configured.\\n"
        "Please add PERPLEXITY_API_KEY to .env file"
    )
'''
                    content = content[:insert_pos] + validation + content[insert_pos:]
        
        # Check if anything changed
        if content == original_content:
            return False, "No changes needed (already fixed or no keys found)"
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True, "✅ Fixed successfully"
        
    except Exception as e:
        return False, f"❌ Error: {e}"


def create_env_file():
    """Create .env file if it doesn't exist."""
    env_path = Path(".env")
    
    if env_path.exists():
        print("✅ .env file already exists")
        return
    
    env_content = """# 🔐 ENVIRONMENT VARIABLES
# ⚠️ NEVER commit this file to Git!

# Perplexity AI API Key
# Get your key from: https://www.perplexity.ai/settings/api
PERPLEXITY_API_KEY=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

# Bybit API Credentials (OPTIONAL for backtesting)
BYBIT_API_KEY=your_bybit_api_key_here
BYBIT_API_SECRET=your_bybit_api_secret_here

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/bybit_strategy_tester

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Application Settings
ENVIRONMENT=development
LOG_LEVEL=INFO
"""
    
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("✅ Created .env file")


def update_gitignore():
    """Add .env to .gitignore if not already there."""
    gitignore_path = Path(".gitignore")
    
    if not gitignore_path.exists():
        gitignore_content = """# Environment variables
.env
.env.local
.env.*.local

# API Keys
*api_key*
*secret*
*.pem
*.key
"""
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write(gitignore_content)
        print("✅ Created .gitignore")
        return
    
    with open(gitignore_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if '.env' in content:
        print("✅ .env already in .gitignore")
        return
    
    with open(gitignore_path, 'a', encoding='utf-8') as f:
        f.write("\n# Environment variables\n.env\n.env.local\n.env.*.local\n")
    
    print("✅ Added .env to .gitignore")


def main():
    """Main execution function."""
    print("\n" + "="*80)
    print("  🔐 AUTOMATED SECURITY FIX")
    print("  Copilot ↔ Perplexity AI Collaborative Analysis")
    print("="*80 + "\n")
    
    # Step 1: Create .env file
    print("📁 Step 1: Create .env file")
    create_env_file()
    print()
    
    # Step 2: Update .gitignore
    print("📝 Step 2: Update .gitignore")
    update_gitignore()
    print()
    
    # Step 3: Fix Priority P0 files
    print("🔧 Step 3: Fix Priority P0 files (Hardcoded keys)")
    print("-" * 80)
    
    p0_fixed = 0
    p0_failed = 0
    
    for filename in PRIORITY_P0_FILES:
        file_path = Path(filename)
        if not file_path.exists():
            print(f"⚠️  {filename:<40} - File not found")
            continue
        
        success, message = fix_hardcoded_api_key(file_path)
        if success:
            print(f"✅ {filename:<40} - {message}")
            p0_fixed += 1
        else:
            print(f"⏭️  {filename:<40} - {message}")
            if "Error" in message:
                p0_failed += 1
    
    print()
    
    # Step 4: Fix Priority P1 files
    print("🔧 Step 4: Fix Priority P1 files (Fallback keys)")
    print("-" * 80)
    
    p1_fixed = 0
    p1_failed = 0
    
    for filename in PRIORITY_P1_FILES:
        file_path = Path(filename)
        if not file_path.exists():
            print(f"⚠️  {filename:<40} - File not found")
            continue
        
        success, message = fix_hardcoded_api_key(file_path)
        if success:
            print(f"✅ {filename:<40} - {message}")
            p1_fixed += 1
        else:
            print(f"⏭️  {filename:<40} - {message}")
            if "Error" in message:
                p1_failed += 1
    
    print()
    
    # Step 5: Fix Priority P2 files (test files)
    print("🔧 Step 5: Fix Priority P2 files (Test files)")
    print("-" * 80)
    
    p2_fixed = 0
    p2_failed = 0
    
    for filename in PRIORITY_P2_FILES:
        file_path = Path(filename)
        if not file_path.exists():
            print(f"⚠️  {filename:<40} - File not found")
            continue
        
        success, message = fix_hardcoded_api_key(file_path)
        if success:
            print(f"✅ {filename:<40} - {message}")
            p2_fixed += 1
        else:
            print(f"⏭️  {filename:<40} - {message}")
            if "Error" in message:
                p2_failed += 1
    
    print()
    
    # Summary
    print("="*80)
    print("  📊 SUMMARY")
    print("="*80)
    print(f"\n  Priority P0: {p0_fixed}/{len(PRIORITY_P0_FILES)} fixed, {p0_failed} failed")
    print(f"  Priority P1: {p1_fixed}/{len(PRIORITY_P1_FILES)} fixed, {p1_failed} failed")
    print(f"  Priority P2: {p2_fixed}/{len(PRIORITY_P2_FILES)} fixed, {p2_failed} failed")
    print(f"\n  Total fixed: {p0_fixed + p1_fixed + p2_fixed}")
    print(f"  Total failed: {p0_failed + p1_failed + p2_failed}")
    
    if p0_failed + p1_failed + p2_failed == 0:
        print("\n  ✅ ALL SECURITY FIXES APPLIED SUCCESSFULLY!")
    else:
        print(f"\n  ⚠️  {p0_failed + p1_failed + p2_failed} files need manual review")
    
    print("\n" + "="*80)
    print("  🚀 NEXT STEPS:")
    print("="*80)
    print("\n  1. Review changes: git diff")
    print("  2. Test with: python -m pytest tests/")
    print("  3. Commit: git add . && git commit -m 'Security: Remove hardcoded API keys'")
    print("\n")


if __name__ == "__main__":
    main()
