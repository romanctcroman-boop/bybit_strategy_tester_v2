#!/usr/bin/env python3
"""
📜 JavaScript Extractor - Bybit Strategy Tester v2

Extracts inline JavaScript from HTML files to external ES6 modules.
Part of Phase 1 Week 3: Extract JavaScript

Usage:
    python extract_js.py [--dry-run] [--file dashboard.html] [--analyze]

@version 1.0.0
@date 2025-12-21
"""

import argparse
import re
import shutil
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
JS_DIR = SCRIPT_DIR / "js" / "pages"
BACKUP_DIR = SCRIPT_DIR / "backups" / "js_extraction"


def extract_script_blocks(html: str) -> list[tuple[int, int, str, dict]]:
    """
    Extract all inline <script>...</script> blocks from HTML.

    Returns list of tuples: (start_pos, end_pos, js_content, attributes)
    Excludes external scripts (with src attribute).
    """
    # Match script tags - both inline and external
    pattern = r"<script([^>]*)>(.*?)</script>"
    blocks = []

    for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
        attrs_str = match.group(1)
        content = match.group(2).strip()

        # Parse attributes
        attrs = {}
        for attr_match in re.finditer(r'(\w+)=["\']([^"\']*)["\']', attrs_str):
            attrs[attr_match.group(1)] = attr_match.group(2)

        # Skip external scripts (those with src attribute)
        if "src" in attrs:
            continue

        # Skip empty scripts
        if not content:
            continue

        blocks.append((match.start(), match.end(), content, attrs))

    return blocks


def analyze_js_content(js: str) -> dict:
    """
    Analyze JavaScript content for structure and patterns.

    Returns dict with:
    - functions: List of function names
    - async_functions: List of async function names
    - event_listeners: List of event listener patterns
    - api_calls: List of API endpoint patterns
    - globals: List of global variable declarations
    - classes: List of class names
    """
    analysis = {
        "functions": [],
        "async_functions": [],
        "event_listeners": [],
        "api_calls": [],
        "globals": [],
        "classes": [],
        "line_count": len(js.split("\n")),
    }

    # Functions: function name() or const name = function
    func_pattern = r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?function)"
    for match in re.finditer(func_pattern, js):
        name = match.group(1) or match.group(2)
        if name:
            analysis["functions"].append(name)

    # Async functions: async function name() or const name = async
    async_pattern = r"async\s+function\s+(\w+)|const\s+(\w+)\s*=\s*async"
    for match in re.finditer(async_pattern, js):
        name = match.group(1) or match.group(2)
        if name:
            analysis["async_functions"].append(name)

    # Event listeners
    listener_pattern = r'\.addEventListener\s*\(\s*[\'"](\w+)[\'"]'
    for match in re.finditer(listener_pattern, js):
        analysis["event_listeners"].append(match.group(1))

    # API calls
    api_pattern = r'fetch\s*\(\s*[`\'"]([^`\'"]+)[`\'"]'
    for match in re.finditer(api_pattern, js):
        analysis["api_calls"].append(match.group(1))

    # Global variables
    global_pattern = r"^(?:let|const|var)\s+(\w+)\s*="
    for match in re.finditer(global_pattern, js, re.MULTILINE):
        analysis["globals"].append(match.group(1))

    # Classes
    class_pattern = r"class\s+(\w+)"
    for match in re.finditer(class_pattern, js):
        analysis["classes"].append(match.group(1))

    return analysis


def get_page_name(filepath: Path) -> str:
    """Get clean page name from filepath."""
    return filepath.stem.replace("-", "_")


def convert_to_es6_module(js: str, page_name: str) -> str:
    """
    Convert inline JavaScript to ES6 module format.

    - Wrap in IIFE or class
    - Add imports for shared utilities
    - Export main functions
    """
    header = f"""/**
 * 📄 {page_name.replace("_", " ").title()} Page JavaScript
 *
 * Page-specific scripts for {page_name}.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 1.0.0
 * @date {datetime.now().strftime("%Y-%m-%d")}
 */

// Import shared utilities
import {{ apiClient, API_CONFIG }} from '../api.js';
import {{ formatNumber, formatCurrency, formatDate, debounce }} from '../utils.js';

"""

    # Analyze to find functions that should be exported
    analysis = analyze_js_content(js)
    exported_funcs = analysis.get("functions", [])[:5]  # Export first 5 functions

    footer = f"""
// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: {", ".join(exported_funcs) if exported_funcs else "none"}

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {{
    window.{page_name.replace("_", "")}Page = {{
        // Add public methods here
    }};
}}
"""

    return header + js + "\n" + footer


def create_page_js(page_name: str, js_content: str) -> str:
    """Create page-specific JS file content."""
    return convert_to_es6_module(js_content, page_name)


def extract_js_from_file(filepath: Path, dry_run: bool = False) -> dict:
    """
    Extract JavaScript from a single HTML file.

    Returns dict with extracted info.
    """
    print(f"\n📄 Processing: {filepath.name}")

    # Read file
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    # Extract script blocks
    script_blocks = extract_script_blocks(html)

    if not script_blocks:
        print("    ℹ️  No inline scripts found")
        return {"status": "no_scripts", "js": "", "lines_extracted": 0}

    print(f"    📦 Found {len(script_blocks)} inline script block(s)")

    # Combine all JS
    all_js = "\n\n".join(block[2] for block in script_blocks)
    lines_count = len(all_js.split("\n"))
    print(f"    📊 Total JS lines: {lines_count}")

    # Analyze content
    analysis = analyze_js_content(all_js)
    if analysis["functions"]:
        print(f"    🔧 Functions: {len(analysis['functions'])}")
    if analysis["async_functions"]:
        print(f"    ⚡ Async functions: {len(analysis['async_functions'])}")
    if analysis["event_listeners"]:
        print(f"    👂 Event listeners: {len(analysis['event_listeners'])}")
    if analysis["api_calls"]:
        print(f"    🌐 API calls: {len(analysis['api_calls'])}")

    # Get page name
    page_name = get_page_name(filepath)

    if dry_run:
        print(f"    🔍 [DRY RUN] Would create js/pages/{page_name}.js")
        return {
            "status": "dry_run",
            "js": all_js,
            "lines_extracted": lines_count,
            "analysis": analysis,
        }

    # Ensure JS pages directory exists
    JS_DIR.mkdir(parents=True, exist_ok=True)

    # Create page JS file
    js_filepath = JS_DIR / f"{page_name}.js"
    page_js = create_page_js(page_name, all_js)

    with open(js_filepath, "w", encoding="utf-8") as f:
        f.write(page_js)

    print(f"    ✅ Created: js/pages/{page_name}.js ({lines_count} lines)")

    return {
        "status": "extracted",
        "js": all_js,
        "js_file": f"pages/{page_name}.js",
        "lines_extracted": lines_count,
        "analysis": analysis,
    }


def update_html_with_js_link(
    filepath: Path, js_filename: str, dry_run: bool = False
) -> bool:
    """
    Update HTML file to link external JS module.

    Returns True if modified.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    # Check if already linked
    if js_filename in html:
        print("    ℹ️  JS already linked")
        return False

    # Add script tag before </body>
    script_tag = (
        f'    <script type="module" src="/frontend/js/{js_filename}"></script>\n'
    )

    html = html.replace("</body>", f"{script_tag}</body>")

    if dry_run:
        print(f"    🔍 [DRY RUN] Would add link to {js_filename}")
        return True

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"    🔗 Added link to {js_filename}")
    return True


def remove_inline_scripts(filepath: Path, dry_run: bool = False) -> tuple[bool, int]:
    """
    Remove inline script blocks from HTML file.

    Returns (was_modified, bytes_removed)
    """
    with open(filepath, "r", encoding="utf-8") as f:
        original_html = f.read()

    # Pattern to match inline scripts (not external with src)
    pattern = r"<script(?![^>]*\bsrc\b)[^>]*>.*?</script>\s*"

    modified_html = re.sub(pattern, "", original_html, flags=re.DOTALL | re.IGNORECASE)

    bytes_removed = len(original_html) - len(modified_html)

    if bytes_removed == 0:
        return False, 0

    if dry_run:
        print(f"    🔍 [DRY RUN] Would remove {bytes_removed} bytes of inline scripts")
        return True, bytes_removed

    # Backup and save
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{filepath.stem}_{timestamp}{filepath.suffix}"
    shutil.copy2(filepath, backup_path)
    print(f"    💾 Backup: {backup_path.name}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(modified_html)

    print(f"    ✂️  Removed {bytes_removed} bytes of inline scripts")

    return True, bytes_removed


def main():
    parser = argparse.ArgumentParser(
        description="Extract inline JavaScript from HTML files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without applying"
    )
    parser.add_argument("--file", type=str, help="Process single file")
    parser.add_argument(
        "--analyze", action="store_true", help="Analyze only, do not extract"
    )
    parser.add_argument(
        "--keep-inline", action="store_true", help="Do not remove inline scripts"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("📜 JavaScript Extractor - Phase 1 Week 3")
    print("=" * 60)

    # Get HTML files
    if args.file:
        html_files = [SCRIPT_DIR / args.file]
        if not html_files[0].exists():
            print(f"❌ File not found: {args.file}")
            return
    else:
        html_files = list(SCRIPT_DIR.glob("*.html"))

    print(f"📁 Found {len(html_files)} HTML files")

    if args.dry_run:
        print("\n⚠️ DRY RUN MODE - No files will be modified\n")

    if args.analyze:
        print("\n📊 ANALYZE MODE - Only analyzing, not extracting\n")

    # Process files
    results = {}
    total_lines = 0
    total_bytes_removed = 0

    for filepath in sorted(html_files):
        result = extract_js_from_file(filepath, dry_run=args.dry_run or args.analyze)
        results[filepath.name] = result
        total_lines += result.get("lines_extracted", 0)

        if not args.analyze and result["status"] == "extracted":
            # Update HTML with JS link
            js_filename = result.get("js_file", f"pages/{get_page_name(filepath)}.js")
            update_html_with_js_link(filepath, js_filename, dry_run=args.dry_run)

            # Remove inline scripts
            if not args.keep_inline:
                _, bytes_removed = remove_inline_scripts(filepath, dry_run=args.dry_run)
                total_bytes_removed += bytes_removed

    # Summary
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)

    extracted_count = sum(
        1
        for r in results.values()
        if r["status"] in ["extracted", "dry_run"] and r.get("lines_extracted", 0) > 0
    )
    print(f"✅ Files with inline JS: {extracted_count}/{len(html_files)}")
    print(f"📜 Total JS lines extracted: {total_lines}")

    if total_bytes_removed > 0:
        print(
            f"📉 Total bytes removed from HTML: {total_bytes_removed:,} ({total_bytes_removed / 1024:.1f} KB)"
        )

    # Show function summary
    all_functions = []
    all_async = []
    all_apis = []

    for result in results.values():
        if "analysis" in result:
            all_functions.extend(result["analysis"].get("functions", []))
            all_async.extend(result["analysis"].get("async_functions", []))
            all_apis.extend(result["analysis"].get("api_calls", []))

    if all_functions:
        print(f"\n🔧 Total functions found: {len(all_functions)}")
    if all_async:
        print(f"⚡ Total async functions: {len(all_async)}")
    if all_apis:
        print(f"🌐 Unique API endpoints: {len(set(all_apis))}")

    if args.dry_run or args.analyze:
        print("\n💡 Run without --dry-run to apply changes")
    else:
        print("\n💡 Page-specific JS files created in 'js/pages' folder")

    print("=" * 60)


if __name__ == "__main__":
    main()
