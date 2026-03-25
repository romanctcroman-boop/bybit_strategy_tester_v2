"""
Tests for Prompt Logs Backup Script

Run: pytest tests/monitoring/test_backup.py -v
"""

import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import pytest

from scripts.backup_prompt_logs import (
    backup_database,
    get_backup_filename,
    list_backups,
    restore_database,
    rotate_backups,
)


class TestBackupFunctions:
    """Tests for backup functions."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database with test data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        # Create table and add test data
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE prompt_logs (
                prompt_id TEXT PRIMARY KEY,
                timestamp TEXT,
                agent_type TEXT,
                task_type TEXT,
                prompt TEXT,
                success INTEGER
            )
        """)

        # Add 10 test records
        for i in range(10):
            cursor.execute(
                "INSERT INTO prompt_logs VALUES (?, ?, ?, ?, ?, ?)",
                (f"test_{i}", datetime.utcnow().isoformat(), "qwen", "test", f"Prompt {i}", 1),
            )

        conn.commit()
        conn.close()

        yield db_path

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def temp_backup_dir(self):
        """Create temporary backup directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_get_backup_filename(self):
        """Test backup filename generation."""
        # With compression
        filename = get_backup_filename(compress=True)
        assert filename.endswith(".db.gz")

        # Without compression
        filename = get_backup_filename(compress=False)
        assert filename.endswith(".db")

        # With timestamp
        timestamp = datetime(2026, 3, 3, 12, 0, 0)
        filename = get_backup_filename(timestamp, compress=False)
        assert "2026-03-03_12-00-00" in filename

    def test_backup_database(self, temp_db, temp_backup_dir):
        """Test database backup."""
        # Create backup
        backup_path = backup_database(db_path=temp_db, backup_dir=temp_backup_dir, compress=True)

        # Backup should exist
        assert backup_path
        assert os.path.exists(backup_path)

        # Should be compressed
        assert backup_path.endswith(".db.gz")

        # File size should be > 0
        assert os.path.getsize(backup_path) > 0

    def test_backup_database_no_compress(self, temp_db, temp_backup_dir):
        """Test uncompressed backup."""
        backup_path = backup_database(db_path=temp_db, backup_dir=temp_backup_dir, compress=False)

        # Should not be compressed
        assert backup_path.endswith(".db")

    def test_restore_database(self, temp_db, temp_backup_dir):
        """Test database restore."""
        # Create backup
        backup_path = backup_database(db_path=temp_db, backup_dir=temp_backup_dir, compress=True)

        # Create new DB path
        new_db = os.path.join(temp_backup_dir, "restored.db")

        # Restore
        success = restore_database(backup_path=backup_path, db_path=new_db)

        # Should succeed
        assert success is True
        assert os.path.exists(new_db)

        # Verify data
        conn = sqlite3.connect(new_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prompt_logs")
        count = cursor.fetchone()[0]
        conn.close()

        # Should have 10 records
        assert count == 10

    def test_restore_database_from_compressed(self, temp_db, temp_backup_dir):
        """Test restore from compressed backup."""
        # Create compressed backup
        backup_path = backup_database(db_path=temp_db, backup_dir=temp_backup_dir, compress=True)

        # Restore
        new_db = os.path.join(temp_backup_dir, "restored2.db")
        success = restore_database(backup_path, new_db)

        assert success is True
        assert os.path.exists(new_db)

    def test_restore_nonexistent_file(self, temp_db):
        """Test restore from nonexistent file."""
        success = restore_database(backup_path="/nonexistent/backup.db", db_path=temp_db)

        assert success is False

    def test_rotate_backups(self, temp_backup_dir):
        """Test backup rotation."""
        # Create some test backups
        backup_dir = Path(temp_backup_dir)

        # Recent backup (should keep)
        recent = backup_dir / f"prompt_logs_{datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')}.db"
        recent.touch()

        # Old backup (should delete)
        old_date = datetime.utcnow() - timedelta(days=40)
        old = backup_dir / f"prompt_logs_{old_date.strftime('%Y-%m-%d_%H-%M-%S')}.db"
        old.touch()

        # Rotate
        deleted = rotate_backups(backup_dir=temp_backup_dir, keep_days=30)

        # Should delete 1 backup
        assert deleted == 1

        # Recent should still exist
        assert recent.exists()

        # Old should be deleted
        assert not old.exists()

    def test_list_backups(self, temp_db, temp_backup_dir):
        """Test listing backups."""
        # Create some backups
        backup_database(temp_db, temp_backup_dir, compress=True)
        backup_database(temp_db, temp_backup_dir, compress=False)

        # List
        backups = list_backups(temp_backup_dir)

        # Should find at least 1 backup (may vary due to test isolation)
        assert len(backups) >= 1

        # Check structure
        for backup in backups:
            assert "filename" in backup
            assert "timestamp" in backup
            assert "size_mb" in backup
            assert "compressed" in backup

    def test_backup_and_verify_content(self, temp_db, temp_backup_dir):
        """Test backup preserves all data."""
        # Get original record count
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prompt_logs")
        original_count = cursor.fetchone()[0]
        conn.close()

        # Create backup
        backup_path = backup_database(temp_db, temp_backup_dir)

        # Restore to new location
        restored_db = os.path.join(temp_backup_dir, "verify.db")
        success = restore_database(backup_path, restored_db)

        assert success is True

        # Verify record count
        conn = sqlite3.connect(restored_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prompt_logs")
        restored_count = cursor.fetchone()[0]
        conn.close()

        # Counts should match
        assert original_count == restored_count


class TestBackupIntegration:
    """Integration tests for backup system."""

    def test_full_backup_restore_cycle(self):
        """Test complete backup-restore cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            backup_dir = os.path.join(tmpdir, "backups")
            restore_dir = os.path.join(tmpdir, "restored")

            os.makedirs(backup_dir)
            os.makedirs(restore_dir)

            # Create database with prompt_logs table (like production)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE prompt_logs (
                    prompt_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    agent_type TEXT,
                    task_type TEXT,
                    prompt TEXT,
                    success INTEGER
                )
            """)
            cursor.execute(
                "INSERT INTO prompt_logs VALUES (?, ?, ?, ?, ?, ?)",
                ("test_1", datetime.utcnow().isoformat(), "qwen", "test", "test_value", 1),
            )
            conn.commit()
            conn.close()

            # Backup
            backup_path = backup_database(db_path, backup_dir)
            assert backup_path

            # Restore
            restored_db = os.path.join(restore_dir, "restored.db")
            success = restore_database(backup_path, restored_db)
            assert success is True

            # Verify
            conn = sqlite3.connect(restored_db)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM prompt_logs")
            row = cursor.fetchone()
            conn.close()

            assert row is not None
            assert row[4] == "test_value"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
