#!/usr/bin/env python3
"""
🔄 HTML CSS Updater - Bybit Strategy Tester v2

Updates HTML files to use external CSS and removes inline styles.
Part of Phase 1 Week 2: Extract CSS

Usage:
    python update_html_css.py [--dry-run] [--file dashboard.html]

@version 1.0.0
@date 2025-12-21
"""

import argparse
import re
import shutil
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BACKUP_DIR = SCRIPT_DIR / "backups" / "css_extraction"


def backup_file(filepath: Path) -> Path:
    """Create backup of the file."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{filepath.stem}_{timestamp}{filepath.suffix}"

    shutil.copy2(filepath, backup_path)
    return backup_path


def get_css_filename(html_filename: str) -> str:
    """Get corresponding CSS filename for HTML file."""
    stem = html_filename.replace(".html", "").replace("-", "_")
    return f"{stem}.css"


def remove_style_blocks(html: str) -> tuple[str, int]:
    """
    Remove all <style>...</style> blocks from HTML.

    Returns: (modified_html, count_removed)
    """
    pattern = r"<style[^>]*>.*?</style>\s*"
    matches = list(re.finditer(pattern, html, re.DOTALL | re.IGNORECASE))

    if not matches:
        return html, 0

    # Remove all style blocks
    modified_html = re.sub(pattern, "", html, flags=re.DOTALL | re.IGNORECASE)

    return modified_html, len(matches)


def add_common_css_link(html: str) -> tuple[str, bool]:
    """
    Add link to common.css if not already present.

    Returns: (modified_html, was_added)
    """
    if "common.css" in html:
        return html, False

    # Insert after components.css link
    pattern = r"(<link[^>]*components\.css[^>]*>)"
    match = re.search(pattern, html)

    if match:
        insert_pos = match.end()
        link_tag = '\n    <link rel="stylesheet" href="/frontend/css/common.css">'
        html = html[:insert_pos] + link_tag + html[insert_pos:]
        return html, True

    return html, False


def ensure_page_css_link(html: str, css_filename: str) -> tuple[str, bool]:
    """
    Ensure page-specific CSS is linked.

    Returns: (modified_html, was_added)
    """
    if css_filename in html:
        return html, False

    # Insert after common.css (or components.css if common.css not present)
    if "common.css" in html:
        pattern = r"(<link[^>]*common\.css[^>]*>)"
    else:
        pattern = r"(<link[^>]*components\.css[^>]*>)"

    match = re.search(pattern, html)

    if match:
        insert_pos = match.end()
        link_tag = f'\n    <link rel="stylesheet" href="/frontend/css/{css_filename}">'
        html = html[:insert_pos] + link_tag + html[insert_pos:]
        return html, True

    return html, False


def clean_empty_lines(html: str) -> str:
    """Remove excessive empty lines."""
    # Replace 3+ newlines with 2
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html


def process_html_file(filepath: Path, dry_run: bool = False) -> dict:
    """
    Process single HTML file.

    Returns dict with results.
    """
    print(f"\n📄 Processing: {filepath.name}")

    # Read file
    with open(filepath, encoding="utf-8") as f:
        original_html = f.read()

    html = original_html
    changes = []

    # 1. Add common.css link
    html, common_added = add_common_css_link(html)
    if common_added:
        changes.append("Added common.css link")

    # 2. Ensure page-specific CSS link
    css_filename = get_css_filename(filepath.name)
    html, page_css_added = ensure_page_css_link(html, css_filename)
    if page_css_added:
        changes.append(f"Added {css_filename} link")

    # 3. Remove inline style blocks
    html, styles_removed = remove_style_blocks(html)
    if styles_removed > 0:
        changes.append(f"Removed {styles_removed} inline style block(s)")

    # 4. Clean up empty lines
    html = clean_empty_lines(html)

    # Report changes
    if not changes:
        print("    ℹ️  No changes needed")
        return {"status": "unchanged", "changes": []}

    for change in changes:
        print(f"    ✏️  {change}")

    if dry_run:
        print("    🔍 [DRY RUN] Would apply changes")
        return {"status": "dry_run", "changes": changes}

    # Backup and save
    backup_path = backup_file(filepath)
    print(f"    💾 Backup: {backup_path.name}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print("    ✅ Updated successfully")

    # Report size reduction
    original_size = len(original_html)
    new_size = len(html)
    reduction = original_size - new_size
    reduction_pct = (reduction / original_size) * 100 if original_size > 0 else 0

    print(
        f"    📊 Size: {original_size:,} → {new_size:,} bytes (-{reduction:,}, -{reduction_pct:.1f}%)"
    )

    return {
        "status": "updated",
        "changes": changes,
        "original_size": original_size,
        "new_size": new_size,
        "reduction": reduction,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Update HTML files to use external CSS"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without applying"
    )
    parser.add_argument("--file", type=str, help="Process single file")
    args = parser.parse_args()

    print("=" * 60)
    print("🔄 HTML CSS Updater - Phase 1 Week 2")
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

    # Process files
    results = []
    total_reduction = 0

    for filepath in sorted(html_files):
        result = process_html_file(filepath, dry_run=args.dry_run)
        results.append(result)
        total_reduction += result.get("reduction", 0)

    # Summary
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)

    updated = sum(1 for r in results if r["status"] == "updated")
    unchanged = sum(1 for r in results if r["status"] == "unchanged")

    print(f"✅ Updated: {updated} files")
    print(f"⏭️  Unchanged: {unchanged} files")

    if total_reduction > 0:
        print(
            f"📉 Total size reduction: {total_reduction:,} bytes ({total_reduction / 1024:.1f} KB)"
        )

    if args.dry_run:
        print("\n💡 Run without --dry-run to apply changes")
    else:
        print("\n💡 Backups saved in 'backups/css_extraction' folder")

    print("=" * 60)


if __name__ == "__main__":
    main()
