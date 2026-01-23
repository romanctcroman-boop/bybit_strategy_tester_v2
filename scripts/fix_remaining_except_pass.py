"""
Fix remaining except:pass blocks in backend files
"""

import re
from pathlib import Path


def fix_file_except_pass(file_path: Path, logger_name: str = None):
    """Fix except:pass blocks in a file"""
    content = file_path.read_text(encoding="utf-8")
    original = content

    # Determine if file uses loguru or standard logging
    uses_loguru = "from loguru import logger" in content or "import loguru" in content

    # Pattern: except Exception: followed by pass
    pattern = r"(\s+)except Exception:\s*\n\s+pass\b"

    def replacement(match):
        indent = match.group(1)
        if uses_loguru:
            return f'{indent}except Exception as _e:\n{indent}    logger.debug("Operation failed (expected): {{}}", _e)'
        else:
            logger_call = logger_name or f'"{file_path.stem}"'
            return f'{indent}except Exception as _e:\n{indent}    logging.getLogger({logger_call}).debug("Operation failed: %s", _e)'

    content = re.sub(pattern, replacement, content)

    # Add logging import if needed and not using loguru
    if not uses_loguru and content != original and "import logging" not in content:
        # Add after first import block
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                # Insert after this import block
                j = i
                while j < len(lines) and (
                    lines[j].startswith("import ")
                    or lines[j].startswith("from ")
                    or lines[j].strip() == ""
                ):
                    j += 1
                lines.insert(j, "import logging")
                content = "\n".join(lines)
                break

    if content != original:
        # Backup
        backup = file_path.with_suffix(".py.bak")
        backup.write_text(original, encoding="utf-8")

        # Write fixed version
        file_path.write_text(content, encoding="utf-8")

        # Count changes
        original_count = len(re.findall(r"except Exception:\s*\n\s+pass", original))
        new_count = len(re.findall(r"except Exception:\s*\n\s+pass", content))
        fixed = original_count - new_count

        print(
            f"✓ {file_path.relative_to(file_path.parent.parent.parent)}: fixed {fixed} blocks"
        )
        return fixed

    return 0


if __name__ == "__main__":
    root = Path(__file__).parent.parent

    # Files to fix
    files_to_fix = [
        root / "backend" / "services" / "adapters" / "bybit.py",
        root / "backend" / "agents" / "unified_agent_interface.py",
        root / "backend" / "agents" / "health_monitor.py",
        root / "backend" / "services" / "archival_service.py",
        root / "backend" / "services" / "data_service.py",
    ]

    total_fixed = 0
    for file_path in files_to_fix:
        if file_path.exists():
            fixed = fix_file_except_pass(file_path)
            total_fixed += fixed

    print(f"\n✅ Complete: {total_fixed} blocks fixed across {len(files_to_fix)} files")
