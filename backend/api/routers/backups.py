"""
Week 1, Day 4: Backup Management API Endpoints
RESTful API for database backup operations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from backend.services.backup_service import BackupService
from backend.core.logging_config import get_logger

router = APIRouter(prefix="/backups", tags=["backups"])
logger = get_logger(__name__)


# Global backup service instance
_backup_service: Optional[BackupService] = None


def get_backup_service() -> BackupService:
    """Get or create backup service instance"""
    global _backup_service
    if _backup_service is None:
        _backup_service = BackupService()
    return _backup_service


@router.post("/create", response_model=Dict[str, Any])
async def create_backup(
    background_tasks: BackgroundTasks,
    backup_type: str = "daily",
    compress: bool = True,
    upload: bool = True,
    apply_retention: bool = True
):
    """
    Create database backup.
    
    Args:
        backup_type: Backup type (daily/weekly/monthly)
        compress: Enable gzip compression
        upload: Upload to cloud storage
        apply_retention: Apply retention policy after backup
        
    Returns:
        Backup metadata
    """
    try:
        service = get_backup_service()
        
        logger.info(f"Creating {backup_type} backup via API")
        
        # Create backup
        backup_metadata = service.create_backup(
            backup_type=backup_type,
            compress=compress
        )
        
        # Upload in background if requested
        if upload:
            backup_path = Path(backup_metadata['path'])
            
            def upload_task():
                try:
                    upload_metadata = service.upload_to_cloud(backup_path)
                    logger.info(f"Background upload completed: {upload_metadata['key']}")
                except Exception as e:
                    logger.error(f"Background upload failed: {e}")
            
            background_tasks.add_task(upload_task)
            backup_metadata['upload_scheduled'] = True
        
        # Apply retention in background if requested
        if apply_retention:
            def retention_task():
                try:
                    result = service.apply_retention_policy()
                    logger.info(
                        f"Retention policy applied: "
                        f"{result['deleted_local_count']} local, "
                        f"{result['deleted_cloud_count']} cloud deleted"
                    )
                except Exception as e:
                    logger.error(f"Retention policy failed: {e}")
            
            background_tasks.add_task(retention_task)
            backup_metadata['retention_scheduled'] = True
        
        return {
            "success": True,
            "backup": backup_metadata,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create backup: {str(e)}"
        )


@router.get("/list", response_model=Dict[str, Any])
async def list_backups(location: str = "all"):
    """
    List available backups.
    
    Args:
        location: Where to list backups (local/cloud/all)
        
    Returns:
        List of backups with metadata
    """
    try:
        service = get_backup_service()
        
        backups = service.list_backups(location=location)
        
        # Calculate totals
        local_count = len(backups.get('local', []))
        local_size_mb = sum(b['size_mb'] for b in backups.get('local', []))
        
        cloud_count = len(backups.get('cloud', []))
        cloud_size_mb = sum(b['size_mb'] for b in backups.get('cloud', []))
        
        return {
            "success": True,
            "backups": backups,
            "summary": {
                "local_count": local_count,
                "local_size_mb": round(local_size_mb, 2),
                "cloud_count": cloud_count,
                "cloud_size_mb": round(cloud_size_mb, 2),
                "total_count": local_count + cloud_count,
                "total_size_mb": round(local_size_mb + cloud_size_mb, 2)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list backups: {str(e)}"
        )


@router.post("/verify/{filename}", response_model=Dict[str, Any])
async def verify_backup(filename: str):
    """
    Verify backup file integrity.
    
    Args:
        filename: Backup filename (in local backup directory)
        
    Returns:
        Verification result
    """
    try:
        service = get_backup_service()
        
        backup_path = service.backup_dir / filename
        
        if not backup_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup file not found: {filename}"
            )
        
        logger.info(f"Verifying backup: {filename}")
        
        is_valid = service.verify_backup(backup_path)
        
        return {
            "success": True,
            "filename": filename,
            "valid": is_valid,
            "size_mb": round(backup_path.stat().st_size / (1024*1024), 2),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backup verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify backup: {str(e)}"
        )


@router.post("/retention/apply", response_model=Dict[str, Any])
async def apply_retention_policy():
    """
    Manually apply retention policy to backups.
    
    Returns:
        Deletion statistics
    """
    try:
        service = get_backup_service()
        
        logger.info("Applying retention policy via API")
        
        result = service.apply_retention_policy()
        
        return {
            "success": True,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Retention policy failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply retention policy: {str(e)}"
        )


@router.get("/config", response_model=Dict[str, Any])
async def get_backup_config():
    """
    Get current backup configuration.
    
    Returns:
        Backup service configuration
    """
    try:
        service = get_backup_service()
        
        return {
            "success": True,
            "config": {
                "backup_dir": str(service.backup_dir),
                "cloud_provider": service.cloud_provider,
                "backup_bucket": service.backup_bucket,
                "backup_prefix": service.backup_prefix,
                "retention": {
                    "daily_days": service.retention_days,
                    "weekly_weeks": service.retention_weeks,
                    "monthly_months": service.retention_months
                },
                "database": {
                    "host": service.db_host,
                    "port": service.db_port,
                    "name": service.db_name,
                    "user": service.db_user
                }
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get backup config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backup config: {str(e)}"
        )


@router.post("/upload/{filename}", response_model=Dict[str, Any])
async def upload_backup_to_cloud(filename: str):
    """
    Upload local backup to cloud storage.
    
    Args:
        filename: Local backup filename
        
    Returns:
        Upload metadata
    """
    try:
        service = get_backup_service()
        
        backup_path = service.backup_dir / filename
        
        if not backup_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup file not found: {filename}"
            )
        
        logger.info(f"Uploading backup to cloud: {filename}")
        
        upload_metadata = service.upload_to_cloud(backup_path)
        
        return {
            "success": True,
            "upload": upload_metadata,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cloud upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload backup: {str(e)}"
        )


@router.delete("/{filename}", response_model=Dict[str, Any])
async def delete_backup(filename: str, location: str = "local"):
    """
    Delete backup file.
    
    Args:
        filename: Backup filename
        location: Where to delete (local/cloud)
        
    Returns:
        Deletion confirmation
    """
    try:
        service = get_backup_service()
        
        if location == "local":
            backup_path = service.backup_dir / filename
            
            if not backup_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Backup file not found: {filename}"
                )
            
            backup_path.unlink()
            logger.info(f"Deleted local backup: {filename}")
            
        elif location == "cloud" and service.cloud_provider == "s3":
            cloud_key = f"{service.backup_prefix}{filename}"
            
            service.s3_client.delete_object(
                Bucket=service.backup_bucket,
                Key=cloud_key
            )
            logger.info(f"Deleted cloud backup: {cloud_key}")
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid location: {location}"
            )
        
        return {
            "success": True,
            "filename": filename,
            "location": location,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backup deletion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete backup: {str(e)}"
        )


@router.get("/status", response_model=Dict[str, Any])
async def get_backup_status():
    """
    Get overall backup system status.
    
    Returns:
        Status summary including disk space, latest backup, etc.
    """
    try:
        service = get_backup_service()
        
        # List all backups
        backups = service.list_backups(location="all")
        
        # Get latest backup
        latest_local = None
        if backups.get('local'):
            latest_local = max(
                backups['local'],
                key=lambda b: b['modified']
            )
        
        latest_cloud = None
        if backups.get('cloud'):
            latest_cloud = max(
                backups['cloud'],
                key=lambda b: b['modified']
            )
        
        # Check disk space
        import shutil
        disk_usage = shutil.disk_usage(service.backup_dir)
        
        return {
            "success": True,
            "status": {
                "backup_dir": str(service.backup_dir),
                "local_backups": len(backups.get('local', [])),
                "cloud_backups": len(backups.get('cloud', [])),
                "latest_local": latest_local,
                "latest_cloud": latest_cloud,
                "disk_usage": {
                    "total_gb": round(disk_usage.total / (1024**3), 2),
                    "used_gb": round(disk_usage.used / (1024**3), 2),
                    "free_gb": round(disk_usage.free / (1024**3), 2),
                    "percent_used": round((disk_usage.used / disk_usage.total) * 100, 1)
                },
                "cloud_provider": service.cloud_provider,
                "retention_policy": {
                    "daily_days": service.retention_days,
                    "weekly_weeks": service.retention_weeks,
                    "monthly_months": service.retention_months
                }
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get backup status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backup status: {str(e)}"
        )
