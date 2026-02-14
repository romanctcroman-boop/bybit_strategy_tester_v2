"""
Cost Tracker for Agent API Usage

Canonical cost tracking module for all agent API calls.
Tracks token usage, costs, and budgets per agent with alerting.

This is the single source of truth — ``backend.monitoring.cost_tracker``
has been removed in favour of this module.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger


@dataclass
class CostRecord:
    """Single cost record for an API call."""

    agent: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    reasoning_tokens: int = 0
    cost_usd: float = 0.0
    session_id: str | None = None
    task_type: str | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class CostSummary:
    """Aggregated cost summary for a time period."""

    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_requests: int = 0
    by_agent: dict[str, float] = field(default_factory=dict)
    by_model: dict[str, float] = field(default_factory=dict)
    period_start: str = ""
    period_end: str = ""
    period: str = ""


# Provider cost tables (USD per 1M tokens: input, output)
COST_TABLE: dict[str, dict[str, tuple[float, float]]] = {
    "deepseek": {
        "deepseek-chat": (0.14, 0.28),
        "deepseek-reasoner": (0.55, 2.19),
    },
    "qwen": {
        "qwen-plus": (0.40, 1.20),
        "qwen-flash": (0.05, 0.40),
        "qwen3-max": (1.20, 6.00),
        "qwq-plus": (0.80, 2.40),
    },
    "perplexity": {
        "sonar": (0.20, 0.60),
        "sonar-pro": (0.20, 0.60),
        "sonar-reasoning": (0.20, 0.60),
        "sonar-reasoning-pro": (0.20, 0.60),
        "sonar-deep-research": (0.20, 0.60),
    },
}


class CostTracker:
    """
    Tracks API costs per agent with budgets and alerting.

    Provides both the simple ``record()`` / ``get_summary()`` API used by the
    agent subsystem **and** the period-aware ``get_summary(period=…)`` /
    ``get_daily_breakdown()`` / ``get_recent_records()`` API consumed by the
    cost dashboard.

    Example::

        tracker = CostTracker()
        tracker.record("deepseek", "deepseek-chat", 1000, 500, 1500)
        print(tracker.get_summary())
    """

    # Alert thresholds (also exposed as public attrs for the dashboard)
    HOURLY_ALERT_THRESHOLD: float = 5.0
    DAILY_ALERT_THRESHOLD: float = 50.0

    def __init__(self, daily_budget_usd: float = 50.0, hourly_budget_usd: float = 5.0):
        self.daily_budget_usd = daily_budget_usd
        self.hourly_budget_usd = hourly_budget_usd
        self.HOURLY_ALERT_THRESHOLD = hourly_budget_usd
        self.DAILY_ALERT_THRESHOLD = daily_budget_usd
        self._records: list[CostRecord] = []
        self._agent_totals: dict[str, dict[str, float]] = defaultdict(
            lambda: {"tokens": 0.0, "cost": 0.0, "requests": 0.0}
        )
        self._alerts_sent: dict[str, float] = {}

    # -- recording ---------------------------------------------------------

    def record(
        self,
        agent: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        reasoning_tokens: int = 0,
        cost_usd: float | None = None,
        session_id: str | None = None,
        task_type: str | None = None,
    ) -> CostRecord:
        """Record an API call's cost."""
        if cost_usd is None:
            cost_usd = self._estimate_cost(agent, model, prompt_tokens, completion_tokens)

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

        self._records.append(record)
        self._agent_totals[agent]["tokens"] += total_tokens
        self._agent_totals[agent]["cost"] += cost_usd
        self._agent_totals[agent]["requests"] += 1

        logger.debug(f"💰 Cost recorded: {agent}/{model} ${cost_usd:.6f} ({total_tokens} tokens)")

        self._check_budget_alerts(agent)
        return record

    def record_cost(self, record: CostRecord) -> None:
        """Record a pre-built CostRecord (used by monitoring adapter)."""
        self._records.append(record)
        self._agent_totals[record.agent]["tokens"] += record.total_tokens
        self._agent_totals[record.agent]["cost"] += record.cost_usd
        self._agent_totals[record.agent]["requests"] += 1
        self._check_budget_alerts(record.agent)

    # -- estimation --------------------------------------------------------

    def _estimate_cost(self, agent: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost using provider cost tables."""
        provider_costs = COST_TABLE.get(agent, {})
        rates = provider_costs.get(model)
        if not rates:
            return (prompt_tokens * 0.5 + completion_tokens * 1.5) / 1_000_000
        input_rate, output_rate = rates
        return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000

    # -- alerting ----------------------------------------------------------

    def _check_budget_alerts(self, agent: str) -> None:
        """Check if budget thresholds are exceeded."""
        now = time.time()

        # Hourly check
        hour_ago = now - 3600
        hourly_cost = sum(r.cost_usd for r in self._records if r.agent == agent and r.timestamp > hour_ago)
        if hourly_cost > self.hourly_budget_usd:
            alert_key = f"{agent}_hourly"
            last_alert = self._alerts_sent.get(alert_key, 0)
            if now - last_alert > 300:
                self._alerts_sent[alert_key] = now
                logger.warning(
                    f"💰 BUDGET ALERT: {agent} hourly cost ${hourly_cost:.4f} "
                    f"exceeds ${self.hourly_budget_usd:.2f} limit"
                )

        # Daily check
        day_ago = now - 86400
        daily_cost = sum(r.cost_usd for r in self._records if r.agent == agent and r.timestamp > day_ago)
        if daily_cost > self.daily_budget_usd:
            alert_key = f"{agent}_daily"
            last_alert = self._alerts_sent.get(alert_key, 0)
            if now - last_alert > 3600:
                self._alerts_sent[alert_key] = now
                logger.error(
                    f"🛑 BUDGET EXCEEDED: {agent} daily cost ${daily_cost:.4f} "
                    f"exceeds ${self.daily_budget_usd:.2f} limit"
                )

    # -- summaries (dashboard API) ----------------------------------------

    def get_summary(
        self,
        period: str = "all",
        session_id: str | None = None,
    ) -> CostSummary:
        """Return an aggregated :class:`CostSummary` for *period*.

        Args:
            period: ``'today'``, ``'yesterday'``, ``'hour'``, ``'all'``
            session_id: Narrow results to a single session.
        """
        now = datetime.now()
        records = self._records

        # Filter by session if requested
        if session_id:
            records = [r for r in records if r.session_id == session_id]
            return self._summarize(records, period_label=f"session:{session_id}")

        # Filter by time window
        if period == "today":
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff = start_of_day.timestamp()
            records = [r for r in records if r.timestamp >= cutoff]
            label = now.strftime("%Y-%m-%d")
            return self._summarize(records, period_label=label, period_start=label, period_end=label)

        if period == "yesterday":
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            end = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            records = [r for r in records if start <= r.timestamp < end]
            label = yesterday.strftime("%Y-%m-%d")
            return self._summarize(records, period_label=label, period_start=label, period_end=label)

        if period == "hour":
            cutoff = time.time() - 3600
            records = [r for r in records if r.timestamp >= cutoff]
            label = now.strftime("%Y-%m-%d_%H")
            return self._summarize(records, period_label=label, period_start=label, period_end=label)

        # "all" / default
        return self._summarize(
            records,
            period_label="all-time",
            period_start="all-time",
            period_end=now.isoformat(),
        )

    def _summarize(
        self,
        records: list[CostRecord],
        period_label: str = "",
        period_start: str = "",
        period_end: str = "",
    ) -> CostSummary:
        by_agent: dict[str, float] = defaultdict(float)
        by_model: dict[str, float] = defaultdict(float)
        total_cost = 0.0
        total_tokens = 0

        for r in records:
            total_cost += r.cost_usd
            total_tokens += r.total_tokens
            by_agent[r.agent] += r.cost_usd
            by_model[r.model] += r.cost_usd

        return CostSummary(
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            total_requests=len(records),
            by_agent=dict(by_agent),
            by_model=dict(by_model),
            period=period_label,
            period_start=period_start or period_label,
            period_end=period_end or period_label,
        )

    def get_daily_breakdown(self, days: int = 7) -> list[dict[str, Any]]:
        """Return daily cost breakdown for the last *days* days."""
        breakdown: list[dict[str, Any]] = []
        now = datetime.now()

        for i in range(days):
            day = now - timedelta(days=i)
            start = day.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            end = start + 86400
            day_records = [r for r in self._records if start <= r.timestamp < end]

            if day_records:
                breakdown.append(
                    {
                        "date": day.strftime("%Y-%m-%d"),
                        "total_cost": sum(r.cost_usd for r in day_records),
                        "requests": len(day_records),
                        "tokens": sum(r.total_tokens for r in day_records),
                        "deepseek": sum(r.cost_usd for r in day_records if r.agent == "deepseek"),
                        "perplexity": sum(r.cost_usd for r in day_records if r.agent == "perplexity"),
                    }
                )

        return breakdown

    def get_recent_records(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent *limit* records as dicts."""
        return [asdict(r) for r in self._records[-limit:]]

    def reset_session(self, session_id: str) -> None:
        """Remove all records belonging to *session_id*."""
        self._records = [r for r in self._records if r.session_id != session_id]

    def set_alert_callback(self, callback: Any) -> None:
        """Set callback for cost alerts (not used in in-memory mode)."""
        # Kept for interface compatibility; in-memory tracker uses loguru.
        pass

    def cleanup_old_records(self, max_age_seconds: float = 172800) -> int:
        """Remove records older than *max_age_seconds*. Returns count removed."""
        cutoff = time.time() - max_age_seconds
        before = len(self._records)
        self._records = [r for r in self._records if r.timestamp > cutoff]
        removed = before - len(self._records)
        if removed > 0:
            logger.debug(f"🧹 Cleaned {removed} old cost records")
        return removed


# Singleton
_cost_tracker: CostTracker | None = None


def get_cost_tracker() -> CostTracker:
    """Get global cost tracker singleton."""
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
    """Convenience function to record API cost."""
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
