"""
Auto-fix except:pass blocks in app.py by adding logging
"""

import re
from pathlib import Path


def fix_app_py(file_path: Path):
    """Fix except:pass blocks in app.py"""
    content = file_path.read_text(encoding="utf-8")
    original = content

    # Pattern: try block with metrics followed by except Exception: pass
    # Replace with except Exception as _e: logging
    pattern = r"(\s+)except Exception:\s*\n\s+pass\b"

    def replacement(match):
        indent = match.group(1)
        return f'{indent}except Exception as _e:\n{indent}    logging.getLogger("backend.api.app").warning("Failed to update metrics: %s", _e)'

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
    app_py = root / "backend" / "api" / "app.py"

    if not app_py.exists():
        print(f"Error: {app_py} not found")
        exit(1)

    fixed_count = fix_app_py(app_py)
    print(f"\n✅ Complete: {fixed_count} blocks fixed")
