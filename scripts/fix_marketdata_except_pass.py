"""
Auto-fix except:pass blocks in marketdata.py by adding logging
"""

import re
from pathlib import Path


def fix_marketdata(file_path: Path):
    """Fix except:pass blocks in marketdata.py"""
    content = file_path.read_text(encoding="utf-8")
    original = content

    # Pattern: except Exception: followed by pass
    pattern = r"(\s+)except Exception:\s*\n\s+pass\b"

    def replacement(match):
        indent = match.group(1)
        # For marketdata, use debug level since some errors are expected (parsing attempts)
        return f'{indent}except Exception as _e:\n{indent}    logger.debug("Parse attempt failed: %s", _e)'

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
    target = root / "backend" / "api" / "routers" / "marketdata.py"

    if not target.exists():
        print(f"Error: {target} not found")
        exit(1)

    fixed_count = fix_marketdata(target)
    print(f"\n✅ Complete: {fixed_count} blocks fixed")
