# -*- coding: utf-8 -*-
"""
Cost Tracker for AI API Usage

Tracks and accumulates costs for DeepSeek and Perplexity API calls.
Stores data in Redis for persistence and fast retrieval.

Features:
- Per-agent cost tracking (deepseek, perplexity)
- Per-session cost tracking
- Daily/hourly aggregation
- Cost alerts when thresholds exceeded
"""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger


@dataclass
class CostRecord:
    """Single cost record for an API call"""

    agent: str  # deepseek, perplexity
    model: str  # deepseek-reasoner, sonar-pro, etc.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0  # DeepSeek V3.2 specific
    cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)
    session_id: str | None = None
    task_type: str | None = None


@dataclass
class CostSummary:
    """Aggregated cost summary"""

    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_requests: int = 0
    by_agent: dict[str, float] = field(default_factory=dict)
    by_model: dict[str, float] = field(default_factory=dict)
    period_start: str = ""
    period_end: str = ""


class CostTracker:
    """
    Tracks API costs across all agents.

    Uses Redis for persistence with sorted sets for time-series data.
    """

    # Redis key prefixes
    COST_RECORDS_KEY = "cost:records"
    COST_DAILY_KEY = "cost:daily"
    COST_HOURLY_KEY = "cost:hourly"
    COST_SESSION_KEY = "cost:session"
    COST_TOTALS_KEY = "cost:totals"

    # Cost alert thresholds (USD)
    HOURLY_ALERT_THRESHOLD = 1.0
    DAILY_ALERT_THRESHOLD = 10.0
    SESSION_ALERT_THRESHOLD = 5.0

    def __init__(self):
        self._redis = None
        self._in_memory_records: list[CostRecord] = []  # Fallback if Redis unavailable
        self._alert_callback: callable | None = None

    def _get_redis(self):
        """Lazy Redis connection"""
        if self._redis is None:
            try:
                import redis

                self._redis = redis.Redis(
                    host="localhost", port=6379, db=0, decode_responses=True
                )
                self._redis.ping()
                logger.debug("✅ Cost tracker connected to Redis")
            except Exception as e:
                logger.warning(f"⚠️ Redis not available for cost tracking: {e}")
                self._redis = None
        return self._redis

    def record_cost(self, record: CostRecord) -> None:
        """
        Record a cost entry from an API call.

        Args:
            record: CostRecord with cost details
        """
        redis = self._get_redis()

        if redis:
            try:
                # Store individual record with timestamp score
                record_data = json.dumps(asdict(record))
                redis.zadd(self.COST_RECORDS_KEY, {record_data: record.timestamp})

                # Update daily totals
                day_key = datetime.fromtimestamp(record.timestamp).strftime("%Y-%m-%d")
                redis.hincrbyfloat(
                    f"{self.COST_DAILY_KEY}:{day_key}", record.agent, record.cost_usd
                )
                redis.hincrbyfloat(
                    f"{self.COST_DAILY_KEY}:{day_key}", "total", record.cost_usd
                )
                redis.hincrby(f"{self.COST_DAILY_KEY}:{day_key}", "requests", 1)
                redis.hincrby(
                    f"{self.COST_DAILY_KEY}:{day_key}", "tokens", record.total_tokens
                )

                # Update hourly totals
                hour_key = datetime.fromtimestamp(record.timestamp).strftime(
                    "%Y-%m-%d_%H"
                )
                redis.hincrbyfloat(
                    f"{self.COST_HOURLY_KEY}:{hour_key}", record.agent, record.cost_usd
                )
                redis.hincrbyfloat(
                    f"{self.COST_HOURLY_KEY}:{hour_key}", "total", record.cost_usd
                )

                # Update session totals if session_id provided
                if record.session_id:
                    redis.hincrbyfloat(
                        f"{self.COST_SESSION_KEY}:{record.session_id}",
                        record.agent,
                        record.cost_usd,
                    )
                    redis.hincrbyfloat(
                        f"{self.COST_SESSION_KEY}:{record.session_id}",
                        "total",
                        record.cost_usd,
                    )

                # Update global totals
                redis.hincrbyfloat(self.COST_TOTALS_KEY, record.agent, record.cost_usd)
                redis.hincrbyfloat(self.COST_TOTALS_KEY, "total", record.cost_usd)
                redis.hincrby(self.COST_TOTALS_KEY, "requests", 1)
                redis.hincrby(self.COST_TOTALS_KEY, "tokens", record.total_tokens)

                # Check alerts
                self._check_alerts(record, redis)

                logger.debug(
                    f"💰 Cost recorded: {record.agent}/{record.model} "
                    f"${record.cost_usd:.6f} ({record.total_tokens} tokens)"
                )

            except Exception as e:
                logger.warning(f"Failed to record cost to Redis: {e}")
                self._in_memory_records.append(record)
        else:
            self._in_memory_records.append(record)

    def _check_alerts(self, record: CostRecord, redis) -> None:
        """Check if cost thresholds exceeded and send notifications"""
        try:
            from backend.monitoring.cost_alerts import send_cost_alert

            # Hourly check
            hour_key = datetime.fromtimestamp(record.timestamp).strftime("%Y-%m-%d_%H")
            hourly_total = float(
                redis.hget(f"{self.COST_HOURLY_KEY}:{hour_key}", "total") or 0
            )
            if hourly_total > self.HOURLY_ALERT_THRESHOLD:
                logger.warning(
                    f"⚠️ COST ALERT: Hourly cost ${hourly_total:.2f} "
                    f"exceeds threshold ${self.HOURLY_ALERT_THRESHOLD}"
                )
                # Send notification via Telegram/Email
                send_cost_alert(
                    alert_type="hourly",
                    current_cost=hourly_total,
                    period=hour_key,
                    agent=record.agent,
                )
                if self._alert_callback:
                    self._alert_callback("hourly", hourly_total)

            # Daily check
            day_key = datetime.fromtimestamp(record.timestamp).strftime("%Y-%m-%d")
            daily_total = float(
                redis.hget(f"{self.COST_DAILY_KEY}:{day_key}", "total") or 0
            )
            if daily_total > self.DAILY_ALERT_THRESHOLD:
                logger.warning(
                    f"⚠️ COST ALERT: Daily cost ${daily_total:.2f} "
                    f"exceeds threshold ${self.DAILY_ALERT_THRESHOLD}"
                )
                # Send notification via Telegram/Email
                send_cost_alert(
                    alert_type="daily",
                    current_cost=daily_total,
                    period=day_key,
                    agent=record.agent,
                )
                if self._alert_callback:
                    self._alert_callback("daily", daily_total)

        except Exception as e:
            logger.debug(f"Alert check failed: {e}")

    def get_summary(
        self, period: str = "today", session_id: str | None = None
    ) -> CostSummary:
        """
        Get cost summary for a period.

        Args:
            period: 'today', 'yesterday', 'week', 'month', 'all', 'hour'
            session_id: Optional session ID for session-specific costs

        Returns:
            CostSummary with aggregated data
        """
        redis = self._get_redis()
        summary = CostSummary()

        now = datetime.now()

        if session_id and redis:
            # Session-specific summary
            session_data = redis.hgetall(f"{self.COST_SESSION_KEY}:{session_id}")
            if session_data:
                summary.total_cost_usd = float(session_data.get("total", 0))
                summary.by_agent = {
                    k: float(v)
                    for k, v in session_data.items()
                    if k not in ("total", "requests", "tokens")
                }
            return summary

        if redis:
            try:
                if period == "today":
                    day_key = now.strftime("%Y-%m-%d")
                    data = redis.hgetall(f"{self.COST_DAILY_KEY}:{day_key}")
                    summary.period_start = day_key
                    summary.period_end = day_key

                elif period == "yesterday":
                    day_key = (now - timedelta(days=1)).strftime("%Y-%m-%d")
                    data = redis.hgetall(f"{self.COST_DAILY_KEY}:{day_key}")
                    summary.period_start = day_key
                    summary.period_end = day_key

                elif period == "hour":
                    hour_key = now.strftime("%Y-%m-%d_%H")
                    data = redis.hgetall(f"{self.COST_HOURLY_KEY}:{hour_key}")
                    summary.period_start = hour_key
                    summary.period_end = hour_key

                elif period == "all":
                    data = redis.hgetall(self.COST_TOTALS_KEY)
                    summary.period_start = "all-time"
                    summary.period_end = now.isoformat()

                else:
                    data = redis.hgetall(self.COST_TOTALS_KEY)

                if data:
                    summary.total_cost_usd = float(data.get("total", 0))
                    summary.total_tokens = int(data.get("tokens", 0))
                    summary.total_requests = int(data.get("requests", 0))
                    summary.by_agent = {
                        k: float(v)
                        for k, v in data.items()
                        if k not in ("total", "requests", "tokens")
                    }

            except Exception as e:
                logger.warning(f"Failed to get cost summary: {e}")

        else:
            # In-memory fallback
            for record in self._in_memory_records:
                summary.total_cost_usd += record.cost_usd
                summary.total_tokens += record.total_tokens
                summary.total_requests += 1
                summary.by_agent[record.agent] = (
                    summary.by_agent.get(record.agent, 0) + record.cost_usd
                )

        return summary

    def get_recent_records(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent cost records"""
        redis = self._get_redis()

        if redis:
            try:
                records = redis.zrevrange(self.COST_RECORDS_KEY, 0, limit - 1)
                return [json.loads(r) for r in records]
            except Exception as e:
                logger.warning(f"Failed to get recent records: {e}")

        # In-memory fallback
        return [asdict(r) for r in self._in_memory_records[-limit:]]

    def get_daily_breakdown(self, days: int = 7) -> list[dict[str, Any]]:
        """Get daily cost breakdown for the last N days"""
        redis = self._get_redis()
        breakdown = []

        if redis:
            try:
                for i in range(days):
                    day = datetime.now() - timedelta(days=i)
                    day_key = day.strftime("%Y-%m-%d")
                    data = redis.hgetall(f"{self.COST_DAILY_KEY}:{day_key}")

                    if data:
                        breakdown.append(
                            {
                                "date": day_key,
                                "total_cost": float(data.get("total", 0)),
                                "requests": int(data.get("requests", 0)),
                                "tokens": int(data.get("tokens", 0)),
                                "deepseek": float(data.get("deepseek", 0)),
                                "perplexity": float(data.get("perplexity", 0)),
                            }
                        )
            except Exception as e:
                logger.warning(f"Failed to get daily breakdown: {e}")

        return breakdown

    def set_alert_callback(self, callback: callable) -> None:
        """Set callback function for cost alerts"""
        self._alert_callback = callback

    def reset_session(self, session_id: str) -> None:
        """Reset costs for a session"""
        redis = self._get_redis()
        if redis:
            redis.delete(f"{self.COST_SESSION_KEY}:{session_id}")


# Global instance
_cost_tracker: CostTracker | None = None


def get_cost_tracker() -> CostTracker:
    """Get global cost tracker instance"""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker


def record_api_cost(
    agent: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: float,
    reasoning_tokens: int = 0,
    session_id: str | None = None,
    task_type: str | None = None,
) -> None:
    """Convenience function to record API cost"""
    tracker = get_cost_tracker()
    record = CostRecord(
        agent=agent,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        reasoning_tokens=reasoning_tokens,
        cost_usd=cost_usd,
        session_id=session_id,
        task_type=task_type,
    )
    tracker.record_cost(record)
