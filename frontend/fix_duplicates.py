"""
Fix duplicate function declarations in JS modules
Removes local function declarations that conflict with imports
"""

import re
from pathlib import Path

PAGES_DIR = Path(__file__).parent / "js" / "pages"

# Functions that are imported from utils.js and may be duplicated locally
IMPORTED_FUNCTIONS = [
    "formatCurrency",
    "formatNumber",
    "formatDate",
    "formatPercent",
    "debounce",
    "throttle",
    "sanitizeHtml",
    "escapeHtml",
]


def find_and_remove_duplicates(content, filename):
    """Find and remove duplicate function declarations"""
    changes = []

    # Check what's imported
    import_match = re.search(
        r"import\s+\{([^}]+)\}\s+from\s+'\.\.\/utils\.js'", content
    )
    if not import_match:
        return content, changes

    imported = [f.strip() for f in import_match.group(1).split(",")]

    for func_name in imported:
        func_name = func_name.strip()
        if not func_name:
            continue

        # Find local function declarations
        # Match patterns like: function formatDate(...)  or  function formatDate (...)
        pattern = rf"(\s*)function\s+{re.escape(func_name)}\s*\([^)]*\)\s*\{{[^}}]*(?:\{{[^}}]*\}}[^}}]*)*\}}"

        matches = list(re.finditer(pattern, content, re.DOTALL))

        if matches:
            for match in matches:
                # Get context around the function to understand its scope
                start = match.start()
                # match.end() not used - brace counting determines actual end

                # Find the balanced braces for the function body
                func_start = content.find("{", start)
                brace_count = 1
                pos = func_start + 1
                while brace_count > 0 and pos < len(content):
                    if content[pos] == "{":
                        brace_count += 1
                    elif content[pos] == "}":
                        brace_count -= 1
                    pos += 1

                # content[start:pos] is the full function text (for future use)

                # Check if it's a standalone function (not inside another function)
                # Count brace levels before this function
                preceding = content[:start]
                open_braces = preceding.count("{") - preceding.count("}")

                # Only remove if it looks like a module-level duplicate
                changes.append(
                    f"  Found duplicate: {func_name} (brace level: {open_braces})"
                )

                # Remove the function and any preceding comment
                # Look back for comment
                search_start = max(0, start - 200)
                preceding_section = content[search_start:start]

                # Find the comment if any
                comment_pattern = r"//[^\n]*\n\s*$|/\*[^*]*\*+(?:[^/*][^*]*\*+)*/\s*$"
                comment_match = re.search(comment_pattern, preceding_section)

                actual_start = start
                if comment_match:
                    actual_start = search_start + comment_match.start()

                # Replace with a comment noting the removal
                replacement = (
                    f"\n        // {func_name} - using imported version from utils.js\n"
                )

                content = content[:actual_start] + replacement + content[pos:]
                changes.append(f"  Removed duplicate function: {func_name}")

    return content, changes


def process_file(filepath):
    """Process a single JS file"""
    print(f"\n📄 Processing: {filepath.name}")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Simple approach: remove duplicate function declarations
    import_match = re.search(
        r"import\s+\{([^}]+)\}\s+from\s+'\.\.\/utils\.js'", content
    )
    if not import_match:
        print("  No utils.js imports found, skipping")
        return False

    imported = [f.strip() for f in import_match.group(1).split(",")]
    imported = [f for f in imported if f]  # Remove empty strings

    changes_made = False

    for func_name in imported:
        # Pattern to match function declaration with its body
        # This is a simplified pattern that should work for most cases
        patterns = [
            # Regular function
            rf"(\n\s*)function\s+{re.escape(func_name)}\s*\([^)]*\)\s*\{{",
            # With comment before
            rf"(\n\s*//[^\n]*\n\s*)function\s+{re.escape(func_name)}\s*\([^)]*\)\s*\{{",
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                # Find the start of the function
                func_start = match.end() - 1  # Position of opening brace

                # Find matching closing brace
                brace_count = 1
                pos = func_start + 1
                while brace_count > 0 and pos < len(content):
                    if content[pos] == "{":
                        brace_count += 1
                    elif content[pos] == "}":
                        brace_count -= 1
                    pos += 1

                # Get the full function text
                full_match_start = match.start()
                full_match_end = pos

                removed_text = content[full_match_start:full_match_end]

                # Replace with comment
                replacement = (
                    f"\n        // {func_name} - using imported version from utils.js"
                )
                content = (
                    content[:full_match_start] + replacement + content[full_match_end:]
                )

                print(
                    f"  ✅ Removed duplicate: {func_name} ({len(removed_text)} chars)"
                )
                changes_made = True
                break  # Move to next function

    if changes_made:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    else:
        print("  No duplicates found")
        return False


def main():
    print("🔧 Fixing Duplicate Function Declarations")
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
