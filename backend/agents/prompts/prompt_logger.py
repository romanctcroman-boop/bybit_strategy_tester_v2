"""
Prompt Logger for AI Agent Requests

Logs prompts and responses for:
- Debugging and troubleshooting
- Audit trails
- Cost tracking
- Performance analysis

Usage:
    logger = PromptLogger()
    prompt_id = logger.log_prompt(agent_type="qwen", task_type="strategy", prompt="...")
    logger.log_response(prompt_id, response="...", tokens=1000, cost=0.01)
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from loguru import logger


@dataclass
class PromptLogEntry:
    """Log entry for a prompt."""

    prompt_id: str
    timestamp: datetime
    agent_type: str
    task_type: str
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    response: str | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None
    duration_ms: float | None = None
    success: bool = True
    error_message: str | None = None


class PromptLogger:
    """
    Logs prompts and responses for AI agent requests.

    Features:
    - SQLite storage for persistence
    - Search and filter capabilities
    - Cost tracking
    - Performance metrics

    Example:
        logger = PromptLogger()
        prompt_id = logger.log_prompt(
            agent_type="qwen",
            task_type="strategy_generation",
            prompt="Generate RSI strategy",
            context={"symbol": "BTCUSDT"}
        )
        logger.log_response(prompt_id, response="...", tokens=1000, cost=0.01)
    """

    def __init__(
        self,
        db_path: str | None = None,
        retention_days: int = 30,
        auto_create_db: bool = True,
    ):
        """
        Initialize prompt logger.

        Args:
            db_path: Path to SQLite database (default: data/prompt_logs.db)
            retention_days: Days to keep logs (default: 30)
            auto_create_db: Create database if not exists (default: True)
        """
        if db_path is None:
            db_path = "data/prompt_logs.db"

        self.db_path = Path(db_path)
        self.retention_days = retention_days

        if auto_create_db:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_database()

        logger.info(f"📝 PromptLogger initialized (db={db_path}, retention={retention_days}d)")

    def _init_database(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_logs (
                prompt_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                task_type TEXT NOT NULL,
                prompt TEXT NOT NULL,
                context TEXT,
                response TEXT,
                tokens_used INTEGER,
                cost_usd REAL,
                duration_ms REAL,
                success INTEGER DEFAULT 1,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for fast searching
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_type ON prompt_logs(agent_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_type ON prompt_logs(task_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON prompt_logs(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_success ON prompt_logs(success)
        """)

        conn.commit()
        conn.close()

        logger.debug(f"📝 Database initialized: {self.db_path}")

    def log_prompt(
        self,
        agent_type: str,
        task_type: str,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Log a prompt before sending to LLM.

        Args:
            agent_type: Agent type (qwen, deepseek, perplexity)
            task_type: Task type (strategy_generation, optimization, etc.)
            prompt: Prompt text
            context: Additional context dict

        Returns:
            Prompt ID for later response logging
        """
        prompt_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO prompt_logs 
            (prompt_id, timestamp, agent_type, task_type, prompt, context)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                prompt_id,
                timestamp,
                agent_type,
                task_type,
                prompt,
                json.dumps(context or {}),
            ),
        )

        conn.commit()
        conn.close()

        logger.debug(f"📝 Logged prompt {prompt_id[:8]}... ({agent_type}/{task_type})")

        return prompt_id

    def log_response(
        self,
        prompt_id: str,
        response: str,
        tokens_used: int | None = None,
        cost_usd: float | None = None,
        duration_ms: float | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """
        Log response from LLM.

        Args:
            prompt_id: ID from log_prompt()
            response: Response text
            tokens_used: Total tokens used
            cost_usd: Cost in USD
            duration_ms: Request duration in milliseconds
            success: Whether request succeeded
            error_message: Error message if failed
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE prompt_logs SET
                response = ?,
                tokens_used = ?,
                cost_usd = ?,
                duration_ms = ?,
                success = ?,
                error_message = ?
            WHERE prompt_id = ?
            """,
            (
                response,
                tokens_used,
                cost_usd,
                duration_ms,
                1 if success else 0,
                error_message,
                prompt_id,
            ),
        )

        conn.commit()
        conn.close()

        log_type = "✅" if success else "❌"
        logger.debug(f"{log_type} Logged response for {prompt_id[:8]}...")

    def get_log(self, prompt_id: str) -> PromptLogEntry | None:
        """
        Retrieve a log entry by ID.

        Args:
            prompt_id: Prompt ID

        Returns:
            Log entry or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM prompt_logs WHERE prompt_id = ?",
            (prompt_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return self._row_to_entry(row)

    def search_logs(
        self,
        agent_type: str | None = None,
        task_type: str | None = None,
        success: bool | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[PromptLogEntry]:
        """
        Search logs with filters.

        Args:
            agent_type: Filter by agent type
            task_type: Filter by task type
            success: Filter by success status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results (default: 100)

        Returns:
            List of log entries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM prompt_logs WHERE 1=1"
        params: list[Any] = []

        if agent_type:
            query += " AND agent_type = ?"
            params.append(agent_type)

        if task_type:
            query += " AND task_type = ?"
            params.append(task_type)

        if success is not None:
            query += " AND success = ?"
            params.append(1 if success else 0)

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_entry(row) for row in rows]

    def get_stats(
        self,
        days: int = 7,
    ) -> dict[str, Any]:
        """
        Get statistics for recent logs.

        Args:
            days: Number of days to analyze (default: 7)

        Returns:
            Statistics dict
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        start_date = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        # Total count
        cursor.execute(
            "SELECT COUNT(*) FROM prompt_logs WHERE timestamp >= ?",
            (start_date,),
        )
        total_count = cursor.fetchone()[0]

        # Success count
        cursor.execute(
            "SELECT COUNT(*) FROM prompt_logs WHERE timestamp >= ? AND success = 1",
            (start_date,),
        )
        success_count = cursor.fetchone()[0]

        # Total tokens
        cursor.execute(
            "SELECT SUM(tokens_used) FROM prompt_logs WHERE timestamp >= ?",
            (start_date,),
        )
        total_tokens = cursor.fetchone()[0] or 0

        # Total cost
        cursor.execute(
            "SELECT SUM(cost_usd) FROM prompt_logs WHERE timestamp >= ?",
            (start_date,),
        )
        total_cost = cursor.fetchone()[0] or 0.0

        # Average duration
        cursor.execute(
            "SELECT AVG(duration_ms) FROM prompt_logs WHERE timestamp >= ?",
            (start_date,),
        )
        avg_duration = cursor.fetchone()[0] or 0.0

        # By agent type
        cursor.execute(
            """
            SELECT agent_type, COUNT(*), SUM(cost_usd)
            FROM prompt_logs WHERE timestamp >= ?
            GROUP BY agent_type
            """,
            (start_date,),
        )
        by_agent = {row[0]: {"count": row[1], "cost": row[2] or 0.0} for row in cursor.fetchall()}

        # By task type
        cursor.execute(
            """
            SELECT task_type, COUNT(*)
            FROM prompt_logs WHERE timestamp >= ?
            GROUP BY task_type
            """,
            (start_date,),
        )
        by_task = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        return {
            "total_requests": total_count,
            "success_count": success_count,
            "failure_count": total_count - success_count,
            "success_rate": success_count / total_count if total_count > 0 else 0.0,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "avg_duration_ms": avg_duration,
            "by_agent": by_agent,
            "by_task": by_task,
            "period_days": days,
        }

    def cleanup_old_logs(self) -> int:
        """
        Delete logs older than retention period.

        Returns:
            Number of deleted logs
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = (datetime.now(UTC) - timedelta(days=self.retention_days)).isoformat()

        cursor.execute(
            "DELETE FROM prompt_logs WHERE timestamp < ?",
            (cutoff_date,),
        )

        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        logger.info(f"🧹 Cleaned up {deleted} old prompt logs")

        return deleted

    def _row_to_entry(self, row: tuple) -> PromptLogEntry:
        """Convert database row to PromptLogEntry."""
        return PromptLogEntry(
            prompt_id=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            agent_type=row[2],
            task_type=row[3],
            prompt=row[4],
            context=json.loads(row[5]) if row[5] else {},
            response=row[6],
            tokens_used=row[7],
            cost_usd=row[8],
            duration_ms=row[9],
            success=bool(row[10]),
            error_message=row[11],
        )

    def export_logs(
        self,
        output_path: str,
        format: Literal["json", "csv"] = "json",
        **filters: Any,
    ) -> str:
        """
        Export logs to file.

        Args:
            output_path: Output file path
            format: Export format (json or csv)
            **filters: Filters for search_logs()

        Returns:
            Path to exported file
        """
        logs = self.search_logs(**filters)

        if format == "json":
            data = [
                {
                    "prompt_id": log.prompt_id,
                    "timestamp": log.timestamp.isoformat(),
                    "agent_type": log.agent_type,
                    "task_type": log.task_type,
                    "prompt": log.prompt,
                    "context": log.context,
                    "response": log.response,
                    "tokens_used": log.tokens_used,
                    "cost_usd": log.cost_usd,
                    "success": log.success,
                }
                for log in logs
            ]

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        elif format == "csv":
            import csv

            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["prompt_id", "timestamp", "agent_type", "task_type", "tokens_used", "cost_usd", "success"]
                )
                for log in logs:
                    writer.writerow(
                        [
                            log.prompt_id,
                            log.timestamp.isoformat(),
                            log.agent_type,
                            log.task_type,
                            log.tokens_used,
                            log.cost_usd,
                            log.success,
                        ]
                    )

        logger.info(f"📥 Exported {len(logs)} logs to {output_path}")

        return output_path
