"""
Find and fix internal duplicate function declarations in JS files
"""

import re
from collections import defaultdict
from pathlib import Path

PAGES_DIR = Path(__file__).parent / "js" / "pages"


def find_all_functions(content):
    """Find all function declarations and their positions"""
    # Pattern to find function declarations
    pattern = r"\bfunction\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\("

    functions = defaultdict(list)
    for match in re.finditer(pattern, content):
        func_name = match.group(1)
        line_num = content[: match.start()].count("\n") + 1
        functions[func_name].append(
            {"line": line_num, "start": match.start(), "end": match.end()}
        )

    return functions


def remove_duplicate_function(content, func_name, occurrences):
    """Remove the second occurrence of a duplicate function"""
    if len(occurrences) < 2:
        return content, False

    # Keep the first occurrence, remove subsequent ones
    for occ in occurrences[1:]:
        line = occ["line"]
        start = occ["start"]

        # Find the function keyword start
        func_keyword_start = content.rfind("\n", 0, start)
        if func_keyword_start == -1:
            func_keyword_start = 0
        else:
            func_keyword_start += 1  # Skip the newline

        # Find the opening brace
        brace_start = content.find("{", start)
        if brace_start == -1:
            continue

        # Find the matching closing brace
        brace_count = 1
        pos = brace_start + 1
        while brace_count > 0 and pos < len(content):
            if content[pos] == "{":
                brace_count += 1
            elif content[pos] == "}":
                brace_count -= 1
            pos += 1

        func_end = pos

        # Look back for any preceding comment
        search_back = max(0, func_keyword_start - 100)
        preceding = content[search_back:func_keyword_start]

        # Check for single-line comment
        last_newline = preceding.rfind("\n")
        if last_newline != -1:
            potential_comment = preceding[last_newline + 1 :].strip()
            if potential_comment.startswith("//"):
                func_keyword_start = search_back + last_newline + 1

        # Replace the duplicate with a comment
        replacement = (
            f"\n        // REMOVED DUPLICATE: {func_name} (was at line {line})\n"
        )

        # Make the replacement
        new_content = content[:func_keyword_start] + replacement + content[func_end:]

        return new_content, True

    return content, False


def process_file(filepath):
    """Process a single JS file"""
    print(f"\n📄 Processing: {filepath.name}")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    functions = find_all_functions(content)

    # Find duplicates
    duplicates = {name: occs for name, occs in functions.items() if len(occs) > 1}

    if not duplicates:
        print("  No internal duplicates found")
        return False

    print(f"  Found {len(duplicates)} duplicated functions:")
    for name, occs in duplicates.items():
        lines = [str(o["line"]) for o in occs]
        print(f"    - {name}: lines {', '.join(lines)}")

    # Fix duplicates
    changes_made = False
    for func_name, occs in duplicates.items():
        content, changed = remove_duplicate_function(content, func_name, occs)
        if changed:
            changes_made = True
            print(f"  ✅ Removed duplicate: {func_name}")

    if changes_made:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    return changes_made


def main():
    print("🔧 Fixing Internal Duplicate Function Declarations")
    print("=" * 50)

    if not PAGES_DIR.exists():
        print(f"❌ Pages directory not found: {PAGES_DIR}")
        return

    js_files = list(PAGES_DIR.glob("*.js"))
    print(f"Found {len(js_files)} JS files")

    fixed_count = 0
    for filepath in js_files:
        if process_file(filepath):
            fixed_count += 1

    print("\n" + "=" * 50)
    print(f"✅ Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
