"""
Week 1, Day 4: Automated Database Backup Service
Production-grade PostgreSQL backup with cloud storage and retention management
"""

import os
import gzip
import shutil
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import boto3
from botocore.exceptions import ClientError

from backend.core.config import get_config
from backend.core.logging_config import get_logger

logger = get_logger(__name__)
config = get_config()


class BackupService:
    """
    Automated database backup service with cloud storage support.
    
    Features:
    - PostgreSQL pg_dump backups
    - Compression (gzip)
    - Cloud upload (S3/Azure/GCS)
    - Retention policy management
    - Backup verification
    - Restore functionality
    """
    
    def __init__(
        self,
        backup_dir: Optional[Path] = None,
        cloud_provider: str = "s3",
        retention_days: int = 7,
        retention_weeks: int = 4,
        retention_months: int = 12
    ):
        """
        Initialize backup service.
        
        Args:
            backup_dir: Local backup directory (default: ./backups)
            cloud_provider: Cloud storage provider (s3/azure/gcs)
            retention_days: Days to keep daily backups
            retention_weeks: Weeks to keep weekly backups
            retention_months: Months to keep monthly backups
        """
        self.backup_dir = backup_dir or Path("./backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.cloud_provider = cloud_provider
        self.retention_days = retention_days
        self.retention_weeks = retention_weeks
        self.retention_months = retention_months
        
        # Database configuration from environment
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "bybit_strategy_tester")
        self.db_user = os.getenv("DB_USER", "postgres")
        self.db_password = os.getenv("DB_PASSWORD", "")
        
        # Cloud storage configuration
        self.backup_bucket = os.getenv("BACKUP_BUCKET", "bybit-backups")
        self.backup_prefix = os.getenv("BACKUP_PREFIX", "backups/")
        
        # Initialize cloud client
        if self.cloud_provider == "s3":
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )
        
        logger.info(
            f"Backup service initialized: "
            f"dir={self.backup_dir}, provider={self.cloud_provider}, "
            f"retention={self.retention_days}d/{self.retention_weeks}w/{self.retention_months}m"
        )
    
    def create_backup(
        self,
        backup_type: str = "daily",
        compress: bool = True
    ) -> Dict[str, Any]:
        """
        Create PostgreSQL backup using pg_dump.
        
        Args:
            backup_type: Backup type (daily/weekly/monthly)
            compress: Whether to compress backup with gzip
            
        Returns:
            Dict with backup metadata:
            {
                "filename": str,
                "path": str,
                "size_bytes": int,
                "duration_seconds": float,
                "timestamp": str,
                "type": str,
                "compressed": bool
            }
        """
        start_time = datetime.now()
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        
        # Generate filename
        base_filename = f"backup_{backup_type}_{timestamp}.sql"
        if compress:
            filename = f"{base_filename}.gz"
        else:
            filename = base_filename
        
        filepath = self.backup_dir / filename
        
        logger.info(f"Starting {backup_type} backup: {filename}")
        
        try:
            # Create pg_dump command
            env = os.environ.copy()
            if self.db_password:
                env["PGPASSWORD"] = self.db_password
            
            dump_command = [
                "pg_dump",
                "-h", self.db_host,
                "-p", self.db_port,
                "-U", self.db_user,
                "-d", self.db_name,
                "-F", "c",  # Custom format (compressed, supports parallel restore)
                "--no-owner",  # Don't output commands to set ownership
                "--no-acl",  # Don't output commands to set access privileges
            ]
            
            if compress:
                # Pipe through gzip for additional compression
                dump_process = subprocess.Popen(
                    dump_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env
                )
                
                with gzip.open(filepath, 'wb') as gz_file:
                    shutil.copyfileobj(dump_process.stdout, gz_file)
                
                dump_process.wait()
                
                if dump_process.returncode != 0:
                    error = dump_process.stderr.read().decode()
                    raise RuntimeError(f"pg_dump failed: {error}")
            else:
                # Direct output to file
                with open(filepath, 'wb') as f:
                    result = subprocess.run(
                        dump_command,
                        stdout=f,
                        stderr=subprocess.PIPE,
                        env=env,
                        check=True
                    )
            
            # Get backup size
            size_bytes = filepath.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            metadata = {
                "filename": filename,
                "path": str(filepath),
                "size_bytes": size_bytes,
                "size_mb": round(size_mb, 2),
                "duration_seconds": round(duration, 2),
                "timestamp": start_time.isoformat(),
                "type": backup_type,
                "compressed": compress,
                "database": self.db_name,
                "host": self.db_host
            }
            
            logger.info(
                f"Backup created successfully: {filename} "
                f"({size_mb:.2f} MB, {duration:.2f}s)"
            )
            
            return metadata
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Backup failed: {error_msg}")
            raise RuntimeError(f"Failed to create backup: {error_msg}")
        except Exception as e:
            logger.error(f"Unexpected error during backup: {e}")
            raise
    
    def upload_to_cloud(self, filepath: Path) -> Dict[str, Any]:
        """
        Upload backup to cloud storage.
        
        Args:
            filepath: Local backup file path
            
        Returns:
            Dict with upload metadata
        """
        if not filepath.exists():
            raise FileNotFoundError(f"Backup file not found: {filepath}")
        
        filename = filepath.name
        cloud_key = f"{self.backup_prefix}{filename}"
        
        logger.info(f"Uploading backup to {self.cloud_provider}: {cloud_key}")
        
        start_time = datetime.now()
        
        try:
            if self.cloud_provider == "s3":
                self.s3_client.upload_file(
                    str(filepath),
                    self.backup_bucket,
                    cloud_key,
                    ExtraArgs={
                        'ServerSideEncryption': 'AES256',
                        'StorageClass': 'STANDARD_IA',  # Infrequent Access (cheaper)
                        'Metadata': {
                            'backup-date': datetime.now().isoformat(),
                            'database': self.db_name
                        }
                    }
                )
                
                # Verify upload
                response = self.s3_client.head_object(
                    Bucket=self.backup_bucket,
                    Key=cloud_key
                )
                
                duration = (datetime.now() - start_time).total_seconds()
                size_mb = response['ContentLength'] / (1024 * 1024)
                
                metadata = {
                    "provider": self.cloud_provider,
                    "bucket": self.backup_bucket,
                    "key": cloud_key,
                    "size_bytes": response['ContentLength'],
                    "size_mb": round(size_mb, 2),
                    "duration_seconds": round(duration, 2),
                    "etag": response['ETag'],
                    "storage_class": response.get('StorageClass', 'STANDARD_IA')
                }
                
                logger.info(
                    f"Backup uploaded successfully: {cloud_key} "
                    f"({size_mb:.2f} MB, {duration:.2f}s)"
                )
                
                return metadata
            
            else:
                raise NotImplementedError(
                    f"Cloud provider '{self.cloud_provider}' not yet implemented"
                )
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"Cloud upload failed ({error_code}): {e}")
            raise RuntimeError(f"Failed to upload backup: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            raise
    
    def verify_backup(self, filepath: Path) -> bool:
        """
        Verify backup integrity.
        
        Args:
            filepath: Backup file path
            
        Returns:
            True if backup is valid
        """
        logger.info(f"Verifying backup: {filepath.name}")
        
        try:
            # Check file exists and is not empty
            if not filepath.exists():
                logger.error(f"Backup file not found: {filepath}")
                return False
            
            if filepath.stat().st_size == 0:
                logger.error(f"Backup file is empty: {filepath}")
                return False
            
            # For gzipped files, verify gzip integrity
            if filepath.suffix == '.gz':
                with gzip.open(filepath, 'rb') as gz_file:
                    # Read first 1MB to verify format
                    gz_file.read(1024 * 1024)
            
            # Verify pg_dump custom format (if not compressed)
            # Note: Full verification would require pg_restore --list
            # which we skip here for performance
            
            logger.info(f"Backup verified successfully: {filepath.name}")
            return True
            
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False
    
    def apply_retention_policy(self) -> Dict[str, Any]:
        """
        Apply retention policy to local and cloud backups.
        
        Returns:
            Dict with deletion statistics
        """
        logger.info("Applying retention policy")
        
        now = datetime.now()
        deleted_local = []
        deleted_cloud = []
        
        # Get all local backups
        local_backups = sorted(self.backup_dir.glob("backup_*.sql*"))
        
        for backup_file in local_backups:
            # Parse backup timestamp from filename
            # Format: backup_<type>_YYYYMMDD_HHMMSS.sql.gz
            try:
                parts = backup_file.stem.replace('.sql', '').split('_')
                if len(parts) >= 4:
                    backup_type = parts[1]  # daily/weekly/monthly
                    date_str = parts[2]
                    time_str = parts[3]
                    
                    backup_date = datetime.strptime(
                        f"{date_str}_{time_str}",
                        "%Y%m%d_%H%M%S"
                    )
                    
                    age_days = (now - backup_date).days
                    
                    # Determine if backup should be deleted
                    should_delete = False
                    
                    if backup_type == "daily" and age_days > self.retention_days:
                        should_delete = True
                    elif backup_type == "weekly" and age_days > (self.retention_weeks * 7):
                        should_delete = True
                    elif backup_type == "monthly" and age_days > (self.retention_months * 30):
                        should_delete = True
                    
                    if should_delete:
                        logger.info(
                            f"Deleting old {backup_type} backup: {backup_file.name} "
                            f"(age: {age_days} days)"
                        )
                        backup_file.unlink()
                        deleted_local.append(backup_file.name)
                        
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse backup filename: {backup_file.name} - {e}")
        
        # Apply retention policy to cloud backups (S3)
        if self.cloud_provider == "s3":
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.backup_bucket,
                    Prefix=self.backup_prefix
                )
                
                if 'Contents' in response:
                    for obj in response['Contents']:
                        key = obj['Key']
                        filename = key.split('/')[-1]
                        
                        # Parse timestamp
                        try:
                            parts = filename.replace('.sql.gz', '').replace('.sql', '').split('_')
                            if len(parts) >= 4:
                                backup_type = parts[1]
                                last_modified = obj['LastModified'].replace(tzinfo=None)
                                age_days = (now - last_modified).days
                                
                                should_delete = False
                                
                                if backup_type == "daily" and age_days > self.retention_days:
                                    should_delete = True
                                elif backup_type == "weekly" and age_days > (self.retention_weeks * 7):
                                    should_delete = True
                                elif backup_type == "monthly" and age_days > (self.retention_months * 30):
                                    should_delete = True
                                
                                if should_delete:
                                    logger.info(f"Deleting old cloud backup: {key} (age: {age_days} days)")
                                    self.s3_client.delete_object(
                                        Bucket=self.backup_bucket,
                                        Key=key
                                    )
                                    deleted_cloud.append(key)
                                    
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Could not parse cloud backup filename: {filename} - {e}")
                            
            except ClientError as e:
                logger.error(f"Failed to apply cloud retention policy: {e}")
        
        result = {
            "deleted_local": deleted_local,
            "deleted_cloud": deleted_cloud,
            "deleted_local_count": len(deleted_local),
            "deleted_cloud_count": len(deleted_cloud)
        }
        
        logger.info(
            f"Retention policy applied: "
            f"{len(deleted_local)} local, {len(deleted_cloud)} cloud backups deleted"
        )
        
        return result
    
    def list_backups(self, location: str = "all") -> Dict[str, List[Dict[str, Any]]]:
        """
        List available backups.
        
        Args:
            location: Where to list backups (local/cloud/all)
            
        Returns:
            Dict with backup lists
        """
        result = {}
        
        if location in ["local", "all"]:
            local_backups = []
            for backup_file in sorted(self.backup_dir.glob("backup_*.sql*")):
                stat = backup_file.stat()
                local_backups.append({
                    "filename": backup_file.name,
                    "path": str(backup_file),
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            result["local"] = local_backups
        
        if location in ["cloud", "all"] and self.cloud_provider == "s3":
            try:
                cloud_backups = []
                response = self.s3_client.list_objects_v2(
                    Bucket=self.backup_bucket,
                    Prefix=self.backup_prefix
                )
                
                if 'Contents' in response:
                    for obj in response['Contents']:
                        cloud_backups.append({
                            "key": obj['Key'],
                            "filename": obj['Key'].split('/')[-1],
                            "size_bytes": obj['Size'],
                            "size_mb": round(obj['Size'] / (1024 * 1024), 2),
                            "modified": obj['LastModified'].isoformat(),
                            "storage_class": obj.get('StorageClass', 'STANDARD')
                        })
                
                result["cloud"] = cloud_backups
                
            except ClientError as e:
                logger.error(f"Failed to list cloud backups: {e}")
                result["cloud"] = []
        
        return result
    
    def restore_backup(
        self,
        backup_path: Path,
        target_db: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Restore database from backup.
        
        Args:
            backup_path: Path to backup file
            target_db: Target database name (default: current database)
            
        Returns:
            Dict with restore metadata
        """
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        target_db = target_db or self.db_name
        
        logger.info(f"Restoring backup to database '{target_db}': {backup_path.name}")
        
        start_time = datetime.now()
        
        try:
            env = os.environ.copy()
            if self.db_password:
                env["PGPASSWORD"] = self.db_password
            
            # Check if backup is gzipped
            if backup_path.suffix == '.gz':
                # Decompress and pipe to pg_restore
                with gzip.open(backup_path, 'rb') as gz_file:
                    restore_process = subprocess.Popen(
                        [
                            "pg_restore",
                            "-h", self.db_host,
                            "-p", self.db_port,
                            "-U", self.db_user,
                            "-d", target_db,
                            "--clean",  # Clean (drop) database objects before recreating
                            "--if-exists",  # Use IF EXISTS when dropping objects
                            "--no-owner",
                            "--no-acl"
                        ],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env
                    )
                    
                    shutil.copyfileobj(gz_file, restore_process.stdin)
                    restore_process.stdin.close()
                    restore_process.wait()
                    
                    if restore_process.returncode != 0:
                        error = restore_process.stderr.read().decode()
                        raise RuntimeError(f"pg_restore failed: {error}")
            else:
                # Direct restore
                subprocess.run(
                    [
                        "pg_restore",
                        "-h", self.db_host,
                        "-p", self.db_port,
                        "-U", self.db_user,
                        "-d", target_db,
                        "--clean",
                        "--if-exists",
                        "--no-owner",
                        "--no-acl",
                        str(backup_path)
                    ],
                    env=env,
                    check=True,
                    capture_output=True
                )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            metadata = {
                "backup_file": backup_path.name,
                "target_database": target_db,
                "duration_seconds": round(duration, 2),
                "timestamp": datetime.now().isoformat(),
                "success": True
            }
            
            logger.info(f"Backup restored successfully in {duration:.2f}s")
            
            return metadata
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Restore failed: {error_msg}")
            raise RuntimeError(f"Failed to restore backup: {error_msg}")
        except Exception as e:
            logger.error(f"Unexpected error during restore: {e}")
            raise


def create_backup_service(**kwargs) -> BackupService:
    """Factory function to create backup service"""
    return BackupService(**kwargs)
