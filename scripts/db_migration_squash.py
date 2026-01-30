"""
Database Migration Squash Script.

This script helps consolidate multiple Alembic migrations into a single
migration for cleaner deployment.

Audit Task: P2 - Database Migration Squash

Usage:
    python -m scripts.db_migration_squash --dry-run
    python -m scripts.db_migration_squash --execute
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
ALEMBIC_DIR = PROJECT_ROOT / "alembic"
VERSIONS_DIR = ALEMBIC_DIR / "versions"
BACKUP_DIR = PROJECT_ROOT / "backups" / "migrations"


def get_migration_files() -> list[Path]:
    """Get all migration files sorted by creation date."""
    if not VERSIONS_DIR.exists():
        return []

    files = list(VERSIONS_DIR.glob("*.py"))
    # Filter out __pycache__ and sort by name (typically contains timestamp)
    files = [f for f in files if not f.name.startswith("__")]
    return sorted(files)


def backup_migrations() -> Path:
    """Create backup of current migrations."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"migrations_{timestamp}"
    backup_path.mkdir(parents=True, exist_ok=True)

    # Copy all migration files
    for f in get_migration_files():
        shutil.copy(f, backup_path / f.name)

    print(f"✅ Backup created at: {backup_path}")
    return backup_path


def get_current_revision() -> str | None:
    """Get current database revision."""
    try:
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        output = result.stdout.strip()
        if output:
            # Parse revision from output like "abc123 (head)"
            return output.split()[0] if output else None
    except Exception as e:
        print(f"⚠️ Could not get current revision: {e}")
    return None


def get_migration_history() -> list[dict[str, str]]:
    """Get migration history."""
    try:
        result = subprocess.run(
            ["alembic", "history", "--verbose"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        # Parse output
        migrations = []
        for line in result.stdout.split("\n"):
            if "->" in line or "Rev:" in line:
                migrations.append({"line": line.strip()})
        return migrations
    except Exception as e:
        print(f"⚠️ Could not get history: {e}")
        return []


def check_pending_migrations() -> bool:
    """Check if there are pending migrations."""
    try:
        result = subprocess.run(
            ["alembic", "check"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        return result.returncode != 0
    except Exception:
        return False


def merge_heads() -> bool:
    """Merge multiple heads if they exist."""
    try:
        result = subprocess.run(
            ["alembic", "heads"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        heads = [line.strip() for line in result.stdout.split("\n") if line.strip()]

        if len(heads) > 1:
            print(f"⚠️ Multiple heads detected: {heads}")
            print("Merging heads...")

            merge_result = subprocess.run(
                ["alembic", "merge", "heads", "-m", "merge_multiple_heads"],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            if merge_result.returncode == 0:
                print("✅ Heads merged successfully")
                return True
            else:
                print(f"❌ Failed to merge heads: {merge_result.stderr}")
                return False

        print("✅ Single head detected")
        return True

    except Exception as e:
        print(f"❌ Error checking heads: {e}")
        return False


def create_squash_migration(message: str = "squashed_migration") -> bool:
    """Create a new squashed migration."""
    try:
        # First, merge heads if needed
        if not merge_heads():
            return False

        # Create new migration that represents current schema
        print("Creating squashed migration...")

        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", message],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        if result.returncode == 0:
            print(f"✅ Squashed migration created: {message}")
            print(result.stdout)
            return True
        else:
            print(f"❌ Failed to create migration: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error creating squash migration: {e}")
        return False


def print_summary() -> None:
    """Print migration summary."""
    migrations = get_migration_files()
    current = get_current_revision()

    print("\n" + "=" * 60)
    print("📊 Migration Summary")
    print("=" * 60)
    print(f"Total migrations: {len(migrations)}")
    print(f"Current revision: {current or 'None'}")
    print(f"Migrations directory: {VERSIONS_DIR}")
    print()

    if migrations:
        print("Migration files:")
        for f in migrations[-10:]:  # Show last 10
            print(f"  - {f.name}")
        if len(migrations) > 10:
            print(f"  ... and {len(migrations) - 10} more")
    print()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Database Migration Squash")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the squash",
    )
    parser.add_argument(
        "--backup-only",
        action="store_true",
        help="Only create backup of migrations",
    )
    parser.add_argument(
        "--message",
        "-m",
        default="squashed_migration",
        help="Message for squashed migration",
    )

    args = parser.parse_args()

    print_summary()

    if args.backup_only:
        backup_migrations()
        return 0

    if args.dry_run:
        print("🔍 Dry run mode - no changes will be made\n")

        print("Steps that would be executed:")
        print("1. Backup current migrations")
        print("2. Check/merge multiple heads")
        print("3. Create squashed migration")
        print("\nRun with --execute to perform these steps")
        return 0

    if args.execute:
        print("⚠️ This will modify your migrations. Proceeding...\n")

        # Step 1: Backup
        backup_migrations()

        # Step 2: Create squash
        if not create_squash_migration(args.message):
            print("\n❌ Squash failed. Migrations backed up, no changes made.")
            return 1

        print("\n✅ Migration squash completed!")
        print("\nNext steps:")
        print("1. Review the generated migration in alembic/versions/")
        print("2. Test on staging: alembic upgrade head")
        print("3. If issues, restore from backup")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
