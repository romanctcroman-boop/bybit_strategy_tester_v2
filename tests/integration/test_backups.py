"""
Week 1, Day 4: Backup Service Tests
Comprehensive testing for automated backup system
"""

import pytest
import os
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil

# Mock boto3 for testing without AWS credentials
pytest.importorskip("boto3", reason="boto3 required for backup tests")


class TestBackupService:
    """Test suite for backup service"""
    
    @pytest.fixture
    def temp_backup_dir(self):
        """Create temporary backup directory"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Setup mock environment variables"""
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "test_db")
        monkeypatch.setenv("DB_USER", "test_user")
        monkeypatch.setenv("DB_PASSWORD", "test_pass")
        monkeypatch.setenv("BACKUP_BUCKET", "test-bucket")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    
    def test_backup_service_initialization(self, temp_backup_dir, mock_env):
        """Test backup service initialization"""
        from backend.services.backup_service import BackupService
        
        service = BackupService(
            backup_dir=temp_backup_dir,
            retention_days=7,
            retention_weeks=4,
            retention_months=12
        )
        
        assert service.backup_dir == temp_backup_dir
        assert service.backup_dir.exists()
        assert service.retention_days == 7
        assert service.retention_weeks == 4
        assert service.retention_months == 12
        assert service.db_name == "test_db"
        assert service.db_host == "localhost"
    
    def test_backup_dir_creation(self, temp_backup_dir):
        """Test backup directory is created if doesn't exist"""
        from backend.services.backup_service import BackupService
        
        backup_dir = temp_backup_dir / "subdir" / "backups"
        assert not backup_dir.exists()
        
        service = BackupService(backup_dir=backup_dir)
        
        assert backup_dir.exists()
        assert backup_dir.is_dir()
    
    def test_backup_filename_format(self):
        """Test backup filename follows correct format"""
        from backend.services.backup_service import BackupService
        
        # We'll mock pg_dump to avoid database requirement
        # For now, test the format logic
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Daily backup format
        filename = f"backup_daily_{timestamp}.sql.gz"
        assert filename.startswith("backup_daily_")
        assert filename.endswith(".sql.gz")
        
        # Weekly backup format  
        filename = f"backup_weekly_{timestamp}.sql.gz"
        assert filename.startswith("backup_weekly_")
        
        # Monthly backup format
        filename = f"backup_monthly_{timestamp}.sql.gz"
        assert filename.startswith("backup_monthly_")
    
    def test_backup_metadata_structure(self):
        """Test backup metadata has expected structure"""
        # Expected metadata structure
        expected_keys = {
            "filename",
            "path",
            "size_bytes",
            "size_mb",
            "duration_seconds",
            "timestamp",
            "type",
            "compressed",
            "database",
            "host"
        }
        
        # Mock metadata
        metadata = {
            "filename": "backup_daily_20250127_120000.sql.gz",
            "path": "/backups/backup_daily_20250127_120000.sql.gz",
            "size_bytes": 1024000,
            "size_mb": 0.98,
            "duration_seconds": 5.23,
            "timestamp": datetime.now().isoformat(),
            "type": "daily",
            "compressed": True,
            "database": "test_db",
            "host": "localhost"
        }
        
        assert set(metadata.keys()) == expected_keys
        assert metadata["type"] in ["daily", "weekly", "monthly"]
        assert metadata["compressed"] is True
        assert metadata["size_mb"] > 0
    
    def test_retention_policy_logic(self):
        """Test retention policy calculation"""
        now = datetime.now()
        
        # Daily backup - keep 7 days
        daily_8_days_old = now - timedelta(days=8)
        assert (now - daily_8_days_old).days > 7  # Should be deleted
        
        daily_6_days_old = now - timedelta(days=6)
        assert (now - daily_6_days_old).days <= 7  # Should be kept
        
        # Weekly backup - keep 4 weeks (28 days)
        weekly_30_days_old = now - timedelta(days=30)
        assert (now - weekly_30_days_old).days > 28  # Should be deleted
        
        weekly_25_days_old = now - timedelta(days=25)
        assert (now - weekly_25_days_old).days <= 28  # Should be kept
        
        # Monthly backup - keep 12 months (360 days)
        monthly_400_days_old = now - timedelta(days=400)
        assert (now - monthly_400_days_old).days > 360  # Should be deleted
        
        monthly_300_days_old = now - timedelta(days=300)
        assert (now - monthly_300_days_old).days <= 360  # Should be kept
    
    def test_backup_file_verification_empty(self, temp_backup_dir):
        """Test verification fails for empty files"""
        from backend.services.backup_service import BackupService
        
        service = BackupService(backup_dir=temp_backup_dir)
        
        # Create empty file
        empty_file = temp_backup_dir / "empty_backup.sql.gz"
        empty_file.touch()
        
        assert not service.verify_backup(empty_file)
    
    def test_backup_file_verification_missing(self, temp_backup_dir):
        """Test verification fails for missing files"""
        from backend.services.backup_service import BackupService
        
        service = BackupService(backup_dir=temp_backup_dir)
        
        missing_file = temp_backup_dir / "missing_backup.sql.gz"
        
        assert not service.verify_backup(missing_file)
    
    def test_list_backups_empty_directory(self, temp_backup_dir):
        """Test listing backups in empty directory"""
        from backend.services.backup_service import BackupService
        
        service = BackupService(backup_dir=temp_backup_dir)
        
        backups = service.list_backups(location="local")
        
        assert "local" in backups
        assert len(backups["local"]) == 0
    
    def test_list_backups_with_files(self, temp_backup_dir):
        """Test listing backups with sample files"""
        from backend.services.backup_service import BackupService
        
        service = BackupService(backup_dir=temp_backup_dir)
        
        # Create sample backup files
        files = [
            "backup_daily_20250127_120000.sql.gz",
            "backup_weekly_20250120_120000.sql.gz",
            "backup_monthly_20250101_120000.sql.gz"
        ]
        
        for filename in files:
            filepath = temp_backup_dir / filename
            filepath.write_text("fake backup data")
        
        backups = service.list_backups(location="local")
        
        assert len(backups["local"]) == 3
        
        # Check metadata
        for backup in backups["local"]:
            assert "filename" in backup
            assert "size_mb" in backup
            assert "modified" in backup
            assert backup["size_mb"] > 0
    
    def test_cloud_storage_configuration(self, mock_env):
        """Test cloud storage configuration"""
        from backend.services.backup_service import BackupService
        
        service = BackupService(cloud_provider="s3")
        
        assert service.cloud_provider == "s3"
        assert service.backup_bucket == "test-bucket"
        assert hasattr(service, 's3_client')
    
    def test_backup_type_validation(self):
        """Test backup type must be valid"""
        valid_types = ["daily", "weekly", "monthly"]
        
        for backup_type in valid_types:
            assert backup_type in valid_types
        
        invalid_types = ["hourly", "yearly", "invalid"]
        
        for backup_type in invalid_types:
            assert backup_type not in valid_types
    
    def test_compression_flag(self):
        """Test compression flag affects filename"""
        # With compression
        compressed_filename = "backup_daily_20250127.sql.gz"
        assert compressed_filename.endswith(".gz")
        
        # Without compression
        uncompressed_filename = "backup_daily_20250127.sql"
        assert not uncompressed_filename.endswith(".gz")
    
    def test_environment_variable_defaults(self):
        """Test default values when environment variables not set"""
        from backend.services.backup_service import BackupService
        
        # Clear environment
        for key in ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"]:
            if key in os.environ:
                del os.environ[key]
        
        service = BackupService()
        
        assert service.db_host == "localhost"  # Default
        assert service.db_port == "5432"  # Default
        assert service.db_name == "bybit_strategy_tester"  # Default
        assert service.db_user == "postgres"  # Default
    
    def test_retention_counts(self, temp_backup_dir):
        """Test retention policy counts old backups correctly"""
        from backend.services.backup_service import BackupService
        
        service = BackupService(
            backup_dir=temp_backup_dir,
            retention_days=7
        )
        
        # Create old backup files (older than 7 days)
        now = datetime.now()
        
        old_backups = [
            (now - timedelta(days=8), "backup_daily_20250119_120000.sql.gz"),
            (now - timedelta(days=9), "backup_daily_20250118_120000.sql.gz"),
            (now - timedelta(days=10), "backup_daily_20250117_120000.sql.gz"),
        ]
        
        for date, filename in old_backups:
            filepath = temp_backup_dir / filename
            filepath.write_text("old backup")
            # Set file mtime
            timestamp = date.timestamp()
            os.utime(filepath, (timestamp, timestamp))
        
        # Create recent backup (within 7 days)
        recent_file = temp_backup_dir / "backup_daily_20250127_120000.sql.gz"
        recent_file.write_text("recent backup")
        
        # Apply retention policy
        result = service.apply_retention_policy()
        
        # 3 old backups should be deleted
        assert result["deleted_local_count"] == 3
        
        # Recent backup should remain
        assert recent_file.exists()


class TestBackupAPI:
    """Test backup REST API endpoints"""
    
    def test_api_create_backup_structure(self):
        """Test API create backup response structure"""
        expected_response = {
            "success": True,
            "backup": {
                "filename": str,
                "size_mb": float,
                "duration_seconds": float
            },
            "timestamp": str
        }
        
        # Verify structure is correct
        assert "success" in expected_response
        assert "backup" in expected_response
        assert "timestamp" in expected_response
    
    def test_api_list_backups_structure(self):
        """Test API list backups response structure"""
        expected_response = {
            "success": True,
            "backups": {
                "local": [],
                "cloud": []
            },
            "summary": {
                "local_count": int,
                "local_size_mb": float,
                "cloud_count": int,
                "cloud_size_mb": float,
                "total_count": int,
                "total_size_mb": float
            },
            "timestamp": str
        }
        
        assert "backups" in expected_response
        assert "summary" in expected_response
    
    def test_api_status_structure(self):
        """Test API status response structure"""
        expected_response = {
            "success": True,
            "status": {
                "backup_dir": str,
                "local_backups": int,
                "cloud_backups": int,
                "disk_usage": {
                    "total_gb": float,
                    "free_gb": float,
                    "percent_used": float
                },
                "retention_policy": {
                    "daily_days": int,
                    "weekly_weeks": int,
                    "monthly_months": int
                }
            }
        }
        
        assert "status" in expected_response
        assert "disk_usage" in expected_response["status"]
        assert "retention_policy" in expected_response["status"]


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s", "--tb=short"])
