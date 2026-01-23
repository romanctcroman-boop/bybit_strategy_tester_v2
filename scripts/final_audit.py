"""
Final simple audit - count issues in committed code only
"""

import re
from pathlib import Path


def audit_project(root_dir: Path):
    """Audit committed Python files"""
    stats = {
        "total_files": 0,
        "except_pass_count": 0,
        "todo_count": 0,
        "files_with_except_pass": [],
        "files_with_todos": [],
    }

    # Scan backend directory
    backend_dir = root_dir / "backend"
    if not backend_dir.exists():
        print("Backend directory not found")
        return stats

    for py_file in backend_dir.rglob("*.py"):
        if ".venv" in str(py_file) or "__pycache__" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            stats["total_files"] += 1

            # Count except:pass
            except_pass_matches = re.findall(r"except[^:]*:\s*pass\b", content)
            if except_pass_matches:
                rel_path = py_file.relative_to(root_dir)
                stats["except_pass_count"] += len(except_pass_matches)
                stats["files_with_except_pass"].append(
                    (str(rel_path), len(except_pass_matches))
                )

            # Count TODOs
            todo_matches = re.findall(r"#\s*TODO:", content, re.IGNORECASE)
            if todo_matches:
                rel_path = py_file.relative_to(root_dir)
                stats["todo_count"] += len(todo_matches)
                stats["files_with_todos"].append((str(rel_path), len(todo_matches)))

        except Exception as e:
            print(f"Error reading {py_file}: {e}")
            continue

    return stats


if __name__ == "__main__":
    root = Path(__file__).parent.parent

    print("=" * 60)
    print("FINAL PROJECT AUDIT (Backend Directory Only)")
    print("=" * 60)

    stats = audit_project(root)

    print(f"\nTotal Python files scanned: {stats['total_files']}")
    print(f"\n🔴 except:pass blocks: {stats['except_pass_count']}")
    print(f"🟡 TODO markers: {stats['todo_count']}")

    if stats["files_with_except_pass"]:
        print("\nTop 10 files with except:pass:")
        sorted_files = sorted(
            stats["files_with_except_pass"], key=lambda x: x[1], reverse=True
        )
        for filepath, count in sorted_files[:10]:
            print(f"  {filepath}: {count}")

    if stats["files_with_todos"]:
        print("\nTop 10 files with TODOs:")
        sorted_todos = sorted(
            stats["files_with_todos"], key=lambda x: x[1], reverse=True
        )
        for filepath, count in sorted_todos[:10]:
            print(f"  {filepath}: {count}")

    print(f"\n{'=' * 60}")
    print("✅ Audit complete")
    print(f"{'=' * 60}")
