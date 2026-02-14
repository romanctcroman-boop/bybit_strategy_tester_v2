"""
Cost Tracker for Agent API Usage

Tracks token usage, costs, and budgets per agent with alerting.
Addresses audit finding: "No cost tracking per agent" (DeepSeek, P2)
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
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


# Provider cost tables (USD per 1M tokens)
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

    Example:
        tracker = CostTracker()
        tracker.record("deepseek", "deepseek-chat", 1000, 500, 1500)
        print(tracker.get_summary())
    """

    def __init__(self, daily_budget_usd: float = 50.0, hourly_budget_usd: float = 5.0):
        self.daily_budget_usd = daily_budget_usd
        self.hourly_budget_usd = hourly_budget_usd
        self._records: list[CostRecord] = []
        self._agent_totals: dict[str, dict[str, float]] = defaultdict(
            lambda: {"tokens": 0.0, "cost": 0.0, "requests": 0.0}
        )
        self._alerts_sent: dict[str, float] = {}

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

        # Check budgets
        self._check_budget_alerts(agent)

        return record

    def _estimate_cost(self, agent: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost using provider cost tables."""
        provider_costs = COST_TABLE.get(agent, {})
        rates = provider_costs.get(model)
        if not rates:
            # Default estimate
            return (prompt_tokens * 0.5 + completion_tokens * 1.5) / 1_000_000

        input_rate, output_rate = rates
        return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000

    def _check_budget_alerts(self, agent: str) -> None:
        """Check if budget thresholds are exceeded."""
        now = time.time()

        # Hourly check
        hour_ago = now - 3600
        hourly_cost = sum(r.cost_usd for r in self._records if r.agent == agent and r.timestamp > hour_ago)
        if hourly_cost > self.hourly_budget_usd:
            alert_key = f"{agent}_hourly"
            last_alert = self._alerts_sent.get(alert_key, 0)
            if now - last_alert > 300:  # Max once per 5 min
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

    def get_summary(self) -> dict[str, Any]:
        """Get cost summary across all agents."""
        now = time.time()
        hour_ago = now - 3600
        day_ago = now - 86400

        summary: dict[str, Any] = {
            "total_cost_usd": round(sum(r.cost_usd for r in self._records), 4),
            "total_tokens": sum(r.total_tokens for r in self._records),
            "total_requests": len(self._records),
            "agents": {},
        }

        for agent, totals in self._agent_totals.items():
            hourly_cost = sum(r.cost_usd for r in self._records if r.agent == agent and r.timestamp > hour_ago)
            daily_cost = sum(r.cost_usd for r in self._records if r.agent == agent and r.timestamp > day_ago)
            summary["agents"][agent] = {
                "total_cost_usd": round(totals["cost"], 4),
                "total_tokens": int(totals["tokens"]),
                "total_requests": int(totals["requests"]),
                "hourly_cost_usd": round(hourly_cost, 4),
                "daily_cost_usd": round(daily_cost, 4),
                "hourly_budget_remaining": round(max(0, self.hourly_budget_usd - hourly_cost), 4),
                "daily_budget_remaining": round(max(0, self.daily_budget_usd - daily_cost), 4),
            }

        return summary

    def cleanup_old_records(self, max_age_seconds: float = 172800) -> int:
        """Remove records older than max_age_seconds. Returns count removed."""
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


def record_api_cost(**kwargs: Any) -> None:
    """Convenience function to record API cost."""
    tracker = get_cost_tracker()
    tracker.record(**kwargs)
