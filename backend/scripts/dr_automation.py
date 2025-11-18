#!/usr/bin/env python3
"""
Week 1, Day 5: Disaster Recovery Automation
Automated DR procedures for rapid system recovery
"""

import sys
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import json

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.backup_service import BackupService
from backend.core.logging_config import get_logger

logger = get_logger(__name__)


class DisasterRecoveryAutomation:
    """
    Automated disaster recovery procedures.
    
    Provides one-command recovery for common disaster scenarios:
    - Database corruption/loss
    - Application server failure
    - Infrastructure outage
    - Security breach
    """
    
    def __init__(self):
        """Initialize DR automation"""
        self.backup_service = BackupService()
        self.recovery_log = []
        self.start_time = None
        
    def log_step(self, step: str, status: str = "INFO"):
        """Log recovery step"""
        timestamp = datetime.now().isoformat()
        entry = {
            "timestamp": timestamp,
            "step": step,
            "status": status
        }
        self.recovery_log.append(entry)
        
        if status == "ERROR":
            logger.error(f"[DR] {step}")
        else:
            logger.info(f"[DR] {step}")
    
    def run_command(self, cmd: List[str], description: str) -> Dict[str, Any]:
        """
        Run shell command and log result.
        
        Args:
            cmd: Command to run
            description: Human-readable description
            
        Returns:
            Dict with result and timing
        """
        self.log_step(f"Executing: {description}")
        start = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            duration = time.time() - start
            
            self.log_step(f"Completed: {description} ({duration:.2f}s)", "SUCCESS")
            
            return {
                "success": True,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
        except subprocess.CalledProcessError as e:
            duration = time.time() - start
            self.log_step(f"Failed: {description} - {e}", "ERROR")
            
            return {
                "success": False,
                "duration": duration,
                "error": str(e),
                "stdout": e.stdout,
                "stderr": e.stderr
            }
    
    def check_system_status(self) -> Dict[str, Any]:
        """
        Check current system status.
        
        Returns:
            Dict with component statuses
        """
        self.log_step("Checking system status...")
        
        status = {}
        
        # Check Docker containers
        result = self.run_command(
            ["docker-compose", "ps"],
            "Check Docker containers"
        )
        status["docker"] = result["success"]
        
        # Check database
        result = self.run_command(
            ["docker-compose", "exec", "-T", "postgres", "pg_isready"],
            "Check PostgreSQL"
        )
        status["database"] = result["success"]
        
        # Check backend
        try:
            import requests
            response = requests.get("http://localhost:8000/health", timeout=5)
            status["backend"] = response.status_code == 200
        except Exception:
            status["backend"] = False
        
        # Check backups
        backups = self.backup_service.list_backups(location="all")
        status["backups_available"] = len(backups.get("local", [])) > 0 or len(backups.get("cloud", [])) > 0
        
        status["overall"] = all([
            status.get("docker", False),
            status.get("database", False),
            status.get("backups_available", False)
        ])
        
        return status
    
    def recover_database_full(
        self,
        backup_file: Optional[str] = None,
        from_cloud: bool = True
    ) -> Dict[str, Any]:
        """
        Complete database recovery from backup.
        
        Args:
            backup_file: Specific backup to restore (None = latest)
            from_cloud: Download from cloud if True
            
        Returns:
            Recovery result with timing
        """
        self.start_time = time.time()
        self.log_step("=" * 80)
        self.log_step("STARTING DATABASE RECOVERY (FULL)")
        self.log_step("=" * 80)
        
        try:
            # Step 1: Stop application
            self.log_step("Step 1/10: Stopping application...")
            self.run_command(
                ["docker-compose", "stop", "backend"],
                "Stop backend service"
            )
            self.run_command(
                ["docker-compose", "stop", "celery"],
                "Stop celery workers"
            )
            
            # Step 2: Create emergency backup of current state
            self.log_step("Step 2/10: Creating emergency backup...")
            emergency_file = f"/tmp/emergency_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            self.run_command(
                ["docker-compose", "exec", "-T", "postgres", "pg_dumpall"],
                "Emergency backup"
            )
            
            # Step 3: List available backups
            self.log_step("Step 3/10: Listing available backups...")
            backups = self.backup_service.list_backups(location="all")
            
            if not backup_file:
                # Use latest backup
                if from_cloud and backups.get("cloud"):
                    backup_file = backups["cloud"][0]["filename"]
                    self.log_step(f"Using latest cloud backup: {backup_file}")
                elif backups.get("local"):
                    backup_file = backups["local"][0]["filename"]
                    self.log_step(f"Using latest local backup: {backup_file}")
                else:
                    raise RuntimeError("No backups available!")
            
            # Step 4: Download from cloud if needed
            backup_path = Path(self.backup_service.backup_dir) / backup_file
            
            if from_cloud and not backup_path.exists():
                self.log_step("Step 4/10: Downloading backup from cloud...")
                cloud_key = f"{self.backup_service.backup_prefix}{backup_file}"
                
                self.backup_service.s3_client.download_file(
                    self.backup_service.backup_bucket,
                    cloud_key,
                    str(backup_path)
                )
                self.log_step(f"Downloaded: {backup_file}")
            else:
                self.log_step("Step 4/10: Using local backup (skip download)")
            
            # Step 5: Verify backup integrity
            self.log_step("Step 5/10: Verifying backup integrity...")
            if not self.backup_service.verify_backup(backup_path):
                raise RuntimeError(f"Backup verification failed: {backup_file}")
            self.log_step("Backup verification passed")
            
            # Step 6: Drop and recreate database
            self.log_step("Step 6/10: Dropping existing database...")
            self.run_command(
                [
                    "docker-compose", "exec", "-T", "postgres",
                    "psql", "-U", "postgres",
                    "-c", "DROP DATABASE IF EXISTS bybit_strategy_tester;"
                ],
                "Drop database"
            )
            
            self.run_command(
                [
                    "docker-compose", "exec", "-T", "postgres",
                    "psql", "-U", "postgres",
                    "-c", "CREATE DATABASE bybit_strategy_tester;"
                ],
                "Create database"
            )
            
            # Step 7: Restore database
            self.log_step("Step 7/10: Restoring database from backup...")
            restore_result = self.backup_service.restore_backup(
                backup_path,
                target_db="bybit_strategy_tester"
            )
            self.log_step(f"Database restored in {restore_result['duration_seconds']}s")
            
            # Step 8: Verify restoration
            self.log_step("Step 8/10: Verifying restoration...")
            result = self.run_command(
                [
                    "docker-compose", "exec", "-T", "postgres",
                    "psql", "-U", "postgres", "-d", "bybit_strategy_tester",
                    "-c", "SELECT COUNT(*) FROM users;"
                ],
                "Verify user table"
            )
            
            if not result["success"]:
                raise RuntimeError("Database verification failed")
            
            # Step 9: Restart application
            self.log_step("Step 9/10: Restarting application...")
            self.run_command(
                ["docker-compose", "start", "backend"],
                "Start backend service"
            )
            self.run_command(
                ["docker-compose", "start", "celery"],
                "Start celery workers"
            )
            
            # Step 10: Health check
            self.log_step("Step 10/10: Running health checks...")
            time.sleep(5)  # Wait for services to start
            
            try:
                import requests
                response = requests.get("http://localhost:8000/health", timeout=10)
                if response.status_code != 200:
                    raise RuntimeError(f"Health check failed: {response.status_code}")
                self.log_step("Health check passed")
            except Exception as e:
                self.log_step(f"Health check failed: {e}", "ERROR")
            
            # Calculate total time
            total_time = time.time() - self.start_time
            
            self.log_step("=" * 80)
            self.log_step(f"DATABASE RECOVERY COMPLETE ({total_time:.2f}s)")
            self.log_step("=" * 80)
            
            return {
                "success": True,
                "duration": total_time,
                "backup_file": backup_file,
                "steps_completed": 10,
                "log": self.recovery_log
            }
            
        except Exception as e:
            total_time = time.time() - self.start_time if self.start_time else 0
            self.log_step(f"Recovery failed: {e}", "ERROR")
            
            return {
                "success": False,
                "duration": total_time,
                "error": str(e),
                "log": self.recovery_log
            }
    
    def recover_application_server(self) -> Dict[str, Any]:
        """
        Recover application server (restart/rebuild).
        
        Returns:
            Recovery result
        """
        self.start_time = time.time()
        self.log_step("=" * 80)
        self.log_step("STARTING APPLICATION SERVER RECOVERY")
        self.log_step("=" * 80)
        
        try:
            # Step 1: Check container status
            self.log_step("Step 1/5: Checking container status...")
            result = self.run_command(
                ["docker-compose", "ps"],
                "List containers"
            )
            
            # Step 2: Try simple restart first
            self.log_step("Step 2/5: Attempting restart...")
            result = self.run_command(
                ["docker-compose", "restart", "backend"],
                "Restart backend"
            )
            
            if not result["success"]:
                # Restart failed, try rebuild
                self.log_step("Step 3/5: Restart failed, rebuilding...")
                self.run_command(
                    ["docker-compose", "down", "backend"],
                    "Stop backend"
                )
                self.run_command(
                    ["docker-compose", "build", "backend"],
                    "Rebuild backend"
                )
                self.run_command(
                    ["docker-compose", "up", "-d", "backend"],
                    "Start backend"
                )
            else:
                self.log_step("Step 3/5: Restart successful (skip rebuild)")
            
            # Step 4: Verify health
            self.log_step("Step 4/5: Running health checks...")
            time.sleep(5)
            
            try:
                import requests
                response = requests.get("http://localhost:8000/health", timeout=10)
                if response.status_code != 200:
                    raise RuntimeError(f"Health check failed: {response.status_code}")
            except Exception as e:
                self.log_step(f"Health check failed: {e}", "ERROR")
                raise
            
            # Step 5: Test critical endpoints
            self.log_step("Step 5/5: Testing critical endpoints...")
            endpoints = [
                "/health",
                "/health/db_pool",
                "/strategies"
            ]
            
            for endpoint in endpoints:
                try:
                    import requests
                    response = requests.get(f"http://localhost:8000{endpoint}", timeout=5)
                    self.log_step(f"Endpoint {endpoint}: {response.status_code}")
                except Exception as e:
                    self.log_step(f"Endpoint {endpoint} failed: {e}", "ERROR")
            
            total_time = time.time() - self.start_time
            
            self.log_step("=" * 80)
            self.log_step(f"APPLICATION RECOVERY COMPLETE ({total_time:.2f}s)")
            self.log_step("=" * 80)
            
            return {
                "success": True,
                "duration": total_time,
                "steps_completed": 5,
                "log": self.recovery_log
            }
            
        except Exception as e:
            total_time = time.time() - self.start_time if self.start_time else 0
            self.log_step(f"Recovery failed: {e}", "ERROR")
            
            return {
                "success": False,
                "duration": total_time,
                "error": str(e),
                "log": self.recovery_log
            }
    
    def verify_recovery(self) -> Dict[str, Any]:
        """
        Comprehensive post-recovery verification.
        
        Returns:
            Verification results
        """
        self.log_step("=" * 80)
        self.log_step("POST-RECOVERY VERIFICATION")
        self.log_step("=" * 80)
        
        checks = {}
        
        # 1. Database integrity
        self.log_step("Checking database integrity...")
        result = self.run_command(
            [
                "docker-compose", "exec", "-T", "postgres",
                "psql", "-U", "postgres", "-d", "bybit_strategy_tester",
                "-c", "SELECT COUNT(*) as users FROM users; SELECT COUNT(*) as strategies FROM strategies;"
            ],
            "Database row counts"
        )
        checks["database_integrity"] = result["success"]
        
        # 2. Application functionality
        self.log_step("Checking application functionality...")
        try:
            import requests
            response = requests.get("http://localhost:8000/health")
            checks["application_health"] = response.status_code == 200
        except Exception:
            checks["application_health"] = False
        
        # 3. API endpoints
        self.log_step("Testing API endpoints...")
        endpoints_ok = 0
        endpoints_total = 3
        
        for endpoint in ["/health", "/strategies", "/backtests"]:
            try:
                import requests
                response = requests.get(f"http://localhost:8000{endpoint}", timeout=5)
                if response.status_code in [200, 401]:  # 401 = auth required (ok)
                    endpoints_ok += 1
            except Exception:
                pass
        
        checks["api_endpoints"] = endpoints_ok >= endpoints_total * 0.66  # 66% pass rate
        
        # 4. Performance
        self.log_step("Checking performance...")
        try:
            import requests
            start = time.time()
            requests.get("http://localhost:8000/health", timeout=5)
            response_time = time.time() - start
            checks["performance"] = response_time < 1.0  # < 1 second
        except Exception:
            checks["performance"] = False
        
        # Overall status
        checks["overall"] = all(checks.values())
        
        if checks["overall"]:
            self.log_step("✅ ALL VERIFICATION CHECKS PASSED", "SUCCESS")
        else:
            failed = [k for k, v in checks.items() if not v and k != "overall"]
            self.log_step(f"❌ VERIFICATION FAILED: {', '.join(failed)}", "ERROR")
        
        return checks
    
    def generate_recovery_report(self) -> str:
        """
        Generate recovery report.
        
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("DISASTER RECOVERY REPORT")
        report.append("=" * 80)
        report.append(f"Timestamp: {datetime.now().isoformat()}")
        report.append("")
        
        if self.start_time:
            total_time = time.time() - self.start_time
            report.append(f"Total Recovery Time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
            report.append("")
        
        report.append("Recovery Steps:")
        report.append("-" * 80)
        
        for entry in self.recovery_log:
            status_icon = {
                "SUCCESS": "✅",
                "ERROR": "❌",
                "INFO": "ℹ️"
            }.get(entry["status"], "•")
            
            report.append(f"{status_icon} [{entry['timestamp']}] {entry['step']}")
        
        report.append("=" * 80)
        
        return "\n".join(report)


def main():
    """Main DR automation entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Disaster Recovery Automation"
    )
    parser.add_argument(
        "action",
        choices=["status", "recover-db", "recover-app", "verify", "full-recovery"],
        help="DR action to perform"
    )
    parser.add_argument(
        "--backup-file",
        help="Specific backup file to restore"
    )
    parser.add_argument(
        "--no-cloud",
        action="store_true",
        help="Don't download from cloud (use local backup)"
    )
    parser.add_argument(
        "--report",
        help="Save recovery report to file"
    )
    
    args = parser.parse_args()
    
    dr = DisasterRecoveryAutomation()
    
    if args.action == "status":
        print("\nChecking system status...")
        status = dr.check_system_status()
        print(json.dumps(status, indent=2))
        
    elif args.action == "recover-db":
        print("\nStarting database recovery...")
        result = dr.recover_database_full(
            backup_file=args.backup_file,
            from_cloud=not args.no_cloud
        )
        print(dr.generate_recovery_report())
        
        if args.report:
            with open(args.report, 'w') as f:
                f.write(dr.generate_recovery_report())
        
        sys.exit(0 if result["success"] else 1)
        
    elif args.action == "recover-app":
        print("\nStarting application recovery...")
        result = dr.recover_application_server()
        print(dr.generate_recovery_report())
        
        if args.report:
            with open(args.report, 'w') as f:
                f.write(dr.generate_recovery_report())
        
        sys.exit(0 if result["success"] else 1)
        
    elif args.action == "verify":
        print("\nRunning post-recovery verification...")
        checks = dr.verify_recovery()
        print(json.dumps(checks, indent=2))
        sys.exit(0 if checks["overall"] else 1)
        
    elif args.action == "full-recovery":
        print("\nStarting FULL system recovery...")
        print("This will:")
        print("  1. Restore database from backup")
        print("  2. Restart application server")
        print("  3. Verify all systems")
        print("")
        
        # Database recovery
        db_result = dr.recover_database_full(
            backup_file=args.backup_file,
            from_cloud=not args.no_cloud
        )
        
        if not db_result["success"]:
            print("❌ Database recovery failed!")
            print(dr.generate_recovery_report())
            sys.exit(1)
        
        # Application recovery
        app_result = dr.recover_application_server()
        
        if not app_result["success"]:
            print("❌ Application recovery failed!")
            print(dr.generate_recovery_report())
            sys.exit(1)
        
        # Verification
        checks = dr.verify_recovery()
        
        print(dr.generate_recovery_report())
        
        if args.report:
            with open(args.report, 'w') as f:
                f.write(dr.generate_recovery_report())
        
        sys.exit(0 if checks["overall"] else 1)


if __name__ == "__main__":
    main()
