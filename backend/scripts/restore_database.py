"""
Week 1, Day 4: Database Restore Script
Restore PostgreSQL database from backup file
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.backup_service import BackupService
from backend.core.logging_config import get_logger

logger = get_logger(__name__)


def main():
    """Main restore execution function"""
    parser = argparse.ArgumentParser(
        description="Restore PostgreSQL database from backup"
    )
    parser.add_argument(
        "backup_file",
        help="Path to backup file (local) or filename (cloud)"
    )
    parser.add_argument(
        "--from-cloud",
        action="store_true",
        help="Download backup from cloud storage"
    )
    parser.add_argument(
        "--target-db",
        help="Target database name (default: current database)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available backups instead of restoring"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify backup, don't restore"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force restore without confirmation"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("DATABASE RESTORE - AUTOMATED EXECUTION")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    try:
        # Initialize backup service
        backup_service = BackupService()
        
        # List backups if requested
        if args.list:
            logger.info("\nListing available backups...")
            
            backups = backup_service.list_backups(location="all")
            
            if backups.get('local'):
                logger.info(f"\n{'=' * 80}")
                logger.info("LOCAL BACKUPS")
                logger.info(f"{'=' * 80}")
                
                for i, backup in enumerate(backups['local'], 1):
                    logger.info(f"\n{i}. {backup['filename']}")
                    logger.info(f"   Size: {backup['size_mb']} MB")
                    logger.info(f"   Modified: {backup['modified']}")
                    logger.info(f"   Path: {backup['path']}")
            
            if backups.get('cloud'):
                logger.info(f"\n{'=' * 80}")
                logger.info("CLOUD BACKUPS")
                logger.info(f"{'=' * 80}")
                
                for i, backup in enumerate(backups['cloud'], 1):
                    logger.info(f"\n{i}. {backup['filename']}")
                    logger.info(f"   Size: {backup['size_mb']} MB")
                    logger.info(f"   Modified: {backup['modified']}")
                    logger.info(f"   Storage Class: {backup['storage_class']}")
                    logger.info(f"   Key: {backup['key']}")
            
            if not backups.get('local') and not backups.get('cloud'):
                logger.warning("No backups found")
            
            return 0
        
        # Determine backup file path
        if args.from_cloud:
            logger.info(f"\nDownloading backup from cloud: {args.backup_file}")
            
            # Download from cloud
            local_path = Path(backup_service.backup_dir) / args.backup_file
            
            cloud_key = f"{backup_service.backup_prefix}{args.backup_file}"
            
            backup_service.s3_client.download_file(
                backup_service.backup_bucket,
                cloud_key,
                str(local_path)
            )
            
            logger.info(f"✅ Downloaded to: {local_path}")
            backup_path = local_path
        else:
            backup_path = Path(args.backup_file)
            
            if not backup_path.is_absolute():
                # Try to find in backup directory
                backup_path = Path(backup_service.backup_dir) / backup_path
        
        if not backup_path.exists():
            logger.error(f"❌ Backup file not found: {backup_path}")
            return 1
        
        logger.info(f"\nBackup file: {backup_path}")
        logger.info(f"Size: {backup_path.stat().st_size / (1024*1024):.2f} MB")
        
        # Verify backup
        logger.info(f"\n{'=' * 80}")
        logger.info("STEP 1: Verifying backup integrity")
        logger.info(f"{'=' * 80}")
        
        if not backup_service.verify_backup(backup_path):
            logger.error("❌ Backup verification failed")
            return 1
        
        logger.info("✅ Backup verification passed")
        
        if args.verify_only:
            logger.info("\n✅ Verify-only mode: Backup is valid")
            return 0
        
        # Confirmation
        target_db = args.target_db or backup_service.db_name
        
        if not args.force:
            logger.warning(f"\n⚠️  WARNING: This will restore database '{target_db}'")
            logger.warning("All existing data will be replaced!")
            
            response = input("\nContinue? (yes/no): ")
            
            if response.lower() != "yes":
                logger.info("Restore cancelled by user")
                return 0
        
        # Restore backup
        logger.info(f"\n{'=' * 80}")
        logger.info("STEP 2: Restoring database")
        logger.info(f"{'=' * 80}")
        logger.info(f"Target database: {target_db}")
        logger.info(f"Backup file: {backup_path.name}")
        
        restore_metadata = backup_service.restore_backup(
            backup_path,
            target_db=target_db
        )
        
        logger.info(f"\n{'=' * 80}")
        logger.info("✅ RESTORE COMPLETED SUCCESSFULLY")
        logger.info(f"{'=' * 80}")
        logger.info(f"Database: {restore_metadata['target_database']}")
        logger.info(f"Duration: {restore_metadata['duration_seconds']}s")
        logger.info(f"Timestamp: {restore_metadata['timestamp']}")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n{'=' * 80}")
        logger.error(f"❌ RESTORE FAILED: {e}")
        logger.error(f"{'=' * 80}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
