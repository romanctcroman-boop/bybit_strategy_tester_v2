"""
Auto-fix except:pass blocks in mcp_integration.py by adding logging
"""

import re
from pathlib import Path


def fix_mcp_integration(file_path: Path):
    """Fix except:pass blocks in mcp_integration.py"""
    content = file_path.read_text(encoding="utf-8")
    original = content

    # Add logging import if not present
    if "import logging" not in content:
        # Find first import block and add logging
        content = content.replace(
            "from pathlib import Path", "from pathlib import Path\nimport logging"
        )

    # Pattern: except Exception: followed by pass
    pattern = r"(\s+)except Exception:\s*\n\s+pass\b"

    def replacement(match):
        indent = match.group(1)
        return f'{indent}except Exception as _e:\n{indent}    logging.getLogger("backend.mcp.mcp_integration").warning("Failed to update metrics: %s", _e)'

    content = re.sub(pattern, replacement, content)

    if content != original:
        # Backup
        backup = file_path.with_suffix(".py.bak")
        backup.write_text(original, encoding="utf-8")
        print(f"✓ Created backup: {backup}")

        # Write fixed version
        file_path.write_text(content, encoding="utf-8")

        # Count changes
        original_count = len(re.findall(r"except Exception:\s*\n\s+pass", original))
        new_count = len(re.findall(r"except Exception:\s*\n\s+pass", content))
        fixed = original_count - new_count

        print(f"✓ Fixed {fixed} except:pass blocks in {file_path.name}")
        return fixed

    return 0


if __name__ == "__main__":
    root = Path(__file__).parent.parent
    target = root / "backend" / "mcp" / "mcp_integration.py"

    if not target.exists():
        print(f"Error: {target} not found")
        exit(1)

    fixed_count = fix_mcp_integration(target)
    print(f"\n✅ Complete: {fixed_count} blocks fixed")
