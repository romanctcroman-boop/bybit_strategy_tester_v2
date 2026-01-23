#!/usr/bin/env python3
"""
🎨 CSS Extractor - Bybit Strategy Tester v2

Extracts inline CSS from HTML files to external stylesheets.
Part of Phase 1 Week 2: Extract CSS

Usage:
    python extract_css.py [--dry-run] [--file dashboard.html]

@version 1.0.0
@date 2025-12-21
"""

import argparse
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CSS_DIR = SCRIPT_DIR / "css"


def extract_style_blocks(html: str) -> list[tuple[int, int, str]]:
    """
    Extract all <style>...</style> blocks from HTML.

    Returns list of tuples: (start_pos, end_pos, css_content)
    """
    pattern = r"<style[^>]*>(.*?)</style>"
    blocks = []

    for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
        blocks.append((match.start(), match.end(), match.group(1).strip()))

    return blocks


def analyze_css_rules(css: str) -> dict:
    """
    Analyze CSS content and categorize rules.

    Returns dict with categories:
    - variables: CSS custom properties (:root, [data-theme])
    - base: Reset and base styles (*, body, html)
    - layout: Layout styles (container, grid, flex)
    - components: Reusable components (buttons, cards, etc.)
    - page_specific: Page-specific styles
    """
    categories = {
        "variables": [],
        "base": [],
        "layout": [],
        "components": [],
        "page_specific": [],
        "animations": [],
    }

    # Simple regex to extract CSS rules
    # Match selector { ... }
    rule_pattern = r"([^{}]+)\{([^{}]+(?:\{[^{}]*\}[^{}]*)*)\}"

    for match in re.finditer(rule_pattern, css, re.DOTALL):
        selector = match.group(1).strip()
        properties = match.group(2).strip()
        full_rule = f"{selector} {{\n    {properties}\n}}"

        # Categorize by selector
        if ":root" in selector or "[data-theme" in selector or "--" in properties:
            categories["variables"].append(full_rule)
        elif (
            selector in ["*", "html", "body"]
            or selector.startswith("html")
            or selector.startswith("body")
        ):
            categories["base"].append(full_rule)
        elif "@keyframes" in selector:
            categories["animations"].append(full_rule)
        elif "@media" in selector:
            categories["layout"].append(full_rule)
        elif any(
            comp in selector
            for comp in [
                ".btn",
                ".card",
                ".badge",
                ".input",
                ".table",
                ".modal",
                ".toast",
                ".nav-",
            ]
        ):
            categories["components"].append(full_rule)
        elif any(
            layout in selector
            for layout in [".container", "-grid", ".row", ".col-", ".flex"]
        ):
            categories["layout"].append(full_rule)
        else:
            categories["page_specific"].append(full_rule)

    return categories


def clean_css(css: str) -> str:
    """Clean and format CSS."""
    # Remove excessive whitespace
    css = re.sub(r"\n\s*\n\s*\n", "\n\n", css)
    # Ensure consistent indentation
    css = css.strip()
    return css


def get_page_name(filepath: Path) -> str:
    """Get clean page name from filepath."""
    return filepath.stem.replace("-", "_")


def create_page_css(page_name: str, css_content: str) -> str:
    """Create page-specific CSS file content."""
    header = f"""/**
 * 📄 {page_name.replace("_", " ").title()} Page Styles
 *
 * Page-specific styles for {page_name}.html
 * Extracted during Phase 1 Week 2: CSS Extraction
 *
 * @version 1.0.0
 * @date {datetime.now().strftime("%Y-%m-%d")}
 */

/* Import shared variables and components */
@import 'variables.css';
@import 'components.css';

/* ============================================
   PAGE-SPECIFIC STYLES
   ============================================ */

"""
    return header + css_content


def find_duplicate_rules(all_css: dict[str, str]) -> dict:
    """
    Find duplicate CSS rules across files.

    Returns dict of {rule_hash: [filenames]}
    """
    rule_occurrences = defaultdict(list)

    for filename, css in all_css.items():
        # Extract individual rules
        rules = re.findall(r"([^{}]+\{[^{}]+\})", css, re.DOTALL)
        for rule in rules:
            # Normalize whitespace for comparison
            normalized = " ".join(rule.split())
            rule_occurrences[normalized].append(filename)

    # Filter to only duplicates
    duplicates = {k: v for k, v in rule_occurrences.items() if len(v) > 1}
    return duplicates


def extract_css_from_file(filepath: Path, dry_run: bool = False) -> dict:
    """
    Extract CSS from a single HTML file.

    Returns dict with extracted info.
    """
    print(f"\n📄 Processing: {filepath.name}")

    # Read file
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    # Extract style blocks
    style_blocks = extract_style_blocks(html)

    if not style_blocks:
        print("    ℹ️  No inline styles found")
        return {"status": "no_styles", "css": "", "lines_extracted": 0}

    print(f"    📦 Found {len(style_blocks)} style block(s)")

    # Combine all CSS
    all_css = "\n\n".join(block[2] for block in style_blocks)
    all_css = clean_css(all_css)

    lines_count = len(all_css.split("\n"))
    print(f"    📊 Total CSS lines: {lines_count}")

    # Analyze categories
    categories = analyze_css_rules(all_css)
    for cat, rules in categories.items():
        if rules:
            print(f"    📂 {cat}: {len(rules)} rules")

    # Get page name
    page_name = get_page_name(filepath)

    if dry_run:
        print(f"    🔍 [DRY RUN] Would create css/{page_name}.css")
        return {
            "status": "dry_run",
            "css": all_css,
            "lines_extracted": lines_count,
            "categories": categories,
        }

    # Create page CSS file
    css_filepath = CSS_DIR / f"{page_name}.css"
    page_css = create_page_css(page_name, all_css)

    with open(css_filepath, "w", encoding="utf-8") as f:
        f.write(page_css)

    print(f"    ✅ Created: css/{page_name}.css ({lines_count} lines)")

    return {
        "status": "extracted",
        "css": all_css,
        "css_file": css_filepath.name,
        "lines_extracted": lines_count,
        "categories": categories,
    }


def update_html_with_css_link(
    filepath: Path, css_filename: str, dry_run: bool = False
) -> bool:
    """
    Update HTML file to link external CSS and optionally remove inline styles.

    Returns True if modified.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    # Check if already linked
    if css_filename in html:
        print("    ℹ️  CSS already linked")
        return False

    # Add link after components.css
    link_tag = f'    <link rel="stylesheet" href="/frontend/css/{css_filename}">\n'

    # Find insertion point after components.css link
    pattern = r"(<link[^>]*components\.css[^>]*>)"
    match = re.search(pattern, html)

    if match:
        insert_pos = match.end()
        html = html[:insert_pos] + "\n" + link_tag + html[insert_pos:]
    else:
        # Fallback: insert before </head>
        html = html.replace("</head>", f"{link_tag}</head>")

    if dry_run:
        print(f"    🔍 [DRY RUN] Would add link to {css_filename}")
        return True

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"    🔗 Added link to {css_filename}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Extract inline CSS from HTML files")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without applying"
    )
    parser.add_argument("--file", type=str, help="Process single file")
    parser.add_argument(
        "--analyze-duplicates", action="store_true", help="Analyze duplicate rules"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🎨 CSS Extractor - Phase 1 Week 2")
    print("=" * 60)

    # Ensure CSS directory exists
    CSS_DIR.mkdir(exist_ok=True)

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
    results = {}
    total_lines = 0

    for filepath in sorted(html_files):
        result = extract_css_from_file(filepath, dry_run=args.dry_run)
        results[filepath.name] = result
        total_lines += result.get("lines_extracted", 0)

        # Update HTML with CSS link if extracted
        if result["status"] == "extracted":
            css_filename = result.get("css_file", f"{get_page_name(filepath)}.css")
            update_html_with_css_link(filepath, css_filename, dry_run=args.dry_run)

    # Summary
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)

    extracted_count = sum(
        1
        for r in results.values()
        if r["status"] in ["extracted", "dry_run"] and r.get("lines_extracted", 0) > 0
    )
    print(f"✅ Files with inline CSS: {extracted_count}/{len(html_files)}")
    print(f"📜 Total CSS lines extracted: {total_lines}")

    # Analyze duplicates if requested
    if args.analyze_duplicates:
        print("\n" + "=" * 60)
        print("🔄 Duplicate Analysis")
        print("=" * 60)

        all_css = {k: v["css"] for k, v in results.items() if v.get("css")}
        duplicates = find_duplicate_rules(all_css)

        if duplicates:
            print(f"Found {len(duplicates)} duplicate rules across files:")
            for rule, files in list(duplicates.items())[:10]:  # Show first 10
                short_rule = rule[:60] + "..." if len(rule) > 60 else rule
                print(f"  • {short_rule}")
                print(f"    In: {', '.join(files)}")
        else:
            print("No duplicates found!")

    if args.dry_run:
        print("\n💡 Run without --dry-run to apply changes")
    else:
        print("\n💡 Page-specific CSS files created in 'css' folder")

    print("=" * 60)


if __name__ == "__main__":
    main()
