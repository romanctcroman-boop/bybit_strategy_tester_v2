"""
Week 1, Day 4: Automated Backup Script
Execute database backup and upload to cloud storage
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
    """Main backup execution function"""
    parser = argparse.ArgumentParser(
        description="Automated PostgreSQL backup with cloud upload"
    )
    parser.add_argument(
        "--type",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="Backup type (determines retention)"
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Disable compression"
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip cloud upload"
    )
    parser.add_argument(
        "--no-retention",
        action="store_true",
        help="Skip retention policy application"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify backup after creation"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode (no actual backup, just validation)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("DATABASE BACKUP - AUTOMATED EXECUTION")
    logger.info(f"Backup type: {args.type}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    try:
        # Initialize backup service
        backup_service = BackupService()
        
        if args.test:
            logger.info("TEST MODE - Validating configuration")
            
            # Test database connection
            import psycopg
            from backend.database import engine
            
            with engine.connect() as conn:
                result = conn.execute("SELECT version()")
                version = result.fetchone()[0]
                logger.info(f"✅ Database connection OK: {version}")
            
            # Test cloud credentials
            if not args.no_upload:
                backups = backup_service.list_backups(location="cloud")
                logger.info(f"✅ Cloud storage OK: {len(backups.get('cloud', []))} backups found")
            
            logger.info("✅ Configuration valid - test passed")
            return 0
        
        # Step 1: Create backup
        logger.info(f"\n{'=' * 80}")
        logger.info("STEP 1: Creating backup")
        logger.info(f"{'=' * 80}")
        
        backup_metadata = backup_service.create_backup(
            backup_type=args.type,
            compress=not args.no_compress
        )
        
        logger.info(f"✅ Backup created:")
        logger.info(f"   File: {backup_metadata['filename']}")
        logger.info(f"   Size: {backup_metadata['size_mb']} MB")
        logger.info(f"   Duration: {backup_metadata['duration_seconds']}s")
        
        backup_path = Path(backup_metadata['path'])
        
        # Step 2: Verify backup (optional)
        if args.verify:
            logger.info(f"\n{'=' * 80}")
            logger.info("STEP 2: Verifying backup")
            logger.info(f"{'=' * 80}")
            
            if backup_service.verify_backup(backup_path):
                logger.info("✅ Backup verification passed")
            else:
                logger.error("❌ Backup verification failed")
                return 1
        
        # Step 3: Upload to cloud
        if not args.no_upload:
            logger.info(f"\n{'=' * 80}")
            logger.info("STEP 3: Uploading to cloud storage")
            logger.info(f"{'=' * 80}")
            
            upload_metadata = backup_service.upload_to_cloud(backup_path)
            
            logger.info(f"✅ Backup uploaded:")
            logger.info(f"   Provider: {upload_metadata['provider']}")
            logger.info(f"   Bucket: {upload_metadata['bucket']}")
            logger.info(f"   Key: {upload_metadata['key']}")
            logger.info(f"   Size: {upload_metadata['size_mb']} MB")
            logger.info(f"   Duration: {upload_metadata['duration_seconds']}s")
        
        # Step 4: Apply retention policy
        if not args.no_retention:
            logger.info(f"\n{'=' * 80}")
            logger.info("STEP 4: Applying retention policy")
            logger.info(f"{'=' * 80}")
            
            retention_result = backup_service.apply_retention_policy()
            
            logger.info(f"✅ Retention policy applied:")
            logger.info(f"   Local backups deleted: {retention_result['deleted_local_count']}")
            logger.info(f"   Cloud backups deleted: {retention_result['deleted_cloud_count']}")
            
            if retention_result['deleted_local']:
                logger.info(f"   Deleted local: {', '.join(retention_result['deleted_local'][:5])}")
            if retention_result['deleted_cloud']:
                logger.info(f"   Deleted cloud: {', '.join(retention_result['deleted_cloud'][:5])}")
        
        # Step 5: List current backups
        logger.info(f"\n{'=' * 80}")
        logger.info("STEP 5: Current backup inventory")
        logger.info(f"{'=' * 80}")
        
        backups = backup_service.list_backups(location="all")
        
        logger.info(f"Local backups: {len(backups.get('local', []))}")
        if backups.get('local'):
            total_size_mb = sum(b['size_mb'] for b in backups['local'])
            logger.info(f"   Total size: {total_size_mb:.2f} MB")
        
        if 'cloud' in backups:
            logger.info(f"Cloud backups: {len(backups.get('cloud', []))}")
            if backups.get('cloud'):
                total_size_mb = sum(b['size_mb'] for b in backups['cloud'])
                logger.info(f"   Total size: {total_size_mb:.2f} MB")
        
        # Success summary
        logger.info(f"\n{'=' * 80}")
        logger.info("✅ BACKUP COMPLETED SUCCESSFULLY")
        logger.info(f"{'=' * 80}")
        logger.info(f"Backup file: {backup_metadata['filename']}")
        logger.info(f"Total time: {backup_metadata['duration_seconds']}s")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n{'=' * 80}")
        logger.error(f"❌ BACKUP FAILED: {e}")
        logger.error(f"{'=' * 80}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
