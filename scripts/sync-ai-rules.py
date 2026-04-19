#!/usr/bin/env python3
"""
Sync AI Rules Script.

Synchronizes the unified .ai/ structure to IDE-specific locations:
- .cursor/rules/ (for Cursor IDE)
- .github/instructions/ and .github/prompts/ (for GitHub Copilot)

Usage:
    python scripts/sync-ai-rules.py [--dry-run] [--verbose]

The .ai/ directory is the single source of truth for all AI rules.
"""

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


def sync_to_cursor(source_dir: Path, dry_run: bool = False, verbose: bool = False) -> int:
    """Sync .ai/rules/ to .cursor/rules/"""
    cursor_rules = source_dir.parent / ".cursor" / "rules"
    ai_rules = source_dir / "rules"

    if not ai_rules.exists():
        print(f"⚠️  Source directory not found: {ai_rules}")
        return 0

    if not dry_run:
        cursor_rules.mkdir(parents=True, exist_ok=True)

    synced = 0
    for rule_file in ai_rules.glob("*.md"):
        target = cursor_rules / rule_file.name
        if verbose:
            print(f"  📄 {rule_file.name} → .cursor/rules/")
        if not dry_run:
            shutil.copy2(rule_file, target)
        synced += 1

    # Also sync path-specific rules
    ai_path_specific = source_dir / "path-specific"
    if ai_path_specific.exists():
        for rule_file in ai_path_specific.glob("*.md"):
            target = cursor_rules / f"path-{rule_file.name}"
            if verbose:
                print(f"  📄 {rule_file.name} → .cursor/rules/path-{rule_file.name}")
            if not dry_run:
                shutil.copy2(rule_file, target)
            synced += 1

    return synced


def sync_to_copilot(source_dir: Path, dry_run: bool = False, verbose: bool = False) -> int:
    """Sync .ai/ to .github/ for Copilot"""
    github_dir = source_dir.parent / ".github"
    github_instructions = github_dir / "instructions"
    github_prompts = github_dir / "prompts"

    if not dry_run:
        github_instructions.mkdir(parents=True, exist_ok=True)
        github_prompts.mkdir(parents=True, exist_ok=True)

    synced = 0

    # Sync path-specific as instructions with applyTo header
    ai_path_specific = source_dir / "path-specific"
    apply_to_mapping = {
        "strategies.md": "**/strategies/**/*.py",
        "api-connectors.md": "**/adapters/**/*.py",
        "backtester.md": "**/backtesting/**/*.py",
        "api-endpoints.md": "**/api/**/*.py",
        "tests.md": "**/tests/**/*.py",
    }

    if ai_path_specific.exists():
        for rule_file in ai_path_specific.glob("*.md"):
            target = github_instructions / f"{rule_file.stem}.instructions.md"
            apply_to = apply_to_mapping.get(rule_file.name, "**/*.py")

            if verbose:
                print(f"  📄 {rule_file.name} → .github/instructions/{target.name}")

            if not dry_run:
                content = rule_file.read_text(encoding="utf-8")
                # Remove existing "Applies to:" line if present
                lines = content.split("\n")
                filtered_lines = [line for line in lines if not line.startswith("**Applies to:**")]
                content = "\n".join(filtered_lines)

                # Add YAML frontmatter with applyTo
                frontmatter = f'---\napplyTo: "{apply_to}"\n---\n\n'
                target.write_text(frontmatter + content.lstrip(), encoding="utf-8")
            synced += 1

    # Sync prompts
    ai_prompts = source_dir / "prompts"
    if ai_prompts.exists():
        for prompt_file in ai_prompts.glob("*.md"):
            target = github_prompts / f"{prompt_file.stem}.prompt.md"
            if verbose:
                print(f"  📄 {prompt_file.name} → .github/prompts/{target.name}")
            if not dry_run:
                shutil.copy2(prompt_file, target)
            synced += 1

    # Generate combined copilot-instructions.md from rules
    ai_rules = source_dir / "rules"
    if ai_rules.exists():
        combined_content = generate_combined_copilot_instructions(ai_rules)
        copilot_main = github_dir / "copilot-instructions.md"
        if verbose:
            print("  📄 Combined rules → .github/copilot-instructions.md")
        if not dry_run:
            copilot_main.write_text(combined_content, encoding="utf-8")
        synced += 1

    return synced


def generate_combined_copilot_instructions(rules_dir: Path) -> str:
    """Generate combined copilot-instructions.md from modular rules."""
    header = f"""# Bybit Strategy Tester v2 - Copilot Instructions

> **Auto-generated from .ai/rules/ on {datetime.now().strftime("%Y-%m-%d %H:%M")}**
> Edit source files in .ai/rules/, then run `python scripts/sync-ai-rules.py`

"""

    content_parts = [header]

    # Read rules in order (01-, 02-, etc.)
    rule_files = sorted(rules_dir.glob("*.md"))
    for rule_file in rule_files:
        rule_content = rule_file.read_text(encoding="utf-8")
        content_parts.append(rule_content)
        content_parts.append("\n---\n\n")

    return "".join(content_parts)


def main():
    parser = argparse.ArgumentParser(description="Sync .ai/ rules to IDE-specific locations")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--cursor-only", action="store_true", help="Only sync to Cursor")
    parser.add_argument("--copilot-only", action="store_true", help="Only sync to Copilot")
    args = parser.parse_args()

    project_root = get_project_root()
    ai_dir = project_root / ".ai"

    if not ai_dir.exists():
        print(f"❌ .ai/ directory not found at {ai_dir}")
        return 1

    print(f"🔄 Syncing AI rules from {ai_dir}")
    if args.dry_run:
        print("   (DRY RUN - no changes will be made)")
    print()

    total_synced = 0

    # Sync to Cursor
    if not args.copilot_only:
        print("📁 Syncing to .cursor/rules/...")
        count = sync_to_cursor(ai_dir, args.dry_run, args.verbose)
        print(f"   ✅ {count} files synced")
        total_synced += count

    # Sync to Copilot
    if not args.cursor_only:
        print("📁 Syncing to .github/...")
        count = sync_to_copilot(ai_dir, args.dry_run, args.verbose)
        print(f"   ✅ {count} files synced")
        total_synced += count

    print()
    print(f"✨ Total: {total_synced} files synced")

    if args.dry_run:
        print("\nRun without --dry-run to apply changes.")

    return 0


if __name__ == "__main__":
    exit(main())
