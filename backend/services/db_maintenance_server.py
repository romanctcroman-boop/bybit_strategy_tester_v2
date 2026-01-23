"""
Database Maintenance Server - Autonomous Background Service.

This is a standalone server that manages all database maintenance tasks:
- Data freshness monitoring and updates
- Gap detection and repair
- Retention policy enforcement
- Scheduled tasks with persistence
- Action logging and history

Features:
- Runs as autonomous background service
- Persists task schedule and history to SQLite
- Survives restarts - continues where it left off
- RESTful API for monitoring and control
- Comprehensive logging of all actions

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                  DB Maintenance Server                          │
├─────────────────────────────────────────────────────────────────┤
│  Scheduler (APScheduler)                                        │
│  ├── FreshnessCheck (every 5 min)                              │
│  ├── GapRepair (every 6 hours)                                 │
│  ├── RetentionCleanup (monthly)                                │
│  └── Custom tasks (user-defined)                               │
├─────────────────────────────────────────────────────────────────┤
│  Action Logger (SQLite)                                         │
│  └── Logs all operations with timestamps                        │
├─────────────────────────────────────────────────────────────────┤
│  REST API (FastAPI)                                             │
│  ├── GET /status - Service status                              │
│  ├── GET /tasks - List scheduled tasks                         │
│  ├── GET /history - Action history                             │
│  ├── POST /task - Add custom task                              │
│  └── POST /run/{task} - Run task immediately                   │
└─────────────────────────────────────────────────────────────────┘
"""

import json
import logging
import signal
import sqlite3
import sys
import threading
import time

# Windows console UTF-8 encoding for emoji support
if sys.platform == "win32":
    try:
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup logging
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "db_maintenance_server.log", mode="a"),
    ],
)
logger = logging.getLogger("DBMaintenanceServer")


# ============================================================================
# Data Classes
# ============================================================================


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskType(str, Enum):
    """Types of scheduled tasks."""

    FRESHNESS_CHECK = "freshness_check"
    GAP_REPAIR = "gap_repair"
    RETENTION_CLEANUP = "retention_cleanup"
    DB_OPTIMIZE = "db_optimize"
    CUSTOM = "custom"


@dataclass
class ScheduledTask:
    """A scheduled task definition."""

    id: str
    name: str
    task_type: TaskType
    interval_seconds: int
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "task_type": self.task_type.value,
            "interval_seconds": self.interval_seconds,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "config": self.config,
        }


@dataclass
class ActionLog:
    """Log entry for an action."""

    id: Optional[int] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    task_id: str = ""
    task_type: str = ""
    action: str = ""
    status: TaskStatus = TaskStatus.PENDING
    details: str = ""
    duration_ms: int = 0
    affected_rows: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "task_id": self.task_id,
            "task_type": self.task_type,
            "action": self.action,
            "status": self.status.value,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "affected_rows": self.affected_rows,
        }


# ============================================================================
# Persistence Layer (SQLite for task state and history)
# ============================================================================


class MaintenanceDB:
    """SQLite database for task state and action history."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                -- Scheduled tasks table
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    interval_seconds INTEGER NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    last_run TEXT,
                    next_run TEXT,
                    run_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    config TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Action history table
                CREATE TABLE IF NOT EXISTS action_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    task_id TEXT,
                    task_type TEXT,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    duration_ms INTEGER DEFAULT 0,
                    affected_rows INTEGER DEFAULT 0
                );

                -- Create indexes for faster queries
                CREATE INDEX IF NOT EXISTS idx_action_history_timestamp
                    ON action_history(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_action_history_task_id
                    ON action_history(task_id);
                CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_next_run
                    ON scheduled_tasks(next_run);
            """)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get thread-safe database connection."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

    def save_task(self, task: ScheduledTask):
        """Save or update a scheduled task."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO scheduled_tasks
                (id, name, task_type, interval_seconds, enabled, last_run, next_run,
                 run_count, error_count, config, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    task.id,
                    task.name,
                    task.task_type.value,
                    task.interval_seconds,
                    1 if task.enabled else 0,
                    task.last_run.isoformat() if task.last_run else None,
                    task.next_run.isoformat() if task.next_run else None,
                    task.run_count,
                    task.error_count,
                    json.dumps(task.config),
                ),
            )
            conn.commit()

    def get_tasks(self) -> List[ScheduledTask]:
        """Get all scheduled tasks."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM scheduled_tasks ORDER BY name"
            ).fetchall()
            return [self._row_to_task(row) for row in rows]

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a specific task by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return self._row_to_task(row) if row else None

    def _row_to_task(self, row: sqlite3.Row) -> ScheduledTask:
        """Convert database row to ScheduledTask."""
        return ScheduledTask(
            id=row["id"],
            name=row["name"],
            task_type=TaskType(row["task_type"]),
            interval_seconds=row["interval_seconds"],
            enabled=bool(row["enabled"]),
            last_run=datetime.fromisoformat(row["last_run"])
            if row["last_run"]
            else None,
            next_run=datetime.fromisoformat(row["next_run"])
            if row["next_run"]
            else None,
            run_count=row["run_count"],
            error_count=row["error_count"],
            config=json.loads(row["config"]) if row["config"] else {},
        )

    def log_action(self, log: ActionLog) -> int:
        """Log an action to history."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO action_history
                (timestamp, task_id, task_type, action, status, details, duration_ms, affected_rows)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    log.timestamp.isoformat(),
                    log.task_id,
                    log.task_type,
                    log.action,
                    log.status.value,
                    log.details,
                    log.duration_ms,
                    log.affected_rows,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_history(
        self,
        limit: int = 100,
        task_id: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[ActionLog]:
        """Get action history with optional filters."""
        with self._get_connection() as conn:
            query = "SELECT * FROM action_history WHERE 1=1"
            params = []

            if task_id:
                query += " AND task_id = ?"
                params.append(task_id)

            if since:
                query += " AND timestamp >= ?"
                params.append(since.isoformat())

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_log(row) for row in rows]

    def _row_to_log(self, row: sqlite3.Row) -> ActionLog:
        """Convert database row to ActionLog."""
        return ActionLog(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            task_id=row["task_id"],
            task_type=row["task_type"],
            action=row["action"],
            status=TaskStatus(row["status"]),
            details=row["details"],
            duration_ms=row["duration_ms"],
            affected_rows=row["affected_rows"],
        )

    def cleanup_old_history(self, days: int = 30) -> int:
        """Delete history older than N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM action_history WHERE timestamp < ?", (cutoff.isoformat(),)
            )
            conn.commit()
            return cursor.rowcount


# ============================================================================
# Task Executors
# ============================================================================


class TaskExecutors:
    """Collection of task execution functions."""

    def __init__(self, data_db_path: Path):
        self.data_db_path = data_db_path
        self._adapter = None

    def _get_adapter(self):
        """Get or create Bybit adapter."""
        if self._adapter is None:
            try:
                from backend.services.adapters.bybit import BybitAdapter

                self._adapter = BybitAdapter()
            except ImportError:
                logger.error("BybitAdapter not available")
        return self._adapter

    def _get_interval_ms(self, interval: str) -> int:
        """Get interval duration in milliseconds."""
        mapping = {
            "1": 60_000,
            "3": 180_000,
            "5": 300_000,
            "15": 900_000,
            "30": 1_800_000,
            "60": 3_600_000,
            "120": 7_200_000,
            "240": 14_400_000,
            "D": 86_400_000,
            "W": 604_800_000,
        }
        return mapping.get(interval, 60_000)

    def freshness_check(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Check data freshness and AUTO-UPDATE stale data."""
        symbols = config.get("symbols", ["BTCUSDT", "ETHUSDT"])
        intervals = config.get("intervals", ["1", "5", "15", "30", "60", "240", "D"])
        max_age_minutes = config.get(
            "max_age_minutes", {"1": 5, "5": 10, "15": 20, "default": 60}
        )

        results = {
            "checked": 0,
            "stale": 0,
            "updated": 0,
            "candles_added": 0,
            "errors": 0,
            "details": [],
        }

        adapter = self._get_adapter()
        if not adapter:
            results["errors"] += 1
            return results

        try:
            conn = sqlite3.connect(str(self.data_db_path))
            c = conn.cursor()
            now = datetime.now(timezone.utc)
            now_ts = int(now.timestamp() * 1000)

            for symbol in symbols:
                for interval in intervals:
                    try:
                        # Get newest candle
                        c.execute(
                            """
                            SELECT MAX(open_time) FROM bybit_kline_audit
                            WHERE symbol = ? AND interval = ?
                        """,
                            (symbol, interval),
                        )
                        row = c.fetchone()

                        if not row or not row[0]:
                            continue

                        results["checked"] += 1
                        newest_ts = row[0]
                        age_minutes = (now_ts - newest_ts) / 60000

                        # Get max age for this interval
                        max_age = max_age_minutes.get(
                            interval, max_age_minutes.get("default", 60)
                        )

                        if age_minutes > max_age:
                            results["stale"] += 1

                            # AUTO-UPDATE: Fetch missing candles from API
                            try:
                                candles_added = self._update_stale_data(
                                    conn,
                                    c,
                                    adapter,
                                    symbol,
                                    interval,
                                    newest_ts,
                                    now_ts,
                                )
                                results["candles_added"] += candles_added

                                if candles_added > 0:
                                    results["updated"] += 1
                                    results["details"].append(
                                        {
                                            "symbol": symbol,
                                            "interval": interval,
                                            "age_minutes": round(age_minutes, 1),
                                            "candles_added": candles_added,
                                            "status": "updated",
                                        }
                                    )
                                else:
                                    results["details"].append(
                                        {
                                            "symbol": symbol,
                                            "interval": interval,
                                            "age_minutes": round(age_minutes, 1),
                                            "status": "no_new_data",
                                        }
                                    )
                            except Exception as e:
                                results["errors"] += 1
                                logger.warning(
                                    f"Auto-update failed for {symbol}:{interval}: {e}"
                                )
                                results["details"].append(
                                    {
                                        "symbol": symbol,
                                        "interval": interval,
                                        "age_minutes": round(age_minutes, 1),
                                        "status": "update_failed",
                                        "error": str(e),
                                    }
                                )

                    except Exception as e:
                        results["errors"] += 1
                        logger.warning(
                            f"Freshness check failed for {symbol}:{interval}: {e}"
                        )

            conn.close()

        except Exception as e:
            results["errors"] += 1
            logger.error(f"Freshness check failed: {e}")

        if results["candles_added"] > 0:
            logger.info(
                f"✅ Auto-updated {results['updated']} intervals, added {results['candles_added']} candles"
            )

        return results

    def _update_stale_data(
        self,
        conn: sqlite3.Connection,
        cursor: sqlite3.Cursor,
        adapter,
        symbol: str,
        interval: str,
        last_ts: int,
        now_ts: int,
    ) -> int:
        """Fetch and insert missing candles."""
        all_candles = []
        end_ts = now_ts

        # Fetch in batches until we reach last_ts
        max_iterations = 10  # Safety limit
        for _ in range(max_iterations):
            try:
                candles = adapter.get_klines_before(
                    symbol=symbol,
                    interval=interval,
                    end_time=end_ts,
                    limit=500,
                )

                if not candles:
                    break

                # Filter only new candles
                new_candles = [c for c in candles if c["open_time"] > last_ts]
                all_candles.extend(new_candles)

                # If we got older candles than last_ts, we're done
                oldest = min(c["open_time"] for c in candles)
                if oldest <= last_ts:
                    break

                end_ts = oldest
                time.sleep(0.1)  # Rate limit

            except Exception as e:
                logger.warning(f"API fetch failed: {e}")
                break

        if not all_candles:
            return 0

        # Insert candles
        inserted = 0
        for candle in all_candles:
            try:
                open_dt = datetime.fromtimestamp(
                    candle["open_time"] / 1000, tz=timezone.utc
                )
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO bybit_kline_audit
                    (symbol, interval, open_time, open_time_dt, open_price, high_price,
                     low_price, close_price, volume, turnover, raw)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        symbol,
                        interval,
                        candle["open_time"],
                        open_dt.isoformat(),
                        candle["open"],
                        candle["high"],
                        candle["low"],
                        candle["close"],
                        candle["volume"],
                        candle["turnover"],
                        json.dumps(
                            {
                                k: (v.isoformat() if isinstance(v, datetime) else v)
                                for k, v in candle.items()
                            }
                        ),
                    ),
                )
                inserted += cursor.rowcount
            except Exception as e:
                logger.warning(f"Insert failed: {e}")

        conn.commit()
        logger.debug(f"Inserted {inserted} candles for {symbol}:{interval}")
        return inserted

    def gap_repair(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Detect and repair data gaps."""
        symbols = config.get("symbols", ["BTCUSDT", "ETHUSDT"])
        intervals = config.get("intervals", ["5", "15", "30", "60", "240", "D"])
        max_gaps_per_run = config.get("max_gaps", 10)

        results = {"gaps_found": 0, "gaps_repaired": 0, "errors": 0, "details": []}

        try:
            from backend.services.data_gap_repair import DataGapRepairService

            repair_service = DataGapRepairService()

            for symbol in symbols:
                for interval in intervals:
                    try:
                        summary = repair_service.get_repair_summary(symbol, interval)

                        if summary.get("needs_repair"):
                            gaps = summary.get("data_gaps", 0)
                            results["gaps_found"] += gaps

                            # Attempt repair
                            repaired = repair_service.repair_all_gaps(
                                symbol, interval, max_gaps=max_gaps_per_run
                            )
                            results["gaps_repaired"] += repaired

                            results["details"].append(
                                {
                                    "symbol": symbol,
                                    "interval": interval,
                                    "gaps_found": gaps,
                                    "gaps_repaired": repaired,
                                }
                            )

                    except Exception as e:
                        results["errors"] += 1
                        logger.warning(
                            f"Gap repair failed for {symbol}:{interval}: {e}"
                        )

        except ImportError:
            results["errors"] += 1
            logger.error("DataGapRepairService not available")
        except Exception as e:
            results["errors"] += 1
            logger.error(f"Gap repair failed: {e}")

        return results

    def retention_cleanup(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Enforce retention policy - delete old data."""
        retention_years = config.get("retention_years", 2)

        results = {"deleted": 0, "errors": 0, "cutoff_date": None}

        try:
            now = datetime.now(timezone.utc)
            cutoff_year = now.year - retention_years + 1
            cutoff_date = datetime(cutoff_year, 1, 1, tzinfo=timezone.utc)
            cutoff_ts = int(cutoff_date.timestamp() * 1000)

            results["cutoff_date"] = cutoff_date.strftime("%Y-%m-%d")

            conn = sqlite3.connect(str(self.data_db_path))
            c = conn.cursor()

            # Count and delete old records
            c.execute(
                "SELECT COUNT(*) FROM bybit_kline_audit WHERE open_time < ?",
                (cutoff_ts,),
            )
            to_delete = c.fetchone()[0]

            if to_delete > 0:
                # Delete in batches
                batch_size = 50000
                total_deleted = 0

                while True:
                    c.execute(
                        """
                        DELETE FROM bybit_kline_audit
                        WHERE id IN (
                            SELECT id FROM bybit_kline_audit
                            WHERE open_time < ?
                            LIMIT ?
                        )
                    """,
                        (cutoff_ts, batch_size),
                    )
                    conn.commit()

                    deleted = c.rowcount
                    if deleted == 0:
                        break
                    total_deleted += deleted

                results["deleted"] = total_deleted
                logger.info(f"Retention cleanup: deleted {total_deleted:,} old candles")

            conn.close()

        except Exception as e:
            results["errors"] += 1
            logger.error(f"Retention cleanup failed: {e}")

        return results

    def db_optimize(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run database optimization: VACUUM and ANALYZE."""
        results = {
            "vacuum": False,
            "analyze": False,
            "size_before_mb": 0,
            "size_after_mb": 0,
            "space_freed_mb": 0,
            "errors": 0,
        }

        try:
            # Get size before
            results["size_before_mb"] = round(
                self.data_db_path.stat().st_size / (1024 * 1024), 2
            )

            conn = sqlite3.connect(str(self.data_db_path))
            c = conn.cursor()

            # Check fragmentation
            c.execute("PRAGMA page_count")
            pages = c.fetchone()[0]
            c.execute("PRAGMA freelist_count")
            free = c.fetchone()[0]
            fragmentation = (free / pages * 100) if pages > 0 else 0

            # Only VACUUM if fragmentation > 5%
            if fragmentation > 5 or config.get("force_vacuum", False):
                logger.info(f"Running VACUUM (fragmentation: {fragmentation:.1f}%)")
                c.execute("VACUUM")
                results["vacuum"] = True
            else:
                logger.info(f"Skipping VACUUM (fragmentation: {fragmentation:.1f}%)")

            # Always run ANALYZE to update statistics
            c.execute("ANALYZE")
            results["analyze"] = True

            conn.close()

            # Get size after
            results["size_after_mb"] = round(
                self.data_db_path.stat().st_size / (1024 * 1024), 2
            )
            results["space_freed_mb"] = round(
                results["size_before_mb"] - results["size_after_mb"], 2
            )

            logger.info(
                f"DB optimization complete: VACUUM={results['vacuum']}, "
                f"freed {results['space_freed_mb']} MB"
            )

        except Exception as e:
            results["errors"] += 1
            logger.error(f"DB optimization failed: {e}")

        return results


# ============================================================================
# Scheduler
# ============================================================================


class TaskScheduler:
    """Simple task scheduler with persistence."""

    def __init__(self, db: MaintenanceDB, executors: TaskExecutors):
        self.db = db
        self.executors = executors
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self):
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Task scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Task scheduler stopped")

    def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                self._check_and_run_tasks()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            # Check every 30 seconds
            self._stop_event.wait(timeout=30)

    def _check_and_run_tasks(self):
        """Check for due tasks and run them."""
        now = datetime.now(timezone.utc)
        tasks = self.db.get_tasks()

        for task in tasks:
            if not task.enabled:
                continue

            # Check if task is due
            if task.next_run and now < task.next_run:
                continue

            # Run the task
            self._execute_task(task)

    def _execute_task(self, task: ScheduledTask):
        """Execute a single task."""
        start_time = time.time()
        now = datetime.now(timezone.utc)

        # Log start
        log = ActionLog(
            task_id=task.id,
            task_type=task.task_type.value,
            action=f"Running {task.name}",
            status=TaskStatus.RUNNING,
        )
        self.db.log_action(log)

        try:
            logger.info(f"▶ Running task: {task.name}")

            # Execute based on task type
            if task.task_type == TaskType.FRESHNESS_CHECK:
                result = self.executors.freshness_check(task.config)
            elif task.task_type == TaskType.GAP_REPAIR:
                result = self.executors.gap_repair(task.config)
            elif task.task_type == TaskType.RETENTION_CLEANUP:
                result = self.executors.retention_cleanup(task.config)
            elif task.task_type == TaskType.DB_OPTIMIZE:
                result = self.executors.db_optimize(task.config)
            else:
                result = {"error": "Unknown task type"}

            # Update task
            task.last_run = now
            task.next_run = now + timedelta(seconds=task.interval_seconds)
            task.run_count += 1

            # Log completion
            duration_ms = int((time.time() - start_time) * 1000)
            affected_rows = result.get("deleted", 0) + result.get("gaps_repaired", 0)

            log.status = TaskStatus.COMPLETED
            log.details = json.dumps(result)
            log.duration_ms = duration_ms
            log.affected_rows = affected_rows
            self.db.log_action(log)

            logger.info(f"✓ Task completed: {task.name} ({duration_ms}ms)")

        except Exception as e:
            task.error_count += 1
            task.last_run = now
            task.next_run = now + timedelta(seconds=task.interval_seconds)

            log.status = TaskStatus.FAILED
            log.details = str(e)
            log.duration_ms = int((time.time() - start_time) * 1000)
            self.db.log_action(log)

            logger.error(f"✗ Task failed: {task.name} - {e}")

        # Save updated task state
        self.db.save_task(task)

    def run_task_now(self, task_id: str) -> Optional[Dict]:
        """Run a specific task immediately."""
        task = self.db.get_task(task_id)
        if not task:
            return None

        self._execute_task(task)
        return task.to_dict()


# ============================================================================
# REST API
# ============================================================================


def create_api(server: "DBMaintenanceServer"):
    """Create FastAPI application for the server."""
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError:
        logger.warning("FastAPI not available, API disabled")
        return None

    app = FastAPI(
        title="DB Maintenance Server",
        description="Autonomous database maintenance service",
        version="1.0.0",
    )

    @app.get("/")
    def root():
        return {"service": "DB Maintenance Server", "status": "running"}

    @app.get("/status")
    def get_status():
        return server.get_status()

    @app.get("/tasks")
    def get_tasks():
        tasks = server.db.get_tasks()
        return {"tasks": [t.to_dict() for t in tasks]}

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str):
        task = server.db.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.to_dict()

    @app.post("/tasks/{task_id}/run")
    def run_task(task_id: str):
        result = server.scheduler.run_task_now(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"message": "Task executed", "task": result}

    @app.post("/tasks/{task_id}/enable")
    def enable_task(task_id: str):
        task = server.db.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        task.enabled = True
        server.db.save_task(task)
        return {"message": "Task enabled", "task": task.to_dict()}

    @app.post("/tasks/{task_id}/disable")
    def disable_task(task_id: str):
        task = server.db.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        task.enabled = False
        server.db.save_task(task)
        return {"message": "Task disabled", "task": task.to_dict()}

    @app.get("/history")
    def get_history(limit: int = 100, task_id: Optional[str] = None):
        history = server.db.get_history(limit=limit, task_id=task_id)
        return {"history": [h.to_dict() for h in history]}

    @app.get("/health")
    def health_check():
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return app


# ============================================================================
# Main Server
# ============================================================================


class DBMaintenanceServer:
    """Main database maintenance server."""

    DEFAULT_TASKS = [
        ScheduledTask(
            id="freshness_check",
            name="Data Freshness Check",
            task_type=TaskType.FRESHNESS_CHECK,
            interval_seconds=300,  # 5 minutes
            config={
                "symbols": ["BTCUSDT", "ETHUSDT"],
                "intervals": ["1", "5", "15", "30", "60", "240", "D"],
                "max_age_minutes": {"1": 5, "5": 10, "15": 20, "default": 60},
            },
        ),
        ScheduledTask(
            id="gap_repair",
            name="Gap Detection & Repair",
            task_type=TaskType.GAP_REPAIR,
            interval_seconds=21600,  # 6 hours
            config={
                "symbols": ["BTCUSDT", "ETHUSDT"],
                "intervals": ["5", "15", "30", "60", "240", "D"],
                "max_gaps": 10,
            },
        ),
        ScheduledTask(
            id="retention_cleanup",
            name="Retention Policy Cleanup",
            task_type=TaskType.RETENTION_CLEANUP,
            interval_seconds=2592000,  # 30 days
            config={"retention_years": 2},
        ),
        ScheduledTask(
            id="db_optimize",
            name="Database Optimization (VACUUM/ANALYZE)",
            task_type=TaskType.DB_OPTIMIZE,
            interval_seconds=604800,  # 7 days (weekly)
            config={"force_vacuum": False},
        ),
    ]

    def __init__(
        self,
        maintenance_db_path: Optional[Path] = None,
        data_db_path: Optional[Path] = None,
        api_port: int = 8001,
    ):
        self.maintenance_db_path = (
            maintenance_db_path or PROJECT_ROOT / "data" / "maintenance.sqlite3"
        )
        self.data_db_path = data_db_path or PROJECT_ROOT / "data.sqlite3"
        self.api_port = api_port

        # Ensure data directory exists
        self.maintenance_db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.db = MaintenanceDB(self.maintenance_db_path)
        self.executors = TaskExecutors(self.data_db_path)
        self.scheduler = TaskScheduler(self.db, self.executors)

        self._running = False
        self._api_thread: Optional[threading.Thread] = None

        # Initialize default tasks if not exist
        self._init_default_tasks()

    def _init_default_tasks(self):
        """Initialize default tasks if they don't exist."""
        existing_tasks = {t.id for t in self.db.get_tasks()}

        for task in self.DEFAULT_TASKS:
            if task.id not in existing_tasks:
                # Set initial next_run to now
                task.next_run = datetime.now(timezone.utc)
                self.db.save_task(task)
                logger.info(f"Initialized default task: {task.name}")

    def get_status(self) -> Dict[str, Any]:
        """Get server status."""
        tasks = self.db.get_tasks()
        recent_history = self.db.get_history(limit=10)

        return {
            "server": "DB Maintenance Server",
            "running": self._running,
            "api_port": self.api_port,
            "maintenance_db": str(self.maintenance_db_path),
            "data_db": str(self.data_db_path),
            "tasks": {
                "total": len(tasks),
                "enabled": sum(1 for t in tasks if t.enabled),
                "list": [t.to_dict() for t in tasks],
            },
            "recent_actions": [h.to_dict() for h in recent_history],
            "uptime": datetime.now(timezone.utc).isoformat(),
        }

    def start(self):
        """Start the server."""
        if self._running:
            logger.warning("Server already running")
            return

        self._running = True
        logger.info("=" * 60)
        logger.info("DB Maintenance Server starting...")
        logger.info(f"  Maintenance DB: {self.maintenance_db_path}")
        logger.info(f"  Data DB: {self.data_db_path}")
        logger.info(f"  API Port: {self.api_port}")
        logger.info("=" * 60)

        # Log startup
        self.db.log_action(
            ActionLog(
                task_id="server",
                task_type="system",
                action="Server started",
                status=TaskStatus.COMPLETED,
            )
        )

        # Start scheduler
        self.scheduler.start()

        # Start API server in background thread
        self._start_api()

        logger.info("✓ Server started successfully")

    def _start_api(self):
        """Start API server in background thread."""
        app = create_api(self)
        if not app:
            return

        def run_api():
            try:
                import uvicorn

                uvicorn.run(
                    app, host="0.0.0.0", port=self.api_port, log_level="warning"
                )
            except Exception as e:
                logger.error(f"API server error: {e}")

        self._api_thread = threading.Thread(target=run_api, daemon=True)
        self._api_thread.start()
        logger.info(f"API server started on http://0.0.0.0:{self.api_port}")

    def stop(self):
        """Stop the server."""
        if not self._running:
            return

        logger.info("Stopping server...")
        self._running = False

        # Stop scheduler
        self.scheduler.stop()

        # Log shutdown
        self.db.log_action(
            ActionLog(
                task_id="server",
                task_type="system",
                action="Server stopped",
                status=TaskStatus.COMPLETED,
            )
        )

        logger.info("Server stopped")

    def run_forever(self):
        """Run the server until interrupted."""
        self.start()

        # Handle signals
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Keep main thread alive
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()


# ============================================================================
# CLI Entry Point
# ============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="DB Maintenance Server")
    parser.add_argument(
        "--port", type=int, default=8001, help="API port (default: 8001)"
    )
    parser.add_argument("--data-db", type=str, help="Path to data database")
    parser.add_argument(
        "--maintenance-db", type=str, help="Path to maintenance database"
    )

    args = parser.parse_args()

    server = DBMaintenanceServer(
        data_db_path=Path(args.data_db) if args.data_db else None,
        maintenance_db_path=Path(args.maintenance_db) if args.maintenance_db else None,
        api_port=args.port,
    )

    server.run_forever()


if __name__ == "__main__":
    main()
