"""
Prompt Logs Database Backup Script

Automated backup for prompt_logs.db:
- Daily backups with timestamp
- Rotation (keep last 30 days)
- Compression (optional)
- Restore functionality

Usage:
    python scripts/backup_prompt_logs.py backup
    python scripts/backup_prompt_logs.py restore --backup-file backup_2026-03-03.db
    python scripts/backup_prompt_logs.py rotate --keep-days 30
"""

import argparse
import gzip
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

# Configuration
DEFAULT_DB_PATH = "data/prompt_logs.db"
DEFAULT_BACKUP_DIR = "data/backups"
DEFAULT_KEEP_DAYS = 30
DEFAULT_COMPRESS = True


def get_backup_filename(timestamp: datetime | None = None, compress: bool = True) -> str:
    """Generate backup filename."""
    if timestamp is None:
        timestamp = datetime.utcnow()

    ext = ".db.gz" if compress else ".db"
    return f"prompt_logs_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}{ext}"


def backup_database(
    db_path: str = DEFAULT_DB_PATH,
    backup_dir: str = DEFAULT_BACKUP_DIR,
    compress: bool = DEFAULT_COMPRESS,
) -> str:
    """
    Backup prompt logs database.

    Args:
        db_path: Path to source database
        backup_dir: Directory for backups
        compress: Compress backup with gzip

    Returns:
        Path to backup file
    """
    # Ensure directories exist
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        logger.warning(f"Database not found: {db_path}")
        return ""

    # Generate backup filename
    backup_filename = get_backup_filename(compress=compress)
    backup_path = backup_dir / backup_filename

    logger.info(f"Starting backup: {db_path} → {backup_path}")

    try:
        # Ensure DB is in consistent state
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()

        if compress:
            # Compress backup
            with open(db_path, "rb") as f_in, gzip.open(backup_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        else:
            # Copy file
            shutil.copy2(db_path, backup_path)

        # Get backup size
        backup_size = backup_path.stat().st_size
        size_mb = backup_size / (1024 * 1024)

        logger.info(f"✅ Backup completed: {backup_filename} ({size_mb:.2f} MB)")

        return str(backup_path)

    except Exception as e:
        logger.error(f"❌ Backup failed: {e}")
        raise


def restore_database(
    backup_path: str,
    db_path: str = DEFAULT_DB_PATH,
) -> bool:
    """
    Restore prompt logs database from backup.

    Args:
        backup_path: Path to backup file
        db_path: Path to restore to

    Returns:
        True if successful
    """
    backup_path = Path(backup_path)
    db_path = Path(db_path)

    if not backup_path.exists():
        logger.error(f"Backup file not found: {backup_path}")
        return False

    logger.info(f"Starting restore: {backup_path} → {db_path}")

    try:
        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Backup current DB if exists
        if db_path.exists():
            timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
            old_backup = db_path.parent / f"prompt_logs_pre_restore_{timestamp}.db"
            shutil.copy2(db_path, old_backup)
            logger.info(f"Current DB backed up to: {old_backup}")

        # Restore from backup
        if str(backup_path).endswith(".gz"):
            # Decompress
            with gzip.open(backup_path, "rb") as f_in, open(db_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        else:
            # Copy file
            shutil.copy2(backup_path, db_path)

        logger.info("✅ Restore completed successfully")

        # Verify restore
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prompt_logs")
        count = cursor.fetchone()[0]
        conn.close()

        logger.info(f"Verified: {count} records in restored database")

        return True

    except Exception as e:
        logger.error(f"❌ Restore failed: {e}")
        return False


def rotate_backups(
    backup_dir: str = DEFAULT_BACKUP_DIR,
    keep_days: int = DEFAULT_KEEP_DAYS,
) -> int:
    """
    Remove old backups.

    Args:
        backup_dir: Directory with backups
        keep_days: Days to keep

    Returns:
        Number of deleted backups
    """
    backup_dir = Path(backup_dir)

    if not backup_dir.exists():
        logger.warning(f"Backup directory not found: {backup_dir}")
        return 0

    cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
    deleted_count = 0

    logger.info(f"Rotating backups: keeping {keep_days} days")

    for backup_file in backup_dir.glob("prompt_logs_*.db*"):
        # Parse timestamp from filename
        try:
            # Format: prompt_logs_YYYY-MM-DD_HH-MM-SS.db[.gz]
            timestamp_str = backup_file.stem.replace("prompt_logs_", "")
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")

            if timestamp < cutoff_date:
                backup_file.unlink()
                deleted_count += 1
                logger.debug(f"Deleted old backup: {backup_file.name}")

        except ValueError as e:
            logger.warning(f"Could not parse timestamp from {backup_file.name}: {e}")

    logger.info(f"✅ Rotation completed: {deleted_count} backups deleted")

    return deleted_count


def list_backups(backup_dir: str = DEFAULT_BACKUP_DIR) -> list[dict]:
    """
    List available backups.

    Args:
        backup_dir: Directory with backups

    Returns:
        List of backup info dicts
    """
    backup_dir = Path(backup_dir)

    if not backup_dir.exists():
        return []

    backups = []

    for backup_file in sorted(backup_dir.glob("prompt_logs_*.db*")):
        try:
            # Parse timestamp
            timestamp_str = backup_file.stem.replace("prompt_logs_", "")
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")

            # Get size
            size_mb = backup_file.stat().st_size / (1024 * 1024)

            backups.append(
                {
                    "filename": backup_file.name,
                    "path": str(backup_file),
                    "timestamp": timestamp.isoformat(),
                    "size_mb": round(size_mb, 2),
                    "compressed": str(backup_file).endswith(".gz"),
                }
            )

        except ValueError:
            continue

    return sorted(backups, key=lambda x: x["timestamp"], reverse=True)


def print_backups(backup_dir: str = DEFAULT_BACKUP_DIR) -> None:
    """Print available backups in table format."""
    backups = list_backups(backup_dir)

    if not backups:
        print("No backups found")
        return

    print(f"\n{'Filename':<50} {'Timestamp':<25} {'Size (MB)':<10} {'Compressed':<10}")
    print("-" * 95)

    for backup in backups:
        compressed = "Yes" if backup["compressed"] else "No"
        print(f"{backup['filename']:<50} {backup['timestamp']:<25} {backup['size_mb']:<10.2f} {compressed:<10}")

    print(f"\nTotal: {len(backups)} backups")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Prompt Logs Database Backup")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Create backup")
    backup_parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Database path")
    backup_parser.add_argument("--dir", default=DEFAULT_BACKUP_DIR, help="Backup directory")
    backup_parser.add_argument("--no-compress", action="store_true", help="Don't compress")

    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument("--backup-file", required=True, help="Backup file to restore")
    restore_parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Database path")

    # Rotate command
    rotate_parser = subparsers.add_parser("rotate", help="Remove old backups")
    rotate_parser.add_argument("--dir", default=DEFAULT_BACKUP_DIR, help="Backup directory")
    rotate_parser.add_argument("--keep-days", type=int, default=DEFAULT_KEEP_DAYS, help="Days to keep")

    # List command
    list_parser = subparsers.add_parser("list", help="List backups")
    list_parser.add_argument("--dir", default=DEFAULT_BACKUP_DIR, help="Backup directory")

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

    # Execute command
    if args.command == "backup":
        backup_path = backup_database(db_path=args.db, backup_dir=args.dir, compress=not args.no_compress)
        if backup_path:
            print(f"✅ Backup created: {backup_path}")
        else:
            print("❌ Backup failed")
            sys.exit(1)

    elif args.command == "restore":
        success = restore_database(backup_path=args.backup_file, db_path=args.db)
        if success:
            print("✅ Restore completed successfully")
        else:
            print("❌ Restore failed")
            sys.exit(1)

    elif args.command == "rotate":
        deleted = rotate_backups(backup_dir=args.dir, keep_days=args.keep_days)
        print(f"✅ Deleted {deleted} old backups")

    elif args.command == "list":
        print_backups(backup_dir=args.dir)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
