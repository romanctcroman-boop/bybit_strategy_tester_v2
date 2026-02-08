#!/usr/bin/env python3
"""
🔧 HTML Updater - Bybit Strategy Tester v2

Updates all HTML files with:
- Content Security Policy meta tag
- Subresource Integrity (SRI) attributes on CDN resources
- External CSS/JS imports

Usage:
    python update_html_security.py [--dry-run] [--file dashboard.html]

@version 1.0.0
@date 2025-12-21
"""

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

# Load SRI hashes
SCRIPT_DIR = Path(__file__).parent
SRI_HASHES_FILE = SCRIPT_DIR / "sri_hashes.json"

# CSP Policy
CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; "
    "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
    "connect-src 'self' https://api.bybit.com wss://stream.bybit.com ws://localhost:* http://localhost:*; "
    "frame-src 'none'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

# Additional security headers as meta tags
SECURITY_META_TAGS = """    <!-- Security Headers -->
    <meta http-equiv="Content-Security-Policy" content="{csp}">
    <meta http-equiv="X-Content-Type-Options" content="nosniff">
    <meta http-equiv="X-Frame-Options" content="DENY">
    <meta name="referrer" content="strict-origin-when-cross-origin">
"""

# External CSS imports
EXTERNAL_CSS_IMPORTS = """    <!-- External CSS (Phase 1) -->
    <link rel="stylesheet" href="/frontend/css/variables.css">
    <link rel="stylesheet" href="/frontend/css/components.css">
"""


def load_sri_hashes() -> dict:
    """Load SRI hashes from JSON file."""
    if SRI_HASHES_FILE.exists():
        with open(SRI_HASHES_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def backup_file(filepath: Path) -> Path:
    """Create backup of the file."""
    backup_dir = filepath.parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{filepath.stem}_{timestamp}{filepath.suffix}"

    shutil.copy2(filepath, backup_path)
    return backup_path


def add_sri_to_script(html: str, sri_hashes: dict) -> str:
    """Add SRI attributes to CDN script tags."""

    for name, data in sri_hashes.items():
        if not data.get("integrity"):
            continue

        url = data["url"]
        integrity = data["integrity"]

        # If script already has integrity, skip
        if "integrity=" in html and url in html:
            # Check if this specific URL already has integrity
            check_pattern = (
                r'<script[^>]*src=["\']' + re.escape(url) + r'["\'][^>]*integrity='
            )
            if re.search(check_pattern, html):
                continue

        # Simple replacement - add integrity and crossorigin
        old_pattern = r'<script\s+src=["\']' + re.escape(url) + r'["\']'
        new_tag = f'<script src="{url}"\n        integrity="{integrity}"\n        crossorigin="anonymous"'

        html = re.sub(old_pattern, new_tag, html, count=1)

    return html


def add_sri_to_link(html: str, sri_hashes: dict) -> str:
    """Add SRI attributes to CDN link (CSS) tags."""

    for name, data in sri_hashes.items():
        if not data.get("integrity"):
            continue

        url = data["url"]
        integrity = data["integrity"]

        if not url.endswith(".css"):
            continue

        # If link already has integrity, skip
        if "integrity=" in html and url in html:
            check_pattern = (
                r'<link[^>]*href=["\']' + re.escape(url) + r'["\'][^>]*integrity='
            )
            if re.search(check_pattern, html):
                continue

        # Simple replacement - add integrity and crossorigin
        old_pattern = (
            r'<link\s+rel=["\']stylesheet["\']\s+href=["\']' + re.escape(url) + r'["\']'
        )
        new_tag = f'<link rel="stylesheet" href="{url}"\n      integrity="{integrity}"\n      crossorigin="anonymous"'

        html = re.sub(old_pattern, new_tag, html, count=1)

    return html


def add_csp_meta_tag(html: str) -> str:
    """Add CSP meta tag after charset meta."""

    # Check if CSP already exists
    if "Content-Security-Policy" in html:
        print("    ⚠️ CSP meta tag already exists")
        return html

    # Find position after viewport meta
    viewport_pattern = r'(<meta\s+name=["\']viewport["\'][^>]*>)'
    match = re.search(viewport_pattern, html)

    if match:
        insert_pos = match.end()
        security_tags = SECURITY_META_TAGS.format(csp=CSP_POLICY)
        html = html[:insert_pos] + "\n" + security_tags + html[insert_pos:]
    else:
        print("    ⚠️ Could not find viewport meta tag")

    return html


def add_external_css_imports(html: str) -> str:
    """Add external CSS imports after CDN CSS."""

    # Check if already imported
    if "/frontend/css/variables.css" in html:
        print("    ⚠️ External CSS already imported")
        return html

    # Find position after Bootstrap Icons link
    icons_pattern = r"(<link[^>]*bootstrap-icons[^>]*>)"
    match = re.search(icons_pattern, html)

    if match:
        insert_pos = match.end()
        html = html[:insert_pos] + "\n" + EXTERNAL_CSS_IMPORTS + html[insert_pos:]
    else:
        # Try to find after any CDN CSS
        css_pattern = r"(<link[^>]*cdn\.jsdelivr\.net[^>]*\.css[^>]*>)"
        matches = list(re.finditer(css_pattern, html))
        if matches:
            insert_pos = matches[-1].end()
            html = html[:insert_pos] + "\n" + EXTERNAL_CSS_IMPORTS + html[insert_pos:]
        else:
            print("    ⚠️ Could not find CDN CSS link")

    return html


def update_html_file(filepath: Path, sri_hashes: dict, dry_run: bool = False) -> bool:
    """
    Update single HTML file with security improvements.

    Returns True if file was modified.
    """
    print(f"\n📄 Processing: {filepath.name}")

    # Read file
    with open(filepath, encoding="utf-8") as f:
        original_html = f.read()

    html = original_html

    # 1. Add SRI to scripts
    html = add_sri_to_script(html, sri_hashes)

    # 2. Add SRI to CSS links
    html = add_sri_to_link(html, sri_hashes)

    # 3. Add CSP meta tag
    html = add_csp_meta_tag(html)

    # 4. Add external CSS imports
    html = add_external_css_imports(html)

    # Check if modified
    if html == original_html:
        print("    ✅ No changes needed")
        return False

    if dry_run:
        print("    🔍 [DRY RUN] Would make changes")
        # Show diff summary
        added_lines = len(html.split("\n")) - len(original_html.split("\n"))
        print(f"    📊 Lines added: {added_lines}")
        return True

    # Backup and save
    backup_path = backup_file(filepath)
    print(f"    💾 Backup: {backup_path.name}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print("    ✅ Updated successfully")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Update HTML files with security improvements"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without applying"
    )
    parser.add_argument("--file", type=str, help="Process single file")
    args = parser.parse_args()

    print("=" * 60)
    print("🔧 HTML Security Updater")
    print("=" * 60)

    # Load SRI hashes
    sri_hashes = load_sri_hashes()
    if not sri_hashes:
        print("❌ No SRI hashes found. Run generate_sri_hashes.py first.")
        return

    print(f"📦 Loaded {len(sri_hashes)} SRI hashes")

    # Get HTML files
    frontend_dir = SCRIPT_DIR

    if args.file:
        html_files = [frontend_dir / args.file]
        if not html_files[0].exists():
            print(f"❌ File not found: {args.file}")
            return
    else:
        html_files = list(frontend_dir.glob("*.html"))

    print(f"📁 Found {len(html_files)} HTML files")

    if args.dry_run:
        print("\n⚠️ DRY RUN MODE - No files will be modified\n")

    # Process files
    modified_count = 0
    for filepath in sorted(html_files):
        if update_html_file(filepath, sri_hashes, dry_run=args.dry_run):
            modified_count += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"✅ Done! Modified {modified_count}/{len(html_files)} files")

    if args.dry_run:
        print("\n💡 Run without --dry-run to apply changes")
    else:
        print("\n💡 Backups saved in 'backups' folder")

    print("=" * 60)


if __name__ == "__main__":
    main()
